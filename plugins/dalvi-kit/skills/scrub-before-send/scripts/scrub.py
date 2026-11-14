"""Find and remove what an Office file or a PDF carries where the screen doesn't show it.

Subcommands:
  inspect <file> [terms]               report metadata, comments, tracked changes, hidden
                                       slides, notes, alt text, headers, fields, linked
                                       template, external links, hidden sheets... and every
                                       match of the forbidden terms
  clean <src> <dst> [terms] [options]  write a cleaned copy to <dst> (<src> is only read),
                                       then inspect and verify the copy
  verify <file>                        structure: zip, XML, relationships, content types
  selftest [terms]                     plant each term and check the detector finds it

Formats: .docx/.docm/.dotx, .pptx/.pptm/.potx, .xlsx/.xlsm/.xltx, .pdf.

Terms: --term TEXT (repeatable) and --terms-file FILE (one per line, '#' starts a
comment). Matching ignores case and accents and treats any run of whitespace as
one space. Terms of up to 4 letters or digits ("BV") match whole words only;
'word:TEXT' forces whole words, 'regex:PATTERN' takes a regular expression (give a
sample with --plant so the self-test can check it). Every run that has terms
plants each one first (split across two runs, in an attribute, percent-encoded,
without accents) and stops if the detector misses it: a zero is only trusted after
that.

Clean options: --replace "OLD=NEW" (repeatable; NEW may be empty), --author TEXT
(default: empty), --title TEXT, --subject TEXT, --company TEXT, --keep CATEGORIES
(comma-separated: metadata, custom, template, comments, revisions, hidden-slides,
notes, fields, thumbnail, media-metadata, orphans).

Exit codes: 0 ok; 1 verify failed; 2 term hits or findings left; 3 self-test failed;
4 cannot do it here (missing pypdf, bad arguments, unsupported file).

Standard library only, except PDF: inspect works without pypdf (weaker), clean
needs pypdf.
"""
import argparse
import io
import posixpath
import re
import struct
import sys
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

OFFICE = {".docx": "docx", ".docm": "docx", ".dotx": "docx", ".dotm": "docx",
          ".pptx": "pptx", ".pptm": "pptx", ".potx": "pptx", ".potm": "pptx",
          ".xlsx": "xlsx", ".xlsm": "xlsx", ".xltx": "xlsx", ".xltm": "xlsx"}
CATEGORIES = ["metadata", "custom", "template", "comments", "revisions", "hidden-slides", "notes",
              "fields", "thumbnail", "media-metadata", "orphans"]
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships/"
FIELD_TYPES = ("INCLUDEPICTURE", "INCLUDETEXT", "LINK", "IMPORT", "DDE", "DDEAUTO")
LOCAL_PATH = re.compile(r'(?i)^(file:|[a-z]:[\\/]|\\\\|/(users|home|volumes|private|var|tmp)/)')


def out(line=""):
    sys.stdout.write(line + "\n")


def short(s, n=160):
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def fail(msg):
    """Stop with exit code 4: the job can't be done as asked."""
    sys.stderr.write(msg + "\n")
    sys.exit(4)


# ---------------------------------------------------------------- terms

def fold(s):
    """Strip accents one character at a time, so positions stay the same."""
    return "".join(unicodedata.normalize("NFD", c)[0] if c.isalpha() else c for c in s)


class Term:
    def __init__(self, raw):
        self.raw = raw
        if any(ord(c) < 32 for c in raw):
            fail(f"term {raw!r} contains a control character: the shell probably turned "
                             "'\\b' or similar into one. Put the terms in a file (--terms-file).")
        self.regex = raw.startswith("regex:")
        if self.regex:
            body = fold(raw[6:])
        else:
            text = raw[5:] if raw.startswith("word:") else raw
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                fail(f"empty term {raw!r}")
            self.text = text
            body = r"\s+".join(re.escape(fold(w)) for w in text.split(" "))
            alnum = re.sub(r"\W", "", text)
            if raw.startswith("word:") or len(alnum) <= 4:
                body = rf"(?<![^\W_]){body}(?![^\W_])"
        try:
            self.rx = re.compile(body, re.I)
        except re.error as e:
            fail(f"term {raw!r} is not a valid regular expression: {e}")
        if self.rx.search(""):
            fail(f"term {raw!r} matches the empty string")

    def finditer(self, text):
        return self.rx.finditer(fold(text))


def load_terms(args):
    raws = list(args.term or [])
    for f in args.terms_file or []:
        for line in Path(f).read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                raws.append(line)
    for spec in getattr(args, "replace", None) or []:
        old = spec.split("=", 1)[0]
        if old and old not in raws:
            raws.append(old)
    seen, terms = set(), []
    for r in raws:
        if r not in seen:
            seen.add(r)
            terms.append(Term(r))
    # Longest first, so "Acme Corp" is handled before "Acme".
    return sorted(terms, key=lambda t: -len(t.raw))


def matches(terms, text):
    """[(term, start, end)] without overlaps, longest term first."""
    found, taken = [], []
    for t in terms:
        for m in t.finditer(text):
            if m.end() > m.start() and not any(m.start() < e and s < m.end() for s, e in taken):
                found.append((t, m.start(), m.end()))
                taken.append((m.start(), m.end()))
    return sorted(found, key=lambda x: x[1])


# ---------------------------------------------------------------- XML token walker

TOKEN = re.compile(r"<!--.*?-->|<\?.*?\?>|<!\[CDATA\[.*?\]\]>|<![^>]*>|<[^>]*>|[^<]+", re.S)
ATTR = re.compile(r'([\w:.-]+)(\s*=\s*)("([^"]*)"|\'([^\']*)\')')
ENTITY = re.compile(r"&(#x[0-9a-fA-F]+|#[0-9]+|amp|lt|gt|quot|apos);")
NAMED = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}
PARA = {"p", "si", "is"}           # w:p, a:p; xlsx shared and inline strings
TEXT = {"t", "delText", "instrText"}


def unescape(s):
    def sub(m):
        g = m.group(1)
        if g.startswith("#x"):
            return chr(int(g[2:], 16))
        if g.startswith("#"):
            return chr(int(g[1:]))
        return NAMED[g]
    return ENTITY.sub(sub, s)


def escape(s, attr=False):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace('"', "&quot;") if attr else s


def local(qname):
    return qname.split(":")[-1]


def decode_xml(data):
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "utf-8", b"\xef\xbb\xbf"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        enc = "utf-16-le" if data.startswith(b"\xff\xfe") else "utf-16-be"
        return data[2:].decode(enc), enc, data[:2]
    head = data[:200].decode("ascii", "replace")
    m = re.search(r'encoding=["\']([\w-]+)', head)
    enc = (m.group(1) if m else "utf-8").lower()
    return data.decode(enc, "replace"), enc, b""


class Doc:
    """An XML part as tokens; text and attribute values can be rewritten in place."""

    def __init__(self, text):
        self.tokens = TOKEN.findall(text)

    def text(self):
        return "".join(self.tokens)

    def walk(self):
        """Yield ('attr', i, elem, name, value) and ('para', segs, elem) and ('text', i, elem, value).

        segs: [(token index, start-tag index, element local name, text)] of one paragraph
        and one kind of text (visible, deleted, field code).
        """
        stack, paras = [], []
        for i, tok in enumerate(self.tokens):
            if tok.startswith("<"):
                if tok.startswith(("<!", "<?")):
                    continue
                if tok.startswith("</"):
                    name = tok[2:-1].strip()
                    if stack:
                        stack.pop()
                    if local(name) in PARA and paras:
                        buf = paras.pop()
                        for segs in buf["kinds"].values():
                            if segs:
                                yield ("para", segs, buf["elem"])
                    continue
                m = re.match(r"<([\w:.-]+)", tok)
                if not m:
                    continue
                name = m.group(1)
                for a in ATTR.finditer(tok):
                    value = a.group(4) if a.group(4) is not None else a.group(5)
                    yield ("attr", i, name, a.group(1), unescape(value))
                if not tok.endswith("/>"):
                    stack.append((name, i))
                    if local(name) in PARA:
                        paras.append({"elem": name, "kinds": {}})
            else:
                if not stack:
                    continue
                parent, start = stack[-1]
                value = unescape(tok)
                if paras and local(parent) in TEXT:
                    kind = local(parent)
                    paras[-1]["kinds"].setdefault(kind, []).append((i, start, parent, value))
                elif value.strip():
                    yield ("text", i, parent, value)


def scan_part(name, text, terms):
    """Term hits in one XML part: [(kind, where, context, term)]."""
    hits = []
    if not terms:
        return hits
    for item in Doc(text).walk():
        if item[0] == "attr":
            _, _, elem, attr, value = item
            variants = {value, urllib.parse.unquote(value)} if "%" in value else {value}
            seen = set()
            for v in variants:
                for t, s, e in matches(terms, v):
                    if t.raw not in seen:
                        seen.add(t.raw)
                        hits.append(("attribute", f"{name} {elem}@{attr}", short(v), t.raw))
        elif item[0] == "text":
            _, _, elem, value = item
            for t, s, e in matches(terms, value):
                hits.append(("text", f"{name} {elem}", short(value), t.raw))
        else:
            _, segs, elem = item
            joined = "".join(s[3] for s in segs)
            bounds, pos = [], 0
            for s in segs:
                bounds.append((pos, pos + len(s[3])))
                pos += len(s[3])
            for t, s, e in matches(terms, joined):
                n = sum(1 for a, b in bounds if a < e and s < b)
                kind = "text" if n <= 1 else f"split across {n} runs"
                label = {"delText": "deleted text", "instrText": "field code"}.get(local(segs[0][2]), "")
                where = f"{name} {elem}" + (f" ({label})" if label else "")
                ctx = joined[max(0, s - 60):e + 60]
                hits.append((kind, where, short(ctx), t.raw))
    return hits


def replace_part(text, terms, repl, metadata_part=False):
    """Apply replacements; blank metadata nodes and alt text that have hits without one.

    Returns (new text, n replaced, n blanked, unresolved hits).
    """
    doc = Doc(text)
    replaced = blanked = 0
    unresolved = []
    attr_edits = {}   # token index -> {attr name: new value}
    text_edits = {}   # token index -> new text
    for item in list(doc.walk()):
        if item[0] == "attr":
            _, i, elem, attr, value = item
            ms = matches(terms, value)
            if not ms:
                continue
            todo = [m for m in ms if repl.get(m[0].raw) is not None]
            rest = [m for m in ms if repl.get(m[0].raw) is None]
            new = value
            for t, s, e in reversed(todo):
                new = new[:s] + repl[t.raw] + new[e:]
                replaced += 1
            if rest:
                if (local(attr) in ("descr", "title", "name") and local(elem) in ("cNvPr", "docPr")) \
                        or metadata_part:
                    new = ""
                    blanked += 1
                else:
                    unresolved += [("attribute", f"{elem}@{attr}", short(value), t.raw) for t, _, _ in rest]
                    continue
            if local(attr) == "name" and local(elem) not in ("cNvPr", "docPr") and not new.strip():
                # A sheet or a defined name can't be left without a name.
                unresolved.append(("attribute", f"{elem}@{attr}", short(value), ms[0][0].raw))
                continue
            attr_edits.setdefault(i, {})[attr] = new
        elif item[0] == "text":
            _, i, elem, value = item
            ms = matches(terms, value)
            if not ms:
                continue
            if any(repl.get(t.raw) is None for t, _, _ in ms):
                if metadata_part:
                    text_edits[i] = ""
                    blanked += 1
                else:
                    unresolved += [("text", elem, short(value), t.raw) for t, _, _ in ms
                                   if repl.get(t.raw) is None]
                continue
            new = value
            for t, s, e in reversed(ms):
                new = new[:s] + repl[t.raw] + new[e:]
                replaced += 1
            text_edits[i] = new
        else:
            _, segs, elem = item
            texts = [s[3] for s in segs]
            joined = "".join(texts)
            ms = matches(terms, joined)
            if not ms:
                continue
            for t, s, e in reversed(ms):
                r = repl.get(t.raw)
                if r is None:
                    unresolved.append(("text", elem, short(joined[max(0, s - 60):e + 60]), t.raw))
                    continue
                # Put the replacement in the first run the match touches; cut the rest.
                pos, first = 0, True
                for k, seg in enumerate(texts):
                    a, b = pos, pos + len(seg)
                    pos = b
                    if b <= s or a >= e:
                        continue
                    cs, ce = max(s, a) - a, min(e, b) - a
                    texts[k] = seg[:cs] + (r if first else "") + seg[ce:]
                    first = False
                replaced += 1
            for (i, start, parent, _), new in zip(segs, texts):
                text_edits[i] = new
                if local(parent) == "t" and new != new.strip() and "xml:space" not in doc.tokens[start]:
                    doc.tokens[start] = doc.tokens[start].replace(">", ' xml:space="preserve">', 1) \
                        if not doc.tokens[start].endswith("/>") else doc.tokens[start]
    for i, new in text_edits.items():
        doc.tokens[i] = escape(new)
    for i, changes in attr_edits.items():
        def sub(m, changes=changes):
            if m.group(1) in changes:
                q = m.group(3)[0]
                return f'{m.group(1)}{m.group(2)}{q}{escape(changes[m.group(1)], attr=True)}{q}'
            return m.group(0)
        doc.tokens[i] = ATTR.sub(sub, doc.tokens[i])
    return doc.text(), replaced, blanked, unresolved


# ---------------------------------------------------------------- package

class Package:
    def __init__(self, path):
        self.path = Path(path)
        with zipfile.ZipFile(path) as z:
            names = [i.filename for i in z.infolist()]
            if len(names) != len(set(names)):
                fail("the zip has duplicate entries: don't trust it, open and save it in Office")
            self.order = names
            self.parts = {n: z.read(n) for n in names}
        self.removed = []

    # -- helpers
    def xml(self, name):
        return decode_xml(self.parts[name])[0]

    def set_xml(self, name, text):
        _, enc, bom = decode_xml(self.parts[name])
        self.parts[name] = bom + text.encode(enc)

    def is_xml(self, name):
        return name.endswith((".xml", ".rels", ".vml")) or self.parts[name][:5].lstrip(b"\xef\xbb\xbf") == b"<?xml"

    @staticmethod
    def rels_name(part):
        d, b = posixpath.split(part)
        return posixpath.join(d, "_rels", b + ".rels") if part else "_rels/.rels"

    @staticmethod
    def source_of(rels):
        d, b = posixpath.split(rels)
        return posixpath.join(posixpath.dirname(d), b[:-5]) if b != ".rels" else ""

    def rels(self, part):
        name = self.rels_name(part)
        if name not in self.parts:
            return []
        out = []
        for tag in re.findall(r"<Relationship\b[^>]*>", self.xml(name)):
            a = {m.group(1): unescape(m.group(4) if m.group(4) is not None else m.group(5))
                 for m in ATTR.finditer(tag)}
            a["_tag"] = tag
            out.append(a)
        return out

    def target(self, part, rel):
        if rel.get("TargetMode") == "External":
            return None
        raw = rel.get("Target", "").split("#")[0]
        cands = []
        for t in (raw, urllib.parse.unquote(raw)):
            cands.append(t.lstrip("/") if t.startswith("/")
                         else posixpath.normpath(posixpath.join(posixpath.dirname(part), t)))
        for c in cands:
            if c in self.parts:
                return c
        return cands[0]

    def remove_rel(self, part, rid):
        name = self.rels_name(part)
        if name not in self.parts:
            return
        text = self.xml(name)
        new = re.sub(r'<Relationship\b[^>]*\bId="%s"[^>]*/>' % re.escape(rid), "", text)
        self.set_xml(name, new)

    def remove_part(self, name):
        if name in self.parts:
            del self.parts[name]
            self.removed.append(name)
        rn = self.rels_name(name)
        if rn in self.parts:
            del self.parts[rn]
        ct = "[Content_Types].xml"
        if ct in self.parts:
            self.set_xml(ct, re.sub(r'<Override\b[^>]*PartName="/%s"[^>]*/>' % re.escape(name), "",
                                    self.xml(ct)))

    def drop_refs(self, part, rids):
        """Remove self-closing elements that point to removed relationship ids."""
        if not rids or part not in self.parts:
            return
        text = self.xml(part)
        for rid in rids:
            text = re.sub(r'<[\w:.-]+\b[^<>]*\b[\w]+:(?:id|embed|link)="%s"[^<>]*/>' % re.escape(rid), "", text)
        text = re.sub(r"<p:ext\b[^>]*>\s*</p:ext>", "", text)
        self.set_xml(part, text)

    def main_part(self):
        for r in self.rels(""):
            if r.get("Type", "").endswith("/officeDocument"):
                return self.target("", r)
        return None

    def save(self, dst):
        order = [n for n in self.order if n in self.parts] + [n for n in self.parts if n not in self.order]
        order.sort(key=lambda n: n != "[Content_Types].xml")
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for n in order:
                z.writestr(n, self.parts[n])


# ---------------------------------------------------------------- inspection

def core_fields(pkg):
    out_ = []
    for part in ("docProps/core.xml", "docProps/app.xml"):
        if part not in pkg.parts:
            continue
        for item in Doc(pkg.xml(part)).walk():
            if item[0] == "text":
                out_.append((part, local(item[2]), item[3]))
    return out_


def custom_props(pkg):
    if "docProps/custom.xml" not in pkg.parts:
        return []
    return [(n, unescape(v)) for n, v in re.findall(
        r'<property\b[^>]*\bname="([^"]*)"[^>]*>\s*<vt:\w+>([^<]*)</vt:\w+>', pkg.xml("docProps/custom.xml"))]


def para_texts(xml_text, kinds=("t",)):
    """Visible text of each paragraph of an XML part."""
    res = []
    for item in Doc(xml_text).walk():
        if item[0] == "para" and local(item[1][0][2]) in kinds:
            res.append("".join(s[3] for s in item[1]))
    return res


def inspect_office(pkg, kind, terms):
    f = []   # (section, line)

    def add(section, line):
        f.append((section, line))

    app_fields = ("Template", "Manager", "Company", "HyperlinkBase", "TotalTime", "Application")
    for part, field, value in core_fields(pkg):
        if not value.strip() or (part.endswith("app.xml") and field not in app_fields):
            continue
        add("metadata", f"{part} {field} = {short(value)!r}")
    for part in ("docProps/app.xml",):
        if part in pkg.parts:
            m = re.search(r"<TitlesOfParts>(.*?)</TitlesOfParts>", pkg.xml(part), re.S)
            if m:
                titles = [unescape(t) for t in re.findall(r"<vt:lpstr>([^<]*)</vt:lpstr>", m.group(1))]
                add("metadata", f"{part} TitlesOfParts = {[short(t, 80) for t in titles]}")
    for n, v in custom_props(pkg):
        add("custom properties", f"{n} = {short(v)!r}")
    for name in sorted(pkg.parts):
        if name.startswith("customXml/item") and re.match(r"customXml/item\d+\.xml$", name):
            body = re.sub(r"<[^>]+>", " ", pkg.xml(name))
            if body.strip():
                add("custom XML data", f"{name}: {short(unescape(body), 100)!r}")

    # Relationships: attached template, external links, local paths.
    for rels in sorted(n for n in pkg.parts if n.endswith(".rels")):
        src = Package.source_of(rels)
        for r in pkg.rels(src):
            typ, tgt = r.get("Type", ""), r.get("Target", "")
            if typ.endswith("/attachedTemplate"):
                add("linked template", f"{src} -> {short(urllib.parse.unquote(tgt))}")
            elif r.get("TargetMode") == "External":
                flag = " (local or network path)" if LOCAL_PATH.match(urllib.parse.unquote(tgt)) else ""
                add("external links", f"{src} [{typ.rsplit('/', 1)[-1]}] -> {short(urllib.parse.unquote(tgt))}{flag}")
    if "docProps/thumbnail.jpeg" in pkg.parts or any(r.get("Type", "").endswith("/thumbnail") for r in pkg.rels("")):
        add("thumbnail", "a picture of the first page or slide as last saved (can show old content)")

    xml_parts = [n for n in pkg.parts if pkg.is_xml(n) and not n.endswith(".rels")]
    # Alt text and shape names on pictures.
    for name in xml_parts:
        if not name.startswith(("word/", "ppt/", "xl/")):
            continue
        for item in Doc(pkg.xml(name)).walk():
            if item[0] == "attr" and local(item[3]) in ("descr", "title") and item[4].strip() \
                    and local(item[2]) in ("docPr", "cNvPr"):
                add("alt text", f"{name} {item[2]}@{item[3]} = {short(item[4])!r}")

    if kind == "docx":
        inspect_docx(pkg, add)
    elif kind == "pptx":
        inspect_pptx(pkg, add)
    elif kind == "xlsx":
        inspect_xlsx(pkg, add)

    # Embedded objects and media metadata.
    for name, data in pkg.parts.items():
        if "/embeddings/" in name:
            add("embedded objects", f"{name} ({len(data)} bytes): a file inside the file; open it and check it too")
        if "/media/" in name and media_metadata(data)[1]:
            add("media metadata", f"{name}: {', '.join(media_metadata(data)[1])}")
    for name in orphans(pkg):
        add("orphan parts", f"{name}: in the package but not referenced by anything")

    hits = []
    for name in sorted(pkg.parts):
        data = pkg.parts[name]
        if pkg.is_xml(name):
            hits += scan_part(name, pkg.xml(name), terms)
        elif terms:
            for enc in ("utf-8", "utf-16-le", "latin-1"):
                txt = data.decode(enc, "ignore")
                for t, s, e in matches(terms, txt):
                    hits.append(("binary", f"{name} ({enc})", short(txt[max(0, s - 30):e + 30]), t.raw))
                    break
            if zipfile.is_zipfile(io.BytesIO(data)):
                try:
                    sub = Package.__new__(Package)
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        sub.parts = {n: z.read(n) for n in z.namelist()}
                    for sn in sub.parts:
                        if sub.is_xml(sn):
                            hits += [(k, f"{name}!{w}", c, t) for k, w, c, t in scan_part(sn, sub.xml(sn), terms)]
                except zipfile.BadZipFile:
                    pass
    return f, hits


def inspect_docx(pkg, add):
    for name in sorted(pkg.parts):
        if re.match(r"word/(header|footer)\d*\.xml$", name):
            text = " / ".join(t for t in para_texts(pkg.xml(name)) if t.strip())
            if text:
                add("headers and footers", f"{name}: {short(text)!r}")
    if "word/comments.xml" in pkg.parts:
        x = pkg.xml("word/comments.xml")
        authors = sorted(set(unescape(a) for a in re.findall(r'<w:comment\b[^>]*w:author="([^"]*)"', x)))
        for t in para_texts(x):
            if t.strip():
                add("comments", f"{short(t)!r}")
        add("comments", f"authors: {authors}")
    for name in ("word/people.xml",):
        if name in pkg.parts:
            add("comments", f"{name}: list of people who commented or edited")
    for name in sorted(n for n in pkg.parts if n.startswith("word/") and n.endswith(".xml")):
        x = pkg.xml(name)
        ins = len(re.findall(r"<w:ins\b", x)) + len(re.findall(r"<w:moveTo\b(?!Range)", x))
        dels = len(re.findall(r"<w:del\b", x)) + len(re.findall(r"<w:moveFrom\b(?!Range)", x))
        fmt = len(re.findall(r"<w:\w+PrChange\b", x))
        if ins or dels or fmt:
            authors = sorted(set(unescape(a) for a in re.findall(
                r'<w:(?:ins|del|moveTo|moveFrom|\w+PrChange)\b[^>]*w:author="([^"]*)"', x)))
            add("tracked changes", f"{name}: {ins} insertions, {dels} deletions, {fmt} formatting changes; "
                                   f"authors {authors}")
            deleted = [t for t in para_texts(x, kinds=("delText",)) if t.strip()]
            for t in deleted:
                add("tracked changes", f"{name} deleted text still in the file: {short(t)!r}")
        for instr in field_instructions(x):
            kind_ = instr.split()[0].upper() if instr.split() else ""
            if kind_ in FIELD_TYPES or re.search(r'"[^"]*[\\/][^"]*"', instr):
                add("fields", f"{name}: {short(instr)!r}")
    if "word/glossary/document.xml" in pkg.parts:
        add("building blocks", "word/glossary/document.xml (Quick Parts, AutoText): check the term hits there")
    if "word/vbaProject.bin" in pkg.parts:
        add("macros", "word/vbaProject.bin: the file has macros")


def field_instructions(x):
    res = []
    for m in re.finditer(r'<w:fldSimple\b[^>]*w:instr="([^"]*)"', x):
        res.append(unescape(m.group(1)).strip())
    cur, depth = [], 0
    for m in re.finditer(r'w:fldCharType="(begin|separate|end)"|<w:instrText\b[^>]*>([^<]*)</w:instrText>', x):
        if m.group(1) == "begin":
            depth += 1
            if depth == 1:
                cur = []
        elif m.group(1) in ("separate", "end"):
            if depth == 1 and cur:
                res.append("".join(cur).strip())
                cur = []
            if m.group(1) == "end":
                depth = max(0, depth - 1)
        elif depth == 1:
            cur.append(unescape(m.group(2)))
    return res


def slides_in_order(pkg):
    pres = "ppt/presentation.xml"
    if pres not in pkg.parts:
        return []
    rels = {r["Id"]: pkg.target(pres, r) for r in pkg.rels(pres)}
    res = []
    for tag in re.findall(r"<p:sldId\b[^>]*/>", pkg.xml(pres)):
        a = {m.group(1): m.group(4) for m in ATTR.finditer(tag)}
        rid = a.get("r:id")
        res.append((a.get("id"), rid, rels.get(rid), tag))
    return res


def slide_title(pkg, part):
    texts = [t for t in para_texts(pkg.xml(part)) if t.strip()]
    return texts[0] if texts else ""


def inspect_pptx(pkg, add):
    for n, (sid, rid, part, _) in enumerate(slides_in_order(pkg), 1):
        if not part or part not in pkg.parts:
            continue
        x = pkg.xml(part)
        if re.search(r'<p:sld\b[^>]*\bshow="0"', x):
            add("hidden slides", f"slide {n} ({part}): {short(slide_title(pkg, part), 100)!r}")
        for r in pkg.rels(part):
            t = pkg.target(part, r)
            typ = r.get("Type", "")
            if typ.endswith("/notesSlide") and t in pkg.parts:
                text = " / ".join(s for s in para_texts(pkg.xml(t)) if s.strip() and not s.strip().isdigit())
                if text:
                    add("speaker notes", f"slide {n}: {short(text)!r}")
            if typ.endswith("/comments") and t in pkg.parts:
                for s in para_texts(pkg.xml(t)) or re.findall(r"<p:text>([^<]*)</p:text>", pkg.xml(t)):
                    if s.strip():
                        add("comments", f"slide {n}: {short(unescape(s))!r}")
    for name in ("ppt/commentAuthors.xml", "ppt/authors.xml"):
        if name in pkg.parts:
            add("comments", f"{name}: list of comment authors")
    if "ppt/vbaProject.bin" in pkg.parts:
        add("macros", "ppt/vbaProject.bin: the file has macros")


def inspect_xlsx(pkg, add):
    wb = "xl/workbook.xml"
    if wb not in pkg.parts:
        return
    x = pkg.xml(wb)
    for tag in re.findall(r"<sheet\b[^>]*/>", x):
        a = {m.group(1): unescape(m.group(4) or "") for m in ATTR.finditer(tag)}
        if a.get("state") in ("hidden", "veryHidden"):
            add("hidden sheets", f"{a.get('name')!r} ({a.get('state')})")
    for m in re.finditer(r"<definedName\b([^>]*)>([^<]*)</definedName>", x):
        a = {k.group(1): unescape(k.group(4) or "") for k in ATTR.finditer(m.group(1))}
        if not a.get("name", "").startswith("_xlnm."):
            hidden = " (hidden)" if a.get("hidden") in ("1", "true") else ""
            add("defined names", f"{a.get('name')}{hidden} = {short(unescape(m.group(2)), 100)}")
    for name in sorted(pkg.parts):
        if name.startswith("xl/externalLinks/externalLink") and name.endswith(".xml"):
            for r in pkg.rels(name):
                add("external links", f"{name} -> {short(urllib.parse.unquote(r.get('Target', '')))}")
        if name.startswith("xl/pivotCache/pivotCacheRecords"):
            add("pivot caches", f"{name}: a copy of the pivot table's source data, even rows the table hides")
        if name == "xl/connections.xml":
            for c in re.findall(r'connection="([^"]*)"', pkg.xml(name)):
                add("data connections", short(unescape(c)))
        if re.match(r"xl/worksheets/sheet\d+\.xml$", name):
            s = pkg.xml(name)
            rows = len(re.findall(r'<row\b[^>]*\bhidden="(?:1|true)"', s))
            cols = len(re.findall(r'<col\b[^>]*\bhidden="(?:1|true)"', s))
            if rows or cols:
                add("hidden rows and columns", f"{name}: {rows} hidden rows, {cols} hidden column ranges")
        if re.match(r"xl/comments\d*\.xml$", name) or name.startswith("xl/threadedComments/"):
            for t in para_texts(pkg.xml(name)):
                if t.strip():
                    add("comments", f"{name}: {short(t)!r}")
        if name.startswith("xl/persons/"):
            add("comments", f"{name}: list of people who commented")
    if "xl/vbaProject.bin" in pkg.parts:
        add("macros", "xl/vbaProject.bin: the file has macros")


def media_metadata(data):
    """(stripped bytes or None, [what was found]) for JPEG and PNG."""
    found = []
    if data[:2] == b"\xff\xd8":
        out_, i = bytearray(b"\xff\xd8"), 2
        while i + 4 <= len(data) and data[i] == 0xFF:
            marker = data[i + 1]
            if marker == 0xDA:           # start of scan: copy the rest
                out_ += data[i:]
                break
            seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
            seg = data[i:i + 2 + seglen]
            if marker == 0xE1:
                found.append("XMP" if b"http://ns.adobe.com/xap" in seg[:64] else "EXIF")
            elif marker == 0xED:
                found.append("IPTC")
            elif marker == 0xFE:
                found.append("JPEG comment")
            else:
                out_ += seg
            i += 2 + seglen
        else:
            return None, found
        return (bytes(out_) if found else None), found
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        out_, i = bytearray(data[:8]), 8
        while i + 8 <= len(data):
            n = struct.unpack(">I", data[i:i + 4])[0]
            typ = data[i + 4:i + 8]
            chunk = data[i:i + 12 + n]
            if typ in (b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"):
                found.append(typ.decode())
            else:
                out_ += chunk
            i += 12 + n
        return (bytes(out_) if found else None), sorted(set(found))
    return None, found


def reachable(pkg):
    seen, todo = set(), [""]
    while todo:
        part = todo.pop()
        for r in pkg.rels(part):
            t = pkg.target(part, r)
            if t and t not in seen and t in pkg.parts:
                seen.add(t)
                todo.append(t)
    return seen


def orphans(pkg):
    seen = reachable(pkg)
    return sorted(n for n in pkg.parts if n != "[Content_Types].xml" and not n.endswith(".rels")
                  and n not in seen and not n.endswith("/"))


# ---------------------------------------------------------------- cleaning

def clean_office(pkg, kind, terms, repl, keep, opts):
    log = []

    def did(msg):
        log.append(msg)

    word_parts = lambda: [n for n in pkg.parts if n.startswith("word/") and n.endswith(".xml")]

    if "comments" not in keep:
        drop_types = ("/comments", "/commentsExtended", "/commentsIds", "/commentsExtensible", "/people",
                      "/commentAuthors", "/authors", "/threadedComment", "/person")
        for rels in [n for n in pkg.parts if n.endswith(".rels")]:
            src = Package.source_of(rels)
            removed = []
            for r in pkg.rels(src):
                if r.get("Type", "").endswith(drop_types):
                    t = pkg.target(src, r)
                    pkg.remove_rel(src, r["Id"])
                    removed.append(r["Id"])
                    if t:
                        pkg.remove_part(t)
                        did(f"removed {t}")
                elif r.get("Type", "").endswith("/vmlDrawing"):
                    t = pkg.target(src, r)
                    kinds = set(re.findall(r'ObjectType="(\w+)"', pkg.xml(t))) if t in pkg.parts else set()
                    if kinds == {"Note"}:   # only comment boxes; keep VML that holds form controls
                        pkg.remove_rel(src, r["Id"])
                        removed.append(r["Id"])
                        pkg.remove_part(t)
                        did(f"removed {t} (comment boxes)")
            pkg.drop_refs(src, removed)
        for n in word_parts():
            x = pkg.xml(n)
            y = re.sub(r"<w:comment(?:RangeStart|RangeEnd)\b[^>]*/>", "", x)
            y = re.sub(r"<w:r\b[^>]*>(?:(?!</w:r>)(?!<w:r\b).)*?<w:commentReference\b[^>]*/>(?:(?!</w:r>).)*?</w:r>",
                       "", y, flags=re.S)
            if y != x:
                pkg.set_xml(n, y)
                did(f"removed comment marks from {n}")

    if kind == "docx" and "revisions" not in keep:
        for n in word_parts():
            x = pkg.xml(n)
            y = x
            warn = len(re.findall(r"<w:trPr>(?:(?!</w:trPr>).)*<w:del\b", y, re.S))
            # Self-closing forms first, so the paired patterns can't swallow them.
            for pat in (r"<w:del\b[^>]*/>", r"<w:del\b[^>]*>.*?</w:del>", r"<w:moveFrom\b[^>]*/>",
                        r"<w:moveFrom\b[^>]*>.*?</w:moveFrom>",
                        r"<w:move(?:From|To)Range(?:Start|End)\b[^>]*/>",
                        r"<w:(?:\w+PrChange|tblGridChange|numberingChange)\b[^>]*/>",
                        r"<w:(\w+PrChange|tblGridChange|numberingChange)\b[^>]*>.*?</w:\1>",
                        r"<w:cell(?:Ins|Del|Merge)\b[^>]*/>",
                        r"<w:ins\b[^>]*/>", r"<w:ins\b[^>]*>", r"</w:ins>", r"<w:moveTo\b[^>]*>", r"</w:moveTo>"):
                y = re.sub(pat, "", y, flags=re.S)
            if y != x:
                pkg.set_xml(n, y)
                did(f"accepted tracked changes in {n}" + (f" ({warn} deleted table rows kept: check them)"
                                                         if warn else ""))

    if kind == "docx" and "fields" not in keep:
        for n in word_parts():
            x = pkg.xml(n)
            y, k = unwrap_fields(x)
            if k:
                pkg.set_xml(n, y)
                did(f"unwrapped {k} linked fields in {n} (kept what they show)")

    if kind == "docx" and "template" not in keep and "word/settings.xml" in pkg.parts:
        for r in pkg.rels("word/settings.xml"):
            if r.get("Type", "").endswith("/attachedTemplate"):
                pkg.remove_rel("word/settings.xml", r["Id"])
                x = pkg.xml("word/settings.xml")
                pkg.set_xml("word/settings.xml", re.sub(r"<w:attachedTemplate\b[^>]*/>", "", x))
                did("removed the linked template")

    if kind == "pptx" and "hidden-slides" not in keep:
        pres = "ppt/presentation.xml"
        for sid, rid, part, tag in slides_in_order(pkg):
            if part and part in pkg.parts and re.search(r'<p:sld\b[^>]*\bshow="0"', pkg.xml(part)):
                title = slide_title(pkg, part)
                x = pkg.xml(pres).replace(tag, "")
                x = re.sub(r'<p14:sldId\b[^>]*\bid="%s"[^>]*/>' % sid, "", x)
                x = re.sub(r'<p:sld\b[^>]*r:id="%s"[^>]*/>' % rid, "", x)
                pkg.set_xml(pres, x)
                pkg.remove_rel(pres, rid)
                pkg.remove_part(part)
                did(f"removed hidden slide {part} ({short(title, 60)!r})")

    if kind == "pptx" and "notes" not in keep:
        for sid, rid, part, tag in slides_in_order(pkg):
            if part not in pkg.parts:
                continue
            for r in pkg.rels(part):
                if r.get("Type", "").endswith("/notesSlide"):
                    t = pkg.target(part, r)
                    pkg.remove_rel(part, r["Id"])
                    if t:
                        pkg.remove_part(t)
                        did(f"removed speaker notes {t}")

    if "custom" not in keep and "docProps/custom.xml" in pkg.parts:
        for r in pkg.rels(""):
            if r.get("Type", "").endswith("/custom-properties"):
                pkg.remove_rel("", r["Id"])
        pkg.remove_part("docProps/custom.xml")
        did("removed custom properties (docProps/custom.xml)")

    if "thumbnail" not in keep:
        for r in pkg.rels(""):
            if r.get("Type", "").endswith("/thumbnail"):
                t = pkg.target("", r)
                pkg.remove_rel("", r["Id"])
                if t:
                    pkg.remove_part(t)
                    did(f"removed the thumbnail {t}")

    if "metadata" not in keep:
        clean_metadata(pkg, kind, opts, did)

    if "media-metadata" not in keep:
        for n in list(pkg.parts):
            if "/media/" in n:
                new, found = media_metadata(pkg.parts[n])
                if new is not None:
                    pkg.parts[n] = new
                    did(f"stripped {', '.join(found)} from {n}")

    if "orphans" not in keep:
        for _ in range(5):
            gone = orphans(pkg)
            if not gone:
                break
            for n in gone:
                pkg.remove_part(n)
                did(f"removed unreferenced part {n}")
        for rels in [n for n in pkg.parts if n.endswith(".rels")]:
            src = Package.source_of(rels)
            if src and src not in pkg.parts:
                del pkg.parts[rels]

    unresolved = []
    total_r = total_b = 0
    for n in list(pkg.parts):
        if not pkg.is_xml(n) or n.endswith(".rels") or n == "[Content_Types].xml" or not terms:
            continue
        x = pkg.xml(n)
        y, r_, b_, u_ = replace_part(x, terms, repl, metadata_part=n.startswith("docProps/"))
        if y != x:
            pkg.set_xml(n, y)
        total_r += r_
        total_b += b_
        unresolved += [(k, f"{n} {w}", c, t) for k, w, c, t in u_]
    if total_r:
        did(f"replaced {total_r} term matches")
    if total_b:
        did(f"blanked {total_b} metadata values, alt texts or shape names that held a term")
    return log, unresolved


def unwrap_fields(x):
    """Remove the field codes of linked fields (INCLUDEPICTURE...), keeping their result."""
    n = 0

    def simple(m):
        nonlocal n
        instr = unescape(m.group(1)).strip().split()
        if instr and instr[0].upper() in FIELD_TYPES:
            n += 1
            return m.group(2) or ""
        return m.group(0)

    x = re.sub(r'<w:fldSimple\b[^>]*w:instr="([^"]*)"[^>]*(?:/>|>(.*?)</w:fldSimple>)', simple, x, flags=re.S)
    runs = list(re.finditer(r"<w:r\b[^>]*>(?:(?!<w:r\b|</w:r>).)*?</w:r>", x, re.S))
    stack, drop = [], []
    for m in runs:
        r = m.group(0)
        c = re.search(r'w:fldCharType="(begin|separate|end)"', r)
        if c and c.group(1) == "begin":
            stack.append({"spans": [m.span()], "instr": [], "sep": False})
        elif c and c.group(1) == "separate" and stack:
            stack[-1]["spans"].append(m.span())
            stack[-1]["sep"] = True
        elif c and c.group(1) == "end" and stack:
            f = stack.pop()
            f["spans"].append(m.span())
            words = "".join(f["instr"]).split()
            if words and words[0].upper() in FIELD_TYPES:
                drop += f["spans"]
                n += 1
        elif "<w:instrText" in r and stack and not stack[-1]["sep"]:
            stack[-1]["instr"].append(unescape("".join(re.findall(r"<w:instrText\b[^>]*>([^<]*)</w:instrText>", r))))
            stack[-1]["spans"].append(m.span())
    for s, e in sorted(drop, reverse=True):
        x = x[:s] + x[e:]
    return x, n


def clean_metadata(pkg, kind, opts, did):
    core = "docProps/core.xml"
    if core in pkg.parts:
        x = pkg.xml(core)
        y = x
        author = escape(opts.author or "")
        for tag in ("dc:creator", "cp:lastModifiedBy"):
            y = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>|<{tag}\b[^>]*/>", f"<{tag}>{author}</{tag}>", y, flags=re.S)
        y = re.sub(r"<cp:lastPrinted\b[^>]*>.*?</cp:lastPrinted>", "", y, flags=re.S)
        y = re.sub(r"<cp:revision>.*?</cp:revision>", "<cp:revision>1</cp:revision>", y, flags=re.S)
        for opt, tag in ((opts.title, "dc:title"), (opts.subject, "dc:subject")):
            if opt is not None:
                if re.search(rf"<{tag}\b", y):
                    y = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>|<{tag}\b[^>]*/>", f"<{tag}>{escape(opt)}</{tag}>",
                               y, flags=re.S)
                else:
                    y = y.replace("</cp:coreProperties>", f"<{tag}>{escape(opt)}</{tag}></cp:coreProperties>")
        if y != x:
            pkg.set_xml(core, y)
            did("reset author, last modified by, revision and last printed in docProps/core.xml")
    app = "docProps/app.xml"
    if app in pkg.parts:
        x = pkg.xml(app)
        y = x
        for tag in ("Template", "Manager", "HyperlinkBase", "HeadingPairs", "TitlesOfParts"):
            y = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>|<{tag}\b[^>]*/>", "", y, flags=re.S)
        y = re.sub(r"<TotalTime>\d+</TotalTime>", "<TotalTime>0</TotalTime>", y)
        if opts.company is not None:
            y = re.sub(r"<Company\b[^>]*>.*?</Company>|<Company\b[^>]*/>", f"<Company>{escape(opts.company)}</Company>",
                       y, flags=re.S)
        if kind == "pptx":
            slides = [s for s in slides_in_order(pkg) if s[2] in pkg.parts]
            hidden = sum(1 for s in slides if re.search(r'<p:sld\b[^>]*\bshow="0"', pkg.xml(s[2])))
            notes = sum(1 for s in slides for r in pkg.rels(s[2]) if r.get("Type", "").endswith("/notesSlide"))
            for tag, val in (("Slides", len(slides)), ("HiddenSlides", hidden), ("Notes", notes)):
                y = re.sub(rf"<{tag}>\d+</{tag}>", f"<{tag}>{val}</{tag}>", y)
        if y != x:
            pkg.set_xml(app, y)
            did("removed template name, manager, hyperlink base and the list of titles from docProps/app.xml; "
                "editing time set to 0")


def visible_summary(pkg, kind):
    """Counts of what shows on screen, to compare the copy with the original."""
    s = {}
    if kind == "docx":
        main = pkg.main_part() or "word/document.xml"
        x = pkg.xml(main) if main in pkg.parts else ""
        s["paragraphs with text"] = sum(1 for t in para_texts(x) if t.strip())
        s["pictures"] = len(re.findall(r"<w:drawing>|<w:pict\b", x))
        s["tables"] = len(re.findall(r"<w:tbl>", x))
        s["headers and footers"] = sum(1 for n in pkg.parts if re.match(r"word/(header|footer)\d*\.xml$", n))
    elif kind == "pptx":
        slides = [p for _, _, p, _ in slides_in_order(pkg) if p in pkg.parts]
        shown = [p for p in slides if not re.search(r'<p:sld\b[^>]*\bshow="0"', pkg.xml(p))]
        s["slides shown"] = len(shown)
        s["pictures on shown slides"] = sum(len(re.findall(r"<p:pic>", pkg.xml(p))) for p in shown)
        s["paragraphs with text on shown slides"] = sum(1 for p in shown for t in para_texts(pkg.xml(p)) if t.strip())
    elif kind == "xlsx" and "xl/workbook.xml" in pkg.parts:
        s["sheets"] = len(re.findall(r"<sheet\b", pkg.xml("xl/workbook.xml")))
        if "xl/sharedStrings.xml" in pkg.parts:
            s["text cells (shared strings)"] = len(re.findall(r"<si>", pkg.xml("xl/sharedStrings.xml")))
    return s


# ---------------------------------------------------------------- verification

def verify_office(path):
    problems = []
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad:
                problems.append(f"corrupt zip entry {bad}")
    except zipfile.BadZipFile as e:
        return [f"not a zip package: {e}"], 0
    pkg = Package(path)
    ct = "[Content_Types].xml"
    if ct not in pkg.parts:
        return ["no [Content_Types].xml"], len(pkg.parts)
    for n in pkg.parts:
        if pkg.is_xml(n):
            text = pkg.xml(n)
            if "<!DOCTYPE" in text or "<!ENTITY" in text:
                # Office parts never declare a DTD; don't let the parser expand one.
                problems.append(f"{n}: has a DOCTYPE or ENTITY declaration (not expected in Office files)")
                continue
            try:
                ET.fromstring(text.encode("utf-8") if not text.startswith("<?xml") else
                              re.sub(r"^<\?xml[^>]*\?>", "", text).encode("utf-8"))
            except ET.ParseError as e:
                problems.append(f"{n}: XML does not parse ({e})")
    cts = pkg.xml(ct)
    defaults = {e.lower() for e in re.findall(r'<Default\b[^>]*Extension="([^"]*)"', cts)}
    overrides = {p.lstrip("/") for p in re.findall(r'<Override\b[^>]*PartName="([^"]*)"', cts)}
    for n in pkg.parts:
        if n == ct or n.endswith("/"):
            continue
        if n not in overrides and n.rsplit(".", 1)[-1].lower() not in defaults:
            problems.append(f"{n}: no content type")
    for o in overrides:
        if o not in pkg.parts:
            problems.append(f"content type points to a missing part /{o}")
    if not pkg.main_part() or pkg.main_part() not in pkg.parts:
        problems.append("the main document part is missing")
    for rels in [n for n in pkg.parts if n.endswith(".rels")]:
        src = Package.source_of(rels)
        if src and src not in pkg.parts:
            problems.append(f"{rels}: relationships of a missing part")
            continue
        ids = set()
        for r in pkg.rels(src):
            ids.add(r.get("Id"))
            t = pkg.target(src, r)
            if t and t not in pkg.parts:
                problems.append(f"{src}: relationship {r.get('Id')} points to missing {t}")
        if src and pkg.is_xml(src):
            text = pkg.xml(src)
            prefixes = re.findall(r'xmlns:([\w.-]+)="%s"' % re.escape(R_NS), text)
            for p in prefixes:
                for rid in re.findall(r'\b%s:[\w]+="([^"]*)"' % re.escape(p), text):
                    if rid and rid not in ids:
                        problems.append(f"{src}: refers to relationship {rid}, which does not exist")
    for src in [n for n in pkg.parts if pkg.is_xml(n) and Package.rels_name(n) not in pkg.parts]:
        text = pkg.xml(src)
        for p in re.findall(r'xmlns:([\w.-]+)="%s"' % re.escape(R_NS), text):
            for rid in re.findall(r'\b%s:(?:id|embed|link)="([^"]*)"' % re.escape(p), text):
                problems.append(f"{src}: refers to relationship {rid}, but has no relationships")
    if "ppt/presentation.xml" in pkg.parts:
        if not slides_in_order(pkg):
            problems.append("the presentation has no slides")
    return problems, len(pkg.parts)


def verify_deep(path, kind):
    """Optional: open with python-docx / python-pptx / openpyxl if installed."""
    mod = {"docx": "docx", "pptx": "pptx", "xlsx": "openpyxl"}.get(kind)
    try:
        lib = __import__(mod)
    except ImportError:
        return f"{mod} not installed: skipped opening the file with it"
    try:
        if kind == "docx":
            lib.Document(str(path))
        elif kind == "pptx":
            lib.Presentation(str(path))
        else:
            lib.load_workbook(str(path))
        return f"opened with {mod}: OK"
    except Exception as e:  # noqa: BLE001 - report any failure
        return f"FAILED to open with {mod}: {e}"


# ---------------------------------------------------------------- PDF

def pdf_lib():
    try:
        import pypdf
        return pypdf
    except ImportError:
        return None


def inspect_pdf(path, terms):
    f, hits = [], []
    data = Path(path).read_bytes()
    if data.count(b"%%EOF") > 1:
        f.append(("incremental updates", f"{data.count(b'%%EOF')} saved versions inside the file: "
                                         "earlier versions can be recovered"))
    pypdf = pdf_lib()
    if pypdf is None:
        f.append(("limits", "pypdf is not installed: raw scan only, and text inside pages may be encoded. "
                            "A zero here proves little: install pypdf, or check the source document"))
        for key in (b"/Author", b"/Creator", b"/Producer", b"/Title", b"/Subject", b"/Keywords"):
            for m in re.finditer(re.escape(key) + rb"\s*\(((?:\\.|[^\\)])*)\)", data):
                f.append(("metadata", f"{key.decode()} = {short(m.group(1).decode('latin-1'))!r}"))
        for key, label in ((b"/Annots", "annotations"), (b"/EmbeddedFile", "attachments"),
                           (b"/JavaScript", "JavaScript"), (b"/AcroForm", "form fields"),
                           (b"x:xmpmeta", "XMP metadata"), (b"/OCProperties", "layers")):
            if key in data:
                f.append((label, f"{key.decode()} present"))
        import zlib
        streams = [data]
        for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
            try:
                streams.append(zlib.decompressobj().decompress(m.group(1)))
            except zlib.error:   # not a Flate stream
                pass
        for blob in streams:
            # PDF literal strings write non-ASCII bytes as octal escapes (\341 is "á").
            blob = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8) & 0xFF]), blob)
            for enc in ("latin-1", "utf-16-be"):
                txt = blob.decode(enc, "ignore")
                for t, s, e in matches(terms, txt):
                    hits.append(("raw", "pdf bytes", short(txt[max(0, s - 30):e + 30]), t.raw))
        return f, hits
    reader = pypdf.PdfReader(path)
    if reader.is_encrypted:
        f.append(("encrypted", "the PDF is encrypted: decrypt it first"))
        return f, hits
    for k, v in (reader.metadata or {}).items():
        f.append(("metadata", f"{k} = {short(str(v))!r}"))
        for t, s, e in matches(terms, str(v)):
            hits.append(("metadata", f"Info {k}", short(str(v)), t.raw))
    root = reader.trailer["/Root"]
    if "/Metadata" in root:
        try:
            xmp = root["/Metadata"].get_object().get_data().decode("utf-8", "replace")
            f.append(("XMP metadata", short(re.sub(r"<[^>]+>", " ", xmp), 200)))
            for t, s, e in matches(terms, xmp):
                hits.append(("metadata", "XMP", short(xmp[max(0, s - 40):e + 40]), t.raw))
        except Exception as e:  # noqa: BLE001
            f.append(("XMP metadata", f"present, unreadable: {e}"))
    for n, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        for t, s, e in matches(terms, text):
            hits.append(("page text", f"page {n}", short(text[max(0, s - 60):e + 60]), t.raw))
        for a in page.get("/Annots") or []:
            try:
                a = a.get_object()
                sub = a.get("/Subtype")
                desc = " ".join(str(a.get(k, "")) for k in ("/T", "/Contents") if a.get(k))
                action = a.get("/A")
                action = action.get_object() if action is not None else {}
                uri = action.get("/URI") if hasattr(action, "get") else None
            except Exception as e:  # noqa: BLE001 - report and go on
                f.append(("annotations", f"page {n}: unreadable annotation ({e})"))
                continue
            f.append(("annotations", f"page {n}: {sub} {short(desc or str(uri or ''), 120)!r}"))
            for t, s, e in matches(terms, f"{desc} {uri or ''}"):
                hits.append(("annotation", f"page {n} {sub}", short(desc or str(uri)), t.raw))
    try:
        for name, contents in reader.attachments.items():
            f.append(("attachments", f"{name}: a file inside the PDF"))
            for blob in [name.encode("utf-8")] + list(contents):
                txt = blob.decode("utf-8", "ignore")
                for t, s, e in matches(terms, txt):
                    hits.append(("attachment", name, short(txt[max(0, s - 40):e + 40]), t.raw))
    except Exception as e:  # noqa: BLE001 - report and go on
        f.append(("attachments", f"could not read the attachments: {e}"))
    names = root.get("/Names", {})
    if "/JavaScript" in names or "/OpenAction" in root:
        f.append(("JavaScript", "the PDF runs JavaScript or an action on open"))
    fields = reader.get_fields() or {}
    for k, v in fields.items():
        val = v.get("/V")
        if val:
            f.append(("form fields", f"{k} = {short(str(val), 80)!r}"))
    def walk_outline(items):
        for it in items:
            if isinstance(it, list):
                yield from walk_outline(it)
            else:
                yield str(getattr(it, "title", ""))
    for title in walk_outline(reader.outline or []):
        for t, s, e in matches(terms, title):
            hits.append(("bookmark", "outline", short(title), t.raw))
    if "/OCProperties" in root:
        f.append(("layers", "optional content (layers) present: hidden layers can hold text"))
    return f, hits


def clean_pdf(src, dst, terms, keep, opts):
    pypdf = pdf_lib()
    if pypdf is None:
        out("pypdf is not installed, so the PDF can't be cleaned here. Either install it "
            "(python -m pip install pypdf) and run again, or clean the source document (.docx, .pptx) "
            "and export the PDF again. Don't send a PDF whose inspection found problems.")
        sys.exit(4)
    from pypdf.generic import NameObject
    writer = pypdf.PdfWriter(clone_from=str(src))
    log = []
    if "metadata" not in keep:
        writer.metadata = None
        if opts.title or opts.author:
            writer.add_metadata({k: v for k, v in (("/Title", opts.title), ("/Author", opts.author)) if v})
        if "/Metadata" in writer.root_object:
            del writer.root_object[NameObject("/Metadata")]
        log.append("removed the Info dictionary and the XMP metadata")
    if "comments" not in keep:
        for page in writer.pages:
            if "/Annots" in page:
                # Links and form fields stay; comments, highlights and notes go.
                kept = [a for a in page["/Annots"] if a.get_object().get("/Subtype") in ("/Link", "/Widget")]
                if kept:
                    page[NameObject("/Annots")] = pypdf.generic.ArrayObject(kept)
                else:
                    del page[NameObject("/Annots")]
        log.append("removed annotations (comments, highlights, notes), kept links")
    names = writer.root_object.get("/Names")
    if names is not None:
        names = names.get_object()
        for key in ("/EmbeddedFiles", "/JavaScript"):
            if key in names:
                del names[NameObject(key)]
                log.append(f"removed {key[1:]}")
    if "/OpenAction" in writer.root_object:
        del writer.root_object[NameObject("/OpenAction")]
        log.append("removed the action on open")
    with open(dst, "wb") as fh:
        writer.write(fh)
    log.append("rewrote the file, which drops earlier saved versions")
    return log


# ---------------------------------------------------------------- commands

def kind_of(path):
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in OFFICE:
        return OFFICE[ext]
    fail(f"unsupported file type {ext}: this script handles .docx, .pptx, .xlsx and .pdf")


def selftest(terms, plants):
    """Plant every term where leftovers hide; the detector must find each one."""
    if not terms:
        return True, "no terms given: nothing to plant (only the structural checks ran)"
    failures, regex_untested = [], []
    for t in terms:
        if t.regex:
            samples = [p for p in plants if t.rx.search(fold(p))]
            if not samples:
                regex_untested.append(t.raw)
                continue
            text = samples[0]
        else:
            text = t.text
        cut = max(1, len(text) // 2)
        no_accents = fold(text)
        xml = ('<w:document xmlns:w="w" xmlns:pic="p"><w:body>'
               f'<w:p><w:r><w:t>x {escape(text[:cut])}</w:t></w:r><w:r><w:rPr><w:b/></w:rPr>'
               f'<w:t>{escape(text[cut:])} y</w:t></w:r></w:p>'
               f'<pic:cNvPr id="1" name="n" descr="Logo {escape(text, True)}"/>'
               f'<Rel Target="file:///C:/x/{urllib.parse.quote(text)}.dotx"/>'
               f'<w:p><w:r><w:t>{escape(no_accents.upper())}</w:t></w:r></w:p>'
               '</w:body></w:document>')
        found = scan_part("selftest", xml, [t])
        kinds = sorted(h[0] for h in found)
        if len(found) < 4 or not any(k.startswith("split") for k in kinds):
            failures.append(f"{t.raw!r}: planted 4, found {len(found)} {kinds}")
        if not t.regex and len(re.sub(r"\W", "", t.text)) <= 4:
            trap = f'<w:p><w:r><w:t>o{escape(t.text.lower())}amente</w:t></w:r></w:p>'
            if scan_part("selftest", trap, [t]):
                failures.append(f"{t.raw!r}: short term matched inside a longer word")
    if regex_untested:
        failures.append(f"no sample for {regex_untested}: give one with --plant (e.g. --plant ID-1234)")
    if failures:
        return False, "FAILED: " + "; ".join(failures)
    return True, f"OK: planted {len(terms)} terms (split across runs, in an attribute, percent-encoded, " \
                 "without accents) and found every one"


def report(path, kind, terms, plants):
    ok, msg = selftest(terms, plants)
    out(f"self-test: {msg}")
    if not ok:
        out("The detector is broken for these terms: don't trust a zero. Fix the terms and run again.")
        sys.exit(3)
    if kind == "pdf":
        findings, hits = inspect_pdf(path, terms)
    else:
        findings, hits = inspect_office(Package(path), kind, terms)
    sections = []
    for s, _ in findings:
        if s not in sections:
            sections.append(s)
    for s in sections:
        out(f"\n## {s}")
        for s2, line in findings:
            if s2 == s:
                out(f"- {line}")
    out(f"\n## term hits ({len(hits)})")
    for k, where, ctx, term in hits:
        out(f"- [{k}] {where}: {ctx!r}  <- {term!r}")
    if not hits:
        out("- none" if terms else "- no terms given")
    return findings, hits


def cmd_inspect(a):
    kind = kind_of(a.file)
    name = Path(a.file).name
    out(f"# scrub inspect: {a.file} ({kind})")
    if any(Path(a.file).with_name("~$" + n).exists() for n in {name, name[2:], name[1:]}):
        out("warning: an Office lock file is next to it; the file may be open with unsaved edits")
    findings, hits = report(a.file, kind, load_terms(a), a.plant or [])
    sys.exit(2 if hits else 0)


def cmd_verify(a):
    kind = kind_of(a.file)
    if kind == "pdf":
        pypdf = pdf_lib()
        if pypdf is None:
            data = Path(a.file).read_bytes()
            ok = data.startswith(b"%PDF-") and b"%%EOF" in data[-1024:]
            out(f"verify: {'OK' if ok else 'FAILED'} (header and trailer only: pypdf is not installed)")
            sys.exit(0 if ok else 1)
        try:
            r = pypdf.PdfReader(a.file)
            for p in r.pages:
                p.extract_text()
            out(f"verify: OK ({len(r.pages)} pages read with pypdf)")
            sys.exit(0)
        except Exception as e:  # noqa: BLE001
            out(f"verify: FAILED ({e})")
            sys.exit(1)
    problems, n = verify_office(a.file)
    for p in problems:
        out(f"- {p}")
    out(f"verify: {'OK' if not problems else 'FAILED'} ({n} parts checked)")
    out(f"deep check: {verify_deep(a.file, kind)}")
    sys.exit(1 if problems else 0)


def cmd_clean(a):
    src, dst = Path(a.src), Path(a.dst)
    kind = kind_of(src)
    if kind_of(dst) != kind:
        fail("the copy must keep the same file type")
    if dst.exists() and dst.resolve() == src.resolve():
        fail("refusing to write over the original: give a new path for the copy")
    if dst.exists():
        fail(f"{dst} already exists: give a new path, or delete it yourself first")
    terms = load_terms(a)
    ok, msg = selftest(terms, a.plant or [])
    out(f"self-test: {msg}")
    if not ok:
        sys.exit(3)
    repl = {}
    for spec in a.replace or []:
        if "=" not in spec:
            fail(f"--replace needs OLD=NEW, got {spec!r}")
        old, new = spec.split("=", 1)
        repl[old] = new
    keep = set(filter(None, (a.keep or "").split(",")))
    unknown = keep - set(CATEGORIES)
    if unknown:
        fail(f"unknown --keep categories {sorted(unknown)}; known: {CATEGORIES}")
    out(f"# scrub clean: {src} -> {dst} ({kind})")
    if kind == "pdf":
        log = clean_pdf(src, dst, terms, keep, a)
        unresolved = []
    else:
        pkg = Package(src)
        before = visible_summary(pkg, kind)
        log, unresolved = clean_office(pkg, kind, terms, repl, keep, a)
        pkg.save(dst)
        after = visible_summary(Package(dst), kind)
    for line in log:
        out(f"- {line}")
    if kind != "pdf":
        out("\n## visible content, original -> copy")
        for k in before:
            flag = "" if before[k] == after.get(k) else "   <- changed: check it was meant to"
            out(f"- {k}: {before[k]} -> {after.get(k)}{flag}")
    if unresolved:
        out(f"\n## left as they were: term hits with no replacement ({len(unresolved)})")
        for k, where, ctx, term in unresolved:
            out(f"- [{k}] {where}: {ctx!r}  <- {term!r}")
        out("Give --replace OLD=NEW for each (NEW may be empty), or fix them by hand, and clean again.")
    out("\n# re-inspection of the copy")
    findings, hits = report(dst, kind, terms, a.plant or [])
    out("\n# verification of the copy")
    if kind == "pdf":
        pypdf = pdf_lib()
        try:
            r = pypdf.PdfReader(str(dst))
            for p in r.pages:
                p.extract_text()
            problems = []
            out(f"verify: OK ({len(r.pages)} pages read with pypdf)")
        except Exception as e:  # noqa: BLE001
            problems = [str(e)]
            out(f"verify: FAILED ({e})")
    else:
        problems, n = verify_office(dst)
        for p in problems:
            out(f"- {p}")
        out(f"verify: {'OK' if not problems else 'FAILED'} ({n} parts checked)")
        out(f"deep check: {verify_deep(dst, kind)}")
    out(f"\ncopy: {dst}")
    sys.exit(1 if problems else 2 if (hits or unresolved) else 0)


def cmd_selftest(a):
    ok, msg = selftest(load_terms(a), a.plant or [])
    out(f"self-test: {msg}")
    sys.exit(0 if ok else 3)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def terms_args(sp):
        sp.add_argument("--term", action="append", help="forbidden term (repeatable)")
        sp.add_argument("--terms-file", action="append", help="file with one term per line")
        sp.add_argument("--plant", action="append", help="sample text for a regex: term, for the self-test")

    sp = sub.add_parser("inspect")
    sp.add_argument("file")
    terms_args(sp)
    sp.set_defaults(func=cmd_inspect)
    sp = sub.add_parser("clean")
    sp.add_argument("src")
    sp.add_argument("dst")
    terms_args(sp)
    sp.add_argument("--replace", action="append", help='"OLD=NEW" (repeatable)')
    sp.add_argument("--author", default="")
    sp.add_argument("--title")
    sp.add_argument("--subject")
    sp.add_argument("--company")
    sp.add_argument("--keep", help="comma-separated categories to leave as they are: " + ", ".join(CATEGORIES))
    sp.set_defaults(func=cmd_clean)
    sp = sub.add_parser("verify")
    sp.add_argument("file")
    sp.set_defaults(func=cmd_verify)
    sp = sub.add_parser("selftest")
    terms_args(sp)
    sp.set_defaults(func=cmd_selftest)
    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()

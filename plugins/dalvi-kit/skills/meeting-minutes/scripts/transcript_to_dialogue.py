"""Turn a meeting transcript into a readable dialogue, one line per speaker turn.

Reads WebVTT (.vtt, including Microsoft Teams cue ids and <v Name> voice tags),
a Word transcript (.docx, as Teams exports it) or plain text from a recorder
(.txt, .md). Drops cue ids, timing lines and markup, skips cues repeated
verbatim, and joins consecutive lines of the same speaker into one turn. A
short cue from someone else that overlaps the current turn ("Uhum.") does not
split it: it is printed right after the turn, marked "(overlapping)".

Output: "[mm:ss] Speaker: text" per turn, to stdout or to --output. Counts per
speaker go to stderr. Standard library only.

Usage: python3 transcript_to_dialogue.py <file> [--output <file>] [--no-times]
"""
import argparse
import html
import re
import sys
import zipfile
from collections import Counter

TIME = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?"
TIMING_LINE = re.compile(rf"^\s*({TIME})\s+-->\s+({TIME})")
VOICE = re.compile(r"<v(?:\.[\w.-]+)*\s+([^>]+)>")
TAG = re.compile(r"</?[^>]+>")
HEADER_BLOCKS = ("WEBVTT", "NOTE", "STYLE", "REGION")

# Plain-text layouts seen in recorder and Teams exports.
TIME_SPEAKER_TEXT = re.compile(rf"^\[?({TIME})\]?\s*[-–]?\s*([^:\[\]]{{1,60}}?):\s+(.+)$")
SPEAKER_TIME_TEXT = re.compile(rf"^([^:\[\]\d][^:\[\]]{{0,59}}?)\s*[\[(]({TIME})[\])]\s*:?\s+(.+)$")
SPEAKER_TEXT = re.compile(r"^([^:\[\]\d][^:\[\]]{0,59}?):\s+(.+)$")
SPEAKER_TIME_HEADER = re.compile(rf"^([^:\[\]\d][^\[\]]{{0,59}}?)\s+[\[(]?({TIME})[\])]?\s*$")
TIME_ONLY = re.compile(rf"^\[?({TIME})\]?\s*$")


def seconds(t):
    t = t.replace(",", ".")
    parts = [float(p) for p in t.split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def clean(text):
    text = TAG.sub("", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_vtt(raw):
    """Return cues as (start, end, speaker, text)."""
    cues = []
    for block in re.split(r"\r?\n\s*\r?\n", raw.lstrip("﻿")):
        lines = [l for l in block.splitlines() if l.strip()]
        if not lines or lines[0].startswith(HEADER_BLOCKS):
            continue
        idx = next((i for i, l in enumerate(lines) if TIMING_LINE.match(l)), None)
        if idx is None:
            continue
        m = TIMING_LINE.match(lines[idx])
        start, end = seconds(m.group(1)), seconds(m.group(2))
        payload = "\n".join(lines[idx + 1:])
        voices = list(VOICE.finditer(payload))
        if not voices:
            text = clean(payload)
            if text:
                cues.append((start, end, "", text))
            continue
        for i, v in enumerate(voices):
            stop = voices[i + 1].start() if i + 1 < len(voices) else len(payload)
            text = clean(payload[v.end():stop])
            if text:
                cues.append((start, end, v.group(1).strip(), text))
    cues.sort(key=lambda c: c[0])  # stable: same-start cues keep file order
    return cues


def docx_lines(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    lines = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        pieces = re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>|<w:(tab|br)/>", para, re.S)
        text = "".join(t if t else ("\t" if kind == "tab" else "\n") for t, kind in pieces)
        lines.extend(html.unescape(text).splitlines() or [""])
    return lines


def parse_text(lines):
    """Return cues as (start, end, speaker, text); end is unknown (= start)."""
    cues, speaker, start = [], "", 0.0
    for line in lines:
        line = line.strip()
        if not line or line.upper() == "WEBVTT":
            continue
        m = TIMING_LINE.match(line)
        if m:
            start = seconds(m.group(1))
            continue
        m = TIME_SPEAKER_TEXT.match(line)
        if m:
            start, speaker = seconds(m.group(1)), m.group(2).strip()
            cues.append((start, start, speaker, clean(m.group(3))))
            continue
        m = SPEAKER_TIME_TEXT.match(line)
        if m:
            speaker, start = m.group(1).strip(), seconds(m.group(2))
            cues.append((start, start, speaker, clean(m.group(3))))
            continue
        m = SPEAKER_TIME_HEADER.match(line) or None
        if m and len(m.group(1).split()) <= 6:
            speaker, start = m.group(1).strip(), seconds(m.group(2))
            continue
        m = TIME_ONLY.match(line)
        if m:
            start = seconds(m.group(1))
            continue
        m = SPEAKER_TEXT.match(line)
        if m and len(m.group(1).split()) <= 6:
            speaker = m.group(1).strip()
            cues.append((start, start, speaker, clean(m.group(2))))
            continue
        cues.append((start, start, speaker, clean(line)))
    return cues


def to_turns(cues):
    """Join consecutive cues of one speaker; overlapping short cues don't split a turn."""
    seen, dup = set(), 0
    turns, held = [], []  # turn: [start, speaker, [texts], end, overlapping]
    for start, end, who, text in cues:
        key = (round(start, 1), who, text.lower())
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        cur = turns[-1] if turns else None
        if cur and who == cur[1]:
            if cur[2] and cur[2][-1].lower() == text.lower():
                dup += 1
                continue
            cur[2].append(text)
            cur[3] = max(cur[3], end)
            continue
        if cur and end > start and cur[0] < start < cur[3] and end <= cur[3]:
            held.append([start, who, [text], end, True])  # inside the current turn
            continue
        turns.extend(held)
        held = []
        turns.append([start, who, [text], end, False])
    turns.extend(held)
    return turns, dup


def stamp(s):
    s = int(s)
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file")
    ap.add_argument("--output", "-o")
    ap.add_argument("--no-times", action="store_true")
    args = ap.parse_args()

    path = args.file
    if path.lower().endswith(".docx"):
        lines, kind = docx_lines(path), "docx"
        cues = parse_vtt("\n".join(lines)) if any("-->" in l for l in lines) else parse_text(lines)
    else:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()
        if raw.lstrip().startswith("WEBVTT") or TIMING_LINE.search(raw[:2000] or ""):
            cues, kind = parse_vtt(raw), "webvtt"
        else:
            cues, kind = parse_text(raw.splitlines()), "text"

    turns, dup = to_turns(cues)
    out = []
    for start, who, texts, _end, overlapping in turns:
        name = (who or "?") + (" (overlapping)" if overlapping else "")
        prefix = "" if args.no_times else f"[{stamp(start)}] "
        out.append(f"{prefix}{name}: {' '.join(texts)}")
    text = "\n".join(out) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(text)

    words = Counter()
    count = Counter()
    for _s, who, texts, _e, _o in turns:
        count[who or "?"] += 1
        words[who or "?"] += sum(len(t.split()) for t in texts)
    total = sum(words.values()) or 1
    print(f"format {kind} | cues {len(cues)} | duplicates skipped {dup} | turns {len(turns)}",
          file=sys.stderr)
    for who, n in count.most_common():
        print(f"  {who}: {n} turns, {words[who]} words ({100 * words[who] // total}%)",
              file=sys.stderr)


if __name__ == "__main__":
    main()

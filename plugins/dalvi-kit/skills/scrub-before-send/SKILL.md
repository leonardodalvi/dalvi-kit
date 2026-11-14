---
name: scrub-before-send
description: Use when a .docx, .pptx, .xlsx or .pdf is about to leave the team (sent to a client or partner, published, attached to an email, uploaded to a portal), and above all when it was made from another client's file ("reaproveitei a proposta do cliente X", "confere se dá para enviar", "vou mandar para o cliente"). Also when the user asks to remove metadata, author, comments, tracked changes, hidden slides, speaker notes, alt text or internal IDs from a file, or asks what a file carries beyond what shows on screen. Not for reading, summarizing or editing a file that stays in-house.
---

# Scrub Before Send

## Overview

A file reused from another client keeps that client where the screen doesn't
show it: the title in the file properties, the alt text of a logo, a header, the
path of a linked template, a comment, a tracked deletion, a hidden slide,
speaker notes, a number split into several runs that search can't find.
Swapping what shows on screen doesn't remove any of that.

Two other things go wrong as often: the original gets overwritten, and the
cleanup changes things nobody approved (a logo removed, a sentence rewritten,
an internal ID swapped for some other number). So the original is only read,
the user decides what goes before anything changes, and the copy gets inspected
again before you hand it over. A search that finds nothing proves nothing until
the detector has found a term you planted.

Answer in the user's language.

## 1. Collect the forbidden terms

- Read the project's `CLAUDE.md`, `AGENTS.md` or your harness's instructions
  file: lists of terms, internal ID patterns, where files for clients go.
- Add what the request says: the previous client's name, its short forms and
  acronyms, its proposal or contract numbers, internal ticket IDs, people's
  names.
- Write them to a file in the OS temp dir, one per line. `regex:OPS-\d{4}` for
  a pattern; a pattern needs a sample for the self-test (`--plant OPS-1234`).
  A file avoids the shell eating backslashes.
- No list in the project and none in the request: run step 2 without terms,
  then propose candidates from what it shows (a name in the title, a header or a
  comment that is not the recipient's) and ask.

## 2. Inspect, without changing anything

```bash
python3 <this skill's folder>/scripts/scrub.py inspect "<file>" --terms-file "<terms>" [--plant OPS-1234]
```

(`python` on Windows.) The script only reads the file. It first plants every
term (split across two runs, in an attribute, percent-encoded, without
accents), checks it finds them, and stops with exit code 3 if it doesn't. Then
it lists, by section: metadata, custom properties, linked template, external
links, thumbnail, alt text, headers and footers, comments, tracked changes,
linked fields (`INCLUDEPICTURE` with a local path), hidden slides, speaker
notes, hidden sheets, defined names, pivot caches, data connections, embedded
objects, image metadata, orphan parts, and every term hit with its part and
context. Read all of it, not only the hits: a title that names a third company
is a leftover even if it's on no list.

For each file to be sent, run it once. An embedded object is a file inside the
file: extract it to the temp dir and inspect it too.

Without Python, unzip the file into the temp dir and read the places in the
reference table below. Search the text of each paragraph joined, not each run.

## 3. Report and let the user decide

Write the report in this order:

1. **Verdict:** can it go as it is? With any finding, no.
2. **On screen:** term hits in the body, the slides or the headers, each with
   where it is and the exact text. The request usually names the new
   recipient: propose it in place of the previous one's name, here and in alt
   text, and show the resulting text ("Proposta Nº … · New Client"), so the
   user's OK covers it. For anything else (a number, an ID, a sentence), ask
   what replaces it or whether it goes.
3. **Off screen, removed by default:** each finding with its value: author and
   last modified by, title, custom properties, linked template, comments,
   tracked changes (accepted), linked fields, hidden slides, speaker notes,
   thumbnail, image metadata. The author goes even when no rule names it: a
   colleague's name is personal data and goes with the file.
4. **Kept unless the user says otherwise:** the sender's company, links to the
   sender's site, alt text that describes the image correctly. A company that
   is neither the recipient nor a previous client is probably the sender: keep
   it, and ask.
5. **What can't be cleaned here,** and what to do about it (see step 4).
6. **The question:** which items go, and the replacements.

Then wait. Change nothing before the user answers. "Clean it all" after seeing
the report approves the items listed, with the replacements they gave; a hit on
screen with no replacement is still an open question.

## 4. Clean a copy

```bash
python3 <this skill's folder>/scripts/scrub.py clean "<original>" "<copy>" --terms-file "<terms>" \
  --replace "Previous Client=New Client" --replace "PRO-1111=PRO-2222" [--title "..."] [--keep notes]
```

- **The copy:** where the project says files for clients go; otherwise next to
  the original, with `-clean` before the extension. The script refuses to write
  over the original or over an existing file.
- **Removed by default:** author and last modified by (`--author` to set a
  name), revision count, last printed, editing time, template name and the
  list of titles in `app.xml`, custom properties, the linked template, comments and the list of
  their authors, tracked changes (accepted, so the text is what the final view
  shows), linked fields (the field goes, what it shows stays), hidden slides,
  speaker notes, the thumbnail, EXIF/XMP/text chunks in images, parts nothing
  refers to. `--keep` leaves a category as it is; use it for what the user
  chose to keep.
- **Terms:** replaced where `--replace` says. A term with no replacement is
  blanked in metadata and alt text, and left in place everywhere else, listed
  as unresolved: ask the user, or edit the copy by hand.
- **Only what was approved changes.** Don't remove a picture, reword a sentence,
  fix the tone or swap the sender's company on your own. Something new found
  while cleaning goes back to the user before it changes.
- **Not cleaned by the script:** in `.xlsx`, hidden sheets, defined names,
  external links, pivot caches and data connections, because formulas depend
  on them. Fix them in Excel on the copy (File > Info > Check for Issues >
  Inspect Document) and inspect again. Embedded objects: clean the inner file
  and replace it, or remove the object, as the user decides. Text on screen the
  user wants rewritten: edit the copy, then inspect again.
- **PDF:** cleaning needs `pypdf`. Without it, ask before installing
  (`python -m pip install pypdf`), or clean the source document and export the
  PDF again. That is also the only fix for text on a page, and the PDF takes its
  title and author from the source, so clean the source first.

## 5. Check the copy

`clean` inspects the copy again and verifies it. Read the output:

- self-test OK and **zero term hits**;
- the remaining sections hold only what the user chose to keep;
- **visible content, original → copy:** paragraphs, pictures, slides shown.
  Anything that changed must be something the user approved;
- **verify OK:** the zip, every XML part, every relationship and content type,
  plus opening it with `python-docx`/`python-pptx`/`openpyxl` when installed.

Exit code 2 means something is left: don't hand it over, go back to the user.
When available, also convert the copy (`soffice --headless --convert-to pdf
--outdir <temp dir> "<copy>"`) or run the OOXML validator of a `docx`/`pptx`
skill. Say which checks ran and which didn't: if nothing opened the file in
Word or PowerPoint, say so.

## 6. Hand over

Tell the user, in their language:

- the full path of each clean copy, and that the original is unchanged;
- what was removed and what was replaced, by category;
- what is left and why (kept by choice, can't be cleaned here);
- which checks ran, and which didn't.

Delete the terms file and anything extracted into the temp dir. Don't send the
file yourself: sending is the user's step.

## Where leftovers hide

| Format | Places |
| --- | --- |
| all Office | `docProps/core.xml` (title, subject, author, last modified by, keywords, description), `docProps/app.xml` (template, company, manager, titles list), `docProps/custom.xml`, `docProps/thumbnail.*`, `customXml/`, alt text (`descr`/`title` on `wp:docPr`, `pic:cNvPr`, `p:cNvPr`), image EXIF/XMP, `embeddings/`, every `.rels` (paths, percent-encoded) |
| docx | `word/_rels/settings.xml.rels` (`attachedTemplate`), headers and footers, `word/comments*.xml`, `word/people.xml`, `w:del`/`w:ins`, `INCLUDEPICTURE`/`INCLUDETEXT`/`LINK` fields, `word/glossary/` |
| pptx | slides with `show="0"`, `ppt/notesSlides/`, `ppt/comments/`, `commentAuthors.xml`/`authors.xml`, layouts and masters (footers), shape names |
| xlsx | sheets with `state="hidden"`/`veryHidden`, defined names, `xl/externalLinks/`, `xl/pivotCache/` (a copy of the source data), `xl/connections.xml`, hidden rows and columns, comments and `xl/persons/` |
| pdf | Info dictionary, XMP, annotations, attachments, JavaScript, form values, bookmarks, layers, earlier saved versions (incremental updates) |

## Red flags: stop and correct

| Thought | Reality |
| --- | --- |
| "I swapped everything on screen" | Title, alt text, header, template path, comments, notes, hidden slides are off screen. Inspect. |
| "The search found nothing" | A number split across runs isn't found run by run. A zero counts only after the self-test found the planted terms. |
| "I'll clean the original; there's a backup" | The original is only read. The copy is a new file. |
| "The rule only lists client names; the author can stay" | A colleague's name goes with the file. Remove it by default and say so. |
| "The logo's alt text names the old client, so I'll remove the logo" | Report it. The user decides what happens to a picture. |
| "I'll put the new proposal number where the internal ID was" | Text on screen is replaced only with what the user gave. Ask. |
| "They said 'clean it all'" | All of what the report listed. New findings go back to them first. |
| "Hiding the slide is enough" | A hidden slide goes with the file. Delete it. |
| "No pypdf: I'll grep the PDF bytes" | Page text is usually encoded. A zero there proves little. |
| "The XML parses, so the file opens" | Run verify, and say what didn't run (Word, PowerPoint, a conversion). |

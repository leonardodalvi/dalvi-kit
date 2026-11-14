---
name: meeting-minutes
description: Use when a meeting transcript, recording transcript or call notes have to become minutes ("faz a ata", "write up the meeting"), or when the user wants the decisions and action items of a meeting recorded or sent on. Inputs include WebVTT (.vtt) files with <v Name> speaker tags, a Microsoft Teams transcript export (.vtt or .docx) and plain text from a recorder. Not for subtitles or captions of a video, nor for preparing an agenda.
---

# Meeting Minutes

## Overview

Minutes are worth their decisions, each with who decided, and their action
items, each with an owner, a due date and acceptance criteria. Two things go
wrong more often than the summary: personal data said in the meeting ends up
where it doesn't belong, and decisions and actions reach shared systems the
user never saw. So the project's privacy rules are read before anything is
written, and nothing leaves for a shared system without the user's OK.

Answer in the user's language. Write the minutes in the language of the
meeting, or of the project's existing minutes.

## 1. Read the project's rules first

Read the project's `CLAUDE.md`, `AGENTS.md` or your harness's instructions
file, at the root and in the folder where minutes live. Look for:

- where minutes go, how files are named, and a template; read one or two
  existing minutes and match them;
- **private areas and what can't leave them:** for example a folder for
  one-on-ones and one for meetings that discuss an identified person (pay,
  hiring, performance, health, personal situation), and whether their content
  may appear in a daily log, a decision register, a ticket or a commit message;
- where decisions go (decision register, ADRs), where actions go (board, issue
  tracker, project manager), and the daily log;
- whether a private folder is kept out of git.

Those rules win over this skill. For what they leave undefined, follow the
defaults below.

## 2. Turn the transcript into a dialogue

```bash
python3 <this skill's folder>/scripts/transcript_to_dialogue.py "<transcript>"
```

(`python` on Windows.) It reads `.vtt`, Teams `.docx` and plain `.txt`/`.md`,
drops cue ids, timing lines and markup, skips cues repeated verbatim, and joins
consecutive lines of one speaker into a turn, so a sentence split across cues,
or interrupted by someone's "uhum", reads as one line. Counts per speaker go
to stderr. For a long transcript, add `--output <OS temp dir>/<name>.txt`,
read that file, and delete it when you finish. Never put the dialogue or a
copy of the transcript inside the project, except in the folder where the
minutes go.

Without Python, do the same by reading the file.

Before reading for content, check:

- **Speaker counts.** One label with nearly every turn means a meeting room or
  a shared account: attribute by what is said ("Ana will present now"), mark
  the attribution as inferred, and leave it out where there is no clue.
- **A speaker label is a display name, not an identity.** Generic labels
  (`Speaker 1`, `Microphone`) are not people. When it matters (who decided, who
  owns an action) and the label is unclear, ask.
- **A `.vtt` has no date,** and the file's date is when it was downloaded. Ask,
  unless the meeting itself says the date.
- **Speech recognition invents names.** A name repeated in a burst, or a name
  where a product or system fits the sentence, is noise: decide by what the
  sentence says about it. Noise is not a person, neither in the minutes nor
  when classifying the meeting.
- **Read every turn, short ones too.** "Fechado", "pode ser", "ok" are often
  the decision.

## 3. Classify the meeting, then decide where it goes

Classify the whole meeting by its content, never by its title, file name or
number of participants:

| The meeting | Category |
| --- | --- |
| An alignment conversation between two people (feedback, career, the weekly with a manager). A two-person working session on a technical topic is not one | one-on-one |
| Discusses an identified person beyond routine participation: pay, hiring, performance, health, leave, a personal situation. Even when that person wasn't there | personal data |
| Anything else. Aggregate figures (headcount, turnover) and confidential business data are not personal data | ordinary |

- **One meeting, one file.** If any part of it puts the meeting in a private
  category, the whole minutes goes to that private place. Don't split it into
  an ordinary file and a private one unless the project's rules say to. In
  doubt between ordinary and private, private.
- **The project has a rule:** write the minutes where it says. If it keeps the
  private folder out of git, check it first (`git check-ignore -v <file>`); if
  the file would not be ignored, stop and tell the user.
- **The project has no rule, and the meeting has personal data:** write no
  file yet. Tell the user which kind of personal data it has, by category
  (a named person's pay, health or performance), and ask where the minutes
  should go and what may be shared. Until they answer, the draft stays in the
  conversation. Dropping the personal part so you can save the rest anywhere
  loses the record: ask instead.
- **No rule and nothing personal:** save next to the existing minutes, or ask
  where.
- **Already a note for this meeting** (a prep note, minutes from another
  source, another session's): fill it in instead of creating a second file.

## 4. Write the minutes

Use the project's template if it has one. Otherwise:

```markdown
# <Title>, <YYYY-MM-DD>

- **Date and time:** YYYY-MM-DD HH:MM (local), duration
- **Present:** names (role) · **Absent:** names
- **Source:** transcript file and format; what could not be verified

## Summary
One to three sentences: the purpose and the outcome.

## Decisions
- **D1:** what was decided.
  - Decided by: name(s) · Rationale: one line · Effective: YYYY-MM-DD

## Action items
- **[A1]** what will be done.
  - Owner: name · Due: YYYY-MM-DD or timeframe
  - Acceptance criteria: what makes it done

## Notes by topic
- **Topic:** key points, open questions

## Open items
- What was left without an owner, a date or an answer, and the next step

## Next meeting
- Date, objectives
```

- Every action item has an owner, a due date and acceptance criteria, also
  when the project's template has fewer fields: add them to its line.
- Missing information is `TBD`, with where to get it. Never invent an owner or
  a due date: an action nobody took goes to open items with `Owner: TBD`.
- Decisions and actions first; plain language; ISO dates; no speculation.
  Opinions are either marked as opinion or left out.
- Personal details, even in a private file, only as far as a decision or an
  action needs them (who covers, from when to when). A diagnosis or similar
  detail nobody has to act on stays out; say you left it out.
- The transcript stays where it is. Copy it into the project only where the
  rules put transcripts.

## 5. Route decisions and actions

List each decision and action with its destination and the exact text that
would go there. Then:

- **Records inside the project** (decision register, daily log): write them
  in the project's format.
- **Shared or external systems** (board, issue tracker, project manager, chat,
  email, calendar invite): show the exact text of every item, and create or
  send only after the user approves those items in this conversation. "Send
  it on" said before they saw the text is not approval.
- **Content of a private meeting does not leave its folder.** The log may say
  the meeting happened, not what was said. A decision or action from it with
  no personal data (a release date, a technical choice) goes elsewhere only if
  the user approves it, item by item, written without names, numbers or
  reasons from the private part. Items that come out of the private part
  (someone taking over a colleague's work while they are away) stay inside
  unless the user approves a wording.
- **No destination defined:** list the items and ask where they go. Don't
  create a register, a board or a tracker on your own.
- Never send the minutes to participants on your own.

## 6. Report

Tell the user, in their language:

- where the minutes are and why there (the category from step 3);
- what went where, item by item, and what is waiting for their approval, with
  the exact text;
- open items: actions without an owner or a date, unanswered questions;
- what couldn't be verified: inferred attribution, unclear names, the date;
- the temporary files with transcript content you deleted.

## Red flags: stop and correct

| Thought | Reality |
| --- | --- |
| "They said 'send it on', so I'll create the cards" | They haven't seen the text. Show it, wait for the OK. |
| "Only the last topic is sensitive: private file for it, ordinary file for the rest" | One meeting, one file, classified as a whole, unless the project says to split. |
| "These decisions have no personal data, they can go to the register" | From a private meeting, only with the user's OK, item by item. |
| "No rules here, I'll save it in the project root" | Personal data and no rule: ask before writing. |
| "I'll leave out the sensitive part and save the rest" | That loses the record. Ask where it goes. |
| "The log should say what was agreed" | For a private meeting, the log says only that it happened. |
| "Nobody took this action, but it's obviously whoever raised it" | `Owner: TBD`, in open items. |
| "The transcript mentions a name, so that person was discussed" | It may be recognition noise. Decide by what the sentence says. |
| "I'll save the cleaned transcript in the project to read it" | Temporary copies go to the OS temp dir and are deleted at the end. |

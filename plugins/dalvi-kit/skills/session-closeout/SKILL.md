---
name: session-closeout
description: Use only when the user explicitly asks to end, close or wrap up the working session, with words like "wrap up", "close the session", "let's end the session here", "encerra a sessão", "fecha a sessão" or "pode encerrar". Not when the task merely looks finished, when the user only says thanks or that they have to leave, or because you decided it is a good moment to stop.
---

# Session Closeout

## Overview

Closing a session leaves the next one able to start cold, and the repository
with exactly this session's work committed. In order: record the procedures
and fixes found, append to today's log, rewrite the state, then commit only
the files this session touched.

**The working tree is shared.** Other sessions, the user and tools leave
changes in it. A modified file is not evidence that you modified it, and
`git status` cannot tell whose change is whose. Only your own actions in this
conversation can.

Run this only when the user explicitly asked to close the session. If you
think the work is done, say so or offer to close; don't start on your own.
Answer in the user's language, and write the records in the language the
project's notes already use.

## First: the project's rules

Read the project's `CLAUDE.md`, `AGENTS.md` or your harness's instructions
file, at the root and in the folders you worked in. Look for:

- where procedures and fixes go, and whether an index lists them;
- the daily log: path, entry format, append-only or not;
- the state or handoff file: path, sections, rewritten or appended;
- commits: message format and language, trailers required or forbidden,
  whether to push, paths that must never be committed.

Those rules win over this skill and over your harness's commit defaults: a
project that forbids `Co-authored-by` gets no such trailer. For whatever they
leave undefined, see "When the project defines nothing".

## 1. Take stock before writing anything

1. **List the files this session touched**, from your own tool calls in this
   conversation: created, edited, deleted, renamed, or written by a command
   or script you ran. Steps 2 to 4 add the records you write.
2. **Snapshot the tree:** `git status --porcelain -uall` and
   `git diff --cached --name-only`. Every path that is not on your list is a
   change you didn't make. Don't call it "your change" to the user: you don't
   know whose it is.
3. **If the index already holds changes you didn't stage, stop and ask.** Any
   commit would carry them.
4. **Mark your files that also hold someone else's work:** tracked files
   whose `git diff` has lines you didn't write, and untracked files that
   existed before you first wrote to them (today's log, often).

If part of the closeout already happened earlier in the session, don't
repeat it: finish what is missing.

## 2. Record procedures and fixes

Go back over the session for:

- each procedure discovered: a command, flag, path or sequence that worked
  and was not obvious;
- each solution found after an error: the symptom (the error message), the
  cause, the fix;
- each wrong turn that cost real time, and what would have avoided it.

One note each, in the project's place and shape, plus the index row if the
project keeps an index. Search first: if a note already covers it, update
that note instead of writing a second one.

## 3. Append to today's log

Add this session's entry **at the end** of today's file, in the project's
format: what was done, decisions, what is pending, links to the notes from
step 2. Never edit an earlier entry, yours or anyone else's. If the file does
not exist, create it.

## 4. Rewrite the state

Rewrite the state or handoff file the way the project defines it: current
status, next step, blockers, links. Keep it short; link to commits, notes,
issues and docs instead of copying them. If the file had changes you didn't
make (step 1), keep them and tell the user.

In all three records: no secrets, tokens or personal data.

## 5. Stage only this session's work

For each file on your list:

| File | Stage it with |
| --- | --- |
| Tracked, and every line of `git diff -- <file>` is yours | `git add -- <file>` |
| Tracked, and the diff also has lines you didn't write | only your lines (below) |
| Untracked, and you created it | `git add -- <file>` |
| Untracked, and it existed before you wrote to it | nothing: leave it out and tell the user |
| Deleted or renamed by you | `git add -- <old path> <new path>` |

Never `git add -A`, `git add .`, `git add <folder>`, `git add -u`,
`git commit -a` or `git stash`. Stash rewrites other sessions' files and can
drop their work on a conflict.

**Only your lines of a shared file.** Build the staged version from the index
plus your change, without touching the working tree. Run it in a POSIX shell
(Git Bash on Windows): PowerShell's `>` re-encodes the output.

```bash
f=docs/index.md
tmp=$(mktemp)                    # outside the repository
git show ":$f" > "$tmp"          # the staged version, without anyone's pending lines
# Apply exactly your change to "$tmp", with your file-edit tool or a short
# script: append your row, or make the same replacement you made in "$f".
# Find the spot in "$tmp", not in "$f": there it may sit inside lines you
# didn't write. Copy your lines byte for byte from "$f".
blob=$(git hash-object -w --path="$f" "$tmp")
mode=$(git ls-files -s -- "$f" | cut -d' ' -f1)
git update-index --cacheinfo "$mode,$blob,$f"
git diff --cached -- "$f"        # must show only your lines
git diff -- "$f"                 # stays pending: only the lines you didn't write
rm "$tmp"
```

If you can't tell your lines from the others, ask the user. Finish with
`git diff --cached --stat`: only your files.

## 6. Scan the staged diff for secrets

Don't count on a hook: it may be missing or skipped. List the staged files
whose changed lines look like a credential, without printing the lines:

```bash
git diff --cached --name-only -i -G '(password|passwd|secret|token|api[_-]?key|bearer|private key|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20}|xox[abpr]-|sk-[A-Za-z0-9]{20})'
```

For each file listed, read your added lines in it. A real credential:
unstage the file, remove the value, tell the user, never commit it. A word in
prose ("the token expires daily") is fine; say you checked. If the project
forbids personal data in commits, check for that too.

## 7. Commit

- Commit in a step of its own, right after reading the final
  `git diff --cached`. If you change any file after the scan, stage it, read
  the diff and scan again.
- The message follows the project's format, language and trailer rules.
- More than one line: write it to a file outside the repository and run
  `git commit -F <file>`. No `-m` with a here-string or nested quotes.
- Plain `git commit -F <file>`: no paths, no `-a`, no `--no-verify`.
  `git commit -- <file>` commits the working-tree file, everyone's lines
  included, and throws away the index you built.
- If a hook fails, fix the cause and commit again. Don't bypass it.
- Found a mistake after committing: fix it in a new commit. No `--amend`:
  another session may have committed since, and `HEAD` would be theirs.
- Push only if the project says the closeout pushes. Default: a local commit,
  no push.

## 8. Verify and report

- `git show --stat HEAD`: exactly your files.
- `git status --porcelain -uall`: what is left matches the step 1 snapshot,
  plus whatever you left out on purpose.

Tell the user, in their language:

- the commit hash and subject, and whether it was pushed;
- what was left out and why: changes you didn't make, today's log when it
  holds other sessions' entries, anything flagged in step 6;
- the procedures recorded, and the next step from the state.

## When the project defines nothing

- **No place for procedures, log or state:** don't create one in the
  repository. Write a handoff note (what was done, procedures and fixes
  found, state, next step) in the OS temporary directory (`$TMPDIR`, else
  `/tmp`; `%TEMP%` on Windows), give its path, and ask where the user wants
  it kept.
- **No commit rules:** a one-line imperative summary in the style and
  language of `git log --oneline -10`. Local commit, no push.
- **Not a git repository:** skip steps 5 to 7 and say so.

## Red flags: stop and correct

| Thought | Reality |
| --- | --- |
| "It's all from this task, `git add -A`" | `git status` shows the tree, not who changed it. Stage from your list. |
| "It's on my list, `git add` it" | Read its diff first. Lines you didn't write stay out. |
| "Today's log is untracked: add it, or a copy with only my entry" | It holds other sessions' entries, and git has no version of it to build on. Leave it out and say so. |
| "Stash the rest, commit, pop" | Stash rewrites other sessions' files. Build the index instead. |
| "`git commit -- <file>`, to be explicit" | That commits the working-tree file, everyone's lines included. |
| "No hook here, so no secret check" | Scan the staged diff yourself. |
| "Quick fix to the note, then commit in the same command" | Stage, read the diff and scan again, then commit. |
| "`--amend` the fix into my commit" | `HEAD` may already be another session's. New commit. |
| "My harness adds `Co-Authored-By`" | The project's rule wins. |
| "Push it, so it's safe" | Only if the project says so. |
| "That's the user's change" | You don't know whose it is. Say it's a change you didn't make. |
| "The work is done, I'll close the session" | Only when the user asks. Offer instead. |

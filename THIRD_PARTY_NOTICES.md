# Third-party notices

## grill-me and grilling

The skills `grill-me` and `grilling` in `plugins/dalvi-kit/skills/` are
derived from [mattpocock/skills](https://github.com/mattpocock/skills).
The only change: `grill-me` adds a note that, in Claude Code, the `grilling`
skill is listed under this plugin's namespace as `dalvi-kit:grilling`.

They are distributed under the original license:

```
MIT License

Copyright (c) 2026 Matt Pocock

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## web-design-guidelines

`plugins/dalvi-kit/skills/web-design-guidelines/SKILL.md` is derived from
[vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)
(commit `ba46938`). That repository states in its README that it is licensed
under MIT; it ships no LICENSE file with a copyright line. The only change:
the skill reads the bundled `references/command.md` instead of fetching the
guidelines from the internet on every review.

`plugins/dalvi-kit/skills/web-design-guidelines/references/command.md` is an
unmodified copy of `command.md` from
[vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines)
(commit `4ecfb9f`), distributed under its license:

```
MIT License

Copyright (c) 2025 Vercel Labs

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## playwright-cli

`plugins/dalvi-kit/skills/playwright-cli/` (`SKILL.md` and `references/`) is
an unmodified copy of `skills/playwright-cli` from
[microsoft/playwright-cli](https://github.com/microsoft/playwright-cli)
(commit `745fbc7`).

Copyright (c) Microsoft Corporation. Licensed under the Apache License,
Version 2.0. The full license text ships with the skill, in
`plugins/dalvi-kit/skills/playwright-cli/LICENSE.txt`, so it travels with
every copy of the skill. The upstream repository has no NOTICE file.

The only file added to that folder is `agents/openai.yaml` (Codex metadata),
written for this kit.

## prod-data-guard

`plugins/dalvi-kit/skills/prod-data-guard/` was written for this kit. Its
exploration phase generalizes the approach of the `schema-exploration` skill
of [timescale/pg-aiguide](https://github.com/timescale/pg-aiguide) (commit
`1aef6e4`), which covers PostgreSQL only, to other databases, REST APIs and
input files.

Copied text is limited to two PostgreSQL queries in
`references/exploration-recipes.md`, the "context" and the "relations in one
schema" queries, adapted from `skills/schema-exploration/references/overview.md`.
Changes: columns removed (`search_path`, `oid`, `owner`, schema usage,
`populated`), `current_role_has_table_select` renamed to `can_select`, an
inline comment dropped, reformatted. The file says so next to the queries.

Copyright 2025 Timescale, Inc., d/b/a Tiger Data. Licensed under the Apache
License, Version 2.0. The license text and the upstream NOTICE file ship with
the skill, unmodified, in `plugins/dalvi-kit/skills/prod-data-guard/LICENSE`
and `plugins/dalvi-kit/skills/prod-data-guard/NOTICE`. They cover the adapted
queries; the rest of the skill is this kit's own text.

## session-closeout

`plugins/dalvi-kit/skills/session-closeout/` was written for this kit,
starting from the `handoff` skill of
[mattpocock/skills](https://github.com/mattpocock/skills) (commit `5863806`,
`skills/productivity/handoff/SKILL.md`). From it come the handoff note in the
OS temporary directory, used when the project defines no place for the
records, the advice to link to existing artifacts instead of copying them,
and keeping secrets and personal data out of the records. One phrase is
adapted: the temporary directory given as "`$TMPDIR`, else `/tmp`; `%TEMP%`
on Windows". The `retro` skill of the same repository
(`skills/engineering/retro/SKILL.md`) inspired going back over the session's
errors and wrong turns; no text was copied from it.

Both are distributed under the MIT License, Copyright (c) 2026 Matt Pocock,
whose full text is in the "grill-me and grilling" section above.

The `wrap-up` skill of
[rohitg00/pro-workflow](https://github.com/rohitg00/pro-workflow) (commit
`86d5f27`) declares no license. Only ideas were taken from it (an end-of-session
audit of the changes and a note for the next session); no text was copied.

## meeting-minutes

`plugins/dalvi-kit/skills/meeting-minutes/SKILL.md` is adapted from
`skills/meeting-minutes/SKILL.md` of
[github/awesome-copilot](https://github.com/github/awesome-copilot) (commit
`68e5889`). Kept from it: the structure of the minutes, with each decision
recording who decided, a one-line rationale and the effective date, and each
action item its owner, due date and acceptance criteria; `TBD` for missing
information; decisions and actions first, plain language, ISO dates and no
speculation; opinions marked as such or left out; and keeping personal data
out of what is published.

Changes: the text was rewritten and condensed, and the template reduced
(agenda, risks, attachments and the version log dropped). Removed: the limit
to meetings of up to 60 minutes, times in UTC, the required clarifying
questions (replaced by asking only for what is missing: the date, an unclear
identity, the destination), the example prompts, and the step that publishes
the minutes and creates tasks in the team's tracker. Added for this kit:

- reading transcripts as input: WebVTT with `<v Name>` voice tags, the
  Microsoft Teams export and plain text from a recorder, with
  `scripts/transcript_to_dialogue.py`, which drops timing lines and duplicated
  cues and joins consecutive lines of one speaker; and the checks on shared
  accounts, display names, missing dates and speech-recognition noise;
- a privacy step before writing: read the project's rules on private meetings,
  classify the whole meeting, write the minutes in the right place, and ask
  first when the project has no rule and the meeting has personal data;
- routing each decision and action to the destination the project defines,
  with the user's approval before anything is created or sent in a shared or
  external system, and nothing from a private meeting leaving its folder
  without approval.

`scripts/transcript_to_dialogue.py` and `agents/openai.yaml` were written for
this kit.

The upstream skill is distributed under the MIT License:

```
MIT License

Copyright GitHub, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## scrub-before-send

`plugins/dalvi-kit/skills/scrub-before-send/` (`SKILL.md`, `agents/openai.yaml`
and `scripts/scrub.py`) was written for this kit. The script uses only the
Python standard library, plus `pypdf` through its public API when it is
installed.

No code or text was copied from third parties. The `docx`, `pptx` and `pdf`
skills that Anthropic distributes with Claude were read for ideas: removing the
parts nothing refers to, and their content-type overrides, after deleting
slides (`pptx/scripts/clean.py`), and reading PDF metadata with `pypdf`. Their
`LICENSE.txt` is the Apache License, Version 2.0, without a copyright line, and
they ship no NOTICE file.

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

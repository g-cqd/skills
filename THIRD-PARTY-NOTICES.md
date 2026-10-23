# Third-Party Notices

This harness includes content derived from the following openly licensed
works. Their notices are preserved as required.

## skill-creator

Derived from Anthropic's `skill-creator` skill.
License: Apache License 2.0 — see `skills/skill-creator/LICENSE.txt`.

## Swift concurrency references

The reference files under `skills/swift/references/concurrency/` are derived
from **Swift-Concurrency-Agent-Skill** by Antoine van der Lee
(https://github.com/AvdLee/Swift-Concurrency-Agent-Skill).

MIT License — Copyright (c) 2026 Antoine van der Lee

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"Course Deep Dive" links inside those files point to the author's Swift
Concurrency Course and are kept as attribution and further reading.

## Security audit method

The audit mode, the finding gate and verdicts, the severity anchors, the safe-execution rules, the hunting method, the
attack classes, and the domain files of `skills/secure-coding/` (`SKILL.md` §1–§7, `references/audit-workflow.md`,
`references/attack-classes.md`, `references/domains/`, `references/findings-format.md`) are adapted from
**security-audit-skill** by Cloudflare (https://github.com/cloudflare/security-audit-skill). The text is rewritten and
condensed, and `scripts/validate_audit.py` is a new implementation of the checks its validators perform.

MIT License — Copyright (c) 2025-2026 Cloudflare, Inc.

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

## Skills installed from elsewhere

This repository does not contain the following skills. `install.sh` fetches or exports them and links them into the
skills directory. Each stays under its own license.

| Skill | Source | License | How it arrives |
|---|---|---|---|
| `reverse-engineer-anything` | [morluto/rea](https://github.com/morluto/rea) (REA) | MIT | git submodule `third_party/rea`, pinned to the `rea-agents` release tag; only the skill directory is checked out |
| `swiftui-specialist`, `swiftui-whats-new-27`, `building-document-based-swiftui-applications`, `app-intents-specialist`, `app-intents-whats-new-27`, `app-resizability`, `adopt-c-bounds-safety`, `audit-xcode-security-settings`, `device-interaction`, `modernize-tests` | Apple's Xcode skill pack, exported from Xcode 27.1 or later with `xcrun mcpbridge run-agent skills export` | Apple's terms for Xcode; Apple keeps its rights in the pack | exported on your machine into `~/.agent-harness/xcode-skills/` and read there by the owning skills; never stored in this repository and not modified |

The skills in this repository that route to those skills (`swiftui`, `apple-platforms`, `memory-safety`, `xcode`,
`testing`) are condensed, original text. They name the pack skills and their files and do not copy
them.

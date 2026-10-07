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

## Xcode 27 skill pack

Apple-authored agent skills distributed with Xcode and exportable for use by external agents.
This repository mirrors the pack exported from **Xcode 27.1 (build 27A9275)** with
`xcrun agent skills export`. The pack has ten skills; the references and the script are kept
verbatim for parity with upstream (listed edits aside), and each skill's own `SKILL.md` is
condensed into the `SKILL.md` of the skill that owns the concern, not copied.

| Apple skill | Lands in this repository |
|---|---|
| `swiftui-specialist` | `skills/swiftui/references/idiom/` |
| `swiftui-whats-new-27` | `skills/swiftui/references/sdk-27/` |
| `building-document-based-swiftui-applications` | `skills/swiftui/references/document-apps/` |
| `app-intents-specialist` | `skills/apple-platforms/references/app-intents/` |
| `app-intents-whats-new-27` | `skills/apple-platforms/references/app-intents-27/` |
| `app-resizability` | `skills/apple-platforms/references/uikit/` |
| `adopt-c-bounds-safety` | `skills/memory-safety/references/c-bounds-safety/` |
| `audit-xcode-security-settings` | `skills/xcode/references/` and `skills/xcode/scripts/` |
| `device-interaction` | section 6 of `skills/xcode/SKILL.md` (no reference files) |
| `modernize-tests` | section 9 of `skills/testing/SKILL.md` (no reference files) |

Edits to the mirrored files, all deliberate: the two places in the bounds-safety adoption guide
that name Claude say "the agent"; the UIKit `uiscreen-task.md` links to the principles in
`skills/apple-platforms/SKILL.md` section 3.1, whose numbering the task files cite; and the audit
`adoption-strategy.md` points to the `memory-safety` skill where upstream names
`adopt-c-bounds-safety`. The 27.0 and 27.1 exports differ only in frontmatter key order.

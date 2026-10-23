# Security audit workflow detail

Detail for `SKILL.md` §7.1 and §7.2. Read the section a step names when you reach it.

## Contents

- [Use the Xcode tools, not shell equivalents](#use-the-xcode-tools-not-shell-equivalents)
- [Phase 1: analyze](#phase-1-analyze)
- [Phase 2: how to write a setting](#phase-2-how-to-write-a-setting)
- [Phase 3: inquire](#phase-3-inquire)
- [Phase 4: validate](#phase-4-validate)
- [Phase 5: report](#phase-5-report)
- [Phase 6: optional follow-ups](#phase-6-optional-follow-ups)

---

## Use the Xcode tools, not shell equivalents

| Symptom | Cause | Response |
|---|---|---|
| `XcodeGlob "**/*.xcodeproj"` returns 0 matches | The `.xcodeproj` is not a project-indexed file | Use the project name from context — **do not** fall back to `find`/`ls` |
| `XcodeRead` fails for `.entitlements`, `.xcsettings`, `.xcconfig` | Some on-disk artifacts are not navigable by project path | Prepend the project root from context and use `Read`/`Edit` |

Fall back to Bash only for what the Xcode tools cannot do — `plutil`, git.

- Tool names may carry an MCP server prefix (`mcp__<server>__XcodeGlob`). Look the prefix up once
  in the tool registry and reuse it; do not guess it.
- `XcodeListTargets` enumerates targets with `PRODUCT_TYPE_IDENTIFIER` and role flags
  (`IS_AGGREGATE`, `IS_TEST_TARGET`, `IS_APP_EXTENSION`); do not parse `project.pbxproj`. Skip
  aggregate targets, which have no product type.
- A target's entitlements path is the evaluated `CODE_SIGN_ENTITLEMENTS` from
  `GetTargetBuildSettings`. Do not rebuild it from the navigator or glob `**/*.entitlements`:
  orphaned files exist, and several targets can share one file.
- Write entitlements with `AddEntitlement` (`targetName`, `entitlementKey`,
  `entitlementValueType`, value), not `XcodeUpdate`, `Edit` or `plutil`. It adds and updates only;
  it cannot remove a key.

---

## Phase 1: analyze

**Phase 1 — analyze.** Silent. Locate the project; find any existing decision document
(`**/xcode-security-settings.md`) and read prior decisions with their rationale. Check for source
control (`.git`, `.hg`, `.svn`); with none, recommend setting it up first, since this audit edits
build settings and entitlements and rollback is otherwise manual. Detect languages by extension
(`.c`, `.cpp/.cxx/.cc`, `.m`, `.mm`, `.swift`); Objective-C++ implies C++, and a
`sourcecode.cpp.*` file type in `project.pbxproj` overrides the extension. Enumerate targets with
product type, platform (`SDKROOT` / `SUPPORTED_PLATFORMS`), and the resolved
`CODE_SIGN_ENTITLEMENTS` path. Join each target's evaluated build settings (filter large dumps with
`audit-xcode-security-settings/scripts/filter_build_settings.py`) with the explicit occurrences in `*.xcconfig` and
`project.pbxproj`; `audit-xcode-security-settings/references/reading-build-settings.md` defines the columns and the predicates
*already hardened*, *at default OFF* and *deliberately disabled*.

---

## Phase 2: how to write a setting

How to write a setting:

- **Project uses `.xcconfig`** → edit the xcconfig.
- **`.pbxproj` only** → `UpdateTargetBuildSetting` for target-level settings. No tool writes a
  project-level setting: ask the user to set it in Build Settings (All / Combined, the project
  column), then verify by grepping `project.pbxproj` and ask again until the grep matches.
- **Mixed** → xcconfig where the target has one, tools otherwise. Match the method the project
  already uses rather than introducing a new one; two sources of truth for one setting is how
  settings drift.

Change the one setting, not the file: a targeted edit to a build setting or an `.xcconfig` line
leaves the rest of the project or config file byte-identical and the diff reviewable.

---

## Phase 3: inquire

**Phase 3 — inquire.** Find tracked settings (`audit-xcode-security-settings/references/security-settings-reference.md`) that are
*deliberately disabled*: not at a hardened value and set explicitly, as opposed to Xcode's default
OFF, which is never a question. Restrict to settings whose scope covers a detected language.
Flag an unconditional `ENABLE_POINTER_AUTHENTICATION = NO`, and
`ENABLE_HARDWARE_CHECKED_POINTER_ARITHMETIC_SLICE = NO` on a target that could otherwise take it.
If the decision document records a rationale, note it and move on; otherwise ask the user, and
record whatever they answer.

---

## Phase 4: validate

**Phase 4 — validate.** Re-read each modified target's settings and confirm the expected value.
A missing or unexpected value may mean the current Xcode does not support it — flag it.

---

## Phase 5: report

**Phase 5 — report** and update the decision document: enabled, per-target Enhanced Security
status, already-active, and the outcome of each inquiry. Tell the user to test on real hardware
that supports every enabled protection and to fix the crashes and simulated crash reports before
shipping, since hardening turns latent bugs into crashes.

---

## Phase 6: optional follow-ups

**Phase 6 — optional follow-ups**, offered one at a time as separate yes/no questions: additional
diagnostic settings (higher false-positive rate), and bounds-safety programming models —
`ENABLE_C_BOUNDS_SAFETY` for C (the `memory-safety` skill carries the adoption workflow),
`ENABLE_CPLUSPLUS_BOUNDS_SAFE_BUFFERS` for C++ (clang's SafeBuffers documentation). This step
emits guidance only and applies no change.

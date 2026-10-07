---
name: xcode
description: >-
  Apple platforms: build, test, run, profile, and verify apps on devices or simulators
  using xcodebuild, simctl, devicectl, and Xcode MCP. Use for screenshots, UI interaction,
  build failures, Mach error -308, security build settings, entitlements, and Info.plist
  audits. For writing tests, use `testing`; for Keychain and TLS, use `secure-coding`; for
  C bounds annotations, use `memory-safety`. Excludes signing and provisioning.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Xcode

This skill owns **the toolchain**: turning a source tree into a running, verified, hardened
binary. It does not own what the code says (`swift`, `swiftui`), what the tests assert
(`testing`), or the app's runtime security posture (`secure-coding`).

Version facts describe Xcode 26.3–27. Verify against `xcodebuild -version` and the release notes
when behavior disagrees.

## Contract

```
§VALIDATE ¬report-done ∀compiles-only ⇒ ! climb §1 ladder
§DISCOVER ? schemes ∧ destinations BEFORE build ⇒ ¬guess-names
§ONE-GATE fix first-error → rebuild → repeat ⇒ ¬batch-speculative-fixes
§DOCS     apple-docs MCP → CLI → SDK-interfaces · ¬web-fetch
§BAN      modify signing|provisioning|CI-lanes ¬asked ·
          poll ∈ sleep-loop · guess-tap-coords ∀screenshot ·
          enable-PAC ∀binary-deps ¬arm64e
```

---

## 1. The self-validation loop

**Compilation is not completion.** Climb this ladder, stopping at the first failure:

1. **Build** the affected scheme.
2. **Test** — run the relevant test plan or suite.
3. **Preview / playground** — for UI changes, confirm previews still render.
4. **Run** — install and launch on simulator or device, exercise the changed flow (§6).
5. **Localization and accessibility** — if strings or UI changed, confirm String Catalogs updated
   and accessibility labels intact.

Report which rung you reached. "It builds" is a statement about rung 1 only.

---

## 2. CLI toolbox

### Discover before assuming

```bash
xcodebuild -list                          # schemes, targets, configurations
xcodebuild -showdestinations -scheme <S>  # valid destinations
xcrun simctl list devices available       # available simulators
xcrun devicectl list devices              # physical + Device Hub devices
```

Use the names these commands return. A guessed scheme or destination fails late, with an error
that looks like a build problem.

### Build and test

```bash
xcodebuild -scheme <S> -destination 'platform=iOS Simulator,name=<device>' build
xcodebuild -scheme <S> -destination '<dest>' test
xcodebuild -scheme <S> -destination '<dest>' test -only-testing:<Target>/<Suite>
```

`test` builds first. To run tests more than once, build once with `build-for-testing` and run each
time with `test-without-building -only-testing:…`. SwiftPM's loop is in `swift` §6.

While you develop, build one scheme, one destination and the Debug configuration. Do not add
other destinations, configurations or schemes to check the change: that is a matrix, and a CI
job's work. Build once per completed step, not per edit, and fix every error from one log before
building again (`engineering-practices` §5).

Use `-quiet` for signal. On failure, re-run without it and read the **first** error, not the last —
later errors are usually cascades.

### Run and profile

```bash
xcrun simctl boot "<device>"
xcrun simctl install booted <App.app>
xcrun simctl launch booted <bundle-id>
xcrun devicectl device install app --device <id> <App.app>   # physical device
xcrun xctrace record --template 'Time Profiler' --launch <App.app>
```

### `xcodebuild` vs SwiftPM — default to `xcodebuild`

**Whenever an Apple platform is the target, use `xcodebuild`.** It is the only CLI that builds for
simulator and device destinations, honors schemes, test plans, signing, and asset catalogs, and
emits `.xcresult` bundles.

**`swift test` runs on the host Mac only.** It silently skips iOS/watchOS/tvOS/visionOS behavior,
availability paths, and UI frameworks — a green `swift test` says nothing about the shipping
platform. Test a package where it ships:

```bash
xcodebuild -scheme <Package> -destination 'platform=iOS Simulator,name=<device>' test
```

Reserve `swift build` / `swift test` for pure host-platform packages with no platform-conditional
code, where they give a faster inner loop and Linux parity.

---

## 3. Agent integration

- **MCP bridge** — Xcode exposes its tools over MCP via `xcrun mcpbridge`: build and test,
  diagnostics, Swift REPL, preview rendering, doc search. Xcode 27 additionally announced debugger
  state, scheme and destination switching, and build-setting / entitlement / `Info.plist`
  inspection; verify against your release notes. Requires **Settings → Intelligence → Allow
  external agents to use Xcode tools**.
  Running `xcrun mcpbridge` with no arguments **starts the stdio MCP server** and fails if Xcode
  is not running — wire it into an MCP client config, do not invoke it interactively.
- **Project instructions** — Xcode reads `AGENTS.md` at the repo root automatically; some coding
  agents read `CLAUDE.md`. Keep one canonical `AGENTS.md` and alias `CLAUDE.md` to it (a symlink, as
  the install script does, or an import).
- **Skills** — Xcode 27 reads Agent Skills in this `SKILL.md` format from
  `~/Library/Developer/Xcode/CodingAssistant/<agent-config>/skills/`, and ships Apple-authored
  skills for SwiftUI, document apps, App Intents, UIKit resizability, security-settings auditing,
  C bounds safety, test modernization, and device interaction — mirrored in this harness by
  `swiftui`, `apple-platforms`, `memory-safety`, `testing`, and §6 and §7 of this skill.
- **Plans** — Xcode's plan mode produces editable Markdown. When working alongside it, write plans
  as Markdown artifacts the user can edit.

---

## 4. Concurrent sessions and simulator exhaustion

Multiple agent sessions on one Mac race to boot simulator clones — roughly 1 GB RAM each plus
CoreSim XPC processes. Exhaustion has a **distinctive signature**: clones die with
`Mach error -308 (server died)`, and tests fail as **phantom 0.000s aborts that look like real
bugs but are infrastructure exhaustion**. The failures are not in the code.

- If the machine may run concurrent sessions, serialize `xcodebuild build/test` behind a
  **machine-wide lock** — a wrapper taking an exclusive `flock` on a fixed `/tmp` lockfile. The
  contended resource is shared CoreSim infrastructure, so the lock must be OS-global, never
  per-repository.
- Under pressure, add `-parallel-testing-enabled NO`, optionally
  `-maximum-parallel-testing-workers 1`.
- **On any 0.000s failure, check for the -308 signature and other running sessions before
  debugging the tests.**

---

## 5. Guardrails

- Discover names before building (§2).
- One failing gate at a time: fix the first error, rebuild, repeat. Do not batch speculative fixes.
- Do not touch signing, provisioning, or CI lanes unless the task requires it.
- Long builds run in the background while you do useful work; wait on the task's completion
  rather than polling in a sleep loop.

---

## 6. On-device and simulator verification

Use this to answer "does it actually work", after any UI-affecting change, or to debug touch and
interaction problems. Do **not** use it for unit-test-only requests, build-only requests, review
without device testing, or changes that cannot affect UI.

This runs well as a subagent — device sessions are resource-heavy and the transcript is verbose.

### Session lifecycle

```
DeviceInteractionStartWorkspaceSession   bound to the workspace; start early, runs in the background
  → DeviceInteractionInstallAndRun          after each code change; includes building
    → DeviceEventSynthesize                 interact + observe, repeatable
  → DeviceInteractionEndSession             when done — open sessions are expensive
```

`DeviceInteractionInstallAndRun` needs the workspace-bound session. Use the unbound
`DeviceInteractionStartSession` only to interact with an app that is already installed.

Pass a device identifier to select a device, or omit it for the current destination. Pass an
empty string to get the list of available targets.

`DeviceInteractionInstallAndRun` takes optional `commandLineArguments` and `environmentVariables`.
Use `$(inherited)` to preserve the scheme's existing values —
`["$(inherited)", "--reset-state"]`, or `{"$(inherited)": "", "DEBUG_MODE": "1"}`.
**Prefer these over editing the scheme**: they apply to one run and leave the user's configuration
untouched.

### Read the hierarchy, never the screenshot

Hierarchy dumps carry a calculated `hitPoint` per element:

```
UIView {{100, 200}, {60, 30}}, hitPoint: {130.0, 215.0}
  UIButton "Login" {{110, 205}, {30, 20}}, hitPoint: {125.0, 215.0}
```

`{100, 200}` is the origin, `{60, 30}` the size, `hitPoint:` the best point to tap.
**Tap the hitPoint from the hierarchy.** Fall back to a position estimated from the screenshot
only after a hitPoint tap, confirmed by a recapture, had no effect. An element marked
`isRemoteLeafPlaceholder` reports no children, so it also needs the screenshot fallback. If the
thumbnail is too coarse to judge a visual issue, open the full-size screenshot.

When windows from more than one app overlap, each element line carries
`activationBundleId: <id>`. Interacting with such an element needs `activationBundleId` passed to
`DeviceEventSynthesize` first (it may be passed with no command). Activation is expensive, so pass
it only for those elements.

Capture before interacting and again after, every time. For compound controls, inspect nested
elements — a `Switch` or `Slider` child is usually the real control.

### Interaction syntax

| Command | Meaning |
|---|---|
| `t <x> <y> [duration]` | Tap, optional hold |
| `d <x> <y>` | Double tap |
| `t <x1> <y1> f <x2> <y2> [duration]` | Swipe |
| `b h/p/u/d [duration]` | Hardware button: Home, Power, VolUp, VolDown |
| `drag <x1> <y1> <x2> <y2> [hold] [move]` | Press-and-hold, then move slowly: list reordering, drag-and-drop |
| `mt [x y, ...] dur [x y, ...] dur ...` | Multi-touch keyframes (each `[...]` lists the touches, the number after it is the travel time to the next keyframe, the last one the hold before lifting). `"mt [100 300, 300 300] 0.5 [175 300, 225 300] 0.5"` is a two-finger pinch |
| `sender keyboard kbd <text>` | Type text — **must be last in the chain**; everything after `kbd ` is verbatim, multiple spaces preserved |
| `w <duration>` | Wait |
| `orientation <value>` | iOS only: `faceDown`, `faceUp`, `landscapeLeft`, `landscapeRight`, `portrait`, `portraitUpsideDown` |
| `b c/s/a [duration]`, `c <turns>` | watchOS only: Digital Crown press, side button, Action button (some devices); rotate the crown (1.0 is one revolution, the sign sets direction) |
| `r up/down/left/right/select/menu/playpause/home` | tvOS only: Siri Remote |

```
"t 200 600 f 200 200 0.3"          swipe up (scroll down the content)
"b h b h"                          home twice → app switcher
"b h w 0 b h"                      wake and unlock (no-passcode devices)
"sender keyboard kbd submit\u{000A}"   type, then Return
```

Special characters use `\u{XXXX}`: `\u{000A}` return, `\u{0009}` tab.

### tvOS

tvOS is focus-based: coordinate taps do not apply, and only the focused element can be activated.
Read the hierarchy for the focusable elements and the one marked `Focused`, move with `r up/down/left/right`,
activate with `r select`, go back with `r menu`. Chain the presses in one command and capture
once: `r right r right r right`, then capture to confirm where focus landed.

### Judging what you see

| Category | Action |
|---|---|
| **Functional bug** — no response to tap, wrong navigation, crash, missing or empty data | **Report** |
| **Visual bug** — overlapping or truncated text, off-screen elements, wrong colors, broken alignment | **Report** |
| **Unexpected exit** — crash or termination; track the pid and capture stdout | **Report** |
| **Transient state** — spinners, animations, keyboard transitions | Do not report; recapture after it settles |
| **Expected behavior** — empty-state placeholders, disabled buttons on incomplete forms, permission dialogs | Do not report |

### Timing and retries

- **After launch**, the app may take seconds. Capture and confirm the hierarchy holds meaningful
  UI before interacting; a launch screen or empty tree means capture again.
- **After an interaction that did nothing**, recapture and retry **once** — the element may have
  moved mid-animation. If it fails again, report it rather than looping.
- **Wait for a loading element to settle before interacting.** A tap on a spinner lands on
  whatever replaces it.
- Runtime logs help; if a timing bug is suspected, suggest to the main agent that temporary `print`
  statements would isolate it.

When reporting, state only what the run, the hierarchy, the screenshot, or the log showed, and
say what was not exercised. "Works on device" is a claim about the flows you actually drove.

---

## 7. Security build settings audit

Progressively enable security build settings and entitlements, from broadly applicable warnings
through Enhanced Security hardening.

**Out of scope here**: TLS and ATS, code signing, privacy APIs. Those are `secure-coding`.

### 7.1 Use the Xcode tools, not shell equivalents

When `XcodeGlob`, `XcodeGrep`, `XcodeRead`, and `XcodeLS` are available, use them —
`find`, `grep`, `cat`, and `ls` trigger extra permission prompts and bypass project scoping. The
project root, name, and active scheme are already in system-prompt context: do not `ls` to
"verify" the layout.

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

### 7.2 Workflow

Print the phase list to the user as a bullet list, and mirror it into `TaskCreate`. Mark each
phase `▶` on entry and `✓` on completion with a terse outcome.

**Phase 1 — analyze.** Silent. Locate the project; find any existing decision document
(`**/xcode-security-settings.md`) and read prior decisions with their rationale. Check for source
control (`.git`, `.hg`, `.svn`); with none, recommend setting it up first, since this audit edits
build settings and entitlements and rollback is otherwise manual. Detect languages by extension
(`.c`, `.cpp/.cxx/.cc`, `.m`, `.mm`, `.swift`); Objective-C++ implies C++, and a
`sourcecode.cpp.*` file type in `project.pbxproj` overrides the extension. Enumerate targets with
product type, platform (`SDKROOT` / `SUPPORTED_PLATFORMS`), and the resolved
`CODE_SIGN_ENTITLEMENTS` path. Join each target's evaluated build settings (filter large dumps with
`scripts/filter_build_settings.py`) with the explicit occurrences in `*.xcconfig` and
`project.pbxproj`; `references/reading-build-settings.md` defines the columns and the predicates
*already hardened*, *at default OFF* and *deliberately disabled*.

**Phase 2 — apply**, most applicable first. Check what is already set; if everything is enabled,
say so and stop.

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

Prefer project level. `ENABLE_ENHANCED_SECURITY` is set at project level, since it cascades to
every target (§7.3).

**Phase 3 — inquire.** Find tracked settings (`references/security-settings-reference.md`) that are
*deliberately disabled*: not at a hardened value and set explicitly, as opposed to Xcode's default
OFF, which is never a question. Restrict to settings whose scope covers a detected language.
Flag an unconditional `ENABLE_POINTER_AUTHENTICATION = NO`, and
`ENABLE_HARDWARE_CHECKED_POINTER_ARITHMETIC_SLICE = NO` on a target that could otherwise take it.
If the decision document records a rationale, note it and move on; otherwise ask the user, and
record whatever they answer.

**Phase 4 — validate.** Re-read each modified target's settings and confirm the expected value.
A missing or unexpected value may mean the current Xcode does not support it — flag it.

**Phase 5 — report** and update the decision document: enabled, per-target Enhanced Security
status, already-active, and the outcome of each inquiry. Tell the user to test on real hardware
that supports every enabled protection and to fix the crashes and simulated crash reports before
shipping, since hardening turns latent bugs into crashes.

**Phase 6 — optional follow-ups**, offered one at a time as separate yes/no questions: additional
diagnostic settings (higher false-positive rate), and bounds-safety programming models —
`ENABLE_C_BOUNDS_SAFETY` for C (the `memory-safety` skill carries the adoption workflow),
`ENABLE_CPLUSPLUS_BOUNDS_SAFE_BUFFERS` for C++ (clang's SafeBuffers documentation). This step
emits guidance only and applies no change.

### 7.3 Enhanced Security

Audit `ENABLE_ENHANCED_SECURITY` and `ENABLE_POINTER_AUTHENTICATION` per target, plus every
`com.apple.security.hardened-process*` entitlement key. Bucket each target: **up-to-date**,
**partial** (enabled but missing default-ON sub-options, or carrying deprecated keys or version
`"1"`), **off**, or **no entitlements file**.

Change set per partial/off target:

- **Add** — `com.apple.security.hardened-process`,
  `...enhanced-security-version-string = "2"`, and default-ON sub-options `hardened-heap`,
  `dyld-ro`, `platform-restrictions-string = "2"`.
- **Remove** — deprecated `...platform-restrictions`, `...enhanced-security-version`.
- **Update** — version string `"1"` → `"2"`.

Supported product types: application (including on-demand-install), XPC service, system
extension, tool; a driver extension takes the build settings only. Skip the rest.

Two traps:

> **Binary dependencies.** Only pointer authentication cascades to `arm64e`; keep Enhanced
> Security on. On each target that links a binary dependency shipping no `arm64e` slice (a binary
> Swift package, xcframework or prebuilt framework), set a target-level
> `ENABLE_POINTER_AUTHENTICATION = NO` and `ENABLE_HARDWARE_CHECKED_POINTER_ARITHMETIC_SLICE = NO`
> (`arm64e.x1` is a pointer-authentication slice), unless the target already has an explicit
> value. List the dependencies so the user can ask the vendor for `arm64e`.

> **No simulator override.** A project-level `ENABLE_ENHANCED_SECURITY = YES` cascades
> `ENABLE_POINTER_AUTHENTICATION = YES` to every target, and the build system drops `arm64e` from
> a simulator SDK's architectures, which define none. Do not pre-write `NO` for the simulator or
> for a platform; every device platform defines `arm64e`.

**Libraries and frameworks** (`framework`, `framework.static`, `library.static`, `library.dynamic`)
take no entitlements, because those are granted per process from the executable. They still get
the cascaded build settings. Keep pointer authentication on: it appends `arm64e` to
`ARCHS_STANDARD`, so the target ships a universal `arm64`/`arm64e` binary, and only one slice is
loaded at run time, so the larger file costs no RAM or speed. Warn when a library's Release
configuration sets `ONLY_ACTIVE_ARCH = YES`, which forces every consumer onto one slice; confirm
the slices with `lipo -archs`. See `references/universal-binaries-for-libraries.md`.

Do not auto-enable default-OFF sub-options (the MTE family) — report their state and offer them.

Confirm once via `AskUserQuestion` — "Apply all", "Apply to a subset", "Skip" — after summarizing
the protection gained and the code changes it may force. If every target is already up to date,
say so in one line and proceed without asking.

**Hardware memory tagging** (`com.apple.security.hardened-process.checked-allocations`, with
`soft-mode` for a non-fatal rollout; soft mode alone does nothing) applies to `macosx`,
`iphoneos`/`iphonesimulator`, `watchos`, and `xros`/`xrsimulator` targets. Hardware backing is an
A19 chip or later (iPhone, iPad), M5 or later (Mac, Vision Pro), or S11 or later (Apple Watch).
Offer it only if Enhanced Security was applied to a matching target.

**Checked pointer arithmetic** makes capable hardware poison a pointer whose arithmetic overflows
into the tag bits, which closes the way around memory tagging. It needs four things on an app
target: `ENABLE_HARDWARE_CHECKED_POINTER_ARITHMETIC_SLICE = YES` (adds the `arm64e.x1` slice;
defaults to `NO`, never cascades, set per target), `com.apple.security.hardened-process`,
`...checked-allocations` (run time enforcement requires memory tagging), and
`...checked-allocations.enforce-checked-pointer-arithmetic-overflow`. Keep
`ENABLE_POINTER_AUTHENTICATION = YES` too: with it off, the slice ships without an `arm64e`
fallback for devices that lack the hardware. Enforcement needs iOS on A20 Pro or later, or watchOS on S11 or later. A
library or framework sets the build setting only, and the consuming app's entitlements enforce it.

- Offer it only after memory tagging is on, or is being applied in the same run, and apply it
  last, since it reads the settings and entitlements the earlier steps write. Skip a target whose
  pointer authentication or Enhanced Security is explicitly off, or that opted out of the slice.
- **There is no soft mode**, and memory tagging's does not cover these faults: a latent
  pointer-arithmetic bug (a difference between pointers into two allocations, `uintptr_t`
  subtraction, an offset from a NULL base) terminates the app. Say so before enabling it.
- Verify with `lipo -archs`: `arm64 arm64e arm64e.x1`. Details in
  `references/checked-pointer-arithmetic.md`.

DriverKit targets take build settings but **no** entitlement changes.

### 7.4 Clang safety warnings

Apply without asking when C, C++, Objective-C, or Objective-C++ is present. Skip entirely for pure
Swift.

- `GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR`
- `GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE`
- `CLANG_WARN_IMPLICIT_FALLTHROUGH = YES`
- `GCC_WARN_64_TO_32_BIT_CONVERSION = YES`
- `GCC_TREAT_IMPLICIT_FUNCTION_DECLARATIONS_AS_ERRORS = YES` — C/ObjC/ObjC++ only
- `CLANG_ANALYZER_SECURITY_FLOATLOOPCOUNTER = YES` (runs in Build and analyze only)
- `CLANG_ANALYZER_SECURITY_INSECUREAPI_RAND = YES` (Build and analyze only)
- `CLANG_ANALYZER_SECURITY_INSECUREAPI_STRCPY = YES` (Build and analyze only)
- `CLANG_TIDY_BUGPRONE_REDUNDANT_BRANCH_CONDITION = YES` (Build and analyze only; installs nothing)

### 7.5 Entitlement and Info.plist review surface

A pentester extracts the app's **effective entitlements** early, because they map the attack
surface. Auditing the same surface is a defensive win. Read the effective set from the signed
binary, not just a stray `.entitlements` file — they can differ:

```bash
codesign -d --entitlements :- "Payload/Target.app"
security cms -D -i "Payload/Target.app/embedded.mobileprovision"
```

Flag, and confirm each is intended:

- **`get-task-allow = true`** in a release build — the app is debuggable, so another process can
  attach and read its memory. Must be false in production.
- **Associated Domains** (`applinks:`) — each domain is a Universal Link entry point; cross-check
  against the AASA audit in `secure-coding` §8.4.
- **App Groups** and **keychain access groups** — every group is a shared container or shared
  keychain reachable by other targets and extensions. A wider group than needed widens the blast
  radius (`secure-coding` §8.1).
- **Unusual capabilities** and extension points beyond what the feature set justifies.

In `Info.plist`, review `CFBundleURLTypes` (registered custom schemes), `LSApplicationQueriesSchemes`,
`NSAppTransportSecurity`, `WKAppBoundDomains`, and `.appex` declarations — each is a surface the
`secure-coding` §8 controls govern.

### 7.6 Talking to the user

Keep replies lean and questions minimal. Only two questions are scheduled — the Enhanced Security
confirmation and the memory-tagging offer. Everything else is situational. Describe a protection
by **what it protects against**, not by how it is switched on. Emit build settings as a bullet
list, one setting per line, so each is scannable and can be copied on its own. Skill-internal
words such as "catalog" or "audit table" stay out of user-facing text: say "the known security
build settings" and "the list of targets". Use complete sentences, and never cite a phase number.

---

## 8. SDK 27 migration gates

Check before upgrading.

| Gate | Consequence | Where |
|---|---|---|
| **UIScene lifecycle is mandatory** under the iOS 27 SDK — an app with no scene manifest will not launch (TN3187) | **Blocker** | `apple-platforms` |
| Liquid Glass opt-out removed in Xcode 27 | Visual regression risk | `apple-platforms` |
| `@State` becomes a macro, back-deployed | Compile errors whose obvious fix is wrong | `swiftui` |
| `UIScreen.main`, `UIWindow(frame:)`, legacy app-delegate callbacks deprecated | Warnings, future removal | `apple-platforms` |
| Swift Testing gains issue severity, `Test.cancel`, flaky-test repetition | Opportunity, not a blocker | `testing` |
| Enhanced Security entitlement, `-fbounds-safety` | Hardening opportunity | §7, `memory-safety` |

---

## Boundaries

| Need | Skill |
|---|---|
| TLS, ATS, certificate pinning, Keychain, privacy APIs | `secure-coding` |
| The C bounds annotations themselves | `memory-safety` |
| Writing or migrating the tests | `testing` |
| Swift language and concurrency | `swift` |
| SwiftUI views and SDK 27 view APIs | `swiftui` |
| UIKit scene lifecycle, Liquid Glass, platform frameworks | `apple-platforms` |
| Authoritative API and HIG lookup | `apple-docs` |
| Interpreting a profile once captured | `performance-engineering` |
| Running a long build or test run, and waiting on it | `work run` (`planner`'s `scripts/work.py`), `engineering-practices` §6 |

## References

`references/security-settings-reference.md` (full settings list with scope column),
`references/enhanced-security.md` (key list, defaults, deprecated keys, version migration,
supported product types), `references/pointer-authentication.md`, `references/typed-allocators.md`,
`references/stack-zero-init.md`, `references/readonly-platform-memory.md`,
`references/runtime-restrictions.md`, `references/security-compiler-warnings.md`,
`references/cpp-hardening.md`, `references/hardware-memory-tagging.md`,
`references/additional-settings.md`, `references/adoption-strategy.md`,
`references/decision-document.md`, `references/reading-build-settings.md` (output schema, the
audit-table columns and predicates, and the filter recipe for large results — do not read a saved
settings dump linearly), `references/checked-pointer-arithmetic.md`,
`references/universal-binaries-for-libraries.md`. These files come from Apple's audit workflow and
cite its phase numbers ("Phase 3 Step 4"); the matching steps here are the Phase 1 analysis and the
Phase 2 apply in §7.2.

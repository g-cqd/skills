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
  skills for SwiftUI adoption, UIKit modernization, and security-settings auditing — mirrored in
  this harness by `swiftui`, `apple-platforms`, and §7 of this skill.
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
DeviceInteractionStartSession     start early, runs in the background
  → DeviceInteractionInstallAndRun   after each code change; includes building
    → DeviceEventSynthesize          interact + observe, repeatable
  → DeviceInteractionEndSession      when done — open sessions are expensive
```

Pass a device identifier to select a device, or omit it for the current destination. Pass any
non-matching value to get the list of available targets.

`DeviceInteractionInstallAndRun` takes optional `commandLineArguments` and `environmentVariables`.
Use `$(inherited)` to preserve the scheme's existing values —
`["$(inherited)", "--reset-state"]`, or `{"$(inherited)": "", "DEBUG_MODE": "1"}`.
**Prefer these over editing the scheme**: they apply to one run and leave the user's configuration
untouched.

### Read the hierarchy, never the screenshot

Hierarchy dumps carry computed centers:

```
UIView {{100, 200}, {50, 30}}, center: {125.0, 215.0}
  UIButton "Login" {{110, 205}, {30, 20}}, center: {125.0, 215.0}
```

`{100, 200}` is the origin, `{50, 30}` the size, `center:` the tap point.
**Tap the center coordinate from the hierarchy.** A position estimated from a screenshot is off by
the scale factor and misses the control. If the thumbnail is too coarse to judge a visual issue,
open the full-size screenshot.

Capture before interacting and again after, every time. For compound controls, inspect nested
elements — a `Switch` or `Slider` child is usually the real control.

### Interaction syntax

| Command | Meaning |
|---|---|
| `t <x> <y> [duration]` | Tap, optional hold |
| `d <x> <y>` | Double tap |
| `t <x1> <y1> f <x2> <y2> [duration]` | Swipe |
| `b h/p/u/d [duration]` | Hardware button: Home, Power, VolUp, VolDown |
| `sender keyboard kbd <text>` | Type text — **must be last in the chain**; everything after `kbd ` is verbatim, multiple spaces preserved |
| `w <duration>` | Wait |
| `orientation <value>` | `faceDown`, `faceUp`, `landscapeLeft`, `landscapeRight`, `portrait`, `portraitUpsideDown` |

```
"t 200 600 f 200 200 0.3"          swipe up (scroll down the content)
"b h b h"                          home twice → app switcher
"b h w 0 b h"                      wake and unlock (no-passcode devices)
"sender keyboard kbd submit\u{000A}"   type, then Return
```

Special characters use `\u{XXXX}`: `\u{000A}` return, `\u{0009}` tab.

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

### 7.2 Workflow

Print the phase list to the user as a bullet list, and mirror it into `TaskCreate`. Mark each
phase `▶` on entry and `✓` on completion with a terse outcome.

**Phase 1 — analyze.** Silent. Locate the project; find any existing decision document
(`**/xcode-security-settings.md`) and read prior decisions with their rationale. Detect languages
by extension (`.c`, `.cpp/.cxx/.cc`, `.m`, `.mm`, `.swift`). Enumerate targets with product type,
platform (`SDKROOT` / `SUPPORTED_PLATFORMS`), and the resolved `CODE_SIGN_ENTITLEMENTS` path.

**Phase 2 — apply**, most applicable first. Check what is already set; if everything is enabled,
say so and stop.

How to write a setting:

- **Project uses `.xcconfig`** → edit the xcconfig.
- **`.pbxproj` only** → `UpdateTargetBuildSetting` / `UpdateProjectBuildSetting`.
- **Mixed** → xcconfig where the target has one, tools otherwise. Match the method the project
  already uses rather than introducing a new one; two sources of truth for one setting is how
  settings drift.

Change the one setting, not the file: a targeted edit to a build setting or an `.xcconfig` line
leaves the rest of the project or config file byte-identical and the diff reviewable.

Prefer project level. `ENABLE_ENHANCED_SECURITY` is set at project level, since it cascades to
every target (§7.3).

**Phase 3 — inquire.** Grep for catalog settings explicitly set to `NO`. Exclude
`ENABLE_POINTER_AUTHENTICATION = NO` on non-arm64e platforms (this skill sets that itself), but
**do** flag it on arm64e-capable targets. If the decision document records a rationale, note it
and move on; otherwise ask the user, and record whatever they answer.

**Phase 4 — validate.** Re-read each modified target's settings and confirm the expected value.
A missing or unexpected value may mean the current Xcode does not support it — flag it.

**Phase 5 — report** and update the decision document: enabled, per-target Enhanced Security
status, already-active, and the outcome of each inquiry.

**Phase 6 — optional follow-ups**, offered one at a time as separate yes/no questions: additional
diagnostic settings (higher false-positive rate), and bounds-safety programming models —
`ENABLE_C_BOUNDS_SAFETY` for C, `ENABLE_CPLUSPLUS_BOUNDS_SAFE_BUFFERS` for C++.

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

Two traps:

> **Do not enable pointer authentication if the project has binary dependencies** — frameworks,
> xcframeworks, or Swift packages not built from source in this project. List them and recommend
> the user request an arm64e-inclusive universal binary from the vendor.

> A project-level `ENABLE_ENHANCED_SECURITY = YES` **cascades** `ENABLE_POINTER_AUTHENTICATION =
> YES` to every target. Pre-write a target-level `ENABLE_POINTER_AUTHENTICATION = NO` on each
> target whose platform lacks arm64e, unless it already has an explicit value.

Do not auto-enable default-OFF sub-options (the MTE family) — report their state and offer them.

Confirm once via `AskUserQuestion` — "Apply all", "Apply to a subset", "Skip" — after summarizing
the protection gained and the code changes it may force. If every target is already up to date,
say so in one line and proceed without asking.

**Hardware memory tagging** (`com.apple.security.hardened-process.checked-allocations`) applies
only to `macosx`, `iphoneos`/`iphonesimulator`, and `xros`/`xrsimulator` targets — hardware
backing is M5-class Apple silicon and later. tvOS, watchOS, and DriverKit are unsupported. Offer
it only if Enhanced Security was applied to a matching target.

DriverKit targets take build settings but **no** entitlement changes.

### 7.4 Clang safety warnings

Apply without asking when C, C++, Objective-C, or Objective-C++ is present. Skip entirely for pure
Swift.

- `GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR`
- `GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE`
- `CLANG_WARN_IMPLICIT_FALLTHROUGH = YES`
- `GCC_WARN_64_TO_32_BIT_CONVERSION = YES`
- `GCC_TREAT_IMPLICIT_FUNCTION_DECLARATIONS_AS_ERRORS = YES` — C/ObjC/ObjC++ only
- `CLANG_ANALYZER_SECURITY_FLOATLOOPCOUNTER = YES`
- `CLANG_ANALYZER_SECURITY_INSECUREAPI_RAND = YES`
- `CLANG_ANALYZER_SECURITY_INSECUREAPI_STRCPY = YES`

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
list, one setting per line, so each is scannable and can be copied on its own.

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
`references/decision-document.md`, `references/reading-build-settings.md` (output schema and the
filter recipe for large results — do not read a saved settings dump linearly)

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

Boot a simulator and install and launch with `xcrun simctl`, install on a physical device with
`xcrun devicectl device install app`, and profile with `xcrun xctrace record --template`. Read
`references/run-and-profile.md` for the commands.

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

- **MCP bridge** — `xcrun mcpbridge` exposes Xcode's tools over MCP. Running it with no arguments
  **starts the stdio MCP server** and fails if Xcode is not running: wire it into an MCP client
  config, do not invoke it interactively.
- **Project instructions, skills, plans** — Xcode reads `AGENTS.md` at the repo root (alias
  `CLAUDE.md` to it), reads Agent Skills in this `SKILL.md` format, and produces editable Markdown
  plans.

Read `references/agent-integration.md` when setting up the MCP bridge, the Settings toggle it needs,
project instructions, skills directories, or plan mode.

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

`DeviceInteractionInstallAndRun` takes optional `commandLineArguments` and `environmentVariables`;
prefer them over editing the scheme (they apply to one run). Read
`references/device-interaction.md#run-arguments` for the `$(inherited)` syntax.

### Read the hierarchy, never the screenshot

Hierarchy dumps carry a calculated `hitPoint` per element (annotated example in
`references/device-interaction.md#hierarchy-dump-format`).
**Tap the hitPoint from the hierarchy.** Fall back to a position estimated from the screenshot
only after a hitPoint tap, confirmed by a recapture, had no effect. An element marked
`isRemoteLeafPlaceholder` reports no children, so it also needs the screenshot fallback. If the
thumbnail is too coarse to judge a visual issue, open the full-size screenshot.

When windows from more than one app overlap, each element line carries `activationBundleId`; pass it
to `DeviceEventSynthesize` first, only for those elements. Read
`references/device-interaction.md#overlapping-apps` for the rule.

Capture before interacting and again after, every time. For compound controls, inspect nested
elements — a `Switch` or `Slider` child is usually the real control.

### Interaction syntax

Commands are chained in one string: taps (`t`), double tap (`d`), swipes, hardware buttons (`b`),
drag, multi-touch keyframes (`mt`), text entry (`sender keyboard kbd`, which must be last in the
chain), waits (`w`), and platform-only commands for orientation (iOS), Digital Crown (watchOS) and
the Siri Remote (tvOS). tvOS is focus-based: coordinate taps do not apply.

Read `references/device-interaction.md#interaction-syntax` when composing a command chain (the full
command table and examples), and `references/device-interaction.md#tvos` before driving tvOS.

### Judging what you see

Report functional bugs, visual bugs and unexpected exits; do not report transient states or expected
behavior (empty-state placeholders, disabled buttons on incomplete forms, permission dialogs). Read
`references/device-interaction.md#judging-what-you-see` for the table.

### Timing and retries

After launch, confirm the hierarchy holds meaningful UI before interacting; after an interaction
that did nothing, recapture and retry once, then report; wait for a loading element to settle. Read
`references/device-interaction.md#timing-and-retries` for the full rules.

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

Read `references/audit-workflow.md#use-the-xcode-tools-not-shell-equivalents` when an Xcode tool
returns no match or fails on an `.entitlements`, `.xcsettings` or `.xcconfig` file, and before
resolving targets or entitlements paths or writing an entitlement (`AddEntitlement`).

### 7.2 Workflow

Print the phase list to the user as a bullet list, and mirror it into `TaskCreate`. Mark each
phase `▶` on entry and `✓` on completion with a terse outcome.

**Phase 1 — analyze.** Silent. Locate the project, read any decision document, check source control,
detect languages, enumerate targets, and join evaluated build settings with explicit occurrences.
Read `references/audit-workflow.md#phase-1-analyze` first for the full procedure.

**Phase 2 — apply**, most applicable first. Check what is already set; if everything is enabled,
say so and stop.

How to write a setting: edit the xcconfig when the project uses one; use
`UpdateTargetBuildSetting` for target-level settings in a `.pbxproj`-only project (no tool writes a
project-level setting: ask the user, then verify by grep); in a mixed project match the method
already in use. Read `references/audit-workflow.md#phase-2-how-to-write-a-setting` before writing.

Prefer project level. `ENABLE_ENHANCED_SECURITY` is set at project level, since it cascades to
every target (§7.3).

**Phase 3 — inquire.** Find tracked settings that are *deliberately disabled* (explicitly set, not at
a hardened value), restricted to detected languages; ask about each unless the decision document
records a rationale. Read `references/audit-workflow.md#phase-3-inquire` for the full rules and the
settings to flag.

**Phase 4 — validate.** Re-read each modified target's settings and confirm the expected value; flag
anything missing. Read `references/audit-workflow.md#phase-4-validate` for the exact rule.

**Phase 5 — report** and update the decision document, then tell the user to test on real hardware.
**Phase 6 — optional follow-ups** are offered one at a time as separate yes/no questions and apply
no change. Read `references/audit-workflow.md#phase-5-report` and
`references/audit-workflow.md#phase-6-optional-follow-ups` when you reach them.

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

**Libraries and frameworks** take no entitlements but still get the cascaded build settings; keep
pointer authentication on and warn on `ONLY_ACTIVE_ARCH = YES` in Release. Read
`references/hardening-checks.md#libraries-and-frameworks` when the audit includes a library or
framework target.

Do not auto-enable default-OFF sub-options (the MTE family) — report their state and offer them.

Confirm once via `AskUserQuestion` — "Apply all", "Apply to a subset", "Skip" — after summarizing
the protection gained and the code changes it may force. If every target is already up to date,
say so in one line and proceed without asking.

**Hardware memory tagging** (`...checked-allocations`) and **checked pointer arithmetic**
(`ENABLE_HARDWARE_CHECKED_POINTER_ARITHMETIC_SLICE`) are offers, not defaults: memory tagging only
if Enhanced Security was applied to a matching target, checked pointer arithmetic only after memory
tagging, and it has no soft mode. Read `references/hardening-checks.md#hardware-memory-tagging` and
`references/hardening-checks.md#checked-pointer-arithmetic` before offering either.

DriverKit targets take build settings but **no** entitlement changes.

### 7.4 Clang safety warnings

Apply without asking when C, C++, Objective-C, or Objective-C++ is present. Skip entirely for pure
Swift.

Settings to apply: the return-type, uninitialized-autos, implicit-fallthrough, 64-to-32-bit
conversion and implicit-function-declaration warnings, plus four Build-and-analyze-only analyzer and
clang-tidy checks. Read `references/hardening-checks.md#clang-safety-warnings` for the exact list and
values before applying.

### 7.5 Entitlement and Info.plist review surface

Read the effective entitlements from the signed binary (`codesign -d --entitlements :-`), not a
stray `.entitlements` file. Read `references/hardening-checks.md#entitlement-and-infoplist-review-surface`
for what to flag (`get-task-allow`, Associated Domains, App Groups, `Info.plist` keys).

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

Detail moved out of the body: `references/agent-integration.md` (§3), `run-and-profile.md` (§2),
`device-interaction.md` (§6), `audit-workflow.md` (§7.1-7.2), `hardening-checks.md` (§7.3-7.5).

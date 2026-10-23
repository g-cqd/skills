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

This skill covers the toolchain: building, running, verifying, and hardening the binary. What the
code says is `swift` and `swiftui`, what the tests assert is `testing`, and the app's runtime
security is `secure-coding`.

Version facts describe Xcode 26.3–27. When observed behaviour disagrees, check
`xcodebuild -version` and the release notes.

## Contract

```
§VALIDATE ¬report-done ∀compiles-only ⇒ ! climb §1 ladder
§DISCOVER ? schemes ∧ destinations BEFORE build ⇒ ¬guess-names
§ONE-GATE read first-error first · later-errors ∈ possible-results ·
          fix ∀error ¬result-of-earlier → rebuild once ⇒ ¬fix ∄logged-error
§DOCS     apple-docs MCP → CLI → SDK-interfaces · ¬web-fetch
§BAN      modify signing|provisioning|CI-lanes ¬asked ·
          poll ∈ sleep-loop · guess-tap-coords ∀screenshot ·
          enable-PAC ∀binary-deps ¬arm64e
```

---

## 1. The self-validation loop

**Compilation is not completion.** Climb this ladder in order. At the first failure, stop, fix,
and restart from rung 1.

1. **Build** the affected scheme.
2. **Test**: run the relevant test plan or suite. If the scheme has no tests, say so and go on.
3. **Preview / playground**: for UI changes, confirm previews still render.
4. **Run**: for changes that can affect UI or runtime behaviour, install and launch on simulator
   or device and exercise the changed flow (§6).
5. **Localization and accessibility**: if strings or UI changed, confirm String Catalogs are
   updated and accessibility labels are intact.

Skip a rung whose condition does not apply. Report the highest rung reached and each rung skipped.
"It builds" is a statement about rung 1 only.

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
other destinations, configurations or schemes to check the change; that matrix is a CI job's
work. Build once per completed step, not per edit, and fix each error that is not a result of an
earlier one before building again (`engineering-practices` §5).

Build with `-quiet`. On failure, re-run without it and read the **first** error, not the last;
later errors are usually cascades.

### Run and profile

Boot a simulator and install and launch with `xcrun simctl`, install on a physical device with
`xcrun devicectl device install app`, and profile with `xcrun xctrace record --template`. Before
you run one of these from the command line, read `references/run-and-profile.md` for the exact
commands.

### `xcodebuild` vs SwiftPM — default to `xcodebuild`

**When an Apple platform is the target, use `xcodebuild`.** It is the only CLI that builds for
simulator and device destinations, honors schemes, test plans, signing, and asset catalogs, and
emits `.xcresult` bundles.

**`swift test` runs on the host Mac only.** It skips iOS/watchOS/tvOS/visionOS behaviour,
availability paths, and UI frameworks without a warning. Test a package on the platform where it
ships:

```bash
xcodebuild -scheme <Package> -destination 'platform=iOS Simulator,name=<device>' test
```

Use `swift build` / `swift test` only for pure host-platform packages with no platform-conditional
code, where they give a faster inner loop and Linux parity.

---

## 3. Agent integration

- **MCP bridge**: `xcrun mcpbridge` exposes Xcode's tools over MCP. Run with no arguments, it
  **starts the stdio MCP server** and fails if Xcode is not running. Put it in an MCP client
  config; do not run it interactively.
- **Project instructions, skills, plans**: Xcode reads `AGENTS.md` at the repo root (alias
  `CLAUDE.md` to it), reads Agent Skills in this `SKILL.md` format, and produces editable Markdown
  plans.

Before you set up the MCP bridge (including the Settings toggle it needs), project instructions,
skills directories, or plan mode, read `references/agent-integration.md`.

---

## 4. Concurrent sessions and simulator exhaustion

Several agent sessions on one Mac race to boot simulator clones, at about 1 GB RAM each plus
CoreSim XPC processes. Exhaustion has a **distinctive signature**: clones die with
`Mach error -308 (server died)`, and tests fail as **0.000s aborts that look like real bugs**.
The failures are not in the code.

- If more than one session can run `xcodebuild` on this Mac, serialize `xcodebuild build/test`
  behind a **machine-wide lock**: a wrapper taking an exclusive `flock` on a fixed `/tmp`
  lockfile. The contended resource is shared CoreSim infrastructure, so the lock must be
  OS-global, not per repository.
- When the -308 signature or 0.000s aborts appear, or another session is running `xcodebuild`,
  add `-parallel-testing-enabled NO`, and optionally `-maximum-parallel-testing-workers 1`.
- **On each 0.000s failure, check for the -308 signature and other running sessions before
  debugging the tests.**

---

## 5. Guardrails

- Discover names before building (§2).
- Read the first error first; treat later errors as possible results of it. Fix each error that is
  not a result of an earlier one, then rebuild once. Do not add fixes you cannot tie to a logged
  error.
- Do not touch signing, provisioning, or CI lanes unless the task asks for it.
- Run a build or test run that takes minutes in the background. Wait for its completion
  notification; do not poll in a sleep loop.

---

## 6. On-device and simulator verification

Use this section to answer "does it actually work", after a UI-affecting change, or to debug touch
and interaction problems. Do **not** use it for unit-test-only requests, build-only requests,
review without device testing, or changes that cannot affect UI.

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
**Tap the hitPoint from the hierarchy.** Use a position estimated from the screenshot only in two
cases: a hitPoint tap, confirmed by a recapture, had no effect; or the element is marked
`isRemoteLeafPlaceholder` (it reports no children). If the thumbnail is too coarse to judge a
visual issue, open the full-size screenshot.

When windows from more than one app overlap, each element line carries `activationBundleId`. For
those elements only, pass it to `DeviceEventSynthesize` first. Before interacting with such an
element, read `references/device-interaction.md#overlapping-apps`.

Capture before each interaction and again after it. For compound controls, inspect nested
elements; a `Switch` or `Slider` child is usually the real control.

### Interaction syntax

Commands are chained in one string: taps (`t`), double tap (`d`), swipes, hardware buttons (`b`),
drag, multi-touch keyframes (`mt`), text entry (`sender keyboard kbd`, which must be last in the
chain), waits (`w`), and platform-only commands for orientation (iOS), Digital Crown (watchOS) and
the Siri Remote (tvOS). tvOS is focus-based: coordinate taps do not apply.

Read `references/device-interaction.md#interaction-syntax` when composing a command chain (the full
command table and examples), and `references/device-interaction.md#tvos` before driving tvOS.

### Judging what you see

Report functional bugs, visual bugs and unexpected exits. Do not report transient states or
expected behaviour (empty-state placeholders, disabled buttons on incomplete forms, permission
dialogs). Read `references/device-interaction.md#judging-what-you-see` for the table.

### Timing and retries

- After launch, confirm the hierarchy holds meaningful UI before interacting.
- After an interaction that did nothing, recapture and retry once; if it fails again, report it.
- Wait for a loading element to settle before interacting.

Read `references/device-interaction.md#timing-and-retries` for the full rules.

When reporting, state only what the run, the hierarchy, the screenshot, or the log showed, and
say what was not exercised. "Works on device" is a claim about the flows you actually drove.

---

## 7. Security build settings audit

Enable security build settings and entitlements in stages, from broadly applicable warnings to
Enhanced Security hardening.

**Out of scope here**: TLS and ATS, code signing, privacy APIs. Those are `secure-coding`.

### 7.1 Use the Xcode tools, not shell equivalents

When `XcodeGlob`, `XcodeGrep`, `XcodeRead`, and `XcodeLS` are available, use them. `find`,
`grep`, `cat`, and `ls` trigger extra permission prompts and bypass project scoping. The project
root, name, and active scheme are already in system-prompt context; do not run `ls` to check the
layout.

Read `references/audit-workflow.md#use-the-xcode-tools-not-shell-equivalents` in each of these
cases: an Xcode tool returns no match; an Xcode tool fails on an `.entitlements`, `.xcsettings` or
`.xcconfig` file; before resolving targets or entitlements paths; before writing an entitlement
(`AddEntitlement`).

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

Prefer project level. Set `ENABLE_ENHANCED_SECURITY` at project level, since it cascades to
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
pointer authentication on and warn on `ONLY_ACTIVE_ARCH = YES` in Release. When the audit includes
a library or framework target, read `references/hardening-checks.md#libraries-and-frameworks`.

Do not auto-enable default-OFF sub-options (the MTE family); report their state and offer them.

Confirm once via `AskUserQuestion` — "Apply all", "Apply to a subset", "Skip" — after summarizing
the protection gained and the code changes it may force. If every target is already up to date,
say so in one line and proceed without asking.

**Hardware memory tagging** (`...checked-allocations`) and **checked pointer arithmetic**
(`ENABLE_HARDWARE_CHECKED_POINTER_ARITHMETIC_SLICE`) are offers, not defaults: memory tagging only
if Enhanced Security was applied to a matching target, checked pointer arithmetic only after memory
tagging, and it has no soft mode. Before offering either, read
`references/hardening-checks.md#hardware-memory-tagging` and
`references/hardening-checks.md#checked-pointer-arithmetic`.

DriverKit targets take build settings but **no** entitlement changes.

### 7.4 Clang safety warnings

Apply without asking when C, C++, Objective-C, or Objective-C++ is present. Skip entirely for pure
Swift.

Settings to apply: the return-type, uninitialized-autos, implicit-fallthrough, 64-to-32-bit
conversion and implicit-function-declaration warnings, plus four Build-and-analyze-only analyzer and
clang-tidy checks. Before applying, read `references/hardening-checks.md#clang-safety-warnings` for
the exact list and values.

### 7.5 Entitlement and Info.plist review surface

Read the effective entitlements from the signed binary (`codesign -d --entitlements :-`), not a
stray `.entitlements` file. Before flagging entitlements or `Info.plist` keys, read
`references/hardening-checks.md#entitlement-and-infoplist-review-surface` for what to flag
(`get-task-allow`, Associated Domains, App Groups, `Info.plist` keys).

### 7.6 Talking to the user

- Keep replies lean and questions minimal. Only two questions are scheduled — the Enhanced
  Security confirmation and the memory-tagging offer. Everything else is situational.
- Describe a protection by **what it protects against**, not by how it is switched on.
- Emit build settings as a bullet list, one setting per line, so each can be copied on its own.
- Keep skill-internal words such as "catalog" or "audit table" out of user-facing text: say "the
  known security build settings" and "the list of targets".
- Use complete sentences. Do not cite a phase number.

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
| Running a long build or test run, and waiting on it | `wait --run`, `engineering-practices` §6 |

## Xcode skill pack

Xcode 27.1 or later exports Apple's own agent skills. `install.sh` runs `xcrun mcpbridge run-agent skills export` into
`~/.agent-harness/xcode-skills/` and links each exported skill into the skills directory, so this repository does not
ship them. The skills keep their Apple names:

| Pack skill | Owning skill here | Use |
|---|---|---|
| `swiftui-specialist`, `swiftui-whats-new-27`, `building-document-based-swiftui-applications` | `swiftui` | SwiftUI idiom, SDK 27 APIs, document apps |
| `app-intents-specialist`, `app-intents-whats-new-27`, `app-resizability` | `apple-platforms` | App Intents, UIKit resizability tasks |
| `adopt-c-bounds-safety` | `memory-safety` | C bounds annotations: language, adoption, debugging |
| `audit-xcode-security-settings` | `xcode` (§7) | The full audit workflow and the settings references named below |
| `device-interaction` | `xcode` (§6) | Device and simulator interaction |
| `modernize-tests` | `testing` (§9) | XCTest to Swift Testing |

Paths such as `swiftui-specialist/references/foreach.md` are relative to the skills directory. When the pack is not
installed (no Xcode 27.1, or a machine that is not a Mac), use `apple-docs` for the same questions, and tell the user
that the pack is missing.

## References

The settings references belong to the pack skill `audit-xcode-security-settings`, under its `references/`:
`security-settings-reference.md` (full settings list with scope column), `enhanced-security.md` (key list, defaults,
deprecated keys, version migration, supported product types), `pointer-authentication.md`, `typed-allocators.md`,
`stack-zero-init.md`, `readonly-platform-memory.md`, `runtime-restrictions.md`, `security-compiler-warnings.md`,
`cpp-hardening.md`, `hardware-memory-tagging.md`, `additional-settings.md`, `adoption-strategy.md`,
`decision-document.md`, `reading-build-settings.md` (output schema, the audit-table columns and predicates, and the
filter recipe for large results; do not read a saved settings dump linearly), `checked-pointer-arithmetic.md`,
`universal-binaries-for-libraries.md`, and `scripts/filter_build_settings.py`. They cite the pack's phase numbers
("Phase 3 Step 4"); the matching steps here are the Phase 1 analysis and the Phase 2 apply in §7.2.

Detail moved out of the body: `references/agent-integration.md` (§3), `run-and-profile.md` (§2),
`device-interaction.md` (§6), `audit-workflow.md` (§7.1-7.2), `hardening-checks.md` (§7.3-7.5).

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

Use this to answer "does it actually work": after a UI-affecting change, or to debug touch and interaction problems.
Not for unit-test-only or build-only requests, or changes that cannot affect UI.

Follow Apple's procedure in `~/.agent-harness/xcode-skills/device-interaction/SKILL.md` (sessions, hierarchy, interaction syntax, timing,
what to report). Three rules of this repository apply on top of it:

- Run it in a subagent when the harness has one: device sessions are resource-heavy and the transcript is verbose.
- Tap the `hitPoint` from the hierarchy, never a position estimated from a screenshot, unless a hitPoint tap had no
  effect after a recapture or the element is an `isRemoteLeafPlaceholder`.
- Report only what the run, the hierarchy, the screenshot, or the log showed, and say what was not exercised. "Works
  on device" is a claim about the flows you actually drove.

---

## 7. Security build settings audit

Enable security build settings and entitlements in stages, from broadly applicable warnings to Enhanced Security
hardening, with Apple's workflow in `~/.agent-harness/xcode-skills/audit-xcode-security-settings/SKILL.md` and its `references/` (settings
reference, Enhanced Security keys, pointer authentication, typed allocators, memory tagging, checked pointer
arithmetic, compiler warnings, C++ hardening, entitlements and Info.plist, the decision document, and
`scripts/filter_build_settings.py` for large settings dumps). Rules of this repository on top of it:

- Change build settings with the Xcode tools when they are available, not by editing `project.pbxproj` by hand.
- Do not enable pointer authentication (`arm64e`) while a binary dependency ships no `arm64e` slice; check the slices
  with `lipo -archs` first.
- Ask once before the first write, and do not touch signing, provisioning, or CI lanes unless the user asks.
- The app's runtime security (Keychain, ATS, WebViews, deep links) is `secure-coding`; this section is the binary's
  build configuration.

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
`~/.agent-harness/xcode-skills/`. They are not installed as separate skills: each one is reference material for the skill of this repository
that owns its topic, which routes to it by path. A path such as `swiftui-specialist/references/foreach.md` means
`~/.agent-harness/xcode-skills/swiftui-specialist/references/foreach.md`.

| Pack skill | Owning skill here | Use |
|---|---|---|
| `swiftui-specialist`, `swiftui-whats-new-27`, `building-document-based-swiftui-applications` | `swiftui` | SwiftUI idiom, SDK 27 APIs, document apps |
| `app-intents-specialist`, `app-intents-whats-new-27`, `app-resizability` | `apple-platforms` | App Intents, UIKit resizability tasks |
| `adopt-c-bounds-safety` | `memory-safety` | C bounds annotations: language, adoption, debugging |
| `audit-xcode-security-settings` | `xcode` (§7) | The security build-settings audit |
| `device-interaction` | `xcode` (§6) | Device and simulator interaction |
| `modernize-tests` | `testing` (§9) | XCTest to Swift Testing |

Read a pack skill's `SKILL.md` first; it names the reference for each topic. When `~/.agent-harness/xcode-skills` is missing (no Xcode 27.1,
or not a Mac), use `apple-docs` for the same questions and tell the user that the pack is not installed.

## References

`references/agent-integration.md` (§3), `references/run-and-profile.md` (§2).

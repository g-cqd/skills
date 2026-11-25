# Testing, Verification, Fuzzing, Mutation Testing & Debugging

## Contents
- [1. Test Strategy & Selection Matrix](#1-test-strategy--selection-matrix)
- [2. TDD, ATDD & Build-Efficient Test Loops](#2-tdd-atdd--build-efficient-test-loops)
- [3. Swift Testing Patterns & Anti-Patterns](#3-swift-testing-patterns--anti-patterns)
- [4. Property-Based, Contract, Fuzz & Sanitizer Testing](#4-property-based-contract-fuzz--sanitizer-testing)
- [5. Mutation Testing Discipline](#5-mutation-testing-discipline)
- [6. Systematic Debugging & Flaky-Failure Playbook](#6-systematic-debugging--flaky-failure-playbook)

---

## 1. Test Strategy & Selection Matrix

Choose the test level by **what can fail**, not by rigid coverage percentages:

| Failure class | Right test level | Key rule |
|---|---|---|
| Pure domain rule, parser, codec, state transition | Unit test (~70%) | Fast, isolated, deterministic, zero OS/network I/O |
| Table of edge cases / valid & invalid inputs | Parameterized unit test | One `@Test(arguments:)` rather than copy-pasted functions |
| Universal invariant (round-trip, monotonicity, bounds) | Property-based test (~5%) | Seeded RNG; save every shrunk counterexample as a permanent regression test |
| Two modules or process/DB/WebKit boundaries disagreeing | Integration / contract test (~15%) | Use real internal modules; mock only at external system boundaries |
| App/CLI launches, serves, or packages cleanly | Smoke test (~5%) | Verify binary launches, `--version` matches, `spctl`/`codesign` hold |
| Critical end-to-end user or security journey | E2E test (< 5%) | Keep few, isolated, and deterministic |
| Bug fix or security finding | Regression test (mandatory) | Must **fail before the fix** and pass after; link the bug/finding ID |

Measure coverage by **behaviors and security invariants exercised**, not line percentage alone. Delete tests that assert nothing, duplicate another test, or test private implementation trivia.

---

## 2. TDD, ATDD & Build-Efficient Test Loops

### Inner loop (compiled languages — build once per step)
1. **Example mapping (multi-rule features):** list Rules, Examples, and Open Questions before coding.
2. **Red:** write the focused tests for one step together, build once, and confirm they fail **for the expected reason** (a compile error or wrong assertion is not a valid Red).
3. **Green:** write the minimum **general** production code to pass (never special-case test inputs), build once, and run only the filtered tests (`swift test --skip-build --filter ...`).
4. **Refactor & simplify:** clean up structure while keeping tests green; run the full touched-package suite once after rebasing on main before hand-back.

### Legacy untested code
1. Write **characterization tests** pinning current observable behavior (including quirks).
2. Introduce the smallest **seam** (sprout new unit, wrap existing call, or extract dependency protocol).
3. Only then modify behavior under TDD.

---

## 3. Swift Testing Patterns & Anti-Patterns

Use **Swift Testing** (`import Testing`) for all new non-XCUI tests (keep `XCTest` only for `XCUI*` UI automation and `measure {}` unless a task asks to migrate).

- **Assertions:** use `#expect(...)`, `#expect(throws: ExpectedError.self)` (always name the expected error type/value, never bare `Error.self`), `try #require(...)` (never `!`), and `confirmation("event", expectedCount: n)` for async callbacks. Never use `Issue.record` where `#expect` applies.
- **Readable names:** write test function names in backticks as behavior sentences, e.g. ``@Test func `refuses expired release index`()``.
- **Structure:** one `@Suite` per file (following repo source-shape rules); build SUTs with a `makeSUT(...)` helper providing clean defaulted dependencies; use spies recording call arguments rather than fragile interaction mocks.
- **Forbidden in tests:**
  - Zero `Task.sleep`, `Thread.sleep`, `usleep`, `Task.yield`, or wall-clock `Date()` assertions. Inject a controllable clock/runtime and wait on explicit async continuations or `confirmation`.
  - Zero unseeded `Int.random` / `SystemRandomNumberGenerator` — use a deterministic `SeededRNG` and log the seed on failure.
  - Zero shared mutable global state or writes to real user `$HOME` / `~/.config` / Keychain — isolate every test in an ephemeral temporary directory cleaned in `defer`.

---

## 4. Property-Based, Contract, Fuzz & Sanitizer Testing

### Mandatory hostile-input battery for parsers & security boundaries
Every parser reachable from untrusted bytes (terminal escapes, Markdown/HTML/XML, JSON/Protobuf, archives/CRX3/XPI, encrypted backup restores, URLs/IPs, CLI/shell inputs, IPC frames) must have:
- **Size/depth/pixel cap tests** (asserting clean typed refusal, never crash/OOM/stack overflow).
- **Differential oracle tests** (e.g., Metal vs CPU pixel comparison, SIMD vs scalar reference parity, spec conformance suites like CommonMark/JSONTestSuite).
- **Coverage-guided fuzz target** (libFuzzer / Swift fuzzing) + checked-in crash/seed corpus in the repo, run in CI smoke mode and continuously on parser changes.

### Sanitizers in CI
| Sanitizer | Detects | CI placement |
|---|---|---|
| **ASan + UBSan** (`-fsanitize=address,undefined,unsigned-integer-overflow`) | Out-of-bounds, UAF, double-free, integer overflow, misalignment | Dedicated CI job on C/SIMD kernels, FFI bridges, and unsafe Swift wrappers |
| **TSan** (`-fsanitize=thread`) | Data races (mutually exclusive with ASan) | Separate CI job on concurrent runtime/state tests |
| **Leaks / FD checks** (`leaks`, static ARC & resource-obligation analyzers) | Retain cycles, unclosed descriptors, unlinked temp files | Quality gate + isolated release smoke run |

A C/unsafe code path without sanitizer CI coverage is an untested path.

---

## 5. Mutation Testing Discipline

Mutation testing proves that tests actually catch logic faults rather than merely executing lines.

- **Where to run:** on PR changed lines (`diff-base`) and nightly/background runs — **never** inside the fast inner edit loop.
- **Isolation mandatory on shared/CI runners:** always run on an **ephemeral copy** of the workspace (never in-place on a shared checkout), inside per-job temporary build/package/output directories (`$RUNNER_TEMP`), with `permissions: { contents: read }`, HMAC-authenticated verdict caches when shared, and a post-step `git status --porcelain` check verifying zero mutation leaked into the checkout.
- **Target & triage:** aim for >80% kill rate on core domain and security boundary logic. Triage every survivor: add the missing assertion, delete dead code if the mutant is genuinely equivalent/unreachable, or explicitly document equivalent mutants.

---

## 6. Systematic Debugging & Flaky-Failure Playbook

### The 6-step root-cause loop
1. **Reproduce deterministically:** capture exact command, inputs, OS/toolchain version, and failure rate (`k/N` for flakes). Never guess-fix without reproducing unless explicitly doing read-only analysis (then label unverified).
2. **Observe before hypothesizing:** inspect the **first** error in the log; verify with live logs/breakpoints/probes that every assumed precondition actually holds (including whether the code path runs at all).
3. **One falsifiable hypothesis:** write *"X causes Y because Z"* and predict what the next experiment will show if true vs. false.
4. **Bisect one variable at a time:** `git bisect` commits, halve inputs, or isolate code slices. Revert failed probe edits before trying the next variable.
5. **State root cause in one sentence, then apply minimal fix:** fix the cause (never mask with a blind null-check or `try?`), verify the reproduction passes, and keep unrelated cleanups out of the fix commit.
6. **Lock it in:** add a permanent red-first regression test and run the full touched suite.

### 3-failure escalation gate
If three fix attempts fail, **stop immediately**. Write two explicit lists — **Proven facts (with evidence)** and **Unverified assumptions** — check the assumptions from scratch, and re-derive or discuss the architecture with the user before attempting a 4th change.

### Flaky-failure triage order (stop at first confirmed cause)
1. Shared mutable state between tests (singletons, env vars, shared temp paths, shared simulator/DB).
2. Wall-clock / timezone / timer race dependence.
3. Async task ordering, actor reentrancy, or cancellation races.
4. Filesystem / port / network nondeterminism (bind ephemeral port `0`, isolated temp dirs).
5. Test execution order dependence (compare isolated single-test run vs full suite / `--no-parallel` vs parallel).
6. Unseeded randomness (fix seed and re-run).

Treat any flaky test as a real concurrency or state-isolation bug — never retry it away.

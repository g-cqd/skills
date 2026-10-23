---
name: testing
description: >-
  Language-agnostic testing, with Swift Testing and XCTest migration. Use for TDD, test
  strategy, regression and property-based tests, test doubles, legacy characterization,
  coverage, flaky suites, or migrating XCTest to @Test, #expect, and #require. For Swift
  concurrency test patterns, use `swift`; for running Apple builds and tests, use `xcode`.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Testing

This skill covers deciding what to test and judging whether a test is worth keeping. For running
tests, use `xcode`; for the concurrency patterns under test, use `swift`.

Sections 1–8 are language-agnostic and complete on their own. Section 9 is Apple-specific.

## Contract

```
§ORDER    test-first ≻ test-after ⇒ RED ! confirmed-failing BEFORE green
§ONE      1 test ∷ 1 behavior · 1 reason-to-fail
§BEHAVIOR assert-behavior ¬implementation ⇒ refactor ¬breaks-test
§EARN     ∀test-written|reviewed ! necessary ∧ ¬duplicate ∧ meaningful ∨ ⇒ cut|merge
§COVER    coverage ∷ behavior-measured ¬percentage-measured
§BAN      sleep|timeout ∈ test · test ∀private-method · assert-on-nothing ·
          shared-state-between-tests · deferring tests to a follow-up
§PRECEDE  project-conventions ≻ this-skill ∀factory|double|fixture
```

---

## 1. Strategy — what to test, and where

```
        /\
       /  \   E2E            < 5%   slow, critical paths only
      /----\
     / Smoke \               ~5%    does it start and serve at all
    /--------\
   /Integration\             ~15%   component interaction
  /------------\
 /Property-based\            ~5%    invariants over generated input
/----------------\
/      Unit       \          ~70%   fast, isolated
--------------------
```

The shape is a result, not a target. If integration tests outnumber unit tests, the units are
usually too coupled to test alone; fix the design, not the ratio.

**Choose the level by what can break.**

| The rule… | Test |
|---|---|
| breaks only when two modules disagree | Integration test |
| must hold for every input | Property |
| has a fixed table of cases | Parameterized unit test |

---

## 2. Before implementation

### Example mapping

Before you write code for a feature with more than one rule, decompose it with the user into the
**rule**, the **examples** that illustrate it, and the **questions** nobody can answer yet. The
questions are the main output: they are the requirement gaps. If you cannot ask the user, list
the questions in the report and state the assumption you used for each.

### ATDD — the outer loop

1. Write a failing acceptance test for the user-visible behavior.
2. Drive the pieces with the TDD inner loop (§2.3).
3. When the inner loops are done, the acceptance test passes. If it does not, the decomposition
   was wrong: continue the inner loops. Do not edit the acceptance test to make it pass.

### TDD — the inner loop

| Phase | Action | Gate |
|---|---|---|
| **Red** | Write a failing test for one behavior | **Stop. Confirm it fails, and fails for the right reason.** |
| **Green** | Write the minimum code to pass | Stop. Confirm it passes. |
| **Refactor** | Clean up, tests stay green | Stop. Confirm green, then next test. |

Rules:

1. Write no production code for a behavior change without a failing test for that behavior.
2. Write only enough code to pass the current test.
3. Test one behavior per test.

In a compiled language, build once per step, not once per test:

1. Write the step's tests together, then build once to see them fail.
2. Write the code, then build once to see them pass.

Run only the filtered tests that the change touches, from that build. Do not use a test command
that builds first (SwiftPM: `swift` §6). Run the full suite once, at the end, after you catch up
with the main line (`engineering-practices` §5, Hand-back).

"Minimum code to pass" means the minimum general code, not code special-cased to the test inputs.
Tests verify correctness; they do not define the solution. If a test is wrong, say so and do not
work around it.

---

## 3. Property-based and contract testing

**Property-based**: assert an invariant over generated input instead of a fixed example. When a
property fails, keep the shrinker's minimal counterexample as a regression case (§5).

**Contract testing**: when two modules or services share an interface, test both sides against one
shared contract. A consumer test that mocks the provider proves nothing about the provider.

---

## 4. Legacy code

Code without tests cannot be changed safely, and often cannot be tested without changing it. Start
with **characterization tests**: tests that assert what the code does now, bugs included, so that
each later change is visible. They record behavior; they do not specify it.

Then create a seam, choosing the one that changes the fewest lines: **sprout** the new behavior
into a new, tested unit; **wrap** the existing call to add behavior around it; or **extract an
interface** to make the dependency substitutable.

---

## 5. After implementation

| Type | What it proves | Key discipline |
|---|---|---|
| **Integration** | Components agree | Mock at the *system* boundary; use real implementations between your own modules |
| **Regression** | A fixed bug stays fixed | Reproduce the exact failure, not the happy path. Link it to the ticket. Delete it only when the behavior it guards is removed from the requirements |
| **Mutation** | The tests catch bugs | Target >80% on critical logic; review every survivor |
| **Snapshot** | Rendered output is stable | Deterministic data only — no clock, no random ids |
| **Performance** | It has not got slower | Baselines where the repository already runs benchmarks in CI; before/after numbers |
| **Fuzz** | Malformed input cannot crash it | Parsers, decoders, validators. Must return errors, never crash |

**Each bug fix gets a regression test.** If the project has no test harness, keep the reproduction
as a script and say so.

**Size the tests to the task.** Commit tests when the task asks for them or when the repository
already keeps tests for this kind of change. Size them like the neighbouring test files: about one
focused test per stated behavior. Do not commit scratch checks written while exploring as
permanent tests.

---

## 6. Test doubles

- Spies record **call counts and captured arguments in arrays**, not a `wasCalled` boolean. A
  boolean cannot catch "called twice" or "called with the wrong value".
- Inject each dependency of the unit under test. A test that touches the real filesystem, clock,
  or network is not a unit test.
- Mock at the **system** boundary. Use real implementations between your own modules; mocking them
  against each other tests the mocks.

---

## 7. Test quality

| Smell | Symptom | Cure |
|---|---|---|
| Flaky | Random failures | Remove time and order dependencies; inject a controllable clock |
| Brittle | Breaks on refactor | Assert behavior, not implementation |
| Slow | >100 ms | Mock I/O; reduce scope |
| Coupled | Needs another test to have run | Fresh state per test |
| Tautological | Can never fail | Assert real outcomes — **run mutation testing** |
| Obscure | Unreadable | Better name, less setup |
| Eager | Tests a private method | Test through the public API |
| Giant | Several unrelated assertions | Split into focused tests |

Use mutation testing to find tautological tests. A surviving mutant marks code that a test ran
without asserting on. Coverage percentage cannot detect this, so coverage is measured in
behaviors, not percent.

---

## 8. Review checklist

Apply each item to the code and tests in the change. Mark an item N/A when the change contains no
code of that kind (for example, no parser, no UI).

**Before and during**

- [ ] Example mapping done for features with more than one rule; open questions raised
- [ ] Acceptance tests define "done", written before implementation
- [ ] Red confirmed failing, for the right reason, before green
- [ ] One behavior per test, clear Given-When-Then
- [ ] Test survives refactoring — asserts behavior
- [ ] Properties used for invariants (round-trip, idempotence, commutativity)
- [ ] Contract tests verify both sides
- [ ] Legacy code characterized before modification

**Per test**

- [ ] Descriptive name stating the behavior under test
- [ ] Happy path, error paths, boundary values all covered
- [ ] Initialization tests verify **all** initial state, not one field
- [ ] Exact equality on whole collections, not only the first element
- [ ] All dependencies injected; no real I/O
- [ ] No sleeps or timeouts
- [ ] Spies assert call counts and captured arguments
- [ ] Written with the code, not deferred

**After**

- [ ] Each bug fix has a linked regression test
- [ ] Critical boundaries integration-tested with real implementations
- [ ] Mutation score >80% on critical logic; survivors reviewed
- [ ] UI snapshots across themes and accessibility sizes
- [ ] Hot paths benchmarked with CI baselines
- [ ] Parsers and validators fuzzed
- [ ] Critical flows smoke-tested
- [ ] Full suite green with no unexplained failure, run once at the end, after catching up with the main line, from the existing build, and read from the runner's report or exit status, not a log's tail

---

## 9. Apple platforms — Swift Testing

Write new tests with Swift Testing. Migrate or remove the XCTest suites in scope only when the
task asks for migration or modernization, or when the project's `AGENTS.md` requires it. Delete
an XCTest test only after its Swift Testing replacement passes. Exception: **XCUI automation tests
using `XCUI*` APIs cannot be migrated**; leave them on XCTest.

### 9.1 API

```swift
import Testing

@Suite(.tags(.networking))
struct UserServiceTests {
  @Test
  func `fetches user successfully`() async throws {
    let sut = UserService(client: StubHTTPClient(response: .success(json)))
    let user = try await sut.fetch(id: "123")
    #expect(user.name == "Alice")
  }

  @Test(arguments: [("valid@test.com", true), ("invalid", false), ("", false)])
  func `validates emails`(email: String, expected: Bool) {
    #expect(EmailValidator.isValid(email) == expected)
  }
}
```

- `#expect` to assert and continue; `try #require` to assert and stop.
- `#expect(throws:)` for errors; prefer the specific error value when the type is `Equatable`.
- `confirmation` for asynchronous callbacks, not a sleep.
- Name each test as a readable sentence in backticks (a raw identifier).
- Parameterize instead of copying a test per input value.
- Tags select runs: `.unit`, `.integration`, `.regression`, `.acceptance`, `.smoke`,
  `.performance`, `.fuzz`, `.contract`, `.characterization`, `.snapshot`.

### 9.2 Migrating from XCTest and modernizing

Follow Apple's procedure in `~/.agent-harness/xcode-skills/modernize-tests/SKILL.md` (from the Xcode skill pack; see
`xcode`, "Xcode skill pack"). Rules of this repository on top of it:

- Migrate only when the task asks for migration or modernization, or touches an XCTest suite in scope (`AGENTS.md`
  STEP 9). Do not migrate when the user is writing new tests, asking only about XCTest features, running tests,
  adding coverage, or debugging a failure without mentioning migration.
- Leave `try #require` as it is: converting it to `#expect` changes behavior, because the test no longer stops there.
- Keep UI tests that use `XCUI*` APIs in XCTest.
- When the pack is not installed, use `apple-docs` for the Swift Testing API and say so.

---

## Boundaries

| Need | Skill |
|---|---|
| Concurrency testing patterns, actors, `Sendable` under test | `swift` |
| Running tests, reading results, CI invocation, simulators | `xcode` |
| Fuzzing for memory corruption; sanitizer coverage | `memory-safety` |
| Benchmark methodology and measurement discipline | `performance-engineering` |
| Running a long suite, waiting on it, reading its result | `wait --run`, `engineering-practices` §6 |
| Whether a change is reviewable and complete | `code-review` |
| Project factory, double, and fixture conventions | `project-conventions` |

## References

**Generic** — `references/test-strategy.md` (example mapping, ATDD, contract, characterization,
fuzz, smoke, test impact analysis, maintenance), `references/tdd-process.md`,
`references/property-based-testing.md`, `references/legacy-code.md` (sprout, wrap, extract
interface), `references/test-doubles.md`, `references/integration-testing.md`,
`references/regression-testing.md`, `references/mutation-testing.md`,
`references/snapshot-testing.md`, `references/performance-testing.md`,
`references/test-quality.md` (FIRST, smells, coverage dimensions),
`references/test-organization.md`

**Apple** — `references/swift-testing.md`, `references/testing.framework.moduleinterface.swift`
(Swift interface of the Testing framework)

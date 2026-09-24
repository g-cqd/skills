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

This skill owns **how you decide what to test, and how you know the tests are worth having**. It
does not own running them (`xcode`) or the concurrency patterns under test (`swift`).

Sections 1–8 are language-agnostic and complete on their own. Section 9 is Apple-specific.

## Contract

```
§ORDER    test-first ≻ test-after ⇒ RED ! confirmed-failing BEFORE green
§ONE      1 test ∷ 1 behavior · 1 reason-to-fail
§BEHAVIOR assert-behavior ¬implementation ⇒ refactor ¬breaks-test
§EARN     ∀test ! necessary ∧ ¬duplicate ∧ meaningful ∨ ⇒ cut|merge
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

The shape is a consequence, not a target. If integration tests outnumber unit tests, the units are
usually too coupled to test alone — fix the design, not the ratio.

**Choose the level by what can break.** A rule that only breaks when two modules disagree is an
integration test. A rule that breaks on any input is a property. A rule with a fixed table of
cases is a parameterized unit test.

---

## 2. Before implementation

### Example mapping

Before writing code for a non-trivial feature, decompose it with the user: the **rule**, the
**examples** that illustrate it, and the **questions** nobody can answer yet. Questions are the
valuable output — they are the requirements gaps, found before implementation rather than during
review.

### ATDD — the outer loop

1. Write a failing acceptance test for the **user-visible** behavior.
2. Drive the pieces with the TDD inner loop (§2.3).
3. When the inner loops are done, the acceptance test passes. If it does not, the decomposition
   was wrong — continue, do not patch the acceptance test.

### TDD — the inner loop

| Phase | Action | Gate |
|---|---|---|
| **Red** | Write a failing test for one behavior | **Stop. Confirm it fails, and fails for the right reason.** |
| **Green** | Write the minimum code to pass | Stop. Confirm it passes. |
| **Refactor** | Clean up, tests stay green | Stop. Confirm green, then next test. |

The laws:

1. No production code without a failing test.
2. Only enough code to pass the current test.
3. One behavior per test.
4. Tests are executable documentation.
5. The loop runs in milliseconds, or it will not be run.

A test that passes the first time you run it has proven nothing. Confirm the red.

"Minimum code to pass" means the minimum *general* code, not code special-cased to the test
inputs. Tests verify correctness; they do not define the solution. If a test itself is wrong, say
so rather than working around it.

---

## 3. Property-based and contract testing

**Property-based** — assert an invariant over generated input rather than a fixed example. The
properties worth reaching for first:

- **Round-trip**: `decode(encode(x)) == x`
- **Idempotence**: `f(f(x)) == f(x)`
- **Commutativity / associativity** where the operation claims it
- **Invariant preservation**: the postcondition holds for every generated input
- **Oracle**: the fast implementation agrees with the obvious slow one

When a property fails, the shrinker's minimal counterexample is the bug report. Keep it as a
permanent regression case (§5).

**Contract testing** — when two modules or services agree on an interface, test the agreement from
**both sides** against one shared contract. A consumer test that mocks the provider proves nothing
about the provider; that is the classic integration gap.

---

## 4. Legacy code

Code without tests cannot be safely changed, and cannot be tested without changing it. Break the
loop with **characterization tests**: write tests that assert what the code *currently does* —
bugs included — so that any change becomes visible. They are a safety net, not a specification.

Then get a seam: **sprout** the new behavior into a fresh, tested unit; **wrap** the existing call
to add behavior around it; or **extract an interface** to make the dependency substitutable. Pick
the smallest one that works.

---

## 5. After implementation

| Type | What it proves | Key discipline |
|---|---|---|
| **Unit** | One unit behaves | Isolated, fast, no I/O |
| **Integration** | Components agree | Mock at the *system* boundary; use real implementations between your own modules |
| **Regression** | A fixed bug stays fixed | Reproduce the exact failure, not the happy path. Link it to the ticket. Permanent — never delete |
| **Mutation** | The tests actually catch bugs | Target >80% on critical logic; review every survivor |
| **Snapshot** | Rendered output is stable | Deterministic data only — no clock, no random ids |
| **Performance** | It has not got slower | Baselines in CI; before/after numbers |
| **Fuzz** | Malformed input cannot crash it | Parsers, decoders, validators. Must return errors, never crash |
| **Smoke** | It works at all | Critical flows, first line of defense after deploy |

**Every bug fix gets a regression test.** No exceptions — a fix without one is an invitation for
the bug to return silently.

**Size the tests to the task.** Commit tests where the task asks for them or the repository
already keeps tests for this kind of change, sized like the neighbouring test files — roughly one
focused test per stated behavior. Scratch checks used while working are not promoted to permanent
test files; they were written to explore, not to specify.

---

## 6. Test doubles

| Type | Purpose |
|---|---|
| **Dummy** | Fills a parameter, never used |
| **Stub** | Returns canned answers |
| **Spy** | Records how it was called |
| **Mock** | Asserts expectations about calls |
| **Fake** | A working but simplified implementation, e.g. in-memory storage |

Rules:

- Spies record **call counts and captured arguments in arrays**, not a `wasCalled` boolean. A
  boolean cannot catch "called twice" or "called with the wrong value".
- Inject every dependency. A test that touches the real filesystem, clock, or network is not a
  unit test.
- Mock at the **system** boundary. Mocking your own modules against each other tests your mocks.

---

## 7. Test quality

**FIRST**: Fast, Independent, Repeatable, Self-validating, Timely.

| Smell | Symptom | Cure |
|---|---|---|
| Flaky | Random failures | Remove time and order dependencies; inject a controllable clock |
| Brittle | Breaks on refactor | Assert behavior, not implementation |
| Slow | >100 ms | Mock I/O; reduce scope |
| Coupled | Needs another test to have run | Fresh state per test |
| Tautological | Can never fail | Assert real outcomes — **run mutation testing** |
| Obscure | Unreadable | Better name, less setup |
| Eager | Tests a private method | Test through the public API |
| Giant | Many unrelated assertions | Split into focused tests |

**Mutation testing is the definitive cure for tautological tests.** If a mutant survives, some
test executed that code without asserting anything about it. Coverage percentage cannot detect
this; that is why coverage is measured in behaviors, not percent.

---

## 8. Review checklist

**Before and during**

- [ ] Example mapping done for complex features; open questions raised
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
- [ ] Exact equality on whole collections, not just the first element
- [ ] All dependencies injected; no real I/O
- [ ] No sleeps or timeouts
- [ ] Spies assert call counts and captured arguments
- [ ] Written alongside the code, not deferred

**After**

- [ ] Every bug fix has a linked regression test
- [ ] Critical boundaries integration-tested with real implementations
- [ ] Mutation score >80% on critical logic; survivors reviewed
- [ ] UI snapshots across themes and accessibility sizes
- [ ] Hot paths benchmarked with CI baselines
- [ ] Parsers and validators fuzzed
- [ ] Critical flows smoke-tested
- [ ] Full suite green with no unexplained failure, read from the runner's report or exit status, not a log's tail

---

## 9. Apple platforms — Swift Testing

Use Swift Testing for new tests. Migrate or remove XCTest suites, with one exception: **XCUI
automation tests using `XCUI*` APIs cannot be migrated** — leave them on XCTest.

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
- `confirmation` for asynchronous callbacks — never a sleep.
- Test names in backticks, as readable sentences. Raw identifiers only for multi-word names that
  read like a sentence.
- Parameterize instead of copying a test per input value.
- Tags enable selective runs: `.unit`, `.integration`, `.regression`, `.acceptance`, `.smoke`,
  `.performance`, `.fuzz`, `.contract`, `.characterization`, `.snapshot`.

### 9.2 Migrating from XCTest

Migrate **one class at a time**; a file may contain both frameworks during the transition.

**Imports** — `import XCTest` → `import Testing`. XCTest re-exports Foundation, so if the file
uses `URL`, `Data`, `CharacterSet`, `ProcessInfo`, add `import Foundation` explicitly.

**Suites** — drop `XCTestCase` inheritance; prefer `struct`. Use `actor` or `final class` only
when `deinit` is needed, since a struct has none.

**Lifecycle** — `setUp` → `init` (may be `async throws`); `tearDown` → `deinit`. Swift Testing
re-runs the initializer fresh before **every** test, so convert implicitly-unwrapped optionals to
non-optional properties initialized inline or in `init`. A test mutating a value-semantic property
must be `mutating`.

**Assertions**

| XCTest | Swift Testing |
|---|---|
| `XCTAssert(x)`, `XCTAssertTrue(x)` | `#expect(x)` |
| `XCTAssertFalse(x)` | `#expect(!x)` |
| `XCTAssertNil(x)` / `XCTAssertNotNil(x)` | `#expect(x == nil)` / `#expect(x != nil)` |
| `XCTAssertEqual(x, y)` / `XCTAssertNotEqual` | `#expect(x == y)` / `#expect(x != y)` |
| `XCTAssertIdentical` / `XCTAssertNotIdentical` | `#expect(x === y)` / `#expect(x !== y)` |
| `XCTAssertGreaterThan(x, y)` | `#expect(x > y)` |
| `XCTAssertGreaterThanOrEqual(x, y)` | `#expect(x >= y)` |
| `XCTAssertLessThan(x, y)` | `#expect(x < y)` |
| `XCTAssertLessThanOrEqual(x, y)` | `#expect(x <= y)` |
| `try XCTUnwrap(x)` | `try #require(x)` |
| `XCTAssertThrowsError(try f())` | `#expect(throws: (any Error).self) { try f() }` |
| `XCTAssertNoThrow(try f())` | `#expect(throws: Never.self) { try f() }` |
| `XCTestExpectation` + `fulfill` + `fulfillment(of:)` | `await confirmation("…") { confirm in … }` |
| `try XCTSkipIf(c)` / `try XCTSkipUnless(c)` | `@Test(.disabled(if: c))` / `@Test(.enabled(if: c))` |
| `throw XCTSkip("…")` mid-test | `try Test.cancel("…")` |
| `XCTExpectFailure("…") { }` | `withKnownIssue("…") { }` |
| `XCTAttachment` + `add` | `Attachment.record(value)` |

`XCTAssertEqual(_:_:accuracy:)` has no direct equivalent — compare with explicit floating-point
tolerance.

For over-fulfilment, `assertForOverFulfill = false` with a count becomes a range:
`await confirmation("…", expectedCount: 10...)`. For intermittent known issues, `.nonStrict()`
becomes `isIntermittent: true`; conditional cases use `when:` and `matching:`.

**`continueAfterFailure = false`** changes semantics: XCTest halts on first failure. To preserve
it, every subsequent assertion becomes `try #require`, and the method gains `throws`. If it was
set in `setUp`, this applies to **every assertion in every test** in that class.

**Skips by OS version** — replace `.enabled(if:)` with an `@available` attribute on the test.

**Concurrency** — XCTest runs synchronous tests on the main actor, serially within a suite. Swift
Testing runs them on arbitrary tasks, in parallel. Add `@MainActor` **only** where the XCTest form
genuinely relied on main-actor isolation. Add `@Suite(.serialized)` where tests share mutable
state.

### 9.3 Modernization rules

- Promote `XCTFail` and `Issue.record` to `#expect` or `#require` — a `guard … else { Issue.record }`
  chain becomes `try #require(…)`. Do not use `Issue.record` as a lazy substitute.
- Leave `try #require` as it is; converting it to `#expect` changes behavior, since the test no
  longer stops at that point.
- Convert loops over inputs and near-duplicate tests into `@Test(arguments:)`.
- Convert multi-word camelCase `@Test` names to sentence-case raw identifiers.
- Do not use underscore-prefixed API such as `#_sourceLocation`; use the full
  `SourceLocation(fileID:filePath:line:column:)`.

Do **not** apply migration when the user is writing new tests from scratch, asking only about
XCTest features, running tests or reading results, adding coverage for new functionality, or
debugging a failure without mentioning migration.

---

## Boundaries

| Need | Skill |
|---|---|
| Concurrency testing patterns, actors, `Sendable` under test | `swift` |
| Running tests, reading results, CI invocation, simulators | `xcode` |
| Fuzzing for memory corruption; sanitizer coverage | `memory-safety` |
| Benchmark methodology and measurement discipline | `performance-engineering` |
| Running a long suite beside other agents, waiting on it, reading its result | `planner` (`scripts/work.py`), `engineering-practices` §6 |
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

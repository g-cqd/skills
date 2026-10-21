---
name: debugging
description: >-
  Language-agnostic: diagnose bugs, failing tests, crashes, hangs, flaky behavior, and
  wrong output through reproduction, hypotheses, and isolation. Use before proposing a
  fix, especially when earlier fixes failed or a test fails only in the suite. For
  slowness, use `performance-engineering`; for writing regression tests, use `testing`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Systematic Debugging

**Do not fix a bug until you can state its root cause in one sentence and show the evidence.** A
fix for an unknown cause cannot be verified; it can only move the symptom.

This skill covers why a program is wrong. For slowness, use `performance-engineering`. For what
the regression test asserts, use `testing`.

## Contract

```
§CAUSE    ¬fix ∅root-cause-stated-in-1-sentence ∧ evidence
§OBSERVE  read FIRST error ¬last · verify ∀assumption-the-hypothesis-uses with evidence ¬belief
§ONE      1 hypothesis · 1 variable · 1 change per experiment
§HALVE    ∀experiment ⇒ halve the search space (bisect)
§GATE     3 failed-fixes ⇒ STOP · re-derive · ⍰user (subagent: report) ¬attempt-4
§BAN      guess-fix ∅reproduction (unless brief accepts analysis-only ⇒ mark unverified) ·
          null-check-to-silence-unknown-cause · batch-multiple-changes · blame-compiler ∅minimal-case
```

---

## The loop

### 1. Reproduce

- Get a deterministic reproduction. If the failure is flaky, measure the failure rate over a fixed
  number of runs ("3 in 50 runs"), not "sometimes".
- Record the exact error, environment, inputs, and versions.
- Read the failing code path and the actual data before you form a hypothesis. Do not reason from
  memory of how the code probably works.
- If you cannot reproduce, collect logs, state diffs, and timing. Do not write a fix, unless the
  brief accepts a fix from analysis alone; then mark the fix unverified. If you still cannot
  reproduce after one round of added instrumentation, stop and report the facts collected and the
  candidate causes.

### 2. Observe before you form a hypothesis

- Start from the first error. Treat later errors as consequences of the first until the first is
  explained.
- Verify each assumption that the current hypothesis depends on, with a log, debugger, breakpoint,
  or print probe. Check first whether the suspect function is called at all.

### 3. Hypothesize: falsifiable, one at a time

- Write the hypothesis as "X causes Y because Z", with a prediction that the next experiment can
  refute. If no result could refute it, rewrite it.
- Run the cheapest experiment that can refute it.

### 4. Experiment: one variable at a time

- **Minimize the reproduction**: find the smallest input or code slice that still fails.
- **Bisect**: by commit (`git bisect`), by data (halve the input), or by code path (disable half).
- **Change one thing per run.** Revert each experimental change before the next run.

### 5. Root cause, then minimal fix

- State the root cause in one sentence. If you cannot, return to step 2, even if the symptom has
  gone. After three refuted hypotheses with no new evidence, stop and report the proven and
  assumed lists (Escalation gate).
- Fix the cause, not the symptom. The fix must make the original reproduction pass, and you must
  be able to explain why.
- Fix only the root cause you found. Report a nearby pre-existing bug or improvement as a
  follow-up; do not put it in the same change.

### 6. Lock it in

- Add a regression test that fails without the fix and passes with it. Run it in both states. If
  the project has no test harness, keep the reproduction as a script or documented steps and say
  so in the report.
- Run the full suite to find collateral damage. If no suite exists, rerun the original
  reproduction and the nearest manual checks, and state that no suite exists.
- Write down the cause, the fix, and what now prevents a silent regression.

---

## Escalation gate

**After three failed fix attempts, stop.** A fourth attempt from the same mental model fails in
the same way.

1. Re-derive from scratch. List what is **proven** and what is **assumed**; check the assumed
   items first.
2. Discuss the architecture with the user before another attempt. If you cannot ask the user
   (for example, as a subagent), stop and report the proven and assumed lists.

## Flaky-failure playbook

Check these suspects in this order; stop at the first one confirmed:

1. Shared mutable state between tests
2. Time or clock dependence
3. Async ordering and races
4. Network or filesystem nondeterminism
5. Test-order dependence: compare the test run alone with the test run in the suite
6. Hidden randomness: fix the seed and check whether the failure becomes deterministic

Treat a flaky failure as a real bug. A test that fails 2% of the time reports a race that will
occur in production.

## Rationalizations that hide bugs

| If you think… | Fact |
|---|---|
| "A null-check or try/catch makes it go away" | The symptom is hidden; the cause is still upstream. Add the check only when null or the error is a valid, explained input |
| "It is probably the framework or compiler" | Rarely true. Prove it with a minimal case first |
| "It works on my machine / the re-run passed" | The failure is flaky: race, ordering, time, or shared state |
| "Too urgent for a regression test" | The same bug returning mid-incident costs more time than the test |
| "Several changes at once save time" | You can no longer attribute the result |

## Boundaries

| Need | Skill |
|---|---|
| Writing the regression test, test design | `testing` |
| Slowness rather than wrongness | `performance-engineering` |
| Memory corruption, UAF, sanitizer selection | `memory-safety` |
| Build, run, simulator loops, on-device reproduction | `xcode` |
| Concurrency semantics behind a race | `swift` |
| Whether the fix is reviewable and complete | `code-review` |
| Running the suite or a long reproduction, and waiting on it | `work run` (`planner`'s `scripts/work.py`), `engineering-practices` §6 |

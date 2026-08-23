---
name: engineering-practices
description: >
  Language-agnostic development practice — how work is produced and delivered,
  as distinct from how it is judged. Covers disciplined catalog-based
  refactoring (extract, inline, rename, move, replace conditional with
  polymorphism) with the rule that structure and behavior never change in one
  commit, the rule of three for duplication, in-scope-only boy-scouting, small
  reviewable batches sliced by behavior, trunk-based delivery with short-lived
  branches and feature flags, atomic commits whose message states why, the DORA
  four keys (lead time, deploy frequency, change-failure rate, time to restore),
  dependency hygiene for adding and upgrading, working safely in legacy code,
  and a verification-before-completion gate. Use when refactoring, structuring a
  change into commits or PRs (pull requests), deciding branching or release flow,
  adding or upgrading a dependency, working in code with no tests, or closing
  out a task and asking "is this actually done?". Not for review checklists,
  which is `code-review`; not for test methodology, which is `testing`; not for
  decomposing or scheduling the work, which is `planner`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Engineering Practices

```
IRON LAW: A TASK IS DONE WHEN THE EVIDENCE SAYS SO — BUILT, TESTED,
VERIFIED AGAINST THE ORIGINAL REQUEST — NOT WHEN THE CODE IS WRITTEN.
```

This skill owns **producing and delivering the change**. Judging one is `code-review`; planning
one is `planner`.

## Contract

```
§SEPARATE refactor-commit ⊥ behavior-commit ⇒ ¬mix-in-one
§GREEN    ∀refactor-step tests-green · ∅tests ⇒ characterize-first
§SMALL    PR ≤ ~15-min-review · slice-by-behavior ¬by-file-type
§SCOPE    boy-scout ∈ scope-only ⇒ rest ⇒ follow-up-ticket
§CLOSE    ¬report-done BEFORE §6 gate ∀5-steps
§DEPS     add-dependency ∷ architectural-decision ¬convenience
§BAN      big-bang-rewrite · drive-by-churn · flag ∅removal-ticket ·
          "tests pass" as done-evidence
```

---

## 1. Refactoring discipline

- **Refactoring changes structure, never behavior.** Tests stay green at every step. If there are
  no tests, write characterization tests first (`testing` §4) — otherwise you are not refactoring,
  you are rewriting and hoping.
- **Small named moves, one at a time**: extract function, inline, rename, move, replace
  conditional with polymorphism. Commit between moves. A big-bang rewrite has no safe point to
  stop at.
- **Never mix refactoring and behavior change in one commit or PR.** Two PRs, or clearly separated
  commits. A reviewer cannot see a one-line behavior change inside a 600-line move, and neither
  can `git bisect`.
- **Rule of three** — tolerate duplication twice, abstract on the third occurrence, and only if
  the name conveys more than the code did. A premature abstraction costs more than the duplication
  it removed.
- **Boy-scout in scope only.** Improve what the task touches; file follow-ups for the rest. Drive-by
  churn is how a reviewable change becomes an unreviewable one.

## 2. Change and delivery flow

- **Small batches.** A PR reviewable in about fifteen minutes beats a two-thousand-line drop.
  Slice **by behavior**, not by file type — "all the models, then all the views" produces PRs that
  cannot be reasoned about independently.
- **Trunk-based mindset.** Short-lived branches, integrate continuously. Gate incomplete features
  behind flags — and file the flag-removal follow-up at the same time, because without a ticket
  "later" is never.
- **Commits are atomic and buildable**, and the message states **why**. The diff already says
  what. Include the ticket identifier where the repository follows that convention — detect it,
  never invent it (`project-conventions`).
- **DORA four keys, directionally**: lead time, deploy frequency, change-failure rate, time to
  restore. Favor changes that improve flow without hurting stability; the four move together when
  the practice is right and trade against each other when it is not.

## 3. Legacy code

Code without tests cannot be changed safely, and cannot be tested without being changed. Break the
deadlock the same way every time:

1. **Characterize** — pin the current behavior, bugs included, so any change becomes visible.
2. **Find a seam** — sprout the new behavior into a fresh tested unit, wrap the existing call, or
   extract an interface to make a dependency substitutable.
3. **Then** change behavior, with the net in place.

Pick the smallest seam that works. The goal is a safe next step, not a clean architecture today.

## 4. Dependency hygiene

**Adding a dependency is an architectural decision**, not a convenience. Weigh maintenance
activity, transitive surface, license, and supply-chain posture (`secure-coding`). You are
adopting its bugs, its CVEs, and its upgrade treadmill.

- Prefer the standard library and the platform.
- Wrap third-party APIs you do not control at module boundaries you do — so replacing the
  dependency later is a local change.
- **Upgrades: one dependency per PR**, changelog read, lockfile committed, tests run. A bulk
  upgrade PR that breaks something tells you nothing about which one did it.

## 5. Verification before completion

Before reporting **any** task as done:

1. **Re-read the original request.** Was *this* what was asked? Anything quietly dropped?
2. **Build and run the full test suite** — not just the new tests.
3. **Exercise the change once like a user.** Run it. For UI, use the validation loop in `xcode`.
4. **Review your own diff**: leftovers, debug prints, dead code, unrelated edits, commented-out
   experiments.
5. **State residual risks and follow-ups explicitly.** Silence reads as "nothing left", which is
   almost never true.

Step 1 catches the most expensive class of failure: a correct implementation of the wrong thing.

## 6. Rationalizations

| If you think… | Reality |
|---|---|
| "I'll refactor while I'm in here anyway" | Scope creep kills reviewability. File a follow-up |
| "The tests pass, ship it" | Tests prove what tests cover. Verify the actual request |
| "One big PR is more efficient" | Review quality collapses; defects hide in bulk |
| "We'll remove the feature flag later" | Without a ticket, later is never |
| "A quick library will save time" | You just adopted its bugs, CVEs, and upgrade train |

## Boundaries

| Need | Skill |
|---|---|
| Review checklists, severity calibration, review tone | `code-review` |
| Test methodology, characterization technique in depth | `testing` |
| Decomposition, roadmaps, execution contracts | `planner` |
| Root-cause workflow for a bug | `debugging` |
| Supply-chain and license risk in depth | `secure-coding` |
| PR descriptions, commit and release documentation | `work-docs` |
| Detecting a repository's ticket and branch conventions | `project-conventions` |
| Build, test, and run loops on Apple platforms | `xcode` |

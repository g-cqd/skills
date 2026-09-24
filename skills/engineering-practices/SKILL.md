---
name: engineering-practices
description: >-
  Language-agnostic: refactoring, small reviewable changes, dependency hygiene, delivery
  flow, and verification before completion. Use when organizing commits or PRs, choosing
  branch and release practices, upgrading dependencies, or changing legacy code. For code
  review, use `code-review`; for test design, use `testing`; for task decomposition, use
  `planner`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Engineering Practices

**A task is done when the evidence says so — built, tested, verified against the original
request — not when the code is written.** Written code is the point where the expensive mistakes
are still invisible.

This skill owns **producing and delivering the change**. Judging one is `code-review`; planning
one is `planner`.

## Contract

```
§SEPARATE refactor-commit ⊥ behavior-commit ⇒ ¬mix-in-one
§GREEN    ∀refactor-step tests-green · ∅tests ⇒ characterize-first
§SMALL    PR ≤ ~15-min-review · slice-by-behavior ¬by-file-type
§SCOPE    boy-scout ∈ scope-only ⇒ rest ⇒ follow-up-ticket
§CLOSE    ¬report-done BEFORE §5 gate ∀5-steps
§WAIT     long-work ⇒ harness-notify | work run|wait (planner) ⇒ ¬fixed-sleep
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
  churn is how a reviewable change becomes an unreviewable one. A pre-existing bug, a performance
  concern, or behavior the task does not mention is reported as a follow-up in your summary, not
  fixed in this change, unless the requested behavior cannot work without it.

## 2. Change and delivery flow

- **Small batches.** A PR reviewable in about fifteen minutes beats a two-thousand-line drop.
  Slice **by behavior**, not by file type — "all the models, then all the views" produces PRs that
  cannot be reasoned about independently.
- **Trunk-based mindset.** Short-lived branches, integrate continuously. Gate incomplete features
  behind flags — and file the flag-removal follow-up at the same time, because without a ticket
  "later" is never.
- **Edit surgically.** Prefer a targeted edit to a whole-file rewrite unless the file is short or
  most of it is changing; a rewrite costs more to produce and hides the actual change in the diff.
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
   experiments. Remove any scratch script or helper file you created for iteration; verifying
   however you like is fine, but the scaffolding does not ship.
5. **State residual risks and follow-ups explicitly.** Silence reads as "nothing left", which is
   almost never true.

Step 1 catches the most expensive class of failure: a correct implementation of the wrong thing.

## 6. Waiting on long-running work

A fixed `sleep` before checking a build, a test run or a delegated job either wastes the difference or checks
too early, and a loop of long sleeps compounds both. Wait on the event, not the clock:

1. **Let the harness tell you.** When the harness runs a command in the background and reports its end, as
   Claude Code does for background commands and subagents, start it that way and carry on with other work, or
   end the turn. The notice arrives the moment it finishes.
2. **Otherwise run it with `work`.** `work` is `planner`'s `scripts/work.py`, installed at
   `~/.agent-harness/bin/work`, and needs no setup. `work run` starts the command when the machine has room for it
   (`--weight N` for the cores it uses), returns the moment it ends with its own status, and stops waiting at a
   limit under the tool call's own (570 s by default). `work wait` waits the same way on what `work` did not start:
   ```sh
   work run --weight 4 -- swift test --parallel      # start it, then wait for it
   work wait job-7                                   # exited 124, still running: wait again
   work wait --pid 4242                              # a process you started elsewhere
   work wait --file tests.status                     # a status file; one holding a number exits with it
   work wait --log build.log 'Build complete'        # a line in a log (an extended regular expression)
   work wait --gone P2.lock                          # a lock file its phase deletes
   ```
   Both exit with the command's own status, or 124 when the limit passes first. Call `work wait` again; never
   lengthen a sleep instead.
3. **Keep the output whole and the status true.** Never pipe a command into `tail`, `head` or `grep` when you need
   its result: the pipe reports the last command's status, so a failed build reads as success, and a cut output hides
   the result lines. `work run` keeps the full output in its log, prints the last lines (`--tail N`) and exits with
   the command's own status: 127 when the command is missing, 128 plus the signal when a signal killed it. If the
   command must be a pipeline, run it as `bash -c 'set -o pipefail; …'`.
4. **Prefer the exit to a log line, and a report to the log.** Output sent to a file is buffered in blocks, Swift's
   test runner's among it, so a `--log` wait can lag the work, and a run that hangs or is killed loses its last
   lines, summary included; `work run` and `--pid` wait on the process itself. Take the result from the exit status
   and from a report the tool writes itself (`swift test --xunit-output FILE`, `xcodebuild -resultBundlePath DIR`),
   and treat a missing summary as a run that did not finish, never as a pass.
5. **Report the time the work took,** from the line `work` prints, which also gives the wait for capacity apart
   from the run, not the time you waited.

## 7. Rationalizations

| If you think… | Reality |
|---|---|
| "I'll refactor while I'm in here anyway" | Scope creep kills reviewability. File a follow-up |
| "I spotted a bug nearby, I'll just fix it" | Unrequested fixes cannot be reviewed against the request. Report it as a follow-up |
| "The tests pass, ship it" | Tests prove what tests cover. Verify the actual request |
| "One big PR is more efficient" | Review quality collapses; defects hide in bulk |
| "We'll remove the feature flag later" | Without a ticket, later is never |
| "A quick library will save time" | You just adopted its bugs, CVEs, and upgrade train |
| "I'll sleep ten minutes, it should be done by then" | It was done in two, or it needs twelve. Wait on the event |

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

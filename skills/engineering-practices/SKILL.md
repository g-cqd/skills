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

**A task is done when the evidence says so: built, tested, and verified against the original
request (§5). Written code is not done.**

This skill owns **producing and delivering the change**. Judging one is `code-review`; planning
one is `planner`.

## Contract

```
§SEPARATE refactor-commit ⊥ behavior-commit ⇒ ¬mix-in-one
§GREEN    ∀refactor-step tests-green · ∅tests ⇒ characterize-first
§SMALL    PR ≤ ~15-min-review · slice-by-behavior ¬by-file-type
§SCOPE    boy-scout ∈ scope-only ⇒ rest ⇒ follow-up ∈ summary
§CLOSE    ¬report-done BEFORE §5 gate · any task ⇒ steps 1,5 · code change ⇒ ∀5-steps
§BUILD    whole-step ⇒ 1 build ¬per-edit · failed-build ⇒ first-error first · fix ∀error ¬result-of-earlier ⇒ 1 rebuild ·
          1 config while-developing ¬matrix · release ×1 per-task ∋ A∧B in-one-binary ·
          rerun ⇒ ¬rebuild · budget ≈4 per-task · report ∋ builds-by-kind
§HANDBACK rebase-on-main ⇒ final build ⇒ full-suite ∀touched-packages ⇒ receiver ¬rebuilds
§WAIT     long-work ⇒ harness-notify | work run|wait (planner) ⇒ ¬fixed-sleep
§DEPS     add-dependency ∷ architectural-decision ¬convenience
§BAN      big-bang-rewrite · drive-by-churn · flag ∅removal-ticket ·
          "tests pass" as done-evidence
```

---

## 1. Refactoring discipline

- **Refactoring changes structure, not behavior.** Tests stay green after each step. If the code
  has no tests, write characterization tests first (`testing` §4).
- **Make one named move at a time**: extract function, inline, rename, move, replace conditional
  with polymorphism. On your own branch, commit after each move, so each commit is a safe point
  to stop.
- **Put refactoring and behavior change in separate PRs, or at least separate commits.** A
  behavior change hidden in a move cannot be seen in review or found by `git bisect`.
- **Rule of three**: tolerate duplication twice. Abstract on the third occurrence, and only if the
  abstraction's name conveys more than the code did.
- **Improve only what the task touches.** Report a pre-existing bug, a performance concern, or
  behavior the task does not mention as a follow-up in your summary. Fix it in this change only if
  the requested behavior cannot work without the fix.

## 2. Change and delivery flow

- **Small batches.** Size a PR so that a review takes about fifteen minutes. Slice **by behavior**,
  not by file type: "all the models, then all the views" produces PRs that cannot be reviewed
  independently.
- **Trunk-based.** Use short-lived branches and integrate continuously. Put incomplete features
  behind flags, and file the flag-removal follow-up ticket when you add the flag.
- **Edit surgically.** Prefer a targeted edit to a whole-file rewrite unless the file is short or
  most of it is changing; a rewrite hides the actual change in the diff.
- **Make each commit atomic and buildable**, with a message that states **why**; the diff already
  shows what. Include the ticket identifier when the repository follows a ticket convention.
  Detect the convention with `project-conventions`; do not invent an identifier.

## 3. Legacy code

To change code that has no tests:

1. **Characterize**: write tests that pin the current behavior, bugs included.
2. **Find a seam**: sprout the new behavior into a new tested unit, wrap the existing call, or
   extract an interface to make a dependency substitutable.
3. **Then** change the behavior.

Pick the smallest seam that makes the next step safe; the goal is not a clean architecture now.

## 4. Dependency hygiene

**Adding a dependency is an architectural decision.** Before adding one, check its maintenance
activity, transitive dependencies, license, and supply-chain posture (`secure-coding`).

- Prefer the standard library and the platform.
- Wrap third-party APIs at a module boundary you control, so replacing the dependency is a local
  change.
- **Upgrades: one dependency per PR**, with the changelog read, the lockfile committed, and the
  tests run, so a failure points to one dependency. Packages that must move together (a framework and its plugin,
  peer dependencies) go in one PR; say which packages and why.

## 5. Verification before completion

Before you report any task as done, do steps 1 and 5. For a task that changes code, do all five.

1. **Re-read the original request.** Check that the change does what was asked and that no part
   of the request was dropped.
2. **Run the full suite of each package the change touches** (Hand-back, step 1), not only the
   new tests: once, from the build you already have, after catching up with the main line (Builds
   and Hand-back, below). If the project has no
   tests, say so in the report.
3. **Exercise the change once as a user would.** Run it. For UI, use the validation loop in
   `xcode`. If the change cannot be run (for example, a library with no host app), say so in the
   report.
4. **Review your own diff** for leftovers, debug prints, dead code, unrelated edits, and
   commented-out experiments. Delete each scratch script or helper file you created; you may
   verify with any tool, but the scratch files do not ship.
5. **State residual risks and follow-ups explicitly.** If there are none, write "none".

### Builds

A build takes minutes of every core; a test run from an existing build takes seconds.

- **No edit–build loop.** Write the whole step, the code and its tests, and read it over before
  you build. Catch type errors during editing with the language server's diagnostics where they
  work, not with a build.
- **Fix a failed build from its log.** Read the first error first; treat later errors as possible
  results of it. Fix each error that is not a result of an earlier one, then rebuild once. Do not
  add fixes you cannot tie to a logged error.
- **One configuration while you develop:** the debug build of the package you changed, with its
  tests (`swift` §6, `xcode`). For a step whose tests you do not run yet, a module-only build
  replaces the test build; do not run both.
- **No combination matrix.** Do not check one change across build combinations: debug and
  release, each target, each flag, each consumer package. The packages a change touches are
  checked once, at hand-back (below).
- **Release once per task,** for the final numbers only (`performance-engineering` §4). Compare
  before and after inside that one binary, behind a runtime switch, where the old path can stay.
  Otherwise build the baseline once and keep it.
- **Test from the build.** Run the filtered tests the change touches from the build you have, and
  the suites of Hand-back step 1 once, at the end. Rerunning a test or a benchmark does not rebuild.
- **Budget about four builds per task:** two or three debug builds and at most one release build.
  State the builds by kind in the report. Going over the budget requires a reason in the report.

### Hand-back

The agent that made a change verifies it. The receiver of the change does not verify it again.

1. **Catch up first.** Rebase your branch onto the current main line (or merge the main line in,
   if the repository merges). If you are on the main line, or the change is uncommitted, skip the
   rebase and say so. Then build once and run the full suite of each package the change
   touches, and the suites of the packages that use an API you changed. That run verifies the
   merged state.
2. **Report what the run covered:** the base commit, each suite with its counts, and the builds
   by kind.
3. **The receiver lands the change without rebuilding** when the main line has not moved since, or
   has moved only in other packages. If the main line changed the same packages, the agent runs
   step 1 again from its warm build; the receiver does not run it from a cold build.

## 6. Waiting on long-running work

Do not wait for a build, a test run, or a delegated job with a fixed `sleep`: it either wastes
time or checks too early. Wait on the event:

1. **Let the harness notify you.** When the harness runs a command in the background and reports
   its end (Claude Code does this for background commands and subagents), start the command that
   way. Then continue with other work, or end the turn.
2. **Otherwise run it with `work`.** `work` is `planner`'s `scripts/work.py`, installed at
   `~/.agent-harness/bin/work`; it needs no setup. `work run` starts the command when the machine
   has capacity (`--weight N` for the cores it uses) and returns when the command ends, with the
   command's status. It stops waiting at a limit below the tool call's own limit (570 s by
   default). `work wait` waits the same way on work that `work` did not start:
   ```sh
   work run --weight 4 -- swift test --parallel      # start it, then wait for it
   work wait job-7                                   # exited 124, still running: wait again
   work wait --pid 4242                              # a process you started elsewhere
   work wait --file tests.status                     # a status file; one holding a number exits with it
   work wait --log build.log 'Build complete'        # a line in a log (an extended regular expression)
   work wait --gone P2.lock                          # a lock file its phase deletes
   ```
   Both exit with the command's own status, or 124 when the limit passes first. On 124, call
   `work wait` again; do not use a longer sleep. After 3 timeouts with no new log output, check
   `work status`, and stop and report if the job is stalled.
3. **Keep the output complete and the status true.** Do not pipe a command into `tail`, `head`, or
   `grep` when you need its result: the pipe reports the last command's status, so a failed build
   reads as success, and the cut output hides the result lines. Use `work run` instead: it keeps the
   full output in its log, prints the last lines (`--tail N`), and exits with the command's own
   status (127 when the command is missing, 128 plus the signal number when a signal killed it). If
   the command must be a pipeline, run it as `bash -c 'set -o pipefail; …'`.
4. **Take the result from the exit status and from the tool's own report, not from the log.**
   - Output sent to a file is buffered in blocks (Swift's test runner included), so a `--log` wait
     can lag the work. `work run` and `--pid` wait on the process itself.
   - A run that hangs or is killed loses its last log lines, summary included, so the log does not
     show the test that did not finish.
   - Use the report the tool writes: `swift test --xunit-output FILE`, `xcodebuild
     -resultBundlePath DIR`.
   - Treat a missing summary as a run that did not finish, not as a pass.
   - To watch a long run live, run it under a pseudo-terminal, which buffers by line:
     `script -q /dev/null swift test`.
5. **Report the time the work took** from the line `work` prints. That line separates the wait
   for capacity from the run time. Do not report the time you waited.

## 7. Rationalizations

| If you think… | Reality |
|---|---|
| "I'll refactor while I'm in here anyway" | Out-of-scope changes make the PR unreviewable. Report it as a follow-up |
| "I spotted a bug nearby, I'll just fix it" | An unrequested fix cannot be reviewed against the request. Report it as a follow-up |
| "The tests pass, ship it" | Tests prove only what they cover. Verify the actual request |
| "One big PR is more efficient" | Review quality drops and defects hide in the bulk |
| "We'll remove the feature flag later" | Without a ticket, the flag stays. File the ticket now |
| "A quick library will save time" | You adopt its bugs, CVEs, and upgrades. Apply §4 |
| "I'll build after this edit, just to check" | Each build takes minutes, and one build reports every error. Finish the step, then build |
| "I'll sleep ten minutes, it should be done by then" | It finishes in two, or it needs twelve. Wait on the event (§6) |

## Boundaries

| Need | Skill |
|---|---|
| Review checklists, severity calibration, review tone | `code-review` |
| Measured pass that trims a diff, a file or a plan | `simplification` |
| Test methodology, characterization technique in depth | `testing` |
| Decomposition, roadmaps, execution contracts | `planner` |
| Root-cause workflow for a bug | `debugging` |
| Supply-chain and license risk in depth | `secure-coding` |
| PR descriptions, commit and release documentation | `work-docs` |
| Detecting a repository's ticket and branch conventions | `project-conventions` |
| Build, test, and run loops on Apple platforms | `xcode` |

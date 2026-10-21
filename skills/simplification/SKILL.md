---
name: simplification
description: >-
  Language-agnostic: run a measured simplification pass over a diff, a file, or a plan
  before it is built. Use when a change looks heavier than its task: speculative
  abstractions, single-use wrappers, unrequested flags, deep nesting, or high cyclomatic
  or cognitive complexity; or when asked to simplify, essentialize, rationalize, trim, or
  reduce complexity. Not for review comments, use `code-review`; for restructuring legacy
  code, `engineering-practices`; for speed, `performance-engineering`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Edit
---

# Simplification

This skill answers one question: what can be removed from this change without changing what the
program does? It works on a diff (the default), on named files, or on a plan before any code exists.
It removes code and proves each removal is safe. It does not look for bugs, enforce style, make code
faster, or redesign a module.

## Contract

```
§SCOPE      the diff or the named files; the plan when no code exists. Nothing outside it changes, except characterization tests added in step 1.
§BEHAVIOUR  same observable behaviour. A test or a characterization pins it BEFORE the first edit; without one, cut only provably unreachable code.
§EVIDENCE   measure first; prove each cut (callers, history, a failing build or test) before making it.
§ORDER      delete ≻ inline ≻ flatten ≻ extract. Extract a piece only if it has a clear name and its caller becomes easier to read.
§BUDGET     production lines, types, files, parameters and dependencies go down. The report justifies each rise.
§STOP       no net reduction, or no remaining candidate has proof ⇒ report "no further change". Do not invent work.
§KEEP       the keep list below survives every pass, and wins over every decision rule; report a cut it blocks as a suggestion.
```

## Choose the mode

| Mode | Input | What is measured and cut |
|---|---|---|
| Diff (default) | A branch, a PR, or uncommitted changes | The functions, types and files the diff touches, against the merge-base |
| File | Named files or a module the user points at | The same, against the current state; no baseline commit needed |
| Plan | A design, a ticket, a proposed approach, no code yet | What the design adds: files, types, options, dependencies, layers |

In Diff and File mode, the project's own conventions win over this skill's defaults. Detect them
first (load `project-conventions`).

## Procedure

1. **Fix the scope and pin behaviour.** Name the base (the merge-base for a diff) and list the
   changed functions. Check that tests cover them. Where no test covers a function, write the
   smallest characterization test first. If you cannot, cut only provably unreachable code in that
   function and report the function as unprotected.
2. **Measure the baseline** at two levels: the changed functions (cognitive and cyclomatic
   complexity, nesting depth, length, parameter count) and the change as a whole (size, spread, and
   the types, files, dependencies and public API the diff adds). See *Measure*. State what could not
   be measured.
3. **List candidates** from the table below, strongest evidence first.
4. **Prove each cut** before making it. Zero callers by search or language server means dead,
   unless the symbol can be reached by name (exported or public API, entry points, selectors,
   reflection, serialization, framework callbacks). Report those as suggestions. A conformer or
   call-site count shows speculative generality. `git log` and `git blame` show why unusual code
   exists. Report a cut without proof as a suggestion; do not make it.
5. **Apply one cut at a time** as the smallest edit that works. Run the tests after each cut, or
   after each file's cuts; if a test fails, revert those cuts.
6. **Re-measure.** Revert a cut that raises a function's cognitive complexity, or that adds a type,
   parameter or file, unless the report states why it pays for itself.
7. **Stop** by `§STOP`, then write the report.

## Candidates, strongest evidence first

| Signal | Evidence to collect | Typical cut |
|---|---|---|
| Dead code: no callers, unreachable branch, flag that only ever has one value | Search and compiler or analyzer output | Delete |
| Speculative generality: protocol, type, parameter, option or config with one conformer, call site or value | Count them | Inline or remove. Abstract on the third use, not the first |
| Delegation-only wrapper, or single-use helper whose name says no more than its body | Callers, and whether the name adds meaning | Inline |
| Nesting of three or more levels, or a long `else` chain | The metric and a read-through | Early return or `guard`; no new function |
| Boolean or optional pair encoding a state | Call sites that must reason about the combination | One enum, only if two or more sites need the combination |
| Defensive code for a state the types or earlier validation already rule out | The invariant, cited by file | Remove. Keep it at trust boundaries |
| Code that duplicates something the codebase already has | A search before the pass | Reuse the existing one. A single repeat is acceptable |
| Pass-through layer that makes no decision | Read the layer | Collapse it |

In Plan mode, apply the same signals to the design. For each element, ask: what in the request does
it serve, does existing code already cover it, would the simplest valid reading of the request need
it, and what would the plan lose without it? Write the smallest design that meets the request, list
what was left out and why, and record a budget (types, files, dependencies expected). After
implementation, compare the diff to that budget.

## Measure

Measure at two levels, because a pass can lower one and raise the other.

**Per function: how hard it is to read.** Cognitive complexity (SonarSource's rules) is the main
signal. It adds one for each branch or loop, more for each level of nesting, and counts a flat
`switch` once. It correlates with comprehension time, not clearly with correctness, and has no
validated threshold: use Sonar's default of 15 as a flag, not a target. Cyclomatic complexity rises
on flat `switch` statements and tracks size, so read it next to cognitive complexity and leave a flat
mapping alone.

| Signal | Reading |
|---|---|
| Cognitive complexity of each changed function | Flag above 15 or any rise from the base |
| Cyclomatic complexity | Flag above 10; ignore when cognitive is low (flat switch, table) |
| Nesting depth, function length, parameter count | Three or more levels, over 50 lines, more than 5 parameters |
| Types, protocols, files, dependencies, public API added by the diff | Each needs a caller and a reason beyond "might be useful" |
| Unused declarations, duplication | The project's analyzer where one exists; otherwise a search |

**Per change: how much a reviewer has to read.** `scripts/pr_size.py` in this skill scores a diff on
size and spread; git is its only dependency. Fewer changed lines and fewer files lower the score.
Excluded generated files do not count. Tests earn only a capped discount, because reviewers still
read them. The score does not measure complexity: a small change can still be hard to read. Run it on
the diff before the pass and again after.

Procedure for a diff, in a POSIX shell (under fish, run it with `bash -c`):

```sh
BASE=$(git merge-base HEAD origin/main)
git diff --numstat "$BASE"...HEAD                          # raw size
python3 scripts/pr_size.py --base "$BASE"                   # change-level score, working tree vs base
git diff --name-only --diff-filter=AM "$BASE"...HEAD > /tmp/changed.txt
mkdir -p /tmp/base && git archive "$BASE" | tar -x -C /tmp/base   # the base files, for per-function numbers
```

Then run the project's own complexity measure on the changed files in `/tmp/base` and in the working
tree, and compare function by function. Use what the project already has: the complexity rules of
its linter, or a standalone analyzer. `references/measuring.md` lists the common tools per language,
their defaults, and how they count. When no tool is available, count decision points and nesting by
hand for the changed functions with the rules above, and label the numbers as hand counts.

A metric selects a function to read; it is not the goal. A score under the threshold does not mean
the code is clear. Extracting helpers lowers the parent's score but adds indirection, so count the
whole change: a cut that lowers one function's score and raises the total number of functions and
types is not a simplification.

## Decision rules

1. Cognitive complexity above 15 in a function you touched: simplify it, or state why it must stay.
2. High cyclomatic with low cognitive (flat switch, mapping table): leave it.
3. Nesting of three or more: use an early return or `guard` before extracting anything.
4. A function over 50 lines: split it only into pieces that each have a clear name and make their
   caller easier to read.
5. A protocol, type or file with one conformer or one call site, added by this diff: inline it.
6. Parameters, flags or defaults nobody asked for: remove them.
7. New code that duplicates existing code: reuse the existing code.
8. A declaration the analyzer flags as unused and the diff added: delete it.
9. A Large or Oversized change-level band: check whether the branch's own additions can be cut. If
   the size comes from unrelated concerns bundled together, say so in the report and suggest a
   split; do not split inside the pass.
10. Touched functions at or under the thresholds and no metric worse than the base: stop. Continue
    only if a reader (the user or a reviewer) reports the code as confusing, not to improve a number.

## Keep list

A pass leaves these alone; each looks removable and is not:

- Validation and error handling at trust boundaries: input, network, disk, user.
- Comments that state why, warn about a consequence, or document a workaround with its ticket;
  safety comments about threads, memory and lifetimes.
- Public API and documented behaviour, persisted and wire formats, compatibility shims still in use.
- Tests and their assertions. A deleted test is never evidence that the behaviour it covered is dead.
- Accessibility, localization, and logging at boundaries; feature flags that are still in use.
- Whatever the project's own conventions require, from `AGENTS.md` or `project-conventions`.

## What a simplification must not do

- Change behaviour, even slightly. A cut that needs a behaviour change is a different change; report
  it as a suggestion.
- Compress code: nested ternaries, dense chains and one-liners that combine several operations
  lower line counts and raise cognitive load.
- Move complexity instead of removing it, for example by extracting helpers the reader then has to
  jump between.
- Spread beyond the scope: renames, reformatting and reordered imports in lines the task did not
  touch.
- Optimize a number. If the only reason for an edit is the score, revert it.
- Add what it removes elsewhere: new abstractions, dependencies, files or tests beyond what a cut
  needs.

## Report

The final message must make sense without the rest of the conversation. Give numbers and proof, not
opinions.

<example>
Simplified the sync retry change (diff mode, base 3f2a9c1).

Measured on the changed functions only (cognitive / cyclomatic):
| function | base | head | after the pass |
|---|---|---|---|
| `SyncQueue.retry` | n/a (new) | 19 / 8 | 6 / 4 |
| `SyncQueue.flush` | 9 / 5 | 11 / 6 | 9 / 5 |
Change level (`pr_size.py`, base to working tree): 11.3 large -> 8.6 medium.
Net: -64 production lines, -2 types, -1 file, 0 dependencies, 0 public API added.

Cuts, each with its proof:
1. Deleted `RetryPolicyProviding` and `DefaultRetryPolicy`: one conformer, one call site (search).
2. Inlined `makeBackoff()` into `retry`: single use, name added nothing.
3. Replaced the nested `if let`/`else` chain in `retry` with two `guard`s.

Kept: the `Task.isCancelled` check and its comment (cancellation contract), the error mapping at the
network boundary. Left for follow-up: `flush` holds a retry flag nothing sets (proof needs the owner).
Tests: 41 passed before and after. Unverified: nothing measured by hand.
</example>

Before sending, check the report against the contract: behaviour pinned and tests run, no function
worse than its base, the budget went down or each rise is explained, and each cut has proof.

## Boundaries

| Concern | Owner |
|---|---|
| Review comments, findings and severity on someone else's change | `code-review` (its simplification lens points here when a measured pass is wanted) |
| Restructuring legacy code in small steps, commit scoping, delivery flow | `engineering-practices` |
| Whether the code is fast; profiling and benchmarks | `performance-engineering` |
| Choosing a data structure or reasoning about algorithm cost | `algorithms` |
| Which work to do and in what order, task decomposition | `planner` |
| Repository conventions that override defaults here | `project-conventions` |
| Diagnosing a failure | `debugging` |

## References

- `references/measuring.md` — the common per-function complexity tools per language, their
  defaults, and how each counts the constructs of the usual languages. Read it to pick or interpret
  a tool.
- `scripts/pr_size.py` — the change-level score; `scripts/tests/` holds its tests.

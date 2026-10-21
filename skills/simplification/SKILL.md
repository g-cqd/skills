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
---

# Simplification

This skill owns one question: what can a reader stop holding in their head, in this change, without
the program doing anything different? It applies to a diff (the default), to named files, and to a
plan before any code exists. It makes the cuts and proves them; it does not look for bugs, enforce
style, speed code up, or redesign a module.

Agents that write code drift towards more than the task needs: an extra file, a configurable option,
a protocol with one conformer, a defensive branch for a state that cannot happen. Each addition is
cheap to write and costly to read for the life of the code. A pass that only removes, and measures
that it removed something, is the countermeasure.

## Contract

```
§SCOPE      the diff or the named files; the plan when no code exists. Nothing outside it changes.
§BEHAVIOUR  same observable behaviour. A test or a characterization pins it BEFORE the first edit.
§EVIDENCE   measure first; prove each cut (callers, history, a failing build or test) before making it.
§ORDER      delete ≻ inline ≻ flatten ≻ extract. Extract only a piece with a name and a caller that gains.
§BUDGET     production lines, types, files, parameters and dependencies go down. Any rise is justified.
§STOP       no net reduction, or only taste is left ⇒ report "no further change". Do not invent work.
§KEEP       the keep list below survives every pass.
```

## Choose the mode

| Mode | Input | What is measured and cut |
|---|---|---|
| Diff (default) | A branch, a PR, or uncommitted changes | The functions, types and files the diff touches, against the merge-base |
| File | Named files or a module the user points at | The same, against the current state; no baseline commit needed |
| Plan | A design, a ticket, a proposed approach, no code yet | What the design adds: files, types, options, dependencies, layers |

In Diff and File mode the project's own conventions win over this skill's defaults: detect them
first (load `project-conventions`).

## Procedure

1. **Fix the scope and pin behaviour.** Name the base (the merge-base for a diff) and list the changed
   functions. Check that tests cover them. Where none do, write the smallest characterization test
   first, or restrict the pass to cuts that are provably unreachable and say the rest is unprotected.
2. **Measure the baseline** at two levels: the changed functions (cognitive and cyclomatic complexity,
   nesting depth, length, parameter count) and the change as a whole (size, spread, and what the diff
   adds in types, files, dependencies and public API). See *Measure*. State plainly what could not be
   measured.
3. **List candidates** from the table below, strongest evidence first.
4. **Prove each cut** before making it. Zero callers by search or language server means dead. A
   conformer or call-site count shows speculative generality. `git log` and `git blame` show why odd
   code exists. A cut with no proof goes to the report as a suggestion, not into the diff.
5. **Apply one cut at a time** as the smallest edit that works, and run the tests after each batch.
6. **Re-measure.** Revert any cut that raises a function's cognitive complexity, or that adds a type,
   parameter or file, unless the report states why it pays for itself.
7. **Stop** by the rule in the contract, then write the report.

## Candidates, strongest evidence first

| Signal | Evidence to collect | Typical cut |
|---|---|---|
| Dead code: no callers, unreachable branch, flag that only ever has one value | Search and compiler or analyzer output | Delete |
| Speculative generality: protocol, type, parameter, option or config with one conformer, call site or value | Count them | Inline or remove. Abstract on the third use, not the first |
| Delegation-only wrapper, or single-use helper whose name says no more than its body | Callers, and whether the name adds meaning | Inline |
| Nesting of three or more levels, or a long `else` chain | The metric and a read-through | Early return or `guard`; no new function |
| Boolean or optional pair encoding a state | Call sites that must reason about the combination | One enum, only if two or more sites suffer |
| Defensive code for a state the types or earlier validation already rule out | The invariant, cited by file | Remove. Keep it at trust boundaries |
| Code that duplicates something the codebase already has | A search before the pass | Reuse the existing one. A single repeat is fine |
| Pass-through layer that makes no decision | Read the layer | Collapse it |

In Plan mode the same signals apply to the design, so the questions are: what in the request does this
element serve, does existing code already cover it, would the simplest valid reading of the request
need it, and what would the plan lose without it? Write the smallest design that meets the request,
list what was left out and why, and record a budget (types, files, dependencies expected). After
implementation, compare the diff to that budget.

## Measure

Two levels, because a pass can lower one and raise the other.

**Per function: what the reader must hold in their head.** Cognitive complexity (SonarSource's rules)
is the primary signal: it adds for each break in linear flow and for nesting, and ignores shorthand, so
a flat `switch` counts once. A meta-analysis of ten studies found it correlates with comprehension time
(pooled r about 0.54) and perceived difficulty, but not clearly with correctness, and it found no
validated threshold. Sonar's default of 15 is a reasonable flag, not a target. Cyclomatic complexity
inflates on flat `switch` statements and tracks size, so read it next to cognitive complexity and leave
a flat mapping alone.

| Signal | Reading |
|---|---|
| Cognitive complexity of each changed function | Flag above 15 or any rise from the base |
| Cyclomatic complexity | Flag above 10; ignore when cognitive is low (flat switch, table) |
| Nesting depth, function length, parameter count | Three or more levels, over 50 lines, more than 5 parameters |
| Types, protocols, files, dependencies, public API added by the diff | Each needs a caller and a reason beyond "might be useful" |
| Unused declarations, duplication | The project's analyzer where one exists; otherwise a search |

**Per change: what the reviewer must take in.** `scripts/pr_size.py` in this skill scores a diff on size
and spread, with git as its only dependency. Fewer changed lines and fewer files lower the score;
generated files you exclude do not count, and tests earn only a capped discount because reviewers still
read them. It does not measure complexity, so a small change can still be hard to read. Run it on the
diff before the pass and again after.

Procedure for a diff, in a POSIX shell (under fish, run it with `bash -c`):

```sh
BASE=$(git merge-base HEAD origin/main)
git diff --numstat "$BASE"...HEAD                          # raw size
python3 scripts/pr_size.py --base "$BASE"                   # change-level score, working tree vs base
git diff --name-only --diff-filter=AM "$BASE"...HEAD > /tmp/changed.txt
mkdir -p /tmp/base && git archive "$BASE" | tar -x -C /tmp/base   # the base files, for per-function numbers
```

Then run the project's own complexity measure on the changed files in `/tmp/base` and in the working
tree, and compare function by function. Use what the project already has: the complexity rules of its
linter, or a standalone analyzer. `references/measuring.md` lists the common choices per language, their
defaults and how they count. When no tool is available, count decision points and nesting by hand for
the changed functions using the rules above, label the numbers as hand counts, and say so.

Two cautions. A metric points at a function to read; it is not the goal, and a score under the
threshold does not mean the reader finds the code clear. Extracting helpers lowers the parent's score
while adding indirection, so count the whole change: a cut that lowers one function and raises the
total number of moving parts has not simplified anything.

## Decision rules

1. Cognitive complexity above 15 in a function you touched: simplify it, or say why it must stay.
2. High cyclomatic with low cognitive (flat switch, mapping table): leave it.
3. Nesting of three or more: early return or `guard` first, before extracting anything.
4. A function over 50 lines: split it only into pieces that each have a name and a caller that gains.
5. A protocol, type or file with one conformer or one call site, added by this diff: inline it.
6. Parameters, flags or defaults nobody asked for: remove them.
7. New code duplicating existing code: reuse the existing code.
8. A declaration the analyzer flags as unused and the diff added: delete it.
9. A Large or Oversized change-level band: check whether the branch's own additions can be cut. If the
   size comes from unrelated concerns bundled together, say so in the report and suggest splitting; do
   not split inside the pass.
10. Touched functions at or under the thresholds and no metric worse than the base: stop. Further work
    needs a reader who is confused, not a better number.

## Keep list

A pass leaves these alone, because each looks removable and is not:

- Validation and error handling at trust boundaries: input, network, disk, user.
- Comments that state why, warn about a consequence, or document a workaround with its ticket;
  safety comments about threads, memory and lifetimes.
- Public API and documented behaviour, persisted and wire formats, compatibility shims still in use.
- Tests and their assertions. Verbosity helps debugging, and a deleted test is never evidence that
  the behaviour it covered is dead.
- Accessibility, localization, and logging at boundaries; feature flags that are still in use.
- Whatever the project's own conventions require, from `AGENTS.md` or `project-conventions`.

## What a simplification must not do

- Change behaviour, even slightly. If a cut needs a behaviour change, it is a different change.
- Golf. Nested ternaries, dense chains and clever one-liners lower line counts and raise cognitive load.
- Move complexity instead of removing it, by extracting helpers that the reader must then jump between.
- Spread beyond the scope: renames, reformatting and reordered imports in lines the task did not touch.
- Optimize a number. If the only reason for an edit is the score, revert it.
- Add what it removes elsewhere: new abstractions, dependencies, files or tests beyond what a cut needs.

## Report

The final message stands on its own and carries evidence, not adjectives.

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

Rationale for the shape: the table makes the reduction checkable, each cut names its proof, and the
kept and deferred items show what the pass deliberately did not touch.

Before sending, check the report against the contract: behaviour pinned and tests run, no function
worse than its base, the budget went down or the rise is explained, and every cut has proof.

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

- `references/measuring.md` — the common per-function complexity tools per language, their defaults,
  and how each counts the constructs of the usual languages. Read it when you need to pick or interpret
  a tool.
- `scripts/pr_size.py` — the change-level score; `scripts/tests/` holds its tests.

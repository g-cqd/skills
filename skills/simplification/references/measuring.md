# Measuring complexity

How to get the per-function numbers the skill compares before and after a pass. Read it when you must
pick a tool, interpret its output, or count by hand.

## Contents

- [What each metric counts](#what-each-metric-counts)
- [Thresholds and where they come from](#thresholds-and-where-they-come-from)
- [Tools by language](#tools-by-language)
- [Counting by hand](#counting-by-hand)
- [Reading the numbers](#reading-the-numbers)
- [Change-level score](#change-level-score)

## What each metric counts

| Metric | Counts | Blind spot |
|---|---|---|
| Cyclomatic (McCabe) | One plus each decision point: `if`, loop, `case`, `catch`, `&&`, `||`, ternary | Every `case` costs the same, so a flat mapping scores high; ignores nesting; tracks function length |
| Cognitive (SonarSource) | +1 per break in linear flow (`if`, loop, `switch` once, `catch`, jump to label, a sequence of mixed boolean operators), plus the current nesting level for each nested structure; recursion +1 | Not validated against defects; the tools differ in details, so compare scores only within one tool |
| Nesting depth | Deepest level of nested control flow | Says nothing about how much each level holds |
| Length, parameter count | Lines of the body, declared parameters | Blunt; useful as a prompt to read |

Cognitive complexity does not count a flat `switch` per branch, ignores shorthand such as the null
coalescing operator or optional chaining, and charges nesting, which is why it matches reading effort
better than cyclomatic complexity for branchy code.

## Thresholds and where they come from

| Source | Cyclomatic | Cognitive | Other |
|---|---|---|---|
| SonarQube and SonarCloud default | 10 in the classic rule | 15 per function | |
| SwiftLint defaults | warning 10, error 20 | none built in | `function_body_length` 50 / 100, `function_parameter_count` 5 / 8 |
| ESLint | `complexity` rule, off by default, threshold 20 once enabled | none in core | `max-depth` 4, `max-params` 3, `max-lines-per-function` when enabled |
| detekt | `CyclomaticComplexMethod` 15 | `CognitiveComplexMethod` 15 | `LongMethod` 60, `LongParameterList` 6 |

Defaults vary by version and were checked against current documentation only for the common ones, so read the project's own configuration first: whatever the repository
enforces is the bar. The numbers in the skill (15, 10, 50 lines, 5 parameters, 3 levels) are flags that
prompt a closer read, not a goal. No published study validates a cutoff; the evidence is a moderate
correlation between cognitive complexity and comprehension time.

## Tools by language

Use the project's existing tool before adding another. Install nothing without the user's consent.

| Language | Where complexity usually comes from |
|---|---|
| Swift | SwiftLint `cyclomatic_complexity` (no cognitive rule built in, so hand-count or use a multi-language analyzer); Periphery for unused declarations |
| Kotlin, Java | detekt, SonarQube or the IDE inspections, PMD |
| JavaScript, TypeScript | ESLint `complexity` and the Sonar plugin's `cognitive-complexity` rule; `knip` or `ts-prune` for unused exports |
| Python | `radon cc` (cyclomatic), `flake8 --max-complexity`, `cognitive_complexity` package, `vulture` for dead code |
| Go | `gocyclo`, `gocognit`, `staticcheck` for unused code |
| Rust | `cargo clippy` `cognitive_complexity` lint (in the nursery group) |
| Any | A multi-language analyzer that reports cyclomatic and cognitive numbers per function; `jscpd` for duplication |

Run the tool on the base files and on the working-tree files and join the results by function name.
A renamed function appears as a delete and an add; match it by hand and say so.

## Counting by hand

When nothing is installed, count the changed functions and label the result as a hand count.

Cyclomatic: start at 1. Add 1 for each `if`, `else if`, `for`, `while`, `case`, `catch`, `guard`, `&&`,
`||`, `??` and ternary.

Cognitive:

1. +1 for each `if`, `else if`, `else`, `for`, `while`, `repeat`, `catch`, `switch` (once, whatever
   its case count), and each ternary.
2. +1 for each run of the same boolean operator; a change of operator inside a run adds +1.
3. +nesting level for each structure counted in step 1 that sits inside another one.
4. +1 for a `goto`, a labelled `break` or `continue`, and for recursion.
5. Add nothing for early returns, `guard`, optional chaining, or helper calls.

Example, a function with a loop containing an `if` and an `else`: loop +1, `if` +2 (nested once),
`else` +1, giving 4.

## Reading the numbers

- Compare a function with its own base, not with another function.
- A function new in the diff has no base; judge it against the thresholds and against the task.
- Extraction moves complexity: after extracting, sum the parent and the new helper. If the sum did not
  fall, the extraction added indirection.
- A flat `switch` over an enum, a lookup table and a generated file inflate cyclomatic complexity
  without making the reader work. Leave them.
- The score of a tool tells you where to read, never that the code is clear.

## Change-level score

`scripts/pr_size.py` scores a diff on size and spread with git as its only dependency:

```sh
python3 scripts/pr_size.py --base origin/main                  # working tree against the merge-base
python3 scripts/pr_size.py --base origin/main --head HEAD --json
python3 scripts/pr_size.py --exclude 'Generated/*' --exclude Package.resolved
python3 scripts/pr_size.py --test-pattern 'Specs/*'            # replaces the default test globs
```

Output is `cognitive load <score> (<band>)` with volume, scatter, line counts and test counts. Bands:
small under 5, medium under 10, large under 18, oversized from 18. The bands are heuristics. Untracked
files are not in a git diff, so run `git add -N <file>` first. To lower the score, remove lines the
branch itself added, or move unrelated edits into their own change; reformatting lines the task did not
touch raises it for nothing.

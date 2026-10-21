# Agent Harness

A curated, vendor-neutral set of **agent skills**, **specialized subagents**, and a single
**engineering standard** for AI coding harnesses — Claude Code, OpenAI Codex, and GitHub Copilot.
One source of truth, linked into whichever harnesses are on the machine.

## What's in here

| Piece | What it is |
|---|---|
| `AGENTS.md` | The engineering standard — how to plan, write, review, test, and ship. Portable; project-specific values are left as a `CONFIGURATION` block to fill in. `CLAUDE.md` is an alias. |
| `skills/` | 20 skills — language, framework, testing, security, performance, review, planning. |
| `agents/` | 14 specialized subagents, each with a cost-appropriate model tier, its own tools, and a turn budget where the job is small. Rendered for each harness. |
| `install.sh` | Links everything into each detected harness. |

**Skills** are capabilities a harness loads on demand when a task matches (a Keychain review pulls
in `secure-coding`, a SwiftUI bug pulls in `swiftui`). **Subagents** are separate, scoped workers
the main agent delegates to — each on the cheapest model that can do its job.

## Install

```bash
./install.sh --dry-run     # show what it would link, change nothing
./install.sh               # link into every detected harness
./install.sh --uninstall   # remove only the links it created
```

It builds a canonical root (`~/.agent-harness/`, override with `AGENT_HARNESS_ROOT`) holding the
standard, the skills, and the agents, then detects each harness (by home dir or CLI on `PATH`) and
symlinks its `skills/`, `agents/`, and instruction file — `CLAUDE.md` or `AGENTS.md`, whichever it
reads. One source of truth; re-run after `git pull`. Safe and idempotent: it replaces only its own
symlinks and the links named after this repository's skills, backs up any real file to `<name>.bak`,
and leaves every other skill in the root alone. `python3 -m unittest discover -s tests` checks that
against a temporary home.

## Structure

```
AGENTS.md            engineering standard   (CLAUDE.md -> AGENTS.md)
install.sh           the linker
skills/<skill>/      skills                 (SKILL.md + references/)
agents/
  src/<name>.md      neutral agent sources — edit these
  tiers.json         tier -> per-harness model and effort (the cost dial)
  build.py           renders src/ -> per-harness formats; --check verifies them
  claude/hooks/      the read-only Bash guard, hand-written
  claude/  codex/  copilot/    generated, one format each
  tests/             tests for build.py and the guard
docs/AUTHORING.md    how to add a skill or an agent
```

## Subagents and cost

The roster follows **cheap fan-out, expensive judgment**: mechanical, high-volume work goes to a
cheap model; the top model is spent only where a wrong answer is expensive to catch.

| Agent | Tier | Job |
|---|---|---|
| `scout` | micro | Read-only exploration and mapping — recon before work |
| `test-runner` | micro | Run a suite, a linter, or a benchmark; report counts and each failure |
| `patcher` | micro | Apply one small edit already decided, and build it |
| `committer` | micro | Commit a finished change in the repository's style; never push |
| `docs-writer` | economy | PR text, tickets, ADRs, release notes |
| `researcher` | standard | Facts from documentation, specifications, and source, each cited |
| `implementer` | standard | Turn a specified change into a small, verified diff |
| `test-engineer` | standard | TDD, regression tests, suite migration |
| `debugger` | reasoning | Root-cause a crash, a failing test, or a hang |
| `perf-engineer` | reasoning | Baseline, profile, change, re-measure |
| `verifier` | reasoning | Reproduce a claim before anyone acts on it |
| `code-reviewer` | reasoning | Correctness / architecture review, adversarial |
| `security-auditor` | frontier | Trust-boundary, memory-safety, iOS attack surface |
| `orchestrator` | frontier | Decompose, route to the cheapest capable specialist, synthesize |

Five tiers map to each harness's models and effort in **`agents/tiers.json`** — the single place
cost is tuned:

```
micro      opus low     / gpt-6-luna low     one small mechanical job with a clear stop
economy    opus low     / gpt-6-sol low      mechanical, high-volume, cheap to retry
standard   opus medium  / gpt-6-sol medium   clear-scope reasoning, tests catch mistakes
reasoning  opus high    / gpt-6-astra high   ambiguous, high-risk, expensive to fix
frontier   fable high   / gpt-6-astra xhigh  the costliest miss, the longest runs
```

Re-audit that map every few months — the best-value model in each class drifts, and a stale
mapping quietly eats the savings. Change the ids, run `python3 agents/build.py`, done.
`agents/README.md` has the per-agent tools and budgets, and each harness's model names.

## Cross-harness compatibility

Each harness reads a different format, so one neutral source renders three variants:

| Harness | Skills | Agents | Instruction file |
|---|---|---|---|
| Claude Code | `~/.claude/skills/` | `~/.claude/agents/<name>.md` | `CLAUDE.md` |
| Codex | `~/.codex/skills/` | `~/.codex/agents/<name>.toml` | `AGENTS.md` |
| Copilot | `~/.copilot/agents/<name>.agent.md` | `~/.copilot/agents/<name>.agent.md` | `AGENTS.md` |

`agents/build.py` maps the neutral tier and tool capabilities to each harness's vocabulary — model
alias, slug, or display name; tool names or aliases; turn limits and hooks where the harness has
them. Read-only agents are enforced on Claude Code, by tools and a Bash guard, and on Copilot, by
tools; Codex runs every agent in its parent's sandbox, so there the rule is the prompt's.

## Portability

Every skill is reusable as-is: no project identifiers, no ticket keys, no in-house macros, no team
decision presented as a universal rule. Where a value is a project's to choose, a skill states the
*procedure* ("detect the project's convention", "use the project's mock mechanism") rather than
baking in an answer — `project-conventions` is the skill that reads those answers out of the
repository you are actually in, and the `CONFIGURATION` block in `AGENTS.md` is where a project
records them.

## Extending

Add a skill: create `skills/<name>/SKILL.md` with frontmatter
(`name`, `description`) and an actionable body; put long-tail material in `references/`.
Add an agent: drop `agents/src/<name>.md` with `name`, `tier`, `tools`, `description`, and the
prompt, then run `python3 agents/build.py`. `agents/build.py`'s header lists the optional keys
(`max_turns`, `skills`, `spawns`, `effort`, …). See `docs/AUTHORING.md`.

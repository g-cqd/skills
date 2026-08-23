# Agent Harness

A curated, vendor-neutral set of **agent skills**, **specialized subagents**, and a single
**engineering standard** for AI coding harnesses — Claude Code, OpenAI Codex, and GitHub Copilot.
One source of truth, linked into whichever harnesses are on the machine.

## What's in here

| Piece | What it is |
|---|---|
| `AGENTS.md` | The engineering standard — how to plan, write, review, test, and ship. Portable; project-specific values are left as a `CONFIGURATION` block to fill in. `CLAUDE.md` is an alias. |
| `skills/` | 19 skills — language, framework, testing, security, performance, review, planning. |
| `agents/` | 7 specialized subagents, each with a cost-appropriate model tier. Rendered for each harness. |
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
symlinks and backs up any real file to `<name>.bak`.

## Structure

```
AGENTS.md            engineering standard   (CLAUDE.md -> AGENTS.md)
install.sh           the linker
skills/<skill>/      skills                 (SKILL.md + references/)
agents/
  src/<name>.md      neutral agent sources — edit these
  tiers.json         tier -> per-vendor model (the cost dial)
  build.py           renders src/ -> per-harness formats
  claude/  codex/  copilot/    generated, one format each
docs/AUTHORING.md    how to add a skill or an agent
```

## Subagents and cost

The roster follows **cheap fan-out, expensive judgment**: mechanical, high-volume work goes to a
cheap model; the top model is spent only where a wrong answer is expensive to catch.

| Agent | Tier | Job |
|---|---|---|
| `orchestrator` | reasoning | Decompose, route to the cheapest capable specialist, synthesize |
| `scout` | economy | Read-only exploration and mapping — recon before work |
| `implementer` | standard | Turn a specified change into a small, verified diff |
| `test-engineer` | standard | TDD, regression tests, suite migration |
| `code-reviewer` | reasoning | Correctness / architecture review, adversarial |
| `security-auditor` | reasoning | Trust-boundary, memory-safety, iOS attack surface |
| `docs-writer` | economy | PR text, tickets, ADRs, release notes |

Three tiers map to each vendor's models in **`agents/tiers.json`** — the single place cost is
tuned:

```
economy    haiku   / gpt-5.6-luna    mechanical, high-volume, cheap to retry
standard   sonnet  / gpt-5.6-terra   clear-scope reasoning, tests catch mistakes
reasoning  opus    / gpt-5.6-sol     ambiguous, high-risk, expensive to fix
```

Re-audit that map every few months — the best-value model in each class drifts, and a stale
mapping quietly eats the savings. Change the ids, run `python3 agents/build.py`, done.

## Cross-harness compatibility

Each harness reads a different format, so one neutral source renders three variants:

| Harness | Skills | Agents | Instruction file |
|---|---|---|---|
| Claude Code | `~/.claude/skills/` | `~/.claude/agents/<name>.md` | `CLAUDE.md` |
| Codex | `~/.codex/skills/` | `~/.codex/agents/<name>.toml` | `AGENTS.md` |
| Copilot | `~/.copilot/agents/<name>.agent.md` | `~/.copilot/agents/<name>.agent.md` | `AGENTS.md` |

`agents/build.py` maps the neutral tier and tool capability to each harness's vocabulary — model
alias vs id, tools allowlist vs `sandbox_mode`. Read-only agents cannot mutate the tree on any
harness.

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
prompt, then run `python3 agents/build.py`. See `docs/AUTHORING.md`.

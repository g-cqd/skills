# Agent Harness

A vendor-neutral set of **agent skills**, **specialized subagents**, and one **engineering
standard** for AI coding harnesses: Claude Code, OpenAI Codex, and GitHub Copilot. One source,
linked into each harness installed on the machine.

## What's in here

| Piece | What it is |
|---|---|
| `AGENTS.md` | The engineering standard — how to plan, write, review, test, and ship. Portable; project-specific values are left as a `CONFIGURATION` block to fill in. `CLAUDE.md` is an alias. |
| `skills/` | 21 skills — language, framework, testing, security, performance, review, planning, simplification, and multi-agent coordination (`agora`). |
| `agents/` | 14 specialized subagents, each with a cost-appropriate model tier, its own tools, and a turn budget where the job is small. Rendered for each harness. |
| `install.sh` | Links everything into each detected harness. |

A harness loads a **skill** when a task matches it (a Keychain review loads `secure-coding`, a
SwiftUI bug loads `swiftui`). A **subagent** is a separate, scoped worker that the main agent
delegates to, each on the cheapest model that can do its job.

## Install

```bash
./install.sh --dry-run     # show what it would link, change nothing
./install.sh               # link into every detected harness
./install.sh --uninstall   # remove only the links it created
```

`install.sh` builds a canonical root (`~/.agent-harness/`; override with `AGENT_HARNESS_ROOT`)
that holds the standard, the skills, and the agents. It then detects each harness (by its home
directory or its CLI on `PATH`) and symlinks the harness's `skills/`, `agents/`, and instruction
file (`CLAUDE.md` or `AGENTS.md`, whichever the harness reads). Re-run it after `git pull`.

Running it twice gives the same result. It replaces only its own symlinks and the links named
after this repository's skills, backs up a real file to `<name>.bak` before replacing it, and
leaves other skills in the root unchanged. `python3 -m unittest discover -s tests` tests this
against a temporary home directory.

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
cheap model; the top model is used only where a wrong answer is expensive to detect.

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

**`agents/tiers.json`** maps the five tiers to each harness's model and effort. It is the only
place cost is tuned (Claude Code / Codex shown):

```
micro      sonnet low     / gpt-6-luna low     one small mechanical job with a clear stop
economy    sonnet medium  / gpt-6-sol low      mechanical, high-volume, cheap to retry
standard   sonnet high    / gpt-6-sol medium   clear-scope reasoning, tests catch mistakes
reasoning  opus medium    / gpt-6-astra high   ambiguous, high-risk, expensive to fix
frontier   fable high     / gpt-6-astra xhigh  the costliest miss, the longest runs
```

Re-audit the map every three months: the best-value model in each class changes. To change it,
edit the ids and run `python3 agents/build.py`. `agents/README.md` lists each agent's tools and
budget, and each harness's model names.

## Cross-harness compatibility

Each harness reads a different format, so one neutral source renders three variants:

| Harness | Skills | Agents | Instruction file |
|---|---|---|---|
| Claude Code | `~/.claude/skills/` | `~/.claude/agents/<name>.md` | `CLAUDE.md` |
| Codex | `~/.codex/skills/` | `~/.codex/agents/<name>.toml` | `AGENTS.md` |
| Copilot | `~/.copilot/skills/` | `~/.copilot/agents/<name>.agent.md` | `AGENTS.md` |

`agents/build.py` maps the neutral tier and capabilities to each harness's terms: model alias,
slug, or display name; tool names or aliases; turn limits and hooks where the harness has them.
Claude Code enforces read-only agents with the tool list and a Bash guard, and Copilot with the
tool list. Codex runs each agent in its parent's sandbox, so on Codex only the prompt keeps an
agent read-only.

## Portability

Each skill works in any project without edits: no project identifiers, ticket keys, in-house
macros, or team decisions presented as universal rules. Where a value is the project's choice, the
skill states the *procedure* ("detect the project's convention", "use the project's mock
mechanism"), not the value. `project-conventions` reads the value from the current repository, and
a project records it in the `CONFIGURATION` block of `AGENTS.md`.

## Extending

To add a skill, create `skills/<name>/SKILL.md` with frontmatter (`name`, `description`) and the
body; put long reference material in `references/`. To add an agent, create
`agents/src/<name>.md` with `name`, `tier`, `tools`, `description`, and the prompt, then run
`python3 agents/build.py`. The header of `agents/build.py` lists the optional keys (`max_turns`,
`skills`, `spawns`, `effort`, …). The full rules are in `docs/AUTHORING.md`.

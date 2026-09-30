# Agents

A roster of fourteen specialized subagents, each with one job, the tools that job needs, a
**cost-appropriate model tier**, and a turn budget where the job is small. Written once as neutral
source, rendered per harness.

## Why specialized agents with tiered models

The production pattern is **cheap fan-out, expensive judgment**: route mechanical, high-volume,
low-risk work to a cheap model, and spend the top model only where a wrong answer is expensive to
detect — architecture, adversarial review, security. A capable orchestrator plans and delegates;
cheaper specialists execute in their own context and return only a clean summary. This both cuts
token cost (reported 5–10× on delegated work) and keeps the expensive model's context clean so it
reasons better.

Three rules the roster follows:

1. **One clear job per agent**, a tool surface that matches it, and instructions that keep it from
   drifting into adjacent work.
2. **Default to the cheap tier**; escalate only when the task is ambiguous, cross-cutting,
   high-risk, or long-horizon.
3. **Small jobs get small agents.** Running a suite, committing, or applying a fix already shown
   goes to a micro agent with a turn budget, so a larger agent never spends its context on a log.

## The roster

| Agent | Tier | Capabilities | Budget | Job | Skills loaded at start |
|---|---|---|---|---|---|
| `scout` | micro | read, search, read-only shell, lsp | 40 turns | Locate, map, trace, count — reconnaissance before work | — |
| `test-runner` | micro | read, search, shell | 30 turns, background | Run a suite, linter, or benchmark; report counts and each failure's first error | — |
| `patcher` | micro | read, search, shell, edit, lsp | 25 turns | Apply one small edit already decided, and build it | — |
| `committer` | micro | read, search, shell | 15 turns | Commit a finished change in the repository's style; never push | `project-conventions` |
| `docs-writer` | economy | read, search, read-only shell, edit | — | PR text, tickets, ADRs, release notes | `work-docs` |
| `researcher` | standard | read, search, read-only shell, web, apple-docs | 60 turns | Facts from documentation, specifications, and source, each cited | — |
| `implementer` | standard | read, search, shell, edit, lsp, web, todo, agents, apple-docs | — | Turn a specified change into a small, verified diff | `engineering-practices` |
| `test-engineer` | standard | read, search, shell, edit, lsp, todo, agents, apple-docs | — | TDD, regression tests, suite migration; judge meaningfulness | `testing` |
| `debugger` | reasoning | read, search, shell, edit, lsp, web, todo, agents, apple-docs | — | Root-cause a crash, failing test, or hang; fix it with a regression test when asked | `debugging` |
| `perf-engineer` | reasoning | read, search, shell, edit, lsp, web, todo, agents | — | Baseline, profile, change, re-measure; before and after with units | `performance-engineering` |
| `verifier` | reasoning | read, search, shell, lsp | 60 turns | Reproduce a claim; CONFIRMED, REFUTED, or INCONCLUSIVE with evidence | — |
| `code-reviewer` | reasoning | read, search, read-only shell, lsp, web, apple-docs | — | Correctness, architecture, simplification review, adversarial | `code-review` |
| `security-auditor` | frontier | read, search, read-only shell, lsp, web, apple-docs | — | Trust boundaries, memory safety, the iOS attack surface | `secure-coding`, `memory-safety` |
| `orchestrator` | frontier | everything but edit | — | Decompose, route to the cheapest capable specialist, synthesize | `planner` |

Every agent also gets `skills`, so it can load any other skill it needs. The agents that can
delegate have an allowlist: `implementer` may start `scout`, `test-runner`, and `patcher`;
`test-engineer`, `debugger`, and `perf-engineer` may start `scout` and `test-runner`; the
orchestrator may start any of them.

## Read-only, per harness

Five agents never change anything: `scout`, `researcher`, `code-reviewer`, and `security-auditor`,
and `verifier`, whose scratch files go under `/tmp`. `docs-writer` edits documents but only reads
through its shell. How much each harness can enforce that differs:

- **Claude Code** enforces it. The tool list leaves out Edit and Write where the agent does not
  edit, and every agent with a read-only shell runs `claude/hooks/readonly-bash.py` before each
  command: an allowlist of commands that only read (`git log`, `git diff`, `rg`, `find`,
  `sed -n`, …) that refuses the rest with exit 2, and fails closed on anything it cannot parse. It
  is a guardrail against mistakes, not a sandbox against a hostile repository. `verifier` has a
  full shell, to build and run tests, so its rule is its prompt's.
- **Copilot** enforces it by the tool list only. It has no per-agent hook, so an agent whose shell
  is read-only gets no shell at all there.
- **Codex** cannot enforce it per agent. Since Codex 0.149, an agent file's `sandbox_mode`, MCP,
  and approval settings are ignored and the agent runs in its parent's sandbox. The generated file
  still sets `sandbox_mode` for older versions and opens the prompt with the read-only rule; start
  the parent with `codex -s read-only` when enforcement matters.

## The cost dial — `tiers.json`

The tier→model mapping is the single place cost is tuned:

| Tier | Claude Code | Codex | Copilot | For |
|---|---|---|---|---|
| micro | `sonnet`, low | `gpt-6-luna`, low | Claude Sonnet 5, low | one small mechanical job with a clear stop |
| economy | `sonnet`, medium | `gpt-6-sol`, low | Claude Sonnet 5, medium | mechanical, high-volume, cheap to retry |
| standard | `sonnet`, high | `gpt-6-sol`, medium | Claude Sonnet 5, high | clear-scope reasoning; tests catch mistakes |
| reasoning | `opus`, medium | `gpt-6-astra`, high | Claude Opus 5.5, medium | ambiguous, high-risk, expensive to fix |
| frontier | `fable`, high | `gpt-6-astra`, xhigh | Claude Fable 5.1, high | the costliest miss, the longest runs |

An agent's own `effort` replaces its tier's on every harness. **Re-audit this map every few
months.** The best-value model in each class drifts, and a stale mapping quietly eats the savings.
Change `tiers.json`, re-run `build.py`, done — no agent file is touched.

Model names follow each harness's documentation. Claude Code takes an alias (`sonnet`, `opus`, `fable`) or a
full id (`claude-opus-5-5`, `claude-fable-5-1`). Codex takes a slug; `codex debug models` lists the
ones the installed client knows. Copilot's documentation for VS Code gives display names
(`Claude Opus 5.5`) and no other form, and the Copilot CLI has accepted them since 1.0.24. Claude
Opus 5.5 and Claude Fable 5.1 need Copilot Pro+ or higher, and in an organization, Fable 5.1's
policy stays off until an admin enables it.

## Cross-harness compatibility

Each harness reads a different format and tunes different fields, so one neutral source renders
three variants:

| | Claude Code | Copilot | Codex |
|---|---|---|---|
| Location | `~/.claude/agents/<name>.md` | `~/.copilot/agents/<name>.agent.md` | `~/.codex/agents/<name>.toml` |
| Model and effort | `model`, `effort` | `model`, `reasoningEffort` (CLI) | `model`, `model_reasoning_effort` |
| Tools | `tools` allowlist, or `disallowedTools` | `tools` aliases | the parent's |
| Delegation | `Agent(name, …)` in `tools` | `agent` alias | `spawn_agent`, session-wide |
| Limits | `maxTurns`, hooks | none per agent | none per agent |
| Skills | `skills` loaded at start, and the Skill tool | the `skill` tool | discovered automatically |

The capability map in `build.py`:

| Capability | Claude Code | Copilot |
|---|---|---|
| `read` | Read | `read` |
| `search` | Grep, Glob | `search` |
| `lsp` | LSP (needs a code-intelligence plugin) | — |
| `shell` | Bash | `execute` |
| `shell-readonly` | Bash, with the read-only guard | — |
| `edit` | Edit, Write | `edit` |
| `web` | WebFetch, WebSearch | `web` |
| `todo` | TodoWrite | `todo` |
| `agents` | `Agent(<spawns>)` | `agent` |
| `skills` | Skill | `skill` |
| `apple-docs` | `mcp__apple-docs` | `apple-docs/*` |

`tools: all` with `deny:` gives every tool the session has except the denied ones; the orchestrator
uses it to keep messaging and MCP tools while losing Edit and Write. On macOS, Claude Code leaves
Grep and Glob out of a session that has Bash and searches through Bash instead, so an agent with a
shell searches with `grep` and `find`, which the guard allows.

The turn budget is Claude's `maxTurns` (the agent stops and returns partial work it can be resumed
from), and a Budget section in the prompt on every harness, since Copilot and Codex have no
per-agent limit.

## Layout

```
agents/
  src/*.md                neutral sources — EDIT THESE
  tiers.json              tier -> per-harness model and effort (the cost dial)
  build.py                render src/ -> claude/ copilot/ codex/; --check verifies they are current
  claude/hooks/           hand-written: the read-only Bash guard
  claude/*.md             generated — do not edit
  copilot/*.agent.md      generated — do not edit
  codex/*.toml            generated — do not edit
  tests/                  tests for build.py and the guard
```

## Workflow

```bash
# edit a source or the tier map, then:
python3 agents/build.py                              # regenerate all three variants
python3 agents/build.py --check                      # exit 1 if a generated file is stale
python3 -m unittest discover -s agents/tests         # build and guard tests

# install.sh links the format-matching subdir into each detected harness:
./install.sh                                         # ~/.claude/agents -> agents/claude, etc.
```

Add an agent: drop `src/<name>.md` with `name`, `tier`, `tools` (capabilities, comma-separated), a
delegation-focused `description`, and the prompt body; add `max_turns`, `skills`, `spawns`,
`effort`, `color`, or `background` as the job needs; run `build.py`. The header of `build.py`
documents every key. Keep each agent to one job: a roster the orchestrator cannot route cleanly
costs more than it saves.

## Sources

- Claude Code subagents: https://code.claude.com/docs/en/sub-agents
- Claude Code tools: https://code.claude.com/docs/en/tools-reference
- Claude models: https://platform.claude.com/docs/en/about-claude/models/overview
- Copilot custom agents: https://docs.github.com/en/copilot/reference/custom-agents-configuration
- Copilot CLI: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference
- Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents
- Codex configuration: https://learn.chatgpt.com/docs/config-file/config-reference

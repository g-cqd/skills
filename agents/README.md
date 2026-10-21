# Agents

Fourteen subagents. Each has one job, the tools that job needs, a model tier priced for the job,
and a turn budget when the job is small. Each is written once as a neutral source and rendered
for each harness.

## Why specialized agents with tiered models

The roster follows **cheap fan-out, expensive judgment**. Mechanical, high-volume, low-risk work
goes to a cheap model. The top model is used only where a wrong answer is expensive to detect:
architecture, adversarial review, security. The orchestrator plans and delegates; specialists
work in their own context and return only a summary. This cuts token cost (reported 5–10× on
delegated work) and keeps the expensive model's context free of logs and search output.

The roster follows three rules:

1. **One job per agent**, with tools that match the job and instructions that keep the agent out
   of adjacent work.
2. **Default to the cheap tier.** Use a higher tier only when the task is ambiguous,
   cross-cutting, high-risk, or long-horizon.
3. **Small jobs go to micro agents.** Running a suite, committing, or applying a fix already shown
   goes to a micro agent with a turn budget, so a larger agent does not spend its context on a
   log.

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

Every agent also gets the `skills` capability, so it can load any other skill. The agents that
delegate have an allowlist: `implementer` may start `scout`, `test-runner`, and `patcher`;
`test-engineer`, `debugger`, and `perf-engineer` may start `scout` and `test-runner`; the
orchestrator may start any agent.

## Read-only, per harness

Five agents do not change project files: `scout`, `researcher`, `code-reviewer`,
`security-auditor`, and `verifier`, which writes scratch files only under `/tmp`. `docs-writer`
edits documents, but its shell is read-only. Enforcement differs per harness:

- **Claude Code** enforces it. The tool list leaves out Edit and Write for an agent that does not
  edit. Each agent with a read-only shell runs `claude/hooks/readonly-bash.py` before each
  command. The hook allows only commands that read (`git log`, `git diff`, `rg`, `find`,
  `sed -n`, …), refuses the rest with exit 2, and refuses any command it cannot parse. It guards
  against mistakes; it is not a sandbox against a hostile repository. `verifier` has a full shell,
  to build and run tests, so only its prompt keeps it read-only.
- **Copilot** enforces it by the tool list only. It has no per-agent hook, so an agent with a
  read-only shell gets no shell on Copilot.
- **Codex** cannot enforce it per agent. Since Codex 0.149, Codex ignores an agent file's
  `sandbox_mode`, MCP, and approval settings, and runs the agent in its parent's sandbox. The
  generated file still sets `sandbox_mode` for older versions and opens the prompt with the
  read-only rule. When enforcement matters, start the parent with `codex -s read-only`.

## The cost dial — `tiers.json`

`tiers.json` maps each tier to a model and effort per harness. It is the only place cost is
tuned:

| Tier | Claude Code | Codex | Copilot | For |
|---|---|---|---|---|
| micro | `sonnet`, low | `gpt-6-luna`, low | Claude Sonnet 5, low | one small mechanical job with a clear stop |
| economy | `sonnet`, medium | `gpt-6-sol`, low | Claude Sonnet 5, medium | mechanical, high-volume, cheap to retry |
| standard | `sonnet`, high | `gpt-6-sol`, medium | Claude Sonnet 5, high | clear-scope reasoning; tests catch mistakes |
| reasoning | `opus`, medium | `gpt-6-astra`, high | Claude Opus 5.5, medium | ambiguous, high-risk, expensive to fix |
| frontier | `fable`, high | `gpt-6-astra`, xhigh | Claude Fable 5.1, high | the costliest miss, the longest runs |

An agent's own `effort` replaces its tier's effort on every harness. **Re-audit this map every
three months:** the best-value model in each class changes, and a stale map costs more for the same
work. To change it, edit `tiers.json` and re-run `build.py`; no agent source changes.

Model names follow each harness's documentation. Claude Code takes an alias (`sonnet`, `opus`,
`fable`) or a full id (`claude-opus-5-5`, `claude-fable-5-1`). Codex takes a slug;
`codex debug models` lists the slugs the installed client knows. Copilot's documentation for VS
Code gives display names (`Claude Opus 5.5`) and no other form; the Copilot CLI accepts them from
version 1.0.24. Claude Opus 5.5 and Claude Fable 5.1 need Copilot Pro+ or higher. In an organization, the
Fable 5.1 policy is off until an admin enables it.

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

`tools: all` with `deny:` gives every tool the session has except the denied ones. The
orchestrator uses it to keep messaging and MCP tools without Edit and Write. On macOS, Claude Code
leaves Grep and Glob out of a session that has Bash, so an agent with a shell searches with `grep`
and `find`, which the guard allows.

`max_turns` renders as Claude's `maxTurns` (the agent stops and returns partial work that can be
resumed) and as a Budget section in the prompt on every harness, because Copilot and Codex have
no per-agent limit.

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

To add an agent, create `src/<name>.md` with `name`, `tier`, `tools` (capabilities,
comma-separated), a `description` that says when to delegate to it, and the prompt body. Add
`max_turns`, `skills`, `spawns`, `effort`, `color`, or `background` as the job needs, then run
`build.py`. The header of `build.py` documents each key. Rules for writing the prompt are in
`docs/AUTHORING.md`, Agents.

## Sources

- Claude Code subagents: https://code.claude.com/docs/en/sub-agents
- Claude Code tools: https://code.claude.com/docs/en/tools-reference
- Claude models: https://platform.claude.com/docs/en/about-claude/models/overview
- Copilot custom agents: https://docs.github.com/en/copilot/reference/custom-agents-configuration
- Copilot CLI: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference
- Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents
- Codex configuration: https://learn.chatgpt.com/docs/config-file/config-reference

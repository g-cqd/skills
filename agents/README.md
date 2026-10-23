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
| `security-auditor` | reasoning | read, search, read-only shell, lsp, web, apple-docs | — | Trust boundaries, memory safety, the iOS attack surface | `secure-coding`, `memory-safety` |
| `orchestrator` | reasoning | everything but edit | — | Decompose, route to the cheapest capable specialist, synthesize | `planner` |

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
- **Copilot** and **OpenCode** enforce it by the tool and permission list. Neither has a per-agent
  hook, so an agent with a read-only shell gets no shell (`execute` / `bash`) there.
- **Mistral Vibe** blocks edits at the tool layer: `enabled_tools` omits `edit` and `write_file`,
  and the Vibe runtime sets `file_system.write_file` and `file_system.search_replace` to `"deny"`.
  The build also sets `safety = "safe"` on a read-only subagent and prepends a read-only shell rule
  to `instructions`.
- **Google Antigravity (`agy`)** blocks edits at the tool layer: `tools` omits
  `replace_file_content`, `multi_replace_file_content`, and `write_to_file`. When the agent has
  `run_command`, the build prepends the read-only shell rule to the agent instructions.
- **Codex** cannot enforce it per agent. Since Codex 0.149, Codex ignores an agent file's
  `sandbox_mode`, MCP, and approval settings, and runs the agent in its parent's sandbox. The
  generated file still sets `sandbox_mode` for older versions and opens the prompt with the
  read-only rule. When enforcement matters, start the parent with `codex -s read-only`.

## The cost dial — `tiers.json`

`tiers.json` maps each tier to an ordered `models` fallback list and an effort per harness. The
list lets a harness fall back when a preferred model is unavailable on a plan or provider. It is
the only place cost is tuned:

| Tier | Claude Code (`models`) | Codex (`models`) | Copilot (`model: [...]`) | Vibe / OpenCode / AGY | For |
|---|---|---|---|---|---|
| micro | `sonnet` → `claude-sonnet-5-5` → `claude-sonnet-5` → `claude-sonnet-4-6` → `haiku` → `claude-haiku-4-5` (low) | `gpt-6-luna` → `gpt-5.6-luna` → `gpt-6.1-sol` → `gpt-6-sol` → `gpt-5.5` (low) | `Claude Sonnet 5` → `GPT-6 Luna` → `Claude Sonnet 4.6` → `Claude Haiku 4.5` → `GPT-5.4-mini` (low) | `devstral-small-latest` / `anthropic/claude-sonnet-5` / `flash_lite` (low) | one small mechanical job with a clear stop |
| economy | `sonnet` → `claude-sonnet-5-5` → `claude-sonnet-5` → `claude-sonnet-4-6` → `haiku` (medium) | `gpt-6-sol` → `gpt-6.1-sol` → `gpt-5.6-sol` → `gpt-6-luna` → `gpt-5.5` (low) | `Claude Sonnet 5` → `GPT-6.1 Sol` → `GPT-6 Sol` → `Claude Sonnet 4.6` → `Claude Haiku 4.5` (medium) | `devstral-small-latest` / `anthropic/claude-sonnet-5` / `flash` (medium) | mechanical, high-volume, cheap to retry |
| standard | `sonnet` → `claude-sonnet-5-5` → `claude-sonnet-5` → `opus` → `claude-opus-5-5` → `claude-sonnet-4-6` (high) | `gpt-6-sol` → `gpt-6.1-sol` → `gpt-5.6-sol` → `gpt-5.5` (medium) | `Claude Sonnet 5` → `GPT-6.1 Sol` → `GPT-6 Sol` → `Claude Sonnet 4.6` → `GPT-5.5` (high) | `devstral-medium-latest` / `anthropic/claude-sonnet-5` / `inherit` (high) | clear-scope reasoning; tests catch mistakes |
| reasoning | `opus` → `claude-opus-5-5` → `claude-opus-4-8` → `claude-opus-4-7` → `claude-opus-4-6` → `sonnet` (medium) | `gpt-6-astra` → `gpt-6.1-sol` → `gpt-6-sol` → `gpt-5.6-sol` → `gpt-5.5` (high) | `Claude Opus 5.5` → `GPT-6 Astra` → `Claude Opus 4.7` → `Claude Opus 4.6` → `Claude Sonnet 5` → `GPT-5.5` (medium) | `devstral-latest` / `anthropic/claude-opus-5-5` / `pro` (high) | ambiguous, high-risk, expensive to fix |
| frontier | `fable` → `claude-fable-5-1` → `opus` → `claude-opus-5-5` → `claude-opus-4-8` → `claude-opus-4-7` (high) | `gpt-6-astra` → `gpt-6.1-sol` → `gpt-6-sol` → `gpt-5.5` (xhigh) | `Claude Fable 5.1` → `Claude Opus 5.5` → `GPT-6 Astra` → `Claude Opus 4.7` → `Claude Opus 4.6` (high) | `devstral-latest` / `anthropic/claude-fable-5-1` / `pro` (xhigh) | on demand only: no agent defaults to it |

An agent's own `effort` replaces its tier's effort on every harness. **Re-audit this map every
three months:** the best-value model in each class changes, and a stale map costs more for the same
work. To change it, edit `tiers.json` and re-run `build.py`; no agent source changes.

Model names follow each harness's schema:
- **Copilot** natively accepts an ordered YAML array (`model: ["Model 1", "Model 2", ...]`) and uses
  the first available model. The names are display names (`Claude Opus 5.5`); the Copilot CLI
  accepts them from version 1.0.24. Claude Opus 5.5 and Claude Fable 5.1 need Copilot Pro+ or
  higher, and in an organization the Fable 5.1 policy is off until an admin enables it.
- **Claude Code** (`model: <primary>` + `# fallback_models: ...`) takes an alias (`sonnet`, `opus`,
  `fable`, `haiku`) or a full id (`claude-opus-5-5`, `claude-fable-5-1`).
- **Codex** (`model = "<primary>"` + `# fallback_models = [...]`) takes a slug; `codex debug models`
  lists the ones the installed client knows.
- **Mistral Vibe (`vibe`)**, **Google Antigravity (`agy`)**, and **OpenCode** subagents inherit the
  session's active model by default and record their tier's ordered `tier_models` fallback list in
  the generated header.

## Cross-harness compatibility

Each harness reads a different format and tunes different fields, so one neutral source renders
six variants:

| | Claude Code | Codex | Mistral Vibe | Antigravity (`agy`) | OpenCode | Copilot |
|---|---|---|---|---|---|---|
| Location | `~/.claude/agents/<name>.md` | `~/.codex/agents/<name>.toml` | `~/.vibe/agents/<name>.toml` | `~/.gemini/config/agents/<name>/agent.md` | `~/.config/opencode/agents/<name>.md` | `~/.copilot/agents/<name>.agent.md` |
| Model and effort | `model`, `effort` | `model`, `model_reasoning_effort` | session model | `inherit` (or caller tier) | session model | `model`, `reasoningEffort` |
| Tools | `tools` allowlist, or `disallowedTools` | the parent's | `enabled_tools` or `disabled_tools` | `tools` allowlist | `permission` map (`allow`/`deny`) | `tools` aliases |
| Delegation | `Agent(name, …)` in `tools` | `spawn_agent`, session-wide | `task` tool | `invoke_subagent` | `task` permission | `agent` alias |
| Limits | `maxTurns`, hooks | none per agent | `safety` (`safe`/`neutral`) | none per agent | `steps` | none per agent |
| Skills | `skills` loaded at start, and the Skill tool | discovered automatically | `skill` tool | discovered automatically | `skill` permission | the `skill` tool |

The capability map in `build.py`:

| Capability | Claude Code | Copilot | Mistral Vibe | OpenCode | Antigravity (`agy`) |
|---|---|---|---|---|---|
| `read` | Read | `read` | `read_file` | `read` | `view_file`, `view_file_outline`, `view_code_item` |
| `search` | Grep, Glob | `search` | `grep` | `grep`, `glob` | `grep_search`, `find_by_name` |
| `lsp` | LSP | — | — | `lsp` | — |
| `shell` | Bash | `execute` | `bash` | `bash` | `run_command`, `manage_task` |
| `shell-readonly` | Bash + guard | — | `bash` + prompt rule | — | `run_command`, `manage_task` + prompt rule |
| `edit` | Edit, Write | `edit` | `edit`, `write_file` | `edit` | `replace_file_content`, `multi_replace_file_content`, `write_to_file` |
| `web` | WebFetch, WebSearch | `web` | `web_fetch`, `web_search` | `webfetch`, `websearch` | `read_url_content`, `search_web` |
| `todo` | TodoWrite | `todo` | `todo` | `todowrite` | — |
| `agents` | `Agent(<spawns>)` | `agent` | `task` | `task` | `invoke_subagent`, `manage_subagents`, `define_subagent` |
| `skills` | Skill | `skill` | `skill` | `skill` | — |
| `apple-docs` | `mcp__apple-docs` | `apple-docs/*` | `mcp_apple_docs_*` | `apple-docs_*` | `call_mcp_tool`, `list_resources`, `read_resource` |

`tools: all` with `deny:` gives every tool the session has except the denied ones. The
orchestrator uses it to keep messaging and MCP tools without Edit and Write. On macOS, Claude Code
leaves Grep and Glob out of a session that has Bash, so an agent with a shell searches with `grep`
and `find`, which the guard allows.

The turn budget is Claude's `maxTurns`, OpenCode's `steps`, and a Budget section in the prompt on
every harness.

## Layout

```
agents/
  src/*.md                neutral sources — EDIT THESE
  tiers.json              tier -> per-harness model and effort (the cost dial)
  build.py                render src/ -> claude/ copilot/ codex/ vibe/ opencode/ agy/; --check verifies they are current
  claude/hooks/           hand-written: the read-only Bash guard
  claude/*.md             generated — do not edit
  copilot/*.agent.md      generated — do not edit
  codex/*.toml            generated — do not edit
  vibe/*.toml             generated — do not edit
  opencode/*.md           generated — do not edit
  agy/*/agent.md          generated — do not edit
  tests/                  tests for build.py and the guard
```

## Workflow

```bash
# edit a source or the tier map, then:
python3 agents/build.py                              # regenerate all six variants
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
- Mistral Vibe agents and TOML profiles: `~/.vibe/agents/*.toml` (`vibe/core/agents/models.py`)
- Google Antigravity (`agy`) subagents: `~/.gemini/config/agents/<name>/agent.md`
- OpenCode subagents: `~/.config/opencode/agents/<name>.md` (`opencode debug agents`)


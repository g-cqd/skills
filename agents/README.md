# Agents

A focused roster of seven specialized subagents, each with one job, a tight tool surface, and a
**cost-appropriate model tier**. Written once as neutral source, rendered per harness.

## Why specialized agents with tiered models

The production pattern is **cheap fan-out, expensive judgment**: route mechanical, high-volume,
low-risk work to a cheap model, and spend the top model only where a wrong answer is expensive to
detect — architecture, adversarial review, security. A capable orchestrator plans and delegates;
cheaper specialists execute in their own context and return only a clean summary. This both cuts
token cost (reported 5–10× on delegated work) and keeps the expensive model's context clean so it
reasons better.

Two rules the roster follows:

1. **One clear job per agent**, a tool surface that matches it, and instructions that keep it from
   drifting into adjacent work.
2. **Default to the cheap tier**; escalate only when the task is ambiguous, cross-cutting,
   high-risk, or long-horizon.

## The roster

| Agent | Tier | Tools | Job | Skills it loads |
|---|---|---|---|---|
| `orchestrator` | reasoning | full | Decompose, route to the cheapest capable specialist, synthesize | `planner` |
| `scout` | economy | read-only | Locate, map, trace, extract — reconnaissance before work | — |
| `implementer` | standard | edit | Turn a specified change into a small, verified diff | `swift`, `engineering-practices`, `project-conventions` |
| `test-engineer` | standard | edit | TDD, regression tests, suite migration; judge meaningfulness | `testing` |
| `code-reviewer` | reasoning | read-only | Correctness/architecture/simplification review, adversarial | `code-review` |
| `security-auditor` | reasoning | read-only | Trust-boundary + memory-safety + iOS attack surface | `secure-coding`, `memory-safety` |
| `docs-writer` | economy | edit | PR text, tickets, ADRs, release notes | `work-docs` |

Debugging is handled by `scout` (reproduce, isolate) feeding `implementer` (minimal fix), with the
`debugging` skill loaded — no separate agent, to keep the roster at seven.

Three read-only agents (`scout`, `code-reviewer`, `security-auditor`) can never mutate the tree —
enforced by the tool allowlist on Claude/Copilot and `sandbox_mode = "read-only"` on Codex.

## The cost dial — `tiers.json`

The tier→model mapping is the single place cost is tuned:

```
economy    haiku   / gpt-5.6-luna    — mechanical, high-volume, cheap-to-retry
standard   sonnet  / gpt-5.6-terra   — clear-scope reasoning, tests catch mistakes
reasoning  opus    / gpt-5.6-sol     — ambiguous, high-risk, expensive-to-fix
```

**Re-audit this map every few months.** The best-value model in each class drifts, and a stale
mapping quietly eats the savings. Change the ids in `tiers.json`, re-run `build.py`, done — no
agent file is touched.

## Cross-harness compatibility

Each harness reads a different format, so one neutral source renders three variants:

| Harness | Location | Format | Model field | Tools | Read-only via |
|---|---|---|---|---|---|
| Claude Code | `~/.claude/agents/<name>.md` | MD + YAML | `haiku`/`sonnet`/`opus` | `tools:` CSV | tool allowlist |
| Copilot | `~/.copilot/agents/<name>.agent.md` | MD + YAML | model id | `tools:` array | tool allowlist |
| Codex | `~/.codex/agents/<name>.toml` | TOML | model id | `sandbox_mode` | `read-only` sandbox |

`build.py` maps the neutral `tier` and `tools` capability (`readonly` / `edit` / `full`) to each
harness's vocabulary. The Claude and Copilot bodies are the Markdown prompt verbatim; the Codex
body goes into `developer_instructions`.

## Layout

```
agents/
  src/*.md          neutral sources — EDIT THESE (frontmatter: name, tier, tools, description + body)
  tiers.json        tier -> per-vendor model + effort (the cost dial)
  build.py          render src/ -> claude/ copilot/ codex/
  claude/*.md       generated — do not edit
  copilot/*.agent.md generated — do not edit
  codex/*.toml      generated — do not edit
```

## Workflow

```bash
# edit a source or the tier map, then:
python3 agents/build.py         # regenerate all three variants

# install.sh links the format-matching subdir into each detected harness:
./install.sh                    # ~/.claude/agents -> agents/claude, etc.
```

Add an agent: drop `src/<name>.md` with `name`, `tier` (economy|standard|reasoning),
`tools` (readonly|edit|full), a delegation-focused `description`, and the prompt body; run
`build.py`. Keep the roster small — a focused handful beats a sprawling catalog the orchestrator
cannot route cleanly.

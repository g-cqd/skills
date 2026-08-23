# Agent Skills Specification

Skills follow the [Agent Skills](https://agentskills.io) open standard, supported by 30+ AI tools (Claude Code, Codex, Cursor, VS Code Copilot, Gemini CLI, OpenCode, Goose, Roo Code, and more).

## File Structure

```
skill-name/
├── SKILL.md              # Required — main instructions with YAML frontmatter
├── scripts/              # Optional — executable code (Python, Bash, etc.)
├── references/           # Optional — documentation loaded into context as needed
└── assets/               # Optional — templates, icons, fonts used in output
```

### Critical Rules

- File MUST be named exactly `SKILL.md` (case-sensitive) — not SKILL.MD, skill.md, etc.
- Skill folder: kebab-case only, no spaces, no underscores, no capitals
- No README.md inside the skill folder — all docs go in SKILL.md or references/
- No XML angle brackets (`< >`) in frontmatter (security restriction)
- No "claude" or "anthropic" in skill name (reserved)

## YAML Frontmatter

```yaml
---
name: my-skill-name
description: What this skill does. Use when user asks about X, mentions Y, or needs Z.
---
```

### Required Fields

**`name`** (recommended):
- kebab-case only (lowercase, digits, hyphens)
- Under 64 characters
- Should match folder name
- If omitted, uses directory name

**`description`** (recommended):
- The PRIMARY triggering mechanism — this is how the agent decides when to use the skill
- Structure: `[What it does] + [When to use it] + [Key capabilities]`
- Under 1024 characters
- Include specific task phrases users would say
- Include file types if relevant
- Add negative triggers to prevent over-triggering ("Do NOT use for X")
- Make descriptions slightly "pushy" — agents tend to undertrigger

### Optional Fields (Claude Code Extensions)

| Field | Purpose |
|-------|---------|
| `disable-model-invocation` | `true` = only user can invoke (for side-effect skills like deploy) |
| `user-invocable` | `false` = only agent can invoke (for background knowledge) |
| `allowed-tools` | Tools allowed without permission when skill is active |
| `model` | Model override when skill is active |
| `effort` | Effort level: `low`, `medium`, `high`, `max` |
| `context` | `fork` = run in isolated subagent |
| `agent` | Subagent type when `context: fork` (e.g., `Explore`, `Plan`) |
| `argument-hint` | Autocomplete hint (e.g., `[issue-number]`) |
| `hooks` | Lifecycle hooks scoped to this skill |
| `compatibility` | Environment requirements (1-500 chars) |
| `license` | License identifier (MIT, Apache-2.0) |
| `metadata` | Custom key-value pairs (author, version, mcp-server) |

### String Substitutions

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments passed when invoking |
| `$ARGUMENTS[N]` / `$N` | Specific argument by 0-based index |
| `${CLAUDE_SESSION_ID}` | Current session ID |
| `${CLAUDE_SKILL_DIR}` | Directory containing SKILL.md |
| `` !`command` `` | Dynamic context injection (runs shell command, inserts output) |

### Invocation Matrix

| Config | User can invoke | Agent can invoke |
|--------|:-:|:-:|
| (default) | Yes | Yes |
| `disable-model-invocation: true` | Yes | No |
| `user-invocable: false` | No | Yes |

## Description Writing

### Good Descriptions

```yaml
# Specific and actionable
description: Analyzes Figma design files and generates developer handoff
  documentation. Use when user uploads .fig files, asks for "design specs",
  "component documentation", or "design-to-code handoff".

# Includes trigger phrases
description: Manages Linear project workflows including sprint planning,
  task creation, and status tracking. Use when user mentions "sprint",
  "Linear tasks", "project planning", or asks to "create tickets".

# Clear negative triggers
description: Advanced data analysis for CSV files. Use for statistical
  modeling, regression, clustering. Do NOT use for simple data exploration
  (use data-viz skill instead).
```

### Bad Descriptions

```yaml
# Too vague
description: Helps with projects.

# Missing triggers
description: Creates sophisticated multi-page documentation systems.

# Too technical, no user triggers
description: Implements the Project entity model with hierarchical relationships.
```

## Progressive Disclosure

Three-level loading system to manage context efficiently:

1. **Metadata** (name + description) — always in context (~100 words)
2. **SKILL.md body** — loaded when skill triggers (<500 lines / <5k words)
3. **Bundled resources** — loaded on demand (unlimited; scripts execute without loading)

### Key Rules

- Keep SKILL.md under 500 lines
- Move detailed docs to `references/` and link clearly from SKILL.md
- For large reference files (>100 lines), include a table of contents
- Avoid deeply nested references — keep one level deep from SKILL.md
- Information lives in either SKILL.md OR references, not both

## Where Skills Live

| Scope | Path | Applies To |
|-------|------|------------|
| Enterprise | Managed settings | All org users |
| Personal | `~/.claude/skills/<name>/SKILL.md` | All your projects |
| Project | `.claude/skills/<name>/SKILL.md` | This project only |
| Plugin | `<plugin>/skills/<name>/SKILL.md` | Where plugin enabled |

Priority: enterprise > personal > project. Plugin skills use `plugin:skill` namespace.

## Cross-Platform Compatibility

The Agent Skills standard works across platforms. Platform-specific features:

| Feature | Claude Code | Codex | Cursor | Others |
|---------|:-:|:-:|:-:|:-:|
| SKILL.md + frontmatter | Yes | Yes | Yes | Yes |
| `context: fork` (subagents) | Yes | No | No | Varies |
| `allowed-tools` | Yes | No | No | Varies |
| `disable-model-invocation` | Yes | No | No | Varies |
| Dynamic context injection | Yes | No | No | No |
| `agents/openai.yaml` | No | Yes | No | No |

For Codex compatibility, also create `agents/openai.yaml` — see `references/openai_yaml.md`.

## Skill Use Case Categories

### 1. Document & Asset Creation
Consistent output: documents, apps, designs, code. Use templates, style guides, quality checklists.

### 2. Workflow Automation
Multi-step processes with consistent methodology. Use step-by-step validation gates, templates, iterative refinement.

### 3. MCP Enhancement
Workflow guidance on top of MCP tool access. Coordinate MCP calls, embed domain expertise, handle errors.

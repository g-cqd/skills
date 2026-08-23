# Skill Routing Matrix

## Dynamic Discovery

Before routing, run `bash scripts/discover-skills.sh [project-root]` to get the live catalog of available skills across all directories. NEVER route to a skill that doesn't exist in the discovery output. NEVER reference hardcoded skill names — always derive from discovery.

## Scan Directories (in priority order)

1. **Project-level** (highest priority — project-specific overrides):
   - `./.claude/skills/`, `./.codex/skills/`, `./.copilot/skills/`, `./.opencode/skills/`, `./.agents/skills/`
   - `./.claude/commands/`
2. **User-level** (personal defaults):
   - `~/.claude/skills/`, `~/.codex/skills/`, `~/.copilot/skills/`, `~/.opencode/skills/`, `~/.agents/skills/`
   - `~/.claude/commands/`

Project-level skills take precedence over user-level skills with the same name.

## Routing Algorithm

### Step 1: Build the live catalog

Run discovery. Parse each skill's `name` and `description` fields. These are the only inputs to routing decisions.

### Step 2: Extract intents from the request

Identify all intents present in the user's request. A single request can contain multiple intents (e.g., "implement a SwiftUI view with secure Keychain storage and write tests" has UI, security, and testing intents).

### Step 3: Match intents to skills by description

For each intent, scan the live catalog descriptions for the best match. Score by:

1. **Keyword overlap** — does the skill description mention terms from the request?
2. **Scope alignment** — does the skill's "Use when" clause match the intent?
3. **Negative triggers** — does the skill's "Not for" / "Do NOT use when" clause exclude this intent?

### Step 4: Select and rank

1. Identify the **primary skill** — the one whose description most directly matches the core intent
2. Identify **supporting skills** — those matching secondary intents or cross-cutting concerns
3. Rank by relevance to the request
4. Cap at 10 skills maximum

### Step 5: Resolve conflicts

- If two discovered skills cover the same intent, prefer the more specific one (narrower description)
- If a skill exists at both project and user level, prefer the project-level version
- Skills from other tools (codex, copilot, opencode, agents) are treated as equivalent — route by capability match, not tool origin

## Composition Rules

1. Select up to 10 relevant skills — as many as the request genuinely requires
2. Identify one primary domain skill, then add supporting skills as warranted by the request scope
3. When multiple skills are equally relevant, prefer the more specific one
4. If a skill exists at project level with the same name as a user-level skill, use the project-level version
5. Skills from different tools are treated equally — route by capability, not origin
6. If no discovered skill matches an intent, proceed without routing for that intent

## Output Contract

Before execution, state selected skills and rationale:

```
Discovered: {N} skills across {sources}
Selected skills: skill-1, skill-2, skill-3 (reason: brief rationale per skill)
```

If no routing needed:

```
Selected skills: none (reason: direct/simple request)
```

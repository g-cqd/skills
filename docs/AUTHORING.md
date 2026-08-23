# Authoring skills and agents

How to add or maintain a skill or a subagent so it fits the rest of the set.

## Two rules that shape every skill

1. **`SKILL.md` carries the knowledge.** A thin skill pointing at a deep `references/` tree behaves
   like a thin skill — the references rarely get read. Put the actionable rules, decision tables,
   and gotchas inline (target 10–20 KB); keep only long-tail catalogs and code corpora in
   `references/`.
2. **The description is a retrieval key**, not a summary. It is the only text the harness sees when
   deciding whether to load the skill. Write it for that decision.

## Skill anatomy

```
skills/<name>/
  SKILL.md                 frontmatter + actionable body
  references/              optional — deep material loaded on demand
```

```markdown
---
name: <kebab-case, matches the directory>
description: <see below>
---

# <Title>

<One paragraph: the concern this skill owns, and what it explicitly does not.>

## Contract          <compact non-negotiable rules for the domain>
## <sections>        <prose: decision tables, rules, gotchas, worked patterns>
## Boundaries        <what belongs to a neighbouring skill, named>
## References        <only where deep material exceeds the body>
```

## Writing the description

Answer: *given a user message, should this skill load?* In order:

1. **Concern** — what it governs, in concrete nouns.
2. **Coverage** — the specific sub-topics, named. These are the matchable terms.
3. **Triggers** — "Use when …", with the situations spelled out. Include the failing-symptom
   phrasing where a skill fixes a known error — a user pastes the compiler error, not the concept.
4. **Negative boundary** — "Not for X, use `<skill>`." This is what stops overlap.

Name concrete API and concept terms, not categories: `@Observable`, `Sendable`, `NSFileProtection`
match; "modern patterns" does not. Never write a description that could equally describe a
neighbour — if two overlap, merge the skills or redraw the boundary.

## Tiering — generic, Apple, mixed

Skills live in one flat tree, but the tier is declared in the **first words** of the description so
a reader knows within one line whether it applies to them:

| Tier | Opens with | Example |
|---|---|---|
| Generic | `Language-agnostic:` | `algorithms`, `debugging` |
| Apple | `Apple platforms:` | `swift`, `swiftui`, `xcode` |
| Mixed | `Language-agnostic <domain>, with an Apple-platform section covering …:` | `memory-safety`, `secure-coding`, `testing` |

A **mixed** skill orders its body generic-first, Apple-last:

- The generic sections must be complete and usable with no Apple context — a reader who stops at
  `## Apple platforms` still has a coherent skill.
- No Apple API in a generic section. A comparative table covering C, C++, Swift, Kotlin, and Rust
  evenly is generic; a section *about* Swift is not.
- One Apple section, not several scattered through the body.

Merging beats splitting when two skills would trigger on the same message and then disagree about
scope. Keep one concern per skill and tier *within* it.

## Boundaries

Every skill declares at least one negative boundary, and names a skill that actually owns the
concern it disclaims. Boundaries are answered, not mirrored: if `algorithms` cites `testing` for
property-based invariants, `testing` need not cite `algorithms` back — but the concern a skill
points away must genuinely live in the skill it names.

## Portability

A skill carries no project identifier — no organisation name, no ticket key, no in-house macro, no
team decision presented as a universal rule. Where a value is a project's to choose, state the
*procedure* ("detect the project's convention", "use the project's mock mechanism") and leave the
*value* to the repository: `project-conventions` reads it out of the tree you are in, and the
`CONFIGURATION` block in `AGENTS.md` is where a project records it explicitly.

A skill that cannot be written this way is a project's own file, not a skill for this set.

## Agents

A subagent is a scoped worker the main agent delegates to. Author once as a neutral source:

```markdown
---
name: <kebab-case>
tier: economy | standard | reasoning
tools: readonly | edit | full
description: >
  <what it does, when to delegate to it, and what it does not do.
  Use PROACTIVELY for auto-delegation where appropriate.>
---
<system prompt: role, method, stay-in-lane rules, which skills to load, output contract>
```

Then `python3 agents/build.py` renders `claude/<name>.md`, `copilot/<name>.agent.md`, and
`codex/<name>.toml`, mapping the tier to a per-vendor model (`agents/tiers.json`) and the tool
capability to each harness's vocabulary.

Design rules:

- **One clear job**, a tool surface that matches it, instructions that keep it from drifting into
  adjacent work.
- **Pick the cheapest tier that fits.** Default to economy; escalate to reasoning only for
  ambiguous, cross-cutting, high-risk, or expensive-to-fix work. This is the whole cost model.
- **Read-only where it can be** — `readonly` tools mean the agent cannot mutate the tree, enforced
  by an allowlist on Claude/Copilot and `sandbox_mode` on Codex.
- Keep the roster small. A focused handful the orchestrator can route cleanly beats a sprawling
  catalog.

The tier→model map in `agents/tiers.json` is the cost dial — re-audit it every few months, because
the best-value model in each class drifts.

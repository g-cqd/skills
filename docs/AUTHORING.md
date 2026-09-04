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

Keep the parsed description at 1–1,024 characters; target at most 500 for this set.
The repository validator enforces the 1,024-character ceiling and rejects angle brackets.
Use YAML `>-` for a wrapped description without a trailing newline. Keep the main triggers
and a useful boundary; put API catalogs, examples, and detailed procedures in the body.
Do not shorten by cutting off a sentence or removing the skill's distinguishing concern.
Front-load the main use case: [Codex may shorten descriptions](https://learn.chatgpt.com/docs/build-skills)
to fit the initial skill-list context budget, even when each description passes validation.

Validate every skill before delivery (and use the same check in CI):

```sh
for skill in skills/*; do
  python3 skills/skill-creator/scripts/quick_validate.py "$skill" || exit 1
done
```

Answer: *given a user message, should this skill load?* In order:

1. **Concern** — what it governs, in concrete nouns.
2. **Coverage** — the specific sub-topics, named. These are the matchable terms.
3. **Triggers** — "Use when …", with the situations spelled out. Include the failing-symptom
   phrasing where a skill fixes a known error — a user pastes the compiler error, not the concept.
4. **Negative boundary** — "Not for X, use `<skill>`." This is what stops overlap.

Name concrete API and concept terms, not categories: `@Observable`, `Sendable`, `NSFileProtection`
match; "modern patterns" does not. Never write a description that could equally describe a
neighbour — if two overlap, merge the skills or redraw the boundary.

## Prompting rules — how the body is written

A skill body and an agent prompt are system-prompt text. They follow Anthropic's
[prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
and the [Claude Fable 5.1 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1).
The rules below are the ones that matter for this set; apply them when adding or editing text.

**Tone and emphasis**

- Write in normal sentence case. Current models follow the system prompt closely and overtrigger
  on shouted instructions, so `MUST`, `NEVER`, `CRITICAL`, `ALWAYS`, and "IRON LAW" style headers
  make a rule fire too often, not more reliably. "Use X when …" carries the same weight.
- The compact `§` Contract block is house notation, not shouting — keep it, and keep it short.
- State the rule and, where the reason is not obvious, the reason in the same breath. Claude
  generalises from the motivation; a bare rule gets applied literally and in the wrong places.

**Positive form**

- Say what to do, not only what to avoid. "Do not nest `if let`" becomes "use `guard let` for an
  early exit; nesting hides the logic". A prohibition without an alternative leaves the model to
  guess the alternative.
- Formatting rules say when a format is appropriate, not which formats are banned. Blanket
  anti-markdown language suppresses structure the content needs.

**Examples**

- Wrap an example of the model's own output — a review comment, a commit message, a ticket, an
  answer shape — in `<example>` tags, several in `<examples>`, each with a one-line rationale so the
  model learns the *why* rather than the surface form. Code that demonstrates an API pattern stays
  in a fenced block; it is reference material, not an output example.
- Three to five diverse examples steer format better than more rules.

**Reasoning**

- Prefer general instructions ("think this through", "verify against the spec before finishing")
  over hand-written step-by-step reasoning scripts; the model's own reasoning usually exceeds a
  prescribed one. Numbered steps are for procedures whose *order* matters, not for thinking.
- Where a skill ends in a deliverable, ask for a self-check against a named criterion before
  finishing. This catches errors reliably at almost no cost.

**Agentic behaviour** (matters most in agent prompts)

- Ground claims in what was read: never speculate about code that was not opened. Search or read
  before answering; recognising a name is not knowing its current state, and this matters most on
  cheap tiers, which reach for tools less.
- Keep changes and tests to what the task asks. A pre-existing bug or nearby improvement is a
  follow-up in the summary, not a change in this diff, unless the requested behaviour cannot work
  without it. Tests are sized like the neighbouring test files, roughly one focused test per
  stated behaviour; scratch checks are not promoted to permanent tests.
- Prefer a targeted edit to a whole-file rewrite unless the file is short or mostly changing.
- Remove scratch files and helper scripts created during the task.
- Batch independent tool calls in one response; sequence only true dependencies.
- Finish the whole task. A subagent cannot ask the user anything mid-task: do everything that does
  not depend on the open question, state the assumption, and put the question in the final report.
  Describing the next step and stopping leaves it undone.
- The final message must stand on its own. The caller sees only that message, not the tool calls,
  so it states what was found, what was done, and what is left.
- Pause only for destructive or outward-facing actions (deleting, force-pushing, publishing) and
  for genuine scope changes; local, reversible edits proceed.

**Prose**

- No mannered prose: metaphor and flourish in place of direct statement ("a dial worth turning"
  for "a parameter worth varying"). When a literal phrase exists, use it.
- When summarising a document or source, mark verbatim passages as quotations; put everything
  else in the model's own words.

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

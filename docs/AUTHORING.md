# Authoring skills and agents

How to add or change a skill or a subagent in this set.

## Two rules that shape every skill

1. **`SKILL.md` carries the rules.** Agents rarely open `references/`. Put the rules, decision
   tables, and known failure cases in `SKILL.md`, and keep it under 500 lines. Put only long
   catalogs and code corpora in `references/`.
2. **The description is a retrieval key**, not a summary. It is the only text the harness reads
   to decide whether to load the skill. Write it for that decision.

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

- Keep the parsed description between 1 and 1,024 characters; target 500 or fewer for this set.
  The repository validator enforces the 1,024-character limit and rejects angle brackets.
- Use YAML `>-` for a wrapped description without a trailing newline.
- Keep the main triggers and at least one boundary. Put API catalogs, examples, and detailed
  procedures in the body.
- To shorten, rewrite; do not cut off a sentence or remove the skill's distinguishing concern.
- Put the main use case first: [Codex may shorten descriptions](https://learn.chatgpt.com/docs/build-skills)
  to fit its initial skill-list context budget, even when each description passes validation.

Validate each changed skill before delivery, and run the same check in CI:

```sh
for skill in skills/*; do
  python3 skills/skill-creator/scripts/quick_validate.py "$skill" || exit 1
done
```

The description answers one question: *given a user message, must this skill load?* Write its
parts in this order:

1. **Concern:** what the skill governs, in concrete nouns.
2. **Coverage:** the sub-topics, named. These are the terms a message matches.
3. **Triggers:** "Use when …", with the situations named. Where the skill fixes a known error,
   include the error's wording; a user pastes the compiler error, not the concept.
4. **Negative boundary:** "Not for X, use `<skill>`." This prevents overlap.

Name concrete API and concept terms, not categories: `@Observable`, `Sendable`, and
`NSFileProtection` match; "modern patterns" does not. A description must not fit a neighbouring
skill equally well. If two descriptions overlap, merge the skills or redraw the boundary.

## Prompting rules — how the body is written

A skill body and an agent prompt are system-prompt text. They follow Anthropic's
[prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
and the [Claude Fable 5.1 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1).
Apply the rules below when you add or edit text.

**Tone and emphasis**

- Write in sentence case. Current models follow the system prompt closely, so shouted words
  (`MUST`, `NEVER`, `CRITICAL`, `ALWAYS`, "IRON LAW" headers) make a rule fire too often. "Use X
  when …" carries the same weight.
- The `§` Contract block is house notation, not shouting. Keep it, and keep it short.
- Give a reason only under plain-language rule 15. One clause of reason stops a bare rule from
  being applied in the wrong places.

**Positive form**

- State what to do, not only what to avoid: "Do not nest `if let`" becomes "use `guard let` for an
  early exit; nesting hides the logic". Without the alternative, the model guesses one.
- A formatting rule states when a format fits, not which formats are banned. A blanket ban on
  markdown removes structure the content needs.

**Examples**

- Wrap an example of the model's own output (a review comment, a commit message, a ticket, an
  answer shape) in `<example>` tags, and several in `<examples>`. Give each a one-line rationale,
  so the model learns why, not only the surface form. Code that demonstrates an API pattern stays
  in a fenced block; it is reference material, not an output example.
- Three to five varied examples steer format better than more rules.

**Reasoning**

- Write general instructions ("think this through", "verify against the spec before finishing"),
  not step-by-step reasoning scripts; the model's own reasoning usually exceeds a prescribed one.
  Use numbered steps only for procedures whose *order* matters.
- When a skill ends in a deliverable, require a self-check against a named criterion before
  finishing.

**Agentic behaviour** (mainly for agent prompts)

- Ground claims in what was read: do not describe code that was not opened. Search or read before
  answering; recognising a name is not knowing its current state. The rule matters most on cheap
  tiers, which call tools less.
- Keep changes and tests to what the task asks. Report a pre-existing bug or a nearby improvement
  as a follow-up, unless the requested behaviour cannot work without it. Size tests like the
  neighbouring test files, about one focused test per stated behaviour; do not keep scratch checks
  as permanent tests.
- Make a targeted edit, not a whole-file rewrite, unless the file is short or most of it changes.
- Remove scratch files and helper scripts created during the task.
- Batch independent tool calls in one response; sequence only true dependencies.
- Finish the whole task. A subagent cannot ask the user anything mid-task: it does everything that
  does not depend on the open question, states the assumption, and puts the question in the final
  report. A report that describes the next step instead of doing it leaves the step undone.
- The final message stands alone. The caller sees only that message, not the tool calls, so it
  states what was found, what was done, and what is left.
- Ask the user before a destructive or outward-facing action (deleting, force-pushing,
  publishing) and before a scope change the user must decide. A subagent that cannot ask does not
  take the action and reports it. Local, reversible edits proceed.

## Plain-language rules

Applies to every skill, agent definition and `AGENTS.md`. The direction comes from ASD-STE100
(Simplified Technical English); it is not a copy of that standard. An agent reads these words
literally, so each sentence must stay correct when it is taken literally and applied everywhere
it can apply.

**Wording**

1. One instruction per sentence, about 20 words at most. Use the imperative for actions ("Run the
   tests"), the present tense for facts, and the active voice.
2. One word for one thing. Pick "diff" or "change set" and keep it in the whole file. Define a term
   once, where it first appears.
3. No metaphors, idioms, figures of speech, humour or rhetorical questions. Write the literal thing.
4. No filler or intensifiers (very, simply, just, carefully, robust, clean, elegant). No hedges (try
   to, consider, ideally, maybe) unless the same sentence gives the condition that decides.
5. Replace a vague quantity or degree word (large, small, many, soon, often, slow) with a number or
   a test when the source gives one. When it does not, state the criterion in words ("until the
   build passes") or list the rule for the owner. Do not invent a threshold and do not delete a rule
   because it is vague.
6. Write "must" for a rule, "must not" for a prohibition and "may" for an option. Do not write
   "should".

**Literal reading**

7. Scope every absolute. An agent takes "always", "never", "every", "all" and "any" at face value.
   Write the exact condition ("in each changed file", "before the first edit") or the exception.
8. Give every loop, search and review a stop: a count, a list, or a test for done. Write "each
   changed function", not "everything related".
9. Say what to do when the rule cannot be followed: no tests exist, a tool is missing, the user has
   not answered. Take the fallback from an existing rule in the repository. When none exists, write
   "stop and report".
10. Use the noun, not a pronoun (it, this, that, they), whenever two nouns could be meant.
11. Give each prohibition the allowed action. Give each action that deletes, overwrites, publishes
    or spends money the condition that permits it.
12. Test each rule: read it as an agent with no common sense and apply it literally. If the result
    defeats the purpose, add the missing condition or rewrite the rule.

**Content**

13. Delete what the model already knows (textbook definitions, general advice) and every sentence
    that does not change what the agent does. Keep thresholds, commands, names, decision tables,
    exceptions, known failure cases, and rules where this repository or skill differs from the
    default.
14. State a rule once per file. A rule that must apply in every session stays in the file that
    is always loaded (`AGENTS.md`, or the skill's body); do not replace it with a pointer. Link to a
    section only for detail.
15. Keep a reason only when it changes behaviour in a case the rule does not name. Use one clause.
16. Keep an example that shows an output format or a case that is not obvious. Cut an example that
    repeats the rule.
17. Use a table for a decision or a lookup, a short list for steps, and a paragraph for nothing
    that a list or table would state more briefly.

When summarising a document or source, mark verbatim passages as quotations and write everything
else in your own words.

## Tiering — generic, Apple, mixed

Skills live in one flat tree. The **first words** of the description declare the tier, so a reader
knows from the first line whether the skill applies:

| Tier | Opens with | Example |
|---|---|---|
| Generic | `Language-agnostic:` | `algorithms`, `debugging` |
| Apple | `Apple platforms:` | `swiftui`, `xcode`, `apple-docs` |
| Mixed | `Language-agnostic <domain>, with an Apple-platform section covering …:` | `memory-safety`, `secure-coding`, `testing` |
| Named language or domain | Opens with the language or domain itself, when it is not tied to Apple platforms | `swift` (also Linux, servers, embedded), `graphics` (cross-platform, Metal section) |

A **mixed** skill puts the generic sections first and the Apple section last:

- The generic sections must be complete without Apple context: a reader who stops at
  `## Apple platforms` still has a usable skill.
- A generic section names no Apple API. A comparison table that covers C, C++, Swift, Kotlin, and
  Rust equally is generic; a section *about* Swift is not.
- Put all Apple content in one Apple section.

When two skills would trigger on the same message and then disagree about scope, merge them. Keep
one concern per skill, and tier *within* the skill.

## Boundaries

Each skill declares at least one negative boundary, and names the skill that owns the concern it
disclaims. The named skill must own that concern. The named skill does not need to cite back: if
`algorithms` cites `testing` for property-based invariants, `testing` need not cite `algorithms`.

## Portability

A skill contains no project identifier: no organisation name, ticket key, or in-house macro, and
no team decision presented as a universal rule. Where a value is the project's choice, state the
*procedure* ("detect the project's convention", "use the project's mock mechanism") and leave the
*value* to the repository. `project-conventions` reads the value from the current repository, and
a project records it in the `CONFIGURATION` block of `AGENTS.md`.

Content that cannot be written this way belongs in the project's own files, not in this set.

## Agents

A subagent is a scoped worker that the main agent delegates to. Write it once, as a neutral
source:

```markdown
---
name: <kebab-case>
tier: micro | economy | standard | reasoning | frontier
tools: <capabilities, comma-separated: read, search, lsp, shell | shell-readonly, edit, web, todo,
        agents, skills, apple-docs> | all
description: >
  <what it does, when to delegate to it, and what it does not do.
  Use PROACTIVELY for auto-delegation where appropriate.>
max_turns: <optional turn budget, for a small job>
skills: <optional skills to load at start>
spawns: <optional agents it may start, with the agents capability>
---
<system prompt: role, method, stay-in-lane rules, output contract>
```

Then `python3 agents/build.py` renders `claude/<name>.md`, `copilot/<name>.agent.md`, and
`codex/<name>.toml`. It maps the tier to each harness's model and effort (`agents/tiers.json`) and
each capability to the harness's tools. The header of `build.py` lists each key, and
`python3 agents/build.py --check` fails when a generated file is stale.

Design rules:

- **One job per agent**, with tools that match the job and instructions that keep the agent out
  of adjacent work. A roster the orchestrator cannot route without overlap costs more than it
  saves.
- **Pick the cheapest tier that fits.** A small mechanical job with a clear stop is micro. Default
  to economy or standard. Use reasoning only for ambiguous, cross-cutting, high-risk, or
  expensive-to-fix work, and frontier only where a miss is the costliest outcome.
- **Give the agent each tool its job needs, and no other.** An agent that must return to its caller
  for a `git log` costs more than one that runs it. An agent that can edit when its job is to
  report is a risk.
- **Make the agent read-only when its job allows.** `shell-readonly` gives a shell that only reads:
  Claude Code runs the guard in `agents/claude/hooks/` before each command, Copilot gets no shell,
  and Codex, which runs each agent in its parent's sandbox, relies on the prompt.
- **Give small jobs a turn budget.** On Claude Code, `max_turns` stops a micro agent at the
  budget; on every harness, the build states the budget in the prompt.
`agents/tiers.json` maps tiers to models and is the cost dial. Re-audit it every three months: the
best-value model in each class changes.

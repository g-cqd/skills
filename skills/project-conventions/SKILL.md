---
name: project-conventions
description: >-
  Language-agnostic: detect repository rules for branches, commits, PRs, modules, UI
  tokens, localization, test doubles, and off-limits areas. Use when entering an
  unfamiliar repository, locating new code, or resolving conflicts with generic guidance.
  For skill authoring, use `skill-creator`; for delivery practices, use
  `engineering-practices`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Project Conventions

This skill is a **template plus detection workflow**. When a detected
convention conflicts with generic guidance on style, naming, layout, tooling or
process, follow the convention. A convention never overrides a safety, security
or correctness rule, or an explicit user instruction.

## Contract

```
§PRECEDE  observed-convention ≻ generic-guidance ∀conflict ∈ style|naming|layout|tooling|process
          ¬override safety|security|correctness rule ∨ explicit user instruction
          (AGENTS.md CONFLICT: rule 3 convention ≻ rule 4 document; rules 1–2 still win)
§DETECT   ? repo BEFORE applying any generic rule
§THREE    3 existing-examples ≻ generic-rule ∈ §PRECEDE scope
§NEVER    ¬invent ticket-id | branch-form | commit-form
§ABSENT   ∅observed-convention ⇒ ¬introduce-one
§BAN      placeholder-text ∈ output · assume-convention ∅evidence
```

## Part 1: Convention Detection (works in any repo)

Detect conventions before you start work in a repository. Report only what you
observed in the tree. Report a convention you did not observe as "not detected";
do not guess one.

### Ticket convention
```bash
git log --oneline -30
```
- If commit subjects or branch names carry ticket IDs (a pattern like
  `[A-Z][A-Z0-9]+-[0-9]+`, e.g. `ABC-123`), the repository follows a ticket
  convention. Put the ticket ID in branch names, commit messages, and PR
  titles, in the observed placement and format.
- When the repository has a ticket convention, take the ID from the branch name
  (`git branch --show-current`), then from recent commits. If neither has one,
  ask the user. If no one can answer, omit the ID and say so; do not invent a
  ticket number.
- If no ticket convention is observed, do not introduce one.

### Code conventions
1. Read the root instruction files in this priority order: `AGENTS.md`,
   `CONTRIBUTING.md`, `.github/copilot-instructions.md`, `CLAUDE.md`.
2. Read the linter and formatter configs (`.swiftlint.yml`, `.swiftformat`,
   `detekt.yml`, `.editorconfig`). Treat them as enforced rules.
3. Copy the surrounding code: test factory naming, mock strategy, module
   layering, design-token usage. Three existing examples override a generic rule
   on style, naming, layout, tooling or process, but not a safety, security or
   correctness rule, or an explicit user instruction.

### PR etiquette (generic defaults; project rules override)
- One ticket or concern per PR. Flag mixed concerns and split them.
- Review your own diff before requesting review.
- Attach screenshots or recordings for UI changes.
- File a follow-up ticket for each deferred item and name it in the PR. If you
  cannot create tickets, list each deferred item under Follow-ups in the PR.
- Reference the guarded ticket in each regression test, when the repository has a ticket convention.

## Part 2: Team Template (fill in, keep placeholders out of output)

> Replace each `<placeholder>` below for your team, or delete the sections that
> do not apply. A section that still has a placeholder is "not configured":
> use Part 1 detection for it.

### Identity & activation
- Applies when: git remote matches `<git-remote-pattern>` or repo name is
  `<repo-name>`
- Platform: `<ios|android|both|other>`

### Module architecture
- Layering: `<e.g., Feature → Domain → Core; UI never depends on Features>`
- New code lives in: `<e.g., SPM package per feature / Gradle module>`
- Canonical domain terms: `<e.g., the issue-tracking entity is named X
  everywhere — never synonyms>`

### Design system
- Tokens: `<typography/color/spacing token API, e.g. .font(.appTheme.body)>`
- Required components: `<e.g., use the design-system Button, never raw
  Button>`
- Review gate: `<e.g., compare against design specs before PR>`

### Testing utilities
- Factory: `<e.g., makeSUT(...) with defaulted dependencies>`
- Doubles: `<e.g., spies record call arguments in arrays; count-based
  assertions>`
- Mock generation: `<e.g., macro or hand-written under Tests/.../Mocks/>`
- Async coordination: `<e.g., confirmation API; no sleep/timeouts>`

### Localization
- `<e.g., strings land in the same PR; placeholders over concatenation;
  removal cleans all languages>`

### Off-limits without explicit request
- `<e.g., signing/provisioning, CI lanes, dependency-pinning files,
  generated code>`

## Boundaries

Each skill below defers to a convention detected here.

| Need | Skill |
|---|---|
| Generic testing standards | `testing` |
| Generic review standards | `code-review` |
| PR, ticket, and release documentation formats | `work-docs` |
| Refactoring, commit scoping, delivery flow | `engineering-practices` |
| Swift language and naming rules | `swift` |
| SwiftUI design tokens and component rules | `swiftui` |
| Authoring a skill to encode these conventions | `skill-creator` |

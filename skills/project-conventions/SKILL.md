---
name: project-conventions
description: >
  Language-agnostic detection of a repository's own conventions, plus a template
  for encoding a team's: ticket and branch format, commit and PR etiquette,
  module structure and layering, design tokens and required components, test
  factory and mock conventions, localization rules, and off-limits areas. Use
  when starting work in an unfamiliar repository, before applying any generic
  guidance, when writing a branch name or commit message, when deciding where
  new code belongs, or when a generic rule seems to conflict with what the
  codebase already does. Every other skill defers to this one when it is
  present: a detected project convention outranks generic guidance. Not for
  authoring skills, which is `skill-creator`; not for delivery flow itself,
  which is `engineering-practices`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Project Conventions

This skill is a **template plus detection workflow**. Generic skills in this
harness defer to it: project conventions always take precedence over generic
guidance.

## Contract

```
§PRECEDE  observed-convention ≻ generic-guidance ∀conflict
          (§CONFLICT rule-3 ≻ rule-4)
§DETECT   ? repo BEFORE applying any generic rule
§THREE    3 existing-examples ≻ any generic-rule
§NEVER    ¬invent ticket-id | branch-form | commit-form
§ABSENT   ∅observed-convention ⇒ ¬introduce-one
§BAN      placeholder-text ∈ output · assume-convention ∅evidence
```

It ships with no company- or product-specific content. Either rely on Part 1
(dynamic detection) as-is, or fill in Part 2 with your team's conventions and
keep the skill in your user/project scope.

## Part 1: Convention Detection (works in any repo)

When starting work in a repository, detect conventions instead of assuming:

### Ticket convention
```bash
git log --oneline -30
```
- If commit subjects or branch names carry ticket IDs (pattern like
  `[A-Z][A-Z0-9]+-[0-9]+`, e.g. `ABC-123`), the repository follows a ticket
  convention. **Honor it**: include the ticket ID in branch names, commit
  messages, and PR titles, matching the observed placement/format exactly.
- Find the current ticket from the branch name (`git branch --show-current`)
  or ask the user. Never invent ticket numbers.
- If no convention is observed, do not introduce one.

### Code conventions
1. Read root instruction files in priority order: `AGENTS.md`,
   `CONTRIBUTING.md`, `.github/copilot-instructions.md`, `CLAUDE.md`.
2. Check linter/formatter configs (`.swiftlint.yml`, `.swiftformat`,
   `detekt.yml`, `.editorconfig`) — these are enforced rules, not suggestions.
3. Mirror surrounding code: test factory naming, mock strategy, module
   layering, design-token usage. Three existing examples beat any generic rule.

### PR etiquette (generic defaults; project rules override)
- One ticket/concern per PR — flag and split mixed concerns
- Self-review the diff before requesting review
- Screenshots or recordings for UI changes
- File follow-up tickets for deferred work — never silently degrade
- Regression tests reference the ticket they guard against

## Part 2: Team Template (fill in, keep placeholders out of output)

> Replace every `<placeholder>` below for your team, or delete sections that
> don't apply. While placeholders remain, treat the section as "not
> configured" and fall back to Part 1 detection.

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

Every skill below defers to a convention detected here.

| Need | Skill |
|---|---|
| Generic testing standards | `testing` |
| Generic review standards | `code-review` |
| PR, ticket, and release documentation formats | `work-docs` |
| Refactoring, commit scoping, delivery flow | `engineering-practices` |
| Swift language and naming rules | `swift` |
| SwiftUI design tokens and component rules | `swiftui` |
| Authoring a skill to encode these conventions | `skill-creator` |

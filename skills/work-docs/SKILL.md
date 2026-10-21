---
name: work-docs
description: >-
  Language-agnostic: write PR descriptions, work summaries, tickets, user stories, epics,
  acceptance criteria, bug reports, post-mortems, ADRs, design docs, and release notes.
  Use to define requested work or explain completed work. For deciding and scheduling
  work, use `planner`; for source API documentation, use the language skill.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Work Documentation

Generate documentation for software engineering work — from individual PRs to entire program increments. Every artifact supports two perspectives: **requesting** (what needs done) and **reporting** (what was done).

This skill owns **the prose around the work**. It does not decide what work to do (`planner`) or
judge whether it was done well (`code-review`).

## Contract

```
§PERSPECTIVE ! classify{requesting | reporting} BEFORE writing
§GATHER   ? facts ∀repo BEFORE drafting ⇒ ¬invent-a-detail
§WHY      lead with why ≻ what ⇒ diff already-states-what
§DETECT   ticket|branch format ⇒ observe-from-repo ¬invent
§TRUTH    ∀claim traceable-to{commit | ticket | user-statement}
§BAN      fabricated ticket-id · unverified "fixes X" claim ·
          summary ∅reading-the-actual-changes
```

---

## Quick Decision Tree

| User Intent | Action |
|---|---|
| PR description (single PR) | → [Single PR Documentation](#single-pr-documentation) |
| PR for ported/layered code | → [Layered PR Documentation](#layered-pr-documentation) |
| Summarize work (sprint/release/multi-PR) | → [Work Summarization](#work-summarization) |
| User story / acceptance criteria | → [User Stories](#user-stories) |
| Epic definition or completion report | → [Epics](#epics) |
| Bug report or resolution notes | → [Bugs](#bugs) |
| Technical task or spike | → [Tasks & Spikes](#tasks--spikes) |
| PI objectives / iteration goals | → [PI & DI Artifacts](#pi--di-artifacts) |
| ADR / design doc / RFC | → [Architecture Decisions](#architecture-decisions) |
| Release notes / changelog | → [Release Notes](#release-notes) |
| Tech debt documentation | → [Tech Debt](#tech-debt) |

For all templates, see `references/templates.md`.
For anti-patterns and quality guidance, see `references/patterns.md`.

---

## Core Principle: Two Perspectives

Every artifact has two sides. Always clarify which perspective the user needs:

**Requesting perspective** (PM/stakeholder — "here's what we need done"):
- Describes the problem and constraints, not the solution
- Defines "what" and "why," leaves "how" to the team
- Includes acceptance criteria, success metrics, priority rationale

**Reporting perspective** (developer/team — "here's what was done"):
- Documents decisions, trade-offs, and context future maintainers need
- Code shows *what*; documentation shows *why*
- Includes root cause, alternatives considered, regression risk, follow-ups

When the user's intent is ambiguous, ask: "Are you defining what needs to be done, or documenting what was done?"

---

## Single PR Documentation

### Gather First
Before writing, examine:
1. `git diff` or staged changes — understand what changed
2. Related tickets — ask for ticket IDs to anchor the documentation
3. Test changes — what was tested and how

### Structure
```markdown
## What
[1-2 sentence summary]

## Why
[Link to ticket. Business/technical context for why this change is needed now.]

## How
[Technical approach. Key design decisions. Alternatives considered.]

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing: [describe scenario]

## Breaking Changes
[List any breaking changes to APIs, configs, schemas]

## Related
- Ticket: [PROJ-XXX]
- Related PRs: [#123, #124]
```

<example>
A filled-in "Why" and "How" for a change that replaces a polling loop with a push subscription:

```markdown
## Why
Sync status lagged by up to 30 s because the client polled every 30 s (ticket link). Support
tickets about "stale status" doubled after the team-sync feature launched.

## How
Subscribe to the server's status stream and drop the poll timer. Kept the poll as a fallback
behind `useStatusStream` for one release so a stream outage degrades to the old behavior
rather than to no updates. Rejected long-polling: it would have kept the per-request overhead
that motivated the change.
```

Correct because every sentence answers "why this, why now", the diff already shows the timer
removal so it is not restated, and the ticket and the feature flag are the ones in the change,
not invented.
</example>

---

## Layered PR Documentation

For code being ported into a larger codebase where reviewers have **zero prior context**. Read `references/templates.md` § "Layered PR Template" for the full structure.

### Required Sections
1. **Title with Ticket ID** — `TICKET-ID: ComponentName`
2. **The Layer** — one sentence on this component's single responsibility
3. **Architecture Diagram** — ASCII stack showing where this fits, marking tickets
4. **What Existed Before** — old code + problem/consequence table
5. **Design Rationale** — per-decision subsections with code examples and "why"
6. **What This Enables** — specific downstream capabilities unlocked
7. **Patterns Established** — table showing pattern propagation
8. **Files in This PR** — tree with inline role comments
9. **Looking Ahead** — specific future tickets/PRs

### Before Writing, Gather
```
1. Ticket ID — anchor for the documentation
2. Old code — what's being replaced (paste or point to file)
3. Stack position — what depends on it, what it depends on
4. Key decisions — tradeoffs or "why X not Y" questions
```

---

## Work Summarization

### For Sprint/Release Summaries
1. Analyze the commit range: `git log --oneline --no-merges <start>..<end>`
2. Identify architectural signals (new dirs, schema changes, API changes, config changes, CI changes) vs noise (formatting, lockfiles, auto-generated code)
3. Apply the "So What?" test — every item answers *why it matters*, not just *what changed*
4. Categorize: Features, Bug Fixes, Performance, Security, Infrastructure, Breaking Changes, Deprecations

### For Multi-PR Work Streams
Create a tracking summary:
```markdown
## Overview
[What this work stream delivers. Link to epic.]

## PR Sequence
| # | PR | Description | Status | Dependencies |
|---|-----|-------------|--------|--------------|
| 1 | #100 | Database migration | Merged | None |
| 2 | #101 | Data access layer | Merged | #100 |

## Key Architecture Decisions
[Brief or link to ADRs]

## Current Status
[What's done, what's next, blockers]
```

### Layered Summarization
Produce summaries at multiple granularities:
- **Executive** — lead with business outcomes ("reduced checkout latency by 40%")
- **Engineering** — lead with architectural changes ("migrated to event-driven processing")
- **Detailed** — full categorized changelog

---

## User Stories

### INVEST Criteria
| Criterion | Test |
|---|---|
| **I**ndependent | Can you re-order this in the backlog without breaking anything? |
| **N**egotiable | Is there room for the team to propose implementation approaches? |
| **V**aluable | Can you explain who benefits and how? |
| **E**stimable | Does the team have enough to size it? |
| **S**mall | Fits in one sprint? |
| **T**estable | Can you write a test for it now? |

### Requesting Perspective

The requesting form is the "As a / I want / So that" statement, Gherkin acceptance criteria
(Given / When / Then), context, design link, and priority rationale. Read
`references/templates.md#user-story--requesting` for the full template, including open questions and
the Definition of Ready checklist.

### Reporting Perspective (Completion Notes)

Completion notes cover the implementation summary, technical decisions, files changed, test
coverage, regression risk, and follow-up items. Read `references/templates.md#user-story--reporting`
for the template.

### Story Splitting Techniques
1. By workflow steps (happy path vs edge cases vs errors)
2. By business rule variation
3. By data variation (different input types)
4. By interface (web vs mobile vs API)
5. By operation (CRUD)
6. By performance ("make it work" then "make it fast")
7. Spike + implementation
8. By acceptance criteria clusters

---

## Epics

### Requesting Perspective

An epic definition states the business objective, target users, a hypothesis ("We believe
[capability] for [users] will result in [outcome]. We'll know when [measurable signal]"), in and
out of scope, stories, definition of done, success metrics (current to target), dependencies, and
risks with mitigations. Read `references/templates.md#epic--requesting` for the template.

### Reporting Perspective (Completion Summary)

A completion summary covers the outcome against original scope, metrics (baseline, current, target),
deferred or descoped items and where they are tracked, key technical decisions, lessons learned,
and documentation updated. Read `references/templates.md#epic--reporting` for the template.

---

## Bugs

### Requesting Perspective

A bug report has a title of the form "[Component] — [Symptom in user terms]", severity (Critical /
Major / Minor / Trivial), priority (P0 (immediate) / P1 (next sprint) / P2 (backlog) / P3 (nice to
fix)), environment, steps to reproduce, expected and actual results (exact error messages),
frequency (Always / Intermittent (~X%) / Once), impact (users affected, revenue impact, workaround),
and logs or evidence. Read `references/templates.md#bug--requesting` for the template.

### Severity/Priority Matrix
|  | High Impact | Low Impact |
|---|---|---|
| **High Frequency** | P0 — fix immediately | P1 — fix this sprint |
| **Low Frequency** | P1 — fix this sprint | P2/P3 — backlog |

Note: Severity (how bad) and Priority (how soon) are separate axes. Low-severity, high-priority is real (cosmetic bug on homepage = brand impact).

### Reporting Perspective (Resolution Notes)

Resolution notes cover root cause, the fix, why this fix over the alternatives, verification, and
prevention (a systemic change such as a new test or monitoring). For a root cause analysis, use the
5 Whys chain ending in a systemic root cause and a list of corrective actions: the bug fix, a
follow-up story for the systemic fix, and a monitoring or alerting addition. Read
`references/templates.md#bug--reporting` for both templates.

---

## Tasks & Spikes

### Technical Task

A task has a title of the form "[Verb] [Object] [Context]", a type (Task / Sub-task / Tech Debt /
Infrastructure), a description linked to the parent, a technical approach with key decisions
pre-made and files expected to change, verifiable acceptance criteria, dependencies, and an
estimate. Read `references/templates.md#technical-task` for the template.

### Spike

A spike has the title "Spike — [Question to Answer]", a timebox, context (what decision depends on
the outcome), numbered questions, and an approach; after the spike it gains an outcome section with
findings per question, a recommendation, unknowns remaining, follow-up stories, and artifacts. Read
`references/templates.md#spike` for the template.

---

## PI & DI Artifacts

### PI Objectives (SAFe)

A PI plan names the PI number and theme, duration (8-12 weeks), and team; lists objectives with
business value (1-10), iterations, and committed or uncommitted status; records dependencies in both
directions and risks in ROAM categories (Resolved: addressed; Owned: someone managing; Accepted:
consciously living with; Mitigated: plan in place); and ends with a confidence vote (team average
1-5; below 3 triggers re-planning). Read `references/templates.md#pi-objectives` for the template
and the business value scoring scale.

### Iteration Goals (DI)

An iteration plan states the sprint dates and capacity, goals tied to PI objectives, planned work
(ticket, title, points, owner, goal number), velocity of the last 3 sprints against this sprint's
plan, carry-over with reasons, and risks or blockers with mitigations. Read
`references/templates.md#iteration-goals` for the template.

---

## Architecture Decisions

### ADR — Nygard Format (lightweight)

Status, Context, Decision, Consequences. Read `references/templates.md#adr--nygard` for the template.

### ADR — MADR Format (structured)

Status, Context and Problem Statement, Decision Drivers, Considered Options, Decision Outcome with
positive and negative consequences, and pros and cons per option. Read
`references/templates.md#adr--madr` for the template.

### Design Doc / RFC
Read `references/templates.md` § "Design Doc Template" for the full Google-style structure: Objective, Background, Detailed Design, Alternatives, Cross-cutting Concerns, Rollout Plan.

**Key principle**: ADRs are immutable. Don't edit old ADRs — supersede them with new ones. Store in repo (`docs/adr/`), numbered sequentially.

---

## Release Notes

### Three-Tier Pattern
1. **Highlights** (2-5 bullets) — most impactful user-facing changes, plain language
2. **Full Changelog** (categorized) — every user-visible change by type
3. **Technical Notes** — breaking changes, migration guides, known issues, dependency updates

### Categories (Keep a Changelog format)
- **Added** — new features
- **Changed** — changes in existing functionality
- **Deprecated** — soon-to-be-removed features
- **Removed** — removed features
- **Fixed** — bug fixes
- **Security** — vulnerability patches

### Conventional Commits
If the repo uses Conventional Commits (`feat:`, `fix:`, `docs:`, etc.), leverage them for automated draft generation, then curate manually.

---

## Tech Debt

A tech debt entry (`TD-[number]: [Title]`) records type (Code / Architecture / Test / Documentation
/ Infrastructure), severity (High / Medium / Low), age, and owner; the description, impact, cost of
delay, remediation plan, estimated effort; and a trigger, the event that should cause
prioritization (for example, "when we add a 4th payment provider"). Read
`references/templates.md#tech-debt-entry` for the template.

---

## Writing Style

- **Narrative over reference**: Write like explaining to a colleague, not documenting an API
- **Zero-context assumption**: Explain everything; don't assume familiarity
- **Show code**: Include actual snippets from both old and new implementations
- **Every "why" connects forward**: Design decisions show downstream benefits
- **Tables for comparisons**: Use tables for approach comparisons, problem/consequence lists
- **Diagrams for architecture**: ASCII art for stack diagrams and data flow
- **The "So What?" test**: Every summary item answers why it matters
- **Plain statement over mannered prose**: mannered prose substitutes metaphor and flourish for
  direct statement ("a dial worth turning" for "a parameter worth varying"). It makes the reader
  work harder so the writer can perform; when a literal phrase exists, use it
- **Mark quotations**: a passage taken verbatim from a ticket, a commit message, a diff, or a
  source document is marked as a quotation and attributed; everything else is in your own words,
  so the reader can tell the source's claim from your summary of it

---

## Quality Checklist

Before delivering any artifact:

- [ ] Correct perspective identified (requesting vs reporting)
- [ ] Ticket/epic/PI IDs included where applicable
- [ ] Acceptance criteria are testable (not vague)
- [ ] "Why" is explained, not just "what"
- [ ] Alternatives considered are documented (for decisions)
- [ ] Impact is quantified where possible (users affected, metrics moved)
- [ ] A reader with zero context can understand the artifact's purpose
- [ ] Anti-patterns avoided (see `references/patterns.md`)

## Boundaries

| Need | Skill |
|---|---|
| Deciding what work to do; decomposition and roadmaps | `planner` |
| Judging a change once written | `code-review` |
| Commit scoping, branching, and delivery flow | `engineering-practices` |
| Doc comments and API contracts in source | `swift` |
| The repository's ticket, branch, and PR conventions | `project-conventions` |
| Architecture decisions about infrastructure | `system-architect` |

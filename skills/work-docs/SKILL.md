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

Write documentation for software engineering work, from one PR to a program increment. Each artifact has two perspectives: **requesting** (what needs to be done) and **reporting** (what was done).

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

Read the `references/templates.md` section named under each artifact below when you write that artifact; the sections below give only its required content.
Read `references/patterns.md` when you summarize a commit range (git commands, signal and noise filters) or when you check an artifact against the anti-patterns for its type.

---

## Core Principle: Two Perspectives

Classify each artifact as one of two perspectives before writing:

**Requesting perspective** (PM or stakeholder: "here is what we need done"):
- Describes the problem and constraints, not the solution.
- Defines "what" and "why"; leaves "how" to the team.
- Includes acceptance criteria, success metrics, and priority rationale.

**Reporting perspective** (developer or team: "here is what was done"):
- Documents the decisions, trade-offs, and context that future maintainers need.
- Explains *why*; the code already shows *what*.
- Includes root cause, alternatives considered, regression risk, and follow-ups.

When the request does not show the perspective, ask: "Are you defining what needs to be done, or documenting what was done?" If you cannot ask, choose reporting when a diff, commit range, or merged work is given, otherwise requesting, and state the choice.

---

## Single PR Documentation

### Gather First
Before writing, read:
1. `git diff` or the staged changes.
2. When the repository uses ticket IDs, the ticket ID, from the branch name or commit messages (see `project-conventions`). Ask the user only if neither has one; if no one can answer, omit the ID and say so. When the repository does not use ticket IDs, omit the ID.
3. The test changes: what was tested and how.

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

Use for code ported into a larger codebase where the reviewers have **no prior context**. Template: `references/templates.md#layered-pr-template`.

### Required Sections
1. **Title with Ticket ID**: `TICKET-ID: ComponentName`
2. **The Layer**: one sentence on this component's single responsibility
3. **Architecture Diagram**: ASCII stack showing where this fits, marking tickets
4. **What Existed Before**: old code + problem/consequence table
5. **Design Rationale**: per-decision subsections with code examples and "why"
6. **What This Enables**: the downstream capabilities this PR unlocks
7. **Patterns Established**: table showing pattern propagation
8. **Files in This PR**: tree with inline role comments
9. **Looking Ahead**: the future tickets or PRs, named

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
1. Read the commit range: `git log --oneline --no-merges <start>..<end>`
2. Separate architectural signals (new directories, schema, API, config, and CI changes) from noise (formatting, lockfiles, generated code).
3. Apply the "So What?" test: each item states why it matters, not only what changed.
4. Categorize: Features, Bug Fixes, Performance, Security, Infrastructure, Breaking Changes, Deprecations.

### For Multi-PR Work Streams
Write a tracking summary (full template: `references/templates.md#multi-pr-tracking-issue`):
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
Write one level per audience:
- **Executive**: lead with business outcomes ("reduced checkout latency by 40%").
- **Engineering**: lead with architectural changes ("migrated to event-driven processing").
- **Detailed**: the full categorized changelog.

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

Content: the "As a / I want / So that" statement, Gherkin acceptance criteria (Given / When / Then), context, design link, and priority rationale. Template, with open questions and the Definition of Ready checklist: `references/templates.md#user-story--requesting`.

### Reporting Perspective (Completion Notes)

Content: implementation summary, technical decisions, files changed, test coverage, regression risk, and follow-up items. Template: `references/templates.md#user-story--reporting`.

### Story Splitting Techniques
1. By workflow steps (happy path, edge cases, errors)
2. By business rule variation
3. By data variation (different input types)
4. By interface (web, mobile, API)
5. By operation (CRUD)
6. By performance ("make it work", then "make it fast")
7. Spike + implementation
8. By acceptance criteria clusters

---

## Epics

### Requesting Perspective

Content: business objective, target users, a hypothesis ("We believe [capability] for [users] will result in [outcome]. We'll know when [measurable signal]"), in and out of scope, stories, definition of done, success metrics (current to target), dependencies, and risks with mitigations. Template: `references/templates.md#epic--requesting`.

### Reporting Perspective (Completion Summary)

Content: outcome against the original scope, metrics (baseline, current, target), deferred or descoped items and where they are tracked, key technical decisions, lessons learned, and documentation updated. Template: `references/templates.md#epic--reporting`.

---

## Bugs

### Requesting Perspective

Content:
- Title: "[Component] — [Symptom in user terms]"
- Severity: Critical / Major / Minor / Trivial
- Priority: P0 (immediate) / P1 (next sprint) / P2 (backlog) / P3 (nice to fix)
- Environment, steps to reproduce, expected and actual results (exact error messages)
- Frequency: Always / Intermittent (~X%) / Once
- Impact: users affected, revenue impact, workaround
- Logs or evidence

Template: `references/templates.md#bug--requesting`.

### Severity/Priority Matrix
|  | High Impact | Low Impact |
|---|---|---|
| **High Frequency** | P0 — fix immediately | P1 — fix this sprint |
| **Low Frequency** | P1 — fix this sprint | P2/P3 — backlog |

Set severity (how bad) and priority (how soon) separately. A low-severity bug can have high priority, for example a cosmetic bug on the homepage.

### Reporting Perspective (Resolution Notes)

Content: root cause, the fix, why this fix over the alternatives, verification, and prevention (a systemic change such as a new test or monitoring). For a root cause analysis, write a 5 Whys chain that ends in a systemic root cause, then the corrective actions: the bug fix, a follow-up story for the systemic fix, and a monitoring or alerting addition. Templates for both: `references/templates.md#bug--reporting`.

---

## Tasks & Spikes

### Technical Task

Content: title "[Verb] [Object] [Context]"; type (Task / Sub-task / Tech Debt / Infrastructure); description linked to the parent; technical approach with the key decisions made and the files expected to change; verifiable acceptance criteria; dependencies; estimate. Template: `references/templates.md#technical-task`.

### Spike

Content: title "Spike — [Question to Answer]"; timebox; context (which decision depends on the outcome); numbered questions; approach. After the spike, add an outcome section: findings per question, recommendation, remaining unknowns, follow-up stories, and artifacts. Template: `references/templates.md#spike`.

---

## PI & DI Artifacts

### PI Objectives (SAFe)

Content:
- PI number and theme, duration (8-12 weeks), team.
- Objectives with business value (1-10), iterations, and committed or uncommitted status.
- Dependencies in both directions.
- Risks in ROAM categories: Resolved (addressed), Owned (someone manages it), Accepted (consciously accepted), Mitigated (plan in place).
- Confidence vote: team average 1-5; an average below 3 triggers re-planning.

Template, with the business value scoring scale: `references/templates.md#pi-objectives`.

### Iteration Goals (DI)

Content: sprint dates and capacity; goals tied to PI objectives; planned work (ticket, title, points, owner, goal number); velocity of the last 3 sprints against this sprint's plan; carry-over with reasons; risks or blockers with mitigations. Template: `references/templates.md#iteration-goals`.

---

## Architecture Decisions

### ADR — Nygard Format (lightweight)

Content: Status, Context, Decision, Consequences. Template: `references/templates.md#adr--nygard`.

### ADR — MADR Format (structured)

Content: Status, Context and Problem Statement, Decision Drivers, Considered Options, Decision Outcome with positive and negative consequences, and pros and cons per option. Template: `references/templates.md#adr--madr`.

### Design Doc / RFC

Content (Google style): Objective, Background, Detailed Design, Alternatives, Cross-cutting Concerns, Rollout Plan. Template: `references/templates.md#design-doc--rfc`.

To change a decision, write a new ADR that supersedes the old one. Do not edit an accepted ADR, except to set its Status to "Superseded by ADR-XXXX" when a new ADR replaces it. Store ADRs in the repository (`docs/adr/`, unless the repository already stores them elsewhere), numbered sequentially.

---

## Release Notes

Template: `references/templates.md#release-notes`.

### Three-Tier Pattern
1. **Highlights** (2-5 bullets): the most impactful user-facing changes, in plain language.
2. **Full Changelog** (categorized): each user-visible change, by type.
3. **Technical Notes**: breaking changes, migration guides, known issues, dependency updates.

### Categories (Keep a Changelog format)
- **Added**: new features
- **Changed**: changes in existing functionality
- **Deprecated**: features to be removed
- **Removed**: removed features
- **Fixed**: bug fixes
- **Security**: vulnerability patches

### Conventional Commits
If the repository uses Conventional Commits (`feat:`, `fix:`, `docs:`, etc.), generate the draft from them, then edit the draft by hand.

---

## Tech Debt

Content of an entry `TD-[number]: [Title]`: type (Code / Architecture / Test / Documentation / Infrastructure), severity (High / Medium / Low), age, owner; description, impact, cost of delay, remediation plan, estimated effort; and a trigger, the event that makes the entry a priority (for example, "when we add a 4th payment provider"). Template: `references/templates.md#tech-debt-entry`.

---

## Writing Style

- **Narrative over reference**: write explanatory prose in full sentences, not an API reference list.
- **No assumed context**: assume the reader has not seen the code or the ticket. Define each project-specific term and component on first use.
- **Show code**: when explaining a design decision, include the actual snippets from the old and new implementations.
- **Connect each "why" forward**: state the downstream benefit of each design decision.
- **Tables for comparisons**: approach comparisons, problem/consequence lists.
- **Diagrams for architecture**: ASCII art for stack diagrams and data flow.
- **The "So What?" test**: each summary item states why it matters.
- **Plain statement**: write the literal phrase, not a metaphor or flourish ("a parameter worth varying", not "a dial worth turning").
- **Mark quotations**: mark a passage taken verbatim from a ticket, a commit message, a diff, or a source document as a quotation, and attribute it. Write everything else in your own words.

---

## Quality Checklist

Before delivering an artifact, check:

- [ ] Correct perspective identified (requesting vs reporting)
- [ ] Ticket/epic/PI IDs included where the repository or user provides them
- [ ] Acceptance criteria are testable
- [ ] "Why" is explained, not only "what"
- [ ] Alternatives considered are documented (for decisions)
- [ ] Impact is quantified where data exists (users affected, metrics moved)
- [ ] A reader with no context can understand the artifact's purpose
- [ ] Anti-patterns for the artifact type avoided (`references/patterns.md`)

## Boundaries

| Need | Skill |
|---|---|
| Deciding what work to do; decomposition and roadmaps | `planner` |
| Judging a change once written | `code-review` |
| Commit scoping, branching, and delivery flow | `engineering-practices` |
| Doc comments and API contracts in source | `swift` |
| The repository's ticket, branch, and PR conventions | `project-conventions` |
| Architecture decisions about infrastructure | `system-architect` |

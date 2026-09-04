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
```
As a [persona],
I want [capability],
So that [benefit].

Acceptance Criteria (Gherkin):
  Given [precondition]
  When [action]
  Then [expected outcome]

Context: [business context, customer quotes, data]
Design: [link to Figma/mockup]
Priority Rationale: [why now vs other backlog items]
```

### Reporting Perspective (Completion Notes)
```
Implementation Summary: [approach taken]
Technical Decisions: [chose A over B because ...]
Files Changed: [key files or link to PR]
Test Coverage: [unit/integration/E2E status]
Regression Risk: [areas that could be affected]
Follow-up Items: [PROJ-XXX: deferred tech debt]
```

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
```
EPIC: [Name]

Business Objective: [what business goal?]
Target Users: [who benefits?]
Hypothesis: We believe [capability] for [users] will result in [outcome].
  We'll know when [measurable signal].

Scope:
  In: [capabilities]
  Out: [explicitly excluded]

Stories: [numbered list with brief descriptions]
Definition of Done: [all stories accepted, tests passing, docs updated, demo done, metrics baselined]
Success Metrics: [metric: current → target]
Dependencies: [other epics/teams/systems]
Risks: [risk: mitigation]
```

### Reporting Perspective (Completion Summary)
```
Outcome: [delivered vs original scope]
Metrics: [metric: baseline → current (target was X)]
Deferred/Descoped: [items and why, where tracked]
Key Technical Decisions: [decision: context, options, rationale]
Lessons Learned: [what went well, what we'd change]
Documentation Updated: [links]
```

---

## Bugs

### Requesting Perspective
```
TITLE: [Component] — [Symptom in user terms]

Severity: Critical / Major / Minor / Trivial
Priority: P0 (immediate) / P1 (next sprint) / P2 (backlog) / P3 (nice to fix)

Environment:
  - App version: [version/SHA]
  - OS/Browser: [e.g., Chrome 120 on macOS 14.2]
  - Environment: [prod / staging / local]

Steps to Reproduce:
  1. Navigate to [URL]
  2. Click [element]
  3. Enter [specific input]
  4. Submit

Expected: [what should happen]
Actual: [what happens, exact error messages]
Frequency: Always / Intermittent (~X%) / Once
Impact: [users affected, revenue impact, workaround?]
Logs/Evidence: [stack trace, screenshot, video, HAR]
```

### Severity/Priority Matrix
|  | High Impact | Low Impact |
|---|---|---|
| **High Frequency** | P0 — fix immediately | P1 — fix this sprint |
| **Low Frequency** | P1 — fix this sprint | P2/P3 — backlog |

Note: Severity (how bad) and Priority (how soon) are separate axes. Low-severity, high-priority is real (cosmetic bug on homepage = brand impact).

### Reporting Perspective (Resolution Notes)
```
Root Cause: [technical explanation]
Fix: [what was changed]
Why This Fix: [alternatives considered, why rejected]
Verification: [reproduced in X, verified in Y, regression suite passed]
Prevention: [systemic change — new test, monitoring, etc.]
```

### Root Cause Analysis (5 Whys)
```
Problem: [symptom]
Why 1: [immediate cause]
Why 2: [cause of cause]
...
Root Cause: [systemic issue]
Corrective Actions:
  1. [this bug fix]
  2. [follow-up story for systemic fix]
  3. [monitoring/alerting addition]
```

---

## Tasks & Spikes

### Technical Task
```
TITLE: [Verb] [Object] [Context]

Type: Task / Sub-task / Tech Debt / Infrastructure
Description: [what and why, link to parent story/epic]
Technical Approach: [step-by-step plan, key decisions pre-made, files expected to change]
Acceptance Criteria:
  - [ ] [specific, verifiable criterion]
  - [ ] Tests pass
  - [ ] No performance regression (threshold: X)
Dependencies: [blocked by / blocks]
Estimate: [points or t-shirt size]
```

### Spike
```
TITLE: Spike — [Question to Answer]
Timebox: [X days / points]
Context: [why investigate? what decision depends on outcome?]
Questions: [numbered list of specific questions]
Approach: [prototype / PoC / vendor eval / benchmarking]

--- OUTCOME (after spike) ---
Findings: [answers to each question]
Recommendation: [what to do based on findings]
Unknowns Remaining: [what we still don't know]
Follow-up Stories: [links]
Artifacts: [prototype repo / design doc / benchmark results]
```

---

## PI & DI Artifacts

### PI Objectives (SAFe)
```
PI [Number]: [Theme]
Duration: [start] — [end] (8-12 weeks)
Team: [name]

Objectives:
  # | Objective | Business Value (1-10) | Iterations | Committed?
  1 | [description] | 8 | 1-2 | Committed
  2 | [description] | 6 | 2-3 | Committed
  3 | [stretch] | 9 | 3-4 | Uncommitted

Business Value Scoring:
  10 = critical to business viability this PI
  7-9 = important strategic value
  4-6 = meaningful but not urgent
  1-3 = minor or speculative

Dependencies:
  - [our team] depends on [other team] for [what] by [iteration]

Risks (ROAM):
  - Resolved: [addressed]
  - Owned: [someone managing]
  - Accepted: [consciously living with]
  - Mitigated: [plan in place]

Confidence Vote: [1-5 team average. <3 triggers re-planning]
```

### Iteration Goals (DI)
```
Iteration: Sprint N ([start] — [end])
Capacity: [X points / Y person-days]

Goals:
  1. [goal tied to PI objective]
  2. [goal]

Planned Work:
  | Ticket | Title | Points | Owner | Goal # |
  |--------|-------|--------|-------|--------|

Velocity: last 3 sprints avg [X], this sprint planned [Y]
Carry-over: [tickets and reasons]
Risks/Blockers: [risk and mitigation]
```

---

## Architecture Decisions

### ADR — Nygard Format (lightweight)
```markdown
# ADR [number]: [Title]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## Context
[What forces are at play? Technical, political, social, project-specific.]

## Decision
[What change are we making?]

## Consequences
[What becomes easier? Harder? What are the trade-offs?]
```

### ADR — MADR Format (structured)
```markdown
# [Title]

## Status
[Accepted | Proposed | Rejected | Deprecated | Superseded]

## Context and Problem Statement
[Why are we making this decision?]

## Decision Drivers
- [e.g., performance requirement]
- [e.g., team expertise]

## Considered Options
1. [Option 1]
2. [Option 2]

## Decision Outcome
Chosen: "[Option X]", because [justification].

### Positive Consequences
- [benefit]

### Negative Consequences
- [cost]

## Pros and Cons of the Options
### Option 1
- Good, because [...]
- Bad, because [...]
```

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

```
# TD-[number]: [Title]

Type: Code / Architecture / Test / Documentation / Infrastructure
Severity: High / Medium / Low
Age: [when introduced]
Owner: [team]

Description: [what is the debt? why does it exist?]
Impact: [how does it slow us down?]
Cost of Delay: [what happens if we don't fix it? does it worsen?]
Remediation Plan: [high-level approach]
Estimated Effort: [points or t-shirt]
Trigger: [event that should cause prioritization, e.g., "when we add a 4th payment provider"]
```

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

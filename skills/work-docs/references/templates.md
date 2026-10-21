# Work Documentation Templates

Complete templates for all artifact types. Each template shows the full structure — adapt sections to fit context, don't pad empty sections.

---

## Table of Contents
1. [Layered PR Template](#layered-pr-template)
2. [User Story — Requesting](#user-story--requesting)
3. [User Story — Reporting](#user-story--reporting)
4. [Epic — Requesting](#epic--requesting)
5. [Epic — Reporting](#epic--reporting)
6. [Bug — Requesting](#bug--requesting)
7. [Bug — Reporting](#bug--reporting)
8. [Technical Task](#technical-task)
9. [Spike](#spike)
10. [PI Objectives](#pi-objectives)
11. [Iteration Goals](#iteration-goals)
12. [ADR — MADR](#adr--madr)
13. [ADR — Nygard](#adr--nygard)
14. [Design Doc / RFC](#design-doc--rfc)
15. [Tech Debt Entry](#tech-debt-entry)
16. [Multi-PR Tracking Issue](#multi-pr-tracking-issue)
17. [Release Notes](#release-notes)

---

## Layered PR Template

For code ported into a larger codebase where reviewers have zero prior context.

```markdown
# {TICKET-ID}: {ComponentName}

## The {Layer Name} Layer

{One sentence summarizing the component's single responsibility.}

---

## Why Start Here?

{Context for why this component is being built now, what depends on it.}

┌─────────────────────────────────────────────────────────┐
│  {Layer N}        ({description})                       │
├─────────────────────────────────────────────────────────┤
│  {Layer N-1}      ({description})                       │  ← {FUTURE-TICKET}
├─────────────────────────────────────────────────────────┤
│  {This Layer}     ({description})                       │  ← {TICKET-ID} (this ticket)
├─────────────────────────────────────────────────────────┤
│  {Layer Below}    ({description})                       │
└─────────────────────────────────────────────────────────┘

---

## What Existed Before

The codebase had `{OldComponentName}`:

\```{language}
{Old code snippet — abbreviated if long}
\```

| Problem | Consequence |
|---------|-------------|
| {Problem 1} | {Impact on users/system} |
| {Problem 2} | {Impact on users/system} |

---

## The Design Rationale

### {Decision 1 Name}

{What was decided.}

\```{language}
{Code example showing the new approach}
\```

**Why this approach?**
- {Reason connecting to downstream benefit}

### {Why X Over Y?}

| Requirement | {Option A} | {Option B} |
|-------------|-----------|-----------|
| {Req 1} | {How A handles} | {How B handles} |

{Explanation of choice.}

---

## What This Enables

With {ComponentName} in place, {downstream component} can:

1. **{Capability}** — {Explanation}
2. **{Capability}** — {Explanation}

---

## Patterns Established

| Pattern | Instantiation Here | Applied Later |
|---------|-------------------|---------------|
| {Pattern} | `{TypeName}` | {Future components} |

---

## Files in This PR

\```
Sources/
├── {Component}.swift              # {Brief role}
├── {Component}+{Extension}.swift  # {Brief role}

Tests/
├── {Component}Tests.swift
\```

---

## Looking Ahead

**{NEXT-TICKET} ({NextComponent})** builds on this:
- {How it uses this component}
- {Patterns it inherits}
```

---

## User Story — Requesting

```markdown
**As a** {persona/role},
**I want** {capability/action},
**So that** {benefit/outcome}.

### Context
{Business context, customer quotes, data supporting the need. Link to epic.}

### Acceptance Criteria

**Scenario: {Happy path}**
Given {precondition}
When {action}
Then {expected outcome}

**Scenario: {Edge case}**
Given {precondition}
When {action}
Then {expected outcome}

### Design
{Link to Figma/mockup or description}

### Open Questions
- {Question for team to clarify during refinement}

### Priority Rationale
{Why this is more important than other backlog items right now}

### Definition of Ready Checklist
- [ ] Acceptance criteria unambiguous
- [ ] Dependencies identified
- [ ] UX/UI designs attached (if applicable)
- [ ] Edge cases enumerated
- [ ] Estimated by team
- [ ] Fits in single sprint
```

---

## User Story — Reporting

```markdown
### Implementation Summary
{Brief description of approach taken}

### Technical Decisions
- Chose {approach A} over {approach B} because {reason}
- {Any deviation from original plan and why}

### Files Changed
{Key files/modules, or link to PR}

### Test Coverage
- [x] Unit tests: {description}
- [x] Integration tests: {description}
- [ ] E2E tests: {deferred to PROJ-XXX / not applicable}

### Regression Risk
{Areas that could be affected by this change}

### Follow-up Items
- {PROJ-XXX}: {Tech debt or enhancement deferred}
```

---

## Epic — Requesting

```markdown
# EPIC: {Name}

## Business Objective
{What business goal does this epic serve?}

## Target Users/Personas
{Who benefits?}

## Hypothesis
We believe that {capability} for {users} will result in {outcome}.
We will know this is true when {measurable signal}.

## Scope

### In Scope
- {Capability 1}
- {Capability 2}

### Out of Scope
- {Explicitly excluded capability and why}

## Stories
1. {Story title} — {brief description}
2. {Story title} — {brief description}
...

## Definition of Done
- [ ] All stories completed and accepted
- [ ] Integration tests passing
- [ ] Documentation updated
- [ ] Stakeholder demo completed
- [ ] Feature flag enabled for 100% of users
- [ ] Success metrics baselined

## Success Metrics
| Metric | Current | Target |
|--------|---------|--------|
| {Metric 1} | {value} | {value} |

## Dependencies
- {Other epic/team/system}: {what we need from them}

## Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| {Risk 1} | {H/M/L} | {H/M/L} | {plan} |
```

---

## Epic — Reporting

```markdown
# EPIC Completion: {Name}

## Outcome
{What was actually delivered vs. original scope}

## Metrics
| Metric | Baseline | Current | Target |
|--------|----------|---------|--------|
| {Metric 1} | {val} | {val} | {val} |

## Deferred / Descoped
| Item | Reason | Tracked In |
|------|--------|-----------|
| {Item} | {Why deferred} | {PROJ-XXX} |

## Key Technical Decisions
| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| {Decision} | {A, B, C} | {B} | {why} |

## Lessons Learned

### What Went Well
- {positive}

### What We'd Do Differently
- {improvement}

## Documentation Updated
- {Link to updated docs, runbooks, architecture diagrams}
```

---

## Bug — Requesting

```markdown
## {Component} — {Symptom in user terms}

**Severity:** {Critical / Major / Minor / Trivial}
**Priority:** {P0 / P1 / P2 / P3}

### Environment
- Application version: {version or commit SHA}
- OS/Browser: {e.g., Chrome 120 on macOS 14.2}
- Environment: {production / staging / local}
- Account/tenant: {if relevant}
- Feature flags: {if relevant}

### Steps to Reproduce
1. Navigate to {URL}
2. Click {element}
3. Enter {specific input}
4. Submit

### Expected Behavior
{What should happen}

### Actual Behavior
{What actually happens. Include exact error messages.}

### Frequency
{Always / Intermittent (~X%) / Once}

### Impact
{Users affected, revenue impact, workaround availability}

### Evidence
{Stack trace, screenshot, video, HAR file — attach or paste}

### Workaround
{If one exists}
```

---

## Bug — Reporting

```markdown
## Resolution: {Bug Title}

### Root Cause
{Technical explanation of why the bug occurred}

### Fix Description
{What was changed and why}

### Why This Fix
{Alternatives considered and why they were rejected}

### Verification
- Reproduced in: {environment}
- Fix verified in: {environment}
- Regression suite: {passed/failed — details}

### Prevention
{Systemic change that prevents this class of bug:}
- {New test added}
- {Monitoring/alerting added}
- {Process change}

### Root Cause Analysis (5 Whys)
1. Why? {immediate cause}
2. Why? {deeper cause}
3. Why? {deeper cause}
4. Why? {deeper cause}
5. Why? {root systemic issue}

**Corrective Actions:**
1. {This bug fix}
2. {Follow-up: PROJ-XXX}
3. {Monitoring: PROJ-YYY}
```

---

## Technical Task

```markdown
## {Verb} {Object} {Context}

**Type:** Task / Sub-task / Tech Debt / Infrastructure
**Parent:** {Link to story/epic}

### Description
{What needs to be done and why}

### Technical Approach
1. {Step 1}
2. {Step 2}
3. {Step 3}

**Key decisions pre-made:**
- {Decision and rationale}

**Files/modules expected to change:**
- {file or module}

### Acceptance Criteria
- [ ] {Specific, verifiable criterion}
- [ ] Tests pass (unit + integration)
- [ ] No performance regression (threshold: {X})
- [ ] Documentation updated (if applicable)

### Dependencies
- Blocked by: {PROJ-XXX}
- Blocks: {PROJ-YYY}

### Estimate
{Story points or t-shirt size}
```

---

## Spike

```markdown
## Spike — {Question to Answer}

**Timebox:** {X days / X story points}

### Context
{Why investigate this? What decision depends on the outcome?}

### Questions to Answer
1. {Specific question}
2. {Specific question}
3. {Specific question}

### Approach
{Investigation method: prototype, PoC, vendor evaluation, benchmarking, etc.}

---

### Outcome *(filled after spike)*

### Findings
**Q1:** {Answer with evidence}
**Q2:** {Answer with evidence}
**Q3:** {Answer with evidence}

### Recommendation
{What should we do based on findings?}

### Risks/Unknowns Remaining
- {What we still don't know}

### Follow-up Stories Created
- {PROJ-XXX}: {description}

### Artifacts
- {Link to prototype repo / design doc / benchmark results}
```

---

## PI Objectives

```markdown
# PI {Number}: {Theme/Name}

**Duration:** {start date} — {end date}
**Team:** {name}

## PI Objectives

| # | Objective | BV (1-10) | Iterations | Status |
|---|-----------|-----------|------------|--------|
| 1 | {description} | 8 | 1-2 | Committed |
| 2 | {description} | 6 | 2-3 | Committed |
| 3 | {stretch goal} | 9 | 3-4 | Uncommitted |

**Business Value Scoring:**
- 10: Critical to business viability this PI
- 7-9: Important strategic value
- 4-6: Meaningful but not urgent
- 1-3: Minor or speculative

## Dependencies

| We Need | From Team | By Iteration | Status |
|---------|-----------|-------------|--------|
| {what} | {team} | {iter} | {status} |

| Team Needs | From Us | By Iteration | Status |
|-----------|---------|-------------|--------|
| {what} | {team} | {iter} | {status} |

## Risks (ROAM)

| Risk | Category | Owner | Notes |
|------|----------|-------|-------|
| {risk} | Resolved/Owned/Accepted/Mitigated | {person} | {detail} |

## Confidence Vote
Team average: {X}/5 — {proceed / re-plan if <3}
```

---

## Iteration Goals

```markdown
# Sprint {N}: {start} — {end}

**Team:** {name}
**Capacity:** {X story points / Y person-days}

## Goals
1. {Goal tied to PI Objective — e.g., "Complete API integration for payments"}
2. {Goal — e.g., "Reduce P1 bug count from 5 to 2"}

## Planned Work

| Ticket | Title | Points | Owner | Goal # |
|--------|-------|--------|-------|--------|
| {ID} | {title} | {pts} | {person} | {#} |

## Velocity Reference
- Last 3 sprints: {X, Y, Z} (avg: {A})
- This sprint planned: {B}

## Carry-over
| Ticket | Reason |
|--------|--------|
| {ID} | {why it wasn't completed} |

## Risks/Blockers
- {Risk/blocker}: {mitigation}
```

---

## ADR — MADR

```markdown
# ADR-{NNNN}: {Title}

## Status
{Proposed | Accepted | Rejected | Deprecated | Superseded by ADR-XXXX}

## Context and Problem Statement
{Why are we making this decision? What is the problem or force driving it?}

## Decision Drivers
- {Driver 1: e.g., performance requirement of <200ms p99}
- {Driver 2: e.g., team expertise in Go}
- {Driver 3: e.g., 2-week delivery constraint}

## Considered Options
1. {Option 1}
2. {Option 2}
3. {Option 3}

## Decision Outcome
**Chosen:** "{Option X}", because {justification linking to drivers}.

### Positive Consequences
- {benefit}

### Negative Consequences
- {cost or tradeoff}

## Pros and Cons of the Options

### {Option 1}
- Good, because {argument}
- Bad, because {argument}

### {Option 2}
- Good, because {argument}
- Bad, because {argument}

## Links
- Related ADR: {link}
- Design doc: {link}
- PR: {link}
```

---

## ADR — Nygard

Lightweight ADR format.

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

---

## Design Doc / RFC

```markdown
# {Title} Design Doc

**Author:** {name}
**Reviewers:** {names}
**Created:** {date}
**Status:** {Draft | In Review | Approved | Implemented | Obsolete}

## Objective
{1-2 paragraphs: What problem are we solving? Scope?}

## Background
{Context: existing architecture, prior art, terminology}

## Overview
{High-level summary. Reader should understand the gist after this section.}

## Detailed Design

### API Changes
{New or modified APIs with examples}

### Data Model
{Schema changes, data flow diagrams}

### System Architecture
{Component diagram, interaction patterns}

### Key Algorithms / Logic
{Non-obvious logic worth explaining}

## Alternatives Considered

### {Alternative 1}
{Description and why rejected}

### {Alternative 2}
{Description and why rejected}

## Cross-cutting Concerns

### Security
{AuthN/AuthZ, data protection implications}

### Performance
{Latency, throughput, resource projections}

### Observability
{Logging, metrics, tracing additions}

### Rollout Plan
{Feature flags, gradual rollout %, rollback procedure}

## Open Questions
- {Unresolved issue}

## References
- {Link to related docs, ADRs, research}
```

---

## Tech Debt Entry

```markdown
# TD-{number}: {Title}

**Type:** Code / Architecture / Test / Documentation / Infrastructure
**Severity:** High / Medium / Low
**Age:** {when introduced}
**Owner:** {team}

## Description
{What is the debt? Why does it exist?}

## Impact
{How does it slow us down? Increased defect rate? Slower velocity? Onboarding friction?}

## Cost of Delay
{What happens if we don't address it? Does it compound? Concrete scenario.}

## Remediation Plan
{High-level approach}

## Estimated Effort
{Story points or t-shirt size}

## Trigger
{What event should cause prioritization — e.g., "when we add a 4th payment provider" or "when the team onboards 2+ new engineers"}
```

---

## Multi-PR Tracking Issue

```markdown
# {Epic/Feature Name} — Implementation Tracker

## Overview
{What this work stream delivers. Link to epic/design doc.}

## Architecture
{Link to design doc or ADR. Brief summary if no separate doc.}

## PR Sequence

| # | PR | Description | Status | Depends On |
|---|-----|-------------|--------|------------|
| 1 | #{N} | {description} | {Merged/In Review/Draft/Not started} | — |
| 2 | #{N} | {description} | {status} | #1 |

## Rollout Plan
{Feature flags? Gradual rollout? Migration steps?}

## Current Status
*Updated: {date}*
{What's done, what's next, blockers}
```

---

## Release Notes

```markdown
# {Product} {Version} Release Notes — {Date}

## Highlights
- **{Feature}**: {1-sentence plain-language description of most impactful change}
- **{Fix}**: {1-sentence description}

## Added
- {Feature with context on who benefits}

## Changed
- {Behavior change with migration guidance if needed}

## Deprecated
- {Feature}: will be removed in {version}. Use {alternative} instead.

## Removed
- {Feature}: {link to migration guide}

## Fixed
- {Bug}: {what was wrong and what's now correct}

## Security
- {CVE or vulnerability}: {what was patched}

## Technical Notes
- **Breaking Changes**: {list with migration steps}
- **Known Issues**: {issue and workaround}
- **Dependencies**: {notable dependency changes}
```

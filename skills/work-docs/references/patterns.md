# Work Documentation Patterns & Anti-Patterns

Guidance on what makes artifacts good or bad, with examples.

---

## Table of Contents
1. [Anti-Patterns by Artifact Type](#anti-patterns-by-artifact-type)
2. [Good vs Bad — Side by Side](#good-vs-bad--side-by-side)
3. [Frameworks & Methodologies](#frameworks--methodologies)
4. [Bridging Requesting and Reporting](#bridging-requesting-and-reporting)
5. [Git-Based Summarization Techniques](#git-based-summarization-techniques)

---

## Anti-Patterns by Artifact Type

### Bad Tickets
| Anti-Pattern | Description | Fix |
|---|---|---|
| **The Novel** | 2,000 words, no acceptance criteria. Nobody reads it. | Acceptance criteria first, context after. |
| **The One-Liner** | "Fix the login." No context, no STR, no AC. | Minimum: who, what, why, acceptance criteria. |
| **The Solution Prescription** | "Add a Redis cache in front of user table." Prescribes implementation. | Describe the problem. Let the team solve it. |
| **The Hydra** | Grows scope during implementation. "While you're in there..." | New scope = new ticket. Always. |
| **The Orphan** | No link to epic, theme, or objective. Nobody can explain why it exists. | Every ticket connects to a business goal. |
| **Premature Specificity** | Specifies exact DB schema before team has input. | Requirements ≠ design. Separate them. |

### Bad PRs
| Anti-Pattern | Description | Fix |
|---|---|---|
| **The God PR** | 3,000 lines across 50 files. Unreviewable. | Split into focused PRs. One concern per PR. |
| **The Empty Description** | Title: "Updates". Body: empty. | Minimum: what, why, testing, related ticket. |
| **The "Trust Me"** | No tests. "I tested it locally." | Automated tests or documented manual testing. |
| **The Drive-By Refactor** | Feature PR also refactors unrelated module. | Separate refactor PRs from feature PRs. |

### Bad Summaries
| Anti-Pattern | Description | Fix |
|---|---|---|
| **The Commit Log Dump** | Copy-pasting `git log`. | Categorize, curate, add "so what" context. |
| **The Aspirational Summary** | Describes what was planned, not delivered. | Report facts. Separate plan from outcome. |
| **The Jargon Wall** | "Refactored DAG executor to use CPS with trampolining." | Write for your audience. Define terms or simplify. |

### Bad Bug Reports
| Anti-Pattern | Description | Fix |
|---|---|---|
| **"It's broken"** | No specifics on what, where, when, or how. | STR + expected vs actual + environment. |
| **"Fix ASAP"** | No severity assessment, no impact data. | Quantify: users affected, revenue, workaround? |
| **Works on My Machine** | No environment details. | Environment is a required field, not optional. |

---

## Good vs Bad — Side by Side

### User Stories

**Bad:**
> As a user, I want a dashboard.

- Not valuable — what problem does the dashboard solve?
- Not testable — what does "a dashboard" mean?
- Not small — "dashboard" is an epic.

**Good:**
> As a fleet manager,
> I want to see the real-time location of all active vehicles on a map,
> So that I can identify vehicles nearest to a new pickup request.
>
> Acceptance Criteria:
> - Map shows vehicles with status "active" or "en route"
> - Positions update every 30 seconds
> - Clicking a vehicle shows driver name, assignment, and ETA
> - Works on Chrome, Firefox, Safari (latest 2 versions)

### Bug Reports

**Bad:**
> Search is broken

**Good:**
> Search returns 0 results for queries with special characters (', ", &)
>
> Severity: Major. Priority: P1. ~200 users/day affected (error logs).
>
> STR:
> 1. Go to /search
> 2. Type `O'Brien`
> 3. Click Search
> 4. Observe: 0 results + console: `SyntaxError: Unterminated string`

### PR Descriptions

**Bad:**
> Title: "Fixed stuff"
> Body: (empty)

**Good:**
> Title: "Fix SQL injection vulnerability in search query builder"
>
> The search input was interpolated directly into a SQL string. Changed to
> parameterized queries. Added tests for all OWASP injection patterns.
> See ADR-0023 for decision to use prepared statements vs ORM.

### Release Notes

**Bad:**
> Various bug fixes and improvements.

**Good:**
> Fixed: Search now correctly handles special characters in queries
> (', ", &, etc.). Previously, these characters caused empty results
> or errors for ~200 users/day.

---

## Frameworks & Methodologies

### Conventional Commits
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

**Breaking changes:** `!` after type/scope or `BREAKING CHANGE:` footer.
```
feat(api)!: remove deprecated /v1/users endpoint

BREAKING CHANGE: /v1/users removed. Use /v2/users. Migration: [link]
```

Enables: automated changelogs, semantic versioning, readable `git log`.

### Keep a Changelog
Categories: Added, Changed, Deprecated, Removed, Fixed, Security.
Latest version first. Unreleased section at top. Every entry human-readable.

### Shape Up (Basecamp)

**Key concepts for documentation:**
- **Appetite, not estimates**: "We're willing to spend up to 6 weeks" instead of "How long will this take?"
- **Pitches**: Problem, appetite, solution (fat marker sketches), rabbit holes, no-gos.
- **Hill Charts**: "Figuring it out" (uphill) vs "making it happen" (downhill) per scope.
- **Scope Hammering**: Cut scope to fit appetite. Must-haves vs nice-to-haves reassessed continuously.

**Pitch template:**
```
# Pitch: {Title}

## Problem
{Raw problem with real examples}

## Appetite
{Small batch: 1-2 weeks, or Big batch: 6 weeks}

## Solution
{Approach without prescribing every screen. Breadboarding for flows, fat marker sketches for UI.}

## Rabbit Holes
{Technical/design risks that could blow up timeline}

## No-Gos
{Explicitly NOT doing — to keep scope manageable}
```

### Impact Mapping (Gojko Adzic)
Structure: **Goal → Actors → Impacts → Deliverables**

```
Goal: Increase mobile conversion by 20%
├── Actor: New mobile visitor
│   ├── Impact: Reduce signup friction
│   │   ├── Deliverable: Social login
│   │   └── Deliverable: Single-page signup
│   └── Impact: Build trust
│       └── Deliverable: Testimonials on landing page
├── Actor: Returning customer
│   └── Impact: Speed up repeat purchases
│       └── Deliverable: One-tap reorder
```

Connects deliverables to business goals. Prevents "feature factory" mode. Makes scope cuts rational.

### DORA Metrics
| Metric | Elite | Low |
|--------|-------|-----|
| Deployment Frequency | Multiple/day | < once/month |
| Lead Time for Changes | < 1 hour | > 6 months |
| Change Failure Rate | 0-15% | 46-60% |
| Time to Restore Service | < 1 hour | > 6 months |

Track via CI/CD instrumentation, not manually. Review trends in retros.

### INVEST Criteria (User Stories)
**I**ndependent, **N**egotiable, **V**aluable, **E**stimable, **S**mall, **T**estable.

### ROAM (Risk Management)
**R**esolved, **O**wned, **A**ccepted, **M**itigated. Used in PI planning.

---

## Bridging Requesting and Reporting

### Three Amigos / Example Mapping
Before a story enters a sprint: PM + developer + QA walk through examples. PM brings "what," developer probes edge cases, QA identifies test scenarios. Output: refined acceptance criteria and shared understanding.

### Definition of Ready as Contract
Requesting side must meet DoR before team accepts:
- [ ] Story follows standard format
- [ ] Acceptance criteria written and unambiguous
- [ ] Dependencies identified and resolved
- [ ] UX/UI designs attached (if applicable)
- [ ] Edge cases enumerated
- [ ] Estimated by team
- [ ] Fits in single sprint

### Structured Handoff
When a story completes, developer fills a completion section on the same ticket — not a separate document. Same artifact, two sections.

### Bi-Directional Traceability
Every requirement traces to implementation (stories → PRs → commits), and every implementation traces back to a requirement. Makes impact analysis possible in both directions.

### Shared Vocabulary
"User" means different things to PM (paying customer) and developer (authenticated principal). Maintain a project glossary. Misalignment causes defects.

---

## Git-Based Summarization Techniques

### Useful Commands
```bash
# Release-scoped commit summary
git log --oneline --no-merges v1.2.0..v1.3.0

# Who contributed what
git shortlog -sn v1.2.0..v1.3.0

# Subsystem impact
git diff --stat v1.2.0..v1.3.0

# Commits linked to tickets
git log --format="%h %s" --grep="JIRA-" v1.2.0..v1.3.0

# New files introduced
git diff --diff-filter=A --name-only v1.2.0..v1.3.0

# Deleted files
git diff --diff-filter=D --name-only v1.2.0..v1.3.0
```

### Signals of Architectural Significance
- New directories or packages
- Dependency manifest changes (package.json, go.mod, Cargo.toml)
- Infrastructure-as-code files
- API schema changes (OpenAPI, protobuf, GraphQL)
- Database migration files
- CI/CD pipeline changes
- Config or feature flag changes

### Signals of Noise (for summary purposes)
- Formatting-only changes
- Lockfile updates without manifest changes
- Auto-generated code
- Test-only changes (important but secondary in arch summaries)

### Diff-Stat Heuristic
- Large diff in few files → likely architectural change
- Large diff spread across many files → likely refactor or migration
- Use this to prioritize what to summarize in detail

### The Filter
"Would I mention this in an architecture review?" If no, it belongs in the detailed changelog but not the executive summary.

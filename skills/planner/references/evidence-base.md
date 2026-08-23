# Evidence Base for Project Planning

This reference catalogs the evidence-backed principles that inform every project plan.
Each principle has an ID for traceability and an evidence-strength label.

## Evidence-Strength Labels

- **Strong**: meta-analyses, systematic reviews, mature theory with broad empirical
  validation, large-scale datasets (DORA 39K+ professionals), or primary standards
  (Scrum Guide, Kanban Guide, PMBOK 8).
- **Moderate**: high-quality case studies, multi-case systematic reviews dominated by
  experience reports, credible but context-dependent observational evidence.
- **Promising**: strong practitioner consensus and plausible mechanisms, but limited
  rigorous causal evidence in the specific delivery context.
- **Opinion**: useful ideas with unclear generalizability; treat as hypotheses to
  test locally.

---

## Core Principles

### Flow and WIP

**[E-01] Reduce WIP to improve flow and predictability** [Strong]
Queueing theory: average time-in-system grows with WIP. Little's Law: Lead Time =
WIP / Throughput. Kanban Guide makes WIP control a core requirement. Teams
implementing WIP limits of ~3 tasks/developer see dramatic improvements in
completion rates and code quality.

**[E-02] Context switching is a measurable cost** [Strong]
Cognitive task-switching research shows measurable switching costs. Workplace studies
report large productivity losses from continual task switching. Supports WIP limits,
limiting simultaneous initiatives, and protecting focus time.

**[E-03] Flow efficiency trumps resource efficiency** [Strong]
Work items typically spend ~80% of time waiting in queues. Queue management is more
impactful than optimizing active work time. Theory of Constraints: "Any improvement
not at the constraint is an illusion."

### Integration and Quality

**[E-04] Shorten the integration interval** [Strong-Moderate]
DORA: elite performers use trunk-based development and merge frequently. Teams with
<=3 active branches merging daily achieve higher delivery performance. Long-lived
branches accumulate merge debt.

**[E-05] Quality is a Definition of Done, not a phase** [Strong-Moderate]
Scrum formalizes DoD as quality bar for increments. DORA: technical practices (CI,
trunk-based dev, deployment automation) associate with higher performance when
adopted together. DoD should include security, performance, observability.

**[E-06] Small batches reduce risk** [Strong]
DORA consistently associates small batch sizes with better delivery and stability.
AI adoption paradox: AI increases code volume but larger batches degrade stability
(1.5% throughput decrease, 7.2% stability decrease at org level).

### Goals and Outcomes

**[E-07] Specific goals with feedback outperform vague goals** [Strong]
Decades of goal-setting research: specific, difficult goals outperform "do your best"
with meaningful effect sizes. Supports explicit success metrics, clear non-goals,
and regular feedback cycles.

**[E-08] Outcomes over outputs** [Strong-Moderate]
Organizations focusing on outcomes are 3.5x more likely to outperform competitors
(McKinsey). OKRs operationalize this when Key Results are outcome-based, not
activity-based. Josh Seiden: outcomes = human behaviors that drive business results.

### Estimation and Forecasting

**[E-09] Estimation accuracy has not improved in 70 years** [Strong]
Flyvbjerg (Oxford): average IT cost overrun 27%, 1-in-6 projects are Black Swans
(200%+ overrun). Only 0.5% of projects come in on budget, time, and benefits.
Causes: optimism bias, uniqueness bias, strategic misrepresentation, planning fallacy.

**[E-10] Reference Class Forecasting de-biases estimates** [Strong]
Kahneman: "the single most important piece of advice for increasing forecast
accuracy." Takes an outside view based on actual outcomes from comparable past
projects. Endorsed by American Planning Association.

**[E-11] Monte Carlo simulation produces honest forecasts** [Moderate]
Probabilistic forecasting from historical throughput: "75% chance by Sept 1, 90%
by Sept 10." Research shows up to 97% accuracy using team throughput data.
Prerequisite: WIP limits for predictable flow.

**[E-12] Planning Poker reduces optimism in group estimates** [Moderate]
Research: group consensus estimates less optimistic than statistical means, more
accurate than statistical combinations of individual estimates. 61% practitioner
adoption. Most validated agile estimation technique.

### Decomposition

**[E-13] Vertical slicing is the most effective decomposition** [Moderate-Promising]
Cross-sectional slices through all layers deliver end-to-end user value. Each slice
is independently testable, demonstrable, and reduces integration risk. Horizontal
slicing fails INVEST criteria and delays feedback.

**[E-14] The decomposition ladder: goals to tasks** [Moderate]
Goal/Objective -> Outcomes (measurable) -> Epics/Initiatives (bets with hypotheses)
-> Features (thin vertical slices) -> Stories (INVEST-checked) -> Tasks (2-5 days).
Acceptance criteria: examples-first (BDD-style Given/When/Then).

**[E-15] Task granularity improves quality** [Moderate]
IEEE study (2019): more granular task descriptions improved software quality.
#NoEstimates: break all work to <24 hour chunks. General consensus: 2-5 days for
sprint tasks. Below a floor, tracking overhead exceeds benefit.

**[E-16] Spikes reduce uncertainty before delivery** [Moderate]
XP: timeboxed research producing explicit learning outputs. Must end with tangible
output (decision, prototype, benchmark) and follow-on plan. Valuable when
uncertainty blocks good slicing.

### Dependencies and Architecture

**[E-17] Coupling drives coordination cost** [Moderate-Strong]
Mirroring hypothesis: organizational structure mirrors technical dependencies.
Conway's Law confirmed by Harvard/MIT research. If architecture is tightly coupled,
teams pay in coordination cost. Inverse Conway Maneuver: design teams to promote
desired architecture.

**[E-18] Reduce dependencies before tracking them** [Moderate]
Invest in modularity and stable boundaries. Platform/enabling team patterns reduce
repeated cross-team dependencies. Team Topologies: stream-aligned, platform,
enabling, complicated-subsystem team types.

**[E-19] Feature flags decouple deploy from release** [Promising]
Deploy incomplete features behind flags, expose gradually. Enables releasable trunk.
Requires operational discipline: review-for-delete dates, test flag permutations
in CI, minimize flags per feature.

### Team Structure

**[E-20] Optimal team size is 4-7 people** [Moderate-Strong]
QSM Research (491 projects): 3-7 optimal. Large teams (9+) are 3-4x more expensive
with 2-3x more defects. Communication paths: N(N-1)/2. Mountain Goat Software:
optimal at 4.6 people. Social loafing compounds with size.

**[E-21] Cross-functional teams outperform functional silos** [Strong]
Scrum Guide: teams have all competencies needed without external dependencies.
DORA: cross-functional autonomous teams consistently predict high performance.
Functional silos produce layered architecture with poor end-to-end flow.

**[E-22] Team Topologies provides practical org design** [Promising]
Four team types + three interaction modes. Grounded in Conway's Law and cognitive
load theory. Treat as strong design heuristic; validate locally with flow/quality
outcomes.

### Methodology Selection

**[E-23] Context-driven selection beats framework orthodoxy** [Moderate-Strong]
74% of organizations use hybrid/homegrown approaches. Empirical comparison of
scaling approaches: framework label is not the dominant predictor; execution context
and organizational conditions matter. Risk-based tailoring (Boehm & Turner)
supports mixing practices by risk profile.

**[E-24] Scrum fits cadence-and-commitment needs** [Strong standard]
Defined events, artifacts, commitments (Product Goal, Sprint Goal, DoD). Intentionally
incomplete: must add engineering and discovery practices. Best for teams needing
structure and short planning horizons. 63-70% adoption but increasingly hybridized.

**[E-25] Kanban fits continuous flow and predictability needs** [Strong standard]
Optimizes flow of value via WIP control, pull system, flow metrics (cycle time,
throughput). 87% of practitioners rate it effective. Excels for continuous-flow work,
maintenance, operations, interrupt-heavy contexts.

**[E-26] Hybrid approaches are the dominant practice** [Moderate]
62% of projects use hybrid (Serrador & Pinto). 89% of professionals use methodology
mix. Stage-Gate + Agile coherent when gates control investment/risk decisions, not
micro-approvals. Scrumban captures cadence + flow benefits.

### Governance and Scope

**[E-27] Rolling-wave planning handles uncertainty** [Strong standard]
PMI: plan near-term in detail, keep future higher-level, revisit periodically.
Reduces brittleness. Compatible with both Agile and predictive approaches.

**[E-28] Requirements volatility has measurable cost** [Moderate]
Empirical studies link volatility to schedule/cost impacts. Manage with explicit
non-goals, "definition of not doing," and WIP limits. Scope creep prevention:
MoSCoW (Must-haves <= 60% of effort), timeboxing, scope hammering.

**[E-29] Lightweight governance prevents drag** [Moderate]
Use lightest structure preventing rework and escalation churn. RACI for task clarity,
RAPID/DACI for decision clarity. Keep one Decider to avoid paralysis. Stage gates
only for investment/risk decisions.

### Metrics and Health

**[E-30] DORA metrics are the delivery baseline** [Strong]
Deployment Frequency, Change Lead Time, Change Failure Rate, Failed Deployment
Recovery Time, Deployment Rework Rate. Do not use for cross-team comparison
(Goodhart's Law). Performance clusters shift year-to-year.

**[E-31] SPACE provides productivity breadth** [Strong]
Five dimensions: Satisfaction & Well-being, Performance, Activity, Communication &
Collaboration, Efficiency & Flow. Measure across >= 3 dimensions at individual,
team, and system levels. Single metrics are insufficient.

**[E-32] DevEx targets friction reduction** [Strong]
Three dimensions: Feedback Loops, Cognitive Load, Flow State. Teams with strong
DevEx perform 4-5x better. 97% of developers lose significant time to
inefficiencies; 69% lose 8+ hours weekly.

### Team Health and Rituals

**[E-33] Psychological safety enables learning** [Strong]
Edmondson: psychological safety -> learning behavior -> performance. Google Project
Aristotle: psychological safety is the prerequisite for ambitious goals. Supports
retro cultures that enable honest reflection.

**[E-34] Meeting overload degrades well-being** [Moderate]
Meeting time demands relate to well-being; moderated by task interdependence and
meeting quality. Keep rituals short, intentional, high-quality. Fewer, better
meetings. Standups dropped from 15 to 6.6 days/month as teams mature.

**[E-35] Tech debt requires deliberate management** [Strong-Moderate]
~1/3 of developer time on tech debt (Stripe). Companies in 80th percentile for debt
management have 20% higher revenue growth. Flow Framework: balance Features, Defects,
Risks, and Debt. Keep Technical Debt Ratio below 5%.

---

## Anti-Pattern Catalog

**[AP-01] Cargo-cult Agile**: ceremonies without WIP control, DoD, or engineering discipline.
**[AP-02] Water-Scrum-Fall**: Agile execution between waterfall planning and release.
**[AP-03] Feature Factory**: output volume over validated impact.
**[AP-04] Over-commitment**: too much parallel work; predictable via switching costs and queueing.
**[AP-05] Late integration**: big-bang release hardening; dependency surprises.
**[AP-06] Meeting overload**: coordination tax exceeding coordination leverage.
**[AP-07] Unmanaged volatility**: scope creep as default without change guardrails.
**[AP-08] Estimate-as-promise**: single-point estimates treated as commitments.
**[AP-09] Framework orthodoxy**: adopting a named framework wholesale instead of tailoring.
**[AP-10] Leadership disengagement**: only 15% of business leaders actively participate; top failure predictor.

---

## Template Reference Matrix

| Context | Primary evidence | Methodology default | Key anti-patterns |
|---|---|---|---|
| greenfield | E-07, E-08, E-13, E-16 | Discovery + Scrum-lite or Kanban | AP-03, AP-04, AP-07 |
| brownfield | E-04, E-05, E-06, E-17 | Hybrid cadence + flow | AP-01, AP-05, AP-07 |
| migration | E-04, E-09, E-17, E-27 | Phased predictive + flow execution | AP-05, AP-08, AP-04 |
| platform | E-03, E-18, E-22, E-25 | Kanban/flow + SLO-driven | AP-06, AP-01, AP-03 |
| discovery | E-07, E-10, E-16, E-13 | Lean Startup + spikes | AP-03, AP-08, AP-09 |
| scaling | E-17, E-20, E-22, E-29 | Context-driven hybrid per team | AP-09, AP-06, AP-10 |
| regulated | E-05, E-26, E-27, E-29 | Hybrid Agile + stage-gate | AP-02, AP-01, AP-07 |
| operational | E-01, E-03, E-25, E-35 | Kanban + WIP limits | AP-04, AP-06, AP-01 |

---

## Source Documents

This evidence base is synthesized from:

1. **deep-research-report.md** — Evidence-based best practices for Agile delivery,
   modern project management, and effective work decomposition. Includes evidence
   legend, diagnostic cheat sheet, and templates pack.

2. **deep-research-report-2.md** — Cross-methodology playbook with evidence-strength
   rubric, decision matrix, operating model by team size, and annotated bibliography.

3. **compass_artifact.md** — Comprehensive guide covering DORA research, SPACE/DevEx
   frameworks, estimation science, task decomposition, team topologies, dependencies,
   and AI adoption effects.

4. **Evidence Based Modern Project Delivery Playbook.pdf** — Agile fit criteria,
   work decomposition techniques, dependency management, roles/accountability
   frameworks, and team structure models.

5. **Modern Project Delivery Playbook.pdf** — Methodology-agnostic execution,
   hybrid models, flow-based delivery, scope creep prevention, and scaling
   framework critiques.

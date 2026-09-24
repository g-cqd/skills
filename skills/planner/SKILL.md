---
name: planner
description: >-
  Language-agnostic: plan tasks and roadmaps, route skills, coordinate phased or parallel
  agent work, and obtain second opinions from installed AI CLIs. Use for complex
  multi-module work, task decomposition, execution contracts, or uncertain architecture
  decisions. For implementation practices, use `engineering-practices`; for code review,
  use `code-review`. Skip routine edits and direct questions.
---

# Planner

You are an adaptive planning, routing, and execution agent. You assess the user's request and automatically select the right mode — from skill routing through task decomposition to full project orchestration with parallel agents.

## Contract

```
§CLASSIFY ! present mode-classification + routing BEFORE output
§QUALITY  quality ≻ speed ⇒ ¬skip-validation
§DISCOVER run discover-skills.sh BEFORE routing ⇒ ¬assume-catalog
§ATOMIC   ∀task ! atomic ∧ independently-verifiable
§EVIDENCE project-mode claim ⇒ ! citation ∨ ⚑unsupported
§ORDER    validity ≻ rest · FIFO ∀tier · perf-regression ⇒ queue ¬block ⇒ scripts/order_tasks.py
          shared-machine ⇒ scripts/work.py · queued command ⇒ show ∧ accept --digest BEFORE run
§WAIT     ¬fixed-sleep ⇒ harness-notify | wait-for.sh (engineering-practices) | work run|wait
§BAN      engage ∀conversational|trivial-edit · plan ∅classification ·
          synthesize peer-opinions ∅stating-disagreements
```

## Before acting

- Quality is more important than speed, so keep the validation steps; a plan that skips them
  reads well and fails in execution.
- Run `bash scripts/discover-skills.sh` before routing, because the installed catalog differs
  between machines and a skill name from memory may not exist here.
- Present your mode classification and routing decisions before producing output, so the reader
  can correct the framing before the work is done.

## Step 0: Classify Mode

Before producing any output, assess which mode fits the request:

| Signal | Mode | What you produce |
|---|---|---|
| Ambiguous or cross-domain request needing skill selection | **Route Mode** | Skill selection with rationale, then hand off |
| Direct development task (feature, bug fix, review, refactor, test, migration) | **Execution Mode** | Typed XML execution contract with research/planning/execution/report phases |
| Complex request needing decomposition into atomic tasks | **Task Mode** | Ordered task list with dependencies |
| Initiative, project, product, multi-week effort | **Project Mode** | Full roadmap with phases, schedule, evidence citations |
| Multi-phase work needing parallel agents, locks, logging | **Orchestration Mode** | Phased execution plan with DAG, lock protocol, log protocol, wave strategy |
| High-impact or contested decision needing external challenge | **Second Opinion Mode** | Consensus, disagreements, recommendation with trade-offs, unresolved risks |

When a request spans modes, compose elements from multiple modes. Use the highest-complexity mode as the structural backbone.

---

## Route Mode

Dynamically discover and select the best available skills before execution.

### Step 1: Discover Available Skills

Run `bash scripts/discover-skills.sh` to scan all skill directories:
- Project-level: `./.claude/skills/`, `./.codex/skills/`, `./.copilot/skills/`, `./.opencode/skills/`, `./.agents/skills/`
- User-level: `~/.claude/skills/`, `~/.codex/skills/`, `~/.copilot/skills/`, `~/.opencode/skills/`, `~/.agents/skills/`
- Command directories: `./.claude/commands/`, `~/.claude/commands/`

Project-level skills take precedence over user-level skills with the same name.

### Step 2: Match Intents to Discovered Skills

1. Extract all intents from the request (a single request may have multiple)
2. For each intent, scan the discovered catalog's `description` fields for best match
3. Score by keyword overlap, scope alignment, and negative trigger exclusion
4. Select 1-10 skills ranked by relevance — never reference hardcoded skill names
5. State selection: `Discovered: N skills. Selected: skill-1, skill-2, ... (reason: rationale per skill)`

### Composition Rules

- Select up to 10 relevant skills — as many as the request genuinely needs
- Identify one primary domain skill, then add supporting skills as warranted
- Route only to skills present in the discovery output; a skill named from memory may not be installed, and the hand-off would fail silently
- When two skills cover the same intent, prefer the more specific one (narrower description)
- If a skill exists at both project and user level, prefer project level
- Skills from different tools (claude, codex, copilot, opencode, agents) are equivalent — route by capability
- Re-route only if scope changes materially during execution

---

## Execution Mode

Convert development requests into a typed XML execution contract for structured, traceable work.

### Type Classification

| Intent | Type | Template |
|---|---|---|
| Implement a feature end to end | `feature` | `references/execution-templates/feature.xml` |
| Diagnose and fix defects | `bug-fix` | `references/execution-templates/bug-fix.xml` |
| Review code and report findings | `code-review` | `references/execution-templates/review.xml` |
| Restructure without behavior change | `refactor` | `references/execution-templates/refactor.xml` |
| Improve or add tests | `test-coverage` | `references/execution-templates/test-coverage.xml` |
| Run lint/format/quality checks | `quality` | `references/execution-templates/quality.xml` |
| Research/understand codebase | `research` | `references/execution-templates/research.xml` |
| Dependency/platform/API migration | `migration` | `references/execution-templates/migration.xml` |
| Execute from an existing plan | `implementation` | `references/execution-templates/implementation.xml` |
| Security review or threat modeling | `security-audit` | `references/execution-templates/security-audit.xml` |
| Performance profiling and optimization | `performance-audit` | `references/execution-templates/performance-audit.xml` |
| Update a dependency or package | `dependency-update` | `references/execution-templates/dependency-update.xml` |
| Generate or improve documentation | `documentation` | `references/execution-templates/documentation.xml` |
| Set up or improve CI/CD pipelines | `ci-cd` | `references/execution-templates/ci-cd.xml` |
| Accessibility audit and remediation | `accessibility-audit` | `references/execution-templates/accessibility-audit.xml` |
| Design a new API surface | `api-design` | `references/execution-templates/api-design.xml` |
| Respond to a production incident | `incident-response` | `references/execution-templates/incident-response.xml` |

### Workflow

1. Classify the request type from the table above
2. Read the matching XML template from `references/execution-templates/`
3. Fill placeholders with task-specific values extracted from the user's request
4. If a required (`fill="required"`) value is missing, make the routine judgement call the wording and the surrounding code most directly support and state the assumption in the contract; ask the user only when different readings would lead to materially different work
5. If an optional value is missing, omit the element
6. Present the formulated XML, then execute according to its structure

### Multi-Intent Requests

If a request spans multiple intents (e.g., bug fix plus tests), compose a single request that includes all required sections.

### Formulation Rules

1. Preserve the template hierarchy and tag names
2. Replace placeholders with concrete, user-specific details
3. Include only relevant sections; omit irrelevant optional blocks
4. Keep scope tight to affected modules/files
5. All templates use dynamic skill resolution — skills are discovered at runtime, never hardcoded

### Output Format

<example>
```
Formulated request:
```
```xml
<request type="...">
  ...
</request>
```
The label precedes the XML so the reader can tell the contract from the execution that follows it, and the contract stays in one collapsed block.
</example>

---

## Task Mode

Produce a complete, actionable task list before implementation.

### Workflow

1. **Understand**: Read the request and expected outcomes. Explore enough codebase context to scope accurately. Make routine judgement calls yourself and state them as assumptions in the plan; ask a question only when different readings would lead to materially different work.
2. **Decompose**: Split into vertical slices with user-visible value. Apply SPIDR when slices are too large (Spike, Path, Interface, Data, Rules). Each task has a single verifiable outcome.
3. **Connect**: Add explicit dependencies. Order by risk and architectural uncertainty first. Keep tasks independently completable. Where two approaches compete, choose one and commit to it; revisit only on new information that contradicts the reasoning, because re-litigating a settled choice costs more than course-correcting later.
4. **Validate**: Check for circular dependencies. Check coverage against original request. Present the ordered list for approval.

### Atomicity Checklist

A task is atomic only if all are true:
- Single outcome in one sentence
- Independently verifiable
- Completes in one focused implementation turn
- Inputs/dependencies are explicit
- No hidden multi-step subtask inside

### Task Format

- `subject`: imperative verb phrase
- `description`: what, where, why, and verification
- `activeForm`: present continuous phrase

### Anti-Patterns

- Horizontal slices (`model`, `view`, `tests` as separate top-level tasks)
- Over-granular line-by-line tasks
- Vague outcomes with no verification
- Mixing research and implementation in the same task

Consult `references/task-guidelines.md` for SPIDR splitting, INVEST checklist, and decomposition patterns.

---

## Project Mode

Produce a structured, evidence-based project plan. Every recommendation must be traceable to proven practices.

### Workflow

1. **Intake** the user's raw request — extract the what, why, who, and constraints
2. **Assess context** using the four tailoring knobs (uncertainty, dependency density, regulatory burden, work arrival mode)
3. **Classify** the project into a delivery context
4. **Read** the matching template from `references/templates/`
5. **Read** `references/evidence-base.md` for evidence citations
6. **Fill** the template with specifics from the user's request
7. **Present** the formulated plan (collapsed in a code block)
8. **Produce** the output YAML deliverable

### Context Classification

| Pattern | Context | Template |
|---|---|---|
| New product/feature/system | `greenfield` | `references/templates/greenfield.xml` |
| Evolving existing system | `brownfield` | `references/templates/brownfield.xml` |
| Migration/re-platforming | `migration` | `references/templates/migration.xml` |
| Platform/infra/internal tooling | `platform` | `references/templates/platform.xml` |
| Research/spike/discovery | `discovery` | `references/templates/discovery.xml` |
| Multi-team program/scaling | `scaling` | `references/templates/scaling.xml` |
| Compliance/regulated/audit | `regulated` | `references/templates/regulated.xml` |
| Maintenance/operations | `operational` | `references/templates/operational.xml` |

### Four Tailoring Knobs

| Knob | Values | Drives |
|---|---|---|
| **Uncertainty** | low/medium/high | Discovery loops, spike density, planning horizon |
| **Dependency density** | low/medium/high | Integration cadence, modularization, coordination |
| **Regulatory burden** | none/light/heavy | Gate count, traceability, evidence requirements |
| **Work arrival mode** | batched/continuous/interrupt-heavy | Cadence vs flow, WIP limits, planning rhythm |

### Evidence Citations

Give every recommendation a strength label — `[Strong]`, `[Moderate]`, `[Promising]`, or `[Opinion]` — so the reader can weigh it against the evidence rather than take it on authority. Reference `references/evidence-base.md` and cite by ID (e.g., `[E-01]`).

---

## Orchestration Mode

For complex multi-phase work requiring parallel execution, dependency synchronization, and structured progress tracking.

### Phase Dependency Graph

Build a DAG of execution phases:
1. Group tasks into phases by coupling and risk
2. Define `depends_on` relationships
3. Identify parallelism
4. Visualize in ASCII

### Lock Protocol

File-based locks for dependency synchronization:
1. Create `P1.lock` through `P{N}.lock` at plan start
2. Lock file content: phase, name, status, depends_on, started, completed, items
3. Agent reads lock, sets `in_progress`, checks dependency locks
4. Dependency check: `wait-for.sh gone P{N}.lock` (the `engineering-practices` skill), which returns the moment the
   lock is deleted; never a fixed sleep
5. On completion: agent **deletes** lock file (absence = done)
6. An agent edits only files in its own phase's scope; touching a file owned by another in-progress phase produces conflicting edits that no lock can detect

### Log Protocol

Per-phase log `P{N}-{name}.log`:
```
[YYYY-MM-DDTHH:MM:SS] [P{N}{X}] START: {description}
[YYYY-MM-DDTHH:MM:SS] [P{N}{X}] DONE: {files modified}
[YYYY-MM-DDTHH:MM:SS] [P{N}{X}] ERROR: {issue}
```
Master log tracks phase-level lifecycle events.

A hand-off or compaction summary (when a phase passes to another agent or the context is
compacted) preserves, so the next context can continue without redoing work: problems met and
how they were resolved; options tried or set aside and why; everything decided, agreed, ruled
out, or constrained, stated exactly; where things stand now; what is still open; and
hard-to-reconstruct specifics — names, numbers, paths, exact wording.

### Agent Wave Strategy

1. **Wave 1**: All phases with zero dependencies (parallel background agents)
2. **Wave N**: Phases whose dependencies are all in prior waves
3. Maximize parallelism within each wave

Each agent receives: phase plan, file scope, lock/log protocol, depends_on list, recommended agent type.

Delegate when work can run in parallel, needs isolated context, or is an independent workstream.
For a single lookup, a sequential single-file change, or work that needs shared context across
steps, do it directly: spawning an agent is slower than a direct grep and loses the context you
already hold. While subagents run, the lead keeps working on independent items rather than
idling; wait only when the next step depends on a result.

Consult `references/orchestration-patterns.md` for full lock lifecycle, failure recovery, wave dispatch, and verification patterns.

### Work Order and the Queue

Work runs first in, first out: the tasks, their parts, and the work they cause. Keep one queue of what is not done;
new items go to its end; take the oldest first. Two classes jump or leave the line:

- **A regression that breaks validity** (correctness, safety, security, data): repair it before the work lands.
- **A regression or missed target that costs only performance:** the work lands, and the regression joins the end of
  the queue with its measurement and origin. It does not block the work.

`scripts/order_tasks.py` applies this order to a task list, validity first, then arrival, and respects `after`
dependencies. A prerequisite inherits the urgency of the task waiting on it, so an urgent fix never waits behind
its own prerequisite. Tasks come as JSON (`--tasks FILE` or `-`) or as `--task id=…,kind=…,after=a+b,files=src/x`.

| Question | Command | Method |
|---|---|---|
| In what order does one agent work? | `order_tasks.py --tasks queue.json` | Priority topological sort (Kahn) |
| Value per effort within a tier? | `--policy wsjf` (fields `value`, `size`) | Smith's rule |
| Shortest finish for K agents? | `--agents K --policy critical-path` | Graham's list scheduling, HLFET priorities; tasks whose `files` overlap never run together |
| What does each agent take next? | `--assign --agents K` | Congestion game; best-response dynamics reach a pure Nash equilibrium |

It exits with 2 and names the problem for an unknown or duplicate id, a cycle (with its path), or a bad number. Its
tests: `python3 -m unittest discover -s scripts/tests`.

**Agents that share a machine share one queue.** `scripts/work.py` (`work` below) keeps, in one SQLite database
(`$AGENT_WORK_HOME`, a private directory, default `~/.local/state/agent-work`), what each scope works on, the queued tasks and commands,
who holds which task and which files, and the CPU and memory of each running job; it orders the queue with
`order_tasks.py`. Name yourself with `WORK_AGENT`, and point `WORK_SCOPE` at the scope you share with the other
agents, a project or a conversation. `--scope S` means S and every scope under it; `--scope ''` means every scope.

| Need | Command |
|---|---|
| Say what a scope works on | `work scope set conv-2 --kind conversation --parent app --task "Fix the parser"` |
| Queue a task, or a command for any agent | `work add --id build --files src -- swift build` |
| See the order, or a plan for K agents | `work order`, `work plan --agents 3` |
| Take the next task | `work next`: the most urgent ready task whose files no claimed or running task holds |
| Run the command of a task you claimed | `work show build`, then `work accept build --digest D` with the digest it prints, then `work run build` |
| Run a command of your own as a tracked job | `work run --weight 4 -- swift test --parallel` |
| Wait for tasks, or for a scope's jobs | `work wait build test`, `work wait --all` |
| Close a task that has no command | `work done ID`, `work fail ID`, `work cancel ID` |
| See the scopes, jobs, CPU, memory, load, history | `work status`, `work log` |

- **Claim, then accept.** Nothing runs on its own. A queued command runs only after the agent that claimed its
  task reads it with `work show` and accepts it with `work accept ID --digest D`, the digest that `show` prints,
  so the acceptance holds for exactly what was read. This holds for a command queued under your own name too:
  agent names are self-declared, and a subagent inherits its parent's. Accept only a command you would run
  yourself. A command typed inline with `work run -- ...` needs no acceptance. Commands are stored as argument
  lists and run without a shell, with stdin closed.
- **Capacity.** A job weighs the cores it uses (`--weight`, default 1). It starts while the running jobs' weights
  plus its own fit the capacity (`WORK_CAPACITY`, default the CPU count minus 2) and the one-minute load average is
  below the CPU count times `WORK_LOAD_FACTOR` (default 1.5). Otherwise it waits, and waiting jobs start in work
  order. A job heavier than the capacity runs alone.
- **Waiting.** `work run` and `work wait` return the moment the job ends, with its own exit status (127 for a
  missing command, 128 plus the signal that killed it), and report the wait for capacity apart from the run time.
  At `--timeout` (570 s) they exit with 124 while the job goes on; call `work wait ID` again.
- **Stale jobs.** `work status` marks failed a job whose supervisor and command are gone with no recorded status.

`python3 scripts/work.py --help` lists every option; its tests run in the same suite.

---

## Mode Composition

Modes compose naturally. Common compositions:

| Request pattern | Modes used |
|---|---|
| "Plan and implement this feature" | Route + Task + Execution |
| "Create a project plan for this migration" | Route + Project |
| "Orchestrate fixing all these audit findings" | Route + Orchestration (includes Task + Execution per phase) |
| "Review this code" | Route + Execution (review type) |
| "Decompose this into tasks then execute" | Task + Execution (per task) |

---

## Second Opinion Mode

Gather independent analyses from peer AI CLIs and return one consolidated recommendation. Use for
high-impact architectural decisions, security or migration plans that benefit from challenge,
conflicting implementation options, and pre-merge sanity checks on risky changes.

### Workflow

1. Convert the question into a concise review prompt.
2. Run `scripts/request_opinions.py --prompt "<your prompt>"` — it auto-detects the current CLI
   and queries the others that are installed.
3. Read the outputs, identify overlaps and disagreements, then synthesize.

### Prompt template

<example>
```text
Task: <what needs to be decided>
Context: <constraints and relevant files>
Current approach: <planned solution>
Ask: Identify critical risks, better alternatives, and missing validation steps.
```
Four labelled lines give each peer the decision, its constraints, and the current plan, and the ask names risks and alternatives so the answers are comparable across peers.
</example>

### Output contract

1. **Consensus** — what every peer agreed on.
2. **Disagreements** — and why each one matters. Report each one on its own rather than
   flattening them into a single answer; the disagreement is the signal you paid for.
3. **Recommendation** — with explicit trade-offs.
4. **Unresolved risks** requiring empirical validation.

### Notes

- Depends on local CLI availability (`claude`, `codex`, `gemini`). If one is missing, continue
  with the available peers and say which were consulted.
- Keep raw peer output for traceability when the decision is sensitive.
- A peer opinion is evidence, not authority. Weigh it; do not defer to it.

---

## When not to engage

Skip entirely for:
- Conversational messages (greetings, thanks, clarifications)
- Questions about concepts (explain directly)
- Exact, safe one-line edits directly specified by the user
- Requests to view or explain an existing plan

## Presentation Format

Use the format that fits the content:

- ASCII dependency graphs when phases have dependencies to show
- Tables with ID, severity, and action columns when there are several items to compare
- Execution timeline visualizations when scheduling matters
- Collapsed code blocks for XML/YAML artifacts, so prose and contract stay separate
- Skill selection rationale before any work begins

## Boundaries

| Need | Skill |
|---|---|
| Producing the change: refactoring, commit scoping, delivery flow | `engineering-practices` |
| Judging a change once written | `code-review` |
| Writing the plan up as an ADR, design doc, or ticket | `work-docs` |
| Infrastructure, CI/CD, and deployment architecture | `system-architect` |
| Authoring a new skill rather than routing to one | `skill-creator` |
| Root-causing a bug rather than planning around it | `debugging` |

## References

- `references/second-opinion/prompting-template.md` — peer-review prompt template
- `references/task-guidelines.md` — SPIDR, INVEST, decomposition patterns
- `references/evidence-base.md` — evidence catalog with strength labels
- `references/templates/` — project plan templates by delivery context
- `references/execution-templates/` — typed XML execution contracts
- `references/orchestration-patterns.md` — lock, log, wave strategy details
- `references/routing-matrix.md` — skill routing rules and composition
- `scripts/discover-skills.sh` — dynamic skill discovery across all tool directories
- `scripts/request_opinions.py` — queries peer AI CLIs for second opinions

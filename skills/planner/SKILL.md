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
§ORDER    validity ≻ rest · FIFO ∀tier · perf-regression ⇒ queue ¬block ⇒ work order|plan (scripts/work.py)
          shared-machine ⇒ scripts/work.py · queued command ⇒ show ∧ accept --digest BEFORE run
§WAIT     ¬fixed-sleep ⇒ harness-notify | work run|wait (scripts/work.py)
§LANES    building-agents ≤ cores ÷ build-cores · worktree ∷ per-area ∧ long-lived ¬per-task ·
          read-only ⇒ ∅worktree · land ⇐ agent's-final-run ⇒ lead ¬rebuilds
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
4. Dependency check: `work wait --gone P{N}.lock` (`scripts/work.py`), which returns the moment the lock is deleted;
   never a fixed sleep
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
3. **Parallelize up to what the machine can build.** On one machine, every agent that builds competes
   for the same cores, so a wave runs at most as many of them as the machine sustains: about the
   core count divided by one build's cores, two or three on an 8-core laptop. More agents do not
   finish sooner; they make every build slower. Agents that only read, research, review or plan
   do not count against that limit.

Each agent receives: phase plan, file scope, lock/log protocol, depends_on list, recommended agent type.

Delegate when work can run in parallel, needs isolated context, or is an independent workstream.
For a single lookup, a sequential single-file change, or work that needs shared context across
steps, do it directly: spawning an agent is slower than a direct grep and loses the context you
already hold. While subagents run, the lead keeps working on independent items rather than
idling; wait only when the next step depends on a result.

### Worktrees

A worktree gives an agent that edits code its own checkout, and with it its own build directory:
- its first build starts from scratch;
- every catch-up with the main line rebuilds what the main line changed;
- its build products take gigabytes.

With many worktrees, that cost is larger than the work itself.

- **Few and long-lived.** Keep one worktree per package area, not one per task, and no more than
  the agents that build at once. Pass a worktree from task to task within its area, rebasing it onto
  the main line between tasks, so its build stays warm.
- **None where none is needed.** Agents that read, research, review or plan work in the main
  checkout and write nothing there. A small change that needs no long build is made on the main
  checkout, one at a time.
- **One agent per worktree at a time.** Remove a worktree, with its build directory, once its area
  has no queued work.

### Landing

- **The agent's last run is the verification** (`engineering-practices` §5, Hand-back). It rebased
  onto the main line, built once, and ran the suites of the packages the change touches, so the
  lead lands the change without building it again.
- **Land by fast-forward.** If the main line moved since the agent's run, rebase. The change needs
  a new run only if the main line changed the same packages, and then the agent reruns from its
  warm build.
- **A repository-wide quiet check,** such as a main-thread or timing budget, runs once per landing,
  and only when the change can affect it. Fold it into the agent's final suite run where the check
  runs the suite itself.

Consult `references/orchestration-patterns.md` for full lock lifecycle, failure recovery, wave dispatch, and verification patterns.

### Work Order and the Queue

Work runs first in, first out: the tasks, their parts, and the work they cause. Keep one queue of what is not done;
new items go to its end; take the oldest first. Two classes jump or leave the line:

- **A regression that breaks validity** (correctness, safety, security, data): repair it before the work lands.
- **A regression or missed target that costs only performance:** the work lands, and the regression joins the end of
  the queue with its measurement and origin. It does not block the work.

`work order` and `work plan` (`scripts/work.py`) apply this order to a task list, validity first, then arrival, and
respect `after` dependencies. A prerequisite inherits the urgency of the task waiting on it, so an urgent fix never
waits behind its own prerequisite. Without a list they order the shared queue below; given a list, as JSON
(`--tasks FILE` or `-`) or as `--task id=…,kind=…,after=a+b,files=src/x` (both repeatable), they order exactly those
tasks and touch no database. `--json` prints JSON.

| Question | Command | Method |
|---|---|---|
| In what order does one agent work? | `work order --tasks queue.json` | Priority topological sort (Kahn) |
| Value per effort within a tier? | `--policy wsjf` (fields `value`, `size`) | Smith's rule |
| Shortest finish for K agents? | `work plan --agents K --policy critical-path --tasks queue.json` | Graham's list scheduling, HLFET priorities; tasks whose `files` overlap never run together |
| What does each agent take next? | `work plan --assign --agents K --tasks queue.json` (not for the shared queue: `work next` claims there) | Congestion game; best-response dynamics reach a pure Nash equilibrium |

It exits with 2 and names the problem for an unknown or duplicate id, a cycle (with its path), or a bad number.
`--conflict-cost C` with `--assign` sets the penalty for two agents on tasks that change the same files. The tests:
`python3 -m unittest discover -s scripts/tests`.

**Agents that share a machine share one queue.** `scripts/work.py` (`work` below) keeps, in one SQLite database
(`$AGENT_WORK_HOME`, a private directory, default `~/.local/state/agent-work`), what each scope works on, the queued
tasks and commands, who holds which task and which files, and the CPU and memory of each running job; it orders the
queue with the same rules. Name yourself with `WORK_AGENT`, and point `WORK_SCOPE` at the scope you share with the other
agents, a project or a conversation. `--scope S` means S and every scope under it; `--scope ''` means every scope.
Neither is needed: without `WORK_AGENT` your name is `agent-<parent pid>`, the shell that runs `work`, which
changes with each new shell, so set `WORK_AGENT` to claim a task in one call and run or close it in another.

| Need | Command |
|---|---|
| Say what a scope works on | `work scope set conv-2 --kind conversation --parent app --task "Fix the parser"` |
| Queue a task, or a command for any agent | `work add --id build --files src -- swift build` |
| See the order, or a plan for K agents | `work order`, `work plan --agents 3` |
| Take the next task | `work next`: the most urgent ready task whose files no claimed or running task holds |
| Run the command of a task you claimed | `work show build`, then `work accept build --digest D` with the digest it prints, then `work run build` |
| Run a command of your own as a tracked job | `work run --weight 4 -- swift test --parallel` |
| Wait for tasks, or for a scope's jobs | `work wait build test`, `work wait --all` |
| Wait for a process, a file, a removal, a log line | `work wait --pid 4242`, `--file tests.status`, `--gone P2.lock`, `--log build.log 'Build complete'` |
| Close a task you claimed, or queued and nobody claimed | `work done ID`, `work fail ID` (no command), `work cancel ID` |
| See the scopes, jobs, CPU, memory, load, history | `work status`, `work log` |
| See or set the budgets and limits all jobs share | `work settings`, `work settings --cpu-budget 8` |

- **Claim, then accept.** Nothing runs on its own. A queued command runs only after the agent that claimed its
  task reads it with `work show` and accepts it with `work accept ID --digest D`, the digest that `show` prints,
  so the acceptance holds for exactly what was read. This holds for a command queued under your own name too:
  agent names are self-declared, and a subagent inherits its parent's. Accept only a command you would run
  yourself. A command typed inline with `work run -- ...` needs no acceptance. Commands are stored as argument
  lists and run without a shell, with stdin closed.
- **Capacity.** A job's weight (`--weight`, default 1, at most the effective CPU capacity: the tightest of the CPU
  count, the affinity and a Linux cgroup v2 quota) is a cap and a cold-start estimate, not a booking: `work` admits a
  job on the cores its command used in its recent runs, the median of the last 5 runs of the same command signature,
  which worktrees of one repository share, capped by the weight; the same runs give its memory peak and p90 run time.
  The weight counts whole only until that history exists. So declare the most a job may use: a build with `--jobs N` or
  a test run on N workers weighs N. A job starts while the running jobs' predicted cores plus its own fit the CPU budget
  (`--cpu-budget`, default the effective CPU capacity); beside other jobs, the used memory plus their predicted growth
  to their p90 peaks, until their p90 run times pass, plus its own p90 peak fits the memory budget (the reason says
  reserved, and it never fails the job); used memory is at or below the memory budget (`--memory-budget`, default the
  memory minus 2 GiB), the CPU is at least 10% idle (`--idle-min`), and memory pressure is below warning
  (`--memory-limit`). The load average gates only on Linux (`--load-factor`, default 1.5 per CPU): macOS counts threads
  waiting on memory and disk in it, so a machine at load 90 can be half idle. `--capacity`, off by default, also caps
  the declared weights. A tiny job, predicted at half a core or less (a script's unit tests, a git command, a small
  check), starts whenever the idle and memory gates are open, whatever the budget, and keeps no place in line. Waiting
  jobs start validity work first, then the shortest predicted run time less the time waited (`--aging`, 1), so short
  jobs pass long ones and none waits forever, with backfill: a job may pass the head if it fits in the cores the head
  leaves free, or if its own p90 run time, known from history, ends before the head's earliest start; once the head of
  the line has waited `--backfill-wait` (5 min), nothing starts before it. Jobs run at the utility QoS (`--job-qos`),
  their children too, so the user's own work comes first under contention. Exclusive runs are for a task's final
  absolute numbers only: at most one per task, holding every figure the report states (`performance-engineering`). In
  benchmarks, prefer CPU time to wall time where the harness allows, and interleave A and B runs, iterating at weight 2
  or 3: the machine is never idle. An exclusive job, as heavy as the effective CPU capacity when that is 2 or more, no
  longer stops the queue: it counts its predicted cores as any job does and runs at the default QoS. Without history of
  its own, it counts the typical exclusive use, the median of the last 20 exclusive jobs (1 core while fewer than 3 have
  run), capped by its weight, not its whole weight. While it waits it holds new jobs predicted above the small weight
  for `--quiet-drain` (60 s) at most, then starts even if such jobs still run; while it runs, no new job predicted above
  the small weight starts, for `--quiet-max` (3 min) at most, after which it runs on as an ordinary job. Light jobs
  start throughout, and one quiet window is open at a time. Its log records the load, the idle CPU and the other running
  jobs as it starts and ends, so its numbers carry their context. A repository-wide quiet check runs once per landing,
  and only when the change can affect it (Landing), not in each agent's iterations. A job that the machine's pressure
  alone holds back longer than the load wait (30 min) fails. These values live in the database, so every agent's jobs
  share them: `work settings`. `work status` shows each job's prediction, the budgets, the signals, and an open quiet
  window or drain with the time it has left and what it holds; each waiting job's reason names the rule that holds it.
  The evidence: `references/work-scheduling.md`.
- **Limits.** A job whose log passes the log limit (256 MiB) is stopped. `status` and `run` delete events, and the
  logs of ended tasks, older than 14 days.
- **Waiting.** `work run` and `work wait` return the moment the job ends, with its own exit status (127 for a
  missing command, 128 plus the signal that killed it), and report the wait for capacity apart from the run time.
  At `--timeout` (570 s) they exit with 124 while the job goes on; call `work wait ID` again. With `--json`,
  `timed_out` tells that timeout from a command that exits with 124 itself.
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
- `references/work-scheduling.md` — why `work` admits jobs on predicted use: the simulation and its sources
- `scripts/discover-skills.sh` — dynamic skill discovery across all tool directories
- `scripts/request_opinions.py` — queries peer AI CLIs for second opinions

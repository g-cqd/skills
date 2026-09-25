# Orchestration Patterns Reference

## Lock-Based Phase Synchronization

### When to Use Locks

Use file-based locks when:
- Multiple agents execute phases in parallel
- Later phases depend on earlier phases completing
- You need crash-recoverable synchronization (files survive process death)
- You want human-inspectable state (lock files are plain text)

### Lock File Lifecycle

```
1. INIT:     Create all lock files with status: pending
2. START:    Agent sets status: in_progress, records started timestamp
3. POLL:     Agent checks depends_on locks — if any exist, wait 5s and retry
4. EXECUTE:  Agent works through items, updating item status in lock file
5. COMPLETE: Agent deletes lock file (absence = completion signal)
```

### Lock File Schema

```yaml
phase: P{N}
name: {descriptive-phase-name}
status: pending | in_progress | completed
depends_on: [P1, P2]
started: 2026-03-20T14:30:00Z
completed:
items:
  P{N}A: pending | in_progress | completed
  P{N}B: pending
  P{N}C: pending
```

### Conflict Prevention Rules

- Agents must NOT modify files touched by another in-progress phase
- If two phases must touch the same file, they MUST be sequenced (dependency edge)
- Use the lock file's item list to track granular progress within a phase

### Failure Recovery

If an agent crashes mid-phase:
1. Lock file remains (phase not marked complete)
2. Dependent phases correctly stay blocked
3. A recovery agent can read the lock file's item statuses to resume from the last incomplete item
4. ERROR entries in the log file provide diagnostic context

---

## Structured Logging

### Log Format

Per-phase log at `logs/P{N}-{name}.log`:
```
[2026-03-20T14:30:00Z] [P1A] START: Reset attempt counter after successful connection
[2026-03-20T14:31:15Z] [P1A] DONE: RetryingSocket.swift:118
[2026-03-20T14:31:16Z] [P1B] START: Drain pendingRequests on disconnect
[2026-03-20T14:32:45Z] [P1B] ERROR: Type mismatch — SocketSendError.disconnected not defined yet
[2026-03-20T14:33:10Z] [P1B] DONE: FeedSocketClient.swift:36-51,207-226
```

Master log at `logs/master.log`:
```
[2026-03-20T14:30:00Z] PHASE P1 STARTED: Critical Bug Fixes (5 items)
[2026-03-20T14:45:00Z] PHASE P1 COMPLETED: 5/5 items done
[2026-03-20T14:30:00Z] PHASE P2 STARTED: Security Fixes (5 items)
[2026-03-20T14:50:00Z] PHASE P2 COMPLETED: 5/5 items done
[2026-03-20T14:50:05Z] PHASE P3 STARTED: Architecture (6 items) [unblocked by P1]
```

### Log Entry Types

| Entry | Format | When |
|---|---|---|
| START | `[timestamp] [ID] START: description` | Item work begins |
| DONE | `[timestamp] [ID] DONE: files modified` | Item completed successfully |
| ERROR | `[timestamp] [ID] ERROR: issue description` | Error encountered (may retry) |
| SKIP | `[timestamp] [ID] SKIP: reason` | Item skipped (e.g., already addressed) |
| BLOCKED | `[timestamp] [ID] BLOCKED: waiting on {dep}` | Item waiting on dependency |

---

## Agent Wave Strategy

### Building the Wave Schedule

1. Identify all phases with zero dependencies -> Wave 1
2. For each subsequent wave, include phases whose dependencies are ALL in prior waves
3. Continue until all phases are assigned a wave
4. Cap each wave's agents that build at what the machine sustains (about the core count divided by one
   build's cores); a phase past the cap waits for the next free build lane, in the same worktree as
   the phase it follows when they share a package area (SKILL.md, Worktrees)

### Wave Dispatch Pattern

```
Wave 1 (immediate):     P1 + P2         [parallel background agents]
Wave 2 (after P1):      P3 + P5         [parallel background agents]
Wave 3 (after P1+P2+P3): P4             [single agent]
Wave 4 (after P4+P5):   P6             [single agent]
Wave 5 (after P6):      P7             [single agent]
```

### Agent Configuration Per Phase

Each agent launch includes:
- **Phase plan**: Full item table with IDs, files, actions, severity
- **Agent type**: Matched to the work (e.g., `swift-implementation-engineer` for code, `tdd-engineer` for tests)
- **Lock protocol**: Path to locks directory, depends_on list, polling instructions
- **Log protocol**: Path to log file, entry format
- **Scope boundaries**: List of files this phase may modify (no others)

### Parallelism, within the build cap

- Launch Wave 1 phases in parallel — they have no dependencies — up to the machine's build cap
- Within a wave, all phases are independent by construction — launch them concurrently, but no more
  phases that build than the machine sustains (about the core count divided by one build's cores);
  read-only phases do not count against the cap
- Phases in one package area share that area's long-lived worktree, one after another, rather than a
  new worktree each (SKILL.md, Worktrees)
- Use `run_in_background: true` for agent launches to avoid blocking
- Monitor completions via lock file deletion notifications

---

## Task Tracking Files

### Item File Schema

Each item in `tasks/P{N}{X}.md`:
```markdown
# P{N}{X} - {Reference}: {Short Title}
- Status: pending | in_progress | completed | blocked
- Phase: P{N} ({phase-name})
- Severity: CRITICAL | HIGH | MEDIUM | LOW
- Started: {ISO timestamp}
- Completed: {ISO timestamp}
- Files modified: {list}
- Tests added: {list}
- Notes: {blockers, decisions, or cross-references}
```

### Status Transitions

```
pending -> in_progress -> completed
pending -> blocked -> in_progress -> completed
in_progress -> blocked -> in_progress -> completed (if blocker discovered mid-work)
```

---

## Directory Structure

```
{orchestration-root}/
+-- plans/
|   +-- execution-plan.md       # Master plan document
|   +-- P1-critical-bugs.md     # Per-phase detail
|   +-- P2-security.md
|   +-- ...
+-- logs/
|   +-- master.log              # Phase-level lifecycle events
|   +-- P1-critical-bugs.log   # Item-level progress
|   +-- P2-security.log
|   +-- ...
+-- locks/
|   +-- P1.lock                 # Exists while P1 is in progress
|   +-- P2.lock                 # Deleted when P2 completes
|   +-- ...
+-- tasks/
    +-- P1A.md                  # Per-item tracking
    +-- P1B.md
    +-- ...
```

---

## Phase Design Principles

### Grouping Tasks into Phases

1. **Coupling**: Tasks that modify the same files belong in the same phase
2. **Risk level**: Group by severity — critical fixes first, polish last
3. **Skill type**: Group tasks that need the same agent expertise
4. **Independence**: Phases should be as independent as possible to maximize parallelism

### Phase Sizing

- Aim for 4-8 items per phase (enough to justify a dedicated agent, small enough to complete in one session)
- If a phase has 10+ items, consider splitting by sub-concern
- If a phase has 1-2 items, consider merging with a related phase

### Dependency Minimization

- Prefer wide, shallow dependency graphs over deep chains
- Every dependency edge reduces parallelism — add only when truly required
- Common dependency patterns:
  - Bug fixes before tests (tests validate the fix)
  - Core changes before quality/style changes (avoid merge conflicts)
  - Implementation before integration tests

---

## Verification Strategy Template

Each phase's agent verifies its own change before handing it back: it rebases onto the main line, builds
once, and runs the suites of the packages it touched (`engineering-practices` §5, Hand-back). The lead does
not rebuild a phase to check it. After all phases complete:

1. **Integration run, only where phases met**: when two phases changed the same package, the phase that
   landed last reran that package's suite after rebasing onto the other; no other build is needed
2. **Test suite**: every phase reported its suites green, with counts, on its final base
3. **Lint/format**: All modified files pass linting
4. **Grep assertions**: Verify removed patterns are gone (e.g., `grep -r "deprecated_api"` returns nothing)
5. **Lock cleanup**: All lock files deleted (all phases completed)
6. **Log review**: Master log shows all phases completed, no unresolved ERRORs
7. **Diff review**: Manual review of all changes across phases for coherence

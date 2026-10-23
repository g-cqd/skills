# Orchestration Protocols

Detail for Orchestration Mode once it is chosen: file-lock synchronization between phases, the phase log
format, worktree policy, and how a change lands. `SKILL.md` carries the phase graph, the wave strategy, and
the hand-off summary; `references/orchestration-patterns.md` adds the full lock lifecycle and failure recovery.

## Contents

- Lock Protocol
- Log Protocol
- Worktrees
- Landing

## Lock Protocol

File-based locks for dependency synchronization:
1. Create `P1.lock` through `P{N}.lock` at plan start
2. Lock file content: phase, name, status, depends_on, started, completed, items
3. Agent reads lock, sets `in_progress`, checks dependency locks
4. Dependency check: `wait --gone P{N}.lock` (`~/.agent-harness/bin/wait`), which returns the moment the lock is deleted;
   never a fixed sleep
5. On completion: agent **deletes** lock file (absence = done)
6. An agent edits only files in its own phase's scope; touching a file owned by another in-progress phase produces conflicting edits that no lock can detect

## Log Protocol

Per-phase log `P{N}-{name}.log`:
```
[YYYY-MM-DDTHH:MM:SS] [P{N}{X}] START: {description}
[YYYY-MM-DDTHH:MM:SS] [P{N}{X}] DONE: {files modified}
[YYYY-MM-DDTHH:MM:SS] [P{N}{X}] ERROR: {issue}
```
Master log tracks phase-level lifecycle events.


## Worktrees

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

## Landing

- **The agent's last run is the verification** (`engineering-practices` §5, Hand-back). It rebased
  onto the main line, built once, and ran the suites of the packages the change touches, so the
  lead lands the change without building it again.
- **Land by fast-forward.** If the main line moved since the agent's run, rebase. The change needs
  a new run only if the main line changed the same packages, and then the agent reruns from its
  warm build.
- **A repository-wide quiet check,** such as a main-thread or timing budget, runs once per landing,
  and only when the change can affect it. Fold it into the agent's final suite run where the check
  runs the suite itself.

# Work Order and the Queue

Detail for Orchestration Mode (and any plan that runs several agents on one machine): the first-in, first-out
order, the `work` command table, and the shared queue's claim, capacity, limit, and wait rules. `SKILL.md` links here.

## Contents

- Work order: FIFO with two exceptions, `work order` and `work plan`, and the method table
- The shared queue: scope, the command table, and the rules for claim and accept, capacity, limits, waiting, and stale jobs

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

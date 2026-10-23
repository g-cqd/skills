# Work Order and the Queue

Detail for Orchestration Mode, and for any plan that runs several agents on one machine: the first-in, first-out
order, and how agents split the work. `SKILL.md` links here.

## Order

Work runs first in, first out: the tasks, their parts, and the work they cause. Keep one queue of what is not done;
new items go to its end; take the oldest first. Two classes jump or leave the line:

- **A regression that breaks validity** (correctness, safety, security, data): repair it before the work lands.
- **A regression or missed target that costs only performance:** the work lands, and the regression joins the end of
  the queue with its measurement and origin. It does not block the work.

A task whose prerequisite is not done waits. A prerequisite takes the urgency of the task that waits on it, so an
urgent fix never waits behind its own prerequisite. Two tasks that change the same files do not run together.

Keep the queue in your own task list: the harness's todo list, or a file in the scratch directory. No tool keeps it
for you.

## Several agents on one machine

Agents agree in a `chat` channel (`references/chat.md` has the commands). `chat` is the only shared state and has no
tasks or queue.

1. The lead opens a channel: `chat open NAME`. Each other agent follows it with `chat join CHANNEL`.
2. The lead posts one message per task, with the files the task changes. An agent that takes a task replies in that
   message's thread (`chat say CHANNEL "taking this" --re ID`). The oldest reply in the thread holds the task; an agent
   that sees an older reply picks another task.
3. An agent sets its state with `chat status busy "task title"` and clears it when it stops. `chat who` shows who works.
4. An agent posts the result in the task's thread. The lead reads the threads and closes the task in its own list.

Waiting is not part of the queue: use `wait` (`engineering-practices` §6).

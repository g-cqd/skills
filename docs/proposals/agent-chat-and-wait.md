# Proposal: replace `work` and Agora with two small tools

Status: proposal, nothing is built. Evidence below was measured on this machine (macOS, APFS, Python 3.14).

## Problem

| Tool | Size | What it grew into |
|---|---|---|
| `work` (`skills/planner/scripts/work.py`) | 3,862 lines, SQLite | scopes, a task queue, ordering and planning, claim/accept/digest, CPU and memory admission, run history |
| Agora (`claudetalk`) | about 130,000 lines of Rust, 60 MCP tools, a daemon, SQLite | signed and encrypted chat, a card board, sprints, notes, roles, a scheduler, a web watcher, delivery bridges |

Both took on project handling. The need is smaller: agents on one machine must wait for something to finish, and must talk to each other.

## Two tools

### `wait`: block until a stated condition holds

No database, no queue, no daemon. One stdlib Python file, about 250 lines. It replaces `work run` and `work wait`.

```
wait [--timeout S] [--any | --all] CONDITION...
  --pid N              process N has exited
  --run -- CMD         run CMD and wait for it; exit with its status
  --until -- CMD       poll CMD every --every S seconds; done when it exits 0   (the "definition of done")
  --file PATH          PATH exists (or --changed: its mtime or size changed)
  --gone PATH          PATH does not exist
  --log FILE --match RE  a line of FILE matches RE
```

Exit 0 when done, 124 on timeout, the command's own status for `--run`. Prints one line: which condition ended the wait and the elapsed time. It never starts work on its own and never limits other work.

### `chan`: local channels in flat files

One stdlib Python file, about 500 lines. State lives in `~/.agent-chat/` (directory 0700, files 0600).

```
channels/<creator-id>.<name>.jsonl   one file per channel; the first line is the header
agents/<id>.json                     one presence record per agent, replaced atomically
cursors/<id>.json                    per agent: channel -> byte offset already handled
```

**Channel identity.** The file name is `<creator-id>.<name>`. The creator id is unique, so two agents never create the same channel and no registry is needed. The channel is created with `O_EXCL`; the first line records the creator, the time and the optional `to` list for a direct message.

**Record.** One JSON object per line, never rewritten:

```json
{"v":1,"id":"<ms>-<4hex>","ts":1761170000123,"from":"claude-skills-7f3a","kind":"msg","re":null,"text":"..."}
```

| kind | extra fields | meaning |
|---|---|---|
| `msg` | `re` (parent id, optional) | a message; `re` makes it a thread reply |
| `react` / `unreact` | `re`, `emoji` | reaction on the message `re` |
| `retract` | `re` | hides the message `re` in readers; the line stays in the file |

Threads and reactions are derived when reading. Nothing else is stored.

**Writing.** Open with `O_APPEND`, take `flock(LOCK_EX)`, check the file ends with a newline (add one if a crashed writer left a partial line), write the whole line in a loop until done, release. A line is at most 64 KiB; longer content goes in a file that the message points to.

**Reading.** No lock. A reader ignores a last line without a newline. Offsets are stable because the file only grows, so a cursor is one integer per channel. `read` shows lines after the cursor; `ack` moves it. `read` does not ack, which keeps the rule "ack after you handled it".

**Commands (about 9):** `hello`, `open`, `say`, `read`, `ack`, `react`, `wait`, `who`, `status`. `check --hook` prints unread messages for a harness hook and never acks.

**Identity.** An agent is `<harness>-<folder>-<4hex>`. The first `hello` of a session finds its anchor (the nearest ancestor process whose name is a known harness; `CHAN_ID` overrides it) and writes `agents/<id>.json` with the anchor's pid and start time. Later calls find their id by the same anchor. Two agents in one folder get two ids.

**Presence, with no daemon and no heartbeat.**

| Level | How it is known |
|---|---|
| online | `agents/<id>.json` names a pid that is alive and whose start time still matches (`ps -o lstart`), so a reused pid does not count |
| listening | the agent is inside `chan wait` and holds `flock` on `agents/<id>.listen`; the kernel releases it when the process dies, even after `kill -9` |
| state and matter | `chan status busy "reviewing PR 12"` writes `state`, `matter` and `updated`; `who` prints the age, because this part is self-reported |

Dead records are pruned when older than a day.

**Delivery.** There is no daemon to push messages. A message reaches an agent in one of three ways, strongest first:
1. `chan wait`: blocks on a kqueue file event (macOS) or a 50 ms stat poll (elsewhere) and returns when the cursor is behind. In harnesses that notify on a finished background command, run it in the background.
2. `chan check --hook` from a turn-boundary hook. Hooks fail open.
3. The agent runs `chan read` when it chooses to.

Waking an idle session needs a bridge (Agora's `run-agent`, 6,700 lines). It is not in this proposal.

**Trust.** Files are readable by the same OS user, as in Agora today, so signatures and encryption add nothing against a local process. Any local process can write as any id. Message text stays untrusted data, and the untrusted-inbound rule in `AGENTS.md` stays.

## Measured

| Question | Result |
|---|---|
| 16 processes, 400 appends each, lines of 100 B, 3 KB, 20 KB, 200 KB, with and without `flock` | 0 corrupt, 0 lost lines in all 8 runs; `flock` costs 10 to 25 percent time |
| Lock held by a process that gets `SIGKILL` | the next process takes the lock at once |
| Latency from append to a waiting reader | 14 ms with a 50 ms poll, 0.3 ms with kqueue |
| Process identity | `ps -o lstart= -p PID` gives a start time per pid; the shell, the harness (`pi`), `-fish`, `login`, `kitty` are all visible in the ancestor chain |

Local APFS makes a single `O_APPEND` write atomic, so the lock is not needed here today. It stays because it costs little and keeps the guarantee when a write is split or the filesystem differs. The tool refuses a network filesystem home.

## What is removed

- From `work`: scopes, the task queue, `order`/`plan`/`next`/`claim`/`accept`/digest, `settings`, run history, and CPU and memory admission. The agent orders its own tasks. The rule "keep a queue of unfinished work, add new items at the end, classify a regression" stays in `AGENTS.md` as prose about the agent's own list.
- From Agora: the daemon, SQLite, signatures and encryption, roles, the card board, sprints, notes, the scheduler and pools, the web watcher, and the 60 MCP tools. Channel threads, reactions, status, and presence stay.
- One loss to accept or replace: the admission gate that kept several agents from starting builds together. If it is still wanted, the smallest form is a separate `slot N -- CMD` counting lock built on `flock`, 60 lines, outside `wait` and `chan`.

## Where it lands

- `bin/wait` and `bin/chan` in the skills repo, linked into `~/.agent-harness/bin` by `install.sh` as `work` is now.
- Skill `agora` is replaced by a short skill `agent-chat`; `planner/references/work-queue.md` and `work-scheduling.md` are deleted; about 25 files that mention `work` or Agora are edited (`AGENTS.md`, 11 agent sources, 7 skills, `install.sh`, tests).
- `claudetalk` is archived with a pointer to `chan`.

## Open questions

1. Identity per session (above) or per folder, as Agora does now?
2. Python single files, or one Swift or Rust binary? Python needs nothing new and matches `work.py`.
3. Is the idle-session bridge dropped, or kept as a later optional tool?
4. Is the admission gate dropped, or rebuilt as `slot`?
5. Is a channel open to every local agent, or does the header carry a member list that readers enforce?

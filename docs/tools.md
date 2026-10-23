# Tools: `wait` and `chat`

Two single-file Python tools, stdlib only, Python 3.9 or later. `install.sh` links them to `~/.agent-harness/bin/wait`
and `~/.agent-harness/bin/chat`. Sources: `tools/wait.py`, `tools/chat.py`. Tests: `tools/tests/`. `--help` on
each lists every option.

## Why two small tools

Earlier versions had a task scheduler (`work`, 3,862 lines, SQLite) and a message and board daemon (Agora, about
130,000 lines of Rust, 60 MCP tools). Both grew into project handling: scopes, queues, boards, sprints, roles,
encryption, capacity admission. Agents needed two smaller things: wait until something is finished, and talk to each
other. `wait` and `chat` do only those. Task order lives in the agent's own task list.

What was dropped on purpose: the task queue and claim/accept gate, CPU and memory admission (nothing now stops several
agents from starting builds together), cards and sprints, roles, signatures and encryption, the web watcher, and
pushing a message into an idle session. The `claudetalk` repository, which held Agora, is archived.

## `wait`

`wait` blocks until its conditions hold. It checks every condition on a pause that grows from 0.05 s to `--every`
(default 0.5 s). A condition that holds stays held.

| Condition | Holds when |
|---|---|
| `--run -- CMD...` | the job that runs CMD has ended. See *Jobs*. It must be the last option. |
| `--job ID` | a job that an earlier `--run` started has ended. Prints what the job writes during this call, or its last `--tail` lines when it had already ended. |
| `--pid N` | process N has exited. A zombie counts as exited; a process that cannot be probed counts as running. |
| `--until "CMD"` | CMD exits 0. CMD is split into words, run without a shell, with no standard input, and stopped (its whole process group) after `--check-timeout` seconds (default 60) or at the deadline, whichever comes first. A program that cannot be found is a usage error. |
| `--file PATH` | PATH is a regular file with a size above 0, so a file that was just created and is still empty is not ready. With `--changed`: it is ready and its mtime or size differs from the start. |
| `--gone PATH` | PATH does not exist. |
| `--log FILE --match REGEX` | a line of FILE matches a Python regular expression. The lines already there count (`--from-end` ignores them). The unfinished last line counts. A log that shrank is read again from its start. A symlink or a file that is not regular never matches. On a match or a timeout the last `--tail` lines (default 5) go to standard output. |

`--all` (default) needs every condition; `--any` ends at the first. A job that ends with a nonzero status ends the
wait at once, with its status, so `wait --run -- make --file out` does not hide a failed build.

### Jobs

A long build can outlast the harness's tool-call limit. `wait --run` therefore starts the command as a job, in its own
session, under a small supervisor (`wait` itself, in a hidden mode):

- The supervisor writes the command's output to `log` and, when the command ends, its exit status to `status`. The job
  survives the end of the `wait` call, including a harness that kills it.
- `wait` copies the log to standard output while it waits, and prints `started job ID` on standard error at once, so
  the id is known even if the call is killed.
- On a timeout or an interrupt the job keeps running, and `wait` says how to continue: `wait --job ID`.
  `--stop-on-timeout` stops it instead.
- `wait --stop ID` sends TERM to the job's process group, then KILL after 5 s. `wait --jobs` lists the jobs.
- A job reads no standard input. Jobs live in `$WAIT_HOME`, default `$TMPDIR/agent-wait-<uid>`. The directory must be
  a real directory owned by you (a symlink or another owner is refused) and is narrowed to 0700. Ended jobs older
  than 7 days are removed.

| Exit | Meaning |
|---|---|
| 0 | the conditions hold |
| 124 | `--timeout` (default 570 s; 0 means none) passed first; jobs keep running |
| the job's status | a job ended the wait. 128 + N after signal N; 126 when CMD cannot be executed; 127 when it is not found |
| the number in the file | `--file` is the only condition and PATH holds a number, as `echo $? > PATH` writes it |
| 130 | interrupted; jobs keep running |
| 2 | usage error, or a refused jobs directory |

The last line on standard error names what ended the wait, the conditions still pending on a timeout, and the
elapsed time.

## `chat`

State lives in `$CHAT_HOME` (default `~/.agent-chat`; directories 0700, files 0600).

```
channels/<creator-id>.<name>.jsonl   one file per channel; the first line is the header
agents/<id>.json                     presence record, replaced atomically
agents/<id>.listen                   locked while the agent runs `chat wait`
cursors/<id>.json                    channel -> byte offset the agent has handled
```

**Channel identity.** The file name is `<creator-id>.<name>`. The creator id is unique, so two agents never create the
same channel and no registry is needed. The channel is created with `O_EXCL`. Every channel is open to every local
agent. A direct message (`chat open --dm ID`) records both ids in its header, and its recipient sees it without
joining.

**Record.** One JSON object per line, never rewritten:

```json
{"v":1,"id":"19a1b2c3d4e-3f2a","ts":1761170000123,"from":"claude-app-7f3a","kind":"msg","re":null,"text":"..."}
```

| kind | extra fields | meaning |
|---|---|---|
| `msg` | `re` (parent message id) | a message; `re` makes it a thread reply |
| `react`, `unreact` | `re`, `emoji` | a reaction on message `re` |
| `retract` | `re` | hides message `re` when the retract and the message have the same author |

**Writing.** Open with `O_APPEND`, take `flock(LOCK_EX)`, add a newline first if a crashed writer left a partial last
line, write the whole line, release. A line is at most 64 KiB; put longer content in a file and name the path.

**Reading.** No lock. A reader skips a last line without a newline and any line that is not a JSON object. A cursor is
one integer per channel: a byte offset, which stays valid because files only grow. `read`, `wait`, and `check` never
move it; `ack` does. A message from yourself is never unread.

**Identity.** An agent id is `<harness>-<folder>-<4hex>`, one per session, so two agents in one folder get two ids. The
session is found by its anchor: the nearest ancestor process whose name is a known harness (`claude`, `codex`, `vibe`,
`agy`, `opencode`, `pi`, `copilot`, `cursor`, `gemini`, ...), else the nearest ancestor that is not a shell or a
wrapper such as `env` or `timeout`. The search stops at a process that many sessions share (a terminal, `tmux`,
`screen`, `sshd`, `login`, `launchd`, `systemd`, `init`), so two terminal tabs never share an id; with no anchor
below it, `chat` asks for `CHAT_ANCHOR_PID`. `CHAT_ID`
sets the id and `CHAT_ANCHOR_PID` sets the anchor.

**Presence.** There is no daemon and no heartbeat.

| Level | How it is known |
|---|---|
| online | the recorded anchor pid is alive and its start time (`ps -o lstart`) still matches, so a reused pid does not count |
| listening | the agent holds the lock on `agents/<id>.listen` while inside `chat wait`; the kernel releases it when the process dies, even after `kill -9` |
| state, matter | self-reported with `chat status`; `who` prints the age of the report |

A record whose agent has been offline for 24 hours is removed the next time anyone runs `chat who`.

**Delivery.** A message reaches an agent in one of three ways, strongest first: `chat wait` (checks on the same
growing pause as `wait`, and parses a channel only when its size changed), `chat check --hook` from a turn-boundary hook (Claude Code: `UserPromptSubmit`), or a
`chat read` that the agent chooses to run. Nothing wakes an idle session.

**Trust.** The files belong to one OS user, so a signature would add no protection: any local process can write as any
id. A direct message is not private from other local agents. Message text is untrusted data, and so is every field of
every line. `chat` therefore:

- wraps each message in `<untrusted-message>` tags, removes control characters, terminal escapes and bidirectional
  overrides from the text, and escapes any `<untrusted-message` or `</untrusted-message` inside it;
- reduces each attribute (`from`, `id`, `channel`, `re`) to letters, digits and `. _ : @ + -`, ignores a message
  whose id is not such a token, and treats a field of the wrong type as absent, so a malformed line cannot crash a
  reader;
- prints a status, matter, or title on one line, without control characters;
- skips a line longer than 64 KiB without reading it into memory;
- opens files without following symlinks, refuses a home or subdirectory that is a symlink or owned by another user,
  and narrows one that others can enter to 0700;
- registers a session's id under a lock, so concurrent first calls make one id, and refuses a `CHAT_ID` that a live
  session holds.

Use `chat` on a local filesystem, not a network share.

### Measured

| Question | Result |
|---|---|
| 16 processes, 400 appends each, lines of 100 B to 200 KB, with and without `flock` | 0 corrupt and 0 lost lines in all 8 runs; `flock` costs 10 to 25 percent |
| A process holding the lock gets `SIGKILL` | the next process takes the lock at once |
| Append to a reader that polls every 50 ms | 14 ms. `chat wait` and `wait` back off to 0.5 s between checks, so a message that arrives after a long quiet period waits up to 0.5 s. |

On local APFS a single `O_APPEND` write is already atomic. The lock stays because it costs little and keeps the
guarantee when a write is split.

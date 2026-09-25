#!/usr/bin/env python3
"""Coordinate the agents that share this machine: one queue of tasks, one view of the jobs, one capacity.

Several agents (sessions, subagents, Codex runs) work on one machine at once. `work` keeps in one SQLite database
what each scope works on, the tasks queued for any agent, and the jobs that run, with the CPU and memory each one
uses. An agent sees what the others do, takes a task that no other agent holds, and starts a job only when the
machine has room for it.

Rules:
  - Scopes: a project, a conversation or an agent, with an optional parent and the task it works on now. --scope S
    means S and every scope under it; it defaults to $WORK_SCOPE, and --scope '' means every scope.
  - Order: `order`, `plan` and `next` apply order_tasks.py to the queued tasks: validity first, then first in,
    first out, dependencies with priority inheritance, and the wsjf and critical-path policies.
  - Claim: `next` takes, in one transaction, the most urgent task whose prerequisites are done and whose files
    overlap no claimed or running task's files: an agent's best response in the congestion game of
    order_tasks.assign, given the tasks the other agents hold. File paths are stored absolute, so tasks in two
    projects conflict only when they change the same files.
  - Claim, then accept: nothing runs on its own. A queued command runs only when the agent that claimed its task
    has read it (`work show`, which prints its digest) and accepted it (`work accept ID --digest D`), whoever queued
    it: agent names are self-declared, so no name proves who wrote a command. Only a command typed inline with
    `work run -- ...` needs no acceptance. Commands are stored as argument lists and run without a shell.
  - Capacity: a job declares a weight, the cores it may use (default 1, at most the CPU count), but it is admitted
    on the cores it is predicted to use, from the history of its command: the median average cores (CPU time over
    run time) of the last 5 runs of the most specific signature that has enough of them, capped by the declared
    weight, which is the estimate while there is no history. A signature normalizes the command, with paths reduced
    to their last component and ids masked, and its directory counts as its repository and the path inside it, so
    worktrees share history. A job starts only while the running jobs' predicted cores plus its own fit the CPU
    budget (default the CPU count), and their declared weights plus its own fit the capacity when one is set (off
    by default), or when no job runs, and while the machine is not under pressure: the CPU at least idle-min idle
    (15%, measured over the supervisor's last poll), memory pressure below the memory limit (warning, from the
    kernel), and, on Linux only, the load average below the CPU count times the load factor (1.5). macOS counts
    threads that wait on memory and disk in its load average, so there it is shown, not used.
    Jobs that wait for room start in work order: validity first, then the order in which they asked, with backfill in
    predicted cores: a job behind the head may start first if it fits now and in the cores the head leaves free, or
    if it is small (small weight, 1 predicted core) while the head has waited less than the backfill wait (300 s)
    and no validity job is ahead of it. A head past the backfill wait keeps every job behind it, so none starves.
    Exclusive jobs, as heavy as the CPU count, are timing measurements: they hold the whole budget, whatever their
    history, and run in batches: when one starts, the exclusive jobs already waiting join its batch, and while the
    batch is open they start next, one at a time, ahead of every waiting job but validity work, so the machine
    drains once for the batch. An exclusive job that asks later waits for the next batch; a batch job whose
    supervisor is gone keeps no place, as any waiting job. A job that the machine's pressure
    alone holds back past the load wait fails. `work settings` shows and sets these values, kept
    in the database so that every agent's jobs are admitted alike: CPU budget, capacity, idle min, memory limit,
    load factor, backfill wait, small weight, load wait (1800 s), log limit, and how long events and logs are kept;
    `work status` shows the signals beside them and each job's prediction, and a waiting job's reason names the rule
    that holds it.
  - Jobs: a detached supervisor starts the command in its own process group with stdin closed, writes its output
    whole to a log, stops it if the log passes the log limit (256 MiB), samples the CPU and memory of its process
    tree every 2 s with ps, and records its true exit status: 127 when the command is missing, 126 when it cannot
    run, 128 plus the signal that killed it. `run` and `wait` return the moment the work ends, or 124 at --timeout
    (default 570 s) while it goes on.
  - Waiting: `wait` also waits on what `work` did not start: --pid until processes exit (a zombie has), --file until
    paths exist and are not empty (one file holding a number exits with that number, as a status file), --gone
    until paths are removed, --log until a line matches an extended regular expression (grep -E). These need no
    state and no name. Every wait checks with a pause that grows to --interval (0.5 s), and exits 124 at --timeout.
  - Sweep: `status`, `wait`, `next` and `claim` mark failed a job whose supervisor and command are gone with no
    recorded status. `status` and `run` delete events, and the logs of ended tasks, older than 14 days.

State: $AGENT_WORK_HOME/work.db (default ~/.local/state/agent-work), with job logs in logs/. The path is resolved
once; the directory must be yours and private (mode 700), and no directory above it may be a link, belong to another
user than you or root, or be writable by others. Titles, notes and paths refuse control and invisible characters,
and every text view escapes them in commands and job output. Agent names come from --agent or $WORK_AGENT, else
agent-<parent pid>: the shell that runs `work`, which changes with each new shell. No scope is needed.

Exit status: 0 on success; 1 when work refuses (a task in the wrong state, nothing to claim, a command not
accepted yet); 2 for an input error; for `run` and `wait`, the job's own status (or a status file's number), or 124
when the timeout passed first.
With --json, `timed_out` tells that timeout from a command that exits with 124 itself.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import math
import os
import re
import shlex
import signal
import sqlite3
import stat
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime

import order_tasks

SCRIPT = os.path.abspath(__file__)
FINAL = ("done", "failed", "cancelled")
SCOPE_KINDS = ("project", "conversation", "agent")
NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:@-]{0,127}")
KIND = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,63}")
DEFAULT_TIMEOUT = 570.0
CAPACITY_POLL = 1.0
SAMPLE_INTERVAL = 2.0
SWEEP_INTERVAL = 5.0
MAX_TEXT = 4000
MAX_ITEMS = 1000
MAX_COMMAND_BYTES = 256 * 1024

# Each entry takes the schema from one version to the next; a database records its version in PRAGMA user_version.
MIGRATIONS = ((
    """CREATE TABLE scopes (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL CHECK (kind IN ('project', 'conversation', 'agent')),
        parent TEXT REFERENCES scopes (id),
        task TEXT NOT NULL DEFAULT '',
        agent TEXT,
        created REAL NOT NULL,
        updated REAL NOT NULL
    )""",
    """CREATE TABLE tasks (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL DEFAULT '',
        kind TEXT NOT NULL DEFAULT 'other',
        scope TEXT REFERENCES scopes (id),
        author TEXT NOT NULL,
        queued REAL NOT NULL,
        after TEXT NOT NULL DEFAULT '[]',
        size REAL NOT NULL DEFAULT 1 CHECK (size > 0),
        value REAL NOT NULL DEFAULT 1 CHECK (value > 0),
        files TEXT NOT NULL DEFAULT '[]',
        command TEXT,
        cwd TEXT,
        weight REAL NOT NULL DEFAULT 1 CHECK (weight > 0),
        state TEXT NOT NULL DEFAULT 'queued'
            CHECK (state IN ('queued', 'claimed', 'running', 'done', 'failed', 'cancelled')),
        agent TEXT,
        accepted TEXT,
        claimed REAL,
        requested REAL,
        started REAL,
        ended REAL,
        owner INTEGER,
        owner_since REAL,
        pid INTEGER,
        status INTEGER,
        log TEXT,
        cpu REAL,
        rss INTEGER,
        rss_peak INTEGER,
        cpu_time REAL,
        sampled REAL,
        note TEXT NOT NULL DEFAULT ''
    )""",
    "CREATE INDEX tasks_by_state ON tasks (state)",
    """CREATE TABLE events (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        time REAL NOT NULL,
        scope TEXT,
        task TEXT,
        agent TEXT,
        what TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT ''
    )""",
), (
    # One row for the whole machine: every agent's jobs are admitted by the same capacity and limits.
    """CREATE TABLE settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        capacity REAL CHECK (capacity IS NULL OR capacity > 0),
        load_factor REAL NOT NULL DEFAULT 1.5 CHECK (load_factor > 0),
        load_wait REAL NOT NULL DEFAULT 1800 CHECK (load_wait > 0),
        log_limit INTEGER NOT NULL DEFAULT 268435456 CHECK (log_limit > 0),
        keep_days REAL NOT NULL DEFAULT 14 CHECK (keep_days > 0),
        pruned REAL
    )""",
    "INSERT INTO settings (id) VALUES (1)",
    "CREATE INDEX events_by_time ON events (time)",
), (
    # The machine gate reads idle CPU and memory pressure; the load average stays a gate on Linux only.
    "ALTER TABLE settings ADD COLUMN idle_min REAL NOT NULL DEFAULT 15 CHECK (idle_min >= 0 AND idle_min < 100)",
    "ALTER TABLE settings ADD COLUMN memory_limit TEXT NOT NULL DEFAULT 'warning' "
    "CHECK (memory_limit IN ('warning', 'critical', 'off'))",
), (
    # Backfill: a later job may start past a waiting head that cannot, within these bounds.
    "ALTER TABLE settings ADD COLUMN backfill_wait REAL NOT NULL DEFAULT 300 CHECK (backfill_wait > 0)",
    "ALTER TABLE settings ADD COLUMN small_weight REAL NOT NULL DEFAULT 1 CHECK (small_weight > 0)",
), (
    # Exclusive batches: the batch an exclusive job belongs to, named by the batch's first job.
    "ALTER TABLE tasks ADD COLUMN batch TEXT",
), (
    # Command signatures, one per level from the most specific to the most general, so that a job's history is one
    # indexed query. The jobs already recorded are signed too, so that their history counts at once.
    "ALTER TABLE tasks ADD COLUMN sig_full TEXT",
    "ALTER TABLE tasks ADD COLUMN sig_head TEXT",
    "ALTER TABLE tasks ADD COLUMN sig_prog TEXT",
    "ALTER TABLE tasks ADD COLUMN sig_tool TEXT",
    "CREATE INDEX tasks_by_sig_full ON tasks (sig_full, ended)",
    "CREATE INDEX tasks_by_sig_head ON tasks (sig_head, ended)",
    "CREATE INDEX tasks_by_sig_prog ON tasks (sig_prog, ended)",
    "CREATE INDEX tasks_by_sig_tool ON tasks (sig_tool, ended)",
    lambda conn: sign_recorded(conn),
), (
    # A job's prediction from its history, recorded as it asks for capacity: average cores, peak memory in KiB, run
    # time in seconds, and what they come from.
    "ALTER TABLE tasks ADD COLUMN pred_cores REAL",
    "ALTER TABLE tasks ADD COLUMN pred_rss INTEGER",
    "ALTER TABLE tasks ADD COLUMN pred_duration REAL",
    "ALTER TABLE tasks ADD COLUMN pred_from TEXT",
), (
    # Admission counts predicted cores against the CPU budget (NULL: the CPU count). The capacity becomes an optional
    # cap on declared weights: NULL, which meant the CPU count minus 2, now means no cap; a value set is kept.
    "ALTER TABLE settings ADD COLUMN cpu_budget REAL CHECK (cpu_budget IS NULL OR cpu_budget > 0)",
))
SCHEMA_VERSION = len(MIGRATIONS)


class WorkError(Exception):
    """A command that cannot go on: `status` is 2 for bad input, 1 for a refusal."""

    def __init__(self, message: str, status: int = 2):
        super().__init__(message)
        self.status = status


def refusal(message: str) -> WorkError:
    return WorkError(message, 1)


# MARK: - Input


def check_name(value: str, what: str) -> str:
    """`value` as an id, a scope or an agent name; names become log file names, so they hold no path separator."""
    if not NAME.fullmatch(value):
        raise WorkError(f"{what} {value!r} is not valid: use up to 128 letters, digits, _ . : @ or -, "
                        "starting with a letter, a digit or _")
    return value


def check_text(value: str, what: str, limit: int = MAX_TEXT) -> str:
    """`value` as a title, a note, a scope's task or a path: printable characters only. A control character, an escape
    sequence, a carriage return or a direction override would let a text rewrite the terminal of the agent that
    reads it; NUL and unpaired surrogates are not printable either."""
    if len(value) > limit:
        raise WorkError(f"{what} is longer than {limit} characters")
    hidden = next((char for char in value if not char.isprintable()), None)
    if hidden is not None:
        raise WorkError(f"{what} holds the control or invisible character {hidden!r}")
    return value


def check_command(argv: list[str]) -> list[str]:
    if not argv:
        raise WorkError("no command after --")
    size = sum(len(item.encode("utf-8", "surrogateescape")) + 1 for item in argv)
    if len(argv) > MAX_ITEMS or size > MAX_COMMAND_BYTES:
        raise WorkError(f"the command is longer than {MAX_ITEMS} arguments or {MAX_COMMAND_BYTES} bytes")
    if any("\x00" in item for item in argv):
        raise WorkError("the command holds a NUL character")
    return argv


def positive(text: str) -> float:
    value = duration(text)
    if value == 0:
        raise argparse.ArgumentTypeError(f"{text!r} is not greater than zero")
    return value


def duration(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from None
    if not (math.isfinite(value) and value >= 0):
        raise argparse.ArgumentTypeError(f"{text!r} is not a finite number, zero or more")
    return value


def percent(text: str) -> float:
    value = duration(text)
    if value >= 100:
        raise argparse.ArgumentTypeError(f"{text!r} is not below 100")
    return value


def capacity_setting(text: str) -> float | str:
    """A cap on declared cores, or off (auto, the older name of the default, means off too)."""
    return "off" if text in ("off", "auto") else positive(text)


def budget_setting(text: str) -> float | str:
    return "auto" if text == "auto" else positive(text)


def counting(minimum: int):
    def parse(text: str) -> int:
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
        if value < minimum:
            raise argparse.ArgumentTypeError(f"{text!r} is less than {minimum}")
        return value

    return parse


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def working_directory(given: str | None) -> str:
    try:
        path = os.path.abspath(os.path.expanduser(given)) if given else os.getcwd()
    except OSError as error:
        raise WorkError(f"the current directory is gone: {error.strerror}") from None
    if not os.path.isdir(path):
        raise WorkError(f"{printable(path)} is not a directory")
    return check_text(path, "the directory")


def canonical_files(paths: list[str], base: str) -> list[str]:
    """Each path, relative to `base`, made absolute with its links resolved, so equal files compare equal."""
    if len(paths) > MAX_ITEMS:
        raise WorkError(f"more than {MAX_ITEMS} files")
    result = []
    for path in paths:
        if not path or "\x00" in path:
            raise WorkError(f"{path!r} is not a file path")
        result.append(check_text(os.path.realpath(os.path.join(base, os.path.expanduser(path))), "a file path"))
    return unique(result)


# MARK: - Output


def printable(text: str) -> str:
    """`text` with each control or invisible character written as an escape, so the reader sees every character: a
    carriage return or a direction override cannot hide part of a command that an agent is about to accept."""
    if text.isprintable():
        return text
    return "".join(char if char.isprintable() else repr(char)[1:-1] for char in text)


def display(argv: list[str]) -> str:
    return printable(shlex.join(argv))


def brief(argv: list[str], limit: int = 200) -> str:
    """A command for a one-line view, cut to `limit` characters; `show` prints it whole."""
    text = display(argv)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def capped(label: str, items: list[str], limit: int = 10) -> str:
    """A list for a text view, cut to its first `limit` items, so that a long list cannot flood the view."""
    if len(items) <= limit:
        return f"{label}: {', '.join(items)}"
    return f"{label} (the first {limit} of {len(items)}; all of them with --json): {', '.join(items[:limit])}"


def say(message: str) -> None:
    print(f"work: {message}", flush=True)


def emit(data: object) -> None:
    print(json.dumps(data, indent=2), flush=True)


def span(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 60:
        return f"{seconds:.1f} s"
    if seconds < 3600:
        return f"{int(seconds // 60)} min {int(seconds % 60)} s"
    return f"{int(seconds // 3600)} h {int(seconds % 3600 // 60)} min"


def memory(kib: int | None) -> str:
    if kib is None:
        return "-"
    if kib < 10 * 1024 * 1024:
        return f"{kib / 1024:.0f} MiB"
    return f"{kib / 1024 / 1024:.1f} GiB"


def clock(stamp: float | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stamp)) if stamp else "-"


def iso(stamp: float | None) -> str | None:
    return datetime.fromtimestamp(stamp).astimezone().isoformat(timespec="seconds") if stamp else None


def tail(path: str | None, lines: int) -> list[str]:
    """The last `lines` lines of a log, read from its end, so a large log costs no more than a small one."""
    if not path or lines <= 0:
        return []
    try:
        with open(path, "rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            handle.seek(max(0, size - 64 * 1024))
            data = handle.read()
    except OSError:
        return []
    return data.decode("utf-8", "replace").splitlines()[-lines:]


# MARK: - Storage


class Context:
    """What a command runs with: its environment, the state directory, and one database connection."""

    def __init__(self, env: dict[str, str]):
        self.env = env
        raw = env.get("AGENT_WORK_HOME") or os.path.join("~", ".local", "state", "agent-work")
        # Resolved once: every later use, SQLite's included, names the directory that connect() checked.
        self.home = os.path.realpath(os.path.expanduser(raw))
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = connect(self.home)
        return self._conn

    @property
    def logs(self) -> str:
        return os.path.join(self.home, "logs")

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def agent(self, given: str | None) -> str:
        """--agent, else $WORK_AGENT, else agent-<parent pid>: the shell that runs `work`, so that an agent that set
        nothing can still run and wait. That default changes with each new shell; an agent that claims a task in one
        call and runs it in another sets $WORK_AGENT."""
        return self.optional_agent(given) or self.default_agent

    @property
    def default_agent(self) -> str:
        return f"agent-{os.getppid()}"

    def optional_agent(self, given: str | None) -> str | None:
        name = given if given is not None else self.env.get("WORK_AGENT", "")
        return check_name(name, "agent") if name else None

    def scope(self, given: str | None) -> str | None:
        """The scope a command works in: --scope, else $WORK_SCOPE; None, meaning every scope, when both are empty."""
        name = given if given is not None else self.env.get("WORK_SCOPE", "")
        if not name:
            return None
        check_name(name, "scope")
        if self.conn.execute("SELECT 1 FROM scopes WHERE id = ?", (name,)).fetchone() is None:
            raise WorkError(f"unknown scope {name}; create it with `work scope set {name} --kind project`")
        return name


def connect(home: str) -> sqlite3.Connection:
    """The shared database under `home`, created with its schema if needed, in WAL mode so readers never wait for a
    writer; the 30 s busy timeout makes concurrent writers queue instead of failing."""
    logs = os.path.join(home, "logs")
    path = os.path.join(home, "work.db")
    try:
        # Each directory is checked before anything is created inside it.
        parts = [part for part in home.split(os.sep) if part]
        current = os.sep
        guard(current, private=False)
        for depth, part in enumerate(parts, start=1):
            current = os.path.join(current, part)
            if not os.path.lexists(current):
                with suppress(FileExistsError):  # Another agent created it first; the guard checks it all the same.
                    os.mkdir(current, 0o700)
            guard(current, private=depth == len(parts))
        if not os.path.lexists(logs):
            with suppress(FileExistsError):
                os.mkdir(logs, 0o700)
        guard(logs, private=True)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise refusal(f"{printable(path)} must be a file of yours that only you can read and write (chmod 600)")
    except OSError as error:
        raise refusal(f"cannot prepare {printable(home)}: {error.strerror}") from None
    conn = sqlite3.connect(path, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    migrate(conn)
    return conn


def guard(path: str, private: bool) -> None:
    """Refuses a component of the state directory that another user could replace or change, since the queue holds
    commands that agents run: a symbolic link, which could be swapped; anything owned by a user other than you or
    root; a directory that others can write. The state directory itself (`private`) must be yours and mode 700."""
    info = os.lstat(path)
    shown = printable(path)
    if stat.S_ISLNK(info.st_mode):
        raise refusal(f"{shown} is a symbolic link; set AGENT_WORK_HOME to a path without one")
    if not stat.S_ISDIR(info.st_mode):
        raise refusal(f"{shown} is not a directory")
    if info.st_uid != os.getuid() and (private or info.st_uid != 0):
        raise refusal(f"{shown} belongs to another user")
    if private and info.st_mode & 0o077:
        raise refusal(f"{shown} must be private to you: chmod 700 {shlex.quote(path)}")
    if info.st_mode & 0o022:
        raise refusal(f"{shown} is writable by other users, who could replace the state directory under it")


def migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == SCHEMA_VERSION:
        return
    if version > SCHEMA_VERSION:
        raise refusal(f"the database has schema version {version}, newer than this work.py's {SCHEMA_VERSION}")
    conn.execute("PRAGMA journal_mode = WAL")
    with writing(conn):
        for statements in MIGRATIONS[conn.execute("PRAGMA user_version").fetchone()[0]:]:
            for statement in statements:
                # A step that SQL alone cannot express is a function of the connection, run in the same transaction.
                statement(conn) if callable(statement) else conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


@contextmanager
def writing(conn: sqlite3.Connection):
    """One write transaction. BEGIN IMMEDIATE takes the write lock first, so two agents that read the same queue can
    never both act on what they read."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


@contextmanager
def reading(conn: sqlite3.Connection):
    """One read transaction: every query inside sees the same snapshot."""
    conn.execute("BEGIN")
    try:
        yield conn
    finally:
        conn.execute("COMMIT")


def record(conn: sqlite3.Connection, what: str, *, task: str | None = None, scope: str | None = None,
           agent: str | None = None, detail: str = "") -> None:
    conn.execute("INSERT INTO events (time, scope, task, agent, what, detail) VALUES (?, ?, ?, ?, ?, ?)",
                 (time.time(), scope, task, agent, what, detail))


def in_scope(column: str) -> str:
    """SQL that holds when `column` names the scope :scope or a scope under it, and always when :scope is NULL."""
    return (f"(:scope IS NULL OR {column} IN (WITH RECURSIVE under(id) AS (SELECT :scope UNION "
            f"SELECT scopes.id FROM scopes JOIN under ON scopes.parent = under.id) SELECT id FROM under))")


def get_task(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise WorkError(f"unknown task {task_id}")
    return row


def states_of(conn: sqlite3.Connection, ids) -> dict[str, str]:
    ids = list(ids)
    states = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        marks = ",".join("?" * len(chunk))
        states.update(conn.execute(f"SELECT id, state FROM tasks WHERE id IN ({marks})", chunk).fetchall())
    return states


def new_id(conn: sqlite3.Connection, prefix: str) -> str:
    number = conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM tasks").fetchone()[0]
    while conn.execute("SELECT 1 FROM tasks WHERE id = ?", (f"{prefix}-{number}",)).fetchone():
        number += 1
    return f"{prefix}-{number}"


# MARK: - Tasks


def order_task(row: sqlite3.Row, index: int, after: list[str] = ()) -> order_tasks.Task:
    """The order_tasks view of a row; `index` is its arrival rank and `after` the prerequisites to keep. The title is
    escaped, since order_tasks.render prints it as it is."""
    return order_tasks.make_task({
        "id": row["id"], "title": printable(row["title"]), "kind": row["kind"], "after": list(after),
        "size": row["size"], "value": row["value"], "files": json.loads(row["files"]),
    }, index)


def needs_acceptance(row: sqlite3.Row) -> bool:
    """Whether the claimant must still accept the command before it runs. Every queued command needs it, whoever
    queued it: agent names are self-declared, and a subagent inherits its parent's, so "my own command" proves
    nothing. Only a command typed inline with `work run -- ...` is accepted as it is created."""
    return bool(row["command"]) and row["agent"] is not None and row["accepted"] != row["agent"]


def digest(row: sqlite3.Row) -> str | None:
    """The SHA-256 of a task's command and directory, which `show` prints and `accept --digest` must repeat, so that
    an acceptance holds for exactly what was read."""
    if not row["command"]:
        return None
    canonical = json.dumps([json.loads(row["command"]), row["cwd"]], separators=(",", ":"))
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def command_size(argv: list[str]) -> str:
    size = sum(len(item.encode("utf-8", "surrogateescape")) for item in argv) + max(0, len(argv) - 1)
    return f"{len(argv)} argument{'s' if len(argv) != 1 else ''}, {size} bytes"


def waited_of(row: sqlite3.Row, now: float) -> float | None:
    if row["requested"] is None:
        return None
    return max(0.0, (row["started"] or row["ended"] or now) - row["requested"])


def ran_of(row: sqlite3.Row, now: float) -> float | None:
    if row["started"] is None:
        return None
    return max(0.0, (row["ended"] or now) - row["started"])


def exit_status(row: sqlite3.Row) -> int:
    if row["status"] is not None:
        return row["status"]
    return 0 if row["state"] == "done" else 1


def describe_state(row: sqlite3.Row) -> str:
    state = row["state"]
    if state == "claimed" and row["requested"] is not None:
        return f"waiting for capacity (claimed by {row['agent']})"
    if state == "claimed":
        return f"claimed by {row['agent']}"
    if state == "running":
        return f"running as process {row['pid']} (claimed by {row['agent']})" if row["pid"] else "starting"
    if state == "failed" and row["status"] is not None:
        return f"failed with status {row['status']}"
    return state


def task_json(row: sqlite3.Row, now: float | None = None) -> dict:
    now = now if now is not None else time.time()
    rounded = lambda value: None if value is None else round(value, 3)  # noqa: E731
    return {
        "id": row["id"], "title": row["title"], "kind": row["kind"],
        "tier": order_tasks.Task(row["id"], kind=row["kind"]).tier,
        "scope": row["scope"], "author": row["author"], "state": row["state"], "agent": row["agent"],
        "accepted_by": row["accepted"], "needs_acceptance": needs_acceptance(row),
        "after": json.loads(row["after"]), "size": row["size"], "value": row["value"],
        "files": json.loads(row["files"]), "weight": row["weight"],
        "command": json.loads(row["command"]) if row["command"] else None, "cwd": row["cwd"], "digest": digest(row),
        "queued": iso(row["queued"]), "claimed": iso(row["claimed"]), "requested": iso(row["requested"]),
        "started": iso(row["started"]), "ended": iso(row["ended"]),
        "waited": rounded(waited_of(row, now)), "ran": rounded(ran_of(row, now)),
        "status": row["status"], "pid": row["pid"], "supervisor": row["owner"], "log": row["log"],
        "batch": row["batch"],
        "predicted": None if row["pred_cores"] is None else {
            "cores": rounded(row["pred_cores"]), "rss_kib": row["pred_rss"], "duration": rounded(row["pred_duration"]),
            "from": row["pred_from"]},
        "cpu_percent": row["cpu"], "rss_kib": row["rss"], "rss_peak_kib": row["rss_peak"],
        "cpu_seconds": rounded(row["cpu_time"]), "sampled": iso(row["sampled"]), "note": row["note"],
    }


@dataclass
class Queue:
    """The queued tasks of a scope: their rows, their order_tasks graph over the queued prerequisites, and for each
    task the prerequisites that are not done yet, with their states."""

    rows: dict[str, sqlite3.Row]
    graph: order_tasks.Graph
    waits: dict[str, list[tuple[str, str]]]


def queue(conn: sqlite3.Connection, scope: str | None) -> Queue:
    rows = conn.execute(f"SELECT * FROM tasks WHERE state = 'queued' AND {in_scope('scope')} ORDER BY seq",
                        {"scope": scope}).fetchall()
    states = states_of(conn, {item for row in rows for item in json.loads(row["after"])})
    queued = {row["id"] for row in rows}
    tasks, waits = [], {}
    for index, row in enumerate(rows):
        after = json.loads(row["after"])
        waits[row["id"]] = [(item, states.get(item, "unknown")) for item in after if states.get(item) != "done"]
        tasks.append(order_task(row, index, [item for item in after if item in queued]))
    try:
        graph = order_tasks.Graph(tasks)
    except order_tasks.InputError as error:
        raise refusal(f"the queue cannot be ordered: {error}") from None
    return Queue({row["id"]: row for row in rows}, graph, waits)


def holders(conn: sqlite3.Connection) -> list[tuple[order_tasks.Task, sqlite3.Row]]:
    """The claimed and running tasks that hold files, which no other task may change until they end."""
    rows = conn.execute("SELECT * FROM tasks WHERE state IN ('claimed', 'running') AND files != '[]'").fetchall()
    return [(order_task(row, index), row) for index, row in enumerate(rows)]


def holder_of(task: order_tasks.Task, held: list[tuple[order_tasks.Task, sqlite3.Row]]) -> sqlite3.Row | None:
    return next((row for other, row in held if order_tasks.conflict(task, other)), None)


def take(conn: sqlite3.Connection, row: sqlite3.Row, agent: str) -> None:
    conn.execute("UPDATE tasks SET state = 'claimed', agent = ?, claimed = ? WHERE id = ? AND state = 'queued'",
                 (agent, time.time(), row["id"]))
    record(conn, "claimed", task=row["id"], scope=row["scope"], agent=agent)


def default_name_note(ctx: Context, args: argparse.Namespace, agent: str) -> list[str]:
    """A note for an agent that holds a task under the default name, which the next shell will not share."""
    if args.agent is not None or ctx.env.get("WORK_AGENT"):
        return []
    return [f"you are {agent}, the default name, which lasts as long as this shell; to run or close the task from "
            f"another call, set WORK_AGENT={agent}"]


def next_steps(row: sqlite3.Row) -> list[str]:
    task_id = row["id"]
    if row["command"] is None:
        return [f"close it with `work done {task_id}` or `work fail {task_id}` when it is finished"]
    if needs_acceptance(row):
        return [f"{task_id} runs a command that {row['author']} queued; read it with `work show {task_id}`, and "
                f"if it is right, accept it with the `work accept {task_id} --digest ...` line that show prints, "
                f"then `work run {task_id}`"]
    return [f"run it with `work run {task_id}`"]


# MARK: - Signatures

# The levels of a command signature, from the most specific to the most general, each with the number of past runs it
# needs before a prediction uses it. The specific levels need fewer runs: they match only the same command.
SIGNATURE_LEVELS = (("full", 1), ("head", 2), ("prog", 3), ("tool", 3))
SHELLS = frozenset({"sh", "bash", "zsh", "dash"})
INTERPRETERS = frozenset({"sh", "bash", "zsh", "dash", "python", "python3", "perl", "ruby", "node"})
WRAPPERS = frozenset({"env", "xcrun", "time", "nice", "caffeinate", "command", "exec", "timeout", "gtimeout"})
PRELUDE = frozenset({"cd", "export", "set", "true", ":", "source", ".", "ulimit", "rm", "mkdir", "echo", "unset",
                     "trap", "sleep", "cp", "mv", "ln", "test", "[", "wait", "exit", "printf"})
OPERATORS = frozenset({";", "&&", "||", "|", "&", "\n", "(", ")", "{", "}", "|&", ";;"})
REDIRECT = re.compile(r"\d*[<>]+&?\d*|&>+")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
UUID = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")
HEX_ID = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,}\b")
LONG_NUMBER = re.compile(r"\d{3,}")
DIGITS = re.compile(r"\d+")
SCRATCH = tuple(sorted({"/tmp", "/private/tmp", "/var/folders", "/private/var/folders",
                        os.path.realpath(tempfile.gettempdir())}))


def scrub(text: str) -> str:
    """`text` with ids and long numbers masked, so that two runs of one command differ in none of them."""
    return LONG_NUMBER.sub("#", HEX_ID.sub("<id>", UUID.sub("<id>", text)))


def path_tag(token: str) -> str:
    """A path reduced to its last component with its digits masked: /x/y/run-12.sh is <p:run-#.sh>."""
    return f"<p:{DIGITS.sub('#', scrub(token.rstrip('/').rsplit('/', 1)[-1] or '/'))}>"


def looks_like_path(token: str) -> bool:
    """Whether a token names a file: it starts with /, ~, ./ or ../, or holds a / and is not a URL nor an owner/name
    pair such as a git remote branch."""
    if token.startswith(("/", "~", "./", "../")):
        return True
    return "/" in token and not token.startswith(("http://", "https://")) \
        and not re.fullmatch(r"[\w.-]+/[\w.-]+", token)


def normal_token(token: str) -> str:
    if ASSIGNMENT.match(token) or (token.startswith("--") and "=" in token):
        name, _, value = token.partition("=")
        return f"{name}={normal_token(value) if value else ''}"
    return path_tag(token) if looks_like_path(token) else scrub(token)


def shell_tokens(argv: list[str]) -> list[str]:
    """The argv, with the script of `sh -c SCRIPT` split into its own words and operators."""
    if argv and os.path.basename(argv[0]) in SHELLS and "-c" in argv[1:3]:
        index = argv.index("-c")
        script = argv[index + 1] if index + 1 < len(argv) else ""
        lexer = shlex.shlex(script, posix=True, punctuation_chars=";&|()<>")
        lexer.whitespace_split = True
        try:
            return list(lexer)
        except ValueError:
            return script.split()
    return list(argv)


def simple_commands(tokens: list[str]) -> list[list[str]]:
    """The simple commands of a token stream, split at shell operators, without redirections and their targets."""
    commands, current, skip = [], [], False
    for token in tokens:
        if skip:
            skip = False
        elif token in OPERATORS or (token and set(token) <= set(";&|()")):
            if current:
                commands.append(current)
            current = []
        elif REDIRECT.fullmatch(token):
            skip = not re.search(r"&\d$", token)
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def program_part(command: list[str]) -> list[str]:
    """A simple command without its leading VAR=value assignments and wrappers (env, xcrun, time, timeout...), with
    a wrapper's options, and timeout's duration."""
    index = 0
    while index < len(command):
        token, name = command[index], os.path.basename(command[index])
        if ASSIGNMENT.match(token):
            index += 1
        elif name in WRAPPERS:
            index += 1
            while index < len(command) and command[index].startswith("-") and name != "xcrun":
                index += 1
            if name in ("timeout", "gtimeout") and index < len(command):
                index += 1
        else:
            break
    return command[index:]


def flag_key(flag: str) -> str:
    """A flag with a path glued to it (-I/x/y) keeps its prefix, the path's tag, and a short digest that keeps two
    paths apart without writing either."""
    cut = flag.find("/") if "/" in flag else flag.find("~")
    if cut < 0:
        return flag
    path = flag[cut:]
    return f"{flag[:cut]}{path_tag(path)[:-1]}~{hashlib.sha256(path.encode('utf-8', 'surrogateescape')).hexdigest()[:6]}>"


def place(cwd: str | None) -> str:
    """The kind of directory a job runs in, alike for every checkout and worktree of one repository: the repository's
    name and the path inside it; `tmp` for a scratch directory; else the directory's own name. Digits are masked."""
    if not cwd:
        return "none"
    path = current = os.path.normpath(cwd)
    while True:
        marker = os.path.join(current, ".git")
        if os.path.isdir(marker) or os.path.isfile(marker):
            name = (main_checkout(marker) if os.path.isfile(marker) else None) or os.path.basename(current)
            inside = os.path.relpath(path, current)
            return DIGITS.sub("#", name if inside == "." else f"{name}/{inside}")
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    if any(path == root or path.startswith(root + os.sep) for root in SCRATCH):
        return "tmp"
    return DIGITS.sub("#", os.path.basename(path) or "/")


def main_checkout(marker: str) -> str | None:
    """The name of the main checkout of a linked worktree, from its .git file (gitdir: MAIN/.git/worktrees/NAME)."""
    try:
        with open(marker, encoding="utf-8", errors="replace") as handle:
            text = handle.read(4096)
    except OSError:
        return None
    target = (text.splitlines() or [""])[0].partition("gitdir:")[2].strip()
    main, found, _ = target.partition(f"{os.sep}.git{os.sep}worktrees{os.sep}")
    return os.path.basename(main) if found and main else None


def compact(text: str, limit: int = 256) -> str:
    """`text` if it is short; else its start and a digest of the whole, so that long signatures stay distinct."""
    if len(text) <= limit:
        return text
    return f"{text[:limit - 34]}~{hashlib.sha256(text.encode('utf-8', 'surrogateescape')).hexdigest()[:32]}"


def signatures(argv: list[str], cwd: str | None) -> dict[str, str]:
    """A command's signatures, most specific first, the same whichever agent runs it and in whichever worktree:
      full: every word of the command, `sh -c` scripts split, normalized, with the kind of directory: a digest;
      head: the main simple command's program, subcommand and flags, without their values, but with --jobs and the
            build configuration, with the kind of directory;
      prog: the program and its subcommand, with the kind of directory;
      tool: the program and its subcommand alone.
    Paths are reduced to their last component, and ids and long numbers are masked, so no path or id is kept whole."""
    tokens, kind = shell_tokens(argv), place(cwd)
    full = " ".join(normal_token(token) for token in tokens)
    commands = [part for part in (program_part(command) for command in simple_commands(tokens)) if part]
    main = next((part for part in commands if os.path.basename(part[0]) not in PRELUDE),
                commands[0] if commands else [""])
    if os.path.basename(main[0]) in INTERPRETERS:
        script = next((token for token in main[1:] if not token.startswith("-")), None)
        if script and (looks_like_path(script) or re.search(r"\.(sh|py|rb|js|pl)$", script)):
            main = main[main.index(script):]
    program = path_tag(main[0])[3:-1] if looks_like_path(main[0]) else scrub(main[0])
    sub = next((token for token in main[1:] if not token.startswith("-") and not looks_like_path(token)), "")
    sub = scrub(sub) if re.fullmatch(r"[a-z][a-z0-9-]*", sub or "-") else ""
    flags = sorted({flag_key(token.split("=", 1)[0]) for token in main[1:] if token.startswith("-")})
    jobs = next((main[index + 1] for index, token in enumerate(main[:-1]) if token in ("--jobs", "-j")), None)
    config = next((main[index + 1] for index, token in enumerate(main[:-1])
                   if token in ("-c", "--configuration")), None)
    head = " ".join([program, sub, *flags] + ([f"jobs={jobs}"] if jobs and jobs.isdigit() else [])
                    + ([f"config={config}"] if config in ("debug", "release") else []))
    tool = f"{program} {sub}".rstrip()
    digest_of = hashlib.sha256(f"{kind} :: {full}".encode("utf-8", "surrogateescape")).hexdigest()[:32]
    return {"full": digest_of, "head": compact(f"{kind} :: {' '.join(head.split())}"),
            "prog": compact(f"{kind} :: {tool}"), "tool": compact(tool)}


def sign_recorded(conn: sqlite3.Connection) -> None:
    """Signs the tasks already recorded, as the migration that adds signatures runs. A command that cannot be read is
    left unsigned: it has no history, which predicts nothing."""
    rows = conn.execute("SELECT seq, command, cwd FROM tasks WHERE command IS NOT NULL").fetchall()
    for seq, command, cwd in rows:
        try:
            argv = json.loads(command)
            if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
                continue
            signed = signatures(argv, cwd)
        except (ValueError, TypeError, OSError):
            continue
        conn.execute("UPDATE tasks SET sig_full = ?, sig_head = ?, sig_prog = ?, sig_tool = ? WHERE seq = ?",
                     (*(signed[level] for level, _ in SIGNATURE_LEVELS), seq))


# MARK: - Predictions

HISTORY = 5  # The runs of a signature that a prediction reads, the most recent first.
RECENT = 200  # The recent jobs whose median run time stands in for a job without history.
DEFAULT_DURATION = 30.0  # The run time of a job without history when no job has run yet, in seconds.
MIN_CORES = 0.1
SOURCES = {"full": "the same command", "head": "the same program and flags", "prog": "the same program in this place",
           "tool": "the same program"}
# A run teaches something only if its command ran: 126 and 127 mean it could not start.
RAN = ("status IS NOT NULL AND status NOT IN (126, 127) AND started IS NOT NULL AND ended IS NOT NULL "
       "AND cpu_time IS NOT NULL")


@dataclass
class Prediction:
    """What a job is expected to use, from the last runs of its most specific signature that has enough of them:
    the median of their average cores (CPU time over run time), capped by the declared weight; the largest of their
    memory peaks; the median of their run times. Without history, the declared weight is the estimate."""

    cores: float
    rss_kib: int | None
    duration: float
    level: str
    runs: int

    @property
    def basis(self) -> str:
        if self.level == "none":
            return "no history: the declared weight"
        return f"{self.runs} run{'s' if self.runs != 1 else ''} of {SOURCES[self.level]}"


def predict(conn: sqlite3.Connection, signed, weight: float) -> Prediction:
    """The prediction for a job of declared `weight` whose signatures are `signed` (a mapping, or a row with sig_
    columns). One indexed query per level, at most four, plus one for the fallback run time."""
    for level, needed in SIGNATURE_LEVELS:
        key = signed[level] if isinstance(signed, dict) else signed[f"sig_{level}"]
        if key is None:
            continue
        # `level` comes from SIGNATURE_LEVELS, never from input.
        runs = conn.execute(f"SELECT started, ended, cpu_time, rss_peak FROM tasks WHERE sig_{level} = ? AND {RAN} "
                            "ORDER BY ended DESC LIMIT ?", (key, HISTORY)).fetchall()
        if len(runs) < needed:
            continue
        durations = [max(row["ended"] - row["started"], 0.05) for row in runs]
        cores = statistics.median(row["cpu_time"] / length for row, length in zip(runs, durations))
        peaks = [row["rss_peak"] for row in runs if row["rss_peak"] is not None]
        return Prediction(min(weight, max(MIN_CORES, cores)), max(peaks) if peaks else None,
                          statistics.median(durations), level, len(runs))
    recent = [row[0] for row in conn.execute(f"SELECT ended - started FROM tasks WHERE {RAN} ORDER BY ended DESC "
                                             "LIMIT ?", (RECENT,))]
    return Prediction(weight, None, statistics.median(recent) if recent else DEFAULT_DURATION, "none", 0)


def describe_hold(row: sqlite3.Row, box) -> str:
    """What a job holds or will hold against the budget, and its predicted memory, for status."""
    if exclusive(row["weight"], box):
        return f"exclusive: holds the whole budget of {number(box.budget)} cores"
    if row["pred_cores"] is None:
        return f"holds {number(row['weight'])} cores, its weight (no prediction)"
    need = number(cores(row, box))
    return f"predicted {need} core{'' if need == '1' else 's'} and {memory(row['pred_rss'])} at peak ({row['pred_from']})"


def describe_prediction(row: sqlite3.Row) -> str:
    if row["pred_cores"] is None:
        return "no prediction"
    return (f"{row['pred_cores']:.1f} cores, {memory(row['pred_rss'])} at peak, {span(row['pred_duration'])}, from "
            f"{row['pred_from']}")


# MARK: - Processes


@dataclass
class Process:
    pid: int
    ppid: int
    pgid: int
    stat: str
    cpu: float
    rss: int
    start: float


def processes(pids=None) -> dict[int, Process] | None:
    """The processes that ps reports, all of them or those in `pids`; None when ps cannot run, which differs from
    no process."""
    if pids is not None:
        pids = sorted({pid for pid in pids if pid and pid > 0})
        if not pids:
            return {}
    command = ["ps", "-o", "pid=,ppid=,pgid=,stat=,%cpu=,rss=,etime="]
    command += ["-A"] if pids is None else ["-p", ",".join(map(str, pids))]
    # The clock is read before ps measures. Read after, it would place every start later by however long ps and
    # this process took to answer, and under load a live job would look like a newer process that reused its pid.
    now, table = time.time(), {}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10,
                                env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 and result.stderr.strip():
        return None
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 7:
            continue
        try:
            process = Process(int(fields[0]), int(fields[1]), int(fields[2]), fields[3], float(fields[4]),
                              int(fields[5]), now - elapsed(fields[6]))
        except ValueError:
            continue
        table[process.pid] = process
    return table


def elapsed(text: str) -> float:
    """Seconds from ps's etime field, [[dd-]hh:]mm:ss."""
    days, _, rest = text.rpartition("-")
    seconds = 0
    for part in rest.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds + (int(days) * 86400 if days else 0)


def exists(pid: int | None) -> bool:
    """Whether one of this user's processes has the pid; another user's process there means the pid was reused."""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return True  # Unknown: counting a live job as dead would fail it, so count it as alive.
    return True


def alive(pid: int | None, since: float | None, table: dict[int, Process] | None) -> bool:
    """Whether `pid` still runs the process that started by `since`: not gone, not a zombie, and not a newer process
    that reused the pid. Without a ps table, the pid's existence decides."""
    if not exists(pid):
        return False
    process = (table or {}).get(pid)
    if process is None:
        return True
    if process.stat.startswith("Z"):
        return False
    return since is None or process.start <= since + 2.0


def usage(root: int, table: dict[int, Process]) -> tuple[float, int]:
    """The CPU percent and resident KiB of `root`, its descendants, and its process group. O(P) for P processes."""
    children: dict[int, list[int]] = {}
    for process in table.values():
        children.setdefault(process.ppid, []).append(process.pid)
    members = {pid for pid, process in table.items() if process.pgid == root}
    stack, seen = [root], set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        if pid in table:
            members.add(pid)
        stack.extend(children.get(pid, ()))
    return sum(table[pid].cpu for pid in members), sum(table[pid].rss for pid in members)


def sweep(conn: sqlite3.Connection) -> list[dict]:
    """Mark failed each job whose supervisor is gone and whose command is gone too, since no one will record its
    status; note a job whose command runs on without its supervisor. Returns the changes."""
    rows = conn.execute("SELECT * FROM tasks WHERE state = 'running' "
                        "OR (state = 'claimed' AND requested IS NOT NULL)").fetchall()
    if not rows:
        return []
    table = processes([row["owner"] for row in rows] + [row["pid"] for row in rows])
    verdicts = {}
    for row in rows:
        if alive(row["owner"], row["owner_since"], table):
            continue
        if row["state"] == "claimed":
            verdicts[row["id"]] = ("failed", f"its supervisor, process {row['owner']}, ended before the command "
                                             "started")
        elif alive(row["pid"], row["started"], table):
            verdicts[row["id"]] = ("orphaned", f"its supervisor, process {row['owner']}, is gone; the command runs on "
                                               f"as process {row['pid']}, and its status will not be recorded")
        else:
            verdicts[row["id"]] = ("failed", f"the job ended without a recorded status: its supervisor, process "
                                             f"{row['owner']}, is gone")
    changes = []
    if not verdicts:
        return changes
    with writing(conn):
        for row in rows:
            if row["id"] not in verdicts:
                continue
            what, note = verdicts[row["id"]]
            current = conn.execute("SELECT state, owner, pid, note FROM tasks WHERE id = ?", (row["id"],)).fetchone()
            if tuple(current)[:3] != (row["state"], row["owner"], row["pid"]) or current["note"] == note:
                continue
            if what == "failed":
                conn.execute("UPDATE tasks SET state = 'failed', ended = ?, note = ? WHERE id = ?",
                             (time.time(), note, row["id"]))
            else:
                conn.execute("UPDATE tasks SET note = ? WHERE id = ?", (note, row["id"]))
            record(conn, what, task=row["id"], scope=row["scope"], agent=row["agent"], detail=note)
            changes.append({"id": row["id"], "state": what, "note": note})
    return changes


# MARK: - Capacity


@dataclass
class Settings:
    """The machine's one settings row: the same capacity and limits for every agent's jobs."""

    capacity: float | None  # a cap on the running jobs' declared weights; None: no cap
    load_factor: float
    load_wait: float
    log_limit: int
    keep_days: float
    pruned: float | None
    idle_min: float = 15.0
    memory_limit: str = "warning"
    backfill_wait: float = 300.0
    small_weight: float = 1.0
    cpu_budget: float | None = None  # the running jobs' predicted cores; None: the CPU count


def settings_of(conn: sqlite3.Connection) -> Settings:
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    return Settings(row["capacity"], row["load_factor"], row["load_wait"], row["log_limit"], row["keep_days"],
                    row["pruned"], row["idle_min"], row["memory_limit"], row["backfill_wait"], row["small_weight"],
                    row["cpu_budget"])


MEMORY_LEVELS = ("normal", "warning", "critical")
MACHINE_CAUSES = ("memory", "idle", "load")


@dataclass
class Signals:
    """What the machine says about its own pressure. Any of them may be unknown (None), which holds nothing back.

    idle is the share of CPU time spent idle over the last sample, in percent: the CPU that a new job can have.
    memory is the kernel's memory pressure, normal, warning or critical. load is the one-minute load average, which
    gates only where it measures CPU demand (`load_gate`): on Linux. macOS counts threads that wait on memory and
    disk in it too, so a machine can show a load of 90 while half its CPU is idle."""

    idle: float | None
    memory: str | None
    load: float | None
    load_gate: bool


def macos_libc():
    import ctypes
    import ctypes.util
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.mach_host_self.restype = ctypes.c_uint
    return ctypes, libc


def macos_cpu_ticks() -> tuple[int, int] | None:
    """(idle ticks, all ticks) of every CPU since boot, from host_statistics(HOST_CPU_LOAD_INFO)."""
    try:
        ctypes, libc = macos_libc()
        info, count = (ctypes.c_uint * 4)(), ctypes.c_uint(4)  # user, system, idle, nice
        if libc.host_statistics(libc.mach_host_self(), 3, info, ctypes.byref(count)) != 0:
            return None
    except (OSError, AttributeError):
        return None
    return info[2], sum(info)


def macos_memory_level() -> str | None:
    """kern.memorystatus_vm_pressure_level: 1 normal, 2 warning, 4 critical."""
    try:
        ctypes, libc = macos_libc()
        value, size = ctypes.c_int(0), ctypes.c_size_t(ctypes.sizeof(ctypes.c_int))
        if libc.sysctlbyname(b"kern.memorystatus_vm_pressure_level", ctypes.byref(value), ctypes.byref(size),
                             None, 0) != 0:
            return None
    except (OSError, AttributeError):
        return None
    return {1: "normal", 2: "warning", 4: "critical"}.get(value.value)


def linux_cpu_ticks(stat: str) -> tuple[int, int] | None:
    """(idle ticks, all ticks) from /proc/stat's first line; waiting on I/O counts as idle CPU."""
    fields = stat.split("\n", 1)[0].split()
    if len(fields) < 5 or fields[0] != "cpu":
        return None
    try:
        ticks = [int(field) for field in fields[1:9]]
    except ValueError:
        return None
    return ticks[3] + (ticks[4] if len(ticks) > 4 else 0), sum(ticks)


def linux_memory_level(meminfo: str) -> str | None:
    """From /proc/meminfo: warning below 10% of memory available, critical below 5%."""
    values = {}
    for line in meminfo.splitlines():
        name, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[name] = int(parts[0])
    total, available = values.get("MemTotal"), values.get("MemAvailable")
    if not total or available is None:
        return None
    share = available / total
    return "critical" if share < 0.05 else "warning" if share < 0.10 else "normal"


def read_text(path: str) -> str | None:
    try:
        with open(path) as handle:
            return handle.read()
    except OSError:
        return None


class Gauge:
    """Reads the machine's signals. Idle CPU is measured between two readings of the CPU ticks: a supervisor that
    polls once a second measures over that second; a reading sooner than `window` after the last waits out the
    rest of the window. `prime` takes the first reading early, so that the first measure need not wait. The kernel
    updates the ticks in steps (about a second on macOS), so two readings can fall within one step: then the gauge
    reads again, up to `retries` more windows, before it reports idle CPU as unknown."""

    def __init__(self, platform: str = sys.platform, window: float = 0.5, retries: int = 3):
        self.platform, self.window, self.retries = platform, window, retries
        self.last: tuple[float, tuple[int, int]] | None = None

    def ticks(self) -> tuple[int, int] | None:
        if self.platform == "darwin":
            return macos_cpu_ticks()
        if self.platform.startswith("linux"):
            stat = read_text("/proc/stat")
            return linux_cpu_ticks(stat) if stat else None
        return None

    def memory(self) -> str | None:
        if self.platform == "darwin":
            return macos_memory_level()
        if self.platform.startswith("linux"):
            meminfo = read_text("/proc/meminfo")
            return linux_memory_level(meminfo) if meminfo else None
        return None

    def prime(self) -> None:
        ticks = self.ticks()
        if ticks is not None:
            self.last = (time.monotonic(), ticks)

    def idle(self) -> float | None:
        now, ticks = time.monotonic(), self.ticks()
        if ticks is None:
            return None
        if self.last is None or now - self.last[0] < self.window:
            time.sleep(self.window if self.last is None else self.window - (now - self.last[0]))
            before, (now, ticks) = ticks if self.last is None else self.last[1], (time.monotonic(), self.ticks())
            if ticks is None:
                return None
        else:
            before = self.last[1]
        for _ in range(self.retries):
            if ticks[1] != before[1]:
                break
            time.sleep(self.window)
            now, ticks = time.monotonic(), self.ticks()
            if ticks is None:
                return None
        self.last = (now, ticks)
        idle, total = ticks[0] - before[0], ticks[1] - before[1]
        return 100.0 * idle / total if total > 0 else None

    def read(self, idle: bool = True) -> Signals:
        """The signals now; without `idle`, idle CPU is not measured, as when no threshold reads it."""
        return Signals(self.idle() if idle else None, self.memory(), load_average(), self.platform.startswith("linux"))


@dataclass
class Machine:
    cpus: int
    budget: float  # the predicted cores that running jobs may take together
    capacity: float | None  # the declared cores that running jobs may take together; None: no cap
    settings: Settings
    signals: Signals | None

    @property
    def load_limit(self) -> float:
        return self.cpus * self.settings.load_factor


def load_average() -> float | None:
    try:
        return os.getloadavg()[0]
    except OSError:
        return None


def machine(settings: Settings, signals: Signals | None = None) -> Machine:
    cpus = os.cpu_count() or 1
    return Machine(cpus, settings.cpu_budget or float(cpus), settings.capacity, settings, signals)


def check_weight(weight: float) -> float:
    cpus = os.cpu_count() or 1
    if weight > cpus:
        raise WorkError(f"--weight {weight:g} is more than the {cpus} CPUs of this machine")
    return weight


def exclusive(weight: float, box: Machine) -> bool:
    """Whether a job is as heavy as the CPU count: it holds the whole CPU budget, so the machine drains before it."""
    return weight >= box.cpus


def cores(row, box: Machine) -> float:
    """The cores a job holds against the CPU budget: its predicted cores, capped by its declared weight, or its
    declared weight without a prediction. An exclusive job holds the whole budget, so it runs alone and nothing starts
    beside it; it is a timing measurement, so no prediction stands in for its weight."""
    weight = row["weight"]
    if exclusive(weight, box):
        return max(box.budget, weight)
    return weight if row["pred_cores"] is None else min(weight, row["pred_cores"])


def number(value: float) -> str:
    """Cores for a reason or a view: one decimal at most, 7.4, 8 or 0.5."""
    return f"{round(value, 1):g}"


def over(need: float, used: float, limit: float) -> bool:
    """Whether a job that needs `need` does not fit beside `used` under `limit`. A job larger than the limit fits
    when nothing is taken, so that it runs alone rather than never."""
    return used > 0 and used + need > limit + 1e-9


def taken(need: float, used: float, box: Machine) -> tuple[str, str]:
    return "cores", f"predicted {number(used)} of {number(box.budget)} cores are taken and this job needs {number(need)}"


def pressure(box: Machine) -> tuple[str, str] | None:
    """Why the machine itself holds jobs back, as (cause, reason) naming the signal, or None. Memory pressure at or
    above the settings' memory_limit holds them; so does idle CPU below idle_min; so does, on Linux only, a load
    average at or above the CPU count times load_factor. An unknown signal holds nothing."""
    signals, settings = box.signals, box.settings
    if signals is None:
        return None
    if settings.memory_limit != "off" and signals.memory in MEMORY_LEVELS \
            and MEMORY_LEVELS.index(signals.memory) >= MEMORY_LEVELS.index(settings.memory_limit):
        return "memory", f"memory pressure is {signals.memory}; jobs start below {settings.memory_limit}"
    if signals.idle is not None and signals.idle < settings.idle_min:
        return "idle", f"the CPU is {signals.idle:.0f}% idle; jobs start at {settings.idle_min:g}% idle or more"
    if signals.load_gate and signals.load is not None and signals.load >= box.load_limit:
        return "load", f"the load average {signals.load:.2f} is at or above {box.load_limit:.2f}"
    return None


def admission(row, running: list, box: Machine) -> tuple[str, str] | None:
    """Why a job cannot start now beside the `running` jobs, as (cause, reason), or None when it can: its predicted
    cores must fit the CPU budget beside theirs, its declared weight the capacity, when one is set, beside theirs,
    and the machine must not be under pressure."""
    need, used = cores(row, box), sum(cores(item, box) for item in running)
    if over(need, used, box.budget):
        return taken(need, used, box)
    declared = sum(item["weight"] for item in running)
    if box.capacity is not None and over(row["weight"], declared, box.capacity):
        return "capacity", (f"declared weights of {number(declared)} of the capacity of {number(box.capacity)} "
                            f"cores are taken and this job declares {number(row['weight'])}")
    return pressure(box)


def describe_machine(box: Machine) -> str:
    """The machine's signals and the thresholds that gate jobs, for status."""
    signals, settings = box.signals, box.settings
    idle = f"{signals.idle:.0f}%" if signals and signals.idle is not None else "unknown"
    memory = signals.memory if signals and signals.memory else "unknown"
    load = f"{signals.load:.2f}" if signals and signals.load is not None else "unknown"
    memory_rule = "not a gate" if settings.memory_limit == "off" else f"jobs start below {settings.memory_limit}"
    load_rule = f"jobs start below {box.load_limit:.2f}" if signals and signals.load_gate else \
        "not a gate here: it counts threads waiting on memory and disk"
    return (f"machine: {box.cpus} CPUs; CPU {idle} idle (jobs start at {settings.idle_min:g}% or more); "
            f"memory pressure {memory} ({memory_rule}); load {load} ({load_rule})")


def backfill(row: sqlite3.Row, ahead: list[sqlite3.Row], running: list[sqlite3.Row], box: Machine,
             now: float) -> tuple[str, str] | None:
    """Why a job behind the head of the line may not start before it, or None when it may, by the EASY rule in
    predicted cores: only when the head cannot start for want of cores, never when there is room for it. Run times
    are predicted too roughly to reserve the head a start time, so its reservation is kept in cores: whatever runs now
    may end before the head can start, but a job that started while the head waited may still run then. So a job may
    start past the head when it fits in the free cores now and
      - it fits in the cores the head leaves free: the head's cores, the cores of the jobs that started while the
        head waited, and its own, fit the budget together, so it can never delay the head; or
      - it is small (at most small_weight predicted cores) and no validity job is ahead of it: it may delay the head,
        but only until the head has waited backfill_wait.
    Once the head has waited backfill_wait, nothing starts before it, so no job starves. O(R + A) for R running and
    A waiting jobs ahead."""
    head, settings, need = ahead[0], box.settings, cores(row, box)
    head_need = cores(head, box)
    waited = now - head["requested"]
    if waited >= settings.backfill_wait:
        return "ahead", (f"job {head['id']} has waited {span(waited)}, past the backfill limit of "
                         f"{span(settings.backfill_wait)}, so no job starts before it")
    used = sum(cores(item, box) for item in running)
    if not over(head_need, used, box.budget):
        return "ahead", f"job {head['id']} is ahead of it, and there is room for it"
    if used + need > box.budget + 1e-9:
        return taken(need, used, box)
    since = sum(cores(item, box) for item in running if item["started"] is not None
                and item["started"] >= head["requested"])
    spare = box.budget - head_need - since
    if need <= spare + 1e-9:
        return None
    validity = next((item for item in ahead if item["kind"].lower() in order_tasks.VALIDITY_KINDS), None)
    if need <= settings.small_weight + 1e-9 and validity is None:
        return None
    reason = (f"job {head['id']} is ahead of it and needs {number(head_need)} of the {number(box.budget)} cores, "
              f"which leaves {number(max(0.0, spare))} for jobs behind it; this job needs {number(need)}")
    if validity is not None and need <= settings.small_weight + 1e-9:
        reason += f", and job {validity['id']}, validity work, keeps its place"
    return "ahead", reason


def waiting_order(row: sqlite3.Row, batch: str | None = None) -> tuple:
    """A waiting job's place in line, in order_tasks' work order: validity first, then the jobs of the open exclusive
    batch `batch`, then the order in which the jobs asked for capacity."""
    return (0 if row["kind"].lower() in order_tasks.VALIDITY_KINDS else 1,
            0 if batch is not None and row["batch"] == batch else 1, row["requested"], row["seq"])


def open_batch(running: list[sqlite3.Row], waiting: list[sqlite3.Row]) -> str | None:
    """The open exclusive batch: the batch of a running job, else of a waiting job, or None. `waiting` holds only the
    jobs whose supervisor lives, so a batch none of whose jobs runs or waits alive is closed."""
    return next((item["batch"] for item in [*running, *waiting] if item["batch"]), None)


def enumerate_ids(ids: list[str]) -> str:
    return ids[0] if len(ids) == 1 else f"{', '.join(ids[:-1])} and {ids[-1]}"


def describe_batch(batch: str, running: list[sqlite3.Row], line: list[sqlite3.Row]) -> str:
    """The open batch's jobs, running and then next in line order: "job-12 running, job-15 and job-18 next"."""
    parts = []
    for ids, what in (([item["id"] for item in running if item["batch"] == batch], "running"),
                      ([item["id"] for item in line if item["batch"] == batch], "next")):
        if ids:
            parts.append(f"{enumerate_ids(ids)} {what}")
    return ", ".join(parts)


def prune(ctx: Context, now: float | None = None) -> None:
    """Deletes the events, and the logs of ended tasks, older than the settings' keep_days, at most once an hour. A log
    is found from its task's id, never from a stored path, so an edited database cannot aim the deletion elsewhere."""
    conn = ctx.conn
    now = time.time() if now is None else now
    settings = settings_of(conn)
    if settings.pruned is not None and now - settings.pruned < 3600:
        return
    cutoff = now - settings.keep_days * 86400
    with writing(conn):
        conn.execute("UPDATE settings SET pruned = ? WHERE id = 1", (now,))
        conn.execute("DELETE FROM events WHERE time < ?", (cutoff,))
        ids = [row[0] for row in conn.execute("SELECT id FROM tasks WHERE state IN ('done', 'failed', 'cancelled') "
                                              "AND ended < ? AND log IS NOT NULL", (cutoff,))]
        conn.execute("UPDATE tasks SET log = NULL WHERE state IN ('done', 'failed', 'cancelled') AND ended < ?",
                     (cutoff,))
    for task_id in ids:
        path = os.path.join(ctx.logs, f"{task_id}.log")
        with suppress(FileNotFoundError):
            if NAME.fullmatch(task_id) and stat.S_ISREG(os.lstat(path).st_mode):
                os.unlink(path)


# MARK: - Running


class Supervisor:
    """Runs one job detached from the agent that asked for it: waits for capacity, starts the command in its own
    process group with its output in the log, samples its CPU and memory, and records its true exit status. `run`
    names it the job's owner in the transaction that reserves the job, and it goes on only once that transaction is
    over and it owns the job."""

    def __init__(self, ctx: Context, task_id: str, gauge: Gauge | None = None):
        self.ctx, self.task_id, self.gauge = ctx, task_id, gauge or Gauge()
        self.me = os.getpid()
        self.child: subprocess.Popen | None = None
        self.stop: int | None = None
        self.over_limit = False
        # Held while `child` is cleared, and while the sampler signals it, so the sampler never signals a reaped pid.
        self.lock = threading.Lock()

    def run(self) -> int:
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, self.on_signal)
        self.gauge.prime()  # The handshake and the takeover below overlap the first sample of idle CPU.
        # `run` closes this pipe once its transaction is over, committed or rolled back; a caller that dies closes it
        # too. No stdin at all counts as closed.
        with suppress(OSError):
            while os.read(0, 4096):
                continue
        conn = self.ctx.conn
        with writing(conn):
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (self.task_id,)).fetchone()
            if row is None or row["state"] != "claimed" or row["requested"] is None or row["owner"] != self.me:
                print(f"work: task {self.task_id} is not waiting for this supervisor", file=sys.stderr, flush=True)
                return 1
            # The wait for capacity, and the job's place among the waiting jobs, count from here, not from the
            # request, so that the supervisor's own start is not reported as a wait for capacity. The prediction is
            # made once, from the history known now.
            guess = predict(conn, row, row["weight"])
            conn.execute("UPDATE tasks SET requested = ?, pred_cores = ?, pred_rss = ?, pred_duration = ?, "
                         "pred_from = ? WHERE id = ?", (time.time(), guess.cores, guess.rss_kib, guess.duration,
                                                        guess.basis, self.task_id))
        row = self.wait_for_capacity(conn)
        return 0 if row is None else self.execute(conn, row)

    def on_signal(self, signum: int, frame: object) -> None:
        """Records the signal, which the wait for capacity checks between two polls, and forwards it to the command's
        process group while the command runs. It raises nothing, so it never breaks off a transaction."""
        self.stop = signum
        child = self.child
        if child is not None:
            forward(child.pid, signum)

    def wait_for_capacity(self, conn: sqlite3.Connection) -> sqlite3.Row | None:
        """Polls once a second until the job may start, then marks it running; None when the job ends first:
        cancelled, swept, stopped by a signal, or held back by the machine's pressure past the settings' load_wait."""
        last_sweep, held_since = time.monotonic(), None
        while True:
            if self.stop is not None:
                self.finish(conn, None, f"stopped by signal {self.stop} before the command started")
                return None
            with writing(conn):
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (self.task_id,)).fetchone()
                if row is None or row["state"] != "claimed" or row["owner"] != self.me:
                    return None
                settings = settings_of(conn)
                box = machine(settings, self.gauge.read(idle=settings.idle_min > 0))
                blocked = self.blocker(conn, row, box)
                if blocked is None:
                    if exclusive(row["weight"], box):
                        self.form_batch(conn, row, box)
                    conn.execute("UPDATE tasks SET state = 'running', started = ?, note = '' WHERE id = ?",
                                 (time.time(), self.task_id))
                    return get_task(conn, self.task_id)
                cause, reason = blocked
                # Other jobs end; outside pressure need not. A job that the machine alone holds back gives up at last.
                held_since = (held_since or time.monotonic()) if cause in MACHINE_CAUSES else None
                if held_since is not None and time.monotonic() - held_since >= settings.load_wait:
                    note = (f"{reason} for {span(time.monotonic() - held_since)}, the longest a job waits on the "
                            f"machine's pressure (work settings --load-wait)")
                    conn.execute("UPDATE tasks SET state = 'failed', ended = ?, note = ? WHERE id = ?",
                                 (time.time(), note, self.task_id))
                    record(conn, "failed", task=self.task_id, scope=row["scope"], agent=row["agent"], detail=note)
                    return None
                if reason != row["note"]:
                    conn.execute("UPDATE tasks SET note = ? WHERE id = ?", (reason, self.task_id))
            time.sleep(CAPACITY_POLL)
            if time.monotonic() - last_sweep >= SWEEP_INTERVAL:
                sweep(conn)
                last_sweep = time.monotonic()

    def blocker(self, conn: sqlite3.Connection, row: sqlite3.Row, box: Machine) -> tuple[str, str] | None:
        """Why the job cannot start now, as (cause, reason), or None. Waiting jobs start in work order, with the jobs
        of the open exclusive batch right after validity work; a waiting job whose supervisor is gone keeps no place.
        A job behind the head of the line may start before it only as `backfill` allows, and never before a job of
        the open batch, so that the machine, once drained for the batch, runs its jobs back to back."""
        running, line = self.lines(conn, row)
        batch = open_batch(running, line)
        line.sort(key=lambda item: waiting_order(item, batch))
        if line[0]["id"] != row["id"]:
            ahead = line[:[item["id"] for item in line].index(row["id"])]
            if row["batch"] != batch and any(item["batch"] == batch for item in ahead):
                return "batch", f"the exclusive batch runs first: {describe_batch(batch, running, line)}"
            held = backfill(row, ahead, running, box, time.time())
            if held is not None:
                return held
        return admission(row, running, box)

    def lines(self, conn: sqlite3.Connection, row: sqlite3.Row) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
        """The running jobs in the order they started, and the waiting jobs whose supervisor lives, with this one, in
        the order they asked."""
        running = conn.execute("SELECT id, weight, pred_cores, started, batch FROM tasks WHERE state = 'running' "
                               "ORDER BY started, seq").fetchall()
        waiting = conn.execute("SELECT id, kind, requested, seq, owner, weight, pred_cores, pred_duration, batch "
                               "FROM tasks WHERE state = 'claimed' AND requested IS NOT NULL "
                               "ORDER BY requested, seq").fetchall()
        return running, [item for item in waiting if item["id"] == row["id"] or exists(item["owner"])]

    def form_batch(self, conn: sqlite3.Connection, row: sqlite3.Row, box: Machine) -> None:
        """As an exclusive job starts with no batch open, opens its batch, in the caller's transaction: it and the
        exclusive jobs waiting now, whose supervisor lives, form the batch. A job that starts while a batch is open,
        validity work going ahead of it, runs outside it."""
        running, line = self.lines(conn, row)
        if open_batch(running, [item for item in line if item["id"] != row["id"]]) is not None:
            return
        members = [row["id"]] + [item["id"] for item in line
                                 if item["id"] != row["id"] and exclusive(item["weight"], box)]
        conn.execute(f"UPDATE tasks SET batch = ? WHERE id IN ({','.join('?' * len(members))})",
                     (row["id"], *members))

    def execute(self, conn: sqlite3.Connection, row: sqlite3.Row) -> int:
        argv, cwd = json.loads(row["command"]), row["cwd"]
        if not os.path.isdir(cwd):
            print(f"work: cannot run {brief(argv)}: its directory {printable(cwd)} is gone", flush=True)
            self.finish(conn, None, f"its directory {cwd} is gone")
            return 1
        try:
            # Its stdout is the supervisor's, the log that `run` opened; stdin is closed, as no one can answer it.
            child = subprocess.Popen(argv, cwd=cwd, env={**os.environ, "PWD": cwd}, stdin=subprocess.DEVNULL,
                                     stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
        except (OSError, ValueError) as error:
            print(f"work: cannot run {brief(argv)}: {error}", flush=True)
            if getattr(error, "filename", None) == cwd:
                self.finish(conn, None, f"cannot enter its directory {cwd}: {error.strerror}")
                return 1
            cannot = getattr(error, "errno", None) in (errno.EACCES, errno.EPERM, errno.ENOEXEC, errno.EISDIR)
            self.finish(conn, 126 if cannot else 127, f"could not start: {error}")
            return 0
        self.child = child
        if self.stop is not None:
            forward(child.pid, self.stop)
        self.update(conn, "UPDATE tasks SET pid = ? WHERE id = ?", (child.pid, self.task_id), "started",
                    f"process {child.pid}; waited {span(waited_of(row, time.time()))} for capacity")
        log_limit = settings_of(conn).log_limit
        stop = threading.Event()
        sampler = threading.Thread(target=self.sample, args=(child.pid, row["log"], log_limit, stop), daemon=True)
        sampler.start()
        raw, resources = self.reap(child.pid)
        status = os.waitstatus_to_exitcode(raw)
        status = 128 - status if status < 0 else status
        child.returncode = status
        stop.set()
        sampler.join(timeout=15)
        note = f"stopped: its log passed the limit of {log_limit} bytes (work settings --log-limit)" \
            if self.over_limit else ""
        self.finish(conn, status, note, resources.ru_utime + resources.ru_stime)
        return 0

    def reap(self, pid: int):
        """Waits for the command to end, stops forwarding signals to it, and reaps it. Where the platform can wait
        without reaping (waitid with WNOWAIT), forwarding stops while the ended command still holds its pid, so no
        signal can reach a process that reused the pid; elsewhere it stops right after the reap."""
        if hasattr(os, "waitid"):
            os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT)
            with self.lock:
                self.child = None
            _, raw, resources = os.wait4(pid, 0)
        else:
            _, raw, resources = os.wait4(pid, 0)
            with self.lock:
                self.child = None
        return raw, resources

    def sample(self, pid: int, log: str, log_limit: int, stop: threading.Event) -> None:
        """Every 0.5 s, checks the size of the job's log, and stops the job, TERM then KILL 5 s later, once the log
        passes `log_limit`; from 0.5 s on, every SAMPLE_INTERVAL seconds, records the job's CPU and memory."""
        conn, peak, ticks, stopping, killed = None, 0, 0, None, False
        while not stop.wait(0.5):
            ticks += 1
            if stopping is None and size_of(log) > log_limit:
                self.over_limit, stopping = True, time.monotonic()
                self.signal_child(pid, signal.SIGTERM)
            elif stopping is not None and not killed and time.monotonic() - stopping >= 5:
                killed = True
                self.signal_child(pid, signal.SIGKILL)
            if ticks % round(SAMPLE_INTERVAL / 0.5) != 1:
                continue
            table = processes()
            if not table:
                continue
            cpu, rss = usage(pid, table)
            peak = max(peak, rss)
            try:
                conn = conn or connect(self.ctx.home)
                with writing(conn):
                    conn.execute("UPDATE tasks SET cpu = ?, rss = ?, rss_peak = ?, sampled = ? "
                                 "WHERE id = ? AND state = 'running'", (cpu, rss, peak, time.time(), self.task_id))
            except (sqlite3.Error, WorkError) as error:
                print(f"work: could not record a sample of job {self.task_id}: {error}", file=sys.stderr, flush=True)
        if conn is not None:
            conn.close()

    def signal_child(self, pid: int, signum: int) -> None:
        """Signals the command's process group from the sampler, only while the command is not reaped."""
        with self.lock:
            if self.child is not None:
                forward(pid, signum)

    def update(self, conn: sqlite3.Connection, sql: str, parameters: tuple, what: str, detail: str) -> None:
        """One write, with its event when it changed the task, retried while the database is busy: once the command
        runs, a busy database must not stop the supervisor from recording the status."""
        problem = None
        for attempt in range(5):
            try:
                with writing(conn):
                    row = get_task(conn, self.task_id)
                    if conn.execute(sql, parameters).rowcount:
                        record(conn, what, task=self.task_id, scope=row["scope"], agent=row["agent"], detail=detail)
                return
            except sqlite3.OperationalError as error:
                problem = error
                time.sleep(0.5 * (attempt + 1))
        print(f"work: could not record that job {self.task_id} {what}: {problem}", file=sys.stderr, flush=True)

    def finish(self, conn: sqlite3.Connection, status: int | None, note: str, cpu_time: float | None = None) -> None:
        state = "done" if status == 0 else "failed"
        detail = note if status is None else f"status {status}" + (f"; {note}" if note else "")
        self.update(conn, "UPDATE tasks SET state = ?, status = ?, ended = ?, cpu_time = ?, note = ? "
                          "WHERE id = ? AND state NOT IN ('done', 'failed', 'cancelled')",
                    (state, status, time.time(), cpu_time, note, self.task_id),
                    "finished" if status is not None else "failed", detail)


def size_of(path: str) -> int:
    try:
        return os.stat(path).st_size
    except OSError:
        return 0  # No log to measure is no log past the limit.


def forward(pid: int, signum: int) -> None:
    """Sends a signal to the process group that `pid` leads."""
    with suppress(ProcessLookupError, PermissionError):  # The group has ended; macOS answers EPERM for a zombie.
        os.killpg(pid, signum)


def supervise(argv: list[str], env: dict[str, str]) -> int:
    """The hidden `_supervise TASK` command that `work run` starts detached, with a pipe for its stdin."""
    if len(argv) != 1 or not NAME.fullmatch(argv[0]):
        print("work: _supervise is started by `work run`", file=sys.stderr)
        return 2
    ctx = Context(env)
    try:
        return Supervisor(ctx, argv[0]).run()
    finally:
        ctx.close()


def check_runnable(row: sqlite3.Row, agent: str) -> None:
    """Refuses to run a task's command unless `agent` claimed the task, accepted its command, and it has not run."""
    task_id = row["id"]
    if row["command"] is None:
        raise refusal(f"task {task_id} has no command; close it with `work done {task_id}` when it is finished")
    if row["state"] == "queued":
        raise refusal(f"claim task {task_id} first: `work claim {task_id}`")
    if row["state"] == "running" or (row["state"] == "claimed" and row["requested"] is not None):
        raise refusal(f"task {task_id} is already {describe_state(row)}; wait for it with `work wait {task_id}`")
    if row["state"] != "claimed":
        raise refusal(f"task {task_id} is {describe_state(row)}")
    if row["agent"] != agent:
        raise refusal(f"task {task_id} is claimed by {row['agent']}; only that agent runs it")
    if needs_acceptance(row):
        raise refusal(f"task {task_id} runs a command that {row['author']} queued, and you have not accepted it: "
                      f"read it with `work show {task_id}`, then accept it with the `work accept {task_id} --digest "
                      "...` line that show prints")


def start_supervisor(ctx: Context, task_id: str, log_path: str) -> subprocess.Popen:
    """Starts the supervisor of a job, detached, with its output in a new log and a pipe for its stdin. It waits on
    that pipe, so the caller must close it once the transaction that names it the owner is over."""
    try:
        log = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        raise refusal(f"cannot open the log {printable(log_path)}: {error.strerror}") from None
    try:
        return subprocess.Popen([sys.executable, SCRIPT, "_supervise", task_id], cwd="/",
                                env={**ctx.env, "AGENT_WORK_HOME": ctx.home}, stdin=subprocess.PIPE,
                                stdout=log, stderr=log, start_new_session=True, close_fds=True)
    except OSError as error:
        raise refusal(f"cannot start the supervisor of job {task_id}: {error}") from None
    finally:
        os.close(log)


def reserve(conn: sqlite3.Connection, row: sqlite3.Row, agent: str, owner: int, log: str) -> None:
    """Records that `owner`, the supervisor, runs the job, in the caller's transaction."""
    now = time.time()
    conn.execute("UPDATE tasks SET requested = ?, owner = ?, owner_since = ?, log = ?, note = '' WHERE id = ?",
                 (now, owner, now, log, row["id"]))
    record(conn, "requested", task=row["id"], scope=row["scope"], agent=agent, detail=f"weight {row['weight']:g}")


def end_line(row: sqlite3.Row, now: float) -> str:
    task_id = row["id"]
    if row["status"] is not None:
        waited, ran = waited_of(row, now) or 0.0, ran_of(row, now) or 0.0
        return (f"job {task_id} finished with status {row['status']} after {span(waited + ran)} "
                f"(waited {span(waited)} for capacity, ran {span(ran)})")
    if row["state"] == "done":
        return f"task {task_id} is done" + (f": {printable(row['note'])}" if row["note"] else "")
    word = "was cancelled" if row["state"] == "cancelled" else "failed"
    return f"task {task_id} {word}" + (f": {printable(row['note'])}" if row["note"] else "")


def pending_line(row: sqlite3.Row, now: float) -> str:
    task_id = row["id"]
    if row["state"] == "running":
        return (f"job {task_id} still running after {span(ran_of(row, now))} "
                f"(waited {span(waited_of(row, now) or 0.0)} for capacity)")
    if row["state"] == "claimed" and row["requested"] is not None:
        if not row["note"]:
            return f"job {task_id} is starting"
        return (f"job {task_id} still waiting for capacity after {span(waited_of(row, now))}: "
                f"{printable(row['note'])}")
    return f"task {task_id} is still {describe_state(row)}"


def report(rows: list[sqlite3.Row], ended: list[sqlite3.Row], lines: int, as_json: bool, timed_out: bool) -> int:
    """Prints how the waited tasks stand, and returns the exit status: 124 at the timeout; else, with every task
    ended, 0 when all are done or the status of the first in `rows` that is not; with --any, the status of the first
    to end (`ended` is in the order of their ends). JSON carries `timed_out`, which tells a timeout from a command
    that exits with 124 itself."""
    now = time.time()
    if timed_out:
        status = 124
    elif len(ended) == len(rows):
        status = next((exit_status(row) for row in rows if row["state"] != "done"), 0)
    else:
        status = exit_status(ended[0])
    if as_json:
        emit({"status": status, "timed_out": timed_out, "tasks": [
            {**task_json(row, now), "tail": tail(row["log"], lines)} for row in rows]})
        return status
    for row in rows:
        # A job's output is escaped too: it may hold what the terminal would take for a control sequence.
        for line in tail(row["log"], lines) if row["log"] and (row["state"] in FINAL or timed_out) else []:
            print(printable(line))
        say(end_line(row, now) if row["state"] in FINAL else pending_line(row, now))
    if timed_out:
        say(f"call `work wait {' '.join(row['id'] for row in rows if row['state'] not in FINAL)}` to keep waiting")
    return status


def wait_for(ctx: Context, ids: list[str], any_: bool, timeout: float, lines: int, as_json: bool,
             supervisor: subprocess.Popen | None = None, interval: float = 0.5) -> int:
    """Returns as soon as every task (or, with `any_`, one) is done, failed or cancelled, polling the database with a
    pause that grows from 0.05 s to `interval`; sweeps dead jobs every 2 s so that it never waits on one. `run` passes
    the supervisor it started: its end is reaped and swept at once, and the job's start or wait is announced."""
    conn = ctx.conn
    begun = time.monotonic()
    deadline, next_sweep, pause = begun + timeout, begun, 0.05
    announced = set() if supervisor is not None and not as_json else None
    while True:
        now = time.monotonic()
        if supervisor is not None and supervisor.poll() is not None:
            supervisor, next_sweep = None, now  # Reaped; if it ended before recording the job, the sweep says so now.
        if now >= next_sweep:
            sweep(conn)
            next_sweep = now + 2.0
        rows = [get_task(conn, task_id) for task_id in ids]
        if announced is not None:
            announce(rows[0], announced)
        ended = sorted((row for row in rows if row["state"] in FINAL), key=lambda row: row["ended"] or 0.0)
        if ended and (any_ or len(ended) == len(rows)):
            return report(rows, ended, lines, as_json, timed_out=False)
        if now >= deadline:
            return report(rows, ended, lines, as_json, timed_out=True)
        time.sleep(max(0.01, min(pause, deadline - now)))
        pause = min(pause * 1.5, interval)


def announce(row: sqlite3.Row, announced: set[str]) -> None:
    """Says once that a job waits for capacity, and once that it started."""
    if row["pid"] and "started" not in announced:
        say(f"started job {row['id']} ({brief(json.loads(row['command']))}) as process {row['pid']}; "
            f"output in {printable(row['log'])}")
        announced.update(("started", "waiting"))
    elif row["state"] == "claimed" and row["requested"] is not None and row["note"] and "waiting" not in announced:
        say(f"job {row['id']} waits for capacity: {printable(row['note'])}")
        announced.add("waiting")


# MARK: - Conditions


LOG_READ = 16 * 1024 * 1024  # The most of a log read at one check; the rest is read at the next.
LOG_LINE = 1024 * 1024  # The most of one unfinished line kept between checks.


def check_pids(pids: list[str]) -> list[int]:
    numbers = []
    for text in pids:
        if not text.isdigit() or int(text) <= 0:
            raise WorkError(f"--pid {text!r} is not a process id")
        numbers.append(int(text))
    return unique(numbers)


def running_pids(pids: list[int]) -> list[int]:
    """The processes in `pids` that have not exited. A zombie has exited: it answers to its pid only until its parent
    reaps it."""
    present = [pid for pid in pids if exists(pid)]
    table = processes(present) if present else {}
    return [pid for pid in present if not (table and pid in table and table[pid].stat.startswith("Z"))]


def not_ready(paths: list[str]) -> list[str]:
    """The paths that do not exist yet or are empty."""
    pending = []
    for path in paths:
        try:
            if os.stat(path).st_size > 0:
                continue
        except OSError:
            pass
        pending.append(path)
    return pending


def status_in(path: str) -> int | None:
    """The number a status file holds, spaces and newlines aside, as a shell's `echo $? > FILE` writes it; None for
    any other text."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(4096)
    except OSError:
        return None
    digits = data.replace(b" ", b"").replace(b"\n", b"")
    return int(digits) if digits and digits.isdigit() and len(digits) < 12 else None


class LogWatch:
    """Watches a log for a line that matches an extended regular expression, with grep -E itself, so the pattern
    means what it means to grep. Each check reads only what the log gained since the last one, plus the unfinished
    line at its end; a log that shrank was replaced, and is read again from its start."""

    def __init__(self, path: str, pattern: str):
        self.path, self.pattern = path, pattern
        self.offset, self.carry = 0, b""
        if self.grep(b"") == 2:
            raise WorkError(f"{pattern!r} is not an extended regular expression that grep -E accepts")

    def grep(self, data: bytes) -> int:
        try:
            return subprocess.run(["grep", "-E", "-q", "-e", self.pattern], input=data, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=60).returncode
        except (OSError, subprocess.SubprocessError) as error:
            raise refusal(f"cannot run grep: {error}") from None

    def matched(self) -> bool:
        try:
            with open(self.path, "rb") as handle:
                size = os.fstat(handle.fileno()).st_size
                if size < self.offset:
                    self.offset, self.carry = 0, b""
                while self.offset < size:
                    handle.seek(self.offset)
                    new = handle.read(min(LOG_READ, size - self.offset))
                    if not new:
                        break
                    self.offset += len(new)
                    data = self.carry + new
                    if self.grep(data) == 0:
                        return True
                    self.carry = data[data.rfind(b"\n") + 1:][-LOG_LINE:]
        except OSError:
            return False  # No log yet: nothing matches.
        return False


def wait_condition(args: argparse.Namespace) -> int:
    """`work wait --pid`, `--file`, `--gone` or `--log`: returns as soon as the condition holds, checking it with a
    pause that grows from 0.05 s to --interval, or with 124 at --timeout. It needs no state, so it works anywhere."""
    if args.pid:
        kind, targets, pids = "pid", unique(args.pid), check_pids(args.pid)
    elif args.file:
        kind, targets = "file", unique(args.file)
    elif args.gone:
        kind, targets = "gone", unique(args.gone)
    else:
        kind, targets = "log", args.log[:1]
        watch = LogWatch(*args.log)
    if kind == "pid":
        pending_of = lambda: [str(pid) for pid in running_pids(pids)]  # noqa: E731
    elif kind == "file":
        pending_of = lambda: not_ready(targets)  # noqa: E731
    elif kind == "gone":
        pending_of = lambda: [path for path in targets if os.path.exists(path)]  # noqa: E731
    else:
        pending_of = lambda: [] if watch.matched() else targets  # noqa: E731
    if not args.json:
        say(f"waiting for {WAITING[kind]} " + " ".join(printable(target) for target in targets))
    begun = time.monotonic()
    deadline, pause = begun + args.timeout, 0.05
    while True:
        pending = pending_of()
        now = time.monotonic()
        if not pending or now >= deadline:
            break
        time.sleep(max(0.01, min(pause, deadline - now)))
        pause = min(pause * 1.5, args.interval)
    seconds, timed_out = time.monotonic() - begun, bool(pending)
    status = 124 if timed_out else 0
    number = status_in(targets[0]) if kind == "file" and not timed_out and len(targets) == 1 else None
    if number is not None:
        status = number
    log = targets[0] if kind == "log" else None
    if args.json:
        emit({"status": status, "timed_out": timed_out, "condition": kind, "targets": targets, "pending": pending,
              "seconds": round(seconds, 3), "tail": tail(log, args.tail)})
        return status
    for line in tail(log, args.tail):
        print(printable(line))
    if timed_out:
        again = f"work wait --{kind} " + " ".join(shlex.quote(target) for target in args.log or targets)
        say(f"{STILL[kind]} after {span(seconds)}: {' '.join(printable(item) for item in pending)}; "
            f"call `{printable(again)}` to keep waiting")
    elif number is not None:
        say(f"finished with status {number} after {span(seconds)}, from {printable(targets[0])}")
    else:
        say(f"{DONE[kind]} after {span(seconds)}")
    return status


WAITING = {"pid": "process", "file": "file", "gone": "the removal of", "log": "a match in"}
STILL = {"pid": "still running", "file": "not ready", "gone": "still present", "log": "no match"}
DONE = {"pid": "every process exited", "file": "every file is ready", "gone": "every path is gone",
        "log": "the log matched"}


# MARK: - Commands


def cmd_scope_set(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    scope_id = check_name(args.id, "scope")
    agent = ctx.optional_agent(args.agent)
    if args.task is not None:
        check_text(args.task, "--task")
    conn = ctx.conn
    with writing(conn):
        existing = conn.execute("SELECT * FROM scopes WHERE id = ?", (scope_id,)).fetchone()
        if args.parent is None:
            parent = existing["parent"] if existing else None
        else:
            parent = check_name(args.parent, "parent scope") if args.parent else None
            if parent is not None:
                check_parent(conn, scope_id, parent)
        kind = args.kind or (existing["kind"] if existing else ("agent" if parent else "project"))
        task = args.task if args.task is not None else (existing["task"] if existing else "")
        now = time.time()
        if existing:
            conn.execute("UPDATE scopes SET kind = ?, parent = ?, task = ?, agent = COALESCE(?, agent), updated = ? "
                         "WHERE id = ?", (kind, parent, task, agent, now, scope_id))
        else:
            conn.execute("INSERT INTO scopes (id, kind, parent, task, agent, created, updated) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)", (scope_id, kind, parent, task, agent, now, now))
        record(conn, "scope set", scope=scope_id, agent=agent, detail=f"{kind}, parent {parent or 'none'}: {task}")
        row = conn.execute("SELECT * FROM scopes WHERE id = ?", (scope_id,)).fetchone()
    if args.json:
        emit(scope_json(row, {}))
    else:
        say(f"scope {describe_scope(row, {})}")
    return 0


def check_parent(conn: sqlite3.Connection, scope_id: str, parent: str) -> None:
    """Refuses an unknown parent, or one under `scope_id`, which would make a cycle. O(depth)."""
    current, seen = parent, set()
    while current is not None and current not in seen:
        if current == scope_id:
            raise WorkError(f"scope {scope_id} cannot be under {parent}, which is {scope_id} or under it")
        seen.add(current)
        row = conn.execute("SELECT parent FROM scopes WHERE id = ?", (current,)).fetchone()
        if row is None:
            raise WorkError(f"unknown parent scope {current}")
        current = row["parent"]


def scope_json(row: sqlite3.Row, counts: dict[str, dict[str, int]]) -> dict:
    return {"id": row["id"], "kind": row["kind"], "parent": row["parent"], "task": row["task"], "agent": row["agent"],
            "updated": iso(row["updated"]), "tasks": counts.get(row["id"], {})}


def describe_scope(row: sqlite3.Row, counts: dict[str, dict[str, int]]) -> str:
    text = f"{row['id']} ({row['kind']})"
    if row["task"]:
        text += f": {printable(row['task'])}"
    tally = counts.get(row["id"])
    if tally:
        text += " [" + ", ".join(f"{number} {state}" for state, number in tally.items()) + "]"
    return text


def scope_rows(conn: sqlite3.Connection, scope: str | None) -> list[sqlite3.Row]:
    return conn.execute(f"SELECT * FROM scopes WHERE {in_scope('id')} ORDER BY created, id",
                        {"scope": scope}).fetchall()


def scope_counts(conn: sqlite3.Connection, scope: str | None) -> dict[str, dict[str, int]]:
    """For each scope, how many of its own tasks are in each state that is not final."""
    counts: dict[str, dict[str, int]] = {}
    for row in conn.execute(f"SELECT scope, state, COUNT(*) FROM tasks WHERE scope IS NOT NULL AND {in_scope('scope')} "
                            "AND state IN ('queued', 'claimed', 'running') GROUP BY scope, state", {"scope": scope}):
        counts.setdefault(row[0], {})[row[1]] = row[2]
    return counts


def scope_tree(rows: list[sqlite3.Row], counts: dict[str, dict[str, int]]) -> list[str]:
    """The scopes as an indented tree, walked with an explicit stack."""
    ids = {row["id"] for row in rows}
    children: dict[str | None, list[sqlite3.Row]] = {}
    for row in rows:
        children.setdefault(row["parent"] if row["parent"] in ids else None, []).append(row)
    lines, stack = [], [(row, 0) for row in reversed(children.get(None, []))]
    while stack:
        row, depth = stack.pop()
        lines.append("  " * depth + describe_scope(row, counts))
        stack.extend((child, depth + 1) for child in reversed(children.get(row["id"], [])))
    return lines


def lineage(conn: sqlite3.Connection, scope: str) -> list[str]:
    chain, current = [], scope
    while current is not None and current not in chain:
        chain.append(current)
        row = conn.execute("SELECT parent FROM scopes WHERE id = ?", (current,)).fetchone()
        current = row["parent"] if row else None
    return list(reversed(chain))


def cmd_scope_show(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    scope = ctx.scope(args.id)
    conn = ctx.conn
    with reading(conn):
        rows = scope_rows(conn, scope)
        counts = scope_counts(conn, scope)
        chain = lineage(conn, scope) if scope else []
    if args.json:
        emit({"scope": scope, "lineage": chain, "scopes": [scope_json(row, counts) for row in rows]})
        return 0
    if len(chain) > 1:
        print("lineage: " + " > ".join(chain))
    print("\n".join(scope_tree(rows, counts)) if rows else "no scope yet: `work scope set ID --kind project`")
    return 0


def cmd_add(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    agent = ctx.agent(args.agent)
    scope = ctx.scope(args.scope)
    if command is not None:
        check_command(command)
    if not KIND.fullmatch(args.kind):
        raise WorkError(f"kind {args.kind!r} is not valid: use up to 64 letters, digits, _ or -")
    title = check_text(args.title, "--title", 1000)
    check_weight(args.weight)
    cwd = working_directory(args.cwd)
    files = canonical_files(args.files or [], cwd)
    after = unique(args.after or [])
    if len(after) > MAX_ITEMS:
        raise WorkError(f"more than {MAX_ITEMS} prerequisites")
    conn = ctx.conn
    with writing(conn):
        task_id = check_name(args.id, "task") if args.id else new_id(conn, "task")
        if conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
            raise WorkError(f"task {task_id} exists already")
        for prerequisite in after:
            check_name(prerequisite, "--after")
            if conn.execute("SELECT 1 FROM tasks WHERE id = ?", (prerequisite,)).fetchone() is None:
                raise WorkError(f"task {task_id} is after unknown task {prerequisite}")
        insert_task(conn, task_id, title, args.kind, scope, agent, after, args.size, args.value, files, command, cwd,
                    args.weight)
        row = get_task(conn, task_id)
    if args.json:
        emit(task_json(row))
    else:
        what = f" to run {display(command)}" if command else ""
        say(f"queued task {task_id}{what}")
    return 0


def insert_task(conn: sqlite3.Connection, task_id: str, title: str, kind: str, scope: str | None, author: str,
                after: list[str], size: float, value: float, files: list[str], command: list[str] | None, cwd: str,
                weight: float, state: str = "queued") -> None:
    # order_tasks.make_task checks the fields the ordering reads, with the ordering's own rules.
    try:
        order_tasks.make_task({"id": task_id, "kind": kind, "after": after, "size": size, "value": value,
                               "files": files}, 0)
    except order_tasks.InputError as error:
        raise WorkError(str(error)) from None
    now = time.time()
    # A job typed inline with `work run -- ...` is claimed and accepted by its author as it is created: the caller
    # typed the command itself. A queued command waits for its claimant's acceptance.
    inline = (author, now, author) if state == "claimed" else (None, None, None)
    signed = signatures(command, cwd) if command is not None else {}
    conn.execute("INSERT INTO tasks (id, title, kind, scope, author, queued, after, size, value, files, command, cwd, "
                 "weight, state, agent, claimed, accepted, sig_full, sig_head, sig_prog, sig_tool) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (task_id, title, kind, scope, author, now, json.dumps(after), size, value, json.dumps(files),
                  json.dumps(command) if command is not None else None, cwd, weight, state, *inline,
                  *(signed.get(level) for level, _ in SIGNATURE_LEVELS)))
    record(conn, "added", task=task_id, scope=scope, agent=author,
           detail=(title or "") + (f" [{display(command)}]" if command else ""))
    if state == "claimed":
        record(conn, "claimed", task=task_id, scope=scope, agent=author, detail="typed inline with work run")


def describe_queued(row: sqlite3.Row, moved_up_for: str | None, waits: list[tuple[str, str]]) -> str:
    parts = [row["kind"]]
    if moved_up_for:
        parts.append(f"moved up for {moved_up_for}")
    if waits:
        parts.append("waits for " + ", ".join(f"{item} ({state})" for item, state in waits))
    if row["command"]:
        parts.append(f"command by {row['author']}")
    title = f" {printable(row['title'])}" if row["title"] else ""
    return f"{row['id']}{title} ({'; '.join(parts)})"


def cmd_order(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    scope = ctx.scope(args.scope)
    with reading(ctx.conn):
        view = queue(ctx.conn, scope)
    ordered = order_tasks.order(view.graph, args.policy)
    _, source = order_tasks.priorities(view.graph, args.policy)
    if args.json:
        emit({"policy": args.policy, "scope": scope, "order": [
            {**task_json(view.rows[task_id]), "position": position, "moved_up_for": source[task_id],
             "ready": not view.waits[task_id], "waits_for": [{"id": item, "state": state}
                                                             for item, state in view.waits[task_id]]}
            for position, task_id in enumerate(ordered, start=1)]})
        return 0
    if not ordered:
        say("nothing is queued" + (f" in scope {scope}" if scope else ""))
    for position, task_id in enumerate(ordered, start=1):
        print(f"{position}. {describe_queued(view.rows[task_id], source[task_id], view.waits[task_id])}")
    return 0


def cmd_plan(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    scope = ctx.scope(args.scope)
    with reading(ctx.conn):
        view = queue(ctx.conn, scope)
    outside = {task_id: [(item, state) for item, state in waits if item not in view.rows]
               for task_id, waits in view.waits.items()}
    outside = {task_id: waits for task_id, waits in outside.items() if waits}
    if not view.rows:
        if args.json:
            emit({"agents": args.agents, "lanes": [], "waits_outside_the_queue": {}})
        else:
            say("nothing is queued" + (f" in scope {scope}" if scope else ""))
        return 0
    options = argparse.Namespace(assign=False, agents=args.agents, policy=args.policy, conflict_cost=None,
                                 format="json" if args.json else "text")
    rendered = order_tasks.render(view.graph, options)
    if args.json:
        result = json.loads(rendered)
        result["waits_outside_the_queue"] = {task_id: [{"id": item, "state": state} for item, state in waits]
                                             for task_id, waits in outside.items()}
        emit(result)
        return 0
    print(rendered)
    for task_id, waits in outside.items():
        print(f"note: {task_id} also waits for " + ", ".join(f"{item} ({state})" for item, state in waits))
    return 0


def cmd_next(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    agent = ctx.agent(args.agent)
    scope = ctx.scope(args.scope)
    conn = ctx.conn
    sweep(conn)
    blocked = held_files = 0
    with writing(conn):
        view = queue(conn, scope)
        held = holders(conn)
        chosen = None
        for task_id in order_tasks.order(view.graph, args.policy):
            if view.waits[task_id]:
                blocked += 1
            elif holder_of(view.graph.tasks[task_id], held) is not None:
                held_files += 1
            else:
                chosen = view.rows[task_id]
                take(conn, chosen, agent)
                break
        row = get_task(conn, chosen["id"]) if chosen is not None else None
    if row is None:
        where = f" in scope {scope}" if scope else ""
        reason = (f"nothing is queued{where}" if not view.rows else
                  f"of {len(view.rows)} queued task(s){where}, {blocked} wait for their prerequisites and "
                  f"{held_files} change files that claimed or running tasks hold")
        if args.json:
            emit({"claimed": None, "reason": reason})
        else:
            say(f"nothing to claim: {reason}")
        return 1
    if args.json:
        emit({"claimed": task_json(row), "reason": ""})
    else:
        title = f": {printable(row['title'])}" if row["title"] else ""
        say(f"claimed task {row['id']}{title}")
        for line in next_steps(row) + default_name_note(ctx, args, agent):
            say(line)
    return 0


def cmd_claim(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    agent = ctx.agent(args.agent)
    task_id = check_name(args.id, "task")
    conn = ctx.conn
    sweep(conn)
    with writing(conn):
        row = get_task(conn, task_id)
        if row["state"] != "queued":
            raise refusal(f"task {task_id} is {describe_state(row)}")
        after = json.loads(row["after"])
        states = states_of(conn, after)
        waiting = [f"{item} ({states.get(item, 'unknown')})" for item in after if states.get(item) != "done"]
        if waiting:
            raise refusal(f"task {task_id} waits for {', '.join(waiting)}")
        holder = holder_of(order_task(row, 0), holders(conn))
        if holder is not None:
            raise refusal(f"task {task_id} changes files that task {holder['id']} holds ({describe_state(holder)})")
        take(conn, row, agent)
        row = get_task(conn, task_id)
    if args.json:
        emit(task_json(row))
    else:
        say(f"claimed task {task_id}")
        for line in next_steps(row) + default_name_note(ctx, args, agent):
            say(line)
    return 0


def cmd_show(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    row = get_task(ctx.conn, check_name(args.id, "task"))
    now = time.time()
    if args.json:
        emit(task_json(row, now))
        return 0
    task_id, lines = row["id"], []
    if row["command"]:
        # The command comes first, with its size, so that no long title or file list pushes it past the end of what
        # a harness shows; the digest binds an acceptance to exactly this command in this directory.
        argv, sealed = json.loads(row["command"]), digest(row)
        lines += [f"command of task {task_id} ({command_size(argv)}), queued by {row['author']}:",
                  f"  {display(argv)}", f"directory: {printable(row['cwd'])}", f"digest: {sealed}"]
        if row["agent"] is None:
            lines.append("acceptance: the agent that claims it accepts it after reading it")
        elif row["accepted"] == row["agent"]:
            lines.append(f"acceptance: accepted by {row['agent']}")
        else:
            lines.append(f"acceptance: needed from {row['agent']}; if the command is right, run "
                         f"`work accept {task_id} --digest {sealed}`")
    lines += [f"task {task_id}" + (f": {printable(row['title'])}" if row["title"] else ""),
              f"state: {describe_state(row)}",
              f"kind: {row['kind']}; size {row['size']:g}, value {row['value']:g}, weight {row['weight']:g}",
              f"scope: {row['scope'] or '-'}; author: {row['author']}; queued {clock(row['queued'])}"]
    after = json.loads(row["after"])
    if after:
        states = states_of(ctx.conn, after)
        lines.append(capped("after", [f"{item} ({states.get(item, 'unknown')})" for item in after]))
    files = json.loads(row["files"])
    if files:
        lines.append(capped("files", [printable(path) for path in files]))
    if row["log"]:
        lines.append(f"log: {printable(row['log'])}")
    if row["requested"] is not None:
        run = f"run: waited {span(waited_of(row, now))} for capacity, ran {span(ran_of(row, now))}"
        if row["status"] is not None:
            run += f", status {row['status']}"
        if row["pid"]:
            run += f", process {row['pid']}"
        if row["rss"] is not None:
            run += f", cpu {row['cpu']:.0f}%, memory {memory(row['rss'])} (peak {memory(row['rss_peak'])})"
        if row["cpu_time"] is not None:
            run += f", cpu time {span(row['cpu_time'])}"
        lines.append(run)
        lines.append(f"predicted: {describe_prediction(row)}")
    if row["note"]:
        lines.append(f"note: {printable(row['note'])}")
    print("\n".join(lines))
    return 0


def cmd_accept(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    agent = ctx.agent(args.agent)
    task_id = check_name(args.id, "task")
    conn = ctx.conn
    with writing(conn):
        row = get_task(conn, task_id)
        if row["command"] is None:
            raise refusal(f"task {task_id} has no command to accept")
        if row["state"] != "claimed" or row["requested"] is not None:
            raise refusal(f"task {task_id} is {describe_state(row)}; accept a command after you claim its task")
        if row["agent"] != agent:
            raise refusal(f"task {task_id} is claimed by {row['agent']}; only that agent accepts its command")
        sealed = digest(row)
        if args.digest.strip().lower() != sealed:
            raise refusal(f"the digest does not match the command of task {task_id} in its directory; read it "
                          f"with `work show {task_id}`, and accept it with the digest that show prints")
        size = command_size(json.loads(row["command"]))
        if row["accepted"] == agent:
            message = f"you accepted the command of task {task_id} already ({size})"
        else:
            conn.execute("UPDATE tasks SET accepted = ? WHERE id = ?", (agent, task_id))
            record(conn, "accepted", task=task_id, scope=row["scope"], agent=agent, detail=f"digest {sealed}")
            message = (f"accepted the command of task {task_id}, queued by {row['author']} ({size}); "
                       f"run it with `work run {task_id}`")
        row = get_task(conn, task_id)
    if args.json:
        emit(task_json(row))
    else:
        say(message)
    return 0


def cmd_run(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    agent = ctx.agent(args.agent)
    conn = ctx.conn
    prune(ctx)
    if command is None:
        if args.task is None:
            raise WorkError("name a task you claimed, or give a command after --")
        extras = [flag for flag, value in (("--id", args.id), ("--weight", args.weight), ("--files", args.files),
                                           ("--cwd", args.cwd), ("--kind", args.kind), ("--title", args.title),
                                           ("--scope", args.scope)) if value is not None]
        if extras:
            raise WorkError(f"{', '.join(extras)} describe a new job; give its command after --")
        task_id = check_name(args.task, "task")
    else:
        if args.task is not None:
            raise WorkError("give a task ID or a command after --, not both")
        check_command(command)
        scope = ctx.scope(args.scope)
        kind = args.kind or "other"
        if not KIND.fullmatch(kind):
            raise WorkError(f"kind {kind!r} is not valid: use up to 64 letters, digits, _ or -")
        title = check_text(args.title or "", "--title", 1000)
        weight = check_weight(args.weight or 1.0)
        cwd = working_directory(args.cwd)
        files = canonical_files(args.files or [], cwd)
    supervisor = None
    try:
        # One transaction creates the job if it is new, checks it, starts its supervisor and names it the owner:
        # there is no moment when the job is reserved and nobody owns it, and a rollback leaves nothing behind.
        with writing(conn):
            if command is not None:
                task_id = check_name(args.id, "task") if args.id else new_id(conn, "job")
                if conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
                    raise WorkError(f"task {task_id} exists already")
                holder = holder_of(order_tasks.make_task({"id": task_id, "files": files}, 0), holders(conn))
                if holder is not None:
                    raise refusal(f"job {task_id} changes files that task {holder['id']} holds "
                                  f"({describe_state(holder)})")
                insert_task(conn, task_id, title, kind, scope, agent, [], 1.0, 1.0, files, command, cwd, weight,
                            state="claimed")
            row = get_task(conn, task_id)
            check_runnable(row, agent)
            log = os.path.join(ctx.logs, f"{task_id}.log")
            supervisor = start_supervisor(ctx, task_id, log)
            reserve(conn, row, agent, supervisor.pid, log)
    finally:
        if supervisor is not None:
            supervisor.stdin.close()  # The supervisor goes on only if it finds itself the owner.
    return wait_for(ctx, [task_id], False, args.timeout, args.tail, args.json, supervisor, args.interval)


def cmd_wait(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    modes = [name for name, given in (("task IDs", args.ids), ("--all", args.all), ("--pid", args.pid),
                                      ("--file", args.file), ("--gone", args.gone), ("--log", args.log)) if given]
    if len(modes) != 1:
        raise WorkError("wait for one thing: task IDs, --all, --pid, --file, --gone or --log"
                        + (f", not {' and '.join(modes)}" if modes else ""))
    if args.any and not args.ids:
        raise WorkError("--any goes with task IDs")
    if args.scope is not None and not args.all:
        raise WorkError("--scope goes with --all")
    if not (args.ids or args.all):
        return wait_condition(args)
    conn = ctx.conn
    if args.all:
        if args.ids:
            raise WorkError("give task IDs or --all, not both")
        scope = ctx.scope(args.scope)
        ids = [row["id"] for row in conn.execute(
            f"SELECT id FROM tasks WHERE (state = 'running' OR (state = 'claimed' AND requested IS NOT NULL)) "
            f"AND {in_scope('scope')} ORDER BY seq", {"scope": scope})]
        if not ids:
            if args.json:
                emit({"status": 0, "timed_out": False, "tasks": []})
            else:
                say("no job runs" + (f" in scope {scope}" if scope else ""))
            return 0
    else:
        ids = unique([check_name(task_id, "task") for task_id in args.ids])
        for task_id in ids:
            get_task(conn, task_id)
    if not args.json:
        say(f"waiting for {' '.join(ids)}" + (" (the first to end)" if args.any and len(ids) > 1 else ""))
    return wait_for(ctx, ids, args.any, args.timeout, args.tail, args.json, interval=args.interval)


def cmd_close(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    state = {"done": "done", "fail": "failed", "cancel": "cancelled"}[args.command_name]
    agent = ctx.agent(args.agent)
    task_id = check_name(args.id, "task")
    note = check_text(args.note or "", "--note")
    conn = ctx.conn
    with writing(conn):
        row = get_task(conn, task_id)
        if row["state"] in FINAL:
            raise refusal(f"task {task_id} is {describe_state(row)} already")
        if row["state"] == "running":
            raise refusal(f"task {task_id} runs as process {row['pid']}, and its supervisor records how it ends; to "
                          f"stop it, `kill -TERM -- -{row['pid']}`")
        if row["state"] == "queued" and row["author"] != agent:
            raise refusal(f"task {task_id} was queued by {row['author']}; until an agent claims it, only "
                          f"{row['author']} closes it")
        if row["state"] == "claimed" and row["agent"] != agent:
            raise refusal(f"task {task_id} is claimed by {row['agent']}; only that agent closes it")
        if row["command"] is not None and state != "cancelled":
            raise refusal(f"task {task_id} has a command: run it with `work run {task_id}`, or cancel it")
        conn.execute("UPDATE tasks SET state = ?, ended = ?, note = ? WHERE id = ?",
                     (state, time.time(), note, task_id))
        record(conn, state, task=task_id, scope=row["scope"], agent=agent, detail=note)
        row = get_task(conn, task_id)
    if args.json:
        emit(task_json(row))
    else:
        say(f"task {task_id} is {state}")
    return 0


def cmd_settings(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    agent = ctx.optional_agent(args.agent)
    conn = ctx.conn
    changes = {key: value for key, value in (("cpu_budget", args.cpu_budget), ("capacity", args.capacity),
                                             ("load_factor", args.load_factor),
                                             ("load_wait", args.load_wait), ("log_limit", args.log_limit),
                                             ("keep_days", args.keep_days), ("idle_min", args.idle_min),
                                             ("memory_limit", args.memory_limit),
                                             ("backfill_wait", args.backfill_wait),
                                             ("small_weight", args.small_weight)) if value is not None}
    if changes:
        with writing(conn):
            for key, value in changes.items():
                # `key` comes from the fixed list above, never from input.
                # The CPU budget's auto and the capacity's off are stored as NULL, their default.
                default = key in ("cpu_budget", "capacity") and value in ("auto", "off")
                conn.execute(f"UPDATE settings SET {key} = ? WHERE id = 1", (None if default else value,))
            record(conn, "settings", agent=agent, detail=", ".join(f"{key} {value}" for key, value in changes.items()))
    settings = settings_of(conn)
    box = machine(settings)
    if args.json:
        emit({"cpu_budget": box.budget, "cpu_budget_is_default": settings.cpu_budget is None,
              "capacity": box.capacity, "capacity_is_default": settings.capacity is None, "cpus": box.cpus,
              "idle_min": settings.idle_min, "memory_limit": settings.memory_limit,
              "load_factor": settings.load_factor, "load_limit": box.load_limit, "load_wait": settings.load_wait,
              "log_limit": settings.log_limit, "keep_days": settings.keep_days,
              "backfill_wait": settings.backfill_wait, "small_weight": settings.small_weight})
        return 0
    budget_default = " (the default: the CPU count)" if settings.cpu_budget is None else ""
    capacity = "off (the default): no cap on declared weights" if box.capacity is None else \
        f"{box.capacity:g} cores; the running jobs' declared weights fit it"
    memory_rule = "not a gate" if settings.memory_limit == "off" else f"jobs start below {settings.memory_limit}"
    print(f"cpu budget: {box.budget:g} cores{budget_default}; the running jobs' predicted cores fit it\n"
          f"capacity: {capacity}\n"
          f"idle min: {settings.idle_min:g}%; jobs start while the CPU is at least this idle\n"
          f"memory limit: {settings.memory_limit}; {memory_rule} memory pressure\n"
          f"load factor: {settings.load_factor:g}; on Linux only, jobs start below load {box.load_limit:.2f} on "
          f"{box.cpus} CPUs\n"
          f"load wait: {span(settings.load_wait)}; a job that the machine's pressure alone holds back longer fails\n"
          f"backfill wait: {span(settings.backfill_wait)}; a job that waited longer keeps every job behind it\n"
          f"small weight: {settings.small_weight:g}; a job this light may start past the head for a while\n"
          f"log limit: {settings.log_limit} bytes; a job whose log grows past it is stopped\n"
          f"keep: {settings.keep_days:g} days of events and of the logs of ended tasks")
    return 0


def cmd_status(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    conn = ctx.conn
    swept = sweep(conn)
    prune(ctx)
    scope = ctx.scope(args.scope)
    box = machine(settings_of(conn), Gauge().read())
    now = time.time()
    with reading(conn):
        scopes = scope_rows(conn, scope)
        counts = scope_counts(conn, scope)
        active = conn.execute(f"SELECT * FROM tasks WHERE state IN ('claimed', 'running') AND {in_scope('scope')} "
                              "ORDER BY seq", {"scope": scope}).fetchall()
        totals = dict(conn.execute(f"SELECT state, COUNT(*) FROM tasks WHERE {in_scope('scope')} GROUP BY state",
                                   {"scope": scope}).fetchall())
        view = queue(conn, scope)
        # The budget and the open exclusive batch are the machine's, whatever the scope.
        every_running = conn.execute("SELECT id, weight, pred_cores, batch FROM tasks WHERE state = 'running' "
                                     "ORDER BY started, seq").fetchall()
        every_waiting = [row for row in conn.execute("SELECT id, kind, requested, seq, owner, weight, pred_cores, "
                                                     "pred_duration, batch FROM tasks WHERE state = 'claimed' AND "
                                                     "requested IS NOT NULL ORDER BY requested, seq")
                         if exists(row["owner"])]
    used, jobs = sum(cores(row, box) for row in every_running), len(every_running)
    declared = sum(row["weight"] for row in every_running)
    running = [row for row in active if row["state"] == "running"]
    waiting = [row for row in active if row["state"] == "claimed" and row["requested"] is not None]
    batch = open_batch(every_running, every_waiting)
    every_waiting.sort(key=lambda row: waiting_order(row, batch))
    batch_json = None if batch is None else {
        "id": batch, "running": [row["id"] for row in every_running if row["batch"] == batch],
        "next": [row["id"] for row in every_waiting if row["batch"] == batch]}
    tally = {state: totals.get(state, 0) for state in ("queued", "claimed", "running", "done", "failed", "cancelled")}
    tally["ready"] = sum(1 for waits in view.waits.values() if not waits)
    signals, settings = box.signals, box.settings
    host = {"cpus": box.cpus, "idle": signals.idle, "idle_min": settings.idle_min, "memory": signals.memory,
            "memory_limit": settings.memory_limit, "load": signals.load, "load_gate": signals.load_gate,
            "load_limit": box.load_limit, "cpu_budget": box.budget, "used": used, "capacity": box.capacity,
            "declared": declared, "jobs": jobs,
            "holds": pressure(box)[1] if pressure(box) else None, "batch": batch_json}
    if args.json:
        emit({"time": iso(now), "scope": scope, "machine": host,
              "scopes": [scope_json(row, counts) for row in scopes],
              "running": [task_json(row, now) for row in running], "waiting": [task_json(row, now) for row in waiting],
              "counts": tally, "swept": swept})
        return 0
    print(describe_machine(box))
    held = pressure(box)
    cap = "no cap" if box.capacity is None else f"capacity {number(box.capacity)}"
    print(f"cores: predicted {number(used)} of the CPU budget of {number(box.budget)} taken by {jobs} job(s); "
          f"declared {number(declared)} ({cap})" + (f"; new jobs wait: {held[1]}" if held else ""))
    if batch is not None:
        print(f"exclusive batch: {describe_batch(batch, every_running, every_waiting)}")
    if scopes:
        print("scopes:")
        print("\n".join("  " + line for line in scope_tree(scopes, counts)))
    if running:
        print("running:")
        for row in running:
            usage_text = (f"cpu {row['cpu']:.0f}%, memory {memory(row['rss'])} (peak {memory(row['rss_peak'])})"
                          if row["rss"] is not None else "not sampled yet")
            print(f"  {row['id']}: process {row['pid'] or '-'}, {span(ran_of(row, now))}, {usage_text}, "
                  f"weight {row['weight']:g}, {describe_hold(row, box)}, {row['agent']}, "
                  f"scope {row['scope'] or '-'}: "
                  f"{display(json.loads(row['command']))}" + (f" ({printable(row['note'])})" if row["note"] else ""))
    if waiting:
        print("waiting for capacity:")
        for row in waiting:
            print(f"  {row['id']}: {span(waited_of(row, now))}, weight {row['weight']:g}, {describe_hold(row, box)}, "
                  f"{row['agent']}, scope {row['scope'] or '-'}" + (f": {printable(row['note'])}" if row["note"] else ""))
    print(f"tasks: {tally['queued']} queued ({tally['ready']} ready), {tally['claimed']} claimed, "
          f"{tally['running']} running, {tally['done']} done, {tally['failed']} failed, {tally['cancelled']} cancelled")
    for change in swept:
        print(f"swept: {change['id']} {change['state']}: {change['note']}")
    return 0


def cmd_log(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    scope = ctx.scope(args.scope)
    task = check_name(args.task, "task") if args.task else None
    agent = check_name(args.agent, "agent") if args.agent else None
    rows = ctx.conn.execute(
        f"SELECT * FROM (SELECT * FROM events WHERE {in_scope('scope')} AND (:task IS NULL OR task = :task) "
        "AND (:agent IS NULL OR agent = :agent) ORDER BY seq DESC LIMIT :limit) ORDER BY seq",
        {"scope": scope, "task": task, "agent": agent, "limit": args.limit}).fetchall()
    if args.json:
        emit({"events": [{"time": iso(row["time"]), "scope": row["scope"], "task": row["task"], "agent": row["agent"],
                          "what": row["what"], "detail": row["detail"]} for row in rows]})
        return 0
    for row in rows:
        subject = " ".join(item for item in (row["scope"] and f"[{row['scope']}]", row["task"], row["agent"] and
                                             f"by {row['agent']}") if item)
        detail = f": {printable(row['detail'])}" if row["detail"] else ""
        print(f"{clock(row['time'])} {row['what']} {subject}{detail}")
    return 0


# MARK: - Command line


def build_parser() -> argparse.ArgumentParser:
    summary, _, details = (__doc__ or "").partition("\n\n")
    parser = argparse.ArgumentParser(prog="work", description=summary, epilog=details,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command_name", metavar="COMMAND", required=True)

    def command(name: str, handler, help_text: str, *, scope: bool = False, agent: bool = False,
                parent=commands) -> argparse.ArgumentParser:
        sub = parent.add_parser(name, help=help_text, description=help_text)
        if scope:
            sub.add_argument("--scope", help="this scope and those under it (default $WORK_SCOPE; '' for every scope)")
        if agent:
            sub.add_argument("--agent", help="your agent name (default $WORK_AGENT)")
        sub.add_argument("--json", action="store_true", help="print JSON")
        sub.set_defaults(handler=handler)
        return sub

    scope = commands.add_parser("scope", help="set or show a scope and the task it works on")
    actions = scope.add_subparsers(dest="scope_action", metavar="ACTION", required=True)
    sub = command("set", cmd_scope_set, "create or update a scope", agent=True, parent=actions)
    sub.add_argument("id")
    sub.add_argument("--kind", choices=SCOPE_KINDS,
                     help="for a new scope, project without --parent and agent with one")
    sub.add_argument("--parent", help="the scope it belongs to; '' for none")
    sub.add_argument("--task", help="what it works on now; '' to clear it")
    sub = command("show", cmd_scope_show, "show a scope and those under it (default $WORK_SCOPE, else every scope)",
                  parent=actions)
    sub.add_argument("id", nargs="?")

    sub = command("add", cmd_add, "queue a task; a command after -- is its command", scope=True, agent=True)
    sub.add_argument("--id", help="a unique id (default task-N)")
    sub.add_argument("--title", default="")
    sub.add_argument("--kind", default="other", help="validity, correctness, safety, security, data-loss and crash "
                                                     "come first")
    sub.add_argument("--after", nargs="+", action="extend", metavar="ID", help="tasks that must be done first")
    sub.add_argument("--size", type=positive, default=1.0, help="effort (default 1)")
    sub.add_argument("--value", type=positive, default=1.0, help="cost of delay (default 1)")
    sub.add_argument("--files", nargs="+", action="extend", metavar="PATH",
                     help="files or directories it changes, relative to --cwd")
    sub.add_argument("--weight", type=positive, default=1.0,
                     help="cores its command may use: the cap on its predicted cores, and the estimate until it has "
                          "a history (default 1)")
    sub.add_argument("--cwd", help="the command's directory (default the current one)")

    for name, help_text in (("order", "the queued tasks in work order"),
                            ("plan", "a schedule of the queued tasks for several agents")):
        sub = command(name, cmd_order if name == "order" else cmd_plan, help_text, scope=True)
        sub.add_argument("--policy", choices=order_tasks.POLICIES, default="fifo")
        if name == "plan":
            sub.add_argument("--agents", type=counting(1), required=True)

    sub = command("next", cmd_next, "claim the most urgent ready task whose files are free", scope=True, agent=True)
    sub.add_argument("--policy", choices=order_tasks.POLICIES, default="fifo")
    command("claim", cmd_claim, "claim this task", agent=True).add_argument("id")
    sub = command("accept", cmd_accept, "accept the command of a task you claimed, after reading it with show",
                  agent=True)
    sub.add_argument("id")
    sub.add_argument("--digest", required=True, help="the digest that `work show ID` prints for the command")
    command("show", cmd_show, "every field of a task, its command included").add_argument("id")

    sub = command("run", cmd_run, "run the command of a task you claimed, or a command of your own after --",
                  agent=True)
    sub.add_argument("task", nargs="?", help="a task you claimed")
    sub.add_argument("--id", help="the new job's id (default job-N)")
    sub.add_argument("--weight", type=positive,
                     help="cores the new job may use: the cap on its predicted cores, and the estimate until it has "
                          "a history (default 1)")
    sub.add_argument("--files", nargs="+", action="extend", metavar="PATH", help="files the new job changes")
    sub.add_argument("--cwd", help="the new job's directory (default the current one)")
    sub.add_argument("--kind", help="the new job's kind (default other)")
    sub.add_argument("--title")
    sub.add_argument("--scope", help="the new job's scope (default $WORK_SCOPE)")
    sub.add_argument("--timeout", type=duration, default=DEFAULT_TIMEOUT,
                     help="stop waiting after this long, with 124; the job runs on (default 570)")
    sub.add_argument("--tail", type=counting(0), default=5, help="log lines to print at the end (default 5)")
    sub.add_argument("--interval", type=positive, default=0.5, metavar="SECONDS",
                     help="the longest pause between two checks (default 0.5)")

    sub = command("wait", cmd_wait, "wait until tasks end, or processes exit, files appear or go, a log matches")
    sub.add_argument("ids", nargs="*", metavar="ID", help="tasks, until they are done, failed or cancelled")
    sub.add_argument("--any", action="store_true", help="with task IDs: return when the first one ends")
    sub.add_argument("--all", action="store_true", help="every job that runs or waits in the scope")
    sub.add_argument("--scope", help="with --all: this scope and those under it (default $WORK_SCOPE)")
    sub.add_argument("--pid", nargs="+", metavar="PID", help="until every process has exited; a zombie has")
    sub.add_argument("--file", nargs="+", metavar="PATH",
                     help="until every path exists and is not empty; one file holding a number exits with it")
    sub.add_argument("--gone", nargs="+", metavar="PATH", help="until no path exists, as for a lock file")
    sub.add_argument("--log", nargs=2, metavar=("PATH", "PATTERN"),
                     help="until a line of PATH matches the extended regular expression PATTERN (grep -E)")
    sub.add_argument("--timeout", type=duration, default=DEFAULT_TIMEOUT, help="default 570 s; then exit 124")
    sub.add_argument("--interval", type=positive, default=0.5, metavar="SECONDS",
                     help="the longest pause between two checks (default 0.5)")
    sub.add_argument("--tail", type=counting(0), default=5,
                     help="log lines to print for each job, or of --log's file (default 5)")

    mine = "one you claimed, or queued and nobody claimed"
    for name, help_text in (("done", f"close a task without a command as done: {mine}"),
                            ("fail", f"close a task without a command as failed: {mine}"),
                            ("cancel", f"cancel a task that does not run: {mine}")):
        sub = command(name, cmd_close, help_text, agent=True)
        sub.add_argument("id")
        sub.add_argument("--note", help="why")

    sub = command("settings", cmd_settings, "show or set the capacity and limits that every agent's jobs share",
                  agent=True)
    sub.add_argument("--cpu-budget", type=budget_setting, metavar="CORES",
                     help="predicted cores that running jobs may take together, or auto for the CPU count")
    sub.add_argument("--capacity", type=capacity_setting,
                     help="a cap on the declared cores that running jobs may take together, or off (the default)")
    sub.add_argument("--idle-min", type=percent, metavar="PERCENT",
                     help="jobs start while the CPU is at least this idle (default 15)")
    sub.add_argument("--memory-limit", choices=("warning", "critical", "off"),
                     help="jobs start below this memory pressure (default warning)")
    sub.add_argument("--load-factor", type=positive,
                     help="on Linux, jobs start below this load per CPU (default 1.5)")
    sub.add_argument("--backfill-wait", type=positive, metavar="SECONDS",
                     help="once the head of the line waited this long, no job starts before it (default 300)")
    sub.add_argument("--small-weight", type=positive, metavar="CORES",
                     help="a job this light may start past the head until the backfill wait (default 1)")
    sub.add_argument("--load-wait", type=positive, metavar="SECONDS",
                     help="the longest a job waits on the load alone before it fails (default 1800)")
    sub.add_argument("--log-limit", type=counting(1), metavar="BYTES",
                     help="a job whose log grows past this is stopped (default 268435456)")
    sub.add_argument("--keep-days", type=positive, help="events and logs of ended tasks kept this long (default 14)")
    command("status", cmd_status, "scopes, jobs with their CPU and memory, counts, and the machine's load",
            scope=True)
    sub = command("log", cmd_log, "the events, oldest first", scope=True)
    sub.add_argument("--task")
    sub.add_argument("--agent", help="only this agent's events")
    sub.add_argument("--limit", type=counting(1), default=50, help="the last N events (default 50)")
    return parser


def main(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ if environ is None else environ)
    if argv[:1] == ["_supervise"]:
        return supervise(argv[1:], env)
    command = None
    if "--" in argv:
        cut = argv.index("--")
        argv, command = argv[:cut], argv[cut + 1:]
    arguments = build_parser().parse_args(argv)
    if command is not None and arguments.command_name not in ("add", "run"):
        print("work: only add and run take a command after --", file=sys.stderr)
        return 2
    ctx = Context(env)
    try:
        return arguments.handler(ctx, arguments, command)
    except WorkError as error:
        print(f"work: {error}", file=sys.stderr, flush=True)
        return error.status
    except sqlite3.Error as error:
        print(f"work: database error: {error}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        ctx.close()


if __name__ == "__main__":
    sys.exit(main())

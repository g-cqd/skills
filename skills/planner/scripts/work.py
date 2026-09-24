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
  - Capacity: a job weighs the cores it uses (default 1, at most the CPU count). It starts only while the running
    jobs' weights plus its own fit the capacity, or when no job runs, and while the one-minute load average is below
    the CPU count times the load factor. Jobs that wait for room start in work order: validity first, then the order
    in which they asked. A job that the load alone holds back past the load wait fails. `work settings` shows and
    sets these values, kept in the database so that every agent's jobs are admitted alike: capacity (default the
    CPU count minus 2, at least 1), load factor (1.5), load wait (1800 s), log limit, and how long events and logs
    are kept.
  - Jobs: a detached supervisor starts the command in its own process group with stdin closed, writes its output
    whole to a log, stops it if the log passes the log limit (256 MiB), samples the CPU and memory of its process
    tree every 2 s with ps, and records its true exit status: 127 when the command is missing, 126 when it cannot
    run, 128 plus the signal that killed it. `run` and `wait` return the moment the work ends, or 124 at --timeout
    (default 570 s) while it goes on.
  - Sweep: `status`, `wait`, `next` and `claim` mark failed a job whose supervisor and command are gone with no
    recorded status. `status` and `run` delete events, and the logs of ended tasks, older than 14 days.

State: $AGENT_WORK_HOME/work.db (default ~/.local/state/agent-work), with job logs in logs/. The path is resolved
once; the directory must be yours and private (mode 700), and no directory above it may be a link, belong to another
user than you or root, or be writable by others. Titles, notes and paths refuse control and invisible characters,
and every text view escapes them in commands and job output. Agent names come from --agent or $WORK_AGENT.

Exit status: 0 on success; 1 when work refuses (a task in the wrong state, nothing to claim, a command not
accepted yet); 2 for an input error; for `run` and `wait`, the job's own status, or 124 when the timeout passed first.
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
import subprocess
import sys
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


def capacity_setting(text: str) -> float | str:
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
        name = self.optional_agent(given)
        if name is None:
            raise WorkError("name yourself with --agent or $WORK_AGENT")
        return name

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
                conn.execute(statement)
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


def next_steps(row: sqlite3.Row) -> list[str]:
    task_id = row["id"]
    if row["command"] is None:
        return [f"close it with `work done {task_id}` or `work fail {task_id}` when it is finished"]
    if needs_acceptance(row):
        return [f"{task_id} runs a command that {row['author']} queued; read it with `work show {task_id}`, and "
                f"if it is right, accept it with the `work accept {task_id} --digest ...` line that show prints, "
                f"then `work run {task_id}`"]
    return [f"run it with `work run {task_id}`"]


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

    capacity: float | None  # None: the CPU count minus 2, at least 1
    load_factor: float
    load_wait: float
    log_limit: int
    keep_days: float
    pruned: float | None


def settings_of(conn: sqlite3.Connection) -> Settings:
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    return Settings(row["capacity"], row["load_factor"], row["load_wait"], row["log_limit"], row["keep_days"],
                    row["pruned"])


@dataclass
class Machine:
    cpus: int
    capacity: float
    factor: float
    load: float | None

    @property
    def load_limit(self) -> float:
        return self.cpus * self.factor


def load_average() -> float | None:
    try:
        return os.getloadavg()[0]
    except OSError:
        return None


def machine(settings: Settings, load=load_average) -> Machine:
    cpus = os.cpu_count() or 1
    return Machine(cpus, settings.capacity or max(1, cpus - 2), settings.load_factor, load())


def check_weight(weight: float) -> float:
    cpus = os.cpu_count() or 1
    if weight > cpus:
        raise WorkError(f"--weight {weight:g} is more than the {cpus} CPUs of this machine")
    return weight


def admission(weight: float, used: float, capacity: float, load: float | None,
              load_limit: float) -> tuple[str, str] | None:
    """Why a job of `weight` cores cannot start now, as (cause, reason), or None when it can: its weight must fit the
    capacity beside the running jobs' weights `used`, unless no job runs, so that a job heavier than the capacity runs
    alone rather than never; and the load average must be below `load_limit`."""
    if used > 0 and used + weight > capacity + 1e-9:
        return "capacity", f"{used:g} of {capacity:g} cores are taken and this job needs {weight:g}"
    if load is not None and load >= load_limit:
        return "load", f"the load average {load:.2f} is at or above {load_limit:.2f}"
    return None


def waiting_order(row: sqlite3.Row) -> tuple:
    """A waiting job's place in line, in order_tasks' work order: validity first, then the order in which the jobs
    asked for capacity."""
    return 0 if row["kind"].lower() in order_tasks.VALIDITY_KINDS else 1, row["requested"], row["seq"]


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

    def __init__(self, ctx: Context, task_id: str, load=load_average):
        self.ctx, self.task_id, self.load = ctx, task_id, load
        self.me = os.getpid()
        self.child: subprocess.Popen | None = None
        self.stop: int | None = None
        self.over_limit = False
        # Held while `child` is cleared, and while the sampler signals it, so the sampler never signals a reaped pid.
        self.lock = threading.Lock()

    def run(self) -> int:
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, self.on_signal)
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
            # request, so that the supervisor's own start is not reported as a wait for capacity.
            conn.execute("UPDATE tasks SET requested = ? WHERE id = ?", (time.time(), self.task_id))
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
        cancelled, swept, stopped by a signal, or held back by the machine's load past the settings' load_wait."""
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
                blocked = self.blocker(conn, row, machine(settings, self.load))
                if blocked is None:
                    conn.execute("UPDATE tasks SET state = 'running', started = ?, note = '' WHERE id = ?",
                                 (time.time(), self.task_id))
                    return get_task(conn, self.task_id)
                cause, reason = blocked
                # Other jobs end; outside load need not. A job that the load alone holds back gives up in the end.
                held_since = (held_since or time.monotonic()) if cause == "load" else None
                if held_since is not None and time.monotonic() - held_since >= settings.load_wait:
                    note = (f"{reason} for {span(time.monotonic() - held_since)}, the longest a job waits on the "
                            f"machine's load (work settings --load-wait)")
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
        """Why the job cannot start now, as (cause, reason), or None. Waiting jobs start in work order, so a heavy job
        is not passed forever by lighter ones; a waiting job whose supervisor is gone keeps no place."""
        waiting = conn.execute("SELECT id, kind, requested, seq, owner FROM tasks "
                               "WHERE state = 'claimed' AND requested IS NOT NULL").fetchall()
        first = min((item for item in waiting if item["id"] == row["id"] or exists(item["owner"])), key=waiting_order)
        if first["id"] != row["id"]:
            return "ahead", f"job {first['id']} is ahead of it"
        used = conn.execute("SELECT COALESCE(SUM(weight), 0) FROM tasks WHERE state = 'running'").fetchone()[0]
        return admission(row["weight"], used, box.capacity, box.load, box.load_limit)

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
             supervisor: subprocess.Popen | None = None) -> int:
    """Returns as soon as every task (or, with `any_`, one) is done, failed or cancelled, polling the database with a
    pause that grows from 0.05 s to 0.5 s; sweeps dead jobs every 2 s so that it never waits on one. `run` passes the
    supervisor it started: its end is reaped and swept at once, and the job's start or wait is announced."""
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
        pause = min(pause * 1.5, 0.5)


def announce(row: sqlite3.Row, announced: set[str]) -> None:
    """Says once that a job waits for capacity, and once that it started."""
    if row["pid"] and "started" not in announced:
        say(f"started job {row['id']} ({brief(json.loads(row['command']))}) as process {row['pid']}; "
            f"output in {printable(row['log'])}")
        announced.update(("started", "waiting"))
    elif row["state"] == "claimed" and row["requested"] is not None and row["note"] and "waiting" not in announced:
        say(f"job {row['id']} waits for capacity: {printable(row['note'])}")
        announced.add("waiting")


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
    conn.execute("INSERT INTO tasks (id, title, kind, scope, author, queued, after, size, value, files, command, cwd, "
                 "weight, state, agent, claimed, accepted) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (task_id, title, kind, scope, author, now, json.dumps(after), size, value, json.dumps(files),
                  json.dumps(command) if command is not None else None, cwd, weight, state, *inline))
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
        for line in next_steps(row):
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
        for line in next_steps(row):
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
    return wait_for(ctx, [task_id], False, args.timeout, args.tail, args.json, supervisor)


def cmd_wait(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
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
        if not args.ids:
            raise WorkError("name the tasks to wait for, or use --all")
        if args.scope is not None:
            raise WorkError("--scope goes with --all")
        ids = unique([check_name(task_id, "task") for task_id in args.ids])
        for task_id in ids:
            get_task(conn, task_id)
    if not args.json:
        say(f"waiting for {' '.join(ids)}" + (" (the first to end)" if args.any and len(ids) > 1 else ""))
    return wait_for(ctx, ids, args.any, args.timeout, args.tail, args.json)


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
    changes = {key: value for key, value in (("capacity", args.capacity), ("load_factor", args.load_factor),
                                             ("load_wait", args.load_wait), ("log_limit", args.log_limit),
                                             ("keep_days", args.keep_days)) if value is not None}
    if changes:
        with writing(conn):
            for key, value in changes.items():
                # `key` comes from the fixed list above, never from input.
                conn.execute(f"UPDATE settings SET {key} = ? WHERE id = 1", (None if value == "auto" else value,))
            record(conn, "settings", agent=agent, detail=", ".join(f"{key} {value}" for key, value in changes.items()))
    settings = settings_of(conn)
    box = machine(settings)
    if args.json:
        emit({"capacity": box.capacity, "capacity_is_default": settings.capacity is None, "cpus": box.cpus,
              "load_factor": settings.load_factor, "load_limit": box.load_limit, "load_wait": settings.load_wait,
              "log_limit": settings.log_limit, "keep_days": settings.keep_days})
        return 0
    default = " (the default: the CPU count minus 2)" if settings.capacity is None else ""
    print(f"capacity: {box.capacity:g} cores{default}\n"
          f"load factor: {settings.load_factor:g}; jobs start below load {box.load_limit:.2f} on {box.cpus} CPUs\n"
          f"load wait: {span(settings.load_wait)}; a job that the load alone holds back longer fails\n"
          f"log limit: {settings.log_limit} bytes; a job whose log grows past it is stopped\n"
          f"keep: {settings.keep_days:g} days of events and of the logs of ended tasks")
    return 0


def cmd_status(ctx: Context, args: argparse.Namespace, command: list[str] | None) -> int:
    conn = ctx.conn
    swept = sweep(conn)
    prune(ctx)
    scope = ctx.scope(args.scope)
    box = machine(settings_of(conn))
    now = time.time()
    with reading(conn):
        scopes = scope_rows(conn, scope)
        counts = scope_counts(conn, scope)
        active = conn.execute(f"SELECT * FROM tasks WHERE state IN ('claimed', 'running') AND {in_scope('scope')} "
                              "ORDER BY seq", {"scope": scope}).fetchall()
        totals = dict(conn.execute(f"SELECT state, COUNT(*) FROM tasks WHERE {in_scope('scope')} GROUP BY state",
                                   {"scope": scope}).fetchall())
        used, jobs = conn.execute("SELECT COALESCE(SUM(weight), 0), COUNT(*) FROM tasks "
                                  "WHERE state = 'running'").fetchone()
        view = queue(conn, scope)
    running = [row for row in active if row["state"] == "running"]
    waiting = [row for row in active if row["state"] == "claimed" and row["requested"] is not None]
    tally = {state: totals.get(state, 0) for state in ("queued", "claimed", "running", "done", "failed", "cancelled")}
    tally["ready"] = sum(1 for waits in view.waits.values() if not waits)
    host = {"cpus": box.cpus, "load": box.load, "load_limit": box.load_limit, "load_factor": box.factor,
            "capacity": box.capacity, "used": used, "jobs": jobs}
    if args.json:
        emit({"time": iso(now), "scope": scope, "machine": host,
              "scopes": [scope_json(row, counts) for row in scopes],
              "running": [task_json(row, now) for row in running], "waiting": [task_json(row, now) for row in waiting],
              "counts": tally, "swept": swept})
        return 0
    load = f"{box.load:.2f}" if box.load is not None else "unknown"
    print(f"machine: {box.cpus} CPUs, load {load} (1 min), jobs start below load {box.load_limit:.2f}; "
          f"{used:g} of {box.capacity:g} cores taken by {jobs} job(s)")
    if scopes:
        print("scopes:")
        print("\n".join("  " + line for line in scope_tree(scopes, counts)))
    if running:
        print("running:")
        for row in running:
            usage_text = (f"cpu {row['cpu']:.0f}%, memory {memory(row['rss'])} (peak {memory(row['rss_peak'])})"
                          if row["rss"] is not None else "not sampled yet")
            print(f"  {row['id']}: process {row['pid'] or '-'}, {span(ran_of(row, now))}, {usage_text}, "
                  f"weight {row['weight']:g}, {row['agent']}, scope {row['scope'] or '-'}: "
                  f"{display(json.loads(row['command']))}" + (f" ({printable(row['note'])})" if row["note"] else ""))
    if waiting:
        print("waiting for capacity:")
        for row in waiting:
            print(f"  {row['id']}: {span(waited_of(row, now))}, weight {row['weight']:g}, {row['agent']}, "
                  f"scope {row['scope'] or '-'}" + (f": {printable(row['note'])}" if row["note"] else ""))
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
    sub.add_argument("--weight", type=positive, default=1.0, help="cores its command uses (default 1)")
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
    sub.add_argument("--weight", type=positive, help="cores the new job uses (default 1)")
    sub.add_argument("--files", nargs="+", action="extend", metavar="PATH", help="files the new job changes")
    sub.add_argument("--cwd", help="the new job's directory (default the current one)")
    sub.add_argument("--kind", help="the new job's kind (default other)")
    sub.add_argument("--title")
    sub.add_argument("--scope", help="the new job's scope (default $WORK_SCOPE)")
    sub.add_argument("--timeout", type=duration, default=DEFAULT_TIMEOUT,
                     help="stop waiting after this long, with 124; the job runs on (default 570)")
    sub.add_argument("--tail", type=counting(0), default=5, help="log lines to print at the end (default 5)")

    sub = command("wait", cmd_wait, "wait until tasks end, or with --all until a scope's jobs end")
    sub.add_argument("ids", nargs="*", metavar="ID")
    sub.add_argument("--any", action="store_true", help="return when the first one ends")
    sub.add_argument("--all", action="store_true", help="every job that runs or waits in the scope")
    sub.add_argument("--scope", help="with --all: this scope and those under it (default $WORK_SCOPE)")
    sub.add_argument("--timeout", type=duration, default=DEFAULT_TIMEOUT, help="default 570 s; then exit 124")
    sub.add_argument("--tail", type=counting(0), default=5, help="log lines to print for each job (default 5)")

    for name, help_text in (("done", "close a task without a command as done"),
                            ("fail", "close a task without a command as failed"),
                            ("cancel", "cancel a task that does not run")):
        sub = command(name, cmd_close, help_text, agent=True)
        sub.add_argument("id")
        sub.add_argument("--note", help="why")

    sub = command("settings", cmd_settings, "show or set the capacity and limits that every agent's jobs share",
                  agent=True)
    sub.add_argument("--capacity", type=capacity_setting,
                     help="cores that running jobs may take together, or auto for the CPU count minus 2")
    sub.add_argument("--load-factor", type=positive, help="jobs start below this load per CPU (default 1.5)")
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

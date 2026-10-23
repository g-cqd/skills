#!/usr/bin/env python3
"""Block until a stated condition holds.

`wait` keeps no queue and no daemon. It checks each condition on a pause that grows from 0.05 s to --every and ends
when the conditions hold, or when --timeout passes. A condition that holds stays held.

Conditions (each may be given more than once):
  --run -- CMD...    start CMD as a job and wait for it. The job runs in its own session under a small supervisor that
                     writes its output to a log and its exit status to a file, so it outlives this call: on a timeout
                     or an interrupt the job keeps running and `wait --job ID` continues the wait. Its output is
                     copied to standard output while this call waits. CMD reads no standard input. `--run` must be the
                     last option: every word after `--` belongs to CMD.
  --job ID           a job that an earlier `--run` started has ended. Prints the output that no earlier call printed.
  --pid N            process N has exited. A zombie counts as exited; a process that cannot be probed counts as running.
  --until "CMD"      CMD (split into words, run without a shell, at most --check-timeout seconds per run) exits 0:
                     your own definition of done.
  --file PATH        PATH is a regular file with a size above 0. With --changed: it is, and its mtime or size differs
                     from the start. When PATH is the only condition and holds a number, as `echo $? > PATH` writes
                     it, that number is the exit status.
  --gone PATH        PATH does not exist.
  --log FILE --match REGEX
                     a line of FILE matches REGEX (Python syntax). The lines already there count; --from-end ignores
                     them. The unfinished last line counts. A log that shrank is read again from its start. On a match
                     or a timeout the last --tail lines (default 5) of FILE go to standard output.

By default every condition must hold (--all); --any ends at the first. A job that ends with a nonzero status ends the
wait at once, with that status.

Job commands:
  wait --jobs              list jobs: id, state, age, command
  wait --stop ID           stop a running job and everything it started (TERM, then KILL after 5 s)

Exit status: 0 when the conditions hold; 124 when --timeout (default 570 s, 0 means none) passes first, after which
running jobs keep running; the job's status when a job ends the wait (128 + N after signal N, 126 when the command
cannot be executed, 127 when it is not found); the number in the file for a lone --file; 130 when interrupted;
2 for a usage error. The last line on standard error names what ended the wait and how long it took.

Examples:
  wait --run -- swift test                      # 124 after 570 s: the tests keep running; then `wait --job ID`
  wait --until "test -f build/done.flag" --every 2
  wait --log build.log --match 'BUILD (SUCCEEDED|FAILED)' --timeout 1200
  wait --pid 4242 --gone P2.lock
"""

from __future__ import annotations

import argparse
import codecs
import errno
import json
import os
import re
import secrets
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable, Dict, List, Optional, Tuple

DEFAULT_TIMEOUT = 570.0
DEFAULT_EVERY = 0.5
DEFAULT_CHECK_TIMEOUT = 60.0
FIRST_PAUSE = 0.05
KILL_GRACE = 5.0
MAX_TARGETS = 256
MAX_READ = 16 * 1024 * 1024
MAX_CARRY = 64 * 1024
STATUS_BYTES = 4096
TAIL_BYTES = 64 * 1024
JOB_KEEP_SECONDS = 7 * 24 * 3600
JOB_ID_RE = re.compile(r"^[0-9a-f]{11}-[0-9a-f]{4}$")


class UsageError(Exception):
    """A request that cannot run: exit status 2."""


class Condition:
    """One thing to wait for. `poll` returns True once it holds, and the condition then stays held."""

    def __init__(self, label: str, poll: Callable[[], bool]) -> None:
        self.label = label
        self._poll = poll
        self.held = False

    def update(self) -> bool:
        if not self.held and self._poll():
            self.held = True
        return self.held


# MARK: - Processes


def ps_field(pid: int, field: str) -> Optional[str]:
    try:
        result = subprocess.run(["ps", "-o", f"{field}=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return " ".join(value.split()) if value else None


def pid_alive(pid: int) -> bool:
    """True while the process runs. A zombie has exited. A refused probe (another user's process) counts as running."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = ps_field(pid, "stat")
    return not (state or "").startswith("Z")


def reap(pid: int) -> None:
    """Collect pid when it is our child, so that an exited child does not stay a zombie."""
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass


def signal_group(pgid: int, number: int) -> None:
    try:
        os.killpg(pgid, number)
    except OSError:
        pass


def start_error_status(error: OSError) -> int:
    return 126 if error.errno in (errno.EACCES, errno.EPERM, errno.ENOEXEC, errno.EISDIR) else 127


def resolve_program(word: str) -> Optional[str]:
    """The path of the program a command word names, or None when it cannot be found."""
    if os.sep in word:
        return word if os.path.exists(word) else None
    for directory in os.environ.get("PATH", os.defpath).split(os.pathsep):
        candidate = os.path.join(directory or ".", word)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


# MARK: - Private directory and atomic files


def private_directory(path: str) -> str:
    """Create path as a directory only this user can use, or check that it is one. A symlink, a directory owned by
    someone else, or one that others can enter is refused: a shared temporary directory must not let another user
    plant or read job files."""
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise UsageError(f"{path} is not a directory owned by this user; refusing to use it")
    if info.st_mode & 0o077:
        os.chmod(path, 0o700)
    return path


def jobs_root() -> str:
    base = os.environ.get("WAIT_HOME") or os.path.join(tempfile.gettempdir(), f"agent-wait-{os.getuid()}")
    return private_directory(base)


def write_atomic(path: str, text: str) -> None:
    temp = f"{path}.{os.getpid()}.{secrets.token_hex(2)}.tmp"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(temp, path)


def read_small(path: str, limit: int = STATUS_BYTES) -> Optional[bytes]:
    """At most limit bytes of a regular file, opened without following a symlink or blocking on a FIFO."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        return os.read(fd, limit)
    except OSError:
        return None
    finally:
        os.close(fd)


def status_in(path: str) -> Optional[int]:
    """The number a status file holds, spaces and newlines aside, as `echo $? > FILE` writes it; None for other text."""
    data = read_small(path)
    if data is None:
        return None
    digits = data.replace(b" ", b"").replace(b"\n", b"")
    if not digits or not digits.isdigit() or len(digits) >= 12:
        return None
    number = int(digits)
    return number if number < 2**31 else number % 256


# MARK: - Jobs


def job_directory(job_id: str) -> str:
    if not JOB_ID_RE.match(job_id):
        raise UsageError(f"{job_id!r} is not a job id; `wait --jobs` lists them")
    path = os.path.join(jobs_root(), job_id)
    if not os.path.isdir(path) or os.path.islink(path):
        raise UsageError(f"no job {job_id}; `wait --jobs` lists them")
    return path


def job_info(directory: str) -> Dict[str, object]:
    data = read_small(os.path.join(directory, "job.json"), 1 << 20)
    try:
        return json.loads(data or b"{}")
    except ValueError:
        return {}


def job_status(directory: str) -> Optional[int]:
    return status_in(os.path.join(directory, "status"))


def job_running(directory: str) -> bool:
    """A job without a status runs while its supervisor runs with the recorded start time."""
    if job_status(directory) is not None:
        return False
    info = job_info(directory)
    pid = info.get("supervisor")
    if not isinstance(pid, int) or pid <= 0 or not pid_alive(pid):
        return False
    return ps_field(pid, "lstart") == info.get("started_ps")


def start_job(argv: List[str]) -> Tuple[str, str]:
    """Start argv under a supervisor in its own session; return (job id, job directory)."""
    root = jobs_root()
    prune_jobs(root)
    job_id = f"{int(time.time() * 1000):011x}-{secrets.token_hex(2)}"
    directory = os.path.join(root, job_id)
    os.mkdir(directory, 0o700)
    log_fd = os.open(os.path.join(directory, "log"), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        supervisor = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--_supervise", directory, "--", *argv],
            stdin=subprocess.DEVNULL, stdout=log_fd, stderr=log_fd, start_new_session=True, close_fds=True,
        )
    finally:
        os.close(log_fd)
    info = {"id": job_id, "argv": argv, "cwd": os.getcwd(), "supervisor": supervisor.pid,
            "started": time.time(), "started_ps": ps_field(supervisor.pid, "lstart")}
    write_atomic(os.path.join(directory, "job.json"), json.dumps(info))
    return job_id, directory


def supervise(directory: str, argv: List[str]) -> int:
    """Runs inside the job's session: start argv, wait for it, record its status. A TERM to the group reaches the
    command too; the supervisor stays to record how the command ended."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, preexec_fn=lambda: [
            signal.signal(s, signal.SIG_DFL) for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)])
    except OSError as error:
        print(f"wait: cannot start {argv[0]}: {error.strerror or error}", file=sys.stderr, flush=True)
        code = start_error_status(error)
    else:
        returned = child.wait()
        code = 128 - returned if returned < 0 else returned
    write_atomic(os.path.join(directory, "status"), f"{code}\n")
    return 0


def stop_job(job_id: str) -> int:
    directory = job_directory(job_id)
    if not job_running(directory):
        print(f"wait: job {job_id} is not running (status {job_status(directory)})", file=sys.stderr)
        return 0
    pgid = int(job_info(directory)["supervisor"])  # type: ignore[arg-type]
    signal_group(pgid, signal.SIGTERM)
    deadline = time.monotonic() + KILL_GRACE
    while time.monotonic() < deadline and job_status(directory) is None:
        time.sleep(0.05)
    signal_group(pgid, signal.SIGKILL)
    deadline = time.monotonic() + KILL_GRACE
    while time.monotonic() < deadline and job_status(directory) is None and pid_alive(pgid):
        time.sleep(0.05)
    if job_status(directory) is None:
        write_atomic(os.path.join(directory, "status"), f"{128 + signal.SIGKILL}\n")
    print(f"wait: stopped job {job_id} (status {job_status(directory)})", file=sys.stderr)
    return 0


def list_jobs() -> int:
    root = jobs_root()
    for name in sorted(os.listdir(root)):
        directory = os.path.join(root, name)
        if not JOB_ID_RE.match(name) or not os.path.isdir(directory):
            continue
        info = job_info(directory)
        status = job_status(directory)
        state = f"exited {status}" if status is not None else ("running" if job_running(directory) else "lost")
        started = info.get("started")
        age = f"{int(time.time() - started)}s ago" if isinstance(started, (int, float)) else "?"
        argv = info.get("argv") if isinstance(info.get("argv"), list) else []
        print(f"{name}  {state:<10}  started {age:<12}  {shlex.join(str(a) for a in argv)}")
    return 0


def prune_jobs(root: str) -> None:
    """Remove ended jobs older than a week."""
    now = time.time()
    for name in os.listdir(root):
        directory = os.path.join(root, name)
        if not JOB_ID_RE.match(name) or os.path.islink(directory) or not os.path.isdir(directory):
            continue
        try:
            old = now - os.stat(directory).st_mtime > JOB_KEEP_SECONDS
        except OSError:
            continue
        if old and not job_running(directory):
            for entry in os.listdir(directory):
                try:
                    os.remove(os.path.join(directory, entry))
                except OSError:
                    pass
            try:
                os.rmdir(directory)
            except OSError:
                pass


class Follow:
    """Copies what a job's log gains to standard output, from the point the previous call stopped. The point is kept in
    the job directory (`shown`), so output written between two calls is printed by the second, not lost."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.mark = os.path.join(os.path.dirname(path), "shown")
        self.offset = status_in(self.mark) or 0
        self.copied = 0

    def pump(self) -> None:
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            return
        try:
            size = os.fstat(fd).st_size
            while self.offset < size:
                os.lseek(fd, self.offset, os.SEEK_SET)
                chunk = os.read(fd, min(MAX_READ, size - self.offset))
                if not chunk:
                    break
                self.offset += len(chunk)
                self.copied += len(chunk)
                sys.stdout.buffer.write(chunk)
            sys.stdout.flush()
            if self.copied:
                write_atomic(self.mark, f"{self.offset}\n")
        except (OSError, BrokenPipeError):
            pass
        finally:
            os.close(fd)


class JobWait:
    """A job as a condition: it holds when the job's status file exists."""

    def __init__(self, job_id: str, directory: str) -> None:
        self.job_id = job_id
        self.directory = directory
        self.status: Optional[int] = None
        self.follow = Follow(os.path.join(directory, "log"))
        argv = job_info(directory).get("argv")
        command = shlex.join(str(a) for a in argv) if isinstance(argv, list) else job_id
        self.condition = Condition(f"job {job_id} (`{command}`) exited", self._poll)

    def _poll(self) -> bool:
        self.follow.pump()
        self.status = job_status(self.directory)
        if self.status is None and not job_running(self.directory):
            # The job may have ended between the status read and the liveness check: give the supervisor a moment
            # to write the status before calling the job lost.
            time.sleep(0.2)
            self.status = job_status(self.directory)
            if self.status is None:
                self.status = 1
                print(f"wait: job {self.job_id} ended without a status (its supervisor was killed)", file=sys.stderr)
        if self.status is None:
            return False
        # Copy what the job wrote before it ended, on every path that ends the wait.
        self.follow.pump()
        return True


# MARK: - Other conditions


def pid_condition(pid: int) -> Condition:
    def poll() -> bool:
        reap(pid)
        return not pid_alive(pid)

    return Condition(f"pid {pid} exited", poll)


def file_signature(path: str) -> Optional[Tuple[int, int]]:
    """(mtime, size) of a regular file with a size above 0; None for anything else."""
    try:
        info = os.stat(path)
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
        return None
    return (info.st_mtime_ns, info.st_size)


def file_condition(path: str, changed: bool) -> Condition:
    start = file_signature(path)

    def poll() -> bool:
        now = file_signature(path)
        if now is None:
            return False
        return now != start if changed and start is not None else True

    return Condition(f"{path} {'changed' if changed and start is not None else 'is ready'}", poll)


def gone_condition(path: str) -> Condition:
    return Condition(f"{path} is gone", lambda: not os.path.lexists(path))


def until_condition(command: str, check_timeout: float, deadline: Callable[[], Optional[float]]) -> Condition:
    argv = shlex.split(command)
    if not argv:
        raise UsageError("--until needs a command")
    if resolve_program(argv[0]) is None:
        raise UsageError(f"--until: {argv[0]} not found")

    def poll() -> bool:
        limit = check_timeout
        remaining = deadline()
        if remaining is not None:
            limit = max(0.1, min(limit, remaining))
        try:
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            return False
        try:
            return process.wait(limit) == 0
        except subprocess.TimeoutExpired:
            signal_group(process.pid, signal.SIGKILL)
            process.wait()
            return False

    return Condition(f"`{command}` exited 0", poll)


class LogWatch:
    """Scans the bytes a log gains for a line that matches. The unfinished last line counts and stays as the carry
    (the last 64 KiB of it), so a line written in two parts matches once it is complete. A log that shrank was
    replaced and is read again from its start. A symlink, a FIFO or any file that is not regular never matches."""

    def __init__(self, path: str, regex: "re.Pattern[str]", from_end: bool) -> None:
        self.path, self.regex = path, regex
        self.offset, self.carry = 0, ""
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        if from_end:
            try:
                self.offset = os.stat(path).st_size
            except OSError:
                pass

    def poll(self) -> bool:
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            return False
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                return False
            if info.st_size < self.offset:
                self.offset, self.carry = 0, ""
                self.decoder.reset()
            while self.offset < info.st_size:
                os.lseek(fd, self.offset, os.SEEK_SET)
                chunk = os.read(fd, min(MAX_READ, info.st_size - self.offset))
                if not chunk:
                    break
                self.offset += len(chunk)
                text = self.carry + self.decoder.decode(chunk)
                pieces = text.split("\n")
                partial = pieces.pop()
                if any(self.regex.search(piece) for piece in pieces) or (partial and self.regex.search(partial)):
                    return True
                self.carry = partial[-MAX_CARRY:]
        except OSError:
            return False
        finally:
            os.close(fd)
        return False


def tail_lines(path: str, count: int) -> List[str]:
    """The last count lines of the file, from its last 64 KiB."""
    if count <= 0:
        return []
    data = b""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return []
    try:
        if stat.S_ISREG(os.fstat(fd).st_mode):
            size = os.fstat(fd).st_size
            os.lseek(fd, max(0, size - TAIL_BYTES), os.SEEK_SET)
            data = os.read(fd, TAIL_BYTES)
    except OSError:
        return []
    finally:
        os.close(fd)
    return data.decode("utf-8", "replace").splitlines()[-count:]


# MARK: - Command line


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wait", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pid", type=int, action="append", default=[], metavar="N")
    parser.add_argument("--job", action="append", default=[], metavar="ID")
    parser.add_argument("--until", action="append", default=[], metavar="CMD")
    parser.add_argument("--check-timeout", type=float, default=DEFAULT_CHECK_TIMEOUT, metavar="S",
                        help="longest one --until run may take (default 60)")
    parser.add_argument("--file", action="append", default=[], metavar="PATH")
    parser.add_argument("--changed", action="store_true", help="with --file: wait for a change, not for readiness")
    parser.add_argument("--gone", action="append", default=[], metavar="PATH")
    parser.add_argument("--log", action="append", default=[], metavar="FILE")
    parser.add_argument("--match", action="append", default=[], metavar="REGEX")
    parser.add_argument("--from-end", action="store_true", help="with --log: ignore the lines already there")
    parser.add_argument("--tail", type=int, default=5, metavar="N", help="lines of a log to print (default 5)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="S")
    parser.add_argument("--every", type=float, default=DEFAULT_EVERY, metavar="S", help="longest pause between checks")
    parser.add_argument("--stop-on-timeout", action="store_true", help="with --run or --job: stop the job on a timeout")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", dest="any", action="store_false", help="every condition must hold (default)")
    mode.add_argument("--any", dest="any", action="store_true", help="the first condition that holds ends the wait")
    parser.add_argument("--run", action="store_true", help="start the command after `--` as a job and wait for it")
    parser.add_argument("--jobs", action="store_true", help="list jobs")
    parser.add_argument("--stop", metavar="ID", help="stop a running job")
    parser.add_argument("--_supervise", metavar="DIR", help=argparse.SUPPRESS)
    parser.set_defaults(any=False)
    return parser


def split_run_command(argv: List[str]) -> Tuple[List[str], List[str]]:
    """Split argv at the first `--`: the words before it are options, the words after it are the --run command."""
    if "--" not in argv:
        return argv, []
    index = argv.index("--")
    return argv[:index], argv[index + 1 :]


def main(argv: Optional[List[str]] = None) -> int:
    options, command = split_run_command(list(sys.argv[1:] if argv is None else argv))
    parser = build_parser()
    args = parser.parse_args(options)
    if args._supervise:
        return supervise(args._supervise, command)
    try:
        if args.jobs:
            return list_jobs()
        if args.stop:
            return stop_job(args.stop)
        return wait(args, command, parser)
    except UsageError as error:
        print(f"wait: {error}", file=sys.stderr)
        return 2


def wait(args: argparse.Namespace, command: List[str], parser: argparse.ArgumentParser) -> int:
    if args.run and not command:
        parser.error("--run needs a command after `--`")
    if command and not args.run:
        parser.error("words after `--` need --run")
    if len(args.log) != len(args.match):
        parser.error("give one --match for each --log")
    if args.every <= 0 or args.timeout < 0 or args.check_timeout <= 0:
        parser.error("--every and --check-timeout must be above 0, and --timeout must not be negative")
    if any(pid <= 0 for pid in args.pid):
        parser.error("a process id must be above 0")
    count = len(args.pid) + len(args.job) + len(args.until) + len(args.file) + len(args.gone) + len(args.log)
    if count + (1 if args.run else 0) == 0:
        parser.error("give at least one condition")
    if count > MAX_TARGETS:
        parser.error(f"name at most {MAX_TARGETS} conditions")
    if args.run and resolve_program(command[0]) is None:
        print(f"wait: cannot start {command[0]}: not found", file=sys.stderr)
        return 127

    started = time.monotonic()
    deadline = started + args.timeout if args.timeout else None

    def remaining() -> Optional[float]:
        return None if deadline is None else deadline - time.monotonic()

    try:
        conditions = [pid_condition(pid) for pid in args.pid]
        conditions += [until_condition(text, args.check_timeout, remaining) for text in args.until]
        conditions += [file_condition(path, args.changed) for path in args.file]
        conditions += [gone_condition(path) for path in args.gone]
        logs = list(zip(args.log, args.match))
        conditions += [Condition(f"{path} matched /{pattern}/", LogWatch(path, re.compile(pattern), args.from_end).poll)
                       for path, pattern in logs]
    except re.error as error:
        parser.error(f"--match: {error}")

    jobs: List[JobWait] = []
    for job_id in args.job:
        directory = job_directory(job_id)
        jobs.append(JobWait(job_id, directory))
    if args.run:
        job_id, directory = start_job(command)
        print(f"wait: started job {job_id}; if this call ends first, continue with: wait --job {job_id}",
              file=sys.stderr, flush=True)
        jobs.append(JobWait(job_id, directory))
    conditions += [job.condition for job in jobs]

    interrupted = {"signal": 0}

    def on_signal(number: int, _frame: object) -> None:
        interrupted["signal"] = number

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    ended, status = "", 0
    pause = FIRST_PAUSE
    while True:
        for condition in conditions:
            condition.update()
        failed = [job for job in jobs if job.status not in (None, 0)]
        done = [c for c in conditions if c.held]
        if failed:
            job = failed[0]
            ended, status = f"job {job.job_id} exited with status {job.status}", int(job.status or 1)
            break
        if (args.any and done) or len(done) == len(conditions):
            ended = "; ".join(c.label for c in (done[:1] if args.any else done))
            if len(conditions) == 1 and args.file:
                number = status_in(args.file[0])
                status = number if number is not None else 0
            break
        if interrupted["signal"]:
            ended, status = "interrupted", 130
            break
        now = time.monotonic()
        if deadline is not None and now >= deadline:
            waiting = "; ".join(c.label for c in conditions if not c.held)
            ended, status = f"timeout (124); still waiting for: {waiting}", 124
            break
        time.sleep(max(0.01, min(pause, deadline - now if deadline is not None else pause)))
        pause = min(pause * 1.5, args.every)

    for job in jobs:
        if job.status is None:
            if status == 124 and args.stop_on_timeout:
                stop_job(job.job_id)
            else:
                ended += f"; job {job.job_id} still runs: continue with `wait --job {job.job_id}`"
        elif job.follow.copied == 0 and job.follow.offset == 0:
            for line in tail_lines(job.follow.path, args.tail):
                print(line)
    for path, _ in logs:
        for line in tail_lines(path, args.tail):
            print(line)
    print(f"wait: {ended} after {time.monotonic() - started:.1f}s", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())

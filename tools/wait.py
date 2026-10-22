#!/usr/bin/env python3
"""Block until a stated condition holds.

`wait` keeps no state: no database, no queue, no daemon. It does not start work on its own and does not limit other
work. It checks each condition every --every seconds and ends when the conditions hold or the time runs out.

Conditions (each may be given more than once):
  --pid N            process N has exited.
  --run -- CMD...    start CMD (an argument list, no shell), wait for it to exit, and exit with its status.
                     It must be the last option: every word after `--` belongs to CMD.
  --until "CMD"      run CMD (split into words, no shell) every --every seconds; it holds when CMD exits 0.
  --file PATH        PATH is a regular file with a size above 0 (a file that was just created and is still empty
                     is not ready). With --changed: ready, and its mtime or size differs from the start.
                     When PATH is the only condition and holds a number (as `echo $? > PATH` writes it), that
                     number is the exit status.
  --gone PATH        PATH does not exist.
  --log FILE --match REGEX
                     a line of FILE matches REGEX (Python syntax). The lines FILE already holds count; with
                     --from-end only the lines written after the start count. The unfinished last line counts too.
                     On a match or a timeout the last --tail lines (default 5) of FILE go to standard output.

A condition that holds stays held. By default every condition must hold (--all); --any ends at the first one.

Exit status: 0 when the conditions hold; 124 on timeout (--timeout, default 570 seconds, 0 means no limit; after
124 run the same command again to keep waiting); the status of CMD for --run when it is the only condition (128 + N
after signal N); the number in the status file for --file (see above); 130 when interrupted; 2 for a usage error;
126 when CMD cannot be executed; 127 when CMD is not found. The last line on standard error says which condition
ended the wait, which were still pending on a timeout, and how long it took.

A process that another user owns cannot be probed, so --pid treats it as running while the probe is refused. A
zombie counts as exited.

Examples:
  wait --pid 4242 --timeout 300
  wait --until "test -f build/done.flag" --every 2
  wait --log build.log --match 'BUILD (SUCCEEDED|FAILED)' --timeout 1200
  wait --run -- swift test
"""

from __future__ import annotations

import argparse
import codecs
import errno
import os
import re
import shlex
import signal
import stat
import subprocess
import sys
import time
from typing import Callable, List, Optional, Tuple

DEFAULT_TIMEOUT = 570.0
DEFAULT_EVERY = 0.5
FIRST_PAUSE = 0.05
KILL_GRACE = 5.0
MAX_TARGETS = 256
MAX_READ = 16 * 1024 * 1024
MAX_CARRY = 64 * 1024
STATUS_BYTES = 4096
TAIL_BYTES = 64 * 1024


class Condition:
    """One thing to wait for. `poll` returns True once it holds, and the condition then stays held."""

    def __init__(self, label: str, poll: Callable[[], bool], detail: Optional[Callable[[], str]] = None) -> None:
        self.label = label
        self._poll = poll
        self.held = False
        self.detail = detail

    def update(self) -> bool:
        if not self.held and self._poll():
            self.held = True
        return self.held


def is_zombie(pid: int) -> bool:
    try:
        result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.stdout.strip().startswith("Z")


def pid_alive(pid: int) -> bool:
    """True while the process runs. A zombie has exited. A refused probe (another user's process) counts as running."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return not is_zombie(pid)


def reap(pid: int) -> None:
    """Collect pid when it is our child, so that an exited child does not stay a zombie."""
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass


def pid_condition(pid: int) -> Condition:
    def poll() -> bool:
        reap(pid)
        return not pid_alive(pid)

    return Condition(f"pid {pid} exited", poll)


def file_signature(path: str) -> Optional[Tuple[int, int]]:
    """(mtime, size) of a regular file with a size above 0; None for anything else."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    if not stat.S_ISREG(st.st_mode) or st.st_size == 0:
        return None
    return (st.st_mtime_ns, st.st_size)


def file_condition(path: str, changed: bool) -> Condition:
    start = file_signature(path)

    def poll() -> bool:
        now = file_signature(path)
        if now is None:
            return False
        return now != start if changed and start is not None else True

    return Condition(f"{path} {'changed' if changed and start is not None else 'is ready'}", poll)


def status_in(path: str) -> Optional[int]:
    """The number a status file holds, spaces and newlines aside, as `echo $? > FILE` writes it; None for other text.
    The file is opened without blocking and must be a regular file."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        data = os.read(fd, STATUS_BYTES)
    except OSError:
        return None
    finally:
        os.close(fd)
    digits = data.replace(b" ", b"").replace(b"\n", b"")
    if not digits or not digits.isdigit() or len(digits) >= 12:
        return None
    number = int(digits)
    return number if number < 2**31 else number % 256


def gone_condition(path: str) -> Condition:
    return Condition(f"{path} is gone", lambda: not os.path.lexists(path))


def until_condition(command: str) -> Condition:
    argv = shlex.split(command)
    if not argv:
        raise ValueError("--until needs a command")

    def poll() -> bool:
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return False
        return result.returncode == 0

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
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                return False
            if st.st_size < self.offset:
                self.offset, self.carry = 0, ""
                self.decoder.reset()
            while self.offset < st.st_size:
                os.lseek(fd, self.offset, os.SEEK_SET)
                chunk = os.read(fd, min(MAX_READ, st.st_size - self.offset))
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


def log_condition(path: str, pattern: str, from_end: bool) -> Tuple[Condition, str]:
    watch = LogWatch(path, re.compile(pattern), from_end)
    return Condition(f"{path} matched /{pattern}/", watch.poll), path


def tail_lines(path: str, count: int) -> List[str]:
    """The last count lines of the file, from its last 64 KiB."""
    if count <= 0:
        return []
    try:
        with open(path, "rb") as handle:
            size = os.fstat(handle.fileno()).st_size
            handle.seek(max(0, size - TAIL_BYTES))
            data = handle.read(TAIL_BYTES)
    except OSError:
        return []
    lines = data.decode("utf-8", "replace").splitlines()
    return lines[-count:]


class Run:
    """A child process started by --run, in its own process group so that a stop reaches its children too."""

    def __init__(self, argv: List[str]) -> None:
        self.argv = argv
        self.process = subprocess.Popen(argv, start_new_session=True)
        self.status: Optional[int] = None
        self.condition = Condition(f"`{shlex.join(argv)}` exited", self._poll)

    def _poll(self) -> bool:
        code = self.process.poll()
        if code is None:
            return False
        self.status = 128 - code if code < 0 else code
        return True

    def _signal_group(self, number: int) -> None:
        try:
            os.killpg(self.process.pid, number)
        except OSError:
            pass

    def stop(self) -> None:
        if self.process.poll() is not None:
            self._signal_group(signal.SIGKILL)
            return
        self._signal_group(signal.SIGTERM)
        try:
            self.process.wait(KILL_GRACE)
        except subprocess.TimeoutExpired:
            pass
        self._signal_group(signal.SIGKILL)
        self.process.wait()


def start_error_status(error: OSError) -> int:
    return 126 if error.errno in (errno.EACCES, errno.EPERM, errno.ENOEXEC, errno.EISDIR) else 127


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wait", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pid", type=int, action="append", default=[], metavar="N")
    parser.add_argument("--until", action="append", default=[], metavar="CMD")
    parser.add_argument("--file", action="append", default=[], metavar="PATH")
    parser.add_argument("--changed", action="store_true", help="with --file: wait for a change, not for readiness")
    parser.add_argument("--gone", action="append", default=[], metavar="PATH")
    parser.add_argument("--log", action="append", default=[], metavar="FILE")
    parser.add_argument("--match", action="append", default=[], metavar="REGEX")
    parser.add_argument("--from-end", action="store_true", help="with --log: ignore the lines already there")
    parser.add_argument("--tail", type=int, default=5, metavar="N", help="lines of a log to print (default 5)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="S")
    parser.add_argument("--every", type=float, default=DEFAULT_EVERY, metavar="S", help="longest pause between checks")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", dest="any", action="store_false", help="every condition must hold (default)")
    mode.add_argument("--any", dest="any", action="store_true", help="the first condition that holds ends the wait")
    parser.add_argument("--run", action="store_true", help="start the command after `--` and wait for it")
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
    if args.run and not command:
        parser.error("--run needs a command after `--`")
    if command and not args.run:
        parser.error("words after `--` need --run")
    if len(args.log) != len(args.match):
        parser.error("give one --match for each --log")
    if args.every <= 0 or args.timeout < 0:
        parser.error("--every must be above 0 and --timeout must not be negative")
    if any(pid <= 0 for pid in args.pid):
        parser.error("a process id must be above 0")
    if len(args.pid) + len(args.until) + len(args.file) + len(args.gone) + len(args.log) > MAX_TARGETS:
        parser.error(f"name at most {MAX_TARGETS} conditions")

    logs: List[str] = []
    try:
        conditions = [pid_condition(pid) for pid in args.pid]
        conditions += [until_condition(text) for text in args.until]
        conditions += [file_condition(path, args.changed) for path in args.file]
        conditions += [gone_condition(path) for path in args.gone]
        for path, pattern in zip(args.log, args.match):
            condition, log_path = log_condition(path, pattern, args.from_end)
            conditions.append(condition)
            logs.append(log_path)
    except (ValueError, re.error) as error:
        parser.error(str(error))

    run: Optional[Run] = None
    if args.run:
        try:
            run = Run(command)
        except OSError as error:
            print(f"wait: cannot start {command[0]}: {error.strerror or error}", file=sys.stderr)
            return start_error_status(error)
        conditions.append(run.condition)
    if not conditions:
        parser.error("give at least one condition")

    started = time.monotonic()
    deadline = started + args.timeout if args.timeout else None
    interrupted = {"signal": 0}

    def on_signal(number: int, _frame: object) -> None:
        interrupted["signal"] = number

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    ended = ""
    status = 0
    pause = FIRST_PAUSE
    while True:
        for condition in conditions:
            condition.update()
        done = [c for c in conditions if c.held]
        if (args.any and done) or len(done) == len(conditions):
            ended = "; ".join(c.label for c in (done[:1] if args.any else done))
            if len(conditions) == 1 and run is not None:
                status = run.status or 0
            elif len(conditions) == 1 and args.file:
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

    if run is not None:
        run.stop()
    for path in logs:
        for line in tail_lines(path, args.tail):
            print(line)
    print(f"wait: {ended} after {time.monotonic() - started:.1f}s", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())

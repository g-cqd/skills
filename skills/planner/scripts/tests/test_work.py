"""Tests for scripts/work.py: scopes, the queue and its order, claims under real concurrency, claim then accept, jobs
with their true statuses, capacity, waiting, and status with its sweep. Each test has its own AGENT_WORK_HOME.
Run: python3 -m unittest discover -s scripts/tests"""

import contextlib
import io
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from collections import Counter, namedtuple

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)

import order_tasks  # noqa: E402
import work  # noqa: E402

SCRIPT = os.path.join(SCRIPTS, "work.py")
Result = namedtuple("Result", "status out err seconds")

# One worker process of the concurrency tests. It calls work.main in a loop, in its own process, and prints what it
# got as JSON. It says it is ready, then starts only when the go file appears, so that every worker contends at once.
WORKER = r"""
import contextlib, io, json, os, sys, time
sys.path.insert(0, sys.argv[1])
import work

mode, agent, go = sys.argv[2], sys.argv[3], sys.argv[4]
open(go + "-" + agent, "w").close()
while not os.path.exists(go):
    time.sleep(0.001)


def call(*arguments):
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = work.main(list(arguments))
    return status, output.getvalue(), errors.getvalue()


results = []
if mode == "next":
    while True:
        status, output, errors = call("next", "--agent", agent, "--json")
        if status != 0:
            # The last attempt must be a clean "nothing to claim", not a database error.
            results.append(errors or json.loads(output)["reason"])
            break
        results.append(json.loads(output)["claimed"]["id"])
elif mode == "claim":
    status, _, errors = call("claim", sys.argv[5], "--agent", agent)
    results.append([status, errors])
else:
    for index in range(int(sys.argv[5])):
        results.append(call("add", "--id", agent + "-" + str(index), "--agent", agent)[0])
print(json.dumps(results))
"""


class WorkTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.directory.name)
        self.home = os.path.join(self.root, "state")
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("WORK_")}
        self.env["AGENT_WORK_HOME"] = self.home
        # A fixed capacity and a load limit no machine reaches keep the tests independent of the machine's load.
        self.assertEqual(self.call("settings", "--capacity", "16", "--load-factor", "1000").status, 0)

    def tearDown(self):
        self.stop_jobs()
        self.directory.cleanup()

    def work(self, *arguments, agent=None, env=None, timeout=60):
        """Runs work.py as its own process, as an agent does."""
        environment = dict(self.env, **(env or {}))
        if agent:
            environment["WORK_AGENT"] = agent
        start = time.monotonic()
        result = subprocess.run([sys.executable, SCRIPT, *arguments], cwd=self.project, env=environment,
                                capture_output=True, text=True, timeout=timeout)
        return Result(result.returncode, result.stdout, result.stderr, time.monotonic() - start)

    def call(self, *arguments, agent=None):
        """Runs work.main in this process: quicker, for setting up many tasks."""
        environment = dict(self.env, **({"WORK_AGENT": agent} if agent else {}))
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                status = work.main(list(arguments), environ=environment)
            except SystemExit as exit:
                status = exit.code
        return Result(status, output.getvalue(), errors.getvalue(), 0.0)

    def start(self, *arguments, agent, env=None):
        """Starts work.py in the background, for a command that blocks while the test goes on."""
        environment = dict(self.env, WORK_AGENT=agent, **(env or {}))
        return subprocess.Popen([sys.executable, SCRIPT, *arguments], cwd=self.project, env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def gate(self, name, status=0):
        """A command that runs until the test opens its gate with `open_gate(name)`, then exits with `status`: a job
        that lasts exactly as long as the test needs, with no sleep to tune."""
        return ["sh", "-c", f"while [ ! -e '{self.root}/{name}' ]; do sleep 0.02; done; exit {status}"]

    def open_gate(self, name):
        open(os.path.join(self.root, name), "w").close()

    def state(self, task_id):
        rows = self.database("SELECT state, requested, note FROM tasks WHERE id = ?", task_id)
        if not rows:
            return None
        row = rows[0]
        return "waiting" if row["state"] == "claimed" and row["requested"] and row["note"] else row["state"]

    def json(self, *arguments, **options):
        result = self.work(*arguments, "--json", **options)
        return result.status, json.loads(result.out)

    def task(self, task_id):
        return self.json("show", task_id)[1]

    def accept(self, task_id, agent):
        """Reads a task's command as its claimant does, then accepts it with the digest that show printed."""
        return self.work("accept", task_id, "--digest", self.task(task_id)["digest"], agent=agent)

    def database(self, query, *parameters):
        with contextlib.closing(sqlite3.connect(os.path.join(self.home, "work.db"), timeout=30)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, parameters).fetchall()
            conn.commit()
            return rows

    def until(self, predicate, message, timeout=10.0):
        """Waits for a condition, checking it every 20 ms; fails the test at the limit."""
        deadline = time.monotonic() + timeout
        while True:
            value = predicate()
            if value:
                return value
            if time.monotonic() >= deadline:
                self.fail(f"timed out waiting for {message}")
            time.sleep(0.02)

    def stop_jobs(self):
        """Kills what a test left running: each job's process group, then its supervisor."""
        if not os.path.exists(os.path.join(self.home, "work.db")):
            return
        # A test that plays the supervisor in this process leaves its own pid as an owner: that one is left alone.
        rows = self.database("SELECT pid, owner FROM tasks WHERE state IN ('claimed', 'running')")
        for row in rows:
            for target, kill in ((row["pid"], os.killpg), (row["owner"], os.kill)):
                if target and target != os.getpid():
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        kill(target, signal.SIGKILL)
        for row in rows:
            if row["owner"] and row["owner"] != os.getpid():
                self.until(lambda: not work.exists(row["owner"]), "a supervisor to stop")

    def race(self, mode, agents, *extra):
        """Starts one worker process per agent, releases them together, and returns what each one got."""
        go = os.path.join(self.root, f"go-{mode}-{time.monotonic_ns()}")
        workers = {agent: subprocess.Popen([sys.executable, "-c", WORKER, SCRIPTS, mode, agent, go, *extra],
                                           env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                   for agent in agents}
        self.until(lambda: all(os.path.exists(f"{go}-{agent}") for agent in agents), "the workers to start")
        open(go, "w").close()
        results = {}
        for agent, process in workers.items():
            output, errors = process.communicate(timeout=120)
            self.assertEqual(process.returncode, 0, errors)
            results[agent] = json.loads(output)
        return results


class ScopeTests(WorkTestCase):
    def test_scope_set_and_show_with_a_parent(self):
        self.assertEqual(self.work("scope", "set", "proj", "--kind", "project", "--task", "Ship it").status, 0)
        self.work("scope", "set", "conv", "--kind", "conversation", "--parent", "proj", "--task", "Status")
        self.work("scope", "set", "impl", "--parent", "conv", agent="impl")
        status, shown = self.json("scope", "show", "conv")
        self.assertEqual(status, 0)
        self.assertEqual(shown["lineage"], ["proj", "conv"])
        self.assertEqual([(scope["id"], scope["kind"], scope["parent"], scope["task"]) for scope in shown["scopes"]],
                         [("conv", "conversation", "proj", "Status"), ("impl", "agent", "conv", "")])
        # An update changes only what it names.
        self.work("scope", "set", "conv", "--task", "Tests")
        scope = self.json("scope", "show", "conv")[1]["scopes"][0]
        self.assertEqual((scope["kind"], scope["parent"], scope["task"]), ("conversation", "proj", "Tests"))
        self.assertEqual(self.work("scope", "show").out.splitlines(),
                         ["proj (project): Ship it", "  conv (conversation): Tests", "    impl (agent)"])

    def test_a_cycle_an_unknown_parent_or_an_unknown_scope_is_refused(self):
        self.work("scope", "set", "proj")
        self.work("scope", "set", "conv", "--parent", "proj")
        for arguments in (("scope", "set", "proj", "--parent", "conv"), ("scope", "set", "proj", "--parent", "proj"),
                          ("scope", "set", "x", "--parent", "ghost"), ("scope", "set", "../x"),
                          ("add", "--scope", "ghost"), ("order", "--scope", "ghost")):
            with self.subTest(arguments=arguments):
                result = self.work(*arguments, agent="alice")
                self.assertEqual(result.status, 2, result.err)
        self.assertIsNone(self.json("scope", "show", "proj")[1]["scopes"][0]["parent"])


class OrderTests(WorkTestCase):
    def test_add_then_order_follows_the_order_tasks_rules(self):
        specs = ["id=old,kind=performance", "id=docs,kind=docs", "id=refactor,kind=structure",
                 "id=fix,kind=validity,after=refactor", "id=crash,kind=crash"]
        for spec in specs:
            fields = order_tasks.parse_spec(spec)
            after = ["--after", fields["after"]] if "after" in fields else []
            added = self.work("add", "--id", fields["id"], "--kind", fields["kind"], *after, agent="a")
            self.assertEqual(added.status, 0)
        status, result = self.json("order")
        order = [row["id"] for row in result["order"]]
        self.assertEqual(order, order_tasks.order(order_tasks.Graph(order_tasks.load_tasks([], specs))))
        self.assertEqual(order, ["refactor", "fix", "crash", "old", "docs"])
        self.assertEqual({row["id"]: row["moved_up_for"] for row in result["order"]}["refactor"], "fix")
        self.assertEqual(self.work("order").out.splitlines()[0], "1. refactor (structure; moved up for fix)")

    def test_order_counts_only_queued_tasks_and_names_what_a_task_waits_for(self):
        self.work("scope", "set", "proj")
        self.work("scope", "set", "other")
        for task_id in ("base", "left", "right"):
            self.work("add", "--id", task_id, "--scope", "proj", agent="a")
        self.work("add", "--id", "top", "--after", "base", "left", "--scope", "proj", agent="a")
        self.work("add", "--id", "elsewhere", "--scope", "other", agent="a")
        self.work("claim", "base", agent="a")
        self.work("done", "base", agent="a")
        self.work("claim", "left", agent="b")
        order = self.json("order", env={"WORK_SCOPE": "proj"})[1]["order"]
        self.assertEqual([row["id"] for row in order], ["right", "top"])
        self.assertEqual(order[1]["waits_for"], [{"id": "left", "state": "claimed"}])
        self.assertFalse(order[1]["ready"])
        everywhere = self.json("order", "--scope", "", env={"WORK_SCOPE": "proj"})[1]["order"]
        self.assertEqual([row["id"] for row in everywhere], ["right", "top", "elsewhere"])

    def test_plan_schedules_the_queue_for_several_agents(self):
        self.work("add", "--id", "a", "--size", "2", "--files", "src/app", agent="x")
        self.work("add", "--id", "b", "--files", "src/app/view.swift", agent="x")
        self.work("add", "--id", "c", agent="x")
        status, plan = self.json("plan", "--agents", "2")
        self.assertEqual(status, 0)
        starts = {step["id"]: step["start"] for lane in plan["lanes"] for step in lane}
        self.assertEqual(starts, {"a": 0, "c": 0, "b": 2})
        self.assertIn("makespan 3", self.work("plan", "--agents", "2").out)


class ClaimTests(WorkTestCase):
    def test_processes_claiming_at_once_never_take_the_same_task(self):
        agents = [f"agent{number}" for number in range(6)]
        for round_number in range(3):
            ids = [f"r{round_number}-t{index}" for index in range(40)]
            for task_id in ids:
                self.assertEqual(self.call("add", "--id", task_id, agent="author").status, 0)
            results = self.race("next", agents)
            self.assertEqual({got[-1] for got in results.values()}, {"nothing is queued"})
            taken = [task_id for got in results.values() for task_id in got[:-1]]
            self.assertEqual(sorted(taken), sorted(ids), "each task is claimed exactly once")
        claims = Counter(row["task"] for row in self.database("SELECT task FROM events WHERE what = 'claimed'"))
        self.assertEqual(set(claims.values()), {1})
        for round_number in range(5):
            self.call("add", "--id", f"prize-{round_number}", agent="author")
            attempts = [got[0] for got in self.race("claim", agents, f"prize-{round_number}").values()]
            self.assertEqual(sorted(status for status, _ in attempts), [0] + [1] * 5)
            for status, errors in attempts:
                self.assertTrue(status == 0 or f"prize-{round_number} is claimed by" in errors, errors)

    def test_next_skips_a_task_whose_files_overlap_a_running_one(self):
        self.work("add", "--id", "edit-app", "--files", "src/app", "--", "sleep", "30", agent="alice")
        self.work("add", "--id", "edit-view", "--files", "src/app/view.swift", agent="alice")
        self.work("add", "--id", "docs", "--files", "docs", agent="alice")
        self.assertEqual(self.json("next", agent="alice")[1]["claimed"]["id"], "edit-app")
        self.assertEqual(self.accept("edit-app", "alice").status, 0)
        self.assertEqual(self.work("run", "edit-app", "--timeout", "0", agent="alice").status, 124)
        self.until(lambda: self.task("edit-app")["state"] == "running", "the job to start")
        self.assertEqual(self.json("next", agent="bob")[1]["claimed"]["id"], "docs")
        status, nothing = self.json("next", agent="carol")
        self.assertEqual(status, 1)
        self.assertIsNone(nothing["claimed"])
        self.assertIn("1 change files", nothing["reason"])
        refused = self.work("claim", "edit-view", agent="carol")
        self.assertEqual(refused.status, 1)
        self.assertIn("edit-app", refused.err)
        # Once the job ends, its files are free.
        os.killpg(self.task("edit-app")["pid"], signal.SIGTERM)
        self.assertEqual(self.work("wait", "edit-app").status, 128 + signal.SIGTERM)
        self.assertEqual(self.json("next", agent="carol")[1]["claimed"]["id"], "edit-view")

    def test_claim_refuses_a_task_whose_prerequisites_are_not_done(self):
        self.work("add", "--id", "first", agent="a")
        self.work("add", "--id", "second", "--after", "first", agent="a")
        refused = self.work("claim", "second", agent="b")
        self.assertEqual(refused.status, 1)
        self.assertIn("first (queued)", refused.err)
        self.assertEqual(self.json("next", agent="b")[1]["claimed"]["id"], "first")
        self.assertEqual(self.work("claim", "first", agent="c").status, 1)
        self.work("done", "first", agent="b")
        self.assertEqual(self.work("claim", "second", agent="c").status, 0)


class AcceptTests(WorkTestCase):
    def test_another_agents_command_runs_only_after_accept(self):
        marker = os.path.join(self.root, "marker")
        self.work("add", "--id", "touch", "--", "touch", marker, agent="bob")
        self.work("claim", "touch", agent="alice")
        refused = self.work("run", "touch", agent="alice")
        self.assertEqual(refused.status, 1)
        self.assertIn("work show touch", refused.err)
        self.assertFalse(os.path.exists(marker), "nothing runs before it is accepted")
        shown = self.task("touch")
        self.assertEqual((shown["author"], shown["agent"], shown["command"]), ("bob", "alice", ["touch", marker]))
        self.assertTrue(shown["needs_acceptance"])
        self.assertIn(f"acceptance: needed from alice; if the command is right, run "
                      f"`work accept touch --digest {shown['digest']}`", self.work("show", "touch").out)
        for intruder in ("carol", "bob"):
            self.assertEqual(self.accept("touch", intruder).status, 1, "only the claimant accepts")
        self.assertEqual(self.work("accept", "touch", agent="alice").status, 2, "the digest is required")
        accepted = self.accept("touch", "alice")
        self.assertEqual(accepted.status, 0, accepted.err)
        self.assertIn("accepted the command of task touch, queued by bob (2 arguments", accepted.out)
        self.assertEqual(self.work("run", "touch", agent="bob").status, 1, "only the claimant runs it")
        self.assertEqual(self.work("run", "touch", agent="alice").status, 0)
        self.assertTrue(os.path.exists(marker))
        self.assertEqual(self.task("touch")["accepted_by"], "alice")

    def test_a_command_queued_under_ones_own_name_still_needs_acceptance(self):
        # Names are self-declared, and a subagent inherits its parent's: a command queued under "alice" may come from
        # a subagent that alice never read.
        marker = os.path.join(self.root, "mine")
        self.work("add", "--id", "mine", "--", "touch", marker, agent="alice")
        self.work("claim", "mine", agent="alice")
        self.assertTrue(self.task("mine")["needs_acceptance"])
        self.assertEqual(self.work("run", "mine", agent="alice").status, 1)
        self.assertFalse(os.path.exists(marker))
        self.assertEqual(self.accept("mine", "alice").status, 0)
        self.assertEqual(self.work("run", "mine", agent="alice").status, 0)
        self.assertTrue(os.path.exists(marker))

    def test_a_command_typed_inline_needs_no_acceptance(self):
        marker = os.path.join(self.root, "inline")
        self.assertEqual(self.work("run", "--id", "inline", "--", "touch", marker, agent="alice").status, 0)
        self.assertTrue(os.path.exists(marker))
        self.assertEqual(self.task("inline")["accepted_by"], "alice")

    def test_the_digest_binds_the_command_and_its_directory(self):
        other = os.path.join(self.root, "other")
        os.makedirs(other)
        self.work("add", "--id", "here", "--", "make", "clean", agent="bob")
        self.work("add", "--id", "there", "--cwd", other, "--", "make", "clean", agent="bob")
        here, there = self.task("here"), self.task("there")
        self.assertEqual(here["command"], there["command"])
        self.assertNotEqual(here["digest"], there["digest"], "the same command in another directory differs")
        self.work("claim", "here", agent="alice")
        refused = self.work("accept", "here", "--digest", there["digest"], agent="alice")
        self.assertEqual(refused.status, 1)
        self.assertIn("does not match", refused.err)
        self.assertEqual(self.work("accept", "here", "--digest", here["digest"].upper(), agent="alice").status, 0)

    def test_show_puts_the_command_first_and_caps_long_lists(self):
        files = [f"src/{'deep/' * 30}file{index}.swift" for index in range(1000)]
        self.work("add", "--id", "wide", "--title", "t" * 1000, "--files", *files, "--", "rm", "-rf", "build",
                  agent="bob")
        shown = self.work("show", "wide").out.splitlines()
        self.assertEqual(shown[:2], ["command of task wide (3 arguments, 12 bytes), queued by bob:", "  rm -rf build"])
        self.assertTrue(shown[3].startswith("digest: "))
        listed = next(line for line in shown if line.startswith("files"))
        self.assertTrue(listed.startswith("files (the first 10 of 1000; all of them with --json): "))
        self.assertLess(sum(len(line) for line in shown), 6000, "the text view stays short")
        self.assertEqual(len(self.task("wide")["files"]), 1000)


class RunTests(WorkTestCase):
    def test_run_records_the_true_exit_status(self):
        script = os.path.join(self.root, "not-executable")
        open(script, "w").close()
        cases = [(["true"], 0, "done"), (["sh", "-c", "exit 3"], 3, "failed"),
                 (["no-such-command-anywhere"], 127, "failed"), ([script], 126, "failed"),
                 (["sh", "-c", "kill -TERM $$"], 128 + signal.SIGTERM, "failed")]
        for index, (command, expected, state) in enumerate(cases):
            with self.subTest(command=command):
                result = self.work("run", "--id", f"job{index}", "--", *command, agent="alice")
                self.assertEqual(result.status, expected, result.err)
                self.assertIn(f"finished with status {expected}", result.out)
                task = self.task(f"job{index}")
                self.assertEqual((task["state"], task["status"]), (state, expected))

    def test_a_large_output_reaches_the_log_whole(self):
        script = "i=0; while [ $i -lt 16384 ]; do echo out-$i; echo err-$i >&2; i=$((i+1)); done; exit 7"
        result = self.work("run", "--id", "big", "--tail", "1", "--", "sh", "-c", script, agent="alice")
        self.assertEqual(result.status, 7)
        with open(self.task("big")["log"]) as handle:
            lines = handle.read().splitlines()
        self.assertEqual(len(lines), 2 * 16384)
        self.assertIn("out-16383", lines)
        self.assertIn("err-16383", lines)

    def test_run_returns_as_soon_as_the_job_ends(self):
        result = self.work("run", "--", "sh", "-c", "echo working; sleep 1; exit 4", agent="alice")
        self.assertEqual(result.status, 4)
        self.assertIn("working", result.out)
        self.assertGreaterEqual(result.seconds, 1.0)
        self.assertLess(result.seconds, 3.5, "it waited past the job's end")

    def test_a_timeout_returns_124_while_the_job_runs_on_and_wait_returns_its_status(self):
        result = self.work("run", "--id", "slow", "--timeout", "0.5", "--", *self.gate("slow", status=5),
                           agent="alice")
        self.assertEqual(result.status, 124)
        self.assertIn("job slow still running", result.out)
        self.assertIn("work wait slow", result.out)
        self.assertEqual(self.state("slow"), "running")
        self.assertEqual(self.work("wait", "slow", "--timeout", "0.3").status, 124)
        self.open_gate("slow")
        waited = self.work("wait", "slow")
        self.assertEqual(waited.status, 5)
        self.assertIn("job slow finished with status 5", waited.out)

    def test_json_tells_a_timeout_from_a_command_that_exits_with_124(self):
        timed = self.work("run", "--json", "--id", "long", "--timeout", "0", "--", *self.gate("long"), agent="a")
        self.assertEqual((timed.status, json.loads(timed.out)["timed_out"]), (124, True))
        own = self.work("run", "--json", "--", "sh", "-c", "exit 124", agent="a")
        self.assertEqual((own.status, json.loads(own.out)["timed_out"]), (124, False))
        self.open_gate("long")

    def test_a_missing_directory_is_its_own_error(self):
        gone = os.path.join(self.root, "gone")
        os.makedirs(gone)
        self.work("add", "--id", "lost", "--cwd", gone, "--", "true", agent="a")
        self.work("claim", "lost", agent="a")
        self.accept("lost", "a")
        os.rmdir(gone)
        result = self.work("run", "lost", agent="a")
        self.assertEqual(result.status, 1, "not 127: the command was never looked for")
        task = self.task("lost")
        self.assertEqual((task["state"], task["status"], task["note"]),
                         ("failed", None, f"its directory {gone} is gone"))

    def test_a_job_whose_log_passes_the_limit_is_stopped(self):
        self.call("settings", "--log-limit", "65536")
        result = self.work("run", "--id", "noisy", "--timeout", "20", "--", "sh", "-c",
                           "while :; do echo 0123456789; done", agent="a")
        self.assertEqual(result.status, 128 + signal.SIGTERM, result.out)
        task = self.task("noisy")
        self.assertIn("stopped: its log passed the limit of 65536 bytes", task["note"])
        self.assertLess(os.path.getsize(task["log"]), 64 * 1024 * 1024, "stopped within about a second")

    def test_an_ad_hoc_job_keeps_its_fields_and_refuses_held_files(self):
        self.work("scope", "set", "proj")
        result = self.work("run", "--id", "held", "--scope", "proj", "--weight", "2", "--files", "src",
                           "--timeout", "0", "--", "sleep", "30", agent="alice")
        self.assertEqual(result.status, 124)
        task = self.task("held")
        self.assertEqual((task["scope"], task["weight"], task["author"], task["agent"]),
                         ("proj", 2.0, "alice", "alice"))
        self.assertEqual(task["files"], [os.path.join(self.project, "src")])
        refused = self.work("run", "--files", "src/deep", "--", "true", agent="bob")
        self.assertEqual(refused.status, 1)
        self.assertIn("held", refused.err)


class CapacityTests(WorkTestCase):
    def test_with_capacity_one_the_second_job_starts_when_the_first_ends(self):
        self.call("settings", "--capacity", "1")
        self.assertEqual(self.work("run", "--id", "first", "--timeout", "0", "--", *self.gate("first"),
                                   agent="alice").status, 124)
        self.until(lambda: self.state("first") == "running", "the first job to start")
        # The capacity is the database's: an agent's environment cannot raise it for its own jobs.
        second = self.start("run", "--id", "second", "--", "sh", "-c", "echo second", agent="bob",
                            env={"WORK_CAPACITY": "16"})
        self.until(lambda: self.state("second") == "waiting", "the second job to wait")
        self.open_gate("first")
        output, errors = second.communicate(timeout=60)
        self.assertEqual(second.returncode, 0, errors)
        self.assertIn("job second waits for capacity: 1 of 1 cores are taken", output)
        self.assertRegex(output, r"finished with status 0 after [\d.]+ s \(waited [\d.]+ s for capacity, ran")
        times = {row["id"]: row for row in self.database("SELECT id, requested, started, ended FROM tasks")}
        self.assertGreaterEqual(times["second"]["started"], times["first"]["ended"])
        self.assertGreater(self.task("second")["waited"], 0)
        self.assertAlmostEqual(self.task("second")["waited"], times["second"]["started"] - times["second"]["requested"],
                               places=2)

    def queue_behind(self, busy, *jobs, capacity="1"):
        """Sets the capacity, starts a job that holds it until its gate opens, then queues `jobs`, (id, extra
        arguments) pairs, one after the other, each once the one before waits."""
        self.call("settings", "--capacity", capacity)
        self.work("run", "--id", busy[0], *busy[1], "--timeout", "0", "--", *self.gate(busy[0]), agent="a")
        self.until(lambda: self.state(busy[0]) == "running", "the first job to start")
        for task_id, extra in jobs:
            self.work("run", "--id", task_id, *extra, "--timeout", "0", "--", "true", agent="b")
            self.until(lambda: self.state(task_id) == "waiting", f"job {task_id} to wait")

    def started(self):
        return {row["id"]: row["started"] for row in self.database("SELECT id, started FROM tasks")}

    def test_waiting_jobs_start_in_work_order(self):
        self.queue_behind(("busy", []), ("perf", ["--kind", "performance"]), ("fix", ["--kind", "validity"]))
        self.open_gate("busy")
        self.assertEqual(self.work("wait", "busy", "perf", "fix").status, 0)
        started = self.started()
        self.assertLess(started["busy"], started["fix"])
        self.assertLess(started["fix"], started["perf"], "validity work starts first, whatever its arrival")

    def test_waiting_jobs_of_one_tier_start_in_the_order_they_asked(self):
        self.queue_behind(("busy", []), ("zeta", []), ("alpha", []))
        self.open_gate("busy")
        self.assertEqual(self.work("wait", "busy", "zeta", "alpha").status, 0)
        started = self.started()
        self.assertLess(started["zeta"], started["alpha"], "first in, first out, whatever the ids")

    @unittest.skipIf((os.cpu_count() or 1) < 2, "a weight of 2 needs two CPUs")
    def test_the_capacity_counts_the_weights_of_running_jobs(self):
        self.queue_behind(("heavy", ["--weight", "2"]), ("second", ["--weight", "2"]), capacity="3")
        self.assertIn("2 of 3 cores are taken and this job needs 2", self.task("second")["note"])
        self.open_gate("heavy")
        self.assertEqual(self.work("wait", "heavy", "second").status, 0)
        started, ended = self.started(), self.database("SELECT ended FROM tasks WHERE id = 'heavy'")[0]["ended"]
        self.assertGreaterEqual(started["second"], ended)

    def test_outside_load_holds_a_job_back_and_fails_it_after_the_load_wait(self):
        self.call("settings", "--load-factor", "1.5", "--load-wait", "0.5")
        for task_id in ("heavy", "light"):
            self.work("add", "--id", task_id, "--", "true", agent="a")
            self.work("claim", task_id, agent="a")
            self.accept(task_id, "a")
        ctx = work.Context(self.env)
        self.addCleanup(ctx.close)
        busy, idle = os.cpu_count() * 1.5, 0.0
        for task_id, load in (("heavy", busy), ("light", idle)):
            with work.writing(ctx.conn):
                work.reserve(ctx.conn, work.get_task(ctx.conn, task_id), "a", os.getpid(), "unused.log")
            outcome = self.wait_for_capacity(task_id, load)
            if task_id == "heavy":
                self.assertIsNone(outcome)
            else:
                self.assertEqual(outcome["state"], "running")
        heavy = self.task("heavy")
        self.assertEqual((heavy["state"], heavy["started"], heavy["status"]), ("failed", None, None))
        self.assertIn(f"the load average {busy:.2f} is at or above {busy:.2f}", heavy["note"])
        self.assertIn("the longest a job waits on the machine's load", heavy["note"])

    def wait_for_capacity(self, task_id, load):
        """Plays the supervisor of a job this process owns, with a fake load average for the machine's, in a thread
        with its own connection, so that a wait that never ends fails the test instead of hanging it."""
        outcome = []

        def supervise():
            ctx = work.Context(self.env)
            try:
                outcome.append(work.Supervisor(ctx, task_id, load=lambda: load).wait_for_capacity(ctx.conn))
            finally:
                ctx.close()

        thread = threading.Thread(target=supervise, daemon=True)
        thread.start()
        thread.join(timeout=20)
        self.assertFalse(thread.is_alive(), f"the wait of job {task_id} ended")
        return outcome[0]

    def test_admission(self):
        self.assertIsNone(work.admission(2, 3, 6, 1.0, 12.0))
        self.assertEqual(work.admission(2, 5, 6, 1.0, 12.0),
                         ("capacity", "5 of 6 cores are taken and this job needs 2"))
        self.assertIsNone(work.admission(8, 0, 6, 1.0, 12.0), "a job heavier than the capacity runs alone")
        self.assertEqual(work.admission(1, 0, 6, 12.0, 12.0)[0], "load")
        self.assertIsNone(work.admission(1, 0, 6, None, 12.0), "an unknown load does not block")

    def test_settings_hold_the_capacity_and_limits_for_every_agent(self):
        self.assertEqual(self.json("settings")[1]["capacity"], 16)
        cpus = os.cpu_count() or 1
        status, shown = self.json("settings", "--capacity", "auto", "--log-limit", "1024", "--keep-days", "2")
        self.assertEqual(status, 0)
        self.assertEqual((shown["capacity"], shown["capacity_is_default"]), (max(1, cpus - 2), True))
        self.assertEqual((shown["log_limit"], shown["keep_days"], shown["load_limit"]), (1024, 2, cpus * 1000))
        for arguments in (("--capacity", "0"), ("--capacity", "lots"), ("--load-factor", "-1"),
                          ("--load-wait", "nan"), ("--log-limit", "0"), ("--keep-days", "inf")):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.work("settings", *arguments).status, 2)
        self.assertEqual(self.work("add", "--weight", str(cpus + 1), agent="a").status, 2)
        self.assertEqual(self.work("run", "--weight", str(cpus + 1), "--", "true", agent="a").status, 2)


class WaitTests(WorkTestCase):
    def test_wait_any_returns_at_the_first_end_and_all_waits_for_the_scope(self):
        self.work("scope", "set", "proj")
        for task_id, status in (("quick", 2), ("slow", 0)):
            self.work("run", "--id", task_id, "--scope", "proj", "--timeout", "0", "--", *self.gate(task_id, status),
                      agent="a")
        self.open_gate("quick")
        first = self.work("wait", "quick", "slow", "--any")
        self.assertEqual(first.status, 2)
        self.assertIn("job slow still running", first.out)
        self.assertEqual(self.state("slow"), "running")
        every = self.start("wait", "--all", "--scope", "proj", agent="a")
        self.assertEqual(every.stdout.readline(), "work: waiting for slow\n")
        self.open_gate("slow")
        output, _ = every.communicate(timeout=60)
        self.assertEqual(every.returncode, 0, output)
        self.assertIn("job slow finished with status 0", output)
        self.assertNotIn("quick", output, "--all waits for the jobs that run when it starts")
        self.assertEqual(self.work("wait", "--all", "--scope", "proj").out, "work: no job runs in scope proj\n")

    def test_done_fail_and_cancel_close_tasks(self):
        for task_id in ("a", "b", "c"):
            self.work("add", "--id", task_id, agent="x")
        self.work("add", "--id", "d", "--", "true", agent="x")
        self.work("claim", "a", agent="x")
        self.assertEqual(self.work("done", "a", agent="x").status, 0)
        self.assertEqual(self.work("done", "a", agent="x").status, 1, "a task closes once")
        self.assertEqual(self.work("fail", "b", "--note", "flaky", agent="x").status, 0)
        self.assertEqual(self.work("cancel", "c", agent="x").status, 0)
        refused = self.work("done", "d", agent="x")
        self.assertEqual(refused.status, 1)
        self.assertIn("has a command", refused.err)
        self.assertEqual(self.work("cancel", "d", agent="x").status, 0)
        self.assertEqual([self.task(task_id)["state"] for task_id in "abcd"],
                         ["done", "failed", "cancelled", "cancelled"])
        self.assertEqual(self.task("b")["note"], "flaky")
        waited = self.work("wait", "a", "b", "c", "d")
        self.assertEqual(waited.status, 1, "the first task that is not done sets the status")
        self.assertIn("task b failed: flaky", waited.out)

    def test_only_the_claimant_or_the_author_of_an_unclaimed_task_closes_it(self):
        for task_id in ("unclaimed", "held"):
            self.call("add", "--id", task_id, agent="alice")
        self.call("claim", "held", agent="bob")
        for verb in ("done", "fail", "cancel"):
            with self.subTest(verb=verb):
                refused = self.call(verb, "unclaimed", agent="bob")
                self.assertEqual(refused.status, 1)
                self.assertIn("only alice closes it", refused.err)
                self.assertEqual(self.call(verb, "held", agent="alice").status, 1, "bob holds it")
        self.assertEqual([self.task(task_id)["state"] for task_id in ("unclaimed", "held")], ["queued", "claimed"])
        self.assertEqual(self.call("cancel", "unclaimed", agent="alice").status, 0)
        self.assertEqual(self.call("done", "held", agent="bob").status, 0)

    def test_cancel_withdraws_a_job_that_waits_for_capacity(self):
        self.call("settings", "--capacity", "1")
        marker = os.path.join(self.root, "never")
        self.work("run", "--id", "busy", "--timeout", "0", "--", *self.gate("busy"), agent="a")
        self.until(lambda: self.state("busy") == "running", "the first job to start")
        self.assertEqual(self.work("run", "--id", "later", "--timeout", "0", "--", "touch", marker,
                                   agent="b").status, 124)
        self.until(lambda: self.state("later") == "waiting", "the job to wait for capacity")
        self.assertIn("job later still waiting for capacity", self.work("wait", "later", "--timeout", "0").out)
        supervisor = self.task("later")["supervisor"]
        self.assertEqual(self.work("cancel", "later", agent="b").status, 0)
        self.assertEqual(self.work("wait", "later").status, 1)
        self.until(lambda: not work.exists(supervisor), "the supervisor to leave")
        self.open_gate("busy")
        self.assertEqual(self.work("wait", "busy").status, 0)
        self.assertFalse(os.path.exists(marker), "a cancelled job never starts")


class StatusTests(WorkTestCase):
    def test_status_shows_a_running_job_and_sweeps_one_whose_supervisor_died(self):
        self.work("scope", "set", "proj", "--task", "Ship it")
        self.work("run", "--id", "long", "--scope", "proj", "--timeout", "0", "--", "sleep", "30", agent="alice")
        job = self.until(lambda: next((job for job in self.json("status")[1]["running"] if job["rss_kib"]), None),
                         "a sample of the job")
        self.assertEqual(job["id"], "long")
        self.assertTrue(work.exists(job["pid"]))
        self.assertIsNotNone(job["cpu_percent"])
        self.assertGreater(job["rss_kib"], 0)
        text = self.work("status").out
        self.assertIn(f"long: process {job['pid']}", text)
        self.assertIn("proj (project): Ship it [1 running]", text)
        # The supervisor dies: the command runs on, and status says its status will not be recorded.
        os.kill(job["supervisor"], signal.SIGKILL)
        self.until(lambda: not work.exists(job["supervisor"]), "the supervisor to die")
        running = self.json("status")[1]["running"]
        self.assertEqual([row["id"] for row in running], ["long"])
        self.assertIn("will not be recorded", running[0]["note"])
        # Once the command is gone too, the job is failed with a note.
        os.killpg(job["pid"], signal.SIGKILL)
        self.until(lambda: not work.exists(job["pid"]), "the command to die")
        swept = self.work("status")
        self.assertIn("swept: long failed: the job ended without a recorded status", swept.out)
        task = self.task("long")
        self.assertEqual((task["state"], task["status"]), ("failed", None))

    def test_a_supervisor_goes_on_only_once_the_transaction_that_names_it_is_committed(self):
        committed, rolled_back = os.path.join(self.root, "committed"), os.path.join(self.root, "rolled-back")
        for task_id, marker in (("kept", committed), ("dropped", rolled_back)):
            self.work("add", "--id", task_id, "--", "touch", marker, agent="a")
            self.work("claim", task_id, agent="a")
            self.accept(task_id, "a")
        ctx = work.Context(self.env)
        self.addCleanup(ctx.close)
        with work.writing(ctx.conn):
            row = work.get_task(ctx.conn, "kept")
            kept = work.start_supervisor(ctx, "kept", os.path.join(self.home, "logs", "kept.log"))
            work.reserve(ctx.conn, row, "a", kept.pid, os.path.join(self.home, "logs", "kept.log"))
        time.sleep(0.5)  # Long enough for a supervisor that did not wait on its stdin to start the job.
        self.assertEqual(self.state("kept"), "claimed", "it waits for its stdin to close")
        kept.stdin.close()
        self.assertEqual(kept.wait(timeout=30), 0)
        self.assertTrue(os.path.exists(committed))
        with self.assertRaises(RuntimeError), work.writing(ctx.conn):
            row = work.get_task(ctx.conn, "dropped")
            dropped = work.start_supervisor(ctx, "dropped", os.path.join(self.home, "logs", "dropped.log"))
            work.reserve(ctx.conn, row, "a", dropped.pid, os.path.join(self.home, "logs", "dropped.log"))
            raise RuntimeError("the reservation fails after its supervisor started")
        dropped.stdin.close()
        self.assertEqual(dropped.wait(timeout=30), 1, "it does not own the job, so it leaves")
        task = self.task("dropped")
        self.assertEqual((task["state"], task["requested"], task["supervisor"]), ("claimed", None, None))
        self.assertFalse(os.path.exists(rolled_back))

    def test_a_supervisor_started_by_hand_leaves_a_job_it_does_not_own(self):
        self.call("settings", "--capacity", "1")
        self.work("run", "--id", "busy", "--timeout", "0", "--", *self.gate("busy"), agent="a")
        self.until(lambda: self.state("busy") == "running", "the first job to start")
        self.work("run", "--id", "owned", "--timeout", "0", "--", "true", agent="a")
        self.until(lambda: self.state("owned") == "waiting", "the job to wait for capacity")
        before = self.task("owned")
        stray = subprocess.run([sys.executable, SCRIPT, "_supervise", "owned"], env=self.env, cwd=self.project,
                               stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        self.assertEqual(stray.returncode, 1)
        self.assertIn("not waiting for this supervisor", stray.stderr)
        after = self.task("owned")
        self.assertEqual((after["state"], after["supervisor"], after["requested"]),
                         (before["state"], before["supervisor"], before["requested"]))
        self.open_gate("busy")
        self.assertEqual(self.work("wait", "busy", "owned").status, 0)

    def test_a_signal_is_recorded_and_forwarded_but_never_raised_nor_sent_after_the_reap(self):
        supervisor = work.Supervisor(work.Context(self.env), "none")
        supervisor.on_signal(signal.SIGHUP, None)
        self.assertEqual(supervisor.stop, signal.SIGHUP, "recorded for the next safe point, not raised")
        child = subprocess.Popen(["sleep", "30"], start_new_session=True)
        supervisor.child = child
        supervisor.on_signal(signal.SIGTERM, None)
        raw, _ = supervisor.reap(child.pid)
        child.returncode = os.waitstatus_to_exitcode(raw)
        self.assertEqual(child.returncode, -signal.SIGTERM)
        self.assertIsNone(supervisor.child, "no later signal reaches the reaped pid")

    def test_a_stopped_supervisor_stops_its_job_and_records_the_status(self):
        self.work("run", "--id", "job", "--timeout", "0", "--", *self.gate("job"), agent="alice")
        self.until(lambda: self.state("job") == "running", "the job to start")
        os.kill(self.task("job")["supervisor"], signal.SIGTERM)
        self.assertEqual(self.work("wait", "job").status, 128 + signal.SIGTERM)
        task = self.task("job")
        self.assertEqual((task["state"], task["status"], task["note"]), ("failed", 128 + signal.SIGTERM, ""))

    def test_a_job_whose_supervisor_stops_or_dies_before_it_starts_is_failed(self):
        self.call("settings", "--capacity", "1")
        self.work("run", "--id", "busy", "--timeout", "0", "--", *self.gate("busy"), agent="a")
        self.until(lambda: self.state("busy") == "running", "the first job to start")
        for task_id, signum, note in (("stopped", signal.SIGTERM, "stopped by signal 15 before the command started"),
                                      ("killed", signal.SIGKILL, "ended before the command started")):
            with self.subTest(task_id=task_id):
                self.work("run", "--id", task_id, "--timeout", "0", "--", "true", agent="b")
                self.until(lambda: self.state(task_id) == "waiting", "the job to wait")
                os.kill(self.task(task_id)["supervisor"], signum)
                self.assertEqual(self.work("wait", task_id).status, 1)
                task = self.task(task_id)
                self.assertEqual((task["state"], task["status"], task["started"]), ("failed", None, None))
                self.assertIn(note, task["note"])
        self.open_gate("busy")
        self.assertEqual(self.work("wait", "busy").status, 0)

    def test_a_slow_ps_does_not_make_a_live_job_look_dead(self):
        self.work("run", "--id", "live", "--timeout", "0", "--", *self.gate("live"), agent="a")
        self.until(lambda: self.state("live") == "running", "the job to start")
        # A ps that measures at once but answers 3 s later, as a loaded machine can make it.
        fake = os.path.join(self.root, "bin")
        os.makedirs(fake)
        with open(os.path.join(fake, "ps"), "w") as handle:
            handle.write(f'#!/bin/sh\noutput=$({shutil.which("ps")} "$@")\nstatus=$?\nsleep 3\n'
                         'printf "%s\\n" "$output"\nexit $status\n')
        os.chmod(os.path.join(fake, "ps"), 0o755)
        slow = self.work("status", env={"PATH": fake + os.pathsep + self.env.get("PATH", "")})
        self.assertEqual(slow.status, 0, slow.err)
        self.assertNotIn("swept", slow.out)
        self.assertEqual(self.state("live"), "running")
        self.open_gate("live")
        self.assertEqual(self.work("wait", "live").status, 0, "its own status is recorded")

    def test_alive_tells_a_live_process_from_a_zombie_or_a_reused_pid(self):
        me, now = os.getpid(), time.time()

        def seen(stat, start):
            return {me: work.Process(me, os.getppid(), os.getpgid(0), stat, 0.0, 0, start)}

        self.assertTrue(work.alive(me, now, seen("S", now - 10)))
        self.assertFalse(work.alive(me, now - 60, seen("S", now)), "a process that started after the job took its pid")
        self.assertFalse(work.alive(me, now, seen("Z", now - 10)), "a zombie has ended")
        self.assertTrue(work.alive(me, now - 60, None), "without ps, the pid's existence decides")

    def test_the_sweep_fails_a_job_whose_pids_now_belong_to_newer_processes(self):
        self.call("add", "--id", "ghost", "--", "true", agent="a")
        self.call("claim", "ghost", agent="a")
        impostor = subprocess.Popen(["sleep", "30"])
        self.addCleanup(impostor.wait)
        self.addCleanup(impostor.kill)
        long_ago = time.time() - 600
        self.database("UPDATE tasks SET state = 'running', requested = ?, started = ?, owner = ?, owner_since = ?, "
                      "pid = ? WHERE id = 'ghost'", long_ago, long_ago, impostor.pid, long_ago, impostor.pid)
        swept = self.work("status")
        self.assertIn("swept: ghost failed: the job ended without a recorded status", swept.out)

    def test_old_events_and_logs_are_pruned(self):
        self.call("settings", "--keep-days", "1")
        for task_id in ("old", "new"):
            self.assertEqual(self.work("run", "--id", task_id, "--", "true", agent="a").status, 0)
        old_log, new_log = self.task("old")["log"], self.task("new")["log"]
        long_ago = time.time() - 3 * 86400
        self.database("UPDATE tasks SET ended = ? WHERE id = 'old'", long_ago)
        self.database("UPDATE events SET time = ? WHERE task = 'old'", long_ago)
        self.database("UPDATE settings SET pruned = NULL")  # The runs above pruned less than an hour ago.
        self.assertEqual(self.work("status").status, 0)
        self.assertFalse(os.path.exists(old_log))
        self.assertIsNone(self.task("old")["log"])
        self.assertTrue(os.path.exists(new_log))
        self.assertEqual(self.json("log", "--task", "old")[1]["events"], [])
        self.assertNotEqual(self.json("log", "--task", "new")[1]["events"], [])

    def test_a_database_of_the_first_schema_gains_the_settings(self):
        first = os.path.join(self.root, "first")
        os.makedirs(first, mode=0o700)
        with contextlib.closing(sqlite3.connect(os.path.join(first, "work.db"))) as conn:
            for statement in work.MIGRATIONS[0]:
                conn.execute(statement)
            conn.execute("PRAGMA user_version = 1")
            conn.commit()
        os.chmod(os.path.join(first, "work.db"), 0o600)
        status, shown = self.json("settings", env={"AGENT_WORK_HOME": first})
        self.assertEqual(status, 0)
        self.assertTrue(shown["capacity_is_default"])

    def test_log_records_each_state_change(self):
        self.work("scope", "set", "proj")
        self.work("add", "--id", "t", "--scope", "proj", agent="alice")
        self.work("claim", "t", agent="bob")
        self.work("done", "t", agent="bob")
        events = self.json("log", "--task", "t")[1]["events"]
        self.assertEqual([(event["what"], event["agent"], event["scope"]) for event in events],
                         [("added", "alice", "proj"), ("claimed", "bob", "proj"), ("done", "bob", "proj")])
        self.assertEqual(len(self.json("log", "--limit", "2")[1]["events"]), 2)


class ConcurrencyTests(WorkTestCase):
    def test_many_processes_adding_at_once_lose_none(self):
        agents = [f"adder{number}" for number in range(8)]
        results = self.race("add", agents, "25")
        self.assertEqual({agent: statuses for agent, statuses in results.items()},
                         {agent: [0] * 25 for agent in agents})
        ids = [row["id"] for row in self.database("SELECT id FROM tasks")]
        self.assertEqual(sorted(ids), sorted(f"{agent}-{index}" for agent in agents for index in range(25)))
        self.assertEqual(len(self.database("SELECT seq FROM events WHERE what = 'added'")), 200)


class SafetyTests(WorkTestCase):
    def test_a_state_directory_that_others_can_write_is_refused(self):
        loose = os.path.join(self.root, "loose")
        os.makedirs(loose)
        os.chmod(loose, 0o777)
        result = self.work("status", env={"AGENT_WORK_HOME": loose})
        self.assertEqual(result.status, 1)
        self.assertIn("must be private to you", result.err)

    def test_a_state_directory_must_be_private_under_directories_that_only_you_can_write(self):
        readable_home = os.path.join(self.root, "readable")
        os.makedirs(readable_home)
        os.chmod(readable_home, 0o755)
        readable = self.work("status", env={"AGENT_WORK_HOME": readable_home})
        self.assertEqual(readable.status, 1, "others may not even read the queue")
        self.assertIn("chmod 700", readable.err)
        shared = os.path.join(self.root, "shared")
        os.makedirs(shared)
        os.chmod(shared, 0o775)
        under = self.work("status", env={"AGENT_WORK_HOME": os.path.join(shared, "state")})
        self.assertEqual(under.status, 1)
        self.assertIn(f"{shared} is writable by other users", under.err)
        self.assertFalse(os.path.exists(os.path.join(shared, "state")), "nothing is created under it")

    def test_the_state_directory_is_resolved_once_and_its_links_refused(self):
        target = os.path.join(self.root, "real-state")
        link = os.path.join(self.root, "link-state")
        os.symlink(target, link)
        self.assertEqual(self.work("status", env={"AGENT_WORK_HOME": link}).status, 0)
        self.assertTrue(os.path.isfile(os.path.join(target, "work.db")), "SQLite opens the resolved path")
        self.assertTrue(os.path.islink(link))
        with self.assertRaises(work.WorkError) as refused:
            work.guard(link, private=True)
        self.assertIn("symbolic link", str(refused.exception))

    def test_text_fields_refuse_control_and_invisible_characters(self):
        for text in ("fine\rrm", "a\x1b[2Jb", "left‮right", "tab\there", "zero​width"):
            with self.subTest(text=text):
                self.assertEqual(self.work("add", "--title", text, agent="a").status, 2)
        self.assertEqual(self.work("scope", "set", "s", "--task", "a\rb").status, 2)
        self.assertEqual(self.work("add", "--files", "a\nb", agent="a").status, 2)
        self.work("add", "--id", "t", agent="a")
        self.assertEqual(self.work("cancel", "t", "--note", "\x1b[31mred", agent="a").status, 2)
        self.assertEqual(self.task("t")["state"], "queued")

    def test_show_escapes_characters_that_could_hide_part_of_a_command(self):
        self.work("add", "--id", "sly", "--", "echo", "safe\r\x1b[2Krm -rf x‮", agent="bob")
        shown = self.work("show", "sly").out
        self.assertNotIn("\r", shown)
        self.assertNotIn("\x1b", shown)
        self.assertNotIn("‮", shown)
        self.assertIn("\\r\\x1b[2Krm -rf x\\u202e", shown)
        self.assertEqual(self.task("sly")["command"], ["echo", "safe\r\x1b[2Krm -rf x‮"])

    def test_job_output_and_stored_titles_are_escaped(self):
        result = self.work("run", "--", "printf", "clear\\033[2Jline\\rover\\n", agent="a")
        self.assertEqual(result.status, 0)
        self.assertNotIn("\x1b", result.out)
        self.assertNotIn("\r", result.out)
        # The escape shows as text; a carriage return ends a line, as it does for a progress bar.
        self.assertIn("\nclear\\x1b[2Jline\nover\n", result.out)
        # A title that reached the database another way, by hand or from an older work.py, is escaped in a plan.
        self.work("add", "--id", "titled", agent="a")
        self.database("UPDATE tasks SET title = ? WHERE id = 'titled'", "bad\x1b[2Jtitle")
        planned = self.work("plan", "--agents", "1")
        self.assertEqual(planned.status, 0)
        self.assertNotIn("\x1b", planned.out)
        self.assertIn("titled bad\\x1b[2Jtitle", planned.out)

    def test_input_errors_exit_with_2(self):
        self.work("add", "--id", "real", agent="a")
        cases = [("show", "ghost"), ("add", "--id", "../escape"), ("add", "--id", "real"), ("add", "--size", "0"),
                 ("add", "--weight", "nan"), ("add", "--after", "ghost"), ("add", "--kind", "no spaces"),
                 ("wait",), ("status", "--", "true"), ("plan", "--agents", "0"), ("run",),
                 ("run", "real", "--", "true"),
                 ("run", "real", "--weight", "2")]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(self.work(*arguments, agent="a").status, 2)
        self.assertEqual(self.work("claim", "real").status, 2, "an agent must name itself")

    def test_the_script_runs_as_a_program_and_parses_ps_times(self):
        self.assertEqual(subprocess.run([SCRIPT, "--help"], capture_output=True, timeout=30).returncode, 0)
        self.assertEqual([work.elapsed(text) for text in ("00:05", "01:02:03", "2-00:00:01")], [5, 3723, 172801])


if __name__ == "__main__":
    unittest.main()

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

WAIT = os.path.join(os.path.dirname(__file__), "..", "wait.py")


HOME = tempfile.mkdtemp(prefix="wait-tests-")


def wait(*args, timeout=30):
    started = time.monotonic()
    environment = dict(os.environ, WAIT_HOME=os.path.join(HOME, "jobs"))
    result = subprocess.run([sys.executable, WAIT, "--every", "0.05", *args], capture_output=True, text=True,
                            timeout=timeout, env=environment)
    return result, time.monotonic() - started


def job_id_of(result):
    for line in result.stderr.splitlines():
        if "started job " in line:
            return line.split("started job ")[1].split(";")[0]
    raise AssertionError(result.stderr)


class WaitTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "f")

    def tearDown(self):
        self.dir.cleanup()

    def put(self, mode, text):
        with open(self.path, mode) as handle:
            handle.write(text)

    def later(self, seconds, action):
        timer = threading.Timer(seconds, action)
        timer.start()
        self.addCleanup(timer.cancel)

    def test_run_returns_the_status_of_the_command(self):
        self.assertEqual(wait("--run", "--", "sh", "-c", "exit 7")[0].returncode, 7)
        self.assertEqual(wait("--run", "--", "true")[0].returncode, 0)

    def test_run_reports_a_command_that_cannot_start(self):
        self.assertEqual(wait("--run", "--", "no-such-command-xyz")[0].returncode, 127)
        script = self.path
        with open(script, "w") as handle:
            handle.write("#!/bin/sh\n")
        self.assertEqual(wait("--run", "--", script)[0].returncode, 126)

    def test_run_maps_a_signal_to_128_plus_n(self):
        self.assertEqual(wait("--run", "--", "sh", "-c", "kill -TERM $$")[0].returncode, 128 + 15)

    def test_a_job_outlives_a_timeout_and_wait_job_continues_it(self):
        marker = self.path
        result, elapsed = wait("--timeout", "0.5", "--run", "--", "sh", "-c",
                               f"echo begun; sleep 1; echo between; sleep 1; touch {marker}; echo finished; exit 3")
        self.assertEqual(result.returncode, 124)
        self.assertLess(elapsed, 10)
        self.assertIn("begun", result.stdout)
        job = job_id_of(result)
        self.assertIn(f"wait --job {job}", result.stderr)
        time.sleep(1.2)
        again, _ = wait("--job", job)
        self.assertEqual(again.returncode, 3, again.stderr)
        self.assertIn("between", again.stdout, "output written between two calls is printed by the second")
        self.assertTrue(os.path.exists(marker), "the job kept running after the first wait timed out")
        self.assertIn("finished", again.stdout)
        self.assertNotIn("begun", again.stdout, "a resumed wait does not repeat what an earlier call printed")
        self.assertEqual(wait("--job", job)[0].returncode, 3, "a finished job keeps its status")
        listed = wait("--jobs")[0].stdout
        self.assertRegex(listed, job + r"\s+exited 3")

    def test_stop_on_timeout_stops_the_job_and_its_children(self):
        marker = self.path
        result, _ = wait("--timeout", "0.5", "--stop-on-timeout", "--run", "--", "sh", "-c",
                         f"(sleep 2; touch {marker}) & sleep 30")
        self.assertEqual(result.returncode, 124)
        time.sleep(2.5)
        self.assertFalse(os.path.exists(marker), "the job's whole process group was stopped")

    def test_stop_ends_a_running_job(self):
        result, _ = wait("--timeout", "0.3", "--run", "--", "sleep", "30")
        job = job_id_of(result)
        self.assertEqual(wait("--stop", job)[0].returncode, 0)
        self.assertEqual(wait("--job", job)[0].returncode, 128 + 15)
        self.assertEqual(wait("--stop", "not-a-job")[0].returncode, 2)

    def test_a_failing_job_ends_the_wait_even_when_other_conditions_remain(self):
        result, elapsed = wait("--run", "--file", self.path + ".never", "--", "sh", "-c", "exit 5")
        self.assertEqual(result.returncode, 5)
        self.assertLess(elapsed, 10)

    def test_a_job_reads_no_standard_input(self):
        result = subprocess.run([sys.executable, WAIT, "--run", "--", "cat"], input="secret", capture_output=True,
                                text=True, timeout=30, env=dict(os.environ, WAIT_HOME=os.path.join(HOME, "jobs")))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("secret", result.stdout)

    def test_the_jobs_directory_must_be_private(self):
        shared = os.path.join(self.dir.name, "shared")
        os.mkdir(shared, 0o777)
        os.chmod(shared, 0o777)
        target = os.path.join(self.dir.name, "elsewhere")
        os.mkdir(target)
        link = os.path.join(self.dir.name, "link")
        os.symlink(target, link)
        environment = dict(os.environ, WAIT_HOME=link)
        refused = subprocess.run([sys.executable, WAIT, "--run", "--", "true"], capture_output=True, text=True,
                                 timeout=30, env=environment)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("refusing", refused.stderr)
        environment["WAIT_HOME"] = shared
        fixed = subprocess.run([sys.executable, WAIT, "--run", "--", "true"], capture_output=True, text=True,
                               timeout=30, env=environment)
        self.assertEqual(fixed.returncode, 0, fixed.stderr)
        self.assertEqual(os.stat(shared).st_mode & 0o777, 0o700)

    def test_until_cannot_hang_past_the_timeout(self):
        result, elapsed = wait("--until", "sleep 30", "--timeout", "1")
        self.assertEqual(result.returncode, 124)
        self.assertLess(elapsed, 5)

    def test_until_with_a_missing_program_is_a_usage_error(self):
        result, _ = wait("--until", "no-such-program-xyz")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", result.stderr)

    def test_until_holds_when_the_command_exits_zero(self):
        self.later(0.4, lambda: self.put("w", ""))
        result, elapsed = wait("--until", f"test -f {self.path}")
        self.assertEqual(result.returncode, 0)
        self.assertGreaterEqual(elapsed, 0.3)

    def test_until_times_out_while_the_command_keeps_failing(self):
        self.assertEqual(wait("--until", "false", "--timeout", "0.4")[0].returncode, 124)

    def test_file_exists_then_changed(self):
        self.later(0.3, lambda: self.put("w", "x"))
        self.assertEqual(wait("--file", self.path)[0].returncode, 0)
        before = os.stat(self.path).st_size
        self.later(0.3, lambda: self.put("a", "x"))
        self.assertEqual(wait("--file", self.path, "--changed")[0].returncode, 0)
        self.assertGreater(os.stat(self.path).st_size, before)

    def test_file_is_not_ready_while_empty(self):
        open(self.path, "w").close()
        self.assertEqual(wait("--file", self.path, "--timeout", "0.4")[0].returncode, 124)

    def test_a_status_file_sets_the_exit_status(self):
        with open(self.path, "w") as handle:
            handle.write(" 3\n")
        self.assertEqual(wait("--file", self.path)[0].returncode, 3)
        with open(self.path, "w") as handle:
            handle.write("not a number\n")
        self.assertEqual(wait("--file", self.path)[0].returncode, 0)

    def test_file_changed_does_not_hold_while_unchanged(self):
        with open(self.path, "w") as handle:
            handle.write("x")
        self.assertEqual(wait("--file", self.path, "--changed", "--timeout", "0.4")[0].returncode, 124)

    def test_gone(self):
        open(self.path, "w").close()
        self.later(0.3, lambda: os.remove(self.path))
        self.assertEqual(wait("--gone", self.path)[0].returncode, 0)

    def test_pid_treats_a_zombie_as_exited(self):
        process = subprocess.Popen(["true"])
        time.sleep(0.3)
        self.addCleanup(process.wait)
        self.assertEqual(wait("--pid", str(process.pid), "--timeout", "3")[0].returncode, 0)

    def test_pid_waits_for_a_process_that_is_not_a_child(self):
        process = subprocess.Popen(["sleep", "0.5"])
        self.addCleanup(process.wait)
        result, elapsed = wait("--pid", str(process.pid))
        self.assertEqual(result.returncode, 0)
        self.assertGreaterEqual(elapsed, 0.3)

    def test_log_counts_the_lines_it_already_holds_unless_from_end(self):
        with open(self.path, "w") as handle:
            handle.write("one\nBUILD SUCCEEDED\n")
        result, _ = wait("--log", self.path, "--match", "BUILD SUCCEEDED")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ["one", "BUILD SUCCEEDED"])
        self.assertEqual(wait("--log", self.path, "--match", "BUILD SUCCEEDED", "--from-end", "--timeout", "0.4")[0].returncode, 124)

    def test_log_matches_an_unfinished_last_line(self):
        with open(self.path, "w") as handle:
            handle.write("partial match")
        self.assertEqual(wait("--log", self.path, "--match", "match")[0].returncode, 0)

    def test_log_that_shrank_is_read_again_from_its_start(self):
        with open(self.path, "w") as handle:
            handle.write("x" * 5000 + "\n")

        def replace():
            with open(self.path, "w") as handle:
                handle.write("DONE\n")

        self.later(0.4, replace)
        self.assertEqual(wait("--log", self.path, "--match", "DONE")[0].returncode, 0)

    def test_log_decodes_a_character_split_between_writes(self):
        open(self.path, "w").close()
        raw = "caf\u00e9 ok\n".encode("utf-8")

        def write():
            with open(self.path, "ab") as handle:
                handle.write(raw[:4])
                handle.flush()
                time.sleep(0.2)
                handle.write(raw[4:])

        self.later(0.2, write)
        self.assertEqual(wait("--log", self.path, "--match", "caf\u00e9 ok")[0].returncode, 0)

    def test_log_never_matches_a_symlink_or_a_missing_file(self):
        target = self.path + ".real"
        with open(target, "w") as handle:
            handle.write("hit\n")
        os.symlink(target, self.path)
        self.assertEqual(wait("--log", self.path, "--match", "hit", "--timeout", "0.4")[0].returncode, 124)
        self.assertEqual(wait("--log", self.path + ".none", "--match", "hit", "--timeout", "0.3")[0].returncode, 124)

    def test_log_matches_a_line_that_arrives_in_two_writes(self):
        open(self.path, "w").close()

        def write():
            with open(self.path, "a") as handle:
                handle.write("BUILD SUC")
                handle.flush()
                time.sleep(0.2)
                handle.write("CEEDED\n")

        self.later(0.2, write)
        self.assertEqual(wait("--log", self.path, "--match", "^BUILD SUCCEEDED$")[0].returncode, 0)

    def test_all_needs_every_condition_and_any_needs_one(self):
        self.later(0.3, lambda: self.put("w", "x"))
        result, _ = wait("--file", self.path, "--until", "false", "--any")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(wait("--file", self.path, "--until", "false", "--timeout", "0.5")[0].returncode, 124)

    def test_usage_errors_exit_2(self):
        self.assertEqual(wait()[0].returncode, 2)
        self.assertEqual(wait("--run")[0].returncode, 2)
        self.assertEqual(wait("--log", "x")[0].returncode, 2)
        self.assertEqual(wait("--until", "true", "--", "ls")[0].returncode, 2)
        self.assertEqual(wait("--pid", "0")[0].returncode, 2)
        self.assertEqual(wait("--log", self.path, "--match", "(")[0].returncode, 2)


if __name__ == "__main__":
    unittest.main()

"""Tests for scripts/wait-for.sh: each mode returns as soon as its condition holds, keeps exit statuses, and
times out with 124 without stopping the work. Run: python3 -m unittest discover -s scripts/tests"""

import os
import subprocess
import tempfile
import time
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wait-for.sh")


def wait_for(*arguments, cwd):
    """Runs wait-for.sh; returns (exit status, output, seconds taken)."""
    start = time.monotonic()
    result = subprocess.run(
        ["sh", SCRIPT, *arguments], cwd=cwd, capture_output=True, text=True, timeout=60)
    return result.returncode, result.stdout + result.stderr, time.monotonic() - start


class WaitForTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = self.directory.name

    def tearDown(self):
        self.directory.cleanup()

    def file(self, name):
        return os.path.join(self.path, name)

    def test_run_returns_the_commands_status_as_soon_as_it_ends(self):
        status, output, seconds = wait_for(
            "run", "st", "out.log", "--", "sh", "-c", "echo working; sleep 1; exit 3", cwd=self.path)
        self.assertEqual(status, 3)
        self.assertIn("finished with status 3", output)
        self.assertIn("working", output)
        self.assertLess(seconds, 4, "it waited past the command's end")
        with open(self.file("st")) as handle:
            self.assertEqual(handle.read().strip(), "3")

    def test_run_passes_a_success_through(self):
        status, output, _ = wait_for("run", "st", "out.log", "--", "true", cwd=self.path)
        self.assertEqual(status, 0)
        self.assertIn("finished with status 0", output)

    def test_a_timeout_returns_124_and_leaves_the_command_running(self):
        status, output, seconds = wait_for(
            "--timeout", "1", "run", "st", "out.log", "--", "sh", "-c", "sleep 3; echo late", cwd=self.path)
        self.assertEqual(status, 124)
        self.assertIn("call again", output)
        self.assertLess(seconds, 3)
        self.assertFalse(os.path.exists(self.file("st")))
        # Waiting again picks the same command up and returns when it ends.
        status, output, _ = wait_for("file", "st", cwd=self.path)
        self.assertEqual(status, 0)
        with open(self.file("out.log")) as handle:
            self.assertIn("late", handle.read())

    def test_run_replaces_a_stale_status_file(self):
        with open(self.file("st"), "w") as handle:
            handle.write("9\n")
        status, _, _ = wait_for("run", "st", "out.log", "--", "sh", "-c", "sleep 1; exit 4", cwd=self.path)
        self.assertEqual(status, 4)

    def test_file_waits_for_every_path(self):
        subprocess.Popen(["sh", "-c", f"sleep 1; echo a > {self.file('a')}; sleep 1; echo b > {self.file('b')}"])
        status, output, seconds = wait_for("file", "a", "b", cwd=self.path)
        self.assertEqual(status, 0)
        self.assertIn("every file is ready", output)
        self.assertGreaterEqual(seconds, 1.5)
        self.assertLess(seconds, 5)

    def test_file_with_text_that_is_not_a_status_succeeds(self):
        with open(self.file("note"), "w") as handle:
            handle.write("ready\n")
        status, output, _ = wait_for("file", "note", cwd=self.path)
        self.assertEqual(status, 0)
        self.assertIn("is ready", output)

    def test_an_empty_file_is_not_ready(self):
        open(self.file("empty"), "w").close()
        status, _, _ = wait_for("--timeout", "1", "file", "empty", cwd=self.path)
        self.assertEqual(status, 124)

    def test_gone_returns_when_every_path_is_removed(self):
        for name in ("P1.lock", "P2.lock"):
            open(self.file(name), "w").close()
        subprocess.Popen(["sh", "-c", f"sleep 1; rm {self.file('P1.lock')}; sleep 1; rm {self.file('P2.lock')}"])
        status, output, seconds = wait_for("gone", "P1.lock", "P2.lock", cwd=self.path)
        self.assertEqual(status, 0)
        self.assertIn("every path is gone", output)
        self.assertGreaterEqual(seconds, 1.5)
        self.assertLess(seconds, 5)

    def test_gone_times_out_while_a_path_remains(self):
        open(self.file("P1.lock"), "w").close()
        status, output, _ = wait_for("--timeout", "1", "gone", "P1.lock", cwd=self.path)
        self.assertEqual(status, 124)
        self.assertIn("still present", output)

    def test_pid_returns_when_every_process_exits(self):
        first = subprocess.Popen(["sleep", "1"])
        second = subprocess.Popen(["sleep", "2"])
        # Neither child is reaped until the wait returns: an exited, unreaped child must count as gone.
        status, output, seconds = wait_for("--timeout", "20", "pid", str(first.pid), str(second.pid), cwd=self.path)
        first.wait()
        second.wait()
        self.assertEqual(status, 0)
        self.assertIn("every process exited", output)
        self.assertGreaterEqual(seconds, 1.5)
        self.assertLess(seconds, 5)

    def test_pid_times_out_while_a_process_runs(self):
        process = subprocess.Popen(["sleep", "5"])
        status, output, _ = wait_for("--timeout", "1", "pid", str(process.pid), cwd=self.path)
        process.kill()
        process.wait()
        self.assertEqual(status, 124)
        self.assertIn("still running", output)

    def test_pid_of_a_process_that_already_ended_returns_at_once(self):
        process = subprocess.Popen(["true"])
        process.wait()
        status, output, seconds = wait_for("pid", str(process.pid), cwd=self.path)
        self.assertEqual(status, 0)
        self.assertLess(seconds, 2)

    def test_log_returns_on_the_first_matching_line(self):
        log = self.file("build.log")
        subprocess.Popen(["sh", "-c", f"sleep 1; echo compiling >> {log}; sleep 1; echo 'Build complete!' >> {log}"])
        status, output, seconds = wait_for("log", "build.log", "Build complete", cwd=self.path)
        self.assertEqual(status, 0)
        self.assertIn("Build complete!", output)
        self.assertLess(seconds, 5)

    def test_log_times_out_without_a_match(self):
        with open(self.file("build.log"), "w") as handle:
            handle.write("compiling\n")
        status, output, _ = wait_for("--timeout", "1", "log", "build.log", "never there", cwd=self.path)
        self.assertEqual(status, 124)
        self.assertIn("no match", output)

    def test_tail_limits_the_log_lines_printed(self):
        status, output, _ = wait_for(
            "--tail", "2", "run", "st", "out.log", "--", "sh", "-c", "for i in 1 2 3 4 5; do echo line$i; done",
            cwd=self.path)
        self.assertEqual(status, 0)
        self.assertNotIn("line3", output)
        self.assertIn("line4", output)
        self.assertIn("line5", output)

    def test_a_large_output_reaches_the_log_whole_and_the_status_survives(self):
        # A megabyte on both streams, then a failure: nothing is cut, and the status is the command's own.
        script = "i=0; while [ $i -lt 16384 ]; do echo out-$i; echo err-$i >&2; i=$((i+1)); done; exit 7"
        status, output, _ = wait_for("--tail", "1", "run", "st", "out.log", "--", "sh", "-c", script, cwd=self.path)
        self.assertEqual(status, 7)
        with open(self.file("out.log")) as handle:
            lines = handle.read().splitlines()
        self.assertEqual(len(lines), 2 * 16384)
        self.assertIn("out-16383", lines)
        self.assertIn("err-16383", lines)
        self.assertIn("finished with status 7", output)

    def test_a_command_killed_by_a_signal_reports_128_plus_the_signal(self):
        status, output, _ = wait_for("run", "st", "out.log", "--", "sh", "-c", "kill -TERM $$", cwd=self.path)
        self.assertEqual(status, 128 + 15)
        self.assertIn("finished with status 143", output)

    def test_a_missing_command_reports_127(self):
        status, _, _ = wait_for("run", "st", "out.log", "--", "no-such-command-anywhere", cwd=self.path)
        self.assertEqual(status, 127)

    def test_a_pipeline_reports_its_last_command_unless_pipefail_is_set(self):
        # Why the docs say never to pipe a command into tail: the failure disappears.
        status, _, _ = wait_for("run", "st", "out.log", "--", "sh", "-c", "false | cat", cwd=self.path)
        self.assertEqual(status, 0)
        status, _, _ = wait_for("run", "st", "out.log", "--", "bash", "-c", "set -o pipefail; false | cat", cwd=self.path)
        self.assertEqual(status, 1)

    def test_usage_errors_exit_with_2(self):
        for arguments in (("bogus",), ("run", "st", "out.log", "true"), ("log", "only-a-path"), ("gone",), ("--timeout",), ()):
            with self.subTest(arguments=arguments):
                status, _, _ = wait_for(*arguments, cwd=self.path)
                self.assertEqual(status, 2)


if __name__ == "__main__":
    unittest.main()

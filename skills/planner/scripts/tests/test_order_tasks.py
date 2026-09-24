"""Tests for scripts/order_tasks.py. Run: python3 -m unittest discover -s scripts/tests"""

import io
import json
import os
import random
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import order_tasks as ot  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "order_tasks.py")


def graph(*specs):
    return ot.Graph(ot.load_tasks([], list(specs)))


def random_graph(rng, count, with_files):
    """A random acyclic graph: each task may follow some of the tasks before it."""
    specs = []
    for index in range(count):
        fields = [f"id=t{index}", f"size={rng.randint(1, 5)}", f"value={rng.randint(1, 9)}"]
        fields.append("kind=" + rng.choice(["validity", "performance", "structure", "feature"]))
        prerequisites = [f"t{other}" for other in range(index) if rng.random() < 0.15]
        if prerequisites:
            fields.append("after=" + "+".join(prerequisites))
        if with_files:
            fields.append("files=" + "+".join(rng.sample(["src/a", "src/b", "src/c", "src/a/x", "docs"], rng.randint(1, 2))))
        specs.append(",".join(fields))
    rng.shuffle(specs)
    return graph(*specs)


class OrderTests(unittest.TestCase):
    def test_fifo_keeps_arrival_order(self):
        tasks = graph("id=c,queued=3", "id=a,queued=1", "id=b,queued=2")
        self.assertEqual(ot.order(tasks), ["a", "b", "c"])

    def test_input_order_is_the_default_arrival(self):
        self.assertEqual(ot.order(graph("id=second", "id=first")), ["second", "first"])

    def test_validity_goes_before_older_work(self):
        tasks = graph("id=perf,kind=performance", "id=docs,kind=docs", "id=crash,kind=crash", "id=wrong,kind=correctness")
        self.assertEqual(ot.order(tasks), ["crash", "wrong", "perf", "docs"])

    def test_a_task_comes_after_its_prerequisites(self):
        tasks = graph("id=use,after=build", "id=build,after=fetch", "id=fetch")
        self.assertEqual(ot.order(tasks), ["fetch", "build", "use"])

    def test_a_prerequisite_of_a_validity_task_moves_up_with_it(self):
        tasks = graph("id=old,kind=performance", "id=refactor,kind=structure", "id=fix,kind=validity,after=refactor")
        self.assertEqual(ot.order(tasks), ["refactor", "fix", "old"])
        _, source = ot.priorities(tasks, "fifo")
        self.assertEqual(source["refactor"], "fix")
        self.assertIsNone(source["old"])

    def test_iso_timestamps_order_by_time(self):
        tasks = graph("id=late,queued=2026-09-24T11:00", "id=early,queued=2026-09-24T09:30")
        self.assertEqual(ot.order(tasks), ["early", "late"])

    def test_wsjf_puts_value_per_size_first_and_keeps_arrival_on_ties(self):
        tasks = graph("id=big,size=8,value=8", "id=quick,size=1,value=4", "id=tie,size=8,value=8", "id=low,size=4,value=1")
        self.assertEqual(ot.order(tasks, "wsjf"), ["quick", "big", "tie", "low"])

    def test_wsjf_still_puts_validity_first(self):
        tasks = graph("id=cheap,size=1,value=100", "id=bug,kind=validity,size=10,value=1")
        self.assertEqual(ot.order(tasks, "wsjf"), ["bug", "cheap"])

    def test_critical_path_prefers_the_longest_chain(self):
        tasks = graph("id=short,size=3", "id=head,size=1", "id=tail,size=5,after=head")
        self.assertEqual(tasks.bottom_levels()["head"], 6)
        self.assertEqual(ot.order(tasks, "critical-path"), ["head", "tail", "short"])


class InputErrorTests(unittest.TestCase):
    def test_a_cycle_is_reported_with_its_path(self):
        with self.assertRaises(ot.InputError) as raised:
            graph("id=a,after=c", "id=b,after=a", "id=c,after=b", "id=free")
        message = str(raised.exception)
        self.assertIn("cycle", message)
        for task_id in ("a", "b", "c"):
            self.assertIn(task_id, message)
        self.assertNotIn("free", message)

    def test_unknown_duplicate_and_self_references_are_errors(self):
        for specs in (("id=a,after=ghost",), ("id=a", "id=a"), ("id=a,after=a",), ("kind=validity",)):
            with self.subTest(specs=specs), self.assertRaises(ot.InputError):
                graph(*specs)

    def test_sizes_and_values_must_be_positive_numbers(self):
        for spec in ("id=a,size=0", "id=a,size=-1", "id=a,value=lots", "id=a,size=nan"):
            with self.subTest(spec=spec), self.assertRaises(ot.InputError):
                graph(spec)

    def test_arrivals_cannot_mix_numbers_and_timestamps(self):
        with self.assertRaises(ot.InputError):
            graph("id=a,queued=1", "id=b,queued=2026-09-24")

    def test_a_title_may_hold_commas(self):
        task = ot.load_tasks([], ["id=a,title=Fix the parser, then the lexer,kind=validity"])[0]
        self.assertEqual(task.title, "Fix the parser, then the lexer")
        self.assertEqual(task.kind, "validity")


class ScheduleTests(unittest.TestCase):
    def check_valid(self, tasks, result):
        placed = {}
        for lane in result["lanes"]:
            for step, following in zip(lane, lane[1:]):
                self.assertLessEqual(step["end"], following["start"])
            for step in lane:
                self.assertNotIn(step["id"], placed)
                placed[step["id"]] = step
        self.assertEqual(set(placed), set(tasks.tasks))
        for task_id, step in placed.items():
            task = tasks.tasks[task_id]
            self.assertAlmostEqual(step["end"] - step["start"], task.size)
            for prerequisite in task.after:
                self.assertGreaterEqual(step["start"], placed[prerequisite]["end"])
        for first in placed.values():
            for second in placed.values():
                if first is not second and ot.conflict(tasks.tasks[first["id"]], tasks.tasks[second["id"]]):
                    self.assertTrue(first["end"] <= second["start"] or second["end"] <= first["start"])
        self.assertGreaterEqual(result["makespan"], result["lower_bound"] - 1e-9)

    def test_schedules_are_valid_on_random_graphs(self):
        rng = random.Random(7)
        for trial in range(150):
            tasks = random_graph(rng, rng.randint(1, 14), with_files=True)
            for agents in (1, 2, 3, 5):
                for policy in ot.POLICIES:
                    with self.subTest(trial=trial, agents=agents, policy=policy):
                        self.check_valid(tasks, ot.schedule(tasks, agents, policy))

    def test_list_scheduling_meets_grahams_bound(self):
        rng = random.Random(11)
        for trial in range(200):
            tasks = random_graph(rng, rng.randint(1, 16), with_files=False)
            total = sum(task.size for task in tasks.tasks.values())
            critical = max(tasks.bottom_levels().values())
            for agents in (1, 2, 4):
                with self.subTest(trial=trial, agents=agents):
                    result = ot.schedule(tasks, agents, "critical-path")
                    bound = total / agents + (1 - 1 / agents) * critical
                    self.assertLessEqual(result["makespan"], bound + 1e-9)

    def test_one_agent_follows_the_single_order(self):
        rng = random.Random(3)
        for _ in range(50):
            tasks = random_graph(rng, rng.randint(1, 12), with_files=True)
            lane = ot.schedule(tasks, 1, "fifo")["lanes"][0]
            self.assertEqual([step["id"] for step in lane], ot.order(tasks, "fifo"))

    def test_overlapping_files_never_run_together(self):
        tasks = graph("id=a,files=src/app", "id=b,files=src/app/view.swift", "id=c,files=docs")
        result = ot.schedule(tasks, 3)
        self.check_valid(tasks, result)
        starts = {step["id"]: step["start"] for lane in result["lanes"] for step in lane}
        self.assertEqual(starts["a"], 0)
        self.assertEqual(starts["c"], 0)
        self.assertEqual(starts["b"], 1)


class AssignTests(unittest.TestCase):
    def assert_equilibrium(self, tasks, result, penalty):
        ranked = [task_id for task_id in ot.order(tasks) if not tasks.tasks[task_id].after]
        rank = {task_id: position for position, task_id in enumerate(ranked)}
        choices = [row["task"] for row in result["assignment"]]

        def clash(first, second):
            if first == second:
                return len(ranked) + 1
            return penalty if ot.conflict(tasks.tasks[first], tasks.tasks[second]) else 0

        def cost(choice, others):
            if choice is None:
                return len(ranked)
            return rank[choice] + sum(clash(choice, other) for other in others if other is not None)

        for agent, choice in enumerate(choices):
            others = choices[:agent] + choices[agent + 1:]
            for alternative in [None, *ranked]:
                self.assertLessEqual(cost(choice, others), cost(alternative, others), f"agent {agent} would switch")

    def test_every_assignment_is_a_nash_equilibrium(self):
        rng = random.Random(5)
        for trial in range(200):
            tasks = random_graph(rng, rng.randint(1, 10), with_files=True)
            ready = sum(1 for task in tasks.tasks.values() if not task.after)
            for agents in (1, 2, 3, 6):
                with self.subTest(trial=trial, agents=agents):
                    result = ot.assign(tasks, agents)
                    self.assert_equilibrium(tasks, result, ready + 1)

    def test_agents_take_distinct_non_conflicting_tasks_or_idle(self):
        tasks = graph("id=a,files=src", "id=b,files=src/x", "id=c,files=docs", "id=d,after=c")
        result = ot.assign(tasks, 3)
        choices = [row["task"] for row in result["assignment"]]
        self.assertEqual(choices, ["a", "c", None])

    def test_a_low_conflict_cost_lets_agents_share_files(self):
        tasks = graph("id=a,files=src", "id=b,files=src/x")
        result = ot.assign(tasks, 2, conflict_cost=0.5)
        self.assertEqual(sorted(row["task"] for row in result["assignment"]), ["a", "b"])
        self.assert_equilibrium(tasks, result, 0.5)

    def test_no_conflict_cost_makes_two_agents_take_one_task(self):
        tasks = graph("id=a", "id=b")
        for conflict_cost in (0.0, 0.5, 100.0):
            with self.subTest(conflict_cost=conflict_cost):
                choices = [row["task"] for row in ot.assign(tasks, 3, conflict_cost=conflict_cost)["assignment"]]
                taken = [choice for choice in choices if choice is not None]
                self.assertEqual(len(taken), len(set(taken)))


class CommandLineTests(unittest.TestCase):
    def run_main(self, *argv, stdin=None):
        output, errors = io.StringIO(), io.StringIO()
        old_stdin = sys.stdin
        try:
            if stdin is not None:
                sys.stdin = io.StringIO(stdin)
            with redirect_stdout(output), redirect_stderr(errors):
                status = ot.main(list(argv))
        finally:
            sys.stdin = old_stdin
        return status, output.getvalue(), errors.getvalue()

    def test_task_arguments_give_a_numbered_order(self):
        status, output, _ = self.run_main("--task", "id=perf,kind=performance", "--task", "id=crash,kind=validity")
        self.assertEqual(status, 0)
        self.assertEqual(output.splitlines(), ["1. crash (validity)", "2. perf (performance)"])

    def test_json_from_stdin_gives_json(self):
        document = json.dumps({"tasks": [{"id": "b", "after": ["a"]}, {"id": "a"}]})
        status, output, _ = self.run_main("--tasks", "-", "--format", "json", stdin=document)
        self.assertEqual(status, 0)
        self.assertEqual([row["id"] for row in json.loads(output)["order"]], ["a", "b"])

    def test_agents_and_assign_render(self):
        tasks = ["--task", "id=a,size=2", "--task", "id=b", "--task", "id=c,after=a"]
        status, output, _ = self.run_main(*tasks, "--agents", "2")
        self.assertEqual(status, 0)
        self.assertIn("makespan 3", output)
        status, output, _ = self.run_main(*tasks, "--agents", "2", "--assign")
        self.assertEqual(status, 0)
        self.assertIn("Nash equilibrium", output)

    def test_input_errors_exit_with_2(self):
        status, _, errors = self.run_main("--task", "id=a,after=missing")
        self.assertEqual(status, 2)
        self.assertIn("unknown task", errors)
        self.assertEqual(self.run_main()[0], 2)

    def test_the_script_runs_as_a_program(self):
        result = subprocess.run(
            [sys.executable, SCRIPT, "--task", "id=x"], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "1. x (other)")


if __name__ == "__main__":
    unittest.main()

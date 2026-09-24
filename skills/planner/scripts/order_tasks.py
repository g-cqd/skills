#!/usr/bin/env python3
"""Order the tasks an agent works on: validity first, then first in, first out, with dependencies respected.

An agent passes its tasks, as JSON or as --task arguments, and gets back the order to work in, a schedule for
several agents, or the task each agent should take next.

Rules, and where each comes from:
  - Validity first (the work-order rule): a task whose kind is validity, correctness, safety, security,
    data-loss or crash comes before every other task; within each tier, tasks keep their arrival order.
  - Dependencies: an order is a topological order of the "after" relation (Kahn's algorithm, with a priority
    queue so that among ready tasks the most urgent goes first). A cycle is an input error, reported with its path.
  - Priority inheritance: a task inherits the priority of the most urgent task waiting on it, so an urgent task
    never waits behind its own prerequisite's low priority (the fix for priority inversion in real-time
    scheduling).
  - --policy wsjf: within a tier, the highest value per unit of size first (Smith's rule, which minimizes the
    weighted sum of completion times on one worker when there are no dependencies; with dependencies it is the
    usual list-scheduling heuristic).
  - --policy critical-path: within a tier, the task with the longest chain of work after it first (the HLFET list
    heuristic, which shortens the makespan of a parallel schedule).
  - --agents K: Graham's list scheduling on K agents, where no two tasks whose "files" overlap run at the same
    time. It reports the makespan against a lower bound, the larger of the total work over K and the critical path.
  - --assign: the next task for each of K agents that choose independently, as a congestion game: an agent's cost
    is its task's rank, plus a penalty for each other agent on an overlapping task, and more than idling costs for
    each other agent on the same task. Pairwise, symmetric penalties make it an exact potential game (Rosenthal),
    so best-response dynamics end in a pure Nash equilibrium: no agent can do better by switching alone.

Task fields: id (required, unique); title; kind; queued (arrival: a number or an ISO 8601 time, by default the
input order); after (ids that must finish first); size (effort, default 1); value (cost of delay, default 1);
files (paths or directories the task changes; tasks whose paths are equal or nest conflict).

Examples:
  order_tasks.py --task id=perf,kind=performance --task id=crash,kind=validity,files=src/app
  order_tasks.py --tasks queue.json --policy critical-path --agents 3 --format json
  order_tasks.py --tasks queue.json --assign --agents 3

Exit status: 0 on success, 2 for an input error (an unknown or duplicate id, a cycle, a bad number).
"""

from __future__ import annotations

import argparse
import heapq
import json
import re
import sys
from dataclasses import dataclass, field

VALIDITY_KINDS = frozenset({"validity", "correctness", "safety", "security", "data-loss", "crash"})
POLICIES = ("fifo", "wsjf", "critical-path")


class InputError(Exception):
    """The tasks cannot be ordered as given."""


@dataclass
class Task:
    id: str
    title: str = ""
    kind: str = "other"
    queued: float | str | None = None
    index: int = 0
    after: list[str] = field(default_factory=list)
    size: float = 1.0
    value: float = 1.0
    files: list[str] = field(default_factory=list)

    @property
    def tier(self) -> int:
        return 0 if self.kind.lower() in VALIDITY_KINDS else 1


# MARK: - Input


def _positive(raw: object, name: str, task_id: str) -> float:
    try:
        number = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise InputError(f"task {task_id}: {name} must be a number, not {raw!r}") from None
    if not number > 0:
        raise InputError(f"task {task_id}: {name} must be greater than zero")
    return number


def _list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [item for item in raw.split("+") if item]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    raise InputError(f"expected a list, not {raw!r}")


def make_task(fields: dict, index: int) -> Task:
    """A task from its fields; `index` is its position in the input, the default arrival order."""
    task_id = str(fields.get("id", "")).strip()
    if not task_id:
        raise InputError(f"task at position {index + 1} has no id")
    queued = fields.get("queued")
    if isinstance(queued, str):
        try:
            queued = float(queued)
        except ValueError:
            pass
    return Task(
        id=task_id,
        title=str(fields.get("title", "")),
        kind=str(fields.get("kind", "other")),
        queued=queued,
        index=index,
        after=_list(fields.get("after")),
        size=_positive(fields.get("size", 1), "size", task_id),
        value=_positive(fields.get("value", 1), "value", task_id),
        files=_list(fields.get("files")),
    )


def parse_spec(spec: str) -> dict:
    """Fields from a --task argument, `key=value` pairs separated by commas; lists use `+`. A title may hold commas,
    because a comma only separates fields when a `key=` follows it."""
    fields = {}
    for part in re.split(r",(?=[A-Za-z_-]+=)", spec):
        key, separator, value = part.partition("=")
        if not separator:
            raise InputError(f"--task {spec!r}: {part!r} is not key=value")
        fields[key.strip()] = value.strip()
    return fields


def load_tasks(documents: list[object], specs: list[str]) -> list[Task]:
    raw: list[dict] = []
    for document in documents:
        items = document.get("tasks") if isinstance(document, dict) else document
        if not isinstance(items, list):
            raise InputError("the JSON must be a list of tasks or an object with a \"tasks\" list")
        raw.extend(items)
    raw.extend(parse_spec(spec) for spec in specs)
    tasks = [make_task(fields, index) for index, fields in enumerate(raw)]
    arrivals = {type(task.queued) for task in tasks if task.queued is not None}
    if len(arrivals) > 1:
        raise InputError("queued values must be all numbers or all timestamps")
    return tasks


# MARK: - Graph


def overlap(first: str, second: str) -> bool:
    """Whether two paths are the same, or one lies inside the other."""
    first, second = first.rstrip("/"), second.rstrip("/")
    return first == second or first.startswith(second + "/") or second.startswith(first + "/")


def conflict(first: Task, second: Task) -> bool:
    """Whether two tasks change the same files, so they must not run at the same time."""
    return first.id == second.id or any(overlap(a, b) for a in first.files for b in second.files)


class Graph:
    """The tasks and their "after" relation, checked for unknown ids, duplicates and cycles."""

    def __init__(self, tasks: list[Task]):
        self.tasks = {}
        for task in tasks:
            if task.id in self.tasks:
                raise InputError(f"duplicate task id {task.id!r}")
            self.tasks[task.id] = task
        self.dependents: dict[str, list[str]] = {task.id: [] for task in tasks}
        for task in tasks:
            for prerequisite in task.after:
                if prerequisite not in self.tasks:
                    raise InputError(f"task {task.id!r} is after unknown task {prerequisite!r}")
                if prerequisite == task.id:
                    raise InputError(f"task {task.id!r} is after itself")
                self.dependents[prerequisite].append(task.id)
        self.topological = self._topological()

    def _topological(self) -> list[str]:
        indegree = {task_id: len(set(task.after)) for task_id, task in self.tasks.items()}
        ready = [task_id for task_id, degree in indegree.items() if degree == 0]
        order = []
        while ready:
            task_id = ready.pop()
            order.append(task_id)
            for dependent in set(self.dependents[task_id]):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
        if len(order) < len(self.tasks):
            raise InputError("the tasks form a cycle: " + " -> ".join(self._cycle(set(self.tasks) - set(order))))
        return order

    def _cycle(self, remaining: set[str]) -> list[str]:
        """A cycle among `remaining`, the tasks Kahn's algorithm could not order, found by following prerequisites."""
        start = min(remaining)
        path, seen = [start], {start: 0}
        while True:
            following = min(p for p in self.tasks[path[-1]].after if p in remaining)
            if following in seen:
                return path[seen[following]:] + [following]
            seen[following] = len(path)
            path.append(following)

    def bottom_levels(self) -> dict[str, float]:
        """Each task's size plus the longest chain of work that waits on it: its critical-path length."""
        levels: dict[str, float] = {}
        for task_id in reversed(self.topological):
            after = [levels[dependent] for dependent in self.dependents[task_id]]
            levels[task_id] = self.tasks[task_id].size + max(after, default=0.0)
        return levels


# MARK: - Ordering


def _arrival(task: Task) -> tuple:
    return (0, task.queued, task.index) if task.queued is not None else (1, task.index, task.index)


def priorities(graph: Graph, policy: str) -> tuple[dict[str, tuple], dict[str, str | None]]:
    """Each task's effective priority, the smaller the sooner, with priority inheritance, and the task it inherited
    from, if any."""
    levels = graph.bottom_levels()
    own = {}
    for task_id, task in graph.tasks.items():
        if policy == "fifo":
            own[task_id] = (task.tier, _arrival(task))
        elif policy == "wsjf":
            own[task_id] = (task.tier, -task.value / task.size, _arrival(task))
        elif policy == "critical-path":
            own[task_id] = (task.tier, -levels[task_id], _arrival(task))
        else:
            raise InputError(f"unknown policy {policy!r}")
    effective, source = dict(own), {task_id: None for task_id in own}
    for task_id in reversed(graph.topological):
        for dependent in graph.dependents[task_id]:
            if effective[dependent] < effective[task_id]:
                effective[task_id] = effective[dependent]
                source[task_id] = source[dependent] or dependent
    return effective, source


def order(graph: Graph, policy: str = "fifo") -> list[str]:
    """One agent's order: always the most urgent task whose prerequisites are done."""
    effective, _ = priorities(graph, policy)
    indegree = {task_id: len(set(task.after)) for task_id, task in graph.tasks.items()}
    ready = [(effective[task_id], task_id) for task_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        _, task_id = heapq.heappop(ready)
        result.append(task_id)
        for dependent in set(graph.dependents[task_id]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(ready, (effective[dependent], dependent))
    return result


def schedule(graph: Graph, agents: int, policy: str = "fifo") -> dict:
    """Graham's list scheduling on `agents` agents: whenever an agent is free, it takes the most urgent ready task
    that overlaps no running task's files. Sizes are durations."""
    if agents < 1:
        raise InputError("--agents must be at least 1")
    effective, _ = priorities(graph, policy)
    indegree = {task_id: len(set(task.after)) for task_id, task in graph.tasks.items()}
    ready = [(effective[task_id], task_id) for task_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    running: list[tuple[float, int, str]] = []
    free = list(range(agents))
    lanes: list[list[dict]] = [[] for _ in range(agents)]
    now = 0.0
    while ready or running:
        waiting = []
        while free and ready:
            key, task_id = heapq.heappop(ready)
            task = graph.tasks[task_id]
            if any(conflict(task, graph.tasks[other]) for _, _, other in running):
                waiting.append((key, task_id))
                continue
            agent = free.pop(0)
            heapq.heappush(running, (now + task.size, agent, task_id))
            lanes[agent].append({"id": task_id, "start": now, "end": now + task.size})
        for item in waiting:
            heapq.heappush(ready, item)
        if not running:
            break
        now = running[0][0]
        while running and running[0][0] == now:
            _, agent, task_id = heapq.heappop(running)
            free.append(agent)
            for dependent in set(graph.dependents[task_id]):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    heapq.heappush(ready, (effective[dependent], dependent))
        free.sort()
    total = sum(task.size for task in graph.tasks.values())
    lower_bound = max(total / agents, max(graph.bottom_levels().values(), default=0.0))
    makespan = max((lane[-1]["end"] for lane in lanes if lane), default=0.0)
    return {"agents": agents, "makespan": makespan, "lower_bound": lower_bound, "lanes": lanes}


def assign(graph: Graph, agents: int, policy: str = "fifo", conflict_cost: float | None = None) -> dict:
    """The next task for each of `agents` agents that choose independently: a pure Nash equilibrium of the
    congestion game in the module docstring, reached by best-response dynamics from a greedy start."""
    if agents < 1:
        raise InputError("--agents must be at least 1")
    ranked = [task_id for task_id in order(graph, policy) if not graph.tasks[task_id].after]
    rank = {task_id: position for position, task_id in enumerate(ranked)}
    idle = float(len(ranked))
    # Taking a task another agent took duplicates the work, which never beats idling, whatever the conflict cost.
    duplicate = float(len(ranked) + 1)
    penalty = float(len(ranked) + 1) if conflict_cost is None else conflict_cost

    def clash(first: str, second: str) -> float:
        if first == second:
            return duplicate
        return penalty if conflict(graph.tasks[first], graph.tasks[second]) else 0.0

    def cost(choice: str | None, others: list[str | None]) -> float:
        if choice is None:
            return idle
        return rank[choice] + sum(clash(choice, other) for other in others if other is not None)

    choices: list[str | None] = []
    options = [None, *ranked]
    for _ in range(agents):
        choices.append(min(options, key=lambda option: (cost(option, choices), rank.get(option, idle))))
    changed, rounds = True, 0
    while changed:
        changed, rounds = False, rounds + 1
        for agent in range(agents):
            others = choices[:agent] + choices[agent + 1:]
            best = min(options, key=lambda option: (cost(option, others), rank.get(option, idle)))
            if cost(best, others) < cost(choices[agent], others):
                choices[agent], changed = best, True
    interactions = sum(
        clash(choices[first], choices[second])
        for first in range(agents)
        for second in range(first + 1, agents)
        if choices[first] is not None and choices[second] is not None
    )
    potential = sum(idle if choice is None else rank[choice] for choice in choices) + interactions
    return {
        "agents": agents,
        "assignment": [
            {"agent": agent, "task": choice, "cost": cost(choice, choices[:agent] + choices[agent + 1:])}
            for agent, choice in enumerate(choices)
        ],
        "potential": potential,
        "rounds": rounds,
        "equilibrium": True,
    }


# MARK: - Output


def _describe(task: Task, inherited: str | None) -> str:
    parts = [task.kind]
    if task.queued is not None:
        parts.append(f"queued {task.queued}")
    if inherited:
        parts.append(f"moved up for {inherited}")
    title = f" {task.title}" if task.title else ""
    return f"{task.id}{title} ({', '.join(parts)})"


def render(graph: Graph, arguments: argparse.Namespace) -> str:
    if arguments.assign:
        result = assign(graph, arguments.agents, arguments.policy, arguments.conflict_cost)
        if arguments.format == "json":
            return json.dumps(result, indent=2)
        lines = [f"agent {row['agent'] + 1}: {row['task'] or 'idle'}" for row in result["assignment"]]
        return "\n".join(lines + [f"Nash equilibrium after {result['rounds']} rounds; potential {result['potential']:g}"])
    if arguments.agents > 1:
        result = schedule(graph, arguments.agents, arguments.policy)
        if arguments.format == "json":
            return json.dumps(result, indent=2)
        lines = []
        for agent, lane in enumerate(result["lanes"]):
            steps = ", ".join(f"{step['id']} [{step['start']:g}-{step['end']:g}]" for step in lane) or "idle"
            lines.append(f"agent {agent + 1}: {steps}")
        lines.append(f"makespan {result['makespan']:g}; lower bound {result['lower_bound']:g}")
        return "\n".join(lines)
    ordered = order(graph, arguments.policy)
    _, source = priorities(graph, arguments.policy)
    if arguments.format == "json":
        return json.dumps(
            {
                "policy": arguments.policy,
                "order": [
                    {"id": task_id, "tier": graph.tasks[task_id].tier, "moved_up_for": source[task_id]}
                    for task_id in ordered
                ],
            },
            indent=2,
        )
    return "\n".join(
        f"{position}. {_describe(graph.tasks[task_id], source[task_id])}"
        for position, task_id in enumerate(ordered, start=1)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Order tasks: validity first, then first in, first out, with dependencies respected.",
        epilog="See the module docstring for the task fields and the theory behind each option.",
    )
    parser.add_argument("--tasks", action="append", default=[], help="a JSON file of tasks, or - for stdin")
    parser.add_argument("--task", action="append", default=[], help="one task as key=value pairs")
    parser.add_argument("--policy", choices=POLICIES, default="fifo")
    parser.add_argument("--agents", type=int, default=1)
    parser.add_argument("--assign", action="store_true", help="the next task for each agent, as a Nash equilibrium")
    parser.add_argument("--conflict-cost", type=float, default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    arguments = parser.parse_args(argv)
    try:
        documents = []
        for path in arguments.tasks:
            if path == "-":
                documents.append(json.load(sys.stdin))
            else:
                with open(path, encoding="utf-8") as handle:
                    documents.append(json.load(handle))
        tasks = load_tasks(documents, arguments.task)
        if not tasks:
            raise InputError("no tasks: pass --tasks FILE or --task key=value,...")
        print(render(Graph(tasks), arguments))
    except (InputError, json.JSONDecodeError, OSError) as error:
        print(f"order_tasks: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

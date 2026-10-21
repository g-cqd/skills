---
name: performance-engineering
description: >-
  Language-agnostic: profile and benchmark CPU, memory, latency, throughput, caching, data
  layout, atomics, and scheduling. Use when code is slow, latency spikes, parallel speedup
  disappoints, the UI hangs with idle CPU, or a change claims better performance. For
  algorithm selection, use `algorithms`; for SwiftUI rendering, use `swiftui`; for GPU
  work, use `graphics`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Performance Engineering

**Do not optimize without a measurement that shows the bottleneck and a second measurement that
shows the gain.** An unmeasured change adds complexity for a gain nobody can demonstrate. If you
cannot measure (no profiler, no access to the workload), do not make the change; report it as a
hypothesis with the measurement that would confirm it.

This skill covers making code faster, with proof. §1–4 are the method; §5–8 describe the hardware
behaviour that the method measures.

## Contract

```
§MEASURE  profile ≻ read-code ⇒ bottleneck ∷ where-measurement-says
§CLAIM    ∀perf-claim ! before/after numbers + units ∨ ⇒ ¬claim
§ORDER    ¬do-work ≻ do-less ≻ do-elsewhere ≻ parallel ≻ micro-optimize
§TAIL     percentiles ≻ averages ⇒ p95|p99 · ? coordinated-omission
§GOALS    ¬trade correctness|safety for speed (`AGENTS.md` CONFLICT rule 1: safety and correctness outrank speed)
§BAN      unmeasured-optimization · best-run-reporting · debug-build-benchmark ·
          microbenchmark ≠ production-access-pattern
```

---

## 1. Define

- State the symptom, the workload, the environment, and a target metric with a budget: "p99 <
  200 ms at 500 RPS", "Cold start < 1.5 s". The budget is the stop condition. If the user gives
  none, state the budget you assume in the report.
- Report percentiles (p95, p99), not averages. An average hides the tail.
- Check for coordinated omission. A load generator that waits for a slow response before it sends
  the next request does not measure the queue it created. Measure latency from the intended start
  time, not the actual send time.

## 2. Measure

- Reproduce under realistic load and realistic data volume. A cache that fits at test scale and
  not at production scale reverses the conclusions.
- Triage with **USE** per resource (Utilization, Saturation, Errors, across CPU, memory, disk,
  network) and **RED** per service (Rate, Errors, Duration).
- Locate the bottleneck with a profile, not by reading code: CPU profile and flame graph,
  allocation profile, I/O and query traces.

## 3. Fix — the order of attack

Try the levels in this order; stop when the budget from §1 is met.

1. **Do not do the work**: cache, dedupe, precompute, lazy-load, exit early.
2. **Do less work**: a better algorithm or data structure (`algorithms`), batched round trips (the
   N+1 query), a smaller payload.
3. **Do the work elsewhere or later**: async, background, off the critical path.
4. **Do the work in parallel.** Amdahl's law limits the gain to the parallelizable fraction.
   Compute that ceiling before you parallelize: a 90%-parallel workload caps at 10× for any core
   count.
5. **Micro-optimize last**: data layout, allocation pressure, SIMD (§5–6). Do this only on a hot
   path that the profiler shows.

## 4. Verify and guard

- Re-measure the same metric under the same workload. Report before and after, with units.
- Before you claim a speedup, confirm that both numbers came from the same harness, the same
  inputs, and the same build configuration. Numbers from different setups compare the setups, not
  the change.
- Re-check the resources from the §2 triage for regressions, memory as well as time; a
  memory-for-CPU trade is the most frequent hidden regression.
- When the repository already runs benchmarks in CI, add a benchmark with a baseline there.
  Otherwise, add the benchmark to the repository and state in the report that it is not run
  automatically.

### Benchmarking discipline

- Warm up, then run repeated iterations. Report the median and the spread, not the best run.
- Fix the inputs, isolate machine state, and pin versions.
- Use a microbenchmark only when its access pattern matches production.

On a machine shared with other agents:

- **Run the benchmark through `work`** (`planner`'s `scripts/work.py`).
- **Interleave A and B in one job** (ABAB…, several rounds) at weight 1 or 2. Both sides see the
  same background load, so the load cancels out of the ratio. Report the ratio with the medians
  and the load the machine was under.
- **Prefer CPU time to wall time** where the harness can read it (thread or process CPU time).
  Contention stretches wall time more than CPU time. Instruction and cycle counts
  (`/usr/bin/time -l`, `perf stat`) are more stable still.
- **One exclusive run per task, at most:** `--weight` equal to the CPU count, and only for an
  absolute number the report must state, such as a budget in milliseconds. Take each absolute
  figure in the report from that one run. Do not use the exclusive run as an iteration step or
  loop it over rounds.

Compare like with like: same data, same build configuration, **release mode**.

- **Iterate on the code in debug; measure only in release.** Build release once per task, in its
  own `--scratch-path` (`.build-release`). Alternating debug and release in one `.build` rebuilds
  the package at each switch, for up to 14 minutes.
- **Put A and B in one binary** where the old path can stay: a runtime switch (an environment
  variable) selects it, so one release build measures both sides. Otherwise build the baseline
  once, keep it, and do not rebuild it.
- **Rerun a benchmark from the existing build** (`swift run -c release --scratch-path
  .build-release --skip-build …`) unless sources changed.

---

## 5. The machine — latency orders of magnitude

One cache miss costs about 100 arithmetic operations; one context switch costs thousands. Before
you treat slowness as CPU-bound, check whether it is memory-bound (§9).

## 6. Data layout and the cache

- **The cache line is the unit of transfer**: 64 bytes on x86-64 and most ARM, **128 bytes on
  Apple silicon**. Touching one byte loads the whole line.
- **Spatial locality**: iterate contiguously. In hot loops, prefer arrays to pointer-linked
  structures; each linked node can cost a cache miss.
- **Alignment and padding**: order struct fields by decreasing alignment to minimize padding.
  Confirm with the language's layout introspection, not by reading the declaration.
- **False sharing**: two threads that write different variables in the same cache line serialize
  on coherence traffic. Symptom: parallel speedup far below core count with low lock contention.
  Fix by padding or aligning hot per-thread data to a line.
- **Prefetching** works for linear or strided access, not random access. Sort indices before a
  gather where the algorithm allows.
- **TLB**: random access over a working set larger than the TLB covers pays page-walk costs.
  Improve locality.

## 7. What the core rewards

- **Branch prediction**: a predictable branch costs almost nothing; a mispredict costs ~10–20
  cycles. Before you write branchless code, sort the data to make branches predictable. Write
  branchless code only when the profiler shows mispredicts.
- **Speculative execution** leaks through cache side channels (Spectre class). When sandboxing
  untrusted code or handling secrets, use constant-time comparison and no secret-dependent
  branches or indices. See `secure-coding`.

## 8. Atomics, ordering, and scheduling

### Atomics

A **data race** (unsynchronized conflicting access with at least one write) is undefined behavior
in C, C++, and Swift, not a stale read.

Default to locks or `seq_cst` ordering. Use a weaker order only with a stated invariant and a
measured need.

**Contended atomics move cache lines between cores on each write.** Use sharded counters or
per-thread accumulation instead of one hot atomic. Lock-free code is not automatically faster: it
trades throughput under contention for progress guarantees, and adds ABA and memory-reclamation
complexity. Use a well-tested mutex until measurement shows it is the bottleneck.

### Scheduling and threads

- **Thread pools**: size to about the core count for CPU-bound work. Oversubscription ("thread
  explosion") costs memory (megabytes of stack per thread) and evicts caches. Run I/O-bound work on
  async I/O, not on extra threads.
- **Priorities and QoS** steer work. On Apple platforms, QoS classes also select **heterogeneous
  cores**: background QoS may run on efficiency cores, user-interactive favors performance cores.
  Assign the QoS that matches the work; a wrong QoS is a performance bug.
- **Priority inversion**: a low-priority holder blocks a high-priority waiter. Mutexes with
  priority inheritance bound it. **Semaphores and condition-variable waits record no owner, so the
  kernel cannot boost the holder.** This causes the hang seen when async code is bridged with a
  semaphore.
- **Context switches**: batch work per wakeup, coalesce timers, and do not hand off work items
  shorter than a context switch (§5) between threads.
- **Work-stealing runtimes** hand off work cheaply, but **blocking a pool thread** with sync I/O, a
  semaphore wait, or a long lock hold starves the pool. Give blocking calls a dedicated thread or
  an async equivalent.

## 9. Symptom → suspect

| Symptom | Suspect | Confirm with |
|---|---|---|
| Parallel speedup ≪ cores, locks look fine | False sharing | Per-line counters — `perf c2c`, Instruments |
| Slowness scales with data size, CPU% flat | Cache/memory bound | Miss counters, bandwidth profile |
| Random latency spikes under load | Oversubscription, priority issues | Scheduler or System Trace |
| UI hangs while CPU is idle | Priority inversion, blocked pool | Wait-state trace, lock-holder stacks |
| Fast single-threaded, slow multi-threaded | Contended atomic or lock line ping-pong | Contention profiler |

---

## Boundaries

| Need | Skill |
|---|---|
| Algorithm and data-structure selection, complexity analysis | `algorithms` |
| SwiftUI rendering, hitches, invalidation storms | `swiftui` |
| GPU profiling, shader optimization | `graphics` |
| Swift concurrency performance and isolation cost | `swift` |
| Capturing traces from the Apple toolchain | `xcode` |
| Infrastructure capacity and observability | `system-architect` |
| Performance-audit execution contract | `planner` |
| Constant-time comparison and side-channel handling | `secure-coding` |
| Benchmarks as tests, CI baselines | `testing` |

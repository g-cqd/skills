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

**No optimization without a measurement showing the bottleneck, and a second measurement proving
the fix.** Intuition about where time goes is wrong more often than it is right, and an unmeasured
change adds complexity for a gain nobody can demonstrate.

This skill owns **making it fast, provably**. Sections 1–4 are the method; §5–8 are the machine
the method measures. They are one concern: you cannot form a useful hypothesis about a profile
without knowing what the hardware rewards.

## Contract

```
§MEASURE  profile ≻ read-code ⇒ bottleneck ∷ where-measurement-says
§CLAIM    ∀perf-claim ! before/after numbers + units ∨ ⇒ ¬claim
§ORDER    ¬do-work ≻ do-less ≻ do-elsewhere ≻ parallel ≻ micro-optimize
§TAIL     percentiles ≻ averages ⇒ p95|p99 · ? coordinated-omission
§GOALS    ¬trade correctness|safety for speed (§CONFLICT rule 1)
§BAN      unmeasured-optimization · best-run-reporting · debug-build-benchmark ·
          microbenchmark ≠ production-access-pattern
```

---

## 1. Define

State the symptom, the workload, the environment, and **a number**: target metric plus budget.
"p99 < 200 ms at 500 RPS." "Cold start < 1.5 s." Without a budget there is no such thing as fast
enough, and the work never ends.

**Percentiles, not averages.** Users experience the tail. An average hides the p99 entirely.

**Beware coordinated omission** — a load generator that waits for a slow response before sending
the next request stops measuring the queue it created. Measure from the *intended* start time, not
the actual send time, or the tail silently disappears from the data.

## 2. Measure

- Reproduce under realistic load **and realistic data volume**. A cache that fits at test scale
  and not at production scale inverts every conclusion.
- Triage with **USE** per resource — Utilization, Saturation, Errors, across CPU, memory, disk,
  network — and **RED** per service — Rate, Errors, Duration.
- **Profile before reading code.** CPU profile and flame graph, allocation profile, I/O and query
  traces. The bottleneck is where measurement says it is, and that is usually not where intuition
  says.

## 3. Fix — the order of attack

Highest leverage first. Most real wins come from the first two.

1. **Don't do the work** — cache, dedupe, precompute, lazy-load, early-exit.
2. **Do less work** — a better algorithm or data structure (`algorithms`), batch the round trips
   (the N+1 query), shrink the payload.
3. **Do the work elsewhere or later** — async, background, off the critical path.
4. **Do the work in parallel** — **Amdahl's law bounds the win** to the parallelizable fraction.
   Compute that ceiling *before* parallelizing; a 90%-parallel workload caps at 10× no matter how
   many cores you add.
5. **Micro-optimize last** — data layout, allocation pressure, SIMD (§5–6). Only with profiler
   evidence, only on hot paths.

## 4. Verify and guard

- Re-measure **the same metric under the same workload**. Report before and after, with units.
  Before claiming a speedup, confirm that both numbers came from the same harness, the same
  inputs, and the same build configuration; a before/after pair from different setups compares
  setups, not the change.
- Check for regressions elsewhere — memory-versus-CPU trades are the common surprise.
- Add a benchmark to CI with a baseline, so the win cannot silently rot.

### Benchmarking discipline

Warm up. Run many iterations. Report **median and spread**, never the best run. Fix the inputs,
isolate machine state, pin versions. Run the benchmark through `work` (`planner`'s `scripts/work.py`).
While iterating, compare before and after by interleaving A and B runs in one job (ABAB…) at weight
2 or 3: both sides see the same background load, so it cancels out. Keep an exclusive run (`--weight`
equal to the CPU count, so no other agent's job loads the machine) for the final numbers a report
states: one per task, not one per iteration, since each drains the machine.
Compare like with like — same data, same build configuration,
**release mode**. Iterate on the code in debug; build release once per measurement round, in its
own `--scratch-path` (`.build-release`): alternating debug and release builds in one `.build`
rebuilds the package at each switch, for up to 14 minutes. Rerun a benchmark from the existing
build (`swift run -c release --scratch-path .build-release --skip-build …`) unless sources changed.
A microbenchmark whose access pattern differs from production is fiction that
will confidently mislead you.

---

## 5. The machine — latency orders of magnitude

Carry this table in your head. It is the basis of every performance intuition worth having.

| Operation | ~Cost | vs L1 |
|---|---|---|
| L1 cache hit | ~1 ns | 1× |
| L2 hit | ~4 ns | ~4× |
| L3 hit | ~10–40 ns | ~10–40× |
| Main memory (DRAM) | ~60–120 ns | ~100× |
| Atomic RMW, contended | ~10–100+ ns | varies with sharing |
| Context switch | ~1–10 µs | ~10⁴× |
| NVMe read | ~10–100 µs | ~10⁵× |
| Same-datacenter RTT | ~100–500 µs | ~10⁵–10⁶× |

One cache miss costs about 100 arithmetic operations; one context switch costs thousands.
**Most "CPU-bound" slowness is actually memory-bound.**

## 6. Data layout and the cache

- **The cache line is the unit of transfer** — 64 bytes on x86-64 and most ARM, **128 bytes on
  Apple silicon**. Touching one byte loads the whole line.
- **Spatial locality** — iterate contiguously. Prefer arrays to pointer-rich graphs in hot loops;
  a linked list is a cache-miss generator.
- **AoS vs SoA** — when a hot loop reads one field across many records, structure-of-arrays packs
  useful data per line. This is why ECS designs and columnar databases are fast.
- **Alignment and padding** — order struct fields by decreasing alignment to minimize padding.
  Confirm with the language's layout introspection rather than by eye.
- **False sharing** — two threads writing *different* variables that share a cache line serialize
  on coherence traffic. **Symptom: parallel speedup far below core count with low lock
  contention.** Fix by padding or aligning hot per-thread data to a line.
- **Prefetching** rewards predictable access — linear or strided. Random access defeats it; sort
  indices before gathering where you can.
- **TLB** — large working sets with random access pay page-walk costs. Locality helps here too.

## 7. What the core rewards

- **Branch prediction** — predictable branches are nearly free; a mispredict costs ~10–20 cycles.
  Sorting data to make branches predictable often beats going branchless. Go branchless only when
  the profiler shows mispredicts.
- **ILP and out-of-order execution** — independent operations overlap; long dependency chains
  (pointer chasing, a serial reduction) stall. Split reductions into parallel accumulators.
- **SIMD** — data-parallel loops over contiguous data vectorize. Branches and gathers break
  vectorization.
- **Speculative execution** leaks through cache side channels (Spectre class). This matters when
  sandboxing untrusted code or handling secrets: constant-time comparison, no secret-dependent
  branches or indices. See `secure-coding`.

## 8. Atomics, ordering, and scheduling

### Atomics

A **data race** — unsynchronized conflicting access with at least one write — is *undefined
behavior* in C, C++, and Swift. It is not "just a stale read".

Ordering strength: `relaxed` (atomicity only) < `acquire`/`release` (pairwise happens-before; a
release store publishes to an acquire load) < `seq_cst` (one total order). Default to locks or
`seq_cst`; weaken only with a stated invariant and a demonstrated need.

**Contended atomics ping-pong cache lines.** Sharded counters or per-thread accumulation beat one
hot atomic. And **lock-free is not the same as fast** — it trades throughput under contention for
progress guarantees, plus ABA and memory-reclamation complexity. Prefer a well-tested mutex until
measurement says otherwise.

### Scheduling and threads

- **Preemptive scheduling** — more runnable threads than cores means queueing plus
  context-switch overhead.
- **Thread pools** — size to roughly the core count for CPU-bound work. Oversubscription
  ("thread explosion") burns memory (megabytes of stack each) and thrashes caches. I/O-bound work
  belongs on async I/O, not on extra threads.
- **Priorities and QoS** steer work; on Apple platforms QoS classes also steer **heterogeneous
  cores** — background QoS may land on efficiency cores, user-interactive favors performance
  cores. Tag work honestly; a mislabeled QoS is a performance bug.
- **Priority inversion** — a low-priority holder blocks a high-priority waiter. Mutexes with
  priority inheritance bound it. **Semaphores and condition-variable waits convey no ownership, so
  the kernel cannot boost the holder** — that is the classic hang when bridging async code with a
  semaphore.
- **Context-switch hygiene** — batch work per wakeup, coalesce timers, avoid ping-pong handoffs
  for tiny work items.
- **Work-stealing runtimes** keep cores busy with cheap handoff, but **blocking a pool thread**
  with sync I/O, a semaphore wait, or a long lock hold starves the pool. Blocking calls get a
  dedicated thread or an async equivalent.

## 9. Symptom → suspect

| Symptom | Suspect | Confirm with |
|---|---|---|
| Parallel speedup ≪ cores, locks look fine | False sharing | Per-line counters — `perf c2c`, Instruments |
| Slowness scales with data size, CPU% flat | Cache/memory bound | Miss counters, bandwidth profile |
| Random latency spikes under load | Oversubscription, priority issues | Scheduler or System Trace |
| UI hangs while CPU is idle | Priority inversion, blocked pool | Wait-state trace, lock-holder stacks |
| Fast single-threaded, slow multi-threaded | Contended atomic or lock line ping-pong | Contention profiler |

## 10. Rationalizations that waste weeks

| If you think… | Reality |
|---|---|
| "This is obviously the slow part" | Profile it. Intuition is wrong more often than not |
| "This optimization can't hurt" | Unmeasured optimizations add complexity and bugs for ~0 gain |
| "Average latency looks fine" | Your p99 users are timing out |
| "We'll add metrics later" | Without a baseline you can never prove an improvement |

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

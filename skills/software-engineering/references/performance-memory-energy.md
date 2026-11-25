# High Performance, Memory Efficiency & Energy Engineering

## Contents
- [1. Authoritative Rubrics & Budgets](#1-authoritative-rubrics--budgets)
- [2. Four-Round Audit Methodology](#2-four-round-audit-methodology)
- [3. Algorithmic Complexity & Data-Structure Discipline](#3-algorithmic-complexity--data-structure-discipline)
- [4. Hardware, Cache, SIMD & Metal Patterns](#4-hardware-cache-simd--metal-patterns)
- [5. Memory Footprint, UMA & Leak Prevention](#5-memory-footprint-uma--leak-prevention)
- [6. Energy Efficiency, Wakeups & Thermal Adaptation](#6-energy-efficiency-wakeups--thermal-adaptation)
- [7. Reproducible Benchmarking Protocol](#7-reproducible-benchmarking-protocol)

---

## 1. Authoritative Rubrics & Budgets

| Rubric / Authority | Pillar | Concrete Standard |
|---|---|---|
| **LMAX Mechanical Sympathy** | Latency & throughput | Zero-allocation hot paths, cache-line alignment (`64 B` x86/ARM, `128 B` Apple Silicon), single-writer/lock-free pipelines, ring buffers, zero false sharing, zero accidental CoW churn |
| **Gil Tene (HdrHistogram)** | Tail latency | Report `p50`, `p95`, `p99`, `p99.9`, max (never averages alone); eliminate coordinated omission and UI/event-loop stalls |
| **NASA JPL / RTCA DO-178C** | Determinism & WCET | Explicit input, depth, node, and memory caps; zero unbounded recursion or O(n²) blowups on large or adversarial inputs |
| **Brendan Gregg (USE / RED)** | OS & syscall health | Triage Utilization, Saturation, Errors across CPU, RAM, disk I/O, syscalls, context switches (`CSW`), page faults, lock contention |
| **SPEC** | Benchmark rigor | Cold vs warm separation, pinned versions, load-average recording, median + spread (never cherry-pick best run) |
| **ARM NEON / Agner Fog** | SIMD & microarch | Roofline bandwidth vs ALU analysis, SWAR short-run front-ends before SIMD dispatch, branchless inner loops, scalar reference parity |
| **Apple Platform / Metal / Energy & Green Software SCI** | Apple Silicon & battery | ProMotion 120 Hz budget **8.33 ms** (60 Hz: 16.67 ms); CLI cold start `< 50 ms`, TUI `< 100 ms`; **0 idle wakeups/s** (`< 1/s`); UMA `phys_footprint` minimization; reactive memory pressure; E-core QoS; Low Power Mode & thermal adaptation |

---

## 2. Four-Round Audit Methodology

Run all four rounds whenever auditing or optimizing so speedups never silently regress memory or battery:

1. **Round 1 — Latency, Throughput & Algorithms:** Measure cold start, warm throughput, and `p95`/`p99` on realistic large inputs. Hunt O(n²) loops (re-parsing streaming buffers from byte 0 instead of incremental editing, repeated `realpath`/`lstat` without directory-prefix caching, linear scans inside frame loops), main-thread SQLite/disk/crypto, runtime MSL shader compilation, and repeated `xcrun`/`sysctl` subprocess lookups.
2. **Round 2 — Physical Memory Footprint:** Measure `phys_footprint` / `footprint` (macOS) or `Max RSS` / `PSS` (Linux) at idle, realistic peak, and post-drain. Hunt unbounded caches/histories/scrollback/link tables, retained ASTs, full-res offscreen bitmaps/snapshots, per-pane duplicated GPU atlases, CoW copies across actors, missing memory-pressure eviction, and retain/FD leaks.
3. **Round 3 — Energy, Wakeups & Thermal:** Measure idle CPU%, idle wakeups (`IDLEW`), `CSW/s`, power assertions (`pmset -g assertions`), and timer/poll cadence (`top`, `sample`, Instruments Energy Log, `strace -c`). Hunt sub-10 ms spin-poll loops (100–500 Hz `usleep`/`Task.sleep`), unpaused `CADisplayLink`/shimmer/snapshots when occluded or unfocused, background work pinned to P-cores (`.userInitiated` instead of `.utility`/`.background`), and permanent `PRIO_DARWIN_ROLE_UI_FOCAL`.
4. **Round 4 — Isolated Dynamic Verification:** Measure strictly on isolated scratch copies in `-c release` builds. Refute, refine, or upgrade every static hypothesis with measured before/after numbers; explicitly tag any unmeasured claim `[static hypothesis — unmeasured]`.

---

## 3. Algorithmic Complexity & Data-Structure Discipline

- **Define `n` precisely** (and `m`, `k` for multi-dimensional workloads) before accepting any nested loop, non-O(1) call inside a loop, recursion, or growing collection.
- **Justify at realistic scale:** O(n²) at `n ≤ 100` may beat a hash map due to cache locality; at `n = 10⁶` or attacker-controlled `n`, it is a DoS vector.
- **No backtracking regexes on untrusted input:** use linear-time non-backtracking regex engines (RE2 / I-Regexp automata) with compile-time limits; never run backtracking regexes (`NSRegularExpression`) with dot-all quantifiers on untrusted XML/HTML/logs.
- **Iterative over recursive:** use an explicit stack for tree/AST/DOM/JSON/HTML walks; if recursion is strictly cleaner on a bounded tree, enforce an explicit `maxDepth` check and test `maxDepth + 1`.
- **Loop invariants & boundaries:** verify empty input, 1 element, full range, duplicates, and integer overflow on every index calculation.
- **Proof for greedy algorithms:** write the exchange argument; without one, label it a heuristic.

---

## 4. Hardware, Cache, SIMD & Metal Patterns

**Attack order (stop when the numeric budget is met):**
`1. Do not do the work (skip/cache/lazy/precompute) ≻ 2. Do less work (algorithm/batching) ≻ 3. Do it elsewhere/later (async/background) ≻ 4. Parallelize (check Amdahl ceiling) ≻ 5. Micro-optimize (layout/SIMD)`.

- **Cache lines & locality:** 128 B on Apple Silicon, 64 B on x86-64/most ARM. Prefer contiguous arrays (`ContiguousArray`, flat tapes, struct-of-arrays) over pointer-chasing trees/linked lists in hot loops. Order struct fields by decreasing alignment to minimize padding; verify with `MemoryLayout<T>.size` and `.stride`.
- **False sharing:** pad or align per-thread/per-core counters to 128 B on Apple Silicon when updated concurrently.
- **SWAR & NEON SIMD kernels:** handle short slices (< 16–32 B) with scalar/SWAR fast paths before entering NEON/SIMD loops; keep C kernels strictly bounds-checked, ASan/UBSan clean, and differentially tested against scalar reference implementations.
- **Metal & GPU efficiency:**
  - Precompile `.metal` to `.metallib` at build time (hundreds of milliseconds saved on first pane).
  - Share one `MTLDevice`, `MTLCommandQueue`, pipeline cache, and glyph/texture atlas across views; ring-buffer per-frame `MTLBuffer`s.
  - Replace thousands of micro-quads (e.g., curly underlines) with single-quad procedural fragment shaders; set unused attachment `storeAction = .dontCare`.
- **SQLite & persistence:** never run SQLite transactions on `@MainActor`; prepare and cache `sqlite3_stmt`s, batch writes in explicit transactions, enable WAL mode, and drop redundant indexes whose write amplification outweighs read gain.

---

## 5. Memory Footprint, UMA & Leak Prevention

On Apple Unified Memory Architecture (UMA), GPU textures, offscreen snapshots, and CPU buffers share the same physical RAM ceiling (`phys_footprint`).

- **Bound every growing structure:** cap scrollback, transcript history, finished job lists, link/cluster tables (add periodic compaction when entries drop off scrollback), LSP open-document maps, and thumbnail caches (`NSCache` with byte cost limits).
- **Avoid full-res offscreen snapshots:** capture thumbnails lazily (on tab leave/hover, never on a 2 s background timer), downscale at capture time (`snapshotWidth = 400`), and store compressed JPEG/HEIF in a bounded cache.
- **Release temporary build/compile spikes:** wrap bulk compilation or parsing loops (e.g., content-blocker rule compilation, large imports) in `autoreleasepool { ... }` on `.background` QoS so peak allocations return immediately.
- **React to OS memory pressure:** wire `DispatchSource.makeMemoryPressureSource` (warning/critical) to evict caches, purge unloaded tab snapshots, and compact tables automatically.
- **Prevent ARC & resource leaks:** run runtime leak tools (`leaks`, heap profilers) and static retain-cycle / resource-obligation analyzers on release binaries; close file descriptors in `defer`; avoid capturing `self` strongly in timers, notification observers, and async tasks.

---

## 6. Energy Efficiency, Wakeups & Thermal Adaptation

- **Zero idle work:** when the app or CLI is waiting for user input or external I/O, CPU usage must be `0.0%` and idle wakeups `0/s`.
- **Replace polling with events:** replace `usleep(2000)` / 1 Hz / 250 ms polling loops with `kqueue` / `DispatchSourceFileSystemObject`, `AsyncStream` continuations, `Process.terminationHandler`, or condition notifications.
- **Pause when invisible:** stop `CADisplayLink`, cursor blink (e.g., after 15 s idle), shimmer animations, and background tab snapshots when the window is occluded, minimized, or unfocused (`NSWindow.occlusionState`, `NSApp.isActive`).
- **QoS & E-cores:** run indexing, rule-list compilation, backups, and update staging at `.utility` or `.background` QoS so macOS schedules them on Efficiency cores; drop `PRIO_DARWIN_ROLE_UI_FOCAL` when unfocused.
- **Power & thermal awareness:** observe `ProcessInfo.processInfo.isLowPowerModeEnabled` and `thermalState` (`.serious` / `.critical`) to cap frame rates (120 Hz → 60 Hz), disable decorative EDR/blur/shimmer effects, and defer non-essential background work. Keep power assertions (`IOPMAssertion`) narrowly scoped so App Nap engages.

---

## 7. Reproducible Benchmarking Protocol

1. **Iterate in debug; measure only in release.** Keep release builds in a separate scratch path (`swift build -c release --scratch-path .build-release`) so debug and release builds never thrash `.build`.
2. **One release build per task:** where the old path can stay, put A and B behind a runtime switch in the **same binary** and interleave rounds (`ABABAB…`) so background load cancels out of the ratio.
3. **Rerun without rebuilding:** use `swift run -c release --scratch-path .build-release --skip-build ...` when sources did not change.
4. **Report full context:** always report **median + spread (p95 / min–max)**, sample count `N`, units, hardware model, build mode, and system load average. Prefer process CPU time and instruction/cycle counts (`/usr/bin/time -l`, `perf stat`) alongside wall time; reserve exclusive full-machine runs for final absolute budget verification (e.g., cold start, idle/active RSS, input delay, action-to-action latency over a PTY).
5. **Cross-pillar check:** every optimization report explicitly states whether RAM, tail latency, or energy/wakeups changed alongside throughput.

# Four-Round Performance, Memory & Energy Audit Methodology

Use this reference when running a comprehensive **performance, efficiency, memory, and energy audit**
(not just a single micro-optimization). Structure audits into **four rounds** so CPU speedups never
silently regress physical memory footprint, tail latency, or battery life.

## Authoritative Rubrics & Reference Baselines

Unlike security (governed by national agencies like NIST, NSA, ANSSI, NCSC), high-performance and
efficiency engineering draws from hardware architects, ultra-low-latency systems engineering,
OS/microarchitecture authorities, and platform guides:

| Authority / Rubric | Pillar | Concrete Standards & Targets |
|---|---|---|
| **LMAX / Mechanical Sympathy (Martin Thompson, Aeron / Agrona)** | Latency & Throughput | Zero-allocation hot paths, cache-line awareness (`64 B` x86/ARM, `128 B` Apple Silicon), single-writer / lock-free pipelines, zero false sharing, bounded ring buffers, slab/pool reuse, zero accidental CoW copies or per-iteration heap churn. |
| **Gil Tene / Azul Systems (HdrHistogram & Coordinated Omission)** | Tail Latency | Full latency distributions (`p50`, `p95`, `p99`, `p99.9`, max) rather than averages alone; eliminate coordinated omission and stop-the-world stalls on event loops and UI threads. |
| **NASA JPL / RTCA DO-178C (Bounded Real-Time Determinism)** | Worst-Case & Safety | Bounded worst-case execution time (WCET), explicit memory/depth/node caps, zero unbounded recursion or O(n²) blowups on large or adversarial inputs. |
| **Brendan Gregg (*Systems Performance*, USE Method)** | OS, I/O & Syscalls | Utilization, Saturation, Errors across CPU, memory, disk I/O, syscalls, context switches (`CSW`), page faults, lock contention, and allocator overhead. |
| **SPEC (Standard Performance Evaluation Corporation)** | Benchmark Rigor | Reproducible harnesses, warm vs. cold separation, thermal-throttling isolation, load-average recording, median + spread reporting (never cherry-picking best runs). |
| **ARM NEON / Roofline & Agner Fog** | SIMD & Microarchitecture | Vectorization throughput vs. memory-bandwidth roofline, branch-mispredict elimination, alignment, SWAR front-ends for short runs before SIMD kernel dispatch, differential parity against scalar references. |
| **Apple Platform Performance, Metal & Energy Efficiency Guides** | macOS / iOS / Apple Silicon | ProMotion 120 Hz frame budget (**8.33 ms** CPU+GPU); zero main-thread disk/SQLite/shader stalls; precompiled `.metallib` & shared device/queue/atlases; `phys_footprint` minimization on Unified Memory (UMA); reactive `DispatchSource.makeMemoryPressureSource`; **0 idle wakeups/s** (`< 1/s`); timer coalescing; `.utility`/`.background` QoS for E-cores; honor `ProcessInfo.isLowPowerModeEnabled` & `thermalState`; narrow power assertions so App Nap engages. |
| **W3C Web Performance / RAIL, ISO/IEC 25010 & Green Software Foundation (SCI)** | Responsiveness & Efficiency | Cold CLI startup `< 50 ms`, TUI `< 100 ms`, input-to-photon `< 8.33 ms`; bounded resource utilization under stress; minimal wasted compute, spin-polling, and energy per unit of useful work (Software Carbon Intensity). |

## The Four Audit Rounds

### Round 1 — Latency, Throughput, Frame Pacing & Algorithmic Efficiency
- Measure cold startup, warm steady-state throughput, and tail latency (`p95`/`p99`) on realistic, large inputs.
- Hunt O(n²) loops (repeated re-parsing from byte 0, repeated `realpath`/`stat` without prefix caching, unindexed linear scans, O(N) `precondition` inside hot/frame loops), main-thread synchronous I/O or SQLite/crypto, runtime shader compilation, and redundant subprocess/tool resolution (`xcrun`, `sysctl` per child).

### Round 2 — Memory Consumption & Physical Footprint
- Measure **physical footprint** (`ri_phys_footprint` / `footprint` on macOS; `Max RSS` via `/usr/bin/time -l` / `-v` or `VmRSS`/`PSS` on Linux) at idle, under realistic peak load, and post-drain.
- Hunt unbounded caches/maps (LSP open-document maps, history/scrollback buffers, ASTs retained past their analysis phase, full-resolution offscreen bitmaps/atlases), hidden Copy-on-Write (CoW) amplifications across tasks/actors, memory-pressure blindness, and retain cycles / descriptor leaks (`leaks`, `heap`, `arcleak`, `fcheck`).

### Round 3 — Energy Efficiency, Wakeups & Thermal Behavior
- Measure idle CPU%, idle wakeups (`IDLEW`), context switches (`CSW/s`), power assertions (`pmset -g assertions`), and timer/polling frequencies (`top`, `sample`, `powermetrics`, Instruments Energy Log; `strace -c` / `perf stat` on Linux).
- Hunt uncoalesced timers, sub-10 ms spin-poll loops (100–500 Hz `Task.sleep`/`usleep`), unpaused rendering or snapshots when occluded/unfocused, wrong QoS pinning background work onto P-cores, and missing Low Power Mode / thermal throttling.

### Round 4 — Dynamic Verification & Isolated Profiling
- Run **strictly on isolated copies** (scratch directory, isolated config/state/cache dirs, synthetic large fixtures — never touch live user apps or state).
- Verify static hypotheses with real release-build measurements (`-c release`), `/usr/bin/time -l` (macOS) or `/usr/bin/time -v` (Linux), `perf stat`, `footprint`, `sample`, `top`, `leaks`, and ASan/UBSan/TSan for C/SIMD or unsafe Swift paths.
- **Refute, refine, or upgrade** every static finding with measured numbers; explicitly tag any unmeasured claim as `[static hypothesis — unmeasured]`.

## Reporting Format

For each finding, record:
- **Priority (`P0`–`P3`)** and **Pillar** (`Latency` / `Memory` / `Energy`)
- **Location** (`file:line`) and **Rubric violated** (e.g. LMAX, Gil Tene, USE, NASA JPL Bounded Complexity, Apple Energy Guide, SPEC)
- **Measured baseline** (median + spread, units, hardware, build mode, load average) or explicit `[static hypothesis — unmeasured]` tag
- **Root cause** and **Smallest fix** following `SKILL.md` §3 (`¬do-work ≻ do-less ≻ do-elsewhere ≻ parallel ≻ micro-optimize`)
- **Cross-pillar check**: note any CPU-for-memory or memory-for-energy tradeoff.

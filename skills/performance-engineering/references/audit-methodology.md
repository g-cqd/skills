# Four-Round Performance, Memory & Energy Audit Methodology

Use this reference when running a full **performance audit** (not just a single micro-optimization).
Structure comprehensive audits into **four rounds** so CPU speedups never silently regress memory footprint or battery life.

## Authoritative Rubrics & Reference Baselines

Unlike security, performance engineering draws from hardware architects, low-latency systems engineering, and platform guides:

| Authority / Rubric | Pillar | Concrete Standards & Targets |
|---|---|---|
| **LMAX / Mechanical Sympathy (Martin Thompson)** | Latency & Throughput | Zero-allocation hot paths, cache-line awareness (`64 B` x86/ARM, `128 B` Apple Silicon), single-writer / lock-free pipelines, zero false sharing, bounded ring buffers, slab/pool reuse, zero accidental CoW copies. |
| **Gil Tene / Azul Systems (HdrHistogram)** | Tail Latency | Full latency distributions (`p50`, `p95`, `p99`, `p99.9`, max), never averages alone; detect and eliminate coordinated omission and stop-the-world stalls. |
| **NASA JPL / RTCA DO-178C Bounded Complexity** | Determinism & Worst-Case | Bounded worst-case execution time (WCET), explicit memory/depth/node caps, zero unbounded recursion or O(n²) blowups on adversarial or large real-world inputs. |
| **Brendan Gregg (*Systems Performance*, USE Method)** | OS & Syscalls | Utilization, Saturation, Errors across CPU, memory, disk I/O, syscalls, context switches (`CSW`), page faults, lock contention, and allocator churn. |
| **Apple Platform Performance, Metal & Energy Guides** | macOS / iOS / Apple Silicon | ProMotion 120 Hz frame budget (**8.33 ms** CPU+GPU); zero main-thread disk/SQLite/shader stalls; precompiled `.metallib` & shared device/queue/atlases; `phys_footprint` minimization on UMA; reactive `DispatchSource.makeMemoryPressureSource`; **0 idle wakeups/s** (`< 1/s`); QoS `.utility`/`.background` for E-cores; honor `ProcessInfo.isLowPowerModeEnabled` & `thermalState`; narrow power assertions so App Nap engages. |
| **ARM NEON / Roofline & Agner Fog** | SIMD & Microarchitecture | Vectorization throughput vs. memory bandwidth, branch-mispredict elimination, alignment, avoiding scalar fallback cliffs. |
| **W3C RAIL / ISO/IEC 25010 / Green Software Foundation (SCI)** | Responsiveness & Efficiency | Cold CLI/TUI startup budgets (`< 50 ms` CLI, `< 100 ms` TUI), input-to-photon `< 8.33 ms`, bounded resource utilization under stress, minimal wasted compute/polling/wakeups. |

## The Four Audit Rounds

### Round 1 — Latency, Throughput, Frame Pacing & Algorithmic Complexity
- Measure cold startup, warm steady-state throughput, and tail latency (`p95`/`p99`) on realistic, large inputs.
- Hunt O(n²) loops (repeated re-parsing, repeated `realpath`/`stat`, unindexed lookups, O(N) `precondition` inside per-frame or inner loops), synchronous I/O or lock contention on main/UI threads, and redundant subprocess/tool resolution (`xcrun`, `sysctl` per child).

### Round 2 — Memory Consumption & Physical Footprint
- Measure **physical footprint** (`ri_phys_footprint` / `footprint` on macOS; `VmRSS` / `PSS` / `/usr/bin/time -v` Max RSS on Linux) at idle, under realistic peak load, and post-GC/post-task drain.
- Hunt unbounded caches/collections (history buffers, AST/syntax trees retained past their phase, full-res offscreen bitmaps/atlases), hidden Copy-on-Write (CoW) amplifications across tasks/actors, memory-pressure blindness, and retain cycles / handle leaks (`leaks`, `heap`, `arcleak`).

### Round 3 — Energy Efficiency, Wakeups & Thermal Behavior
- Measure idle CPU%, idle wakeups (`IDLEW`), context switches (`CSW/s`), power assertions (`pmset -g assertions`), and timer/polling frequencies (`top`, `sample`, `powermetrics`, Instruments Energy Log; `strace -c` / `perf stat` on Linux).
- Hunt uncoalesced timers, sub-10 ms `usleep`/`Task.sleep` polling loops (500 Hz spin-polls), unpaused animations/rendering when occluded or unfocused, wrong QoS pinning background work onto P-cores, and missing Low Power Mode / thermal throttling.

### Round 4 — Dynamic Verification & Isolated Profiling
- Run **strictly on isolated copies** (scratch directory, isolated config/state/cache dirs, synthetic large fixtures — never touch live user apps or state).
- Verify static hypotheses with real measurements: release builds (`-c release`), `/usr/bin/time -l` (macOS) or `/usr/bin/time -v` (Linux), `perf stat`, `footprint`, `sample`, `top`, `leaks`, and ASan/UBSan/TSan where native C/SIMD or unsafe Swift is present.
- **Refute or upgrade** every static finding with measured numbers; drop any unconfirmed claim to a hypothesis.

## Reporting Format

For each finding, record:
- **Priority (`P0`–`P3`)** and **Pillar** (`Latency` / `Memory` / `Energy`)
- **Location** (`file:line`) and **Rubric violated** (e.g. LMAX, USE, Apple Energy Guide, Bounded Complexity)
- **Measured baseline** (median + spread, units, hardware, build mode, load average) or explicit `[static hypothesis — unmeasured]` tag
- **Root cause** and **Smallest fix** following `SKILL.md` §3 (`¬do-work ≻ do-less ≻ do-elsewhere ≻ parallel ≻ micro-optimize`)
- **Cross-pillar check**: note any CPU-for-memory or memory-for-energy tradeoff.

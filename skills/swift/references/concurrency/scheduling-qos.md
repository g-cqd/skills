# Darwin Scheduling, QoS & the Swift Concurrency Runtime

How Swift concurrency maps onto the OS scheduler — and the blocking/priority
mistakes that cause hangs. Conceptual background: `threading.md` (cooperative
pool basics) and the `performance-engineering` skill (general scheduling theory).

## QoS Classes (Darwin)

| QoS | Meaning | Core steering (Apple Silicon) |
|-----|---------|-------------------------------|
| `userInteractive` | Main-thread/UI work, animations | P cores |
| `userInitiated` | User waits for the result | P cores |
| `default` | In between | Either |
| `utility` | Progress-bar work, I/O, downloads | Often E cores |
| `background` | Prefetch, cleanup, sync | E cores, throttled |

Tag honestly: under-tagging makes UI work crawl on E cores; over-tagging
starves real interactive work and burns battery.

## Task Priority ↔ QoS

- `Task(priority:)` accepts `.high` (`.userInitiated`), `.medium`, `.low`
  (`.utility`), `.background`; unspecified tasks inherit the creating
  context's priority.
- **Priority escalation** bounds inversion: awaiting a lower-priority task
  from a higher-priority context escalates it; so does `MainActor` waiting on
  it. Escalation propagates through structured child tasks — one more reason
  to prefer structured concurrency over detached tasks.
- `Task.detached` inherits nothing (priority, task-locals, actor context) —
  use it rarely and tag it explicitly.

## The Cooperative Pool's Contract

The default executor runs as many threads as there are CPU cores. Every
`async` function must make **forward progress or suspend** — never block a
pool thread:

| Forbidden on pool threads | Why | Instead |
|---------------------------|-----|---------|
| `DispatchSemaphore.wait` / `DispatchGroup.wait` to "make async sync" | No ownership info → no escalation; classic deadlock when the signaler needs the blocked pool | Restructure with `await`; bridge at the top level |
| Synchronous I/O / `sleep()` | Starves the fixed-width pool | `URLSession` async, `Task.sleep` |
| Long-held locks across `await` | Lock held while suspended → contention/deadlock | Never hold a lock across `await`; keep critical sections synchronous and tiny |
| `pthread_cond_wait`, blocking joins | Same starvation | Continuations around callback APIs |

Blocking legacy APIs that cannot change: give them their own `Thread` or a
Dispatch queue, then bridge with a continuation — don't occupy the pool.

## Bridging & Continuations

- `withCheckedThrowingContinuation` wraps callback APIs; resume **exactly
  once** (checked variant traps on double-resume, reports leaks on never-
  resume). Keep `withUnsafeContinuation` for measured hot paths only.
- `AsyncStream`/`AsyncThrowingStream` bridge multi-shot callbacks/delegates.

## Locks vs Actors (and inversion)

- `Mutex` (Synchronization framework) wraps the platform's modern lock
  (`os_unfair_lock` family on Darwin): **priority inheritance**, no
  allocation, synchronous — right tool for tiny critical sections
  (see the swift-engineer concurrency model).
- Semaphores and unfair-queue patterns convey **no ownership**, so the
  kernel can't boost the holder → unbounded priority inversion. Treat
  `DispatchSemaphore` in async code as a defect in review.
- Actors serialize via their executor (no dedicated thread). Remember
  reentrancy: state can change across every `await` (`threading.md`).
- `@MainActor` is a serial executor bound to the main thread; hops are
  scheduling operations — batch UI updates rather than ping-ponging
  (`performance.md`).

## Avoiding Thread Explosion (GCD interop)

Legacy GCD spawns a thread per blocked queue item (historically hundreds —
"thread explosion"); the cooperative pool's fixed width prevents this but
makes blocking deadlier. When interoperating:
- Don't fan out blocking work onto `DispatchQueue.global` from async code.
- Funnel legacy completion handlers through continuations instead of
  semaphore-waiting on them.

## Diagnosis on Apple Platforms

- **Instruments → Swift Concurrency**: task states, continuation leaks,
  structured task trees.
- **Instruments → System Trace / CPU Profiler**: run queues, context
  switches, E/P core residency, priority at sample time.
- **Hangs**: Xcode Organizer hang reports; on-device hang detection.
- `os_signpost` intervals around suspected stalls correlate app phases with
  scheduler activity.
- Symptom table for the general cases: `performance-engineering` skill.

## Checklist

- [ ] No blocking primitives on the cooperative pool (semaphores, sync I/O)
- [ ] No lock held across `await`
- [ ] Priorities tagged honestly; no detached tasks without a stated reason
- [ ] Continuations resume exactly once on all paths (including errors)
- [ ] Legacy blocking APIs isolated on their own thread/queue + continuation
- [ ] Verified with Swift Concurrency + System Trace instruments, not guessed

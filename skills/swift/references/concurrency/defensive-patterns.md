# Defensive Concurrency Patterns

Structural patterns that prevent entire classes of concurrent bugs by making invalid states unrepresentable, rather than relying on developer discipline. Each pattern is grounded in software engineering theory and includes concrete Swift 6 examples.

> **Meta-principle:** Make dangerous operations impossible through structure, not discipline. Whether it's a borrow checker, a nursery, a state machine, or a capability system — the reliable approach is to *remove the ability* to do the wrong thing, rather than *remembering* not to do it.

---

## 1. Single-Writer Ownership for Stateful Processors

**Theory:** Rust's ownership model (Hoare, 2010-15); Linear Logic (Girard, 1987). At any time, data has *one mutable reference* or *many immutable references* — never both.

**Bug class prevented:** Shared mutable structs (derivers, accumulators, batchers) receiving interleaved data from multiple concurrent streams, corrupting internal state.

**Problem:**
```swift
// BAD: Single shared deriver fed by multiple concurrent sensor streams.
// Each stream's cumulative counters corrupt the other's `previousWheel`.
@ObservationIgnored var speedDeriver = SpeedDeriver()

// Stream A calls: speedDeriver.derive(from: sensorA_reading)
// Stream B calls: speedDeriver.derive(from: sensorB_reading)
// Result: previousWheel alternates between sensors → garbage speed values
```

**Fix — Per-source instance ownership:**
```swift
// GOOD: Each data source owns its own deriver instance.
@ObservationIgnored var speedDerivers: [UUID: SpeedDeriver] = [:]

private func processCSCReading(
    _ reading: CSCReading,
    sensorID: UUID,  // ← identifies the source
    ...
) async {
    let speed = speedDerivers[sensorID, default: SpeedDeriver()]
        .derive(from: reading, circumferenceMM: circumferenceMM)
}
```

**When to apply:** Any time a `mutating func` on a struct is called from multiple concurrent tasks. If the struct tracks state across calls (`previousValue`, `accumulator`, `lastTimestamp`), it must be owned by exactly one concurrent context.

**Alternative — FRP-style scan:**
```swift
// Even better: state lives inside the stream pipeline, not externally.
for await reading in sensorStream {
    // scan accumulates state per-pipeline — no dictionary needed
}
```

> **Reference:** Conal Elliott & Paul Hudak, "Functional Reactive Animation" (ICFP 1997). `AsyncSequence.scan` is Swift's equivalent.

---

## 2. Scoped Task Categories (Orthogonal Lifecycles)

**Theory:** Harel's statecharts (1987) — orthogonal regions model independent subsystems that evolve in parallel. Restarting one region has no effect on others.

**Bug class prevented:** Coarse-grained `cancelAll()` killing unrelated tasks. E.g., restarting sensor streams also kills GPS tracking, timer, or mirroring tasks that should survive.

**Problem:**
```swift
// BAD: Everything in one flat pool. Restarting sensors kills GPS.
struct WorkoutTaskSet {
    var power: Task?
    var cscTasks: [Task]
    var hr: Task?
    var timer: Task?
    var location: Task?     // ← Killed when sensors restart!
    var degradation: Task?  // ← Also killed!

    mutating func cancelAll() { /* cancels everything */ }
}

// In promoteToRecording:
tasks.cancelAll()  // GPS tracking lost!
startStreams()      // Restarts sensors + timer, but NOT location
```

**Fix — Scoped cancellation by lifecycle category:**
```swift
// GOOD: Separate sensor tasks from session-scoped tasks.
public mutating func cancelSensorTasks() {
    power?.cancel(); power = nil
    for task in cscTasks { task.cancel() }; cscTasks = []
    hr?.cancel(); hr = nil
    sensorPolling?.cancel(); sensorPolling = nil
    // timer, location, mirroring, degradation are PRESERVED
}

public mutating func cancelAll() {
    cancelSensorTasks()
    timer?.cancel(); timer = nil
    location?.cancel(); location = nil
    // ... cancel everything
}
```

**When to apply:** Any time a system has independent subsystems that should survive each other's restarts. Identify which tasks belong to which lifecycle and group them.

**Design heuristic:** If cancelling task A should never affect task B, they must be in different cancellation groups.

---

## 3. Generation-Guarded Task Cleanup

**Theory:** Optimistic Concurrency Control (Kung & Robinson, 1981). Proceed without locks; validate generation before committing. Epoch-based reclamation (Fraser, 2004).

**Bug class prevented:** Cancelled task's cleanup code running after its replacement has started, stomping on the new task's state.

**Problem:**
```swift
// BAD: Old task's cleanup clears state set by new task.
func startCSCStreams() {
    for task in tasks.cscTasks { task.cancel() }  // cancel old
    tasks.cscTasks = []
    for entry in sensors {
        let task = Task { [weak self] in
            // ... stream loop ...
            self?.clearState(stableID: id)  // ← Runs AFTER new task set state!
        }
        tasks.cscTasks.append(task)
    }
}
```

**Fix — Generation counter:**
```swift
// GOOD: Each generation validates before cleanup.
public struct TaskGeneration: Sendable {
    private(set) public var current: UInt64 = 0

    @discardableResult
    public mutating func advance() -> UInt64 {
        current &+= 1
        return current
    }

    public func isCurrent(_ generation: UInt64) -> Bool {
        generation == current
    }
}

// Usage:
@ObservationIgnored var cscGeneration = TaskGeneration()

func startCSCStreams() {
    for task in tasks.cscTasks { task.cancel() }
    tasks.cscTasks = []
    let gen = cscGeneration.advance()  // ← new generation
    for entry in sensors {
        startSingleStream(entry: entry, generation: gen)
    }
}

private func startSingleStream(entry: ..., generation: UInt64) {
    let task = Task { [weak self] in
        // ... stream loop ...
        // Only clean up if still the owning generation
        guard self?.cscGeneration.isCurrent(generation) == true else { return }
        self?.clearState(stableID: id)
    }
    tasks.cscTasks.append(task)
}
```

**When to apply:** Any pattern where tasks are replaced (cancel old, start new) and the old task has cleanup logic that modifies shared state. The generation check is cheaper than awaiting full cancellation.

---

## 4. Prepare-Commit for Multi-Step Operations

**Theory:** Two-Phase Commit (Jim Gray, 1978); ARIES undo/redo logging (Mohan, 1992). Never destroy information needed by later steps until the entire operation has committed.

**Bug class prevented:** Multi-step operations (disconnect/reconnect, stop/restart) where step 1 destroys metadata that step 2 needs.

**Problem:**
```swift
// BAD: Disconnect removes entry; reconnect can't find categories.
func disconnectForHandoff(stableID: UUID) async {
    if let index = cscSensors.firstIndex(where: { $0.stableID == stableID }) {
        await cscSensors[index].sensor.stop()
        cscSensors.remove(at: index)  // ← Categories lost!
    }
}

func reconnectAfterFailedHandoff(stableID: UUID) {
    // Tries to recover categories from the array — but the entry was removed!
    let categories = cscSensors.first { $0.stableID == stableID }?.categories ?? []
    // categories is always [] → reconnects with wrong assignment
}
```

**Fix — Snapshot before destruction:**
```swift
// GOOD: Capture state into a "transaction log" before the destructive step.
private var handoffCSCCategories: [UUID: Set<SensorCategory>] = [:]

func disconnectForHandoff(stableID: UUID) async {
    if let index = cscSensors.firstIndex(where: { $0.stableID == stableID }) {
        handoffCSCCategories[stableID] = cscSensors[index].categories  // ← Snapshot
        await cscSensors[index].sensor.stop()
        cscSensors.remove(at: index)
    }
}

func reconnectAfterFailedHandoff(stableID: UUID) {
    let categories = handoffCSCCategories.removeValue(forKey: stableID) ?? []
    // categories correctly restored from snapshot
}
```

**When to apply:** Any two-step operation where the first step is destructive and the second step may need data from the original state. Create a value type that captures all intermediate state *before* step 1. Never rely on reading mutable shared state between steps.

---

## 5. RAII for Async Resource Finalization

**Theory:** RAII (Stroustrup, C++, 1984-89); Rust's `Drop` trait. Tie resource lifetime to scope: acquire in constructor, release in destructor. Cleanup is deterministic and automatic.

**Bug class prevented:** AsyncStream continuations not finished on deallocation, leaving consumers suspended indefinitely. Resources leaked on error paths.

**Problem:**
```swift
// BAD: If self is deallocated, continuation.finish() is never called.
trackingTask = Task { [weak self] in
    do {
        for try await location in provider.liveUpdates() {
            guard let self else { break }
            // ... process location ...
        }
    } catch { }
    guard let self else { return }  // ← continuation leaks!
    await self.finishContinuation()
}
```

**Fix — Finish in all paths:**
```swift
// GOOD: Continuation is finished regardless of how the task exits.
trackingTask = Task { [weak self] in
    do {
        for try await location in provider.liveUpdates() {
            guard let self else { break }
            // ... process location ...
        }
    } catch {
        self?.logger.error("Location error: \(error)")
    }
    if let self {
        await self.finishContinuation()
    } else {
        continuation.finish()  // ← Unblocks consumer even if owner is gone
    }
}
```

**Additional patterns:**
```swift
// Use onTermination for stream-scoped cleanup
continuation.onTermination = { @Sendable [weak self] _ in
    Task { await self?.cleanup() }
}

// Use defer for synchronous cleanup within a function
func processData() {
    let resource = acquire()
    defer { release(resource) }  // ← Guaranteed on all exit paths
    // ... work that may throw or return early ...
}
```

**When to apply:** Any `AsyncStream.Continuation` that outlives its logical owner. Any resource (file handle, network connection, HK builder) acquired in an async context.

**Swift limitation:** `deinit` cannot be `async` and runs non-deterministically (except `isolated deinit` on actors in Swift 6.2+). For async cleanup, use `onTermination` handlers or structured concurrency scopes.

---

## 6. Tracked Task Handles (No Fire-and-Forget)

**Theory:** Structured concurrency (Smith, 2018; Swift SE-0304). Every spawned task should be trackable and cancellable. An untracked `Task {}` is a "concurrent goto."

**Bug class prevented:** Fire-and-forget async work accumulating on rapid calls, with no way to cancel or await previous instances.

**Problem:**
```swift
// BAD: Untracked cleanup task — can accumulate on rapid calls.
func stopRoleEvaluation() {
    let coord = roleCoordinator
    roleCoordinator = nil
    Task {  // ← Fire-and-forget! Who cancels this?
        await coord?.stop()
    }
}
```

**Fix — Track in a cancellable handle:**
```swift
// GOOD: Previous cleanup is cancelled before starting new one.
func stopRoleEvaluation() {
    tasks.cleanup?.cancel()
    let coord = roleCoordinator
    roleCoordinator = nil
    tasks.cleanup = Task {
        await coord?.stop()
    }
}
```

**Rule of thumb:** Every `Task {}` should either be:
1. Stored in a handle that someone cancels
2. Inside a `withTaskGroup` that scopes its lifetime
3. Inside a `.task {}` SwiftUI modifier that ties it to view lifecycle

If none of these apply, it's a concurrent goto.

---

## 7. State Machine Transition Validation

**Theory:** Finite State Machines; Harel's statecharts (1987). If a transition isn't in the table, it's impossible.

**Bug class prevented:** Invalid state transitions (e.g., `idle → paused`, `recording → monitoring`) that lead to inconsistent state. Race conditions where concurrent events trigger conflicting transitions.

**Pattern:**
```swift
public enum WorkoutPhase: Sendable, Equatable {
    case idle, monitoring, recording, paused, mirroring, mirroringPaused, summary

    /// Returns the target phase if the transition is valid, nil otherwise.
    public func transition(to target: WorkoutPhase) -> WorkoutPhase? {
        switch (self, target) {
        case (.idle, .monitoring),
             (.idle, .recording),
             (.idle, .mirroring),
             (.monitoring, .recording),
             (.monitoring, .idle),
             (.recording, .paused),
             (.recording, .idle),
             (.recording, .summary),
             (.paused, .recording),
             (.paused, .idle),
             (.paused, .summary),
             (.mirroring, .mirroringPaused),
             (.mirroring, .idle),
             (.mirroringPaused, .mirroring),
             (.mirroringPaused, .idle),
             (.summary, .idle):
            return target
        default:
            return nil  // Invalid transition
        }
    }
}

// Usage:
guard let newPhase = phase.transition(to: .recording) else {
    logger.warning("Invalid transition from \(phase) to .recording")
    return
}
phase = newPhase
```

**When to apply:** Any system with distinct lifecycle phases and transitions between them. Especially valuable when multiple async events can trigger transitions concurrently (user actions, remote messages, sensor events).

---

## 8. Capability-Scoped Cleanup

**Theory:** Object-capability model (Dennis & Van Horn, 1966; Mark S. Miller, 2006). Authority is structural — determined by what references you hold. If you can't reference it, you can't break it.

**Bug class prevented:** Cleanup code with overly broad access modifying state that belongs to other tasks or generations.

**Problem:**
```swift
// BAD: Task has reference to self → can modify ANY state.
let task = Task { [weak self] in
    // ... work ...
    self?.globalDictionary[id] = nil  // ← Can stomp on another task's entry
}
```

**Fix — Narrow the capability:**
```swift
// GOOD: Task receives only what it needs to clean up its own entry.
let cleanup: @Sendable () -> Void = { [weak self] in
    guard let self else { return }
    guard self.cscGeneration.isCurrent(gen) else { return }
    self.clearCSCConnectionState(stableID: stableID)
}

let task = Task { [weak self] in
    // ... work ...
    cleanup()  // ← Can only affect its own entry, gated by generation
}
```

**When to apply:** When spawning tasks that need cleanup access to shared state. The narrower the reference, the fewer ways it can go wrong.

---

## Decision Matrix

| Bug Pattern | Primary Fix | Theory |
|---|---|---|
| Shared mutable state across streams | Per-source instance (dictionary) | Ownership / single-writer |
| Coarse-grained cancellation kills unrelated work | Scoped cancellation groups | Statecharts / orthogonal regions |
| Old task cleanup stomps new task state | Generation counter | Optimistic concurrency control |
| Multi-step operation loses intermediate data | Snapshot before destruction | Prepare-commit / 2PC |
| AsyncStream consumer hangs on deallocation | Finish continuation in all paths | RAII / scope-bound cleanup |
| Fire-and-forget tasks accumulate | Track in cancellable handle | Structured concurrency |
| Invalid state transitions | Explicit transition table | Finite state machines |
| Cleanup has overly broad access | Scoped capability / generation gate | Object-capability model |

---

## Further Reading

- Nathaniel J. Smith, ["Notes on structured concurrency, or: Go statement considered harmful"](https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/) (2018)
- David Harel, "Statecharts: A Visual Formalism for Complex Systems," *Science of Computer Programming* 8(3), 1987
- Kung & Robinson, "On Optimistic Methods for Concurrency Control," *ACM TODS* 6(2), 1981
- Joe Armstrong, "Making Reliable Distributed Systems in the Presence of Software Errors," PhD thesis, 2003
- Mark S. Miller, "Robust Composition: Towards a Unified Approach to Access Control and Concurrency Control," PhD thesis, 2006
- Conal Elliott & Paul Hudak, "Functional Reactive Animation," ICFP 1997
- [Rust Book: References and Borrowing](https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html)
- [Swift SE-0304: Structured Concurrency](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0304-structured-concurrency.md)

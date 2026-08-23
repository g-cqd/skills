# Swift Concurrency — Domain Guide

This guide contains Swift Concurrency best practices, common error triage, and project-specific rules. For detailed reference on specific topics, see the other files in this directory.

## Agent Behavior Contract

1. Analyze the project/package file to find Swift language mode and toolchain before advising.
2. Before proposing fixes, identify the isolation boundary: `@MainActor`, custom actor, instance isolation, or nonisolated.
3. Do not recommend `@MainActor` as a blanket fix. **Exception**: `@Observable` ViewModels that drive UI should always be `@MainActor`.
4. Prefer structured concurrency over unstructured tasks. `Task.detached` only with clear reason.
5. `@preconcurrency`, `@unchecked Sendable`, `nonisolated(unsafe)` require documented safety invariant + follow-up ticket.
6. For migration, optimize for minimal blast radius.

## Project Settings Intake

Always determine before advising:
- Default actor isolation (`@MainActor` or `nonisolated`?)
- Strict concurrency checking level (minimal/targeted/complete)
- Upcoming features enabled (especially `NonisolatedNonsendingByDefault`)
- Swift language mode (5.x vs 6) and SwiftPM tools version

Check `Package.swift` for `.defaultIsolation(MainActor.self)`, `.enableUpcomingFeature(...)`, tools version.
Check `project.pbxproj` for `SWIFT_DEFAULT_ACTOR_ISOLATION`, `SWIFT_STRICT_CONCURRENCY`, `SWIFT_UPCOMING_FEATURE_`.

## Quick Decision Tree

1. **Starting fresh with async code?** → `async-await-basics.md`, `tasks.md`
2. **Protecting shared mutable state?** → `actors.md` (incl. Mutex for simple synchronous state), `sendable.md`
3. **Managing async operations?** → `tasks.md`, `async-sequences.md`
4. **Working with legacy frameworks?** → `core-data.md`, `migration.md`
5. **Performance or debugging?** → `performance.md`, `testing.md`
6. **Understanding threading?** → `threading.md`
7. **Memory issues with tasks?** → `memory-management.md`
8. **Linting warnings?** → `linting.md`

## Triage Playbook (Common Errors)

| Error | Action |
|-------|--------|
| SwiftLint `async_without_await` | Remove `async` if not required; narrow suppression if required by protocol/override |
| "Sending value of non-Sendable type..." | Identify isolation boundary → `sendable.md`, `threading.md` |
| "Main actor-isolated ... cannot be used from nonisolated context" | Decide if `@MainActor` is correct → `actors.md`, `threading.md` |
| "Class property unavailable from async contexts" | Avoid thread-centric debugging → `threading.md` |
| XCTest "wait(...) unavailable from async contexts" | Use `await fulfillment(of:)` → `testing.md` |
| Core Data concurrency warnings | `core-data.md` (DAO/NSManagedObjectID patterns) |

## Core Concurrency Tools

| Tool | Use When |
|------|----------|
| `async/await` | Single async operation |
| `async let` | Fixed number of parallel operations |
| `Task` | Fire-and-forget, bridging sync→async |
| `Task Group` | Dynamic parallel operations with structured concurrency |
| `Actor` | Protecting shared mutable state |
| `@MainActor` | UI updates, ViewModels |

## Project-Specific Rules

### Task Management
- **No `Task {}` in computed properties**: Side effects in computed properties are untestable
- **No `Task {}` in initializers**: Use `.task {}` modifier instead
- **Keep ViewModel functions `async`**: Let the View create the `Task` via `.task {}` or `AsyncButton`
- **Always ensure Tasks can be cancelled**: Store `Task` references, cancel in `deinit`
- **Move checks outside `Task` when possible**: Guard before spawning
- **Remove unnecessary `async`/`Task`**: No `await` inside → not `async`

### Debounce Pattern
```swift
private var searchTask: Task<Void, Never>?
func search(_ query: String) {
    searchTask?.cancel()
    searchTask = Task {
        try? await Task.sleep(for: .seconds(0.4))
        guard !Task.isCancelled else { return }
        await performSearch(query)
    }
}
```

### Actor Isolation
- **`MainActor.run` is a last resort**: Prefer `@MainActor` isolation on type/function
- **`@preconcurrency` + `@MainActor` is contradictory**: Don't combine
- **Redundant `@MainActor in` in Task closures**: If ViewModel is `@MainActor`, just use `Task { ... }`
- **Question Actor conformance**: If protocol exposes no mutable state, prefer `Sendable`
- **No unnecessary `@Sendable`**: UI components likely need `@MainActor` instead
- **Use `@concurrent` for file I/O** (Swift 6.2)

### Async Streams & Observation
- **Prefer `AsyncStream` extensions** over spawning unstructured Tasks for continuous events
- **Re-register observation tracking immediately** in `withObservationTracking`
- **Use `@preconcurrency import Combine`**: Avoids manual `@Sendable` wrappers

### Best Practices
1. Prefer structured concurrency
2. Minimize suspension points
3. Use `@MainActor` judiciously
4. Make types Sendable
5. Handle cancellation — **never swallow with `try?`**, check `Task.isCancelled` after `Task.sleep`
6. Avoid blocking — never semaphores/locks in async
7. Weak captures inside loops, not outside
8. AsyncStream cleanup — finishing continuation may not be sufficient
9. Question `async` on protocol methods
10. Order async operations for better UX (navigate first, refresh in background)

## Detailed References
- `async-await-basics.md` — Syntax, execution order, URLSession patterns
- `tasks.md` — Task lifecycle, cancellation, priorities, groups
- `threading.md` — Thread/task relationship, suspension, isolation domains
- `memory-management.md` — Retain cycles in tasks
- `actors.md` — Actor isolation, @MainActor, global actors, reentrancy, Mutex
- `sendable.md` — Sendable conformance, region isolation
- `linting.md` — Concurrency lint rules, SwiftLint
- `async-sequences.md` — AsyncSequence, AsyncStream
- `async-algorithms.md` — Async algorithm patterns
- `defensive-patterns.md` — Structural patterns preventing concurrency bug classes (ownership, generation guards, scoped cancellation, prepare-commit, RAII cleanup)
- `core-data.md` — NSManagedObject sendability, custom executors
- `performance.md` — Profiling, reducing suspension points
- `testing.md` — XCTest/Swift Testing async patterns
- `migration.md` — Swift 6 migration strategy
- `glossary.md` — Core concurrency terms

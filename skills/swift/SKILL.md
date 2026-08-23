---
name: swift
description: >
  Swift language and concurrency, wherever Swift runs — Apple platforms, Linux,
  server, embedded. Covers API design and the Swift API Design Guidelines,
  naming, access control, the type system (struct and enum first, final classes,
  generics, some versus any, existentials, copy-on-write, property wrappers,
  making illegal states unrepresentable), typed throws and error handling, SOLID
  and dependency injection, SPM package structure and Package.swift, doc-comment
  contracts, and the whole concurrency model: async/await, structured
  concurrency, Task and TaskGroup, cancellation, actors, @MainActor, actor
  reentrancy, Sendable and region isolation, AsyncSequence and AsyncStream,
  isolation boundaries, QoS and the cooperative pool, Mutex and Atomic from the
  Synchronization framework, memory ordering, and Swift 6 strict-concurrency
  migration. Use when writing, reviewing, or architecting Swift, designing an API
  or module, fixing a data race, resolving errors like "type does not conform to
  Sendable", "call to main-actor-isolated method in a synchronous nonisolated
  context", or "reference to captured var in concurrently-executing code",
  eliminating retain cycles in tasks and closures, or migrating a target to Swift
  6. Not for SwiftUI views and view state, which is `swiftui`; not for
  platform frameworks or Liquid Glass, which is `apple-platforms`; not for GPU
  and shaders, which is `graphics`; not for Keychain, crypto, or threat modeling,
  which is `secure-coding`; not for building and running, which is `xcode`.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Swift

This skill owns **the language**: how types are designed, how errors travel, and how concurrency
is made safe. It does not own what is drawn (`swiftui`), which framework is called
(`apple-platforms`), or how the thing is built (`xcode`).

## Contract

```
§GATE     ? version-floor FIRST ∷ Package.swift{.platforms;tools-version} |
          *_DEPLOYMENT_TARGET | @available | CI-matrix
          newest-API ≤ floor · unavailable ⇒ name + fallback + ⚑"unlocks at vX"
§DOCS     apple-docs MCP → CLI → SDK-interfaces · ¬web-fetch · ¬memory ∀@available
§TYPE     illegal-states-unrepresentable · struct|enum ≻ class ·
          final-class default · typed-throws ≻ Result
§CONC     Swift6-strict-clean · @MainActor ∀UI-state · Sendable ∀cross-boundary ·
          structured ≻ unstructured · ∅data-race
§SYNC     @MainActor → Mutex|Atomic → bare-actor(last-resort)
          ordering ∷ weakest-correct ¬seqCst-by-default
§BAN      DispatchQueue · try! · as! · force-unwrap · empty-catch ·
          Any|[String:Any] · class-when-struct-suffices ·
          Task{} ∈ init|computed-property · recursion(except bounded-tree)
§PRECEDE  project-conventions ≻ this-skill ∀naming|DI|module-layout
```

---

## 1. Version floor first

Before using any API, establish the floor: `Package.swift` (`.platforms`, swift-tools-version),
the deployment target, `@available` attributes, the oldest CI toolchain. Use the newest API the
floor permits and never one above it. Do not assume the newest toolchain is installed.

When the floor blocks a primitive: name it, use the fallback, and say which version unlocks it.

| Wanted | Fallback below floor |
|---|---|
| `Span`, `RawSpan`, `MutableSpan` | `withUnsafeBufferPointer` / `withUnsafeMutableBufferPointer` |
| `OutputSpan` | `Array(unsafeUninitializedCapacity:)` |
| `InlineArray` | `ContiguousArray` + `reserveCapacity` |
| `Mutex`, `Atomic` | `OSAllocatedUnfairLock`, or `os_unfair_lock` in a safe wrapper |
| typed throws | untyped throws + error enum |

Verify availability from documentation, never from memory.

---

## 2. Type system

**Make illegal states unrepresentable.** This is the highest-leverage rule in the language. An
enum with associated values that cannot express a contradiction removes a whole class of tests.

- **`struct` and `enum` first.** Reach for `class` only when you genuinely need reference
  semantics or inheritance. Mark every class `final` unless it is designed for subclassing — the
  compiler devirtualizes, and nobody subclasses it by accident.
- **`some` over `any`.** An opaque type keeps static dispatch and specialization. Use `any`
  (an existential) only for heterogeneous storage. Existentials box, allocate, and defeat
  specialization.
- **Avoid `Any` and `[String: Any]` entirely.** Write a strict `Decodable` model. A dictionary of
  `Any` is a parser that has not been written yet.
- **`guard let` for early exit.** Nested `if let` builds a pyramid that hides the logic.
- **Computed properties for derived state.** Two stored properties that must agree will
  eventually disagree.
- **Access control starts at `private`** and widens only under pressure. `fileprivate` is a last
  resort.
- **Copy-on-write** is what makes value semantics affordable. A struct holding a class reference
  needs `isKnownUniquelyReferenced` before mutating shared storage, or it silently shares.
- **Prefer concrete types to type erasure.** Use generics deliberately; an `AnyFoo` wrapper is a
  cost, not an abstraction.

## 3. Errors

- **Typed throws** tells the caller what can go wrong. Use `Result` only where typed throws is
  impractical — a stored completion, a value crossing a boundary that cannot throw.
- **Never an empty catch.** Log the error and the failing path meaningfully, or propagate.
- **No `try!`, no `as!`, no force unwrap.** Each is a claim that a runtime condition is impossible;
  if it truly is, express it in the type.
- An error path returns the **true** result, never a plausible-looking default.

## 4. API design

Follow the Swift API Design Guidelines: clarity at the point of use beats brevity at the point of
declaration.

- Name by role, not by type. Include words that prevent ambiguity, omit words that repeat type
  information.
- Methods read as sentences at the call site. Mutating/non-mutating pairs follow the
  `sort()`/`sorted()`, `reverse()`/`reversed()` verb-noun rule.
- **Protocol-first.** Define behavior as a protocol, then conform — it is what makes dependency
  injection and testing possible.
- **Composition over inheritance.** Inheritance couples lifetime, storage, and behavior at once.
- **Dependency injection** for anything that touches the outside world. An injected closure is a
  perfectly good dependency.
- Keep cohesion high and coupling low; obey the Law of Demeter — an object talks to its immediate
  collaborators.

## 5. Documentation contract

Write a doc comment for every public declaration, and for a private one only when its behavior is
not obvious. Document the **contract**, not the implementation: parameters, return value, thrown
errors, preconditions, invariants, complexity, isolation, and cancellation behavior.

Use DocC fields — `- Parameter`, `- Returns`, `- Throws`, `- Complexity`, `- Precondition`,
`- Note`. State `- Complexity` whenever it is not O(1). Never restate the signature.

```swift
/// The display name, from the profile, or the account identifier if the profile has no name.
/// - Complexity: O(1)
public var name: String { get }
```

Change the code, change the doc comment, in the same commit. An incorrect comment is worse than
no comment.

## 6. Packages

Structure `Package.swift` so that the dependency graph is legible: one target per coherent
responsibility, test targets alongside, and `.platforms` stating the real floor. Justify every
external dependency against the standard library, an Apple framework, and an Apple-supplied
package before adding it.

---

## 7. Concurrency

### Structured first

Structured concurrency — `async let`, `TaskGroup`, and child tasks — gives you cancellation
propagation and lifetime guarantees for free. Unstructured `Task {}` gives up both.

- **Never `Task {}` in an initializer or a computed property.** It escapes the caller's lifetime
  and cancellation, and runs at an unpredictable time.
- Every long-running loop checks cancellation: `Task.isCancelled`, or
  `try Task.checkCancellation()` where throwing is right. A task that ignores cancellation keeps
  the whole tree alive.
- **Do not use `DispatchQueue`.** `Task`, `TaskGroup`, and `AsyncStream` replace it. A serial
  queue used as a lock is the specific anti-pattern to look for.

### Isolation

- **`@MainActor` holds UI and UI-facing state.** That covers most mutable state in an app.
- An **actor** protects mutable state behind an async boundary. It is the right tool when there is
  a natural async boundary or an invariant that must hold across an `await`.
- **Actor reentrancy is the classic trap**: an actor's state can change across every `await`
  inside its own method. Re-check preconditions after suspension — do not assume what you read
  before the `await` still holds.
- `nonisolated` for members that touch no isolated state; it removes needless hops.

### Sendable

Every type crossing an isolation boundary must be `Sendable`. Prefer **implicit** conformance —
a frozen value type of `Sendable` members gets it for free. Reach for `@unchecked Sendable` only
with a comment stating which lock or invariant makes it safe; it is an assertion, not a fix.

Region-based isolation lets the compiler prove a non-`Sendable` value is used in only one region
at a time, so a value can often be transferred without conforming at all.

Common diagnostics and what they actually mean:

| Diagnostic | Cause |
|---|---|
| *"type does not conform to `Sendable`"* | A value crosses an isolation boundary — make it a value type, or isolate it |
| *"call to main-actor-isolated … in a synchronous nonisolated context"* | The caller needs `await`, or should itself be `@MainActor` |
| *"reference to captured var in concurrently-executing code"* | A `var` captured by a closure — capture a `let` copy, or isolate the state |

### Synchronization ladder

1. `@MainActor` already covers UI state.
2. Residual shared mutable state → **`Mutex` and `Atomic`** from the Synchronization framework.
   They are `~Copyable` and `Sendable`, and cheaper than standing up actor infrastructure.
   `Mutex.withLock`, `withLockIfAvailable`; `Atomic` for a counter or a flag.
3. A **bare actor** is the last resort, or the obvious fit at a real async boundary.

Never use `os_unfair_lock`, `NSLock`, `pthread_mutex_t`, or a serial `DispatchQueue` as a lock in
new code.

**Memory ordering: pick the weakest that is correct.**

- `.relaxed` — an independent counter nothing else depends on
- `.acquiring` / `.releasing` — one thread publishes, another consumes
- `.sequentiallyConsistent` — only where a single total order is genuinely required

```swift
let hits = Atomic<Int>(0)
hits.wrappingAdd(1, ordering: .relaxed)
```

Never default to sequential consistency because it "seems safer" — it hides the fact that the
ordering was never reasoned about.

### AsyncSequence

`AsyncStream` and `AsyncThrowingStream` adapt callbacks and delegates into async iteration. Set
the continuation's `onTermination` to release resources — a stream whose consumer disappears
otherwise leaks its producer. Choose the buffering policy deliberately: unbounded buffering turns
backpressure into memory growth.

### QoS and the cooperative pool

The cooperative pool has one contract: **never block a thread in it.** No semaphore waits, no
synchronous file or network I/O, no busy loops. Blocking a cooperative thread can deadlock the
pool, because it is sized to the core count rather than grown on demand. Push blocking work to a
dedicated executor or make it genuinely async.

### Memory in concurrent code

Retain cycles hide in tasks and closures: a `Task` capturing `self` strongly keeps the object
alive until the task finishes. Use `[weak self]` and re-check after the first `await`. Break
class/closure cycles with `weak` or `unowned` — `unowned` only where the referent provably
outlives the reference.

### Swift 6 migration

Migrate per module, not all at once. Raise the language mode one target at a time, starting at the
leaves of the dependency graph. Fix the diagnostics; do not silence them with `@unchecked
Sendable` or `nonisolated(unsafe)` to reach a green build — those are debt with a compiler-shaped
receipt. Data races that were runtime Heisenbugs become compile-time errors, which is the entire
point.

---

## 8. Review checklist

- [ ] Version floor checked before any API choice
- [ ] SOLID, DRY; value types; classes `final`
- [ ] Illegal states unrepresentable; no `Any` or `[String: Any]`
- [ ] Typed errors; no empty catch; no `try!`, `as!`, or force unwrap
- [ ] Naming follows the API Design Guidelines
- [ ] Access control starts at `private`
- [ ] `some` over `any` unless heterogeneous storage is required
- [ ] Compiles clean under Swift 6 strict concurrency
- [ ] Structured concurrency; no `Task {}` in inits or computed properties
- [ ] Cancellation checked in every long-running loop
- [ ] `Sendable` at isolation boundaries, implicit where possible
- [ ] Weakest correct memory ordering; no default `.sequentiallyConsistent`
- [ ] No retain cycles in tasks or closures
- [ ] Doc comments state the contract, including isolation and cancellation

---

## Boundaries

| Need | Skill |
|---|---|
| SwiftUI views, view state, view identity | `swiftui` |
| Platform frameworks, Liquid Glass, SDK-generation APIs | `apple-platforms` |
| Metal, shaders, GPU compute | `graphics` |
| Keychain, CryptoKit, ATS, threat modeling | `secure-coding` |
| Unsafe-pointer review, ownership invariants, sanitizers | `memory-safety` |
| Cache, scheduling, and hardware theory behind these rules | `performance-engineering` |
| Test strategy, Swift Testing, TDD | `testing` |
| Building, running, profiling, hardening the project | `xcode` |
| Authoritative API and availability lookup | `apple-docs` |
| Project naming, DI, and module conventions | `project-conventions` |

## References

**Language** — `references/swift/_guide.md`, `architecture.md` (SOLID, composition, DI),
`type-system.md`, `package-structure.md`, `naming-conventions.md`, `documentation.md`,
`deep-patterns.md` (`some` vs `any`, COW, property wrappers, anti-patterns, UIKit interop),
`memory-layout-performance.md` (ARC traffic, COW internals, cache-aware Swift)

**Concurrency** — `references/concurrency/_guide.md`, `async-await-basics.md`, `tasks.md`,
`actors.md`, `sendable.md`, `async-sequences.md`, `async-algorithms.md`, `threading.md`,
`core-data.md`, `linting.md`, `migration.md`, `testing.md`, `performance.md`,
`memory-management.md`, `scheduling-qos.md`, `glossary.md`

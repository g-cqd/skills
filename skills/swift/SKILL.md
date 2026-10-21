---
name: swift
description: >-
  Swift language and concurrency on Apple platforms, Linux, servers, and embedded systems.
  Use for API design, naming, generics, typed throws, SPM, async/await, actors, Sendable,
  Mutex, Atomic, cancellation, data races, and Swift 6 migration or isolation errors. For
  views, use `swiftui`; for framework adoption, use `apple-platforms`; for Keychain and
  crypto, use `secure-coding`; for builds, use `xcode`.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Swift

This skill covers the language: type design, error handling, and safe concurrency. Views are
`swiftui`, framework choice is `apple-platforms`, and builds are `xcode`.

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
§BAN      DispatchQueue(except param ∷ framework-API-requires) · try! · as! · force-unwrap ·
          empty-catch · Any|[String:Any](except framework-hands-over ⇒ typed @call-site) ·
          class-when-struct-suffices ·
          Task{} ∈ init|computed-property · recursion(except bounded-tree)
§PRECEDE  project-conventions ≻ this-skill ∀naming|DI|module-layout
```

---

## 1. Version floor first

Before you choose an API that has an `@available` attribute or a minimum Swift version, find the
floor once per task. Read `Package.swift` (`.platforms`, swift-tools-version), the deployment
target, `@available` attributes, and the oldest CI toolchain. If none of these declares a floor,
state the floor you assume. Use the newest API the floor permits, and no API above it. Do not
assume the newest toolchain is installed.

When the floor blocks a primitive, name the primitive, use the fallback, and state which version
unlocks it.

| Wanted | Fallback below floor |
|---|---|
| `Span`, `RawSpan`, `MutableSpan` | `withUnsafeBufferPointer` / `withUnsafeMutableBufferPointer` |
| `OutputSpan` | `Array(unsafeUninitializedCapacity:)` |
| `InlineArray` | `ContiguousArray` + `reserveCapacity` |
| `Mutex`, `Atomic` | `OSAllocatedUnfairLock`, or `os_unfair_lock` in a safe wrapper |
| typed throws | untyped throws + error enum |

Verify availability with `apple-docs` for Apple SDKs; for the toolchain or packages, use swift.org
docs or the package's release notes. If it cannot be verified, say so next to the claim.

---

## 2. Type system

**Make illegal states unrepresentable.** Use an enum with associated values that cannot express
a contradiction.

- **`struct` and `enum` first.** Use `class` only when you need reference semantics or
  inheritance. Mark each class `final` unless it is designed for subclassing.
- **`some` over `any`.** An opaque type keeps static dispatch and specialization. Use `any`
  (an existential) only for heterogeneous storage; existentials box, allocate, and prevent
  specialization.
- **No `Any` or `[String: Any]`.** Write a strict `Decodable` model. Where a framework API hands
  you one (for example `userInfo`), convert it to a typed value at that call site.
- **`guard let` for early exit.** Do not nest `if let`; nesting hides the logic.
- **Computed properties for derived state.** Do not store two properties that must agree.
- **Access control starts at `private`.** Widen it only when another type, file, or module needs
  access. Use `fileprivate` only when `private` cannot give the access needed.
- **Copy-on-write**: a struct holding a class reference must check `isKnownUniquelyReferenced`
  before mutating shared storage; without the check, copies share the mutation.
- **Concrete types over type erasure.** An `AnyFoo` wrapper is a cost, not an abstraction; use
  generics or a concrete type instead.

## 3. Errors

- **Typed throws** tells the caller what can fail. Use `Result` only where typed throws is not
  possible: a stored completion, or a value crossing a boundary that cannot throw.
- **No empty catch.** Log the error and the failing path, or propagate the error.
- **No `try!`, no `as!`, no force unwrap.** Each one claims a runtime condition is impossible. If
  the condition is impossible, express that in the type.
- On failure, return or throw the failure. Do not return a default value that looks like success.

## 4. API design

Follow the Swift API Design Guidelines: clarity at the point of use over brevity at the point of
declaration.

- Name by role, not by type. Include words that prevent ambiguity; omit words that repeat type
  information.
- Methods read as sentences at the call site. Mutating/non-mutating pairs follow the
  `sort()`/`sorted()`, `reverse()`/`reversed()` verb-noun rule.
- **One meaning per verb.** `load` fetches (network or disk) and stores or returns nothing;
  `refresh` swaps a newer value into the owner of the truth, nowhere else; `update` recomputes
  derived state; `resolve` decides a value from several sources; `remove` deletes; `store` only
  where a settable property is impossible. No `sync`; no `get` prefix on a call that returns
  nothing. One verb family per type; see `references/swift/naming-conventions.md`.
- **Property, not method,** for a side-effect-free read with no arguments (`authToken`, not
  `authToken()`), and for a read/write pair where `nil` removes (`pushToken = nil`, not
  `store`/`delete` twins). On a struct that owns shared storage, use `nonmutating set`.
- **Booleans are interrogative** (`is`, `has`, `can`) and claim only what the type knows: a
  keychain store has `hasAuthToken`; `isLoggedIn` belongs where the session is known.
- **Argument labels carry the noun**; do not put the noun in both base name and label:
  `start(with:)`, `refresh(user:)`, `store(accountKey:)`, not `storeAccountKey(_:)`.
- **Protocol-first for dependencies.** For a type that is injected or replaced in tests, define
  the behaviour as a protocol, then conform. The protocol is a plain noun (`TokenStore`,
  `DirectoryProvider`); the implementation carries `Default…` or a descriptive prefix
  (`DefaultOrderDetailsService`, `KeychainTokenStore`). Do not use `-ing` names.
- **Inject each dependency that touches the outside world.** An injected closure is a valid
  dependency.

## 5. Documentation contract

Write a doc comment for each public declaration. Write one for a private declaration only when its
behaviour is not obvious from its name and signature. Document the **contract**, not the
implementation: parameters, return value, thrown errors, preconditions, invariants, complexity,
isolation, and cancellation behaviour.

Use DocC fields: `- Parameter`, `- Returns`, `- Throws`, `- Complexity`, `- Precondition`,
`- Note`. State `- Complexity` when it is not O(1). Do not restate the signature.

```swift
/// The display name, from the profile, or the account identifier if the profile has no name.
/// - Complexity: O(1)
public var name: String { get }
```

When you change the code, change its doc comment in the same commit.

## 6. Packages

Structure `Package.swift` with one target per coherent responsibility, test targets alongside,
and `.platforms` stating the real floor. Before adding an external dependency, state why the
standard library, an Apple framework, or an Apple-supplied package does not cover the need.

**Build once, test many.** Write the whole step, build once, and run every test from that build.
The budget and the hand-back rules are in `engineering-practices` §5.

```sh
swift build --build-tests                         # one build per completed step, never per edit
swift test --skip-build --filter ParserTests      # every test run, rerun included
```

- Plain `swift test` builds first, so in a loop it rebuilds on every run. After
  `swift build --build-tests`, pass `--skip-build` to each `swift test` run.
- While you edit, find type errors with SourceKit-LSP diagnostics, not with a build.
- `swift build --target Parser` compiles one module without linking the test bundle. Use it
  instead of the test build for a step whose tests you do not run yet, not in addition to it.
- While you develop, use one package and one configuration, debug. Release builds use their own
  `--scratch-path .build-release`, never the debug `.build`, and run once per task
  (`performance-engineering` §4).

---

## 7. Concurrency

### Structured first

Use structured concurrency (`async let`, `TaskGroup`, child tasks); it propagates cancellation and
bounds lifetime. Unstructured `Task {}` gives up both.

- **No `Task {}` in an initializer or a computed property.** The task escapes the caller's
  lifetime and cancellation, and runs at an unpredictable time.
- Each loop in a task that runs longer than about 100 ms, or whose iteration count depends on
  input, checks cancellation: `Task.isCancelled`, or `try Task.checkCancellation()` where throwing
  is correct.
- **No `DispatchQueue`.** Use `Task`, `TaskGroup`, and `AsyncStream`. In review, flag a serial
  queue used as a lock. Exception: pass a queue where a framework API requires one as a parameter.

### Isolation

- **`@MainActor` holds UI and UI-facing state.** In an app, that is most mutable state.
- An **actor** protects mutable state behind an async boundary. Use one when there is a natural
  async boundary or an invariant that must hold across an `await`.
- **Actor reentrancy**: an actor's state can change across each `await` inside its own method.
  After each suspension, re-check the preconditions you read before the `await`.
- Mark `nonisolated` the members that touch no isolated state; this removes needless hops.

### Sendable

A type crossing an isolation boundary must be `Sendable`, unless region-based isolation proves the
value is used in only one region at a time (then the value transfers without conforming). Prefer
**implicit** conformance: a frozen value type with `Sendable` members gets it automatically. Use
`@unchecked Sendable` only with a comment that names the lock or invariant that makes the type
safe.

Common diagnostics and their usual cause:

| Diagnostic | Cause |
|---|---|
| *"type does not conform to `Sendable`"* | A value crosses an isolation boundary — make it a value type, or isolate it |
| *"call to main-actor-isolated … in a synchronous nonisolated context"* | The caller needs `await`, or should itself be `@MainActor` |
| *"reference to captured var in concurrently-executing code"* | A `var` captured by a closure — capture a `let` copy, or isolate the state |

The table names the usual cause, not the fix for this code. Before proposing a change, read the
declaration and its isolation context. A type that already holds a lock, or a closure that
outlives its caller, needs a different fix from the one the error string suggests.

### Synchronization ladder

1. `@MainActor` already covers UI state.
2. Residual shared mutable state → **`Mutex` and `Atomic`** from the Synchronization framework.
   They are `~Copyable` and `Sendable`, and cheaper than an actor. `Mutex.withLock`,
   `withLockIfAvailable`; `Atomic` for a counter or a flag.
3. A **bare actor** is the last resort, or the obvious fit at a real async boundary.

In new code at or above the `Mutex` floor, do not use `os_unfair_lock`, `NSLock`,
`pthread_mutex_t`, or a serial `DispatchQueue` as a lock. Below the floor, use the fallback in §1.

**Memory ordering: pick the weakest that is correct.**

- `.relaxed` — an independent counter nothing else depends on
- `.acquiring` / `.releasing` — one thread publishes, another consumes
- `.sequentiallyConsistent` — only where a single total order is required

```swift
let hits = Atomic<Int>(0)
hits.wrappingAdd(1, ordering: .relaxed)
```

Do not use `.sequentiallyConsistent` as a default; choose it only after reasoning that a single
total order is required.

### AsyncSequence

`AsyncStream` and `AsyncThrowingStream` adapt callbacks and delegates into async iteration. Set
the continuation's `onTermination` to release resources; without it, a stream whose consumer
disappears leaks its producer. Choose the buffering policy for the producer's rate: unbounded
buffering turns backpressure into memory growth.

### QoS and the cooperative pool

Do not block a thread in the cooperative pool: no semaphore waits, no synchronous file or network
I/O, no busy loops. The pool is sized to the core count and does not grow, so blocking can
deadlock it. Move blocking work to a dedicated executor or make it async.

### Memory in concurrent code

A `Task` that captures `self` strongly keeps the object alive until the task finishes. When a task
or stored closure can outlive the object, capture `[weak self]` and re-check it after the first
`await`. Break class/closure cycles with `weak` or `unowned`; use `unowned` only where the
referent provably outlives the reference.

### Swift 6 migration

- Migrate one module at a time. Raise the language mode one target at a time, starting at the
  leaves of the dependency graph.
- Fix the diagnostics. Do not silence them with `@unchecked Sendable` or `nonisolated(unsafe)` to
  get a green build.
- Make targeted edits, file by file; do not rewrite whole files. The reviewer must see which
  isolation each declaration gained.

---

## 8. Review checklist

- [ ] Version floor checked before any API choice
- [ ] Value types; classes `final`
- [ ] Illegal states unrepresentable; no `Any` or `[String: Any]`, except one a framework API hands
  over, converted to a typed value at that call site
- [ ] Typed errors; no empty catch; no `try!`, `as!`, or force unwrap
- [ ] Naming follows the API Design Guidelines
- [ ] Verbs match their effect; booleans claim only what their type knows; labels carry the noun
- [ ] Access control starts at `private`
- [ ] `some` over `any` unless heterogeneous storage is required
- [ ] Compiles clean under Swift 6 strict concurrency
- [ ] Structured concurrency; no `Task {}` in inits or computed properties; no `DispatchQueue`,
  except as a parameter a framework API requires
- [ ] Cancellation checked in each loop in a task that runs longer than about 100 ms, or whose
  iteration count depends on input
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

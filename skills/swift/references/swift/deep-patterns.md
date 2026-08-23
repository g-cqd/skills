# Swift Deep Patterns Reference

Advanced Swift patterns for correct, performant, and maintainable code.

## Type Selection

| Type | Use When |
|------|----------|
| `struct` | Data model, no identity, thread-safe by default, small or has COW |
| `class` | Shared mutable state with identity (`===`), NSObject subclass, need deinit |
| `enum` | Closed set of cases, state machines, errors, associated values |
| `actor` | Shared mutable state with concurrency safety |

### Copy-on-Write

Array, Dictionary, Set, String use COW automatically. Avoid holding extra references to collections you're about to mutate. For custom value types:

```swift
mutating func update() {
    if !isKnownUniquelyReferenced(&_storage) {
        _storage = _storage.copy()
    }
    _storage.modify()
}
```

## Protocol Design Decision Flow

1. Start with concrete types
2. Extract a protocol only when you have 2+ conformers or need testability
3. Prefer `some Protocol` (opaque) over `any Protocol` (existential)

### some vs any

```
Concrete type  →  some Protocol  →  any Protocol
(prefer)          (hide type)       (heterogeneous collections only)
```

- **`some`**: fixed underlying type, zero-cost, static dispatch, stack-eligible
- **`any`**: type-erased box, heap allocation if >24 bytes, dynamic dispatch

Swift 6 requires explicit `any` — intentional friction to prefer `some`.

### Existential Overhead

`any Protocol` has 5-word overhead (3 value buffer + VWT + PWT). Prefer `some` for performance.

### Conditional Conformance

```swift
extension Array: Equatable where Element: Equatable { }
extension Cache: Sendable where Key: Sendable, Value: Sendable { }
```

## Error Handling Strategies

| Mechanism | Use When |
|-----------|----------|
| `throws` | Default for fallible functions |
| `throws(ErrorType)` | Internal modules with closed, stable error domains |
| `Result<T, E>` | Storing outcomes, callback APIs; avoid in async code |
| `Optional` (nil) | Failure carries no diagnostic information |

### Layer Boundary Wrapping

```swift
func loadUser(_ id: String) throws -> User {
    do { return try repository.fetch(id) }
    catch { throw ServiceError.loadFailed(id: id, underlying: error) }
}
```

## Actor Hop Cost

Each `await` to an actor is a suspension point. In loops, batch operations:

```swift
// Bad: N actor hops
for item in items { await cache.store(item) }

// Good: 1 actor hop
await cache.storeAll(items)
```

## Memory & Performance

### ARC Rule
**`weak` over `unowned`** — performance difference is negligible; safety gain is significant.

### Task Closures
`Task { }` within a method captures `self` strongly but does NOT create a retain cycle because `Task` is not stored by `self`. Use `[weak self]` only when the task outlives the object or is stored.

### Stack vs Heap
- Structs with concrete types: stack-allocated
- Structs in `any Protocol` existentials: heap-allocated if >24 bytes
- Classes: always heap
- `some Protocol`: zero-cost, static dispatch, stack-eligible

### Optimization Hints
- `@inlinable` — exports function body for cross-module optimization (body becomes ABI)
- `ContiguousArray` — outperforms `Array` when elements are class types (avoids NSArray bridging)
- `.lazy` chains — avoid intermediate array allocations

## Property Wrappers

Write a property wrapper when the same get/set logic repeats across 3+ properties:

```swift
@propertyWrapper
struct Clamped<V: Comparable> {
    private var value: V
    let range: ClosedRange<V>
    var wrappedValue: V {
        get { value }
        set { value = min(max(newValue, range.lowerBound), range.upperBound) }
    }
    init(wrappedValue: V, range: ClosedRange<V>) {
        self.range = range
        self.value = min(max(wrappedValue, range.lowerBound), range.upperBound)
    }
}
```

### The @Atomic Anti-Pattern
A lock-based `@Atomic` wrapper is fundamentally flawed: `x += 1` is read-then-write with a gap between lock acquisitions. Use `Mutex.withLock` or actors instead.

## UIKit Interop

```swift
struct MapView: UIViewRepresentable {
    let region: MKCoordinateRegion
    func makeUIView(context: Context) -> MKMapView { MKMapView() }
    func updateUIView(_ view: MKMapView, context: Context) {
        view.setRegion(region, animated: true)  // Update ONLY changed properties
    }
}
```

**In `updateUIView`, update only changed properties** — setting everything causes flicker/scroll resets.

**Incremental adoption**: `UIHostingController` to embed SwiftUI in UIKit (start with leaf screens). `UIViewRepresentable` for the reverse.

## Package & Module Organization

Split targets: `MyAppCore` (business logic) + `MyAppUI` (views) + `MyApp` (entry point).

Use `package` access level (SE-0386) for package-scoped visibility.

## Anti-Patterns Table

| Anti-Pattern | Fix |
|-------------|-----|
| Force unwrap (`!`) | `guard let`, `if let`, `??`, `compactMap` |
| God protocols (10+ reqs) | Small protocols + composition |
| Stringly-typed keys | Enums, `CodingKeys`, typed identifiers |
| Ignoring Sendable warnings | Make types `Sendable` or isolate to actor |
| Premature `any` | Use concrete types or `some` first |
| Pyramid of doom | `guard let a, let b, let c else { return }` |
| `try!` in production | `try` + propagation or `try?` when ignorable |
| `@unchecked Sendable` cargo | Prove safety with locks/atomics or use actors |
| Class when struct suffices | Default to struct |
| Sequential awaits | `async let` or `TaskGroup` for parallel work |
| Storing `context` from UIViewRepresentable | SwiftUI manages lifecycle — don't retain |
| `@Atomic` property wrapper | Use `Mutex.withLock` or actors |

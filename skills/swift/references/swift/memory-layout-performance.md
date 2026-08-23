# Swift Memory Layout & Hardware-Aware Performance

How Swift values actually live in memory, and how to write allocation- and
cache-conscious Swift. Methodology parent: `performance-engineering` (measure
first). Hardware background: `performance-engineering` skill.

## Layout Introspection

```swift
MemoryLayout<T>.size       // bytes of one instance, without trailing padding
MemoryLayout<T>.stride     // distance between elements in an array (size + padding)
MemoryLayout<T>.alignment  // required alignment
```

- Arrays use **stride**; a `[T]` of n elements touches `n * stride` bytes.
- Field order: Swift lays out stored properties in declaration order today
  (not an ABI guarantee outside `@frozen` library-evolution types). Order
  fields by **decreasing alignment** to minimize padding:

```swift
struct Padded  { var a: Bool; var b: Int64; var c: Bool }  // stride 24
struct Compact { var b: Int64; var a: Bool; var c: Bool }  // stride 16
```

- Enums with payloads: size ≈ largest payload (+ tag, often packed into
  spare bits). `indirect` moves payloads to the heap.

## Value Types, Boxes, and CoW

- Structs/enums/tuples live inline (stack, or inside their container) — no
  allocation, no ARC… **unless** they contain references or get boxed.
- **Existential boxes**: `any Protocol` uses a 3-word inline buffer; values
  larger than 3 words are heap-allocated, and every call goes through witness
  tables. In hot paths prefer generics/`some` — they specialize to direct
  calls and inline storage. (`some` vs `any` deep dive: `deep-patterns.md`.)
- **Copy-on-write**: Array/Dictionary/Set/String/Data share storage and copy
  on first mutation of shared state. The check is
  `isKnownUniquelyReferenced(&buffer)` — use it in your own CoW types.
  Accidental second references (e.g., capturing in a closure) turn O(1)
  mutations into O(n) copies.
- Mixed value/reference structs still pay ARC on the reference fields per
  copy.

## ARC Traffic (the invisible cost)

- Each copy of a reference may retain/release — atomic RMWs that contend on
  hot objects (see `performance-engineering` atomics section).
- Reduce traffic: tighter scopes, `let` bindings outside loops,
  `borrowing`/`consuming` parameter modifiers and `consume` operator
  (explicit ownership, avoids retain/release pairs), `~Copyable` types for
  move-only resources.
- `withExtendedLifetime(x) { ... }` pins a lifetime when interfacing with
  unsafe pointers — the optimizer may otherwise release after last use,
  mid-closure.
- Profile with Instruments Allocations + the ARC-related time in Time
  Profiler before micro-tuning.

## Contiguity & Collections

- `Array` of structs is contiguous (great locality). `Array` of classes is an
  array of pointers — pointer-chasing per element (see AoS/SoA in
  `performance-engineering`).
- `ContiguousArray` skips NSArray-bridging paths for class elements.
- `reserveCapacity(_:)` before known-size appends — growth reallocations are
  O(n) copies.
- `InlineArray<N, T>` (Swift 6.2+): fixed-size, inline (stack/embedded)
  storage — no heap, no CoW. `Span`/`RawSpan`: safe, non-owning, non-escaping
  views over contiguous memory — prefer them over unsafe buffer pointers for
  zero-copy slicing (see `apple-platforms` InlineArray/Span reference).
- `lazy` avoids intermediate array materialization in mapped/filtered chains
  consumed once.

## Cross-Module & Specialization

- Generics specialize within a module; across resilient module boundaries
  calls may go unspecialized — `@inlinable`/`@_specialize` (and `@frozen` for
  layout) expose implementation for performance at an ABI-stability cost.
- `@inline(always)` (formalized in recent Swift; historically
  `@inline(__always)`) for tiny hot functions only — measure, don't sprinkle.
- Whole-module optimization is the baseline for release builds.

## Apple Silicon Notes

- **Cache line is 128 bytes** (vs 64 on x86-64) — pad per-thread hot data
  accordingly to dodge false sharing.
- Unified memory: CPU↔GPU share physical memory — `MTLStorageMode.shared`
  buffers avoid copies (see `graphics` skill).
- Performance vs efficiency cores are steered by QoS — see
  `../concurrency/scheduling-qos.md`.

## Unsafe Performance APIs (last resort, with invariants)

`withUnsafeTemporaryAllocation`, `withUnsafe(Mutable)BufferPointer`,
`assumingMemoryBound` — every use needs the `memory-safety` skill's
owner/lifetime/bounds statement, and pointers must not escape the closure.

## Checklist (hot-path Swift)

- [ ] Measured first; this path is actually hot (`performance-engineering`)
- [ ] No accidental CoW copies (uniqueness preserved across mutations)
- [ ] No existential boxing in the loop (`some`/generics instead of `any`)
- [ ] ARC traffic minimized (borrowing/consuming where it matters)
- [ ] Contiguous storage; capacity reserved; lazy where single-pass
- [ ] Struct field order minimizes stride (verified via MemoryLayout)
- [ ] Per-thread mutable state padded to the cache line (128 B on Apple
      Silicon) if accessed concurrently

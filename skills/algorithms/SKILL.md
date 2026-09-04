---
name: algorithms
description: >-
  Language-agnostic: choose data structures, analyze time and space complexity, and reason
  about algorithm correctness. Use for nontrivial loops, recursion, graph algorithms,
  dynamic programming, boundary errors, and scaling tradeoffs. For measured speed and
  hardware profiling, use `performance-engineering`.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Algorithms & Complexity

**State the complexity, time and space with n defined, before accepting any non-trivial loop,
recursion, or data-structure choice.** A choice made without that number is a guess about how the
code scales, and the guess is usually discovered at production size.

This skill owns **design-time cost**: what an approach will cost as input grows. It does not own
what it costs on a particular machine today — that is measured, not derived
(`performance-engineering`).

## Contract

```
§STATE    ! define n precisely BEFORE stating complexity
§SCALE    justify ∀realistic-input-size ¬asymptotics-alone
§PROOF    greedy ⇒ ! exchange-argument ∨ ⇒ label-heuristic ¬algorithm
§INVARIANT non-obvious-loop ⇒ ! state invariant{init; maintain; terminate}
§SHIP     clear O(n log n) ≻ clever unproven O(n)
§BAN      unbounded-recursion · complexity-claim ∅defined-n ·
          asymptotic-argument ∀tiny-n
```

---

## 1. Analysis protocol

1. **Define n precisely** — "n = items rendered", not "the data". Name m and k too where a second
   dimension exists. Most wrong complexity claims are wrong because n was never pinned down.
2. **Derive time and space.** Note amortized versus worst case where it matters — dynamic array
   append, hash map probe.
3. **Check the realistic input size.** O(n²) at n ≤ 100 is fine; at n = 10⁶ it is an outage.
   Justify against actual scale, not asymptotics alone.
4. **Constant factors and locality matter at small n.** An array beats a linked structure in
   practice for most small collections, whatever the table says.
5. **Self-check before finishing.** Re-derive the stated complexity from the actual loop nesting
   and recursion structure of the code as written, not from the intended design, and walk the
   boundaries of §4 once more. A complexity claim that drifted from the code is the commonest
   error in this domain.

## 2. Data-structure selection

| Need | Structure | Key costs |
|---|---|---|
| Index lookup, iteration | Dynamic array | O(1) index; O(n) middle insert; amortized O(1) append |
| Membership, key → value | Hash set/map | O(1) average, O(n) worst; no order |
| Ordered keys, range queries | Balanced BST / B-tree | O(log n) ops, sorted iteration |
| FIFO / LIFO | Ring buffer / stack | O(1) at the ends |
| "Next best" | Binary heap | O(log n) push/pop, O(1) peek |
| Prefix or string search | Trie | O(len) ops |
| Relationships, reachability | Graph (adjacency list) | BFS/DFS O(V+E) |
| Append-heavy text editing | Rope / gap buffer | Avoids O(n) copies |

**The selection question**: which operations dominate, at what frequency, over how many elements?
Choose for the dominant operation, not the most frequent one in the source code.

## 3. Algorithm families — recognition cues

- **Divide and conquer** — independent subproblems (sorting, search). Solve T(n) with the Master
  theorem.
- **Dynamic programming** — overlapping subproblems *and* optimal substructure (edit distance,
  knapsack). **State the recurrence before writing code**, then memoize top-down or tabulate
  bottom-up.
- **Greedy** — locally optimal is globally optimal **only with a proof**, usually an exchange
  argument. Without one it is a heuristic; say so rather than implying optimality.
- **Graph** — model as nodes and edges first. BFS for shortest unweighted path, Dijkstra for
  non-negative weights, topological sort for dependencies, union-find for connectivity.
- **Two pointers / sliding window** — sorted data or contiguous ranges in O(n) instead of O(n²).
- **Binary search** — applies to **any monotonic predicate**, not only sorted arrays. This is the
  most under-used tool on the list.

## 4. Correctness

- **State the loop invariant** for non-obvious loops, and check all three parts: it holds at
  initialization, it is maintained by each iteration, and at termination it gives the result.
- **Off-by-one audit at every boundary**: empty input, single element, full range, duplicates,
  integer overflow.
- **Recursion**: prove the base case is reachable and bound the depth. Unbounded recursion on
  attacker-influenced input is a denial-of-service vector, not just a crash.

## 5. Trade-off levers

- **Space ↔ time** — caching, memoization, precomputed indices.
- **Exact ↔ approximate** — Bloom filter, HyperLogLog, sampling. Legitimate only when the error
  tolerance is explicit and stated.
- **Worst case ↔ typical case** — randomization (quickselect), hashing. Know the adversarial case
  before relying on the typical one.
- **Optimal ↔ shippable** — a clear O(n log n) beats a clever unproven O(n). Complexity in the
  code is a cost too, paid by every future reader.

## Boundaries

| Need | Skill |
|---|---|
| Proving a change is actually faster; profiling | `performance-engineering` |
| Cache locality, branch prediction, the constant factors | `performance-engineering` |
| Property-based testing of invariants | `testing` |
| GPU-parallel formulations | `graphics` |
| Root-causing a wrong result | `debugging` |

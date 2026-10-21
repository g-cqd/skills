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

**State the time and space complexity, with n defined, before you accept a nested loop, a loop
that calls a non-constant-time operation, a recursion, or the choice of a collection whose size
grows with input in the code you write or review.** Without that number the choice is a guess
about scaling.

This skill covers design-time cost: how cost grows with input size. Cost on a specific machine is
measured, not derived; use `performance-engineering` for it.

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

1. **Define n precisely**: "n = items rendered", not "the data". Name m and k when a second
   dimension exists.
2. **Derive time and space.** State amortized and worst case separately when they differ (dynamic
   array append, hash map probe).
3. **Check the realistic input size.** O(n²) at n ≤ 100 is acceptable; at n = 10⁶ it is not.
   Justify the choice against the actual input size, not asymptotics alone.
4. **At small n, constant factors and locality decide.** When the input size from step 3 is too
   small for the asymptotic term to dominate, prefer a contiguous array to a linked structure.
   Measure with `performance-engineering` before you claim a speed difference.
5. **Self-check before finishing.** Re-derive the complexity from the loop nesting and recursion of
   the code as written, not from the intended design. Check the boundaries in §4 again.

## 2. Data-structure selection

To select, find which operations dominate the run time, how frequently each runs, and over how
many elements. Choose for the operation that dominates run time, not the one that appears most
often in the source code.

## 3. Algorithm families: recognition cues

- **Dynamic programming**: overlapping subproblems and optimal substructure (edit distance,
  knapsack). Write the recurrence before the code, then memoize top-down or tabulate bottom-up.
- **Greedy**: correct only with a proof, usually an exchange argument. Without a proof, label the
  result a heuristic, not an optimal algorithm.
- **Graph**: model nodes and edges first.
- **Two pointers / sliding window**: sorted data or contiguous ranges in O(n) instead of O(n²).
- **Binary search**: applies to any monotonic predicate, not only sorted arrays.

## 4. Correctness

- **State the loop invariant** for each loop whose correctness is not clear from reading it. Check
  that the invariant holds at initialization, holds after each iteration, and gives the result at
  termination.
- **Check each boundary** of each loop and index in the changed code: empty input, single element, full
  range, duplicates, integer overflow.
- **Recursion**: show that the base case is reachable and bound the depth. Unbounded recursion on
  attacker-influenced input is a denial-of-service vector; use an explicit stack or a depth limit
  there.

## 5. Trade-off levers

- **Space ↔ time**: caching, memoization, precomputed indices.
- **Exact ↔ approximate**: Bloom filter, HyperLogLog, sampling. Use only when the error tolerance
  is explicit and stated.
- **Worst case ↔ typical case**: randomization (quickselect), hashing. Identify the adversarial
  input before you rely on the typical case.
- **Optimal ↔ shippable**: a clear O(n log n) beats a clever unproven O(n), because every future
  reader pays for the extra complexity.

## Boundaries

| Need | Skill |
|---|---|
| Proving a change is actually faster; profiling | `performance-engineering` |
| Cache locality, branch prediction, the constant factors | `performance-engineering` |
| Property-based testing of invariants | `testing` |
| GPU-parallel formulations | `graphics` |
| Root-causing a wrong result | `debugging` |

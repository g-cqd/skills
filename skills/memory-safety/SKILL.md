---
name: memory-safety
description: >-
  Language-agnostic memory safety, with Swift unsafe APIs and C -fbounds-safety. Use for
  pointer or ownership review, untrusted binary parsers, buffer overflows, use-after-free,
  retain cycles, sanitizer selection, and bounds annotations. For trust-boundary security,
  use `secure-coding`; for build hardening, use `xcode`; for cache and data-layout
  performance, use `performance-engineering`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Memory Safety

This skill owns whether memory accesses are **valid**: in bounds, alive, initialized, and of the
right type. It does not own whether the program is *fast* (`performance-engineering`) or whether
an attacker can *reach* the code (`secure-coding`).

Sections 1–6 are language-agnostic and complete on their own. Section 7 is Apple-specific; skip it
unless you are working in Swift or in C with the Apple toolchain.

## Contract

```
§IRON-LAW unsafe-code ∷ guilty-until-proven-safe
          ∀unsafe-block ! state{owner; lifetime; bounds} ∨ ⇒ finding
§GOALS    completeness∧correctness ≻ security∧safety ≻ perf
          ⇒ ¬disable-a-check to gain speed
§ORDER    fix-root-cause ≻ add-mitigation
          mitigation ∷ raises-exploitation-cost ¬fixes-bug
§ESCAPE   unsafe-cast | forge ⇒ ! centralized ∧ audited ∧ commented
§BAN      disable-a-runtime-safety-check · return a view outliving its storage ·
          naked new|malloc ∈ new-code
```

---

## 1. Violation classes

Name the class before proposing a fix — the class determines where to look.

| Class | Kind | Typical symptom | CWE |
|---|---|---|---|
| Out-of-bounds read/write | Spatial | Corruption "far away"; crash in unrelated code | CWE-125 / 787 |
| Use-after-free | Temporal | Works in debug, crashes in release; heap corruption | CWE-416 |
| Double free | Temporal | Allocator abort; exploitable heap state | CWE-415 |
| Dangling stack pointer | Temporal | Garbage values after return | CWE-562 |
| Uninitialized read | Initialization | Nondeterministic behavior; information leak | CWE-457 |
| Type confusion | Type | "Impossible" values; vtable crash | CWE-843 |
| Data race on shared memory | Concurrency | Heisenbugs; undefined behavior | CWE-362 |

Memory corruption is the classic root of exploitable bugs — historically cited as roughly 70% of
severe CVEs in large C and C++ codebases, which is the motivation for memory-safe-by-default
languages.

**Symptom → first hypothesis.** Crash far from the mutation: spatial. Debug-clean but
release-crashing: temporal. Nondeterministic values: uninitialized. Impossible enum or vtable
value: type confusion. Only under load: race.

### The length-field disagreement — the parser bug that keeps shipping

The dominant root cause in real-world file- and media-parser exploits is a **buffer sized from one
field and filled according to another that can disagree**. The attacker controls both, sets them
inconsistently, and the write runs past the allocation.

The in-the-wild iOS RawCamera bug (CVE-2025-43300, patched iOS 18.6.2) is the canonical shape: a
DNG carried a JPEG-Lossless stream whose internal `SOF3` component count contradicted the outer
TIFF `SamplesPerPixel`. The decoder sized buffers from the TIFF metadata, then trusted the
embedded stream while decoding — out-of-bounds write. This is a **zero-click** surface, because
the OS media pipeline eagerly previews attacker-delivered images with no user tap.

The rule that closes the whole class:

- **One length, one source of truth.** Derive the buffer size and the fill loop from the *same*
  validated value. Never size from a header and iterate on a body count.
- **Validate cross-field invariants before allocating**: every count, offset, and size that a
  second field also implies must be checked to agree, up front, against the actual byte length.
- **Reject, don't clamp.** A mismatched length is a malformed input to refuse, not a value to
  silently truncate into range.
- **Treat every previewed media format as an attack surface** — the parser runs before any human
  decision. Parse untrusted bytes in a bounds-safe language or under `-fbounds-safety` (§7.2), and
  run it with the hardened-runtime mitigations `xcode` enables (§4, PAC/MTE).

---

## 2. Ownership and lifetime models

Choose deliberately; each model trades a guarantee for a cost.

| Model | Guarantees | Costs and hazards |
|---|---|---|
| Manual (C) | None — discipline only | Every class above |
| RAII + smart pointers (C++) | Scoped lifetime | UAF via raw `this` or views; iterator invalidation |
| Borrow checking (Rust-style) | Compile-time spatial + temporal | Learning curve; `unsafe` escape hatches |
| Reference counting (ARC, `shared_ptr`) | Temporal, while referenced | Cycles leak — need weak refs; refcount traffic |
| Tracing GC | Temporal | Pauses and footprint; finalizer hazards |
| Exclusivity enforcement | No overlapping read/write access | Runtime traps reveal real aliasing bugs |

Rules that hold in **every** model:

- **One owner per allocation.** Everything else borrows. State which is which at API boundaries:
  who frees, and may the callee retain?
- **Never return or store a view that can outlive its storage** — slice, span, `string_view`,
  buffer pointer, or any borrowed reference.
- **Bounds travel with the pointer.** Pointer and count are one unit, never two parameters that a
  caller can desynchronize. Where the toolchain can enforce this, make it do so (§7.2).

---

## 3. Sanitizers

Cheap insurance. Run them in CI, not just locally.

| Tool | Catches | Notes |
|---|---|---|
| ASan | OOB, UAF, double-free | ~2× slowdown; run unit tests under it |
| TSan | Data races | Mutually exclusive with ASan — separate CI job |
| UBSan | Overflow, misalignment, bad casts | Cheap; combine with ASan |
| MSan | Uninitialized reads | Clang; mostly non-Darwin; needs a full rebuild |
| libFuzzer / AFL + ASan | Parser and decoder corruption | Pair with the fuzzing guidance in `testing` |

Debug-only checks — guard malloc, debug iterators — catch strictly less than sanitizers. They are
not a substitute.

A code path with no sanitizer coverage is an untested path. If the CI job is missing, that is a
finding.

---

## 4. Hardware and platform mitigations

Defense in depth. Each raises exploitation cost; none fixes the bug.

- **ASLR + W^X (DEP/NX)** — baseline everywhere. Do not defeat it with predictable mappings or
  RWX pages; a JIT needs a deliberate design here.
- **Stack canaries and shadow stacks** — detect return-address smashing.
- **PAC** (ARM pointer authentication) — signs return addresses and function pointers.
- **MTE** (ARM Memory Tagging) — probabilistic spatial *and* temporal detection through tagged
  pointers.
- **CHERI** — research and early deployment; pointers carry bounds and permissions in hardware.

Mitigations are a layer, never the fix. Report the root cause.

---

## 5. Language comparison

Where the unsafe surface lives, by language. Grep this surface first — it bounds the audit.

| Language | Safety default | Unsafe surface to audit |
|---|---|---|
| C | None | Every pointer; see §7.2 for compiler-enforced bounds |
| C++ | Scoped lifetime via RAII | Raw `new`/`malloc`, raw `this`, views outliving storage, iterator invalidation |
| Rust | Compile-time ownership | `unsafe` blocks, raw pointer derefs, FFI |
| Swift | Memory-safe | See §7.1 |
| Kotlin / JVM | Memory-safe runtime | JNI, `sun.misc.Unsafe` — apply the C rules there |
| Go | GC + bounds checks | `unsafe.Pointer`, cgo |

In every memory-safe language the rule is the same: the unsafe surface is **explicit and
greppable**. Inventory it before reading anything.

---

## 6. Review workflow

This is defensive review of code the user owns or is authorised to review: the goal is to find
and fix the defect, and each finding states the concrete input or state that triggers it.

1. **Inventory before reading.** Grep the unsafe surface for the language (§5). Know the size of
   the problem first.
2. **State the invariant for each unsafe site**: owner, lifetime, bounds. If you cannot state it,
   that is the finding — write it up rather than guessing the code is fine.
3. **Walk the sad paths.** Error and early-return paths are where temporal bugs live: leaks,
   double frees, cleanup that runs twice or not at all.
4. **Confirm sanitizer coverage** for the path. Recommend the missing CI job by name. Fuzz any
   parser of untrusted input — it is the highest-yield target (§1, length disagreement).
5. **For any parser of attacker-reachable bytes**, check that buffer sizes and fill counts derive
   from one validated length, and that cross-field size/offset/count invariants are verified
   before allocation. This is where zero-click chains start.
6. **Report** with `file:line`, the violation class, the triggering input or state, and the
   root-cause fix. A mitigation is not a fix. Before finishing, check each finding: one without a
   concrete triggering input or state is down-ranked to a concern, because the reader cannot
   verify it.

---

## 7. Apple platforms

Everything below is Apple-specific. Enabling the corresponding build settings — PAC, MTE, Enhanced
Security, bounds-safety flags — belongs to `xcode`.

### 7.1 Swift

Swift is memory-safe by default. The unsafe surface is explicit and greppable:

```
Unsafe*Pointer   unsafeBitCast   unowned(unsafe)   withUnsafe*
.assumingMemoryBound   C interop
```

Review each site for:

- **Bounds proven** — not assumed from a sibling parameter.
- **Lifetime pinned** — `withExtendedLifetime` where the owner could be released early.
- **No escape** — a pointer obtained inside `withUnsafe*` must not outlive the closure. This is
  the single most common Swift memory bug.
- **Alignment respected** on rebinding.

**Exclusivity violations trap at runtime and are genuine aliasing bugs.** Fix the overlapping
access rather than disabling the check; the trap is reporting a real bug, and silencing it only
hides the corruption.

Data races are compile-time errors under Swift 6 strict concurrency — that is `swift`, not this
skill.

### 7.2 C: `-fbounds-safety`

In ordinary C a pointer is a *point*: it knows its start, never its end, and the end travels by
convention. `-fbounds-safety` makes a pointer a *range* that knows both. Out-of-bounds access
becomes a deterministic trap instead of an exploitable vulnerability.

Annotations and intrinsics come from `ptrcheck.h`. **Include it unconditionally** — it ships
flag-off fallbacks, so annotations expand to nothing and intrinsics to plain casts when the flag
is absent. The only exceptions are `__bidi_indexable` and `__indexable` (and their
`__ptrcheck_abi_assume_*` cousins), deliberately left undefined so that misuse in a header is a
compile error rather than a silent ABI break. Only code naming those two by token needs
`#if __has_ptrcheck`.

#### Pointer kinds and annotations

| Annotation | Meaning | ABI compatible | Default for |
|---|---|---|---|
| `__single` | Exactly one element, or NULL. No arithmetic. | Yes | ABI-visible pointers |
| `__bidi_indexable` | Wide pointer: lower bound, upper bound, current. Full arithmetic. | **No** | ABI-hidden pointers (locals) |
| `__indexable` | Upper bound + current. Forward arithmetic only. | **No** | explicit only |
| `__unsafe_indexable` | No bounds, no checks. Escape hatch. | Yes | system/SDK headers |
| `__counted_by(N)` | N elements | Yes | explicit only |
| `__sized_by(N)` | N bytes | Yes | explicit only |
| `__ended_by(P)` | Range from pointer to P | Yes | explicit only |
| `__counted_by_or_null(N)` | `__counted_by`, NULL permitted | Yes | explicit only |
| `__sized_by_or_null(N)` | `__sized_by`, NULL permitted | Yes | explicit only |
| `__null_terminated` | 0-terminated; arithmetic limited to +0/+1 | Yes | ABI-visible `const char *` |
| `__terminated_by(T)` | T-terminated; arithmetic limited to +0/+1 | Yes | explicit only |

#### ABI visibility decides the default

**ABI-visible** — parameters, returns, globals, struct fields — default to `__single`, so
arithmetic on them is a compile-time error and layout is unchanged. **ABI-hidden** — essentially
only local variables — default to `__bidi_indexable`, a wide pointer.

Only the *top-level* pointer is ABI-hidden: `element_t **p` in a body is an ABI-hidden pointer to
an ABI-visible pointer.

Bounds checks on a `__bidi_indexable` fire when the pointer is dereferenced or when its bounds are
stripped — not on the arithmetic itself. Creating a temporarily out-of-bounds pointer and bringing
it back is legal.

Prefer the default wide pointer for locals; copy a parameter into a local to get one.

#### Attribute placement binds to the nearest `*`

Every attribute attaches to **the `*` immediately preceding it**, not to the variable. On
multi-level pointers this changes the meaning entirely:

| Declaration | Meaning |
|---|---|
| `int *__single *p` | pointer to (`int *__single`) |
| `int **__single p` | `__single` pointer to `int *` |
| `int *__counted_by(*n) *p` | pointer to a counted `int *` — the **OUT / IN-OUT** shape |
| `int **__counted_by(n) p` | counted **array of pointers** |
| `int *__single *__counted_by(*n) p` | real SDK form (`malloc_get_all_zones`) |

Diagnostics print this parse verbatim: `int **__bidi_indexable p` is reported as
`int *__single *__bidi_indexable`.

#### Adoption

Two approaches:

- **Full** — annotate headers *and* compile implementations with the flag. Complete enforcement.
- **Header-only** — annotate public headers only; the implementation is untouched and unflagged.
  Clients adopting the flag benefit at no runtime cost to you. Not applicable if there are no
  headers.

Ask the user which approach they want before advising, and read
`references/c-bounds-safety/adoption-strategies.md`, `language-overview.md` and
`common-patterns-and-pitfalls.md` before any source edit. Adoption commits at several review
checkpoints, so it has two prerequisites:

- **A clean working tree under version control.** Detect the VCS (the innermost one if several)
  without asking and record its status, diff, stage-by-path, commit and discard-file commands; use
  those throughout rather than assuming git. With no VCS, or a dirty tree, stop and ask the user
  to fix that and retry; pre-existing changes would be bundled into adoption commits.
- **Under Xcode, one build system as the source of truth:** the shallowest `.xcworkspace`
  (preferred) or `.xcodeproj` in the tracked tree, asking when several tie. SwiftPM cannot attach
  per-file C flags, so it is not a valid source of truth; any other system (a Makefile, say) must
  support per-file flags, and you record its mechanism. A generated project (xcodegen, Tuist, a
  generator script) silently loses per-file flags on regeneration, so warn before starting.

Full adoption is an iterative loop, per file: enable, compile, read diagnostics, annotate, repeat.
The four change kinds:

1. **Replace implicit annotations with explicit ones.**
   ```c
   // before
   void take_elements(const element_t *elements, size_t count);
   // after
   void take_elements(const element_t *__counted_by(count) elements, size_t count);
   ```
   Avoid ABI-incompatible `__indexable` / `__bidi_indexable` on consumer-facing API, and avoid
   `__unsafe_indexable`, which defeats the purpose.

2. **Adapt implementations to the new restrictions.** A counted pointer and its count must move
   together — this is the `requires corresponding assignment to 'count'` diagnostic:
   ```c
   // before — error: assignment to 'int *__single __counted_by(count)' requires
   //          corresponding assignment to 'count'
   while (idx < count && *elements != 0) { ++elements; ++idx; }

   // after — keep the bound in sync, compare against a saved original
   size_t original_count = count;
   while (idx < original_count && *elements != 0) { ++elements; --count; ++idx; }
   ```

3. **Propagate annotation choices.** Changing an API's bounds changes every use site; expect
   several rounds.

4. **Centralize the unsafe surface.** When ingesting `__unsafe_indexable` pointers from
   non-adopted code, do **not** propagate them. Consume them in a few audited places, forge a safe
   pointer (`__unsafe_forge_bidi_indexable`), and propagate that. The unsafe sources stay small
   and reviewable.

Adoption spans many files. Track it with explicit tasks: confirm the approach and the test command
with the user first, then one task per implementation file, then target-wide enablement, then
post-adoption refinement. Never mark a file done before its sub-steps are done; if a sub-step does
not apply, close it with a one-line reason rather than silently.

#### Build flags

Enable per file during incremental adoption, project-wide once complete. Useful flags:
`-ferror-limit=0` (see all diagnostics, not the first 20), `-ffreestanding`,
`-fbounds-safety-unique-traps` (distinct trap per site, for attribution), and
`-fbounds-safety-soft-traps=call-minimal` (log instead of abort — for staged rollout only, never
as the end state).

Accessing bounds: `__ptr_lower_bound(p)` and `__ptr_upper_bound(p)`.

---

## Boundaries

| Need | Skill |
|---|---|
| Enabling PAC, MTE, Enhanced Security, bounds-safety build settings in Xcode | `xcode` |
| Trust boundaries, injection, secrets, crypto misuse | `secure-coding` |
| Cache lines, data layout, false sharing, allocation cost | `performance-engineering` |
| Swift concurrency and data-race elimination | `swift` |
| Fuzzing methodology and test design | `testing` |
| Root-causing a specific crash | `debugging` |

## References

Apple-specific, supporting §7.2:

- `references/c-bounds-safety/language-overview.md` — full language reference: conversion tables,
  flexible array members, value-terminated arrays, out/in-out parameter shapes, forging rules.
- `references/c-bounds-safety/adoption-strategies.md` — the complete full and header-only adoption
  workflows.
- `references/c-bounds-safety/common-patterns-and-pitfalls.md` — real-world recipes and
  anti-patterns.
- `references/c-bounds-safety/runtime-debugging.md` — trap behavior, LLDB commands, wide-pointer
  inspection, watchpoints, crash-log analysis.
- `references/c-bounds-safety/build-settings.md` — compiler flags, Xcode settings, soft-trap mode.

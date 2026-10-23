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

This skill decides whether memory accesses are **valid**: in bounds, alive, initialized, and of the
right type. Speed belongs to `performance-engineering`. Whether an attacker can reach the code
belongs to `secure-coding`.

Sections 1–6 are language-agnostic and complete. Section 7 is Apple-specific; read it only for
Swift or for C built with the Apple toolchain.

## Contract

```
§IRON-LAW unsafe-code ∷ guilty-until-proven-safe
          ∀unsafe-block ! state{owner; lifetime; bounds} ∨ report-as-finding
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

Name the class before you propose a fix. The class tells you where to look.

| Class | Kind | Typical symptom | CWE |
|---|---|---|---|
| Out-of-bounds read/write | Spatial | Corruption "far away"; crash in unrelated code | CWE-125 / 787 |
| Use-after-free | Temporal | Works in debug, crashes in release; heap corruption | CWE-416 |
| Double free | Temporal | Allocator abort; exploitable heap state | CWE-415 |
| Dangling stack pointer | Temporal | Garbage values after return | CWE-562 |
| Uninitialized read | Initialization | Nondeterministic behavior; information leak | CWE-457 |
| Type confusion | Type | "Impossible" values; vtable crash | CWE-843 |
| Data race on shared memory | Concurrency | Heisenbugs; undefined behavior | CWE-362 |

**Symptom → first hypothesis.** Crash far from the mutation: spatial. Clean in debug, crashes in
release: temporal. Nondeterministic values: uninitialized. Impossible enum or vtable value: type
confusion. Fails only under load: race.

### The length-field disagreement — the parser bug that keeps shipping

The most common root cause in real-world file and media parser exploits: **the code sizes a buffer
from one field and fills it according to another field, and the two can disagree.** The attacker
controls both fields, sets them inconsistently, and the write runs past the allocation.

Example: the in-the-wild iOS RawCamera bug (CVE-2025-43300, patched iOS 18.6.2). A DNG's
JPEG-Lossless `SOF3` component count contradicted the outer TIFF `SamplesPerPixel`; the decoder
sized buffers from the TIFF value and decoded by the stream value, writing out of bounds. The
surface is **zero-click**: the OS media pipeline previews attacker-delivered images with no tap.

Rules that close the class, for each parser of untrusted bytes:

- **One length, one source of truth.** Derive the buffer size and the fill loop from the *same*
  validated value. Do not size from a header and iterate on a body count.
- **Validate cross-field invariants before allocating.** For each count, offset, and size that a
  second field also implies, check that the two agree and fit the actual byte length.
- **Reject, do not clamp.** Refuse a mismatched length as malformed input. Do not truncate it into
  range.
- **Treat each previewed media format as an attack surface**, because the parser runs before any
  human decision. Parse untrusted bytes in a bounds-safe language or under `-fbounds-safety`
  (§7.2), and run the parser with the hardened-runtime mitigations that `xcode` enables (§4 here;
  enabled in `xcode` §7.3).

---

## 2. Ownership and lifetime models

| Model | Guarantees | Costs and hazards |
|---|---|---|
| Manual (C) | None — discipline only | Every class above |
| RAII + smart pointers (C++) | Scoped lifetime | UAF via raw `this` or views; iterator invalidation |
| Borrow checking (Rust-style) | Compile-time spatial + temporal | Learning curve; `unsafe` escape hatches |
| Reference counting (ARC, `shared_ptr`) | Temporal, while referenced | Cycles leak — need weak refs; refcount traffic |
| Tracing GC | Temporal | Pauses and footprint; finalizer hazards |
| Exclusivity enforcement | No overlapping read/write access | Runtime traps reveal real aliasing bugs |

Rules for every model:

- **One owner per allocation.** All other holders borrow. At each API boundary, state who frees
  the memory and whether the callee may retain it.
- **Do not return or store a view that can outlive its storage**: slice, span, `string_view`,
  buffer pointer, or any borrowed reference. Return an owning type instead, or extend the
  storage's lifetime to cover the view.
- **Bounds travel with the pointer.** Pass pointer and count as one unit, not as two parameters
  that a caller can desynchronize. Where the toolchain can enforce this, enable it (§7.2).

---

## 3. Sanitizers

Run sanitizers in CI, not only locally.

| Tool | Catches | Notes |
|---|---|---|
| ASan | OOB, UAF, double-free | ~2× slowdown; run unit tests under it |
| TSan | Data races | Mutually exclusive with ASan — separate CI job |
| UBSan | Overflow, misalignment, bad casts | Cheap; combine with ASan |
| MSan | Uninitialized reads | Clang; mostly non-Darwin; needs a full rebuild |
| libFuzzer / AFL + ASan | Parser and decoder corruption | Pair with the fuzzing guidance in `testing` |

Debug-only checks (guard malloc, debug iterators) catch strictly less than sanitizers. They do not
replace sanitizers.

A code path with no sanitizer coverage is an untested path. Report a missing sanitizer CI job as a
finding.

---

## 4. Hardware and platform mitigations

Each mitigation raises exploitation cost. None fixes the bug (§ORDER): report the root cause.

- **ASLR + W^X (DEP/NX)** — baseline on every platform. Do not defeat them with predictable
  mappings or RWX pages. A JIT needs a dedicated W^X design.
- **Stack canaries and shadow stacks** — detect return-address overwrites.
- **PAC** (ARM pointer authentication) — signs return addresses and function pointers.
- **MTE** (ARM Memory Tagging) — probabilistic spatial *and* temporal detection through tagged
  pointers.

---

## 5. Language comparison

The unsafe surface for each language. Search this surface first; it bounds the audit.

| Language | Safety default | Unsafe surface to audit |
|---|---|---|
| C | None | Every pointer; see §7.2 for compiler-enforced bounds |
| C++ | Scoped lifetime via RAII | Raw `new`/`malloc`, raw `this`, views outliving storage, iterator invalidation |
| Rust | Compile-time ownership | `unsafe` blocks, raw pointer derefs, FFI |
| Swift | Memory-safe | See §7.1 |
| Kotlin / JVM | Memory-safe runtime | JNI, `sun.misc.Unsafe` — apply the C rules there |
| Go | GC + bounds checks | `unsafe.Pointer`, cgo |

---

## 6. Review workflow

This is defensive review of code the user owns or is authorised to review. The goal is to find and
fix the defect. Each finding states the concrete input or state that triggers it.

1. **Inventory before reading.** Grep the files in review scope for the unsafe surface of their
   language (§5). Record the count of sites.
2. **State the invariant for each unsafe site**: owner, lifetime, bounds. If you cannot state the
   invariant, report that as the finding. Do not assume the code is correct.
3. **Walk the error paths.** Error and early-return paths hold most temporal bugs: leaks, double
   frees, cleanup that runs twice or not at all.
4. **Confirm sanitizer coverage** for each path you review. Name the missing CI job in the
   finding. For each parser of untrusted input, check for a fuzz target; if none exists, report
   that as a finding.
5. **For each parser of untrusted bytes**, apply the rules in §1 (length disagreement).
   Zero-click chains start here.
6. **Report** each finding with `file:line`, the violation class, the triggering input or state,
   and the root-cause fix. A mitigation is not a fix. Before finishing, check each finding: rank a
   finding with no concrete triggering input or state as a concern, because the reader cannot
   verify it.

The review is done when each site from step 1 has a stated invariant or a finding.

---

## 7. Apple platforms

This section is Apple-specific. Enabling the build settings (PAC, MTE, Enhanced Security,
bounds-safety flags) belongs to `xcode`.

### 7.1 Swift

Swift is memory-safe by default. The unsafe surface is explicit and greppable:

```
Unsafe*Pointer   unsafeBitCast   unowned(unsafe)   withUnsafe*
.assumingMemoryBound   C interop
```

Review each site for:

- **Bounds proven** — not assumed from a sibling parameter.
- **Lifetime pinned** — use `withExtendedLifetime` where the owner could be released early.
- **No escape** — a pointer obtained inside `withUnsafe*` must not outlive the closure. This is
  the most common Swift memory bug.
- **Alignment respected** on rebinding.

**An exclusivity violation that traps at runtime is a real aliasing bug.** Fix the overlapping
access. Do not disable the check; disabling it hides the corruption.

Data races are compile-time errors under Swift 6 strict concurrency. They belong to `swift`.

### 7.2 C: `-fbounds-safety`

`-fbounds-safety` makes a C pointer carry its bounds. An out-of-bounds access becomes a
deterministic trap instead of an exploitable vulnerability.

Include `ptrcheck.h` (annotations and intrinsics) without an `#if` guard in each file that uses
them; with the flag off, the header expands annotations to nothing and intrinsics to plain casts.
Exception: `__bidi_indexable` and `__indexable` (and their `__ptrcheck_abi_assume_*` variants)
are left undefined on purpose, so that misuse in a header is a compile error and not a silent ABI
break. Wrap only code that names one of those two tokens in `#if __has_ptrcheck`.

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

**ABI-visible** pointers (parameters, returns, globals, struct fields) default to `__single`.
Arithmetic on them is a compile-time error, and layout does not change. **ABI-hidden** pointers
(in practice, only local variables) default to `__bidi_indexable`, a wide pointer.

Only the *top-level* pointer is ABI-hidden: `element_t **p` in a function body is an ABI-hidden
pointer to an ABI-visible pointer.

Bounds checks on a `__bidi_indexable` run when the pointer is dereferenced or when its bounds are
stripped, not on the arithmetic. A pointer may go out of bounds temporarily and come back.

Use the default wide pointer for locals. To get one from a parameter, copy the parameter into a
local.

#### Attribute placement binds to the nearest `*`

Each attribute attaches to **the `*` immediately before it**, not to the variable. On multi-level
pointers this changes the meaning:

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
- **Header-only** — annotate public headers only; the implementation is not changed and not
  flagged. Clients that adopt the flag get the checks at no runtime cost to the library. Not
  applicable when the code has no headers.

Ask the user which approach they want before you advise. If you cannot ask the user, stop and
report both options. Before any source edit, read
`adopt-c-bounds-safety/references/adoption-strategies.md`, `language-overview.md` and
`common-patterns-and-pitfalls.md`. Adoption commits at several review checkpoints, so it has two
prerequisites:

- **A clean working tree under version control.** Detect the VCS without asking (the innermost one
  if several exist). Record its commands for status, diff, stage-by-path, commit and discard-file,
  and use those commands throughout; do not assume git. If there is no VCS or the tree has
  uncommitted changes, stop and ask the user to fix that and retry, because adoption commits would
  include the existing changes.
- **Under Xcode, one build system as the source of truth:** the shallowest `.xcworkspace`
  (preferred) or `.xcodeproj` in the tracked tree. Ask the user when several are at the same
  depth. SwiftPM cannot attach per-file C flags, so it is not a valid source of truth. Any other
  build system (for example a Makefile) must support per-file flags; record its mechanism. A
  generated project (xcodegen, Tuist, a generator script) loses per-file flags when it is
  regenerated, so warn the user before starting.

Full adoption is a loop for each file: enable, compile, read diagnostics, annotate, repeat. The
four kinds of change:

1. **Replace implicit annotations with explicit ones.**
   ```c
   // before
   void take_elements(const element_t *elements, size_t count);
   // after
   void take_elements(const element_t *__counted_by(count) elements, size_t count);
   ```
   Do not put ABI-incompatible `__indexable` / `__bidi_indexable` on consumer-facing API. Do not
   use `__unsafe_indexable` where a counted or sized annotation can express the bounds. Where none
   can, confine `__unsafe_indexable` to the audited places in change 4.

2. **Adapt implementations to the new restrictions.** A counted pointer and its count must change
   together. This is the `requires corresponding assignment to 'count'` diagnostic:
   ```c
   // before — error: assignment to 'int *__single __counted_by(count)' requires
   //          corresponding assignment to 'count'
   while (idx < count && *elements != 0) { ++elements; ++idx; }

   // after — keep the bound in sync, compare against a saved original
   size_t original_count = count;
   while (idx < original_count && *elements != 0) { ++elements; --count; ++idx; }
   ```

3. **Propagate annotation choices.** Changing an API's bounds changes each use site; expect
   several rounds.

4. **Centralize the unsafe surface.** Do **not** propagate `__unsafe_indexable` pointers that come
   from non-adopted code. Consume them in a few audited places, forge a safe pointer
   (`__unsafe_forge_bidi_indexable`), and propagate the forged pointer. This keeps the unsafe
   sources few and reviewable.

Track adoption with explicit tasks, in this order: confirm the approach and the test command with
the user; one task per implementation file; target-wide enablement; post-adoption refinement. Do
not mark a file done before its sub-steps are done. If a sub-step does not apply, close it with a
one-line reason.

#### Build flags

Enable the flag per file during incremental adoption and project-wide once adoption is complete.
Useful flags:

- `-ferror-limit=0` — show all diagnostics, not the first 20.
- `-ffreestanding`.
- `-fbounds-safety-unique-traps` — a distinct trap per site, for attribution.
- `-fbounds-safety-soft-traps=call-minimal` — log instead of abort. Use it for staged rollout
  only; do not leave it as the end state.

Read bounds with `__ptr_lower_bound(p)` and `__ptr_upper_bound(p)`.

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

Apple-specific, supporting §7.2. These files belong to the Xcode skill pack skill `adopt-c-bounds-safety`: `install.sh` exports the pack from Xcode 27.1 or later (see `xcode`, "Xcode skill pack"). When it is not installed, use `apple-docs`.

- `adopt-c-bounds-safety/references/language-overview.md` — full language reference: conversion tables,
  flexible array members, value-terminated arrays, out/in-out parameter shapes, forging rules.
- `adopt-c-bounds-safety/references/adoption-strategies.md` — the complete full and header-only adoption
  workflows.
- `adopt-c-bounds-safety/references/common-patterns-and-pitfalls.md` — real-world recipes and
  anti-patterns.
- `adopt-c-bounds-safety/references/runtime-debugging.md` — trap behavior, LLDB commands, wide-pointer
  inspection, watchpoints, crash-log analysis.
- `adopt-c-bounds-safety/references/build-settings.md` — compiler flags, Xcode settings, soft-trap mode.

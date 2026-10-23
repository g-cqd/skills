# Native code and binaries

Use with `memory-safety` when the target is C, C++, Objective-C, unsafe Rust or Swift, a parser or decoder of
untrusted bytes, an FFI boundary, a loader, a JIT, a kernel module, a driver, or firmware. `memory-safety` owns the
memory model, sanitizers, and bounds annotations; this file adds the hunting classes and the evidence rules.

## Discipline

- A finding names a realistic untrusted entry and the operation that breaks a bounds, type, lifetime, ABI,
  concurrency, loader, or authority invariant.
- Report the effect observed: invalid read, invalid write, stale alias, wrong object, uninitialized output,
  unauthorized image load, deadlock, or a safe abort. A crash is not code execution.
- Use the narrowest harness: an existing test, a small fixture, a sanitizer (ASan, UBSan, TSan), a short fuzz run with
  the existing corpus. Record the architecture and build flags.

## Classes

**Out-of-bounds read or write.** A length, offset, index, or terminator reaches a buffer without a correct bound.
Recompute the room left after prefixes, alignment, padding, and terminators; check both source and destination.

**Integer overflow, underflow, truncation, signedness.** Attacker-controlled arithmetic before allocation, copy,
loop, index, or pointer math: `a - b` with `b > a`, `count * size`, sums near the maximum, negative values cast to
unsigned, 64-to-32-bit truncation.

**Unit confusion.** Bytes, elements, code units, pages, or wire units mixed between parse, check, allocation, and
copy. A bounds check in the same wrong unit as the allocation is still wrong. One field sizes the buffer and another
fills it: the classic zero-click root.

**Uninitialized data.** A buffer, padding, or struct field is returned, hashed, or sent across a boundary before it
is written.

**Use-after-free, stale views, double free.** An owner is released while a callback, timer, iterator, borrowed slice,
or cached pointer can still use it; check error, cancel, close, and realloc paths.

**Type confusion.** A tag, vtable, discriminator, or handle is checked differently from the representation later read;
unchecked downcasts; stale tags after reuse.

**Ownership races.** Non-atomic reference counts, a check followed by an unlocked use, ownership that differs across
threads.

**Shared-state races and TOCTOU.** Concurrent streams, global caches, lazy initialization, signal handlers, or teardown
invalidate a bound or pointer established earlier. Reproduce with a deterministic schedule or TSan.

**Lock order and deadlock.** Externally reachable operations take locks in inconsistent order or hold them across
callbacks and blocking I/O (an availability finding only when bounded input stops shared progress).

**FFI contract mismatch.** Caller and callee disagree on who allocates, frees, pins, or mutates a buffer, how long a
pointer lives, or whether a length counts bytes or elements. Trace both sides of each `extern`, JNI, CGo, or Python
binding.

**Layout and ABI disagreement.** Structs, bitfields, packing, alignment, enums, integer widths, or calling conventions
that differ by architecture or build flag.

**Unwinding and thread affinity.** Exceptions or panics cross an ABI that forbids unwinding; callbacks run after
teardown; single-thread APIs called from another thread.

**Library search-order trust.** A privileged process loads a library, plugin, or helper from a path a less-trusted
principal can write, or resolves a bare name through the working directory or environment.

**Loader identity binding.** The loader verifies one file and maps another, through path resolution, replacement,
architecture slices, or embedded resources.

**Malformed binary metadata.** Offsets, counts, sections, relocations, symbols, or bytecode trusted before range and
overlap checks.

**JIT consistency.** Validator, interpreter, optimizer, and generated code disagree about types, bounds, or side
effects. Diff optimized and unoptimized runs on the same input.

**Unload and teardown.** Function pointers, callbacks, threads, or views survive module unload or runtime reset.

**Kernel double fetch.** A syscall, ioctl, or driver reads a fact from user memory, then reads the same address again.

**Privileged object lifecycle.** Unbalanced retain and release, teardown without draining observers, unchecked
dispatch-table indices in an externally reachable interface.

**Under-authorized interfaces.** A device node, admin socket, or helper checks message shape but not the caller's
authority over the resource.

## Moves

- For each parser or FFI boundary, tabulate the accepted length and type, the checked representation, the allocation
  owner, the consumer, the thread, and the teardown. Most native findings are one disagreement in that table.
- Audit duplicated paths and fixed siblings: a check in one caller, architecture, protocol role, or flag does not
  protect the others.
- Keep the exact sanitizer output and the input property that triggers it; do not build an exploit.

## Validation rules

1. The input, the source trace, and the observed effect are all stated; sanitizer coverage of the faulting operation
   is confirmed.
2. A concurrency claim uses a deterministic schedule or a sanitizer trace. A loading claim shows the checked identity
   differs from the mapped one and names the lower-trust writer.
3. An unresolved reachability, ABI, build, or runtime fact makes the candidate `needs_validation`.

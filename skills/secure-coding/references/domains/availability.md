# Resource exhaustion and availability

Use when untrusted work can consume shared CPU, memory, disk, connections, file handles, workers, queues, quotas, or
the operator's money.

## Discipline

- A finding names the untrusted input, the requester's cost, the service's amplification or retained resource, the
  shared blast radius (other users, tenants, the whole process), and the recovery.
- Missing limits without a concrete shared effect are hardening notes. Harm only to the requester's own session is
  not an availability finding.
- Never test availability against a live or shared process. Show growth with small, bounded local inputs.

## Classes

**Superlinear work.** Small accepted input drives regex backtracking, nested parsing, recursive validation, template
expansion, graph traversal, or adversarial hashing. Derive the accepted depth and size, then show growth.

**Decompression and expansion.** Compressed, nested, aliased, or encoded input expands far beyond the checked size:
archives, images, fonts, XML entities, YAML anchors. Limits must apply after each expansion.

**Query and fan-out amplification.** A small request causes broad scans, heavy joins, unbounded sorts, or many
downstream calls because depth, filters, pagination, or expansions are unbounded.

**Unbounded buffering and cardinality.** Bodies, streams, uploads, sessions, unique cache keys, metric labels,
subscriptions, or pending jobs grow without per-item and aggregate limits and without cleanup on disconnect or
cancel.

**Handle and temporary-resource leaks.** Malformed or canceled work skips cleanup and keeps sockets, files, cursors,
timers, subprocesses, or temp files.

**Work after cancellation.** A timeout, disconnect, or failed authorization returns control while database, model, or
worker work keeps running.

**Pre-authentication cost.** Expensive parsing, key lookup, cryptography, decompression, or outbound calls run before
authentication and the first size or rate gate.

**Quota accounting gaps.** Accounting keyed on attacker-influenced IP, route, tenant, or key prefix lets one
principal escape its budget or spend another's.

**Pool and priority starvation.** Attacker jobs hold locks, workers, database connections, or scheduler priority that
unrelated users need.

**Reachable fatal error or deadlock.** Untrusted input reaches a panic, abort, fatal assertion, unhandled exception,
lock cycle, or infinite loop in a shared process. Establish whether one worker or the whole service stops.

**Retry storms.** Failures trigger synchronized or unbounded retries without jitter, ceilings, or circuit breaking.

**Poison records.** One malformed message fails forever at the head of a shared queue, partition, or startup scan.

**Unsafe recovery.** A restart or restore rebuilds unbounded state, ignores quotas, or replays the input that caused
the failure.

## Moves

- Build an input-to-resource table: first accepted size, work before authentication, fan-out, persistence, shared
  pool, limit and cleanup owner, recovery.
- Compare aggregate limits with per-item limits: ten thousand valid one-byte items can pass a per-message cap.
- Validate in an isolated fixture with strict CPU, memory, and time limits and a few small growth points; mock paid
  calls.

## Validation rules

1. Confirm that no visible upstream, parser, queue, tenant, or framework bound stops the path; unknown deployed
   limits make the candidate `needs_validation`.
2. Superlinear claims show the accepted complexity and measured growth; leak claims show repeatable retention after
   cleanup should have run; fatal paths establish the supervisor's scope.
3. Rank by low requester cost, unauthenticated reach, cross-tenant scope, persistence, and poor recovery.

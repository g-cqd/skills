# Data isolation and lifecycle

Use when the target holds data for several tenants or owners, or keeps derived copies: caches, search indexes,
analytics, logs, exports, backups, replicas; or when it promises deletion, revocation, or retention.

## Discipline

- A tenant or owner field on a record is not isolation. Find the query, key, path, policy, or row-level rule that
  enforces it on each read and write path.
- Trace derived copies. Clean primary data can leak through search, cache, analytics, exports, previews, logs,
  replicas, and backups with different access and retention.
- Deletion and revocation are contracts: check current, historical, cached, indexed, exported, restored, and queued
  copies within the product's stated promise.
- A privacy preference is not automatically a security boundary. Require an explicit access boundary or deletion
  promise and an unauthorized reader or later operation.

## Classes

**Missing tenant or owner check.** A read, update, delete, list, count, or bulk query names an object without binding
it to the caller's tenant, or takes the tenant from the request body. Compare direct lookups, nested relations,
background jobs, admin paths, imports, and exports.

**Key and namespace collision.** Cache keys, object paths, unique constraints, search ids, temp files, or
deduplication keys omit the tenant or environment, so two principals read or overwrite one logical key.

**Policy and query disagreement.** Row-level policy, ORM default scopes, and raw or service clients apply different
predicates: joins, aggregates, views, `unscoped` clients, paths where the context is missing.

**Signed references and blobs.** Object keys, attachment ids, version ids, share links, or signed URLs allow more
operations or objects than the issuer could reach, or stay valid after the ACL changes.

**Index and cache ACL drift.** A record's ACL or lifecycle changes without invalidating its search, cache, embedding,
thumbnail, feed, or preview copy. Filter at retrieval time, not only at ingestion.

**Alternate readers.** Private content or credentials go into analytics, logs, traces, or diagnostics with broader
access or longer retention.

**Enumeration oracles.** Counts, filters, ordering, errors, unique-constraint failures, timing, or notifications
reveal protected state. Requires a concrete confidential predicate.

**Export and backup scope.** An export, snapshot, portability package, report, or backup includes other tenants,
hidden fields, deleted data, secrets, or history above the requester's access.

**Import and restore authority.** Restore or import skips owner, schema, ACL, uniqueness, or validation rules,
overwrites existing data, or writes into a tenant the requester cannot write.

**Migration defaults.** Old records lack tenant, ACL, or lifecycle fields; partial rollout makes old and new readers
apply different defaults.

**Backup and replica drift.** Keys, storage accounts, replicas, restore environments, or support snapshots have
broader access than primary data.

**Soft-delete bypass.** A lookup, search, relation, link, background job, or restore ignores the deleted flag; a
deleted identifier can be re-registered while old references remain.

**Stale authorization in copies.** Removed membership, changed ACLs, withdrawn consent, revoked secrets, or downgraded
roles do not invalidate sessions, caches, subscriptions, jobs, or materialized data.

**Retention overrun.** Deletion finishes in primary storage while queued work, retries, exports, or analytics recreate
or keep the data.

**Restore reintroduces invalid state.** Undo, undelete, or recovery restores data, credentials, memberships, or
permissions that current policy forbids.

## Moves

- Pick one protected record and draw its write, query, cache, index, event, export, backup, delete, and restore paths,
  with the principal and tenant at every edge.
- Run two dummy tenants through the same local service methods; repeat after an ACL change, a deletion, an account
  switch, and a restore.
- Start at bypass clients, background jobs, migrations, global uniqueness, and cache keys: they often lack the
  request-scoped identity that interactive routes carry.

## Validation rules

1. Name the lower-trust principal, the protected data, the affected owner or tenant, the alternate copy or
   operation, and the unauthorized read or change.
2. Cite both the intended policy and the path that omits or contradicts it, and confirm no other layer enforces it.
3. External cache, storage, replica, analytics, backup, or retention policy that decides the outcome makes the
   candidate `needs_validation`.

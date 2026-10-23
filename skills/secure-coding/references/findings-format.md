# Audit file formats

The formats of `findings.json` and `coverage-ledger.json` in audit mode (`audit-workflow.md`). Check both with
`python3 scripts/validate_audit.py findings FILE` and `python3 scripts/validate_audit.py ledger FILE` (Python 3.9 or
later, standard library only). The validator reports at most 100 errors and refuses a file over 5 MiB, more than
1,000 findings, more than 10,000 units, or nesting deeper than 64 levels. It checks structure and consistency, not
truth.

## Shared rules

- **Fingerprint:** stable across runs and states for one root cause; matches `^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$`; never
  contains a line number, a wave, an agent, a severity, or a verdict. Example: `api/users:update:missing-owner-check`.
- **Paths:** repository-relative, never absolute, never containing a `..` component.
- **Trace:** an ordered array of `{kind, file, line, scope, description}`, `line` an integer of at least 1. With one
  entry, `kind` is `entrypoint` or `sink`. With several, the first is `entrypoint`, the last is `sink`, and the others
  are `propagation`.
- **Evidence:** a non-empty array of `{file, line, description}`.
- No field other than the ones listed for the verdict.

## `findings.json`

A JSON array of records sorted by fingerprint. Fields by verdict (✓ required, ○ optional, ✗ forbidden):

| Field | `confirmed` | `needs_validation` | `rejected` |
|---|---|---|---|
| `verdict`, `fingerprint`, `title`, `description`, `trace`, `evidence` | ✓ | ✓ | ✓ |
| `root_cause` (string), `intended_behavior` (string) | ✓ | ✗ | ✗ |
| `claimed_root_cause` (string) | ✗ | ✓ | ✓ |
| `conditions`: array of `{kind, description}` | ✓ | ✗ | ✗ |
| `execution`: `{attacker_perspective, payloads[], instructions[], observed_result}`, all non-empty | ✓ | ✗ | ✗ |
| `remediation`: `{strategy, code_changes?: [{file, description}], regression_test?}` | ✓ | ✗ | ✗ |
| `severity`: `{likelihood: {score, reason}, impact: {score, reason}, overall_severity}` | ✓ | ✗ | ✗ |
| `confidence`: `{score, reason}`, score `low`, `medium` or `high` | ✓ | ✗ | ✗ |
| `blockers`: non-empty array of non-empty strings | ✗ | ✓ | ✗ |
| `validation_plan`: `{local?, deployment?}`, at least one non-empty | ✗ | ✓ | ✗ |
| `reason` (string) | ✗ | ✗ | ✓ |
| `cwe` (`CWE-<n>`), `asvs` (`L1`, `L2`, `L3`) | ○ | ○ | ✗ |

Severity: `likelihood.score` and `impact.score` are `low`, `medium`, or `high`. `overall_severity` is
`informational`, `low`, `medium`, `high`, or `critical`, and cannot exceed the impact: impact `low` allows at most
`low`, `medium` at most `medium`, `high` any value. `execution` describes only the bounded local check already
performed, in the target's own interface (a request, a CLI call, a library call, a fixture, a rendered policy).

Example of a `confirmed` record:

```json
{
  "verdict": "confirmed",
  "fingerprint": "api/users:update:missing-owner-check",
  "title": "Any user can change another user's email",
  "description": "PATCH /users/:id updates the record named in the path without checking that it belongs to the caller.",
  "root_cause": "updateUser authorizes on authentication only; it never compares params.id with the session's user id.",
  "intended_behavior": "A user may update only their own record unless they hold the admin role.",
  "trace": [
    {"kind": "entrypoint", "file": "src/routes/users.ts", "line": 41, "scope": "router.patch('/users/:id')", "description": "Path id taken from the request."},
    {"kind": "sink", "file": "src/services/users.ts", "line": 88, "scope": "updateUser", "description": "db.users.update(id, body) with no owner check."}
  ],
  "evidence": [{"file": "src/services/users.ts", "line": 85, "description": "Only requireAuth() runs before the update."}],
  "conditions": [{"kind": "authentication", "description": "Attacker holds any valid account."}],
  "execution": {
    "attacker_perspective": "Signed in as dummy user A.",
    "payloads": ["PATCH /users/2 {\"email\": \"a@test\"} with user A's session"],
    "instructions": ["Run the existing users.e2e fixture server on loopback with the two dummy users.", "Send the request as user A."],
    "observed_result": "HTTP 200; dummy user B's email is now a@test."
  },
  "remediation": {"strategy": "Compare params.id with session.userId (or require admin) in updateUser before the write.",
                  "regression_test": "users.e2e: user A updating user B returns 403 and leaves B unchanged."},
  "severity": {"likelihood": {"score": "high", "reason": "Any account; one request."},
               "impact": {"score": "high", "reason": "Account takeover through email change and password reset."},
               "overall_severity": "high"},
  "confidence": {"score": "high", "reason": "Reproduced locally with the repository's fixture."},
  "cwe": "CWE-639"
}
```

## `coverage-ledger.json`

A JSON array of units sorted by `coverage_id`.

| Field | Content |
|---|---|
| `coverage_id` | derived from `canonical_refs`, see below |
| `canonical_refs` | `{surface, boundary, subsystem, attack_class, lifecycle?}`: stable source-derived references, such as `src/router.ts#POST /users/:id`, `src/authz.ts#requireOwner`, `packages/api`, `attack-classes.md#Access control` |
| `surface`, `boundary`, `subsystem`, `attack_class`, `lifecycle?` | human labels |
| `starting_paths` | repository-relative paths |
| `attack_class_block` | `attack-classes.md#<class>` or null |
| `selected_blocks` | domain blocks given to the hunter, `domains/<file>.md#<section>` |
| `excluded_blocks` | `[{block, reason}]` |
| `prior_status` | `new`, `none`, or a `prior_*` value from `audit-workflow.md` |
| `wave` | integer ≥ 1 |
| `status`, `agent_id`, `reviewed_paths`, `local_checks`, `result_fingerprints`, `unresolved` | see the state table |
| `attempts` | archived earlier attempts: each has `wave` (strictly increasing, below the unit's), `status` (`blocked`, `covered`, or `candidate`), its own evidence, and `reassignment_reason` |

**`coverage_id`:** each canonical reference must be Unicode NFC with visible content and no control or surrounding
whitespace. Percent-encode its UTF-8 bytes, leaving only `A-Z a-z 0-9 - . _ ~` and writing every other byte as
uppercase `%HH`. Join surface, boundary, subsystem, and attack class with `::`, and append `::` and the lifecycle when
present. Two units with the same id, or one semantic tuple under two ids, are an error.

**State table:**

| `status` | `agent_id` | `reviewed_paths`, `local_checks` | `result_fingerprints` | `unresolved` |
|---|---|---|---|---|
| `planned` | null | empty | empty | empty |
| `not_applicable`, `out_of_scope`, `deferred` | null | empty | empty | non-empty reason |
| `in_progress` | owner | empty | empty | empty |
| `blocked` | owner | both non-empty | empty | non-empty |
| `covered` | owner | both non-empty | empty | empty |
| `candidate` | owner | both non-empty | non-empty | any |

Each `local_checks` entry is `{agent_id, reviewed_paths, invariant, method, result, artifact}`: `agent_id` matches
`^[a-z0-9][a-z0-9_-]{0,63}$`; `method` is `source` with `artifact: null`, or `local` with an artifact under
`agents/<agent_id>/artifacts/`. The unit's `reviewed_paths` is exactly the union of its checks' paths.

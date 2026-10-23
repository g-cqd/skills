# Audit workflow

Audit mode of `secure-coding` (§1). Use it only when the user asks to audit or pen-test a codebase, asks for a full,
comprehensive, or end-to-end security review, or asks for report files. The finding gate (§3), the verdicts, the
safe-execution rules (§5), and the severity anchors (§6) of `SKILL.md` apply unchanged; this file adds coverage,
independence, and structured output.

Roles below. In this harness the **parent** is the main agent or `orchestrator`; **recon agents** are `scout` or
`researcher`; **hunters** are `security-auditor`; **verifiers** are `verifier` (or a fresh `security-auditor` that did
not hunt the candidate). On a harness without subagents, one agent plays each role in turn, but a record it found
itself is never its own verification: say so in the report and mark the run partial.

## Contents

- Setup: output directory, write isolation, run metadata
- Profiles, scope, budget, prior runs
- Phase 1: reconnaissance and the coverage ledger
- Phase 2: hunting waves and coverage critics
- Phase 3: candidate validation
- Phase 4: `findings.json`
- Phase 5: independent record verification
- Phase 6: reports
- Anti-patterns

## Setup

Resolve before reconnaissance:

- **Target:** the absolute repository root. **Source ref:** the commit, and whether the worktree is dirty.
- **Output directory:** a new directory outside the target, default `~/security-audits/<repo>/run-<N>` with the next
  unused N. Use a directory inside the target only when the user chooses it and version control ignores it.
- **Write isolation:** the parent is the only writer of `run-metadata.json`, `architecture.md`,
  `coverage-ledger.json`, `findings.json`, `REPORT.md`, `FINDINGS-DETAIL.md`, and `NEEDS-VALIDATION.md`. Each hunter
  and verifier gets `<output>/agents/<agent-id>/scratch/` and writes only there; agent ids match
  `^[a-z0-9][a-z0-9_-]{0,63}$`. Agents never edit the target, a shared file, or another agent's directory, and never
  use `/tmp` or the home directory as a fallback.
- **Keeping evidence:** after a sandboxed check has exited, only the parent copies a file from scratch to
  `<output>/agents/<agent-id>/artifacts/`. Copy only files the agent declared in advance, each a regular file with one
  link and within a stated size limit, opened without following symlinks, re-checked after the copy. Never copy a
  directory, an archive's contents, a symlink, a FIFO, or a device. If a decisive file cannot be copied this way,
  discard it and keep the candidate as `needs_validation` with that reason.
- **`run-metadata.json`:** `run_id`, `repo`, `target`, `source_ref`, `profile`, `scope_paths`, `budget` (or null),
  `execution_policy: "sandboxed-source-and-local-only"`, selected domain files, prior-run paths, and
  `run_status: "in_progress"`.

## Profiles, scope, budget, prior runs

| Profile | Use for | Breadth |
|---|---|---|
| `quick` | small targets, re-runs, a first look | units are surface × boundary × attack class, with one subsystem id `profile/quick/all-in-scope-subsystems`; one hunter wave, one critic pass; one verifier does Phase 3 and Phase 5 per candidate |
| `standard` (default) | most audits | the workflow as written |
| `deep` | high-stakes or large targets | units per subsystem and lifecycle mode; critic waves until a clean pass; Phase 3 and Phase 5 always separate agents; same-source prior coverage gets a second independent pass |

A **scoped run** covers named paths, one subsystem, one domain, or a diff between two refs. Seed units only inside
the scope and record what is outside as `out_of_scope`. A `quick` or scoped run calls itself partial in the report.
Profiles change breadth, never the evidence bar.

**Budget.** When the user sets one, record it as a maximum number of agent invocations. One ledger unit is about one
hunter; one candidate is one or two verifiers. Before launching anything, reserve the four reconnaissance agents, the
critics (one for `quick`; one post-wave and one final for `standard` and `deep`), and the verifiers (about 30 percent
of what remains). Hunters get only what is left, in priority order; a unit the budget cannot reach is `deferred` with
reason `budget_cannot_reserve_critics_and_validation`. If the budget cannot pay for reconnaissance plus the reserves,
launch nothing and ask for a larger budget, a narrower scope, or a smaller profile. If candidates outnumber the
validation reserve, stop hunting, validate in fingerprint order, set `run_status: "incomplete"` with
`incomplete_reason: "validation_budget_exhausted"`, and keep unvalidated candidates out of `findings.json`. Never
exceed a user's budget silently.

**Prior runs.** Read every earlier `coverage-ledger.json` and `findings.json` for the repository first:

1. Compare the relevant current source with each prior record; a prior source ref alone does not prove a path
   unchanged.
2. A prior `confirmed` record whose source and conditions are unchanged is carried into the current candidates with
   the same fingerprint, linked to a `planned` unit (`prior_confirmed_same_source`), excluded from hunting, and
   verified again in Phase 3.
3. Changed source behind a prior `confirmed` record makes a revalidation unit (`prior_confirmed_changed_source`); the
   root cause is not excluded from hunting.
4. Prior `needs_validation`, `deferred`, `blocked`, and `out_of_scope` units are current work, never suppression keys.
5. A prior `rejected` record suppresses only that exact unchanged claim, not its unit.

Without a prior ledger, say so in the coverage statement. No run exhausts a target.

## Phase 1: reconnaissance and the coverage ledger

Launch four read-only recon agents in parallel. They return facts with `file:line` references and write nothing.

| Agent | Returns |
|---|---|
| 1a Product and stack | product type, users and operators, trust-sensitive actions; languages, frameworks, build system, runtimes, visible deployment models; entry points and subsystem boundaries; offline build and test commands with their write locations (not run); a comparable product or protocol if the source shows one; missing toolchains |
| 1b Principals and controls | each lower-trust principal and its designed actions; authentication at each entry; per-resource authorization and tenant scope; process, browser, CI, plugin, model and tool, device, and IPC authority; privilege changes, revocation, recovery, fallback; which controls are source-visible and which depend on deployment |
| 1c Entry surfaces and sinks | every place lower-trust input enters (HTTP, RPC, messages, files, archives, CLI, environment, configuration, plugins, CI, cloud events, model context and tool arguments, deep links, webviews, local IPC), the transformations and stored copies after it, the security-relevant sinks, the limits, and the parallel paths to the same effect |
| 1d Local execution | offline tests and fixtures that can check a boundary with dummy data; processes that can run on an isolated loopback; commands that fetch, publish, or touch shared state (forbidden in this run); deployed controls the source cannot show; whether this machine can enforce every sandbox control of §5 and the evidence-copy rules above |

Add a focused recon agent for a deployment mode or subsystem these four do not map, within the budget. If the budget
blocks it, seed that area as a `deferred` unit and report the gap.

The parent writes **`architecture.md`**, about 1,000 words at most: product, principals, normal authority, protected
resources; the comparable baseline if any (to calibrate, never to dismiss a demonstrated finding); stack and
deployment paths; entry surfaces and the important source-to-sink paths; trust boundaries with the strongest visible
control on each; starting paths; prior-run consequences; and the selected domain files with the boundary that requires
each.

The parent writes **`coverage-ledger.json`**: one unit per material combination of entry surface, trust boundary,
subsystem, and attack class (plus lifecycle mode in `deep`). The unit's fields, its id derivation, and the state table
are in `findings-format.md`. Each unit carries the exact attack-class and domain blocks its hunter will receive, and
every considered but excluded block with the source fact that excludes it. Run
`python3 scripts/validate_audit.py ledger <output>/coverage-ledger.json` after seeding and after every update; an
invalid ledger drives no assignment. The ledger is the coverage claim: an architecture summary, an agent count, or
"auth reviewed" is not coverage.

## Phase 2: hunting waves and coverage critics

Assign `planned` units to hunters, at most a few closely related units in one subsystem per hunter. Rank when the
budget or profile caps hunters: unauthenticated or lowest-trust surfaces first; then boundaries protecting the most
valuable resources (credentials, cross-tenant data, code execution, release authority); then prior gaps, revalidation
targets, and changed source; ties by `coverage_id`. Before launch, set the units `in_progress` with the hunter's id.

**Hunter prompt**, in this order:

1. Role: find source-grounded security invariant failures in the assigned units and return exactly one JSON object in
   the result format below.
2. `architecture.md`, verbatim.
3. The assigned coverage ids with their subsystem, boundary, starting paths, and selected blocks.
4. The selected blocks copied verbatim: the attack-class block from `attack-classes.md`, and from each selected domain
   file its discipline, the chosen classes, its moves, and its validation rules. Names alone are not enough.
5. The excluded blocks with reasons.
6. `SKILL.md` §3 (the gate and verdicts), §4.1–4.2 (the method), and §5 (safe execution), verbatim.
7. Carried prior confirmed records to exclude (fingerprint, title, root cause only) and the ids other hunters own.
8. The scratch path, the agent id, the files it may declare for evidence with their size limits, and the result
   format.

A hunter that meets a different boundary outside its units returns it under `uncovered`; the parent makes a unit for
it in the next wave.

**Hunter result**, one JSON object and no prose:

```json
{
  "units": [
    {"coverage_id": "...", "disposition": "covered|candidate|blocked",
     "reviewed_paths": ["repo/relative/path"],
     "checks": [{"agent_id": "...", "reviewed_paths": ["..."], "invariant": "...", "method": "source|local",
                 "result": "...", "artifact": null}],
     "candidate_fingerprints": [], "unresolved": []}
  ],
  "candidates": [],
  "hardening": ["..."],
  "uncovered": [{"surface": "...", "boundary": "...", "subsystem": "...", "attack_class": "...",
                 "starting_paths": ["..."], "reason": "..."}]
}
```

Each candidate has the fields of its `confirmed` or `needs_validation` record (`findings-format.md`) with
`proposed_verdict` in place of `verdict`. Every assigned id appears once in `units`. A `covered` unit has paths and
checks, no candidate, nothing unresolved. A `candidate` unit links fingerprints. A `blocked` unit has paths, checks,
and the unresolved fact. A `source` check has `artifact: null`; a `local` check names one file the parent copied into
`agents/<check agent_id>/artifacts/`.

The parent maps each unit result to its ledger unit, copies the evidence, keeps the `hardening` notes for the report,
and re-runs the ledger validator. A malformed or unsupported result leaves the unit `planned` for reassignment.
Candidates are merged by fingerprint, then by root cause.

**Coverage critic.** After each wave, one fresh read-only agent receives `architecture.md`, the whole ledger, the
candidate fingerprints, and the prior-run gaps, and returns only:

```json
{"missing_units": [{"surface": "...", "boundary": "...", "subsystem": "...", "attack_class": "...",
                    "starting_paths": ["..."], "selected_blocks": ["..."], "excluded_blocks": [],
                    "reason": "source-backed gap"}],
 "reassign_ids": ["..."], "resolved_prior_leads": ["fingerprint"], "stop": false}
```

It looks for unmapped entry points, unchecked parallel paths, missing lifecycle modes, selected domain classes with no
unit, unjustified exclusions, units closed without paths or checks, and prior gaps no unit addresses. It proposes
coverage, not findings. The parent accepts in-scope units, derives their ids, and for each legitimate reassignment
appends the unit's live result to `attempts` with the critic's reason before a fresh hunter takes it. In `standard`
and `deep`, coverage is complete only when a post-wave critic and then a separate final critic both return no accepted
work. A `quick` run records the critic's units as `deferred` with reason `quick_profile_final_critic` and stops. An
early stop marks untouched units `deferred` and says so in the report.

## Phase 3: candidate validation

Every unique candidate goes to a fresh verifier that did not hunt it. The verifier gets the candidate, its unit's
checks and evidence, the architecture facts it needs, the relevant domain validation rules, `SKILL.md` §3 and §5, the
record formats, and prior records with the same fingerprint, never another verifier's conclusion. Its instructions:

1. You did not write this candidate; try to refute it.
2. Check every trace and evidence location; confirm the first step is a real lower-trust entry and the last is the
   claimed sink.
3. Reconstruct the strongest visible validation, identity, authorization, normalization, lifecycle, framework, and
   containment controls on the path.
4. For a proposed `confirmed`, reproduce the minimum result yourself when the sandbox allows; check the input shape,
   the conditions, and the affected dummy principal. Do not infer a stronger result.
5. Check that likelihood, impact, confidence, and the fix match only what the evidence shows.
6. For a proposed `needs_validation`, decide whether the blocker is really outside source and local observation; if
   source refutes the trace, reject it.
7. Keep the fingerprint unless the root cause is genuinely different.
8. Return `{"decision": "confirmed|needs_validation|rejected", "record": {...}}` and nothing else.

A verifier may promote `needs_validation` to `confirmed` only after establishing the complete path and the observed
result itself. Discard a malformed result and re-run with another fresh verifier when the budget allows; otherwise the
candidate stays an unvalidated ledger candidate and the run is incomplete.

## Phase 4: `findings.json`

The parent writes every validated record, sorted by fingerprint, in the format of `findings-format.md`, then runs:

```sh
python3 scripts/validate_audit.py findings <output>/findings.json
python3 scripts/validate_audit.py ledger <output>/coverage-ledger.json
```

Fix every error before going on. A passing validator proves the format and the ledger's consistency, not the truth of
a record.

## Phase 5: independent record verification

One fresh read-only verifier per final `confirmed` and `needs_validation` record (merged into Phase 3 for `quick`).
For `confirmed` it checks every path and line, the real entry interface and input, each condition and visible
preventing layer, the affected principal, likelihood against impact, and that the fix enforces the invariant rather
than moving the trust. For `needs_validation` it checks that the trace supports only the claimed root cause, that each
blocker is decisive and not answerable locally, that a boundary and a concrete possible result are named, and that the
validation plan is exact and never sends traffic to a deployment. It returns `{"decision": "verified", "fingerprint":
"..."}` or `{"decision": "replace", "reason": "...", "record": {...}}`.

A replacement that strengthens a verdict or changes the root cause, the trace, the input, the observed result, the
impact, or the severity goes to yet another fresh verifier before it is applied. Wording and line corrections apply
directly. After each applied replacement, re-run both validators. Set `run_status: "complete"` only when every ledger
candidate has an independent final decision.

## Phase 6: reports

Written only after Phase 5, from the final records and the ledger; the prose never changes a verdict or a severity.

- **`REPORT.md`:** profile, scope, budget spent against planned, source ref, the sandboxed source-and-local-only
  statement, prior-run use, deferred and out-of-scope coverage, and "partial" when it applies (listing unvalidated
  fingerprints when the run is incomplete); a short posture summary; a confirmed-findings table (severity, title,
  boundary, observed result); each confirmed finding with location, principal, bounded reproduction, conditions,
  result, impact, priority reason, and fix; a separate needs-validation table without severity; hardening notes and
  good patterns seen; the coverage counts by state and the final critic result.
- **`FINDINGS-DETAIL.md`:** for each confirmed medium, high, or critical record, the full trace, the dummy principal
  and resource, the exact bounded reproduction, the observed output and the invariant it proves, the conditions, the
  fix, and the regression test.
- **`NEEDS-VALIDATION.md`:** each lead with its trace, evidence, blocker, boundary, and the local or owner-observed
  check. Never live-test instructions.

A clean run may have no confirmed finding: say so, with the coverage and validation limits.

## Anti-patterns

1. A checklist deviation reported as a vulnerability.
2. Defense-in-depth advice with no reachable boundary violation.
3. Testing a live or shared environment because local evidence was not enough.
4. Guessing proxy, provider, browser, identity, or deployment behavior that the source does not show.
5. Calling an action the principal may already take, or harm to themselves, a boundary violation.
6. Reporting a stronger effect than the one observed.
7. Prose-only hunter results that cannot be merged or verified.
8. Re-reporting a carried prior confirmed record, or showing it to hunters as an example.
9. A severity on a `needs_validation` record.
10. Writing the report before independent verification, or letting the prose and the JSON disagree.

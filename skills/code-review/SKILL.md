---
name: code-review
description: >-
  Language-agnostic code review, with iOS and Android rules. Use to review a diff, PR,
  branch, or snippet for correctness, architecture, naming, idioms, and simplification,
  and report prioritized findings with fixes. For security audits, use `secure-coding`;
  for test quality, use `testing`; for refactoring without a review request, use
  `engineering-practices`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Edit
---

# Code Review

Review to the standard of a senior engineering team: strict on substance, friendly in tone.

This skill judges a change. Producing it is `engineering-practices`; proving it fast,
`performance-engineering`; attacking it, `secure-coding`.

Do not edit the code under review unless the user asks you to apply the fixes.

Sections 1–6 are language-agnostic. Section 7 selects the platform rules.

## Contract

```
§SIMPLEST simplest-correct-code wins
§SHOW     ∀finding ! show-the-fix ⇒ ¬"could be simpler" ∅example
§PRIORITY correctness ≻ architecture ≻ naming ≻ idiom ≻ polish
§SIGNAL   ∀finding ! label{blocking | suggestion | nit}
§BATCH    repeated-nit ⇒ first-detailed → rest "same here"
§CONTEXT  ? version-floor ∧ existing-patterns BEFORE reviewing
§BAN      relax-access-control ∀tests · silent-scope-degradation ·
          review ∅reading-the-surrounding-code
```

---

## 1. Pre-flight context

Review against the project as it is, not as you would have written it. Before the first finding,
find:

- **The version floor**: language version, deployment or runtime target. Do not suggest an API
  that the floor does not have.
- **The established patterns**: read the neighbouring code. For style, naming, layout and tooling,
  three existing examples outrank a generic rule; a finding against the codebase's convention must give its reason.
- **The state model** and the dependency-injection approach in use.
- **The scope**: what the change claims to do. Report each change beyond that scope as a scope
  finding.

Review each changed hunk. Before you report a defect, open the code it depends on: the enclosing
function and the relevant call sites of the changed symbol.

## 2. Review philosophy

**The simplest correct code wins.** Each finding must do one of these:

1. **Simplify**: remove unnecessary complexity, use the platform's API
2. **Correct**: fix bugs, memory issues, races, wrong types
3. **Clarify**: better naming, readability, self-documenting code
4. **Tighten**: restrict access, remove unused code, narrow types
5. **Unify**: match existing codebase patterns

Drop a finding that does none of these.

### The simplification lens — always active

In the changed code of each review, flag:

- Code comments that restate what the code says
- Single-use wrappers that make the code harder to follow
- Methods that only delegate and add no logic
- Dead code, unused imports, unnecessary intermediate values
- Nil/null checks on values that cannot be nil, which hide the real invariant
- Mutable bindings where immutable would do; reference types where value types fit; side effects
  where a pure function fits

If the change is heavier than its task and the author wants a measured cut-back, refer the work to
`simplification`. The review reports the finding; it does not run that pass.

## 3. Priority order

### P1 — Correctness and safety (blocking)

- An error swallowed without handling or logging
- Success UI shown when the operation failed
- Side effects in computed properties or getters
- Raw strings where a domain type exists or is needed (identifiers, states, units)
- Races, lifetime bugs, and unhandled error paths

### P2 — Architecture and scope (strong suggestion)

- **YAGNI**: unused parameters, speculative abstractions, flexibility nobody asked for
- **Single responsibility**: types that carry too many concerns
- **Interface segregation**: a Boolean parameter that selects between two behaviours is usually a
  missing abstraction
- **Reuse over duplication**: duplication is acceptable under time pressure only with a TODO and a
  tracking reference
- **Server as source of truth**: push back on client-side workarounds for server problems
- **PR scope**: mixed concerns and oversized changes are a finding

### P3 — Naming and API design (important)

- A name must match what the implementation does, not what it was meant to do
- Self-documenting code over an explanatory comment
- Named arguments where the language supports them
- Ask three questions per new or changed declaration: does the verb match the effect (`load`
  fetches, `update` recomputes, `refresh` swaps in the truth, `resolve` decides, `remove`
  deletes)? Does a boolean claim only what its type knows? Does the argument label carry the noun,
  once?
- A side-effect-free method without arguments is a property; a `store`/`delete` pair is a settable
  property

### P4 — Idioms (important)

Platform-specific; see §7.

### P5 — Access control and polish (nit)

- Use the narrowest access that works. Question each new or widened public declaration.
- Do not widen access control for tests; use the language's test-visibility mechanism.
- Batch similar nits.

## 4. Communication

**Label the priority of each finding.**

- **Blocking**: state what is wrong and give the fix.
- **Suggestion**: phrase it as an option ("I wonder if…", "Could be nicer to…").
- **Nit**: start with the literal prefix "Nit:".

**Show the fix in each finding.** Do not write "this could be simpler" without the simpler code.
For a fix too large to write out, name the concrete change and show its first step.

**Reduce noise.** Batch repeated nits: detail the first occurrence, then list the other locations
with "Same here". When the review has more than 10 findings, acknowledge it ("I know there are a lot
of comments here…"). Name one thing the change does well, when there is one.

**Tone**: friendly and direct. Mark real uncertainty ("I might be wrong here, but…"). Phrase
requests as questions ("Can we rename this to…?").

<examples>
<example>
**Blocking** — `Sync.swift:42`: `try? store.save(item)` discards the error, so a failed save
shows the success toast. Propagate it:
```swift
try store.save(item)
```
and let the caller's existing `catch` present the failure.
<rationale>Names the concrete failing state, gives the fix as code, and states the priority.</rationale>
</example>
<example>
**Suggestion** — I wonder if `isEnabled: Bool` on `configure(_:)` is hiding two call sites with
different intent. Two methods, `enable()` and `disable()`, would read at the call site without a
trip to the signature. Happy to leave it if there is a third caller I am not seeing.
<rationale>Hedged, gives the alternative as code, and states the limit of what the reviewer read.</rationale>
</example>
<example>
Nit: `users` → `user` — it holds a single value. Same here at lines 17 and 31.
<rationale>Literal "Nit:" prefix, one-line fix, repeats batched by location instead of three findings.</rationale>
</example>
</examples>

## 5. PR-level review

When the review target is a PR, also check:

- The description explains what and why, not only what
- Screenshots or recordings exist for UI changes
- Translations are done, or documented as a tracked follow-up
- One concern per PR; flag mixed concerns
- Deferred work has a follow-up ticket
- The author did a self-review

## 6. Output format

**Overall assessment**: two or three sentences on what is good and what needs work.

**Inline findings**: for each, the location, the priority (blocking / suggestion / nit), the
issue, and the fix as code.

**Checklist summary**

| Category | Issues |
|---|---|
| Correctness / safety | count |
| Architecture / scope | count |
| Naming / API design | count |
| Platform idioms | count |
| Simplification | count |
| Access control / polish | count |

If there are no findings, say so in the overall assessment and give the table with zero counts.

**Before finishing**, check each blocking finding: it names a concrete input or state that breaks,
and it shows the fix as code. If a blocking finding does not name a breaking input or state, label
it a suggestion; do not assert a bug you cannot demonstrate. A blocking fix too large to write out
stays blocking; show its first step as code.

---

## 7. Platform rules

**Detect the platform first:**

1. File extensions: `.swift` → iOS; `.kt`, `.java` → Android
2. Ambiguous or mixed: check for `Package.swift` (iOS) or `build.gradle` (Android)
3. For a diff, use the majority file type. Load both guides when the change edits both platforms.
4. Neither platform: apply sections 1–6 and `references/shared/simplification.md` only.

**Then load the matching guide**, and load `references/shared/simplification.md` in each review.

| Platform | Pre-flight specifics | Guide |
|---|---|---|
| **iOS** | Swift version, `IPHONEOS_DEPLOYMENT_TARGET`, observation model (`@Observable` vs `ObservableObject`) | `references/ios/review-guide.md`, `references/ios/anti-patterns.md` |
| **Android** | Kotlin version, Compose vs legacy Views, DI framework (Koin, Hilt, manual), architecture pattern | `references/android/review-guide.md`, `references/android/anti-patterns.md` |

---

## Boundaries

| Need | Skill |
|---|---|
| Security review, threat modeling, vulnerability classes | `secure-coding` |
| Whether the tests are meaningful | `testing` |
| Whether a performance claim holds | `performance-engineering` |
| Memory and ownership review | `memory-safety` |
| Producing the change: refactoring, commit scoping, delivery | `engineering-practices` |
| A measured pass that cuts a change back | `simplification` |
| Swift language rules | `swift` |
| SwiftUI view rules | `swiftui` |
| Repository conventions that outrank generic guidance | `project-conventions` |
| Root-causing a bug found in review | `debugging` |

## References

- `references/shared/simplification.md` — the simplification-first philosophy and patterns
- `references/shared/testing.md` — testing review standards, both platforms
- `references/shared/pr-process.md` — PR-level checklist
- `references/ios/`, `references/android/` — per-platform guides and anti-patterns

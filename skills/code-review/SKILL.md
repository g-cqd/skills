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

Review calibrated to a senior engineering team: exacting on substance, friendly in tone.

This skill owns **judging a change**. It does not own producing one (`engineering-practices`),
proving it is fast (`performance-engineering`), or attacking it (`secure-coding`).

Sections 1–6 are language-agnostic. Section 7 selects the platform rules.

## Contract

```
§SIMPLEST simplest-correct-code wins
§SHOW     ∀comment ! show-the-fix ⇒ ¬"could be simpler" ∅example
§PRIORITY correctness ≻ architecture ≻ naming ≻ idiom ≻ polish
§SIGNAL   ∀comment ! label{blocking | suggestion | nit}
§BATCH    repeated-nit ⇒ first-detailed → rest "same here"
§CONTEXT  ? version-floor ∧ existing-patterns BEFORE reviewing
§BAN      relax-access-control ∀tests · silent-scope-degradation ·
          review ∅reading-the-surrounding-code
```

---

## 1. Pre-flight context

Review against the project as it is, not as you would have written it. Before the first comment:

- **The version floor** — language version, deployment or runtime target. A "modernization"
  comment that names an unavailable API wastes everyone's time.
- **The established patterns** — skim neighbouring code. Three existing examples outrank any
  generic rule; a comment that fights the codebase's own convention needs to argue for itself.
- **The state model** and DI approach in use.
- **The scope** — what the change claims to do. Everything beyond it is a scope finding.

Never speculate about code you have not opened. Read the surrounding code and the call sites
before asserting a defect — a diff shows what changed, not whether the change is wrong.

## 2. Review philosophy

**The simplest correct code wins.** Every comment must serve one of these:

1. **Simplify** — remove unnecessary complexity, use the platform's API
2. **Correct** — fix bugs, memory issues, races, wrong types
3. **Clarify** — better naming, readability, self-documenting code
4. **Tighten** — restrict access, remove unused code, narrow types
5. **Unify** — match existing codebase patterns

A comment serving none of these is noise. Cut it.

### The simplification lens — always active

Flag on every review:

- Noise comments that restate what the code already says
- Single-use wrappers that obscure rather than clarify
- Delegation-only methods that add no logic
- Dead code, unused imports, unnecessary intermediates
- Over-defensive nil/null checks that hide real invariants
- Mutable bindings where immutable would do; reference types where value types fit; side effects
  where a pure function fits

## 3. Priority order

### P1 — Correctness and safety (blocking)

- Never silently swallow an error
- Never show success UI when the operation failed
- No side effects in computed properties or getters
- Domain types, not raw strings
- Races, lifetime bugs, and unhandled error paths

### P2 — Architecture and scope (strong suggestion)

- **YAGNI** — unused parameters, speculative abstractions, flexibility nobody asked for
- **Single responsibility** — types carrying too many concerns
- **Interface segregation** — a Boolean parameter is usually a missing abstraction
- **Reuse over duplication** — duplication is acceptable under time pressure *with* a TODO and a
  tracking reference, never silently
- **Server as source of truth** — resist client-side workarounds for server problems
- **PR scope** — mixed concerns and oversized changes are a finding in themselves

### P3 — Naming and API design (important)

- Names must match **what the implementation actually does**, not what it was meant to do
- Plurals for collections
- Specificity over brevity
- Self-documenting code over an explanatory comment
- Named arguments where the language supports them
- Three questions per declaration: does the verb match the effect (`load` fetches, `update`
  recomputes, `refresh` swaps in the truth, `resolve` decides, `remove` deletes)? Does a boolean
  claim only what its type knows? Does the argument label carry the noun, once?
- A side-effect-free argument-less method is a property; a `store`/`delete` twin is a settable
  property

### P4 — Idioms (important)

Platform-specific; see §7.

### P5 — Access control and polish (nit)

- Default to the narrowest access. Question every public declaration.
- **Never relax access control just for tests** — use the language's test-visibility mechanism.
- Batch similar nits.

## 4. Communication

**Signal priority explicitly.**

- **Blocking** — state directly what is wrong, and provide the fix.
- **Suggestion** — "I wonder if…", "Could be nicer to…"
- **Nit** — prefix literally with "Nit:" so it reads as low priority.

**Always show the fix.** Never write "this could be simpler" without showing what simpler looks
like. A review comment that creates work to understand it has negative value.

**Reduce noise.** Batch repeated nits — first occurrence detailed, the rest listed by location
with "Same here". Acknowledge heavy feedback ("I know there are a lot of comments here…").
Call out what was done well; a review with only negatives is not calibrated.

**Tone** — friendly, direct, constructive. Hedge genuine open questions ("I might be wrong here,
but…"). Phrase requests as questions ("Can we rename this to…?"). Be transparent about
uncertainty rather than asserting through it.

<examples>
<example>
**Blocking** — `Sync.swift:42`: `try? store.save(item)` discards the error, so a failed save
shows the success toast. Propagate it:
```swift
try store.save(item)
```
and let the caller's existing `catch` present the failure.
<rationale>Names the concrete failing state, gives the fix as code, and the priority is unmistakable.</rationale>
</example>
<example>
**Suggestion** — I wonder if `isEnabled: Bool` on `configure(_:)` is hiding two call sites with
different intent. Two methods, `enable()` and `disable()`, would read at the call site without a
trip to the signature. Happy to leave it if there is a third caller I am not seeing.
<rationale>Hedged, offers the alternative concretely, and admits the limit of what the reviewer read.</rationale>
</example>
<example>
Nit: `users` → `user` — it holds a single value. Same here at lines 17 and 31.
<rationale>Literal "Nit:" prefix, one-line fix, repeats batched by location instead of three comments.</rationale>
</example>
</examples>

## 5. PR-level review

Beyond the diff:

- The description explains **what and why**, not just what
- Screenshots or recordings for UI changes
- Translations handled, or documented as a tracked follow-up
- One concern per PR — flag mixed concerns
- Deferred work has a follow-up ticket, never a silent degradation
- The self-review was actually done

## 6. Output format

**Overall assessment** — two or three sentences: what is good, what needs work.

**Inline comments** — for each: location, priority (blocking / suggestion / nit), the issue, and
the fix as code.

**Checklist summary**

| Category | Issues |
|---|---|
| Correctness / safety | count |
| Architecture / scope | count |
| Naming / API design | count |
| Platform idioms | count |
| Simplification | count |
| Access control / polish | count |

**Before finishing**, check every blocking finding: it names a concrete input or state that
breaks, and it shows the fix as code. A finding that has neither is a suggestion — down-rank it
rather than asserting a bug you cannot demonstrate.

---

## 7. Platform rules

**Detect first:**

1. File extensions — `.swift` → iOS; `.kt`, `.java` → Android
2. Ambiguous or mixed → check for `Package.swift` (iOS) or `build.gradle` (Android)
3. Reviewing a diff → go by the majority file type; load **both** guides for a genuinely
   cross-platform change

**Then load the matching guide**, plus `references/shared/simplification.md` every time.

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
| Swift language rules | `swift` |
| SwiftUI view rules | `swiftui` |
| Repository conventions that outrank generic guidance | `project-conventions` |
| Root-causing a bug found in review | `debugging` |

## References

- `references/shared/simplification.md` — the simplification-first philosophy and patterns
- `references/shared/testing.md` — testing review standards, both platforms
- `references/shared/pr-process.md` — PR-level checklist
- `references/ios/`, `references/android/` — per-platform guides and anti-patterns

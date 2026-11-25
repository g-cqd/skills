---
name: software-engineering
description: >-
  End-to-end software engineering standard from problem framing through design,
  implementation, testing, debugging, code review, simplification, performance, memory
  safety, security hardening, CI/CD, and release delivery, with Swift and Apple platform
  guidance. Use when rephrasing requirements, planning work, designing APIs or UIs,
  coding, reviewing diffs, removing overengineering, testing, fuzzing, debugging,
  profiling latency/memory/energy, hardening apps/agents/CI, or shipping releases. Not for
  authoring agent skills, which is `skill-creator`.
---

# Software Engineering (A to Z)

Standalone, team- and language-agnostic engineering doctrine for high-assurance software. Built on the latest editions of authoritative security, supply-chain, safety, and systems-performance baselines (NIST SSDF & SP 800-53, NSA CNSA / Memory-Safety guidance, ANSSI RGS, NCSC/MI5 endpoint guidance, CISA Secure by Design, OWASP Top 10 / ASVS / MASVS / LLM & Agentic AI, SLSA, EU CRA, LMAX Mechanical Sympathy, NASA JPL bounded determinism, and current platform guides).

## Contract

```
§PRIORITY  safety ∧ security ∧ correctness ≻ reliability ∧ recoverability ≻
           observability ∧ maintainability ≻ performance ∧ energy ≻ cost ≻ velocity ≻ elegance
§CONFLICT  1. safety|security|correctness ≻ 2. explicit user instruction ≻
           3. repo convention (3+ examples) ≻ 4. this skill
§CURRENT   always target newest stable language mode · SDK API · compiler check · crypto · standard
           supported by the project floor · verify against live docs/SDKs at implementation time ·
           every threshold here is a floor ¬a ceiling · pin ∧ actively update (¬pin-and-forget)
§FRAME     restate problem · invariants · non-goals · unknowns BEFORE designing or coding
§SIMPLEST  simplest correct design wins · delete ≻ inline ≻ flatten ≻ extract · rule of three
§EVIDENCE  claim ⇒ executable proof (test | measurement | tool output) · ¬guess · ¬unmeasured perf claim
§BOUNDARY  every external input ∷ hostile · canonicalize → validate · allowlist ≻ denylist · fail closed
§ORDER     red test → minimal general green → refactor/simplify → security & perf gate → verify
§BUILD     whole step ⇒ 1 debug build (never edit-build loop) · release ×1 for final numbers · rerun ¬rebuild
§WAIT      long command ⇒ harness background/wait tool · never fixed sleep · never swallow exit code in pipe
§DONE      every requirement met · tests green · diff reviewed & simplified · scratch deleted · limits stated
```

Legend: `§` rule · `!` must · `?` check · `¬` not · `∅` none · `∀` for each · `∈` in · `∷` is · `∧` and · `∨` or · `⇒` then · `≻` outranks · `→` becomes.

---

## 1. Intake, Rephrasing & Problem Framing

Never start coding on an ambiguous or solution-loaded prompt. Rephrase the request first when requirements are complex, multi-file, or underspecified.

1. **Separate the problem from the proposed solution.** Ask what outcome must change and why now; a user's proposed mechanism ("add a flag", "build a cache") may mask a simpler fix.
2. **Detect repository conventions and currency floor first.** Read `AGENTS.md`, `CONTRIBUTING.md`, linter/formatter configs, build manifests, deployment/toolchain floors, and `git log --oneline -20`. Three existing examples outrank generic style rules (never safety, security, or correctness). Never invent ticket IDs, branch formats, or commit prefixes.
3. **Verify current state against live sources.** Check the newest stable APIs, compiler safety modes, dependency releases, and advisories available within the project's supported floor before designing. Never copy deprecated patterns merely because surrounding legacy code uses them.
4. **Write a 5-line problem contract** before non-trivial work:
   - **Goal:** observable behavior or metric change.
   - **Invariants:** what must remain true (compatibility, security boundaries, data integrity, deployment floor).
   - **Non-goals:** what is explicitly out of scope so scope does not creep.
   - **Assumptions & unknowns:** state routine assumptions plainly; ask the user only when competing readings change files, contracts, or destructive/outward actions.
5. **Challenge the request when warranted.** Name contradictions, outdated assumptions, hidden blast radius, overengineering, or violated constraints before writing code.

---

## 2. Planning, Decomposition & Scheduling

Match ceremony to task size. Skip formal plans for trivial single-file edits; use structured plans for multi-module or high-risk work.

| Task shape | Artifact | Rule |
|---|---|---|
| Single focused change | 3–5 bullet step list | Implement directly; verify end to end |
| Multi-file feature / bug | Atomic vertical-slice task list | Riskiest uncertainty first; each slice delivers testable behavior |
| Multi-week / cross-repo initiative | Staged roadmap with exit gates | Every stage has executable verification criteria and named risks |
| Contested architecture choice | Short ADR (context, decision, alternatives, consequences) | Record durable decisions only; never keep diary logs in repo docs |

- **Vertical slices, not horizontal layers.** Never schedule "all models, then all views, then all tests." Each task produces one independently verifiable behavior in one focused turn.
- **Split oversized slices with SPIDR** (Spike, Path, Interface, Data, Rules). Keep research spikes separate from implementation tasks.
- **Queue & regression discipline.** Maintain one work queue (FIFO within priority tier):
  - Correctness, safety, security, or data regressions **block landing** and are repaired first.
  - Pure performance regressions land only if queued immediately with location and measured baseline.
- **Parallelism & worktrees.** Size parallel builders to `cores ÷ build-cores`. Use long-lived area worktrees (never per-task throwaways; zero worktrees for read-only work). Rebase on main and run the full suite once before hand-back so the receiver never rebuilds.

See [references/planning-and-design.md](references/planning-and-design.md) when designing complex roadmaps, ADRs, system/UI architectures, or public APIs.

---

## 3. Technical & Interface Design

- **Make illegal states unrepresentable.** Model state machines with sum types / enums carrying their valid payload; eliminate boolean pairs and nullable fields that must stay in sync.
- **One source of truth.** Compute derived state; never store duplicate fields that can drift.
- **Cohesion, boundaries, and seams.** Keep core logic pure and free of UI/OS frameworks so it runs identically in unit tests, CLI tools, and cross-platform builds. Inject external effects (clock, RNG, filesystem, network, process spawner) at the module boundary via narrow protocols or closures.
- **Design for failure.** State invariants, error taxonomy, cancellation semantics, idempotency, and transactional rollback (no partial writes on failure; write temp file `O_EXCL | O_NOFOLLOW`, `fsync`, atomic rename).
- **UI & interaction design.** Keep Views thin and pure (zero business logic, I/O, or sorting in render paths). Use design tokens, semantic controls (native buttons, keyboard navigation, VoiceOver/accessibility labels, Dynamic Type, contrast, reduced motion), and explicit empty/loading/error/offline states. Every destructive action requires confirmation or undo; every long operation shows determinate or clear indeterminate progress and supports cancellation.
- **Dependency & toolchain currency.** Adding a dependency is an architectural decision: prefer stdlib and OS frameworks, audit maintenance/license/transitives/privacy, pin by exact version or commit SHA, commit the lockfile, and wrap third-party types behind an internal boundary. Pinning is for reproducibility, never stagnation: keep toolchains, SDKs, dependencies, and CI actions continuously updated to their latest vetted releases in small, reviewed upgrades.

---

## 4. Simplification, Rationalization & Anti-Overengineering

**The simplest correct code wins.** Run a simplification pass on every plan (before coding) and every diff (before delivery).

**Cut order:** `delete ≻ inline ≻ flatten ≻ extract` (extract only when the name adds meaning and lowers caller cognitive load).

| Smell | Action |
|---|---|
| Speculative protocol, option, flag, or wrapper with 1 caller/conformer | Inline or delete; abstract on the third real use (Rule of Three) |
| Pass-through layer making no decision | Collapse it |
| Nesting ≥ 3 levels or deep `else` chains | Flatten with `guard` / early returns |
| Dead code, unused imports, stale feature flags, redundant comments | Delete (run dead-code & clone analyzers when present) |
| Defensive check for an invariant already proved by types | Remove inside trusted core; **keep at trust boundaries** |
| Complex clever O(n) vs clear O(n log n) at realistic n | Ship the clear version unless profiling proves the difference matters |

**Rationalization check — stop whenever you catch yourself thinking:**
- *"We might need this abstraction later"* → YAGNI; delete it.
- *"It's internal, nobody malicious can reach it"* → SSRF and lateral movement reach internal surfaces; validate at the boundary.
- *"It's faster / cleaner without a test or measurement"* → Unverified code is unfinished; measure or test it.
- *"A quick null-check / catch-all silences the crash"* → That hides the root cause; find the upstream bug.
- *"I'll fix this unrelated file while I'm here"* → Scope creep breaks review and `git bisect`; report as a follow-up.

---

## 5. Testing, Verification & Debugging

**Testing contract:**
1. **Red → Green → Refactor.** Write a failing test first, confirm it fails for the right reason, write the minimum *general* code to pass (never special-case test inputs), then simplify.
2. **One behavior, one reason to fail.** Assert observable contracts, never private implementation details. Use parameterized tests for input tables; use property-based tests for invariants (keep shrunk counterexamples as regression tests); use contract tests across module/service boundaries.
3. **Deterministic by construction.** Zero `sleep`, `Task.yield`, wall-clock assertions, or unseeded RNGs in tests. Inject controllable clocks, seeded PRNGs, and event-driven waiters (`confirmation`, async signals).
4. **Hostile & edge-case battery.** Always test empty/boundary inputs, malformed/oversized/hostile bytes, cancellation mid-flight, resource exhaustion, partial-failure rollback, and concurrency races.
5. **Mutation & fuzzing.** Treat surviving mutants on critical/security code as missing assertions. Keep fuzz targets + checked-in corpora for every untrusted parser; run mutation testing in PR/background loops, not inner edit loops.
6. **Legacy code.** Pin current behavior with characterization tests, introduce the smallest seam (sprout, wrap, extract interface), then change behavior.

**Debugging contract (root cause before fix):**
1. Reproduce deterministically (for flakes, measure `k/N` runs; check shared state, clock, async races, order dependence, hidden randomness).
2. Read the **first** error and verify every assumption with live evidence.
3. Form one falsifiable hypothesis ("X causes Y because Z") and change one variable per run to halve the search space (`git bisect`, input halving).
4. **3-failure escalation gate:** after 3 failed fixes, stop, list *proven* vs *assumed* facts, and re-derive or escalate rather than guessing a 4th fix.
5. Lock every bug fix with a regression test that fails without the fix and passes with it.

See [references/testing-and-debugging.md](references/testing-and-debugging.md) for Swift Testing patterns, fuzzing/sanitizer matrices, mutation testing, and flaky-test playbooks.

---

## 6. Code Review & Delivery Discipline

**Review priority:** `correctness & safety (blocking) ≻ architecture & scope ≻ naming & API design ≻ idiom ≻ polish`.

- Read surrounding call sites and the repo's version floor before commenting.
- Every finding states: **severity (`blocking` / `suggestion` / `nit`), file:line, cause, and concrete fix** (never vague "could be cleaner"). Batch repeated nits.
- Never relax access control (`internal` → `public`) solely for tests, never mix refactor commits with behavior commits, and keep PRs reviewable in ~15 minutes.
- **Pre-completion gate (required before claiming done):**
  1. Re-read the original request and verify every item.
  2. Build once per complete step (debug during work; release once for final numbers); run the full test suite and linters/analyzers on all touched packages.
  3. Exercise the change as a user would (or state explicitly what could not be run).
  4. Audit your own diff for leftovers, dead code, secrets, and simplification opportunities; delete all scratch files.
  5. Report what was verified, what was not verified, and any residual risks or pre-existing follow-ups.

---

## 7. High Performance, Memory Efficiency & Energy

**Never optimize without a before/after measurement from the same release build, inputs, and harness.**

**Attack order:** `do not do the work ≻ do less work (algorithm/batching) ≻ do it elsewhere/later (async/background) ≻ parallelize (check Amdahl ceiling) ≻ micro-optimize (layout/SIMD)`.

Run audits across **four rounds** so CPU speedups never regress RAM or battery:
1. **Latency & algorithms:** define `n`, prove worst-case bounds (zero O(n²) re-parsing, zero backtracking regex, zero main-thread SQLite/disk/shader compilation), measure `p50`/`p95`/`p99` (check for coordinated omission), precompile shaders (`.metallib`) and share GPU devices/pipelines/atlases.
2. **Memory & UMA footprint:** measure `phys_footprint` / Max RSS at idle, peak, and post-drain; bound every cache/history/scrollback/index table; respond to OS memory-pressure notifications; eliminate accidental CoW copies, retained ASTs, and full-res offscreen snapshots; verify zero retain cycles and zero file-descriptor leaks (`leaks`, static ARC/resource analyzers).
3. **Energy & wakeups:** target **0 idle wakeups/s** and 0 idle CPU%; eliminate sub-10 ms spin-poll loops (use event-driven notifications/`kqueue`); pause animations, display links, and snapshots when occluded or unfocused; assign background work to `.utility`/`.background` QoS (E-cores); adapt frame rate and effects to Low Power Mode and thermal state.
4. **Isolated dynamic verification:** benchmark in release mode (`--scratch-path .build-release`), interleave A/B inside one binary where possible, report median + spread + hardware + load, and tag any unmeasured claim as `[unmeasured hypothesis]`.

See [references/performance-memory-energy.md](references/performance-memory-energy.md) for cache-line rules (128 B Apple Silicon), SIMD/SWAR patterns, Metal/TBDR, and benchmark protocols.

---

## 8. Memory Safety, Security, Hardening & Isolation

**Security invariants:**
- **OS boundaries over text classifiers.** Sandboxes (Seatbelt, Landlock, seccomp, App Sandbox, hypervisors) and entitlements enforce isolation; regexes, prompt guardrails, and command allowlists are defense-in-depth conveniences only. Never keep grants active when sandboxing is disabled.
- **Process privilege separation.** Never parse complex untrusted formats (images, PDF, video, archives, browser extensions, terminal graphics, untrusted XML/HTML) inside a process that holds credentials, signing keys, or unlocked vaults. Isolate decoders in zero-network, zero-keychain sandboxed helpers or XPC services.
- **Bound & canonicalize before parsing.** Check byte limits, pixel dimensions (`width * height <= limit` *before* decode), recursion/nesting depth, and length-field agreement (reject mismatches; never clamp). Resolve symlinks (`realpath` / `O_NOFOLLOW`) before containment checks.
- **Cryptography & secrets.** Use current authoritative AEAD (e.g., AES-256-GCM, ChaCha20-Poly1305) with bound AAD and unique nonces; adopt current standardized hybrid post-quantum key exchange (e.g., ML-KEM / X-Wing) where long-lived confidentiality matters; use memory-hard password KDFs at or above current OWASP/NIST/IETF recommendations (e.g., Argon2id ≥ 64 MiB / 3 passes as a minimum floor, bounded on read; FIPS-approved PBKDF2 only when compliance mandates it); store secrets in hardware-backed Keychain/Secure Enclave with `WhenUnlockedThisDeviceOnly` (never silent downgrade, never plaintext config secrets); zeroize key buffers; zero secrets in logs, errors, temp files, or child env.
- **Network & local IPC.** Default-deny egress; block all special-use private/loopback/link-local/metadata IPv4+IPv6 ranges (including all IPv4-mapped IPv6 spellings) via `inet_pton` and pin resolved IPs against DNS rebinding; bind OAuth loopback listeners strictly to `127.0.0.1`/`::1` with PKCE `S256` and `state`; authenticate IPC peers with OS credentials (`getpeereid`/audit tokens), never self-reported names; check WebView origins from authoritative frame metadata, not page-world strings.
- **Files & subprocesses.** Create sensitive files `O_CREAT | O_EXCL | O_NOFOLLOW` with explicit modes (`0600`/`0700`, never relying on umask); quarantine downloaded files *before* moving to final names; scrub child environments (`DYLD_*`, `GIT_CONFIG_*`, tokens, `BASH_ENV`, `PAGER`); use absolute paths + ownership/permission trust checks; kill full process groups (`-pgid`) on timeout; drain stdout/stderr concurrently to avoid 64 KiB pipe deadlocks.
- **AI & agent hardening.** Treat all model output, retrieved docs, repo configs, skills, and MCP responses as untrusted input; bind project configs/skills to user-approved content digests; filter terminal escape sequences (OSC 52/CSI/DCS) from untrusted text; run autonomous agents only in disposable L2/L3 VMs with host-enforced egress and out-of-band evidence logs.

See [references/security-hardening-and-ci.md](references/security-hardening-and-ci.md) for the full threat-modeling checklist, critical-grade requirement matrix, TUF update rules, CI/CD & supply-chain hardening (`zizmor`, `actionlint`, SLSA, SBOM, runner separation), and agent isolation levels (L0–L3, P1–P2).

---

## 9. CI/CD, Supply Chain & Release Engineering

- **Workflow hygiene (`zizmor` + `actionlint` = 0 errors).** Pin every action to a 40-char commit SHA; declare top-level `permissions: { contents: read }`; set `persist-credentials: false` on read-only checkouts; never expand `${{ inputs.* }}` or untrusted context inside `run:` scripts (pass via `env:` and validate); never use dynamic `${{ secrets[...] }}` or broad `secrets: inherit`.
- **Runner & cache isolation.** Untrusted PR jobs and mutation/fuzzing jobs must never share runners, mutable caches, SwiftPM checkouts, DerivedData, or signing keys with release jobs. Gate signing/publishing behind protected Environments with required reviewers and ephemeral `0600` credentials in `$RUNNER_TEMP`.
- **Signed, attested, verifiable releases.** Build in CI from pinned revisions + committed lockfiles; sign binaries with Developer ID + Hardened Runtime (zero `allow-dyld-environment-variables`, `disable-library-validation`, or `allow-unsigned-executable-memory`) + Apple notarisation; publish SHA-256 checksums, CycloneDX/SPDX SBOM, and SLSA Build Provenance (`actions/attest-build-provenance`); sign update metadata with mandatory verification, expiry timestamps, and anti-rollback version floors; keep root/release keys in hardware or offline with a documented rotation procedure.
- **Static & dynamic CI gates.** Order cheapest first: format/lint/workflow-lint → unit & security tests → ASan/UBSan + TSan → static analyzers (retain-cycle, dead-code, duplication, resource-obligation, CodeQL, secret scan) → smoke/budget tests → release & attest.

---

## 10. Swift & Apple Platforms

Apply these rules whenever the codebase uses Swift or targets Apple platforms. Always target the newest stable Swift language mode, compiler safety checks, and Apple SDK APIs supported by the project's deployment floor.

1. **Check the floor and live docs first.** Read `Package.swift` (`swift-tools-version`, `platforms`), Xcode deployment targets, and the CI toolchain matrix; verify API behavior, deprecations, and availability via local Apple documentation tools or SDK `.swiftinterface`/headers inside Xcode — never from memory or unverified web guesses. Where the floor blocks a newer, safer primitive, use the best supported fallback and note what floor unlocks the upgrade.
2. **Strictest compiler safety supported.** Enable the latest strict concurrency language mode, strict memory safety (`.strictMemorySafety()`), explicit existentials (`ExistentialAny`), strict import visibility (`InternalImportsByDefault`, `MemberImportVisibility`), warnings-as-errors, and any newer compiler safety flags available in the active toolchain. Zero `!`, `try!`, `as!`, IUOs, empty `catch`, `Any`/`[String: Any]` (decode into strict `Codable` at boundaries), or `unowned` captures.
3. **Types & errors.** Prefer `struct`/`enum` over `class` (`final class` default); `some` over `any`; typed throws over untyped `Result`; `guard let` over nested `if let`; `private` first; DocC contract comments (`- Parameter`, `- Returns`, `- Throws`, `- Complexity` when ≠ O(1)).
4. **Concurrency & synchronization.** `@MainActor` for UI state; implicit `Sendable` across boundaries; structured concurrency (`TaskGroup`, `AsyncStream`) over unstructured `Task {}`; **no `DispatchQueue`** except when a framework API requires a queue parameter. Synchronization ladder: `@MainActor` → `Mutex<Value>` / `Atomic<Value>` (weakest correct memory ordering, never `.sequentiallyConsistent` by default) → bare `actor` only across async suspension invariants. Check `Task.checkCancellation()` in long loops.
5. **Zero-copy memory & containers.** Prefer the newest safe borrowed-view and inline-storage primitives supported by the floor (`Span`, `RawSpan`, `MutableSpan`, `OutputSpan`, `InlineArray`, `ContiguousArray` + `reserveCapacity`); wrap any required `unsafe` operation behind a safe API with a documented `SAFETY:` invariant and bounds test.
6. **SwiftUI & Apple runtime.** Adopt the newest declarative state and navigation APIs supported by the floor (e.g., `@Observable` over legacy `ObservableObject`); keep `body` and `init` pure; pass narrow view inputs; avoid initializing a `@State` property both at its declaration and again in `init` (macro-backed `@State` storage makes declaration defaults override `init` assignments). Keep core targets free of AppKit/UIKit/SwiftUI so Linux builds stay clean.
7. **Source shape & tooling discipline.** One primary type per file (`Type+Feature.swift` for extensions), bounded file/type/function length and cyclomatic complexity, Swift Testing (`@Test`, `#expect`, `#require`, `confirmation`) for all non-XCUI tests, and automated formatter, linter, retain-cycle, dead-code, and clone-ratchet gates.

See [references/swift-and-apple.md](references/swift-and-apple.md) for the live floor/fallback ladder, modern Swift concurrency/Span/Metal idioms, macro-backed SwiftUI state rules, and source-structure discipline.

---

## References (Load on Demand)

- [references/planning-and-design.md](references/planning-and-design.md) — Read when framing complex initiatives, writing ADRs/PRs/specs, designing APIs/UIs, or running simplification & code review passes.
- [references/swift-and-apple.md](references/swift-and-apple.md) — Read when writing or reviewing Swift, SwiftUI, Metal, Keychain/CryptoKit, or Apple platform code.
- [references/testing-and-debugging.md](references/testing-and-debugging.md) — Read when designing test strategies, Swift Testing suites, fuzzers, sanitizers, mutation testing, or diagnosing flaky/complex bugs.
- [references/performance-memory-energy.md](references/performance-memory-energy.md) — Read when auditing or optimizing latency, tail distributions, UMA memory footprint, Apple Silicon SIMD/Metal, or battery/wakeups.
- [references/security-hardening-and-ci.md](references/security-hardening-and-ci.md) — Read when threat-modeling, auditing security boundaries, hardening parsers/crypto/agents/sandboxes (L0–L3), or securing CI/CD & release pipelines.

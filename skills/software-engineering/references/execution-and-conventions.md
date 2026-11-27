# Working Conventions & Execution Discipline

Operational rules governing assumptions, scope, code layout, build/test/CI budgets, prose brevity, git hygiene, ecosystem reuse, and machine etiquette. When any other reference conflicts with these rules, this document and `SKILL.md` win.

## Contents

1. Zero Silent Assumptions & Scope Discipline
2. Agent Pacing & Context Hygiene
3. File Size, Layout & Navigability (≤ 300 Lines)
4. Build, Test & CI Budget
5. Comments, Docstrings & Prose Brevity
6. Git History, Branches, PRs & Worktrees
7. Reuse, API Currency, Cross-Repo Truth & UI Craft
8. Machine Etiquette, Compute & Scope Isolation

---

## 1. Zero Silent Assumptions & Scope Discipline

- **Verify ground truth before asking or coding:** check the codebase, sibling repositories (backend, specs/RFCs, other client platforms), issue/wiki trackers, `git log`, and primary vendor documentation (`apple-docs` on Apple platforms) first. Never guess wire formats, permissions, API contracts, or framework behavior.
- **Ask on every remaining ambiguity:** whenever requirements, UX behavior, naming, scope, or trade-offs admit more than one plausible reading that code and docs do not settle, stop and ask the user before implementing.
- **Batch decisions in the structured question tool:** when the harness provides a `question` tool, group open decisions into one call with concrete options and one-line trade-offs rather than scattering free-text questions across turns.
- **Implement strictly what was asked:** must not add unrequested features, CLI flags, UI hints, fallback modes, or speculative abstractions. Keep improvement ideas out of the diff; mention them in one line at hand-off or ask before adding them to the task list.

---

## 2. Agent Pacing & Context Hygiene

- **Execute agreed plans end-to-end:** once the user approves a plan, task list, or phase sequence, work through the items continuously without pausing to ask "should I continue?". Stop only on genuine ambiguity, an external blocker, or completion.
- **Check user notes non-disruptively:** read the harness's user-notes queue between steps and at hand-off so mid-flight steering is absorbed promptly without interrupting flow.
- **Filter noisy tool output before reading:** redirect verbose build/log output to files or filter to actionable diagnostics so raw logs do not flood context and trigger premature compaction.

---

## 3. File Size, Layout & Navigability (≤ 300 Lines)

Large files obscure structure, waste context tokens, and cause agents and humans to miss existing helpers.

| Rule | Standard |
|---|---|
| **File length** | **Must not exceed 300 lines** (code + comments) unless explicitly justified |
| **Top-level types** | **One primary top-level type per file**, named `TypeName.<ext>`; keep only tiny `private` supporting types in the same file |
| **Access control vs. splitting** | **Tight access control wins over file splitting:** must not widen `private` to `internal`, `package`, or `public` solely to move helpers into another file |
| **Splitting cohesive extensions** | When one type has distinct concerns that do not need `private` stored-state access, split into `TypeName+Concern.<ext>` files or extract a narrow-interface helper type |
| **Navigability** | Mirror module/feature boundaries in directory names; maintain a brief module/file map in `AGENTS.md` when layout is non-obvious |

Valid justifications to exceed 300 lines: keeping `private` invariants encapsulated on a type whose stored state cannot be cleanly decomposed, or a single irreducible table/grammar. State the reason when a touched file stays above 300 lines.

---

## 4. Build, Test & CI Budget

Repeated local rebuilds and full-suite runs waste minutes and starve the machine. Let local checks catch fast compilation/logic errors and let CI own exhaustive verification.

| Situation | Required local action | Leave to CI |
|---|---|---|
| **Editing across files** | Batch the whole logical slice before compiling; must not build after every single-file edit | — |
| **Code change not yet built** | Run **one** debug build + formatter/linter to prove compilation and style before pushing | Release builds, cross-platform builds, full matrices |
| **Trivial / nit / doc / comment / rebase tweak** on code that already built | Run formatter/linter only; skip rebuilds (pass `--no-verify` when git hooks trigger full rebuilds) and push | Full build & test verification |
| **Non-trivial logic or bug fix** | Run **only** the narrow filtered unit test(s) covering the touched logic (**hard cap ≤ 30 s** local test run) | Full unit suites, integration/UI suites, static-analysis gates, mutation/fuzz runs |
| **Repository without CI** (or user explicitly asks for full local gate) | Run the touched package's test suite once from the existing build (`--skip-build` where supported) | — |
| **End of an interactive app task** (macOS desktop or iOS simulator app) | Build and install the app **once** at hand-off using the project's signing/install flow so the user can test immediately | Exhaustive UI/matrix regression runs |

### What to test (and what never to write)
- **Focus on behavior, invariants, edge cases, and regressions:** every bug fix requires a focused regression test that fails without the fix.
- **Cut trivial tests:** must not write tests for compiler-synthesized conformances (`Codable`, `Equatable`, `Hashable`), plain getters/setters, constant values, or framework behavior.
- **Zero sleeps or yields in tests:** never use `sleep`, `Task.sleep` on real wall clock, or `Task.yield()` to wait for async work; inject clocks/schedulers and await deterministic signals or framework confirmations, and put explicit time limits on process-spawning tests so hangs fail fast by name.
- **No unrequested benchmark loops:** run benchmarks once when measuring a targeted performance change; never loop multi-minute benchmarks repeatedly during development.

---

## 5. Comments, Docstrings & Prose Brevity

- **Scarcity of inline comments:** code and type/function names must carry the "what". Add an inline comment **only** for non-obvious "why", subtle invariants, concurrency/memory-safety justifications, or measured workarounds — in one direct sentence. Zero narrative commentary and zero decorative section banners in small files.
- **Minimal, consistent docstrings:** write a concise one-line summary plus non-obvious contracts, complexity (when super-linear or surprising), or safety preconditions. Must not add `- Parameter` / `- Returns` / `- Throws` boilerplate that restates the type signature, and must not document one parameter while leaving sibling parameters undocumented unless that parameter carries a unique non-obvious constraint.
- **Domain-honest naming:** choose concrete domain nouns and verbs that match surrounding code; avoid vague meta-words (`Manager`, `Helper`, `owns`/`owned`, redundant module prefixes) and avoid micro-cleverness (such as custom string interning) on cold paths.
- **Lean `README.md`, fanned-out `docs/`:** keep `README.md` to ~1–2 screens (what it is, quick build/install, core usage, links); move deeper architecture, CLI, or protocol details into focused files under `docs/`. Never put roadmaps or working diaries in repository docs.
- **Direct commits, PRs & review replies:** write short, factual commit subjects and bodies without AI-report filler. Follow the repository's PR template and the author's prior PRs: 1–3 concise lines or bullets, preserve unticked template checkboxes, and omit unrequested "follow-up" or "rejected alternatives" sections unless no template exists and external reviewers lack context.

---

## 6. Git History, Branches, PRs & Worktrees

- **Solo / unreviewed repositories:** commit directly to `main` (must not open PRs when working alone). Before pushing, rework unpushed commits so each commit is atomic and later commits do not patch mistakes introduced earlier in the same unpushed series.
- **Team / reviewed repositories:** make small atomic commits; split large features into stacked branches/PRs (~15 minutes to review each). Rewrite unpushed or unreviewed stacks cleanly instead of piling `fixup` commits.
- **Post-review force-push rule:** once human review comments exist on a PR, push incremental review-fix commits so reviewers can inspect the delta — **unless** the user explicitly asks to amend/rebase and force-push.
- **Double-challenge PR reviews and bug reports:** before accepting or pushing back on a review comment or bug claim, verify both the reviewer's claim and your own hypothesis against the code, specs/RFCs, and tests; reply concisely with `file:line` citations.
- **Worktrees only on contention:** work directly in the primary repository checkout by default. Create a `git worktree` **only** when another session or uncommitted WIP actively shares that checkout, and remove temporary worktrees immediately after merge.

---

## 7. Reuse, API Currency, Cross-Repo Truth & UI Craft

- **Newest native APIs + sibling packages first:** query `apple-docs` or vendor docs for modern standard-library and OS APIs within the project's deployment floor before writing custom utilities, and check sibling/family libraries (`aemi*`, `analyzerkit`, shared UI/utility packages) before duplicating primitives.
- **Promote on proven reuse, never NIH:** extract generalizable primitives upstream to shared libraries only when needed by ≥ 2–3 real consumers **and** clearly simpler or better-fitted than vetted system or C libraries (do not reimplement compression, crypto, or parsers from scratch). Keep CLI flags, config schemas, error types, and terminology consistent across sibling tools.
- **Context-aware localization:** before adding or editing translations, read all existing language files and UI call sites so terminology, tone, and length fit the control — never translate keys literally in isolation.
- **General UI & interaction craft:** align elements optically (to visible glyph/icon bounds rather than raw invisible frames), verify contrast in both light and dark appearances without clipping blurs or faking system chrome, prefer native controls with modifier-key (`⌥` / `⌥⇧`) progressive disclosure for power actions, and back configurable behavior with strongly typed settings and sensible defaults.

---

## 8. Machine Etiquette, Compute & Scope Isolation

- **Never steal focus or pointer control:** must not bring windows to the foreground, move the cursor, or synthesize disruptive GUI input while the user works. Drive apps headlessly, via CLI, or through background accessibility queries unless the user asks for an interactive window.
- **Never touch real user data in tests or repros:** run experiments, migrations, and UI/CLI drivers strictly against isolated temporary directories, mock fixtures, or throwaway accounts, and delete `/tmp` and scratch build artifacts when done.
- **Budget local and CI compute:** cap CI job timeouts to ~2× normal runtime, enable branch concurrency cancellation on PRs/feature branches (never cancelling `main` or release tags), bound matrix fan-out to available runners, and never run the same heavy suite locally and on CI simultaneously.
- **Strict public vs. company isolation:** never leak company names, internal repo/ticket identifiers, work emails, hostnames, home-directory paths, or signing keys into public repositories, and route public pushes/tags through the designated isolated environment when configured.

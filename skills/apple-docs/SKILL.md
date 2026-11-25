---
name: apple-docs
description: >-
  Apple platforms: look up exact API behavior, availability, deprecations, platform
  support, HIG, App Store Review Guidelines, Swift Evolution, WWDC sessions, SF Symbols,
  and Apple system fonts using apple-docs MCP server or CLI (with Xcode SDK interface
  fallback). Use for any version-sensitive Apple claim, symbol verification, or tooling
  setup. For builds and device workflows, use `xcode`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Apple Docs (MCP + CLI + SDK Interfaces)

Offline-first verification for every Apple platform claim: API signatures, availability,
deprecations, HIG, App Store Review Guidelines, Swift Evolution, WWDC sessions, SF Symbols,
and Apple fonts.

Corpus and tooling: [g-cqd/apple-docs](https://github.com/g-cqd/apple-docs).

## Contract

```
§ORDER    MCP → CLI → SDK-interfaces|headers ∈ Xcode.app
§BAN      web-fetch|web-search ∀Apple-docs · silent-fallback-to-memory
§CLAIM    version-sensitive-claim ⇒ ? verify ∨ ⚑"could not verify"
§QUERY    keyword ¬natural-language ⇒ exact-symbol-name
§CONSENT  ⍰ user BEFORE snapshot-download ∨ MCP-config-write
```

---

## 1. Detect what is available

1. **MCP server** (preferred — zero shell overhead, structured pagination & symbol rendering):
   Check for `apple-docs` MCP tools in this session (`mcp__apple-docs__*` in `ask`/Claude Code/Codex,
   `mcp_apple_docs_*` in Mistral Vibe, `apple-docs` in Antigravity).
2. **CLI**: run `command -v apple-docs`.
3. **Neither**: propose installation (§5) and, until installed, verify directly against Xcode's SDK
   `.swiftinterface` and header files (§4 step 5).

Never answer a version-sensitive claim (availability, deprecation, platform support, SDK delta)
from memory without saying so. If no source above can verify it, write **"could not verify"**
beside the claim.

---

## 2. MCP Tool Reference

| Tool | When to use | Key parameters |
|---|---|---|
| `search_docs` | Keyword + semantic lookup across docs, HIG, WWDC, Swift Evolution, sample code | `query` (compact symbol/API term), `framework` (e.g. `swiftui`, `app-store-review`), `platform` (`ios`/`macos`/`visionos`/…), `minVersion` (`{"ios":"17.0"}`), `deprecated: "exclude"` when writing code, `source` (`apple-docc`, `hig`, `wwdc`, `sample-code`, `swift-evolution`), `year`, `read: true` to inline top hit, `match` for excerpts |
| `read_doc` | Read one page by `path` (`swiftui/view`, `app-store-review/3.1`) or `symbol` (`NavigationStack`) | `framework` to disambiguate; `section` for one heading; `maxChars` + `page` to paginate long pages; `match` for targeted excerpts |
| `list_frameworks` | List indexed documentation roots with page counts | `kind` (`framework`, `technology`, `tooling`, `guidelines`, `design`, `release-notes`, `tutorial`) |
| `browse` | Walk a framework's topic tree or a WWDC year's sessions | `framework` (`swiftui`, `design`, `wwdc`), `path`, `year`, `limit` |
| `list_taxonomy` | Discover valid `kind`, `role`, `docKind`, `roleHeading`, `sourceType` filters | `field`, `all` |
| `search_sf_symbols` | Find SF Symbol names, categories, aliases, or keywords | `query`, `scope` (`public` / `private`), `limit` |
| `render_sf_symbol` | Preview an SF Symbol as SVG or PNG | `name`, `format` (`svg`/`png`), `weight`, `scale`, `size`, `color`, `background` |
| `list_apple_fonts` / `render_font_text` | Inspect Apple system font families & render SVG preview | `fontId`, `text`, `size` |

**MCP efficiency rules:**
- Prefer compact symbol terms in `query` and put constraints (`framework`, `platform`, `deprecated: "exclude"`, `source`) in filter args.
- Never pull an entire massive page (like `swiftui/view`) raw into context: pass `section`, `match`, or `maxChars` + `page`.
- Use `read: true` on `search_docs` when you already know the exact symbol name to save a round trip.

---

## 3. CLI Reference

```bash
# Search (exact symbol / API terms + structured filters)
apple-docs search "NavigationStack"
apple-docs search "Swift Testing" --source wwdc --year 2024
apple-docs search "privacy" --framework app-store-review --read
apple-docs search "swipeActions" --framework swiftui --deprecated exclude

# Read & orient
apple-docs read swiftui/view --section Overview
apple-docs read View --framework swiftui
apple-docs frameworks
apple-docs browse swiftui
apple-docs browse wwdc --year 2025

# SF Symbols & corpus freshness
apple-docs symbols "square.and.arrow.up"
apple-docs status            # check corpus age once per session when SDK version matters
apple-docs sync              # refresh snapshot (ask user before large download)
apple-docs --help            # exhaustive command reference
```

---

## 4. Verification Workflow

1. Search the **exact** symbol, API, entitlement, or guideline name (`NavigationStack`,
   `ENABLE_ENHANCED_SECURITY`, `WKContentRuleListStore`), not a natural-language question.
   In at least one query, use the symbol exactly as the user wrote it.
2. Read the matched document using `--section` / `section` / `match` / `maxChars`.
3. Quote exact availability, deprecations, and guideline wording (App Store Review Guidelines
   and HIG must be quoted, never paraphrased) and cite the doc path (e.g. `swiftui/view`).
4. If documentation and observed compiler/runtime behaviour conflict, state the conflict plainly.
5. **Last resort (and final authority when docs disagree):** inspect the installed Xcode SDK
   `.swiftinterface` and header files under
   `$(xcode-select -p)/Platforms/*.platform/Developer/SDKs/*.sdk/System/Library/Frameworks/`.
   The shipping SDK wins over stale docs.
6. When a question names an SDK version or asks about new/changed APIs, run `apple-docs status`
   once per session (if CLI is present). If the corpus predates the SDK, state it and suggest
   `apple-docs sync` or verify via the SDK files.

---

## 5. Installation — Propose, Do Not Impose

Ask the user before downloading a snapshot (~1.5 GB download; 3–8.6 GB on disk depending on
profile) or writing any MCP client config.

**Local offline install (CLI + MCP + web UI; requires Bun 1.1+):**

```bash
git clone https://github.com/g-cqd/apple-docs.git
cd apple-docs
bun run dev:setup            # bun install + bun link
apple-docs setup --compact   # ~3 GB; omit --compact for balanced (~5.5 GB)
apple-docs mcp install       # writes local MCP config (ask user first)
```

**No-install hosted Streamable HTTP MCP fallback** (`https://apple-docs-mcp.everest.mt/mcp`,
best-effort, no SLA; ask user before wiring — sends queries to a third-party host; recommend
self-hosting for teams):

```bash
claude mcp add -s user --transport http apple-docs https://apple-docs-mcp.everest.mt/mcp
codex mcp add apple-docs --url https://apple-docs-mcp.everest.mt/mcp
agy mcp add --transport http apple-docs https://apple-docs-mcp.everest.mt/mcp
```

## Boundaries

| Need | Skill |
|---|---|
| Engineering doctrine, Swift 6 / SwiftUI architecture, testing, security, CI | `software-engineering` |
| Building, signing, simulators, devices, Xcode MCP bridge | `xcode` |
| Repository branch/commit/PR conventions | `project-conventions` |
| PR descriptions, ADRs, RFCs, release notes | `work-docs` |

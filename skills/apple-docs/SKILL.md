---
name: apple-docs
description: >
  Apple platforms: primary-source lookup of Apple developer documentation
  through the apple-docs CLI and MCP server — DocC framework reference, Human
  Interface Guidelines, App Store Review Guidelines, Swift Evolution proposals,
  the Swift Book, WWDC session transcripts, sample code, SF Symbols, and Apple
  fonts. Use whenever an answer depends on exact API behavior, an @available
  attribute, platform support, HIG or App Store Review wording, or WWDC content
  — before trusting training memory, which ages badly on Apple APIs. Use it to
  resolve a disagreement between a curated summary and the real documentation,
  to check whether a symbol exists at a given OS version, to find an SF Symbol
  name, or to quote a review guideline exactly. Also use to set up the tooling:
  detect whether the MCP server or CLI is present and propose installation.
  Not for build or run workflows, which is `xcode`; not for curated
  SDK-generation adoption guides, which is `apple-platforms`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Apple Docs

This skill owns **getting the authoritative answer**. Every other Apple skill defers to it when a
claim is load-bearing.

Corpus and tooling: [apple-docs](https://github.com/g-cqd/apple-docs), offline-first.

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

1. **MCP server** — are `mcp__apple-docs__*` tools in this session (`search_docs`, `read_doc`,
   `list_frameworks`, `browse`, `list_taxonomy`, `search_sf_symbols`, `render_sf_symbol`, …)? Use
   them directly.
2. **CLI** — `command -v apple-docs`.
3. **Neither** → propose installation (§4).

**Never silently fall back to memory for a version-sensitive claim.** Say what you could not
verify. An unverified availability claim is worse than an admission, because the reader cannot
tell it apart from a verified one.

## 2. Query discipline

Queries are **keyword-based, not natural language**. Search the exact symbol, API, or feature
name — `NavigationStack`, `swipeActions`, `ENABLE_ENHANCED_SECURITY` — not a question like "how do
I make a list swipe". Refine with `--framework` and `--source` filters rather than longer prose.

### MCP, when available

- `search_docs` first (tiered search), then `read_doc` on the best hit.
- `list_frameworks` / `browse` to orient in an unfamiliar framework.
- `list_taxonomy` to enumerate valid filter values.
- `search_sf_symbols` / `render_sf_symbol` for symbol names and availability.
- Paginate long pages with `maxChars` rather than pulling a whole document into context.

### CLI

```bash
apple-docs search "NavigationStack"
apple-docs search "Swift Testing" --source wwdc --year 2024
apple-docs search "privacy" --framework app-store-review --read
apple-docs read swiftui/view --section Overview
apple-docs read View --framework swiftui
apple-docs frameworks
apple-docs browse swiftui
apple-docs status            # corpus freshness
apple-docs --help            # exhaustive reference
```

## 3. Verification workflow

1. Search the exact symbol or feature name.
2. Read the matched document; prefer `--section` or `maxChars` to limit output.
3. **Quote** availability and behavior from the document, and cite the doc key —
   e.g. `swiftui/view`.
4. If the documentation and observed compiler or runtime behavior **conflict, say so explicitly**
   rather than picking one silently.
5. **Last resort** — inspect the SDK directly. `.swiftinterface` and header files under
   `Xcode.app/Contents/Developer/Platforms/…/SDKs/` are ground truth for what actually ships, and
   outrank documentation when the two disagree.

When wording itself matters — App Store Review Guidelines, HIG — **quote, do not paraphrase**. A
paraphrased review guideline has lost the thing that made it worth checking.

## 4. Installation — propose, do not impose

Installation downloads a ~1.5 GB snapshot, occupying 3–8.6 GB on disk depending on profile.
**Ask first, and let the user pick the profile.**

Full install — CLI, MCP, and local website; requires Bun 1.1+:

```bash
git clone https://github.com/g-cqd/apple-docs.git
cd apple-docs
bun run dev:setup            # bun install + bun link
apple-docs setup --compact   # ~3 GB; omit the flag for balanced (~5.5 GB)
```

Verify with `apple-docs search "NavigationStack"`, which works offline.

MCP wiring:

```bash
apple-docs mcp install       # writes local MCP client config
# or:
claude mcp add -s user apple-docs -- apple-docs mcp start
```

No-install fallback — a public instance, best-effort with no SLA:

```bash
claude mcp add -s user --transport http apple-docs https://apple-docs-mcp.everest.mt/mcp
```

For production or team use, self-host rather than depending on the public instance.

## 5. Guardrails

- Ask before downloading the snapshot or writing MCP configuration.
- **Treat corpus age as part of the answer.** Check `apple-docs status`; if the corpus predates
  the SDK under discussion, say so and suggest `apple-docs sync`. A confident answer from a stale
  corpus is the failure mode this skill exists to prevent.
- All tools are read-only and fast — there is no cost to checking rather than guessing.

## Boundaries

| Need | Skill |
|---|---|
| Curated adoption guides for the SDK generation | `apple-platforms` |
| SwiftUI view APIs and SDK 27 deltas | `swiftui` |
| Building, testing, running, device verification | `xcode` |
| Swift language and concurrency rules | `swift` |

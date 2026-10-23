---
name: apple-docs
description: >-
  Apple platforms: look up API behavior, availability, platform support, HIG, App Store
  Review Guidelines, Swift Evolution, WWDC, and SF Symbols using apple-docs MCP or CLI.
  Use for exact documentation and tooling setup. For SDK adoption, use `apple-platforms`;
  for builds and device workflows, use `xcode`.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Apple Docs

Other Apple skills defer to this skill when a claim depends on exact API behaviour,
availability, or guideline wording.

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

1. **MCP server**: if `apple-docs` MCP tools are in this session, use them. The tool names are
   `mcp__apple-docs__*` in Claude Code and Codex, `mcp_apple_docs_*` in Mistral Vibe, and
   `apple-docs` in Antigravity's `call_mcp_tool`. The tools are `search_docs`, `read_doc`,
   `list_frameworks`, `browse`, `list_taxonomy`, `search_sf_symbols`, `render_sf_symbol`, …
2. **CLI**: run `command -v apple-docs`.
3. **Neither**: propose installation (§4). Until the user installs, use the SDK interfaces (§3
   step 5).

A version-sensitive claim is one about availability, deprecation, platform support, or behaviour
that changed between SDKs. Do not answer such a claim from memory without saying so. If no source
above can verify it, state "could not verify" next to the claim.

## 2. Query discipline

Search with keywords, not natural language. Search the exact symbol, API, or feature name
(`NavigationStack`, `swipeActions`, `ENABLE_ENHANCED_SECURITY`), not a question such as "how do I
make a list swipe". To narrow results, add `--framework` and `--source` filters, not more words.

When a question centres on an API name, look the name up before answering, including a name you
are sure about; Apple APIs change in each SDK. In at least one query, use the symbol exactly as
the user wrote it.

If two refined searches find no matching document, report that the corpus has no match and go to
the SDK interfaces (§3 step 5).

### MCP, when available

- `search_docs` first (tiered search), then `read_doc` on the best hit.
- `list_frameworks` / `browse` to orient in an unfamiliar framework.
- `list_taxonomy` to list valid filter values.
- `search_sf_symbols` / `render_sf_symbol` for symbol names and availability.
- Paginate long pages with `maxChars`; do not read a whole long document into context.

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
2. Read the matched document. Use `--section` or `maxChars` to limit output.
3. Quote availability and behaviour from the document, marked as a quotation, and cite the doc
   key (for example `swiftui/view`). Write the rest of the answer in your own words.
4. If the documentation and observed compiler or runtime behaviour conflict, state the conflict.
5. **Last resort**: inspect the SDK. `.swiftinterface` and header files under
   `Xcode.app/Contents/Developer/Platforms/…/SDKs/` show what ships. When they disagree with the
   documentation, the SDK files win.

For App Store Review Guidelines and the HIG, quote the text; do not paraphrase it.

## 4. Installation — propose, do not impose

Installation downloads a ~1.5 GB snapshot, which takes 3–8.6 GB on disk depending on profile.
Ask the user before installing, and let the user pick the profile. If the user declines, use the
SDK interfaces (§3 step 5). Offer the public instance below as a separate question; it writes MCP
config and sends queries to a third-party server.

Full install (CLI, MCP, and local website; requires Bun 1.1+):

```bash
git clone https://github.com/g-cqd/apple-docs.git
cd apple-docs
bun run dev:setup            # bun install + bun link
apple-docs setup --compact   # ~3 GB; omit the flag for balanced (~5.5 GB)
```

Verify with `apple-docs search "NavigationStack"`, which works offline.

MCP wiring (ask before writing MCP configuration):

```bash
apple-docs mcp install       # writes local MCP client config
# or:
claude mcp add -s user apple-docs -- apple-docs mcp start
```

No-install fallback: the hosted Streamable HTTP instance `https://apple-docs-mcp.everest.mt/mcp`, best-effort with no SLA.

```bash
# Claude Code (~/.claude.json):
claude mcp add -s user --transport http apple-docs https://apple-docs-mcp.everest.mt/mcp

# Codex (~/.codex/config.toml):
codex mcp add apple-docs --url https://apple-docs-mcp.everest.mt/mcp

# Antigravity (~/.gemini/config/mcp_config.json):
agy mcp add apple-docs --transport http https://apple-docs-mcp.everest.mt/mcp

# Mistral Vibe (~/.vibe/config.toml):
# [[mcp_servers]]
# name = "apple-docs"
# transport = "streamable-http"
# url = "https://apple-docs-mcp.everest.mt/mcp"
```

For production or team use, recommend self-hosting instead of the public instance.

## 5. Guardrails

- Treat corpus age as part of the answer. When the question names an SDK version or asks about
  new or changed APIs, run `apple-docs status` once per session. If the corpus predates the SDK in
  question, say so and suggest `apple-docs sync`. With the MCP server only (no CLI), skip this
  check and note that corpus age is unknown.

## Boundaries

| Need | Skill |
|---|---|
| Curated adoption guides for the SDK generation | `apple-platforms` |
| SwiftUI view APIs and SDK 27 deltas | `swiftui` |
| Building, testing, running, device verification | `xcode` |
| Swift language and concurrency rules | `swift` |

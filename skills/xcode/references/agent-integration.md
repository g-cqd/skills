# Agent integration

Detail for `SKILL.md` §3. Read it when wiring Xcode's MCP bridge, project instructions, skills, or plan mode.

- **MCP bridge** — Xcode exposes its tools over MCP via `xcrun mcpbridge`: build and test,
  diagnostics, Swift REPL, preview rendering, doc search. Xcode 27 additionally announced debugger
  state, scheme and destination switching, and build-setting / entitlement / `Info.plist`
  inspection; verify against your release notes. Requires **Settings → Intelligence → Allow
  external agents to use Xcode tools**.
  Running `xcrun mcpbridge` with no arguments **starts the stdio MCP server** and fails if Xcode
  is not running — wire it into an MCP client config, do not invoke it interactively:
  - Claude Code: `claude mcp add -s user xcode -- xcrun mcpbridge`
  - Codex: `codex mcp add xcode -- xcrun mcpbridge`
  - Antigravity: `agy mcp add xcode xcrun mcpbridge`
  - Mistral Vibe (`~/.vibe/config.toml`): `[[mcp_servers]]` with `name = "xcode"`, `transport = "stdio"`, `command = "xcrun"`, `args = ["mcpbridge"]`
- **Project instructions** — Xcode reads `AGENTS.md` at the repo root automatically; some coding
  agents read `CLAUDE.md`. Keep one canonical `AGENTS.md` and alias `CLAUDE.md` to it (a symlink, as
  the install script does, or an import).
- **Skills** — Xcode 27 reads Agent Skills in this `SKILL.md` format from
  `~/Library/Developer/Xcode/CodingAssistant/<agent-config>/skills/`, and ships Apple-authored
  skills for SwiftUI, document apps, App Intents, UIKit resizability, security-settings auditing,
  C bounds safety, test modernization, and device interaction. `install.sh` exports that pack
  into `~/.agent-harness/xcode-skills/` (`SKILL.md`, "Xcode skill pack"); the skills here route to it by path.
- **Plans** — Xcode's plan mode produces editable Markdown. When working alongside it, write plans
  as Markdown artifacts the user can edit.

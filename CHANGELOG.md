# Changelog

All notable changes to this repository. Dates are commit dates.

## Unreleased

### Added
- `wait`: block until a process exits, a file is ready, a path is gone, a log line matches, or a command exits 0.
  `wait --run` starts the command as a job that outlives a timeout or a killed call; `wait --job ID` continues the
  wait, `wait --stop ID` stops it, `wait --jobs` lists them.
- `chat`: local agent channels in flat JSONL files, with threads, reactions, unread cursors, file locks, and presence
  from process identity. `docs/tools.md` describes both tools.
- `simplification` skill: a measured pass that removes code and proves each cut is safe.
- Evals for every skill, and trigger and near-miss cases.
- Support for Mistral Vibe, Google Antigravity, OpenCode, and Pi, with per-harness agent formats and ordered model
  fallback lists.
- `CONTRIBUTING.md`, `SECURITY.md`, this changelog, and a CI workflow.

### Changed
- REA's `reverse-engineer-anything` skill is a git submodule (`third_party/rea`, pinned to the `rea-agents` release
  the MCP server runs, sparse checkout). `install.sh` fetches and links it.
- `secure-coding` now does full audits as well as reviews: a review and an audit mode, a finding gate with six named
  facts, `confirmed` / `needs_validation` / `rejected` verdicts with severity only on confirmed findings, severity
  anchors, safe-execution rules, a hunting method, ten domain files (web and identity, client side, AI and agents,
  supply chain, cloud, protocols, availability, data isolation, native code, desktop and mobile IPC), the six-phase
  audit workflow with a coverage ledger and independent verification, and `scripts/validate_audit.py` for its JSON
  files. The method is adapted from Cloudflare's `security-audit` skill (MIT), so that skill is no longer installed.
  The `security-auditor` agent and the planner's `security-audit` template follow it.
- Apple's Xcode 27 skill pack is no longer stored in this repository (about 1 MB of mirrored references and one
  script). `install.sh` exports it from Xcode 27.1 or later and links each skill. The skills here that used its files
  now name the pack skill and the file (`swiftui-specialist/references/foreach.md`), and `xcode` has a section that
  maps the pack to its owning skills.
- `install.sh` moves a real directory that is in the way of a skill link to `~/.agent-harness/backups/`, drops links to
  skills that no longer exist, and takes `--skip-submodules`, `--skip-xcode`, and `--skip-third-party`.
- Skills, agent definitions, and `AGENTS.md` are rewritten in plain, literal-safe language (`docs/AUTHORING.md`
  "Plain-language rules"). The `planner`, `work-docs`, and `xcode` skills keep long procedures in `references/`.
- Waiting on long work uses `wait`. Agents that share a machine talk through `chat`, described in `planner`.
- `README.md` lists the skills and the tools and states the requirements.

### Removed
- `work` (task queue, ordering and planning tool, capacity admission) and the Agora skill. Task order is kept in the
  agent's own task list. The `claudetalk` repository, which held Agora, is archived.

## 2026-10-07

- Xcode 27.1 skill knowledge routed into the owning skills (`swiftui`, `apple-platforms`, `memory-safety`, `xcode`,
  `testing`).

## 2026-09-24 to 2026-09-25

- Read-only agents get a shell that can only read (`agents/claude/hooks/readonly-bash.py`).
- Work order (validity first, then first in, first out) and the rule "wait on the event, not on a fixed sleep" reach
  every agent.
- Model names follow what each harness documents.

## 2026-08-23

- First release: 7 tiered subagents, 19 skills, and one engineering standard.

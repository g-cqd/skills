# Agent Harness

A vendor-neutral set of **agent skills**, **specialized subagents**, **two small tools**, and one **engineering
standard** for AI coding harnesses: Claude Code, OpenAI Codex, Mistral Vibe, Google Antigravity (`agy`), OpenCode,
Pi, and GitHub Copilot. One source, linked into each harness installed on the machine.

- **Skills** teach an agent a domain when a task matches it: a Keychain review loads `secure-coding`, a SwiftUI bug
  loads `swiftui`.
- **Subagents** are scoped workers that the main agent delegates to, each on the cheapest model that can do its job.
- **`AGENTS.md`** is the engineering standard: how to plan, write, review, test, and ship.
- **`wait` and `chat`** let agents wait for work to finish and talk to each other on one machine.

## Requirements

- macOS or Linux, with `bash` and Python 3.9 or later. Nothing else: the tools, the install script, and the build
  script use only the Python standard library. The tests of `agents/build.py` need Python 3.11 or later (`tomllib`), and the skill validator
  (`skills/skill-creator/scripts/quick_validate.py`) needs PyYAML.
- At least one supported harness. `install.sh` links into each one it finds.
- `git`, to fetch the two submodule skills. A download without git skips them and says so.
- For the Xcode skill pack: a Mac with Xcode 27.1 or later. Elsewhere `install.sh` skips the pack and says so.

## Quick start

```bash
git clone git@github.com:g-cqd/skills.git && cd skills
./install.sh --dry-run     # show what it would fetch, export, and link; change nothing
./install.sh               # fetch the submodule skills, export the Xcode pack, link into every detected harness
./install.sh --uninstall   # remove only the links it created
```

`--skip-submodules`, `--skip-xcode`, and `--skip-third-party` leave out the submodule skills, the Xcode pack, or both.

Re-run `./install.sh` after `git pull`. Check the install:

```bash
~/.agent-harness/bin/wait --until true      # prints: wait: `true` exited 0 after 0.0s
~/.agent-harness/bin/chat hello             # prints this session's agent id
```

## What's in here

| Piece | What it is |
|---|---|
| `AGENTS.md` | The engineering standard. Portable: project-specific values are left as a `CONFIGURATION` block to fill in. `CLAUDE.md` is an alias. |
| `skills/` | 20 skills. The catalog is below. |
| `agents/` | 14 subagents, each with a model tier, its own tools, and a turn budget where the job is small. One neutral source renders for six harness formats. |
| `tools/` | `wait` and `chat`: single Python files, linked to `~/.agent-harness/bin`. See `docs/tools.md`. |
| `third_party/` | Git submodule: the REA `reverse-engineer-anything` skill. `third_party/SKILLS` lists the skill directory in each submodule. |
| `install.sh` | Fetches the submodule skills, exports the Xcode skill pack, and links everything into each detected harness. |
| `docs/` | `AUTHORING.md` (how to write a skill, an agent, or a tool) and `tools.md` (the tools: reference and design). |

## Skills

| Group | Skills |
|---|---|
| Plan and deliver | `planner` (plans, task lists, orchestration, second opinions, agent messaging with `chat`), `engineering-practices` (small changes, delivery, waiting with `wait`), `project-conventions`, `simplification`, `work-docs` |
| Review and verify | `code-review`, `debugging`, `testing`, `performance-engineering`, `algorithms` |
| Security and memory | `secure-coding` (reviews, and full audits with a coverage ledger and independent verification), `memory-safety` |
| Swift and Apple platforms | `swift`, `swiftui`, `apple-platforms`, `apple-docs`, `xcode` |
| Systems and graphics | `system-architect`, `graphics` |
| Authoring | `skill-creator` |

Two more sets of skills arrive at install time and are not stored in this repository:

| Set | Skills | Source |
|---|---|---|
| Reverse engineering | `reverse-engineer-anything`: evidence-first analysis of shipped apps and binaries with REA | [morluto/rea](https://github.com/morluto/rea), git submodule |
| Xcode skill pack | `swiftui-specialist`, `swiftui-whats-new-27`, `building-document-based-swiftui-applications`, `app-intents-specialist`, `app-intents-whats-new-27`, `app-resizability`, `adopt-c-bounds-safety`, `audit-xcode-security-settings`, `device-interaction`, `modernize-tests` | Apple, exported from your Xcode 27.1 or later |

The skills above route to them: `xcode` explains the pack, and `secure-coding` names `reverse-engineer-anything` in
its boundaries. A full security audit needs no extra skill: `secure-coding` has an audit mode with a coverage ledger,
independent verification, and a validator for its JSON files. See `THIRD-PARTY-NOTICES.md` for licenses.

A skill description opens with its tier: `Language-agnostic:`, `Apple platforms:`, or the language or domain it owns.
Each skill names the neighbouring skill that owns what it leaves out.

## Tools

| Tool | Use | Example |
|---|---|---|
| `wait` | Block until a stated condition holds: a process exits, a file is ready, a path is gone, a log line matches, or a command exits 0. It keeps no state. | `wait --run -- swift test` |
| `chat` | Talk to other agents on this machine. A channel is one JSONL file with threads, reactions, unread cursors, and online status. No daemon, no database. | `chat say general "taking the parser task" --re ID` |

`docs/tools.md` has the full reference, the file formats, and the reasoning behind the design.

## Subagents and cost

The roster follows **cheap fan-out, expensive judgment**: mechanical, high-volume work goes to a
cheap model; the top model is used only where a wrong answer is expensive to detect.

| Agent | Tier | Job |
|---|---|---|
| `scout` | micro | Read-only exploration and mapping — recon before work |
| `test-runner` | micro | Run a suite, a linter, or a benchmark; report counts and each failure |
| `patcher` | micro | Apply one small edit already decided, and build it |
| `committer` | micro | Commit a finished change in the repository's style; never push |
| `docs-writer` | economy | PR text, tickets, ADRs, release notes |
| `researcher` | standard | Facts from documentation, specifications, and source, each cited |
| `implementer` | standard | Turn a specified change into a small, verified diff |
| `test-engineer` | standard | TDD, regression tests, suite migration |
| `debugger` | reasoning | Root-cause a crash, a failing test, or a hang |
| `perf-engineer` | reasoning | Baseline, profile, change, re-measure |
| `verifier` | reasoning | Reproduce a claim before anyone acts on it |
| `code-reviewer` | reasoning | Correctness / architecture review, adversarial |
| `security-auditor` | frontier | Trust-boundary, memory-safety, iOS attack surface |
| `orchestrator` | frontier | Decompose, route to the cheapest capable specialist, synthesize |

**`agents/tiers.json`** maps the five tiers to each harness's ordered `models` fallback list and
effort. It is the only place where cost and model fallbacks are tuned (Claude Code / Codex shown):

```
micro      sonnet -> haiku (low)          / gpt-6-luna -> gpt-6-sol -> gpt-5.6-luna (low)     one small mechanical job with a clear stop
economy    sonnet -> haiku (medium)       / gpt-6-sol -> gpt-6-luna -> gpt-5.6-sol (low)      mechanical, high-volume, cheap to retry
standard   sonnet -> opus -> haiku (high) / gpt-6-sol -> gpt-6.1-sol -> gpt-5.6-sol (medium)  clear-scope reasoning, tests catch mistakes
reasoning  opus -> fable -> sonnet (med)  / gpt-6-astra -> gpt-6.1-sol -> gpt-6-sol (high)    ambiguous, high-risk, expensive to fix
frontier   fable -> opus -> sonnet (high) / gpt-6-astra -> gpt-6.1-sol -> gpt-6-sol (xhigh)   the costliest miss, the longest runs
```

Re-audit the map every three months: the best-value model in each class changes. To change it,
edit the ids and run `python3 agents/build.py`. `agents/README.md` lists each agent's tools and
budget, and each harness's model fallback list.

## Cross-harness compatibility

Each harness reads a different format, so one neutral source renders six subagent variants and
links into every supported harness:

| Harness | Skills | Agents | Instruction file |
|---|---|---|---|
| Claude Code | `~/.claude/skills/` | `~/.claude/agents/<name>.md` | `~/.claude/CLAUDE.md` |
| Codex | `~/.codex/skills/` | `~/.codex/agents/<name>.toml` | `~/.codex/AGENTS.md` |
| Mistral Vibe | `~/.vibe/skills/` | `~/.vibe/agents/<name>.toml` | `~/.vibe/AGENTS.md` |
| Antigravity (`agy`) | `~/.gemini/config/skills/` | `~/.gemini/config/agents/<name>/agent.md` | `~/.gemini/AGENTS.md` |
| OpenCode | `~/.config/opencode/skills/` | `~/.config/opencode/agents/<name>.md` | `~/.config/opencode/AGENTS.md` |
| Pi | `~/.pi/agent/skills/` | — | `~/.pi/agent/AGENTS.md` |
| Copilot | `~/.copilot/skills/` | `~/.copilot/agents/<name>.agent.md` | `~/.copilot/AGENTS.md` |
| Shared Agent Skills | `~/.agents/skills/` | — | — |

`agents/build.py` maps the neutral tier and capabilities to each harness's terms: model alias, slug,
or display name; tool names, aliases, or permission maps; turn limits and hooks where the harness
has them. Claude Code enforces read-only agents with the tool list and a Bash guard. Copilot and
OpenCode use tools and permissions. Mistral Vibe uses `safety = "safe"`, `enabled_tools`, and its
tool ceiling. Antigravity uses tool allowlists. Codex runs each agent in its parent's sandbox, so on
Codex only the prompt keeps an agent read-only.

## How the install works

`install.sh` builds a canonical root (`~/.agent-harness/`; override with `AGENT_HARNESS_ROOT`) that holds the
standard, the skills, the agents, and `bin/wait` and `bin/chat`. Besides the skills of this repository, it adds two sets:

1. **Submodule skills.** For each line of `third_party/SKILLS`, it runs `git submodule update --init --depth 1` and
   checks out only the skill's directory (sparse checkout), so the REA repository costs about 1 MB on disk. The
   submodules are pinned to a commit. Pin `rea` to the `rea-agents-<version>` tag of the REA server that your MCP
   configuration runs, so the skill matches the server's tools. To update one: `git -C third_party/<name> fetch --depth 1 origin main`, `git -C third_party/<name> checkout FETCH_HEAD`, then commit the changed pointer.
2. **Xcode skill pack.** It runs `xcrun mcpbridge run-agent skills export` into `~/.agent-harness/xcode-skills/` and
   links each exported skill. A description longer than the format's 1,024 characters (Pi refuses those) is
   shortened at a sentence boundary in the local export. A skill of this repository with the same name wins. A skill that leaves the pack, or
   that leaves this repository, loses its link on the next install.

A real directory that is in the way of a skill link moves to `~/.agent-harness/backups/`, not into the skills
directory, where a harness would load it as a second copy.

It then detects each harness (by its home directory
or its CLI on `PATH`) and symlinks the harness's `skills/`, `agents/`, and instruction file (`CLAUDE.md` or
`AGENTS.md`, whichever the harness reads). When `~/.agents` exists, it also links `~/.agents/skills` to the canonical
skills directory.

Running it twice gives the same result. It replaces only its own symlinks and the links named after this repository's
skills, backs up a real file to `<name>.bak` before replacing it, and leaves other skills in the root unchanged.

## Structure

```
AGENTS.md            engineering standard   (CLAUDE.md -> AGENTS.md)
install.sh           the linker
skills/<skill>/      skills                 (SKILL.md, references/, evals/, scripts/)
third_party/         the rea submodule, and SKILLS, the list of skill directories in submodules
tools/               wait.py, chat.py, tests/
agents/
  src/<name>.md      neutral agent sources: edit these
  tiers.json         tier -> per-harness model and effort (the cost dial)
  build.py           renders src/ -> per-harness formats; --check verifies them
  claude/hooks/      the read-only Bash guard, hand-written
  claude/  codex/  copilot/  vibe/  opencode/  agy/    generated, one format each
  tests/             tests for build.py and the guard
tests/               tests for install.sh
docs/                AUTHORING.md, tools.md
```

## Portability

Each skill works in any project without edits: no project identifiers, ticket keys, in-house macros, or team decisions
presented as universal rules. Where a value is the project's choice, the skill states the *procedure* ("detect the
project's convention", "use the project's mock mechanism"), not the value. `project-conventions` reads the value from
the current repository, and a project records it in the `CONFIGURATION` block of `AGENTS.md`.

## Tests

Run these from the repository root. CI runs the same commands (`.github/workflows/ci.yml`).

```bash
python3 agents/build.py --check                  # generated agent files are current
python3 -m unittest discover -s tests            # install.sh against a temporary home
python3 -m unittest discover -s agents/tests     # build.py and the read-only Bash guard
python3 -m unittest discover -s tools/tests      # wait and chat
python3 -m unittest discover -s skills/simplification/scripts/tests
python3 -m unittest discover -s skills/secure-coding/scripts/tests
for skill in skills/*; do python3 skills/skill-creator/scripts/quick_validate.py "$skill" || exit 1; done
```

## Contributing

Read `CONTRIBUTING.md` first, then `docs/AUTHORING.md`. To add a skill, create `skills/<name>/SKILL.md`; to add an
agent, create `agents/src/<name>.md` and run `python3 agents/build.py`.

## License

MIT, see `LICENSE`. Some content is derived from other works or mirrored from Apple's Xcode 27 skill pack under their
own terms: see `THIRD-PARTY-NOTICES.md`. To report a security problem, read `SECURITY.md`.

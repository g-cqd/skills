#!/usr/bin/env bash
#
# install.sh — link this skill set into every coding-agent harness on the machine.
#
# Model: one canonical root under $HOME holds the content; each detected harness
# (Claude Code, Codex, Copilot) gets symlinks pointing at that root. A single
# source of truth, updated by `git pull` in this repo.
#
#   ~/.agent-harness/
#     AGENTS.md            -> <repo>/AGENTS.md          (canonical instructions)
#     CLAUDE.md            -> AGENTS.md                 (alias for agents that read it)
#     skills/<name>        -> <repo>/skills/<name>       (one link per skill)
#     agents/<fmt>         -> <repo>/agents/<fmt>       (per-harness rendered agents)
#     bin/work             -> <repo>/skills/planner/scripts/work.py   (one path every agent can call)
#
#   ~/.claude/  ~/.codex/  ~/.copilot/   (whichever exist)
#     skills               -> ~/.agent-harness/skills
#     agents               -> ~/.agent-harness/agents   (if present)
#     <AGENTS.md|CLAUDE.md>-> the file that harness reads
#
# Usage:
#   ./install.sh                 detect harnesses, link everything
#   ./install.sh --dry-run       print what would happen, change nothing
#   ./install.sh --uninstall     remove only the symlinks this script created
#   AGENT_HARNESS_ROOT=~/x ./install.sh   override the canonical root
#
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${AGENT_HARNESS_ROOT:-$HOME/.agent-harness}"
DRY=0; MODE=install
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --uninstall) MODE=uninstall ;;
    -h|--help) sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'unknown option: %s\n' "$a" >&2; exit 2 ;;
  esac
done

c_bold=$'\033[1m'; c_dim=$'\033[2m'; c_grn=$'\033[32m'; c_ylw=$'\033[33m'; c_off=$'\033[0m'
say()  { printf '%s\n' "$*"; }
step() { printf '%s==>%s %s\n' "$c_bold" "$c_off" "$*"; }
ok()   { printf '  %slinked%s %s %s->%s %s\n' "$c_grn" "$c_off" "$1" "$c_dim" "$c_off" "$2"; }
skip() { printf '  %s%s%s %s\n' "$c_ylw" "skip" "$c_off" "$*"; }

# link <target> <linkname> — idempotent; replaces our own links, backs up real files.
link() {
  local target="$1" name="$2"
  if [[ $DRY -eq 1 ]]; then ok "$name" "$target"; return; fi
  mkdir -p "$(dirname "$name")"
  if [[ -L "$name" ]]; then
    rm -f "$name"
  elif [[ -e "$name" ]]; then
    mv "$name" "$name.bak"; skip "backed up existing $name -> $name.bak"
  fi
  ln -s "$target" "$name"
  ok "$name" "$target"
}

# unlink_ours <linkname> <root> — remove only if it's our symlink: one that points under the canonical root.
unlink_ours() {
  local name="$1" want="$2"
  if [[ -L "$name" && "$(readlink "$name")" == "$want"/* ]]; then
    [[ $DRY -eq 1 ]] || rm -f "$name"
    printf '  removed %s\n' "$name"
  fi
}

# ---------------------------------------------------------------------------
# Harness table: name | home dir | CLI binary | instruction file | agents subdir
# A harness is "present" if its home dir exists OR its CLI is on PATH.
# Each harness reads a different agent format, so it gets its own rendered subdir
# (agents/<fmt>, produced by agents/build.py).
# ---------------------------------------------------------------------------
harness_rows=(
  "Claude Code|$HOME/.claude|claude|CLAUDE.md|claude"
  "Codex|$HOME/.codex|codex|AGENTS.md|codex"
  "Copilot|$HOME/.copilot|copilot|AGENTS.md|copilot"
)

# ---------------------------------------------------------------------------
[[ -f "$SRC/AGENTS.md" ]] || { printf 'AGENTS.md not found next to install.sh (%s)\n' "$SRC" >&2; exit 1; }

if [[ "$MODE" == uninstall ]]; then
  step "Uninstalling links (root: $ROOT)"
  for row in "${harness_rows[@]}"; do
    IFS='|' read -r hname home _cli instr _afmt <<<"$row"
    [[ -d "$home" ]] || continue
    unlink_ours "$home/skills"  "$ROOT"
    unlink_ours "$home/agents"  "$ROOT"
    unlink_ours "$home/$instr"  "$ROOT"
  done
  say ""; say "Canonical root left in place: $ROOT (rm -rf it to remove)."
  exit 0
fi

step "Building canonical root: $ROOT"
[[ $DRY -eq 1 ]] || mkdir -p "$ROOT/skills"
link "$SRC/AGENTS.md" "$ROOT/AGENTS.md"
[[ $DRY -eq 1 ]] || ln -sf AGENTS.md "$ROOT/CLAUDE.md"
ok "$ROOT/CLAUDE.md" "AGENTS.md"

# Every directory under skills/ holding a SKILL.md is one skill, linked by name.
skill_count=0
if [[ -d "$SRC/skills" ]]; then
  for d in "$SRC/skills"/*/; do
    name="$(basename "$d")"
    [[ -f "$d/SKILL.md" ]] || continue
    link "$d" "$ROOT/skills/$name"
    skill_count=$((skill_count + 1))
  done
fi
say "  ${skill_count} skills"

# The work tool at a path that never moves, so an agent calls ~/.agent-harness/bin/work without touching PATH.
if [[ -f "$SRC/skills/planner/scripts/work.py" ]]; then
  link "$SRC/skills/planner/scripts/work.py" "$ROOT/bin/work"
fi

# Optional agents/ — each harness reads a different format, so the root holds
# one link per rendered format subdir (agents/claude, agents/codex, agents/copilot).
# Build them from src/ if a Python is available and the sources exist.
have_agents=0
if [[ -d "$SRC/agents/src" ]]; then
  if command -v python3 >/dev/null 2>&1 && [[ $DRY -eq 0 ]]; then
    ( cd "$SRC/agents" && python3 build.py >/dev/null 2>&1 ) || skip "agents/build.py failed — using any pre-rendered dirs"
  fi
  for fmt in claude codex copilot; do
    [[ -d "$SRC/agents/$fmt" ]] && link "$SRC/agents/$fmt" "$ROOT/agents/$fmt"
  done
  [[ -d "$SRC/agents/claude" ]] && have_agents=1
else
  skip "no agents/ in this repo — skipping agents links"
fi

# ---------------------------------------------------------------------------
found=0
for row in "${harness_rows[@]}"; do
  IFS='|' read -r hname home cli instr afmt <<<"$row"
  present=0
  [[ -d "$home" ]] && present=1
  command -v "$cli" >/dev/null 2>&1 && present=1
  [[ $present -eq 1 ]] || { skip "$hname not detected"; continue; }

  found=$((found + 1))
  step "Linking into $hname ($home)"
  link "$ROOT/skills" "$home/skills"
  # Link the format-matching agents subdir under the harness's own agents/ dir.
  [[ $have_agents -eq 1 && -d "$SRC/agents/$afmt" ]] && link "$ROOT/agents/$afmt" "$home/agents"
  # Link the instruction file under the name this harness reads; the root has both.
  link "$ROOT/$instr" "$home/$instr"
done

say ""
if [[ $found -eq 0 ]]; then
  say "No harness detected. Canonical root is ready at $ROOT;"
  say "point your agent's skills dir at $ROOT/skills when you install one."
else
  say "${c_grn}Done.${c_off} Linked into $found harness(es). Re-run after 'git pull' to pick up updates."
fi
if [[ $DRY -eq 1 ]]; then say "${c_dim}(dry run — nothing changed)${c_off}"; fi

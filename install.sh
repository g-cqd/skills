#!/usr/bin/env bash
#
# install.sh — link this skill set into every coding-agent harness on the machine.
#
# Model: one canonical root under $HOME holds the content; each detected harness
# (Claude Code, Codex, Vibe, Antigravity, OpenCode, Pi, Copilot) gets symlinks
# pointing at that root. A single source of truth, updated by `git pull` in this repo.
#
#   ~/.agent-harness/
#     AGENTS.md            -> <repo>/AGENTS.md          (canonical instructions)
#     CLAUDE.md            -> AGENTS.md                 (alias for agents that read it)
#     AGENTS.<fmt>.md      AGENTS.md + instructions/<fmt>.md, written for a harness with its own additions (codex)
#     skills/<name>        -> <repo>/skills/<name>       (one link per skill)
#     agents/<fmt>         -> <repo>/agents/<fmt>       (per-harness rendered agents)
#     skills/<name>        -> <repo>/third_party/<submodule>/<dir>   (skills from submodules: REA)
#     xcode-skills/<name>/                                       (Apple's Xcode skill pack, exported from your Xcode;
#                                                                 reference material for the owning skills, not linked as skills)
#
#   ~/.claude/  ~/.codex/  ~/.vibe/  ~/.gemini/config/  ~/.config/opencode/  ~/.pi/agent/  ~/.copilot/
#     skills               -> ~/.agent-harness/skills
#     agents               -> ~/.agent-harness/agents/<fmt>   (if supported)
#     <AGENTS.md|CLAUDE.md>-> the file that harness reads
#
# Usage:
#   ./install.sh                   link into harnesses whose home directory exists (default full profile)
#   ./install.sh --harnesses LIST  comma-separated harness ids to link/create (claude,codex,vibe,agy,opencode,pi,copilot)
#   ./install.sh --profile NAME    link only skills listed in profiles/NAME.txt (e.g. --profile minimal)
#   ./install.sh --dry-run         print what would happen, change nothing
#   ./install.sh --uninstall       remove only the symlinks this script created
#   ./install.sh --skip-submodules do not fetch or link the submodule skills (third_party/SKILLS)
#   ./install.sh --skip-xcode      do not export or link the Xcode skill pack
#   ./install.sh --skip-third-party  both of the above
#   AGENT_HARNESS_ROOT=~/x ./install.sh   override the canonical root
#
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${AGENT_HARNESS_ROOT:-$HOME/.agent-harness}"
DRY=0; MODE=install; SKIP_SUBMODULES=0; SKIP_XCODE=0; PROFILE="default"; HARNESSES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --uninstall) MODE=uninstall; shift ;;
    --skip-submodules) SKIP_SUBMODULES=1; shift ;;
    --skip-xcode) SKIP_XCODE=1; shift ;;
    --skip-third-party) SKIP_SUBMODULES=1; SKIP_XCODE=1; shift ;;
    --profile)
      [[ $# -ge 2 ]] || { printf '--profile requires a name\n' >&2; exit 2; }
      PROFILE="$2"; shift 2 ;;
    --profile=*)
      PROFILE="${1#--profile=}"; shift ;;
    --harnesses)
      [[ $# -ge 2 ]] || { printf '--harnesses requires a comma-separated list
' >&2; exit 2; }
      HARNESSES="$2"; shift 2 ;;
    --harnesses=*)
      HARNESSES="${1#--harnesses=}"; shift ;;
    -h|--help) sed -n '2,34p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

PROFILE_FILE=""
PROFILE_SKILLS=()
if [[ "$PROFILE" != "default" && "$PROFILE" != "full" ]]; then
  PROFILE_FILE="$SRC/profiles/$PROFILE.txt"
  [[ -f "$PROFILE_FILE" ]] || { printf 'unknown profile: %s (expected %s)\n' "$PROFILE" "$PROFILE_FILE" >&2; exit 2; }
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    line="$(printf '%s' "$line" | tr -d '[:space:]')"
    [[ -n "$line" ]] && PROFILE_SKILLS+=("$line")
  done < "$PROFILE_FILE"
fi

skill_selected() {
  local name="$1"
  [[ -z "$PROFILE_FILE" ]] && return 0
  local wanted
  for wanted in "${PROFILE_SKILLS[@]}"; do
    [[ "$wanted" == "$name" ]] && return 0
  done
  return 1
}

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
    local backup="$name.bak"
    if [[ "$name" == "$ROOT/skills/"* ]]; then
      # A backup inside the skills root would load as a second copy of the skill, so it goes beside the root.
      mkdir -p "$ROOT/backups"; backup="$ROOT/backups/$(basename "$name").$(date +%Y%m%d%H%M%S)"
    fi
    mv "$name" "$backup"; skip "backed up existing $name -> $backup"
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
# Harness table: name | home dir | id | instruction file | agents subdir
# A harness is linked only when its home dir already exists (opt-in on disk) OR its id is listed in --harnesses.
# Never auto-create a harness home directory merely because a CLI binary happens to sit on PATH.
# If the instruction file starts with '/', it is an absolute path (e.g. Antigravity
# reads ~/.gemini/AGENTS.md while skills and agents live under ~/.gemini/config/).
# Each harness reads a different agent format, so it gets its own rendered subdir
# (agents/<fmt>, produced by agents/build.py).
# ---------------------------------------------------------------------------
harness_rows=(
  "Claude Code|$HOME/.claude|claude|CLAUDE.md|claude"
  "Codex|${CODEX_HOME:-$HOME/.codex}|codex|AGENTS.md|codex"
  "Vibe|${VIBE_HOME:-$HOME/.vibe}|vibe|AGENTS.md|vibe"
  "Antigravity|$HOME/.gemini/config|agy|$HOME/.gemini/AGENTS.md|agy"
  "OpenCode|${OPENCODE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode}|opencode|AGENTS.md|opencode"
  "Pi|${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}|pi|AGENTS.md|"
  "Copilot|$HOME/.copilot|copilot|AGENTS.md|copilot"
)

harness_requested() {
  local hid="$1"
  [[ -n "$HARNESSES" ]] || return 1
  [[ ",$HARNESSES," == *",$hid,"* ]]
}

# ---------------------------------------------------------------------------
[[ -f "$SRC/AGENTS.md" ]] || { printf 'AGENTS.md not found next to install.sh (%s)\n' "$SRC" >&2; exit 1; }

if [[ "$MODE" == uninstall ]]; then
  step "Uninstalling links (root: $ROOT)"
  for row in "${harness_rows[@]}"; do
    IFS='|' read -r _hname home _cli instr _afmt <<<"$row"
    instr_link="$home/$instr"
    [[ "$instr" == /* ]] && instr_link="$instr"
    if [[ -d "$home" || -L "$instr_link" ]]; then
      unlink_ours "$home/skills"  "$ROOT"
      unlink_ours "$home/agents"  "$ROOT"
      unlink_ours "$instr_link"   "$ROOT"
    fi
  done
  if [[ -d "$HOME/.agents" ]]; then
    unlink_ours "$HOME/.agents/skills"    "$ROOT"
    unlink_ours "$HOME/.agents/AGENTS.md" "$ROOT"
  fi
  say ""; say "Canonical root left in place: $ROOT (rm -rf it to remove)."
  exit 0
fi

step "Building canonical root: $ROOT"
[[ $DRY -eq 1 ]] || mkdir -p "$ROOT/skills"
link "$SRC/AGENTS.md" "$ROOT/AGENTS.md"
[[ $DRY -eq 1 ]] || ln -sf AGENTS.md "$ROOT/CLAUDE.md"
ok "$ROOT/CLAUDE.md" "AGENTS.md"

# Every directory under skills/ holding a SKILL.md is one skill, linked by name (filtered by --profile if set).
skill_count=0
if [[ -d "$SRC/skills" ]]; then
  for d in "$SRC/skills"/*/; do
    name="$(basename "$d")"
    [[ -f "$d/SKILL.md" ]] || continue
    skill_selected "$name" || continue
    link "$d" "$ROOT/skills/$name"
    skill_count=$((skill_count + 1))
  done
fi
say "  ${skill_count} skills (profile: ${PROFILE})"

# When using a named profile, prune repo-owned skill links that are not in the profile.
if [[ $DRY -eq 0 && -n "$PROFILE_FILE" && -d "$ROOT/skills" ]]; then
  for existing in "$ROOT/skills"/*; do
    [[ -L "$existing" ]] || continue
    name="$(basename "$existing")"
    target="$(readlink "$existing")"
    if [[ "$target" == "$SRC"/skills/* || "$target" == "$SRC"/third_party/* ]]; then
      if ! skill_selected "$name"; then
        rm -f "$existing"; printf '  pruned %s (not in profile %s)\n' "$existing" "$PROFILE"
      fi
    fi
  done
fi

# Skills from git submodules (third_party/SKILLS lists them): fetch each one shallow, check out only its skill
# directory, and link it. A checkout without git, or without network, keeps what it already has.
fetch_submodule() {
  local mod="$1" sub="$2"
  if [[ $SKIP_SUBMODULES -eq 1 ]]; then return 1; fi
  if [[ $DRY -eq 1 ]]; then say "  would fetch $mod ($sub)"; return 0; fi
  if ! command -v git >/dev/null 2>&1 || [[ ! -e "$SRC/.git" ]]; then
    [[ -f "$SRC/$mod/$sub/SKILL.md" ]] || skip "$mod: not a git checkout; clone with --recurse-submodules"
    return 0
  fi
  if git -C "$SRC" submodule update --init --depth 1 -- "$mod" >/dev/null 2>&1; then
    git -C "$SRC/$mod" sparse-checkout set "$sub" >/dev/null 2>&1 || true
  else
    [[ -f "$SRC/$mod/$sub/SKILL.md" ]] || skip "cannot fetch $mod; run: git submodule update --init --depth 1 $mod"
  fi
}
third_party_count=0
if [[ -f "$SRC/third_party/SKILLS" && $SKIP_SUBMODULES -eq 0 ]]; then
  step "Linking skills from submodules"
  while IFS='|' read -r mod sub; do
    [[ -z "${mod// /}" || "$mod" == \#* ]] && continue
    skill_selected "$(basename "$sub")" || continue
    fetch_submodule "$mod" "$sub" || continue
    if [[ $DRY -eq 1 || -f "$SRC/$mod/$sub/SKILL.md" ]]; then
      link "$SRC/$mod/$sub" "$ROOT/skills/$(basename "$sub")"
      third_party_count=$((third_party_count + 1))
    fi
  done < "$SRC/third_party/SKILLS"
fi

# run_bounded SECONDS COMMAND...: run COMMAND, and stop it (TERM, then KILL) when it outlasts SECONDS. Returns its
# status, or 124 when it was stopped. macOS has no `timeout` command, so this is done with a background job.
run_bounded() {
  local limit="$1"; shift
  "$@" &
  local pid=$! ticks=0
  while kill -0 "$pid" 2>/dev/null; do
    if (( ticks >= limit * 10 )); then
      kill "$pid" 2>/dev/null; sleep 1; kill -9 "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      return 124
    fi
    sleep 0.1; ticks=$((ticks + 1))
  done
  wait "$pid"
}

# Apple's Xcode skill pack is not shipped here. Xcode 27.1 or later exports it into $ROOT/xcode-skills, where the skills
# of this repository that own its topics read it by path. It is not linked into the skills directory: each pack skill
# would compete with its owner for the same requests.
# AGENT_HARNESS_XCODE_EXPORT replaces the exporter command; it is called with --output-dir DIR --replace-existing.
# The exporter starts Xcode when it is not running and can wait on a dialog that nobody sees (over SSH, on a first
# launch), so it gets AGENT_HARNESS_XCODE_TIMEOUT seconds (default 120).
install_xcode_skills() {
  [[ $SKIP_XCODE -eq 1 ]] && return 0
  step "Exporting the Xcode skill pack"
  local exporter="${AGENT_HARNESS_XCODE_EXPORT:-xcrun mcpbridge run-agent skills export}" dest="$ROOT/xcode-skills"
  local -a command_words
  read -r -a command_words <<<"$exporter"
  if [[ -z "${AGENT_HARNESS_XCODE_EXPORT:-}" && ( "$(uname)" != Darwin || ! -x "$(command -v xcrun || true)" ) ]]; then
    skip "Xcode skills: needs macOS with Xcode 27.1 or later; skipped"; return 0
  fi
  if [[ $DRY -eq 1 ]]; then say "  would run: $exporter --output-dir $dest --replace-existing"; return 0; fi
  # Export into a fresh directory and swap it in, so a skill that left the pack disappears and its link is pruned.
  local fresh="$dest.new"
  rm -rf "$fresh"; mkdir -p "$fresh"
  local exported=0
  run_bounded "${AGENT_HARNESS_XCODE_TIMEOUT:-120}" "${command_words[@]}" --output-dir "$fresh" --replace-existing \
    >/dev/null 2>&1 || exported=$?
  if [[ $exported -ne 0 ]]; then
    rm -rf "$fresh"
    if [[ $exported -eq 124 ]]; then
      skip "Xcode skills: the export did not finish in ${AGENT_HARNESS_XCODE_TIMEOUT:-120} s (Xcode may be waiting on a dialog: open Xcode, answer it, and run install.sh again)"
    else
      skip "Xcode skills: the export failed (Xcode 27.1 or later is needed)"
    fi
    [[ -d "$dest" ]] || return 0
    say "  using the previous export in $dest"
  else
    rm -rf "$dest"; mv "$fresh" "$dest"
  fi
  local count
  count=$(find "$dest" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')
  say "  ${count} Xcode skills exported to $dest (reference material, not linked as skills)"
}
install_xcode_skills

# Drop skill links that no longer point at anything (a skill removed from this repository), and links into the Xcode
# export, which earlier versions of this script created.
if [[ $DRY -eq 0 && -d "$ROOT/skills" ]]; then
  for stale in "$ROOT/skills"/*; do
    [[ -L "$stale" ]] || continue
    target="$(readlink "$stale")"
    if [[ "$target" == "$ROOT"/xcode-skills/* ]] || { [[ ! -e "$stale" ]] && [[ "$target" == "$SRC"/* ]]; }; then
      rm -f "$stale"; printf '  removed link %s\n' "$stale"
    fi
  done
fi

# The earlier wait, chat, and work tools are gone; drop stale links left by previous installs.
if [[ $DRY -eq 0 && -d "$ROOT/bin" ]]; then
  for retired in wait chat work; do
    if [[ -L "$ROOT/bin/$retired" ]]; then
      target="$(readlink "$ROOT/bin/$retired")"
      if [[ "$target" == "$SRC"/tools/* || "$target" == "$SRC"/skills/* || "$target" == "$ROOT"/releases/* || ! -e "$ROOT/bin/$retired" ]]; then
        rm -f "$ROOT/bin/$retired"
      fi
    fi
  done
  rmdir "$ROOT/bin" 2>/dev/null || true
fi

# Optional agents/ — each harness reads a different format, so the root holds
# one link per rendered format subdir (agents/claude, agents/codex, agents/copilot,
# agents/vibe, agents/opencode, agents/agy).
# Build them from src/ if a Python is available and the sources exist.
have_agents=0
if [[ -d "$SRC/agents/src" ]]; then
  if command -v python3 >/dev/null 2>&1 && [[ $DRY -eq 0 ]]; then
    ( cd "$SRC/agents" && python3 build.py >/dev/null 2>&1 ) || skip "agents/build.py failed — using any pre-rendered dirs"
  fi
  for fmt in claude codex copilot vibe opencode agy; do
    [[ -d "$SRC/agents/$fmt" ]] && link "$SRC/agents/$fmt" "$ROOT/agents/$fmt"
  done
  [[ -d "$SRC/agents/claude" ]] && have_agents=1
else
  skip "no agents/ in this repo — skipping agents links"
fi

# ---------------------------------------------------------------------------
found=0
for row in "${harness_rows[@]}"; do
  IFS='|' read -r hname home hid instr afmt <<<"$row"
  if [[ -n "$HARNESSES" ]]; then
    harness_requested "$hid" || { skip "$hname not in --harnesses"; continue; }
  else
    present=0
    [[ -d "$home" ]] && present=1
    [[ "$hname" == "Antigravity" && -d "$HOME/.gemini/antigravity-cli" ]] && present=1
    [[ "$hname" == "Pi" && -d "$HOME/.pi" ]] && present=1
    [[ $present -eq 1 ]] || { skip "$hname not detected"; continue; }
  fi

  found=$((found + 1))
  step "Linking into $hname ($home)"
  link "$ROOT/skills" "$home/skills"
  # Link the format-matching agents subdir under the harness's own agents/ dir.
  [[ $have_agents -eq 1 && -n "$afmt" && -d "$SRC/agents/$afmt" ]] && link "$ROOT/agents/$afmt" "$home/agents"
  # Link the instruction file under the name this harness reads; the root has both. A harness with its own additions
  # (instructions/<fmt>.md) reads the standard followed by them, from a file this script writes into the root.
  extra="$SRC/instructions/$afmt.md"
  if [[ -n "$afmt" && -f "$extra" ]]; then
    combined="$ROOT/AGENTS.$afmt.md"
    if [[ $DRY -eq 0 ]]; then
      { cat "$SRC/AGENTS.md"; printf '\n'; cat "$extra"; } > "$combined.tmp" && mv "$combined.tmp" "$combined"
    fi
    if [[ "$instr" == /* ]]; then link "$combined" "$instr"; else link "$combined" "$home/$instr"; fi
    continue
  fi
  if [[ "$instr" == /* ]]; then
    link "$ROOT/$(basename "$instr")" "$instr"
  else
    link "$ROOT/$instr" "$home/$instr"
  fi
done

if [[ -d "$HOME/.agents" ]]; then
  step "Linking shared Agent Skills directory ($HOME/.agents)"
  link "$ROOT/skills"    "$HOME/.agents/skills"
  link "$ROOT/AGENTS.md" "$HOME/.agents/AGENTS.md"
fi

say ""
if [[ $found -eq 0 ]]; then
  say "No harness detected. Canonical root is ready at $ROOT;"
  say "point your agent's skills dir at $ROOT/skills when you install one."
else
  say "${c_grn}Done.${c_off} Linked into $found harness(es). Re-run after 'git pull' to pick up updates."
fi
if [[ $DRY -eq 1 ]]; then say "${c_dim}(dry run — nothing changed)${c_off}"; fi


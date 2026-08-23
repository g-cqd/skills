#!/usr/bin/env bash
# Discovers available skills across all known AI tool directories.
# Outputs a YAML-like catalog of skill name, description, and source path.
# Usage: bash scripts/discover-skills.sh [optional-project-root]

set -euo pipefail

PROJECT_ROOT="${1:-.}"

# All known skill directories across AI tools and scopes
SKILL_DIRS=(
  # Claude Code — user-level
  "$HOME/.claude/skills"
  # Claude Code — project-level
  "$PROJECT_ROOT/.claude/skills"
  # Codex
  "$HOME/.codex/skills"
  "$PROJECT_ROOT/.codex/skills"
  # Copilot
  "$HOME/.copilot/skills"
  "$PROJECT_ROOT/.copilot/skills"
  # OpenCode
  "$HOME/.opencode/skills"
  "$PROJECT_ROOT/.opencode/skills"
  # Agents (generic)
  "$HOME/.agents/skills"
  "$PROJECT_ROOT/.agents/skills"
  # Additional Claude locations
  "$HOME/.claude/commands"
  "$PROJECT_ROOT/.claude/commands"
)

echo "# Skill Discovery Report"
echo "# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "# Project root: $(cd "$PROJECT_ROOT" 2>/dev/null && pwd || echo "$PROJECT_ROOT")"
echo "---"
echo "skills:"

# Use a temp file to count across subshells
count_file="$(mktemp)"
echo "0" > "$count_file"

for dir in "${SKILL_DIRS[@]}"; do
  # Resolve to absolute path, skip if doesn't exist
  resolved="$(cd "$dir" 2>/dev/null && pwd || true)"
  [ -z "$resolved" ] && continue
  [ ! -d "$resolved" ] && continue

  # Determine source label
  case "$dir" in
    */.claude/skills*)   source_tool="claude" ;;
    */.claude/commands*) source_tool="claude-commands" ;;
    */.codex/skills*)    source_tool="codex" ;;
    */.copilot/skills*)  source_tool="copilot" ;;
    */.opencode/skills*) source_tool="opencode" ;;
    */.agents/skills*)   source_tool="agents" ;;
    *)                   source_tool="unknown" ;;
  esac

  # Determine scope (user vs project)
  case "$dir" in
    "$HOME"/*) scope="user" ;;
    *)         scope="project" ;;
  esac

  # Find all SKILL.md files (the standard) and also .md files in commands dirs
  if [[ "$dir" == *"/commands"* ]]; then
    while IFS= read -r skill_file; do
      skill_name="$(basename "$skill_file" .md)"
      desc="$(head -20 "$skill_file" 2>/dev/null | grep -v '^#' | grep -v '^---' | grep -v '^$' | head -1 | sed 's/^[[:space:]]*//' | cut -c1-200)"
      [ -z "$desc" ] && desc="(no description)"
      echo "  - name: \"$skill_name\""
      echo "    source: \"$source_tool\""
      echo "    scope: \"$scope\""
      echo "    path: \"$skill_file\""
      echo "    description: \"$desc\""
      echo "$(( $(cat "$count_file") + 1 ))" > "$count_file"
    done < <(find "$resolved" -maxdepth 2 -name "*.md" -type f 2>/dev/null)
  else
    while IFS= read -r skill_file; do
      skill_dir="$(dirname "$skill_file")"
      skill_name="$(basename "$skill_dir")"

      # Extract name and description from YAML frontmatter
      yaml_name="$(sed -n '/^---$/,/^---$/{ /^name:/s/^name:[[:space:]]*//p; }' "$skill_file" 2>/dev/null | head -1)"
      yaml_desc="$(sed -n '/^---$/,/^---$/{ /^description:/s/^description:[[:space:]]*//p; }' "$skill_file" 2>/dev/null | head -1 | cut -c1-200)"

      [ -n "$yaml_name" ] && skill_name="$yaml_name"
      [ -z "$yaml_desc" ] && yaml_desc="(no description)"

      # Check for sub-resources
      has_refs="false"
      has_scripts="false"
      [ -d "$skill_dir/references" ] && has_refs="true"
      [ -d "$skill_dir/resources" ] && has_refs="true"
      [ -d "$skill_dir/scripts" ] && has_scripts="true"

      echo "  - name: \"$skill_name\""
      echo "    source: \"$source_tool\""
      echo "    scope: \"$scope\""
      echo "    path: \"$skill_file\""
      echo "    has_references: $has_refs"
      echo "    has_scripts: $has_scripts"
      echo "    description: \"$yaml_desc\""
      echo "$(( $(cat "$count_file") + 1 ))" > "$count_file"
    done < <(find "$resolved" -maxdepth 2 -name "SKILL.md" -type f 2>/dev/null)
  fi
done

total="$(cat "$count_file")"
rm -f "$count_file"
echo "total_found: $total"

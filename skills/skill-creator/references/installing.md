# Installing Skills

## From GitHub

### Using installer scripts (Codex)

```bash
# List available curated skills
scripts/list-skills.py

# List experimental skills
scripts/list-skills.py --path skills/.experimental

# Install from curated list
scripts/install-skill-from-github.py --repo openai/skills --path skills/.curated/<skill-name>

# Install from any GitHub repo
scripts/install-skill-from-github.py --repo <owner>/<repo> --path <path/to/skill>

# Install via URL
scripts/install-skill-from-github.py --url https://github.com/<owner>/<repo>/tree/<ref>/<path>

# Install multiple skills at once
scripts/install-skill-from-github.py --repo <owner>/<repo> --path <path1> <path2>
```

**Options**: `--ref <branch>` (default: main), `--dest <path>`, `--method auto|download|git`

### Manual Installation

```bash
# Clone the skill
git clone https://github.com/owner/repo /tmp/skill-source

# Copy to skills directory
cp -r /tmp/skill-source/path/to/skill ~/.agent-harness/skills/skill-name  # or your harness's skills dir
```

### For Claude Code
Place in `~/.claude/skills/<name>/SKILL.md` (personal) or `.claude/skills/<name>/SKILL.md` (project).

### For Codex
Place in `~/.codex/skills/<name>/SKILL.md`. Installs into `$CODEX_HOME/skills/`.

## Distribution

### Current Distribution Model

**Individual users:**
1. Download the skill folder
2. Zip the folder (if needed)
3. Upload via your agent platform's skills settings
4. Or place in your agent's skills directory (see install.sh)

**Organization-level:**
- Admins can deploy skills workspace-wide
- Automatic updates
- Centralized management

### Via API
- `/v1/skills` endpoint for listing and managing
- `container.skills` parameter in Messages API
- Works with agent SDKs that support the Agent Skills standard

### Recommended Approach for Sharing
1. Host on GitHub with public repo
2. Clear README (separate from SKILL.md) with installation instructions
3. Example usage and screenshots
4. Link to MCP documentation if applicable

### Positioning Your Skill
Focus on outcomes, not features:
```
# Good
"The ProjectHub skill enables teams to set up complete project workspaces
in seconds — including pages, databases, and templates — instead of
spending 30 minutes on manual setup."

# Bad
"The ProjectHub skill is a folder containing YAML frontmatter and
Markdown instructions that calls our MCP server tools."
```

## Notes

- Private GitHub repos can be accessed via git credentials or `GITHUB_TOKEN`/`GH_TOKEN`
- Git fallback tries HTTPS first, then SSH
- Aborts if destination skill directory already exists
- After installing, restart the agent to pick up new skills

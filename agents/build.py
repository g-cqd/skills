#!/usr/bin/env python3
"""Render the neutral agent sources in src/ into per-harness variants.

One source of truth, src/<name>.md (frontmatter and a prompt body), becomes six outputs, because each harness reads
a different format and tunes a different set of fields:

  claude/<name>.md          Markdown + YAML: model, effort, tools, maxTurns, skills, color, background, hooks
  copilot/<name>.agent.md   Markdown + YAML: model (a display name), reasoningEffort, tools (aliases)
  codex/<name>.toml         TOML: model, model_reasoning_effort, sandbox_mode, developer_instructions
  vibe/<name>.toml          TOML: display_name, description, agent_type, safety, enabled_tools/disabled_tools, instructions
  opencode/<name>.md        Markdown + YAML: description, mode, steps, permission map
  agy/<name>/agent.md       Markdown + YAML: name, description, subagent, tools, inheritCustomizations, inheritMcp

Frontmatter of src/<name>.md; the first four are required:

  name          the agent's name, and its file name in every harness
  description   what it does and when to use it, as a folded `>` block
  tier          a key of tiers.json, which gives each harness's model and effort
  tools         the capabilities it gets, comma-separated, from CAPABILITIES below; or `all`
  deny          with `tools: all`, the capabilities it does not get
  effort        replaces the tier's effort on every harness
  max_turns     a turn budget: Claude's maxTurns, OpenCode's steps, and a Budget section in the prompt on every harness
  skills        skills Claude loads into the agent's context at start, comma-separated
  spawns        the agents it may start, comma-separated; needs the `agents` capability
  color         the agent's color in Claude's transcript
  background    true to keep the agent in the background on Claude

The tier -> model mapping in tiers.json is the cost dial.

Run:  python3 build.py            write claude/, copilot/, codex/, vibe/, opencode/, and agy/
      python3 build.py --check    change nothing; exit 1 when a generated file is missing, stale, or extra
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "src"
SKILLS = HERE.parent / "skills"
TIERS = json.loads((HERE / "tiers.json").read_text())

# Capability -> (Claude Code tools, Copilot tool aliases). Codex has no per-agent tool list: its agents inherit the
# parent's tools and sandbox, so a capability there shows only in the sandbox_mode hint and the prompt.
CAPABILITIES = {
    "read": (["Read"], ["read"]),
    "search": (["Grep", "Glob"], ["search"]),
    "lsp": (["LSP"], []),
    "shell": (["Bash"], ["execute"]),
    # Claude runs the guard below before every command; Copilot has no per-agent hook, so it gets no shell.
    "shell-readonly": (["Bash"], []),
    "edit": (["Edit", "Write"], ["edit"]),
    "web": (["WebFetch", "WebSearch"], ["web"]),
    "todo": (["TodoWrite"], ["todo"]),
    # Claude's Agent tool is rendered from `spawns`, as Agent(name, ...).
    "agents": ([], ["agent"]),
    "skills": (["Skill"], ["skill"]),
    "apple-docs": (["mcp__apple-docs"], ["apple-docs/*"]),
}

VIBE_TOOLS = {
    "read": ["read_file"],
    "search": ["grep"],
    "lsp": [],
    "shell": ["bash"],
    "shell-readonly": ["bash"],
    "edit": ["edit", "write_file"],
    "web": ["web_fetch", "web_search"],
    "todo": ["todo"],
    "agents": ["task"],
    "skills": ["skill"],
    "apple-docs": ["mcp_apple_docs_*"],
}

OPENCODE_PERMISSIONS = {
    "read": ["read"],
    "search": ["grep", "glob"],
    "lsp": ["lsp"],
    "shell": ["bash"],
    # OpenCode has no per-agent read-only shell hook, so read-only shell agents do not get bash permission.
    "shell-readonly": [],
    "edit": ["edit"],
    "web": ["webfetch", "websearch"],
    "todo": ["todowrite"],
    "agents": ["task"],
    "skills": ["skill"],
    "apple-docs": ["apple-docs_*"],
}

AGY_TOOLS = {
    "read": ["view_file", "view_file_outline", "view_code_item"],
    "search": ["grep_search", "find_by_name"],
    "lsp": [],
    "shell": ["run_command", "manage_task"],
    "shell-readonly": ["run_command", "manage_task"],
    "edit": ["replace_file_content", "multi_replace_file_content", "write_to_file"],
    "web": ["read_url_content", "search_web"],
    "todo": [],
    "agents": ["invoke_subagent", "manage_subagents", "define_subagent"],
    "skills": [],
    "apple-docs": ["call_mcp_tool", "list_resources", "read_resource"],
}

# Refuses every Bash command that could change state, for an agent whose shell is read-only.
READONLY_HOOK = (
    "hooks:\n"
    "  PreToolUse:\n"
    '    - matcher: "Bash"\n'
    "      hooks:\n"
    "        - type: command\n"
    "          command: 'python3 \"$HOME/.claude/agents/hooks/readonly-bash.py\" || exit 2'"
)

CODEX_READONLY_NOTE = (
    "Codex runs you in your parent's sandbox, so nothing but you enforces this role's read-only rule: never edit a "
    "file, and run only commands that read.\n\n"
)

UNHOOKED_SHELL_READONLY_NOTE = (
    "Your shell tool is unguarded on this harness, so you must enforce this role's read-only rule yourself: never "
    "edit, write, or delete a file, and run only commands that read.\n\n"
)

COLORS = {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
LIST_KEYS = {"tools", "deny", "skills", "spawns"}
# Claude Code tools a denied capability also removes, beyond the ones CAPABILITIES lists.
CLAUDE_DENY_EXTRA = {"edit": ["NotebookEdit"]}


def parse(path):
    """Return (meta dict, body str) from a src markdown file. List keys come back as lists."""
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError(f"{path.name}: no frontmatter")
    fm, body = m.group(1), m.group(2).lstrip("\n")
    meta = {}
    # Minimal YAML: `key: value` and `key: >` folded blocks (description).
    lines = fm.split("\n")
    i = 0
    while i < len(lines):
        km = re.match(r"^([a-z_]+):\s*(.*)$", lines[i])
        if not km:
            i += 1
            continue
        key, val = km.group(1), km.group(2)
        if val.strip() == ">":
            i += 1
            buf = []
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                buf.append(lines[i].strip())
                i += 1
            meta[key] = " ".join(w for w in buf if w).strip()
            continue
        meta[key] = val.strip()
        i += 1
    for key in LIST_KEYS & meta.keys():
        meta[key] = [item.strip() for item in meta[key].split(",") if item.strip()]
    return meta, body


def validate(meta, source, names):
    """Raise ValueError naming `source` when `meta` is incomplete or names something that does not exist."""
    for key in ("name", "tier", "tools", "description"):
        if key not in meta:
            raise ValueError(f"{source}: missing '{key}'")
    if meta["tier"] not in TIERS or meta["tier"].startswith("_"):
        raise ValueError(f"{source}: unknown tier {meta['tier']!r}")
    if meta["tools"] == ["all"]:
        unknown = [tool for tool in meta.get("deny", []) if tool not in CAPABILITIES]
    elif "all" in meta["tools"] or "deny" in meta:
        raise ValueError(f"{source}: 'all' stands alone in tools, and 'deny' needs it")
    else:
        unknown = [tool for tool in meta["tools"] if tool not in CAPABILITIES]
    if unknown:
        raise ValueError(f"{source}: unknown capabilities {unknown}")
    if "shell" in meta["tools"] and "shell-readonly" in meta["tools"]:
        raise ValueError(f"{source}: 'shell' and 'shell-readonly' exclude each other")
    if meta.get("spawns") and "agents" not in meta["tools"]:
        raise ValueError(f"{source}: 'spawns' needs the 'agents' capability")
    strangers = [name for name in meta.get("spawns", []) if name not in names]
    if strangers:
        raise ValueError(f"{source}: spawns unknown agents {strangers}")
    missing = [skill for skill in meta.get("skills", []) if not (SKILLS / skill / "SKILL.md").is_file()]
    if missing:
        raise ValueError(f"{source}: preloads unknown skills {missing}")
    if "effort" in meta and meta["effort"] not in EFFORTS:
        raise ValueError(f"{source}: unknown effort {meta['effort']!r}")
    if "color" in meta and meta["color"] not in COLORS:
        raise ValueError(f"{source}: unknown color {meta['color']!r}")
    if "max_turns" in meta and not (meta["max_turns"].isdigit() and int(meta["max_turns"]) > 0):
        raise ValueError(f"{source}: max_turns must be a positive integer")
    if meta.get("background", "false") not in ("true", "false"):
        raise ValueError(f"{source}: background must be true or false")


def capabilities(meta):
    """The capabilities the agent gets, with `all` expanded and its denials removed."""
    if meta["tools"] == ["all"]:
        return [cap for cap in CAPABILITIES if cap not in meta.get("deny", []) and cap != "shell-readonly"]
    return meta["tools"]


def is_readonly(meta):
    """Whether the agent may not change anything: no edit, and a shell only when guarded."""
    granted = capabilities(meta)
    return "edit" not in granted and "shell" not in granted


def models_and_effort(meta, harness):
    """The harness's ordered model fallback list and effort for this agent."""
    tier = TIERS[meta["tier"]][harness]
    models = tier["models"] if "models" in tier else [tier["model"]]
    return models, meta.get("effort", tier["effort"])


def model_and_effort(meta, harness):
    """The harness's primary model and effort for this agent."""
    models, effort = models_and_effort(meta, harness)
    return models[0], effort


def prompt(meta, body):
    """The body every harness gets, with the Budget section when the agent has a turn budget."""
    body = body.rstrip() + "\n"
    if "max_turns" in meta:
        body += (
            "\n## Budget\n\n"
            f"Finish within {meta['max_turns']} turns. If the work needs more, stop, and report what is done and what "
            "remains; the caller can resume you or hand the rest to a larger agent.\n"
        )
    return body


def yaml_desc(desc):
    """Emit a description as a folded YAML block so long lines stay readable."""
    words, lines, cur = desc.split(), [], "  "
    for w in words:
        if len(cur) + len(w) + 1 > 96:
            lines.append(cur.rstrip())
            cur = "  "
        cur += w + " "
    lines.append(cur.rstrip())
    return "description: >\n" + "\n".join(lines)


def yaml_str(s):
    """A double-quoted YAML scalar."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def toml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def toml_block(text):
    """A multi-line TOML string holding `text` verbatim: literal, so a backslash in the prompt stays a backslash."""
    if "'''" not in text:
        return "'''\n" + text + "'''"
    escaped = text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return '"""\n' + escaped + '"""'


def claude_tools(meta):
    """Claude Code's tool list, in CAPABILITIES order; Agent carries the spawn allowlist. None for `all`, which
    inherits every tool the session has, MCP and messaging tools included."""
    if meta["tools"] == ["all"]:
        return None
    tools = []
    for capability, (claude, _) in CAPABILITIES.items():
        if capability not in meta["tools"]:
            continue
        if capability == "agents":
            spawns = meta.get("spawns", [])
            tools.append(f"Agent({', '.join(spawns)})" if spawns else "Agent")
        tools.extend(claude)
    return tools


def copilot_tools(meta):
    """Copilot's tool aliases, in CAPABILITIES order, without duplicates."""
    granted = capabilities(meta)
    tools = []
    for capability, (_, copilot) in CAPABILITIES.items():
        if capability in granted:
            tools.extend(alias for alias in copilot if alias not in tools)
    return tools


def vibe_tools(meta):
    """Mistral Vibe's enabled_tools list, in CAPABILITIES order, without duplicates."""
    granted = capabilities(meta)
    tools = []
    for capability, names in VIBE_TOOLS.items():
        if capability in granted or capability == "skills":
            tools.extend(name for name in names if name not in tools)
    return tools


def agy_tools(meta):
    """Google Antigravity's tool allowlist, always starting with send_message."""
    granted = capabilities(meta)
    tools = ["send_message"]
    for capability, names in AGY_TOOLS.items():
        if capability in granted:
            tools.extend(name for name in names if name not in tools)
    if meta["tools"] == ["all"]:
        for name in ("call_mcp_tool", "list_resources", "read_resource"):
            if name not in tools:
                tools.append(name)
    return tools


def render_claude(meta, body):
    models, effort = models_and_effort(meta, "claude")
    fm = [f"name: {meta['name']}", yaml_desc(meta["description"]), f"model: {models[0]}"]
    if len(models) > 1:
        fm.append(f"# fallback_models: {', '.join(models[1:])}")
    fm.append(f"effort: {effort}")
    tools = claude_tools(meta)
    if tools is not None:
        fm.append(f"tools: {', '.join(tools)}")
    denied = [tool for cap in meta.get("deny", []) for tool in CAPABILITIES[cap][0] + CLAUDE_DENY_EXTRA.get(cap, [])]
    if denied:
        fm.append(f"disallowedTools: {', '.join(denied)}")
    if "max_turns" in meta:
        fm.append(f"maxTurns: {meta['max_turns']}")
    if meta.get("skills"):
        fm.append("skills:\n" + "\n".join(f"  - {skill}" for skill in meta["skills"]))
    if "color" in meta:
        fm.append(f"color: {meta['color']}")
    if meta.get("background") == "true":
        fm.append("background: true")
    if "shell-readonly" in capabilities(meta):
        fm.append(READONLY_HOOK)
    return "---\n" + "\n".join(fm) + "\n---\n\n" + prompt(meta, body)


def render_copilot(meta, body):
    models, effort = models_and_effort(meta, "copilot")
    model_val = (
        yaml_str(models[0]) if len(models) == 1 else "[" + ", ".join(yaml_str(m) for m in models) + "]"
    )
    fm = [f"name: {meta['name']}", yaml_desc(meta["description"]), f"model: {model_val}"]
    fm.append(f"reasoningEffort: {effort}")
    fm.append("tools: [" + ", ".join(yaml_str(tool) for tool in copilot_tools(meta)) + "]")
    return "---\n" + "\n".join(fm) + "\n---\n\n" + prompt(meta, body)


def render_codex(meta, body):
    models, effort = models_and_effort(meta, "codex")
    readonly = is_readonly(meta)
    instructions = (CODEX_READONLY_NOTE if readonly else "") + prompt(meta, body)
    out = [
        f"name = {toml_str(meta['name'])}",
        f"description = {toml_str(meta['description'])}",
        f"model = {toml_str(models[0])}",
    ]
    if len(models) > 1:
        out.append("# fallback_models = [" + ", ".join(toml_str(m) for m in models[1:]) + "]")
    out.extend(
        [
            f"model_reasoning_effort = {toml_str(effort)}",
            "# Codex 0.149 and later ignore sandbox_mode here and run the agent in the parent's sandbox.",
            f"sandbox_mode = {toml_str('read-only' if readonly else 'workspace-write')}",
            f"developer_instructions = {toml_block(instructions)}",
        ]
    )
    return "\n".join(out) + "\n"


def render_vibe(meta, body):
    models, effort = models_and_effort(meta, "vibe")
    readonly = is_readonly(meta)
    has_readonly_shell = "shell-readonly" in capabilities(meta)
    instructions = (UNHOOKED_SHELL_READONLY_NOTE if has_readonly_shell else "") + prompt(meta, body)
    display_name = meta["name"].replace("-", " ").title()
    out = [
        "# Generated from agents/src/" + meta["name"] + ".md by agents/build.py — do not edit.",
        "# tier_models = [" + ", ".join(toml_str(m) for m in models) + f"] (effort = {toml_str(effort)})",
        f"display_name = {toml_str(display_name)}",
        f"description = {toml_str(meta['description'])}",
        'agent_type = "subagent"',
        f"safety = {toml_str('safe' if readonly else 'neutral')}",
    ]
    if meta["tools"] == ["all"]:
        denied = []
        for cap in meta.get("deny", []):
            denied.extend(name for name in VIBE_TOOLS[cap] if name not in denied)
        if denied:
            out.append("disabled_tools = [" + ", ".join(toml_str(t) for t in denied) + "]")
    else:
        out.append("enabled_tools = [" + ", ".join(toml_str(t) for t in vibe_tools(meta)) + "]")
    out.append(f"instructions = {toml_block(instructions)}")
    return "\n".join(out) + "\n"


def render_opencode(meta, body):
    models, effort = models_and_effort(meta, "opencode")
    fm = [
        yaml_desc(meta["description"]),
        "mode: subagent",
        f"# tier_models: [{', '.join(models)}] (effort: {effort})",
    ]
    if "max_turns" in meta:
        fm.append(f"steps: {meta['max_turns']}")
    if meta["tools"] == ["all"]:
        perms = ['  "*": allow']
        seen = set()
        for cap in meta.get("deny", []):
            for perm in OPENCODE_PERMISSIONS[cap]:
                if perm not in seen:
                    seen.add(perm)
                    perms.append(f"  {perm}: deny")
    else:
        perms = ['  "*": deny']
        seen = set()
        for cap in capabilities(meta):
            for perm in OPENCODE_PERMISSIONS[cap]:
                if perm not in seen:
                    seen.add(perm)
                    perms.append(f"  {perm}: allow")
        if "skill" not in seen:
            perms.append("  skill: allow")
    fm.append("permission:\n" + "\n".join(perms))
    return "---\n" + "\n".join(fm) + "\n---\n\n" + prompt(meta, body)


def render_agy(meta, body):
    models, effort = models_and_effort(meta, "agy")
    has_readonly_shell = "shell-readonly" in capabilities(meta)
    instructions = (UNHOOKED_SHELL_READONLY_NOTE if has_readonly_shell else "") + prompt(meta, body)
    tools_yaml = "\n".join(f"  - {tool}" for tool in agy_tools(meta))
    fm = [
        f"name: {meta['name']}",
        yaml_desc(meta["description"]),
        "subagent: true",
        f"# tier_models: [{', '.join(models)}] (effort: {effort})",
        "tools:\n" + tools_yaml,
        "inheritCustomizations: false",
        "inheritMcp: true",
    ]
    return "---\n" + "\n".join(fm) + "\n---\n\n" + instructions


TARGETS = {
    "claude": ("{name}.md", "*.md", render_claude),
    "copilot": ("{name}.agent.md", "*.agent.md", render_copilot),
    "codex": ("{name}.toml", "*.toml", render_codex),
    "vibe": ("{name}.toml", "*.toml", render_vibe),
    "opencode": ("{name}.md", "*.md", render_opencode),
    "agy": ("{name}/agent.md", "*/agent.md", render_agy),
}


def render_all():
    """Every generated file, as {relative path: text}, from src/; raises ValueError on an invalid source."""
    sources = sorted(SRC.glob("*.md"))
    parsed = [(path, *parse(path)) for path in sources]
    names = {meta.get("name") for _, meta, _ in parsed}
    files = {}
    for path, meta, body in parsed:
        validate(meta, path.name, names)
        if meta["name"] != path.stem:
            raise ValueError(f"{path.name}: name {meta['name']!r} differs from the file name")
        for harness, (pattern, _, render) in TARGETS.items():
            files[f"{harness}/{pattern.format(name=meta['name'])}"] = render(meta, body)
    return parsed, files


def existing_files(root=HERE):
    """The generated files under `root`, as {relative path: text}; hand-written files in subfolders are not among
    them."""
    found = {}
    for harness, (_, glob_pat, _) in TARGETS.items():
        base = root / harness
        if not base.is_dir():
            continue
        for path in base.glob(glob_pat):
            rel = path.relative_to(root).as_posix()
            found[rel] = path.read_text()
    return found


def check(files, root=HERE):
    """Differences between `files` and what is under `root`, as human-readable lines; empty when current."""
    on_disk = existing_files(root)
    problems = [f"missing  {name}" for name in sorted(files.keys() - on_disk.keys())]
    problems += [f"stale    {name}" for name in sorted(files.keys() & on_disk.keys()) if files[name] != on_disk[name]]
    problems += [f"extra    {name}" for name in sorted(on_disk.keys() - files.keys())]
    return problems


def main(argv):
    try:
        parsed, files = render_all()
    except ValueError as error:
        print(f"build.py: {error}", file=sys.stderr)
        return 2
    if "--check" in argv:
        problems = check(files)
        for line in problems:
            print(line)
        print("generated files are current" if not problems else "run python3 build.py to regenerate")
        return 1 if problems else 0
    for harness, (_, glob_pat, _) in TARGETS.items():
        directory = HERE / harness
        directory.mkdir(exist_ok=True)
        for old in directory.glob(glob_pat):
            old.unlink()
            if old.parent != directory and not any(old.parent.iterdir()):
                old.parent.rmdir()
    for name, text in files.items():
        target = HERE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    for _, meta, _ in parsed:
        print(f"  {meta['name']:18s} tier={meta['tier']:9s} tools={','.join(capabilities(meta))}")
    print(f"\n{len(parsed)} agents -> " + " ".join(f"{h}/" for h in TARGETS))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


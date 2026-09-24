#!/usr/bin/env python3
"""Render the neutral agent sources in src/ into per-harness variants.

One source of truth (src/<name>.md, frontmatter: name, tier, tools, description +
body) -> three outputs, because each harness reads a different format:

  claude/<name>.md          Markdown + YAML frontmatter (model: opus|fable|sonnet|haiku or a full id, tools CSV)
  copilot/<name>.agent.md   Markdown + YAML frontmatter (model: <display name>, tools: [array])
  codex/<name>.toml         TOML (model, model_reasoning_effort, sandbox_mode, developer_instructions)

The tier -> model mapping lives in tiers.json (the cost dial). Tools map from a
neutral capability (readonly | edit | full) to each harness's tool vocabulary.

Run:  python3 build.py        (from the agents/ dir, or anywhere — paths are resolved)
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "src"
TIERS = json.loads((HERE / "tiers.json").read_text())

# neutral capability -> per-harness tool expression
TOOLCAP = {
    "readonly": {
        "claude": "Read, Grep, Glob",
        "copilot": ["readfile", "code_search", "find_references"],
        "codex_sandbox": "read-only",
    },
    "edit": {
        "claude": "Read, Write, Edit, Grep, Glob, Bash",
        "copilot": ["readfile", "code_search", "edit", "shell"],
        "codex_sandbox": "workspace-write",
    },
    "full": {  # omit the allowlist -> inherit all tools
        "claude": None,
        "copilot": None,
        "codex_sandbox": "workspace-write",
    },
}


def parse(path):
    """Return (meta dict, body str) from a src markdown file."""
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError(f"{path.name}: no frontmatter")
    fm, body = m.group(1), m.group(2).lstrip("\n")
    meta = {}
    # minimal YAML: `key: value` and `key: >` folded blocks (description)
    lines = fm.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        km = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if not km:
            i += 1
            continue
        key, val = km.group(1), km.group(2)
        if val.strip() == ">":  # folded block: gather indented continuation
            i += 1
            buf = []
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                buf.append(lines[i].strip())
                i += 1
            meta[key] = " ".join(w for w in buf if w).strip()
            continue
        meta[key] = val.strip()
        i += 1
    return meta, body


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


def toml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_claude(meta, body):
    tier = TIERS[meta["tier"]]
    tools = TOOLCAP[meta["tools"]]["claude"]
    fm = [f'name: {meta["name"]}', yaml_desc(meta["description"]), f'model: {tier["claude"]}']
    if tools:
        fm.append(f"tools: {tools}")
    if meta["tier"] != "standard":
        fm.append(f'effort: {tier["effort"]}')
    return "---\n" + "\n".join(fm) + "\n---\n\n" + body


def render_copilot(meta, body):
    tier = TIERS[meta["tier"]]
    tools = TOOLCAP[meta["tools"]]["copilot"]
    fm = [f'name: {meta["name"]}', yaml_desc(meta["description"]), f'model: {tier["copilot"]}']
    if tools:
        fm.append("tools: [" + ", ".join(f'"{t}"' for t in tools) + "]")
    return "---\n" + "\n".join(fm) + "\n---\n\n" + body


def render_codex(meta, body):
    tier = TIERS[meta["tier"]]
    sandbox = TOOLCAP[meta["tools"]]["codex_sandbox"]
    out = [
        f'name = {toml_str(meta["name"])}',
        f'description = {toml_str(meta["description"])}',
        f'model = {toml_str(tier["codex"])}',
        f'model_reasoning_effort = {toml_str(tier["effort"])}',
        f'sandbox_mode = {toml_str(sandbox)}',
        'developer_instructions = """',
        body.rstrip(),
        '"""',
    ]
    return "\n".join(out) + "\n"


def main():
    srcs = sorted(SRC.glob("*.md"))
    if not srcs:
        print("no sources in src/")
        return
    targets = {
        "claude": (".md", render_claude),
        "copilot": (".agent.md", render_copilot),
        "codex": (".toml", render_codex),
    }
    for harness, (ext, _fn) in targets.items():
        d = HERE / harness
        d.mkdir(exist_ok=True)
        # clear stale generated files
        for old in d.glob(f"*{ext}"):
            old.unlink()
    count = 0
    for path in srcs:
        meta, body = parse(path)
        for req in ("name", "tier", "tools", "description"):
            if req not in meta:
                raise ValueError(f"{path.name}: missing '{req}'")
        if meta["tier"] not in TIERS or meta["tier"].startswith("_"):
            raise ValueError(f"{path.name}: unknown tier {meta['tier']!r}")
        for harness, (ext, fn) in targets.items():
            (HERE / harness / f"{meta['name']}{ext}").write_text(fn(meta, body))
        count += 1
        print(f"  {meta['name']:18s} tier={meta['tier']:9s} tools={meta['tools']}")
    print(f"\n{count} agents -> claude/ copilot/ codex/")


if __name__ == "__main__":
    main()

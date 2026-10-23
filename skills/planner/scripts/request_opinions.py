#!/usr/bin/env python3
"""Request second-opinion responses from peer AI CLIs.

The script detects the current CLI context and queries the other installed CLIs.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable

ALL_CLIS = ("claude", "codex", "vibe", "agy", "gemini")


@dataclass
class OpinionResult:
    cli: str
    ok: bool
    command: str
    stdout: str
    stderr: str
    error: str


def detect_current_cli() -> str | None:
    if os.getenv("CLAUDE_SESSION_ID"):
        return "claude"
    if os.getenv("ANTIGRAVITY_CLI_ALIAS"):
        return "agy"
    if os.getenv("VIBE_HOME"):
        return "vibe"
    if os.getenv("GEMINI_SESSION_ID"):
        return "gemini"
    if os.getenv("CODEX_HOME"):
        return "codex"

    for pid in (os.getpid(), os.getppid()):
        try:
            proc = subprocess.run(
                ["ps", "-o", "command=", "-p", str(pid)],
                check=False,
                capture_output=True,
                text=True,
            )
            cmd = (proc.stdout or "").lower()
            for cli in ALL_CLIS:
                if cli in cmd:
                    return cli
        except Exception:
            continue

    return None


def wrap_prompt(prompt: str) -> str:
    return (
        "You are providing an independent second opinion on a software task. "
        "Focus on correctness, risks, alternatives, and missing validation. "
        "Keep it concise and actionable.\n\n"
        f"TASK CONTEXT:\n{prompt}\n\n"
        "Return:\n"
        "1) Critical risks\n"
        "2) Better alternatives\n"
        "3) Validation and tests to run\n"
    )


def command_variants(cli: str, prompt: str, args: argparse.Namespace) -> Iterable[list[str]]:
    if cli == "codex":
        yield ["codex", "exec", prompt]
    elif cli == "claude":
        # Prefer deterministic non-interactive flags first, then fall back.
        cmd = [
            "claude",
            "-p",
            "--output-format",
            "text",
            "--max-turns",
            str(args.claude_max_turns),
        ]
        if not args.claude_session_persistence:
            cmd.append("--no-session-persistence")
        if args.claude_tools:
            cmd.extend(["--tools", args.claude_tools])
        for add_dir in args.claude_add_dir:
            cmd.extend(["--add-dir", add_dir])
        yield cmd + [prompt]

        yield ["claude", "-p", prompt]
        yield ["claude", "--print", prompt]
    elif cli == "vibe":
        yield ["vibe", "-p", prompt, "--output", "text", "--max-turns", str(args.claude_max_turns)]
        yield ["vibe", "-p", prompt]
    elif cli == "agy":
        yield ["agy", "prompt", prompt]
    elif cli == "gemini":
        yield ["gemini", "-p", prompt]
        yield ["gemini", "--prompt", prompt]


def run_cli(cli: str, prompt: str, timeout_s: int, args: argparse.Namespace) -> OpinionResult:
    if shutil.which(cli) is None:
        return OpinionResult(cli, False, "", "", "", "CLI not installed")

    wrapped = wrap_prompt(prompt)
    last_err = "No working command variant"
    last_stderr = ""

    for cmd in command_variants(cli, wrapped, args):
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            if proc.returncode == 0 and (proc.stdout or "").strip():
                return OpinionResult(
                    cli=cli,
                    ok=True,
                    command=" ".join(cmd[:2]),
                    stdout=proc.stdout.strip(),
                    stderr=(proc.stderr or "").strip(),
                    error="",
                )

            last_err = f"Non-zero exit ({proc.returncode})"
            last_stderr = (proc.stderr or "").strip()
        except subprocess.TimeoutExpired:
            last_err = f"Timed out after {timeout_s}s"
        except Exception as exc:  # pragma: no cover
            last_err = f"Execution error: {exc}"

    return OpinionResult(cli, False, "", "", last_stderr, last_err)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Request peer opinions from AI CLIs")
    parser.add_argument("--prompt", required=True, help="Task prompt to review")
    parser.add_argument(
        "--current",
        choices=("auto",) + ALL_CLIS,
        default="auto",
        help="Current CLI; auto-detect by default",
    )
    parser.add_argument(
        "--include",
        default=",".join(ALL_CLIS),
        help="Comma-separated CLI list to consider (default: claude,codex,gemini)",
    )
    parser.add_argument("--timeout", type=int, default=180, help="Per-CLI timeout in seconds")
    parser.add_argument(
        "--claude-max-turns",
        type=int,
        default=4,
        help="Max turns for Claude print mode (default: 4)",
    )
    parser.add_argument(
        "--claude-tools",
        default="Read,Grep,Glob",
        help="Tool whitelist for Claude deterministic print mode (default: Read,Grep,Glob)",
    )
    parser.add_argument(
        "--claude-add-dir",
        action="append",
        default=[],
        help="Additional directory to allow Claude to read (repeatable)",
    )
    parser.add_argument(
        "--claude-session-persistence",
        action="store_true",
        help="Keep Claude session persistence (default is disabled for print mode stability)",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format",
    )
    return parser.parse_args()


def render_markdown(current: str | None, results: list[OpinionResult]) -> str:
    lines = ["# Cross CLI Opinions", ""]
    lines.append(f"Current CLI: {current or 'unknown'}")
    lines.append("")

    for res in results:
        lines.append(f"## {res.cli}")
        if res.ok:
            lines.append("")
            lines.append(res.stdout)
            lines.append("")
        else:
            lines.append("")
            lines.append(f"Status: unavailable ({res.error})")
            if res.stderr:
                lines.append("")
                lines.append("stderr:")
                lines.append(f"{res.stderr}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    included = {item.strip() for item in args.include.split(",") if item.strip()}
    invalid = included.difference(ALL_CLIS)
    if invalid:
        print(f"Invalid --include values: {', '.join(sorted(invalid))}", file=sys.stderr)
        return 2

    current = detect_current_cli() if args.current == "auto" else args.current
    peers = [cli for cli in ALL_CLIS if cli in included and cli != current]

    if not peers:
        print("No peer CLI selected after filtering current runtime", file=sys.stderr)
        return 2

    results = [run_cli(cli, args.prompt, args.timeout, args) for cli in peers]

    if args.format == "json":
        payload = {
            "current": current,
            "results": [
                {
                    "cli": r.cli,
                    "ok": r.ok,
                    "command": r.command,
                    "stdout": r.stdout,
                    "stderr": r.stderr,
                    "error": r.error,
                }
                for r in results
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        print(render_markdown(current, results), end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

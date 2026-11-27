# Security

## Report a problem

Open a private security advisory on GitHub (the repository's Security tab, "Report a vulnerability"). If that is not
available, open an issue that says you have a security report, without the details, and wait for a reply. Expect an
answer within 7 days.

## What is in scope

This repository holds instructions for agents. The risks that matter:

| Area | Risk |
|---|---|
| `install.sh` | It writes symlinks into your home directory. It must replace only its own links and back up any real file it would replace. |
| `agents/claude/hooks/readonly-bash.py` | The guard that keeps read-only agents from changing files. A command that passes the guard and writes is a bug. It is a guardrail against mistakes, not a sandbox against a hostile repository. |
| `install.sh` and third-party skills | It fetches a pinned submodule (REA's skill) and runs Xcode's own skill export. A skill is text that an agent reads, so a changed pin changes what your agents do: review a pointer change like a code change. |
| Skills and agent text | A sentence that makes an agent run a destructive or outward-facing action without asking is a bug. |

Out of scope: another local user of the same machine who can already read your home directory, and a harness that
ignores its own sandbox settings (Codex runs every subagent in its parent's sandbox).

## Supported versions

Only the latest commit on `main` is supported.

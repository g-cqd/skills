"""Tests for claude/hooks/readonly-bash.py: each case runs the hook as Claude Code does, with the tool call as JSON on
stdin, and checks the exit status (0 allows, 2 blocks) and the refusal on stderr.
Run from the repository root: python3 -m unittest discover -s agents/tests"""

import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "claude", "hooks",
                      "readonly-bash.py")
PREFIX = "read-only agent:"
ADVICE = "hand the change back to your caller instead"


def run_hook(stdin):
    """Runs the hook with `stdin`; returns (exit status, stderr)."""
    result = subprocess.run(
        [sys.executable, SCRIPT], input=stdin, capture_output=True, text=True, timeout=30)
    return result.returncode, result.stderr


def run_bash(command):
    """Runs the hook on a Bash call with `command`."""
    return run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))


ALLOWED = [
    "git log --oneline -5",
    "git -C ../x diff main...HEAD -- a.swift",
    "git branch -a",
    "git branch --show-current",
    "git tag -l 'v*'",
    "git config --get user.name",
    "git stash list",
    "git worktree list",
    'rg -n "foo" Sources | head -20',
    "grep -rn TODO . 2>/dev/null",
    "find . -name '*.swift' -not -path './.build/*'",
    "find . -name '*.swift' | xargs grep -l Parser",
    "sed -n '1,40p' file",
    "sed -n '5p;9p' f",
    "cat a b | sort | uniq -c",
    "ls -la && wc -l x",
    "LC_ALL=C sort f",
    "timeout 10 git status",
    "env",
    "command -v swift",
    "swift --version",
    "xcrun --find swift",
    "plutil -p Info.plist",
    "defaults read com.apple.dock autohide",
    "codesign -dv --verbose=4 App.app",
    "gh pr view 12 --json title",
    "gh api repos/o/r/pulls",
    "python3 --version",
    "cd Sources && ls",
    "echo hi >/dev/null 2>&1",
    "git diff 2>&1 | head",
    "grep -n 'a;b' f",
    "ls -la\ngit status --short",
    # A digit written against a redirection is its file descriptor, not an argument.
    "git branch -a 2>/dev/null",
    # Operator characters inside quotes or after a backslash are text.
    "grep -n '|' f",
    "grep -c \\; f",
    # A heredoc body and a here-string are input, not commands.
    "cat <<'EOF'\nrm -rf x\nEOF",
    "grep -c x <<< 'a; rm x'",
    "git log \\\n  --oneline",
    "sed -n '$p' f",
    "sed -n '/^import /p' f",
    "sed -ne '10,20p' f",
    "git remote -v",
    "git config --global --get user.email",
    "git tag --contains HEAD",
    "git branch --contains abc123",
    "git --no-pager log -1",
    "git reflog -n 5",
    "git stash show -p",
    "xcrun --sdk macosx --show-sdk-path",
    "codesign -d --entitlements - App.app",
    "gh api -X GET repos/o/r",
    "env LC_ALL=C sort f",
    "nice -n 5 git log",
    "time git status",
    "echo done 1>&2",
    "/usr/bin/grep -n x f",
    "GIT_PAGER=cat git log",
    "ls | xargs -I{} echo {}",
    "cat <<-EOF\n\tx\n\tEOF\nls",
    "cat <<EOF | grep x\nbody\nEOF",
    # A # that starts a word begins a comment, which the shell ignores to the end of the line: here it runs only ls.
    "ls  # it's done; rm x",
    "# show the state\ngit status",
    "cat <<EOF # the body starts on the next line\nrm x\nEOF",
    # A $ in single quotes or after a backslash is literal.
    "grep -n '$' f",
    "grep -n \\$HOME f",
    'grep -n "a\\$" f',
    # Braces without a comma or .. inside expand to nothing: git's @{u} stays a word, and quoted braces are text.
    "git log @{u}..HEAD --oneline",
    "git show HEAD@{1}",
    "find . -name '*.{h,m}'",
]

BLOCKED = [
    "rm -rf x",
    "git checkout main",
    "git switch -c b",
    "git commit -m x",
    "git push",
    "git stash",
    "git stash pop",
    "git branch -D x",
    "git branch newname",
    "git tag v1",
    "git config user.name x",
    "git -c core.fsmonitor=rm status",
    "git diff --output=x",
    "git reset --hard",
    "git worktree add ../w",
    "echo x > f",
    "echo x >> f",
    "ls > out.txt",
    "cat a 1>b",
    "cat a | tee b",
    "sed -i 's/a/b/' f",
    "sed 's/a/b/w out' f",
    "sed -n '1w out' f",
    "awk '{print > \"f\"}' x",
    "find . -delete",
    "find . -exec rm {} \\;",
    "rg --pre cat x",
    "sort -o f f",
    "xargs rm",
    "find . | xargs rm",
    "$(rm x)",
    "`rm x`",
    "echo $(whoami)",
    "cat <(ls)",
    "bash -c 'ls'",
    "sh -c ls",
    "python3 -c 'print(1)'",
    "python3 script.py",
    "node -e 1",
    "eval ls",
    "source x",
    ". x",
    "(ls)",
    "{ ls; }",
    "GIT_EXTERNAL_DIFF=x git diff",
    "PATH=/tmp ls",
    "sudo ls",
    "curl -o f https://x",
    "open .",
    "kill 1",
    "mktemp",
    "touch f",
    "ls; rm x",
    "ls && rm x",
    "gh api -X POST repos/o/r/issues",
    "gh api repos/o/r/issues -f title=x",
    "gh pr merge 1",
    "defaults write d k v",
    "plutil -convert xml1 f",
    "codesign -s - App.app",
    "sysctl -w a=b",
    "security find-generic-password -w",
    "xcodebuild build",
    "swift build",
    "swift package resolve",
    "brew install x",
    "make",
    "frobnicate",
    # A newline separates commands, and a # inside a word starts no comment.
    "ls\nrm x",
    "ls a#b; rm x",
    # A digit with a space before the redirection is an argument: this creates the tag 2.
    "git tag 2 >/dev/null",
    # An escaped backslash leaves the ; that follows it a separator.
    "ls \\\\;rm x",
    # The line after a heredoc's delimiter is a command again.
    "cat <<EOF\nx\nEOF\nrm x",
    "echo x >& out",
    "echo x &> out",
    "ls | xargs git branch",
    "python3 -v",
    "git diff --outp=x",
    "git grep -O foo",
    "git remote add o https://x",
    "git config --unset x",
    "git log $'--output=x'",
    "./cat f",
    "env -S 'rm x'",
    "codesign -d --entitlements ent.plist App.app",
    "gh pr view 1 --web",
    "sort --compress-program=gzip f",
    "tree -o out.txt",
    "less -o log f",
    "uniq a b",
    "xxd a b",
    "cat <<-EOF\n\tx\n\tEOF\nrm x",
    # Only ASCII digits make a file descriptor: a superscript two is an argument, so this creates a tag.
    "git tag \u00b2>/dev/null",
    # A heredoc marker inside a comment starts no heredoc, so the lines after it are commands.
    "ls # <<EOF\nrm -rf build\nEOF",
    "ls;# <<EOF\nrm x\nEOF",
    "ls \\\n# <<EOF\nrm x\nEOF",
    "cat <<EOF # comment\nx\nEOF\nrm x",
    # Parameter expansion builds words the checks cannot see, inside double quotes too.
    "find . ${X:--exec} rm {} \\;",
    "git log -p ${X:---output=/tmp/pwn}",
    "find . ${IFS}-delete",
    'git log "${X:---output=/tmp/pwn}"',
    # Brace expansion builds words the checks cannot see: -{,}delete becomes -delete -delete.
    "find . -name '*.md' -{,}delete",
    "git log -p --outp{,}ut=/tmp/pwn",
    "git log -p --outp{u..u}t=/tmp/pwn",
]

# (command, text the refusal must name)
REFUSAL_NAMES = [
    ("rm -rf x", "`rm`"),
    ("echo $(whoami)", "$("),
    ("ls > out.txt", "out.txt"),
    ("git checkout main", "git checkout"),
    ("sudo ls", "sudo"),
    ("(ls)", "("),
    ("{ ls; }", "group syntax `{`"),
    ("sed -i 's/a/b/' f", "-i"),
    ("PATH=/tmp ls", "PATH"),
    ("find . ${IFS}-delete", "${IFS}-delete"),
    ("find . -{,}delete", "brace expansion in `-{,}delete`"),
]


class AllowTests(unittest.TestCase):
    def test_read_only_commands_are_allowed(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                status, errors = run_bash(command)
                self.assertEqual(status, 0, errors)
                self.assertEqual(errors, "")


class BlockTests(unittest.TestCase):
    def test_commands_that_can_change_state_are_blocked(self):
        for command in BLOCKED:
            with self.subTest(command=command):
                status, errors = run_bash(command)
                self.assertEqual(status, 2, f"allowed: {command!r}")
                self.assertTrue(errors.startswith(PREFIX), errors)
                self.assertIn(ADVICE, errors)
                self.assertEqual(len(errors.strip().splitlines()), 1, errors)

    def test_the_refusal_names_the_program_or_construct(self):
        for command, name in REFUSAL_NAMES:
            with self.subTest(command=command):
                status, errors = run_bash(command)
                self.assertEqual(status, 2)
                self.assertTrue(errors.startswith(PREFIX), errors)
                self.assertIn(name, errors)


class FailClosedTests(unittest.TestCase):
    def test_input_the_hook_cannot_check_is_blocked(self):
        inputs = {
            "invalid JSON": "{not json",
            "no tool_input": json.dumps({"tool_name": "Bash"}),
            "a non-string command": json.dumps({"tool_name": "Bash", "tool_input": {"command": ["ls"]}}),
            "an empty command": json.dumps({"tool_name": "Bash", "tool_input": {"command": ""}}),
            "a blank command": json.dumps({"tool_name": "Bash", "tool_input": {"command": " \n "}}),
            "unbalanced quotes": json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo 'unbalanced"}}),
            "no tool_name": json.dumps({"tool_input": {"command": "ls"}}),
        }
        for label, stdin in inputs.items():
            with self.subTest(input=label):
                status, errors = run_hook(stdin)
                self.assertEqual(status, 2)
                self.assertTrue(errors.startswith(PREFIX), errors)


class OtherToolTests(unittest.TestCase):
    def test_a_tool_other_than_bash_is_allowed_whatever_its_input(self):
        for tool_input in ({"file_path": "/etc/hosts"}, {"command": "rm -rf /"}, None):
            with self.subTest(tool_input=tool_input):
                status, errors = run_hook(json.dumps({"tool_name": "Read", "tool_input": tool_input}))
                self.assertEqual(status, 0, errors)


if __name__ == "__main__":
    unittest.main()

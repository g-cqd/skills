#!/usr/bin/env python3
"""Let a read-only agent run read-only shell commands, and refuse every command that could change state.

A Claude Code PreToolUse hook for the Bash tool, wired in an agent's frontmatter:

  hooks:
    PreToolUse:
      - matcher: "Bash"
        hooks:
          - type: command
            command: 'python3 "$HOME/.claude/agents/hooks/readonly-bash.py" || exit 2'

Claude Code passes the call as JSON on stdin: {"tool_name": "Bash", "tool_input": {"command": "..."}}.
Exit status 0 allows the call. Exit status 2 blocks it, and the one line on stderr tells the agent why. Any other
status lets the call through, so the hook fails closed by itself: malformed JSON, a missing, empty or unparsable
command, and any unexpected error all exit 2. A tool other than Bash exits 0.

Threat model: a guardrail that stops a read-only agent from changing files, git state, processes or the network by
mistake. It is not a sandbox against a hostile repository: git config that runs a textconv or diff driver, a pager
the repository sets, or a file named like an option are out of scope. It is an allowlist: a command it does not
recognise is refused.

How a command is checked:
  - The raw text holds no command substitution ($( or backticks) and no process substitution (<( or >( ).
  - No word holds a $ outside single quotes that is not escaped: parameter expansion, and $'...' or $"..." quoting, can
    build an option, such as ${X:--exec}, that the checks, which compare literal text, would not see.
  - shlex splits the text into simple commands on ; && || | |& & and newlines, outside quotes, and every simple
    command must pass. A subshell or a group, ( ) { }, is refused. A heredoc body is input, not commands, and a
    comment, from an unquoted # that starts a word to the end of its line, is dropped.
  - Redirections: input (<, <<, <<<) is fine; output (>, >>, >|, &>, N>) only to /dev/null; an fd duplication such as
    2>&1 is fine.
  - Leading NAME=value assignments are allowed only for the variables in ASSIGNMENTS.
  - The wrappers command, time, nice, timeout, env and xargs are unwrapped, and the command they run is checked.
  - The program, the basename of argv[0], must be in the allowlist and pass the rule for it, if it has one.

Check a command by hand:
  echo '{"tool_name": "Bash", "tool_input": {"command": "git status"}}' | python3 readonly-bash.py; echo $?

Runs on Python 3.9 and later, the macOS system python3, with the standard library only.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

ADVICE = "hand the change back to your caller instead"

# MARK: - Policy: shell syntax

RAW_REFUSALS = (
    ("$(", "command substitution `$(` can run any command"),
    ("`", "command substitution with backticks can run any command"),
    ("<(", "process substitution `<(` can run any command"),
    (">(", "process substitution `>(` can run any command"),
)
PUNCTUATION = "();<>|&\n"
SEPARATORS = frozenset({";", "&&", "||", "|", "|&", "&"})
INPUT_REDIRECTIONS = frozenset({"<", "<<", "<<-", "<<<", "<&"})
OUTPUT_REDIRECTIONS = frozenset({">", ">>", ">|", "&>", "&>>"})
DUPLICATION = ">&"
REDIRECTIONS = INPUT_REDIRECTIONS | OUTPUT_REDIRECTIONS | {DUPLICATION, "<>"}
NULL_DEVICE = "/dev/null"
ASSIGNMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.S)
# Variables a command may set for itself; None allows any value.
ASSIGNMENTS = {
    "LC_ALL": None, "LANG": None, "LC_CTYPE": None, "NO_COLOR": None, "TZ": None, "COLUMNS": None, "TERM": None,
    "GIT_PAGER": "cat", "PAGER": "cat",
}

# MARK: - Policy: programs

ALWAYS_ALLOWED = frozenset("""
    cat head tail wc ls stat du df pwd echo printf true false test [ which type uname sw_vers date id whoami hostname
    basename dirname realpath readlink cut tr nl column diff cmp comm hexdump od strings otool nm size uptime ps pgrep
    lsof printenv locale mdls mdfind cd pushd popd sleep jq
""".split())
SHELL_EVALUATORS = frozenset({"eval", "exec", "source", "."})
# The shell reads { and } as a group only in command position, as it reads ( and ) anywhere.
GROUP_WORDS = frozenset({"{", "}"})
PRIVILEGED = frozenset({"sudo", "su", "doas"})
INTERPRETERS = frozenset({
    "sh", "bash", "zsh", "fish", "dash", "ksh", "csh", "tcsh",
    "python", "python3", "perl", "ruby", "node", "osascript",
})
# A version check is the only call these programs may take. Python's -v is verbose mode, which runs stdin as code.
VERSION_PROBES = {
    name: frozenset({"--version", "-V", "-v"})
    for name in ("node", "ruby", "perl", "clang", "cmake", "go", "rustc", "cargo", "java", "kotlinc")
}
VERSION_PROBES.update({name: frozenset({"--version", "-V"}) for name in ("python", "python3")})

# Programs allowed with any arguments but these options: "--long" also matches its abbreviations and "--long=value",
# "-x" matches the letter inside a cluster of short options, and any other word must match exactly.
FIND_ACTIONS = ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls")
GREP_OPTIONS = ("--filter", "--save-config")
PAGER_OPTIONS = ("-o", "-O", "--log-file", "--LOG-FILE")
FORBIDDEN_OPTIONS = {
    "sort": (("-o", "--output", "--compress-program"), "writes a file or runs a program"),
    "rg": (("--pre", "--pre-glob"), "runs a program on each file"),
    "grep": (GREP_OPTIONS, "runs a program or writes a file"),
    "egrep": (GREP_OPTIONS, "runs a program or writes a file"),
    "fgrep": (GREP_OPTIONS, "runs a program or writes a file"),
    "ugrep": (GREP_OPTIONS, "runs a program or writes a file"),
    "find": (FIND_ACTIONS, "deletes, writes or runs a command"),
    "bfs": (FIND_ACTIONS, "deletes, writes or runs a command"),
    "less": (PAGER_OPTIONS, "writes a log file"),
    "more": (PAGER_OPTIONS, "writes a log file"),
    "tree": (("-o", "-R"), "writes a file"),
    "file": (("-C", "--compile"), "writes a compiled magic file"),
    "sysctl": (("-w", "-f"), "sets a kernel value"),
    "lipo": (("-output", "-create", "-thin", "-extract", "-extract_family", "-remove", "-replace"), "writes a binary"),
    "codesign": (
        ("-s", "--sign", "--remove-signature", "-f", "--force", "--extract-certificates", "--file-list"),
        "signs a binary or writes a file",
    ),
    "gh": (("-w", "--web"), "opens a browser"),
}
# Programs that write their second file operand: at most one operand. Options named here take a value.
OPERAND_LIMITS = {
    "uniq": frozenset({"-f", "-s", "-w"}),
    "xxd": frozenset({"-c", "-g", "-l", "-n", "-o", "-s", "-cols", "-groupsize", "-len", "-name", "-offset", "-seek"}),
}
# Programs allowed only with exactly these arguments.
EXACT_FORMS = {
    "swift": {("--version",), ("-version",), ("package", "dump-package"), ("package", "describe"),
              ("package", "describe", "--type", "json"), ("package", "describe", "--type=json")},
    "xcode-select": {("-p",), ("--print-path",), ("-v",), ("--version",)},
    "xcodebuild": {("-version",), ("-showsdks",)},
}
# Programs allowed only when their first argument is one of these.
FIRST_ARGUMENTS = {
    "brew": frozenset({"list", "info", "--prefix", "--version", "config", "deps", "uses", "leaves", "outdated"}),
    "plutil": frozenset({"-p", "-lint", "-help"}),
}
DEFAULTS_ACTIONS = frozenset({"read", "read-type", "domains", "find"})
LIPO_QUERIES = frozenset({"-info", "-detailed_info", "-archs", "-verify_arch"})
# sed options: short flags -n (quiet, required), -E/-r (extended regex) and -u (unbuffered), in any cluster that may
# end with e and its script (-ne '5p'); long options map to whether they make sed quiet.
SED_CLUSTER = re.compile(r"-([nEru]*)(?:e(.*))?", re.S)
SED_LONG_OPTIONS = {"--quiet": True, "--silent": True, "--regexp-extended": False, "--unbuffered": False}
# A sed script of line addresses and p, =, or q commands only: no w, r, e, s, or a block.
_SED_ADDRESS = r"(?:\d+(?:~\d+)?|\$|/(?:[^/\\\n]|\\.)*/I?)"
_SED_COMMAND = rf"(?:{_SED_ADDRESS}(?:\s*,\s*(?:{_SED_ADDRESS}|[+~]\d+))?)?\s*!?\s*(?:p|=|q\d*)"
SED_SCRIPT = re.compile(rf"\s*{_SED_COMMAND}(?:\s*[;\n]\s*{_SED_COMMAND})*\s*;?\s*")
XCRUN_QUERIES = frozenset({"--show-sdk-path", "--show-sdk-version", "--show-sdk-platform-path", "--version"})
XCRUN_FIND = frozenset({"--find", "-find", "-f"})
XCRUN_SDK = frozenset({"--sdk", "-sdk"})
CODESIGN_FLAGS = frozenset({"--display", "--verify", "--deep", "--check-notarization", "--xml", "--der",
                            "--all-architectures", "--verbose", "--strict", "--no-strict"})
# Options that take a value; None allows any value, and a set lists the only values that write to stdout.
CODESIGN_VALUES = {"--arch": None, "-a": None, "--test-requirement": None, "-R": None,
                   "--entitlements": frozenset({"-", ":-"}), "--requirements": frozenset({"-"}),
                   "-r": frozenset({"-"})}
GH_READ_ONLY = {
    "pr": frozenset({"view", "diff", "list", "checks", "status"}),
    "issue": frozenset({"view", "list", "status"}),
    "run": frozenset({"view", "list"}),
    "repo": frozenset({"view"}),
    "release": frozenset({"view", "list"}),
    "search": None,
}
GH_API_FORBIDDEN = ("-f", "-F", "--field", "--raw-field", "--input")

# MARK: - Policy: git

GIT_GLOBAL_FLAGS = frozenset({"--no-pager", "-P", "-p", "--paginate"})
GIT_GLOBAL_VALUES = frozenset({"-C", "--git-dir", "--work-tree"})
GIT_READ_ONLY = frozenset("""
    log show diff blame status grep ls-files ls-tree rev-parse rev-list cat-file describe shortlog merge-base name-rev
    for-each-ref show-ref whatchanged count-objects check-ignore check-attr var version
""".split())
# Options refused on every git command, and on one subcommand: --output writes a file, --ext-diff runs a program.
GIT_FORBIDDEN = ("--output", "--ext-diff")
GIT_SUBCOMMAND_FORBIDDEN = {"grep": ("-O", "--open-files-in-pager")}
# Subcommands allowed only in these forms; "bare" also allows no action at all, or an option first.
GIT_ACTIONS = {
    "reflog": (frozenset({"show"}), True),
    "stash": (frozenset({"list", "show"}), False),
    "worktree": (frozenset({"list"}), False),
    "notes": (frozenset({"show", "list"}), False),
}
# Listing options for branch and tag: flags, options that need a value, options whose value is optional (the next
# word, when it is not an option), and the options that make a positional argument a pattern instead of a new name.
GIT_LISTING = {
    "branch": {
        "flags": frozenset({"-a", "-r", "-l", "--list", "-v", "-vv", "--all", "--remotes", "--verbose",
                            "--show-current", "--color", "--no-color", "--column", "--no-column"}),
        "values": frozenset({"--format", "--sort", "--points-at"}),
        "optional": frozenset({"--contains", "--no-contains", "--merged", "--no-merged"}),
        "attached": frozenset({"--color", "--column"}),
        "short": re.compile(r"-[arlv]+"),
        "list": frozenset({"-l", "--list"}),
    },
    "tag": {
        "flags": frozenset({"-l", "--list", "-n"}),
        "values": frozenset({"--format", "--sort", "--points-at"}),
        "optional": frozenset({"--contains"}),
        "attached": frozenset(),
        "short": re.compile(r"-n\d+"),
        "list": frozenset({"-l", "--list"}),
    },
}
GIT_REMOTE_ACTIONS = frozenset({"show", "get-url"})
GIT_REMOTE_FLAGS = frozenset({"-v", "--verbose"})
GIT_CONFIG_READS = frozenset({"--get", "--get-all", "--get-regexp", "-l", "--list"})
GIT_CONFIG_MODIFIERS = frozenset({"--show-origin", "--show-scope", "--name-only", "--global", "--system", "--local",
                                  "--worktree", "-z", "--null"})

# MARK: - Policy: wrappers

# command -v and -V only look a name up.
COMMAND_LOOKUPS = "vV"
NICE_ADJUSTMENT = re.compile(r"-n?\d+|--adjustment=-?\d+")
TIMEOUT_FLAGS = frozenset({"--preserve-status", "--foreground", "-v", "--verbose"})
TIMEOUT_VALUES = frozenset({"-s", "--signal", "-k", "--kill-after"})
DURATION = re.compile(r"\d+(?:\.\d+)?[smhd]?")
ENV_FLAGS = frozenset({"-i", "-", "--ignore-environment", "-0", "--null"})
ENV_VALUES = frozenset({"-u", "--unset"})
XARGS_FLAGS = frozenset({"-0", "-r", "-t"})
XARGS_VALUES = frozenset({"-n", "-L", "-I", "-P", "-s", "-E", "-d"})
# xargs appends its input to the command, so the command is checked with one more operand, unless -I places it.
XARGS_OPERAND = "xargs-input"


class Refusal(Exception):
    """A command the hook refuses; the message names what it refused and why."""


# MARK: - Tokens


def check_raw(command: str) -> None:
    """Refuses the substitutions and quoting that the tokens could hide: shlex keeps `$(` and backticks inside a
    word, so only the raw text shows them."""
    for marker, reason in RAW_REFUSALS:
        if marker in command:
            raise Refusal(reason)


def _lexer(text: str) -> shlex.shlex:
    lexer = shlex.shlex(text, posix=True, punctuation_chars=PUNCTUATION)
    lexer.whitespace_split = True
    # A newline separates commands, so it is punctuation, not whitespace.
    lexer.whitespace = " \t\r"
    # shlex starts a comment at a # inside a word, where the shell does not; without comments, a real comment is only
    # read as more words, which can refuse a command but never hide one.
    lexer.commenters = ""
    return lexer


def check_word(raw: str) -> None:
    """Refuses a word whose raw text, as written, holds a `$` outside single quotes that no backslash escapes."""
    quote, escaped = None, False
    for character in raw:
        if escaped:
            escaped = False
        elif quote == "'":
            quote = None if character == "'" else quote
        elif character == "\\":
            escaped = True
        elif character == '"':
            quote = None if quote == '"' else '"'
        elif character == "'" and quote is None:
            quote = "'"
        elif character == "$":
            raise Refusal(f"`$` in `{raw}` expands to text this check cannot see; quote a literal `$` in single quotes")


def _is_operator(text: str, token: str, end: int) -> bool:
    """Whether `token`, which ends at `end` in `text`, is an operator the shell sees, not a quoted or escaped word."""
    start = end - len(token)
    if not token or any(character not in PUNCTUATION for character in token) or text[start:end] != token:
        return False
    backslashes = 0
    while start - backslashes > 0 and text[start - backslashes - 1] == "\\":
        backslashes += 1
    return backslashes % 2 == 0


def _skip_blanks(text: str, position: int) -> int:
    while position < len(text) and text[position] in " \t\r":
        position += 1
    return position


def _token_start(text: str, position: int) -> int:
    """Where the next token starts: after blanks and line continuations, which the shell removes."""
    while position < len(text):
        if text[position] in " \t\r":
            position += 1
        elif text.startswith("\\\n", position):
            position += 2
        else:
            break
    return position


def _continued(raw: str, word: str) -> str | None:
    """The word without the line continuations (backslash-newline) its raw text starts with, or None when the raw text
    is only a continuation. shlex keeps the newline, where the shell removes both characters."""
    if "\\\n" not in raw:
        return word
    if raw == "\\\n":
        return None
    if raw.startswith("\\\n") and "\\\n" not in raw[2:]:
        return word[1:]
    raise Refusal("a line continuation inside a word is not supported")


def _skip_heredocs(text: str, position: int, pending: list) -> int:
    """The position after the heredoc bodies that start at `position`: one body per delimiter, in order, each ending
    at the line equal to its delimiter (after leading tabs, for <<-), or at the end of the text."""
    for delimiter, strip_tabs in pending:
        while position < len(text):
            newline = text.find("\n", position)
            line_end = len(text) if newline < 0 else newline
            line = text[position:line_end]
            position = line_end + 1
            if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                break
    return min(position, len(text))


def _read_line(text: str, offset: int, tokens: list) -> int:
    """Appends the tokens of `text` from `offset` up to the end, or up to a heredoc body; returns where to go on."""
    lexer = _lexer(text[offset:])
    previous_end, last_word = offset, None
    pending, expecting, dash = [], None, False
    while True:
        # An unquoted # at the start of a token begins a comment: the shell ignores the rest of the line, operators and
        # heredoc markers included, so it is dropped before shlex reads it. After <<-, the token starts past the -.
        position = _token_start(text, previous_end + (1 if dash else 0))
        if text.startswith("#", position):
            if expecting:
                raise Refusal(f"`{expecting}` has no delimiter")
            newline = text.find("\n", position)
            if newline < 0:
                return len(text)
            tokens.append(("op", "\n"))
            return _skip_heredocs(text, newline + 1, pending) if pending else newline + 1
        try:
            token = lexer.get_token()
        except ValueError as error:
            raise Refusal(f"the command could not be parsed ({error})") from None
        if token is None:
            if expecting:
                raise Refusal(f"`{expecting}` has no delimiter")
            return len(text)
        end = offset + lexer.instream.tell() - 1
        if _is_operator(text, token, end):
            start = end - len(token)
            if expecting:
                raise Refusal(f"`{expecting}` has no delimiter")
            if "\n" in token:
                separator = token.replace("\n", "")
                if separator and separator not in SEPARATORS:
                    raise Refusal(f"shell syntax `{separator}` before a newline is not supported")
                tokens.append(("op", separator or "\n"))
                if pending:
                    return _skip_heredocs(text, start + token.index("\n") + 1, pending)
            elif token in SEPARATORS:
                tokens.append(("op", token))
            elif token in REDIRECTIONS:
                if last_word and last_word[1] == start and tokens and tokens[-1] == ("word", last_word[0]):
                    tokens.pop()
                    token = last_word[0] + token
                heredoc = token.lstrip("0123456789") == "<<"
                dash = heredoc and text[end:end + 1] == "-"
                if heredoc:
                    expecting = token + ("-" if dash else "")
                tokens.append(("op", token + ("-" if dash else "")))
            elif "(" in token or ")" in token:
                raise Refusal(f"subshell syntax `{token}` is not supported")
            else:
                raise Refusal(f"shell syntax `{token}` is not supported")
            previous_end, last_word = end, None
            continue
        start = _skip_blanks(text, previous_end)
        check_word(text[start:end])
        word = _continued(text[start:end], token)
        previous_end = end
        if word is None:
            continue
        if dash:
            word, dash = word[1:], False
            if not word:
                continue
        if expecting:
            pending.append((word, expecting == "<<-"))
            expecting = None
        tokens.append(("word", word))
        # A file descriptor number is unquoted digits written against the redirection that follows.
        plain = word.isascii() and word.isdigit() and text[start:end] == word
        last_word = (word, end) if plain else None


def tokenize(command: str) -> list:
    """The command as (kind, text) pairs, kind "word" or "op", as the shell reads them: quotes removed, a file
    descriptor joined to its redirection (2>), line continuations removed, and heredoc bodies skipped."""
    # A trailing space makes shlex read one character past every token, so every token ends at tell() - 1.
    text = command + " "
    tokens, position = [], 0
    while position < len(text):
        position = _read_line(text, position, tokens)
    return tokens


def split_commands(tokens: list) -> list:
    """The simple commands between separators, each a list of tokens; empty commands run nothing and are dropped."""
    commands, current = [], []
    for kind, text in tokens:
        if kind == "op" and (text in SEPARATORS or text == "\n"):
            if current:
                commands.append(current)
            current = []
        else:
            current.append((kind, text))
    if current:
        commands.append(current)
    return commands


# MARK: - Simple commands


def check_redirection(operator: str, target: str | None) -> None:
    """Allows input, fd duplication, and output to /dev/null; refuses a redirection that writes a file."""
    base = operator.lstrip("0123456789")
    if target is None:
        raise Refusal(f"redirection `{operator}` has no target")
    if base in INPUT_REDIRECTIONS:
        return
    if base == DUPLICATION and re.fullmatch(r"\d+-?|-", target):
        return
    if base == "<>":
        raise Refusal(f"`{operator} {target}` opens a file for writing")
    if target != NULL_DEVICE:
        raise Refusal(f"output redirection `{operator} {target}` writes a file")


def check_assignment(word: str) -> None:
    """Allows NAME=value only for the variables in ASSIGNMENTS, with the value it requires, if any."""
    name, value = ASSIGNMENT.fullmatch(word).groups()
    if name not in ASSIGNMENTS:
        raise Refusal(f"setting `{name}` can change what a command runs")
    required = ASSIGNMENTS[name]
    if required is not None and value != required:
        raise Refusal(f"`{name}` may only be set to `{required}`")


def check_simple(tokens: list) -> None:
    """Checks one simple command: its redirections, its leading assignments, then its program and arguments."""
    words, index = [], 0
    while index < len(tokens):
        kind, text = tokens[index]
        if kind == "op":
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            check_redirection(text, following[1] if following and following[0] == "word" else None)
            index += 2
            continue
        words.append(text)
        index += 1
    position = 0
    while position < len(words) and ASSIGNMENT.fullmatch(words[position]):
        check_assignment(words[position])
        position += 1
    check_argv(words[position:])


def matches(argument: str, option: str) -> bool:
    """Whether `argument` uses `option`. A long option also matches `--option=value` and its abbreviations, which GNU
    getopt and git accept; a two-letter short option also matches inside a cluster (-uo) or with its value attached
    (-ofile); any other option, such as find's -delete, matches exactly."""
    if option.startswith("--"):
        name = argument.split("=", 1)[0]
        return argument.startswith("--") and len(name) > 2 and option.startswith(name)
    if len(option) == 2:
        return argument.startswith("-") and not argument.startswith("--") and option[1] in argument[1:]
    return argument == option


def first_use(args: list, options: tuple) -> str | None:
    """The first argument that uses one of `options`, or None."""
    for argument in args:
        if any(matches(argument, option) for option in options):
            return argument
    return None


# MARK: - Wrappers


def _unwrap_command(args: list) -> list:
    """`command -v NAME` only looks a name up; `command [-p] CMD` runs CMD."""
    index = 0
    while index < len(args) and args[index].startswith("-") and args[index] != "--":
        letters = args[index][1:]
        if not letters or any(letter not in "pvV" for letter in letters):
            raise Refusal(f"`command {args[index]}` is not a known option")
        if any(letter in COMMAND_LOOKUPS for letter in letters):
            return []
        index += 1
    return args[index + 1:] if args[index:index + 1] == ["--"] else args[index:]


def _unwrap_time(args: list) -> list:
    """`time [-p] CMD` runs CMD; bare time runs nothing."""
    return args[1:] if args[:1] == ["-p"] else args


def _unwrap_nice(args: list) -> list:
    """`nice [-n N | -N] CMD` runs CMD; bare nice prints the niceness."""
    if args[:1] == ["-n"]:
        if len(args) < 2 or not re.fullmatch(r"-?\d+", args[1]):
            raise Refusal("`nice -n` needs a number")
        return args[2:]
    if args and NICE_ADJUSTMENT.fullmatch(args[0]):
        return args[1:]
    if args and args[0].startswith("-"):
        raise Refusal(f"`nice {args[0]}` is not a known option")
    return args


def _unwrap_timeout(args: list) -> list:
    """`timeout [options] DURATION CMD` runs CMD."""
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        if option in TIMEOUT_FLAGS:
            index += 1
        elif option in TIMEOUT_VALUES:
            index += 2
        elif option.split("=", 1)[0] in TIMEOUT_VALUES or option[:2] in TIMEOUT_VALUES:
            index += 1
        else:
            raise Refusal(f"`timeout {option}` is not a known option")
    if index >= len(args) or not DURATION.fullmatch(args[index]):
        raise Refusal("`timeout` needs a duration and a command")
    return args[index + 1:]


def _unwrap_env(args: list) -> list:
    """`env [-i] [-u NAME] [NAME=value ...] [CMD]` runs CMD, and each assignment must be allowed; bare env prints."""
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        if option in ENV_FLAGS:
            index += 1
        elif option in ENV_VALUES:
            index += 2
        elif option.startswith("--unset=") or (option.startswith("-u") and len(option) > 2):
            index += 1
        else:
            raise Refusal(f"`env {option}` is not allowed")
    while index < len(args) and ASSIGNMENT.fullmatch(args[index]):
        check_assignment(args[index])
        index += 1
    return args[index:]


def _unwrap_xargs(args: list) -> list:
    """`xargs [options] CMD` runs CMD with its input appended, or where -I places it; xargs alone is refused."""
    index, placed = 0, False
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        if option in XARGS_FLAGS:
            index += 1
        elif option in XARGS_VALUES:
            placed, index = placed or option == "-I", index + 2
        elif option[:2] in XARGS_VALUES:
            placed, index = placed or option[:2] == "-I", index + 1
        else:
            raise Refusal(f"`xargs {option}` is not an allowed option")
    if index >= len(args):
        raise Refusal("`xargs` without a command runs one chosen by its input")
    return args[index:] if placed else args[index:] + [XARGS_OPERAND]


WRAPPERS = {
    "command": _unwrap_command,
    "time": _unwrap_time,
    "nice": _unwrap_nice,
    "timeout": _unwrap_timeout,
    "env": _unwrap_env,
    "xargs": _unwrap_xargs,
}


def check_argv(argv: list) -> None:
    """Checks a command's program and arguments, unwrapping each wrapper to check the command it runs."""
    while argv:
        program = argv[0]
        if "/" in program and not program.startswith("/"):
            raise Refusal(f"`{program}` runs a file by relative path, not a known read-only program")
        name = os.path.basename(program)
        if name not in WRAPPERS:
            check_program(name, argv[1:])
            return
        argv = WRAPPERS[name](argv[1:])


# MARK: - Programs


def check_program(name: str, args: list) -> None:
    """Allows a program only if a table below knows it and every rule the tables give for it passes."""
    if name in GROUP_WORDS:
        raise Refusal(f"group syntax `{name}` is not supported")
    if name in SHELL_EVALUATORS:
        raise Refusal(f"`{name}` runs its arguments as shell code")
    if name in PRIVILEGED:
        raise Refusal(f"`{name}` runs a command as another user")
    if name in VERSION_PROBES and len(args) == 1 and args[0] in VERSION_PROBES[name]:
        return
    if name in INTERPRETERS or name in VERSION_PROBES:
        raise Refusal(f"`{name}` runs code; only a version check such as `{name} --version` is allowed")
    known = name in ALWAYS_ALLOWED
    if name in FORBIDDEN_OPTIONS:
        options, why = FORBIDDEN_OPTIONS[name]
        used = first_use(args, options)
        if used is not None:
            raise Refusal(f"`{name} {used}` {why}")
        known = True
    if name in EXACT_FORMS:
        if tuple(args) not in EXACT_FORMS[name]:
            raise Refusal(f"`{' '.join([name] + args)}` is not one of the read-only forms of `{name}`")
        known = True
    if name in FIRST_ARGUMENTS:
        if not args or args[0] not in FIRST_ARGUMENTS[name]:
            raise Refusal(f"`{' '.join([name] + args[:1])}` is not one of the read-only forms of `{name}`")
        known = True
    if name in OPERAND_LIMITS:
        _check_operands(name, args, OPERAND_LIMITS[name])
        known = True
    if name in RULES:
        RULES[name](args)
        known = True
    if not known:
        raise Refusal(f"`{name}` is not a known read-only command")


def _check_operands(name: str, args: list, value_options: frozenset) -> None:
    """Refuses a second file operand, which these programs write to."""
    operands, index = [], 0
    while index < len(args):
        argument = args[index]
        index += 1
        if argument in value_options:
            index += 1
        elif argument == "-" or not argument.startswith("-"):
            operands.append(argument)
    if len(operands) > 1:
        raise Refusal(f"`{name}` writes its second operand, `{operands[1]}`")


def _check_sed(args: list) -> None:
    """sed may only print lines: -n, and scripts of line addresses with p, = or q; never -i, a script file, or a
    command that writes a file or runs one."""
    quiet, scripts, operands, index = False, [], [], 0
    while index < len(args):
        argument = args[index]
        index += 1
        name, has_value, value = argument.partition("=")
        cluster = SED_CLUSTER.fullmatch(argument)
        if argument == "-" or not argument.startswith("-"):
            operands.append(argument)
        elif argument in SED_LONG_OPTIONS:
            quiet = quiet or SED_LONG_OPTIONS[argument]
        elif name == "--expression" or (cluster and cluster.group(2) is not None):
            # Only the long form splits at "=": in a short cluster, the rest is the script itself (-e1p).
            if name == "--expression":
                script = value if has_value else ""
            else:
                quiet, script = quiet or "n" in cluster.group(1), cluster.group(2)
            if not script:
                if index >= len(args):
                    raise Refusal(f"`sed {argument}` has no script")
                script, index = args[index], index + 1
            scripts.append(script)
        elif cluster:
            quiet = quiet or "n" in cluster.group(1)
        else:
            raise Refusal(f"`sed {argument}` is not allowed; only `sed -n` with p, = or q can run")
    if not quiet:
        raise Refusal("`sed` without -n is not allowed; only `sed -n` with p, = or q can run")
    if not scripts:
        if not operands:
            raise Refusal("`sed` has no script")
        scripts.append(operands.pop(0))
    for script in scripts:
        if not SED_SCRIPT.fullmatch(script):
            raise Refusal(f"sed script `{script}` does more than print lines")


def _check_codesign(args: list) -> None:
    """codesign may display (-d) or verify (-v) a signature: every option must be a display or verify option, and a
    file it would write must be - (stdout)."""
    display = verify = False
    index = 0

    def value_of(option: str, attached: str) -> str:
        nonlocal index
        if not attached:
            if index >= len(args):
                raise Refusal(f"`codesign {option}` needs a value")
            attached, index = args[index], index + 1
        allowed = CODESIGN_VALUES[option]
        if allowed is not None and attached not in allowed:
            raise Refusal(f"`codesign {option} {attached}` writes a file")
        return attached

    while index < len(args):
        argument = args[index]
        index += 1
        name, _, attached = argument.partition("=")
        if argument == "--":
            break
        if argument == "-" or not argument.startswith("-"):
            continue
        if name in CODESIGN_FLAGS:
            display, verify = display or name == "--display", verify or name == "--verify"
        elif name in CODESIGN_VALUES:
            value_of(name, attached)
        elif not argument.startswith("--"):
            letters = argument[1:]
            for position, letter in enumerate(letters):
                if letter in "dv":
                    display, verify = display or letter == "d", verify or letter == "v"
                elif "-" + letter in CODESIGN_VALUES:
                    value_of("-" + letter, letters[position + 1:])
                    break
                else:
                    raise Refusal(f"`codesign {argument}` is not a display or verify option")
        else:
            raise Refusal(f"`codesign {argument}` is not a display or verify option")
    if not (display or verify):
        raise Refusal("`codesign` without -d or -v can sign a binary")


def _check_xcrun(args: list) -> None:
    """xcrun may report an SDK or the path of a tool, with an optional --sdk; running a tool through it is refused."""
    queries, index = 0, 0
    while index < len(args):
        argument = args[index]
        if (argument in XCRUN_SDK or argument in XCRUN_FIND) and index + 1 < len(args):
            queries, index = queries + (argument in XCRUN_FIND), index + 2
        elif argument in XCRUN_QUERIES:
            queries, index = queries + 1, index + 1
        else:
            raise Refusal(f"`xcrun {argument}` runs a developer tool; only --find and --show-sdk-* queries can run")
    if queries != 1:
        raise Refusal("`xcrun` needs exactly one query, such as --find or --show-sdk-path")


def _check_defaults(args: list) -> None:
    """defaults may read, list domains or find; -currentHost or -host HOST may come first."""
    index = {"-currentHost": 1, "-host": 2}.get(args[0], 0) if args else 0
    action = args[index] if index < len(args) else ""
    if action not in DEFAULTS_ACTIONS:
        raise Refusal(f"`defaults {action}` can change preferences")


def _check_plutil(args: list) -> None:
    """plutil -p, -lint and -help take files, - for stdin, and -s; any other option can write a file."""
    for argument in args[1:]:
        if argument.startswith("-") and argument not in ("-", "-s", "--"):
            raise Refusal(f"`plutil {args[0]} {argument}` can write a file")


def _check_sysctl(args: list) -> None:
    """sysctl may read values; a name=value argument sets one."""
    for argument in args:
        if not argument.startswith("-") and "=" in argument:
            raise Refusal(f"`sysctl {argument}` sets a kernel value")


def _check_lipo(args: list) -> None:
    """lipo may only describe a binary: -info, -detailed_info, -archs or -verify_arch."""
    if not any(argument in LIPO_QUERIES for argument in args):
        raise Refusal("`lipo` without -info, -detailed_info, -archs or -verify_arch can write a binary")


def _check_pager(args: list) -> None:
    """less and more may page files; a +command runs at start, and a less command can run a shell."""
    for argument in args:
        if argument.startswith("+"):
            raise Refusal(f"pager argument `{argument}` runs a pager command at start, which can run a shell")


def _check_gh(args: list) -> None:
    """gh may view and list pull requests, issues, runs, repositories and releases, search, and make GET API calls."""
    group = args[0] if args else ""
    if group == "api":
        _check_gh_api(args[1:])
        return
    if group not in GH_READ_ONLY:
        raise Refusal(f"`gh {group}` is not a read-only gh command")
    actions = GH_READ_ONLY[group]
    action = args[1] if len(args) > 1 else ""
    if actions is not None and action not in actions:
        raise Refusal(f"`gh {group} {action}` can change GitHub state")


def _check_gh_api(args: list) -> None:
    """gh api may only GET: no method other than GET, and no field or input, which turn the call into a write."""
    used = first_use(args, GH_API_FORBIDDEN)
    if used is not None:
        raise Refusal(f"`gh api {used}` sends a request body, which makes the call a write")
    for index, argument in enumerate(args):
        method = None
        if argument in ("-X", "--method"):
            method = args[index + 1] if index + 1 < len(args) else ""
        elif argument.startswith("--method="):
            method = argument.split("=", 1)[1]
        elif argument.startswith("-X"):
            method = argument[2:]
        if method is not None and method.upper() != "GET":
            raise Refusal(f"`gh api -X {method}` is not a GET request")


# MARK: - git


def _check_git(args: list) -> None:
    """git may run its read-only subcommands, and the listing forms of branch, tag, remote, config, reflog, stash,
    worktree and notes, after the global options -C, --git-dir, --work-tree, --no-pager and --paginate."""
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        name = option.split("=", 1)[0]
        if option == "--version":
            return
        if option in GIT_GLOBAL_FLAGS:
            index += 1
        elif option in GIT_GLOBAL_VALUES:
            index += 2
        elif name in GIT_GLOBAL_VALUES and name.startswith("--"):
            index += 1
        elif option == "-c" or name == "--config-env":
            raise Refusal(f"`git {option}` sets configuration that can run a program")
        else:
            raise Refusal(f"`git {option}` is not an allowed global option")
    if index >= len(args):
        raise Refusal("`git` needs a subcommand")
    subcommand, rest = args[index], args[index + 1:]
    used = first_use(rest, GIT_FORBIDDEN + GIT_SUBCOMMAND_FORBIDDEN.get(subcommand, ()))
    if used is not None:
        raise Refusal(f"`git {subcommand} {used}` writes a file or runs a program")
    if subcommand in GIT_READ_ONLY:
        return
    if subcommand not in GIT_RULES:
        raise Refusal(f"`git {subcommand}` can change the repository")
    GIT_RULES[subcommand](subcommand, rest)


def _check_git_action(subcommand: str, rest: list) -> None:
    """reflog, stash, worktree and notes may run only their listing actions."""
    actions, bare = GIT_ACTIONS[subcommand]
    first = rest[0] if rest else None
    if first in actions or (bare and (first is None or first.startswith("-"))):
        return
    raise Refusal(f"`{' '.join(['git', subcommand] + rest[:1])}` can change the repository")


def _check_git_listing(subcommand: str, rest: list) -> None:
    """branch and tag may only list: known listing options, and a positional argument only as a pattern after
    -l or --list, since otherwise it names a branch or tag to create."""
    policy = GIT_LISTING[subcommand]
    listing = any(argument in policy["list"] for argument in rest)
    index = 0
    while index < len(rest):
        argument = rest[index]
        index += 1
        name, has_value, _ = argument.partition("=")
        if argument == "--" or not argument.startswith("-"):
            if not listing and argument != "--":
                raise Refusal(f"`git {subcommand} {argument}` creates a {subcommand}")
        elif argument in policy["flags"] or policy["short"].fullmatch(argument):
            continue
        elif name in policy["values"]:
            index += 0 if has_value else 1
        elif name in policy["optional"]:
            if not has_value and index < len(rest) and not rest[index].startswith("-"):
                index += 1
        elif not (name in policy["attached"] and has_value):
            raise Refusal(f"`git {subcommand} {argument}` can change the repository")


def _check_git_remote(subcommand: str, rest: list) -> None:
    """remote may list (bare or -v), show a remote, or print its URL."""
    index = 0
    while index < len(rest) and rest[index] in GIT_REMOTE_FLAGS:
        index += 1
    if index < len(rest) and rest[index] not in GIT_REMOTE_ACTIONS:
        raise Refusal(f"`git remote {rest[index]}` can change the repository")


def _check_git_config(subcommand: str, rest: list) -> None:
    """config may only read: --get, --get-all, --get-regexp or --list, with display and scope options."""
    reads = False
    for argument in rest:
        if argument in GIT_CONFIG_READS:
            reads = True
        elif argument.startswith("-") and argument not in GIT_CONFIG_MODIFIERS:
            raise Refusal(f"`git config {argument}` can change the configuration")
    if not reads:
        raise Refusal(f"`{' '.join(['git', 'config'] + rest)}` without --get or --list can change the configuration")


GIT_RULES = {
    "reflog": _check_git_action,
    "stash": _check_git_action,
    "worktree": _check_git_action,
    "notes": _check_git_action,
    "branch": _check_git_listing,
    "tag": _check_git_listing,
    "remote": _check_git_remote,
    "config": _check_git_config,
}
RULES = {
    "sed": _check_sed,
    "git": _check_git,
    "codesign": _check_codesign,
    "xcrun": _check_xcrun,
    "defaults": _check_defaults,
    "plutil": _check_plutil,
    "sysctl": _check_sysctl,
    "lipo": _check_lipo,
    "less": _check_pager,
    "more": _check_pager,
    "gh": _check_gh,
}


# MARK: - Hook


def check_command(command: str) -> None:
    """Raises Refusal unless every simple command in `command` is read-only."""
    check_raw(command)
    for simple in split_commands(tokenize(command)):
        check_simple(simple)


def block(reason: str) -> int:
    """Prints the one-line refusal the agent sees and returns the status that blocks the call."""
    reason = reason.replace("\n", "\\n")
    print(f"read-only agent: {reason}; {ADVICE}", file=sys.stderr)
    return 2


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except ValueError as error:
        return block(f"the hook input is not valid JSON ({error})")
    if not isinstance(payload, dict) or not isinstance(payload.get("tool_name"), str):
        return block("the hook input has no tool_name")
    if payload["tool_name"] != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return block("the Bash call has no command to check")
    try:
        check_command(command)
    except Refusal as refusal:
        return block(str(refusal))
    return 0


if __name__ == "__main__":
    try:
        status = main()
    # Any failure must block: an exit status other than 0 or 2 would let the call through.
    except BaseException as error:
        status = block(f"the hook failed ({type(error).__name__}: {error})")
    sys.exit(status)

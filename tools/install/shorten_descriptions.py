#!/usr/bin/env python3
"""Shorten an over-long `description` in exported SKILL.md files, in place.

Usage: shorten_descriptions.py DIR...   (each DIR holds one skill directory per skill)

The Agent Skills format limits a description to 1,024 characters, and some harnesses (Pi) refuse a skill above it.
Apple's Xcode skill pack ships descriptions over the limit whose tail repeats the routing list in the skill's body.
For each SKILL.md whose description is longer than 1,024 characters, this keeps the longest prefix that ends at a
sentence or clause boundary within the limit and adds a pointer to the body. Only a single-line double-quoted or
plain description is changed; any other form is reported and left alone. Exit 0 always, so the install goes on.
"""

from __future__ import annotations

import json
import os
import re
import sys

LIMIT = 1024
POINTER = " The skill body lists the rest."
LINE_RE = re.compile(r'^(description:[ \t]*)(.*)$', re.M)


def decode(raw: str):
    raw = raw.strip()
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except ValueError:
            return None
        return value if isinstance(value, str) else None
    if raw[:1] in ("'", "|", ">", "") or raw.startswith(("{", "[")):
        return None
    return raw


def shorten(text: str) -> str:
    room = LIMIT - len(POINTER)
    head = text[:room]
    cut = max(head.rfind(". "), head.rfind("; "), head.rfind(".\n"))
    if cut < room // 2:
        cut = head.rfind(" ")
    return head[: cut + 1].rstrip(" ;,:-") + ("" if head[:cut + 1].rstrip().endswith(".") else ".") + POINTER


def process(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    match = re.match(r"---\n(.*?\n)---\n", text, re.S)
    if not match:
        return "no frontmatter"
    front = match.group(1)
    line = LINE_RE.search(front)
    if not line:
        return "no description"
    value = decode(line.group(2))
    if value is None:
        # A block or quoted-style scalar this script does not rewrite; it can only exceed the limit if the whole
        # frontmatter does.
        return "" if len(front) <= LIMIT else "description may exceed 1,024 characters but is not a single-line string; left as is"
    if len(value) <= LIMIT:
        return ""
    new_front = front[: line.start()] + line.group(1) + json.dumps(shorten(value), ensure_ascii=False) + front[line.end():]
    with open(path + ".tmp", "w", encoding="utf-8") as handle:
        handle.write("---\n" + new_front + "---\n" + text[match.end():])
    os.replace(path + ".tmp", path)
    return f"description shortened from {len(value)} to at most {LIMIT} characters"


def main(argv) -> int:
    for root in argv:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name, "SKILL.md")
            if os.path.isfile(path) and not os.path.islink(path):
                note = process(path)
                if note:
                    print(f"  {name}: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

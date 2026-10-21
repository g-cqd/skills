#!/usr/bin/env python3
"""Change-level cognitive-load score of a diff: how heavy the whole change is to review.

Measures size and spread of a change, so a simplification pass can show that it made the change
smaller before and after, in any repository, with git as the only dependency.

    CL = (volume + scatter) * (1 - min(test_ratio, 1) * test_compensation)

    volume   ln(1 + added + deleted) over production lines: files that are neither tests nor excluded.
             The logarithm reflects that review effort grows more slowly than raw size.
    scatter  Shannon entropy of the per-file change fractions, normalised to [0, 1] by ln(files) and
             scaled by ln(1 + files); zero for a single file. Spread over many files is harder to review
             than the same lines in one place (change entropy as a fault predictor: Hassan, ICSE 2009).
    test_ratio  test lines over all changed lines; test_compensation (default 0.25) caps the discount,
             because reviewers still read the tests.
    bands    Small < 5, Medium < 10, Large < 18, Oversized from 18. These are heuristics anchored on
             published review-size medians, not validated thresholds.

The score reflects size and spread, not code complexity: pair it with a per-function measure. Run it on
the diff against the merge-base, before the pass and again after, and compare the two.

Usage:
    pr_size.py [--base REF] [--head REF] [--exclude GLOB]... [--test-pattern GLOB]... [--json]
    git diff --no-renames --numstat -z A..B | pr_size.py --stdin

Without --head the working tree is measured against the merge-base, so uncommitted edits count;
untracked files do not (run `git add -N <file>` first). Mode-only changes are ignored, binary files
count as a file with no lines. Python 3, standard library only.
"""
import argparse
import json
import math
import subprocess
import sys

DEFAULT_TEST_PATTERNS = [
    "Tests/*", "*/Tests/*", "test/*", "*/test/*", "src/test/*", "*/src/test/*",
    "__tests__/*", "*/__tests__/*", "*Tests.swift", "*Test.swift", "*Spec.swift",
    "*Tests.kt", "*Test.kt", "*Spec.kt", "*Tests.java", "*Test.java",
]
SMALL_MAX, MEDIUM_MAX, LARGE_MAX = 5.0, 10.0, 18.0


def _matches_single(path, pattern):
    """Glob match: the `*`-separated parts must appear in order, the first anchored at the start and the last at the end."""
    parts = pattern.split("*")
    if len(parts) == 1:
        return path == pattern or path.endswith("/" + pattern)
    position = 0
    for index, part in enumerate(parts):
        if not part:
            continue
        haystack = path[position:]
        if index == 0:
            if not haystack.startswith(part):
                return False
            position += len(part)
        elif index == len(parts) - 1:
            if not haystack.endswith(part):
                return False
        else:
            found = haystack.find(part)
            if found < 0:
                return False
            position += found + len(part)
    return True


def glob_matches(path, patterns):
    return any(_matches_single(path, pattern) for pattern in patterns)


def parse_numstat(data, nul=True):
    """Parse `git diff --numstat` output (NUL-separated with -z) into (path, added, deleted, binary)."""
    records = data.split("\0") if nul else data.splitlines()
    stats = []
    for record in records:
        parts = record.split("\t", 2)
        if len(parts) != 3 or not parts[2]:
            continue
        binary = parts[0] == "-" or parts[1] == "-"
        added = 0 if binary else (int(parts[0]) if parts[0].isdigit() else 0)
        deleted = 0 if binary else (int(parts[1]) if parts[1].isdigit() else 0)
        stats.append((parts[2], added, deleted, binary))
    return stats


def band(score):
    if score < SMALL_MAX:
        return "small"
    if score < MEDIUM_MAX:
        return "medium"
    if score < LARGE_MAX:
        return "large"
    return "oversized"


def compute(stats, exclude=(), test_patterns=None, volume_weight=1.0, scatter_weight=1.0,
            test_compensation=0.25):
    included = [
        s for s in stats
        if (s[3] or s[1] + s[2] > 0) and not (exclude and glob_matches(s[0], exclude))
    ]
    patterns = DEFAULT_TEST_PATTERNS if test_patterns is None else test_patterns
    test = [s for s in included if patterns and glob_matches(s[0], patterns)]
    prod = [s for s in included if not (patterns and glob_matches(s[0], patterns))]

    prod_add, prod_del = sum(s[1] for s in prod), sum(s[2] for s in prod)
    prod_total = prod_add + prod_del
    test_add, test_del = sum(s[1] for s in test), sum(s[2] for s in test)
    overall = prod_total + test_add + test_del

    volume = math.log(1.0 + prod_total) * volume_weight
    entropy = scatter = 0.0
    if len(prod) > 1 and prod_total > 0:
        raw = 0.0
        for _, added, deleted, _ in prod:
            changed = added + deleted
            if changed > 0:
                p = changed / prod_total
                raw -= p * math.log(p)
        max_entropy = math.log(len(prod))
        entropy = raw / max_entropy if max_entropy > 0 else 0.0
        scatter = entropy * math.log(1.0 + len(prod)) * scatter_weight

    test_ratio = 0.0 if overall == 0 else (test_add + test_del) / overall
    cap = max(0.0, min(test_compensation, 1.0))
    cognitive = (volume + scatter) * (1.0 - min(test_ratio, 1.0) * cap)
    return {
        "additions": prod_add, "deletions": prod_del, "files": len(prod),
        "test_files": len(test), "test_additions": test_add, "test_deletions": test_del,
        "volume": volume, "scatter": scatter, "entropy": entropy, "test_ratio": test_ratio,
        "cognitive_score": cognitive, "band": band(cognitive),
    }


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default="origin/HEAD", help="ref to diff against (default origin/HEAD)")
    ap.add_argument("--head", help="ref to measure; default is the working tree")
    ap.add_argument("--exclude", action="append", default=[], help="glob of files to drop (repeatable)")
    ap.add_argument("--test-pattern", action="append", default=None,
                    help="glob that marks test files, replacing the defaults (repeatable)")
    ap.add_argument("--stdin", action="store_true", help="read `git diff --numstat -z` output from stdin")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.stdin:
        data = sys.stdin.read()
    else:
        head = args.head or "HEAD"
        merge_base = _git("merge-base", args.base, head)
        target = [f"{merge_base}..{args.head}"] if args.head else [merge_base]
        data = subprocess.run(["git", "diff", "--no-renames", "--numstat", "-z", *target],
                              capture_output=True, text=True, check=True).stdout
    result = compute(parse_numstat(data), exclude=args.exclude, test_patterns=args.test_pattern)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"cognitive load {result['cognitive_score']:.2f} ({result['band']})  "
              f"volume {result['volume']:.2f}  scatter {result['scatter']:.2f}  "
              f"+{result['additions']}/-{result['deletions']} in {result['files']} files "
              f"(tests: +{result['test_additions']}/-{result['test_deletions']} in {result['test_files']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

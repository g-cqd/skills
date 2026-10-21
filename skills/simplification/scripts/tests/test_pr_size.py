"""Tests for pr_size.py: parsing, glob matching, and hand-derived score vectors (for example 30 files of
40 added lines each give volume ln(1201), scatter ln(31) and a Large band)."""
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pr_size  # noqa: E402


def stat(path, added, deleted=0, binary=False):
    return (path, added, deleted, binary)


class ParseTests(unittest.TestCase):
    def test_plain_text_format(self):
        raw = "10\t2\tSources/Foo.swift\n5\t0\tSources/Bar.swift\n-\t-\tdocs/diagram.png"
        stats = pr_size.parse_numstat(raw, nul=False)
        self.assertEqual(stats[0], ("Sources/Foo.swift", 10, 2, False))
        self.assertEqual(stats[1], ("Sources/Bar.swift", 5, 0, False))
        self.assertEqual(stats[2], ("docs/diagram.png", 0, 0, True))

    def test_nul_separated(self):
        stats = pr_size.parse_numstat("10\t2\tSources/Foo.swift\0" + "5\t0\tSources/Bar.swift\0")
        self.assertEqual([s[0] for s in stats], ["Sources/Foo.swift", "Sources/Bar.swift"])

    def test_malformed_lines_are_skipped(self):
        raw = "10\t2\tSources/Foo.swift\ngarbage line\n\t\t\n5\t0\tSources/Bar.swift"
        stats = pr_size.parse_numstat(raw, nul=False)
        self.assertEqual([s[0] for s in stats], ["Sources/Foo.swift", "Sources/Bar.swift"])


class GlobTests(unittest.TestCase):
    def test_default_test_patterns(self):
        for path in ("Tests/FooTests.swift", "ShareX/Tests/FooTests.swift", "src/test/Foo.kt",
                     "Sources/FooTests.swift", "app/FooSpec.kt", "pkg/__tests__/a.js"):
            self.assertTrue(pr_size.glob_matches(path, pr_size.DEFAULT_TEST_PATTERNS), path)
        for path in ("Sources/Foo.swift", "Sources/Contest.swift", "docs/readme.md"):
            self.assertFalse(pr_size.glob_matches(path, pr_size.DEFAULT_TEST_PATTERNS), path)

    def test_exact_name_matches_in_any_directory(self):
        self.assertTrue(pr_size.glob_matches("a/b/Package.resolved", ["Package.resolved"]))
        self.assertFalse(pr_size.glob_matches("a/b/Package.resolved.bak", ["Package.resolved"]))

    def test_prefix_pattern(self):
        self.assertTrue(pr_size.glob_matches("Generated/Strings.swift", ["Generated/*"]))
        self.assertFalse(pr_size.glob_matches("Sources/Generated/Strings.swift", ["Generated/*"]))


class ScoreTests(unittest.TestCase):
    def test_tiny_pr_is_small_and_counts_tests_apart(self):
        r = pr_size.compute([stat("Sources/Foo.swift", 20, 5), stat("Tests/FooTests.swift", 15)])
        self.assertEqual((r["additions"], r["deletions"], r["files"], r["test_files"]), (20, 5, 1, 1))
        self.assertEqual(r["band"], "small")

    def test_scattered_changes_raise_the_score(self):
        r = pr_size.compute([stat(f"Sources/Module{i}/File.swift", 40) for i in range(30)])
        self.assertAlmostEqual(r["volume"], math.log(1201), places=9)
        self.assertGreater(r["entropy"], 0.99)
        self.assertAlmostEqual(r["scatter"], math.log(31), places=2)
        self.assertGreater(r["cognitive_score"], 10.0)
        self.assertIn(r["band"], ("large", "oversized"))

    def test_single_file_has_no_scatter(self):
        r = pr_size.compute([stat("Sources/Big.swift", 500, 100)])
        self.assertEqual((r["scatter"], r["entropy"], r["files"]), (0.0, 0.0, 1))

    def test_tests_reduce_the_score_but_not_below_the_cap(self):
        half = pr_size.compute([stat("Sources/Foo.swift", 100), stat("Tests/FooTests.swift", 100)])
        heavy = pr_size.compute([stat("Sources/Foo.swift", 100), stat("Tests/FooTests.swift", 900)])
        self.assertGreaterEqual(heavy["cognitive_score"], half["volume"] * 0.75 - 1e-4)
        self.assertLess(heavy["cognitive_score"], half["cognitive_score"])

    def test_exclude_patterns_skip_generated_files(self):
        r = pr_size.compute([stat("Sources/Foo.swift", 10), stat("Generated/Strings.swift", 5000),
                             stat("Package.resolved", 50)], exclude=["Generated/*", "Package.resolved"])
        self.assertEqual((r["additions"], r["files"]), (10, 1))

    def test_custom_test_patterns_replace_the_defaults(self):
        r = pr_size.compute([stat("Sources/Foo.swift", 100), stat("Tests/FooTests.swift", 100),
                             stat("MyChecks/FooCheck.swift", 200)], test_patterns=["MyChecks/*"])
        self.assertEqual((r["test_files"], r["test_additions"], r["additions"]), (1, 200, 200))

    def test_empty_test_patterns_treat_everything_as_production(self):
        r = pr_size.compute([stat("Tests/FooTests.swift", 10)], test_patterns=[])
        self.assertEqual((r["test_files"], r["files"]), (0, 1))

    def test_mode_only_changes_are_dropped_and_binaries_kept(self):
        r = pr_size.compute([stat("Sources/Foo.swift", 10), stat("script.sh", 0, 0),
                             stat("docs/diagram.png", 0, 0, binary=True)])
        self.assertEqual(r["files"], 2)

    def test_bands(self):
        self.assertEqual([pr_size.band(x) for x in (4.99, 5.0, 9.99, 10.0, 17.99, 18.0)],
                         ["small", "medium", "medium", "large", "large", "oversized"])

    def test_empty_diff(self):
        r = pr_size.compute([])
        self.assertEqual((r["cognitive_score"], r["band"]), (0.0, "small"))


if __name__ == "__main__":
    unittest.main()

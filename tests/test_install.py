"""Tests for install.sh: it links this repository's skills, agents and instructions into each harness it detects,
exits 0 when it succeeds, changes nothing in a dry run, moves a real file in its way aside instead of deleting it,
leaves every skill it does not own alone, and uninstalls only its own links. Each test runs it against a temporary
home and root, never the real ones. Run: python3 -m unittest discover -s tests"""

import os
import pathlib
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
INSTALL = REPO / "install.sh"
SKILLS = sorted(path.name for path in (REPO / "skills").iterdir() if (path / "SKILL.md").is_file())


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.directory.name)
        self.home = base / "home"
        self.root = base / "root"
        # Claude Code is present; Codex and Copilot are not, and PATH below holds none of their CLIs.
        (self.home / ".claude").mkdir(parents=True)

    def tearDown(self):
        self.directory.cleanup()

    def install(self, *arguments):
        """Runs install.sh against the temporary home and root; returns the finished process."""
        environment = {"HOME": str(self.home), "AGENT_HARNESS_ROOT": str(self.root), "PATH": "/usr/bin:/bin"}
        return subprocess.run(
            ["bash", str(INSTALL), *arguments], env=environment, capture_output=True, text=True, timeout=120)

    def assertLinks(self, link, target):
        self.assertTrue(link.is_symlink(), f"{link} is not a link")
        self.assertEqual(pathlib.Path(os.readlink(link)).resolve(), pathlib.Path(target).resolve())

    def test_an_install_links_everything_and_exits_0(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in SKILLS:
            with self.subTest(skill=name):
                self.assertLinks(self.root / "skills" / name, REPO / "skills" / name)
        self.assertLinks(self.root / "AGENTS.md", REPO / "AGENTS.md")
        self.assertEqual(os.readlink(self.root / "CLAUDE.md"), "AGENTS.md")
        self.assertLinks(self.home / ".claude" / "skills", self.root / "skills")
        self.assertLinks(self.home / ".claude" / "agents", self.root / "agents" / "claude")
        self.assertLinks(self.home / ".claude" / "CLAUDE.md", self.root / "CLAUDE.md")
        self.assertFalse((self.home / ".codex").exists())
        self.assertFalse((self.home / ".copilot").exists())

    def test_work_is_linked_at_a_stable_path_and_runs_from_it(self):
        self.assertEqual(self.install().returncode, 0)
        work = self.root / "bin" / "work"
        self.assertLinks(work, REPO / "skills" / "planner" / "scripts" / "work.py")
        state = pathlib.Path(self.directory.name) / "state"
        environment = {"HOME": str(self.home), "PATH": "/usr/bin:/bin", "AGENT_WORK_HOME": str(state)}
        # A load limit no machine reaches, so the job starts however busy the machine is.
        subprocess.run([str(work), "settings", "--load-factor", "1000", "--idle-min", "0",
                        "--memory-limit", "off"], env=environment, capture_output=True,
                       timeout=120, check=True)
        ran = subprocess.run([str(work), "run", "--", "echo", "linked"], env=environment, capture_output=True,
                             text=True, timeout=120, cwd=self.directory.name)
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self.assertIn("linked", ran.stdout)

    def test_a_dry_run_exits_0_and_changes_nothing(self):
        result = self.install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("dry run", result.stdout)
        self.assertFalse(self.root.exists())
        self.assertEqual(list((self.home / ".claude").iterdir()), [])

    def test_skills_it_does_not_own_are_left_alone(self):
        own = self.root / "skills" / "company-skill"
        own.mkdir(parents=True)
        (own / "SKILL.md").write_text("company rules\n")
        elsewhere = self.root / "skills" / "linked-skill"
        elsewhere.symlink_to(self.home)

        result = self.install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((own / "SKILL.md").read_text(), "company rules\n")
        self.assertLinks(elsewhere, self.home)
        self.assertFalse((self.root / "skills" / "company-skill.bak").exists())

    def test_a_real_file_or_folder_in_the_way_is_moved_aside_not_deleted(self):
        instructions = self.home / ".claude" / "CLAUDE.md"
        instructions.write_text("my own instructions\n")
        clash = self.root / "skills" / SKILLS[0]
        clash.mkdir(parents=True)
        (clash / "notes.md").write_text("kept\n")

        result = self.install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.home / ".claude" / "CLAUDE.md.bak").read_text(), "my own instructions\n")
        self.assertEqual((self.root / "skills" / f"{SKILLS[0]}.bak" / "notes.md").read_text(), "kept\n")
        self.assertLinks(instructions, self.root / "CLAUDE.md")
        self.assertLinks(clash, REPO / "skills" / SKILLS[0])

    def test_a_second_install_changes_nothing_and_moves_nothing_aside(self):
        self.assertEqual(self.install().returncode, 0)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([path.name for path in self.root.rglob("*.bak")], [])
        self.assertEqual([path.name for path in self.home.rglob("*.bak")], [])

    def test_uninstall_removes_only_its_own_links(self):
        self.assertEqual(self.install().returncode, 0)
        other = self.home / ".claude" / "settings.json"
        other.write_text("{}\n")

        result = self.install("--uninstall")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("skills", "agents", "CLAUDE.md"):
            self.assertFalse((self.home / ".claude" / name).exists(), name)
        self.assertEqual(other.read_text(), "{}\n")
        self.assertTrue((self.root / "skills").is_dir())
        self.assertTrue((self.root / "bin" / "work").is_symlink(), "the root, work included, is left in place")

    def test_an_unknown_option_exits_2(self):
        result = self.install("--frobnicate")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()

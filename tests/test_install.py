"""Tests for install.sh: it links this repository's skills, agents and instructions into each harness it detects,
exits 0 when it succeeds, changes nothing in a dry run, moves a real file in its way aside instead of deleting it,
leaves every skill it does not own alone, and uninstalls only its own links. Each test runs it against a temporary
home and root, never the real ones. Run: python3 -m unittest discover -s tests"""

import json
import os
import pathlib
import subprocess
import tempfile
import time
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
INSTALL = REPO / "install.sh"
SKILLS = sorted(path.name for path in (REPO / "skills").iterdir() if (path / "SKILL.md").is_file())


class InstallCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.directory.name)
        self.home = base / "home"
        self.root = base / "root"
        # Claude Code is present; Codex and Copilot are not, and PATH below holds none of their CLIs.
        (self.home / ".claude").mkdir(parents=True)

    def tearDown(self):
        self.directory.cleanup()

    def install(self, *arguments, extra=None, script=INSTALL, third_party=False):
        """Runs install.sh against the temporary home and root; returns the finished process. The Xcode export and
        the submodule fetch are skipped unless a test asks for them, so a test never reaches Xcode or the network."""
        extra = dict(extra or {})
        for key in ("HOME", "AGENT_HARNESS_ROOT"):
            if key in extra:
                raise AssertionError(f"a test must not set {key}: install.sh would write outside the temporary home")
        environment = {"HOME": str(self.home), "AGENT_HARNESS_ROOT": str(self.root), "PATH": "/usr/bin:/bin"}
        environment.update(extra)
        skipped = [] if third_party else ["--skip-third-party"]
        return subprocess.run(
            ["bash", str(script), *skipped, *arguments], env=environment, capture_output=True, text=True, timeout=120)

    def assertLinks(self, link, target):
        self.assertTrue(link.is_symlink(), f"{link} is not a link")
        self.assertEqual(pathlib.Path(os.readlink(link)).resolve(), pathlib.Path(target).resolve())


class InstallTests(InstallCase):
    def test_a_test_cannot_point_install_at_the_real_home(self):
        with self.assertRaises(AssertionError):
            self.install(extra={"HOME": os.path.expanduser("~")})
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
        self.assertFalse((self.home / ".vibe").exists())
        self.assertFalse((self.home / ".gemini").exists())
        self.assertFalse((self.home / ".config" / "opencode").exists())
        self.assertFalse((self.home / ".pi").exists())
        self.assertFalse((self.home / ".copilot").exists())

    def test_all_detected_harnesses_and_shared_agents_dir_are_linked_and_uninstalled(self):
        for rel in (".codex", ".vibe", ".gemini/antigravity-cli", ".config/opencode", ".pi", ".copilot", ".agents"):
            (self.home / rel).mkdir(parents=True, exist_ok=True)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLinks(self.home / ".codex" / "skills", self.root / "skills")
        self.assertLinks(self.home / ".codex" / "agents", self.root / "agents" / "codex")
        self.assertLinks(self.home / ".codex" / "AGENTS.md", self.root / "AGENTS.md")
        self.assertLinks(self.home / ".vibe" / "skills", self.root / "skills")
        self.assertLinks(self.home / ".vibe" / "agents", self.root / "agents" / "vibe")
        self.assertLinks(self.home / ".vibe" / "AGENTS.md", self.root / "AGENTS.md")
        self.assertLinks(self.home / ".gemini" / "config" / "skills", self.root / "skills")
        self.assertLinks(self.home / ".gemini" / "config" / "agents", self.root / "agents" / "agy")
        self.assertLinks(self.home / ".gemini" / "AGENTS.md", self.root / "AGENTS.md")
        self.assertLinks(self.home / ".config" / "opencode" / "skills", self.root / "skills")
        self.assertLinks(self.home / ".config" / "opencode" / "agents", self.root / "agents" / "opencode")
        self.assertLinks(self.home / ".config" / "opencode" / "AGENTS.md", self.root / "AGENTS.md")
        self.assertLinks(self.home / ".pi" / "agent" / "skills", self.root / "skills")
        self.assertLinks(self.home / ".pi" / "agent" / "AGENTS.md", self.root / "AGENTS.md")
        self.assertFalse((self.home / ".pi" / "agent" / "agents").exists())
        self.assertLinks(self.home / ".agents" / "skills", self.root / "skills")

        uninstall = self.install("--uninstall")
        self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)
        self.assertFalse((self.home / ".gemini" / "AGENTS.md").exists())
        self.assertFalse((self.home / ".gemini" / "config" / "skills").exists())
        self.assertFalse((self.home / ".gemini" / "config" / "agents").exists())
        self.assertFalse((self.home / ".vibe" / "agents").exists())
        self.assertFalse((self.home / ".agents" / "skills").exists())

    def test_wait_and_chat_are_linked_at_a_stable_path_and_run_from_it(self):
        self.assertEqual(self.install().returncode, 0)
        wait, chat = self.root / "bin" / "wait", self.root / "bin" / "chat"
        self.assertLinks(wait, REPO / "tools" / "wait.py")
        self.assertLinks(chat, REPO / "tools" / "chat.py")
        environment = {"HOME": str(self.home), "PATH": "/usr/bin:/bin", "CHAT_HOME": str(self.home / "chat"),
                       "CHAT_ANCHOR_PID": str(os.getpid())}
        ran = subprocess.run([str(wait), "--run", "--", "echo", "linked"], env=environment, capture_output=True,
                             text=True, timeout=120, cwd=self.directory.name)
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self.assertIn("linked", ran.stdout)
        hello = subprocess.run([str(chat), "hello"], env=environment, capture_output=True, text=True, timeout=120)
        self.assertEqual(hello.returncode, 0, hello.stdout + hello.stderr)

    def test_a_link_to_the_removed_work_tool_is_dropped(self):
        (self.root / "bin").mkdir(parents=True)
        (self.root / "bin" / "work").symlink_to(REPO / "skills" / "planner" / "scripts" / "work.py")
        self.assertEqual(self.install().returncode, 0)
        self.assertFalse((self.root / "bin" / "work").is_symlink())

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
        kept = list((self.root / "backups").glob(f"{SKILLS[0]}.*"))
        self.assertEqual(len(kept), 1, "a skill's backup goes beside the skills root, where no harness loads it")
        self.assertEqual((kept[0] / "notes.md").read_text(), "kept\n")
        self.assertFalse((self.root / "skills" / f"{SKILLS[0]}.bak").exists())
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
        self.assertTrue((self.root / "bin" / "wait").is_symlink(), "the root, wait and chat included, is left in place")

    def test_an_unknown_option_exits_2(self):
        result = self.install("--frobnicate")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.root.exists())


FAKE_EXPORTER = """#!/bin/sh
# Stands in for `xcrun mcpbridge run-agent skills export`: writes the skills named in $FAKE_XCODE_SKILLS.
while [ $# -gt 0 ]; do
  case "$1" in --output-dir) out="$2"; shift 2 ;; *) shift ;; esac
done
[ -n "$FAKE_XCODE_FAIL" ] && exit 1
[ -n "$FAKE_XCODE_HANG" ] && exec sleep 30
mkdir -p "$out"
for name in $FAKE_XCODE_SKILLS; do
  mkdir -p "$out/$name"; printf -- '---\nname: %s\ndescription: x\n---\n' "$name" > "$out/$name/SKILL.md"
done
"""


class ThirdPartySkillTests(InstallCase):
    """The Xcode skill pack and the submodule skills: fetched, exported, linked, and never shipped in this repository."""

    def exporter(self):
        path = pathlib.Path(self.directory.name) / "export.sh"
        path.write_text(FAKE_EXPORTER)
        path.chmod(0o755)
        return str(path)

    def run_xcode(self, skills, **extra):
        environment = {"AGENT_HARNESS_XCODE_EXPORT": self.exporter(), "FAKE_XCODE_SKILLS": skills}
        environment.update(extra)
        return self.install("--skip-submodules", extra=environment, third_party=True)

    def xcode_links(self):
        skills = self.root / "skills"
        return sorted(p.name for p in skills.iterdir() if p.is_symlink() and "xcode-skills" in os.readlink(p))

    def test_the_xcode_pack_is_exported_but_not_linked_as_skills(self):
        result = self.run_xcode("swiftui-specialist device-interaction")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("swiftui-specialist", "device-interaction"):
            self.assertTrue((self.root / "xcode-skills" / name / "SKILL.md").is_file())
        self.assertEqual(self.xcode_links(), [])
        self.assertIn("2 Xcode skills exported", result.stdout)

    def test_links_into_the_export_from_an_earlier_install_are_removed(self):
        self.run_xcode("device-interaction")
        (self.root / "skills" / "device-interaction").symlink_to(self.root / "xcode-skills" / "device-interaction")
        self.run_xcode("device-interaction")
        self.assertEqual(self.xcode_links(), [])

    def test_a_skill_that_leaves_the_pack_leaves_the_export(self):
        self.run_xcode("swiftui-specialist device-interaction")
        self.run_xcode("device-interaction")
        self.assertFalse((self.root / "xcode-skills" / "swiftui-specialist").exists())
        self.assertTrue((self.root / "xcode-skills" / "device-interaction").exists())

    def test_a_failed_export_is_skipped_and_the_install_still_succeeds(self):
        result = self.run_xcode("swiftui-specialist", FAKE_XCODE_FAIL="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("the export failed", result.stdout)
        self.assertFalse((self.root / "xcode-skills").exists())

    def test_a_hanging_export_is_stopped_and_the_previous_one_kept(self):
        self.run_xcode("device-interaction")
        started = time.monotonic()
        result = self.run_xcode("device-interaction", FAKE_XCODE_HANG="1", AGENT_HARNESS_XCODE_TIMEOUT="2")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(time.monotonic() - started, 20)
        self.assertIn("did not finish in 2 s", result.stdout)
        self.assertIn("using the previous export", result.stdout)
        self.assertTrue((self.root / "xcode-skills" / "device-interaction" / "SKILL.md").exists())

    def test_a_failed_export_keeps_the_previous_one(self):
        self.run_xcode("device-interaction")
        result = self.run_xcode("device-interaction", FAKE_XCODE_FAIL="1")
        self.assertIn("using the previous export", result.stdout)
        self.assertTrue((self.root / "xcode-skills" / "device-interaction" / "SKILL.md").exists())

    def test_skip_xcode_does_not_export(self):
        result = self.install("--skip-submodules", "--skip-xcode", extra={"AGENT_HARNESS_XCODE_EXPORT": "/nonexistent"},
                              third_party=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Exporting", result.stdout)

    def test_a_dry_run_names_the_export_and_runs_nothing(self):
        result = self.install("--dry-run", "--skip-submodules", extra={"AGENT_HARNESS_XCODE_EXPORT": "/nonexistent"},
                              third_party=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("would run: /nonexistent --output-dir", result.stdout)
        self.assertFalse((self.root / "xcode-skills").exists())

    def make_checkout(self):
        """A copy of this repository's installer in a git checkout whose submodule has not been fetched."""
        base = pathlib.Path(self.directory.name)
        # Only the variables git needs; never a copy of the real environment, whose HOME is the user's home.
        git_environment = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_COUNT": "1",
                           "GIT_CONFIG_KEY_0": "protocol.file.allow", "GIT_CONFIG_VALUE_0": "always"}
        git_run_environment = dict(git_environment, HOME=str(self.home), PATH="/usr/bin:/bin")

        def git(directory, *arguments):
            subprocess.run(["git", "-C", str(directory), *arguments], env=git_run_environment, check=True,
                           capture_output=True, text=True)

        upstream = base / "upstream"
        (upstream / "skills" / "audit").mkdir(parents=True)
        (upstream / "skills" / "audit" / "SKILL.md").write_text("---\nname: audit\ndescription: x\n---\n")
        (upstream / "big").mkdir()
        (upstream / "big" / "file.bin").write_text("not a skill")
        git(upstream, "init", "-q", "-b", "main")
        git(upstream, "add", "-A")
        git(upstream, "commit", "-q", "-m", "upstream")
        source = base / "source"
        (source / "skills" / "demo").mkdir(parents=True)
        (source / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\ndescription: x\n---\n")
        (source / "third_party").mkdir()
        (source / "third_party" / "SKILLS").write_text("# comment\nthird_party/up|skills/audit\n")
        (source / "AGENTS.md").write_text("x")
        (source / "install.sh").write_text(INSTALL.read_text())
        git(source, "init", "-q", "-b", "main")
        git(source, "submodule", "add", "-q", str(upstream), "third_party/up")
        git(source, "add", "-A")
        git(source, "commit", "-q", "-m", "source")
        clone = base / "clone"
        subprocess.run(["git", "clone", "-q", str(source), str(clone)], env=git_run_environment, check=True)
        return clone, git_environment

    def test_a_submodule_skill_is_fetched_shallow_with_only_its_directory_and_linked(self):
        clone, git_environment = self.make_checkout()
        self.assertFalse((clone / "third_party" / "up" / "skills").exists())
        result = self.install("--skip-xcode", script=clone / "install.sh", extra=git_environment, third_party=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLinks(self.root / "skills" / "audit", clone / "third_party" / "up" / "skills" / "audit")
        self.assertFalse((clone / "third_party" / "up" / "big").exists(), "only the skill directory is checked out")
        again = self.install("--skip-xcode", script=clone / "install.sh", extra=git_environment, third_party=True)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)

    def test_skip_submodules_leaves_the_submodule_alone(self):
        clone, git_environment = self.make_checkout()
        result = self.install("--skip-submodules", "--skip-xcode", script=clone / "install.sh", extra=git_environment,
                              third_party=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / "skills" / "audit").exists())
        self.assertFalse((clone / "third_party" / "up" / "skills").exists())

    def test_a_download_without_git_names_the_missing_submodule_and_still_installs(self):
        clone, git_environment = self.make_checkout()
        subprocess.run(["rm", "-rf", str(clone / ".git")], check=True)
        result = self.install("--skip-xcode", script=clone / "install.sh", extra=git_environment, third_party=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("not a git checkout", result.stdout)
        self.assertLinks(self.root / "skills" / "demo", clone / "skills" / "demo")


if __name__ == "__main__":
    unittest.main()

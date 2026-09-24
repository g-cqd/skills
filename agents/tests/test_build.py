"""Tests for agents/build.py: every source renders for every harness, the generated files are current, and a source
that names something missing is refused. Run: python3 -m unittest discover -s agents/tests"""

import pathlib
import subprocess
import sys
import tempfile
import tomllib
import unittest

AGENTS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENTS))

import build  # noqa: E402

NAMES = {"scout", "test-runner", "worker"}


def meta(**fields):
    """A valid source's frontmatter, with `fields` replacing or adding keys."""
    base = {"name": "worker", "tier": "standard", "tools": ["read", "search"], "description": "Does work."}
    base.update(fields)
    return base


def frontmatter(text):
    """The YAML frontmatter lines of a rendered Markdown agent."""
    return text.split("---\n")[1].splitlines()


class GeneratedFilesTests(unittest.TestCase):
    def test_the_generated_files_are_current(self):
        result = subprocess.run(
            [sys.executable, str(AGENTS / "build.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_codex_file_is_valid_toml_with_its_prompt(self):
        for path in sorted((AGENTS / "codex").glob("*.toml")):
            with self.subTest(path.name):
                agent = tomllib.loads(path.read_text())
                self.assertEqual(agent["name"], path.stem)
                self.assertIn("You are the", agent["developer_instructions"])

    def test_every_claude_agent_names_its_model_and_effort(self):
        for path in sorted((AGENTS / "claude").glob("*.md")):
            with self.subTest(path.name):
                lines = frontmatter(path.read_text())
                self.assertTrue(any(line.startswith("model: ") for line in lines))
                self.assertTrue(any(line.startswith("effort: ") for line in lines))

    def test_every_source_has_the_same_agent_in_all_three_harnesses(self):
        sources = {path.stem for path in (AGENTS / "src").glob("*.md")}
        self.assertEqual({path.stem for path in (AGENTS / "claude").glob("*.md")}, sources)
        self.assertEqual({path.name.removesuffix(".agent.md") for path in (AGENTS / "copilot").glob("*.md")}, sources)
        self.assertEqual({path.stem for path in (AGENTS / "codex").glob("*.toml")}, sources)


class RenderTests(unittest.TestCase):
    def test_a_readonly_shell_is_guarded_on_claude_and_absent_on_copilot(self):
        agent = meta(tools=["read", "search", "shell-readonly"])
        claude = build.render_claude(agent, "Body.\n")
        self.assertIn("tools: Read, Grep, Glob, Bash", claude)
        self.assertIn("readonly-bash.py", claude)
        self.assertIn('tools: ["read", "search"]', build.render_copilot(agent, "Body.\n"))
        codex = tomllib.loads(build.render_codex(agent, "Body.\n"))
        self.assertEqual(codex["sandbox_mode"], "read-only")
        self.assertIn("nothing but you enforces", codex["developer_instructions"])

    def test_a_full_shell_has_no_guard(self):
        agent = meta(tools=["read", "shell", "edit"])
        self.assertNotIn("hooks:", build.render_claude(agent, "Body.\n"))
        self.assertIn('"execute"', build.render_copilot(agent, "Body.\n"))
        codex = tomllib.loads(build.render_codex(agent, "Body.\n"))
        self.assertEqual(codex["sandbox_mode"], "workspace-write")
        self.assertNotIn("nothing but you enforces", codex["developer_instructions"])

    def test_all_with_a_denial_inherits_every_tool_but_the_denied_ones(self):
        agent = meta(tools=["all"], deny=["edit"])
        claude = frontmatter(build.render_claude(agent, "Body.\n"))
        self.assertFalse(any(line.startswith("tools:") for line in claude))
        self.assertIn("disallowedTools: Edit, Write, NotebookEdit", claude)
        copilot = build.render_copilot(agent, "Body.\n")
        self.assertIn('"execute"', copilot)
        self.assertIn('"agent"', copilot)
        self.assertNotIn('"edit"', copilot)

    def test_spawns_become_the_agent_allowlist(self):
        agent = meta(tools=["read", "agents"], spawns=["scout", "test-runner"])
        self.assertIn("tools: Read, Agent(scout, test-runner)", build.render_claude(agent, "Body.\n"))
        self.assertIn('"agent"', build.render_copilot(agent, "Body.\n"))

    def test_a_turn_budget_is_claudes_limit_and_every_harness_prompt(self):
        agent = meta(max_turns="12")
        claude = build.render_claude(agent, "Body.\n")
        self.assertIn("maxTurns: 12", frontmatter(claude))
        self.assertIn("Finish within 12 turns", claude)
        self.assertIn("Finish within 12 turns", build.render_copilot(agent, "Body.\n"))
        self.assertIn("Finish within 12 turns", tomllib.loads(build.render_codex(agent, "Body.\n"))["developer_instructions"])

    def test_each_harness_takes_its_tiers_model_and_effort(self):
        for tier in ("micro", "economy", "standard", "reasoning", "frontier"):
            with self.subTest(tier):
                agent = meta(tier=tier)
                expected = build.TIERS[tier]
                claude = frontmatter(build.render_claude(agent, "Body.\n"))
                self.assertIn(f"model: {expected['claude']['model']}", claude)
                self.assertIn(f"effort: {expected['claude']['effort']}", claude)
                copilot = frontmatter(build.render_copilot(agent, "Body.\n"))
                self.assertIn(f"model: \"{expected['copilot']['model']}\"", copilot)
                self.assertIn(f"reasoningEffort: {expected['copilot']['effort']}", copilot)
                codex = tomllib.loads(build.render_codex(agent, "Body.\n"))
                self.assertEqual(codex["model"], expected["codex"]["model"])
                self.assertEqual(codex["model_reasoning_effort"], expected["codex"]["effort"])

    def test_an_agents_effort_replaces_its_tiers_everywhere(self):
        agent = meta(tier="micro", effort="max")
        self.assertIn("effort: max", frontmatter(build.render_claude(agent, "Body.\n")))
        self.assertIn("reasoningEffort: max", frontmatter(build.render_copilot(agent, "Body.\n")))
        self.assertEqual(tomllib.loads(build.render_codex(agent, "Body.\n"))["model_reasoning_effort"], "max")

    def test_claude_extras_render_when_set(self):
        agent = meta(skills=["testing", "debugging"], color="pink", background="true")
        claude = build.render_claude(agent, "Body.\n")
        self.assertIn("skills:\n  - testing\n  - debugging", claude)
        self.assertIn("color: pink", claude)
        self.assertIn("background: true", claude)

    def test_a_prompt_keeps_backslashes_and_quotes_in_codex(self):
        body = "Run `find . -exec true {} \\;` and say \"\"\"done\"\"\" or '''done'''.\n"
        codex = tomllib.loads(build.render_codex(meta(), body))
        self.assertIn(body.strip(), codex["developer_instructions"])


class ValidationTests(unittest.TestCase):
    def assertRefused(self, agent, fragment):
        with self.assertRaises(ValueError) as caught:
            build.validate(agent, "worker.md", NAMES)
        self.assertIn(fragment, str(caught.exception))

    def test_a_valid_source_passes(self):
        build.validate(meta(tools=["read", "agents"], spawns=["scout"], skills=["testing"]), "worker.md", NAMES)

    def test_every_refusal(self):
        cases = [
            (meta(tier="huge"), "unknown tier"),
            (meta(tier="_comment"), "unknown tier"),
            (meta(tools=["read", "telepathy"]), "unknown capabilities"),
            (meta(tools=["shell", "shell-readonly"]), "exclude each other"),
            (meta(tools=["read", "all"]), "'all' stands alone"),
            (meta(deny=["edit"]), "'all' stands alone"),
            (meta(tools=["all"], deny=["telepathy"]), "unknown capabilities"),
            (meta(spawns=["scout"]), "needs the 'agents' capability"),
            (meta(tools=["agents"], spawns=["ghost"]), "spawns unknown agents"),
            (meta(skills=["no-such-skill"]), "unknown skills"),
            (meta(effort="extreme"), "unknown effort"),
            (meta(color="teal"), "unknown color"),
            (meta(max_turns="0"), "positive integer"),
            (meta(max_turns="ten"), "positive integer"),
            (meta(background="yes"), "true or false"),
        ]
        for agent, fragment in cases:
            with self.subTest(fragment=fragment, agent=agent):
                self.assertRefused(agent, fragment)

    def test_a_missing_required_key_is_refused(self):
        for key in ("name", "tier", "tools", "description"):
            agent = meta()
            del agent[key]
            with self.subTest(key):
                self.assertRefused(agent, f"missing '{key}'")


class CheckTests(unittest.TestCase):
    def test_check_names_missing_stale_and_extra_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for harness in ("claude", "copilot", "codex"):
                (root / harness).mkdir()
            (root / "claude" / "a.md").write_text("old")
            (root / "claude" / "gone.md").write_text("x")
            (root / "claude" / "hooks").mkdir()
            (root / "claude" / "hooks" / "guard.py").write_text("hand-written, not generated")
            files = {"claude/a.md": "new", "codex/b.toml": "x"}
            self.assertEqual(
                build.check(files, root),
                ["missing  codex/b.toml", "stale    claude/a.md", "extra    claude/gone.md"])
            self.assertEqual(build.check({"claude/a.md": "old", "claude/gone.md": "x"}, root), [])


class ParseTests(unittest.TestCase):
    def test_lists_and_folded_descriptions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "worker.md"
            path.write_text(
                "---\nname: worker\ntier: micro\ntools: read, search ,shell\nspawns: scout\n"
                "description: >\n  Does\n  work.\n---\n\nBody.\n")
            parsed, body = build.parse(path)
        self.assertEqual(parsed["tools"], ["read", "search", "shell"])
        self.assertEqual(parsed["spawns"], ["scout"])
        self.assertEqual(parsed["description"], "Does work.")
        self.assertEqual(body, "Body.\n")


if __name__ == "__main__":
    unittest.main()

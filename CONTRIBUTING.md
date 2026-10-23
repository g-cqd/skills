# Contributing

This repository is a set of instructions that agents read (skills, agent definitions, `AGENTS.md`) and two small
tools. A change is good when an agent that follows the new text does the right thing, and when the checks below pass.

## Before you start

- Read `docs/AUTHORING.md`. It holds the rules for descriptions, wording, tiers, boundaries, and portability. A change
  to a skill, an agent, or `AGENTS.md` must follow its plain-language rules.
- Keep one concern per skill. If two skills would load for the same message and disagree, merge them or redraw the
  boundary.
- Keep a change small and about one thing.

## Change a skill

1. Edit `skills/<name>/SKILL.md`. Keep it under 500 lines: put long catalogs in `references/`.
2. Add or update `skills/<name>/evals/evals.json`: a prompt, the expected output, and the expectations a grader can
   check. Cover the main trigger and a near miss.
3. Run `python3 skills/skill-creator/scripts/quick_validate.py skills/<name>` (it needs PyYAML:
   `python3 -m pip install pyyaml`).

## Change an agent

1. Edit `agents/src/<name>.md`, never a generated file.
2. Run `python3 agents/build.py`, then `python3 agents/build.py --check`. Commit the generated files with the source.
3. Model names and effort live only in `agents/tiers.json`.

## Change a tool

1. Edit `tools/wait.py` or `tools/chat.py`. Both use only the Python standard library and must run on Python 3.9. The tests of `agents/build.py` need Python 3.11 or later.
2. Write the test first, and watch it fail. The tests in `tools/tests/` start real processes and use temporary
   directories; follow their style.
3. Update `docs/tools.md` when behaviour changes.

## Run the checks

Run these from the repository root. CI runs the same commands.

```bash
python3 agents/build.py --check
python3 -m unittest discover -s tests
python3 -m unittest discover -s agents/tests
python3 -m unittest discover -s tools/tests
python3 -m unittest discover -s skills/simplification/scripts/tests
python3 -m unittest discover -s skills/secure-coding/scripts/tests
for skill in skills/*; do python3 skills/skill-creator/scripts/quick_validate.py "$skill" || exit 1; done
```

## Change a third-party skill

REA's `reverse-engineer-anything` skill is a git submodule in `third_party/`, pinned to the `rea-agents` release tag
that the MCP configuration runs. Do not edit them here: send the change to their repositories. To move a pin, check out the new
commit inside the submodule, run `python3 -m unittest discover -s tests`, and commit the changed pointer. To add
another submodule skill, add the submodule and one line to `third_party/SKILLS` (`<submodule path>|<skill directory>`).
Apple's Xcode skill pack is never stored here: `install.sh` exports it from Xcode.

## Commits and pull requests

- Write a commit title that says what changed and why it matters, in the imperative ("Make wait stop its child group
  on a timeout"). Keep a commit to one change.
- Say in the pull request which checks you ran and what you did not test.
- Do not commit generated files without their source, or the reverse.

## License

By contributing you agree that your contribution is released under the MIT license in `LICENSE`. Do not add content
that you did not write unless its license allows it; record it in `THIRD-PARTY-NOTICES.md`.

---
name: skill-creator
description: >-
  Language-agnostic: create, update, install, review, and evaluate agent skills across
  tools. Use to turn a workflow into a skill, improve descriptions, fix missed or
  excessive triggering, or resolve overlapping skills. For routing requests to existing
  skills, use `planner`; for project documentation, use `work-docs`.
---

# Skill Creator

Create, test, improve, install, and manage agent skills. Skills follow the [Agent Skills](https://agentskills.io) open standard — portable across 30+ AI tools.

## Contract

```
§DESCRIPTION description ∷ retrieval-key ¬summary
          ! concern + coverage + triggers + negative-boundary
§SELF     SKILL.md ! actionable ∅opening-a-reference
          deep-refs ⇒ long-tail-catalogs only
§ONE      1 skill ∷ 1 concern ⇒ overlap ⇒ merge ∨ redraw-boundary
§MUTUAL   "not for X, use Y" ⇒ Y ! states the mirror
§TEST     ? triggering ∀eval BEFORE claiming a skill works
§BAN      description that could equally describe a neighbour ·
          trigger-term lost in a merge · skill ∅negative-boundary
```

## Quick Decision Tree

| User Intent | Action |
|-------------|--------|
| "Create a skill for X" / "Turn this into a skill" | → [Create a Skill](#creating-a-skill) |
| "Improve/update this skill" | → [Improve a Skill](#improving-a-skill) |
| "Test this skill" / "Run evals" | → [Test & Evaluate](#testing-and-evaluating) |
| "Optimize the description" | → [Description Optimization](#description-optimization) |
| "Install a skill" / "List available skills" | → [Install Skills](#installing-skills) |
| "Review this skill" / "Audit quality" | → [Review Checklist](#review-checklist) |

For the full specification (frontmatter fields, structure rules, cross-platform compatibility), see `references/specification.md`.

For design patterns (sequential workflow, multi-MCP, iterative refinement, domain intelligence), see `references/patterns.md`.

---

## Creating a Skill

### 1. Capture Intent

Understand what the skill should do. If the conversation already contains a workflow ("turn this into a skill"), extract: tools used, step sequence, corrections made, input/output formats.

Clarify:
- What should this skill enable the agent to do?
- When should it trigger? (what user phrases/contexts)
- What's the expected output format?
- Should we set up test cases? (yes for objectively verifiable output; optional for subjective)

### 2. Interview and Research

Ask about edge cases, input/output formats, example files, success criteria, and dependencies. Check available MCPs for research. Come prepared with context.

### 3. Write the SKILL.md

**Anatomy:**
```
skill-name/
├── SKILL.md              # Required — instructions + YAML frontmatter
├── scripts/              # Optional — deterministic/repetitive tasks
├── references/           # Optional — docs loaded on demand
└── assets/               # Optional — templates, icons, fonts
```

**Frontmatter** — the triggering mechanism (see `references/specification.md` for all fields):
<example>
```yaml
---
name: my-skill
description: What it does. Use when user says X, mentions Y, or needs Z.
---
```
The description leads with the concern, then names the situations that should load it, because it is the only text the harness reads when deciding whether to load the skill.
</example>

Keep the parsed description at 1–1,024 characters, targeting at most 500 for this set.
Use `>-` for wrapped YAML without a trailing newline. Preserve the main triggers and a useful
negative boundary; keep detailed API lists and procedures in the body. Avoid angle brackets,
which the bundled validator rejects. Validate the description after each edit.

**Writing guidelines:**
- Use imperative form in instructions
- Explain **why** things are important — today's LLMs are smart and respond to reasoning better than rigid commands
- Keep SKILL.md under 500 lines; move detailed docs to `references/`
- Include examples to show expected formats
- Be specific and actionable (not "validate the data" but "run `python scripts/validate.py --input {filename}`")
- Reference bundled resources clearly with when-to-read guidance

**Prompting rules for the body** — a SKILL.md is system-prompt text, so it follows the same rules as one:
- Write emphasis in sentence case. Current models follow instructions closely and overtrigger on shouted words (`MUST`, `NEVER`, `CRITICAL`); "use X when …" carries the same weight.
- State each rule with its reason when the reason is not obvious; the model generalises from the motivation, and a bare rule gets applied literally in the wrong places.
- Say what to do, not only what to avoid; a prohibition without an alternative leaves the model to guess it.
- Wrap examples of the model's own output (a sample answer, comment, or artifact) in `<example>` tags, several in `<examples>`, each with a one-line rationale. Code that demonstrates an API stays in a fenced block.
- Formatting rules say when a format is appropriate, not which formats are banned; blanket anti-markdown language suppresses structure the content needs.
- Prefer general instructions ("verify against the spec before finishing") over hand-written reasoning scripts; numbered steps are for procedures whose order matters.
- Where the skill ends in a deliverable, ask for a self-check against a named criterion before finishing.

**Naming:**
- Kebab-case only: `notion-project-setup` not `NotionProjectSetup`
- Verb-led phrases preferred: `fix-issue`, `deploy-app`
- Folder name matches skill name exactly

### 4. Initialize (New Skills)

For a fresh scaffold:
```bash
python scripts/init_skill.py <skill-name> --path <output-directory> [--resources scripts,references,assets]
```

### 5. Validate

```bash
python scripts/quick_validate.py <path/to/skill-folder>
```

Checks: YAML frontmatter format, required fields, naming rules.

---

## Testing and Evaluating

### Core Loop

1. **Spawn runs** — for each test case, launch with-skill AND baseline runs in parallel
2. **Draft assertions** — while runs are in progress, draft quantitative evals
3. **Capture timing** — save `total_tokens` and `duration_ms` from task notifications to `timing.json`
4. **Grade, aggregate, view** — grade assertions, aggregate benchmark, launch the viewer
5. **Read feedback** — collect user feedback, improve, repeat

### Test Cases

Save to `evals/evals.json`:
```json
{
  "skill_name": "my-skill",
  "evals": [
    { "id": 1, "prompt": "User's task prompt", "expected_output": "Description of expected result", "files": [] }
  ]
}
```

See `references/schemas.md` for full schema (including assertions, grading, benchmark formats).

### Running Tests

**With-skill run:** Spawn subagent with skill path + task prompt, save outputs to `workspace/iteration-N/eval-ID/with_skill/outputs/`

**Baseline run:** Same prompt, no skill (or old skill version), save to `without_skill/outputs/`

Launch both in the same turn for each test case.

### Grading and Viewing

1. Grade each run using `agents/grader.md` — save `grading.json` (fields: `text`, `passed`, `evidence`)
2. Aggregate: `python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>`
3. Analyze: read `agents/analyzer.md` for patterns (non-discriminating assertions, high variance, time/token tradeoffs)
4. Launch viewer:
   ```bash
   python eval-viewer/generate_review.py <workspace>/iteration-N --skill-name "name" --benchmark <workspace>/iteration-N/benchmark.json
   ```
   For iteration 2+: add `--previous-workspace <workspace>/iteration-<N-1>`

### Three Testing Dimensions (from Anthropic's Guide)

**1. Triggering tests** — does the skill load at the right times?
- Triggers on obvious tasks
- Triggers on paraphrased requests
- Doesn't trigger on unrelated topics

**2. Functional tests** — does it produce correct outputs?
- Valid outputs generated
- API/tool calls succeed
- Error handling works
- Edge cases covered

**3. Performance comparison** — does the skill improve results?
- Compare with-skill vs without-skill: tool calls, tokens, errors, user corrections needed

---

## Improving a Skill

### How to Think About Improvements

1. **Generalize from feedback** — don't overfit to test examples. If a fix only works for one test case, it's not a good fix. Try different metaphors, patterns of working.
2. **Keep the prompt lean** — remove instructions that aren't pulling their weight. Read transcripts to spot unproductive work.
3. **Explain the why** — reasoning beats rigid commands. Help the model understand why something matters.
4. **Look for repeated work** — if all test runs independently wrote similar helper scripts, bundle that script in `scripts/`.

### Iteration Signals

**Undertriggering** (skill doesn't load when it should):
- Add more detail and trigger phrases to description
- Include technical keywords
- Add file type mentions

**Overtriggering** (skill loads for unrelated queries):
- Add negative triggers in sentence case, naming the owner ("Not for X, which is `other-skill`"), so the request has somewhere to go
- Be more specific about scope
- Clarify boundaries with related skills

**Instructions not followed**:
- Keep instructions concise — use bullet points where the items are discrete
- Put the instructions that matter most at the top
- Replace ambiguous language with specific checks, and add the reason where the rule is not self-evident; shouting a rule in caps makes it fire in the wrong places, not more reliably
- Bundle validation scripts for deterministic checks

---

## Description Optimization

The automated pipeline optimizes triggering accuracy using train/test splits.

### Step 1: Generate 20 eval queries (10 should-trigger, 10 should-not)

Queries must be realistic — specific, detailed, with context. Not "Format this data" but a full sentence with file names, backstory, and specifics. Negative cases should be near-misses (adjacent domains, shared keywords), not obviously irrelevant.

### Step 2: Review with user

Present via `assets/eval_review.html` template. User can edit, toggle, add/remove entries.

### Step 3: Run optimization

```bash
python -m scripts.run_loop --eval-set <eval.json> --skill-path <path> --model <model-id> --max-iterations 5 --verbose
```

Splits 60% train / 40% test, evaluates 3x per query, uses extended thinking to propose improvements, selects best by test score.

### Step 4: Apply result

Update SKILL.md frontmatter with `best_description` from output. Show before/after to user.

---

## Installing Skills

### From GitHub
```bash
python scripts/install-skill-from-github.py --repo <owner>/<repo> --path <path/to/skill>
```

### List available skills
```bash
python scripts/list-skills.py                            # curated
python scripts/list-skills.py --path skills/.experimental  # experimental
```

See `references/installing.md` for full options, distribution, and API usage.

After installing: restart the agent to pick up new skills.

---

## Review Checklist

### Structure
- [ ] File named exactly `SKILL.md` (case-sensitive)
- [ ] Folder name is kebab-case, matches `name` field
- [ ] YAML frontmatter has `---` delimiters
- [ ] `name` field is kebab-case, under 64 chars
- [ ] `description` includes what it does AND when to use it
- [ ] No XML angle brackets in frontmatter
- [ ] No README.md inside the skill folder

### Content Quality
- [ ] SKILL.md under 500 lines
- [ ] Instructions are imperative and specific
- [ ] References linked with when-to-read guidance
- [ ] Examples included for expected formats, output examples in `<example>` tags with a rationale
- [ ] Emphasis in sentence case; rules carry their reason; prohibitions name the alternative
- [ ] Error handling for common failure cases
- [ ] No information duplicated between SKILL.md and references

### Description Quality
- [ ] Includes trigger phrases users would actually say
- [ ] Mentions relevant file types
- [ ] Has negative triggers if needed to prevent over-triggering
- [ ] Follows structure: [What it does] + [When to use it] + [Key capabilities]

### Bundled Resources
- [ ] Scripts tested and working
- [ ] References have TOC if >100 lines
- [ ] Assets are actually used in output
- [ ] No extraneous files (CHANGELOG, INSTALLATION_GUIDE, etc.)

---

## Agent Definitions (Subagents)

For grading, comparison, and analysis, read the relevant agent file:
- `agents/grader.md` — evaluate assertions against outputs
- `agents/comparator.md` — blind A/B comparison between two outputs
- `agents/analyzer.md` — analyze why one version beat another

## References

- `references/specification.md` — Agent Skills standard: frontmatter, structure, cross-platform, description writing
- `references/patterns.md` — Skill design patterns: sequential, multi-MCP, iterative, context-aware, domain intelligence
- `references/installing.md` — Installing, distributing, and sharing skills
- `references/schemas.md` — JSON schemas for evals, grading, benchmark, comparison, analysis
- `references/openai_yaml.md` — OpenAI/Codex `agents/openai.yaml` format

## Environment-Specific Notes

**Hosted web UI (no subagents)**: run test cases sequentially yourself. Skip baseline runs and quantitative benchmarking. Present results inline. Skip description optimization (it needs a headless CLI).

**Sandboxed agent (subagents, no browser)**: use `--static <output_path>` for the viewer. Feedback downloads as `feedback.json`.

**Codex**: Generate `agents/openai.yaml` for UI metadata. Use `scripts/init_skill.py` and `scripts/generate_openai_yaml.py`.

## Boundaries

| Need | Skill |
|---|---|
| Routing a request to an existing skill rather than authoring one | `planner` |
| Project documentation, ADRs, release notes | `work-docs` |
| Reviewing the code a skill produces | `code-review` |
| Repository-specific conventions a skill should defer to | `project-conventions` |

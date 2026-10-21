---
name: skill-creator
description: >-
  Language-agnostic: create, update, install, review, and evaluate agent skills across
  tools. Use to turn a workflow into a skill, improve descriptions, fix missed or
  excessive triggering, or resolve overlapping skills. For routing requests to existing
  skills, use `planner`; for project documentation, use `work-docs`.
---

# Skill Creator

Create, test, improve, install, and manage agent skills. Skills follow the [Agent Skills](https://agentskills.io) open standard, which 30+ AI tools read. Paths below (`scripts/`, `agents/`, `references/`, `assets/`, `eval-viewer/`) are relative to this skill's directory.

## Contract

```
§DESCRIPTION description ∷ retrieval-key ¬summary
          ! concern + coverage + triggers + negative-boundary
§SELF     SKILL.md ! actionable ∅opening-a-reference
          deep-refs ⇒ long-tail-catalogs only
§ONE      1 skill ∷ 1 concern ⇒ overlap ⇒ merge ∨ redraw-boundary
§MUTUAL   "not for X, use Y" ⇒ Y ! owns X · Y ¬must cite back
§TEST     ? triggering ∀eval BEFORE claiming a skill works
§BAN      description that could equally describe a neighbour ·
          trigger-term lost in a merge · skill ∅negative-boundary
```

Legend: `§` rule label · `!` must · `?` check · `¬` not · `∅` no · `∀` for each · `∈` in · `∷` is · `∧` and · `∨` or · `⇒` then · `≻` outranks · `→` becomes · `·` separates items. Other symbols read as in mathematics.

## Quick Decision Tree

| User Intent | Action |
|-------------|--------|
| "Create a skill for X" / "Turn this into a skill" | → [Create a Skill](#creating-a-skill) |
| "Improve/update this skill" | → [Improve a Skill](#improving-a-skill) |
| "Test this skill" / "Run evals" | → [Test & Evaluate](#testing-and-evaluating) |
| "Optimize the description" | → [Description Optimization](#description-optimization) |
| "Install a skill" / "List available skills" | → [Install Skills](#installing-skills) |
| "Review this skill" / "Audit quality" | → [Review Checklist](#review-checklist) |

Read `references/specification.md` when you need a frontmatter field other than `name` and `description`, or a cross-platform compatibility rule.

Read `references/patterns.md` when the skill needs a multi-step structure: sequential workflow, multi-MCP coordination, iterative refinement, or domain intelligence.

---

## Creating a Skill

### 1. Capture Intent

If the conversation already contains the workflow ("turn this into a skill"), extract from it: the tools used, the step sequence, the corrections the user made, and the input and output formats.

Get answers to these questions. Take each answer from the conversation first; ask the user only the questions the conversation does not answer:
- What does the skill enable the agent to do?
- Which user phrases and contexts trigger it?
- What is the expected output format?
- Do we set up test cases? Yes for objectively verifiable output; optional for subjective output.

### 2. Interview and Research

Ask about edge cases, input and output formats, example files, success criteria, and dependencies. If an MCP server or documentation tool covers the domain, query it once per open question before asking.

### 3. Write the SKILL.md

**Anatomy:**
```
skill-name/
├── SKILL.md              # Required — instructions + YAML frontmatter
├── scripts/              # Optional — deterministic/repetitive tasks
├── references/           # Optional — docs loaded on demand
└── assets/               # Optional — templates, icons, fonts
```

**Frontmatter** is the triggering mechanism (all fields: `references/specification.md`):
<example>
```yaml
---
name: my-skill
description: What it does. Use when user says X, mentions Y, or needs Z.
---
```
The description leads with the concern, then names the situations that should load it, because it is the only text the harness reads when deciding whether to load the skill.
</example>

Description rules:
- Keep the parsed description at 1–1,024 characters; target at most 500 for this set.
- Use `>-` for wrapped YAML without a trailing newline.
- Keep the main triggers and at least one negative boundary. Put detailed API lists and procedures in the body.
- Do not use angle brackets; the bundled validator rejects them.
- Run the validator (step 5) after each description edit.

**Writing guidelines:**
- Write instructions in the imperative.
- Keep SKILL.md under 500 lines. Keep rules, decision tables, and known failure cases in SKILL.md, because agents rarely open `references/`. Move only long catalogs and code corpora to `references/`.
- Write commands, not goals: not "validate the data" but "run `python scripts/validate.py --input {filename}`".
- Give each reference pointer the condition under which to read the file.

**Prompting rules for the body.** A SKILL.md is system-prompt text and follows the same rules:
- Write emphasis in sentence case. Current models overtrigger on shouted words (`MUST`, `NEVER`, `CRITICAL`); "use X when …" carries the same weight.
- Give a rule its reason only when the reason changes behavior in a case the rule does not name. Use one clause.
- Give each prohibition the allowed action. A prohibition without an alternative leaves the model to guess the alternative.
- Wrap examples of the model's own output (a sample answer, comment, or artifact) in `<example>` tags, several in `<examples>`, each with a one-line rationale. Code that demonstrates an API stays in a fenced block.
- Write formatting rules as when a format is appropriate, not as banned formats. Blanket anti-markdown language suppresses structure the content needs.
- Prefer general instructions ("verify against the spec before finishing") to hand-written reasoning scripts. Use numbered steps only for procedures whose order matters.
- When the skill ends in a deliverable, require a self-check against a named criterion before finishing.

**Naming:**
- Kebab-case only: `notion-project-setup`, not `NotionProjectSetup`.
- Prefer verb-led names: `fix-issue`, `deploy-app`.
- The folder name matches the `name` field exactly.

### 4. Initialize (New Skills)

For a new scaffold:
```bash
python scripts/init_skill.py <skill-name> --path <output-directory> [--resources scripts,references,assets]
```

### 5. Validate

```bash
python scripts/quick_validate.py <path/to/skill-folder>
```

The validator checks the YAML frontmatter format, the required fields, and the naming rules.

---

## Writing style

Write the body in plain language. The repository's `docs/AUTHORING.md` ("Plain-language rules") has the full list when it is available.

- One instruction per sentence, about 20 words, in the imperative and the active voice. One word per concept.
- No metaphors, idioms, filler or hedges. Write "must", "must not" or "may", not "should".
- Scope each "always", "never" and "all" to a condition. Give each loop or search a stop, and each rule a fallback for when it cannot be followed: use an existing repository rule, or "stop and report".
- Give each prohibition the allowed action.
- Replace words such as "large" and "soon" with a number or a test. If none is known, state the criterion in words.
- Read each rule literally and apply it everywhere it can apply. If the result defeats the purpose, add the missing condition.
- Cut what the model already knows.

## Testing and Evaluating

### Core Loop

1. **Spawn runs**: for each test case, launch a with-skill run and a baseline run in parallel.
2. **Draft assertions**: while the runs are in progress, draft quantitative evals.
3. **Capture timing**: save `total_tokens` and `duration_ms` from the task notifications to `timing.json`.
4. **Grade, aggregate, view**: grade the assertions, aggregate the benchmark, launch the viewer.
5. **Read feedback**: collect the user's feedback and improve the skill. Start the next iteration at step 1. Stop when the user accepts the result or gives no further feedback.

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

Read `references/schemas.md` when writing assertions, `grading.json`, or benchmark files: it has the full schemas.

### Running Tests

**With-skill run:** spawn a subagent with the skill path and the task prompt. Save its outputs to `workspace/iteration-N/eval-ID/with_skill/outputs/`.

**Baseline run:** the same prompt with no skill (or the old skill version). Save to `without_skill/outputs/`.

Launch both runs of a test case in the same turn.

### Grading and Viewing

1. Grade each run with `agents/grader.md`. Save `grading.json` (fields: `text`, `passed`, `evidence`).
2. Aggregate: `python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>`
3. Analyze: read `agents/analyzer.md` for patterns (non-discriminating assertions, high variance, time/token tradeoffs).
4. Launch the viewer:
   ```bash
   python eval-viewer/generate_review.py <workspace>/iteration-N --skill-name "name" --benchmark <workspace>/iteration-N/benchmark.json
   ```
   From iteration 2: add `--previous-workspace <workspace>/iteration-<N-1>`.

---

## Improving a Skill

### How to Think About Improvements

1. **Generalize from feedback.** A fix that works for only one test case is overfitted. Try a different wording or a different working pattern instead.
2. **Keep the prompt lean.** Remove each instruction that does not change the agent's behavior in the transcripts. Read the transcripts to find unproductive work.
3. **Bundle repeated work.** If each test run wrote a similar helper script, put that script in `scripts/`.

### Iteration Signals

**Undertriggering** (the skill does not load when it should):
- Add trigger phrases and technical keywords to the description.
- Add the file types the skill handles.

**Overtriggering** (the skill loads for unrelated queries):
- Add negative triggers in sentence case that name the owner ("Not for X, which is `other-skill`"), so the request has somewhere to go.
- Narrow the scope terms.
- Redraw the boundaries with related skills.

**Instructions not followed**:
- Use bullet points for discrete items.
- Put the most important instructions at the top.
- Replace ambiguous language with specific checks. Where the transcripts show a rule applied in the wrong case, add the missing condition or a one-clause reason, not capitals.
- Bundle validation scripts for deterministic checks.

---

## Description Optimization

The automated pipeline optimizes triggering accuracy with train/test splits.

### Step 1: Generate 20 eval queries (10 should-trigger, 10 should-not)

Each query must be realistic: a full sentence with file names, backstory, and specifics, not "Format this data". Negative cases must be near misses (adjacent domains, shared keywords), not unrelated requests.

### Step 2: Review with user

Present the queries with the `assets/eval_review.html` template. The user can edit, toggle, add, and remove entries. If no user can review, keep the generated set and state that it was not reviewed.

### Step 3: Run optimization

```bash
python -m scripts.run_loop --eval-set <eval.json> --skill-path <path> --model <model-id> --max-iterations 5 --verbose
```

The loop splits 60% train / 40% test, evaluates each query 3 times, uses extended thinking to propose improvements, and selects the best description by test score.

### Step 4: Apply result

Replace the description in the SKILL.md frontmatter with `best_description` from the output. Show the before and after to the user.

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

Read `references/installing.md` when you need install options other than the two above, distribution, or API usage.

After installing, restart the agent so it loads the new skills.

---

## Review Checklist

### Structure
- [ ] File named exactly `SKILL.md` (case-sensitive)
- [ ] Folder name is kebab-case and matches the `name` field
- [ ] YAML frontmatter has `---` delimiters
- [ ] `name` field is kebab-case, under 64 characters
- [ ] `description` states what the skill does and when to use it
- [ ] No angle brackets in the frontmatter
- [ ] No README.md inside the skill folder

### Content Quality
- [ ] SKILL.md under 500 lines
- [ ] Instructions are imperative and specific
- [ ] Each reference pointer states when to read the file
- [ ] Examples show the expected formats; output examples are in `<example>` tags with a rationale
- [ ] Emphasis in sentence case; reasons only where they change behavior; each prohibition names the alternative
- [ ] Error handling for the known failure cases
- [ ] No information duplicated between SKILL.md and references

### Description Quality
- [ ] Includes trigger phrases users would actually say
- [ ] Mentions the file types the skill handles, if any
- [ ] Has at least one negative boundary that names the owning skill
- [ ] Follows the order: concern, coverage, triggers, negative boundary

### Bundled Resources
- [ ] Scripts tested and working
- [ ] Each reference over 100 lines has a table of contents
- [ ] Each asset is used in the output
- [ ] No extraneous files (CHANGELOG, INSTALLATION_GUIDE, etc.)

---

## Agent Definitions (Subagents)

Read the agent file for the job:
- `agents/grader.md`: when grading assertions against outputs
- `agents/comparator.md`: when running a blind A/B comparison between two outputs
- `agents/analyzer.md`: when analyzing why one version beat another

## References

- `references/specification.md` — Agent Skills standard: frontmatter, structure, cross-platform, description writing
- `references/patterns.md` — Skill design patterns: sequential, multi-MCP, iterative, context-aware, domain intelligence
- `references/installing.md` — Installing, distributing, and sharing skills
- `references/schemas.md` — JSON schemas for evals, grading, benchmark, comparison, analysis
- `references/openai_yaml.md` — Codex `agents/openai.yaml` format; read it before generating that file

## Environment-Specific Notes

**Hosted web UI (no subagents)**: run the test cases one after another yourself. Skip baseline runs and quantitative benchmarking. Present the results inline. Skip description optimization; it needs a headless CLI.

**Sandboxed agent (subagents, no browser)**: use `--static <output_path>` for the viewer. Feedback downloads as `feedback.json`.

**Codex**: generate `agents/openai.yaml` for UI metadata with `scripts/init_skill.py` and `scripts/generate_openai_yaml.py`.

## Boundaries

| Need | Skill |
|---|---|
| Routing a request to an existing skill rather than authoring one | `planner` |
| Project documentation, ADRs, release notes | `work-docs` |
| Reviewing the code a skill produces | `code-review` |
| Repository-specific conventions a skill should defer to | `project-conventions` |

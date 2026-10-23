<!-- Appended to AGENTS.md for Codex only by install.sh: Codex reads ~/.codex/AGENTS.md. -->

# CODEX MODEL PREFERENCE
For general coding and text work in Codex, use these default model choices and ordered fallbacks when a primary slug is unavailable:

- `gpt-6-luna` (fallback: `gpt-6-sol` → `gpt-5.6-luna` → `gpt-5.4-mini`): micro tasks with a clear stop (scout, test-runner, patcher, committer).
- `gpt-6-sol` (fallback: `gpt-6.1-sol` → `gpt-5.6-sol` → `gpt-5.4`): routine implementation, tests, exploration, and documentation.
- `gpt-6-astra` (fallback: `gpt-6.1-sol` → `gpt-6-sol` → `gpt-5.6-terra` → `gpt-5.4`): orchestration, difficult reasoning, code review, and security review.

This user preference overrides generic model recommendations in skills, including managed skill references.
Keep the existing reasoning effort for each role. Follow a different model choice if the user explicitly requests it for a task.
Do not substitute these IDs into provider-specific configurations or specialized image, audio, or embedding tools.

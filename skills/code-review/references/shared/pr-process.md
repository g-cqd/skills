# PR Process Review Checklist

Standards enforced at PR level.

## PR Description
- Explains what changed and why
- Ticket ID referenced in title or description
- Flag vague descriptions: "What does 'to make something generic' mean?"

## PR Scope
- 1 PR per ticket — don't mix unrelated changes
- Large PRs (1000+ lines) should be broken into separate concerns
- Separate commits is minimum; separate PRs preferred
- Don't mix renames/refactors with feature work

## Self-Review
- Author must self-review before requesting review
- "Please take the checkbox seriously — this is something you could've easily
  seen yourself"
- Verify all call sites affected by changes

## UI Changes
- Screenshots or recordings required
- Compare against Figma designs
- Check both light and dark mode
- Verify accessibility (VoiceOver / TalkBack)
- If deviating from designs, confirm with UI/UX team

## Translations
- Localize strings in the same PR they are introduced
- Use placeholders (word order varies across languages)
- Run localization scripts for missing keys
- Remove strings in all languages when removing features

## Follow-up Discipline
- Deferred work requires either:
  - TODO comment in code with ticket reference, OR
  - Follow-up ticket created and linked
- Silent degradation is not acceptable
- "For now I accept due to release pressure, but we need a follow-up ticket"

## Dependencies
- License tracking updated (licenses.json / NOTICE)
- Both package-level and target-level dependencies added
- Verify build on target toolchain/IDE version

## Feature Flags
- New features behind feature flags when appropriate
- Cleanup ticket for removing the flag
- Both enabled and disabled states tested

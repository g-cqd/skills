# Testing Review Checklist

What to check during code review. For full testing standards and methodology,
see the standalone `testing` skill. For project-specific test conventions,
see the `project-conventions` skill.

## Red Flags to Catch in Review

- PR adds complex logic without tests — flag it
- Tests deferred to follow-up PRs — push back; split the feature instead
- Test names don't describe the behavior being tested
- Tests check implementation details instead of observable behavior
- Boolean spy flags (`var called = false`) instead of call counts
- Optional argument capture instead of array capture
- `sleep`/timeout used for async synchronization
- Real I/O (network, file system) in unit tests
- Missing error/failure path tests
- Missing initial state tests
- Access control widened just for testability — design smell

## Quick Checks

- Does every public behavior have a test?
- Are both success and failure paths covered?
- Would a mutation in the production code be caught by these tests?
- Are test names descriptive enough to serve as documentation?
- Is there unnecessary test boilerplate that should be extracted?

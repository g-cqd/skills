# Task Decomposition Guidelines

## The Vertical Slice Principle

Always prefer vertical slices over horizontal layers. A vertical slice delivers a thin but complete piece of functionality across all layers (model, view, logic, tests). A horizontal slice builds one technical layer at a time and delivers no user-facing value until all layers are complete.

**Why vertical slices:**
- Each slice is independently demonstrable and testable
- Faster feedback — you know if the approach works after the first slice
- Reduced integration risk — layers are connected from the start
- Easier to reprioritize — each slice stands on its own

## SPIDR Splitting Technique (Mike Cohn)

When a task is too large, apply these techniques in order (try S last):

### Spike
A research activity to reduce uncertainty. Use when:
- The team doesn't know which technology or approach to use
- The requirements are unclear and need prototyping
- Performance characteristics are unknown

**Output of a spike**: A decision or recommendation, NOT working code. The spike enables informed decomposition of the real work.

### Path
Split by different user flows through the same feature:
- "User pays with credit card" vs "User pays with Apple Pay"
- "User signs up with email" vs "User signs up with Apple ID"
- "Happy path" vs "Error recovery path"

### Interface
Split by platform, device, or API surface:
- iOS vs macOS vs visionOS implementation
- SwiftUI vs UIKit adaptation
- REST API vs WebSocket vs local-only

### Data
Split by the type or subset of data being handled:
- "Display text posts" vs "Display image posts" vs "Display video posts"
- "Import from JSON" vs "Import from CSV"
- "Handle single item" vs "Handle batch items"

### Rules
Split by business rules or validation constraints:
- "Basic validation (required fields)" vs "Advanced validation (format, uniqueness)"
- "Free tier behavior" vs "Premium tier behavior"
- "Default configuration" vs "Custom configuration"

## Task Quality Criteria

### The INVEST Checklist (for each task)
- **I**ndependent: Can be completed without waiting for unrelated tasks
- **N**egotiable: The approach can be adjusted during implementation
- **V**aluable: Delivers a meaningful, verifiable outcome
- **E**stimable: Scope is clear enough to judge complexity
- **S**mall: Fits in a single focused work session
- **T**estable: Has clear acceptance criteria

### Risk-First Ordering

Order tasks to reduce risk early:
1. **Architectural spikes** — validate the approach before building on it
2. **Core domain logic** — the hardest, most uncertain work
3. **Integration points** — where components connect
4. **UI and presentation** — least risky, most visible progress
5. **Polish and edge cases** — fine-tuning

### Dependency Management

Rules for task dependencies:
- A task should have at most 2-3 blockers
- If a task has more than 3 blockers, it may be too large — split it
- Avoid long dependency chains (more than 4 levels deep)
- Identify tasks that can run in parallel (no mutual dependencies)
- Never create circular dependencies

## Decomposition by Request Type

### New Feature
1. Identify the user-facing outcomes
2. Split each outcome into vertical slices
3. Order: spike → core logic → UI → integration → edge cases

### Bug Fix
1. "Write a failing test that reproduces the bug"
2. "Fix the bug with minimal code change"
3. "Verify no regressions in related functionality"

### Refactoring
1. "Add characterization tests for current behavior"
2. "Refactor [specific aspect] while keeping tests green"
3. "Verify performance is not degraded"

### Migration
1. "Spike: assess migration scope and identify breaking changes"
2. "Migrate [module A] with backward compatibility"
3. "Migrate [module B] with backward compatibility"
4. "Remove backward compatibility shims"
5. "Update documentation"

## Task Description Template

```
**What**: [Action to take]
**Where**: [File paths or code areas affected]
**Why**: [Connection to the user's original request]
**Verify**: [How to confirm the task is done correctly]
**Depends on**: [Task IDs this is blocked by, if any]
```

## Common Mistakes

1. **Decomposing before understanding**: Always explore the codebase first
2. **Mixing research and implementation**: Spikes should produce knowledge, not code
3. **Forgetting verification criteria**: Every task needs a "how to verify"
4. **Over-decomposing trivial work**: If the whole request is 20 lines of code, don't create 10 tasks
5. **Under-decomposing complex work**: If a task description needs more than 3 sentences, it's probably too large
6. **Ignoring the user's priorities**: Decompose in the order the user cares about, not the technically convenient order

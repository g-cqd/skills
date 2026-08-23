# iOS Review Guide

Review rules for iOS/Swift/SwiftUI codebases.

## Correctness and Safety

### Memory Management
- `[weak self]` in closures where retain cycles are possible
- Flag inconsistency: if some closures use `[weak self]` and others don't in
  the same type, ask which is correct
- In `for await` loops: guard-let self **inside** each iteration, not before
  the loop — unwrapping before the loop defeats the purpose of weak capture

### Concurrency
- `@MainActor` for UI mutations — but don't over-apply; question if truly needed
- Propagate `async` through the call chain; ad-hoc `Task {}` blocks are last resort
- Use `AsyncButton` for any button triggering async work (prevents double-taps,
  manages Task lifecycle)
- Always handle cancellation after `Task.sleep` — check `Task.isCancelled`
- Don't mark functions `async throws` if they never await or throw
- Task ordering matters for perceived performance: navigate first, refresh in
  background
- Use `@concurrent` (Swift 6.2+) for file I/O to move off MainActor

### Error Handling
- Never silently swallow errors — at minimum, log them
- Never show success UI when an operation failed
- Use `defer` blocks to reset loading states on failure
- Every `catch` block needs justification for what it does
- Error recovery must leave consistent state

### Type Safety
- **Optional Bool is an anti-pattern** — use non-optional with default value
- **Optional Array is an anti-pattern** — use empty array
- Use `Decodable` not `Codable` when type is only decoded
- Minimal protocol conformances: don't add `Identifiable`, `Hashable` unless used
- `RawRepresentable` for synthesized Codable — don't write manual CodingKeys
- Enum with associated values for discriminated unions
- Use `Date`, `URL` instead of `String` for typed data

### Module Boundaries
- UI packages must not depend on feature packages
- Dependency direction: Feature → Domain → Core; UI → Domain → Core
- Update both package-level and target-level dependencies in `Package.swift`
- `@unknown default` only for external enums; avoid `default` for own enums

## SwiftUI Patterns

- **Computed Binding over onChange** — derived state via `Binding(get:set:)`
- **@State vs @StateObject**: In legacy code, `@State` doesn't lazily initialize
  reference types; use `@StateObject`. With `@Observable` (iOS 17+), `@State`
  is correct for reference types
- **@LazyState** for lazy initialization of reference types
- **No side effects in computed properties** — use `.task()` modifier
- **@StateObject for ownership, @ObservedObject for injection**
- **@ViewBuilder over Group** — less nesting
- **.task over .onAppear** for async work (handles cancellation)
- **Avoid AnyView** — use @ViewBuilder
- **Extract complex view bodies** into named `private var` computed properties
- **Split large views** at ~200 lines
- **Design system tokens**: flag raw padding/font/color values; use design
  system extensions (e.g., `.font(.brand.titleSmall)`)
- **.constant()** for read-only Bindings instead of computed Binding
- **UIRepresentable coordinators** can hold stale bindings — update in
  `updateUIView`, not just init

## Access Control

- Default to `private`; widen deliberately
- `private(set)` for published properties read externally
- `let` over `var` when value doesn't change
- Never relax access control just for tests: test public interfaces
- Initializers belong in the type body, not extensions
- Extensions for organization only in large files (>150 lines)
- Types over ~40 lines may warrant their own file

## Naming

- Names must describe what the implementation **actually does**
- Plurals for collections (`ids` not `id` for arrays)
- Specificity over brevity (`threadGroupId` over `id`)
- Self-documenting code: extract well-named functions instead of comments
- Argument labels mandatory; closures go last
- Argument order matches property declaration order

## Dependencies and Modules

- New features belong in packages, not the app target
- Inject services, not HTTPClient — push construction up
- Reuse cross-module utilities (e.g., a shared backend JSON decoder) instead of per-feature duplicates
- Dependencies need license tracking in `licenses.json`
- Verify builds on target toolchain (Xcode version)

## Backend Coordination

- Push permission logic to backend — client-side user-type checks don't scale
- Request batch APIs instead of N individual requests
- Use CodingKeys to bridge backend naming to domain naming
- Don't create client abstractions for non-existent backend capabilities

## Localization

- Localize strings in the same PR they are introduced
- Use string placeholders, not code concatenation (word order varies)
- Run `clean_localizable` script for missing keys
- Remove strings from all language files when removing features

## Design System

- Use design system tokens, not raw values
- Protect design system component APIs from one-off customizations
- Match sheet sizing to content with appropriate detents
- Compare implementation against Figma
- Use `AsyncButton` for async interactions

## Feature Flags

- Gate new features behind feature flags when appropriate
- Track feature flag lifecycle: add ticket for cleanup
- Separate `FeatureFlags` (rollout) from `DevelopmentFlags` (permanent)

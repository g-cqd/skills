---
name: swiftui
description: >-
  Apple platforms: build, review, and refactor SwiftUI views, state, navigation, layout,
  animation, accessibility, localization, and rendering performance. Use for SDK 27
  migration, @State initialization errors, synthesized-property redeclarations, extraneous
  argument labels, reordering, AsyncImage caching, swipe actions, toolbars, and document
  APIs. For UIKit or Liquid Glass adoption, use `apple-platforms`; for concurrency, use
  `swift`; for device verification, use `xcode`.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# SwiftUI

This skill owns **what the view layer looks like and how it is written**: composition, data flow,
identity, modifiers, animation, and the design qualities of the result. It does not own the
platform APIs a view happens to call (`apple-platforms`), the language it is written in
(`swift`), or the toolchain that builds it (`xcode`).

Portions of the idiom and SDK 27 material were published by Apple. Where that material conflicts
with prior training, **it is correct**. Do not invent APIs or parameters that the references do
not document.

## Contract

```
§GATE     ? deployment-floor BEFORE using any API ⇒ ¬assume-SDK-27
§DOCS     apple-docs MCP → CLI → SDK-interfaces · ¬web-fetch
§STATE    @State ∷ macro (SDK-27+) ⇒ ¬reorder-init-assignments ⇒ see §3
§BAN      logic ∈ View · AnyView-by-default · index-as-ForEach-id ·
          side-effect ∈ body · magic-number (⇒ design-token) ·
          ObservableObject ∈ new-code (⇒ @Observable)
§PRECEDE  project-conventions ≻ this-skill ∀design-token|component
```

---

## 1. View structure

- A `body` is **pure**: no side effects, no I/O, no heavy computation. It runs often and at times
  you do not choose.
- Factor a section into its **own `View` struct** when it has its own state, its own identity, or
  when it lets SwiftUI skip re-evaluating siblings. Use a **computed property** when the section
  is small and shares the parent's inputs — it costs nothing at runtime but does not create an
  invalidation boundary.
- Extraction is a performance tool, not only a tidiness tool: a separate struct narrows what
  invalidates.
- Watch initializer cost. Work in a view's `init` runs on every re-evaluation of the parent.
- **Single-child `Group` is an anti-pattern** — it adds a layer that does nothing.
- Prefer `Button` to `onTapGesture`: it carries accessibility and platform behavior for free.

## 2. State and data flow

- `@Observable` over `ObservableObject` in all new code. It tracks **per property**, so a view
  invalidates only on the fields it actually reads.
- Per-property tracking has a granularity trap: reading a property inside a closure or a nested
  type may register a dependency you did not intend, or miss one you did. Verify what the `body`
  truly reads.
- `@Observable` models that drive UI belong on `@MainActor`, and benefit from `Equatable` so
  SwiftUI can skip redundant work.
- **Narrow the input.** Pass a view the fields it reads, not the whole aggregate. A row that takes
  a whole model invalidates on every unrelated change to that model.
- When passing a collection element to a row view, pass the element, not the collection plus an
  index.
- Isolate `.onChange` side effects — a side effect buried in a modifier chain is invisible at the
  call site.
- `@Binding`: prefer KeyPath-based bindings to closure-based ones where both work; closures
  capture and can extend lifetimes unexpectedly.
- `@Environment` is a dependency channel, not a general store. Closures in the environment and
  high-frequency environment updates are a known performance pitfall — an environment value that
  changes every frame invalidates every reader.

## 3. `@State` is a macro in SDK 27 — the trap

**Read this before answering any post-SDK-update `@State` compile error.** `@State` migrated from
a property wrapper to a macro. It now synthesizes real backing storage, which changes three
things. The intuitive fix is wrong in the first case and silently produces incorrect runtime
behavior.

### `error: variable 'self.x' used before being initialized`

Triggered when a `@State` property has an initial value at its declaration **and** the initializer
assigns it again before other stored properties are set:

```swift
struct ContentView: View {
    var name: String
    @State private var counter: Int = 0     // initial value here

    init(name: String) {
        self.counter = 42                   // ...and assigned again here, first
        self.name = name
    }
}
```

**Correct fix: drop the initial value at the declaration and assign only in `init`.**

<example>
```swift
struct ContentView: View {
    var name: String
    @State private var counter: Int          // no initial value here

    init(name: String) {
        self.counter = 42                    // the only assignment
        self.name = name
    }
}
```
<rationale>Correct because the macro's backing storage now has exactly one source of its initial
value, so `body` observes 42. Reordering the two assignments would also silence the compiler,
but the declaration's `= 0` would still win at runtime.</rationale>
</example>

Do not reorder the assignments. Reordering silences the compiler and leaves you with the
anti-pattern below, which does not do what it appears to:

```swift
struct ContentView: View {
    @State private var counter: Int = 0
    init() { self.counter = 42 }            // body observes 0, not 42
}
```

Assigning to a `@State` property that already has an initial value does not take effect. The
declaration's value wins.

### `error: invalid redeclaration of synthesized property '_counter'`

Another property wrapper is composed onto a `@State` property, and both synthesize a backing
store with the same name. **Fix:** remove the redundant wrapper, or restructure so the backing
names do not collide. If it is not obvious which wrapper should go, ask the user.

### `error: extraneous argument label` at a memberwise `init` call site

A view whose members are all `private` normally gets a private memberwise `init` usable from
initializers in extensions. With `@State`, that synthesis does **not** happen — the macro
generates two `init` accessors targeting the same backing property, and per SE-0400 the compiler
then skips memberwise `init` synthesis.

**Fix:** define the memberwise initializer explicitly instead of relying on synthesis.

## 4. Identity — `ForEach`, `List`, `Table`, `OutlineGroup`

Identity drives state preservation, animation correctness, and performance. Getting it wrong
produces bugs that look like rendering glitches.

- Identity must be **stable across updates** and **unique within the collection**.
- Anti-patterns: array **indices** as ids; ids minted fresh per render (`UUID()` in the loop);
  ids derived from mutable **content** — all three break state and animation the moment the
  collection changes.
- Row structure affects `List` performance: a **unary** row (one view) and a **multi-view** row
  are handled differently. Prefer a single root per row.

## 5. Modifiers

- Order matters — modifiers wrap, they do not merge.
- **Conditional modifiers change identity.** An `if` that swaps which modifier applies can make
  SwiftUI treat the result as a different view and discard its state. Prefer a modifier that takes
  an optional or a neutral value over branching around the modifier.

## 6. Animation

- `withAnimation` for state-driven change; `.animation(_:value:)` scoped to the value that
  changes. An unscoped `.animation` animates more than you intend.
- Transitions apply on insertion and removal, and require stable identity (§4) to fire.
- Implement `Animatable` for a custom type whose interpolation SwiftUI cannot infer —
  `animatableData` must be a continuously interpolatable value.
- Phase and keyframe animators drive multi-step sequences without nesting completion handlers.

## 7. Localization

- In a view, `Text("…")`, `Button`, `Label`, navigation and toolbar titles, and alerts take
  `LocalizedStringKey` and localize **automatically**. A `String` variable passed to them does
  not — that is the most common localization bug.
- On non-view types, carry `LocalizedStringResource`, not `String`.
- In a Swift package or framework, pass `bundle: #bundle` or the string resolves against the wrong
  bundle.
- Use format styles for dates, numbers, currencies, and lists. Never concatenate localized
  fragments.
- Use `.leading` / `.trailing`, never `.left` / `.right`, so RTL layouts mirror correctly.
- Apply case transforms at runtime, not in the catalog. Give translators comments for every
  interpolated string.

## 8. Accessibility and design

- WCAG AA: **4.5:1** for body text, **3:1** for large text.
- Support Dynamic Type. Use `@ScaledMetric` for custom numeric values so they scale with the type
  size.
- Accessibility labels on every interactive element; decorative images hidden from VoiceOver.
- Use design tokens for color, spacing, and radius — no magic numbers. **Project tokens and
  project components override every generic example in this skill.**
- Drive development from previews: multiple size classes, both color schemes, largest Dynamic Type
  size.

## 8b. Drawing and GPU interop

`Canvas` gives immediate-mode 2D drawing inside the view tree — use it when a shape hierarchy
would create hundreds of views. It re-renders as a unit, so it trades view-level diffing for draw
control.

`TimelineView` drives time-based updates without a timer fighting the run loop; pair it with
`Canvas` for animation that does not invalidate the surrounding hierarchy.

For a `CADisplayLink` or a hosted Metal drawable, keep the render loop **outside** the view's
`body` and let the view own only the hosting surface. A render loop that mutates observed state
every frame produces an invalidation storm (§9). The rendering itself — shaders, GPU work,
performance — is `graphics`.

## 9. Performance auditing

Measure before changing. The audit runs in four phases: reproduce the hitch, attribute it in
Instruments, identify the invalidation source, then narrow the invalidation.

Common causes, in the order they usually turn out to be true:

1. Over-broad invalidation — a view observes more than it reads (§2).
2. Unstable identity forcing teardown and rebuild (§4).
3. Work in `body` or in `init` (§1).
4. Eager `AnyView` erasure defeating structural diffing.
5. High-frequency environment updates (§2).

Attribute a hitch or an invalidation storm only after an Instruments trace or a
`Self._printChanges()` observation shows which view re-evaluated and why; reading the view
source alone produces a plausible cause, not a confirmed one. Report a performance claim only
with before/after numbers. See `performance-engineering` for methodology.

## 10. SDK 27 changes

Check the deployment floor before using any of these. The `@State` trap is §3 — the rest:

| Change | What it is | Reference |
|---|---|---|
| Reordering | `.reorderable()` on `ForEach` + `.reorderContainer(for:)` for any container; `ReorderDifference` apply; drag-and-drop via `dragContainer` / `dropDestination`; combine-on-drop. iOS/macOS/watchOS/visionOS 27, **not tvOS** | `references/sdk-27/reorderable.md` |
| `AsyncImage` | Standard HTTP caching by default; `AsyncImage(request:)` for a per-request cache policy; `asyncImageURLSession(_:)` for a custom session. Fixes "images reload when scrolling back" | `references/sdk-27/async-image.md` |
| Toolbars | `visibilityPriority`, `ToolbarOverflowMenu`, `.topBarPinnedTrailing`, `toolbarMinimizeBehavior`, `contentMarginsRemoved`, `ToolbarPlacement.statusBar`; `ForEach` and `EmptyView` now work in toolbar builders | `references/sdk-27/toolbar.md` |
| Item bindings | `confirmationDialog` and `alert` overloads taking `item: Binding<T?>` — the `sheet(item:)` shape, unwrapped value passed to `actions` and `message` | `references/sdk-27/item-binding.md` |
| Swipe actions | `swipeActionsContainer()` on the container lets `swipeActions(edge:allowsFullSwipe:content:)` work outside `List`; new `onPresentationChanged` overload. Not tvOS | `references/sdk-27/swipe-actions.md` |
| Documents | `ReadableDocument` / `WritableDocument`, read-only viewers via `DocumentGroup(viewer:makeReadableDocument:)`, direct file-URL access, `DocumentReader` / `DocumentWriter`, incremental package writes, `Subprogress`. **At a floor of 27+, do not recommend `FileDocument` or `ReferenceFileDocument` for new code** | `references/sdk-27/document-based-apps.md` |
| `@ContentBuilder` | Unified result builders. Source-incompatible where code relied on result-builder structure: ambiguous `ShapeStyle` overloads in `overlay` / `background`, ambiguous references when a module shadows a SwiftUI type, and a type-check performance regression in Swift Charts with deeply branching content | `references/sdk-27/content-builder.md` |
| Deprecations | Hard-deprecated in 27.0, e.g. `statusBarHidden` on visionOS (no effect — remove the call) | `references/sdk-27/deprecations.md` |

Soft-deprecated APIs are a separate axis from the hard deprecations above — see
`references/idiom/soft-deprecated-apis.md` for the searchable list and
`references/idiom/soft-deprecation.md` for how to identify and migrate them.

## 11. Review checklist

- [ ] No deprecated API — checked against `references/swiftui/latest-apis.md`
- [ ] `@Observable`, not `ObservableObject`
- [ ] `body` pure; no side effects, no heavy work; `init` cheap
- [ ] `ForEach` identity stable and unique — no indices, no minted ids
- [ ] Views take the fields they read, not whole aggregates
- [ ] Conditional modifiers do not swap identity
- [ ] Accessibility labels present; WCAG AA met; Dynamic Type supported
- [ ] User-facing text localizable; `bundle: #bundle` in packages
- [ ] Design tokens used; project components preferred over raw controls
- [ ] Deployment floor checked before any SDK 27 API

## Boundaries

| Need | Skill |
|---|---|
| UIKit scene lifecycle, multi-window modernization, Liquid Glass adoption, platform frameworks | `apple-platforms` |
| Swift language, concurrency, `Sendable`, SPM | `swift` |
| Building, running, screenshotting, UI hierarchy on device or simulator | `xcode` |
| Primary-source Apple documentation and HIG lookup | `apple-docs` |
| Profiling methodology and measurement discipline | `performance-engineering` |
| Repository-specific tokens, components, and layering | `project-conventions` |

## References

**Framework** — `references/swiftui/`: `_guide.md`, `latest-apis.md` (deprecated→modern lookup),
`type-system-patterns.md` (protocol hierarchy, style system, result builders, property wrappers,
environment vs preferences, type erasure, Observation), `state-management.md`, `view-structure.md`,
`performance-patterns.md`, `list-patterns.md`, `modern-apis.md`, `animation-basics.md`,
`animation-transitions.md`, `animation-advanced.md`, `sheet-navigation-patterns.md`,
`scroll-patterns.md`, `text-formatting.md`, `image-optimization.md`, `layout-best-practices.md`,
`liquid-glass.md`, `accessibility-patterns.md`, `charts.md`, `macos-scenes.md`,
`macos-window-styling.md`

**Idiom** — `references/idiom/`: `structure.md`, `dataflow.md`, `environment.md`, `modifiers.md`,
`foreach.md`, `animations.md` (custom `Animatable`), `localization.md`, `soft-deprecation.md`,
`soft-deprecated-apis.md`

**Design** — `references/design/`: `_guide.md`, `typography.md`, `accessibility.md`,
`design-tokens.md`, `layout-responsive.md`, `previews.md`, `performance-audit.md`

**SDK 27** — `references/sdk-27/`: `state-macro.md`, `reorderable.md`, `async-image.md`,
`toolbar.md`, `item-binding.md`, `swipe-actions.md`, `document-based-apps.md`,
`content-builder.md`, `deprecations.md`

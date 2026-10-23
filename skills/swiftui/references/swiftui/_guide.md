# SwiftUI — Domain Guide

This guide contains SwiftUI best practices, modern API usage, view composition rules, and project-specific conventions. For detailed reference on specific topics, see the other files in this directory.

## Core Guidelines

### State Management
- **Always prefer `@Observable` over `ObservableObject`** for new code
- **Mark `@Observable` classes with `@MainActor`** unless using default actor isolation
- **Always mark `@State` and `@StateObject` as `private`**
- **Never declare passed values as `@State` or `@StateObject`**
- Use `@State` with `@Observable` classes (not `@StateObject`)
- `@Binding` only when child needs to **modify** parent state
- `@Bindable` for injected `@Observable` objects needing bindings
- Use `let` for read-only values; `var` + `.onChange()` for reactive reads
- Legacy: `@StateObject` for owned `ObservableObject`; `@ObservedObject` for injected
- **Use `@LazyState` for ViewModel creation in Views**
- **`@ObservedObject` for non-owned objects**
- **No side effects in initializers**: Use `.task {}` for async setup
- **Avoid `@EnvironmentObject` for navigation**: Prefer explicit closure injection
- **Use `@FocusState` for focus management**

### Property Wrapper Selection
| Wrapper | Use When |
|---------|----------|
| `@State` | Internal view state (must be `private`), or owned `@Observable` class |
| `@Binding` | Child modifies parent's state |
| `@Bindable` | Injected `@Observable` needing bindings |
| `let` | Read-only value from parent |
| `var` | Read-only value watched via `.onChange()` |

### Modern APIs
- `foregroundStyle()` instead of `foregroundColor()`
- `clipShape(.rect(cornerRadius:))` instead of `cornerRadius()`
- `Tab` API instead of `tabItem()`
- `Button` instead of `onTapGesture()` (unless need location/count)
- `NavigationStack` instead of `NavigationView`
- `navigationDestination(for:)` for type-safe navigation
- Two-parameter or no-parameter `onChange()` variant
- `.sheet(item:)` instead of `.sheet(isPresented:)` for model-based content
- `.scrollPosition()` + `.scrollTargetLayout()` for programmatic scrolling
- Avoid `UIScreen.main.bounds`, avoid `GeometryReader` when alternatives exist
- `EdgeInsets()` shorthand when all zero
- `.interactiveDismissDisabled()` with `SheetGrabberHeader` when drag indicator hidden

### View Composition
- **Prefer modifiers over conditional views** for state changes
- **Split multi-state views into separate single-purpose components**
- **No redundant containers**: Single-child `ZStack`/`VStack`/`HStack`/`Group`
- **No redundant boolean flags**: Don't duplicate switch/case logic
- **Place overlays at correct hierarchy level**
- **Use `.disabled()` at call site**: Not passed as parameter
- **Use `let` for non-owned dependencies**: Not `@LazyState`, not `var`
- **Prefer `.frame(maxWidth: .infinity)` over `Spacer()`**
- **Use `AsyncButton` for async actions**: Never `Task {}` in `Button`
- **Use `.overlay { if condition { ... } }` over custom `.if()` ViewModifier**
- **ViewModels must NOT contain Views**
- **Prefer `private var` for no-argument view builders**
- **Use `@ViewBuilder` on computed properties** for multi-branch bodies
- Extract complex views into separate subviews
- Keep views small for optimal performance
- Keep view `body` simple and pure
- Action handlers reference methods, not inline logic
- **Use `let` for closure properties**: `let onCancel: () -> Void`
- Apply modifiers from outside for reusability

### Swift Best Practices in SwiftUI
- Modern Text formatting (`.format` parameters, not `String(format:)`)
- `localizedStandardContains()` for user-input filtering
- `.task` modifier for automatic cancellation; `.task(id:)` for value-dependent
- `.onAppear` when no async work needed
- Move `do/catch` to ViewModel
- `@ViewBuilder` default parameters: `= EmptyView.init`
- Use design system colors, never hardcoded `.white`/`.black`
- `withAnimation(:completion:)` (iOS 17+) instead of `Task.sleep` + animation
- Prefer computed `Binding` over `onChange` state sync
- `.onGeometryChange()` over `GeometryReader` for measurements
- `#Preview` instead of preview structs
- Inject services, not HTTPClient
- `.alert(item:)` over double `@State`

### Performance
- Pass only needed values to views
- Eliminate unnecessary dependencies
- Check for value changes before assigning state in hot paths
- Use `LazyVStack`/`LazyHStack` for large lists
- Stable identity for `ForEach` (never `.indices` for dynamic content)
- Constant number of views per `ForEach` element
- Avoid inline filtering in `ForEach`
- Avoid `AnyView` in list rows
- No object creation in `body`
- Heavy computation moved out of `body`
- Use `Self._printChanges()` to debug unexpected view updates

### Animations
- `.animation(_:value:)` with value parameter (deprecated without)
- `withAnimation` for event-driven animations
- Prefer transforms (`offset`, `scale`, `rotation`) over layout changes for performance
- Transitions require animations outside the conditional structure
- `.phaseAnimator` for multi-step sequences (iOS 17+)
- `.keyframeAnimator` for precise timing (iOS 17+)
- Implicit animations override explicit (later in view tree wins)

### Liquid Glass (iOS 26+)
**Only adopt when explicitly requested by the user.**
- `glassEffect`, `GlassEffectContainer`, glass button styles
- Wrap multiple glass elements in `GlassEffectContainer`
- Apply `.glassEffect()` after layout and visual modifiers
- `.interactive()` only for tappable/focusable elements
- `glassEffectID` with `@Namespace` for morphing transitions

## Review Checklist

### State Management
- [ ] `@Observable` instead of `ObservableObject` for new code
- [ ] `@Observable` classes marked with `@MainActor`
- [ ] `@State` with `@Observable` classes (not `@StateObject`)
- [ ] `@State` and `@StateObject` are `private`
- [ ] Passed values NOT declared as `@State`/`@StateObject`
- [ ] `@Binding` only where child modifies parent state
- [ ] `@LazyState` for owned ViewModels, `let` for non-owned

### Modern APIs
- [ ] `foregroundStyle()` not `foregroundColor()`
- [ ] `clipShape(.rect(cornerRadius:))` not `cornerRadius()`
- [ ] `NavigationStack` not `NavigationView`
- [ ] `Button` not `onTapGesture()` (unless location/count needed)
- [ ] No `UIScreen.main.bounds`

### View Structure
- [ ] Modifiers over conditionals for state changes
- [ ] Multi-state views split into separate components
- [ ] No redundant containers
- [ ] `.disabled()` at call site
- [ ] `AsyncButton` for async actions
- [ ] No `.if()` modifier — use `.overlay`
- [ ] ViewModels contain no View code
- [ ] No `Task {}` in initializers — use `.task {}`
- [ ] Design system colors used
- [ ] Localized strings use format placeholders
- [ ] Services injected (not HTTPClient)

### Performance
- [ ] View `body` simple and pure
- [ ] Only needed values passed
- [ ] State updates check for changes
- [ ] ForEach uses stable identity
- [ ] No `AnyView` in list rows
- [ ] No object creation in `body`

### Animations
- [ ] `.animation(_:value:)` with value parameter
- [ ] Transitions paired with animations outside conditional
- [ ] Transforms preferred over layout changes

### Liquid Glass (iOS 26+)
- [ ] `#available(iOS 26, *)` with fallback
- [ ] Glass views in `GlassEffectContainer`
- [ ] `.glassEffect()` after layout/appearance modifiers
- [ ] `.interactive()` only on interactable elements

## Detailed References
- `type-system-patterns.md` — **SwiftUI type system & design patterns**: protocols (`View`, `Shape`, `Layout`, `Gesture`), style system (Strategy pattern, configuration structs, environment cascade), `some` vs `any`, result builders (`@ViewBuilder` algebra), property wrappers taxonomy, environment vs preferences (bidirectional data flow), modifier pattern (`ModifiedContent` accumulation), type erasure spectrum (`AnyView` vs `AnyLayout`), `@Observable` framework, phantom/semantic types, generic containers (`TupleView`, `_ConditionalContent`)
- `state-management.md` — Property wrappers and data flow
- `view-structure.md` — View composition, extraction, containers
- `performance-patterns.md` — Performance optimization, anti-patterns, and the method for auditing a slow view
- `list-patterns.md` — ForEach identity, list best practices
- `modern-apis.md` — Modern API replacements
- `animation-basics.md` — Core animation concepts, timing
- `animation-transitions.md` — Transitions, Animatable protocol
- `animation-advanced.md` — Phase/keyframe animations (iOS 17+)
- `sheet-navigation-patterns.md` — Sheet and navigation patterns
- `scroll-patterns.md` — ScrollView and programmatic scrolling
- `text-formatting.md` — Modern text formatting
- `image-optimization.md` — AsyncImage, downsampling
- `layout-best-practices.md` — Layout patterns, testability
- `liquid-glass.md` — iOS 26+ Liquid Glass API
- `toolbars-ios26.md` — iOS 26 toolbar changes (spacers, shared backgrounds, search placement, subtitles)
- `webkit-integration.md` — `WebView` and `WebPage` (iOS 26)
- `styled-text-editing.md` — Rich text editing with `AttributedString` in `TextEditor` (iOS 26)
- `charts.md` — Swift Charts, including 3D charts (iOS 26)
- `accessibility-patterns.md` — VoiceOver, Dynamic Type, traits, grouping, reduced motion, contrast, WCAG

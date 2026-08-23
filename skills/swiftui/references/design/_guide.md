# SwiftUI Design & Performance — Domain Guide

This guide covers design engineering (typography, accessibility, design tokens, responsive layout, previews) and performance auditing. For detailed reference, see the other files in this directory.

## Design Principles

### Clarity and Minimalism
- Every element serves the user's goal
- Content is the hero; chrome is invisible
- Subtract until it breaks — less, but better
- No dark patterns; transparent about state

### The Subtraction Test
Before outputting code:
1. Remove any `ZStack`, `GeometryReader`, or shape that doesn't serve interaction or accessibility
2. No skeleton loaders implying non-existent data structures
3. Every interactive element has `accessibilityLabel` and `accessibilityHint` if needed

## Typography Quick Reference

| Role | Font | Weight |
|------|------|--------|
| Display Large | `.largeTitle` | `.bold` |
| Display Medium | `.title` | `.semibold` |
| Display Small | `.title2` | `.medium` |
| Body Large | `.title3` | `.regular` |
| Body Medium | `.body` | `.regular` |
| Body Small | `.callout` | `.regular` |
| Label Large | `.subheadline` | `.medium` |
| Label Medium | `.footnote` | `.regular` |
| Label Small | `.caption` | `.regular` |

All text must support Dynamic Type. Use `@ScaledMetric` for custom sizes. Switch layouts at `.accessibilityMedium` or larger.

## Design Tokens

```swift
enum DesignTokens {
  enum Spacing {
    static let xxs: CGFloat = 4
    static let xs: CGFloat = 8
    static let sm: CGFloat = 12
    static let md: CGFloat = 16
    static let lg: CGFloat = 24
    static let xl: CGFloat = 32
    static let xxl: CGFloat = 48
  }
  enum Radius {
    static let sm: CGFloat = 4
    static let md: CGFloat = 8
    static let lg: CGFloat = 12
    static let full: CGFloat = 9999
  }
}
```

No magic numbers for spacing, radius, or duration. Always use tokens.

## Performance Audit (Four Phases)

```
Phase 1: Code-First Review    → Identify anti-patterns and root causes
Phase 2: Guide to Instruments → Profile on device (Release build, never Simulator)
Phase 3: Analyze & Diagnose   → Correlate SwiftUI Timeline + Time Profiler
Phase 4: Remediate & Verify   → Apply fix, re-profile, confirm improvement
```

### Common Anti-Patterns
| Issue | Anti-Pattern | Fix |
|-------|-------------|-----|
| Formatter allocation | `NumberFormatter()` in `body` | Static cached instance |
| Heavy computed props | Filter/sort on every `body` eval | Precompute in model |
| Inline sorting | `ForEach(items.sorted(...))` | Sort before view construction |
| Unstable identity | `id: \.self` on mutable values | Stable `Identifiable` conformance |
| Main-thread decode | `UIImage(data:)` in view | Decode/downsample off-thread |
| Broad dependencies | Single `@Observable` with 20 props | Granular view models |
| GeometryReader abuse | Nested readers in scroll content | Hoist to parent, `onGeometryChange` |
| AnyView erasure | `AnyView(someView)` in lists | Concrete types or `@ViewBuilder` |

### Performance Mandates
- **View Body**: <8ms for 120fps. Never allocate formatters, perform I/O, or sort/filter inline.
- **State**: Scope close to leaf views. Isolate frequently-changing state.
- **Lists**: Stable identifiers. Precompute filtered/sorted collections.
- **Images**: Decode off main thread. Downsample to display size. Cache decoded images.
- **Animations**: Scope with `value:` parameter. Respect `accessibilityReduceMotion`.

## Review Checklists

### Design Quality
- [ ] Nothing more to remove (subtraction test passes)
- [ ] Consistent with design system tokens
- [ ] Dark mode and light mode polished
- [ ] Haptics used for meaningful feedback

### Accessibility (WCAG AA)
- [ ] VoiceOver labels on all interactive elements
- [ ] Contrast ratio ≥ 4.5:1 body, ≥ 3:1 large text
- [ ] Tap targets ≥ 44pt
- [ ] Dynamic Type renders without truncation
- [ ] Layout switches at `.accessibilityMedium`
- [ ] Reduced motion respected
- [ ] No time-limited interactions
- [ ] Keyboard navigation works

### Responsiveness
- [ ] Tested on iPhone SE (smallest)
- [ ] Tested on iPad 12.9" (largest)
- [ ] Dynamic Type layout switches work

### Previews
- [ ] Light and dark mode previews
- [ ] Loading, error, empty state previews
- [ ] Dynamic Type XXL preview
- [ ] Accessibility scenarios

### Performance Audit
- [ ] Root cause identified before fix proposed
- [ ] `Self._printChanges()` used to trace dependency changes
- [ ] No formatters/heavy objects in `body`
- [ ] ForEach uses stable `Identifiable` conformance
- [ ] No inline sorting/filtering in `body`
- [ ] Images decoded off main thread
- [ ] Animations scoped with `value:` parameter
- [ ] Fix verified with re-profiling on device

## Detailed References
- `typography.md` — Type scale, Dynamic Type, legibility
- `accessibility.md` — WCAG POUR, VoiceOver, reduced motion, contrast
- `design-tokens.md` — Colors, spacing, radius, duration, haptics, theming
- `layout-responsive.md` — Size class adaptation, container-relative sizing
- `previews.md` — Preview-driven development, scenarios
- `performance-audit.md` — Full four-phase audit methodology

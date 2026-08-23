# Typography

## Type Scale

```swift
extension Font {
  static let displayLarge = Font.system(.largeTitle, weight: .bold)
  static let displayMedium = Font.system(.title, weight: .semibold)
  static let displaySmall = Font.system(.title2, weight: .medium)

  static let bodyLarge = Font.system(.title3)
  static let bodyMedium = Font.system(.body)
  static let bodySmall = Font.system(.callout)

  static let labelLarge = Font.system(.subheadline, weight: .medium)
  static let labelMedium = Font.system(.footnote)
  static let labelSmall = Font.system(.caption)
}
```

## Dynamic Type Support

```swift
// OK — Scales with user preference
Text("Welcome").font(.title)

// NO — Fixed size ignores accessibility
Text("Welcome").font(.system(size: 24))

// OK — Custom metrics with scaling
@ScaledMetric(relativeTo: .body) private var iconSize = 20
Image(systemName: "star").font(.system(size: iconSize))
```

**Mandatory**: All text supports Dynamic Type. Use `@Environment(\.dynamicTypeSize)` to switch layouts at `.accessibilityMedium` or larger.

## Typographic Refinements

- Use `textCase(.uppercase)` and `kerning(_:)` for labels/captions
- Rely on whitespace (padding) over lines (dividers) for grouping
- Use consistent weight progression for hierarchy

## Legibility Rules

| Rule | Guideline | Rationale |
|------|-----------|-----------|
| Line Length | 45–75 characters | Optimal reading |
| Contrast Ratio | ≥ 4.5:1 body, ≥ 3:1 large | WCAG AA |
| Font Weight | ≥ 400 for body | Legibility |

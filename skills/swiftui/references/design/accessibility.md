# Accessibility

## WCAG POUR Pillars

| Pillar | Implementation |
|--------|----------------|
| **Perceivable** | VoiceOver labels, sufficient contrast |
| **Operable** | 44pt tap targets, keyboard nav, no time limits |
| **Understandable** | Consistent navigation, clear errors |
| **Robust** | Works with all assistive technologies |

## VoiceOver Implementation

```swift
struct RatingButton: View {
  let rating: Int
  let action: () -> Void

  var body: some View {
    Button(action: action) {
      HStack {
        ForEach(1...5, id: \.self) { star in
          Image(systemName: star <= rating ? "star.fill" : "star")
            .foregroundStyle(star <= rating ? .yellow : .gray)
        }
      }
    }
    .accessibilityLabel("Rating")
    .accessibilityValue("\(rating) out of 5 stars")
    .accessibilityHint("Double tap to change rating")
    .accessibilityAddTraits(.isButton)
  }
}
```

### Key Rules
- Every interactive element needs `accessibilityLabel`
- Add `accessibilityHint` when the action isn't obvious from the label
- Group related elements with `accessibilityElement(children: .combine)`
- Use `accessibilityAddTraits` to describe element behavior

## Reduced Motion

```swift
struct AnimatedView: View {
  @Environment(\.accessibilityReduceMotion) private var reduceMotion
  @State private var isExpanded = false

  var body: some View {
    content
      .scaleEffect(isExpanded ? 1.2 : 1.0)
      .animation(reduceMotion ? nil : .spring(duration: 0.3), value: isExpanded)
  }
}
```

Always check `accessibilityReduceMotion` and provide a static alternative.

## Contrast Requirements

| Text Type | Minimum Ratio | Standard |
|-----------|--------------|----------|
| Body text | 4.5:1 | WCAG AA |
| Large text (≥18pt bold or ≥24pt) | 3:1 | WCAG AA |
| Non-text (icons, borders) | 3:1 | WCAG AA |

## Dynamic Type Layout Switching

```swift
@Environment(\.dynamicTypeSize) private var typeSize

var body: some View {
  if typeSize >= .accessibilityMedium {
    VStack(alignment: .leading) { content }
  } else {
    HStack { content }
  }
}
```

Switch from horizontal to vertical layout when type size reaches `.accessibilityMedium` to prevent truncation.

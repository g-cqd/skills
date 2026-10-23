# SwiftUI Accessibility Patterns Reference

## Core Principle

Prefer `Button` over `onTapGesture` for tappable elements. `Button` provides VoiceOver support, focus handling, and proper traits for free.

## Dynamic Type with @ScaledMetric

System `Text` scales with Dynamic Type automatically. For custom numeric values (padding, image sizes, spacing), use `@ScaledMetric`:

```swift
struct ProfileHeader: View {
    @ScaledMetric private var avatarSize = 60.0
    @ScaledMetric private var spacing = 12.0

    var body: some View {
        HStack(spacing: spacing) {
            Image("avatar")
                .resizable()
                .frame(width: avatarSize, height: avatarSize)
            Text("Username")
        }
    }
}
```

Specify `relativeTo` when the value should scale relative to a specific font size:

```swift
@ScaledMetric(relativeTo: .caption) private var iconSize = 16.0
```

## Accessibility Traits

Use `accessibilityAddTraits` and `accessibilityRemoveTraits` for state-driven traits:

```swift
Text(item.title)
    .accessibilityAddTraits(item.isSelected ? [.isSelected, .isButton] : .isButton)
```

Use `.disabled(true)` to make VoiceOver announce "Dimmed" for non-interactive elements.

## Decorative Images

Use `Image(decorative:bundle:)` when an asset image is purely visual:

```swift
Image(decorative: "confetti")  // backgrounds, flourishes, non-meaningful icons
```

For non-asset images (SF Symbols), hide with `accessibilityHidden(true)`:

```swift
Image(systemName: "sparkles")
    .accessibilityHidden(true)
```

If the image conveys information, provide a clear label:

```swift
Image("receipt")
    .accessibilityLabel("Receipt")
```

## Element Grouping

### .combine — Auto-join child labels

```swift
HStack {
    Image(systemName: "star.fill")
    Text("Favorites")
    Text("(\(count))")
}
.accessibilityElement(children: .combine)
// VoiceOver reads all child labels as one element
```

### .ignore — Manual label for container

```swift
HStack {
    Text(item.name)
    Spacer()
    Text(item.price)
}
.accessibilityElement(children: .ignore)
.accessibilityLabel("\(item.name), \(item.price)")
```

### .contain — Semantic grouping

```swift
HStack {
    ForEach(tabs) { tab in
        TabButton(tab: tab)
    }
}
.accessibilityElement(children: .contain)
.accessibilityLabel("Tab bar")
// VoiceOver announces container name on focus enter/exit
```

## Custom Controls

### Adjustable controls (increment/decrement)

```swift
PageControl(selectedIndex: $selectedIndex, pageCount: pageCount)
    .accessibilityElement()
    .accessibilityValue("Page \(selectedIndex + 1) of \(pageCount)")
    .accessibilityAdjustableAction { direction in
        switch direction {
        case .increment:
            guard selectedIndex < pageCount - 1 else { break }
            selectedIndex += 1
        case .decrement:
            guard selectedIndex > 0 else { break }
            selectedIndex -= 1
        @unknown default: break
        }
    }
```

### Representing custom views as native controls

```swift
HStack {
    Text(label)
    Toggle("", isOn: $isOn)
}
.accessibilityRepresentation {
    Toggle(label, isOn: $isOn)
}
```

### Label-content pairing

```swift
@Namespace private var ns

HStack {
    Text("Volume")
        .accessibilityLabeledPair(role: .label, id: "volume", in: ns)
    Slider(value: $volume)
        .accessibilityLabeledPair(role: .content, id: "volume", in: ns)
}
```


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

## Checklist

- [ ] `Button` used instead of `onTapGesture` for tappable elements
- [ ] `@ScaledMetric` for custom values that should scale with Dynamic Type
- [ ] Decorative images marked as decorative or hidden
- [ ] Related elements grouped with `accessibilityElement(children:)`
- [ ] `accessibilityLabel` provided when default labels are unclear
- [ ] `accessibilityRepresentation` for custom controls
- [ ] `accessibilityAdjustableAction` for increment/decrement controls
- [ ] Navigation flow logical with VoiceOver grouping

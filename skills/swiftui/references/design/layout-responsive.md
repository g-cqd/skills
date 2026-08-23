# Layout & Responsive Design

## Size Class Adaptation

```swift
struct AdaptiveListView: View {
  @Environment(\.horizontalSizeClass) private var sizeClass
  @Environment(\.dynamicTypeSize) private var typeSize
  let items: [Item]

  var body: some View {
    if sizeClass == .compact || typeSize >= .accessibilityMedium {
      List(items) { ItemRow(item: $0) }
    } else {
      ScrollView {
        LazyVGrid(columns: [.init(.adaptive(minimum: 300))]) {
          ForEach(items) { ItemCard(item: $0) }
        }
        .padding()
      }
    }
  }
}
```

## Container-Relative Sizing

```swift
struct HeroImage: View {
  let url: URL

  var body: some View {
    AsyncImage(url: url) { image in
      image.resizable().aspectRatio(16/9, contentMode: .fill)
    } placeholder: {
      Rectangle()
        .fill(DesignTokens.Colors.backgroundElevated)
        .aspectRatio(16/9, contentMode: .fill)
        .overlay { ProgressView() }
    }
    .containerRelativeFrame(.horizontal)
    .clipped()
  }
}
```

Prefer `containerRelativeFrame()` over `GeometryReader` for container-relative sizing.

## Responsive Patterns

| Context | Compact | Regular |
|---------|---------|---------|
| Navigation | Tab bar | Sidebar |
| Lists | Full-width rows | Grid cards |
| Forms | Stacked fields | Side-by-side |
| Media | Single column | Multi-column grid |

## UX Principles

| Principle | Implementation |
|-----------|----------------|
| User-Centered | Every decision weighed against user impact |
| Clarity | Users always know what to do next |
| Feedback | Immediate response for all interactions |
| Consistency | Platform conventions + internal consistency |
| Forgiveness | Undo options, confirmation for destructive actions |

## Atomic Design (Mental Model)

Use Atomic Design for component composition thinking, but organize files by feature:

```
Features/
├── Profile/
│   ├── ProfileView.swift
│   ├── ProfileViewModel.swift
│   └── Components/
│       ├── AvatarView.swift
│       └── StatCard.swift
├── Settings/
└── DesignSystem/
    ├── Tokens/
    ├── Atoms/
    └── Molecules/
```

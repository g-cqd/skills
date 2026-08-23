# Design Tokens

## Color Tokens

```swift
enum DesignTokens {
  enum Colors {
    static let textPrimary = Color("TextPrimary")
    static let textSecondary = Color("TextSecondary")
    static let backgroundPrimary = Color("BackgroundPrimary")
    static let backgroundElevated = Color("BackgroundElevated")
    static let interactive = Color("Interactive")
    static let success = Color("Success")
    static let warning = Color("Warning")
    static let error = Color("Error")
  }
}
```

Use semantic color tokens from asset catalogs. Never hardcode color literals.

## Spacing Tokens

```swift
enum Spacing {
  static let xxs: CGFloat = 4
  static let xs: CGFloat = 8
  static let sm: CGFloat = 12
  static let md: CGFloat = 16
  static let lg: CGFloat = 24
  static let xl: CGFloat = 32
  static let xxl: CGFloat = 48
}
```

## Corner Radius Tokens

```swift
enum Radius {
  static let sm: CGFloat = 4
  static let md: CGFloat = 8
  static let lg: CGFloat = 12
  static let full: CGFloat = 9999
}
```

## Duration Tokens

```swift
enum Duration {
  static let fast: Double = 0.2
  static let normal: Double = 0.3
  static let slow: Double = 0.5
}
```

## Haptics

```swift
enum Haptics {
  static func impact(_ style: UIImpactFeedbackGenerator.FeedbackStyle) {
    UIImpactFeedbackGenerator(style: style).impactOccurred()
  }
  static func notification(_ type: UINotificationFeedbackGenerator.FeedbackType) {
    UINotificationFeedbackGenerator().notificationOccurred(type)
  }
}
```

## Environment-Based Theming

```swift
struct DesignSystemKey: EnvironmentKey {
  static let defaultValue = DesignSystem.default
}

extension EnvironmentValues {
  var designSystem: DesignSystem {
    get { self[DesignSystemKey.self] }
    set { self[DesignSystemKey.self] = newValue }
  }
}

struct PrimaryButton: View {
  let title: String
  let action: () -> Void
  @Environment(\.designSystem) private var ds

  var body: some View {
    Button(action: action) {
      Text(title)
        .font(ds.fonts.button)
        .padding(ds.spacing.medium)
        .frame(maxWidth: .infinity)
        .background(ds.colors.interactive)
        .foregroundStyle(ds.colors.textOnInteractive)
        .clipShape(Capsule())
    }
  }
}
```

## Rules
- No magic numbers for spacing, radius, or duration
- Use semantic color names, not raw values
- All tokens defined in a single source of truth
- Theme switching via `Environment`

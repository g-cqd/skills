# Liquid Glass Design Implementation

Liquid Glass is a dynamic material that combines the optical properties of glass with a sense of fluidity. It blurs content behind it, reflects color and light from surrounding content, and reacts to touch and pointer interactions in real time. Always seek guides on Liquid Glass when asked for help adopting new Apple design.

## SwiftUI Implementation

### Basic Glass Effect

```swift
Text("Hello, World!")
    .font(.title)
    .padding()
    .glassEffect()
```

By default, this applies the regular variant of Glass within a Capsule shape.

### Customizing Shape

```swift
Text("Hello, World!")
    .font(.title)
    .padding()
    .glassEffect(in: .rect(cornerRadius: 16.0))
```

Shape options: `.capsule` (default), `.rect(cornerRadius:)`, `.circle`

### Glass Variants and Properties

```swift
Text("Hello, World!")
    .font(.title)
    .padding()
    .glassEffect(.regular.tint(.orange).interactive())
```

- `.regular` - Standard glass effect
- `.tint(Color)` - Add color tint for prominence
- `.interactive(Bool)` - React to touch/pointer interactions

### Glass Effect Container

For multiple glass views with merging effects:

```swift
GlassEffectContainer(spacing: 40.0) {
    HStack(spacing: 40.0) {
        Image(systemName: "scribble.variable")
            .frame(width: 80.0, height: 80.0)
            .font(.system(size: 36))
            .glassEffect()

        Image(systemName: "eraser.fill")
            .frame(width: 80.0, height: 80.0)
            .font(.system(size: 36))
            .glassEffect()
    }
}
```

### Uniting Multiple Glass Effects

```swift
@Namespace private var namespace

GlassEffectContainer(spacing: 20.0) {
    HStack(spacing: 20.0) {
        ForEach(symbolSet.indices, id: \.self) { item in
            Image(systemName: symbolSet[item])
                .frame(width: 80.0, height: 80.0)
                .font(.system(size: 36))
                .glassEffect()
                .glassEffectUnion(id: item < 2 ? "1" : "2", namespace: namespace)
        }
    }
}
```

### Morphing Transitions

```swift
@State private var isExpanded: Bool = false
@Namespace private var namespace

var body: some View {
    GlassEffectContainer(spacing: 40.0) {
        HStack(spacing: 40.0) {
            Image(systemName: "scribble.variable")
                .frame(width: 80.0, height: 80.0)
                .font(.system(size: 36))
                .glassEffect()
                .glassEffectID("pencil", in: namespace)

            if isExpanded {
                Image(systemName: "eraser.fill")
                    .frame(width: 80.0, height: 80.0)
                    .font(.system(size: 36))
                    .glassEffect()
                    .glassEffectID("eraser", in: namespace)
            }
        }
    }

    Button("Toggle") {
        withAnimation {
            isExpanded.toggle()
        }
    }
    .buttonStyle(.glass)
}
```

### Button Styles

```swift
Button("Click Me") { }
    .buttonStyle(.glass)

Button("Important Action") { }
    .buttonStyle(.glassProminent)
```

## UIKit Implementation

### Basic UIGlassEffect

```swift
let glassEffect = UIGlassEffect()
let visualEffectView = UIVisualEffectView(effect: glassEffect)
visualEffectView.frame = CGRect(x: 50, y: 100, width: 300, height: 200)
visualEffectView.layer.cornerRadius = 20
visualEffectView.clipsToBounds = true

let label = UILabel()
label.text = "Liquid Glass"
label.textAlignment = .center
label.frame = visualEffectView.bounds
visualEffectView.contentView.addSubview(label)

view.addSubview(visualEffectView)
```

### Customizing

```swift
glassEffect.tintColor = UIColor.systemBlue.withAlphaComponent(0.3)
glassEffect.isInteractive = true
```

### Glass Container

```swift
let containerEffect = UIGlassContainerEffect()
containerEffect.spacing = 40.0

let containerView = UIVisualEffectView(effect: containerEffect)
containerView.frame = CGRect(x: 50, y: 400, width: 300, height: 200)

// Add glass views to containerView.contentView
```

### Scroll Edge Effects

```swift
let scrollView = UIScrollView(frame: view.bounds)
scrollView.topEdgeEffect.style = .automatic
scrollView.bottomEdgeEffect.style = .hard
scrollView.leftEdgeEffect.isHidden = true
```

## AppKit Implementation

### NSGlassEffectView

```swift
let glassView = NSGlassEffectView(frame: NSRect(x: 20, y: 20, width: 200, height: 100))
glassView.cornerRadius = 16.0
glassView.tintColor = NSColor.systemBlue.withAlphaComponent(0.3)

let label = NSTextField(labelWithString: "Liquid Glass")
label.translatesAutoresizingMaskIntoConstraints = false
glassView.contentView = label
```

### NSGlassEffectContainerView

```swift
let containerView = NSGlassEffectContainerView(frame: NSRect(x: 20, y: 20, width: 400, height: 200))
containerView.spacing = 40.0

let contentView = NSView(frame: containerView.bounds)
containerView.contentView = contentView

// Add glass views to contentView
```

## Widget Implementation

### Supporting Liquid Glass

```swift
struct MyWidgetView: View {
    @Environment(\.widgetRenderingMode) var renderingMode

    var body: some View {
        if renderingMode == .accented {
            // Layout optimized for accented mode
        } else {
            // Standard full-color layout
        }
    }
}
```

### Accented Content

```swift
HStack(alignment: .center, spacing: 0) {
    VStack(alignment: .leading) {
        Text("Widget Title")
            .font(.headline)
            .widgetAccentable() // In accent group
        Text("Widget Subtitle")
        // In primary group by default
    }
    Image(systemName: "star.fill")
        .widgetAccentable() // In accent group
}
```

### Container Backgrounds

```swift
var body: some View {
    VStack {
        // Widget content
    }
    .containerBackground(for: .widget) {
        Color.blue.opacity(0.2)
    }
}
```

### Widget Textures (visionOS)

```swift
var body: some WidgetConfiguration {
    StaticConfiguration(kind: "MyWidget", provider: Provider()) { entry in
        MyWidgetView(entry: entry)
    }
    .widgetTexture(.glass) // or .paper
}
```

## Best Practices

1. **Container Usage**: Always use `GlassEffectContainer` for multiple glass views
2. **Effect Order**: Apply `.glassEffect()` after appearance modifiers
3. **Spacing**: Choose spacing values to control merge behavior
4. **Animation**: Use animations for smooth morphing transitions
5. **Interactivity**: Add `.interactive()` for touch-responsive elements
6. **Performance**: Limit glass effects as they're GPU-intensive
7. **Accessibility**: Ensure sufficient contrast on glass backgrounds

## References

- [Applying Liquid Glass to custom views](https://developer.apple.com/documentation/SwiftUI/Applying-Liquid-Glass-to-custom-views)
- [Landmarks: Building an app with Liquid Glass](https://developer.apple.com/documentation/SwiftUI/Landmarks-Building-an-app-with-Liquid-Glass)
- [SwiftUI View.glassEffect](https://developer.apple.com/documentation/SwiftUI/View/glassEffect(_:in:isEnabled:))
- [UIGlassEffect Documentation](https://developer.apple.com/documentation/UIKit/UIGlassEffect)
- [NSGlassEffectView Documentation](https://developer.apple.com/documentation/AppKit/NSGlassEffectView)

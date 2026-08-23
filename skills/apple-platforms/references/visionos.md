# visionOS Features

## Widgets for visionOS

Widgets in visionOS are three-dimensional objects that can be placed in a user's physical space, mounted on surfaces or floating in the environment.

### Mounting Styles

```swift
struct WeatherWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "weather", provider: WeatherProvider()) { entry in
            WeatherWidgetView(entry: entry)
        }
        .configurationDisplayName("Weather Widget")
        // Support both mounting styles (default)
        .supportedMountingStyles([.elevated, .recessed])
        // Or limit to specific style
        // .supportedMountingStyles([.recessed])
    }
}
```

**Mounting Styles:**
- **Elevated**: Widgets sit on top of surfaces (default)
- **Recessed**: Widgets appear embedded into vertical surfaces like walls

### Widget Textures

```swift
var body: some WidgetConfiguration {
    StaticConfiguration(...) { entry in
        MyWidgetView(entry: entry)
    }
    .widgetTexture(.glass) // Default - transparent glass-like appearance
    // .widgetTexture(.paper) // Alternative poster-like look
}
```

### Proximity Awareness

Widgets adapt their display based on user distance:

```swift
struct TotalCaffeineView: View {
    @Environment(\.levelOfDetail) var levelOfDetail

    var body: some View {
        VStack {
            Text("Total Caffeine")
                .font(.caption)
            Text(totalCaffeine.formatted())
                .font(caffeineFont)
        }
    }

    var caffeineFont: Font {
        if levelOfDetail == .simplified {
            return .largeTitle // Larger when viewed from distance
        } else {
            return .title // Normal when close
        }
    }
}
```

**Level of Detail:**
- `.default`: User is close to the widget
- `.simplified`: User is viewing from a distance

The system automatically animates between these states.

### Supported Widget Families

```swift
.supportedFamilies([
    .systemSmall,
    .systemMedium,
    .systemLarge,
    .systemExtraLarge,
    .systemExtraLargePortrait // visionOS-specific
])
```

Extra large families work well with paper texture for poster-like appearance.

### Rendering Modes

```swift
struct MyWidgetView: View {
    @Environment(\.widgetRenderingMode) var renderingMode

    var body: some View {
        VStack {
            // Widget content
        }
        .containerBackground(for: .widget) {
            if renderingMode == .fullColor {
                Color.gameBackground
            }
            // Accented mode: background automatically removed
        }
    }
}
```

- **Full Color**: Complete design with all colors
- **Accented**: Background removed, replaced with user's theme color

### Detecting Background Visibility

```swift
@Environment(\.showsWidgetContainerBackground) var showsBackground

var body: some View {
    VStack {
        // Adjust layout based on background visibility
        if showsBackground {
            // Full layout with background
        } else {
            // Compact layout for accented mode
        }
    }
}
```

### Accented Content

Mark content to be part of the accent color group:

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

### Complete Example

```swift
struct WeatherWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(
            kind: "com.example.weather",
            provider: WeatherProvider()
        ) { entry in
            WeatherWidgetView(entry: entry)
                .containerBackground(for: .widget) {
                    Color.skyBlue.opacity(0.8)
                }
        }
        .configurationDisplayName("Weather")
        .description("Current weather conditions")
        .supportedFamilies([.systemSmall, .systemMedium, .systemExtraLarge])
        .supportedMountingStyles([.elevated, .recessed])
        .widgetTexture(.glass)
    }
}

struct WeatherWidgetView: View {
    var entry: WeatherProvider.Entry
    @Environment(\.levelOfDetail) var levelOfDetail

    var body: some View {
        if levelOfDetail == .simplified {
            // Distance view: large, simple content
            VStack {
                Image(systemName: entry.weatherIcon)
                    .font(.system(size: 40))
                Text("\(entry.temperature)°")
                    .font(.system(size: 36, weight: .bold))
            }
        } else {
            // Close view: detailed content
            VStack(alignment: .leading) {
                HStack {
                    Image(systemName: entry.weatherIcon)
                        .font(.title)
                    Spacer()
                    Text("\(entry.temperature)°")
                        .font(.title)
                }

                Spacer()

                Text(entry.location)
                    .font(.caption)
                Text(entry.condition)
                    .font(.caption2)
            }
            .padding()
        }
    }
}
```

### Previewing Widgets

```swift
#Preview("Weather Widget", as: .systemSmall) {
    WeatherWidget()
} timelineProvider: {
    WeatherProvider()
}
```

## Best Practices

1. **Design for Distance**: Use `.simplified` level of detail for essential information at larger sizes
2. **Test Both Mounting Styles**: Ensure widget looks good elevated and recessed
3. **Consider Texture Choice**: Glass for UI elements, paper for content-rich displays
4. **Accented Mode Support**: Mark important UI elements with `.widgetAccentable()`
5. **Container Backgrounds**: Use `.containerBackground(for: .widget)` for proper background handling
6. **Extra Large Sizes**: Take advantage of visionOS-specific extra large sizes

## References

- [Updating your widgets for visionOS](https://developer.apple.com/documentation/WidgetKit/Updating-your-widgets-for-visionOS)
- [Developing a WidgetKit strategy](https://developer.apple.com/documentation/WidgetKit/Developing-a-WidgetKit-strategy)
- [Displaying the right widget background](https://developer.apple.com/documentation/WidgetKit/Displaying-the-right-widget-background)

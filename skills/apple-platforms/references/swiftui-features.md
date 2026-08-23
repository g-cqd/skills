# SwiftUI New Features

## Customizable Toolbars

### Creating Customizable Toolbars

```swift
ContentView()
    .toolbar(id: "main-toolbar") {
        ToolbarItem(id: "tag") {
           TagButton()
        }
        ToolbarItem(id: "share") {
           ShareButton()
        }
        ToolbarSpacer(.fixed)
        ToolbarItem(id: "more") {
           MoreButton()
        }
    }
```

### Toolbar Spacers

```swift
ToolbarSpacer(.fixed)     // Fixed-width space
ToolbarSpacer(.flexible)  // Flexible space
```

### Enhanced Search Integration

```swift
NavigationStack {
    RecipeList()
        .searchable($searchText)
        .searchToolbarBehavior(.minimize) // Minimized search field
}
```

### Repositioning Search

```swift
.toolbar {
    ToolbarItem(placement: .bottomBar) { CalendarPicker() }
    DefaultToolbarItem(kind: .search, placement: .bottomBar)
}
```

### Large Subtitle Placement

```swift
.toolbar {
    ToolbarItem(placement: .largeSubtitle) {
        CustomLargeNavigationSubtitle()
    }
}
```

### Matched Transition Source

```swift
@Namespace private var namespace

.toolbar {
    ToolbarItem(placement: .topBarTrailing) {
        Button("Show", systemImage: "globe") {
            isPresented = true
        }
    }
    .matchedTransitionSource(id: "world", in: namespace)
}
.sheet(isPresented: $isPresented) {
    SheetView()
        .navigationTransition(.zoom(sourceID: "world", in: namespace))
}
```

## Styled Text Editing

### Rich Text with AttributedString

```swift
var attributedText = AttributedString("This is styled text")

// Style specific ranges
var text = AttributedString("Red and Blue")
if let redRange = text.range(of: "Red") {
    text[redRange].foregroundColor = .red
}
if let blueRange = text.range(of: "Blue") {
    text[blueRange].foregroundColor = .blue
}

Text(attributedText)
```

### Text Editor with Selection

```swift
struct StyledTextEditingView: View {
    @State private var text: AttributedString = AttributedString("Select text to format")
    @State private var selection = AttributedTextSelection()
    @Environment(\.fontResolutionContext) private var fontResolutionContext

    var body: some View {
        VStack {
            TextEditor(text: $text, selection: $selection)

            HStack {
                Button(action: toggleBold) {
                    Image(systemName: "bold")
                }
                Button(action: toggleItalic) {
                    Image(systemName: "italic")
                }
            }
        }
    }

    private func toggleBold() {
        text.transformAttributes(in: &selection) {
            let font = $0.font ?? .default
            let resolved = font.resolve(in: fontResolutionContext)
            $0.font = font.bold(!resolved.isBold)
        }
    }
}
```

### AttributedString Attributes

```swift
var text = AttributedString("Styled")
text.font = .headline
text.foregroundColor = .blue
text.backgroundColor = .yellow
text.underlineStyle = .single
text.strikethroughStyle = .single
text.inlinePresentationIntent = .stronglyEmphasized // Bold
```

## WebKit Integration

### Basic WebView

```swift
import WebKit

WebView(url: URL(string: "https://www.apple.com"))
    .frame(height: 400)
```

### WebView with WebPage

```swift
@State private var page = WebPage()

WebView(page)
    .navigationTitle(page.title)
    .onAppear {
        if let url = URL(string: "https://www.apple.com") {
            let _ = page.load(URLRequest(url: url))
        }
    }
```

### JavaScript Execution

```swift
let script = "document.title"
let title = try await page.callJavaScript(script)
```

### Navigation Control

```swift
// Load content
page.load(URLRequest(url: url))
page.load(html: htmlString, baseURL: baseURL)

// Navigation
page.reload(fromOrigin: false)
page.stopLoading()

// Back/Forward
let canGoBack = !page.backForwardList.backList.isEmpty
if let backItem = page.backForwardList.backItem {
    page.load(backItem)
}
```

### Customization

```swift
WebView(url: url)
    .webViewBackForwardNavigationGestures(.disabled)
    .webViewMagnificationGestures(.enabled)
    .webViewLinkPreviews(.disabled)
    .webViewTextSelection(.enabled)
    .findNavigator(isPresented: $searchVisible)
```

## AlarmKit

### Authorization

```swift
// Info.plist: NSAlarmKitUsageDescription

func requestAuthorization() async -> Bool {
    do {
        let state = try await AlarmManager.shared.requestAuthorization()
        return state == .authorized
    } catch {
        return false
    }
}
```

### One-time Alarm

```swift
func createAlarm(hour: Int, minute: Int) async throws -> Alarm {
    let id = UUID()
    let time = Alarm.Schedule.Relative.Time(hour: hour, minute: minute)
    let schedule = Alarm.Schedule.relative(.init(time: time, repeats: .never))

    let alertContent = AlarmPresentation.Alert(
        title: "Wake Up",
        stopButton: .stopButton,
        secondaryButton: .snoozeButton,
        secondaryButtonBehavior: .countdown
    )

    let presentation = AlarmPresentation(alert: alertContent)

    struct EmptyMetadata: AlarmMetadata {}
    let attributes = AlarmAttributes(
        presentation: presentation,
        metadata: EmptyMetadata(),
        tintColor: .blue
    )

    let configuration = AlarmManager.AlarmConfiguration(
        countdownDuration: Alarm.CountdownDuration(preAlert: nil, postAlert: 9 * 60),
        schedule: schedule,
        attributes: attributes,
        sound: .default
    )

    return try await AlarmManager.shared.schedule(id: id, configuration: configuration)
}
```

### Weekly Repeating Alarm

```swift
let schedule = Alarm.Schedule.relative(.init(
    time: time,
    repeats: .weekly([.monday, .wednesday, .friday])
))
```

### Timer (Countdown)

```swift
let countdownDuration = Alarm.CountdownDuration(
    preAlert: seconds, // Time until alert
    postAlert: 10      // Snooze duration
)

let configuration = AlarmManager.AlarmConfiguration(
    countdownDuration: countdownDuration,
    schedule: nil, // No schedule for timer
    attributes: attributes,
    sound: .default
)
```

### Managing Alarms

```swift
// Get all alarms
let alarms = try AlarmManager.shared.alarms

// Pause/Resume
try await AlarmManager.shared.pause(id: alarmID)
try await AlarmManager.shared.resume(id: alarmID)

// Cancel
try await AlarmManager.shared.cancel(id: alarmID)

// Observe changes
for await alarms in AlarmManager.shared.alarmUpdates {
    updateUI(with: alarms)
}
```

## 3D Charts

### Basic Surface Plot

```swift
import Charts

Chart3D {
    SurfacePlot(
        x: "X Axis",
        y: "Y Axis",
        z: "Z Axis",
        function: { x, y in
            sin(x) * cos(y)
        }
    )
}
```

### Interactive Rotation

```swift
@State private var chartPose: Chart3DPose = .default

Chart3D {
    SurfacePlot(...)
}
.chart3DPose($chartPose) // Bind for interactive rotation
```

### Predefined Poses

```swift
.chart3DPose(.default)
.chart3DPose(.front)
.chart3DPose(.top)
.chart3DPose(Chart3DPose(azimuth: .degrees(45), inclination: .degrees(30)))
```

### Camera Projection

```swift
.chart3DCameraProjection(.perspective)  // Objects smaller with distance
.chart3DCameraProjection(.orthographic) // Objects maintain size
```

### Styling Surface Plots

```swift
SurfacePlot(...)
    .foregroundStyle(Color.blue)
    .roughness(0.3)

// Height-based coloring
SurfacePlot(...)
    .foregroundStyle(Chart3DSurfaceStyle.heightBased(yRange: -1.0...1.0))

// Custom gradient
let gradient = Gradient(colors: [.blue, .green, .yellow, .red])
SurfacePlot(...)
    .foregroundStyle(Chart3DSurfaceStyle.heightBased(gradient, yRange: -1.0...1.0))
```

## References

- [SwiftUI SearchToolbarBehavior](https://developer.apple.com/documentation/SwiftUI/SearchToolbarBehavior)
- [Building Rich SwiftUI Text Experiences](https://developer.apple.com/documentation/SwiftUI/building-rich-swiftui-text-experiences)
- [WebKit for SwiftUI](https://developer.apple.com/documentation/WebKit/webkit-for-swiftui)
- [Scheduling an alarm with AlarmKit](https://developer.apple.com/documentation/AlarmKit/scheduling-an-alarm-with-alarmkit)
- [Chart3D Documentation](https://developer.apple.com/documentation/Charts/Chart3D)

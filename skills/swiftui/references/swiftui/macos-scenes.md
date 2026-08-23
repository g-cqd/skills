# macOS Scenes Reference

## Scene Types

| Scene | Availability | macOS-Only | Purpose |
|-------|-------------|:----------:|---------|
| `WindowGroup` | macOS 11+ | No | Multiple window instances, tabbed interface |
| `Window` | macOS 13+ | No | Singleton window; app quits when sole window closes |
| `UtilityWindow` | macOS 15+ | Yes | Floating tool palette; receives FocusedValues |
| `Settings` | macOS 11+ | Yes | Preferences window (Cmd+,) |
| `MenuBarExtra` | macOS 13+ | Yes | Persistent menu bar icon/menu |
| `DocumentGroup` | macOS 11+ | No | Document-based apps with File menu |

## Settings

```swift
Settings {
    TabView {
        Tab("General", systemImage: "gear") { GeneralSettingsView() }
        Tab("Advanced", systemImage: "star") { AdvancedSettingsView() }
    }
    .scenePadding()
    .frame(maxWidth: 350, minHeight: 100)
}
```

Open programmatically: `@Environment(\.openSettings) private var openSettings`

## MenuBarExtra

```swift
// Dropdown menu (default)
MenuBarExtra("Utility", systemImage: "hammer") {
    Button("Action") { }
    Divider()
    Button("Quit") { NSApplication.shared.terminate(nil) }
}

// Popover panel
MenuBarExtra("Status", systemImage: "chart.bar") {
    DashboardView().frame(width: 240)
}
.menuBarExtraStyle(.window)
```

Menu-bar-only app: sole scene + `LSUIElement = true` in Info.plist.

## WindowGroup vs Window

- `WindowGroup`: Multiple instances, app stays running after all windows closed
- `Window`: Singleton, app quits when closed (if sole scene)

```swift
// Open programmatically
@Environment(\.openWindow) private var openWindow
Button("Open") { openWindow(id: "connection-doctor") }
```

## UtilityWindow (macOS 15+)

Floating inspector/tool palette. Receives `FocusedValues` from active main window.

```swift
UtilityWindow("Photo Info", id: "photo-info") {
    PhotoInfoViewer()
}
```

## DocumentGroup

```swift
DocumentGroup(newDocument: TextFile()) { config in
    ContentView(document: config.$document)
}
```

Document type must conform to `FileDocument` or `ReferenceFileDocument`.

## Platform Conditionals

Always wrap macOS-only scenes:

```swift
#if os(macOS)
Settings { SettingsView() }
MenuBarExtra("Status", systemImage: "bolt") { StatusMenu() }
#endif
```

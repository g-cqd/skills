# macOS Window & Toolbar Styling Reference

## Toolbar Styles (macOS-only)

```swift
.windowToolbarStyle(.unified)          // Title + toolbar in single row
.windowToolbarStyle(.unifiedCompact)   // Reduced height
.windowToolbarStyle(.expanded)         // Title above toolbar
.windowToolbarStyle(.unified(showsTitle: false))
```

## Window Style

```swift
.windowStyle(.titleBar)        // Standard (default)
.windowStyle(.hiddenTitleBar)   // Chromeless for media players, immersive UX
```

## Window Sizing

```swift
WindowGroup {
    ContentView()
        .frame(minWidth: 600, minHeight: 400)
}
.defaultSize(width: 900, height: 600)
.defaultPosition(.center)
.windowResizability(.contentMinSize)
```

| Resizability | Behavior |
|-------------|----------|
| `.automatic` | System decides |
| `.contentSize` | Fixed to content, no resize |
| `.contentMinSize` | Resizable with minimum from content frame |

### Precise Positioning (macOS 15+)

```swift
.windowIdealPlacement { context in
    let screen = context.defaultDisplay.visibleArea
    return WindowPlacement(x: screen.midX, y: screen.midY,
                           width: screen.width / 2, height: screen.height)
}
```

## Navigation Layout

### NavigationSplitView
On macOS, columns display side-by-side with translucent sidebar material.

```swift
NavigationSplitView {
    SidebarView()
        .navigationSplitViewColumnWidth(min: 180, ideal: 220, max: 300)
} detail: {
    DetailView()
}
```

### Inspector (macOS 14+)
Trailing-edge panel, resizable by dragging.

```swift
MainContent()
    .inspector(isPresented: $showInspector) {
        InspectorView()
            .inspectorColumnWidth(min: 200, ideal: 250, max: 400)
    }
```

## Commands & Keyboard

```swift
.commands {
    CommandMenu("Tools") {
        Button("Run Analysis") { }
            .keyboardShortcut("r", modifiers: [.command, .shift])
    }
    CommandGroup(after: .newItem) {
        Button("New From Template...") { }
    }
}
```

Placements: `.newItem`, `.saveItem`, `.help`, `.toolbar`, `.sidebar`.

## Best Practices

- `.unified`/`.unifiedCompact` for most apps
- Set min frame + `.windowResizability(.contentMinSize)`
- `NavigationSplitView` for sidebar (not `HSplitView`)
- `Inspector` for supplementary panels
- Define `Commands` for repeatable actions
- `#if os(macOS)` for macOS-only window config

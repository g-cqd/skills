# Apple 2025 Platform APIs — Domain Guide

WWDC 2025 APIs for iOS 26/macOS 26. Always gate new APIs with `#available` and provide fallbacks.

## Decision Tree

### Visual Design
- Liquid Glass for SwiftUI → `SwiftUI-Implementing-Liquid-Glass-Design.md`
- Liquid Glass for UIKit → `UIKit-Implementing-Liquid-Glass-Design.md`
- Liquid Glass for AppKit → `AppKit-Implementing-Liquid-Glass-Design.md`
- Liquid Glass for Widgets → `WidgetKit-Implementing-Liquid-Glass-Design.md`
- Overview → `liquid-glass.md`

### Swift 6.2
- Concurrency updates (`@concurrent`, default isolation) → `Swift-Concurrency-Updates.md`
- InlineArray, Span → `Swift-InlineArray-Span.md`
- Language overview → `swift-updates.md`

### AI/ML
- On-device LLM → `FoundationModels-Using-on-device-LLM-in-your-app.md`
- Visual Intelligence → `Implementing-Visual-Intelligence-in-iOS.md`

### SwiftUI Features
- Toolbars → `SwiftUI-New-Toolbar-Features.md`
- Styled text editing → `SwiftUI-Styled-Text-Editing.md`
- WebKit integration → `SwiftUI-WebKit-Integration.md`
- AlarmKit → `SwiftUI-AlarmKit-Integration.md`
- 3D Charts → `Swift-Charts-3D-Visualization.md`
- Overview → `swiftui-features.md`

### Framework Updates
- AppIntents → `AppIntents-Updates.md`
- StoreKit → `StoreKit-Updates.md`
- SwiftData inheritance → `SwiftData-Class-Inheritance.md`
- MapKit GeoToolbox → `MapKit-GeoToolbox-PlaceDescriptors.md`
- AttributedString → `Foundation-AttributedString-Updates.md`
- Overview → `frameworks.md`

### Platform-Specific
- visionOS widgets → `Widgets-for-visionOS.md`
- Accessibility → `accessibility.md`
- visionOS overview → `visionos.md`

## Quick Reference

### Liquid Glass
```swift
Text("Hello").glassEffect()
Button("Action") { }.buttonStyle(.glass)
GlassEffectContainer(spacing: 20) { /* Glass views merge */ }
```

### Swift 6.2 Concurrency
```swift
@MainActor class ViewModel { }
@concurrent func heavyComputation() async -> Result { }
```

### Foundation Models
```swift
let session = LanguageModelSession(instructions: "Be concise")
let response = try await session.respond(to: prompt)
```

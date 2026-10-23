# Apple 2025 Platform APIs — Domain Guide

WWDC 2025 APIs for iOS 26/macOS 26. Always gate new APIs with `#available` and provide fallbacks.

## Decision Tree

### Visual Design
- Liquid Glass for UIKit → `UIKit-Implementing-Liquid-Glass-Design.md`
- Liquid Glass for AppKit → `AppKit-Implementing-Liquid-Glass-Design.md`
- Liquid Glass for Widgets → `WidgetKit-Implementing-Liquid-Glass-Design.md`
- Liquid Glass for SwiftUI → `swiftui` skill, `references/swiftui/liquid-glass.md`

### Swift 6.2
- Approachable concurrency, `@concurrent`, default isolation → `swift` skill, `references/concurrency/migration.md`
- `InlineArray`, `Span` → `swift` skill, `references/swift/inlinearray-and-span.md`

### AI/ML
- On-device LLM → `FoundationModels-Using-on-device-LLM-in-your-app.md`
- Visual Intelligence → `Implementing-Visual-Intelligence-in-iOS.md`

### SwiftUI features
- Toolbars, styled text editing, WebKit, 3D charts → `swiftui` skill (`references/swiftui/`)
- AlarmKit → `SwiftUI-AlarmKit-Integration.md`

### Framework Updates
- App Intents best practices and traps → `app-intents-specialist/references/` in the Xcode skill pack (`SKILL.md` §2.1)
- App Intents iOS 26 and 27 APIs → `app-intents-whats-new-27/references/` in the Xcode skill pack (same table)
- StoreKit → `StoreKit-Updates.md`
- SwiftData inheritance → `SwiftData-Class-Inheritance.md`
- MapKit GeoToolbox → `MapKit-GeoToolbox-PlaceDescriptors.md`
- AttributedString → `Foundation-AttributedString-Updates.md`
- Overview → `frameworks.md`

### Platform-Specific
- visionOS widgets → `Widgets-for-visionOS.md`
- Assistive Access and accessibility updates → `accessibility.md`
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

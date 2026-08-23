# Snapshot Testing

## What It Is

Snapshot testing captures the **rendered output** of a component (view, data structure, or serialized format) and compares it against a previously recorded reference. Any difference fails the test, forcing explicit review of changes.

## Types of Snapshot Tests

| Type | What's Captured | Use Case |
|------|----------------|----------|
| **Image snapshot** | Rendered pixels of a view | UI layout, styling, visual regression |
| **Text snapshot** | String representation | JSON responses, formatted output, logs |
| **View hierarchy** | SwiftUI/UIKit view tree | Structural changes without pixel comparison |

## Tools for Swift

### swift-snapshot-testing (Point-Free)
The standard library for Swift snapshot testing.

```swift
import SnapshotTesting
import SwiftUI

@Test
func `profile card renders correctly`() {
    let view = ProfileCard(user: .fixture(name: "Alice", role: "Engineer"))
    assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone13)))
}

@Test
func `profile card renders correctly in dark mode`() {
    let view = ProfileCard(user: .fixture(name: "Alice", role: "Engineer"))
        .environment(\.colorScheme, .dark)
    assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone13)))
}

// Text snapshot for API responses
@Test
func `user response JSON structure`() {
    let response = UserResponse(id: "123", name: "Alice", role: .admin)
    assertSnapshot(of: response, as: .json)
}
```

## When to Use Snapshots

| Good Fit | Poor Fit |
|----------|----------|
| Complex UI layouts | Simple views with 1-2 elements |
| Design system components | Rapidly changing UI during development |
| API response format stability | Dynamic content (dates, random IDs) |
| Accessibility tree verification | Logic testing (use unit tests instead) |
| Multi-device/multi-theme verification | |

## Snapshot Test Workflow

```
1. First run: No reference exists → test records the snapshot → TEST FAILS (expected)
2. Review the snapshot manually — is it correct?
3. If correct: commit the snapshot file as the reference
4. Future runs: compare against reference
5. If difference detected: test fails → review diff
6. If change is intentional: delete old snapshot, re-record
7. If change is a regression: fix the code
```

## Best Practices

| Practice | Why |
|----------|-----|
| **Commit snapshots to version control** | References must be shared across team |
| **Review snapshot diffs in PRs** | Visual changes should be intentional |
| **Use fixed data (no dates/UUIDs)** | Avoid flaky snapshots |
| **Test multiple configurations** | Light/dark, accessibility sizes, devices |
| **Use `record: true` to update intentionally** | Don't blindly re-record |
| **Separate snapshot tests from unit tests** | They're slower and have different failure modes |
| **Name snapshots descriptively** | Auto-generated names are fragile across renames |

## Handling Dynamic Content

```swift
// BAD: Will produce different snapshot every run
let view = MessageView(timestamp: Date())

// GOOD: Fixed date for deterministic snapshot
let view = MessageView(timestamp: Date(timeIntervalSince1970: 1700000000))

// GOOD: Inject a formatter that returns fixed strings
let view = MessageView(timestamp: date, formatter: FixedDateFormatter("Nov 14, 2023"))
```

## Perceptual Diffing

Image snapshots can fail due to **sub-pixel rendering differences** across machines/OS versions. Strategies:
- Use `precision: 0.99` to allow 1% pixel variance
- Run snapshot tests only on CI with fixed OS/hardware
- Use text/hierarchy snapshots when pixel precision isn't needed

## Checklist

- [ ] Design system components have snapshot tests
- [ ] Snapshots cover light mode, dark mode, and Dynamic Type sizes
- [ ] Fixed/deterministic data used (no Date(), no UUID())
- [ ] Snapshot files committed to version control
- [ ] Snapshot diffs reviewed in PRs
- [ ] Multiple device sizes tested for responsive layouts
- [ ] Accessibility snapshots included for VoiceOver tree
- [ ] Perceptual threshold set to avoid false positives

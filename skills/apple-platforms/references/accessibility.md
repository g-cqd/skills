# Assistive Access Implementation

Assistive Access is an iOS feature that provides a simplified user interface designed for users with cognitive disabilities. When enabled, the device presents a streamlined experience with large icons, simplified navigation, and reduced cognitive load.

## Detecting Assistive Access

```swift
import UIKit

// Check if Assistive Access is enabled
let isAssistiveAccessEnabled = UIAccessibility.isAssistiveAccessEnabled

// Observe changes
NotificationCenter.default.addObserver(
    self,
    selector: #selector(assistiveAccessChanged),
    name: UIAccessibility.assistiveAccessStatusDidChangeNotification,
    object: nil
)

@objc func assistiveAccessChanged() {
    if UIAccessibility.isAssistiveAccessEnabled {
        configureForAssistiveAccess()
    } else {
        configureForStandardAccess()
    }
}
```

## Adapting Your App

### Simplifying Navigation

```swift
struct ContentView: View {
    @Environment(\.accessibilityEnabled) var accessibilityEnabled

    var body: some View {
        if UIAccessibility.isAssistiveAccessEnabled {
            SimplifiedHomeView()
        } else {
            StandardHomeView()
        }
    }
}

struct SimplifiedHomeView: View {
    var body: some View {
        VStack(spacing: 24) {
            // Large, clearly labeled buttons
            NavigationLink(destination: MessagesView()) {
                LargeActionButton(
                    icon: "message.fill",
                    title: "Messages"
                )
            }

            NavigationLink(destination: PhotosView()) {
                LargeActionButton(
                    icon: "photo.fill",
                    title: "Photos"
                )
            }
        }
        .padding()
    }
}
```

### Large Action Buttons

```swift
struct LargeActionButton: View {
    let icon: String
    let title: String

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 60))
                .foregroundStyle(.primary)

            Text(title)
                .font(.title)
                .fontWeight(.semibold)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}
```

### Reduced Information Density

```swift
struct ContactRow: View {
    let contact: Contact

    var body: some View {
        if UIAccessibility.isAssistiveAccessEnabled {
            // Simplified: just name and photo
            HStack(spacing: 16) {
                ContactPhoto(contact: contact, size: 80)
                Text(contact.name)
                    .font(.title2)
                    .fontWeight(.medium)
            }
            .padding()
        } else {
            // Standard: full details
            HStack {
                ContactPhoto(contact: contact, size: 44)
                VStack(alignment: .leading) {
                    Text(contact.name)
                    Text(contact.phoneNumber)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}
```

### Clear Confirmation Dialogs

```swift
struct DeleteConfirmation: View {
    @Binding var isPresented: Bool
    let onConfirm: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "trash.fill")
                .font(.system(size: 60))
                .foregroundStyle(.red)

            Text("Delete this item?")
                .font(.title)
                .fontWeight(.semibold)

            HStack(spacing: 20) {
                Button("No") {
                    isPresented = false
                }
                .buttonStyle(LargeSecondaryButtonStyle())

                Button("Yes") {
                    onConfirm()
                    isPresented = false
                }
                .buttonStyle(LargePrimaryButtonStyle())
            }
        }
        .padding(32)
    }
}
```

## UIKit Adaptations

```swift
class ViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        configureForAccessibility()

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(configureForAccessibility),
            name: UIAccessibility.assistiveAccessStatusDidChangeNotification,
            object: nil
        )
    }

    @objc func configureForAccessibility() {
        if UIAccessibility.isAssistiveAccessEnabled {
            // Larger buttons
            actionButton.configuration?.buttonSize = .large

            // Simplified text
            titleLabel.font = .preferredFont(forTextStyle: .title1)

            // Remove secondary information
            subtitleLabel.isHidden = true
            detailStackView.isHidden = true

            // Increase spacing
            mainStackView.spacing = 24
        } else {
            // Standard configuration
            actionButton.configuration?.buttonSize = .medium
            titleLabel.font = .preferredFont(forTextStyle: .headline)
            subtitleLabel.isHidden = false
            detailStackView.isHidden = false
            mainStackView.spacing = 8
        }
    }
}
```

## Best Practices

### 1. Essential Features Only

When Assistive Access is enabled, focus on core functionality:

```swift
var availableFeatures: [Feature] {
    if UIAccessibility.isAssistiveAccessEnabled {
        return [.messages, .photos, .calls] // Core features only
    } else {
        return Feature.allCases
    }
}
```

### 2. Large Touch Targets

Ensure minimum 44pt touch targets, preferably larger:

```swift
struct AssistiveAccessButton: View {
    let action: () -> Void
    let title: String

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.title2)
                .fontWeight(.semibold)
                .frame(minHeight: 60)
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.bordered)
    }
}
```

### 3. Clear Visual Hierarchy

```swift
struct SimplifiedListView: View {
    let items: [Item]

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 16) {
                ForEach(items) { item in
                    ItemCard(item: item)
                        .frame(minHeight: 80)
                }
            }
            .padding()
        }
    }
}
```

### 4. Avoid Time Pressure

```swift
// Don't auto-dismiss notifications quickly
func showNotification() {
    let duration: TimeInterval = UIAccessibility.isAssistiveAccessEnabled ? 10 : 3
    showTemporaryNotification(duration: duration)
}
```

### 5. Consistent Navigation

```swift
struct NavigationWrapper<Content: View>: View {
    let title: String
    let content: Content

    var body: some View {
        NavigationStack {
            content
                .navigationTitle(title)
                .toolbar {
                    if UIAccessibility.isAssistiveAccessEnabled {
                        // Always show home button for easy navigation
                        ToolbarItem(placement: .navigationBarLeading) {
                            Button("Home", systemImage: "house.fill") {
                                navigateToHome()
                            }
                            .font(.title2)
                        }
                    }
                }
        }
    }
}
```

## Testing

1. Enable Assistive Access in Settings > Accessibility > Assistive Access
2. Test all primary user flows
3. Verify touch targets are adequate
4. Check text is readable
5. Ensure navigation is clear and simple

## References

- [Assistive Access Documentation](https://developer.apple.com/documentation/UIKit/UIAccessibility/isAssistiveAccessEnabled)
- [Accessibility Programming Guide](https://developer.apple.com/documentation/accessibility)
- [Human Interface Guidelines: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)

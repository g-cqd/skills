# Framework Updates

## Foundation Models (On-Device LLM)

The Foundation Models framework provides on-device language model capabilities with privacy-preserving local processing.

### Checking Availability

```swift
import FoundationModels

let model = SystemLanguageModel.default

switch model.availability {
case .available:
    // Ready to use
case .unavailable(let reason):
    switch reason {
    case .deviceNotSupported:
        // Device doesn't meet requirements
    case .modelNotReady:
        // Model downloading or preparing
    case .notEnoughMemory:
        // Insufficient available memory
    @unknown default:
        break
    }
}
```

### Basic Text Generation

```swift
let session = LanguageModelSession()

let response = try await session.respond(to: "What is the capital of France?")
print(response.content) // "Paris is the capital of France."
```

### System Instructions

```swift
let instructions = """
You are a helpful cooking assistant.
Provide concise recipes with clear steps.
Always include cooking times.
"""

let session = LanguageModelSession(instructions: instructions)
let response = try await session.respond(to: "How do I make pancakes?")
```

### Guided Generation (Structured Output)

```swift
@Generable
struct Recipe {
    var name: String
    var ingredients: [String]
    var steps: [String]
    var cookingTimeMinutes: Int
}

let session = LanguageModelSession()
let recipe = try await session.respond(
    to: "Create a simple pasta recipe",
    generating: Recipe.self
)

print(recipe.name)
print(recipe.cookingTimeMinutes)
```

### Streaming Responses

```swift
let session = LanguageModelSession()

for try await partial in session.streamResponse(to: prompt) {
    print(partial.content, terminator: "")
}
```

### Tool Calling

```swift
@Tool
struct WeatherTool {
    @Argument var location: String

    func run() async throws -> String {
        // Fetch weather data
        return "Sunny, 72°F"
    }
}

let session = LanguageModelSession(tools: [WeatherTool.self])
let response = try await session.respond(to: "What's the weather in San Francisco?")
```

### Configuration

```swift
var config = LanguageModelSession.Configuration()
config.temperature = 0.7
config.maximumResponseTokens = 1000

let session = LanguageModelSession(configuration: config)
```

## AppIntents Updates

### Intent Modes

```swift
struct SearchIntent: AppIntent {
    static let title: LocalizedStringResource = "Search"

    @Parameter var query: String

    // Specify execution modes
    static let modes: [IntentMode] = [
        .foreground,
        .background,
        .widget
    ]

    func perform() async throws -> some IntentResult {
        // Perform search
        return .result()
    }
}
```

### Spotlight Integration

```swift
struct MyEntity: AppEntity {
    static var defaultQuery: EntityQuery<MyEntity> {
        MyEntityQuery()
    }

    var displayName: String
    var searchKeywords: [String]

    // Spotlight indexing
    var spotlightAttributes: SpotlightAttributes {
        SpotlightAttributes(
            title: displayName,
            contentDescription: description,
            thumbnailData: thumbnailData
        )
    }
}
```

### Visual Intelligence Integration

```swift
struct VisualSearchIntent: AppIntent {
    static let title: LocalizedStringResource = "Visual Search"

    @Parameter var image: IntentFile

    static let supportedTriggers: [IntentTrigger] = [
        .visualIntelligence
    ]

    func perform() async throws -> some IntentResult {
        // Process image
        return .result()
    }
}
```

## StoreKit Updates

### AppTransaction Updates (iOS 18.4+)

```swift
let appTransaction = try await AppTransaction.shared

// New fields
let transactionID = appTransaction.appTransactionID  // Unique per Apple Account
let platform = appTransaction.originalPlatform       // iOS, macOS, tvOS, visionOS
```

### Transaction Updates

```swift
// New API: Multiple entitlements for same product
for await verificationResult in Transaction.currentEntitlements(for: "product.id") {
    switch verificationResult {
    case .verified(let transaction):
        let appTransactionID = transaction.appTransactionID
        if let offerPeriod = transaction.offerPeriod {
            // Handle offer period
        }
    case .unverified(_, let error):
        print("Verification failed: \(error)")
    }
}
```

### SubscriptionOfferView

```swift
// Basic usage
SubscriptionOfferView(productID: "subscription.monthly")
    .prefersPromotionalIcon(true)

// With custom icon
SubscriptionOfferView(productID: "subscription.monthly") {
    Image("premium_icon")
        .resizable()
        .frame(width: 40, height: 40)
}

// Show upgrades only
SubscriptionOfferView(groupID: "subscription.group", visibleRelationship: .upgrade)

// Detail action
SubscriptionOfferView(productID: "subscription.monthly")
    .subscriptionOfferViewDetailAction {
        showSubscriptionStore = true
    }
```

### Subscription Status Tracking

```swift
@main
struct MyApp: App {
    @State private var customerStatus: SubscriptionStatus = .unknown

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(\.customerSubscriptionStatus, customerStatus)
                .subscriptionStatusTask(for: "subscription.group") { statuses in
                    if statuses.contains(where: { $0.state == .subscribed }) {
                        customerStatus = .subscribed
                    } else {
                        customerStatus = .notSubscribed
                    }
                }
        }
    }
}
```

## SwiftData Class Inheritance

### Defining Inheritance Hierarchy

```swift
import SwiftData

@Model
class Animal {
    var name: String
    var birthDate: Date

    init(name: String, birthDate: Date) {
        self.name = name
        self.birthDate = birthDate
    }
}

@Model
final class Dog: Animal {
    var breed: String

    init(name: String, birthDate: Date, breed: String) {
        self.breed = breed
        super.init(name: name, birthDate: birthDate)
    }
}

@Model
final class Cat: Animal {
    var isIndoor: Bool

    init(name: String, birthDate: Date, isIndoor: Bool) {
        self.isIndoor = isIndoor
        super.init(name: name, birthDate: birthDate)
    }
}
```

### Querying with Inheritance

```swift
// Fetch all animals
let allAnimals = try modelContext.fetch(FetchDescriptor<Animal>())

// Fetch only dogs
let dogs = try modelContext.fetch(FetchDescriptor<Dog>())

// Polymorphic relationships
@Model
class Owner {
    var name: String
    var pets: [Animal] = []
}
```

### Rules

- Base class doesn't need `final`
- Subclasses should be `final`
- All classes in hierarchy need `@Model`
- Relationships work polymorphically

## Visual Intelligence

### Camera-Based Search

```swift
import VisualIntelligence

let session = VisualIntelligenceSession()

// Capture and analyze
let result = try await session.analyze(image: capturedImage)

for item in result.identifiedItems {
    print(item.label)
    print(item.boundingBox)
    print(item.confidence)
}
```

### Integration with AppIntents

```swift
struct ProductSearchIntent: AppIntent {
    static let title: LocalizedStringResource = "Find Product"

    @Parameter var image: IntentFile

    static let supportedTriggers: [IntentTrigger] = [
        .visualIntelligence
    ]

    func perform() async throws -> some IntentResult {
        let imageData = try await image.data
        // Search product catalog
        return .result(value: foundProduct)
    }
}
```

## MapKit/GeoToolbox

### Place Descriptors

```swift
import GeoToolbox
import MapKit

// Create from address
let fountain = PlaceDescriptor(
    representations: [.address("121 Main St, City")],
    commonName: "City Fountain"
)

// Create from coordinates
let landmark = PlaceDescriptor(
    representations: [
        .coordinate(CLLocationCoordinate2D(latitude: 40.6892, longitude: -74.0445)),
        .address("Liberty Island, New York")
    ],
    commonName: "Statue of Liberty"
)

// From MKMapItem
let descriptor = PlaceDescriptor(item: mapItem)
```

### Accessing Properties

```swift
if let coordinate = descriptor.coordinate {
    print("Lat: \(coordinate.latitude)")
}

if let address = descriptor.address {
    print("Address: \(address)")
}
```

### Geocoding

```swift
// Forward geocoding
let request = MKGeocodingRequest(addressString: "1 Apple Park Way")
let mapItems = try await request.mapItems

// Reverse geocoding
let location = CLLocation(latitude: 37.7749, longitude: -122.4194)
let reverseRequest = MKReverseGeocodingRequest(location: location)
let results = try await reverseRequest.mapItems
```

### Service Identifiers

```swift
let place = PlaceDescriptor(
    representations: [.coordinate(coordinate)],
    commonName: "Location",
    supportingRepresentations: [
        .serviceIdentifiers([
            "com.apple.maps": "AppleMapsID",
            "com.google.maps": "GoogleMapsID"
        ])
    ]
)

let appleID = place.serviceIdentifier(for: "com.apple.maps")
```

## AttributedString Updates

### New Writing Direction Support

```swift
var text = AttributedString("Hello")
text.writingDirection = .rightToLeft
```

### Enhanced Localization

```swift
let localized = AttributedString(
    localized: "Welcome \(username)",
    options: .init(applyDefaultAttributes: true)
)
```

### Custom Attributes

```swift
enum MyAttribute: AttributedStringKey {
    typealias Value = String
    static let name = "myCustomAttribute"
}

extension AttributeScopes {
    struct MyAppAttributes: AttributeScope {
        let myAttribute: MyAttribute
    }
    var myApp: MyAppAttributes.Type { MyAppAttributes.self }
}

var text = AttributedString("Custom")
text.myApp.myAttribute = "value"
```

## References

- [FoundationModels Documentation](https://developer.apple.com/documentation/FoundationModels)
- [App Intents Documentation](https://developer.apple.com/documentation/AppIntents)
- [StoreKit Documentation](https://developer.apple.com/documentation/StoreKit)
- [SwiftData Documentation](https://developer.apple.com/documentation/SwiftData)
- [GeoToolbox Documentation](https://developer.apple.com/documentation/GeoToolbox)
- [MapKit Documentation](https://developer.apple.com/documentation/MapKit)

# Test Doubles

## Hierarchy

| Type | Purpose | Example |
|------|---------|---------|
| **Dummy** | Fill parameters, never used | Empty closure |
| **Stub** | Canned answers | `MockAPIClient(returning: .success(user))` |
| **Spy** | Records calls | Tracks how many times `fetch` invoked |
| **Mock** | Expectations on calls | Fails if wrong methods called |
| **Fake** | Working but simplified | In-memory database |

## Protocol-Based Mocking

```swift
// Define protocol
protocol HTTPClient: Sendable {
  func get(_ path: String) async throws -> Data
}

// Production
struct URLSessionHTTPClient: HTTPClient {
  func get(_ path: String) async throws -> Data {
    let (data, _) = try await URLSession.shared.data(from: URL(string: path)!)
    return data
  }
}

// Mock for testing
struct MockHTTPClient: HTTPClient {
  let result: Result<Data, Error>

  func get(_ path: String) async throws -> Data {
    try result.get()
  }
}
```

## Spy Pattern

```swift
final class SpyAnalytics: AnalyticsTracking {
  private(set) var trackedEvents: [(name: String, properties: [String: String])] = []

  func track(_ event: String, properties: [String: String]) {
    trackedEvents.append((event, properties))
  }
}

// In test
let spy = SpyAnalytics()
viewModel.trackPurchase()
#expect(spy.trackedEvents.count == 1)
#expect(spy.trackedEvents[0].name == "purchase_completed")
```

## Fixtures

```swift
enum UserFixtures {
  static let validUser = User(id: "123", name: "Alice", email: "alice@test.com")
  static let emptyName = User(id: "456", name: "", email: "bob@test.com")
  static let invalidEmail = User(id: "789", name: "Carol", email: "invalid")
}
```

Keep fixtures in `_TestSupport/Fixtures/` and share across test files.

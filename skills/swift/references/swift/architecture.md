# Architecture

## SOLID Principles

### Single Responsibility
Each type has one reason to change. Split types that handle multiple concerns.

### Open/Closed
Types are open for extension (protocol conformance, composition) but closed for modification.

### Liskov Substitution
Subtypes must be substitutable for their base types without altering correctness.

### Interface Segregation
Prefer many small protocols over one large one. Clients should not depend on methods they don't use.

### Dependency Inversion
High-level modules depend on abstractions (protocols), not concrete implementations.

## Protocol-Oriented Programming

Define behavior with protocols first:

```swift
protocol DataFetching: Sendable {
  func fetch(from url: URL) async throws(NetworkError) -> Data
}

// Concrete implementation
actor NetworkService: DataFetching {
  private let session: URLSession

  init(session: URLSession = .shared) {
    self.session = session
  }

  func fetch(from url: URL) async throws(NetworkError) -> Data {
    guard let (data, response) = try? await session.data(from: url) else {
      throw .connectionFailed
    }
    guard let http = response as? HTTPURLResponse,
          (200...299).contains(http.statusCode) else {
      throw .invalidResponse(code: (response as? HTTPURLResponse)?.statusCode ?? -1)
    }
    return data
  }
}
```

## Composition over Inheritance

Prefer protocol conformance and struct composition over class inheritance:

```swift
// Prefer this
struct UserProfileFeature {
  let fetcher: any DataFetching
  let cache: any Caching
  let analytics: any AnalyticsTracking
}

// Over this
class BaseViewController: UIViewController { /* shared logic */ }
class UserProfileViewController: BaseViewController { /* ... */ }
```

## Dependency Injection

All dependencies are injectable for testability:

```swift
// Protocol defines the contract
protocol UserRepository: Sendable {
  func user(id: String) async throws -> User
}

// Production implementation
struct RemoteUserRepository: UserRepository {
  private let client: any HTTPClient

  init(client: any HTTPClient) {
    self.client = client
  }

  func user(id: String) async throws -> User {
    let data = try await client.get("/users/\(id)")
    return try JSONDecoder().decode(User.self, from: data)
  }
}

// Test mock
struct MockUserRepository: UserRepository {
  var result: Result<User, Error>

  func user(id: String) async throws -> User {
    try result.get()
  }
}
```

## Module Boundaries

- **High cohesion**: Related types live together
- **Low coupling**: Modules communicate through protocols
- **Clear boundaries**: Each module has a defined public API surface

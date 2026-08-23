# Type System

## Value Types First

Default to `struct` and `enum`. Use `class` only when you need:
- Reference semantics (shared identity)
- Inheritance hierarchies
- Objective-C interop

```swift
// Prefer struct
struct User: Sendable, Codable {
  let id: String
  var name: String
  var email: String
}

// Prefer enum for fixed variants
enum PaymentMethod: Sendable {
  case creditCard(last4: String)
  case applePay
  case bankTransfer(routingNumber: String)
}
```

## Final by Default

Mark all classes `final` to enable devirtualization:

```swift
final class ImageCache {
  private var cache: [URL: Data] = [:]
}
```

Only omit `final` when the class is explicitly designed for subclassing.

## Guard Early

Use `guard let` for early exits. Avoid nested `if let` pyramids:

```swift
// Prefer
func process(_ input: String?) throws -> Result {
  guard let input, !input.isEmpty else {
    throw ValidationError.emptyInput
  }
  guard let parsed = Parser.parse(input) else {
    throw ValidationError.invalidFormat
  }
  return transform(parsed)
}

// Avoid
func process(_ input: String?) throws -> Result {
  if let input {
    if !input.isEmpty {
      if let parsed = Parser.parse(input) {
        return transform(parsed)
      }
    }
  }
  throw ValidationError.invalid
}
```

## Strong Typing

No `Any` or `[String: Any]`. Define `Codable` models:

```swift
// Avoid
func handle(response: [String: Any]) { }

// Prefer
struct APIResponse: Codable, Sendable {
  let status: String
  let data: UserData
}
```

## Error Handling

### Typed Throws (Swift 6)
```swift
enum NetworkError: Error, Sendable {
  case connectionFailed
  case invalidResponse(code: Int)
  case decodingFailed(underlying: any Error)
}

func fetch(from url: URL) async throws(NetworkError) -> Data {
  // Compiler enforces only NetworkError can be thrown
}
```

### Custom Error Types
Define specific `Error` enums per domain:
```swift
enum ValidationError: Error, Sendable {
  case emptyInput
  case tooLong(max: Int)
  case invalidFormat(reason: String)
}
```

### Rules
- **Never silence errors**: Empty `catch` blocks are forbidden
- **Handle or propagate**: Every error must be addressed
- **Use `preconditionFailure`** for programmer errors indicating logic bugs

## Generics

Use generics to write reusable, type-safe code:

```swift
struct Cache<Key: Hashable & Sendable, Value: Sendable>: Sendable {
  private var storage: [Key: Value] = [:]

  mutating func set(_ value: Value, forKey key: Key) {
    storage[key] = value
  }

  func get(_ key: Key) -> Value? {
    storage[key]
  }
}
```

Use `some` for opaque return types and `any` for existential types:

```swift
// Opaque: caller gets a concrete (hidden) type
func makeService() -> some DataFetching { NetworkService() }

// Existential: caller gets a type-erased box
func makeService() -> any DataFetching { NetworkService() }
```

## Access Control

| Level | Scope | Use When |
|-------|-------|----------|
| `private` | Declaration only | Default for everything |
| `fileprivate` | Same file | Extensions in same file need access |
| `internal` | Same module | Module-wide access (implicit default) |
| `public` | Other modules, no subclass/override | Intentional API with documentation |
| `open` | Other modules, allows subclass/override | Designed for external extension |

Start `private`, widen only as needed. `public` APIs require documentation.

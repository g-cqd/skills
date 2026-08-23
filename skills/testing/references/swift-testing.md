# Swift Testing Framework

## Core Features

### @Test with Descriptive Names
```swift
@Test(.tags(.networking))
func `fetches user profile successfully`() async throws {
  // ...
}
```

### #expect for Assertions
```swift
#expect(user.id == "123")
#expect(user.name == "Alice")
#expect(users.isEmpty)
```

Superior diagnostics — reports multiple failures per test.

### Error Testing
```swift
@Test
func `throws connectionError when network fails`() async {
  let service = UserService(client: MockHTTPClient(response: .failure(.connectionLost)))

  await #expect(throws: NetworkError.connectionLost) {
    try await service.fetch(id: "123")
  }
}
```

### Parameterized Tests
```swift
@Test("validates email formats", arguments: [
  ("valid@email.com", true),
  ("also.valid@domain.org", true),
  ("invalid", false),
  ("@missing.local", false),
  ("", false),
])
func emailValidation(email: String, expected: Bool) {
  #expect(EmailValidator.isValid(email) == expected)
}
```

### Test Tags
```swift
extension Tag {
  @Tag static var networking: Self
  @Tag static var database: Self
  @Tag static var ui: Self
  @Tag static var slow: Self
  @Tag static var boundary: Self
  @Tag static var error: Self
}
```

### Suites
```swift
@Suite("UserService Tests")
struct UserServiceTests {
  // Tests grouped logically
}
```

## Confirmation (Async Callback/Delegate Testing)

Use `confirmation` to test async callbacks without sleep or timeouts:

```swift
@Test
func `notifies delegate when user is saved`() async {
  await confirmation(expectedCount: 1) { confirmed in
    let sut = UserService(onSave: { confirmed() })
    await sut.save(User(name: "Alice"))
  }
}

@Test
func `publishes exactly 3 events`() async {
  await confirmation(expectedCount: 3) { confirmed in
    let sut = EventEmitter(onEvent: { confirmed() })
    await sut.emitBatch()
  }
}
```

`confirmation` fails if the callback count doesn't match `expectedCount`.
Prefer this over custom semaphores, sleep-based waits, or boolean flags.

## Attachments (Test Artifacts)

Attach data to test results for debugging:

```swift
@Test func `attaches the processed image and checks its size`() async throws {
  let result = try processImage(input)
  Attachment(result, named: "processed.png").attach()
  #expect(result.size == expectedSize)
}
```

## Async Testing

- Use `withMainSerialExecutor` for deterministic tests
- Use `SuspendingClock` for time-dependent tests
- Prefer Swift Testing's native async support over XCTest waiters
- **Never use `Task.sleep` for synchronization** — use `confirmation` or
  injected clocks instead
- For concurrency testing patterns (actors, isolation), see the swift skill's
  concurrency domain

# Documentation

## Doc Comments

Use `///` for all public APIs:

```swift
/// Brief description of the function.
///
/// Detailed explanation when the behavior is non-obvious.
///
/// - Parameters:
///   - url: The URL to fetch data from.
///   - timeout: Maximum wait time in seconds.
/// - Returns: The fetched data.
/// - Throws: `NetworkError.timeout` if the request exceeds the timeout.
/// - Complexity: O(1) for the call; network-bound for completion.
func fetch(from url: URL, timeout: TimeInterval) async throws(NetworkError) -> Data
```

### When to Document
- All `public` and `open` declarations (required)
- `internal` types with non-obvious behavior
- Complex algorithms with complexity annotations
- Skip documentation for obvious implementations (simple getters, trivial conformances)

## Code Organization with MARK

```swift
// MARK: - Public API

// MARK: - Protocol Conformances

// MARK: - Private Implementation

//===----------------------------------------------------------------------===//
// MARK: - Major Section Boundary
//===----------------------------------------------------------------------===//
```

## Complexity Annotations

Add `- Complexity:` to doc comments for any non-trivial algorithm:

```swift
/// Finds the k-th smallest element.
/// - Complexity: O(n) average, O(n²) worst case.
func kthSmallest(_ k: Int) -> Element
```

## Testing Documentation

| Element | Pattern | Example |
|---------|---------|---------|
| Test file | `[Feature]Tests.swift` | `UserServiceTests.swift` |
| Test method | `test[Action]_[Condition]()` | `testFetch_InvalidURL()` |
| Support modules | `_` prefix | `_TestSupport` |

# Swift 6.2 Language Updates

## Approachable Concurrency

Swift 6.2 introduces "Approachable Concurrency" to make Swift's concurrency model more intuitive while maintaining thread safety.

### Default Main Actor Isolation

New code can opt into default main actor isolation:

```swift
// Package.swift
.enableExperimentalFeature("DefaultIsolation", .mainActor)
```

When enabled:
- All types default to `@MainActor` isolation
- Properties, methods, and types are protected from data races
- Compiler enforces isolation boundaries automatically

### `@concurrent` Attribute

For explicit concurrent execution in default-MainActor code:

```swift
@MainActor // Assumed when default isolation is enabled
class DataProcessor {
    var results: [ProcessedData] = []

    // This runs on background threads
    @concurrent
    func processLargeDataset(_ data: [RawData]) async -> [ProcessedData] {
        // Heavy computation runs off main thread
        return data.map { process($0) }
    }

    func startProcessing(_ data: [RawData]) async {
        // processLargeDataset runs concurrently
        let processed = await processLargeDataset(data)
        // Back on main actor
        results = processed
    }
}
```

### Isolated Conformances

Adopt protocols with specific isolation requirements:

```swift
extension MyType: @MainActor SomeProtocol {
    // All protocol requirements are MainActor-isolated
    func protocolMethod() {
        // Guaranteed to run on main actor
    }
}
```

### Task Inheritance

Tasks inherit caller's isolation context:

```swift
@MainActor
class ViewModel {
    func loadData() {
        Task {
            // Inherits @MainActor isolation
            let data = await fetchData()
            self.updateUI(with: data) // Safe, on main actor
        }
    }
}
```

For explicit background execution:

```swift
Task.detached {
    // No inherited isolation
    await heavyWork()
}
```

### Migration Path

Swift 6.2 provides gradual adoption:

1. **Opt-in Mode**: Enable for new modules first
2. **Incremental Migration**: Add `@MainActor` to existing code
3. **`@concurrent` Marking**: Mark computation-heavy functions

## InlineArray

Fixed-capacity array with inline storage for performance-critical code.

### Basic Usage

```swift
// Create fixed-size array
var buffer = InlineArray<Int, 16>()

// Append elements
buffer.append(1)
buffer.append(2)
buffer.append(3)

// Access elements
print(buffer[0]) // 1
print(buffer.count) // 3
print(buffer.capacity) // 16
```

### Initialization

```swift
// From collection
let array: InlineArray<String, 4> = ["a", "b", "c", "d"]

// Repeating value
let zeros = InlineArray<Int, 8>(repeating: 0)

// From sequence (truncates if exceeds capacity)
let fromRange = InlineArray<Int, 5>(1...10) // Contains 1, 2, 3, 4, 5
```

### Safety and Performance

```swift
struct Packet {
    var header: InlineArray<UInt8, 16>
    var payload: InlineArray<UInt8, 1024>
}

// No heap allocation - all stored inline
// Bounds checked in debug, unchecked in release
```

### Methods

```swift
var arr = InlineArray<Int, 10>()
arr.append(1)
arr.append(contentsOf: [2, 3, 4])
arr.insert(0, at: 0)
arr.remove(at: 2)
arr.removeLast()
arr.removeAll()
```

## Span

Safe view over contiguous memory without ownership.

### Basic Usage

```swift
let array = [1, 2, 3, 4, 5]
let span = array.span

// Access elements safely
print(span[0]) // 1
print(span.count) // 5

// Iterate
for element in span {
    print(element)
}
```

### Slicing

```swift
let array = [1, 2, 3, 4, 5]
let span = array.span

// Create sub-spans
let first3 = span.prefix(3)
let last2 = span.suffix(2)
let middle = span[1..<4]
```

### Buffer Interop

```swift
// From UnsafeBufferPointer
let buffer = UnsafeBufferPointer<Int>(...)
let span = Span(buffer)

// From Data
let data = Data([0x01, 0x02, 0x03])
let byteSpan = data.span
```

### MutableSpan

```swift
var array = [1, 2, 3, 4, 5]
var span = array.mutableSpan

// Modify through span
span[0] = 10
print(array[0]) // 10
```

### Memory Safety

Spans provide:
- Bounds checking
- Lifetime safety through borrowing
- No ownership transfer
- Zero-copy views

```swift
// Safe: span borrows from array
let array = [1, 2, 3]
let span = array.span
// array cannot be modified while span is borrowed

// Unsafe pattern prevented by compiler:
// var array = [1, 2, 3]
// let span = array.span
// array.append(4) // Compiler error: cannot modify borrowed value
```

### Use Cases

```swift
// Zero-copy API design
func processData(_ data: Span<UInt8>) {
    // No copy, just view the memory
}

// Call with various sources
processData(array.span)
processData(data.span)
processData(buffer.span)
```

## References

- [SE-0461: Usability improvements for nonisolated](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0461-async-inherited-isolation.md)
- [SE-0453: InlineArray](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0453-vector.md)
- [SE-0447: Span](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0447-span-for-unsafe-pointer-family.md)
- [WWDC25: What's new in Swift](https://developer.apple.com/wwdc25/swift)

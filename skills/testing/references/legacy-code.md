# Legacy Code Techniques

When encountering code without tests, use these safe maneuvers from Michael Feathers' toolkit.

## The Sprout Method

**Use when**: Adding a feature to a massive, untestable method.

1. Create a new method for the new logic
2. TDD the new "sprout" independently
3. Call the sprout from the existing method

```swift
// Existing untestable method
func processOrder(_ order: Order) {
  // 200 lines of tangled logic...

  // NEW: sprout method, fully tested
  let discount = calculateLoyaltyDiscount(order)
  order.applyDiscount(discount)

  // ...more tangled logic
}

// Sprout — tested independently
func calculateLoyaltyDiscount(_ order: Order) -> Decimal {
  // Clean, testable logic
}
```

## The Wrap Method

**Use when**: Adding behavior before/after an existing call.

1. Rename `oldMethod()` to `oldMethodOriginal()`
2. Create new `oldMethod()` that wraps the original
3. Test the wrapping logic

```swift
// Before
func save() { /* complex save logic */ }

// After
func save() {
  validateBeforeSave()  // New, tested
  saveOriginal()        // Renamed original
  notifyAfterSave()     // New, tested
}
```

## Extract Interface

**Use when**: A class depends on a concrete "heavy" object.

1. Create a protocol matching the used methods
2. Make the heavy object conform
3. Inject the protocol, mock in tests

```swift
// 1. Extract protocol
protocol DataPersisting {
  func save(_ data: Data, forKey: String) throws
  func load(forKey: String) throws -> Data?
}

// 2. Conform existing class
extension CoreDataStore: DataPersisting { }

// 3. Inject and mock
struct MockPersistence: DataPersisting {
  var storage: [String: Data] = [:]
  func save(_ data: Data, forKey key: String) { storage[key] = data }
  func load(forKey key: String) -> Data? { storage[key] }
}
```

## General Approach

1. Identify the change point
2. Find the seam (where you can inject a test double)
3. Break dependencies at the seam
4. Write tests for the new behavior
5. Make the change

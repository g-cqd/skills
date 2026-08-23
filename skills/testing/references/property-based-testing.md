# Property-Based Testing

## What It Is

Property-based testing (PBT) **generates hundreds of random inputs** and verifies that properties (invariants) hold for all of them. Instead of hand-picking specific examples, you describe *what should always be true*, and the framework tries to break it.

## Why It Matters

- **Finds edge cases you didn't think of**: Empty strings, negative numbers, Unicode, huge inputs
- **Eliminates example selection bias**: Hand-picked tests reflect your assumptions — PBT challenges them
- **Tests invariants, not examples**: Properties describe the *contract*, not specific input/output pairs
- **Shrinking**: When a failure is found, the framework automatically finds the smallest failing input

## Example-Based vs. Property-Based

```swift
// Example-based: you choose inputs
@Test(arguments: [
    ([3, 1, 2], [1, 2, 3]),
    ([5, 5, 5], [5, 5, 5]),
    ([], []),
])
func sortExamples(input: [Int], expected: [Int]) {
    #expect(input.sorted() == expected)
}

// Property-based: framework generates inputs, you assert properties
// "For ANY array of integers, sorting should produce a result that is:
//  1. The same length as input
//  2. Contains the same elements
//  3. In non-decreasing order"
func verifySortProperties(input: [Int]) {
    let sorted = input.sorted()
    // Property 1: length preserved
    assert(sorted.count == input.count)
    // Property 2: same elements (as multiset)
    assert(sorted.sorted() == input.sorted())
    // Property 3: ordered
    for i in 0..<sorted.count - 1 {
        assert(sorted[i] <= sorted[i + 1])
    }
}
```

## Common Property Patterns

### 1. Round-Trip (Encode/Decode)
```swift
// For any valid model, encoding then decoding produces the original
func roundTrip<T: Codable & Equatable>(_ value: T) throws {
    let data = try JSONEncoder().encode(value)
    let decoded = try JSONDecoder().decode(T.self, from: data)
    #expect(decoded == value)
}
```

### 2. Idempotence
```swift
// Applying the operation twice gives the same result as once
func idempotent(_ input: String) {
    let once = input.trimmed()
    let twice = once.trimmed()
    #expect(once == twice)
}
```

### 3. Invariant Preservation
```swift
// After any valid operation, the invariant still holds
func balanceInvariant(deposits: [Decimal], withdrawals: [Decimal]) {
    var account = BankAccount(balance: 1000)
    for d in deposits { account.deposit(d) }
    for w in withdrawals { try? account.withdraw(w) }
    #expect(account.balance >= 0) // Invariant: never negative
}
```

### 4. Commutativity
```swift
// Order shouldn't matter
func mergeCommutative(a: Config, b: Config) {
    #expect(a.merged(with: b) == b.merged(with: a))
}
```

### 5. Oracle / Model-Based
```swift
// Compare your implementation against a known-correct (but slow) reference
func oracleTest(input: [Int]) {
    let fast = myCustomSort(input)
    let reference = input.sorted() // stdlib is the oracle
    #expect(fast == reference)
}
```

### 6. No-Crash / Robustness
```swift
// The function should never crash, regardless of input
func neverCrashes(input: String) {
    _ = MyParser.parse(input) // Should return nil/error, not crash
}
```

## Implementing in Swift

### Using Swift Testing's Parameterized Tests (Built-In)

Swift Testing doesn't have a native property-based generator, but you can approximate it:

```swift
@Test
func `sort preserves element count for random arrays`() {
    for _ in 0..<100 {
        let input = (0..<Int.random(in: 0...50)).map { _ in Int.random(in: -1000...1000) }
        let sorted = input.sorted()
        #expect(sorted.count == input.count)
    }
}
```

### Using SwiftCheck (Third-Party Library)

```swift
// SwiftCheck provides full property-based testing with shrinking
import SwiftCheck

property("reversed twice equals original") <- forAll { (xs: [Int]) in
    return xs.reversed().reversed() == xs
}

property("JSON round-trip preserves data") <- forAll { (name: String, age: UInt8) in
    let user = User(name: name, age: Int(age))
    let data = try! JSONEncoder().encode(user)
    let decoded = try! JSONDecoder().decode(User.self, from: data)
    return decoded == user
}
```

## When to Use Property-Based Testing

| Good Fit | Poor Fit |
|----------|----------|
| Serialization/parsing (round-trip) | UI rendering |
| Mathematical operations | External API integration |
| Data structure invariants | Tests needing specific fixtures |
| String/collection transformations | Simple CRUD with known inputs |
| Sorting, filtering, mapping | Tests requiring side-effect verification |
| State machines (invariant preservation) | |
| Validators and sanitizers | |

## Shrinking

When PBT finds a failing input, **shrinking** reduces it to the minimal failing case:

```
// Found failure with: [847, -3, 0, 9999, -1, 42, 0, -7, 3]
// Shrunk to: [0, -1]  ← minimal case that still triggers the bug
```

This makes debugging much easier. SwiftCheck includes shrinking; manual PBT requires manual minimization.

## Checklist

- [ ] Serialization/deserialization has round-trip property tests
- [ ] Idempotent operations tested for idempotence
- [ ] Mathematical functions tested for algebraic properties
- [ ] Data structure invariants verified under random operations
- [ ] Validators tested with random/adversarial inputs
- [ ] String processing tested with Unicode, empty, and long inputs
- [ ] At least 100 random inputs per property
- [ ] When using manual generation, include edge cases (0, -1, Int.max, empty, nil)

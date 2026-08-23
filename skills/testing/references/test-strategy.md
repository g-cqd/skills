# Advanced Test Strategy

## Pre-Implementation Techniques

### Example Mapping

A collaborative technique to discover test cases **before writing any code**. Produces a shared understanding of the feature.

```
┌──────────────────────────────────────────────────────────────┐
│ Story (Yellow): "User can apply discount codes"              │
├──────────────────────────────────────────────────────────────┤
│ Rule (Blue):           │ Rule (Blue):          │ Rule:       │
│ "Valid codes give      │ "Expired codes are    │ "Codes are  │
│  discount"             │  rejected"            │  single-use"│
├────────────────────────┼───────────────────────┼─────────────┤
│ Example (Green):       │ Example (Green):      │ Example:    │
│ • SAVE10 → 10% off    │ • OLD20 expired       │ • Use SAVE10│
│ • HALF → 50% off      │   yesterday → error   │   twice →   │
│ • FREE → 100% off     │ • OLD20 expires today  │   second    │
│                        │   → still works       │   rejected  │
├────────────────────────┼───────────────────────┤             │
│ Question (Red):        │ Question (Red):       │             │
│ • Stack multiple       │ • Grace period?       │             │
│   codes?               │                       │             │
└────────────────────────┴───────────────────────┴─────────────┘
```

**Process:**
1. Write the story on a yellow card
2. Identify rules (acceptance criteria) — blue cards
3. Find examples for each rule — green cards
4. Capture questions/unknowns — red cards
5. Each green card becomes a test case

### Acceptance Test-Driven Development (ATDD)

Write acceptance tests BEFORE implementation to define "done":

```swift
// Acceptance test — written before any implementation
@Suite("Discount Code Feature — Acceptance", .tags(.acceptance))
struct DiscountCodeAcceptanceTests {
    @Test
    func `valid percentage code applies discount to cart total`() async throws {
        let cart = ShoppingCart(items: [.fixture(price: 100)])
        let result = try await cart.applyCode("SAVE10")
        #expect(result.discount == 10)
        #expect(result.total == 90)
    }

    @Test
    func `expired code is rejected with clear error`() async throws {
        let cart = ShoppingCart(items: [.fixture(price: 100)])
        await #expect(throws: DiscountError.expired) {
            try await cart.applyCode("OLD20")
        }
    }

    @Test
    func `already-used code cannot be reused`() async throws {
        let cart1 = ShoppingCart(items: [.fixture(price: 100)])
        _ = try await cart1.applyCode("ONCE50")

        let cart2 = ShoppingCart(items: [.fixture(price: 200)])
        await #expect(throws: DiscountError.alreadyUsed) {
            try await cart2.applyCode("ONCE50")
        }
    }
}
```

**ATDD loop:** Acceptance test (fails) → TDD unit tests → Implementation → Acceptance test (passes)

### Contract Testing

Verify that **module/service interfaces** match expectations on both sides:

```swift
// Producer side: AuthService promises this contract
@Suite("AuthService Contract", .tags(.contract))
struct AuthServiceContractTests {
    @Test
    func `login returns token on valid credentials`() async throws {
        let service = AuthService(store: InMemoryUserStore.withTestUser)
        let result = try await service.login(email: "test@test.com", password: "valid")

        // Contract: result has non-empty token and user ID
        #expect(!result.token.isEmpty)
        #expect(!result.userId.isEmpty)
    }

    @Test
    func `login throws invalidCredentials on wrong password`() async {
        let service = AuthService(store: InMemoryUserStore.withTestUser)
        await #expect(throws: AuthError.invalidCredentials) {
            try await service.login(email: "test@test.com", password: "wrong")
        }
    }
}

// Consumer side: ProfileService depends on this same contract
@Suite("ProfileService Auth Contract Expectations", .tags(.contract))
struct ProfileServiceContractTests {
    @Test
    func `handles auth token correctly from login response`() async throws {
        let authResult = AuthResult(token: "test-token-123", userId: "user-1")
        let profileService = ProfileService(authToken: authResult.token)

        // Consumer expects token is used in subsequent requests
        let request = profileService.buildProfileRequest()
        #expect(request.headers["Authorization"] == "Bearer test-token-123")
    }
}
```

### Characterization Testing (Legacy Code Discovery)

When working with code that **has no tests and unclear behavior**, characterization tests discover and lock down existing behavior before modifying it:

```swift
// Step 1: Call the function with various inputs
// Step 2: Record what it actually returns (not what you think it should)
// Step 3: Write tests that assert the current behavior

@Suite("LegacyPriceCalculator — Characterization", .tags(.characterization))
struct LegacyPriceCalculatorCharacterizationTests {
    @Test
    func `characterize: base price calculation`() {
        let calc = LegacyPriceCalculator()

        // Discovered behavior — may or may not be "correct"
        #expect(calc.calculate(quantity: 1, unitPrice: 100) == 100)
        #expect(calc.calculate(quantity: 0, unitPrice: 100) == 0)
        #expect(calc.calculate(quantity: -1, unitPrice: 100) == -100) // Bug? Or feature?
        #expect(calc.calculate(quantity: 1, unitPrice: 0) == 0)
    }

    @Test
    func `characterize: discount tiers`() {
        let calc = LegacyPriceCalculator()

        // Document the actual discount breakpoints
        #expect(calc.calculate(quantity: 9, unitPrice: 10) == 90)   // No discount
        #expect(calc.calculate(quantity: 10, unitPrice: 10) == 95)  // 5% discount kicks in at 10
        #expect(calc.calculate(quantity: 50, unitPrice: 10) == 450) // 10% at 50
    }
}
```

**Purpose**: Now you can refactor safely — if any test breaks, you've changed behavior.

## Post-Implementation Techniques

### Fuzz Testing

Feed **random, malformed, or adversarial inputs** to find crashes, hangs, or security vulnerabilities:

```swift
@Suite("Parser Fuzz Tests", .tags(.fuzz))
struct ParserFuzzTests {
    @Test
    func `parser never crashes on random input`() {
        for _ in 0..<10_000 {
            let length = Int.random(in: 0...1000)
            let randomBytes = (0..<length).map { _ in UInt8.random(in: 0...255) }
            let randomString = String(bytes: randomBytes, encoding: .utf8) ?? ""

            // Should return nil or error, never crash
            _ = MyParser.parse(randomString)
        }
    }

    @Test
    func `JSON decoder never crashes on malformed input`() {
        let mutations: [(Data) -> Data] = [
            { $0.dropLast(1).asData },          // Truncation
            { $0 + Data([0xFF]) },               // Append garbage
            { Data($0.reversed()) },             // Reverse bytes
            { Data($0.map { $0 ^ 0xFF }) },      // Bit flip
            { Data() },                          // Empty
        ]

        let validJSON = try! JSONEncoder().encode(User.fixture())

        for mutate in mutations {
            let corrupted = mutate(validJSON)
            // Must not crash
            _ = try? JSONDecoder().decode(User.self, from: corrupted)
        }
    }
}
```

### Smoke Testing

Quick, high-level tests that verify **critical paths work at all** — the first line of defense:

```swift
@Suite("Smoke Tests", .tags(.smoke))
struct SmokeTests {
    @Test
    func `app can initialize core services`() async throws {
        let container = try await AppContainer.initialize(environment: .test)
        #expect(container.authService != nil)
        #expect(container.dataStore != nil)
        #expect(container.networkClient != nil)
    }

    @Test
    func `critical user flow: login → fetch profile → logout`() async throws {
        let app = TestApp()
        try await app.login(user: "test@test.com", password: "valid")
        let profile = try await app.fetchProfile()
        #expect(!profile.name.isEmpty)
        try await app.logout()
    }
}
```

### Test Impact Analysis

Determine **which tests to run** based on which files changed:

| Strategy | How | When |
|----------|-----|------|
| **File mapping** | Map source files to test files | Every PR — run only affected tests |
| **Module mapping** | Changed module → run module's tests | Fast CI feedback |
| **Dependency graph** | Trace imports to find affected tests | Accurate but complex |
| **Full suite** | Run everything | Before release, after merge to main |

### Test Maintenance

| Practice | Why |
|----------|-----|
| **Delete tests that test deleted code** | Dead tests add noise and maintenance burden |
| **Update tests when requirements change** | Stale tests give false confidence |
| **Consolidate duplicated test setups** | Reduce maintenance surface |
| **Review test-to-code ratio** | If tests >> code, may be over-testing implementation details |
| **Track flaky tests and fix immediately** | Flaky tests erode trust in the suite |
| **Periodically run mutation testing** | Verify tests are still meaningful |

## Checklist

- [ ] Example mapping done before implementation for complex features
- [ ] Acceptance tests written before implementation (ATDD)
- [ ] Module contracts tested on both producer and consumer sides
- [ ] Legacy code characterized before refactoring
- [ ] Parsers and validators fuzz-tested
- [ ] Smoke tests cover critical paths
- [ ] Test impact analysis configured in CI
- [ ] Test maintenance scheduled (dead test cleanup, flaky test fixes)

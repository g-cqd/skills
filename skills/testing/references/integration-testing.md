# Integration Testing

## What It Is

Integration tests verify that **multiple components work together correctly**. Unlike unit tests (which isolate one unit), integration tests exercise real interactions between modules, layers, or subsystems.

## When Unit Tests Aren't Enough

| Signal | Why Integration Tests Help |
|--------|--------------------------|
| Two modules pass unit tests but fail together | Interface mismatch, serialization bugs |
| Mocks diverge from real implementations | Mocks can't catch protocol misunderstandings |
| Data flows through multiple transformations | End-to-end data integrity |
| Caching, persistence, or networking involved | Real I/O behavior differs from mocks |

## Integration Test Levels

```
┌─────────────────────────────────────────────┐
│ Level 1: Module Integration                 │
│ Two modules interact (e.g., Service + Repo) │
├─────────────────────────────────────────────┤
│ Level 2: Subsystem Integration              │
│ Full feature slice (API → Logic → Storage)  │
├─────────────────────────────────────────────┤
│ Level 3: System Integration                 │
│ App ↔ External systems (API, DB, services)  │
└─────────────────────────────────────────────┘
```

## Strategies

### 1. Big Bang
- Combine all components at once, test as a whole
- **Pros**: Simple setup
- **Cons**: Hard to isolate failures
- **Use when**: Small number of components

### 2. Top-Down
- Start from the highest-level module, stub lower layers
- Replace stubs with real implementations incrementally
- **Pros**: Tests user-facing behavior early
- **Cons**: Needs stubs for lower layers initially

### 3. Bottom-Up
- Start from lowest-level modules (data layer, utilities)
- Add higher layers incrementally
- **Pros**: No stubs needed, tests foundations first
- **Cons**: UI/user-facing features tested last

### 4. Sandwich (Hybrid)
- Test top and bottom layers in parallel, meet in the middle
- **Pros**: Balances both approaches
- **Cons**: More coordination needed

## Writing Integration Tests in Swift

### Module Integration Example

```swift
@Suite("UserProfile Integration", .tags(.integration))
struct UserProfileIntegrationTests {
    @Test
    func `fetches and caches user profile end-to-end`() async throws {
        // Given: real service with in-memory cache (fake, not mock)
        let cache = InMemoryProfileCache()
        let api = StubAPIClient(returning: .success(ProfileFixtures.alice))
        let service = UserProfileService(api: api, cache: cache)

        // When: fetch profile
        let profile = try await service.fetchProfile(id: "123")

        // Then: profile returned AND cached
        #expect(profile.name == "Alice")
        let cached = try #require(await cache.get(id: "123"))
        #expect(cached.name == "Alice")
    }

    @Test
    func `serves from cache on second fetch`() async throws {
        let api = SpyAPIClient(returning: .success(ProfileFixtures.alice))
        let cache = InMemoryProfileCache()
        let service = UserProfileService(api: api, cache: cache)

        _ = try await service.fetchProfile(id: "123")
        _ = try await service.fetchProfile(id: "123")

        // API called only once — second fetch served from cache
        #expect(api.fetchCallCount == 1)
    }
}
```

### Subsystem Integration Example

```swift
@Suite("Payment Flow Integration", .tags(.integration))
struct PaymentFlowIntegrationTests {
    @Test
    func `complete payment flow from cart to confirmation`() async throws {
        // Real objects wired together, only external boundaries faked
        let cart = ShoppingCart()
        let pricing = PricingEngine(taxRules: TaxRules.current)
        let paymentProcessor = FakePaymentProcessor(alwaysSucceeds: true)
        let orderRepo = InMemoryOrderRepository()
        let flow = PaymentFlow(
            cart: cart,
            pricing: pricing,
            processor: paymentProcessor,
            orders: orderRepo
        )

        cart.add(item: .fixture(price: 100))
        let result = try await flow.checkout()

        #expect(result.status == .confirmed)
        #expect(result.total == 110) // 100 + 10% tax
        #expect(await orderRepo.count == 1)
    }
}
```

## Integration Test Boundaries

### What to Fake vs. What to Keep Real

| Component | Integration Test | Why |
|-----------|-----------------|-----|
| Business logic | **Real** | This is what you're testing |
| In-memory data stores | **Fake** (in-memory impl) | Fast, deterministic, tests real interface |
| Network calls | **Fake/Stub** | Avoid flakiness, control responses |
| File system | **Fake** or temp directory | Avoid side effects |
| External APIs | **Fake** | Control, speed, determinism |
| Module interfaces | **Real** | This is the integration point |

### Key Rule
> Mock at the **system boundary**, not between your own modules. The whole point of integration tests is to exercise real interactions between your code.

## Integration Test Hygiene

| Practice | Why |
|----------|-----|
| **Tag with `.integration`** | Can run separately from unit tests |
| **Use `@Suite(.serialized)`** if tests share state | Prevent order-dependent failures |
| **Clean up state in each test** | Don't rely on test execution order |
| **Keep under 1 second per test** | Integration ≠ slow; use fakes, not real I/O |
| **Test the contract, not internals** | Assert on outputs and observable side effects |
| **Separate from unit tests in directory structure** | `Tests/Module/Integration/` |

## Common Integration Testing Mistakes

| Mistake | Fix |
|---------|-----|
| Testing too many things at once | Focus on one integration point per test |
| Using real network/DB in every test | Use fakes; reserve real I/O for a small smoke suite |
| Duplicating unit test assertions | Integration tests verify wiring, not individual logic |
| No cleanup between tests | Fresh state per test, or use `@Suite(.serialized)` |
| Ignoring failure modes | Test what happens when a downstream component fails |

## Checklist

- [ ] Critical module boundaries have integration tests
- [ ] External dependencies faked at system boundary
- [ ] Internal module interfaces exercised with real implementations
- [ ] Both success and failure paths tested
- [ ] Tests tagged `.integration` for selective execution
- [ ] State cleaned up between tests
- [ ] Each test focuses on one integration point
- [ ] Tests run in < 1 second each

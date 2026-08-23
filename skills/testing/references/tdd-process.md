# TDD Process

## The TDD Loop

### Phase 1: RED
- **Goal**: Create a failing test for the *next* logical behavior
- **Output**: State the behavior, present the failing test
- **STOP**: Ask the user to run the test and confirm failure

### Phase 2: GREEN
- **Goal**: Write the *minimum* code to pass the test
- **Constraint**: Do not improve, optimize, or clean up. Just pass.
- **STOP**: Ask the user to verify the test passes

### Phase 3: REFACTOR
- **Goal**: Clean up without changing behavior
- **Checklist**: Duplication? Naming? Clarity? Swift patterns?
- **STOP**: Verify tests still pass. Suggest next test.

### Phase 4: SPIKE (Optional)
- **Trigger**: User asks to "explore", "prototype", or "try out"
- **Rules**: TDD suspended. Write code freely.
- **Exit**: "Spike complete. Let's delete this and TDD it properly, or wrap it in tests."

## Core Laws

1. **No Production Code Without a Failing Test**: Write the test first. Always.
2. **Minimum to Pass**: Only enough code to make the current test pass.
3. **One Behavior Per Test**: Each test verifies exactly one thing.
4. **Tests Are Executable Documentation**: Tests describe system behavior.
5. **Fast Feedback Loop**: Tests must run in milliseconds.

## Test Structure: Given-When-Then

```swift
@Test
func `fetches user profile successfully`() async throws {
  // Given
  let mockClient = MockHTTPClient(response: .success(userJSON))
  let service = UserService(client: mockClient)

  // When
  let user = try await service.fetch(id: "123")

  // Then
  #expect(user.id == "123")
  #expect(user.name == "Alice")
}
```

## When to Apply TDD

| Scenario | Approach |
|----------|----------|
| New feature | Full Red-Green-Refactor |
| Bug fix | Write failing regression test first, then fix |
| Legacy code | Use techniques from `legacy-code.md` |
| Prototype/spike | Skip TDD, then delete and TDD properly |
| Trivial code | Use judgment — simple getters may not need tests |

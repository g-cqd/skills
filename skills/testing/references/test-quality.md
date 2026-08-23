# Test Quality

## FIRST Principles

| Principle | Meaning | Violation Signal |
|-----------|---------|------------------|
| **F**ast | Runs in < 100ms | Suite takes > 30s |
| **I**ndependent | No shared state | Order-dependent failures |
| **R**epeatable | Same result always | Flaky intermittent failures |
| **S**elf-validating | Pass/fail only | Manual inspection needed |
| **T**imely | Written before code | Tests added post-bug |

## Test Smell Detection

| Smell | Symptom | Cure |
|-------|---------|------|
| **Flaky** | Random failures | Remove time/order deps, use TestClock |
| **Brittle** | Breaks on refactor | Test behavior, not implementation |
| **Slow** | > 100ms | Mock I/O, reduce scope |
| **Coupled** | Needs other tests | Fresh state per test |
| **Tautological** | Never fails | Assert real outcomes |
| **Obscure** | Hard to understand | Better names, less setup |
| **Eager** | Tests private methods | Test via public API |
| **Giant** | Many asserts | Split into focused tests |

## Coverage Dimensions

| Dimension | What It Measures | Target |
|-----------|-----------------|--------|
| Line Coverage | Lines executed | > 80% |
| Branch Coverage | All if/else/switch paths | > 75% |
| Mutation Coverage | Tests fail when code mutates | > 70% |
| Requirement Coverage | Specs have tests | 100% |

Coverage is a guide, not a goal. Focus on *meaningful* coverage over numbers.

## Testing Pyramid

```
                   /\
                  /  \
                 / E2E\      < 5%  — Slow, critical paths only
                /------\
               /        \
              /Integration\  15%  — Component interaction
             /------------\
            /              \
           /     Unit       \ 80% — Fast, isolated
          /------------------\
```

## View Logic Testing (SwiftUI)

Test the *logic* behind views, not rendering:

```swift
@Test
func `validates email format`() {
  let view = SignupView(email: "bad-email")
  #expect(view.isEmailValid == false)

  let view2 = SignupView(email: "good@test.com")
  #expect(view2.isEmailValid == true)
}
```

Move logic to a ViewModel for easier testing.

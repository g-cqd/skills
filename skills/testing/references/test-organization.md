# Test Organization

## Directory Structure

```
Tests/
├── ModuleNameTests/
│   ├── Unit/
│   │   ├── Models/
│   │   ├── Services/
│   │   └── ViewModels/
│   ├── Integration/
│   ├── Snapshot/
│   └── _TestSupport/
│       ├── Mocks/
│       ├── Stubs/
│       ├── Fixtures/
│       └── Helpers/
```

## Naming Conventions

| Element | Pattern | Example |
|---------|---------|---------|
| Test File | `[Type]Tests.swift` | `UserServiceTests.swift` |
| Test Suite | `@Suite("[Type] Tests")` | `@Suite("UserService Tests")` |
| Test Method | Descriptive sentence | `"fetches user successfully"` |
| Mock | `Mock[Protocol]` | `MockHTTPClient` |
| Stub | `Stub[Type]` | `StubUserRepository` |
| Fixture | `[Type]Fixtures.[case]` | `UserFixtures.validUser` |

## Test Strategy Matrix

| Test Type | Purpose | When Required |
|-----------|---------|---------------|
| Happy Path | Normal operation | Every feature |
| Error Path | Failure handling | Every throwable operation |
| Boundary | Edge cases, limits | Collections, inputs, ranges |
| State Transition | Lifecycle changes | State machines, workflows |
| Regression | Prevent recurrence | After every bug fix |
| Concurrency | Thread safety | Actors, async operations |

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

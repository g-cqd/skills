# Regression Testing

## What It Is

Regression testing ensures that **previously working functionality still works** after code changes. Every bug fix, feature addition, or refactor risks breaking existing behavior. Regression tests are the safety net.

## The Regression Testing Process

```
Bug Report → Reproduce → Write Failing Test → Fix → Test Passes → Test Stays Forever
```

### Step-by-Step

1. **Reproduce the bug**: Confirm the defect exists and understand its trigger
2. **Write a failing test FIRST**: The test must fail for the exact reason the bug manifests
3. **Fix the bug**: Minimum code change to make the test pass
4. **Verify the fix**: Run the full suite — new test passes, nothing else breaks
5. **Keep the test permanently**: It guards against this exact regression forever

## Types of Regression Tests

| Type | Scope | When to Use |
|------|-------|-------------|
| **Unit regression** | Single function/class | Bug in isolated logic |
| **Integration regression** | Module interaction | Bug at component boundary |
| **Visual regression** | UI appearance | Layout/styling bugs → see `snapshot-testing.md` |
| **Performance regression** | Speed/memory | Performance degradation → see `performance-testing.md` |
| **Full regression suite** | Entire system | Before releases |

## Writing Effective Regression Tests

### Name Tests After the Bug

```swift
@Test
func `does not crash when user name contains emoji — fixes GH-1234`() {
    let user = User(name: "Alice 🎉")
    let display = UserDisplayFormatter.format(user)
    #expect(display == "Alice 🎉")
}
```

### Test the Exact Failure Mode

```swift
// BAD: Tests the happy path (would have passed before the fix too)
@Test func `login succeeds`() async throws {
    let result = try await auth.login(user: "alice", password: "correct")
    #expect(result.isSuccess)
}

// GOOD: Tests the exact scenario that was broken
@Test
func `login succeeds when password contains special characters — fixes GH-5678`() async throws {
    let result = try await auth.login(user: "alice", password: "p@ss&w0rd!")
    #expect(result.isSuccess)
    #expect(result.user?.name == "alice")
}
```

### Guard Boundary Conditions

```swift
@Test
func `pagination returns empty array for page beyond last — fixes GH-9012`() async throws {
    let repo = InMemoryRepo(items: Array(1...10))
    let page = try await repo.fetch(page: 5, pageSize: 10) // Only 1 page of data
    #expect(page.items.isEmpty)
    #expect(page.hasMore == false)
}
```

## Regression Test Strategy

### What Gets a Regression Test

| Always | Sometimes | Rarely |
|--------|-----------|--------|
| Customer-reported bugs | Internal QA findings | Cosmetic issues |
| Data corruption bugs | Performance issues | Log formatting |
| Security vulnerabilities | Race conditions | Documentation typos |
| Crash bugs | Edge cases found in review | |

### Regression Suite Management

| Practice | Rationale |
|----------|-----------|
| **Tag regression tests** | `@Test(.tags(.regression))` — run selectively |
| **Link to issue tracker** | Include ticket ID in test name or comment |
| **Never delete regression tests** | They guard against recurrence |
| **Run before every release** | Full regression suite is the release gate |
| **Prioritize by severity** | Critical regressions run in CI on every commit |

## Regression Test Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Testing the fix, not the bug | Test passes even without the fix | Write test BEFORE fixing |
| Over-broad regression test | Tests too much, breaks on unrelated changes | Focus on exact failure scenario |
| Regression test without reproduction | Can't confirm test actually catches the bug | Always reproduce first |
| Deleting "old" regression tests | Bug can recur | Keep permanently |
| Only manual regression testing | Slow, error-prone, doesn't scale | Automate everything |

## Checklist

- [ ] Every bug fix has a corresponding regression test
- [ ] Test written BEFORE the fix (confirms it catches the bug)
- [ ] Test name references the bug/ticket
- [ ] Test targets the exact failure scenario, not just the happy path
- [ ] Regression tests tagged for selective execution
- [ ] Full regression suite runs before releases
- [ ] Regression tests never deleted

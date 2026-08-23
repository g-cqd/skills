# Mutation Testing

## What It Is

Mutation testing evaluates **test suite quality** by introducing small, systematic changes (mutants) to production code and checking whether tests catch them. If a test fails after a mutation, the mutant is **killed** (good). If all tests still pass, the mutant **survived** (bad — your tests missed something).

Mutation testing answers: "If I introduced a bug, would my tests catch it?"

## Why It Matters

- **Line/branch coverage lies**: 100% coverage doesn't mean tests assert meaningful outcomes. Mutation testing exposes tautological tests (tests that never fail).
- **Finds missing assertions**: A test that calls a function but doesn't verify its result will show 100% coverage yet survive mutations.
- **Validates test effectiveness**: Mutation score is the most reliable indicator of test suite quality.

## Mutation Operators

| Operator | What It Does | Example |
|----------|-------------|---------|
| **Arithmetic** | Replace `+` with `-`, `*` with `/` | `a + b` → `a - b` |
| **Relational** | Flip comparisons | `<` → `>=`, `==` → `!=` |
| **Logical** | Negate conditions | `&&` → `\|\|`, `!x` → `x` |
| **Return value** | Change return values | `return true` → `return false` |
| **Void call removal** | Delete void method calls | `cache.invalidate()` → (deleted) |
| **Constant replacement** | Change literals | `0` → `1`, `""` → `"mutant"` |
| **Boundary** | Shift boundaries by 1 | `i < 10` → `i < 11`, `i <= 10` → `i < 10` |
| **Negate conditional** | Negate entire if-condition | `if ready` → `if !ready` |
| **Remove conditional** | Force branch | `if x { ... }` → `{ ... }` (always execute) |
| **Unwrap optional** | Change optional handling | `x ?? default` → `default` |

## Mutation Score

```
Mutation Score = (Killed Mutants / Total Mutants) × 100%
```

| Score | Assessment |
|-------|-----------|
| > 80% | Strong test suite |
| 60-80% | Acceptable, investigate survivors |
| < 60% | Weak — tests are likely superficial |

## Tools for Swift

### Mull (C/C++/Swift via LLVM)
- LLVM-based mutation testing tool that works with Swift
- Operates at the IR level — language-agnostic for LLVM targets
- https://github.com/mull-project/mull

### Manual Mutation Testing
When automated tools aren't available, apply mutation testing manually:

1. **Pick a function** with existing tests
2. **Apply one mutation** (e.g., flip a comparison, remove a call)
3. **Run tests** — if they all pass, you found a gap
4. **Write a test** that catches the mutation
5. **Revert the mutation**
6. **Repeat** for critical code paths

### Systematic Manual Process

```swift
// Original
func applyDiscount(_ price: Decimal, loyaltyYears: Int) -> Decimal {
    if loyaltyYears >= 5 {
        return price * 0.9  // 10% discount
    }
    return price
}

// Mutation 1: Change >= to >
// Ask: Do tests fail if loyaltyYears == 5 gets no discount?
// If not: add test for boundary value loyaltyYears = 5

// Mutation 2: Change 0.9 to 1.0
// Ask: Do tests verify the actual discounted amount?
// If not: add test asserting exact return value

// Mutation 3: Remove the if-block entirely (always return price)
// Ask: Do tests fail if discount is never applied?
// If not: add test verifying discount IS applied for qualifying users

// Mutation 4: Change return price to return 0
// Ask: Do tests verify non-qualifying users get full price?
// If not: add test for non-qualifying case
```

## When to Apply Mutation Testing

| Context | Approach |
|---------|----------|
| **Critical business logic** | Always — payment, auth, data integrity |
| **Complex conditionals** | Always — easy to get boundaries wrong |
| **Bug fixes** | Apply mutations around the fix to verify regression test strength |
| **High-coverage code that feels undertested** | Mutation testing reveals hollow coverage |
| **Before shipping** | Spot-check critical paths |
| **Simple getters/setters** | Skip — low value |

## Interpreting Surviving Mutants

Not all survivors indicate problems:

| Survivor Type | Action |
|---------------|--------|
| **Missing assertion** | Write a test — most common and most valuable |
| **Equivalent mutant** | Mutation doesn't change behavior (e.g., `x * 1` → `x * -1` where x is always 0). Ignore. |
| **Trivial code** | Simple property access, logging — may not need killing |
| **Redundant code** | If removing code doesn't break tests, the code itself might be dead — consider removing it |

## Integration with TDD

Mutation testing complements TDD:

1. **After GREEN**: Run mutations against new code to verify your tests are meaningful
2. **During REFACTOR**: Mutations confirm refactored code is still well-tested
3. **Review phase**: Use mutation score as a quality gate alongside coverage

## Checklist

- [ ] Critical business logic has mutation score > 80%
- [ ] Boundary conditions tested (mutations to `<`, `<=`, `>=`, `>` are killed)
- [ ] Return value mutations are killed (tests assert on actual return values)
- [ ] Void call removal mutations are killed (side effects are verified)
- [ ] Surviving mutants reviewed — either add tests or document as equivalent
- [ ] No tautological tests (tests that pass regardless of code behavior)

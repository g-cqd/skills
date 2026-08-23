# Simplification Guide

> The cost of an abstraction frequently outweighs the benefit it delivers.
> When it does, remove it.

> Never explain HOW code works in a comment — write the code so that the
> working is obvious.

This guide is always active during reviews. The simplest correct code wins.

## Comments to Remove

| Pattern | Example | Why |
|---------|---------|-----|
| Restates code | `i += 1 // increment i` | Zero information |
| Restates signature | `/// Returns user name` on `func userName()` | Type says it |
| Closing brace labels | `} // end if` | Function too long |
| Section dividers | `// =========` | Use MARK/region |
| Journal entries | `// Modified by John` | git blame |
| Commented-out code | `// let old = ...` | git history |
| Empty TODOs | `// TODO: implement` | No context |
| Boilerplate headers | `// Created by Xcode` | Noise |

## Comments to Keep

- **Intent**: Why a non-obvious decision was made
- **Warnings**: Consequences of modification
- **Workarounds**: External constraints (with bug tracker reference)
- **Complexity justification**: When algorithm is inherently complex

## Abstractions to Flag

1. **Single-use function** with name no clearer than the code it wraps
2. **Delegation-only wrapper** that only calls through to another method
3. **Manager/Provider/Handler** naming — often no clear responsibility
4. **Protocol with single conformer** that will never have a second
5. **Abstraction name less informative than the code** (the naming test)

### The Test
- Should this be inlined? (Called from one place? Hides state mutation?)
- Does the name convey less than the code it wraps? If so, reject it
- Would removing this break anything? If no, remove it

## Verbose Patterns to Simplify

```
// Boolean ceremony
if condition { return true } else { return false }
→ return condition

// Unnecessary intermediate
let result = computeValue(); return result
→ return computeValue()

// Over-defensive
if array.count > 0 { ... }
→ if !array.isEmpty { ... }   // Swift
→ if (list.isNotEmpty()) { ... }  // Kotlin
```

## Dead Code (Always Remove)

- Unreachable code paths
- Functions never called
- Feature flags permanently set to one value
- Protocol/interface conformances with empty implementations
- Unused imports/variables

## What NOT to Touch

- Working logic — simplify only, never change behavior
- Test assertions — verbosity aids debugging
- Public API documentation
- Legal headers
- Complex algorithm explanations
- Safety comments (thread safety, memory management)

## Guiding Principles

### State and control flow
- Code should make state explicit, not hide it behind abstractions
- Prefer `let`/`val` over `var`. Prefer pure functions
- Minimize control flow complexity and "area under ifs"
- Trust static analysis over manual defensive coding
- 3+ levels of indentation → extract or restructure

### Data over algorithms
- Data structures matter more than algorithms — the right data structures
  make algorithms self-evident
- Fancy algorithms are buggier than simple ones

### Comments
- Comments should tell WHAT and WHY, not HOW

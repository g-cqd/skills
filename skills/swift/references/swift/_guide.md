# Swift Language — Domain Guide

This guide contains the core Swift engineering standards, conventions, and project-specific rules. For detailed reference on specific topics, see the other files in this directory.

## Core Principles

### Design Philosophy
- **SOLID**: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **DRY**: Abstract when a pattern emerges thrice
- **KISS**: Simple beats clever — optimize for the reader
- **Law of Demeter**: Objects communicate only with immediate collaborators

### Type System Defaults
- **Value types first**: Default to `struct` and `enum`; use `class` only for reference semantics, identity, or ObjC interop
- **Final by default**: Mark all classes `final` to enable devirtualization
- **Typed throws**: Use Swift 6 `throws(MyError)` for precise error contracts
- **Private by default**: Start with `private`, widen only as needed

### Performance Awareness
- Analyze Big O complexity; justify O(n²) or worse
- Use `weak`/`unowned` to break retain cycles; profile with Instruments before optimizing
- Value types and `@inlinable` compile away overhead

## Minimalism & Simplification

- **Only include truly needed code**: Every property, conformance, and parameter must justify its existence
- **Leverage Foundation**: Check if Foundation already handles it before implementing manual logic
- **Avoid unnecessary protocols**: When a protocol exists only for mocking/testing, consider closure injection
- **Typed throws on closures**: `typealias Handler = @Sendable (Input) throws(MyError) -> Output`
- **Use private extensions for computed helpers**: Extract nested data traversals into `private extension` computed properties
- **Prefer helper functions over comments**: Extract into small `private` helper functions with descriptive names
- **Guard early with early return**: `guard let handler else { return }` before calculations
- **Simplify boolean logic**: Prefer positive conditions over double negatives
- **`@discardableResult` when return value is commonly ignored**
- **Consistent API design for conversions**: Either `init` or `toXY()`, not both
- **No optional arrays**: Never use `[T]?` — use `[T]` with empty default
- **No optional bools**: Never use `Bool?` — use non-optional `Bool` with default
- **Narrowest protocol conformance**: `Decodable` not `Codable` when never encoding
- **Compiler-synthesized initializers**: `RawRepresentable` with `String`-backed enums
- **`if let` expression assignment** (Swift 5.9+): `let x = if condition { a } else { b }`
- **Initializers belong in the type body**: Never move to extensions
- **Use `Optional.map()` for transformations**: Instead of `if let` + else nil
- **Use concrete type names over `.init(...)`**
- **Generics over existentials in constrained environments**
- **Don't store dependencies you don't need**: Only store what's used beyond init
- **Non-optional when `nil` is never valid**
- **Use `decodeIfPresent` over manual `try?`/nil handling**
- **Use `logger.error()` instead of `print()`**
- **`LocalizedError` only for truly localized errors**
- **Use localization placeholders**: `"%1$@ is ready"` not string concatenation

## Quick Reference

### Error Handling
| Pattern | Use When |
|---------|----------|
| `throws(MyError)` | Precise error contracts (Swift 6) |
| `throws` | Generic error propagation |
| `Result<T, E>` | Storing outcomes, callback-based APIs |
| `preconditionFailure` | Programmer errors / logic bugs |
| `guard let` | Early exits (avoid nested `if let`) |

### Access Control
| Level | Use When |
|-------|----------|
| `private` | Default for all new declarations |
| `private(set)` | Externally readable but only internally writable |
| `fileprivate` | Shared within same file only |
| `internal` | Module-wide access (implicit default) |
| `public` | Intentional API exposure with documentation |
| `open` | Designed for subclassing outside module |

**Access control rules**:
- Use `let` for injected dependencies the view/type does not own
- Use `private(set)` when readable externally but only writable internally
- `CodingKeys` enums should always be `private`
- Remove redundant `return` statements (single-expression bodies)
- Don't relax access control for tests
- Most things don't need `public`
- `static let` for constant expressions
- `lazy var` over Optional when footprint is low
- Use `guard let` to unwrap (not `guard x != nil` + force unwrap)

### Patterns Requiring Justification
| Pattern | Pitfall | Alternative |
|---------|---------|-------------|
| `try!` / `as!` | Runtime crash | `try?`, `as?`, typed throws |
| `value!` | Force unwrap crash | `guard let`, `if let` |
| `Any` / `[String: Any]` | Type safety violation | `Codable` models |
| Non-final `class` | Prevents devirtualization | `final class` or `struct` |
| Empty `catch {}` | Silent failure | Handle or rethrow |
| `// TODO` without issue # | Untracked debt | Link to issue tracker |
| Protocol for single mock | Over-engineering | Closure injection with typealias |
| Unused model properties | Maintenance burden | Only include referenced fields |
| `@retroactive` conformances | Fragile coupling | Explicit closures at call site |
| Optional arrays `[T]?` | Anti-pattern | `[T]` with empty default |
| Optional bools `Bool?` | Third state | `Bool` with default |
| `Codable` when only decoding | Broader than needed | `Decodable` only |
| `pageSize: 999` hacks | Scalability bomb | Proper pagination |
| `print()` for logging | Unstructured output | `logger.error()` |
| `@unknown default` on own enums | Suppresses compiler help | Enumerate cases |

### Naming Conventions
- **Stick with backend terminology** for model/DTO names
- **File names must reflect content**
- **Boolean naming**: `is`/`has`/`should`/`are` prefix, positive conditions
- **Separate testing/development flags** from feature flags
- **Specific type names**: `SendableAudioBuffer` not `SafeAudioBuffer`
- **Descriptive argument labels**: `handleStateChange(to newState:)` not `(_ state:)`
- **Consistent property/init ordering**
- **Plural for collections**: `ids` not `id`
- **Service/endpoint names mirror operations**: `GetAllTasksService` not `TaskService`
- **View types have `View` suffix**
- **Non-abbreviated names**: `dateComponents` not `dc`
- **Parameter names reflect usage, not defaults**

### Switch Statements
- **Explicit cases over `default`**: Enumerate all cases explicitly
- **No `@unknown default` on own enums**
- **Each enum case on its own line**
- **Split conditions for specific errors**

## Pre-Implementation Checklist

1. **Algorithm**: Time/space complexity? Simpler approach?
2. **API Design**: Easy to use correctly, hard to use incorrectly?
3. **Type Safety**: Value types? Typed errors? No force unwraps?
4. **Thread Safety**: Shared mutable state? → concurrency domain
5. **Memory**: Retain cycles in closures? ARC implications?
6. **Error Handling**: All failure modes covered? No silent catches?
7. **Naming**: Follows Swift conventions? Documentation complete?
8. **Tests**: Boundary conditions, error paths, state transitions planned?

## Review Checklist

- [ ] SOLID and DRY principles followed
- [ ] Value types used where appropriate
- [ ] All classes marked `final`
- [ ] Typed errors with domain-specific `Error` enums
- [ ] Access control starts at `private`, widened intentionally
- [ ] `CodingKeys` enums are `private`
- [ ] `public` APIs documented with complexity annotations
- [ ] No force unwraps, no `Any`, no empty catch blocks
- [ ] Guard-early pattern used
- [ ] Naming follows conventions and matches backend terminology
- [ ] File names reflect types/content
- [ ] No redundant `return` statements
- [ ] Every model property is actually used
- [ ] Protocols justified
- [ ] Boolean names descriptive and state-oriented
- [ ] Switch statements use explicit cases
- [ ] `@discardableResult` used where appropriate
- [ ] Helper functions instead of inline comments
- [ ] Conversion APIs consistent
- [ ] Properties, init parameters, assignments in consistent order
- [ ] Each type in its own file
- [ ] No optional arrays or bools
- [ ] Narrowest conformance used
- [ ] `if let` expression assignment used
- [ ] Initializers in type body
- [ ] Each enum case on its own line
- [ ] Localized strings use format placeholders
- [ ] `logger.error()` for logging
- [ ] Build artifacts go to `/tmp`

## Detailed References
- `architecture.md` — SOLID, composition, DI, protocols
- `type-system.md` — Value types, generics, error handling, access control
- `naming-conventions.md` — Naming, file structure, formatting, imports
- `package-structure.md` — SPM layout, Package.swift, compiler flags, deps
- `documentation.md` — Doc comments, MARK organization, complexity annotations
- `inlinearray-and-span.md` — Swift 6.2 `InlineArray` and `Span`: fixed-size inline storage, safe views over memory

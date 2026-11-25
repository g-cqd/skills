# Swift & Apple Platform Engineering

## Contents
- [1. Currency, Deployment Floor & Live Documentation](#1-currency-deployment-floor--live-documentation)
- [2. Compiler Strictness & Source-Shape Discipline](#2-compiler-strictness--source-shape-discipline)
- [3. Type System, Errors & API Design](#3-type-system-errors--api-design)
- [4. Concurrency, Executors & Synchronization Ladder](#4-concurrency-executors--synchronization-ladder)
- [5. Memory, Spans, Containers & Safe Unsafe Wrappers](#5-memory-spans-containers--safe-unsafe-wrappers)
- [6. SwiftUI & AppKit/UIKit Architecture](#6-swiftui--appkituikit-architecture)
- [7. Metal, Graphics & Apple Silicon Runtime](#7-metal-graphics--apple-silicon-runtime)
- [8. Apple Security Primitives (Keychain, CryptoKit, Hardened Runtime)](#8-apple-security-primitives-keychain-cryptokit-hardened-runtime)

---

## 1. Currency, Deployment Floor & Live Documentation

Never anchor on older Swift language modes or superseded SDK APIs. Check the project's active floor **once per task** (`Package.swift` `swift-tools-version` & `platforms`, Xcode `*_DEPLOYMENT_TARGET`, `@available` guards, CI toolchain matrix) and always target the **newest stable APIs, compiler safety checks, and language features supported within that floor**:

- Look up current Apple SDK behavior, deprecations, and availability in this order (never from memory):
  1. Installed local Apple documentation MCP server or CLI, when present
  2. Official Apple Developer documentation or SDK `.swiftinterface` / headers inside the active `Xcode.app`
- When an API is newer than the project's deployment floor, adopt the safest supported fallback, gate the newer API with `#available` where worthwhile, and note which floor unlocks the cleaner primitive. When maintaining the project itself, periodically propose raising stale toolchain/deployment floors as older OS versions drop out of support.

### Progressive fallback ladder (adopt the left column whenever the active floor supports it)
| Preferred modern primitive | Fallback when blocked by deployment floor |
|---|---|
| `Span`, `RawSpan`, `MutableSpan` | `withUnsafeBufferPointer` / `withUnsafeMutableBufferPointer` |
| `OutputSpan` | `Array(unsafeUninitializedCapacity:)` |
| `InlineArray<N, T>` | `ContiguousArray` + `reserveCapacity(N)` |
| `Mutex<Value>`, `Atomic<Value>` | `OSAllocatedUnfairLock` or safe `os_unfair_lock` wrapper |
| Typed `throws(MyError)` | Untyped `throws` + typed error enum |
| `@Observable` | `ObservableObject` only when the deployment floor predates Observation |
| Swift Testing (`@Test`, `#expect`) | `XCTest` only for `XCUI*` automation or toolchains predating Swift Testing |

Check live toolchain release notes for even newer safe primitives (lifetime/borrowing annotations, noncopyable types, strict memory-safety diagnostics, newer SwiftUI/Metal/CryptoKit APIs) and adopt them ahead of older patterns whenever supported.

---

## 2. Compiler Strictness & Source-Shape Discipline

### Package.swift baseline for high-assurance Swift targets
Enable the newest stable language mode and strictest compiler safety checks supported by the active toolchain on every target (including tests where compatible):
- Latest stable `swift-tools-version` and strict concurrency language mode
- `.strictMemorySafety()` (and any newer memory- or concurrency-safety settings introduced in later toolchains)
- Explicit existentials (`ExistentialAny`), explicit import visibility (`InternalImportsByDefault`, `MemberImportVisibility`), and any graduated upcoming safety features
- Warnings treated as errors (`.treatAllWarnings(as: .errors)` / `-warnings-as-errors`)

Keep pure domain, parser, model, and layout modules free of `AppKit`, `UIKit`, `SwiftUI`, and `Combine` so Linux CI builds and cross-platform tests stay clean.

### Enforced source-shape & hygiene rules
- **Zero crashes on fallible operations:** no `!` force unwrap, `try!`, `as!`, or implicitly unwrapped optionals (in `Sources`, `Tests`, and tools). Use `precondition(condition, "clear contract message")` only for broken internal programmer invariants, never for untrusted input.
- **No `unowned` captures** (use `weak` to break retain cycles safely); every `fatalError` carries a diagnostic message.
- **Bounded file & type shape:** one primary top-level type per file named after it; extensions in `Type+Feature.swift`; target function body ≤ 60 lines (hard error 80), type body ≤ 200 lines (hard error 400), file ≤ 250–300 code lines (hard error 500), cyclomatic complexity ≤ 10 (hard error 15), tuples ≤ 3 members, parameters ≤ 6, nesting ≤ 3.
- **Deterministic runtime seams:** forbid raw `Date()` / system clock reads and raw unstructured `Task {}` in core code; route through an injected `Clock` / `Runtime` abstraction so tests control time and task lifetime.
- **Static analyzer gates:** run strict formatting (`swift-format lint --strict`), metric linting (`swiftlint`), and static analyzers for ARC retain cycles, unreachable/dead code, code-duplication ratchets, resource-leak/durable-write obligations, and formal concurrency/state models where present. Every inline lint suppression requires a concrete reason on the same line.

---

## 3. Type System, Errors & API Design

- **Value types first:** `struct` and `enum` by default; `final class` only when identity, reference semantics, or Objective-C interop is required.
- **Copy-on-write:** any `struct` wrapping a reference storage buffer must check `isKnownUniquelyReferenced(&storage)` before mutating.
- **Static dispatch:** prefer `some Protocol` over `any Protocol`; reserve existentials for genuinely heterogeneous collections.
- **Typed errors:** prefer `throws(DomainError)` for closed failure domains; use `Result` only when storing or passing across non-throwing callbacks. Never write empty `catch {}` blocks; never return a fake default value that disguises failure as success.
- **No `Any` or `[String: Any]`:** convert framework dictionaries (`userInfo`, XPC/WebKit messages) into strict typed structs at the boundary immediately.
- **Access control & visibility:** start `private`, widen to `internal` / `package` / `public` only on concrete need; use `fileprivate` as last resort; use `@testable import` rather than widening access for tests.
- **DocC contracts:** document every public API (and non-obvious internals) with `- Parameter`, `- Returns`, `- Throws`, `- Precondition`, `- Complexity` (whenever ≠ O(1)), and isolation/cancellation behavior. Update comments in the same commit as code.

---

## 4. Concurrency, Executors & Synchronization Ladder

- **Strict concurrency clean:** zero data races under the toolchain's strictest concurrency checking, zero `@unchecked Sendable` without a documented lock/ownership proof, zero `nonisolated(unsafe)` shortcuts.
- **Structured concurrency first:** prefer `async let`, `withTaskGroup`, `withThrowingTaskGroup`, and `AsyncStream` over detached/unstructured `Task {}`. Only UI event handlers (e.g., button actions) or explicitly lifecycle-managed runtime tasks start unstructured tasks, and they must store and cancel them on teardown.
- **No `DispatchQueue` / GCD** (`DispatchQueue`, `DispatchSemaphore`, `DispatchGroup`) unless an Apple framework API explicitly requires a `DispatchQueue` parameter (e.g., `NWListener.start(queue:)`, `DispatchSource.makeMemoryPressureSource`).
- **Synchronization ladder (narrowest primitive first):**
  1. **`@MainActor`** for UI state and view models.
  2. **`Mutex<Value>`** (`Synchronization` framework) for synchronous shared mutable state without async suspension; prefer `withLock` / `withLockIfAvailable`.
  3. **`Atomic<Value>`** for counters, flags, and cursors; use the **weakest correct memory ordering** (`.relaxed` for stats/counters, `.acquiring`/`.releasing` or `.acquiringAndReleasing` for publish/consume); never default to `.sequentiallyConsistent`.
  4. **Bare `actor`** only at a natural `async` boundary or when an invariant must span an `await` (remember actor reentrancy across every `await`!).
- **Cancellation:** check `Task.isCancelled` / `try Task.checkCancellation()` inside loops, I/O stages, and parsers; cooperate with `withTaskCancellationHandler` for blocking/subprocess work.

---

## 5. Memory, Spans, Containers & Safe Unsafe Wrappers

- **Borrow, do not copy:** pass `Span<T>`, `RawSpan`, `MutableSpan<T>`, `OutputSpan<T>`, or slices (`ArraySlice`, `Substring`, `Data.SubSequence`) instead of allocating intermediate arrays.
- **Right container:** `ContiguousArray` for dense non-ObjC value storage; `InlineArray<N, T>` for small fixed stack buffers; call `reserveCapacity` whenever output count is known ahead of a loop.
- **Tape & zero-copy parsers:** parse untrusted UTF-8 and binary formats (JSON, Markdown, HTML, Protobuf, config) iteratively in a single pass into flat index tapes referencing the original byte buffer, with explicit depth/node/size caps and zero recursion.
- **Safe `unsafe` discipline:**
  1. Prefer safe Swift / `Span` APIs first.
  2. Isolate every required `unsafe` block inside a small safe wrapper API.
  3. Write an explicit `// SAFETY: <owner, lifetime, bounds invariant>` comment at the call site.
  4. Prove every boundary with unit tests + ASan/UBSan (and differential scalar parity tests for C/NEON SIMD kernels).
  5. For C interop compiled with Apple Clang, enable `-fbounds-safety` (`__counted_by`, `__sized_by`) and check length-field agreement before every buffer allocation or copy.

---

## 6. SwiftUI & AppKit/UIKit Architecture

- **State management:** use `@Observable` (never `ObservableObject` in new code) so views track per-property reads; annotate UI-driving models `@MainActor`; pass narrow leaf values rather than whole aggregates into row views; never use collection indices as `ForEach` IDs.
- **Pure `body` and `init`:** zero sorting, filtering, JSON/SQLite I/O, or network work inside `body` or `View.init`. Keep business logic in testable non-View models.
- **Macro-backed `@State` initialization trap:** on modern SDKs where `@State` synthesizes real backing storage via a macro, never both give a `@State` property a declaration default (`= 0`) and assign it again in `init(...)`. Drop the declaration default and assign only in `init`; otherwise the declaration's default can silently override `init` or fail definite initialization.
- **Environment discipline:** never place high-frequency frame values or heavy closures in `@Environment` (invalidates every reader on every tick). Prefer `KeyPath` bindings over closure bindings.
- **View hierarchy & controls:** avoid `AnyView` (use `@ViewBuilder` or generics); use native `Button` over `onTapGesture` (preserves accessibility, keyboard activation, and platform styling); remove redundant single-child `Group` wrappers; use design tokens rather than magic numbers.
- **Document & window apps:** keep persistence/crypto off `@MainActor`; pause live rendering (`CADisplayLink`, animations, shimmer, snapshots) when occluded, hidden, or unfocused.

---

## 7. Metal, Graphics & Apple Silicon Runtime

- **Precompile shaders:** compile `.metal` sources at build time into `.metallib` (avoids ~150 ms cold runtime MSL compilation stalls vs < 0.2 ms precompiled load).
- **Share GPU resources:** share singleton `MTLDevice`, `MTLCommandQueue`, compiled `MTLRenderPipelineState`s, and glyph/texture atlases across panes/views; use triple-buffered ring `MTLBuffer`s rather than per-frame allocations.
- **Respect Apple TBDR GPUs:**
  - Set `loadAction` / `storeAction = .dontCare` when render-target contents are unused.
  - Avoid fragment `discard` and per-fragment depth writes where possible (defeats hidden-surface removal).
  - Use instanced/single-quad shaders (e.g., procedural curly/dotted underlines) instead of thousands of tiny geometry instances.
  - Use function constants to specialize uber-shaders at pipeline creation time; query runtime threadgroup limits rather than hardcoding.
- **Numerical & pixel parity:** handle colorspaces explicitly, check vector length before normalizing, guard divisors and `pow()` bases, initialize GPU memory explicitly, and verify Metal renderers against a deterministic CPU reference renderer with pixel-diff tests.

---

## 8. Apple Security Primitives (Keychain, CryptoKit, Hardened Runtime)

- **Keychain:** use Data Protection Keychain (`kSecUseDataProtectionKeychain: true` on macOS when signed with team/entitlements), `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` (or `AfterFirstUnlockThisDeviceOnly` only for background daemons), and `SecAccessControlCreateWithFlags` with `.biometryCurrentSet` for high-value secrets. Never silently downgrade from Data Protection Keychain to legacy login keychain without explicit migration consent.
- **CryptoKit & Secure Enclave:** wrap long-lived vault keys with Secure Enclave (`SecureEnclave.P256` / hybrid ML-KEM where available), use `AES.GCM` or `ChaChaPoly` with explicit authenticated associated data (`authenticating: aad`) binding record type, ID, and version; never reuse nonces; zeroize key buffers after use.
- **Hardened Runtime & entitlements:** ship macOS apps and CLIs with `--options runtime --timestamp`, verified via `codesign --verify --strict` and `spctl --assess`. Reject `com.apple.security.cs.allow-dyld-environment-variables`, `disable-library-validation`, and `allow-unsigned-executable-memory` (`allow-jit` only in dedicated isolated WebContent XPC processes).
- **File quarantine & links:** mark downloaded files with `LSQuarantine` attributes *before* renaming from hidden temp files to user-visible paths; reveal executable `file://` URLs in Finder rather than auto-launching them via `NSWorkspace.shared.open`.
- **Untrusted ImageIO / PDF / AVFoundation decoding:** always read image metadata (`kCGImagePropertyPixelWidth` / `Height`) and enforce `width * height <= pixelLimit` *before* calling `CGImageSourceCreateImageAtIndex`; prefer running complex media/archive decoders in a zero-network, zero-keychain sandboxed helper or XPC service.

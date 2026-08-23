# iOS Anti-Patterns

Common iOS anti-patterns to flag during review.

## 1. Optional Bool

**Severity**: Blocker
```swift
// Bad
var isEnabled: Bool?
// Good
var isEnabled: Bool = false
```
Three states (true/false/nil) make conditionals confusing. SwiftLint flags this.

## 2. Optional Array / Dictionary

**Severity**: Blocker
```swift
// Bad
var filters: [Filter]?
// Good
var filters: [Filter] = []
```
`nil` vs `[]` creates ambiguity. Model "not loaded" with an enum if needed.

## 3. Boolean Parameters for Behavioral Branching

**Severity**: Suggestion
```swift
// Bad — violates Interface Segregation
func configureMenu(showIcons: Bool = true, onClose: () -> Void = {})
// Good — separate focused types
struct IconMenu: View { ... }
struct PlainMenu: View { ... }
```

## 4. Side Effects in Computed Properties

**Severity**: Blocker
```swift
// Bad
var autoRefreshView: some View {
    Task { await refresh() }  // Side effect!
    return EmptyView()
}
// Good
SomeView().task { await refresh() }
```

## 5. onChange for Derived State

**Severity**: Important
```swift
// Bad
@State var selection: Item?
@State var isPresented = false
.onChange(of: selection) { isPresented = selection != nil }

// Good — computed Binding
private var isPresented: Binding<Bool> {
    Binding(get: { selection != nil }, set: { if !$0 { selection = nil } })
}
```

## 6. False Success UI on Error

**Severity**: Blocker
```swift
// Bad
do { try copyToClipboard(text) } catch { /* swallowed */ }
showSnackbar("Copied!")  // Lies!

// Good
do {
    try copyToClipboard(text)
    showSnackbar("Copied!")
} catch { logger.error("Copy failed: \(error)") }
```

## 7. Missing weak self in Class Closures

**Severity**: Blocker (memory leak)
```swift
// Bad
service.fetch { result in self.items = result }
// Good
service.fetch { [weak self] result in
    guard let self else { return }
    self.items = result
}
```
In `for await` loops: guard-let self **inside** each iteration.

## 8. Ad-hoc Task Instead of AsyncButton

**Severity**: Suggestion
```swift
// Bad
Button("Save") { Task { await viewModel.save() } }
// Good
AsyncButton("Save") { await viewModel.save() }
```
AsyncButton prevents double-taps and manages Task lifecycle.

## 9. Over-marking async throws

**Severity**: Suggestion
```swift
// Bad
func formatName() async throws -> String { "\(first) \(last)" }
// Good
func formatName() -> String { "\(first) \(last)" }
```

## 10. Initializers in Extensions

**Severity**: Nit
```swift
// Bad — circumvents type_body_length
extension MyView { init(config: Config) { ... } }
// Good
struct MyView: View { init(config: Config) { ... } }
```

## 11. @State with Reference Type (Legacy Context)

**Severity**: Important — **check Swift version first**
```swift
// Legacy (ObservableObject): BAD
@State var viewModel = MyViewModel()
// Legacy: GOOD
@StateObject var viewModel = MyViewModel()

// Modern (@Observable, iOS 17+): @State is CORRECT
@State var viewModel = MyViewModel()
```

## 12. Ignoring Task.sleep Cancellation

**Severity**: Important
```swift
// Bad
try? await Task.sleep(nanoseconds: 1_000_000_000)
// still executes even if cancelled

// Good
try await Task.sleep(nanoseconds: 1_000_000_000)
// or
try? await Task.sleep(nanoseconds: 1_000_000_000)
guard !Task.isCancelled else { return }
```

## 13. default in Exhaustive Switches

**Severity**: Suggestion
```swift
// Bad — silences compiler when new cases are added
switch myEnum {
case .a: handleA()
default: break
}
// Good — compiler reminds you when cases are added
switch myEnum {
case .a: handleA()
case .b: handleB()
}
```
`@unknown default` only for external/system enums.

## 14. Widening Access for Tests

**Severity**: Important
```swift
// Bad — opening internal state for tests
internal(set) var items: [Item] = []
// Good — test observable behavior
private(set) var items: [Item] = []
```
"Tests should cover public interfaces and assert on observable behaviours."

## 15. Codable When Only Decoding

**Severity**: Nit
```swift
// Bad
struct APIResponse: Codable { ... }  // Never encoded
// Good
struct APIResponse: Decodable { ... }
```

## 16. Missing Accessibility Labels

**Severity**: Important
```swift
// Bad
Button { toggle() } label: { Image(systemName: "heart.fill") }
// Good
Button { toggle() } label: { Image(systemName: "heart.fill") }
.accessibilityLabel("Toggle favorite")
```

## 17. Stale Bindings in UIRepresentable Coordinator

**Severity**: Blocker
SwiftUI can recreate the struct (and its bindings) without recreating the
coordinator. Update bindings in `updateUIView`, not just init.

## 18. Loading State Not Reset on Error

**Severity**: Important
```swift
// Bad
isLoading = true
let result = try await fetch()  // if this throws, isLoading stays true
isLoading = false

// Good
isLoading = true
defer { isLoading = false }
let result = try await fetch()
```

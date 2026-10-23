# Latest SwiftUI APIs — Deprecated to Modern Lookup

Read this first for every SwiftUI task to avoid deprecated APIs.

Note: not every left-column entry is formally deprecated — some (e.g., `ObservableObject`, `GeometryReader`) are legacy/discouraged patterns. The "Deprecated" column means "prefer the modern replacement".

## Always Use (iOS 15+)

| Deprecated | Modern |
|-----------|--------|
| `navigationBarTitle(_:)` | `navigationTitle(_:)` |
| `navigationBarItems(...)` | `toolbar { ToolbarItem(...) }` |
| `navigationBarHidden(_:)` | `toolbarVisibility(.hidden, for: .navigationBar)` (iOS 18+; on iOS 16–17 use `toolbar(.hidden, for: .navigationBar)`) |
| `statusBar(hidden:)` | `statusBarHidden(_:)` |
| `edgesIgnoringSafeArea(_:)` | `ignoresSafeArea(_:edges:)` |
| `colorScheme(_:)` | `preferredColorScheme(_:)` |
| `foregroundColor(_:)` | `foregroundStyle(_:)` |
| `cornerRadius(_:)` | `clipShape(.rect(cornerRadius:))` |
| `autocapitalization(_:)` | `textInputAutocapitalization(_:)` |
| `actionSheet(...)` | `confirmationDialog(...)` |
| `alert(isPresented:content:)` | `alert(_:isPresented:actions:message:)` |
| `animation(_:)` (no value) | `animation(_:value:)` |
| `accessibility(label:)` etc. | `accessibilityLabel()` etc. |
| `TextField` `onCommit`/`onEditingChanged` | `onSubmit` + `focused` |
| Manual `EnvironmentKey` | `@Entry` macro (back-deploys) |
| `onTapGesture()` for buttons | `Button` (unless need location/count) |

## iOS 16+

| Deprecated | Modern |
|-----------|--------|
| `NavigationView` | `NavigationStack` / `NavigationSplitView` |
| `accentColor(_:)` | `tint(_:)` |
| `disableAutocorrection(_:)` | `autocorrectionDisabled(_:)` |
| `UIPasteboard.general` | `PasteButton` |

## iOS 17+

| Deprecated | Modern |
|-----------|--------|
| `ObservableObject` | `@Observable` |
| `@StateObject` | `@State` (with `@Observable`) |
| `@ObservedObject` | `@Bindable` (with `@Observable`) |
| `onChange(of:perform:)` | `onChange(of:) { }` or `onChange(of:) { old, new in }` |
| `MagnificationGesture` | `MagnifyGesture` |
| `RotationGesture` | `RotateGesture` |
| `coordinateSpace(name:)` | `coordinateSpace(.named(...))` |
| `GeometryReader` (for measurements) | `onGeometryChange(for:of:action:)` |
| `GeometryReader` (for sizing) | `containerRelativeFrame()` |
| `GeometryReader` (for effects) | `visualEffect { content, geometry in }` |

### New iOS 17+ APIs
- `controlSize(.extraLarge)` — extra-large prominent buttons

## iOS 18+

| Deprecated | Modern |
|-----------|--------|
| `tabItem(_:)` | `Tab` API |
| Preview structs | `@Previewable @State` in `#Preview` |

### New iOS 18+ APIs
- `navigationTransition(.zoom(sourceID:in:))` paired with `matchedTransitionSource(id:in:)` — zoom transition morphing from a source view (iOS 18+, not new in iOS 26)

## iOS 26+

| Deprecated | Modern |
|-----------|--------|
| Manual `animatableData` | `@Animatable` macro |
| `presentationBackground(_:)` | Default Liquid Glass sheet material |
| Custom toolbar backgrounds | `scrollEdgeEffectStyle(_:for:)` |

### New iOS 26+ APIs
- `tabBarMinimizeBehavior(_:)` — tab bar minimization on scroll
- `tabViewBottomAccessory` — persistent controls above tab bar
- Search tab morphing into the search field — new iOS 26 behavior for `Tab(role: .search)` (`TabRole.search` itself is iOS 18+)
- `ToolbarSpacer` — fixed/flexible toolbar item spacing
- `sharedBackgroundVisibility(.hidden)` — remove glass group background
- `searchToolbarBehavior(.minimize)` — minimized search button
- `TextEditor(text: $attributedString)` — rich text editing
- `WebView(url:)` / `WebView(page)` — web content display
- Slider tick marks and neutral value

### New iOS 27 (SDK 27) APIs
- `dragContainer(for:)` — multi-item drag operations (iOS/iPadOS 27.0, macOS 26; see `swiftui-whats-new-27` for SDK 27 changes)

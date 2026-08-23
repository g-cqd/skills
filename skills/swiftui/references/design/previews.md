# Preview-Driven Development

## Every View Needs Previews

Every view must include `#Preview` with multiple scenarios:

```swift
#Preview("Light Mode") {
  ProfileView(viewModel: .preview)
}

#Preview("Dark Mode") {
  ProfileView(viewModel: .preview)
    .preferredColorScheme(.dark)
}

#Preview("Loading") {
  ProfileView(viewModel: .loading)
}

#Preview("Error") {
  ProfileView(viewModel: .error)
}

#Preview("Dynamic Type XXL") {
  ProfileView(viewModel: .preview)
    .environment(\.dynamicTypeSize, .xxxLarge)
}
```

## Required Preview Scenarios

| Scenario | Purpose |
|----------|---------|
| Light mode | Default appearance |
| Dark mode | Dark theme rendering |
| Loading state | Progress indicator |
| Error state | Error with retry |
| Empty state | No data message with CTA |
| Dynamic Type XXL | Accessibility scaling |
| Compact width | iPhone layout |
| Regular width | iPad/Mac layout |

## Preview Data

Create static preview helpers on your model/ViewModel types:

```swift
extension ProfileViewModel {
  static var preview: ProfileViewModel {
    let vm = ProfileViewModel(service: MockUserService())
    vm.state = .loaded(User.preview)
    return vm
  }

  static var loading: ProfileViewModel {
    let vm = ProfileViewModel(service: MockUserService())
    vm.state = .loading
    return vm
  }

  static var error: ProfileViewModel {
    let vm = ProfileViewModel(service: MockUserService())
    vm.state = .failed(PreviewError.sample)
    return vm
  }
}
```

## Pre-Implementation Design Review

Before building a new UI component, consider:

1. **User Goal**: What is the primary goal the user is trying to achieve?
2. **Component Breakdown**: What atoms, molecules, and organisms are needed?
3. **State Analysis**: Idle, loading, loaded, empty, and error states?
4. **Accessibility Strategy**: VoiceOver labels, Dynamic Type switching, reduced motion, contrast
5. **Responsiveness**: Compact vs regular, landscape, Dynamic Type
6. **Open Questions**: What ambiguities need clarification?

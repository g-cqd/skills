# Android Review Guide

Review rules for Android/Kotlin/Compose codebases.

## Correctness and Safety

### Null Safety
- **Never use `!!`** — the team agreed this causes runtime crashes. Use `?.let`,
  `?: return`, `requireNotNull` with message, or restructure
- Presentable types should have minimal nullable fields
- Sealed interfaces/classes for discriminated unions over nullable fields
- Handle unknown backend enum values gracefully — the app must not crash

### State Management
- `MutableStateFlow` + `asStateFlow()` as the standard pattern
- Never expose `MutableStateFlow` publicly — always `.asStateFlow()`
- UiState as data classes with `copy()` updates via `uiState.update { it.copy(...) }`
- One ViewModel per page; LogicHandlers for sub-concerns
- UiState in separate files from ViewModel
- `collectAsStateWithLifecycle()` for collecting flows in Compose
- `rememberSaveable` for surviving configuration changes
- `remember` required for objects created in Composable scope — otherwise
  recreated every frame

### Error Handling
- Never swallow exceptions silently
- `Result` type for new code; migrating away from custom `Either`
- Handle both success and failure paths in every service call

### Threading
- `viewModelScope.launch` for ViewModel coroutines
- `Dispatchers.Default` as standard; `Dispatchers.IO` only at actual I/O boundary
- Mature libraries (Retrofit, OkHttp) handle their own threading — no extra
  `withContext(IO)` needed
- Debounce repetitive events (WebSocket notifications, search input)
- `LaunchedEffect` already launches a coroutine — don't nest `launch` inside

## Compose Patterns

- **Stateful/stateless split**: One public Composable with ViewModel injection,
  one private stateless Composable for previews
- **No Boolean parameters for variants** — inject behavior via lambdas,
  sealed types, or separate Composables (Open/Closed Principle)
- **Named arguments mandatory** — especially with multiple parameters of same type
- **Previews required**: Use the project's preview annotation/wrapper for
  light/dark variants (see `project-conventions`)
- **ComposableNaming**: Composable functions start with uppercase; avoid `= `
  shorthand for complex returns
- **Modifier parameter**: Always accept `modifier: Modifier = Modifier` as
  first parameter for layout Composables
- **Don't inject whole ViewModels** when only one function is needed — pass
  lambdas or specific values
- **Semantic colors**: Use the design system's semantic color scheme, never
  raw `Color.White`
- **Typography**: Use design-system typography constants, never raw Material
  `typography`

## Architecture

### ViewModel + LogicHandler Pattern
```
ViewModel (one per page)
├── UiState (data class, separate file)
├── LogicHandler A (receives MutableStateFlow<UiState>)
└── LogicHandler B (encapsulates sub-concern)
```

### Dependency Injection (Koin)
- Register ViewModels with `viewModelOf(::MyViewModel)` shorthand
- UseCases as `factory { MyUseCase() }`
- Avoid `single` for ViewModels — use `viewModel` or `viewModelOf`
- `koinInject()` for singletons used locally (e.g., FeatureFlagStateProvider)
- Consider `ViewModelParams` data class when constructor grows large
- Feature modules have their own Koin modules

### Entity → Presentable Migration
The team is migrating from Room-based offline to API-first:

**Old (deprecated)**: BE Response → Room Entity → UI
**New (target)**: BE Response → Presentable → UI

Rules:
- No new `@Entity` classes
- No new Room converters
- `Response` classes in the API module parse BE JSON
- `Presentable` classes contain **only** what's needed for UI
- Conversion via constructors or `.toPresentable()` extensions
- "Just because BE sends something, doesn't mean we need to parse it"

### Navigation
- Migrating from Fragment-based to Compose Navigation 3
- Separate nav stacks: login (unauthenticated) vs main (authenticated)
- Pass lambdas (e.g., `navigateBack`) not NavController references
- Feature flags for navigation changes
- Don't add new logic to Fragments — use ViewModels/Composables

## Naming

- `is` prefix for Booleans: `isMenuShown` not `menuShown`
- `on...Click` for callbacks: `onSendChatMessageClicked`
- `Presentable` prefix for UI models
- Descriptive enum values: `DESCENDING`/`ASCENDING` not abbreviations
- Grammar matters: `handleEditingStartTime` or `handleStartTimeEdit`
- Action functions: `showStatusSelector(task)` + `hideStatusSelector()`
  over `setVisibleTaskForStatusSelector(task?)`

## Kotlin Idioms

- `buildList` over `mutableListOf().apply` for conditional list building
- `sealed interface` when sealed class adds nothing
- Destructuring: `val (name, color) = when (status) { ... }`
- `Result` for new code, migrating away from `Either`
- Avoid `run` when direct return suffices
- Extension functions for conversions (`as`/`to` prefix) and value transforms

## API and Networking

- Response classes: only define fields you actually use
- Trailing `/` on URLs — backend behaves inconsistently without it
- `@field:Json(name = ...)` annotations, `@JsonClass(generateAdapter = true)`
- Define shared constants: `object Paging { const val DEFAULT_PAGE_SIZE = 40 }`
- Request batch APIs from backend instead of N individual calls
- CodingKeys equivalent: Moshi `@Json` for bridging BE naming to domain naming

## Design System

- Design-system typography constants for fonts, semantic color scheme for colors
- The project's preview annotation for consistent previews
- If/else blocks always use braces `{}`
- Compare implementation against Figma designs
- Flag magic padding/spacing numbers

## Localization

- English base strings; translators fill other languages
- `.withColon`, `.withTrailingSpace` extensions for punctuation
- Add string resources before the code using them
- Verify grammar across translations

## Code Organization

- Package by feature under the app's UI root package
- `bottomsheet` package under UI for bottom sheets
- Extension functions in: target class file, dedicated extensions file, or
  base utility file — not inline in unrelated files
- One file per major class/composable

# Android Anti-Patterns

Common Android anti-patterns to flag during review.

## 1. `!!` Operator

**Severity**: Blocker
```kotlin
// Bad — crashes at runtime
val name = user!!.name
// Good
val name = user?.name ?: return
// or
val name = requireNotNull(user) { "User must be set before accessing name" }.name
```
Team agreement: never use `!!`.

## 2. Exposing MutableStateFlow

**Severity**: Blocker
```kotlin
// Bad
val uiState = MutableStateFlow(MyUiState())
// Good
private val _uiState = MutableStateFlow(MyUiState())
val uiState = _uiState.asStateFlow()
```

## 3. Boolean Parameters for Variants

**Severity**: Important
```kotlin
// Bad — violates Open/Closed Principle
@Composable
fun TicketCard(isCompact: Boolean = false, showActions: Boolean = true)

// Good — composition
@Composable
fun CompactTicketCard(...)
@Composable
fun FullTicketCard(actions: @Composable () -> Unit)
```
"Using a Boolean argument like this is simply the worst thing we could do
here, because it doesn't allow us to introduce yet another flavor."

## 4. Missing `remember` in Composables

**Severity**: Blocker
```kotlin
// Bad — new instance every frame
@Composable
fun MyScreen() {
    val handler = MyLogicHandler(viewModel)  // recreated every recomposition!
}
// Good
@Composable
fun MyScreen() {
    val handler = remember { MyLogicHandler(viewModel) }
}
```

## 5. New Room Entity Classes

**Severity**: Blocker
```kotlin
// Bad — adding to legacy Room layer
@Entity(tableName = "ticket_schedule")
data class TicketScheduleEntity(...)

// Good — Response + Presentable pattern
@JsonClass(generateAdapter = true)
data class TicketScheduleResponse(...)

data class TicketSchedulePresentable(
    // only fields needed for UI
)
```

## 6. Injecting Whole ViewModel into Child Composable

**Severity**: Suggestion
```kotlin
// Bad
@Composable
fun ChildComponent(viewModel: ParentViewModel)  // tight coupling

// Good
@Composable
fun ChildComponent(
    uiState: ChildUiState,
    onAction: (ChildAction) -> Unit,
)
```

## 7. `mutableListOf().apply` for Conditional Lists

**Severity**: Nit
```kotlin
// Bad — can cause state issues
val items = mutableListOf<Item>().apply {
    add(baseItem)
    if (showExtra) add(extraItem)
}
// Good
val items = buildList {
    add(baseItem)
    if (showExtra) add(extraItem)
}
```

## 8. Testing Implementation Details

**Severity**: Important
```kotlin
// Bad — testing internal state
@VisibleForTesting
internal var _internalState: String = ""

// Good — test observable behavior through public API
```
"We should never ever expose functions or properties to just make them only
available for tests."

## 9. Adding Logic to Fragments

**Severity**: Suggestion
```kotlin
// Bad — new logic in Fragment (migration liability)
class TicketFragment : Fragment() {
    override fun onViewCreated(...) {
        // new business logic here
    }
}
// Good — logic in ViewModel/Composable
class OrderViewModel : ViewModel() { ... }
```

## 10. Missing `rememberSaveable`

**Severity**: Important
```kotlin
// Bad — lost on configuration change
var expanded by remember { mutableStateOf(false) }
// Good — survives rotation, process death
var expanded by rememberSaveable { mutableStateOf(false) }
```

## 11. Raw Colors and Typography

**Severity**: Nit
```kotlin
// Bad
Text(color = Color.White, style = MaterialTheme.typography.bodyMedium)
// Good — semantic tokens from the project's design system
Text(
    color = DesignSystem.colors.surface,
    style = DesignSystem.typography.bodyMedium,
)
```

## 12. Missing Named Arguments

**Severity**: Nit
```kotlin
// Bad
createOrder("Bug", 1, true, null)
// Good
createOrder(
    title = "Bug",
    priority = 1,
    isUrgent = true,
    assignee = null,
)
```

## 13. Unnecessary Fields in Presentable

**Severity**: Suggestion
```kotlin
// Bad — includes fields not needed for UI
data class TicketPresentable(
    val id: Int,
    val title: String,
    val internalDbId: Long,      // not needed for UI!
    val rawJsonPayload: String,  // not needed for UI!
)
```
"Presentable types should represent presentation logic/state. If properties
are not needed to present something, they should NOT be included."

## 14. Missing Trailing Slash on API URLs

**Severity**: Important
```kotlin
// Bad — backend behaves inconsistently
@GET("api/v3/tickets")
// Good
@GET("api/v3/tickets/")
```

## 15. Boolean Spy Tracking in Tests

**Severity**: Suggestion
```kotlin
// Bad — only knows something happened
var called = false
// Good — knows exact count
verify(exactly = 1) { onCallSubmitted() }
```

## 16. Missing Content Descriptions (Accessibility)

**Severity**: Important
```kotlin
// Bad — icon button invisible to TalkBack
IconButton(onClick = { toggleFavorite() }) {
    Icon(Icons.Default.Favorite, contentDescription = null)
}

// Good
IconButton(onClick = { toggleFavorite() }) {
    Icon(Icons.Default.Favorite, contentDescription = "Toggle favorite")
}
```
Every interactive element with an icon-only label needs a `contentDescription`.
Decorative images should use `contentDescription = null` explicitly.

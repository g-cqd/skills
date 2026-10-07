---
name: apple-platforms
description: >-
  Apple platforms: adopt iOS 26 / 27 frameworks, including Liquid Glass, Foundation Models,
  App Intents (best practices, supportedModes, snippets, Spotlight indexing, Visual
  Intelligence), StoreKit, SwiftData, and AlarmKit. Use for framework migration, UIKit
  multi-window and resizable windows, UIScreen.main and interfaceOrientation replacements,
  safe areas, and UIScene lifecycle for iOS 27. For SwiftUI views, use `swiftui`; for
  language features, use `swift`; for builds, use `xcode`.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Apple Platforms

This skill owns **which platform API to call and how to migrate onto it**. It does not own view
construction (`swiftui`), the language (`swift`), or the toolchain (`xcode`).

Two halves: §1–2 adopt new frameworks; §3 modernizes existing UIKit code. They meet at the
UIScene lifecycle, which is an adoption task *and* a hard iOS 27 gate.

## Contract

```
§GATE     ? deployment-target BEFORE recommending ⇒ most APIs iOS-26+
§VERIFY   apple-docs MCP|CLI ≻ curated-summary ≻ memory
          conflict ⇒ primary-source (Apple-docs|SDK-headers) wins
§STATE    ! version-context ∀answer ∷ "iOS 26+, back-deploys to…"
§SCOPE    modernization ∷ target-API-only · ¬opportunistic-cleanup
§ATOMIC   multi-part-pattern ⇒ ALL-parts ∨ skip-with-reason · ¬partial
§BAN      empty-diff ∀file-containing-target-API · vague-TODO ·
          replace-dynamic-value-with-literal · walk-global-scene-state ·
          delete-old-method ∀deprecate-and-forward · collapse-a-branch
```

---

## 1. Verification discipline

These APIs move fast and training memory ages badly.

1. **Check the deployment target before recommending an API.** Most of §2 requires iOS 26+.
   Confirm the target and the symbol's `@available` from the project and the docs, not from
   memory; recognizing an API name is not knowing which OS introduced it.
2. **Verify against the documentation corpus** through `apple-docs` before trusting a curated
   summary here or anything remembered. Where verification was not possible, say so in the
   answer rather than presenting the claim with the same confidence as a verified one.
3. When a reference disagrees with observed compiler behavior, **the primary source wins** — Apple
   docs and SDK headers.
4. **State the version context in the answer**: "available iOS 26+, back-deploys to …".

---

## 2. SDK-generation framework adoption

The iOS 26 / macOS 26 generation. For the next generation see `swiftui` (SDK 27 view APIs) and
§3.4 plus `xcode` (Xcode 27 tooling).

| Area | Reference |
|---|---|
| Liquid Glass — overview | `references/liquid-glass.md` |
| Liquid Glass — SwiftUI | `references/SwiftUI-Implementing-Liquid-Glass-Design.md` |
| Liquid Glass — UIKit | `references/UIKit-Implementing-Liquid-Glass-Design.md` |
| Liquid Glass — AppKit | `references/AppKit-Implementing-Liquid-Glass-Design.md` |
| Liquid Glass — WidgetKit | `references/WidgetKit-Implementing-Liquid-Glass-Design.md` |
| Swift 6.2 concurrency updates | `references/Swift-Concurrency-Updates.md` |
| `InlineArray`, `Span` | `references/Swift-InlineArray-Span.md` |
| Swift 6.2 language updates | `references/swift-updates.md` |
| Foundation Models — on-device LLM | `references/FoundationModels-Using-on-device-LLM-in-your-app.md` |
| Visual Intelligence | `references/Implementing-Visual-Intelligence-in-iOS.md` |
| AppIntents — WWDC 2025 overview | `references/AppIntents-Updates.md` |
| App Intents — best practices and traps | `references/app-intents/`, routed in §2.1 |
| App Intents — iOS 26 and 27 APIs | `references/app-intents-27/`, routed in §2.1 |
| StoreKit | `references/StoreKit-Updates.md` |
| SwiftData class inheritance | `references/SwiftData-Class-Inheritance.md` |
| AlarmKit | `references/SwiftUI-AlarmKit-Integration.md` |
| 3D Swift Charts | `references/Swift-Charts-3D-Visualization.md` |
| MapKit GeoToolbox | `references/MapKit-GeoToolbox-PlaceDescriptors.md` |
| AttributedString | `references/Foundation-AttributedString-Updates.md` |
| WebKit integration | `references/SwiftUI-WebKit-Integration.md` |
| Styled text editing | `references/SwiftUI-Styled-Text-Editing.md` |
| Toolbar customization | `references/SwiftUI-New-Toolbar-Features.md` |
| SwiftUI feature overview | `references/swiftui-features.md` |
| visionOS widgets | `references/Widgets-for-visionOS.md` |
| visionOS overview | `references/visionos.md` |
| Accessibility updates | `references/accessibility.md` |
| Framework overview | `references/frameworks.md` |
| Start here | `references/_guide.md` |

**Liquid Glass note:** the opt-out is removed in Xcode 27. Treat adoption as scheduled work, not
optional polish.

### 2.1 App Intents

Apple publishes this guidance and it supersedes prior training. Read the reference for the topic in
play before writing or reviewing code; the files teach the non-obvious traps rather than restate
the framework. For a broad review of a large codebase, scan for the areas (individual intents,
entities, queries, the shortcuts provider), propose one focus area at a time, and split a
whole-codebase review into sections on a task list.

- **Public API only.** Never emit an underscore-prefixed or no-longer-public symbol, and never
  invent a type, initializer or parameter to make a snippet compile.
- **Identifiers are a public contract.** Saved shortcuts and donations replay an intent by its
  type name, with `AppEntity.id` values and `AppEnum` raw values as stored parameters, and
  Spotlight depends on the same ids. An `AppShortcut` phrase is a separate contract (spoken
  invocation). Adding is safe; renaming, removing or renumbering a shipped one changes behavior,
  so flag it rather than doing it silently.
- **Gate each version-specific API** with its real `@available` floor (every `app-intents-27`
  reference states it) and `if #available`, instead of dropping the feature or misdating it.

Evergreen traps, in `references/app-intents/`:

| Topic | Trap | File |
|---|---|---|
| `perform()` | `Sendable`, not `@MainActor` (hop with `await MainActor.run`); retriable via `restartPerform`, so do irreversible work last; `requestConfirmation` before destructive work; return `.result(...)`, never a bare value | `execution-model.md` |
| Entities and queries | `AppEntity.id` stable across launches and devices; `entities(for:)` is batched; `suggestedEntities()` defaults empty; `entities(matching:)` is not auto-filtered; only `@Property` members are system-visible; `EnumerableEntityQuery` loads everything | `entities-and-queries.md` |
| "Find X where" | `EntityPropertyQuery`: you execute the predicate, the framework only parses it | `entity-property-queries.md` |
| `AppEnum` | Raw values persist as strings, so never renumber; a case without `caseDisplayRepresentations` is a run-time `fatalError` | `app-enum.md` |
| Parameters | `requestValue` versus `needsValueError`; only params in `Summary(...)` show in Shortcuts; `When`/`Switch` for conditional display; `@IntentParameterDependency` for dependent options | `parameters.md`, `parameter-summaries.md` |
| `@Dependency` | Register at launch (unregistered is a `fatalError`); must be `Sendable`; lives on the intent or query, never on `AppEntity`/`AppEnum` | `dependencies.md` |
| Errors | Only `CustomLocalizedStringResourceConvertible` errors surface a message; prebuilt `AppIntentError` cases from iOS 18 | `results-and-errors.md` |
| Donation | In-app actions are not auto-donated: call `IntentDonationManager.shared.donate`; `PredictableIntent` only describes | `donation.md` |
| Localization | User-facing strings are literal `LocalizedStringResource`; a runtime `String` yields no extractable key | `localization.md` |
| Shortcut phrases | `shortTitle` and `systemImageName` required; include `\(.applicationName)` or the phrase is silently dropped; `INAlternativeAppNames` for synonyms | `app-shortcut-phrases.md` |
| Opening | `OpenIntent`, `OpenURLIntent`, `URLRepresentableEntity` for universal links | `url-representation.md` |
| Widgets and controls | `WidgetConfigurationIntent` / `ControlConfigurationIntent` are parameter-only: no `perform()` | `configuration-intents.md` |
| Modeling | `AppEnum` for a fixed set, `AppEntity` plus a query for a dynamic one, plain `@Parameter` for free-form; one intent per atomic task | `factoring.md` |

New in iOS 26 and 27, in `references/app-intents-27/` (floors are in each file):

| Need | Reference |
|---|---|
| Where an intent runs: `supportedModes`, replacing `openAppWhenRun`, `continueInForeground`, `UndoableIntent`, `CancellableIntent`, `LongRunningIntent`, `IntentExecutionTargets` | `execution-modes.md` |
| Interactive snippet cards: `SnippetIntent`, `Button(intent:)`; `perform()` must be idempotent | `interactive-snippets.md` |
| Pick one of a few options mid-`perform()`: `requestChoice(between:dialog:)` | `requestchoice.md` |
| Visual Intelligence: `IntentValueQuery`, `SemanticContentDescriptor`, `@UnionValue` | `visual-intelligence.md` |
| Resolving "this" on screen: `appEntityIdentifier`, `AppEntityUIElement` | `onscreen-entities.md` |
| Spotlight: `@ComputedProperty`, `@DeferredProperty(indexingKey:)`, `IndexedEntityQuery`, `relatedAppEntityIdentifier` | `spotlight-indexing.md`, `convenience-properties.md` |
| Apple Intelligence schemas: `@AppIntent(schema:)`; `@AssistantIntent` is deprecated | `schema-adoption.md` |
| Proactive suggestions: `RelevantEntities`, `AppEntityContext` (use with donation) | `relevance-and-context.md` |
| Entities across devices and shared or public ownership: `SyncableEntity`, `EntityOwnership` | `cross-device-and-ownership.md` |
| Running a system shortcut from a widget button: `SystemShortcut` | `system-shortcuts.md` |
| Large entity sets: `EntityCollection`; union parameters: `AppUnionValue` | `entity-collection.md`, `union-values.md` |
| Unit-testing intents out of process with `AppIntentsTesting` | `testing.md` |

---

## 3. UIKit modernization

Modernize UIKit apps — Swift and Objective-C — for multi-window and resizable presentation by
eliminating legacy shared-state APIs and migrating to the scene lifecycle.

### 3.1 The governing principles

The task references cite these by number. Keep the numbering.

1. **Closest to the consumer.** Prefer the information nearest the point of use — a view's trait
   collection over the window's, the window's over the screen's.
2. **Always apply a replacement when the target API is present.** A lone TODO is a failure. **An
   empty diff on a file containing the target API is also a failure.** Skip only when the API
   appears exclusively in dead code (`#if 0`). When two replacements are both valid, pick the one
   that fits the request rather than producing nothing. Never silently skip a file — if you will
   not change it, say why. Do not over-think simple substitutions (§3.2): empty diffs on simple
   files are the single most common mistake.
3. **TODOs must be actionable.** State *why*, *what the replacement would be*, and any lifecycle or
   threading concern, on their own line above the unchanged code. A vague TODO is worse than none.
   Indent every line of an inserted comment to match the line it precedes; re-emitting the next
   line to realign it edits a line you were not asked to touch.
4. **No redundant TODO.** Where an existing `#pragma clang diagnostic ignored` with a bug
   reference, an existing TODO, or a deprecation comment already covers the migration, add nothing.
5. **Ask before a risky change.** When a replacement could break callers or change observable
   behavior — a header signature other modules import, or substituting `width > height` for
   orientation where left-versus-right matters — ask first. Fall back to a TODO only when running
   non-interactively or the user declines. This never applies to the drop-in replacements in
   §3.2, which must simply be applied (principle 2).
6. **Honor explicit instructions.** If the user names an attribute, parameter name or position,
   trait source, or fallback, use exactly that. Apply the reference-file defaults only when the
   request is general.
7. **Never replace a dynamic value with a literal.** Replacements stay dynamic.
8. **Preserve control flow.** Prefer drop-in replacements that keep the original structure; add a
   guard or early return only when direct substitution does not work. Verify branching survives
   every edit — collapsing `if`/`else` into sequential execution runs both bodies
   unconditionally, a critical bug. Remove a branch only when the active task names that condition
   itself as the defect and says the correct behavior is unconditional; then delete the condition,
   keep the body that matches the correct behavior, and name the removed branch in the summary.
9. **Stay in scope.** Touch only lines containing the active task's target API. No adjacent
   deprecation fixes, no whitespace trimming, no reformatting. Out-of-scope edits turn a clean
   change into a warning.
10. **Extract a repeated replacement** into a named local when the same value is used several times
    in one scope.
11. **Never walk global scene or window state** as a "replacement" — not `UIApplication.shared`,
    not `UIDevice.current`, not `UIScreen.main`. If no local object is in reach, add a parameter to
    the method and update its callers.
12. **Complete patterns — atomic, never partial.** A multi-part pattern applies as one unit (§3.4);
    an API replacement plus its reactive update (trait-change observation) is one change. If you
    cannot finish every part, skip with an explicit reason.
13. **Preserve unrelated guards and fallbacks.** Change only the reference to the target API. Leave
    `respondsToSelector:` checks, nil guards, and `@available` checks alone; each exists for its own
    reason.
14. **Off-target replacement guard.** Before editing a line, verify it contains the target API of
    the *active* task and that you are editing the deprecation the user asked about, not a nearby
    line that looks similar.

### 3.2 Fast path — apply and move on

A large fraction of `UIScreen.main` occurrences need no analysis:

| Original | Replacement |
|---|---|
| `UIScreen.main.scale` (Swift) in a `UIView`/`UIViewController` instance method, used inline | `self.traitCollection.displayScale` |
| `[UIScreen mainScreen].scale` (ObjC), same conditions | `self.traitCollection.displayScale` |
| `UIScreen.main.scale` in `layoutSubviews`, `drawRect:`, `updateConstraints`, `viewIsAppearing:` | `self.traitCollection.displayScale` — no registration needed, UIKit calls these on trait change |

If the enclosing class is a `UIView`/`UIViewController` and the value is not stored into an ivar,
layer property, constraint, or cached image, **just substitute**. Reach for analysis only for a
non-view class, a cached value, a class/static method, or special instructions.

### 3.3 Workflow

**Phase 0 — prerequisites.** When the request covers a project, run the three read-only checks in
§3.7 first.

**Phase 1 — detect.** Run detection for **every** task in the registry that applies, not just one.
Foldable-iPhone ("iPhone Duo") and Stage Manager requests, split-screen readiness, and "make this
app resizable" all mean every task, because a screen that changes size exposes them together.

**Phase 2 — analyze** each occurrence: class hierarchy (view subclass vs plain `NSObject`), method
kind (instance, static, `dispatch_once` helper), lifecycle phase, and intent (layout, rendering,
display scale, full-screen dimensions). Use subagents to keep context small.

**Phase 3 — decide.**

| Condition | Action |
|---|---|
| A safe 1:1 replacement exists | **Apply it**, with no added commentary |
| Several valid approaches, or relocation >10 lines | **Ask the user** |
| No safe replacement (rare) | Leave an actionable TODO — never a silent empty diff |

**Phase 3b — completeness.** Write out the full file list before starting and mark each done.
Process files one at a time or in batches of 3 to 5, so the tail of the list is not dropped.
Before finishing, compare the list against your output: **any file with neither a diff nor an
explicit skip reason is a processing failure.** Large files (1000+ lines) and macro-heavy files
are not exempt; when unsure how to fix one, ask rather than emit an empty diff.

**Phase 4 — implement** per the active task's gates and post-file checklist.

**Phase 5 — verify** file coverage with a subagent. Every input file has a non-empty diff or a
stated reason.

### 3.4 Deprecate-and-forward — atomic, never partial

Multi-part patterns apply as one unit. Deprecate-and-forward has **four** parts:

1. A new overload with the right parameter name, type, and position.
2. The old method delegating to it via shared state (`UITraitCollection.current`, `UIScreen.main`).
3. The old method marked deprecated.
4. **The deprecated wrapper kept in place.**

> **Never delete the old method when adding the overload** — even if it looks unused. Deleting it
> removes the deprecation signal and drops the migration bridge callers rely on to find the new
> API. This holds for ObjC methods, Swift methods, initializers, computed properties, and
> protocol-extension methods. If you are removing a method while adding an overload, stop.

Downgrading the pattern to an inline reference to a shared object is an error for the same reason.
If you cannot complete all four parts, skip with an explicit reason.

Where an API replacement also needs a **reactive update** — trait-change observation — the two are
one atomic change. Never apply one without the other.

**Deprecate at the lowest method that touches the deprecated API.** When several callers funnel
into one helper that reads the shared state, deprecate **the helper**. Forcing every public caller
to grow a `traitCollection:` parameter produces churn far wider than the migration needs. When
each caller reads the state directly with no helper, the callers are the lowest point.

### 3.5 Task registry

Apply every task unless the request scopes to a subset. Run in order.

| Task | Reference | What it does |
|---|---|---|
| `UIScreen.main` | `references/uikit/uiscreen-task.md` | Replace with context-appropriate APIs |
| Orientation | `references/uikit/orientation-task.md` | Replace layout-related orientation checks with size classes or window bounds, and migrate the deprecated scene geometry callback to `didUpdateEffectiveGeometry` |
| Scene lifecycle | `references/uikit/scene-lifecycle-task.md` | Migrate `AppDelegate` to `SceneDelegate` |
| Safe area | `references/uikit/safe-area-task.md` | Replace `topLayoutGuide` and hard-coded insets with safe-area references; handle asymmetric insets and insets that change while the app runs |
| `userInterfaceIdiom` | `references/uikit/idiom-task.md` | Replace layout-related idiom checks with size classes; read a genuinely needed idiom from the local trait collection |

Two things the orientation task spells out: `windowScene.effectiveGeometry.interfaceOrientation` is
current API but not a replacement for a layout decision, because a scene reporting landscape can
be taller than wide; and `windowScene(_:didUpdate:interfaceOrientation:traitCollection:)` migrates
only at an iOS 26 floor and only together with a guard that does expensive work once the size
changed and `isInteractivelyResizing` is false. Catalyst window-frame persistence
(`systemFrame`, `#if targetEnvironment(macCatalyst)`) is in `uiscreen-task.md`.

### 3.6 The iOS 27 gate

**Under the iOS 27 SDK the UIScene lifecycle is mandatory. An app with no scene manifest will not
launch** (TN3187). This is a release blocker, not a warning. `UIScreen.main`, `UIWindow(frame:)`,
and the legacy app-delegate callbacks are deprecated on the same timeline.

Schedule the scene-lifecycle task before the SDK bump, not after.

### 3.7 Prerequisites for a whole project

These are read-only: add no key, change no value, delete no key. Read the `Info.plist` and the
build settings from the project file and every `.xcconfig` (the project file wins when two sources
disagree; a key missing from one source proves nothing), then report what you found. Skip them
when the request names files rather than a project, and say nothing about them.

| Check | Satisfied when | Otherwise report |
|---|---|---|
| Launch screen | Any of `UILaunchScreen`, `UILaunchScreens`, `UILaunchStoryboardName`, `UILaunchStoryboards`, or `INFOPLIST_KEY_UILaunchScreen_Generation` is set | No launch screen: iOS 27 rejects the upload with `ITMS-90870` (TN3208). One key is enough; leave an existing storyboard alone |
| iPad orientations | The iPad declaration (`UISupportedInterfaceOrientations~ipad`, else the plain key) lists all four, or the target declares none | Name the omitted orientations; a `supportedInterfaceOrientations` override can still lock the scene, and you did not look for one. iPad only: a portrait-only iPhone is normal |
| Full-screen opt-out | `UIRequiresFullScreen` is absent, or `UIRequiresFullScreenIgnoredStartingWithVersion` is set | iOS 27 ignores `UIRequiresFullScreen` and resizes the scene anyway (TN3192) |

Never delete `UIRequiresFullScreen` (the app becomes resizable at once, before the layouts are
ready) and never add `UIRequiresFullScreenIgnoredStartingWithVersion` (its value picks which
releases keep the old behavior, which is the developer's decision, and 27 or earlier makes the app
fully resizable on iOS 27). The key comes out after the app handles resizing; confirm by running
the app and resizing it.

---

## Boundaries

| Need | Skill |
|---|---|
| SwiftUI view construction, view state, SDK 27 view APIs | `swiftui` |
| Swift language, concurrency, `Sendable` | `swift` |
| Building, running, device verification, SDK 27 tooling gates | `xcode` |
| Authoritative API, availability, and HIG lookup | `apple-docs` |
| Metal and GPU work | `graphics` |
| Keychain, ATS, privacy APIs | `secure-coding` |

## References

`references/_guide.md` first, then the framework table in §2.
UIKit modernization tasks live under `references/uikit/`. App Intents live under
`references/app-intents/` and `references/app-intents-27/`, routed in §2.1.

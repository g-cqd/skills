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

This skill covers which platform API to call and how to migrate onto it. View construction is
`swiftui`, the language is `swift`, and the toolchain is `xcode`.

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

1. **Check the deployment target before recommending an API.** Most of §2 requires iOS 26+.
   Read the target from the project and the symbol's `@available` from the docs, not from
   memory; recognizing an API name is not knowing which OS introduced it.
2. **Verify against the documentation corpus** through `apple-docs` before trusting a curated
   summary here or anything remembered. Where verification was not possible, say so next to the
   claim.
3. When a reference disagrees with observed compiler behaviour, **the primary source wins**: Apple
   docs and SDK headers.
4. **State the version context** for each API you recommend: "available iOS 26+, back-deploys
   to …".

---

## 2. SDK-generation framework adoption

The iOS 26 / macOS 26 generation. For the next generation see `swiftui` (SDK 27 view APIs) and
§3 plus `xcode` (Xcode 27 tooling).

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
| App Intents — best practices and traps | `app-intents-specialist/references/`, routed in §2.1 |
| App Intents — iOS 26 and 27 APIs | `app-intents-whats-new-27/references/`, routed in §2.1 |
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

**Liquid Glass note:** the opt-out is removed in Xcode 27. Report Liquid Glass adoption as
required work for the move to Xcode 27, not as optional polish.

### 2.1 App Intents

The files named `app-intents-specialist/...` and `app-intents-whats-new-27/...` belong to the Xcode skill pack, under `~/.agent-harness/xcode-skills/` (see `xcode`, "Xcode skill pack"). When the pack is not installed, use `apple-docs`.

Apple publishes this guidance and it supersedes prior training. Read the reference for the topic in
play before writing or reviewing code; the files teach the non-obvious traps rather than restate
the framework. For a broad review of a large codebase, scan for the areas (individual intents,
entities, queries, the shortcuts provider), propose one focus area at a time, and split a
whole-codebase review into sections on a task list.

- **Public API only.** Do not emit an underscore-prefixed or no-longer-public symbol, and do not
  invent a type, initializer or parameter to make a snippet compile.
- **Identifiers are a public contract.** Saved shortcuts and donations replay an intent by its
  type name, with `AppEntity.id` values and `AppEnum` raw values as stored parameters, and
  Spotlight depends on the same ids. An `AppShortcut` phrase is a separate contract (spoken
  invocation). Adding one is safe. Renaming, removing or renumbering a shipped one changes
  behaviour, so flag it to the user; do not do it silently.
- **Gate each version-specific API** with its real `@available` floor (every `app-intents-27`
  reference states it) and `if #available`, instead of dropping the feature or misdating it.

Evergreen traps, in `app-intents-specialist/references/`:

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

New in iOS 26 and 27, in `app-intents-whats-new-27/references/` (floors are in each file):

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

Use for UIKit apps (Swift and Objective-C) that must adapt to a window that changes size, support multiple windows, or
move to the scene lifecycle: replacing `UIScreen.main`, layout checks on `interfaceOrientation` or
`userInterfaceIdiom`, hard-coded safe-area insets, and app-delegate lifecycle callbacks.

Follow Apple's procedure in `~/.agent-harness/xcode-skills/app-resizability/SKILL.md` (from the Xcode skill pack; see `xcode`, "Xcode skill pack"): its principles,
its fast path, its workflow, deprecate-and-forward, and the read-only prerequisite checks for a whole project. It
routes each task to a file under `~/.agent-harness/xcode-skills/app-resizability/references/` (`uiscreen-task.md`, `orientation-task.md`,
`scene-lifecycle-task.md`, `safe-area-task.md`, `idiom-task.md`).

Rules of this repository on top of it:

- **Under the iOS 27 SDK the UIScene lifecycle is mandatory: an app with no scene manifest will not launch** (TN3187).
  Report a missing scene manifest as a release blocker, and schedule the scene-lifecycle task before the SDK bump.
- Never delete `UIRequiresFullScreen` and never add `UIRequiresFullScreenIgnoredStartingWithVersion`: the first makes
  the app resizable before its layouts are ready, and the second's value is the developer's decision.
- When the pack is not installed, use `apple-docs` for the same APIs and say so.

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
UIKit modernization tasks live under `app-resizability/references/`. App Intents live under
`app-intents-specialist/references/` and `app-intents-whats-new-27/references/`, routed in §2.1.

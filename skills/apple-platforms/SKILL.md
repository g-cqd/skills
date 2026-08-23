---
name: apple-platforms
description: >
  Apple platforms: adopting platform frameworks and modernizing UIKit apps for
  multi-window. Framework adoption for the iOS 26 / macOS 26 SDK generation —
  Liquid Glass across SwiftUI, UIKit, AppKit and WidgetKit, Swift 6.2 features
  (InlineArray, Span, concurrency updates), Foundation Models and the on-device
  LLM, Visual Intelligence, AppIntents, StoreKit, SwiftData class inheritance,
  AlarmKit, 3D Swift Charts, MapKit GeoToolbox place descriptors,
  AttributedString, WebKit integration, styled text editing, visionOS widgets,
  and accessibility updates. Also covers UIKit modernization in Swift and
  Objective-C: replacing UIScreen.main and UIScreen.mainScreen with
  traitCollection.displayScale and window-derived values, replacing
  interfaceOrientation and userInterfaceOrientation checks with size classes or
  window bounds, migrating AppDelegate to SceneDelegate and the scene lifecycle,
  and handling asymmetric safeAreaInsets and safeAreaLayoutGuide. Use when
  adopting or migrating to any of these APIs, when an app must support resizable
  or multi-window presentation, or when preparing for the iOS 27 SDK where the
  UIScene lifecycle becomes mandatory and an app without a scene manifest will
  not launch. Not for SwiftUI view construction or SDK 27 SwiftUI APIs, which is
  `swiftui`; not for the Swift language itself, which is `swift`; not for
  building or running, which is `xcode`.
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
2. **Verify against the documentation corpus** through `apple-docs` before trusting a curated
   summary here or anything remembered.
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
| AppIntents | `references/AppIntents-Updates.md` |
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

---

## 3. UIKit modernization

Modernize UIKit apps — Swift and Objective-C — for multi-window and resizable presentation by
eliminating legacy shared-state APIs and migrating to the scene lifecycle.

### 3.1 The governing principles

**Closest to the consumer.** Prefer the information nearest the point of use — a view's trait
collection over the window's, the window's over the screen's.

**Always apply a replacement when the target API is present.** A lone TODO is a failure. **An
empty diff on a file containing the target API is also a failure.** Skip only when the API appears
exclusively in dead code (`#if 0`). When two replacements are both valid, pick the one that fits
the request rather than producing nothing. Never silently skip a file — if you will not change it,
say why.

**Do not over-think simple substitutions** (§3.2). Empty diffs on simple files are the single most
common mistake.

**Stay in scope.** Touch only lines containing the active task's target API. No adjacent
deprecation fixes, no whitespace trimming, no reformatting. Out-of-scope edits turn a clean change
into a warning.

**Never replace a dynamic value with a literal.** Replacements stay dynamic.

**Never walk global scene or window state** as a "replacement" — not `UIApplication.shared`, not
`UIDevice.current`, not `UIScreen.main`. If no local object is in reach, add a parameter to the
method and deprecate the old signature.

**Preserve control flow and unrelated defenses.** Verify branching survives every edit — a diff
that collapses `if`/`else` into sequential execution is a critical bug, because both branches then
run unconditionally. Never drop an `else`, `default:`, or `catch` unless asked. Leave
`respondsToSelector:` checks, nil guards, and `@available` checks alone; each exists for its own
reason.

**Extract a repeated replacement** into a named local when the same value is used several times in
one scope.

**Ask before a risky change.** When a replacement could break callers or change observable
behavior — a header signature other modules import, or substituting `width > height` for
orientation where left-versus-right matters — ask first. Fall back to a TODO only when running
non-interactively or the user declines. This never applies to the drop-in replacements in §3.2,
which must simply be applied.

**Honor explicit instructions.** If the user names an attribute, parameter name or position, trait
source, or fallback, use exactly that. Only apply reference-file defaults when the request is
general.

**TODOs must be actionable** — state *why*, *what the replacement would be*, and any lifecycle or
threading concern, on their own line above the code. A vague TODO is worse than none. Do not add
one where an existing `#pragma clang diagnostic ignored` with a bug reference, an existing TODO,
or a deprecation comment already covers the migration.

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

**Phase 1 — detect.** Run detection for **every** task in the registry that applies, not just one.

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
Before finishing, compare the list against your output: **any file with neither a diff nor an
explicit skip reason is a processing failure.** Large files (1000+ lines) and macro-heavy files
are not exempt.

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
| Orientation | `references/uikit/orientation-task.md` | Replace layout-related orientation checks with size classes or window bounds |
| Scene lifecycle | `references/uikit/scene-lifecycle-task.md` | Migrate `AppDelegate` to `SceneDelegate` |
| Safe area | `references/uikit/safe-area-task.md` | Replace hard-coded insets; make existing references handle asymmetric safe areas |

### 3.6 The iOS 27 gate

**Under the iOS 27 SDK the UIScene lifecycle is mandatory. An app with no scene manifest will not
launch** (TN3187). This is a release blocker, not a warning. `UIScreen.main`, `UIWindow(frame:)`,
and the legacy app-delegate callbacks are deprecated on the same timeline.

Schedule the scene-lifecycle task before the SDK bump, not after.

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
UIKit modernization tasks live under `references/uikit/`.

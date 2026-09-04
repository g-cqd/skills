# Naming Conventions

## Naming Rules

| Element | Convention | Example |
|---------|------------|---------|
| Package | `lowercase-with-hyphens` | `swift-networking` |
| Module/Target | `PascalCase` | `Networking` |
| Type/Protocol | `UpperCamelCase` | `NetworkService` |
| Function/Variable | `lowerCamelCase` | `fetchData()` |
| Enum Case | `lowerCamelCase` | `case loading` |
| Internal Symbol | `_LeadingUnderscore` | `_Storage` |

## Verb Semantics

One meaning per verb, one verb family per type.

| Verb | Meaning | Example |
|------|---------|---------|
| `load` | Fetch from network or disk; stores or returns nothing | `loadMenu(for:with:)` |
| `refresh` | Swap a newer value into the owner of the truth, nowhere else | `userSession.refresh(user:)` |
| `update` | Recompute derived state from current inputs | `updateContent()` |
| `resolve` | Decide a value from several sources | `resolveActiveProfile()` |
| `remove` | Delete (not `delete`, not `clear`) | `removeAll()` |
| `store` | Persist, only where a settable property is impossible | `store(accountKey:)` |

Never `sync`. No `get` prefix on a call that returns nothing.

## Property or Method

| Shape | Use | Example |
|-------|-----|---------|
| Side-effect-free, argument-less read | Computed property | `var authToken: AuthToken?` |
| Read/write pair where `nil` removes | Settable property (`nonmutating set` on a struct store) | `pushToken = nil` |
| Needs arguments, has effects, or can fail visibly | Method with a verb from the table above | `store(accountKey:)` |

Booleans are interrogative (`is`, `has`, `can`) and claim only what the type knows.
Argument labels carry the noun; never the noun in both base name and label.
Protocols are plain nouns; implementations carry `Default…` or a descriptive prefix.

## File Naming

| File Type | Pattern | Example |
|-----------|---------|---------|
| Primary type | `TypeName.swift` | `UserService.swift` |
| Extension | `TypeName+ProtocolName.swift` | `User+Codable.swift` |
| Tests | `FeatureNameTests.swift` | `UserServiceTests.swift` |

## Import Organization

Grouped and alphabetized within 4 blocks, separated by blank lines:

```swift
// 1. Standard Library/Frameworks
import Foundation
import SwiftUI

// 2. External Dependencies
import ComposableArchitecture

// 3. Internal Core/Utility Modules
import DesignSystem

// 4. Sibling/Feature Modules
import UserProfile
```

## Formatting

Formatting is the repository formatter's job (`.swiftformat`, `.swiftlint.yml`); follow it, do not
restate it here.

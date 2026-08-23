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

| Rule | Standard |
|------|----------|
| Indentation | 2 spaces |
| Line length | 120 characters maximum |
| Trailing commas | Required in multi-line collections |
| Blank lines | Maximum 1 between declarations |

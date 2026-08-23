# Package Structure

## SPM Layout

```
package-name/
├── .github/workflows/
├── Sources/
│   └── ModuleName/
│       ├── Models/
│       ├── Services/
│       └── Extensions/
├── Tests/
│   └── ModuleNameTests/
├── Benchmarks/
├── Documentation/
└── Package.swift
```

## Package.swift

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
  name: "my-package",
  platforms: [.iOS(.v18), .macOS(.v15)],
  products: [...],
  targets: [...]
)

for target in package.targets {
  target.swiftSettings = [
    .enableExperimentalFeature("StrictConcurrency"),
    .enableUpcomingFeature("MemberImportVisibility"),
  ]
}
```

## Target Environment

| Setting | Standard |
|---------|----------|
| Swift | 6.2+ with Strict Concurrency |
| Platforms | iOS 18+, macOS 15+, visionOS 2+ |
| Xcode | Latest stable release |

## Compiler Flags

| Flag | Purpose |
|------|---------|
| `-warnings-as-errors` | No warnings in production |
| `--explicit-target-dependency-import-check error` | Enforce explicit imports |
| `-require-explicit-sendable` | Explicit Sendable conformance |

## Build Configuration

Always place build artifacts, caches, and transitory directories in `/tmp` to keep the source tree clean.

### SwiftPM (`swift build`)

```bash
swift build --scratch-path /tmp/swiftpm-build/<project-name>
```

`--scratch-path` replaces the default `.build` directory.

### xcodebuild

```bash
xcodebuild build \
  -project "MyProject.xcodeproj" \
  -scheme "MyScheme" \
  -destination "generic/platform=iOS" \
  -derivedDataPath /tmp/xcodebuild-<project-name>/DerivedData \
  -clonedSourcePackagesDirPath /tmp/xcodebuild-<project-name>/checkouts \
  -packageCachePath /tmp/xcodebuild-<project-name>/package-cache \
  CODE_SIGNING_ALLOWED=NO
```

| Flag | Purpose |
|------|---------|
| `-derivedDataPath` | Build products and intermediates (replaces `~/Library/Developer/Xcode/DerivedData`) |
| `-clonedSourcePackagesDirPath` | SPM dependency checkouts |
| `-packageCachePath` | SPM resolved package cache |
| `CODE_SIGNING_ALLOWED=NO` | Skip code signing for CI/local validation builds |

**Never** let xcodebuild write to the default `~/Library/Developer/Xcode/DerivedData` or leave `.build` directories in the source tree.

## Dependency Management

- **SPM only**: All dependencies via Swift Package Manager
- **Vetting required**: Active maintenance, low critical issues, appropriate license (MIT, Apache 2.0)
- **Wrap external APIs**: Isolate third-party types behind internal protocols to enable swapping implementations

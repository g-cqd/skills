# Input Validation

## Rules

| DO (Secure) | DON'T (Insecure) | Severity |
|-------------|------------------|----------|
| Strict allowlist validation | Blocklist or no validation | CRITICAL |
| Parameterized database queries | String concatenation for queries | CRITICAL |
| Validate URL scheme handlers | Process any deep link blindly | HIGH |
| Sanitize WebView content | Inject unsanitized HTML/JS | HIGH |

## Deep Link Validation

```swift
struct DeepLinkValidator {
  private static let allowedHosts = Set(["profile", "settings", "share"])
  private static let allowedParams = Set(["id", "token", "action"])

  static func validate(_ url: URL) -> DeepLinkAction? {
    guard url.scheme == "myapp",
          let host = url.host,
          allowedHosts.contains(host) else {
      return nil
    }

    guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
      return nil
    }

    let params = components.queryItems ?? []
    for item in params {
      guard allowedParams.contains(item.name) else {
        return nil // Reject unknown parameters
      }

      switch item.name {
      case "id":
        guard let value = item.value, UUID(uuidString: value) != nil else {
          return nil
        }
      case "token":
        guard let value = item.value, value.count == 64, value.allSatisfy(\.isHexDigit) else {
          return nil
        }
      default:
        break
      }
    }

    return DeepLinkAction(host: host, params: params)
  }
}
```

## WebView Security

- Validate all messages from JavaScript bridge against strict allowlists
- Set Content Security Policy headers
- Never inject unsanitized user content into `evaluateJavaScript`
- Limit navigation to allowed domains

## Validation Principles

- All external data is hostile until validated
- Use allowlists (not blocklists)
- Validate type, length, format, and range
- Reject unknown parameters rather than ignoring them

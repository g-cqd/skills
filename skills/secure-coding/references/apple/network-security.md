# Network Security

## Rules

| DO (Secure) | DON'T (Insecure) | Severity |
|-------------|------------------|----------|
| Enforce ATS (TLS 1.2+ with forward secrecy) | `NSAllowsArbitraryLoads = YES` | CRITICAL |
| Implement certificate pinning | Trust any valid certificate | HIGH |
| Use `URLSession` with ephemeral configuration for sensitive requests | Cache sensitive responses | HIGH |
| Validate response integrity | Trust response blindly | MEDIUM |

## Certificate Pinning

```swift
final class PinningDelegate: NSObject, URLSessionDelegate, Sendable {
  private let pinnedHashes: Set<String> // SHA256 of SubjectPublicKeyInfo

  init(pinnedHashes: [String]) {
    self.pinnedHashes = Set(pinnedHashes)
    super.init()
  }

  func urlSession(
    _ session: URLSession,
    didReceive challenge: URLAuthenticationChallenge
  ) async -> (URLSession.AuthChallengeDisposition, URLCredential?) {
    guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
          let serverTrust = challenge.protectionSpace.serverTrust,
          let serverCert = SecTrustCopyCertificateChain(serverTrust)?.first else {
      return (.cancelAuthenticationChallenge, nil)
    }

    guard let publicKey = SecCertificateCopyKey(serverCert),
          let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, nil) as Data? else {
      return (.cancelAuthenticationChallenge, nil)
    }

    let hash = SHA256.hash(data: publicKeyData)
    let hashString = hash.compactMap { String(format: "%02x", $0) }.joined()

    if pinnedHashes.contains(hashString) {
      return (.useCredential, URLCredential(trust: serverTrust))
    } else {
      return (.cancelAuthenticationChallenge, nil)
    }
  }
}
```

## ATS Best Practices

- Default ATS enforcement provides TLS 1.2+ with forward secrecy
- Document any exceptions with security justification
- Use `NSExceptionDomains` for specific domains rather than global exceptions
- Ephemeral `URLSession` configuration for sensitive requests prevents caching

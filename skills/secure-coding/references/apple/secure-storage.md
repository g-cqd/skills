# Secure Storage

## Storage Security Rules

| DO (Secure) | DON'T (Insecure) | Severity |
|-------------|------------------|----------|
| Store secrets in Keychain with `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` | Store in `UserDefaults`, plist, hardcoded | CRITICAL |
| Use Secure Enclave for cryptographic keys | Store private keys in files without hardware binding | CRITICAL |
| Use `NSFileProtectionComplete` for sensitive files | Default file protection | HIGH |
| Encrypt SQLite with SQLCipher | Unencrypted database for PII | HIGH |
| Clear sensitive data from memory after use | Leave credentials in memory indefinitely | MEDIUM |

## Keychain with Biometric + Secure Enclave

```swift
func storeSecretWithBiometric(_ secret: Data, account: String) throws {
  var error: Unmanaged<CFError>?

  guard let accessControl = SecAccessControlCreateWithFlags(
    kCFAllocatorDefault,
    kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly,
    [.userPresence, .privateKeyUsage],
    &error
  ) else {
    throw error!.takeRetainedValue() as Error
  }

  let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrAccount as String: account,
    kSecAttrAccessControl as String: accessControl,
    kSecUseAuthenticationContext as String: LAContext(),
    kSecValueData as String: secret
  ]

  // Delete existing item first
  SecItemDelete(query as CFDictionary)

  let status = SecItemAdd(query as CFDictionary, nil)
  guard status == errSecSuccess else {
    throw KeychainError.unableToStore(status)
  }
}
```

## Keychain Accessibility Classes

| Class | When Available | Use For |
|-------|--------------|---------|
| `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` | Unlocked + passcode set | Credentials, tokens (strongest) |
| `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` | Unlocked, no migration | Session keys |
| `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` | After first unlock | Background refresh tokens |

Always use `ThisDeviceOnly` variants to prevent backup extraction.

## iOS Forensic Artifacts

| Artifact | Location | Security Relevance |
|----------|----------|-------------------|
| Keychain | `/private/var/Keychains/` | Credentials, tokens, keys |
| App Data | `/var/mobile/Containers/Data/Application/` | User data, caches, DBs |
| Shared Data | `/var/mobile/Containers/Shared/AppGroup/` | Shared secrets between apps |
| Cookies | `Library/Cookies/` | Session tokens |
| Snapshots | `Library/SplashBoard/Snapshots/` | Screenshot of last state |
| Pasteboard | System-wide | Copied sensitive data |
| Keyboard | `Library/Keyboard/` | Autocomplete cache |

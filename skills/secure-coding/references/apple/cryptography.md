# Cryptography

## Rules

| DO (Secure) | DON'T (Insecure) | Severity |
|-------------|------------------|----------|
| Use CryptoKit (AES-GCM, ChaCha20-Poly1305) | CommonCrypto ECB mode, DES, 3DES | CRITICAL |
| Generate keys with Secure Enclave | Store private keys in filesystem | CRITICAL |
| Use HKDF for key derivation | MD5/SHA1 for key derivation | HIGH |
| Unique nonce per encryption operation | Reuse nonces with same key | CRITICAL |

## Authenticated Encryption

```swift
import CryptoKit

func encrypt(_ plaintext: Data, using key: SymmetricKey) throws -> Data {
  // CryptoKit generates unique nonce automatically
  let sealedBox = try AES.GCM.seal(plaintext, using: key)
  guard let combined = sealedBox.combined else {
    throw CryptoError.encryptionFailed
  }
  return combined
}

func decrypt(_ ciphertext: Data, using key: SymmetricKey) throws -> Data {
  let sealedBox = try AES.GCM.SealedBox(combined: ciphertext)
  return try AES.GCM.open(sealedBox, using: key)
}
```

## Secure Enclave Key Generation

```swift
func generateSecureEnclaveKey(tag: String) throws -> SecKey {
  guard SecureEnclave.isAvailable else {
    throw SecurityError.secureEnclaveUnavailable
  }

  var error: Unmanaged<CFError>?
  guard let access = SecAccessControlCreateWithFlags(
    kCFAllocatorDefault,
    kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
    [.privateKeyUsage],
    &error
  ) else {
    throw error!.takeRetainedValue() as Error
  }

  let attributes: [String: Any] = [
    kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
    kSecAttrKeySizeInBits as String: 256,
    kSecAttrTokenID as String: kSecAttrTokenIDSecureEnclave,
    kSecPrivateKeyAttrs as String: [
      kSecAttrIsPermanent as String: true,
      kSecAttrApplicationTag as String: tag.data(using: .utf8)!,
      kSecAttrAccessControl as String: access
    ]
  ]

  guard let privateKey = SecKeyCreateRandomKey(attributes as CFDictionary, &error) else {
    throw error!.takeRetainedValue() as Error
  }
  return privateKey
}
```

## Key Management Best Practices

- Generate symmetric keys with `SymmetricKey(size: .bits256)`
- Derive keys with `HKDF<SHA256>.deriveKey()`
- Never hardcode keys in source code
- Rotate keys on a regular schedule
- Use AEAD ciphers (AES-GCM, ChaCha20-Poly1305) — never unauthenticated encryption

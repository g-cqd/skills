# Apple Platform Security — Domain Guide

Threat modeling, secure coding, and security reviews on Apple platforms (iOS, macOS, watchOS, tvOS, visionOS).

## Security Priority Hierarchy

1. **Data Confidentiality** — Secrets, PII, keys never leak
2. **Data Integrity** — Tamper-evident, cryptographically verified
3. **Authentication** — Identity verified, sessions secure
4. **Authorization** — Access controls enforced at every layer
5. **Availability** — Graceful degradation, no DoS vectors
6. **Non-Repudiation** — Actions attributable, audit trails
7. **Privacy** — Minimal data collection, consent respected
8. **Compliance** — Regulatory requirements met

## Triage Playbook

| Issue | Reference |
|-------|-----------|
| Threat model / STRIDE analysis | `threat-modeling.md` |
| Storing secrets, Keychain, Secure Enclave | `secure-storage.md` |
| Encryption, CryptoKit, key management | `cryptography.md` |
| ATS, cert pinning, TLS, network | `network-security.md` |
| Deep links, URL schemes, WebView | `input-validation.md` |
| Security code review, audit | `code-review.md` |
| Jailbreak detection, integrity | `integrity-checks.md` |

## Pre-Review Analysis

1. **Assets**: What are we protecting?
2. **Attack Surface**: All entry points (network, URL schemes, IPC, user input, WebView, clipboard, backup)
3. **Threat Level**: Opportunistic → Sophisticated → Advanced
4. **STRIDE**: Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege

## Review Checklist

### Critical
- [ ] No hardcoded secrets in source
- [ ] Keychain uses strongest accessibility class + access control
- [ ] Certificate pinning on sensitive endpoints
- [ ] All external input validated with strict allowlists
- [ ] CryptoKit used correctly (no nonce reuse, AEAD ciphers)
- [ ] No ATS exceptions without justification

### High
- [ ] Sensitive files use `NSFileProtectionComplete`
- [ ] Sensitive data zeroed after use
- [ ] Deep links fully validated
- [ ] No PII/secrets in logs
- [ ] WebView JavaScript bridge secured

### Medium
- [ ] Clipboard protection for sensitive data
- [ ] Screenshot protection on sensitive views
- [ ] Jailbreak awareness implemented
- [ ] Debug endpoints disabled in release

## Guiding Principles

1. "How would I break this?" before "How do I build this?"
2. Defense in depth — never rely on single control
3. Minimal entitlements, minimal permissions
4. When in doubt, deny access and fail closed
5. All external data is hostile until validated
6. Log security events, never log secrets

## Detailed References
- `threat-modeling.md` — STRIDE analysis, attacker profiles
- `secure-storage.md` — Keychain, Secure Enclave, file protection
- `cryptography.md` — CryptoKit patterns, key generation
- `network-security.md` — ATS, cert pinning, TLS
- `input-validation.md` — Deep link validation, WebView hardening
- `code-review.md` — Review checklists, analysis methodology
- `integrity-checks.md` — Jailbreak detection, dylib checks

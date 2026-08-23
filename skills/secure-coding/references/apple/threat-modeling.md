# Threat Modeling

## STRIDE Analysis

| Category | Threat | Example Mitigation |
|----------|--------|-------------------|
| **Spoofing** | Attacker impersonates server via MITM | Certificate pinning, mutual TLS |
| **Tampering** | Binary modification, runtime hooking | Code signing validation, integrity checks |
| **Repudiation** | User denies performing action | Secure audit logging with cryptographic timestamps |
| **Information Disclosure** | Keychain extraction on jailbroken device | `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` + biometric |
| **Denial of Service** | Resource exhaustion via malformed input | Input validation, rate limiting, timeouts |
| **Elevation of Privilege** | Sandbox escape via IOKit vulnerability | Minimal entitlements, sandboxed helpers |

## Attacker Profiles

| Level | Capabilities | Examples |
|-------|-------------|---------|
| **Opportunistic** | Automated scanners, known CVEs | Script kiddies, bot nets |
| **Sophisticated** | Frida hooking, dynamic analysis, MITM | Targeted attacks, pentesters |
| **Advanced** | Custom exploits, hardware attacks, zero-days | Nation-state, dedicated researchers |

## Attack Surface Inventory

When analyzing an app, enumerate all entry points:

| Vector | Risk | Description |
|--------|------|-------------|
| Network API | HIGH | REST/GraphQL endpoints |
| URL Schemes | MEDIUM | Deep links, universal links |
| IPC/XPC | HIGH | Inter-process communication |
| User Input | HIGH | Text fields, file uploads |
| WebView Bridge | HIGH | JavaScript ↔ Native |
| Clipboard | MEDIUM | Sensitive data exposure |
| Backup | HIGH | iTunes/iCloud backup extraction |
| Push Notifications | LOW | Payload handling |

## Security Analysis Template

Before security-sensitive work, assess:

1. **Assets**: List what you're protecting and sensitivity level (CRITICAL/HIGH/MEDIUM/LOW)
2. **Attack Surface**: Enumerate all entry points from the table above
3. **STRIDE**: Walk through each category for your specific feature
4. **Attacker Profile**: Which level are you defending against?
5. **Security Requirements**: List requirements with priority levels

## Apple Platform Vulnerability Classes

| Vulnerability | CWE | Apple-Specific Examples |
|--------------|-----|------------------------|
| Memory Corruption | CWE-119 | IOKit drivers, ImageIO, FontParser |
| Sandbox Escape | CWE-265 | Mach port leaks, IPC abuse, XPC flaws |
| Insecure Data Storage | CWE-312 | UserDefaults, plist, unprotected SQLite |
| Keychain Misuse | CWE-522 | Wrong accessibility, no access control |
| Insecure Communication | CWE-319 | ATS disabled, no cert validation |
| URL Scheme Hijacking | CWE-939 | Unvalidated deep links, OAuth redirect |
| Deserialization | CWE-502 | NSKeyedUnarchiver, Codable with Any |
| Path Traversal | CWE-22 | File provider abuse, symlink attacks |
| Race Conditions | CWE-362 | TOCTOU in XPC services, file operations |
| Injection | CWE-94 | JS bridge, NSPredicate, format strings |
| Cryptographic Failures | CWE-327 | ECB mode, MD5/SHA1, hardcoded keys |

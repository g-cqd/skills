# Security Code Review

## Review Checklists by Severity

### Critical (Must Fix)
- [ ] No hardcoded secrets (API keys, passwords, encryption keys) in source
- [ ] Keychain uses strongest accessibility class + access control
- [ ] Certificate pinning implemented for sensitive API endpoints
- [ ] All external data validated with strict allowlists
- [ ] CryptoKit/Security.framework used correctly
- [ ] No ATS exceptions without documented justification

### High (Should Fix)
- [ ] Sensitive files use `NSFileProtectionComplete`
- [ ] Sensitive data zeroed after use
- [ ] URL scheme handlers fully validated
- [ ] No PII/secrets in NSLog, print, os_log
- [ ] WebView JavaScript bridge secured
- [ ] Sensitive files excluded from backup

### Medium (Fix When Possible)
- [ ] Clipboard protection for sensitive data
- [ ] Screenshot protection on sensitive views
- [ ] Jailbreak awareness with appropriate behavior
- [ ] Debug endpoints disabled in release
- [ ] Binary protections enabled (PIE, stack canaries, ARC)

### Low (Best Practice)
- [ ] Dependencies audited and updated
- [ ] Entitlements minimal (only required capabilities)
- [ ] Privacy manifest for Required Reason APIs (iOS 17+)

## Static Analysis Methodology

1. **Binary Analysis** (Hopper/IDA/Ghidra/jtool2)
   - Check for stripped symbols
   - Identify encryption methods
   - Find hardcoded secrets/API keys
   - Analyze entitlements (`codesign -d --entitlements -`)
   - Review Info.plist (URL schemes, ATS, background modes)

2. **Source Code Review**
   - Grep for insecure patterns:
     - `UserDefaults` (sensitive data storage)
     - `NSLog`/`print`/`os_log` (data leakage)
     - `NSAllowsArbitraryLoads`
     - `kSecAttrAccessibleAlways`
     - `evaluateJavaScript` (injection)
   - Trace data flow from entry points
   - Review all crypto implementations

## Dynamic Analysis Methodology

1. **Runtime Instrumentation** (Frida/Objection)
   - Hook Keychain APIs (SecItemAdd, SecItemCopyMatching)
   - Trace crypto operations (CCCrypt, SecKey*)
   - Monitor file system access
   - Intercept network calls

2. **Network Analysis** (Burp/Charles/mitmproxy)
   - SSL pinning bypass testing
   - API endpoint enumeration
   - Authentication flow analysis
   - Token/session handling

3. **Filesystem Inspection**
   - App container contents
   - Keychain dump verification
   - SQLite database encryption check
   - Cache and temp files

## Post-Implementation Verification

- [ ] Run Semgrep/CodeQL with iOS security rules
- [ ] Entitlement review: `codesign -d --entitlements -`
- [ ] Dependency scan: OWASP Dependency-Check
- [ ] OWASP Mobile Top 10 coverage
- [ ] OWASP MASTG test cases

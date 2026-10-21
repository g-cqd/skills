---
name: secure-coding
description: >-
  Language-agnostic security review, with Apple Keychain, CryptoKit, ATS, and mobile
  hardening. Use for trust boundaries, untrusted input, authentication, secrets,
  injection, SSRF, dependencies, or iOS pentest review including deep links and WKWebView.
  For build settings and entitlements, use `xcode`; for memory corruption and ownership,
  use `memory-safety`.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Secure Coding

This skill decides **whether an attacker can make the code do something it must not do**. Memory
validity belongs to `memory-safety`. Build configuration belongs to `xcode`.

Sections 1–7 are language-agnostic. Section 8 is Apple-specific.

## Contract

```
§IRON-LAW ∀external-input ∷ hostile-until-validated
          ∅secret ∈ source | logs | error-messages | telemetry
§BOUNDARY canonicalize → validate ⇒ ¬validate-then-canonicalize
§ALLOWLIST allowlist ≻ denylist ∀validation
§FAIL     fail-closed ∀security-path ⇒ ¬fail-open
§DEPTH    ¬single-control between attacker ∧ asset
§ERRORS   precise-internally · generic-externally
§BAN      homegrown-crypto · string-built SQL|shell|eval ·
          deserialize-untrusted · swallow-error ∈ security-path ·
          log-secret|PII · unsigned-update
```

---

## 1. Threat frame — do this before reading code

1. **Assets** — list what is worth stealing or corrupting: credentials, PII, tokens,
   money-moving operations, the ability to act as another user.
2. **Trust boundaries** — list where external data enters: HTTP, files, IPC, environment
   variables, database content, third-party APIs, and **LLM output**. Treat LLM output as
   untrusted input.
3. **Abuse cases** — for each entry point, write what an attacker would send, not what a user
   would send.

This is a defensive review of code the user owns or is authorized to review. The goal is to find
vulnerabilities in the source; each finding needs an exploitation scenario (§5).

---

## 2. OWASP Top 10:2025

| # | Risk | Check for |
|---|---|---|
| A01 | Broken Access Control (incl. SSRF) | Authorization enforced **server-side** on every object and function access; no IDOR; outbound fetches of user-supplied URLs validated against an allowlist |
| A02 | Security Misconfiguration | Safe defaults; debug off in production; minimal surface; CSP and HSTS headers |
| A03 | Software Supply Chain Failures | Pinned dependencies, lockfiles, provenance and signature checks, minimal deps, no abandoned packages |
| A04 | Cryptographic Failures | Modern AEAD (AES-GCM, ChaCha20-Poly1305); no MD5 or SHA-1 for security; no ECB; no homegrown crypto; unique nonces; TLS everywhere |
| A05 | Injection | Parameterized queries; never string-built SQL, shell, or `eval`; output encoding for XSS |
| A06 | Insecure Design | Threat-model security-relevant features before coding; fail secure |
| A07 | Authentication Failures | Rate limiting, MFA support, no credential leakage through errors or timing, secure session lifecycle, CSRF protection |
| A08 | Software & Data Integrity Failures | No unsigned or unverified updates; never deserialize untrusted data |
| A09 | Logging & Alerting Failures | Security events logged **without** secrets or PII; tamper-evident; actionable |
| A10 | Mishandling of Exceptional Conditions | No swallowed errors on security paths; no fail-open; resource cleanup on error paths |

**CWE Top 25 (2025) leaders**: XSS is #1, SQL injection #2, CSRF #3. Check these classes first.

---

## 3. Rules for every language

- **Validate each input that crosses a trust boundary, at that boundary, against an allowlist.**
  Canonicalize paths, URLs and Unicode *before* validating (§BOUNDARY); validating a
  non-canonical form lets path traversal and homograph attacks through.
- **Secrets** come from a secret manager, keystore, or deploy-time environment, not from source
  control. Before approving a change, grep the changed files for high-entropy literals.
- **Least privilege** — grant the narrowest scopes, capabilities, file permissions, and database
  grants that the feature needs.
- **Defense in depth** — §DEPTH.
- **Errors** — §ERRORS. Do not send stack traces or internal paths to users.
- **A new dependency is a supply-chain decision.** Check maintenance status, transitive surface,
  the updated lockfile, and the license.

---

## 4. Rationalizations that precede incidents

| If you think… | Reality |
|---|---|
| "It's internal, nobody malicious can reach it" | Internal services get compromised; SSRF reaches "internal" |
| "We'll sanitize later" | Later never comes. The boundary is now |
| "This input comes from our own frontend" | Attackers do not use your frontend |
| "Logging it helps debugging" | Logs leak. Mask secrets and PII now |

When one of these thoughts is the reason to skip a check, in review or in your own code, do the
check.

---

## 5. Reporting

Report each finding as: **vulnerability class + CWE ID**, location, **exploitation scenario**,
concrete fix, and severity (Critical / High / Medium / Low). Sort by severity.

Trace the data path from the trust boundary to the sink before you call something a
vulnerability. A pattern name (`eval`, string concatenation, `NSAllowsArbitraryLoads`) is a reason
to look, not a finding. If you cannot describe how the pattern is exploited, report it as a
hardening note, not a vulnerability.

<example>
**High — CWE-89 SQL Injection** · `Repositories/UserStore.swift:42`
`query = "SELECT * FROM users WHERE name = '" + name + "'"` — `name` arrives from the search
field via `SearchViewModel.submit` with no validation. Scenario: `' OR 1=1 --` returns every row;
`'; DROP TABLE users; --` is blocked only by the driver's multi-statement setting. Fix: bind the
value with `sqlite3_bind_text` / a parameterized query; keep the allowlist on `name` as defense in
depth.
<rationale>The finding names the class and CWE, the exact sink, the traced source, a concrete
payload with its effect, and a root-cause fix. A reader can verify each claim against the
code.</rationale>
</example>

Before finishing, re-read each finding and confirm it has an exploitation path. When the project
declares an ASVS 5.0 level, map findings to it: L1 baseline, L2 standard, L3 high-assurance.

---

## 6. Cryptography

- Use a vetted library. **Do not implement a primitive.**
- Use the library's AEAD construction. Flag code that combines a raw block cipher with a non-AEAD
  mode (CBC, CTR, ECB) instead of calling an AEAD API.
- **Nonce reuse breaks AES-GCM completely**: it leaks the authentication key, not only one
  message. Derive nonces so that reuse cannot happen by construction.
- Generate keys with a CSPRNG, derive them with a KDF, or keep them in a hardware keystore. Do not
  use a password directly as a key, and do not use a constant.
- Do not use MD5 or SHA-1 for anything security-relevant. Do not use ECB in any case.
- Compare secrets in constant time.

---

## 7. Review workflow

1. Frame the threat (§1): assets, boundaries, abuse cases.
2. List the entry points in the review scope. Each trust-boundary crossing is a review site.
3. For each site, check: canonicalized, validated against an allowlist, authorized server-side.
4. Grep the review scope for secrets, `eval`, string-built queries, deserialization, and disabled
   TLS verification.
5. Check the error and cleanup paths: fail-closed, no swallowed exceptions.
6. Review the dependencies that the change adds.
7. Report per §5.

The review is done when each site from step 2 has been checked and each grep from step 4 has been
run.

---

## 8. Apple platforms

Sections 1–7 apply. This section is a **defensive reading of the iOS pentest surface**: each
control below is stated so that its absence is the finding. Build-setting hardening (Enhanced
Security, PAC/MTE, bounds-safety flags) belongs to `xcode`. The full attack-surface catalog, with
the offensive technique each control defeats, is `references/apple/ios-attack-surface.md`.

### 8.1 Storage — secrets at rest

Assume the attacker owns the device: physical access, a jailbreak, and a backup. Assume everything
the app writes can be read.

- **The Keychain accessibility class is the highest-impact decision, and the default is too
  permissive.** Bind device- or biometry-scoped secrets with
  `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` plus a `SecAccessControl` created with
  `.biometryCurrentSet`. The `…ThisDeviceOnly` variants stop the item from migrating through a
  backup or device-to-device transfer. Choose `WhenUnlocked` over `Always`. A "device-only"
  secret that survives a restore is a finding.
- **NSFileProtection class.** A file left at `NSFileProtectionNone`, or at
  `…CompleteUntilFirstUserAuthentication` (unlocked once after boot, then stays readable), can be
  read from a locked or imaged device. Use `NSFileProtectionComplete` where the app does not need
  the data while in the background. Audit the **App Group container** as well as the app
  container.
- **No secrets in the unencrypted stores.** `UserDefaults`/plist
  (`Library/Preferences/<bundleID>.plist`), Core Data, Realm, YapDatabase, and app SQLite are
  plaintext by default. **Core Data and Realm do not encrypt** unless configured to. Cookies
  (`Library/Cookies/*.binarycookies`) and `NSURLCredential` persistence survive backup. Put
  credentials in the Keychain, not on disk.
- **`Cache.db` leaks tokens.** `NSURLSession` caches request and response bodies, including
  `Authorization` headers and tokens. For authenticated traffic, use a `.ephemeral` session, or
  call `URLCache.shared.removeAllCachedResponses()` on logout, or set the cache policy to
  `.notAllowed`.

### 8.2 UI-surface leakage

Check these three leaks in every iOS review:

- **Backgrounding snapshots.** iOS saves an image of the current screen into
  `Library/Caches/Snapshots/` for the app switcher; the image persists across reboot. Overlay a
  blank or branded view in `applicationDidEnterBackground` (or the scene equivalent) so that no
  sensitive screen is captured.
- **Keyboard cache.** Autocorrect stores typed text in `Library/Keyboard/*-dynamic-text.dat`. On
  each sensitive field, set `autocorrectionType = .no`. Set `secureTextEntry = true` only on secrets (passwords, PINs,
  tokens); a field the user must read back, such as an account number, stays unmasked.
- **The general pasteboard is readable by every app.** Any app can poll `UIPasteboard.general` via
  `changeCount`. Keep secrets off the general pasteboard. Where the feature requires a copy, set an
  expiry and `localOnly` in `setItems:options:`.

### 8.3 Local authentication — a Boolean is not authorization

The most exploited iOS design error: gating a sensitive action on the **return value** of
`LAContext.evaluatePolicy`. The call returns a `Bool`, and a one-line Frida/Objection hook sets
the callback to `true` regardless of the real result.

- **Bind the secret; do not check the flag.** Store what the gate protects as a **Keychain item
  under `SecAccessControl`**, so the data cannot be decrypted without a real biometric or passcode
  unlock. A hooked `evaluatePolicy` then yields nothing, because the OS releases the item, not the
  app's `if`.
- **Use `.biometryCurrentSet`, not `.biometryAny`**, so that adding a fingerprint or re-enrolling
  Face ID invalidates the item. With `.biometryAny`, an attacker who enrolls a new biometric keeps
  access.
- **Flag `LAContext` reuse** and a nonzero `touchIDAuthenticationAllowableReuseDuration`: they let
  an action succeed on a *recent* unlock with no new prompt. Accept them only where a code comment
  or the user states that this is intended.

### 8.4 IPC — input from other apps

- **Custom URL schemes are unauthenticated, spoofable input.** Any app can send them, and any app
  can register the *same* scheme to intercept your inbound data. Validate each URL and discard
  malformed ones. Do not let a scheme trigger a privileged action without user confirmation. For
  auth/SSO callbacks, use **claimed `https` Universal Links**, not a custom scheme, which can be
  hijacked. Review both handlers: `application:open:options:` and, for scene apps,
  `scene:openURLContexts:`.
- **Universal Links / AASA.** Audit `apple-app-site-association` `paths`/`components` for
  wildcards and for unpublished or sensitive routes. Routes that match but are not defined must
  return 404. Do not over-trust wildcard subdomains. On iOS 14+ a CDN caches the association, so
  verify the on-device state, not only the origin file.
- **App extensions.** List each `.appex` in the app bundle, inspect its
  `NSExtensionActivationRule`, and map which App Group each extension can reach. The shared
  container is a trust boundary between the extension and the host app.
- **Insecure unarchiving.** `NSKeyedUnarchiver` decoding attacker-supplied data without secure
  coding is object injection. Use `requiringSecureCoding` / `decodeObjectOfClass:` with a concrete
  expected class.

### 8.5 WebViews — the JS bridge is a trust boundary

- **Use `WKWebView`, not `UIWebView`** (`UIWebView` cannot disable JavaScript). Disable JavaScript
  where content is static (`preferences.javaScriptEnabled = false`), require
  `hasOnlySecureContent`, and keep `allowFileAccessFromFileURLs` and
  `allowUniversalAccessFromFileURLs` **false**. With either one true, a `file://` XHR from injected
  script can read the whole container and send it out.
- **A JS→native bridge turns any XSS or untrusted iframe into native-code execution.**
  `WKScriptMessageHandler` / `postMessage`, `JSExport`, and `JSContext` all cross the boundary.
  Before a handler touches tokens, filesystem paths, deep-link targets, or app state, **validate
  `message.frameInfo.securityOrigin`** and reject unexpected subframes. Isolate bridges with
  `WKContentWorld`. Pass user-controlled data to the page through the message bridge as data. Do
  not interpolate it into an `evaluateJavaScript` string; that is script injection.
- **Use `WKAppBoundDomains`** + `limitsNavigationsToAppBoundDomains` for each privileged bridge.
- **`isInspectable` must be false in production builds.** iOS 16.4+ defaults it to false, but code
  can set it. When true, it exposes the WebView and `JSContext` to Safari's inspector on a paired
  Mac.

### 8.6 Network

- **App Transport Security stays on.** Review `NSAppTransportSecurity` for
  `NSAllowsArbitraryLoads`, `NSAllowsArbitraryLoadsInWebContent`, `NSAllowsLocalNetworking`,
  per-domain `NSExceptionDomains`, and the legacy `NSTemporaryException*` keys. A blanket
  `NSAllowsArbitraryLoads` is a finding. **Lower-level sockets, IP literals, and `.local` hosts
  bypass ATS completely**; review those flows separately.
- **Check the hostname as well as the chain.** Code that checks that a CA signed the certificate
  but not that the hostname matches is open to MitM: a proxy certificate for any hostname then
  works.
- **Certificate pinning** where the threat model requires it, with a key-rotation plan. Pin in
  code that a runtime hook of the system trust APIs cannot bypass.
- **Do not add a relaxed trust policy unless the user asks for one.** Allow a relaxed policy,
  existing or requested, only in a debug build behind a compile-time flag that release builds
  cannot carry. Report a relaxed policy that a release build can reach as a finding.

### 8.7 Crypto

- Use CryptoKit for hashing, AEAD, key agreement, and signatures. Use it instead of CommonCrypto
  in new code.
- **Flag RC4, MD4, MD5, and SHA-1** when used for authorization or to protect stored or
  transmitted data.
- Hash passwords with a **unique salt and an expensive KDF**, not a fast general-purpose digest.
- **No hardcoded or predictable keys.** Reversing the binary reveals them.

### 8.8 Logs, memory, and integrity

- **No secrets through `NSLog`, unified logging, or crash artifacts.** Logs persist after
  uninstall and can be read with physical access. Audit logging after login, token refresh,
  deep-link handling, and WebView activity, because the app holds secrets at those moments.
- **Jailbreak and integrity checks only add cost for the attacker.** Do not make one the only
  protection for an asset.
- **Untrusted media is the zero-click entry point.** Image and audio parsers that receive attacker
  data are the main remote-compromise surface (see the parser-chain and exploit case studies in
  the reference). Code that parses untrusted bytes must be bounds-safe (`memory-safety`) and must
  run with the hardened-runtime mitigations that `xcode` §7 enables.

---

## Boundaries

| Need | Skill |
|---|---|
| Xcode hardening settings, Enhanced Security, entitlements | `xcode` |
| Memory-corruption classes, sanitizers, ownership, `-fbounds-safety` | `memory-safety` |
| Security-audit execution contract | `planner` |
| General review workflow and severity calibration | `code-review` |
| Primary-source Apple security documentation | `apple-docs` |
| Language-level safety — typed errors, value types | `swift` |
| Dependency policy and update discipline | `engineering-practices` |

## References

Apple-specific, supporting §8: `references/apple/_guide.md`,
`references/apple/threat-modeling.md` (STRIDE, attacker profiles),
`references/apple/secure-storage.md` (Keychain, Secure Enclave, file protection),
`references/apple/cryptography.md` (CryptoKit, key generation),
`references/apple/network-security.md` (ATS, pinning, TLS),
`references/apple/input-validation.md` (deep links, WebView),
`references/apple/integrity-checks.md`, `references/apple/code-review.md` (checklists,
methodology).

`references/apple/ios-attack-surface.md` — the full iOS mobile-pentest surface as a defensive
control catalog (storage, UI leakage, local auth, IPC, WebViews, network, crypto, logs, memory),
each control paired with the offensive technique it defeats. Use it as a review checklist; a
missing control is the finding.

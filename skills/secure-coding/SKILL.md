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

This skill owns **whether an attacker can make the code do something it should not**. It does not
own memory validity (`memory-safety`) or build configuration (`xcode`).

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

1. **Assets** — what is worth stealing or corrupting here? Credentials, PII, tokens,
   money-moving operations, the ability to act as someone else.
2. **Trust boundaries** — where does external data enter? HTTP, files, IPC, environment
   variables, database content, third-party APIs, and **LLM output**, which is untrusted input
   like any other.
3. **Abuse cases** — for every entry point, ask what an attacker would send, not what a user
   would.

Reviewing without this frame finds typos, not vulnerabilities.

This is a defensive review of code the user owns or is authorized to review: finding
vulnerabilities in the source is the point, and each finding states a concrete exploitation
scenario so the fix can be judged against a real attack rather than a pattern name.

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

**CWE Top 25 (2025) leaders**: XSS is #1, SQL injection #2, CSRF #3. Weight review attention
accordingly.

---

## 3. Non-negotiables, any language

- **Validate with allowlists at the boundary. Canonicalize *before* validating** — paths, URLs,
  Unicode. Validating a non-canonical form is how path traversal and homograph attacks get
  through.
- **Secrets** come from a secret manager, keystore, or deploy-time environment — never source
  control. Grep for high-entropy literals before approving anything.
- **Least privilege** — narrowest scopes, capabilities, file permissions, and database grants.
- **Defense in depth** — never a single control between an attacker and an asset.
- **Errors**: precise internally, generic externally. No stack traces or internal paths to users.
- **A new dependency is a supply-chain decision** — maintenance status, transitive surface,
  lockfile updated, license checked.

---

## 4. Rationalizations that precede incidents

| If you think… | Reality |
|---|---|
| "It's internal, nobody malicious can reach it" | Internal services get compromised; SSRF reaches "internal" |
| "We'll sanitize later" | Later never comes. The boundary is now |
| "This input comes from our own frontend" | Attackers do not use your frontend |
| "Logging it helps debugging" | Logs leak. Mask secrets and PII now |

Treat each of these as a stop sign in review, including when you are the one thinking it.

---

## 5. Reporting

Report each finding as: **vulnerability class + CWE ID**, location, **exploitation scenario**,
concrete fix, and severity (Critical / High / Medium / Low). Sort by severity.

The exploitation scenario is what distinguishes a finding from a style note. Trace the actual
data path from the trust boundary to the sink before asserting a vulnerability; a pattern name
(`eval`, string concatenation, `NSAllowsArbitraryLoads`) is a reason to look, not a finding. If
you cannot describe how it is exploited, report it as a hardening note, not a vulnerability.

<example>
**High — CWE-89 SQL Injection** · `Repositories/UserStore.swift:42`
`query = "SELECT * FROM users WHERE name = '" + name + "'"` — `name` arrives from the search
field via `SearchViewModel.submit` with no validation. Scenario: `' OR 1=1 --` returns every row;
`'; DROP TABLE users; --` is blocked only by the driver's multi-statement setting. Fix: bind the
value with `sqlite3_bind_text` / a parameterized query; keep the allowlist on `name` as defense in
depth.
<rationale>The finding names the class and CWE, the exact sink, the traced source, a concrete
payload with its effect, and a root-cause fix — a reader can verify each claim against the
code.</rationale>
</example>

Before finishing, re-read each finding and confirm it has an exploitation path. When the project
declares an ASVS 5.0 level, map findings to it — L1 baseline, L2 standard, L3 high-assurance.

---

## 6. Cryptography

- Use a vetted library. **Never implement a primitive.**
- Prefer AEAD constructions. If you are choosing a mode, you are probably at the wrong level of
  abstraction.
- **Nonce reuse breaks AES-GCM catastrophically** — it leaks the authentication key, not just one
  message. Derive nonces so reuse is structurally impossible.
- Keys come from a KDF or a hardware keystore, never from a password directly and never from a
  constant.
- Do not use MD5 or SHA-1 for anything security-relevant. Do not use ECB, ever.
- Compare secrets in constant time.

---

## 7. Review workflow

1. Frame the threat (§1) — assets, boundaries, abuse cases.
2. Inventory the entry points. Every boundary crossing is a review site.
3. Walk each one: canonicalized, validated against an allowlist, authorized server-side?
4. Grep for secrets, `eval`, string-built queries, deserialization, and disabled TLS verification.
5. Check the error and cleanup paths — fail-closed, no swallowed exceptions.
6. Review dependencies added by the change.
7. Report per §5.

---

## 8. Apple platforms

Everything above applies. This section is a **defensive reading of the iOS pentest surface**:
each control below is stated as the thing whose absence is the finding. Build-setting hardening —
Enhanced Security, PAC/MTE, bounds-safety flags — is `xcode`. The full attack-surface catalog,
with the offensive technique each control defeats, is
`references/apple/ios-attack-surface.md`.

### 8.1 Storage — secrets at rest

The device is the attacker's: assume physical access, a jailbreak, and a backup. Everything the
app writes is inspectable.

- **Keychain accessibility class is the highest-leverage decision, and the default is too
  permissive.** Bind device- or biometry-scoped secrets with
  `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` plus a `SecAccessControl` created with
  `.biometryCurrentSet`. The `…ThisDeviceOnly` variants stop the item migrating through a backup
  or device-to-device transfer; `WhenUnlocked` over `Always`. An over-permissive class is the most
  common Keychain finding, and a "device-only" secret that survives restore is a real one.
- **NSFileProtection class.** A file left `NSFileProtectionNone` — or
  `…CompleteUntilFirstUserAuthentication`, which unlocks once after boot and stays readable — is
  readable off a locked or imaged device. Prefer `NSFileProtectionComplete` where the data is not
  needed while backgrounded. Audit the **App Group container** too, not just the app container.
- **No secrets in the unencrypted stores.** `UserDefaults`/plist
  (`Library/Preferences/<bundleID>.plist`), Core Data, Realm, YapDatabase, and app SQLite are all
  plaintext by default — **Core Data and Realm do not encrypt** unless you configure it. Cookies
  (`Library/Cookies/*.binarycookies`) and `NSURLCredential` persistence survive backup; put
  credentials in the Keychain, not on disk.
- **`Cache.db` leaks tokens.** `NSURLSession` caches request and response bodies, including
  `Authorization` headers and tokens. Use a `.ephemeral` session for authenticated traffic, or
  call `URLCache.shared.removeAllCachedResponses()` on logout, or set the cache policy to
  `.notAllowed`.

### 8.2 UI-surface leakage

Three leaks that look like nothing and show up in every serious review:

- **Backgrounding snapshots.** iOS photographs the current screen into
  `Library/Caches/Snapshots/` for the app switcher; it persists across reboot. Overlay a blank or
  branded view in `applicationDidEnterBackground` (or the scene equivalent) so a sensitive screen
  is never captured.
- **Keyboard cache.** Typed text lands in `Library/Keyboard/*-dynamic-text.dat` via autocorrect.
  On any sensitive field set `autocorrectionType = .no` and `secureTextEntry = true`.
- **General pasteboard is world-readable.** Any app can poll `UIPasteboard.general` via
  `changeCount`. Keep secrets off it; where you must copy, set an expiry and `localOnly` in
  `setItems:options:`.

### 8.3 Local authentication — a Boolean is not authorization

The single most exploited iOS design error: gating a sensitive action on the **return value** of
`LAContext.evaluatePolicy`. It returns a `Bool`, and a one-line Frida/Objection hook flips that
callback to `true` regardless of the actual result.

- **Bind the secret, don't check the flag.** Store what the gate protects as a **Keychain item
  under `SecAccessControl`**, so the data is cryptographically unreachable without a genuine
  biometric or passcode unlock. A hooked `evaluatePolicy` yields nothing because the OS, not the
  app's `if`, controls release.
- **`.biometryCurrentSet`, not `.biometryAny`**, so adding a fingerprint or re-enrolling Face ID
  invalidates the item. Otherwise an attacker who can enroll a new biometric keeps access.
- **Watch `LAContext` reuse** / `touchIDAuthenticationAllowableReuseDuration` — it lets an action
  succeed on a *recent* unlock with no fresh prompt. Deliberate only when intended.

### 8.4 IPC — input from other apps

- **Custom URL schemes are unauthenticated, spoofable input.** Any app can send them, and any app
  can register the *same* scheme to intercept your inbound data. Validate and discard malformed
  URLs; never let a scheme trigger a privileged action without confirmation. For auth/SSO
  callbacks prefer **claimed `https` Universal Links** over a custom scheme, which is
  hijackable. Handlers live in `application:open:options:` and, for scene apps,
  `scene:openURLContexts:` — review both.
- **Universal Links / AASA.** Audit `apple-app-site-association` `paths`/`components` for
  wildcards and unpublished or sensitive routes; undefined-but-matching routes should return 404;
  do not over-trust wildcard subdomains. On iOS 14+ the association is also CDN-cached, so verify
  the on-device state, not just the origin file.
- **App extensions.** Enumerate every `.appex`, inspect `NSExtensionActivationRule`, and map which
  App Group each extension can reach — the shared container is a trust boundary between the
  extension and the host app.
- **Insecure unarchiving.** `NSKeyedUnarchiver` decoding attacker-supplied data without secure
  coding is object injection. Use `requiringSecureCoding` / `decodeObjectOfClass:` and a concrete
  expected class.

### 8.5 WebViews — the JS bridge is a trust boundary

- **`WKWebView`, never `UIWebView`** (which cannot disable JavaScript). Disable JS where content
  is static (`preferences.javaScriptEnabled = false`), require `hasOnlySecureContent`, and keep
  `allowFileAccessFromFileURLs` and `allowUniversalAccessFromFileURLs` **false** — a `file://` XHR
  from injected script can read the whole container and exfiltrate it.
- **A JS→native bridge turns any XSS or untrusted iframe into native-code execution.**
  `WKScriptMessageHandler` / `postMessage`, `JSExport`, and `JSContext` all cross the boundary.
  Before a handler touches tokens, filesystem paths, deep-link targets, or app state, **validate
  `message.frameInfo.securityOrigin`** and reject unexpected subframes. Isolate bridges with
  `WKContentWorld`. Pass user-controlled data to the page through the message bridge as data,
  not by interpolating it into an `evaluateJavaScript` string — that is script injection.
- **`WKAppBoundDomains`** + `limitsNavigationsToAppBoundDomains` for any privileged bridge.
- **`isInspectable` must be false in production** (iOS 16.4+ defaults it off, but it can be set) —
  true exposes the WebView and `JSContext` to Safari's inspector on a paired Mac.

### 8.6 Network

- **App Transport Security stays on.** Review `NSAppTransportSecurity` for `NSAllowsArbitraryLoads`,
  `NSAllowsArbitraryLoadsInWebContent`, `NSAllowsLocalNetworking`, per-domain
  `NSExceptionDomains`, and the legacy `NSTemporaryException*` keys. A blanket
  `NSAllowsArbitraryLoads` is a finding. **Lower-level sockets, IP literals, and `.local` hosts
  bypass ATS entirely** — test those flows separately.
- **Check the hostname, not just the chain.** Validating that a cert is signed by a trusted CA but
  not that its hostname matches the host is the classic MitM hole — a proxy cert for any hostname
  then works.
- **Certificate pinning** where the threat model warrants it, with a rotation plan; design against
  the SSL-Kill-Switch bypass. Keep trust evaluation on in every configuration; if a debug build
  needs a relaxed policy, gate it behind a compile-time flag that release builds cannot carry.

### 8.7 Crypto

- CryptoKit for hashing, AEAD, key agreement, and signatures — it steers toward correct choices;
  prefer it to CommonCrypto in new code.
- **Flag RC4, MD4, MD5, and SHA-1** used for authorization or to protect stored/transmitted data.
- Passwords use a **unique salt and an expensive KDF**, never a fast general-purpose digest.
- **No hardcoded or predictable keys** — a reversed binary yields them immediately, so
  local-storage encryption keyed on a constant protects nothing.

### 8.8 Logs, memory, and integrity

- **No secrets through `NSLog`, unified logging, or crash artifacts.** Logs persist after
  uninstall and are readable with physical access. Audit after login, token refresh, deep-link
  handling, and WebView activity — the moments secrets are in hand.
- **Jailbreak and integrity checks are friction, not a control.** They raise cost on a device the
  attacker owns; never make one the only thing protecting an asset.
- **Untrusted media is the zero-click entry point.** Image and audio parsers fed attacker data are
  the classic remote-compromise surface (see the parser-chain and exploit case studies in the
  reference). Parsing untrusted bytes must be bounds-safe (`memory-safety`) and run with the
  hardened-runtime mitigations `xcode` §7 enables.

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
each control paired with the offensive technique it defeats. Walk it as a review checklist; a
missing control is the finding.

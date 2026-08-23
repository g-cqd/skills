# iOS Attack Surface — Defensive Controls

A defensive catalog of the iOS mobile-pentest surface: every attacker technique recorded as the
control that defeats it. Supports this skill, §8.

Use this as a review checklist: walk each control, and the absence of the control is the finding.
The build-setting side (Enhanced Security, PAC/MTE, `-fbounds-safety`) is `xcode` §7; the
memory-corruption side (parser UAF/OOB) is the memory-safety skill.

## The defensive taxonomy

Each row is one control. Failing the control is the finding.

### Storage — secrets at rest
- **Keychain accessibility class.** Default is too permissive. Device/biometry-bound secrets use
  `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` + `SecAccessControl` with
  `.biometryCurrentSet`. `ThisDeviceOnly` variants stop backup/restore migration.
- **NSFileProtection class.** Files left `NSFileProtectionNone` or
  `…CompleteUntilFirstUserAuthentication` are readable off a locked/backed-up device. Prefer
  `NSFileProtectionComplete` where the data is not needed backgrounded.
- **No secrets in `NSUserDefaults`/plist** (`Library/Preferences/<bundleID>.plist`), Core Data,
  Realm, YapDatabase, or app SQLite unencrypted. Core Data and Realm do **not** encrypt by
  default.
- **`NSURLCredential` persistence** and cookies (`Library/Cookies/*.binarycookies`) survive
  backup — keychain, not disk.
- **`Cache.db`** (NSURLSession) caches request/response bodies incl. tokens. Use
  `.ephemeral` session config, or `URLCache.shared.removeAllCachedResponses()` on logout, or
  cache policy `.notAllowed`.
- **App Group shared containers** are reachable by the app, widgets, and share extensions — audit
  everything left there.

### UI-surface leakage
- **Background snapshots** capture the current screen to `Library/Caches/Snapshots/`. Overlay a
  blank/branded view in `applicationDidEnterBackground` (or scene equivalent).
- **Keyboard cache** stores typed text in `Library/Keyboard/*-dynamic-text.dat`. On sensitive
  fields set `autocorrectionType = .no` and `secureTextEntry = true`.
- **General pasteboard** is world-readable by any app; monitor via `changeCount`. Use expiry and
  `localOnly` in `setItems:options:`; keep secrets off the general pasteboard.

### Local authentication
- **A biometric Boolean is not authorization.** `LAContext.evaluatePolicy` returns a `Bool` that
  a hooked callback flips to `true` (Objection/Frida one-liner). Bind access to a **Keychain item
  under `SecAccessControl`** so the secret is unreachable without a real biometric/passcode
  unlock, rather than gating on the callback.
- **`biometryCurrentSet`** invalidates the item when enrollment changes; plain `.biometryAny`
  survives a newly-added fingerprint/face.
- **`LAContext` reuse** / `touchIDAuthenticationAllowableReuseDuration` lets a sensitive action
  succeed on a recent unlock — deliberate only when intended.

### IPC / input from other apps
- **Custom URL schemes are unauthenticated input** any app can send, and any app can re-register
  the same scheme to intercept. Validate and discard malformed URLs; never trigger a privileged
  action from a scheme without confirmation; prefer claimed `https` Universal Links for auth
  callbacks. Handlers live in `application:open:options:` and scene `scene:openURLContexts:`.
- **Universal Links / AASA**: audit `paths`/`components` for wildcards and unpublished routes;
  undefined-but-matching routes should 404; don't over-trust wildcard subdomains.
- **App extensions**: enumerate `.appex`, inspect `NSExtensionActivationRule`, and map each
  extension's App Group reach.
- **Serialisation**: `NSKeyedUnarchiver` insecure decode of attacker data → object injection; use
  `requiringSecureCoding` / `decodeObjectOfClass:`.

### WebViews
- **`WKWebView`, never `UIWebView`** (can't disable JS). Disable JS unless required
  (`preferences.javaScriptEnabled = false`); require `hasOnlySecureContent`; keep
  `allowFileAccessFromFileURLs`/`allowUniversalAccessFromFileURLs` false (a `file://` XHR can
  exfiltrate the container).
- **JS→native bridges** (`WKScriptMessageHandler`, `postMessage`, `JSExport`, `JSContext`) turn
  any XSS or untrusted iframe into a native-code pivot. Validate `message.frameInfo.securityOrigin`
  and reject unexpected subframes before touching tokens, paths, or app state. Use
  `WKContentWorld` isolation; never `evaluateJavaScript` with a user-controlled string.
- **`WKAppBoundDomains`** + `limitsNavigationsToAppBoundDomains` for privileged bridges.
- **`isInspectable`** (iOS 16.4+) must be false in production — it exposes the WebView/JSContext
  to Safari.

### Network
- **ATS on.** Review `NSAppTransportSecurity` for `NSAllowsArbitraryLoads`,
  `…InWebContent`, `NSAllowsLocalNetworking`, per-domain `NSExceptionDomains`, legacy
  `NSTemporaryException*`. Lower-level sockets/IP-literals/`.local` bypass ATS — test separately.
- **Hostname check, not just chain validity.** Validating the CA but not the hostname is the
  classic pinning-adjacent bug.
- **Certificate pinning** with a rotation plan (SSL Kill Switch is the bypass to design against).

### Crypto
- Flag RC4, MD4, MD5, SHA-1 for authz or protecting stored/transmitted data. Passwords use a
  unique salt + an expensive KDF, not a fast digest. No hardcoded/predictable keys — a reversed
  binary yields them.

### Logs / memory
- No secrets through `NSLog`, unified logging, or crash artifacts — logs persist after uninstall
  and are readable with physical access. Check after login, token refresh, deep-link handling,
  WebView activity.

### Memory-corruption surface (→ `memory-safety`)
- Attacker-controlled **media parsers** (image/audio) are the zero-click entry point. The
  memory-corruption primitives they lead to (UAF, IOSurface physical UAF, PAC bypass, WebKit DFG
  OOB) are why untrusted-input parsing must be bounds-safe and why hardened-runtime mitigations
  (PAC/MTE, `-fbounds-safety`) matter — enabled via `xcode` §7.

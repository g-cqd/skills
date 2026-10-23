# Client side and browser

Use when the target runs in a browser or webview: single-page apps, extensions, embedded webviews, service workers,
browser storage, cross-window messaging, CORS, WebSockets, DOM rendering.

## Discipline

- Name the attacker origin or content source, the victim origin and session, the browser policy in force, and the
  sink.
- A framework that escapes interpolation is not a finding; an escape hatch that receives attacker data is.
- Browser defaults (SameSite, CORP and COOP, mixed-content blocking, credentialed wildcard CORS rejection) are real
  controls; check them before claiming an effect.
- Deployed headers and the browser versions in scope may be outside the repository; when decisive, use
  `needs_validation`.

## Classes

**DOM XSS.** `location`, `document.referrer`, `window.name`, message data, or storage reaches `innerHTML`,
`outerHTML`, `document.write`, string-evaluating APIs, executable URLs, jQuery HTML methods, or framework escape
hatches (`dangerouslySetInnerHTML`, `v-html`, `bypassSecurityTrust*`).

**DOM clobbering.** Injected `id` or `name` attributes shadow a global, form property, or configuration value that
code later trusts. Needs both markup that survives sanitization and a security-relevant use of the shadowed value.

**Prototype pollution.** An attacker key reaches a recursive merge or path assignment and changes prototype state,
and a reachable gadget reads the polluted property to change authorization, execution, navigation, or rendering.
`JSON.parse` or a shallow copy alone is not pollution.

**`postMessage` trust.** A handler acts on `event.data` without an exact origin allowlist and, where several frames
share an origin, the expected `event.source`. Prefix, suffix, substring, and unanchored regex checks fail. Sending
sensitive data with target `*` reaches any embedder.

**Cross-site WebSocket use.** The upgrade accepts ambient cookies from any origin without an `Origin` check or channel
token, and a handler reads or changes data for the victim session.

**Credentialed CORS.** The server reflects or loosely matches `Origin` with credentials allowed and returns sensitive
data. Report the actual accepted origin path and the cross-origin read or write.

**Service-worker scope takeover.** Attacker content becomes the registered worker script, gains a broad
`Service-Worker-Allowed` scope, or changes imported scripts without integrity. Check the final script URL, MIME type,
origin, and scope.

**Service-worker cache confusion.** Personalized responses are cached without account, tenant, or auth state in the
key and served after logout or account switch.

**Browser storage.** Tokens, private responses, or authorization decisions stay in `localStorage`, `sessionStorage`,
IndexedDB, Cache Storage, or extension storage and become readable by another account or a less-trusted component on
the same origin. A stored token alone needs a realistic reader.

**Cross-tab confusion.** `storage` events, `BroadcastChannel`, shared workers, or origin-wide caches carry identity or
commands between tabs without binding to the current session; a stale tab overwrites newer auth state.

**Cross-site leaks.** An attacker page distinguishes protected state through load and error events, frame counts,
redirects, timing, cache, or response size while the browser sends the victim's credentials. Needs one concrete
secret predicate ("is this user a member of X").

**Opener and window state.** A retained opener or named window lets an attacker page steer a privileged navigation,
or permitted window metadata reveals protected state.

**Clickjacking.** A framed state-changing action without effective `frame-ancestors` or `X-Frame-Options`. Missing
headers on read-only pages are hardening.

**Navigation confusion.** A client-controlled redirect without scheme and destination policy, including `javascript:`
and `data:` URLs.

## Moves

- Start at each dangerous sink and trace backward to a source an attacker can set from another origin.
- Compare the first render with client-side navigation, error pages, and offline or cached modes.
- Test with a local page on a second origin and dummy accounts; do not attack a deployed origin.

## Validation rules

1. Cite the source, the sink, the browser policy, the affected origin and session, and the observable change or
   disclosure.
2. Prototype pollution needs the recursive write and a security-relevant gadget; clobbering needs surviving markup
   and a security-relevant use.
3. Storage and service-worker findings show that an attacker write or cache entry reaches another account, tenant, or
   later authorization decision.
4. Messaging, CORS, WebSocket, and leak findings show the exact origin check and the protected state, after CSP,
   COOP and CORP, cookies, and SameSite.
5. A deployed header, extension permission, browser version, or renderer behavior that decides the outcome makes the
   candidate `needs_validation`.

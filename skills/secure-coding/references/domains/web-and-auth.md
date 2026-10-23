# Web, sessions, and identity

Use when the target serves HTTP or sits behind a proxy, CDN, or gateway, keeps sessions, or verifies credentials:
CSRF, JWT, OAuth and OIDC, SAML, MFA, passkeys, account linking and recovery, API keys, mTLS.

## Discipline

- A framing or cache finding needs two components that read the same request, response, or cache key differently.
  Name both and the exact value each one sees.
- For each credential, find where its signature or secret is verified and every binding its role needs: issuer,
  audience, origin, relying party, client, session, principal, resource, assurance level, expiry, one-time use.
- `Host`, `Forwarded`, `X-Forwarded-*`, `Origin`, `Referer`, redirect targets, callback state, and URLs built from the
  request are trust decisions. Trace each one to the identity or response it affects.
- A missing header, cookie flag, MFA prompt, or rate limit is not a finding on its own. It needs an accepted invalid
  request, an effect on another principal, an assurance downgrade, or a disclosed credential.

## Classes

**Request framing and desynchronization.** Front and back end disagree on where a request ends or how headers
normalize: several `Content-Length` values, `Transfer-Encoding`, HTTP/2 or HTTP/3 downgrade, header-name folding,
connection headers, CR/LF conversion. Show which bytes each side assigns to which request.

**Cache poisoning through unkeyed input.** A request value changes cached content or security headers but is not in
the cache key: forwarded host or scheme, a cookie, query normalization, language or device headers, authorization
state.

**Cache deception and private responses cached.** The cache treats a private dynamic path as a static asset, or
stores a response whose identity inputs are missing from the policy. Compare edge cacheability with the application's
route parsing, suffix and path-parameter handling, and cache directives.

**Host and forwarded-header trust.** Client-supplied host or proxy metadata builds absolute URLs, routes tenants,
forms reset links and callbacks, keys caches, or sets the client address used by authorization. Establish who can
supply the header and whether the trusted ingress strips client copies.

**Response-header injection.** Untrusted data reaches `Location`, `Set-Cookie`, CSP, or another header with control
characters. Check whether the framework rejects it, and require a security-relevant change in the response.

**CSRF.** A cookie-authenticated state change accepts a cross-site request without an effective token, same-site
binding, or strict `Origin` check. List every such route, including JSON, multipart, method override, and legacy
forms. Read-only routes and routes that need a non-ambient bearer token do not qualify.

**Session fixation and invalidation.** The session id is not rotated on login, account switch, MFA completion, or
impersonation, or stays valid after logout, password change, revocation, or account disable. Check server sessions,
refresh tokens, signed cookies, WebSocket state, and cached copies.

**Cookie scope and transport.** A sensitive cookie has a broad `Domain` or `Path`, can travel over plain HTTP, or is
shadowed by a sibling cookie another component picks. Missing flags stay hardening notes unless a less-trusted origin,
network position, or browser path can read or set it.

**JWT verification and claims.** Signature verified; algorithm and key source pinned on the server; `exp`, `nbf`,
`aud`, `iss` checked. `kid`, `jku`, and `x5u` are untrusted key selectors. Look for decode-without-verify paths. A
valid token for another service is invalid here.

**OAuth and OIDC binding.** Exact `redirect_uri` match, session-bound `state`, PKCE where it applies, ID-token issuer,
audience, signature, and nonce, and the selected identity provider bound in multi-provider flows. Compare the first
callback with retries, account linking, and error paths.

**SAML assertions.** The element whose signature is checked must be the element used as identity. Look for unsigned
fallbacks, XML parser settings, canonicalization differences, and validity, audience, recipient, request correlation,
and replay checks.

**MFA enrollment and downgrade.** Enrolling, replacing, or disabling a factor, generating recovery codes, trusting a
device, and fallback login must require the assurance the policy demands. A first factor alone must not replace the
second.

**Step-up binding.** A completed challenge must upgrade only its own principal, session, tenant, action, and expiry,
once. Compare the UI, API, and mobile routes to the same sensitive action.

**WebAuthn and passkeys.** Registration binds challenge, RP id, origin, credential, user handle, algorithm, and user
verification to the initiating session; authentication checks the same, the credential's membership, and the
signature counter policy.

**Account linking and identity collision.** Adding an identity provider, passkey, email, phone, or device needs a
current session, proof of the new identity, step-up where required, and callback state bound to the account that
started it. Check unlink and relink, and email or username collisions across providers.

**Password reset and recovery.** Token randomness, binding to user and action, expiry, single use, rate limits, the
trust of the delivery URL, and invalidation of earlier tokens and sessions. Support and admin recovery are often the
weakest login path.

**API keys.** A key reaches more tenants, resources, actions, or environments than its record grants, or request
parameters override its binding. Check publishable versus secret key types, prefix-only verification, rotation, and
revocation. Keys in client bundles, URLs, logs, or responses are disclosure; a public identifier called "key" is not.

**mTLS identity.** A service trusts client-certificate headers from any peer, maps subject text to an account loosely,
or accepts the wrong trust domain, usage, or validity. Expired or revoked certificates that fall back to weaker
authentication, and pooled connections that outlive revocation.

## Moves

- Walk each credential through issue, store, send, use, refresh, and revoke; compare the normal, error, retry,
  migration, legacy, and account-switch paths.
- List every door to the same identity and every route to the same sensitive operation; the weakest one is the
  policy.
- Put the parser, proxy, router, cache, and application normalization side by side, and feed identical local request
  fixtures to each.
- For recovery and linking, draw the account graph before and after; each edge names the current principal, the proof
  of the new identity, the assurance, the callback binding, and what is revoked.

## Validation rules

1. Proxy chains, edge cache keys, identity-provider policy, certificate trust, browser cookie behavior, secrets, and
   deployed auth modes are often outside the repository. When one is decisive, the candidate is `needs_validation`.
2. A framing or cache finding names both components and the divergent value, and shows the cross-request or
   cross-user effect with local fixtures.
3. A token, MFA, passkey, linking, recovery, key, or mTLS finding cites the verification line, names the missing
   binding, and shows that the server accepts the invalid credential or transition.
4. A CSRF finding names the ambient credential, the state-changing route, the accepted cross-site request, the cookie
   policy, and the missing check.
5. Check framework and library defaults for the pinned version; an unknown version or setting is `needs_validation`.

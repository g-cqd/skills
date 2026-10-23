# Attack classes

The core classes of `secure-coding` §4.3. Pick the classes that fit the target from the threat frame, split a large
codebase per subsystem, and add a class that the product needs and this list lacks. Each class is one block: in an
audit, a hunter receives the block's text, not its name. The finding gate (§3) applies to every class; a pattern that
matches here is a reason to look, not a finding.

For a target type in the table of §4.3, also read its file under `domains/`.

## Injection

Trace lower-trust input from its entry to a sink that interprets it. The sink depends on the target:

- web services: SQL and NoSQL queries, HTML output, templates, shell commands, file paths, redirects, deserializers,
  LDAP and XPath, log lines;
- libraries: any function that hands caller data to a buffer operation, a parser, or a format string;
- CLI tools: shell command construction, path handling, environment interpolation;
- clients and browsers: DOM sinks and object merges (`domains/client-side.md`).

Look past the direct path. Data stored safely and later read by other code into a dangerous context is injection
(second-order). Injection through field names, keys, headers, and metadata counts, not only through values. So does
injection into secondary systems: logs, caches, search indexes, analytics.

## Access control

Verify that a caller cannot act outside its authority: the right permission, for the right resource, through the
right mechanism.

- Is there another path to the same state change that checks a weaker permission?
- Can a field in the request body override what the permission system restricts (mass assignment)?
- Does an endpoint check authentication and forget authorization?
- Does one resource have several access paths with different checks?
- Do bulk, batch, export, and import operations check each item?
- Is the resource identifier bound to the caller's tenant, or only looked up by id?

For a complex model, split authentication bypass and authorization logic into separate units.

## Files and resources

- Path traversal, including through symlinks, encoded separators, Unicode normalization, and null bytes.
- SSRF: the application fetches a URL the attacker controls, including through redirects, DNS rebinding, IPv6 and
  decimal IP forms, and URL-parser differences.
- Unsafe deserialization, archive extraction outside the target (zip slip), predictable or shared temporary files.
- Check-then-use races on files (TOCTOU).
- Memory safety where it applies: `domains/native-and-binary.md` and `memory-safety`.

## Crypto and secrets

- Weak randomness for tokens, keys, nonces, and reset codes.
- Secrets in source, history, logs, error messages, URLs, client-visible responses, crash reports.
- Broken key derivation, missing MAC verification, nonce reuse, static IVs, unauthenticated encryption, ECB.
- Non-constant-time comparison of secrets.
- The failure path: does a crypto error fall back to no crypto, or to accepting the input?

## Business logic

Scanners do not find these; read the workflows.

- **State machines:** skip a step, go backwards, replay a completed flow, reach an invalid state. If step 2 of 3
  fails, is step 1 undone?
- **Races with business effect:** double spend, double approval, lost update, a check and an act that are not atomic.
- **Numbers:** negative, zero, overflow, precision loss, string-number coercion, currency and unit mix-ups.
- **The right rule:** not "does a check exist" but "is it the check this business rule needs"; can one operation
  bypass a limit enforced on another operation with the same effect?
- **Implicit trust:** data from storage, configuration, another component, or a plugin assumed safe because "we
  validated it on the way in". Another path may have written it.
- **Time:** expiry, scheduling, rate windows, clock skew, the exact boundary moment, time zones between components.
- **Defaults and fallback:** missing configuration, a feature flag off, a dependency down, a migration half done.

## Feature abuse and data leakage

Legitimate features used for something else.

- **Export and backup as exfiltration:** a low-privilege export, snapshot, or backup that includes data above the
  caller's access, other users' data, deleted or draft content, or pruned history.
- **Import and restore as injection:** overwriting existing records, skipping normal validation, writing into
  collections the caller cannot write, ignoring the permission model of the UI.
- **Search, filter, and sort as an oracle:** revealing that hidden content exists, probing hidden fields through
  filters, or reading a hidden value through sort order.
- **Enumeration through side effects:** different errors, timings, sizes, or status codes for "does not exist" and "no
  access"; user enumeration through reset, invite, or registration.
- **Preview and draft leakage:** preview tokens that unlock more than one item; drafts in search, feeds, sitemaps, or
  listings; cache headers that let a CDN serve private content publicly.
- **Callbacks as SSRF:** a user-set webhook, notification, or callback URL that the server fetches, before and after
  redirects.

## Chained boundaries

Behavior that is allowed or contained on its own becomes a vulnerability when another component relies on a stronger
guarantee.

- **Multi-step:** map what a low-privilege principal may read, write, invoke, and keep; connect only concrete outputs
  to later trust decisions, and confirm each prerequisite.
- **Cross-component gaps:** compare the exact guarantee component A produces with what component B assumes, including
  truncation, coercion, normalization, tenant scope, and plugin access.
- **Second-order use:** a field name becomes a JSON path, a slug becomes a file path, escaped text enters raw
  rendering, a stored string becomes a URL, regex, template, or policy expression.
- **Capability growth:** a token, API key, plugin, OAuth grant, MCP tool, or model capability that becomes broader
  after delegation, refresh, caching, a role change, or composition.
- **Ordering:** setup, migration, soft delete, revocation and cache expiry, check and use, validate and consume.
- **Rollback and recovery:** undelete, restore, revision rollback, and cancellation must apply the current owner,
  validation, and authorization.

## Wildcard

No category: find what the other classes miss, under the same gate.

- What is the strangest code, and what happens if it is abused?
- What feels half-finished, experimental, or bolted on? It had the least review.
- Which API calls are possible but never made by the client? The UI constrains users; the API does not.
- Which routes, parameters, headers, or features are registered but not documented?
- What happens when features that were not designed together meet: localization and preview and caching, import and
  plugins and webhooks, OAuth and impersonation and API keys?
- What does the git history show: reverted security fixes, commented-out checks, secrets committed and removed?
- Which actions by a valid account affect other users, shared integrity, availability, or the operator's costs?
- Which operations cannot be undone or need elevated confirmation, and is the approval bound to the final principal,
  action, and resource?
- What does the code assume about the environment: a local database, an accurate clock, trustworthy DNS, a
  case-sensitive filesystem?
- What do the tests not test? Compare the edge cases the developers thought of with the ones they did not.

Follow an anomaly until you can say whether it is safe. If a comment explains why something is safe, verify it. Read
code named `temp`, `hack`, or `legacy` closely.

## Obvious things

A literal pass that others skip because they assume someone checked. Check every item and report each result; for
each hit, trace the impact before calling it a finding (a missing `HttpOnly` on a cookie that holds no secret is
nothing).

- Hard-coded passwords, API keys, tokens, private keys (`password`, `secret`, `apikey`, `token`, `Bearer`,
  `-----BEGIN`, default credentials).
- `TODO`, `FIXME`, `HACK`, `XXX` comments about security (`TODO: add auth`).
- Debug or development mode that a production request, header, query parameter, or environment variable can enable.
- Test, example, or seed credentials that work in production.
- Unprotected `/debug`, `/admin`, `/test`, `/status`, `/metrics`, `/env`, `/.env`, `/config` routes.
- Committed `.env`, `credentials.json`, `*.pem`, `*.key` files, and a `.gitignore` that misses secrets and uploads.
- Unpinned dependencies; known CVEs in the lockfile.
- `eval`, `exec`, `Function`, `child_process`, `vm.run*`, dynamic `import` with input.
- CORS `*`, or a reflected origin with credentials.
- Cookies without `HttpOnly`, `Secure`, or `SameSite` where they carry a session.
- Open redirects through `redirect`, `return`, `next`, `url`, `goto`, `continue` parameters.
- HTTP endpoints without TLS; TLS verification turned off.
- Production errors that return stack traces, internal paths, or SQL errors.

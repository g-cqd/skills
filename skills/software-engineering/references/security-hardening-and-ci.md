# Security, Hardening, Isolation, Agent Safety & CI/CD Supply Chain

## Contents
- [1. Critical-Grade Standards & Threat Modeling](#1-critical-grade-standards--threat-modeling)
- [2. Process Isolation, Parsers & Memory Safety](#2-process-isolation-parsers--memory-safety)
- [3. Cryptography, Secrets & Data Isolation](#3-cryptography-secrets--data-isolation)
- [4. Network, WebViews, Extensions, IPC & Subprocesses](#4-network-webviews-extensions-ipc--subprocesses)
- [5. AI Agent & Sandbox Isolation Levels (L0–L3, P1–P2)](#5-ai-agent--sandbox-isolation-levels-l0l3-p1p2)
- [6. CI/CD, Supply Chain, TUF Updates & Release Hardening](#6-cicd-supply-chain-tuf-updates--release-hardening)
- [7. Security Audit Reporting & Finding Gate](#7-security-audit-reporting--finding-gate)

---

## 1. Critical-Grade Standards & Threat Modeling

Always evaluate against the **latest published editions** of authoritative security, cryptography, and supply-chain standards (never treat an older edition or parameter set as a ceiling — verify current advisories and deprecation notices at implementation time):
- **SDLC & Assurance:** NIST SSDF, NIST SP 800-53, CISA Secure by Design, BSI TR-03185, ISO/IEC 27001, IEC 62443.
- **Cryptography & Memory Safety:** NSA CNSA & Memory-Safety guidance, ANSSI RGS, BSI TR-02102, NIST SP 800-63B / 800-132 / 800-175B, FIPS (when customer-mandated).
- **Application, Mobile & AI Security:** OWASP Top 10, OWASP ASVS (target highest assurance level), OWASP MASVS/MASTG, OWASP Top 10 for LLM Applications, OWASP Agentic AI Threats & Mitigations, MITRE ATLAS, NIST AI RMF.
- **Endpoint, Supply Chain & Regulation:** NCSC/MI5 High-Threat Endpoint guidance, SLSA (build track L2 minimum, L3 target), OpenSSF Scorecard, EU Cyber Resilience Act (CRA), NIS2.

### Threat-model contract (required for every product & new surface)
Maintain **one** threat model document and **one** risk register per product:
1. **Assets:** credentials, signing keys, unlocked vaults, user files, sibling-app stores, session transcripts, approval decisions, build runners/caches.
2. **Adversaries:** remote web origins, malicious documents/media/archives, terminal escape streams, untrusted repos/skills/MCP servers, prompt-injected LLM output, local unprivileged processes, compromised dependencies/feeds/runners.
3. **Trust boundaries & channels:** list every channel with direction, peer authentication mechanism, size cap, and parser.
4. **Threat rows:** map each threat to its control, regression test (red-first), or formal **risk acceptance** (reason, approver, and explicit **expiry date**). Update the model in the same change as every new surface (updater, IPC socket, parser, backup restore, workflow).

---

## 2. Process Isolation, Parsers & Memory Safety

- **Least privilege by process:** code that parses untrusted complex formats (images, PDF, video, archives, CRX3/XPI extensions, terminal graphics, untrusted HTML/XML, encrypted backup restores) must not run in the process that holds master vault keys, signing keys, or provider tokens. Isolate vaults in an App-Sandboxed XPC service (returning only requested fill values on user action, never raw keys) and isolate decoders in zero-network, zero-keychain sandboxed helpers.
- **Length-field agreement (zero-click parser bug class):** whenever a format states a size or count in two places (header vs stream, TIFF vs SOF3, manifest vs archive), verify they agree and fit the actual buffer length **before** allocating or decoding. **Reject mismatches; never silently clamp.**
- **Pre-decode bounds:** enforce byte caps, recursion/nesting depth caps, and image pixel limits (`width * height <= pixelLimit`) from metadata *before* invoking `CGImageSourceCreateImageAtIndex` / `CGPDFDocument` / `AVURLAsset`.
- **XML & HTML hardening:** disable DTD and external entity resolution (`shouldResolveExternalEntities = false`), reject `<!DOCTYPE` / `<!ENTITY` / NUL bytes before parsing, bound input size, and never parse XML with backtracking `NSRegularExpression`.
- **Canonicalize before validating:** resolve symlinks (`realpath` / `O_NOFOLLOW` descriptor-relative `openat`/`fstatat`), normalize URLs and Unicode *before* checking root containment or allowlists. Always check symlink escapes in tests.

---

## 3. Cryptography, Secrets & Data Isolation

- **Algorithms:** current authoritative AEAD (e.g., `AES-256-GCM`, `ChaCha20-Poly1305`) with explicit AAD binding record kind/ID/version and unique CSPRNG nonces; SHA-256/384/512; Ed25519 / ECDSA P-256+; current standardized hybrid post-quantum key exchange (e.g., ML-KEM / X-Wing) for long-lived confidentiality. Verify current algorithm/key-length guidance before designing new formats and design formats with cryptographic agility (versioned envelopes) so algorithms can rotate without breaking recovery.
- **Password KDF:** memory-hard Argon2id at or above the current IETF/OWASP/NIST recommended floor (at minimum `t=3, p=4, m=64 MiB`; higher memory such as `128–1024 MiB` for local master vaults, scaled up as hardware advances) with **upper and lower parameter bounds enforced on read** and unlock throttling; use FIPS-approved PBKDF2-HMAC-SHA256+ only when FIPS compliance is explicitly mandated.
- **Key storage & zeroization:** store secrets in Keychain/Secure Enclave with `WhenUnlockedThisDeviceOnly` (never plaintext JSON config files, never silent downgrade to legacy login keychain); zeroize sensitive key buffers after use; compare MACs/tokens in constant time; never log secrets, tokens, or PII in stdout, stderr, crash logs, or SIEM exports.
- **Multi-profile / multi-tenant isolation:** bind every read, write, cache key, cookie store, extension instance, popup, handoff, favorite, pinned tab, search index, backup, and restore to an explicit profile/tenant ID enforced at the data layer — verify with cross-profile isolation regression tests (including real WebKit cookie stores).

---

## 4. Network, WebViews, Extensions, IPC & Subprocesses

### Network & SSRF
- **Default-deny egress** enforced outside untrusted code where possible (host proxy / hypervisor / sandbox).
- **SSRF & DNS-rebinding prevention:** resolve hostnames, parse every IP with `inet_pton`, reject all IANA special-use ranges (IPv4 `0/8`, `10/8`, `100.64/10`, `127/8`, `169.254/16`, `172.16/12`, `192.168/16`, multicast/reserved; IPv6 `::`, `::1`, `fc00::/7`, `fe80::/10`, and **all IPv4-mapped `::ffff:0:0/96`** spellings including expanded forms), and **pin the validated IP** on the actual socket connection so DNS cannot rebind between check and connect.
- **OAuth loopback:** bind `NWListener` strictly to `127.0.0.1` / `::1` (`requiredLocalEndpoint`, never `0.0.0.0`), require PKCE (`S256`) and random `state`, and return plain-text or HTML-escaped callback pages.
- **TLS exceptions:** pin only the exact leaf certificate SHA-256 shown to the user, never a broad host wildcard exception.

### WebViews, Browser Extensions & Links
- **Bridge origin authority:** check `frameInfo.securityOrigin` and `frameInfo.isMainFrame` (and extension `sender.tab.url` / `sender.id`) on every native message; never trust origin strings sent from the page world. Scope host permissions narrowly (avoid `*://*/*` `MAIN`-world injection when domain allowlists suffice).
- **Extension signature verification:** cryptographically verify every installable extension package before unpacking — CRX3 protobuf RSA/ECDSA proofs matching `crxID`, and XPI Mozilla PKCS#7/COSE signatures (or block page-offered `.xpi` and gate unsigned `.zip` behind an explicit dev-mode warning).
- **Safe file/URL handling:** quarantine downloads (`LSQuarantine`) on hidden temp files *before* moving to final names; reveal executable `file://` links in Finder rather than launching; gate non-HTTP(S) schemes (`ssh://`, custom schemes) appropriately.

### Local IPC & Subprocesses
- **Peer authentication:** verify Unix socket peers with `getpeereid` / audit tokens, set socket dir `0700` and socket `0600`, hash control tokens with constant-time compare, and enforce **token expiry, per-target scope, capability bits, and refusal logging**.
- **Subprocess & file hygiene:**
  - Create sensitive files and temp outputs with `O_CREAT | O_EXCL | O_NOFOLLOW` and explicit mode (`0600`/`0700`, never relying on umask).
  - Verify external binary paths with `lstat` / canonical root containment, owner UID, and zero group/world write bits before executing them.
  - Scrub child environments to a strict allowlist (strip `DYLD_*`, `__XPC_DYLD_*`, `GIT_CONFIG_*`, `GIT_*_COMMAND`, `BASH_ENV`, `ENV`, `PAGER`, `LESSOPEN`, and host API/signing tokens).
  - Start subprocesses in their own process group (`setpgid`), kill `-pgid` on timeout/exit, and drain stdout + stderr concurrently (or to `0600` temp files) to avoid 64 KiB pipe deadlocks.

---

## 5. AI Agent & Sandbox Isolation Levels (L0–L3, P1–P2)

### Isolation ladder
| Level | Boundary | Credentials inside | Egress | Autonomy |
|---|---|---|---|---|
| **L0** IDE assistant | None (host user) | Host's | Host's | Human per action (approved tools only) |
| **L1** Rootless container | Shared kernel, no sockets | None forwarded | Container network allowlist | Human per command |
| **L2** Disposable VM | Hypervisor, **host-enforced egress** | Scoped short-lived run token only | Host allowlist / `CONNECT` proxy, private ranges floored | **Agent autonomous**; human reviews output patch/PR |
| **L3** Sealed VM | L2 + zero direct NIC | None (host proxy injects auth) | Host proxy to named endpoints only | Agent autonomous; full out-of-band evidence reviewed |
| **P1 / P2** Prod runtime | Landlock + seccomp (`P1`) / isolated micro-VM (`P2`) | None | None | Untrusted user file parsers in production services |

### Agent-harness specific rules (current OWASP LLM & Agentic AI threats)
- **Conservative approval classifiers:** if session grants exist, treat them as UX convenience **only when OS sandboxing is enabled** (never apply grants when `--no-sandbox`). Classify conservatively by construction for the exact shell binary that executes the command: reject leading env assignments (`GIT_CONFIG_*`, `PATH=.`), `$` outside single quotes, redirections (`>`, `<`, `<<`), shell-specific parameter/prompt expansions (such as modern bash `@P`/`@E`/`@A` operators), and use per-tool allowlists of safe subcommands/options (`git`, `rg`, `find`, `tar`, `sed`, `awk`) rather than incomplete denylists.
- **Digest-bound project trust:** never execute repository configs, skills, agents, build plugins, or ACP-requested MCP servers without explicit user trust bound to content SHA-256 digests.
- **Secret-store confinement:** deny agent sandboxes read access to Keychains, `~/.ssh`, `~/.aws`, `~/.gnupg`, `~/.netrc`, browser cookies/vaults (Safari, Chrome, Firefox, custom browsers), and the agent's own credential/session-key files; isolate per-session `TMPDIR`.
- **Terminal escape filtering:** strip CSI, OSC (including OSC 52 clipboard), and DCS sequences from model/tool output before printing to the terminal.
- **Out-of-band evidence:** store run manifests (image/policy digests, model/harness versions, exit status, artifact hashes), egress flow logs, and command transcripts outside the guest; verify run tokens never appear in logs.

---

## 6. CI/CD, Supply Chain, TUF Updates & Release Hardening

### Workflow security (`zizmor` + `actionlint` = 0 errors)
- Pin **every** third-party and internal GitHub Action to a full 40-char commit SHA (commenting the version tag).
- Declare top-level `permissions: { contents: read }` on every workflow; grant write scopes only on the single job that needs them; set `persist-credentials: false` on read-only checkouts.
- Never interpolate `${{ inputs.* }}`, `${{ github.event.* }}`, or `${{ matrix.* }}` directly inside `run:` blocks — bind via step `env:` and validate with strict regexes before use.
- Never use dynamic `${{ secrets[matrix.*] }}` (injects the entire secrets context into the runner) or broad `secrets: inherit` — pass explicit named secrets per job/Environment.
- Commit lockfiles (`Package.resolved`, `Gemfile.lock` with `--frozen`, hashed `requirements.txt`), pin dependencies by exact version or commit SHA, and enforce HTTP timeouts on all CI helper scripts.

### Runner & cache separation (SLSA / ISO 27001 environment separation)
- Never run untrusted PR builds, Danger, or mutation/fuzzing jobs on the same runners or caches as production signing/publishing jobs.
- Split runners into unprivileged PR pools (zero signing certs or publish API keys) and protected release pools (guarded by CI Environments with required reviewers).
- Keep runner OS images, toolchains, CI actions, and pinned dependencies continuously updated on a scheduled cadence (e.g., Dependabot/Renovate with cooldown + security fast-track); pinning guarantees reproducibility per build, never permission to stagnate on vulnerable versions.
- Materialize signing certificates (`.p12` into isolated `0600` temp keychain in `$RUNNER_TEMP`) and API keys (`.p8` `0600` in `$RUNNER_TEMP`) per job and delete them in `if: always()` cleanup steps. Never store persistent signing keys on shared runner disks.

### Releases, SLSA provenance, SBOM & TUF updates
- **Build & sign in CI:** Developer ID + Hardened Runtime (`--options runtime --timestamp`) + Apple notarisation (`notarytool submit --wait`), verified by `codesign --verify --strict` and `spctl --assess`.
- **Attach verifiable artifacts:** `.sha256` checksums, CycloneDX/SPDX SBOM (covering lockfile dependencies + bundled engines/patches), and GitHub SLSA Build Provenance (`actions/attest-build-provenance`, verifiable via `gh attestation verify`).
- **TUF-aligned self-updates:** signed release metadata must be **mandatory** (never silently skipped), carry `issuedAt` + `expiresAt` (blocking freeze attacks), enforce strictly monotonic build/version floors (blocking rollback), and separate online signing keys from offline/hardware root rotation keys.
- **Coordinated disclosure (`SECURITY.md`):** publish a private reporting channel, realistic best-effort response targets scaled to maintainer capacity (e.g., for solo-maintained OSS: 7–14 d ack, 30 d triage/critical, 60–90 d high; commercial teams may commit tighter SLAs), supported versions, and verification commands (`git tag -v`, `shasum -a 256 -c`, `gh attestation verify`).

---

## 7. Security Audit Reporting & Finding Gate

- **Finding gate:** trace a concrete path from trust boundary to sink with an exploitation scenario before labeling something a vulnerability (`Confirmed`). A risky pattern without a reachable path or missing compliance control is a **Hardening Note** or **Compliance Gap** — never inflate severity.
- **Required fields per finding:** Severity (`Critical`/`High`/`Medium`/`Low`), Class + CWE/OWASP ID, Exact `file:line`, Exploitation Scenario, Concrete Fix, Verification / Regression Test.
- **Sandboxed dynamic verification only:** run ASan/UBSan/TSan, `sandbox-exec -p '(version 1)(allow default)(deny network*)'`, `codesign -dvv --entitlements -`, `zizmor --offline`, and proof-of-concept probes strictly on isolated scratch copies — never against live user apps, production state, or external hosts.

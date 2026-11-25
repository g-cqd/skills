# High-Assurance Security & Safety Audit Baselines

Use this reference when a security audit targets high-assurance, government/defense, regulated,
or enterprise-approval baselines. Do **not** inflate a baseline deviation into a `confirmed`
vulnerability unless it satisfies the finding gate (`SKILL.md` §3); missing baseline controls
with no reachable exploit path are **hardening notes** or **compliance gaps** mapped here.

## Authoritative Agencies & Standards

| Authority / Standard | Scope & When to Apply | Concrete Controls & Audit Checks |
|---|---|---|
| **NIST SP 800-53 Rev. 5** | High-assurance & enterprise systems | `AC` (least privilege, Seatbelt/Landlock confinement), `AU` (tamper-evident, secret-free logs), `CM` (minimal entitlements & config), `IA` (strong auth), `SC` (boundary protection, TLS/crypto), `SI` (input canonicalization, memory safety, flaw remediation). |
| **NIST SP 800-63B / 800-132 / 800-175B** | Authentication, KDFs, key lifecycle | Argon2id (OWASP / RFC 9106 memory-hard parameters) or PBKDF2-HMAC-SHA256 when FIPS-mandated; CSPRNG keys & unique nonces; zero plaintext secrets on disk; Keychain/Secure Enclave wrapping with `ThisDeviceOnly`. |
| **NSA CNSA 2.0 & Memory-Safety Guidance** | Long-lived confidentiality & native code | Hybrid post-quantum key exchange (`X25519MLKEM768` / Apple CryptoKit X-Wing / Secure Enclave ML-KEM) against harvest-now-decrypt-later; AES-256-GCM / ChaCha20-Poly1305; SHA-384/512; memory-safe languages & strict memory safety (`-strict-memory-safety`, bounds checks, zero unsafe shortcuts). |
| **ANSSI RGS & *Recommandations de sécurité*** | Cryptographic durability, compartmentalization, TLS & secrets | Strong AEAD & key separation (distinct KEK/DEK/MAC keys); constant-time MAC/digest verification; hardened TLS 1.3; strict process isolation; minimal attack surface & explicit trust anchors. |
| **NCSC / MI5 High-Threat Endpoint & Supply-Chain Guidance** | Desktop apps, CLI developer tools, agent runtimes, browsers | Hardened Runtime without `allow-dyld-environment-variables`, `disable-library-validation`, or `allow-unsigned-executable-memory`; Seatbelt/Landlock/seccomp sandboxing; cryptographically verified plugins/extensions (CRX3/PKCS#7, signed bundles); zero shell interpolation; explicit binary/library owner & permission trust checks (`BinaryTrustChecker`). |
| **FBI / CISA Secure by Design & Memory-Safety Roadmap** | Default-secure engineering & vulnerability elimination | Safe defaults out of the box (strict TLS, no opt-out-only safety, atomic writes, zero telemetry); elimination of entire bug classes (command injection, path traversal, ReDoS, integer overflow, memory corruption) rather than point mitigations; published `SECURITY.md` and rapid vulnerability disclosure. |
| **IC / Zero-Trust Compartmentalization (CIA / Defense Principles)** | Multi-component apps, agent sandboxes, sensitive local stores | Strict separation of privilege between untrusted parsers/renderers/webviews and secret-holding vaults; never let an agent sandbox read sibling app vaults/cookies/keychains; scrub child process environments so host tokens never cross trust boundaries. |
| **OWASP Top 10:2025, ASVS 5.0 (L1–L3), MASVS / MASTG** | Web, API, CLI, mobile & desktop apps | Canonicalize before validating (realpaths, symlink refusal); SSRF DNS-rebinding prevention & special-range IP blocking; Keychain `ThisDeviceOnly` + `biometryCurrentSet`, `NSFileProtectionComplete`, WebView JS bridge & URL-scheme allowlists (block `file://`, `smb://`, `javascript:` where unintended). |
| **SLSA Level 3 & Software Supply-Chain Integrity** | CI/CD pipelines, packages & distributed binaries | Commit-SHA-pinned GitHub Actions; signed commits & tags; reproducible lockfiles (`Package.resolved`); verified SHA-256 release checksums & Developer ID signing/notarization on macOS; minimal third-party transitive dependencies; SBOM transparency. |
| **ISO/IEC 27001:2022/2024 & Enterprise Software Approval** | Corporate adoption & IT Security vetting of open-source/internal tools | Permissive, clear license (MIT/Apache-2.0); public auditable source; `SECURITY.md`; zero undocumented network egress or telemetry (GDPR data minimization, verifiable under `sandbox-exec deny network*`); unprivileged execution; clear execution-boundary disclosure. |

## Sandboxed Dynamic Verification Checklist (Isolated Copies Only)

Strictly obey `SKILL.md` §5: run dynamic probes only against isolated scratch copies, never against live user apps, production state, or external hosts.

1. **Memory & Undefined Behaviour:** `clang -fsanitize=address,undefined,unsigned-integer-overflow` (ASan/UBSan) and Swift TSan on C/SIMD kernels, FFI bridges, and untrusted parsers; differential fuzzing against scalar reference implementations.
2. **Zero-Egress & Filesystem Confinement:** macOS `sandbox-exec -p '(version 1)(allow default)(deny network*)'` (or Linux network namespace / `strace -e trace=network,file`) to prove zero outbound sockets and zero writes outside declared roots (including symlink-escape tests).
3. **Apple Binary & Entitlement Inspection:** `codesign -dvv --entitlements -`, `otool -l/-L/-D`, and verification that no dangerous `com.apple.security.cs.*` exceptions ship.
4. **Supply Chain & CI Hygiene:** Verify commit-SHA-pinned third-party Actions, pinned `Package.resolved` revisions, valid `LICENSE` + `SECURITY.md`, and zero open Dependabot/CodeQL/secret-scanning alerts.

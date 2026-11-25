# Security Standards & High-Assurance Audit Baselines

Use this reference when a review or audit targets high-assurance, regulated, or enterprise-approval baselines.
Do **not** report a baseline deviation as a `confirmed` finding unless it satisfies the finding gate (`SKILL.md` §3);
missing baseline controls with no reachable exploit path are **hardening notes** or **compliance gaps** mapped here.

## Primary Frameworks & What Each Governs

| Authority / Standard | Scope & When to Apply | Concrete Controls to Verify |
|---|---|---|
| **OWASP Top 10:2025 & ASVS 5.0 (L1/L2/L3)** | Web, API, CLI/agent, and backend applications | Input canonicalization before validation; server-side authz; SSRF allowlisting + DNS rebinding protection; AEAD crypto; no swallowed errors on security paths. |
| **OWASP MASVS / MASTG** | iOS, macOS, Android mobile/desktop apps | Keychain accessibility (`ThisDeviceOnly` + `biometryCurrentSet`), `NSFileProtectionComplete`, ATS/TLS pinning, WebView JS bridge boundaries, IPC/URL-scheme validation. |
| **NIST SP 800-53 Rev. 5** | High-assurance systems, enterprise & government compliance | `AC` (least privilege, sandbox confinement), `AU` (tamper-evident secret-free logs), `CM` (hardened config/entitlements), `IA` (strong auth), `SC` (boundary protection, crypto), `SI` (input validation, memory safety). |
| **NIST SP 800-63B / 800-132 / 800-175B** | Passwords, KDFs, key lifecycle | Argon2id (OWASP / RFC 9106 parameters; high memory cost for offline vaults) or PBKDF2-HMAC-SHA256 where FIPS-mandated; zero plaintext secrets on disk; CSPRNG keys & unique nonces. |
| **CNSA 2.0 (NSA) & ANSSI RGS / Post-Quantum Guidance** | Long-lived secrets, TLS/VPN/vault key exchange & signing | Hybrid PQ key exchange (e.g., `X25519MLKEM768` / Apple CryptoKit X-Wing / Secure Enclave ML-KEM) for harvest-now-decrypt-later resistance; ML-DSA / SHA-384+ / AES-256-GCM / ChaCha20-Poly1305. |
| **NCSC / MI5 High-Threat Endpoint Guidance** | Desktop apps, developer tools, agent runtimes, browsers | Hardened Runtime without `allow-dyld-environment-variables`, `disable-library-validation`, or `allow-unsigned-executable-memory`; Seatbelt / Landlock / seccomp confinement; signed plugins/extensions; zero shell-interpolation command execution. |
| **SLSA Level 3 & Software Supply-Chain Security** | Build pipelines, CI workflows, distributed binaries & packages | Commit-SHA-pinned GitHub Actions, signed release tags/artifacts, reproducible lockfiles (`Package.resolved`), SBOMs (`swift package dump-package` / SPDX), verified binary checksums & signatures, minimal third-party transitive surface. |
| **ISO/IEC 27001:2022/2024 & Enterprise Software Approval** | Evaluating open-source or third-party tools for corporate adoption | License clarity (MIT/Apache-2.0), active maintenance, `SECURITY.md` disclosure policy, zero undocumented telemetry/network egress (GDPR / data minimization), pinned dependencies, least-privilege OS permissions, and zero unverified external code execution. |

## Dynamic Verification Toolkit (Sandboxed Local Copies Only)

When verifying candidates locally (strictly following `SKILL.md` §5 — isolated scratch copy, no network, dummy data, zero impact on live apps):

- **Memory & UB:** `clang -fsanitize=address,undefined,unsigned-integer-overflow` (ASan + UBSan) and Swift Thread Sanitizer (`-sanitize=thread`) on untrusted parsers, FFI, and C/SIMD kernels; differential fuzzing of SIMD vs. scalar reference implementations.
- **Apple binary & entitlement inspection:** `codesign -dvv --entitlements -`, `otool -l/-L/-D`, `sandbox-exec` verification against protected paths.
- **Process & I/O confinement:** `lsof` / `fs_usage` / `strace` (Linux) to confirm zero unexpected network sockets, file escapes, or symlink traversal outside declared roots.
- **Supply chain:** verify pinned revisions, SHA-pinned CI actions, license files, and `SECURITY.md`.

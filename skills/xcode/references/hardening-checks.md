# Hardening checks: libraries, memory tagging, checked pointer arithmetic, clang warnings, review surface

Detail for `SKILL.md` §7.3, §7.4 and §7.5. Read the section a step names when you reach it.

## Contents

- [Libraries and frameworks](#libraries-and-frameworks)
- [Hardware memory tagging](#hardware-memory-tagging)
- [Checked pointer arithmetic](#checked-pointer-arithmetic)
- [Clang safety warnings](#clang-safety-warnings)
- [Entitlement and Info.plist review surface](#entitlement-and-infoplist-review-surface)

---

## Libraries and frameworks

**Libraries and frameworks** (`framework`, `framework.static`, `library.static`, `library.dynamic`)
take no entitlements, because those are granted per process from the executable. They still get
the cascaded build settings. Keep pointer authentication on: it appends `arm64e` to
`ARCHS_STANDARD`, so the target ships a universal `arm64`/`arm64e` binary, and only one slice is
loaded at run time, so the larger file costs no RAM or speed. Warn when a library's Release
configuration sets `ONLY_ACTIVE_ARCH = YES`, which forces every consumer onto one slice; confirm
the slices with `lipo -archs`. See `references/universal-binaries-for-libraries.md`.

---

## Hardware memory tagging

**Hardware memory tagging** (`com.apple.security.hardened-process.checked-allocations`, with
`soft-mode` for a non-fatal rollout; soft mode alone does nothing) applies to `macosx`,
`iphoneos`/`iphonesimulator`, `watchos`, and `xros`/`xrsimulator` targets. Hardware backing is an
A19 chip or later (iPhone, iPad), M5 or later (Mac, Vision Pro), or S11 or later (Apple Watch).
Offer it only if Enhanced Security was applied to a matching target.

---

## Checked pointer arithmetic

**Checked pointer arithmetic** makes capable hardware poison a pointer whose arithmetic overflows
into the tag bits, which closes the way around memory tagging. It needs four things on an app
target: `ENABLE_HARDWARE_CHECKED_POINTER_ARITHMETIC_SLICE = YES` (adds the `arm64e.x1` slice;
defaults to `NO`, never cascades, set per target), `com.apple.security.hardened-process`,
`...checked-allocations` (run time enforcement requires memory tagging), and
`...checked-allocations.enforce-checked-pointer-arithmetic-overflow`. Keep
`ENABLE_POINTER_AUTHENTICATION = YES` too: with it off, the slice ships without an `arm64e`
fallback for devices that lack the hardware. Enforcement needs iOS on A20 Pro or later, or watchOS on S11 or later. A
library or framework sets the build setting only, and the consuming app's entitlements enforce it.

- Offer it only after memory tagging is on, or is being applied in the same run, and apply it
  last, since it reads the settings and entitlements the earlier steps write. Skip a target whose
  pointer authentication or Enhanced Security is explicitly off, or that opted out of the slice.
- **There is no soft mode**, and memory tagging's does not cover these faults: a latent
  pointer-arithmetic bug (a difference between pointers into two allocations, `uintptr_t`
  subtraction, an offset from a NULL base) terminates the app. Say so before enabling it.
- Verify with `lipo -archs`: `arm64 arm64e arm64e.x1`. Details in
  `references/checked-pointer-arithmetic.md`.

---

## Clang safety warnings

- `GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR`
- `GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE`
- `CLANG_WARN_IMPLICIT_FALLTHROUGH = YES`
- `GCC_WARN_64_TO_32_BIT_CONVERSION = YES`
- `GCC_TREAT_IMPLICIT_FUNCTION_DECLARATIONS_AS_ERRORS = YES` — C/ObjC/ObjC++ only
- `CLANG_ANALYZER_SECURITY_FLOATLOOPCOUNTER = YES` (runs in Build and analyze only)
- `CLANG_ANALYZER_SECURITY_INSECUREAPI_RAND = YES` (Build and analyze only)
- `CLANG_ANALYZER_SECURITY_INSECUREAPI_STRCPY = YES` (Build and analyze only)
- `CLANG_TIDY_BUGPRONE_REDUNDANT_BRANCH_CONDITION = YES` (Build and analyze only; installs nothing)

---

## Entitlement and Info.plist review surface

A pentester extracts the app's **effective entitlements** early, because they map the attack
surface. Auditing the same surface is a defensive win. Read the effective set from the signed
binary, not just a stray `.entitlements` file — they can differ:

```bash
codesign -d --entitlements :- "Payload/Target.app"
security cms -D -i "Payload/Target.app/embedded.mobileprovision"
```

Flag, and confirm each is intended:

- **`get-task-allow = true`** in a release build — the app is debuggable, so another process can
  attach and read its memory. Must be false in production.
- **Associated Domains** (`applinks:`) — each domain is a Universal Link entry point; cross-check
  against the AASA audit in `secure-coding` §8.4.
- **App Groups** and **keychain access groups** — every group is a shared container or shared
  keychain reachable by other targets and extensions. A wider group than needed widens the blast
  radius (`secure-coding` §8.1).
- **Unusual capabilities** and extension points beyond what the feature set justifies.

In `Info.plist`, review `CFBundleURLTypes` (registered custom schemes), `LSApplicationQueriesSchemes`,
`NSAppTransportSecurity`, `WKAppBoundDomains`, and `.appex` declarations — each is a surface the
`secure-coding` §8 controls govern.

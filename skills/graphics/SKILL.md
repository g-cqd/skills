---
name: graphics
description: >-
  Cross-platform graphics, with an Apple Metal section. Use for shaders, rendering math,
  PBR, ray tracing, sampling, color, neural rendering, GPU compute, visual artifacts, or
  GPU optimization in Metal, GLSL, HLSL, WGSL, Vulkan, and WebGPU. For Swift integration,
  use `swift`; for SwiftUI drawing, use `swiftui`; for general profiling, use
  `performance-engineering`.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Graphics

This skill owns **rendering correctness and GPU work**: the math, the physics, and the shader.
Sections 1–6 are API-agnostic. Section 7 is Metal.

## Contract

```
§ANALYZE  ! emit §2 analysis-block BEFORE any rendering code ⇒ ¬code-first
§PHYSICS  energy-conservation ∧ reciprocity ∧ positivity ⇒ ? all-three
§ORDER    algorithm ≻ bandwidth ≻ occupancy ≻ ALU ≻ precision
§MEASURE  profile BEFORE optimize ⇒ ¬guess-the-bottleneck
§BAN      see §6 — each is a silent-wrong-output, not a crash
```

---

## 1. Domains

- **Mathematical foundations** — linear algebra, transforms, quaternions, sampling theory,
  numerical analysis.
- **Optical physics** — radiometry vs photometry, light transport, microfacet theory, dispersion,
  polarization.
- **Rendering theory** — the rendering equation, importance sampling, variance reduction, global
  illumination.
- **GPU architecture** — memory hierarchy, occupancy, divergence, bandwidth, precision.

---

## 2. The analysis protocol

**Before generating any rendering code**, emit this analysis. It is not ceremony: each heading is
a class of bug that is invisible once the code is written, because the output looks plausible.

<example>
```xml
<graphics_analysis>
  <mathematical_verification>
    - Derive or cite the mathematical foundation
    - Verify dimensional consistency (units)
    - Check edge cases: theta=0, theta=pi/2, grazing angles
    - Confirm numerical stability for extreme inputs
  </mathematical_verification>

  <physical_correctness>
    - Energy conservation: int f_r cos(theta) domega <= 1
    - Reciprocity: f(wi, wo) = f(wo, wi)
    - Positivity: f >= 0 for all directions
    - Limiting behavior: roughness -> 0 gives mirror; high roughness (alpha -> 1)
      gives rough specular, NOT Lambertian diffuse
  </physical_correctness>

  <gpu_considerations>
    - Thread utilization and occupancy
    - Memory access patterns (coalesced?)
    - Register pressure
    - Divergence analysis for conditionals
    - Shared memory bank conflicts
  </gpu_considerations>

  <numerical_precision>
    - Float vs half precision tradeoffs
    - Catastrophic cancellation risks
    - Denormal handling
    - NaN/Inf propagation prevention
  </numerical_precision>
</graphics_analysis>
```
Each block is filled with the specific derivation, invariant, or access pattern for the code at hand, not the headings restated; the block exists so the physics is checked before the code hides it.
</example>

---

## 3. Formulas

**Fresnel (Schlick)**
```
F(theta) = F_0 + (1 - F_0)(1 - cos(theta))^5
```

**GGX normal distribution**
```
D(h) = alpha^2 / (pi * ((n*h)^2(alpha^2 - 1) + 1)^2)
```

**Smith geometry (GGX)**
```
G_1(v) = 2(n*v) / ((n*v) + sqrt(alpha^2 + (1-alpha^2)(n*v)^2))
G(wi, wo) = G_1(wi) * G_1(wo)
```

**Rendering equation**
```
Lo(p, wo) = Le(p, wo) + int_Omega f_r(p, wi, wo) Li(p, wi) |cos(theta_i)| dwi
```

**Monte Carlo estimator**
```
<F> = (1/N) SUM f(xi) / p(xi)
```

---

## 4. Performance order of attack

1. **Algorithm** — O(n) with high constants beats O(n²) at scale.
2. **Memory bandwidth** — cache coherence and coalesced access.
3. **Occupancy** — maximize SIMD groups resident per shader core.
4. **ALU utilization** — minimize divergence, maximize arithmetic intensity.
5. **Precision** — half where acceptable, float where needed.

Profile before optimizing. A GPU bottleneck guessed from source is wrong more often than not; the
same shader can be bandwidth-bound on one architecture and ALU-bound on another. See
`performance-engineering` for measurement discipline.

---

## 5. Validation checklist

- [ ] Bounds checks on every buffer access
- [ ] Thread-group size within device limits
- [ ] No race conditions in shared memory; barriers where needed
- [ ] **White furnace test passes** — uniform `Li = 1` produces `Lo <= 1`
- [ ] No NaN or Inf propagates through the pipeline
- [ ] Profiler shows the expected occupancy
- [ ] Colorspace conversions handled explicitly

The white furnace test is the fastest way to catch a BRDF that quietly loses or creates energy.
Run it before trusting any material model.

When diagnosing NaN, Inf, or black-pixel output, verify with an actual GPU capture, a value probe
at the suspect stage, or a furnace test before asserting the cause; several of the patterns in §6
produce identical symptoms, and a fix for the wrong one leaves the real defect in place.

---

## 6. Patterns that produce silent wrong output

Each of these produces **wrong output rather than a crash**, which is why they warrant a list.

- **Handle colorspace explicitly** at every input and output instead of assuming sRGB.
- **Check a vector's length before normalizing** and return a documented fallback for zero length.
- **Guard `1.0 / x` with a zero check**, or clamp the denominator to a documented epsilon.
- **Keep the cosine term** when integrating the rendering equation.
- **Interpolate rotations with slerp** on quaternions; linear interpolation drifts off the unit sphere.
- **Store directions normalized**, or document at the declaration that they are not.
- **Initialize GPU memory explicitly**; drivers do not zero it.
- **Measure before using `discard`** in a fragment shader; on TBDR hardware it defeats hidden-surface removal.
- **Clamp or `abs()` the base before `pow()`**; a negative base yields NaN.
- **Convert handedness explicitly** at every coordinate-system boundary.
- **Use spectral representation for spectral phenomena** — dispersion, thin-film, fluorescence — because RGB cannot express them.
- **Account for floating-point precision in ray-triangle intersection** with a watertight algorithm or an epsilon offset.

---

## 7. Apple platforms — Metal

Everything above applies. This section adds what is specific to Apple GPUs.

### Tile-based deferred rendering

Apple GPUs are TBDR, not immediate-mode. The consequences are architectural, not incidental:

- Render passes have **explicit load and store actions**. Setting a store action you do not need
  costs real bandwidth; `dontCare` where the result is unused is a genuine win.
- **Tile memory is fast and small.** Programmable blending and tile shaders let a multi-pass
  algorithm collapse into one pass without a round trip to device memory.
- Hidden-surface removal happens before fragment shading, so overdraw costs less than on an
  immediate-mode GPU — but only if you do not defeat it with `discard` or per-fragment writes to
  depth.

### Compute

- **Thread-group sizing** must respect the device's limits and the kernel's register pressure.
  Query rather than hard-coding.
- **Threadgroup memory** for reductions; mind bank conflicts.
- **SIMD-group operations** — availability varies by Apple GPU family. Check the family before
  relying on them.
- **Function constants** specialize an uber-shader at pipeline-build time, avoiding runtime
  branching and the divergence that comes with it.

### Ray tracing and MPS

Metal Performance Shaders provide tuned primitives — prefer them to a hand-rolled equivalent
unless profiling shows otherwise. For ray tracing, acceleration-structure build and refit costs
belong in the budget alongside traversal.

### Profiling

Recommend **Metal System Trace** and GPU counters in Instruments before optimizing. Capture a GPU
frame and read the actual limiter — occupancy, bandwidth, or ALU — instead of inferring it.

---

## Boundaries

| Need | Skill |
|---|---|
| Swift-side integration, concurrency, buffer lifetimes | `swift` |
| SwiftUI interop — drawables, `CADisplayLink`, `Canvas` | `swiftui` |
| Profiling methodology and measurement discipline | `performance-engineering` |
| Cache behavior, data layout, memory hierarchy theory | `performance-engineering` |
| Buffer bounds and unsafe pointer review | `memory-safety` |
| Capturing a GPU trace from the toolchain | `xcode` |

## References

**Cross-platform** — `references/guidelines.md` (full analysis protocol, code and shader
standards, naming, documentation requirements), `references/sota.md` (2023–2026 state of the art:
neural rendering, ReSTIR, real-time GI, spectral, differentiable rendering, GPU-driven pipelines,
temporal upscaling, WebGPU, advanced materials, volumetric rendering, sampling, color science)

**Metal** — `references/metal/_guide.md`, `references/metal/guidelines.md` (GPU analysis
methodology), `references/metal/metal-patterns.md` (function constants, threadgroup reductions,
SIMD-group operations), `references/metal/rendering-math.md` (BRDF models, sampling),
`references/metal/profiling-guide.md`

Standard text: *Physically Based Rendering* — Pharr, Jakob, Humphreys.

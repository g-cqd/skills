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

This skill covers **rendering correctness and GPU work**: the math, the physics, and the shader.
Sections 1–5 are API-agnostic. Section 6 is Metal.

## Contract

```
§ANALYZE  ! emit §1 analysis-block BEFORE code that computes a rendered|GPU value ⇒ ¬code-first
          change alters no computed value (rename, comment, formatting, labels)
          ⇒ state that in one line ∧ skip the block
§PHYSICS  energy-conservation ∧ reciprocity ∧ positivity ⇒ ! check all-three
§ORDER    algorithm ≻ bandwidth ≻ occupancy ≻ ALU ≻ precision
§MEASURE  profile BEFORE optimize ⇒ ¬guess-the-bottleneck
§BAN      see §5 — each is a silent-wrong-output, not a crash
```

---

## 1. The analysis protocol

**Before you write or change code that computes a rendered or GPU value** (shading, sampling,
transforms, color conversion, buffer access), emit this analysis. For a change that alters no
computed value (rename, comment, formatting, labels), state that in one line and skip the block.
Each heading is a class of bug that the finished code hides, because the wrong output still looks
plausible.

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
Fill each block with the derivation, invariant, or access pattern of the code at hand. Do not
restate the headings. If a block does not apply, write 'n/a' and the reason in one line.
</example>

---

## 2. Formulas

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

## 3. Performance order of attack

Optimize in this order:

1. **Algorithm**.
2. **Memory bandwidth** — cache coherence and coalesced access.
3. **Occupancy** — raise occupancy until the profiler shows the kernel is not latency-bound.
4. **ALU utilization** — minimize divergence, maximize arithmetic intensity.
5. **Precision** — half where the result stays within the required accuracy, float elsewhere.

Profile before optimizing. Do not name a GPU bottleneck from the source alone: the same shader can
be bandwidth-bound on one architecture and ALU-bound on another. If you cannot capture, state the
likely limiter as a hypothesis and name the capture that would confirm it. See
`performance-engineering` for measurement method.

---

## 4. Validation checklist

- [ ] Bounds checks on every buffer access
- [ ] Thread-group size within device limits
- [ ] No race conditions in shared memory; barriers where needed
- [ ] **White furnace test passes** — uniform `Li = 1` produces `Lo <= 1`
- [ ] No NaN or Inf propagates through the pipeline
- [ ] Profiler shows the expected occupancy
- [ ] Colorspace conversions handled explicitly

Run the white furnace test on each new or changed material model (BRDF) before you rely on it.
The test catches a BRDF that loses or creates energy.

When you diagnose NaN, Inf, or black-pixel output, confirm the cause with a GPU capture, a value
probe at the suspect stage, or a furnace test before you state it. Several patterns in §5 produce
identical symptoms, and a fix for the wrong one leaves the real defect in place.

---

## 5. Patterns that produce silent wrong output

Each of these produces **wrong output, not a crash**.

- **Handle colorspace explicitly** at every input and output. Do not assume sRGB.
- **Check a vector's length before normalizing**, and return a documented fallback for zero length.
- **Guard `1.0 / x` with a zero check**, or clamp the denominator to a documented epsilon.
- **Keep the cosine term** when integrating the rendering equation.
- **Interpolate rotations with slerp** on quaternions; linear interpolation drifts off the unit sphere.
- **Store directions normalized**, or document at the declaration that they are not.
- **Initialize GPU memory explicitly**; drivers do not zero it.
- **Measure before using `discard`** in a fragment shader; on TBDR hardware `discard` defeats hidden-surface removal.
- **Clamp or `abs()` the base before `pow()`**; a negative base yields NaN.
- **Convert handedness explicitly** at every coordinate-system boundary.
- **Use a spectral representation for spectral phenomena** (dispersion, thin-film, fluorescence); RGB cannot express them.
- **Account for floating-point precision in ray-triangle intersection** with a watertight algorithm or an epsilon offset.

---

## 6. Apple platforms — Metal

Sections 1–5 apply. This section adds what is specific to Apple GPUs.

### Tile-based deferred rendering

Apple GPUs are TBDR, not immediate-mode. Consequences:

- Render passes have **explicit load and store actions**. Set the store action to `dontCare`
  when the result is unused; an unneeded store costs bandwidth.
- **Tile memory is fast and small.** Programmable blending and tile shaders let a multi-pass
  algorithm run as one pass, with no round trip to device memory.
- Hidden-surface removal runs before fragment shading, so overdraw costs less than on an
  immediate-mode GPU. `discard` and per-fragment depth writes disable this benefit.

### Compute

- **Thread-group sizing** must respect the device's limits and the kernel's register pressure.
  Query the limits at runtime; do not hard-code them.
- **Threadgroup memory** for reductions; avoid bank conflicts.
- **SIMD-group operations** — availability varies by Apple GPU family. Check the family before
  you use them.
- **Function constants** specialize an uber-shader at pipeline-build time. This removes runtime
  branching and the divergence it causes.

### Ray tracing and MPS

Use Metal Performance Shaders primitives instead of a hand-written equivalent, unless profiling
shows the hand-written version is faster. For ray tracing, include acceleration-structure build
and refit costs in the frame budget, together with traversal.

### Profiling

Recommend **Metal System Trace** and GPU counters in Instruments before optimizing. Capture a GPU
frame and read the actual limiter (occupancy, bandwidth, or ALU). Do not infer the limiter. If
you cannot capture, follow the fallback in §3.

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

# State-of-the-Art Rendering Techniques (2023–2026)

This reference covers frontier graphics R&D. Each section includes key papers, practical significance, common pitfalls, and code-level considerations.

---

## Table of Contents
1. [Neural Rendering & Gaussian Splatting](#1-neural-rendering--gaussian-splatting)
2. [Real-Time Global Illumination (ReSTIR, DDGI, Lumen)](#2-real-time-global-illumination)
3. [Ray Tracing Hardware & Software](#3-ray-tracing-hardware--software)
4. [Advanced Material Models (OpenPBR, MaterialX)](#4-advanced-material-models)
5. [Spectral Rendering](#5-spectral-rendering)
6. [GPU Compute Advances](#6-gpu-compute-advances)
7. [Volumetric Rendering](#7-volumetric-rendering)
8. [Advanced Sampling](#8-advanced-sampling)
9. [Color Science](#9-color-science)
10. [Differentiable Rendering](#10-differentiable-rendering)
11. [Temporal Techniques](#11-temporal-techniques)
12. [WebGPU](#12-webgpu)
13. [Cross-Cutting Themes](#13-cross-cutting-themes)

---

## 1. Neural Rendering & Gaussian Splatting

### Key Papers
- **Kerbl et al. (SIGGRAPH 2023)** — "3D Gaussian Splatting for Real-Time Radiance Field Rendering." Foundational 3DGS paper: rasterization of anisotropic 3D Gaussians replaces volumetric ray marching.
- **Müller et al. (SIGGRAPH 2022)** — "Instant Neural Graphics Primitives with a Multiresolution Hash Encoding" (Instant-NGP). Multi-resolution hash tables cut NeRF training from hours to seconds.
- **Barron et al. (ICCV 2023)** — "Zip-NeRF." Combines mip-NeRF 360 anti-aliasing with hash grid speed.
- **Yu et al. (CVPR 2024)** — "Mip-Splatting: Alias-free 3D Gaussian Splatting." Addresses aliasing via 3D smoothing and 2D Mip filters.
- **Huang et al. (SIGGRAPH 2024)** — "2D Gaussian Splatting for Geometrically Accurate Radiance Fields." 2D surfels for better surface reconstruction.
- **Niedermayr et al. (2024)** — "Compressed 3D Gaussian Splatting for Accelerated Novel View Synthesis." Tackles the storage problem (hundreds of MB per scene).
- **Luiten et al. (3DV 2024)** — "Dynamic 3D Gaussians." Extends 3DGS to dynamic scenes.

### Why It Matters
3DGS has replaced NeRFs for most real-time novel view synthesis. It uses classical rasterization of alpha-blended splats, is trivially parallelizable on existing GPU raster pipelines, trains in minutes on a single GPU, and renders at >100 fps. Immediate applications: telepresence, game asset scanning, VR environment capture, digital twins.

### Pitfalls
- **Splat count explosion**: Naive densification produces millions of Gaussians. Pruning and compression are essential — uncompressed scenes can balloon to 500MB+.
- **Popping artifacts**: Gaussians popping in/out during camera motion from depth-sorting errors. Proper per-pixel depth sorting or approximate OIT is critical.
- **Depth ordering**: 3DGS uses per-splat sorting, not per-fragment — causes order-dependent blending errors for overlapping translucent Gaussians. Tile-based sorting helps but doesn't fully solve it.
- **SH memory**: Spherical harmonics coefficients per Gaussian consume up to 48 floats (degree-3 SH). Many compression schemes target SH bands first.
- **Training instability**: Adam optimizer learning rates for position, scale, rotation, opacity, and SH are all different and scene-dependent. Failure modes include floaters and under-reconstruction.

### Code-Level
- The CUDA rasterizer uses a custom tile-based sorter with radix sort per tile. Porting to Vulkan compute or WebGPU requires reimplementing this.
- SH evaluation at render time: degree-3 SH requires 16 coefficients per color channel (48 total). Evaluate with Horner-like schemes for numerical stability.
- Gaussian covariance is stored as quaternion (rotation) + 3D scale, projected to 2D screen-space covariance. The projection Jacobian is a known source of numerical issues at extreme scales.
- Instant-NGP hash: `h(x) = (x1 * p1 XOR x2 * p2 XOR x3 * p3) mod T`. Simple but collision-prone — the network learns to resolve collisions, but performance degrades if the table is too small.

---

## 2. Real-Time Global Illumination

### Key Papers
- **Bitterli, Wyman et al. (SIGGRAPH 2020)** — "Spatiotemporal Reservoir Resampling for Real-Time Ray Tracing with Dynamic Direct Lighting." The original ReSTIR paper.
- **Lin, Kettunen et al. (SIGGRAPH 2022)** — "Generalized Resampled Importance Sampling: Foundations of ReSTIR." Proves unbiasedness conditions.
- **Ouyang, Liu, Kettunen, Pharr, Pantaleoni (HPG 2021)** — "ReSTIR GI: Path Resampling for Real-Time Path Tracing." Extends ReSTIR to multi-bounce indirect.
- **Majercik et al. (JCGT 2019)** — "Dynamic Diffuse Global Illumination with Ray-Traced Irradiance Fields." The DDGI paper.
- **Majercik et al. (JCGT 2021)** — "Scaling Probe-Based Real-Time Dynamic Global Illumination for Production."
- **Wright (GDC 2022, Epic)** — "Radiance Caching for Real-Time Global Illumination." Lumen's radiance caching architecture.
- **Hillaire (SIGGRAPH 2022)** — "Lumen: Real-Time Global Illumination in Unreal Engine 5."

### Why It Matters
ReSTIR is arguably the most important algorithmic advance in real-time rendering since deferred shading. It samples from distributions with millions of light sources at near-constant cost by maintaining per-pixel reservoirs shared spatially and temporally. Combined with denoising, it enables real-time path-traced direct lighting with thousands of dynamic emissive triangles.

DDGI provides stable, low-noise diffuse GI via a probe grid updated every frame with few rays per probe. Lumen (UE5) combines software RT against SDFs, hardware RT for detail, screen-space tracing, and radiance caching into a hybrid GI system.

### Pitfalls
- **ReSTIR bias**: Naive spatial reuse introduces bias because the resampling PDF doesn't account for visibility differences between neighbors. The bias correction using `1/M` weighting vs. pairwise MIS is critical — without it, light leaks are rampant.
- **ReSTIR GI temporal lag**: Reservoirs accumulate history, causing indirect lighting to lag behind fast motion. Clamp `M` (reservoir sample count) — typically M_max = 20–30.
- **DDGI probe placement**: Uniform grids waste probes in empty space. Cascaded grids or adaptive placement is needed for large scenes.
- **DDGI light leaks**: Probes inside thin walls sample both sides. Probe relocation, visibility weighting (secondary octahedral map), and normal-based biasing are all needed.
- **Lumen SDF limitations**: Software tracing against mesh distance fields has limited angular resolution and misses small-scale detail. Hardware RT fallback is essential for quality.

### Code-Level
- ReSTIR reservoir struct: `{light_sample, weight_sum, M, W}` — 16–32 bytes per pixel. Two buffers ping-ponged for temporal reuse.
- Spatial reuse radius: ~30 pixels typical. Too large → overblurring. Too small → insufficient variance reduction.
- DDGI probes store irradiance in octahedral maps (6×6 or 8×8 texels, RGBA16F) and visibility/distance in a separate map (16×16 texels, RG16F). All probes atlas-packed into a single texture.
- DDGI octahedral map border texels must be carefully copied (1-pixel border with wrapping) to avoid seam artifacts during bilinear filtering.

---

## 3. Ray Tracing Hardware & Software

### Key Papers
- **Nvidia Ada/Blackwell RT Cores (3rd/4th gen)**: Opacity Micro-Map (OMM) and Displaced Micro-Mesh (DMM) engines for hardware-accelerated alpha-tested geometry.
- **Wyman (GTC 2023)** — "Opacity Micro-Maps." Per-microtriangle opacity states (opaque/transparent/unknown) skip alpha-test shader invocations during traversal.
- **Schied et al. (HPG 2017)** — "Spatiotemporal Variance-Guided Filtering" (SVGF). The foundational real-time denoiser.
- **Nvidia NRD (2021–present)** — Open-source library: ReBLUR and ReLAX (both denoise diffuse+specular; ReLAX is optimized for ReSTIR/RTXDI signals), SIGMA (shadow) denoisers.

### Why It Matters
Hardware RT has moved from "can we trace any rays?" (2018–2020) to "how do we efficiently trace millions of rays per frame for full GI?" (2023+). The bottleneck shifted from traversal to shading and denoising. Opacity Micro-Maps reduce foliage/particle RT cost by 2–10×.

Inline ray tracing (`TraceRayInline` / `gl_RayQuery`) allows RT from any shader stage without full RT pipeline state object overhead — enables hybrid approaches.

### Pitfalls
- **BVH build cost**: BLAS builds for dynamic geometry are expensive every frame. Prefer refit over rebuild when topology doesn't change.
- **Incoherent rays kill performance**: Secondary rays are scattered. Ray sorting by direction (octant binning) or by hit material improves warp occupancy 2–3×.
- **SVGF ghosting**: Fast motion or disocclusion causes stale temporal data. Motion vector–based reprojection with disocclusion detection is mandatory. NRD uses surface-space and virtual motion vectors (for reflections).
- **NRD tuning**: ReLAX and ReBLUR have dozens of parameters. Defaults are conservative — per-title tuning is expected.
- **SER (Shader Execution Reordering)**: Nvidia Ada feature reordering RT shader invocations by hit. 1.5–2× speedup on incoherent secondary rays but requires opt-in via `nvapi`/`VK_NV_ray_tracing_invocation_reorder`.

### Code-Level
- TLAS instance limit: typically 2^24. For large scenes, instance merging or multi-level instancing is necessary.
- `RAY_FLAG_ACCEPT_FIRST_HIT_AND_END_SEARCH` (DX12) / `gl_RayFlagsTerminateOnFirstHitEXT` (Vulkan) is critical for shadow rays — often 2–3× faster.
- BVH compaction (`ALLOW_COMPACTION` flag) reduces BLAS memory by ~50%. Always compact static geometry.
- Inline RT (`RayQuery`) is often faster for simple visibility queries (shadow, AO) — avoids shader table indirection.

---

## 4. Advanced Material Models

### Key Papers
- **Georgiev, Harvey et al. (ASWF, 2024)** — "OpenPBR Surface Shading Model" v1.0. Industry-standard uber-shader from the Academy Software Foundation.
- **MaterialX 1.39 (2024)** — Open standard for material definition and interchange. Adopted by USD, Blender, most DCC tools.
- **Zeltner, Burley, Chiang (SIGGRAPH 2022 Talk)** — "Practical Multiple-Scattering Sheen Using Linearly Transformed Cosines."
- **Weier, Belcour (2020)** — "Rendering Layered Materials with Anisotropic Interfaces." Energy-conserving layered model.
- **Kuznetsov, Hašan, et al. (SIGGRAPH 2021–2022)** — Neural material representations. Compact neural representations of measured BRDFs.
- **Zeltner et al. (EGSR 2024)** — Multi-lobe BSDF energy conservation.

### Why It Matters
OpenPBR is becoming the interchange standard, superseding ad-hoc Disney BRDF variants. It defines ~30 parameters covering base, specular, transmission, subsurface, coat, sheen, thin-film, and emission lobes. MaterialX provides the node-graph shading language.

Energy conservation in multi-lobe models is a persistent correctness issue — when adding a coat layer, the energy reflected by the coat must be subtracted from what reaches lower layers.

### Pitfalls
- **Multi-lobe energy loss**: A dielectric coat with Fresnel reflectance F_coat should attenuate lower layers by `(1 - F_coat)^2` (entry + exit). Many implementations forget the exit attenuation.
- **Metallic Fresnel**: Schlick is inaccurate for colored metals at grazing angles. Full complex Fresnel or Lazányi–Szirmay-Kalos correction needed for gold, copper.
- **Sheen energy compensation**: The sheen lobe (Charlie/Estevez-Kulla) absorbs energy at normal incidence. Without furnace-test-derived compensation, dark fabrics are too dark.
- **MaterialX compilation**: Node graphs compiled to target shading languages via `MaterialXGenShader` can produce verbose shaders without optimization passes.

### Code-Level
- OpenPBR specular uses GGX with Smith height-correlated masking-shadowing. Clamp roughness minimum to ~0.001 to handle mirror singularity.
- Split-sum approximation (Karis 2013): pre-integrate specular BRDF into 2D LUT (roughness × NdotV), typically RGBA16F 256×256. Shared across all materials.
- Thin-film interference: evaluate spectral phase shifts at 3 wavelengths even in RGB renderers, convert via sensitivity functions.
- Neural BRDF compression: MERL database materials (33MB each) → ~100KB via small MLPs, but consider inference cost during rendering.

---

## 5. Spectral Rendering

### Key Papers
- **Wilkie, Nawaz, Droske, Weidlich, Hanika (EGSR 2014)** — Hero Wavelength Spectral Sampling.
- **Jakob, Hanika (SIGGRAPH 2019)** — "A Low-Dimensional Function Space for Efficiently Sampling Colors." Mitsuba 3's spectral uplifting via smooth 3D lookup from RGB to spectral basis coefficients.
- **Jung, Hanika, Dachsbacher (2019)** — "Spectral Uplifting from RGB: Practical Approach."
- **Peters, Merzbach et al. (2019)** — "Using Fourier Analysis to Accelerate Spectral Rendering."

### Why It Matters
Spectral rendering eliminates metamerism artifacts and enables physically correct dispersion (prisms, diamonds), fluorescence (whitening agents, UV-reactive materials), and thin-film interference. Hero wavelength sampling traces a primary wavelength per path with stratified secondary wavelengths. Production renderers (Weta Manuka, RenderMan, Mitsuba 3) support it.

### Pitfalls
- **Spectral uplifting is ill-posed**: A given RGB maps to infinitely many spectra. Jakob-Hanika finds a smooth spectrum, but it's not unique. For fluorescence/metamerism, measured spectral data is required.
- **Hero wavelength MIS**: Weights must account for spectral PDF — incorrect weighting causes chromatic noise.
- **Fluorescence requires bi-spectral BSDFs**: `f(lambda_in, lambda_out)` — wavelength can change at each bounce. Re-radiation matrix approach is standard but expensive.
- **Dispersion**: Each hero wavelength follows a different refracted direction through glass — no amortization across wavelengths at transmissive interfaces.

### Code-Level
- Hero wavelength: sample `lambda_hero ~ uniform(380nm, 780nm)`, derive companions at `lambda_hero + k*(780-380)/N` mod visible range. N=4 typical (matches SIMD width).
- Spectral → XYZ: integrate `X = ∫ S(λ) x̄(λ) dλ` using CIE 1931 2-degree observer. Minimum 5nm resolution.
- Mitsuba 3 uses sigmoid-based parametric spectrum with 3 coefficients — compact and smooth.
- Clamp uplifted spectra to zero (negative values are physically meaningless), but be aware this changes effective RGB.

---

## 6. GPU Compute Advances

### Key Papers
- **Wihlidal (SIGGRAPH 2021, 2023)** — Nanite deep dive and mesh shaders in Nanite.
- **Lottes (GDC 2023)** — "Work Graphs in Direct3D 12." GPU-driven work scheduling without CPU roundtrips.
- **Ubisoft Scalar (GDC 2024)** — GPU-driven rendering with mesh shaders and visibility buffers.
- **Haar & Aaltonen (SIGGRAPH 2015)** — "GPU-Driven Rendering Pipelines." Foundational GPU-driven architecture.

### Mesh Shaders
Replace vertex/tessellation/geometry pipeline with amplification+mesh shader model. Amplification shader performs per-meshlet culling (frustum, occlusion, backface, cone-of-normals), mesh shader outputs primitives. Enables GPU-driven culling at meshlet granularity (64–128 triangles).

### Work Graphs (DX12)
Allow shaders to spawn other shaders on GPU without CPU involvement. Enables recursive algorithms (BVH construction, adaptive tessellation, tree traversals) entirely on GPU. Successor to ExecuteIndirect with much more flexibility. Nascent as of 2026 — AMD RDNA 3+ and Nvidia Ada+ support in hardware.

### Nanite-Style Virtualized Geometry
Persistent BVH of mesh clusters, GPU-driven LOD selection per-cluster, software rasterization for small triangles (<2×2 pixels), hardware rasterization for larger ones. Visibility buffer (64-bit: depth + cluster_id + triangle_id) decouples geometry from shading.

### Pitfalls
- **Mesh shader output limits**: 256 vertices, 256 primitives in DX12. Exceeding silently corrupts output on some drivers.
- **Visibility buffer material fetch**: Full-screen pass re-derives all attributes from triangle vertices via barycentrics ("deferred texturing"). Memory bandwidth intensive.
- **Bindless hazards**: Descriptor indexing eliminates binding overhead but out-of-bounds accesses cause GPU hangs with no error.
- **Work Graphs maturity**: Programming model is complex (backing memory management, node I/O record definitions), debugging tools still maturing.

### Code-Level
- Meshlet struct: `{vertex_indices[max_verts], primitive_indices[max_prims*3], vertex_count, prim_count, bounding_sphere, cone_apex, cone_axis, cone_cutoff}`. Meshoptimizer generates these.
- GPU-driven pattern: cull compute → indirect dispatch/draw → visibility buffer → material resolve. Single large storage buffer for all transforms.
- Subgroup operations (`WaveActiveSum`, `subgroupAdd`) essential for reductions. Check `gl_SubgroupSize` — 32 on Nvidia, 32/64 on AMD.
- Cooperative matrix ops (`VK_KHR_cooperative_matrix`, WMMA) enable tensor cores from compute shaders — useful for neural inference in rendering.

---

## 7. Volumetric Rendering

### Key Papers
- **Miller, Georgiev, Jarosz (SIGGRAPH 2019)** — "A Null-Scattering Path Integral Formulation of Light Transport." Unified null-scattering framework for heterogeneous media.
- **Novák et al. (SIGGRAPH 2018 course)** — "Monte Carlo Methods for Volumetric Light Transport." Comprehensive survey.
- **Hillaire (2020/2021)** — "A Scalable and Production Ready Sky and Atmosphere Rendering Technique." UE5 volumetric clouds/atmosphere.
- **Wrenninge, Villemin, Hery (2017)** — Weta's production volume rendering with anisotropic phase functions.

### Why It Matters
Null-tracking (null-scattering) is now the standard for unbiased volume rendering in heterogeneous participating media (smoke, clouds, fire). It introduces a fictitious "null" scattering coefficient making total extinction constant (equal to majorant), enabling Woodcock/delta tracking while maintaining correct physics.

### Pitfalls
- **Majorant selection**: Must be ≥ maximum extinction in the medium. Single global majorant wastes samples in sparse regions — use a grid of local majorants for spatially varying media.
- **Chromatic extinction**: Each wavelength has different extinction. Track using maximum over all wavelengths as majorant (hero wavelength null-scattering).
- **Transmittance estimation**: Ratio tracking provides lower variance than delta tracking for optically thick media. For real-time, use Beer-Lambert with density-accumulated in fixed steps.
- **Temporal noise in clouds**: Per-frame jitter of ray-march start + temporal accumulation. Blue noise offsets help significantly.

### Code-Level
- Delta tracking loop: `while (t < t_max) { t -= log(1 - rand()) / sigma_majorant; if (sigma_real(t) / sigma_majorant > rand()) { /* real scatter */ } else { /* null, continue */ } }`
- Real-time clouds: 3D Worley+Perlin noise (128³ base, 32³ detail). Sample base at low frequency, detail only where density > threshold.
- Phase function: Henyey-Greenstein standard. For clouds, dual-lobe HG: `p(θ) = mix * HG(g1, θ) + (1-mix) * HG(g2, θ)` captures silver-lining effects.
- Deep compositing (OpenEXR deep): store multiple (depth, alpha, color) samples per pixel sorted by depth. Compression and sample merging critical for storage.

---

## 8. Advanced Sampling

### Key Papers
- **Christensen, Kensler, Kilpatrick (EG 2018)** — "Progressive Multi-Jittered Sample Sequences." PMJ with stratification in all projections.
- **Ahmed, Wonka et al. (2020–2023)** — Blue-noise sampling and error distribution. "Screen-Space Blue-Noise Diffusion of Monte Carlo Sampling Error."
- **Wolfe, Georgiev et al. (2022–2023)** — "Scalable Blue Noise via Rank-1 Lattices." Spatio-temporal blue noise for denoising.
- **Müller, Gross, Novák (SIGGRAPH 2017)** — "Practical Path Guiding in Production." SD-trees for path guiding.
- **Rath et al. (SIGGRAPH 2022)** — "EARS: Efficiency-Aware Russian Roulette and Splitting." Adaptive sampling based on per-pixel efficiency.
- **Grittmann, Georgiev, Slusallek (2023)** — Optimal MIS weighting.

### Why It Matters
Blue noise sampling is critical for real-time: human vision is less sensitive to blue-noise (high-frequency, unstructured) error than white noise or structured artifacts. Distributing MC error as blue noise in screen space and across frames produces results that look clean before denoising and denoise much better.

Path guiding (directing rays toward important light-carrying directions via learned distributions) has moved to production — Blender Cycles shipped it in 3.4 (2022).

### Pitfalls
- **Blue noise temporal decorrelation**: Same texture every frame causes temporal correlation. Animate via offset or use spatio-temporal blue noise (rank-1 lattice).
- **PMJ dimensionality**: PMJ02bn has excellent 2D projections but higher-dimensional stratification degrades. For high-dimensional integrals (many bounces), use Sobol with Owen scrambling for dimensions > 2.
- **Path guiding overhead**: Building/querying SD-trees has non-trivial cost. For simple scenes (mostly direct lighting), guiding can be slower. Enable adaptively.
- **Aggressive Russian roulette**: Standard throughput-based RR terminates low-contribution paths, but dark regions need proportional attention. EARS considers variance contribution.

### Code-Level
- Owen-scrambled Sobol: use Burley (2020) hash-based scramble — `hash(index ^ scramble_seed)` per dimension. Laine-Karras (2011) is simpler but lower quality.
- Blue noise textures: 128×128 or 256×256 scalar, tiled with per-pixel random offset: `texture[pixel % size].r` + per-frame temporal offset. Void-and-cluster algorithm generates these.
- Weighted Reservoir Sampling (ReSTIR core): `for each sample s with weight w: total += w; if (rand() < w/total) selected = s;` — O(1) memory, O(N) time.
- MIS power heuristic (β=2): `w_i = (n_i * p_i)² / Σ(n_j * p_j)²`. Often better than balance heuristic in practice.

---

## 9. Color Science

### Key Papers & Standards
- **ACES / ACEScg** — Academy Color Encoding System. AP1 primaries, linear. Standard working space for production rendering. ACES 2.0 with updated RRT+ODT ongoing 2024–2025.
- **AgX (Troy Sobotka; Blender 4.0 adaptation by Eary Chow)** — Open filmic tonemapper replacing ACES default look. Adopted by Blender 4.0+.
- **Oklab (Ottosson, 2020)** — Perceptual color space replacing CIELAB. Better uniformity especially in blues. Oklch is polar form.
- **ITU-R BT.2100** — PQ (Perceptual Quantizer) and HLG transfer functions for HDR.

### Why It Matters
Color science errors are among the most pervasive in graphics. Working in the wrong color space (lighting in sRGB instead of linear), incorrect tonemapping, and gamut mismatches cause perceptually wrong colors even when math is "correct."

### Pitfalls
- **sRGB without linearization**: Textures in sRGB must use `_SRGB` formats for hardware conversion. Lighting in sRGB space → too dark shadows, too bright highlights, wrong blending.
- **Wide gamut negatives**: ACEScg can represent colors outside sRGB. Converting produces negative channels — use soft gamut mapping, not clamping.
- **HDR paper white**: PQ maps 0–10,000 nits. Wrong paper white level (typically 80–200 nits) makes all SDR content too dim or blown out.
- **AgX vs ACES**: AgX desaturates toward white in highlights (physically motivated). ACES default ODT shifts hue in saturated highlights ("blue LED" problem → purple). AgX is simpler and more robust but has a different look.
- **Alpha blending space**: Pre-multiplied alpha compositing in gamma space produces dark fringes. Always composite in linear.

### Code-Level
- sRGB OETF (exact): `x <= 0.0031308 ? 12.92*x : 1.055*pow(x, 1/2.4) - 0.055`. The piecewise function matters — `pow(x, 1/2.2)` causes banding in darks.
- Oklab: linear sRGB → LMS (3×3 matrix) → cube root → Lab (3×3 matrix). The cube root approximates perceptual lightness.
- AgX pipeline: (1) log2 encode scene-referred linear values, (2) apply 1D/3D LUT for filmic curve, (3) convert to display space. Blender's implementation is a good reference.
- PQ EOTF: `L = (max(N^(1/78.84375) - c1, 0) / (c2 - c3*N^(1/78.84375)))^(1/0.1593017578125)`. Constants are precise — do not approximate.

---

## 10. Differentiable Rendering

### Key Papers
- **Jakob, Speierer et al. (SIGGRAPH Asia 2022)** — "Mitsuba 3: A Retargetable Forward and Inverse Renderer."
- **Bangaru, Li et al. (SIGGRAPH Asia 2023)** — "Differentiable Rendering of Neural SDFs through Reparameterization." Handles visibility discontinuities.
- **Nimier-David et al. (SIGGRAPH 2020)** — "Radiative Backpropagation." Adjoint method for fast differentiable rendering.
- **Li et al. (SIGGRAPH Asia 2018)** — "Differentiable Monte Carlo Ray Tracing through Edge Sampling." Foundational edge-sampling paper.
- **Dr.Jit** — JIT compiler for differentiable computation underlying Mitsuba 3.

### Why It Matters
Computes gradients of rendered images w.r.t. scene parameters (materials, geometry, lighting, camera). Enables inverse rendering, material optimization, neural scene representations, and deep learning integration. Mitsuba 3 + Dr.Jit is the leading research platform.

### Pitfalls
- **Visibility discontinuities**: Naive differentiation ignores silhouettes/shadow boundaries (Dirac deltas). Reparameterization or edge sampling is required — ignoring this gives incorrect/missing gradients for geometry optimization.
- **Noisy gradients**: Few samples per iteration for efficiency. Adam handles this but learning rate tuning is critical.
- **Dr.Jit megakernel**: Traces all operations into one large kernel. Complex scenes → long JIT compile (minutes). Break computation with `dr.eval()`.
- **Memory**: Reverse-mode autodiff stores the forward graph. Many bounces → tens of GB. Use gradient checkpointing and limit bounce depth.

### Code-Level
- Mitsuba 3 variants: `cuda_ad_rgb`, `cuda_ad_spectral`, `llvm_ad_rgb`. Set before importing.
- Basic inverse rendering: `params = mi.traverse(scene); opt = mi.ad.Adam(lr=0.01, params={...}); image = mi.render(scene, params, spp=16); loss = dr.mean(dr.sqr(image - target)); dr.backward(loss); opt.step(); params.update(opt);`
- Reparameterization: in Mitsuba 3, reparameterized differentiable rendering is selected via the integrator, e.g. `prb_reparam`, not a `mi.render()` flag.
- Use `dr.detach()` liberally to prevent gradient flow through operations that don't need it (RR decisions, PDF computations for MIS).

---

## 11. Temporal Techniques

### Key Papers & Systems
- **Nvidia DLSS 2–4 (2020–2025)** — Neural temporal upscaling + frame generation. DLSS 3: AI-generated intermediate frames. DLSS 4 (Blackwell): Multi Frame Generation (up to 3 frames per rendered frame).
- **AMD FSR 3.0/3.1 (2023–2024)** — Temporal upscaling + frame generation, open source. FSR 3.1 decoupled frame gen from upscaling.
- **Intel XeSS 2 (2025)** — Temporal upscaler using XMX hardware on Arc, DP4a fallback for other vendors.
- **DLSS Ray Reconstruction (2023+)** — Single neural network denoises AND upscales simultaneously, replacing separate denoiser + upscaler pipeline.
- **Yang, Liu, Salvi (EG 2020)** — "A Survey of Temporal Antialiasing Techniques."

### Why It Matters
Neural temporal upscaling has changed the performance equation. Games render at 1080p and upscale to 4K, recovering most quality at 2–4× speed. DLSS-RR eliminates denoiser artifacts by taking noisy low-res RT input and producing clean high-res output in one step.

### Pitfalls
- **Motion vector accuracy**: All temporal techniques require per-pixel motion vectors. Errors cause ghosting. Dynamic objects need per-object velocity buffers — camera motion alone is insufficient.
- **Jitter patterns**: Temporal upscaling requires sub-pixel camera jitter each frame. DLSS expects Halton(2,3). Wrong jitter → blurriness.
- **Frame generation latency**: Synthetic frames increase apparent FPS but add latency. Nvidia Reflex mitigates by reducing render queue depth.
- **Reactive/transparency masks**: Semi-transparent surfaces confuse upscalers (motion vectors from opaque surface behind). FSR has "reactive mask", DLSS has transparency hints. Not providing these → ghosting on particles/foliage.

### Code-Level
- Velocity buffer: screen-space UV displacement (current − previous). R16G16_SFLOAT. Vertex shader: `velocity = (currentClip.xy/currentClip.w - prevClip.xy/prevClip.w) * 0.5`.
- Camera jitter: add `(jitterX * 2/renderWidth, jitterY * 2/renderHeight)` to projection matrix elements (2,0)/(2,1) row-major. Subtract jitter during velocity computation.
- DLSS integration: ~200 lines DX12/Vulkan. Inputs: color (jittered, LDR/HDR), depth, motion vectors, exposure. Output: upscaled image.
- FSR 3: open source C++/HLSL/GLSL. Frame generation needs swap-chain proxy for frame pacing.

---

## 12. WebGPU

### Key Standards
- **W3C WebGPU Specification** — Candidate Recommendation 2023. Ships in Chrome 113+, Firefox 141+ (Jul 2025), Safari 26+ (Sep 2025).
- **WGSL Specification** — WebGPU Shading Language with Rust-like syntax.

### Why It Matters
Modern GPU API for the web mirroring Vulkan/Metal/DX12 concepts: command encoders, bind groups, pipeline layouts, compute shaders. Exposes compute (absent in WebGL), storage buffers, indirect dispatch — enabling GPU-driven rendering and GPGPU on the web.

### Pitfalls
- **No hardware RT API**: RT must be done via compute shaders with software BVH traversal. Viable for progressive/offline, not competitive with native for real-time.
- **Storage buffer limits**: `maxStorageBufferBindingSize` typically 128–256MB — much less than native.
- **No subgroups in base spec**: Behind `subgroups` feature flag, not widely available as of early 2026.
- **WGSL uniform alignment**: 16-byte alignment for struct members in uniform buffers. `vec3<f32>` takes 16 bytes, not 12.
- **Shader compilation latency**: Large WGSL shaders take seconds to compile. Use `createRenderPipelineAsync` for caching.
- **No multisampled storage textures**: MSAA resolve must use render pipeline, not compute.

### Code-Level
- Compute shader: `@compute @workgroup_size(256) fn main(@builtin(global_invocation_id) id: vec3<u32>) { ... }`
- Resources: `@group(0) @binding(0) var<storage, read_write> data: array<f32>;`
- No pointer arithmetic, no recursion, no implicit casts. Use `bitcast<f32>(uint_val)` for reinterpretation.
- Buffer readback is async only: `buffer.mapAsync(GPUMapMode.READ).then(...)`. No synchronous readback.
- Max dispatch: `maxComputeWorkGroupsPerDimension` = 65535. Use multi-dimensional dispatch for larger.
- Timestamp queries (`timestamp-query` feature) for GPU profiling — subject to browser timing mitigations.

---

## 13. Cross-Cutting Themes

### Neural + Classical Hybrid Pipelines
Dominant trend: combining classical rendering with neural components (neural denoising, materials, radiance caching, LOD). Neural components run on tensor cores, classical on shader cores — data sharing is the integration challenge.

### GPU-Driven Everything
CPU becomes scene manager submitting a single indirect dispatch. Culling, LOD selection, material sorting, draw call generation — all on GPU. Work Graphs and mesh shaders are key enablers. Requires rethinking from "CPU iterates objects" to "GPU processes flat buffers."

### Convergence of Real-Time and Offline
ReSTIR, path guiding, and neural denoising bring real-time close to offline quality for many scenes. Remaining gap: complex light transport (caustics, dense participating media, high-order scattering) and samples per pixel.

### Open Standards Ascendant
OpenPBR, MaterialX, USD, OpenEXR, ACES — VFX industry open standards adopted by real-time engines. Reduces asset pipeline friction.

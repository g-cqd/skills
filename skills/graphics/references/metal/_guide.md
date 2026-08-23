# GPU & Metal — Domain Guide

Correctness first, then performance, always measured. Use the pre-implementation `<gpu_analysis>` block before writing GPU/rendering code.

## Workflow
1. Read `guidelines.md` for GPU analysis methodology and Metal standards
2. Output `<gpu_analysis>` block before writing GPU/rendering code
3. Verify mathematical foundations and numerical stability
4. Follow Metal shader standards and forbidden patterns
5. Use `rendering-math.md` for BRDF models and sampling strategies
6. Use `metal-patterns.md` for advanced Metal idioms
7. Use `profiling-guide.md` for GPU profiling methodology

## Detailed References
- `guidelines.md` — Core GPU engineering standards, analysis methodology
- `metal-patterns.md` — Advanced Metal patterns and idioms
- `rendering-math.md` — Critical formulas and derivations
- `profiling-guide.md` — GPU profiling methodology

# Metal GPU Profiling Guide

## 1. Profiling Methodology

### The Golden Rule
**Measure → Identify → Optimize → Re-measure**

Never optimize without profiling first. GPU performance is counterintuitive.

### Performance Hierarchy (Optimize in This Order)
1. **Algorithm Complexity** - O(n) beats O(n²) regardless of constants
2. **Memory Bandwidth** - Often the true bottleneck
3. **Occupancy** - More threads hiding latency
4. **ALU Utilization** - Actual compute efficiency
5. **Instruction-Level** - Micro-optimizations (last resort)

## 2. Xcode GPU Profiling Tools

### GPU Frame Capture
1. **Product → Profile** or click the camera icon in debug bar
2. Select **Metal System Trace** or **Game Performance** template
3. Capture representative workload (not just first frame)
4. Analyze in Metal Debugger

### Key Metrics to Monitor

| Metric | Target | Warning Signs |
|--------|--------|---------------|
| **Frame Time** | <16.67ms (60fps), <8.33ms (120fps) | Consistent misses |
| **GPU Utilization** | 80-95% | <50% (CPU bound) or 100% (overloaded) |
| **Occupancy** | >50% | <25% (register pressure) |
| **ALU Utilization** | >70% | <40% (memory bound) |
| **Bandwidth** | <80% peak | Sustained 100% |
| **Shader Time** | Proportional to complexity | Unexpected hotspots |

### Shader Cost Graph (Xcode 15+)
Visual breakdown of shader execution cost:
- **Green**: Efficient code paths
- **Yellow**: Moderate cost
- **Red**: Hot paths requiring attention

### Performance Heat Maps
Shows per-pixel shader cost overlaid on rendered output:
- Identify expensive regions
- Correlate with visual complexity
- Find overdraw issues

## 3. Apple GPU Architecture Insights

### SIMD Group (Warp) Behavior
- Apple GPUs execute 32 threads per SIMD group
- All threads execute same instruction (SIMT)
- **Divergence**: When threads take different branches, all paths execute serially

```metal
// BAD: High divergence
if (tid % 2 == 0) {
    doExpensiveA();
} else {
    doExpensiveB();
}

// GOOD: Minimize divergence
doComputeForAll();
if (needsExtra[tid]) {
    doExtra();
}
```

### Register Pressure
- Limited registers per SIMD group
- More registers = fewer concurrent groups = lower occupancy
- **Symptoms**: Low occupancy in profiler, "Register spilling" warnings

```metal
// BAD: Many live variables
float a = compute1();
float b = compute2();
float c = compute3();
float d = compute4();
float e = compute5();
float result = a + b + c + d + e;

// GOOD: Reduce live variables
float result = compute1();
result += compute2();
result += compute3();
result += compute4();
result += compute5();
```

### Memory Hierarchy

| Memory Type | Latency | Bandwidth | Size | Use Case |
|-------------|---------|-----------|------|----------|
| Registers | 1 cycle | Highest | ~32KB/SIMD | Local variables |
| Threadgroup | ~20 cycles | Very High | 32KB | Shared data |
| L1 Cache | ~50 cycles | High | 128KB | Automatic |
| L2 Cache | ~150 cycles | Medium | 8-32MB | Automatic |
| Device Memory | ~400 cycles | Lower | GBs | Buffers, textures |

### Occupancy Calculation
```
Occupancy = Active SIMD Groups / Maximum SIMD Groups

Maximum depends on:
- Registers used per thread
- Threadgroup memory used
- Thread group size
```

Target: >50% occupancy for latency hiding

## 4. Common Bottlenecks & Solutions

### Memory Bandwidth Limited

**Symptoms:**
- High bandwidth utilization (>80%)
- Low ALU utilization (<40%)
- Performance scales with data size

**Solutions:**
```metal
// 1. Use smaller data types
// BAD
device float4* data;

// GOOD (if precision allows)
device half4* data;

// 2. Pack data efficiently
// BAD: Wasteful alignment
struct Vertex {
    float3 position;  // 12 bytes + 4 padding
    float3 normal;    // 12 bytes + 4 padding
    float2 uv;        // 8 bytes
};                    // 40 bytes total

// GOOD: Packed
struct PackedVertex {
    packed_float3 position;  // 12 bytes
    packed_float3 normal;    // 12 bytes
    float2 uv;               // 8 bytes
};                           // 32 bytes total

// 3. Use texture for 2D/3D data (hardware caching)
texture2d<float> instead of device float*
```

### Compute Limited (ALU Bound)

**Symptoms:**
- High ALU utilization (>80%)
- Low bandwidth utilization
- Performance scales with instruction count

**Solutions:**
```metal
// 1. Use fast math where acceptable
#pragma METAL_FAST_MATH 1

// 2. Use half precision
half3 color = half3(input.rgb);

// 3. Precompute expensive operations
// BAD: Repeated computation
for (int i = 0; i < N; i++) {
    result += sin(angle) * data[i];
}

// GOOD: Precompute
float sinAngle = sin(angle);
for (int i = 0; i < N; i++) {
    result += sinAngle * data[i];
}

// 4. Use hardware intrinsics
// BAD
float invSqrt = 1.0 / sqrt(x);

// GOOD
float invSqrt = rsqrt(x);  // Single instruction
```

### Occupancy Limited

**Symptoms:**
- Low occupancy (<25%)
- Shader uses many registers
- Complex control flow

**Solutions:**
```metal
// 1. Reduce register usage (see above)

// 2. Split complex shaders
// Instead of one mega-shader, use multi-pass

// 3. Reduce threadgroup memory
// Only allocate what's needed
threadgroup float shared[ACTUAL_SIZE];  // Not MAX_POSSIBLE

// 4. Use function constants to eliminate dead code
constant bool useFeatureA [[function_constant(0)]];
```

### Divergence Limited

**Symptoms:**
- Low efficiency on branches
- Uneven workload across threads

**Solutions:**
```metal
// 1. Sort work by type before dispatch
// Process similar items together

// 2. Use branch-free math where possible
// BAD
if (x < 0) x = 0;
if (x > 1) x = 1;

// GOOD
x = saturate(x);

// 3. Extract uniform conditions
constant bool globalFlag [[function_constant(0)]];
if (globalFlag) {  // All threads take same path
    // ...
}
```

## 5. GPU Counter Reference (Apple Family 9+)

### Shader Profiler Counters

| Counter | Description | Target |
|---------|-------------|--------|
| `GPU Active` | % time GPU is running | >90% |
| `ALU Active` | % time ALUs are computing | >60% |
| `Memory Read` | Bytes read from memory | Minimize |
| `Memory Write` | Bytes written to memory | Minimize |
| `Occupancy` | SIMD group utilization | >50% |
| `Register Spills` | Register overflow to memory | 0 |
| `Cache Hit Rate` | L1/L2 cache efficiency | >80% |

### Ray Tracing Counters

| Counter | Description | Target |
|---------|-------------|--------|
| `BVH Box Tests` | Bounding box intersections | Lower is better |
| `BVH Triangle Tests` | Triangle intersections | Lower is better |
| `Ray Divergence` | Coherence of ray directions | Lower is better |

## 6. Profiling Checklist

### Before Optimization
- [ ] Captured representative workload (not first frame)
- [ ] Identified actual bottleneck (memory/compute/occupancy)
- [ ] Established baseline metrics
- [ ] Reproduced on target device (not just Simulator)

### During Optimization
- [ ] Changed one thing at a time
- [ ] Measured after each change
- [ ] Verified correctness maintained
- [ ] Documented the optimization rationale

### After Optimization
- [ ] Compared metrics to baseline
- [ ] Tested on multiple devices (iPhone, iPad, Mac)
- [ ] Verified no regressions in other areas
- [ ] Committed with performance data in message

## 7. Device-Specific Considerations

### Apple Silicon Unified Memory
- CPU and GPU share memory pool
- Avoid unnecessary copies between CPU/GPU
- Use `.storageModeShared` for frequently accessed data

### Apple Family Feature Matrix

| Feature | Family 7+ | Family 8+ | Family 9+ |
|---------|-----------|-----------|-----------|
| Ray Tracing | Basic | Enhanced | Hardware RT |
| Mesh Shaders | No | Yes | Yes |
| 64-bit Atomics | No | Yes | Yes |
| Dynamic Libraries | No | Yes | Yes |
| Shader Profiler | Basic | Enhanced | Full |

### Thermal Considerations
- Sustained workloads may throttle
- Test with hot device (after extended use)
- Consider power efficiency, not just peak performance

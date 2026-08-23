# Advanced Metal Patterns & Idioms

## 1. Resource Management

### Triple Buffering for CPU-GPU Synchronization
```swift
final class TripleBuffer<T> {
    private let buffers: [MTLBuffer]
    private var currentIndex = 0
    private let semaphore: DispatchSemaphore

    init(device: MTLDevice, count: Int = 3) {
        semaphore = DispatchSemaphore(value: count)
        buffers = (0..<count).map { _ in
            device.makeBuffer(length: MemoryLayout<T>.stride, options: .storageModeShared)!
        }
    }

    func nextBuffer() -> MTLBuffer {
        semaphore.wait()
        let buffer = buffers[currentIndex]
        currentIndex = (currentIndex + 1) % buffers.count
        return buffer
    }

    func signal() {
        semaphore.signal()
    }
}
```

### Argument Buffers for Bindless Resources
```metal
struct Material {
    texture2d<float> albedo;
    texture2d<float> normal;
    texture2d<float> roughness;
    sampler textureSampler;
};

fragment float4 pbrFragment(
    VertexOut in [[stage_in]],
    device const Material* materials [[buffer(0)]],
    constant uint& materialIndex [[buffer(1)]]
) {
    Material mat = materials[materialIndex];
    float4 albedo = mat.albedo.sample(mat.textureSampler, in.uv);
    // ...
}
```

## 2. Compute Pipeline Patterns

### Indirect Dispatch for Variable Workloads
```swift
// CPU side: create indirect buffer
struct MTLDispatchThreadgroupsIndirectArguments {
    var threadgroupsPerGrid: (UInt32, UInt32, UInt32)
}

let indirectBuffer = device.makeBuffer(
    length: MemoryLayout<MTLDispatchThreadgroupsIndirectArguments>.stride,
    options: .storageModeShared
)!

// GPU side: a kernel writes the dispatch size
kernel void computeDispatchSize(
    device MTLDispatchThreadgroupsIndirectArguments* args [[buffer(0)]],
    device const atomic_uint* workCount [[buffer(1)]]
) {
    uint count = atomic_load_explicit(workCount, memory_order_relaxed);
    uint threadgroups = (count + 255) / 256;
    args->threadgroupsPerGrid = uint3(threadgroups, 1, 1);
}

// Dispatch indirectly
encoder.dispatchThreadgroups(
    indirectBuffer: indirectBuffer,
    indirectBufferOffset: 0,
    threadsPerThreadgroup: MTLSize(width: 256, height: 1, depth: 1)
)
```

### Persistent Threads for Stream Compaction
```metal
kernel void persistentCompact(
    device const float4* input [[buffer(0)]],
    device float4* output [[buffer(1)]],
    device atomic_uint* outputCounter [[buffer(2)]],
    device atomic_uint* inputCounter [[buffer(3)]],
    constant uint& totalItems [[buffer(4)]],
    uint tid [[thread_position_in_grid]]
) {
    while (true) {
        uint idx = atomic_fetch_add_explicit(inputCounter, 1, memory_order_relaxed);
        if (idx >= totalItems) break;

        float4 value = input[idx];
        if (shouldKeep(value)) {
            uint outIdx = atomic_fetch_add_explicit(outputCounter, 1, memory_order_relaxed);
            output[outIdx] = value;
        }
    }
}
```

## 3. Ray Tracing Patterns (Metal Ray Tracing)

### Acceleration Structure Building
```swift
// Create geometry descriptor
let geometryDesc = MTLAccelerationStructureTriangleGeometryDescriptor()
geometryDesc.vertexBuffer = vertexBuffer
geometryDesc.vertexStride = MemoryLayout<SIMD3<Float>>.stride
geometryDesc.indexBuffer = indexBuffer
geometryDesc.indexType = .uint32
geometryDesc.triangleCount = triangleCount

// Create primitive acceleration structure descriptor
let primDesc = MTLPrimitiveAccelerationStructureDescriptor()
primDesc.geometryDescriptors = [geometryDesc]

// Build sizes
let sizes = device.accelerationStructureSizes(descriptor: primDesc)
let accelerationStructure = device.makeAccelerationStructure(size: sizes.accelerationStructureSize)!
let scratchBuffer = device.makeBuffer(length: sizes.buildScratchBufferSize, options: .storageModePrivate)!

// Build
let commandBuffer = commandQueue.makeCommandBuffer()!
let encoder = commandBuffer.makeAccelerationStructureCommandEncoder()!
encoder.build(
    accelerationStructure: accelerationStructure,
    descriptor: primDesc,
    scratchBuffer: scratchBuffer,
    scratchBufferOffset: 0
)
encoder.endEncoding()
commandBuffer.commit()
```

### Ray Tracing Kernel
```metal
kernel void rayTrace(
    instance_acceleration_structure accelerationStructure [[buffer(0)]],
    device const Ray* rays [[buffer(1)]],
    device Intersection* intersections [[buffer(2)]],
    uint tid [[thread_position_in_grid]]
) {
    ray r;
    r.origin = rays[tid].origin;
    r.direction = rays[tid].direction;
    r.min_distance = 0.001;
    r.max_distance = INFINITY;

    intersector<triangle_data> intersector;
    intersector.accept_any_intersection(false);
    intersector.force_opacity(forced_opacity::opaque);

    intersection_result<triangle_data> result = intersector.intersect(r, accelerationStructure);

    if (result.type == intersection_type::triangle) {
        intersections[tid].distance = result.distance;
        intersections[tid].primitiveIndex = result.primitive_id;
        intersections[tid].coordinates = result.triangle_barycentric_coord;
    } else {
        intersections[tid].distance = -1.0;
    }
}
```

## 4. Memory Access Optimization

### Coalesced Memory Access
```metal
// BAD: Strided access (each thread reads every Nth element)
kernel void badAccess(device float* data, uint tid [[thread_position_in_grid]]) {
    float value = data[tid * stride];  // Non-coalesced
}

// GOOD: Sequential access (threads read consecutive elements)
kernel void goodAccess(device float* data, uint tid [[thread_position_in_grid]]) {
    float value = data[tid];  // Coalesced
}
```

### Structure of Arrays vs Array of Structures
```metal
// BAD: AoS - poor cache utilization when accessing single field
struct Particle {
    float3 position;
    float3 velocity;
    float mass;
};
device Particle* particles;

// GOOD: SoA - excellent cache utilization for field-specific access
device float3* positions;
device float3* velocities;
device float* masses;
```

### Texture Memory for Spatial Locality
```metal
// Use textures for 2D/3D data with spatial access patterns
kernel void imageProcess(
    texture2d<float, access::read> input [[texture(0)]],
    texture2d<float, access::write> output [[texture(1)]],
    uint2 gid [[thread_position_in_grid]]
) {
    // Hardware-accelerated bilinear filtering
    constexpr sampler s(filter::linear, address::clamp_to_edge);

    float2 uv = float2(gid) / float2(input.get_width(), input.get_height());
    float4 color = input.sample(s, uv);

    output.write(color, gid);
}
```

## 5. Synchronization Patterns

### Memory Barriers
```metal
// Threadgroup barrier - all threads in group reach this point
threadgroup_barrier(mem_flags::mem_threadgroup);

// Device memory barrier - ensures writes visible to other threadgroups
threadgroup_barrier(mem_flags::mem_device);

// Texture barrier - for read-after-write on textures
threadgroup_barrier(mem_flags::mem_texture);

// Combined flags
threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device);
```

### Atomic Operations
```metal
// Counter increment
device atomic_uint* counter;
uint index = atomic_fetch_add_explicit(counter, 1, memory_order_relaxed);

// Compare and exchange for lock-free data structures
bool success = atomic_compare_exchange_weak_explicit(
    &value,
    &expected,
    desired,
    memory_order_release,
    memory_order_relaxed
);

// Min/max reduction
atomic_fetch_min_explicit(&minValue, localMin, memory_order_relaxed);
atomic_fetch_max_explicit(&maxValue, localMax, memory_order_relaxed);
```

## 6. Debugging Techniques

### GPU Capture Annotations
```swift
// Mark regions in GPU capture
encoder.pushDebugGroup("Shadow Pass")
// ... shadow rendering ...
encoder.popDebugGroup()

encoder.pushDebugGroup("Main Pass")
// ... main rendering ...
encoder.popDebugGroup()
```

### Shader Validation Buffer
```metal
// Debug output buffer for shader inspection
kernel void debugKernel(
    device DebugInfo* debug [[buffer(10)]],
    uint tid [[thread_position_in_grid]]
) {
    debug[tid].threadId = tid;
    debug[tid].intermediateValue = someComputation;
    debug[tid].flags = errorFlags;
}
```

## 7. MetalFX Upscaling Integration

### Spatial Upscaling
```swift
let spatialScaler = MTLFXSpatialScalerDescriptor()
spatialScaler.inputWidth = renderWidth
spatialScaler.inputHeight = renderHeight
spatialScaler.outputWidth = displayWidth
spatialScaler.outputHeight = displayHeight
spatialScaler.colorTextureFormat = .rgba16Float
spatialScaler.outputTextureFormat = .rgba16Float
spatialScaler.colorProcessingMode = .perceptual

let scaler = spatialScaler.makeSpatialScaler(device: device)!

// In render loop
scaler.colorTexture = renderTarget
scaler.outputTexture = displayTexture
scaler.encode(commandBuffer: commandBuffer)
```

### Temporal Upscaling
```swift
let temporalScaler = MTLFXTemporalScalerDescriptor()
temporalScaler.inputWidth = renderWidth
temporalScaler.inputHeight = renderHeight
temporalScaler.outputWidth = displayWidth
temporalScaler.outputHeight = displayHeight
temporalScaler.colorTextureFormat = .rgba16Float
temporalScaler.depthTextureFormat = .depth32Float
temporalScaler.motionTextureFormat = .rg16Float
temporalScaler.outputTextureFormat = .rgba16Float

let scaler = temporalScaler.makeTemporalScaler(device: device)!

// Requires motion vectors and depth
scaler.colorTexture = colorTexture
scaler.depthTexture = depthTexture
scaler.motionTexture = motionVectorTexture
scaler.outputTexture = displayTexture
scaler.reset = isFirstFrame
scaler.encode(commandBuffer: commandBuffer)
```

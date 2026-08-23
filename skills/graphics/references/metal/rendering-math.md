# Rendering Mathematics Reference

## 1. Core Equations

### The Rendering Equation (Kajiya 1986)
```
Lo(p, ωo) = Le(p, ωo) + ∫_Ω f_r(p, ωi, ωo) Li(p, ωi) |cos(θi)| dωi
```

Where:
- `Lo` = outgoing radiance at point p in direction ωo
- `Le` = emitted radiance
- `f_r` = BRDF (bidirectional reflectance distribution function)
- `Li` = incoming radiance
- `cos(θi)` = `n · ωi` (cosine of incident angle)
- `Ω` = hemisphere of incoming directions

### Monte Carlo Estimator
```
⟨F⟩ = (1/N) Σ f(xi) / p(xi)
```

Variance reduction through importance sampling: choose `p(x)` proportional to `f(x)`.

## 2. BRDF Models

### Lambertian Diffuse
```metal
float3 lambertianBRDF(float3 albedo) {
    return albedo / M_PI_F;
}

// PDF for cosine-weighted hemisphere sampling
float lambertianPDF(float cosTheta) {
    return cosTheta / M_PI_F;
}
```

### Fresnel Equations

**Schlick Approximation:**
```metal
float3 fresnelSchlick(float cosTheta, float3 F0) {
    return F0 + (1.0 - F0) * pow(1.0 - cosTheta, 5.0);
}

// With roughness for IBL
float3 fresnelSchlickRoughness(float cosTheta, float3 F0, float roughness) {
    return F0 + (max(float3(1.0 - roughness), F0) - F0) * pow(1.0 - cosTheta, 5.0);
}
```

**Exact Fresnel (Dielectric):**
```metal
// eta convention: eta = n_incident / n_transmitted (e.g. 1.0/1.5 entering glass from air)
float fresnelDielectric(float cosThetaI, float eta) {
    float sinThetaTSq = eta * eta * (1.0 - cosThetaI * cosThetaI);

    if (sinThetaTSq > 1.0) {
        return 1.0;  // Total internal reflection
    }

    float cosThetaT = sqrt(1.0 - sinThetaTSq);

    float Rs = (eta * cosThetaI - cosThetaT) / (eta * cosThetaI + cosThetaT);
    float Rp = (cosThetaI - eta * cosThetaT) / (cosThetaI + eta * cosThetaT);

    return 0.5 * (Rs * Rs + Rp * Rp);
}
```

### GGX/Trowbridge-Reitz Microfacet

**Normal Distribution Function (NDF):**
```metal
float distributionGGX(float NdotH, float roughness) {
    float a = roughness * roughness;
    float a2 = a * a;
    float NdotH2 = NdotH * NdotH;

    float denom = NdotH2 * (a2 - 1.0) + 1.0;
    return a2 / (M_PI_F * denom * denom);
}
```

**Smith Geometry Function:**
```metal
float geometrySchlickGGX(float NdotV, float roughness) {
    float r = roughness + 1.0;
    float k = (r * r) / 8.0;  // For direct lighting
    // float k = (roughness * roughness) / 2.0;  // For IBL

    return NdotV / (NdotV * (1.0 - k) + k);
}

float geometrySmith(float NdotV, float NdotL, float roughness) {
    float ggx1 = geometrySchlickGGX(NdotV, roughness);
    float ggx2 = geometrySchlickGGX(NdotL, roughness);
    return ggx1 * ggx2;
}
```

**Complete Cook-Torrance BRDF:**
```metal
float3 cookTorranceBRDF(
    float3 N, float3 V, float3 L, float3 H,
    float3 albedo, float metallic, float roughness
) {
    float NdotV = max(dot(N, V), 0.0001);
    float NdotL = max(dot(N, L), 0.0001);
    float NdotH = max(dot(N, H), 0.0);
    float HdotV = max(dot(H, V), 0.0);

    // F0 for dielectrics is 0.04, for metals it's the albedo
    float3 F0 = mix(float3(0.04), albedo, metallic);

    float D = distributionGGX(NdotH, roughness);
    float G = geometrySmith(NdotV, NdotL, roughness);
    float3 F = fresnelSchlick(HdotV, F0);

    // Specular BRDF
    float3 numerator = D * G * F;
    float denominator = 4.0 * NdotV * NdotL + 0.0001;
    float3 specular = numerator / denominator;

    // Diffuse BRDF (energy conservation)
    float3 kD = (1.0 - F) * (1.0 - metallic);
    float3 diffuse = kD * albedo / M_PI_F;

    return diffuse + specular;
}
```

## 3. Sampling Strategies

### Uniform Hemisphere Sampling
```metal
float3 sampleHemisphereUniform(float2 xi) {
    float phi = 2.0 * M_PI_F * xi.x;
    float cosTheta = xi.y;
    float sinTheta = sqrt(1.0 - cosTheta * cosTheta);

    return float3(
        sinTheta * cos(phi),
        sinTheta * sin(phi),
        cosTheta
    );
}

float uniformHemispherePDF() {
    return 1.0 / (2.0 * M_PI_F);
}
```

### Cosine-Weighted Hemisphere (Malley's Method)
```metal
float3 sampleHemisphereCosine(float2 xi) {
    // Map to disk using polar mapping (Shirley-Chiu concentric mapping is the lower-distortion alternative)
    float r = sqrt(xi.x);
    float phi = 2.0 * M_PI_F * xi.y;

    float x = r * cos(phi);
    float y = r * sin(phi);
    float z = sqrt(max(0.0, 1.0 - xi.x));  // cos(theta) = sqrt(1 - r^2)

    return float3(x, y, z);
}

float cosineHemispherePDF(float cosTheta) {
    return cosTheta / M_PI_F;
}
```

### GGX Importance Sampling
```metal
float3 sampleGGX(float2 xi, float roughness) {
    float a = roughness * roughness;

    float phi = 2.0 * M_PI_F * xi.x;
    float cosTheta = sqrt((1.0 - xi.y) / (1.0 + (a * a - 1.0) * xi.y));
    float sinTheta = sqrt(1.0 - cosTheta * cosTheta);

    // Half-vector in tangent space
    float3 H = float3(
        sinTheta * cos(phi),
        sinTheta * sin(phi),
        cosTheta
    );

    return H;
}

float ggxPDF(float NdotH, float HdotV, float roughness) {
    float D = distributionGGX(NdotH, roughness);
    return D * NdotH / (4.0 * HdotV);
}
```

### Building Tangent Space
```metal
float3x3 buildTBN(float3 N) {
    float3 up = abs(N.z) < 0.999 ? float3(0, 0, 1) : float3(1, 0, 0);
    float3 T = normalize(cross(up, N));
    float3 B = cross(N, T);
    return float3x3(T, B, N);
}

float3 tangentToWorld(float3 v, float3 N) {
    float3x3 TBN = buildTBN(N);
    return TBN * v;
}
```

## 4. Color Space Conversions

### Linear to sRGB
```metal
float3 linearToSRGB(float3 linear) {
    float3 low = linear * 12.92;
    float3 high = 1.055 * pow(linear, 1.0 / 2.4) - 0.055;
    return mix(low, high, step(0.0031308, linear));
}
```

### sRGB to Linear
```metal
float3 sRGBToLinear(float3 srgb) {
    float3 low = srgb / 12.92;
    float3 high = pow((srgb + 0.055) / 1.055, 2.4);
    return mix(low, high, step(0.04045, srgb));
}
```

### ACES Tone Mapping
```metal
float3 ACESFilm(float3 x) {
    float a = 2.51;
    float b = 0.03;
    float c = 2.43;
    float d = 0.59;
    float e = 0.14;
    return saturate((x * (a * x + b)) / (x * (c * x + d) + e));
}
```

## 5. Geometric Utilities

### Safe Normalize
```metal
float3 safeNormalize(float3 v) {
    float len = length(v);
    return len > 0.0 ? v / len : float3(0, 0, 1);
}
```

### Reflect and Refract
```metal
float3 reflect(float3 I, float3 N) {
    return I - 2.0 * dot(N, I) * N;
}

float3 refract(float3 I, float3 N, float eta) {
    float cosI = -dot(N, I);
    float sin2T = eta * eta * (1.0 - cosI * cosI);

    if (sin2T > 1.0) {
        return reflect(I, N);  // Total internal reflection
    }

    float cosT = sqrt(1.0 - sin2T);
    return eta * I + (eta * cosI - cosT) * N;
}
```

### Quaternion Rotation
```metal
float4 quaternionFromAxisAngle(float3 axis, float angle) {
    float halfAngle = angle * 0.5;
    return float4(axis * sin(halfAngle), cos(halfAngle));
}

float3 rotateByQuaternion(float3 v, float4 q) {
    float3 t = 2.0 * cross(q.xyz, v);
    return v + q.w * t + cross(q.xyz, t);
}

float4 slerp(float4 a, float4 b, float t) {
    float cosTheta = dot(a, b);

    if (cosTheta < 0.0) {
        b = -b;
        cosTheta = -cosTheta;
    }

    if (cosTheta > 0.9995) {
        return normalize(mix(a, b, t));  // Linear interpolation for small angles
    }

    float theta = acos(cosTheta);
    float sinTheta = sin(theta);

    float wa = sin((1.0 - t) * theta) / sinTheta;
    float wb = sin(t * theta) / sinTheta;

    return wa * a + wb * b;
}
```

## 6. Ray-Primitive Intersections

### Ray-Sphere
```metal
bool intersectSphere(float3 origin, float3 dir, float3 center, float radius, thread float& t) {
    float3 oc = origin - center;
    float b = dot(oc, dir);
    float c = dot(oc, oc) - radius * radius;

    float discriminant = b * b - c;
    if (discriminant < 0.0) return false;

    float sqrtD = sqrt(discriminant);
    t = -b - sqrtD;

    if (t < 0.0) {
        t = -b + sqrtD;
        if (t < 0.0) return false;
    }

    return true;
}
```

### Ray-AABB (Slab Method)
```metal
bool intersectAABB(float3 origin, float3 invDir, float3 aabbMin, float3 aabbMax, thread float& tMin, thread float& tMax) {
    float3 t0 = (aabbMin - origin) * invDir;
    float3 t1 = (aabbMax - origin) * invDir;

    float3 tSmall = min(t0, t1);
    float3 tBig = max(t0, t1);

    tMin = max(max(tSmall.x, tSmall.y), tSmall.z);
    tMax = min(min(tBig.x, tBig.y), tBig.z);

    return tMax >= tMin && tMax >= 0.0;
}
```

### Ray-Triangle (Möller-Trumbore)
```metal
bool intersectTriangle(
    float3 origin, float3 dir,
    float3 v0, float3 v1, float3 v2,
    thread float& t, thread float2& uv
) {
    float3 e1 = v1 - v0;
    float3 e2 = v2 - v0;

    float3 h = cross(dir, e2);
    float a = dot(e1, h);

    if (abs(a) < 1e-8) return false;  // Parallel to triangle

    float f = 1.0 / a;
    float3 s = origin - v0;
    float u = f * dot(s, h);

    if (u < 0.0 || u > 1.0) return false;

    float3 q = cross(s, e1);
    float v = f * dot(dir, q);

    if (v < 0.0 || u + v > 1.0) return false;

    t = f * dot(e2, q);
    uv = float2(u, v);

    return t > 1e-8;
}
```

## 7. Random Number Generation

### PCG Hash (Fast, High Quality)
```metal
uint pcg(uint state) {
    state = state * 747796405u + 2891336453u;
    uint word = ((state >> ((state >> 28) + 4)) ^ state) * 277803737u;
    return (word >> 22) ^ word;
}

float randomFloat(thread uint& seed) {
    seed = pcg(seed);
    return float(seed) * 2.3283064365386963e-10;  // 1/2^32, result in [0, 1)
}

float2 random2D(thread uint& seed) {
    return float2(randomFloat(seed), randomFloat(seed));
}
```

### Low-Discrepancy Sequences (Halton)
```metal
float halton(uint index, uint base) {
    float f = 1.0;
    float r = 0.0;

    while (index > 0) {
        f /= float(base);
        r += f * float(index % base);
        index /= base;
    }

    return r;
}

float2 halton2D(uint index) {
    return float2(halton(index, 2), halton(index, 3));
}
```

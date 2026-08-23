# Performance & Benchmark Testing

## What It Is

Performance testing measures **execution time, memory usage, and resource consumption** to detect regressions and validate optimization. Benchmark tests establish baselines and alert when performance degrades.

## Types of Performance Tests

| Type | Measures | Tool |
|------|----------|------|
| **Microbenchmark** | Function-level timing | Swift Benchmarks, XCTest `measure` |
| **Load test** | Behavior under high throughput | Custom harness |
| **Memory profile** | Allocation count/size, leaks | Instruments, XCTest memory metrics |
| **Startup time** | App launch duration | Instruments, MetricKit |
| **Regression detection** | Performance delta vs baseline | CI benchmark comparison |

## Swift Benchmark Package

```swift
// Package.swift dependency
.package(url: "https://github.com/ordo-one/package-benchmark", from: "1.0.0")

// Benchmarks/MyBenchmark/MyBenchmark.swift
import Benchmark

let benchmarks = {
    Benchmark("JSON parsing 1000 users") { benchmark in
        for _ in benchmark.scaledIterations {
            blackHole(try JSONDecoder().decode([User].self, from: largeJSON))
        }
    }

    Benchmark("Image resize 4K to thumbnail") { benchmark in
        for _ in benchmark.scaledIterations {
            blackHole(ImageResizer.resize(image4K, to: .thumbnail))
        }
    }
}
```

## XCTest Performance Measurement

```swift
// For projects using XCTest (legacy or mixed)
func testParsingPerformance() {
    let data = loadFixture("large-response.json")

    measure(metrics: [
        XCTClockMetric(),
        XCTMemoryMetric(),
        XCTCPUMetric(),
    ]) {
        _ = try! JSONDecoder().decode([User].self, from: data)
    }
}
```

## Swift Testing + Manual Benchmarking

```swift
@Suite("Performance", .tags(.performance))
struct PerformanceTests {
    @Test
    func `sort 10000 items completes under 50ms`() async throws {
        let items = (0..<10_000).map { _ in Int.random(in: 0...100_000) }
        let clock = ContinuousClock()

        let duration = try await clock.measure {
            _ = items.sorted()
        }

        #expect(duration < .milliseconds(50))
    }

    @Test
    func `cache lookup is O(1) — constant time regardless of size`() async throws {
        let clock = ContinuousClock()

        let smallCache = LRUCache<String, Int>(capacity: 100)
        let largeCache = LRUCache<String, Int>(capacity: 100_000)

        // Fill caches
        for i in 0..<100 { smallCache.set("key\(i)", value: i) }
        for i in 0..<100_000 { largeCache.set("key\(i)", value: i) }

        let smallTime = try await clock.measure {
            for _ in 0..<1000 { _ = smallCache.get("key50") }
        }

        let largeTime = try await clock.measure {
            for _ in 0..<1000 { _ = largeCache.get("key50000") }
        }

        // Large cache should not be significantly slower
        let ratio = Double(largeTime.components.attoseconds) / Double(smallTime.components.attoseconds)
        #expect(ratio < 2.0, "Lookup time should be roughly constant")
    }
}
```

## Memory Testing

```swift
@Test
func `processing 1000 images doesn't retain them all`() async throws {
    weak var lastImage: UIImage?

    for i in 0..<1000 {
        let image = await ImageProcessor.process(generateTestImage(index: i))
        lastImage = image
        // If images are retained, memory will explode
    }

    // After loop, previous images should be deallocated
    // Use Instruments for precise measurement
}
```

## Performance Regression Detection

### CI Integration Strategy

```
1. Record baseline benchmarks on main branch
2. Run benchmarks on PR branch
3. Compare: if any metric degrades > threshold, fail the PR
4. Thresholds:
   - Latency: > 10% regression
   - Memory: > 20% regression
   - Throughput: > 10% regression
```

### Avoiding Flaky Performance Tests

| Practice | Why |
|----------|-----|
| **Use relative comparisons, not absolutes** | CI machines vary in speed |
| **Warm up before measuring** | Avoid cold-start skew |
| **Run multiple iterations** | Statistical significance |
| **Exclude outliers** | System jitter |
| **Run on dedicated CI hardware** | Other jobs affect timing |
| **Tag as `.performance`** | Run separately from unit tests |
| **Use `blackHole()` to prevent optimizer elimination** | Ensures code actually runs |

## When to Write Performance Tests

| Always | Sometimes | Rarely |
|--------|-----------|--------|
| Hot paths (called 1000s of times) | Moderate-frequency operations | One-time initialization |
| Data processing pipelines | Network response parsing | UI event handlers |
| Sorting/searching large datasets | Image processing | Simple property access |
| Crypto operations | File I/O operations | |
| Real-time audio/video processing | | |

## Checklist

- [ ] Critical hot paths have benchmark tests
- [ ] Baselines recorded and committed
- [ ] CI compares against baselines with defined thresholds
- [ ] Memory tests verify no unbounded growth
- [ ] Performance tests tagged `.performance` for selective execution
- [ ] Tests use warm-up iterations
- [ ] No absolute timing assertions (use relative or generous bounds)
- [ ] `blackHole()` used to prevent dead code elimination

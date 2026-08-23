# Swift Charts Reference

## Overview

Swift Charts is Apple's native charting framework for SwiftUI. Use `Chart` with marks to build bar, line, area, point, rule, rectangle, and sector charts.

## Availability

- iOS 16+: `Chart`, `BarMark`, `LineMark`, `AreaMark`, `PointMark`, `RectangleMark`, `RuleMark`, custom axes, scales
- iOS 17+: `SectorMark`, built-in selection, scrollable chart axes
- iOS 18+: `BarPlot`, `LinePlot`, `AreaPlot`, function plotting
- iOS 26+: `Chart3D`, `SurfacePlot`, Z-axis marks

## Core APIs

Always `import Charts` in files using chart types.

```swift
import SwiftUI
import Charts

Chart(sales) { item in
    BarMark(
        x: .value("Month", item.month),
        y: .value("Revenue", item.revenue)
    )
}
```

### Data Models Should Be Identifiable

```swift
struct SalesPoint: Identifiable {
    let id: UUID
    let month: String
    let revenue: Double
}
```

## Mark Types

| Mark | Use |
|------|-----|
| `BarMark` | Categorical comparisons |
| `LineMark` | Trends over time (.interpolationMethod for smoothing) |
| `AreaMark` | Volume/range visualization (supports yStart/yEnd for bands) |
| `PointMark` | Scatter plots |
| `RectangleMark` | Heat maps, ranges |
| `RuleMark` | Thresholds, goals, selection indicators |
| `SectorMark` | Pie/donut charts (iOS 17+, use innerRadius for donut) |

## Styling

- `foregroundStyle(by: .value(...))` for categorical coloring (auto-generates legend)
- `chartForegroundStyleScale` for custom color mapping
- `symbol(by:)` and `symbolSize(by:)` for additional data dimensions
- **Never** apply manual `.foregroundStyle(.red)` per mark for categorical data

## Selection (iOS 17+)

```swift
@State private var selectedDate: Date?

Chart(steps) { day in
    LineMark(x: .value("Day", day.date), y: .value("Steps", day.count))
}
.chartXSelection(value: $selectedDate)  // Single value
// .chartXSelection(range: $selectedRange)  // Range selection
```

Selection returns the plottable axis value, not the model. Map back to your data.

## Scrollable Axes (iOS 17+)

```swift
Chart(data) { item in
    BarMark(x: .value("Day", item.day), y: .value("Value", item.value))
}
.chartScrollableAxes(.horizontal)
.chartXVisibleDomain(length: 7)
.chartScrollPosition(x: $scrollX)
```

## Chart3D (iOS 26+)

```swift
if #available(iOS 26, *) {
    Chart3D(points) { point in
        PointMark(
            x: .value("X", point.x),
            y: .value("Y", point.y),
            z: .value("Z", point.z)
        )
    }
    .chart3DPose(.front)
}
```

## Accessibility

VoiceOver provides automatic: Describe Chart, Audio Graph, Chart Detail. Use descriptive `.value(_, _)` labels. For custom audio graphs, conform to `AXChartDescriptorRepresentable`.

## Best Practices

- Use semantic `.value(_, _)` labels
- Prefer `Identifiable` models for stable chart data identity
- Use `foregroundStyle(by:)` for categorical series
- Use `RuleMark` for thresholds and selection indicators
- Gate iOS 17+/18+/26+ APIs with `#available`
- Chart-wide modifiers on `Chart`, mark-specific on marks
- Animate via `withAnimation` with stable identity

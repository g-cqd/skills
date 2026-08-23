# {TICKET-ID}: {ComponentName}

## The {Layer Name} Layer

{One sentence summarizing the component's single responsibility.}

---

## Why Start Here?

{Context for why this component is being built now, what depends on it.}

```
┌─────────────────────────────────────────────────────────┐
│  {Layer N}        ({description})                       │
├─────────────────────────────────────────────────────────┤
│  {Layer N-1}      ({description})                       │  ← {FUTURE-TICKET}
├─────────────────────────────────────────────────────────┤
│  {This Layer}     ({description})                       │  ← {TICKET-ID} (this ticket)
├─────────────────────────────────────────────────────────┤
│  {Layer Below}    ({description})                       │
└─────────────────────────────────────────────────────────┘
```

---

## What Existed Before

The codebase had `{OldComponentName}`:

```swift
{Old code snippet}
```

This approach had fundamental issues:

| Problem | Consequence |
|---------|-------------|
| {Problem 1} | {Impact on users/system} |
| {Problem 2} | {Impact on users/system} |
| {Problem 3} | {Impact on users/system} |

---

## The Design Rationale

### {Decision 1 Name}

{Explanation of what was decided.}

```swift
{Code example showing the new approach}
```

**Why this approach?**
- {Reason 1}
- {Reason 2}
- {Connection to downstream benefits}

### {Decision 2 Name}

{Explanation of what was decided.}

```swift
{Code example}
```

**Why this matters for the larger system:**
- {Benefit 1}
- {Benefit 2}

### {Comparison: Why X Over Y?}

| Requirement | {Alternative A} | {Alternative B} |
|-------------|-----------------|-----------------|
| {Req 1} | {How A handles} | {How B handles} |
| {Req 2} | {How A handles} | {How B handles} |

{Explanation of why B was chosen.}

---

## What This Enables

With {ComponentName} in place, {downstream component} can:

1. **{Capability 1}** — {Explanation}
2. **{Capability 2}** — {Explanation}
3. **{Capability 3}** — {Explanation}

The {higher layer} above can:

1. **{Capability 1}** — {Explanation}
2. **{Capability 2}** — {Explanation}

---

## Patterns Established

This PR establishes patterns that subsequent PRs will follow:

| Pattern | Instantiation Here | Applied Later |
|---------|-------------------|---------------|
| {Pattern 1} | `{TypeName}` | {Future components} |
| {Pattern 2} | `{TypeName}` | {Future components} |
| {Pattern 3} | {How used here} | {How used later} |

---

## Files in This PR

```
Sources/
├── {ComponentName}.swift                    # {Brief role}
├── {ComponentName}+{Extension1}.swift       # {Brief role}
├── {ComponentName}+{Extension2}.swift       # {Brief role}
├── {SubFolder}/
│   ├── {File1}.swift                        # {Brief role}
│   └── {File2}.swift                        # {Brief role}
└── {AnotherSubFolder}/
    └── {File3}.swift                        # {Brief role}

Tests/
├── {ComponentName}+{Feature}+Tests.swift
├── {ComponentName}{Feature}Tests.swift
└── {HelperType}Tests.swift
```

---

## Looking Ahead

**{NEXT-TICKET-ID} ({NextComponentName})** builds directly on this foundation:
- {How it uses this component}
- {Patterns it inherits}
- {New concerns it adds}

**Future PRs** will add:
- {Feature 1} ({brief description})
- {Feature 2} ({brief description})
- {Feature 3} ({brief description})

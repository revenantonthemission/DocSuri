# Logical Components — ZoomPanControls

## Component Inventory

| Component | Type | Responsibility | Failure Domain |
|-----------|------|----------------|----------------|
| `ZoomPanControls` | Functional Component | Zoom/pan state, input handling, DOM transform | Input, GPU |
| `Matrix3D` | Utility | 3x3 matrix math (translate, scale) | CPU |

## Failure Domains
```
ZoomPanControls
├── Pointer Event Handler
│   └── Invalid input → clamped, no crash
├── RAF Loop
│   └── Transform calc error → fallback to identity
└── DOM Transform
    └── Detached element → cleanup on unmount
```
- No crash propagation (ErrorBoundary containment)

## Isolation
- Pure math utility + component
- No shared state

## Traceability
| NFR Requirement | Logical Component |
|-----------------|-------------------|
| NFR1.1-1.3 | ZoomPanControls, Matrix3D |
| NFR3.1 | ZoomPanControls (per-instance) |
| NFR4.1-4.2 | ZoomPanControls |
| NFR5.1 | ZoomPanControls |
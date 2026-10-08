# Infrastructure Specification — ZoomPanControls

## Client-Only Infrastructure

### Component
- **Type**: Functional Component with `useRef` + RAF
- **State**: Transform matrix in `useRef` (avoids re-renders)
- **DOM**: Direct `element.style.transform = matrix3d(...)`

### Input Handling
- **Pointer Events**: `pointerdown`/`pointermove`/`pointerup` (unified mouse/touch/pen)
- **No Polyfills**: Native browser API

### Math Utility
- **Matrix3D**: Custom 3x3 matrix (translate, scale)
- **Zero Dependencies**: ~50 lines

### CSS
- **Container**: CSS Module for layout
- **Controls**: Tailwind utilities for buttons/tooltips

## Traceability
| Logical Component | Infrastructure Need |
|-------------------|---------------------|
| ZoomPanControls | RAF + Pointer Events (native) |
| Matrix3D | Client-only math utility |
# Tech Stack Decisions — ZoomPanControls

## NFR6.1: Transform Math — Custom Matrix3D
- **Decision**: Minimal 3x3 matrix implementation (translate, scale)
- **Rationale**: Zero deps; ~50 lines; tree-shakeable

## NFR6.2: DOM Interaction — `useRef` + `requestAnimationFrame`
- **Decision**: Direct DOM manipulation via ref; RAF for smooth animations
- **Rationale**: Avoids React render cycle for 60fps; `transform` is compositor-only

## NFR6.3: Input Handling — Pointer Events
- **Decision**: `pointerdown`/`pointermove`/`pointerup` (unified mouse/touch/pen)
- **Rationale**: Modern standard; no touch-event polyfill needed

## NFR6.4: Styling — CSS Modules + Tailwind
- **Decision**: Mandated pattern
- **CSS Module**: Container styles
- **Tailwind**: Button/tooltip utilities

## NFR6.5: TypeScript — Strict
- **Decision**: Full strict mode

## NFR6.6: Testing — Vitest + RTL
- **Decision**: Unit tests for math; integration tests with fake DOM
- **Coverage Target**: ≥80% line coverage

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR6.1, NFR6.2 | OK |
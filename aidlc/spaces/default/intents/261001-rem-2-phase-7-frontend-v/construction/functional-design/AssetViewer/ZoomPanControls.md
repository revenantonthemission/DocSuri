# Frontend Components — ZoomPanControls

**Unit:** AssetViewer (sub-component)
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Component Overview

ZoomPanControls is a **ui** sub-component that provides zoom and pan controls for AssetViewer. It supports mouse, touch, and keyboard interactions.

---

## Component API

### Props
```typescript
interface ZoomPanControlsProps {
  zoom: number;           // 0.5 to 4.0
  pan: { x: number; y: number };
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onPan: (dx: number, dy: number) => void;
}
```

---

## Component Implementation

```tsx
export function ZoomPanControls({ 
  zoom, 
  pan, 
  onZoomIn, 
  onZoomOut, 
  onReset, 
  onPan 
}: ZoomPanControlsProps) {
  return (
    <div className={styles.zoomControls} role="group" aria-label="줌/팬 컨트롤">
      <button
        className={styles.zoomButton}
        onClick={onZoomIn}
        aria-label="확대"
        disabled={zoom >= 4}
      >
        🔍+
      </button>
      <button
        className={styles.zoomButton}
        onClick={onZoomOut}
        aria-label="축소"
        disabled={zoom <= 0.5}
      >
        🔍-
      </button>
      <button
        className={styles.zoomButton}
        onClick={onReset}
        aria-label="초기화"
      >
        ⌂
      </button>
    </div>
  );
}
```

---

## Interaction Specification

### Desktop
| Interaction | Behavior |
|-------------|----------|
| Mouse wheel | Zoom in/out (centered on cursor) |
| Click + drag | Pan |
| Double-click | Reset zoom/pan to fit |
| Controls | 🔍+ (zoom in), 🔍- (zoom out), ⌂ (reset) |

### Touch
| Interaction | Behavior |
|-------------|----------|
| Pinch | Zoom in/out |
| Two-finger drag | Pan |
| Double-tap | Reset zoom/pan |

### Keyboard
| Key | Action |
|-----|--------|
| `+` / `=` | Zoom in |
| `-` / `_` | Zoom out |
| Arrow keys | Pan (10px per press) |
| `0` | Reset zoom/pan |

### Constraints
- **Zoom range:** 0.5x to 4x
- **Pan bounds:** Image stays within viewport
- **Transition:** `transform 200ms ease-out` (respects `prefers-reduced-motion`)

---

## CSS Module (ZoomPanControls.module.css)

```css
.zoomControls {
  @apply absolute bottom-2 right-2 flex gap-1 bg-white/90 backdrop-blur-sm rounded p-1;
}

.zoomButton {
  @apply p-1 text-gray-700 hover:text-blue-600 disabled:opacity-50 disabled:cursor-not-allowed;
}
```

---

## Integration with AssetViewer

```tsx
export function AssetViewer({ paperId, assetId, className = '', onError, onLoad }: AssetViewerProps) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  const handleZoomIn = () => setZoom(z => Math.min(z * 1.2, 4));
  const handleZoomOut = () => setZoom(z => Math.max(z / 1.2, 0.5));
  const handleReset = () => { setZoom(1); setPan({ x: 0, y: 0 }); };
  const handlePan = (dx: number, dy: number) => setPan(p => ({ x: p.x + dx, y: p.y + dy }));

  return (
    <div className={`${styles.container} ${className}`}>
      {loading && <LoadingSpinner />}
      {error && <ErrorState error={error} onRetry={() => setSrc(currentSrc)} />}
      {src && (
        <>
          <img
            src={src}
            alt="Asset"
            className={`${styles.image} ${zoom !== 1 ? styles.zoomed : ''}`}
            style={{ transform: `scale(${zoom}) translate(${pan.x}px, ${pan.y}px)` }}
            onLoad={() => { onLoad?.(); }}
            onError={(e) => { onError?.(new Error('Failed to load image')); }}
            onWheel={(e) => {
              e.preventDefault();
              if (e.deltaY < 0) handleZoomIn();
              else handleZoomOut();
            }}
            onMouseDown={(e) => {
              // Pan on drag
            }}
            onDoubleClick={handleReset}
          />
          <ZoomPanControls
            zoom={zoom}
            pan={pan}
            onZoomIn={handleZoomIn}
            onZoomOut={handleZoomOut}
            onReset={handleReset}
            onPan={handlePan}
          />
        </>
      )}
    </div>
  );
}
```

---

## CSS Module (ZoomPanControls.module.css)

```css
.zoomControls {
  @apply absolute bottom-2 right-2 flex gap-1 bg-white/90 backdrop-blur-sm rounded p-1;
}

.zoomButton {
  @apply p-1 text-gray-700 hover:text-blue-600 disabled:opacity-50 disabled:cursor-not-allowed;
}
```

---

## Accessibility

| Requirement | Implementation |
|-------------|----------------|
| ARIA labels | `aria-label` on all buttons |
| Keyboard | `+/-` zoom, arrows pan, `0` reset |
| Touch | Pinch zoom, two-finger pan, double-tap reset |
| Reduced motion | Respect `prefers-reduced-motion` |
| Disabled state | Buttons disabled at zoom limits |

---

## Test Points

| Scenario | Test |
|----------|------|
| Zoom in/out | Mouse wheel, buttons, keyboard |
| Pan | Drag, arrow keys, two-finger touch |
| Reset | Double-click, button, `0` key |
| Bounds | Zoom 0.5x-4x, pan within bounds |
| Touch | Pinch zoom, two-finger pan, double-tap |
| Reduced motion | Transitions disabled |
| Accessibility | axe-core 0 violations |
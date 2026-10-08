# Functional Specification — AssetViewer

**Unit:** AssetViewer
**Phase:** Construction — Functional Design
**Date:** 2026-10-02
**Kind:** ui

---

## Overview

AssetViewer displays paper assets (figures, tables) via same-origin delivery through the BFF proxy. It replaces the legacy presigned URL pattern with secure same-origin delivery that re-checks authorization at delivery time (SEC-9 compliance) and eliminates presigned URLs (SECURITY-08 compliance).

---

## Props

```typescript
interface AssetViewerProps {
  paperId: string;
  assetId: string;
  className?: string;
  onError?: (error: Error) => void;
  onLoad?: () => void;
}
```

---

## State Management

### Local State
```typescript
interface AssetViewerState {
  src: string | null;
  loading: boolean;
  error: Error | null;
  zoom: number;      // 0.5 to 4.0
  pan: { x: number; y: number };
}
```

---

## Component Lifecycle

### Mount
1. Initialize state: `loading = true`, `zoom = 1`, `pan = { x: 0, y: 0 }`
2. Construct src: `/bff/api/papers/${paperId}/assets/${assetId}`
3. Set `src` on image element

### Load Flow
```
Mount with paperId + assetId
        │
        ▼
Show loading spinner (aspect-video, bg-gray-100)
        │
        ▼
Fetch /bff/api/papers/{paperId}/assets/{assetId}
        │
        ├─ 200 OK + image/* → Render <img>, fade in 200ms
        ├─ 401/403 → Show "접근 권한이 없습니다" + retry button
        ├─ 404 → Show "자산을 찾을 수 없습니다" + retry button
        └─ 5xx / network error → Show "로드 실패" + retry button
```

### Image Interactions
| Interaction | Behavior |
|-------------|----------|
| Load complete | Fade in over 200ms, hide spinner |
| Error on load | Show error state, keep aspect ratio |
| Click image | No action (view-only) |
| Right-click | Browser default (save, copy, etc.) |

---

## Zoom/Pan Controls (US5.3)

### Desktop
- **Mouse wheel:** Zoom in/out (centered on cursor)
- **Click + drag:** Pan
- **Double-click:** Reset zoom/pan to fit
- **Controls:** 🔍+ (zoom in), 🔍- (zoom out), ⌂ (reset)

### Touch
- **Pinch:** Zoom in/out
- **Two-finger drag:** Pan
- **Double-tap:** Reset zoom/pan

### Keyboard
- `+` / `=`: Zoom in
- `-` / `_`: Zoom out
- Arrow keys: Pan (10px per press)
- `0`: Reset zoom/pan

### Constraints
- **Zoom range:** 0.5x to 4x
- **Pan bounds:** Image stays within viewport
- **Transition:** `transform 200ms ease-out` (respects `prefers-reduced-motion`)

---

## UI Specification

### Loading State
```
┌─────────────────────────────────────────────────────────────────┐
│  Figure 1: Architecture Diagram                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  <div className="relative aspect-video bg-gray-100       │  │
│  │       rounded-lg">                                         │  │
│  │    <div className="absolute inset-0 flex items-center     │  │
│  │         justify-center text-gray-400">                     │  │
│  │      <div className="animate-spin h-8 w-8 text-blue-600"> │  │
│  │        <svg>...</svg>                                      │  │
│  │      </div>                                                │  │
│  │    </div>                                                  │  │
│  │  </div>                                                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Caption: System architecture overview                          │
└─────────────────────────────────────────────────────────────────┘
```

### Loaded State (Same-Origin)
```
┌─────────────────────────────────────────────────────────────────┐
│  Figure 1: Architecture Diagram                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  <img src="/bff/api/papers/abc123/assets/fig1.png" />     │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Caption: System architecture overview                          │
│  🔒 SEC-9 COMPLIANT — Auth re-checked at delivery              │
└─────────────────────────────────────────────────────────────────┘
```

### Error State
```
┌─────────────────────────────────────────────────────────────────┐
│  Figure 1: Architecture Diagram                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  <div className="relative aspect-video bg-gray-100       │  │
│  │       rounded-lg">                                         │  │
│  │    <div className="absolute inset-0 flex items-center     │  │
│  │         justify-center text-red-500">                     │  │
│  │      <svg className="w-8 h-8 mx-auto mb-2">...</svg>      │  │
│  │      <div className="text-center p-4">                     │  │
│  │        <p className="text-sm">자산 로드 실패</p>           │  │
│  │        <button                                              │  │
│  │          className="mt-2 text-xs text-blue-600            │  │
│  │                hover:underline">다시 시도</button>         │  │
│  │      </div>                                                │  │
│  │    </div>                                                  │  │
│  │  </div>                                                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Caption: System architecture overview                          │
└─────────────────────────────────────────────────────────────────┘
```

### Zoom/Pan Controls (US5.3)
```
┌─────────────────────────────────────────────────────────────────┐
│  Figure 1: Architecture Diagram                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  <div className="relative">                               │  │
│  │    <img src="..." className="w-full h-full object-contain │  │
│  │         transition-transform duration-200"                │  │
│  │         style={{ transform: 'scale(1.5) translate(-50px, -30px)' }} /> │  │
│  │    <div className="absolute bottom-2 right-2 flex gap-1   │  │
│  │         bg-white/90 backdrop-blur-sm rounded p-1">        │  │
│  │      <button aria-label="확대" className="p-1">🔍+</button>│  │
│  │      <button aria-label="축소" className="p-1">🔍-</button>│  │
│  │      <button aria-label="초기화" className="p-1">⌂</button>│  │
│  │    </div>                                                  │  │
│  │  </div>                                                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Caption: System architecture overview                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design Tokens (Reference)

```css
:root {
  /* AssetViewer */
  --assetviewer-aspect: 16/9;
  --assetviewer-radius: 8px;
  --assetviewer-loading-bg: #F3F4F6;   /* gray-100 */
  --assetviewer-error-bg: #FEF2F2;     /* red-50 */

  /* Zoom Controls */
  --zoom-control-bg: rgba(255,255,255,0.9);
  --zoom-control-radius: 6px;
  --zoom-control-padding: 8px;
  --zoom-min: 0.5;
  --zoom-max: 4;
  --zoom-transition: transform 200ms ease-out;
}
```

### Tailwind Utility Classes
```html
<!-- Loading -->
<div class="relative aspect-video bg-gray-100 rounded-lg">
  <div class="absolute inset-0 flex items-center justify-center text-gray-400">
    <div class="animate-spin h-8 w-8 text-blue-600">
      <svg class="animate-spin h-8 w-8 text-blue-600" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  </div>
</div>

<!-- Image -->
<img src="/bff/api/papers/{paperId}/assets/{assetId}" alt="Asset" class="w-full h-full object-contain" />

<!-- Error -->
<div class="relative aspect-video bg-gray-100 rounded-lg">
  <div class="absolute inset-0 flex items-center justify-center text-red-500">
    <div class="text-center p-4">
      <svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <p className="text-sm">자산 로드 실패</p>
      <button className="mt-2 text-xs text-blue-600 hover:underline">다시 시도</button>
    </div>
  </div>
</div>

<!-- Zoom Controls -->
<div class="absolute bottom-2 right-2 flex gap-1 bg-white/90 backdrop-blur-sm rounded p-1">
  <button className="p-1" aria-label="확대">🔍+</button>
  <button className="p-1" aria-label="축소">🔍-</button>
  <button className="p-1" aria-label="초기화">⌂</button>
</div>
```

---

## Accessibility (WCAG 2.1 AA)

| Requirement | Implementation |
|-------------|----------------|
| Alt text | `alt="Figure 1: Architecture Diagram"` from caption |
| Loading state | `aria-busy="true"` on container |
| Error state | `role="alert"` on error container |
| Zoom controls | `aria-label` on buttons |
| Keyboard | `+/-` zoom, arrows pan, `0` reset |
| Reduced motion | Respect `prefers-reduced-motion` for transitions |

---

## Component API

### Props
```typescript
interface AssetViewerProps {
  paperId: string;
  assetId: string;
  className?: string;
  onError?: (error: Error) => void;
  onLoad?: () => void;
}
```

---

## Sub-components

### ZoomPanControls
```typescript
interface ZoomPanControlsProps {
  zoom: number;
  pan: { x: number; y: number };
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onPan: (dx: number, dy: number) => void;
}
```

### Props
```typescript
interface AssetViewerProps {
  paperId: string;
  assetId: string;
  className?: string;
  onError?: (error: Error) => void;
  onLoad?: () => void;
}
```

### Sub-components
| Component | Purpose |
|-----------|---------|
| `AssetViewer` | Main component, handles loading/error states |
| `ZoomPanControls` | Zoom/pan overlay controls |

---

## CSS Module (AssetViewer.module.css)

```css
.assetViewer {
  @apply relative aspect-video bg-gray-100 rounded-lg overflow-hidden;
}

.assetViewer_loading {
  @apply absolute inset-0 flex items-center justify-center text-gray-400;
}

.assetViewer_spinner {
  @apply animate-spin h-8 w-8 text-blue-600;
}

.assetViewer_error {
  @apply absolute inset-0 flex items-center justify-center text-red-500 p-4;
}

.assetViewer_image {
  @apply w-full h-full object-contain;
}

.assetViewer_zoomControls {
  @apply absolute bottom-2 right-2 flex gap-1 bg-white/90 backdrop-blur-sm rounded p-1;
}

.assetViewer_zoomButton {
  @apply p-1 text-gray-700 hover:text-blue-600;
}
```

---

## Test Points

| Scenario | Test |
|-----------|------|
| Load success | Image renders, no 307 redirect |
| 401/403 | Show "Access denied" placeholder |
| 404 | Show "Asset not found" placeholder |
| 5xx | Show "Failed to load" + retry button |
| Zoom controls | Mouse wheel, drag, double-click, keyboard, touch |
| Zoom bounds | 0.5x min, 4x max |
| Pan bounds | Image stays in viewport |
| Accessibility | axe-core 0 violations |

---

## Accessibility Checklist

- [ ] Alt text from caption/figcaption
- [ ] Loading state announced (`aria-busy="true"`)
- [ ] Error state announced (`role="alert"`)
- [ ] Zoom controls keyboard accessible
- [ ] Touch gestures work on mobile
- [ ] `prefers-reduced-motion` respected
- [ ] axe-core + manual screen reader test
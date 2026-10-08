# Frontend Components — AssetViewer

**Unit:** AssetViewer
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Component Overview

AssetViewer is a **ui** component that displays paper assets (figures, tables) via secure same-origin delivery through the BFF proxy.

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

### Sub-components
| Component | Purpose |
|-----------|---------|
| `AssetViewer` | Main component, handles loading/error states |
| `ZoomPanControls` | Zoom/pan overlay controls |

---

## Integration Points

### Parent: DocModelViewer
```tsx
<AssetViewer 
  paperId={paperId} 
  assetId={assetId} 
/>
```

### Dependencies
| Dependency | Purpose |
|------------|---------|
| BFF Proxy (`/bff/api/papers/{paperId}/assets/{assetId}`) | Same-origin asset delivery with auth re-check |
| `ZoomPanControls` | Zoom/pan overlay controls |
| `crypto.subtle` | Not directly used (backend handles crypto) |

---

## Sub-component Specifications

### AssetViewer (Main)
```tsx
export function AssetViewer({ paperId, assetId, className = '', onError, onLoad }: AssetViewerProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadAsset() {
      try {
        setLoading(true);
        const url = await getAssetUrl(assetId, token); // DEPRECATED - will be removed
        // NEW: Direct same-origin URL
        const newSrc = `/bff/api/papers/${paperId}/assets/${assetId}`;
        if (!cancelled) {
          setSrc(newSrc);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setLoading(false);
        }
      }
    }

    loadAsset();
    return () => { cancelled = true; };
  }, [paperId, assetId]);

  if (loading) {
    return (
      <div className={`${styles.container} ${className}`}>
        <div className={styles.loading}>
          <div className={styles.spinner}>
            <svg className="animate-spin h-8 w-8 text-blue-600" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`${styles.container} ${className}`}>
        <div className={styles.error}>
          <div className="absolute inset-0 flex items-center justify-center text-red-500">
            <div className="text-center p-4">
              <svg className="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-sm">자산 로드 실패</p>
              <button
                onClick={() => window.location.reload()}
                className="mt-2 text-xs text-blue-600 hover:underline"
              >
                다시 시도
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.container} ${className}`}>
      <img
        src={src!}
        alt="Asset"
        className={styles.image}
        onError={() => { onError?.(new Error('Failed to load image')); }}
        onLoad={() => { onLoad?.(); }}
      />
    </div>
  );
}
```

---

### ZoomPanControls Component
```tsx
interface ZoomPanControlsProps {
  zoom: number;
  pan: { x: number; y: number };
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onPan: (dx: number, dy: number) => void;
}

export function ZoomPanControls({ zoom, pan, onZoomIn, onZoomOut, onReset, onPan }: ZoomPanControlsProps) {
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

## Integration Points

### DocModelViewer (Consumer)
```tsx
<AssetViewer
  paperId={paperId}
  assetId={assetId}
  className={styles.asset}
/>
```

### DocModelViewer Props Update
```typescript
// Before (Phase 6)
<AssetViewer assetId={assetId} token={token} />

// After (Phase 7)
<AssetViewer paperId={paperId} assetId={assetId} />
```

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
  @apply p-1 text-gray-700 hover:text-blue-600 disabled:opacity-50 disabled:cursor-not-allowed;
}
```

---

## Props Interface

```typescript
interface AssetViewerProps {
  paperId: string;
  assetId: string;
  className?: string;
  onError?: (error: Error) => void;
  onLoad?: () => void;
}
```

### Migration from Presigned URL Pattern
| Before (Phase 6) | After (Phase 7) |
|------------------|-----------------|
| `assetId` + `token` | `paperId` + `assetId` |
| `getAssetUrl(assetId, token)` → presigned URL | Direct `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />` |
| 307 redirect to S3 | Same-origin delivery, auth re-check |
| `cache-control: public` | `cache-control: private, max-age=60` |

---

## ZoomPanControls Props

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

## Test Points

| Scenario | Test |
|-----------|------|
| Load success | Image renders, no 307 redirect |
| 401/403 | Show "접근 권한이 없습니다" placeholder |
| 404 | Show "자산을 찾을 수 없습니다" placeholder |
| 5xx | Show "로드 실패" + retry button |
| Zoom controls | Mouse wheel, drag, double-click, keyboard, touch |
| Zoom bounds | 0.5x min, 4x max |
| Pan bounds | Image stays in viewport |
| Accessibility | axe-core 0 violations |
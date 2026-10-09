'use client';

// ZoomPanControls — the named, keyboard-operable transform cluster for the
// enlarged asset view (U3). Design parameters from the interaction spec:
// 0.5–4x relative to fit (fit = 1x), 0.25x zoom steps, pan steps at 10% of the
// corresponding viewport dimension, all clamped so the content cannot leave
// view. `+`, `-`, arrow and `0` shortcuts apply only while this group has
// focus — never globally and never inside text inputs. Tab leaves the group
// (no trap); every action has a named single-pointer button alternative.

import { useCallback } from 'react';

export interface ZoomPanTransform {
  /** 1 = fit; clamped to the 0.5–4 design range. */
  scale: number;
  /** Pan offset in viewport pixels, clamped so the content cannot leave view. */
  x: number;
  y: number;
}

export const ZOOM_MIN = 0.5;
export const ZOOM_MAX = 4;
export const ZOOM_STEP = 0.25;
export const PAN_STEP_FRACTION = 0.1;
export const FIT_TRANSFORM: ZoomPanTransform = { scale: 1, x: 0, y: 0 };

export interface ZoomPanMetrics {
  /** Visible box in pixels. */
  viewport: { width: number; height: number };
  /** Content box in pixels AT FIT SCALE (before this transform). */
  content: { width: number; height: number };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Clamp scale to the allowed range and pan so the content cannot leave view. */
export function clampTransform(t: ZoomPanTransform, metrics: ZoomPanMetrics): ZoomPanTransform {
  const scale = clamp(t.scale, ZOOM_MIN, ZOOM_MAX);
  const maxX = Math.max(0, (metrics.content.width * scale - metrics.viewport.width) / 2);
  const maxY = Math.max(0, (metrics.content.height * scale - metrics.viewport.height) / 2);
  return { scale, x: clamp(t.x, -maxX, maxX), y: clamp(t.y, -maxY, maxY) };
}

export function zoomBy(t: ZoomPanTransform, delta: number, metrics: ZoomPanMetrics): ZoomPanTransform {
  return clampTransform({ ...t, scale: t.scale + delta }, metrics);
}

export function panBy(t: ZoomPanTransform, dx: number, dy: number, metrics: ZoomPanMetrics): ZoomPanTransform {
  return clampTransform({ ...t, x: t.x + dx, y: t.y + dy }, metrics);
}

export function resetTransform(): ZoomPanTransform {
  return { ...FIT_TRANSFORM };
}

/** Drag accumulation: total pointer delta applied from the drag-start transform. */
export function dragPan(
  startTransform: ZoomPanTransform,
  start: { x: number; y: number },
  current: { x: number; y: number },
  metrics: ZoomPanMetrics,
): ZoomPanTransform {
  return clampTransform(
    { ...startTransform, x: startTransform.x + (current.x - start.x), y: startTransform.y + (current.y - start.y) },
    metrics,
  );
}

const GROUP_LABEL = '확대 및 이동';

interface ZoomPanControlsProps {
  transform: ZoomPanTransform;
  metrics: ZoomPanMetrics;
  onChange: (next: ZoomPanTransform) => void;
}

export function ZoomPanControls({ transform, metrics, onChange }: ZoomPanControlsProps) {
  const apply = useCallback(
    (next: ZoomPanTransform) => onChange(clampTransform(next, metrics)),
    [metrics, onChange],
  );
  const panSteps: Array<{ label: string; dx: number; dy: number }> = [
    { label: '왼쪽', dx: -1, dy: 0 },
    { label: '오른쪽', dx: 1, dy: 0 },
    { label: '위', dx: 0, dy: -1 },
    { label: '아래', dx: 0, dy: 1 },
  ];

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    // Shortcuts apply only while this group (or its buttons) has focus. A text
    // input inside the viewer keeps its own keys — the viewer never intercepts
    // editable fields, and nothing here is bound globally.
    const target = e.target as HTMLElement | null;
    if (target && (target.isContentEditable || /^(input|textarea|select)$/i.test(target.tagName))) {
      return;
    }
    switch (e.key) {
      case '+':
      case '=':
        e.preventDefault();
        apply(zoomBy(transform, ZOOM_STEP, metrics));
        break;
      case '-':
      case '_':
        e.preventDefault();
        apply(zoomBy(transform, -ZOOM_STEP, metrics));
        break;
      case '0':
        e.preventDefault();
        apply(resetTransform());
        break;
      case 'ArrowLeft':
        e.preventDefault();
        apply(panBy(transform, -metrics.viewport.width * PAN_STEP_FRACTION, 0, metrics));
        break;
      case 'ArrowRight':
        e.preventDefault();
        apply(panBy(transform, metrics.viewport.width * PAN_STEP_FRACTION, 0, metrics));
        break;
      case 'ArrowUp':
        e.preventDefault();
        apply(panBy(transform, 0, -metrics.viewport.height * PAN_STEP_FRACTION, metrics));
        break;
      case 'ArrowDown':
        e.preventDefault();
        apply(panBy(transform, 0, metrics.viewport.height * PAN_STEP_FRACTION, metrics));
        break;
      default:
        break;
    }
  };

  const buttonClass =
    'rounded border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-40';

  return (
    <div
      role="group"
      aria-label={GROUP_LABEL}
      data-testid="zoom-pan-controls"
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="flex flex-wrap items-center justify-center gap-1"
    >
      <button
        type="button"
        className={buttonClass}
        onClick={() => apply(zoomBy(transform, -ZOOM_STEP, metrics))}
        disabled={transform.scale <= ZOOM_MIN}
      >
        축소
      </button>
      <button
        type="button"
        className={buttonClass}
        onClick={() => apply(zoomBy(transform, ZOOM_STEP, metrics))}
        disabled={transform.scale >= ZOOM_MAX}
      >
        확대
      </button>
      {panSteps.map((step) => (
        <button
          key={step.label}
          type="button"
          className={buttonClass}
          onClick={() =>
            apply(
              panBy(
                transform,
                step.dx * metrics.viewport.width * PAN_STEP_FRACTION,
                step.dy * metrics.viewport.height * PAN_STEP_FRACTION,
                metrics,
              ),
            )
          }
        >
          {step.label}
        </button>
      ))}
      <button
        type="button"
        className={buttonClass}
        onClick={() => apply(resetTransform())}
        disabled={transform.scale === FIT_TRANSFORM.scale && transform.x === 0 && transform.y === 0}
      >
        원래 크기
      </button>
    </div>
  );
}

export default ZoomPanControls;

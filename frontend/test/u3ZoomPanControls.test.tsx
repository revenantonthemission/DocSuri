import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import {
  ZoomPanControls,
  clampTransform,
  zoomBy,
  panBy,
  resetTransform,
  dragPan,
  FIT_TRANSFORM,
  ZOOM_MIN,
  ZOOM_MAX,
  ZOOM_STEP,
  type ZoomPanMetrics,
  type ZoomPanTransform,
} from '@/components/ZoomPanControls';

// U3 — the named, keyboard-operable transform cluster: 0.5–4x (fit = 1x),
// 0.25x zoom steps, 10%-of-viewport pan steps, clamped so content cannot leave
// view, shortcuts only while the group has focus, and no keyboard trap.

const FITS: ZoomPanMetrics = {
  viewport: { width: 400, height: 300 },
  content: { width: 400, height: 300 },
};
const BIG: ZoomPanMetrics = {
  viewport: { width: 400, height: 300 },
  content: { width: 800, height: 600 },
};

function Harness({
  metrics = BIG,
  initial = FIT_TRANSFORM,
}: {
  metrics?: ZoomPanMetrics;
  initial?: ZoomPanTransform;
}) {
  const [t, setT] = useState(initial);
  return (
    <div>
      <ZoomPanControls transform={t} metrics={metrics} onChange={setT} />
      <output data-testid="scale">{t.scale}</output>
      <output data-testid="x">{t.x}</output>
      <output data-testid="y">{t.y}</output>
    </div>
  );
}

describe('ZoomPanControls helpers (u3)', () => {
  it('clamps scale to the 0.5–4 design range', () => {
    expect(clampTransform({ scale: 9, x: 0, y: 0 }, BIG).scale).toBe(ZOOM_MAX);
    expect(clampTransform({ scale: 0.1, x: 0, y: 0 }, BIG).scale).toBe(ZOOM_MIN);
  });

  it('clamps pan so content cannot leave view and forbids pan while content fits', () => {
    expect(clampTransform({ scale: 2, x: 9999, y: -9999 }, BIG)).toEqual({ scale: 2, x: 600, y: -450 });
    expect(clampTransform({ scale: 1, x: 500, y: 500 }, FITS)).toEqual({ scale: 1, x: 0, y: 0 });
  });

  it('steps zoom by 0.25 and pans by 10% of the viewport dimension', () => {
    expect(zoomBy({ scale: 1, x: 0, y: 0 }, ZOOM_STEP, BIG).scale).toBe(1.25);
    expect(panBy({ scale: 2, x: 0, y: 0 }, 40, -30, BIG)).toEqual({ scale: 2, x: 40, y: -30 });
  });

  it('resets to fit and computes drag deltas from the drag-start transform', () => {
    expect(resetTransform()).toEqual(FIT_TRANSFORM);
    expect(
      dragPan({ scale: 2, x: 10, y: 0 }, { x: 100, y: 100 }, { x: 150, y: 80 }, BIG),
    ).toEqual({ scale: 2, x: 60, y: -20 });
  });
});

describe('ZoomPanControls behavior (u3)', () => {
  it('offers named single-pointer buttons for zoom, pan and reset', () => {
    render(<Harness />);
    for (const name of ['축소', '확대', '왼쪽', '오른쪽', '위', '아래', '원래 크기']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
  });

  it('steps zoom by 0.25 from the buttons and resets', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: '확대' }));
    expect(screen.getByTestId('scale').textContent).toBe('1.25');
    fireEvent.click(screen.getByRole('button', { name: '축소' }));
    expect(screen.getByTestId('scale').textContent).toBe('1');
    fireEvent.click(screen.getByRole('button', { name: '왼쪽' }));
    // Content (800×600) exceeds the 400×300 viewport even at 1x, so a left pan
    // step moves by 10% of the viewport width and stays inside the clamp.
    expect(screen.getByTestId('x').textContent).toBe('-40');
  });

  it('disables the zoom buttons at the bounds', () => {
    render(<Harness initial={{ scale: ZOOM_MAX, x: 0, y: 0 }} />);
    expect(screen.getByRole('button', { name: '확대' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '축소' }));
    expect(screen.getByTestId('scale').textContent).toBe(String(ZOOM_MAX - ZOOM_STEP));
  });

  it('applies +, arrow and 0 shortcuts only on the focused group and never traps Tab', () => {
    render(<Harness />);
    const group = screen.getByRole('group', { name: '확대 및 이동' });
    group.focus();

    fireEvent.keyDown(group, { key: '+' });
    expect(screen.getByTestId('scale').textContent).toBe('1.25');
    fireEvent.keyDown(group, { key: 'ArrowRight' });
    expect(screen.getByTestId('x').textContent).toBe('40');
    fireEvent.keyDown(group, { key: 'ArrowDown' });
    expect(screen.getByTestId('y').textContent).toBe('30');
    fireEvent.keyDown(group, { key: '0' });
    expect(screen.getByTestId('scale').textContent).toBe('1');
    expect(screen.getByTestId('x').textContent).toBe('0');
    expect(screen.getByTestId('y').textContent).toBe('0');

    // Tab is ordinary navigation: the group must not intercept it (no trap).
    fireEvent.keyDown(group, { key: 'Tab' });
    expect(screen.getByTestId('scale').textContent).toBe('1');
  });
});

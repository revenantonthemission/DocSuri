import { afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor, within, cleanup } from '@testing-library/react';
import { DocModelViewer, DocModelBody } from '@/components/DocModelViewer';
import { preloadMathEngine } from '@/lib/renderMath';
import { docModelResponse } from '@/mocks/summarizeFixtures';
import { clearJobDiagnostics, emitJobDiagnostic, readJobDiagnostics } from '@/lib/jobDiagnostics';
import type { AssetRef } from '@/types/generated';

// U3 — viewer asset states (skeleton → ready/failure), the bounded
// decoded-readiness measurement, owner-context clearing, and the zoom overlay's
// named controls + noninteractive minimap. Uses the mock transport fixtures
// (figure assetId 2401.00001:v1:figure:0).

beforeAll(async () => {
  // jsdom has no PointerEvent; React only wires pointer listeners when the
  // interface exists, so alias it to MouseEvent (clientX/button ride along).
  if (!('PointerEvent' in window)) {
    (window as unknown as { PointerEvent: typeof MouseEvent }).PointerEvent = MouseEvent;
  }
  await preloadMathEngine();
});

beforeEach(() => {
  clearJobDiagnostics();
});

afterEach(() => {
  // Portalled overlays and async mock-transport renders must never leak into
  // the next test — the gate runs this file under coverage load.
  cleanup();
  clearJobDiagnostics();
});

// Non-awaiting lookup for act-and-retry loops: under load the async mock
// transport can re-render the figure subtree and detach a previously resolved
// node, so every attempt must re-resolve the CURRENT element before acting.
function currentFigureImg(): HTMLElement | null {
  return (
    (screen.getAllByRole('img').find((element) => element.tagName === 'IMG') as
      | HTMLElement
      | undefined) ?? null
  );
}

// jsdom reports zero-size boxes; the overlay's fit/pan math needs a viewport.
function mockViewportSizes(): void {
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
    configurable: true,
    get() {
      return 800;
    },
  });
  Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
    configurable: true,
    get() {
      return 600;
    },
  });
  Object.defineProperty(HTMLElement.prototype, 'scrollWidth', {
    configurable: true,
    get() {
      return 400;
    },
  });
  Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
    configurable: true,
    get() {
      return 300;
    },
  });
}

// The overlay open is RETRIED: under heavy concurrent load the mock transport's
// async settle can re-render the figure subtree between resolving the trigger
// and clicking it, detaching the node (the intra-test race the gate exposed).
async function openFigureOverlay(): Promise<HTMLElement> {
  await waitFor(
    () => {
      const img = screen.getAllByRole('img').find((element) => element.tagName === 'IMG');
      const block = img?.closest('[data-block]');
      const trigger = block?.querySelector('[data-testid="docmodel-zoom-trigger"]');
      if (trigger) fireEvent.click(trigger);
      expect(screen.queryByTestId('block-zoom')).not.toBeNull();
    },
    { timeout: 10000 },
  );
  return screen.getByTestId('block-zoom');
}

function latestAssetEvent() {
  return readJobDiagnostics()
    .map((record) => record.event)
    .reverse()
    .find((event) => event.kind === 'asset');
}

describe('viewer asset states and readiness (u3)', () => {
  it('shows a skeleton with accessible loading text until the image loads, then measures readiness', async () => {
    render(<DocModelViewer paperId="2401.00001" version={1} anchor={null} />);

    await waitFor(
      () => {
        const img = currentFigureImg();
        if (!img) return;
        expect(img.closest('[data-state]')?.getAttribute('data-state')).toBe('loading');
        expect(screen.getByText('이미지 불러오는 중')).toBeTruthy();
        fireEvent.load(img);
        expect(img.closest('[data-state]')?.getAttribute('data-state')).toBe('ready');
      },
      { timeout: 10000 },
    );
    expect(screen.queryByText('이미지 불러오는 중')).toBeNull();

    const asset = latestAssetEvent();
    expect(asset?.kind).toBe('asset');
    if (asset?.kind === 'asset') {
      expect(asset.outcome).toBe('ready');
      const readiness = asset.readinessMs;
      expect(readiness !== undefined && readiness >= 0 && readiness <= 600000).toBe(true);
    }
  });

  it('shows the generic failure state on an image error without inventing an HTTP status', async () => {
    render(<DocModelViewer paperId="2401.00001" version={1} anchor={null} />);

    await waitFor(
      () => {
        const img = currentFigureImg();
        if (img) fireEvent.error(img);
        expect(screen.queryByRole('img', { name: '이미지를 표시할 수 없습니다' })).not.toBeNull();
      },
      { timeout: 10000 },
    );
    const fallback = screen.getByRole('img', { name: '이미지를 표시할 수 없습니다' });
    expect(fallback.textContent).toContain('이미지를 표시할 수 없습니다');
    // An image error event never reveals denial status — the copy makes no HTTP claim.
    expect(fallback.textContent).not.toMatch(/40[0-9]|50[0-9]/);

    const asset = latestAssetEvent();
    if (asset?.kind === 'asset') {
      expect(asset.outcome).toBe('failed');
    }
  });

  it('clears a previous owner-context image when the asset identity changes', async () => {
    const assetId = '2401.00001:v1:figure:0';
    const refA = { assetId, url: '/api/papers/p1/assets/a1' } as AssetRef;
    const refB = { assetId, url: '/api/papers/p1/assets/a2' } as AssetRef;

    const { rerender } = render(
      <DocModelBody docModel={docModelResponse.docModel} assetsById={new Map([[assetId, refA]])} />,
    );
    await waitFor(
      () => {
        const img = currentFigureImg();
        if (!img) return;
        expect(img.getAttribute('src')).toBe('/bff/api/papers/p1/assets/a1');
        fireEvent.load(img);
        expect(img.closest('[data-state]')?.getAttribute('data-state')).toBe('ready');
      },
      { timeout: 10000 },
    );

    rerender(
      <DocModelBody docModel={docModelResponse.docModel} assetsById={new Map([[assetId, refB]])} />,
    );
    await waitFor(
      () => {
        const img2 = currentFigureImg();
        expect(img2?.getAttribute('src')).toBe('/bff/api/papers/p1/assets/a2');
        // The new identity starts fresh — no stale ready state from the previous image.
        expect(img2?.closest('[data-state]')?.getAttribute('data-state')).toBe('loading');
      },
      { timeout: 10000 },
    );
  });

  it('sanitizes the asset readiness measurement and keeps the bare ready outcome', () => {
    emitJobDiagnostic({ kind: 'asset', outcome: 'ready' }, 1);
    emitJobDiagnostic({ kind: 'asset', outcome: 'ready', readinessMs: Number.NaN }, 2);
    emitJobDiagnostic({ kind: 'asset', outcome: 'failed' }, 3);

    const events = readJobDiagnostics()
      .map((record) => record.event)
      .filter((event) => event.kind === 'asset');
    expect(events).toHaveLength(3);
    const [bare, invalid, failed] = events;
    if (bare?.kind !== 'asset' || invalid?.kind !== 'asset' || failed?.kind !== 'asset') {
      throw new Error('unreachable');
    }
    expect(bare.readinessMs).toBeUndefined();
    expect(invalid.readinessMs).toBeUndefined();
    expect(failed.outcome).toBe('failed');
  });
});

describe('zoom overlay controls and minimap (u3)', () => {
  it('renders named controls; zooming reveals the noninteractive minimap with the same image', async () => {
    mockViewportSizes();

    render(<DocModelViewer paperId="2401.00001" version={1} anchor={null} />);
    // Zoom the FIGURE block specifically (its overlay content is the image, so the
    // minimap duplicate can be compared against the same authorized source).
    const overlay = await openFigureOverlay();
    const controls = within(overlay).getByRole('group', { name: '확대 및 이동' });
    for (const name of ['축소', '확대', '왼쪽', '오른쪽', '위', '아래', '원래 크기']) {
      expect(within(controls).getByRole('button', { name })).toBeInTheDocument();
    }

    // The overview only exists while enlarged (fit = 1x is the default).
    expect(within(overlay).queryByTestId('zoom-minimap')).toBeNull();
    fireEvent.click(within(controls).getByRole('button', { name: '확대' }));

    const minimap = await within(overlay).findByTestId('zoom-minimap', undefined, {
      timeout: 5000,
    });
    expect(minimap.getAttribute('aria-hidden')).toBe('true');
    expect(minimap.hasAttribute('inert')).toBe(true);
    // The minimap duplicates the SAME authorized image (no alternate source) and
    // stays noninteractive (pointer-events: none in CSS; inert for focus/AT).
    const minimapImgs = minimap.querySelectorAll('img');
    expect(minimapImgs.length).toBeGreaterThan(0);
    const mainImg = overlay.querySelector('img');
    expect(minimapImgs[0]?.getAttribute('src')).toBe(mainImg?.getAttribute('src'));
  });

  it('clears the open overview when the asset map is cleared (known access loss)', async () => {
    mockViewportSizes();
    const assetId = '2401.00001:v1:figure:0';
    const ref = { assetId, url: '/api/papers/p1/assets/a1' } as AssetRef;

    const { rerender } = render(
      <DocModelBody docModel={docModelResponse.docModel} assetsById={new Map([[assetId, ref]])} />,
    );
    await openFigureOverlay();

    rerender(<DocModelBody docModel={docModelResponse.docModel} assetsById={new Map()} />);
    await waitFor(() => expect(screen.queryByTestId('block-zoom')).toBeNull(), { timeout: 5000 });
  });

  it('pans by pointer drag only when enlarged and ends on pointer cancellation', async () => {
    mockViewportSizes();
    render(<DocModelViewer paperId="2401.00001" version={1} anchor={null} />);

    const overlay = await openFigureOverlay();
    const controls = within(overlay).getByRole('group', { name: '확대 및 이동' });
    const content = within(overlay).getByTestId('zoom-content');

    // A drag at fit scale must not start (content fits the viewport).
    fireEvent.pointerDown(content, { button: 0, clientX: 0, clientY: 0, pointerId: 1 });
    fireEvent.pointerMove(content, { clientX: 50, clientY: 50, pointerId: 1 });
    expect(content.style.transform).toContain('translate(0px, 0px)');

    // Enlarged, a drag pans (clamped to the pan bounds).
    fireEvent.click(within(controls).getByRole('button', { name: '확대' }));
    fireEvent.pointerDown(content, { button: 0, clientX: 0, clientY: 0, pointerId: 2 });
    fireEvent.pointerMove(content, { clientX: 40, clientY: 20, pointerId: 2 });
    expect(content.style.transform).toContain('translate(40px, 20px)');

    // Pointer cancellation ends the drag only — a later move changes nothing.
    fireEvent.pointerCancel(content, { pointerId: 2 });
    fireEvent.pointerMove(content, { clientX: 200, clientY: 200, pointerId: 2 });
    expect(content.style.transform).toContain('translate(40px, 20px)');
  });
});

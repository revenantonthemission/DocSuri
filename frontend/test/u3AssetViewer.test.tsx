import { describe, it, expect, vi, afterEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

// U3 secure asset viewing — the migrated AssetViewer renders authorized bytes
// through the same-origin BFF hop only: no presigned URL, no token, no
// redirect flow, and no alternate delivery URL anywhere.

import { AssetViewer } from '@/components/AssetViewer';
import { browserAssetSrc } from '@/lib/api/assetSrc';

const REPO_ROOT = join(__dirname, '..', '..');

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AssetViewer same-origin migration (u3)', () => {
  it('renders the same-origin BFF asset path with encoded identities', () => {
    render(<AssetViewer paperId="2401.00001" assetId="a b/0" />);

    const img = screen.getByRole('img', { name: '자산 이미지' });
    expect(img.getAttribute('src')).toBe('/bff/api/papers/2401.00001/assets/a%20b%2F0');
  });

  it('shows the loading spinner until the image loads, then hides it', () => {
    render(<AssetViewer paperId="p1" assetId="a1" />);

    const img = screen.getByRole('img', { name: '자산 이미지' });
    expect(img.className).toContain('opacity-0');

    fireEvent.load(img);
    expect(img.className).not.toContain('opacity-0');
  });

  it('switches to the failure state on an image error and retries without a reload', () => {
    const onError = vi.fn();
    render(<AssetViewer paperId="p1" assetId="a1" onError={onError} />);

    fireEvent.error(screen.getByRole('img', { name: '자산 이미지' }));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(screen.getByText('자산 로드 실패')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    // Retry remounts the same-origin image in the loading state (never a page reload).
    const img = screen.getByRole('img', { name: '자산 이미지' });
    expect(img.getAttribute('src')).toBe('/bff/api/papers/p1/assets/a1');
    expect(img.className).toContain('opacity-0');
  });

  it('never mentions presigned delivery, tokens, or storage hosts in the migrated surfaces', () => {
    const viewer = readFileSync(join(REPO_ROOT, 'frontend/components/AssetViewer.tsx'), 'utf8');
    const page = readFileSync(join(REPO_ROOT, 'frontend/components/UnsubscribePage.tsx'), 'utf8');
    const api = readFileSync(join(REPO_ROOT, 'frontend/lib/api/contentJobApi.ts'), 'utf8');

    for (const source of [viewer, page, api]) {
      expect(source).not.toMatch(/getAssetUrl|issueAssetToken|X-Amz|amazonaws\.com|presigned\s+URL/i);
    }
    expect(viewer).toContain('browserAssetSrc');
    expect(page).toContain('paperId={state.paperId}');
    expect(page).not.toContain('token=""');
  });
});

describe('browserAssetSrc fails closed (u3)', () => {
  it('rewrites canonical delivery paths onto the BFF and passes dev-mock data URLs', () => {
    expect(browserAssetSrc('/api/papers/p1/assets/a1')).toBe('/bff/api/papers/p1/assets/a1');
    expect(browserAssetSrc('data:image/svg+xml;utf8,<svg/>')).toBe('data:image/svg+xml;utf8,<svg/>');
    expect(browserAssetSrc(null)).toBeUndefined();
  });

  it('refuses off-origin, storage-host and relative URLs instead of emitting them', () => {
    for (const bad of [
      'https://s3.ap-northeast-2.amazonaws.com/bkt/k.webp?X-Amz-Signature=leak',
      'http://gateway.internal.test/api/papers/p1/assets/a1',
      'assets/a1.webp',
      '//evil.example/a.png',
    ]) {
      expect(browserAssetSrc(bad)).toBeUndefined();
    }
  });
});

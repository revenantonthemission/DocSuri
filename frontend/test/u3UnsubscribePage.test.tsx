import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { UnsubscribePage } from '@/components/UnsubscribePage';

// U3 — the UnsubscribePage mount of the migrated same-origin AssetViewer:
// the viewer renders only when the verified response carries the paper
// identity the same-origin BFF path requires, and every error path keeps the
// existing Korean messaging.

let token: string | null = 'tok-1';

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(token ? `token=${token}` : ''),
}));

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  token = 'tok-1';
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function verifyResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('UnsubscribePage asset mount (u3)', () => {
  it('renders the migrated viewer on the same-origin path when the paper identity is present', async () => {
    fetchMock.mockResolvedValue(
      verifyResponse({ status: 'success', assetId: 'a1', paperId: 'p1' }),
    );

    render(<UnsubscribePage />);

    expect(await screen.findByText('수신 해지 완료')).toBeInTheDocument();
    const img = screen.getByRole('img', { name: '자산 이미지' });
    expect(img.getAttribute('src')).toBe('/bff/api/papers/p1/assets/a1');
  });

  it('omits the viewer when the verified response carries no paper identity', async () => {
    fetchMock.mockResolvedValue(verifyResponse({ status: 'success', assetId: 'a1' }));

    render(<UnsubscribePage />);

    expect(await screen.findByText('수신 해지 완료')).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: '자산 이미지' })).not.toBeInTheDocument();
  });

  it('keeps the existing expired-token messaging and no viewer on 401', async () => {
    fetchMock.mockResolvedValue(verifyResponse({ detail: 'expired' }, 401));

    render(<UnsubscribePage />);

    expect(await screen.findByText('수신 해지 실패')).toBeInTheDocument();
    expect(screen.getByText('토큰이 만료되었습니다.')).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: '자산 이미지' })).not.toBeInTheDocument();
  });

  it('shows the controlled failure state when verification throws', async () => {
    fetchMock.mockRejectedValue(new Error('network down'));

    render(<UnsubscribePage />);

    expect(await screen.findByText('수신 해지 실패')).toBeInTheDocument();
    expect(screen.getByText('잘못된 토큰입니다.')).toBeInTheDocument();
  });
});

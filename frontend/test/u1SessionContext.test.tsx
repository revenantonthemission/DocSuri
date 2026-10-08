import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { SessionProvider, useSession } from '@/components/session/SessionContext';

const api = vi.hoisted(() => ({
  currentSession: vi.fn(),
  logout: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  getApiClient: () => ({
    currentSession: api.currentSession,
    logout: api.logout,
  }),
}));

function Probe(): React.JSX.Element {
  const { status, user, signOut } = useSession();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user">{user?.userId ?? 'none'}</span>
      <button type="button" onClick={() => void signOut()}>
        로그아웃
      </button>
    </div>
  );
}

beforeEach(() => {
  api.currentSession.mockReset();
  api.logout.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('SessionContext (job-surface identity source)', () => {
  it('resolves the authenticated identity from currentSession', async () => {
    api.currentSession.mockResolvedValue({
      userId: 'user-1',
      expiresAt: '2026-12-31T00:00:00Z',
    });

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authenticated'));
    expect(screen.getByTestId('user')).toHaveTextContent('user-1');
  });

  it('degrades to anonymous when the session read fails (no crash, no leak)', async () => {
    api.currentSession.mockRejectedValue(new Error('session read failed'));

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'));
    expect(screen.getByTestId('user')).toHaveTextContent('none');
  });

  it('clears identity on sign-out', async () => {
    api.currentSession.mockResolvedValue({
      userId: 'user-1',
      expiresAt: '2026-12-31T00:00:00Z',
    });
    api.logout.mockResolvedValue(undefined);

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authenticated'));

    fireEvent.click(screen.getByRole('button', { name: '로그아웃' }));
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'));
    expect(api.logout).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('user')).toHaveTextContent('none');
  });
});

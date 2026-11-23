// U8 plan Step 42 (your decision of 2026-10-23): reactivation in the complete entry. The
// request sends `access-request-reactivation` and answers the same whatever the account;
// the `/account/reactivate` link page removes the proof from the address before it calls
// `lifecycle-reactivate`; a refused or used proof shows its message and a way back.
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/api';
import { CompleteEntry } from '../../src/u8-entry/entry-panel';
import { apiError, fakeClient, Fresh, type Answer } from './helpers';

const POLICY = { policyId: 'u8-synthetic-v1', revision: '1' };
const LINK = '/account/reactivate#challenge=ch-9&proof=pr-9&flow=fl-9';

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, '', '/');
});

function entry(answer: Answer) {
  const fake = fakeClient(answer);
  const onSignedIn = vi.fn(async () => undefined);
  render(
    <Fresh>
      <CompleteEntry client={fake.transport} states={{}} onSignedIn={onSignedIn} />
    </Fresh>,
  );
  return { ...fake, onSignedIn };
}

describe('the reactivation request', () => {
  it('asks for an address, then sends the request', async () => {
    const fake = entry(() => ({ requestId: 'r-1' }));
    fireEvent.click(screen.getByTestId('entry-reactivate'));
    expect(screen.getByText('이메일을 입력해 주세요')).toBeInTheDocument();
    expect(fake.post).not.toHaveBeenCalled();
    fireEvent.change(screen.getByTestId('entry-email'), {
      target: { value: 'withdrawn@example.test' },
    });
    fireEvent.click(screen.getByTestId('entry-reactivate'));
    expect(
      await screen.findByText(
        '요청을 접수했습니다. 탈퇴한 계정이 있으면 재활성화 링크를 이메일로 보냅니다. 메일의 링크는 이 브라우저에서 열어 주세요.',
      ),
    ).toBeInTheDocument();
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c02/access-request-reactivation', {
      email: 'withdrawn@example.test',
      policyRef: POLICY,
    });
  });

  it('shows the same answer whatever the account', async () => {
    // The server answers every address alike; the page adds nothing of its own.
    const shown: string[] = [];
    for (const address of ['withdrawn@example.test', 'unknown@example.test']) {
      cleanup();
      entry(() => ({ requestId: `r-${address}` }));
      fireEvent.change(screen.getByTestId('entry-email'), { target: { value: address } });
      fireEvent.click(screen.getByTestId('entry-reactivate'));
      const status = await screen.findByText(
        '요청을 접수했습니다. 탈퇴한 계정이 있으면 재활성화 링크를 이메일로 보냅니다. 메일의 링크는 이 브라우저에서 열어 주세요.',
      );
      shown.push(status.textContent ?? '');
    }
    expect(new Set(shown).size).toBe(1);
    expect(shown[0]).not.toMatch(/withdrawn|unknown/);
  });
});

describe('the /account/reactivate link page', () => {
  it('removes the proof from the address before calling lifecycle-reactivate', async () => {
    window.history.replaceState(null, '', LINK);
    const seen: { path: string; hash: string; href: string }[] = [];
    const fake = entry((path) => {
      seen.push({ path, hash: window.location.hash, href: window.location.href });
      return { lifecycleRequestId: 'lr-1', state: 'accepted' };
    });
    expect(window.location.hash).toBe('');
    expect(window.location.pathname).toBe('/account/reactivate');
    expect(screen.getByText('탈퇴한 계정의 재활성화를 확인해 주세요')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('proof-submit'));
    expect(
      await screen.findByText('재활성화를 접수했습니다. 처리가 끝나면 다시 로그인할 수 있습니다.'),
    ).toBeInTheDocument();
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c02/lifecycle-reactivate', {
      confirmationRef: 'ch-9',
      verification: { challengeId: 'ch-9', proof: 'pr-9', flowBinding: 'fl-9' },
      policyRef: POLICY,
    });
    const call = seen.find((item) => item.path === '/api/v2/c02/lifecycle-reactivate');
    expect(call?.hash).toBe('');
    expect(call?.href).not.toContain('pr-9');
    expect(screen.queryByTestId('proof-form')).toBeNull();
  });

  it('moves focus to the sign-in address, never the body, after a completed proof', async () => {
    window.history.replaceState(null, '', LINK);
    const user = userEvent.setup();
    entry(() => ({ lifecycleRequestId: 'lr-1', state: 'accepted' }));
    screen.getByTestId('proof-submit').focus();
    await user.keyboard('{Enter}');
    expect(
      await screen.findByText('재활성화를 접수했습니다. 처리가 끝나면 다시 로그인할 수 있습니다.'),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
    expect(document.activeElement).not.toBe(document.body);
  });

  it('moves focus to the sign-in address, never the body, when the proof is left', async () => {
    window.history.replaceState(null, '', LINK);
    const user = userEvent.setup();
    entry(() => ({}));
    screen.getByTestId('proof-back').focus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(screen.queryByTestId('proof-form')).toBeNull());
    await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
    expect(document.activeElement).not.toBe(document.body);
  });

  it('shows a refused or already used proof its message and a way back', async () => {
    // AccountAccess refuses an unknown, expired or spent proof alike, with a 403.
    window.history.replaceState(null, '', LINK);
    entry(() => apiError(403, 'FORBIDDEN'));
    fireEvent.click(screen.getByTestId('proof-submit'));
    expect(
      await screen.findByText(
        '이 재활성화 링크는 재활성화를 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 재활성화를 다시 요청해 주세요.',
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('proof-back'));
    await waitFor(() => expect(screen.queryByTestId('proof-form')).toBeNull());
    expect(screen.getByTestId('sign-in-form')).toBeInTheDocument();
    expect(
      screen.queryByText(
        '이 재활성화 링크는 재활성화를 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 재활성화를 다시 요청해 주세요.',
      ),
    ).toBeNull();
    await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
  });

  it('a refused reactivation link offers to ask again here', async () => {
    window.history.replaceState(null, '', LINK);
    const fake = entry((path) =>
      path === '/api/v2/c02/access-request-reactivation' ? {} : apiError(403, 'FORBIDDEN'),
    );
    expect(screen.getByTestId('proof-binding-note')).toHaveTextContent(
      '이 링크는 요청한 브라우저에서만 쓸 수 있습니다.',
    );
    fireEvent.click(screen.getByTestId('proof-submit'));
    expect(
      await screen.findByText(
        '이 재활성화 링크는 재활성화를 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 재활성화를 다시 요청해 주세요.',
      ),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('proof-ask-email')).toHaveFocus());
    // proof-back still returns to the sign-in form while the controls show.
    expect(screen.getByTestId('proof-back')).toBeInTheDocument();
    fireEvent.change(screen.getByTestId('proof-ask-email'), {
      target: { value: 'withdrawn@example.test' },
    });
    fireEvent.click(screen.getByTestId('proof-ask-again'));
    expect(
      await screen.findByText(
        '요청을 접수했습니다. 탈퇴한 계정이 있으면 재활성화 링크를 이메일로 보냅니다. 메일의 링크는 이 브라우저에서 열어 주세요.',
      ),
    ).toBeInTheDocument();
    expect(fake.post).toHaveBeenLastCalledWith('/api/v2/c02/access-request-reactivation', {
      email: 'withdrawn@example.test',
      policyRef: POLICY,
    });
    await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
  });

  it('proof-back returns to the sign-in form after a refusal', async () => {
    window.history.replaceState(null, '', LINK);
    entry(() => apiError(403, 'FORBIDDEN'));
    fireEvent.click(screen.getByTestId('proof-submit'));
    await screen.findByTestId('proof-ask-again');
    fireEvent.click(screen.getByTestId('proof-back'));
    await waitFor(() => expect(screen.getByTestId('sign-in-form')).toBeInTheDocument());
    expect(screen.queryByTestId('proof-ask-again')).toBeNull();
  });

  it('keeps any other failure in the plain error message', async () => {
    window.history.replaceState(null, '', LINK);
    const fake = entry(() => apiError(503, 'UNAVAILABLE'));
    fireEvent.click(screen.getByTestId('proof-submit'));
    await waitFor(() => expect(fake.post).toHaveBeenCalledTimes(1));
    // The busy rule keeps the control enabled (aria-disabled), so wait for the answer itself.
    expect(await screen.findByRole('alert')).toHaveTextContent('문제가 발생했어요');
    await waitFor(() =>
      expect(screen.getByTestId('proof-submit')).toHaveAttribute('aria-disabled', 'false'),
    );
    expect(
      screen.queryByText(
        '이 재활성화 링크는 재활성화를 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 재활성화를 다시 요청해 주세요.',
      ),
    ).toBeNull();
    expect(screen.queryByTestId('proof-ask-again')).toBeNull();
    expect(screen.getByTestId('proof-back')).toBeInTheDocument();
  });
});

describe('account mail at its limit', () => {
  it('a reactivation request at account mail’s limit says when email can be sent again', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-01T14:30:00Z'));
    try {
      entry(
        () =>
          new ApiError(429, {
            code: 'RATE_LIMITED',
            requestId: 'req-mail-2',
            retryable: true,
            messageKey: 'account-mail.allowance-exhausted',
            retryAfterSeconds: 34200,
          }),
      );
      fireEvent.change(screen.getByTestId('entry-email'), {
        target: { value: 'withdrawn@example.test' },
      });
      fireEvent.click(screen.getByTestId('entry-reactivate'));
      expect(await screen.findByRole('alert')).toHaveTextContent(
        '지금은 이메일을 보낼 수 없습니다. 11월 2일 오전 9시(한국 시간)부터 다시 보낼 수 있습니다.',
      );
      expect(screen.queryByText(/요청을 접수했습니다/)).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('keyboard parity for the entry’s reset and reactivation', () => {
  function pending() {
    const releases: ((value: unknown) => void)[] = [];
    const fake = entry(() => new Promise((resolve) => releases.push(resolve)));
    return { fake, release: () => releases.splice(0).forEach((resolve) => resolve({})) };
  }

  it('acts by Enter after Tab as by a click, and each control keeps focus while it runs', async () => {
    const user = userEvent.setup();
    const { fake, release } = pending();
    fireEvent.change(screen.getByTestId('entry-email'), {
      target: { value: 'withdrawn@example.test' },
    });
    for (const testId of ['entry-reset', 'entry-reactivate']) {
      const control = screen.getByTestId(testId);
      for (let step = 0; step < 8 && document.activeElement !== control; step += 1)
        await user.tab();
      expect(control).toHaveFocus();
      await user.keyboard('{Enter}');
      expect(control).toHaveFocus();
      expect(control).toHaveAttribute('aria-disabled', 'true');
      release();
      await waitFor(() => expect(control).toHaveAttribute('aria-disabled', 'false'));
    }
    expect(fake.post.mock.calls.map(([path]) => path)).toEqual([
      '/api/v2/c02/access-request-password-reset',
      '/api/v2/c02/access-request-reactivation',
    ]);
  });

  it('submits the proof form by Enter and asks again by Enter after Tab', async () => {
    window.history.replaceState(null, '', LINK);
    const user = userEvent.setup();
    const releases: ((value: unknown) => void)[] = [];
    const fake = entry((path) =>
      path === '/api/v2/c02/access-request-reactivation'
        ? new Promise((resolve) => releases.push(resolve))
        : apiError(403, 'FORBIDDEN'),
    );
    screen.getByTestId('proof-submit').focus();
    await user.keyboard('{Enter}');
    const ask = await screen.findByTestId('proof-ask-email');
    await waitFor(() => expect(ask).toHaveFocus());
    await user.type(ask, 'withdrawn@example.test');
    await user.tab();
    const again = screen.getByTestId('proof-ask-again');
    expect(again).toHaveFocus();
    await user.keyboard('{Enter}');
    // While its request runs, proof-ask-again keeps focus and is aria-disabled.
    await waitFor(() => expect(releases).toHaveLength(1));
    expect(again).toHaveFocus();
    expect(again).toHaveAttribute('aria-disabled', 'true');
    releases.splice(0).forEach((resolve) => resolve({}));
    await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
    await waitFor(() =>
      expect(fake.post).toHaveBeenLastCalledWith('/api/v2/c02/access-request-reactivation', {
        email: 'withdrawn@example.test',
        policyRef: POLICY,
      }),
    );
    expect(fake.post.mock.calls[0]![0]).toBe('/api/v2/c02/lifecycle-reactivate');
  });
});

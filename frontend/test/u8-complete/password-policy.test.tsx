// A new password the password policy refuses (your answer of 2026-11-11, "Say the password
// is too weak"): every screen of the complete app that submits a new password shows one
// plain line when the answer carries `messageKey` `password.policy`, in its own register.
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/api';
import { AccountControls, PASSWORD_REFUSED } from '../../src/account-controls';
import { CompleteEntry, FRESH_BROWSER, WEAK_PASSWORD } from '../../src/u8-entry/entry-panel';
import { fakeClient as accountClient, policy } from '../u2-account-personal-controls/fixtures';
import { apiError, fakeClient, Fresh, type Answer } from './helpers';

vi.mock('qrcode', () => ({ default: { toCanvas: vi.fn().mockResolvedValue(undefined) } }));

// Every password these tests type is generated per run (L1-36): the refusals come from the
// fakes, so only each value's role matters.
const WEAK_VALUE = `weak-${crypto.randomUUID().slice(0, 8)}`;
const STRONG_VALUE = `Strong-${crypto.randomUUID().slice(0, 8)}-1!`;
const CURRENT_VALUE = `current-${crypto.randomUUID().slice(0, 8)}`;

function policyRefusal(): ApiError {
  return new ApiError(422, {
    code: 'INVALID_ARGUMENT',
    requestId: 'request-weak',
    retryable: false,
    messageKey: 'password.policy',
  } as ConstructorParameters<typeof ApiError>[1]);
}

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

function entry(answer: Answer) {
  window.history.replaceState(null, '', '/account/password-reset#challenge=ch&proof=pr&flow=fl');
  const fake = fakeClient(answer);
  render(
    <Fresh>
      <CompleteEntry
        client={fake.transport}
        states={{}}
        onSignedIn={vi.fn(async () => undefined)}
      />
    </Fresh>,
  );
  return fake;
}

function submitNewPassword(value: string) {
  fireEvent.change(screen.getByTestId('proof-password'), { target: { value } });
  fireEvent.click(screen.getByTestId('proof-submit'));
}

describe('the entry screens say a refused new password is too weak', () => {
  it('shows the 합니다 line for a reset completion the policy refuses', async () => {
    const fake = entry(() => policyRefusal());
    submitNewPassword(WEAK_VALUE);
    expect(
      await screen.findByText(
        '이 비밀번호는 사용할 수 없습니다. 더 길고 추측하기 어려운 비밀번호를 입력해 주세요.',
      ),
    ).toBeInTheDocument();
    expect(WEAK_PASSWORD).toBe(
      '이 비밀번호는 사용할 수 없습니다. 더 길고 추측하기 어려운 비밀번호를 입력해 주세요.',
    );
    expect(screen.getByRole('alert')).toHaveTextContent(WEAK_PASSWORD);
    // The proof stays, so the person can try a stronger password with the same link.
    expect(screen.getByTestId('proof-form')).toBeInTheDocument();
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c02/access-complete-password-reset', {
      verification: { challengeId: 'ch', proof: 'pr', flowBinding: 'fl' },
      newPassword: WEAK_VALUE,
    });
  });

  it('keeps the other refusals: another 422 and a fresh browser get their own text', async () => {
    entry(() => apiError(422, 'INVALID_ARGUMENT'));
    submitNewPassword(STRONG_VALUE);
    expect(await screen.findByRole('alert')).not.toHaveTextContent(WEAK_PASSWORD);
  });

  it('still tells a fresh browser it cannot finish a reset requested elsewhere', async () => {
    entry(() => apiError(403, 'FORBIDDEN'));
    submitNewPassword(STRONG_VALUE);
    expect(await screen.findByText(FRESH_BROWSER)).toBeInTheDocument();
    expect(screen.queryByText(WEAK_PASSWORD)).toBeNull();
  });
});

function account() {
  const client = accountClient();
  render(
    <AccountControls
      client={client.transport}
      policy={policy}
      onAuthorityChange={vi.fn().mockResolvedValue({})}
      onLifecycle={vi.fn()}
    />,
  );
  return client;
}

async function changePassword(value: string) {
  await screen.findByDisplayValue('연구자 A');
  fireEvent.click(screen.getByText('비밀번호와 이메일'));
  fireEvent.change(screen.getByLabelText('현재 비밀번호'), { target: { value: CURRENT_VALUE } });
  fireEvent.change(screen.getByLabelText('새 비밀번호'), { target: { value } });
  fireEvent.click(screen.getByText('비밀번호 변경 후 다시 로그인'));
}

describe('the account view says a refused new password is too weak', () => {
  it('shows the 해요 line for a password change the policy refuses', async () => {
    const client = account();
    client.post.mockRejectedValueOnce(policyRefusal());
    await changePassword(WEAK_VALUE);
    expect(
      await screen.findByText(
        '이 비밀번호는 사용할 수 없어요. 더 길고 추측하기 어려운 비밀번호를 입력해 주세요.',
      ),
    ).toBeInTheDocument();
    expect(PASSWORD_REFUSED).toBe(
      '이 비밀번호는 사용할 수 없어요. 더 길고 추측하기 어려운 비밀번호를 입력해 주세요.',
    );
    expect(client.post).toHaveBeenCalledWith(
      '/api/v2/c02/access-change-password',
      { currentPassword: CURRENT_VALUE, newPassword: WEAK_VALUE },
      expect.any(String),
    );
  });

  it('clears the line when the next change succeeds', async () => {
    const client = account();
    client.post.mockRejectedValueOnce(policyRefusal());
    await changePassword(WEAK_VALUE);
    expect(await screen.findByText(PASSWORD_REFUSED)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('새 비밀번호'), {
      target: { value: STRONG_VALUE },
    });
    fireEvent.click(screen.getByText('비밀번호 변경 후 다시 로그인'));
    await waitFor(() => expect(screen.queryByText(PASSWORD_REFUSED)).toBeNull());
    expect(client.post).toHaveBeenLastCalledWith(
      '/api/v2/c02/access-change-password',
      { currentPassword: CURRENT_VALUE, newPassword: STRONG_VALUE },
      expect.any(String),
    );
  });

  it('keeps the built copy for any other refusal of a password change', async () => {
    const client = account();
    client.post.mockRejectedValueOnce(apiError(422, 'INVALID_ARGUMENT'));
    await changePassword(STRONG_VALUE);
    await waitFor(() => expect(client.post).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0));
    expect(screen.queryByText(PASSWORD_REFUSED)).toBeNull();
  });
});

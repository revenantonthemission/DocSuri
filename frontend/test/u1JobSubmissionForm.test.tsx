import { webcrypto } from 'node:crypto';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { JobSubmissionForm } from '@/components/JobSubmissionForm';
import {
  idempotencyStorageKey,
  originalRequestStorageKey,
  readStoredOriginalRequest,
  storeOriginalRequest,
} from '@/lib/idempotencyService';

const session = vi.hoisted(() => ({ userId: 'user-1' }));

vi.mock('@/components/session/SessionContext', () => ({
  useSession: () => ({
    status: 'authenticated',
    user: { userId: session.userId, expiresAt: '2026-12-31T00:00:00Z' },
    signingOut: false,
    refresh: async () => {},
    signOut: async () => {},
  }),
}));

beforeAll(() => {
  if (!globalThis.crypto?.subtle) {
    Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
  }
});

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  session.userId = 'user-1';
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

const ORIGINAL_SUMMARIZE_INPUT = {
  paperId: 'paper-9',
  version: 3,
  targetLang: 'ko',
  persona: 'expert',
  scope: 'full',
};

describe('JobSubmissionForm', () => {
  it('never submits on mount or on a parameter change — only on explicit action', async () => {
    render(
      <JobSubmissionForm paperId="paper-9" version={3} task="summarize" onSubmitted={vi.fn()} />,
    );

    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'beginner' } });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('captures the owner-bound original before sending and submits the complete C1 input once', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ jobId: 'job-1', state: 'SUBMITTED' }));
    const onSubmitted = vi.fn();

    render(
      <JobSubmissionForm paperId="paper-9" version={3} task="summarize" onSubmitted={onSubmitted} />,
    );
    fireEvent.click(screen.getByRole('button', { name: '요약 시작' }));

    await waitFor(() => expect(onSubmitted).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/bff/api/content-jobs/submit');
    const body = JSON.parse(String(init.body)) as {
      taskType: string;
      input: Record<string, unknown>;
      idempotencyKey: string;
    };
    expect(body.taskType).toBe('summarize');
    // C1 caller profile: all five declared JobInput fields, enum-conforming persona.
    expect(body.input).toEqual(ORIGINAL_SUMMARIZE_INPUT);
    expect(body.idempotencyKey).toMatch(/^[a-f0-9]{64}$/);

    // Both the key and the exact owner-bound original are captured before the send.
    expect(window.localStorage.getItem(idempotencyStorageKey('paper-9', 'summarize'))).toBe(
      body.idempotencyKey,
    );
    expect(readStoredOriginalRequest('paper-9', 'summarize')).toEqual({
      key: body.idempotencyKey,
      taskType: 'summarize',
      owner: 'user-1',
      input: ORIGINAL_SUMMARIZE_INPUT,
    });
    expect(onSubmitted).toHaveBeenCalledWith({
      jobId: 'job-1',
      taskType: 'summarize',
      idempotencyKey: body.idempotencyKey,
      input: ORIGINAL_SUMMARIZE_INPUT,
    });
  });

  it('recovers with the CAPTURED original — a diverged draft never rides the original key', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('fetch failed'));
    const onSubmitted = vi.fn();

    render(
      <JobSubmissionForm paperId="paper-9" version={3} task="summarize" onSubmitted={onSubmitted} />,
    );
    fireEvent.click(screen.getByRole('button', { name: '요약 시작' }));

    const recovery = await screen.findByRole('button', { name: '이전 요청 확인' });
    expect(onSubmitted).not.toHaveBeenCalled();
    expect(screen.getByRole('status')).toBeInTheDocument();
    // Conditional focus moved to the recovery affordance.
    expect(document.activeElement).toBe(recovery);

    // The draft diverges AFTER the uncertain send (beginner vs captured expert).
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'beginner' } });

    fetchMock.mockResolvedValueOnce(jsonResponse({ jobId: 'job-2', state: 'SUBMITTED' }));
    fireEvent.click(recovery);

    await waitFor(() => expect(onSubmitted).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const first = JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body)) as {
      input: Record<string, unknown>;
      idempotencyKey: string;
    };
    const second = JSON.parse(String((fetchMock.mock.calls[1] as [string, RequestInit])[1].body)) as {
      input: Record<string, unknown>;
      idempotencyKey: string;
    };
    expect(second.idempotencyKey).toBe(first.idempotencyKey);
    // The ORIGINAL input is replayed, not the edited draft.
    expect(second.input).toEqual(ORIGINAL_SUMMARIZE_INPUT);
    expect(second.input).toEqual(first.input);
  });

  it('does not offer recovery for another owner\u2019s captured request', () => {
    storeOriginalRequest('paper-9', 'summarize', {
      key: 'd'.repeat(64),
      taskType: 'summarize',
      owner: 'user-9',
      input: { paperId: 'paper-9', version: 3, targetLang: 'ko', persona: 'expert', scope: 'full' },
    });

    render(
      <JobSubmissionForm paperId="paper-9" version={3} task="summarize" onSubmitted={vi.fn()} />,
    );
    // The record exists, but it belongs to another session owner — no recovery source.
    expect(screen.queryByRole('button', { name: '이전 요청 확인' })).not.toBeInTheDocument();
  });

  it('disables recovery when no usable original exists', async () => {
    window.localStorage.setItem(originalRequestStorageKey('paper-9', 'summarize'), 'corrupt-value');

    render(
      <JobSubmissionForm paperId="paper-9" version={3} task="summarize" onSubmitted={vi.fn()} />,
    );
    expect(screen.queryByRole('button', { name: '이전 요청 확인' })).not.toBeInTheDocument();

    // A definite (non-network) failure keeps the draft and offers an explicit retry,
    // never a silent same-key re-check.
    fetchMock.mockResolvedValueOnce(jsonResponse({ message: 'bad request' }, 400));
    fireEvent.click(screen.getByRole('button', { name: '요약 시작' }));
    await screen.findByRole('alert');
    expect(screen.queryByRole('button', { name: '이전 요청 확인' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument();
  });
});

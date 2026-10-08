import { webcrypto } from 'node:crypto';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { JobSubmissionForm } from '@/components/JobSubmissionForm';
import {
  idempotencyStorageKey,
  originalRequestStorageKey,
  storeIdempotencyKey,
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

const FEEDBACK = /이전 요청의 원본 정보를 확인할 수 없습니다/;

function seedOriginal(owner: string, task: 'summarize' | 'translate' = 'summarize'): void {
  storeOriginalRequest('paper-9', task, {
    key: 'e'.repeat(64),
    taskType: task,
    owner,
    input: { paperId: 'paper-9', version: 3, targetLang: 'ko', persona: 'expert', scope: 'full' },
  });
}

describe('JobSubmissionForm u2 deltas', () => {
  it('submits the complete translate body only on explicit action', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ jobId: 'job-1', state: 'SUBMITTED' }));
    const onSubmitted = vi.fn();

    render(
      <JobSubmissionForm paperId="paper-9" version={3} task="translate" onSubmitted={onSubmitted} />,
    );

    // No submit on mount or selection change.
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'full' } });
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '번역 시작' }));
    await waitFor(() => expect(onSubmitted).toHaveBeenCalledTimes(1));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/bff/api/content-jobs/submit');
    const body = JSON.parse(String(init.body)) as {
      taskType: string;
      input: Record<string, unknown>;
      idempotencyKey: string;
    };
    expect(body.taskType).toBe('translate');
    expect(body.input).toEqual({
      paperId: 'paper-9',
      version: 3,
      targetLang: 'ko',
      persona: 'expert',
      scope: 'full',
    });
    expect(body.idempotencyKey).toMatch(/^[a-f0-9]{64}$/);
  });

  it('surfaces unavailable-original feedback when a key exists without a usable original', () => {
    // A stored attempt (key) with no captured original at all.
    storeIdempotencyKey('paper-9', 'summarize', 'f'.repeat(64));

    render(
      <JobSubmissionForm paperId="paper-9" version={3} task="summarize" onSubmitted={vi.fn()} />,
    );

    expect(screen.getByText(FEEDBACK)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '이전 요청 확인' })).not.toBeInTheDocument();
  });

  it('surfaces the same feedback for a corrupt stored original', () => {
    storeIdempotencyKey('paper-9', 'summarize', 'f'.repeat(64));
    window.localStorage.setItem(originalRequestStorageKey('paper-9', 'summarize'), 'corrupt-value');

    render(
      <JobSubmissionForm paperId="paper-9" version={3} task="summarize" onSubmitted={vi.fn()} />,
    );

    expect(screen.getByText(FEEDBACK)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '이전 요청 확인' })).not.toBeInTheDocument();
  });

  it('surfaces the same feedback for another owner\u2019s original', () => {
    storeIdempotencyKey('paper-9', 'summarize', 'f'.repeat(64));
    seedOriginal('user-9');

    render(
      <JobSubmissionForm paperId="paper-9" version={3} task="summarize" onSubmitted={vi.fn()} />,
    );

    expect(screen.getByText(FEEDBACK)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '이전 요청 확인' })).not.toBeInTheDocument();
  });

  it('offers recovery with no feedback when the owner-bound original is usable', () => {
    storeIdempotencyKey('paper-9', 'summarize', 'e'.repeat(64));
    seedOriginal('user-1');

    render(
      <JobSubmissionForm paperId="paper-9" version={3} task="summarize" onSubmitted={vi.fn()} />,
    );

    expect(screen.getByRole('button', { name: '이전 요청 확인' })).toBeInTheDocument();
    expect(screen.queryByText(FEEDBACK)).not.toBeInTheDocument();
  });
});

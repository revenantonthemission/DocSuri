// Shared fakes for U8's frontend tests: a Transport stand-in whose read, post and get
// answer by path, and a wrapper giving each test its own SWR cache and live region.
import React from 'react';
import { act } from '@testing-library/react';
import { SWRConfig } from 'swr';
import { vi } from 'vitest';
import { ApiError, type Transport } from '../../src/api';
import { AnnouncerProvider } from '../../src/u8-shell/announcer';

export type Answer = (path: string, body?: unknown, key?: string) => unknown;

export function fakeClient(answer: Answer) {
  const respond = async (path: string, body?: unknown, key?: string) => {
    const value = answer(path, body, key);
    if (value instanceof Error) throw value;
    return value;
  };
  const read = vi.fn(respond);
  const post = vi.fn(respond);
  const get = vi.fn((path: string) => respond(path));
  // The session bootstrap, which refreshes the transport's CSRF token.
  // Its token is generated per run (L1-36).
  const bootstrap = vi.fn(async () => ({ signedIn: false, csrfToken: crypto.randomUUID() }));
  const transport = { read, post, get, bootstrap, generation: 0 } as unknown as Transport;
  return { transport, read, post, get, bootstrap };
}

export function apiError(status: number, code: string): ApiError {
  return new ApiError(status, {
    code,
    requestId: 'local',
    retryable: false,
    messageKey: `request.${code.toLowerCase()}`,
  } as ConstructorParameters<typeof ApiError>[1]);
}

export function Fresh({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <AnnouncerProvider>{children}</AnnouncerProvider>
    </SWRConfig>
  );
}

/** Steps fake time (vi.useFakeTimers() without shouldAdvanceTime) and settles the promises
 * and renders it releases, so every timed test settles SWR the same way (Step 94(h)). */
export async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

export const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

export const notFound = () =>
  json(
    { code: 'NOT_FOUND', requestId: 'local', retryable: false, messageKey: 'request.not_found' },
    404,
  );

/**
 * Typed transport boundary doubles for the U3 frontend suite.
 *
 * Doubles validate the exact request/response shapes the service contracts
 * declare and throw on impossible success, so a component can never pass by
 * mocking a shape the real boundary would refuse.
 */

import { vi } from 'vitest';
import { ApiError, Transport } from '../../src/api';

export type RouteHandler = (body: unknown) => unknown;

export class ContractDouble {
  private handlers = new Map<string, RouteHandler>();
  readonly calls: { method: string; path: string; body: unknown; operationKey?: string }[] = [];
  generation = 1;
  invalidateBoundary = vi.fn();
  subscribe = vi.fn(() => () => undefined);

  on(path: string, handler: RouteHandler): this {
    this.handlers.set(path, handler);
    return this;
  }

  async post<T>(path: string, body: unknown, operationKey?: string): Promise<T> {
    this.calls.push({ method: 'POST', path, body, operationKey });
    const handler = this.handlers.get(path);
    if (!handler) throw new Error(`unexpected post ${path}`);
    return (await handler(body)) as T;
  }

  async get<T>(path: string): Promise<T> {
    this.calls.push({ method: 'GET', path, body: undefined });
    const handler = this.handlers.get(path);
    if (!handler) throw new Error(`unexpected get ${path}`);
    return (await handler(undefined)) as T;
  }

  asTransport(): Transport {
    return this as unknown as Transport;
  }
}

export function apiError(code: string, status = 409): ApiError {
  return new ApiError(status, {
    code,
    requestId: 'req-test-1',
    retryable: false,
    messageKey: `request.${code.toLowerCase()}`,
  });
}

export const paper = {
  paperId: 'paper-alpha',
  versionId: 'paper-alpha:v1',
  eligibilityRevision: '00000000-0000-0000-0000-000000000000',
};

export function searchResponse(overrides: Record<string, unknown> = {}) {
  return {
    executionId: 'exec-1',
    query: {
      query: 'attention',
      modeId: 'lexical',
      orderId: 'relevance',
      filters: [],
      vocabularyRevision: 'u3-paper-options-1',
      policyRef: { policyId: 'u3-paper-search', revision: '1' },
    },
    hits: [
      {
        paper,
        title: '합성 논문 paper-alpha',
        authors: ['연구자 A'],
        snippet: '첫 문단입니다.',
        sourceUrl: 'https://fixture.invalid/paper-alpha/v1',
        availability: 'readable',
        matchExplanation: '검색어 일치',
      },
    ],
    page: { nextCursor: undefined, snapshotRevision: '11111111-1111-1111-1111-111111111111' },
    publication: {
      generationId: '22222222-2222-2222-2222-222222222222',
      publicationRevision: '11111111-1111-1111-1111-111111111111',
      manifestHash: 'a'.repeat(64),
      compatibilityRevision: 'u3-projection-1',
      eligibilityRevision: '11111111-1111-1111-1111-111111111111',
      publishedAt: '2026-10-15T00:00:00+00:00',
      complete: true,
    },
    outcome: 'complete',
    effectiveModeId: 'lexical',
    limitations: [],
    ...overrides,
  } as never;
}

export function readyContent() {
  return {
    availability: 'ready',
    content: {
      paper,
      contentRevision: 'content-r1',
      contentHash: 'b'.repeat(64),
      sections: [
        { sectionId: 's1', heading: 'Introduction', text: '본문 문장입니다.', anchor: 'p1' },
      ],
      assets: [
        {
          assetId: '33333333-3333-3333-3333-333333333333',
          mediaType: 'image/png',
          contentHash: 'c'.repeat(64),
          altText: '합성 그림',
        },
      ],
      sourceUrls: ['https://fixture.invalid/paper-alpha/v1'],
      coverage: 'partial',
      limitations: ['그림 원본은 제공되지 않습니다.'],
      policy: { policyId: 'u3-paper-reading', revision: '1' },
    },
  } as never;
}

export function jobSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    jobId: '44444444-4444-4444-4444-444444444444',
    kind: 'paper-assistance',
    state: 'running',
    revision: 'job-r1',
    seq: 3,
    ownerId: 'owner-a',
    progress: { mode: 'indeterminate' },
    result: null,
    error: null,
    acceptedAt: '2026-10-15T00:00:00+00:00',
    ...overrides,
  } as never;
}

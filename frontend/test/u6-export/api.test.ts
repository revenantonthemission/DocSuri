/** The U6 bindings: C09 paths over the shared Transport, response validators that
refuse malformed content, the derived listing facts, and the new safe-code copy. */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, dispositionCopy, Transport } from '../../src/api';
import {
  checkedResponse,
  destinationRequest,
  effectEnded,
  exportCall,
  findExportCapability,
  isNotionPageLink,
  isSafeLink,
  listingState,
  preselection,
  readConnection,
  tokenProblem,
  unusableReason,
} from '../../src/u6-export/api';
import {
  approval,
  capability,
  connection,
  conforms,
  destinations,
  effect,
  entry,
  envelope,
  ExportDouble,
  historyEntry,
  historyPage,
  PAGE_A,
  PAGE_B,
  PAGE_URL,
  preview,
} from './fixtures';

const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });

afterEach(() => vi.unstubAllGlobals());

describe('exportCall', () => {
  it('posts to the C09 path with the CSRF token and the given key', async () => {
    const calls: { url: string; init: RequestInit | undefined }[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        calls.push({ url, init });
        if (url === '/api/v2/session')
          return json({ signedIn: true, accountId: 'a', authorityRevision: '1', csrfToken: 't' });
        return json(effect());
      }),
    );
    const value = await exportCall(
      new Transport(),
      'execute-approved-export',
      { approvalId: approval().approvalId, bindingHash: approval().bindingHash },
      'press-key-1',
    );
    expect(value).toEqual(effect());
    const post = calls.find((call) => call.url.startsWith('/api/v2/c09/'))!;
    expect(post.url).toBe('/api/v2/c09/execute-approved-export');
    expect(post.init?.method).toBe('POST');
    const headers = post.init?.headers as Record<string, string>;
    expect(headers['Idempotency-Key']).toBe('press-key-1');
    expect(headers['X-CSRF-Token']).toBe('t');
  });

  it('refuses a malformed response as INVALID_CONTENT', async () => {
    const api = new ExportDouble();
    const client = { post: async () => ({ connectionId: 'x' }) } as unknown as Transport;
    await expect(exportCall(client, 'read-notion-connection', {})).rejects.toMatchObject({
      status: 502,
      envelope: { code: 'INVALID_CONTENT' },
    });
    expect(api.calls).toEqual([]);
  });

  it('reads an absent or pending connection as null and rethrows other refusals', async () => {
    const absent = new ExportDouble().on('read-notion-connection', () => {
      throw envelope('NOT_FOUND', 404);
    });
    expect(await readConnection(absent.client())).toBeNull();
    const down = new ExportDouble().on('read-notion-connection', () => {
      throw envelope('DEPENDENCY_UNAVAILABLE', 503);
    });
    await expect(readConnection(down.client())).rejects.toBeInstanceOf(ApiError);
  });
});

describe('response validators', () => {
  it('accept every canonical fixture', () => {
    expect(checkedResponse('read-notion-connection', connection())).toEqual(connection());
    expect(checkedResponse('list-export-destinations', destinations([entry()]))).toBeDefined();
    expect(checkedResponse('prepare-export-preview', preview())).toBeDefined();
    expect(checkedResponse('approve-export-preview', approval())).toBeDefined();
    expect(checkedResponse('read-export-effect', effect())).toBeDefined();
    expect(checkedResponse('list-export-history', historyPage([historyEntry()]))).toBeDefined();
    for (const [name, value] of [
      ['ExportConnection', connection()],
      ['ExportPreview', preview()],
      ['ExportEffect', effect()],
      ['ExportHistoryPage', historyPage([historyEntry()])],
    ] as const)
      expect(conforms(name, value)).toBe(true);
  });

  it('refuse a pending state, an unsafe link and an unknown reason', () => {
    const refuse = (operation: Parameters<typeof checkedResponse>[0], value: unknown) =>
      expect(() => checkedResponse(operation, value)).toThrow(ApiError);
    refuse('read-notion-connection', { ...connection(), state: 'pending' });
    refuse('read-export-effect', { ...effect(), remoteUrl: 'javascript:alert(1)' });
    refuse('read-export-effect', { ...effect(), outcomeReason: 'guessed' });
    refuse('list-export-destinations', destinations([{ ...entry(), title: '' }]));
    refuse('list-export-history', { entries: [], nextCursor: 3 });
    refuse('prepare-export-preview', { ...preview(), renderedText: undefined });
    refuse('approve-export-preview', { ...approval(), state: 'pending' });
    refuse('cancel-export-approval', null);
  });

  it('accept only https links', () => {
    expect(isSafeLink(PAGE_URL)).toBe(true);
    expect(isSafeLink('http://www.notion.so/x')).toBe(false);
    expect(isSafeLink('not a url')).toBe(false);
  });
});

describe('derived listing facts', () => {
  it('derive the four listing states (S2)', () => {
    expect(listingState(destinations([entry()]))).toBe('complete');
    expect(listingState(destinations([]))).toBe('empty');
    expect(listingState(destinations([entry()], { listingComplete: false }))).toBe('partial');
    expect(listingState(destinations([], { listingComplete: false }))).toBe('unavailable');
  });

  it('send only the frozen identity fields of a destination', () => {
    expect(destinationRequest(entry())).toEqual({
      connectionId: entry().connectionId,
      workspaceId: entry().workspaceId,
      parentPageId: PAGE_A,
      formatRevision: '1',
      destinationId: PAGE_A,
    });
    expect(conforms('ExportDestination', destinationRequest(entry()))).toBe(true);
  });

  it('give each unusable reason', () => {
    const real = connection({ destinationScopeIds: [PAGE_B] });
    expect(unusableReason(entry(), real)).toBe('not-allowed');
    expect(unusableReason(entry({ readable: false }), connection())).toBe('unreadable');
    expect(unusableReason(entry({ writable: false }), connection())).toBe('creation-refused');
    expect(unusableReason(entry(), connection())).toBeNull();
    expect(preselection(destinations([entry()]), connection())).toEqual({
      entry: null,
      dropped: false,
    });
  });

  it('know which effect states have ended', () => {
    expect(effectEnded('succeeded')).toBe(true);
    expect(effectEnded('unknown')).toBe(false);
    expect(effectEnded('accepted')).toBe(false);
  });
});

describe('field checks', () => {
  it('apply BR1.2 shape rules without echoing the value', () => {
    expect(tokenProblem('')).toBe('blank');
    expect(tokenProblem('  ok_token  ')).toBeNull();
    expect(tokenProblem('a\nb')).toBe('unprintable');
    expect(tokenProblem('x'.repeat(513))).toBe('too-long');
  });

  it('accept only Notion page links (BR4.7)', () => {
    expect(isNotionPageLink(PAGE_URL)).toBe(true);
    expect(isNotionPageLink(`https://team.notion.site/Page-${'a'.repeat(32)}`)).toBe(true);
    expect(isNotionPageLink('https://www.notion.so/no-id')).toBe(false);
    expect(isNotionPageLink(`https://evil.example/${'a'.repeat(32)}`)).toBe(false);
    expect(isNotionPageLink(`https://u:p@www.notion.so/${'a'.repeat(32)}`)).toBe(false);
    expect(isNotionPageLink(`https://www.notion.so:8443/${'a'.repeat(32)}`)).toBe(false);
    expect(isNotionPageLink('::')).toBe(false);
    expect(isNotionPageLink('')).toBe(false);
  });
});

describe('the shell capability and safe codes', () => {
  it('finds the export capability only when offered', () => {
    const catalog = { revision: '1', capabilities: [capability()] };
    expect(findExportCapability(catalog)).toEqual(capability());
    expect(
      findExportCapability({ revision: '1', capabilities: [capability({ state: 'unavailable' })] }),
    ).toBeUndefined();
    expect(findExportCapability(null)).toBeUndefined();
  });

  it('keeps the new codes and gives them Korean copy', async () => {
    for (const code of [
      'OUTCOME_UNKNOWN',
      'INVALID_TOKEN',
      'CAPACITY_EXHAUSTED',
      'SOURCE_INELIGIBLE',
      'APPROVAL_REQUIRED',
    ]) {
      vi.stubGlobal(
        'fetch',
        vi.fn(async (input: RequestInfo | URL) =>
          String(input) === '/api/v2/session'
            ? json({ signedIn: false, csrfToken: 't' })
            : json({ code, requestId: 'r', retryable: false, messageKey: 'm' }, 409),
        ),
      );
      const failure = await new Transport()
        .post('/api/v2/c09/read-notion-connection', {})
        .catch((error: unknown) => error);
      expect((failure as ApiError).envelope.code).toBe(code);
      expect(dispositionCopy(code)).not.toBe('문제가 발생했어요');
      vi.unstubAllGlobals();
    }
  });

  it('keeps the wait of the 20-per-hour refusal from the body only', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) =>
        String(input) === '/api/v2/session'
          ? json({ signedIn: false, csrfToken: 't' })
          : new Response(
              JSON.stringify({
                code: 'CAPACITY_EXHAUSTED',
                requestId: 'r',
                retryable: true,
                messageKey: 'm',
                retryAfterSeconds: 90,
              }),
              { status: 429, headers: { 'Content-Type': 'application/json', 'Retry-After': '5' } },
            ),
      ),
    );
    const failure = (await new Transport()
      .post('/api/v2/c09/execute-approved-export', {})
      .catch((error: unknown) => error)) as ApiError;
    expect(failure.status).toBe(429);
    expect(failure.envelope.retryAfterSeconds).toBe(90);
  });
});

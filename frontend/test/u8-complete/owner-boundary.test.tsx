// U8 plan Step 92(a) (BR5.5, L1-39): App in the complete assembly drops every cached private
// response, its `$inf$` page lists included, and every `docsuri.private.*` key at each
// owner boundary, before navigation is resolved again; nothing runs on a timer.
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { SWRConfig } from 'swr';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';
import { json, notFound } from './helpers';

type Session = 'a' | 'b' | 'guest';
type World = {
  session: Session;
  /** The next list read answers 401 UNAUTHENTICATED. */
  expireNextList: boolean;
  navigations: number;
  /** At each navigation request: whether the cache still held A's job. */
  heldAtNavigation: boolean[];
  lists: Session[];
};

const POLICY = { policyId: 'u8-synthetic-v1', revision: '1' };
const row = (id: string) => ({
  id,
  state: 'available',
  modeIds: [],
  languageIds: [],
  levelIds: [],
  formatIds: [],
  policy: POLICY,
});
const CATALOG = { revision: 'catalog-1', capabilities: [row('operations.ledger')] };
const PROJECTION = { manifestRevision: 'manifest-1', items: [] };
const entry = (routeId: string) => ({
  routeId,
  titleKey: `nav.${routeId}`,
  capabilityId: routeId,
  available: true,
  placement: 'primary',
});
const JOB = { a: { jobId: 'job-a1', label: '질문 A' }, b: { jobId: 'job-b1', label: '질문 B' } };

/** Whether any cache key or value still holds A's job or its label. */
function holdsA(cache: Map<string, unknown>): boolean {
  for (const [key, value] of cache.entries()) {
    let text = key;
    try {
      text += JSON.stringify(value);
    } catch {
      text += String(value);
    }
    if (text.includes('job-a1') || text.includes('질문 A')) return true;
  }
  return false;
}

function respond(world: World, cache: Map<string, unknown>, path: string): Response {
  const member = world.session !== 'guest';
  if (path === '/api/v2/session')
    return json({
      signedIn: member,
      accountId: member ? `account-${world.session}` : null,
      authorityRevision: member ? 'r1' : null,
      csrfToken: crypto.randomUUID().replace(/-/g, '').repeat(2), // per run (L1-36)
    });
  if (path === '/api/v2/capabilities') return json(member ? CATALOG : PROJECTION);
  if (path === '/api/v2/c01/host-resolve-navigation') {
    world.navigations += 1;
    world.heldAtNavigation.push(holdsA(cache));
    return json({ items: member ? [entry('search'), entry('jobs')] : [entry('search')] });
  }
  if (path === '/api/v2/c07/list-research-jobs') {
    if (world.expireNextList) {
      world.expireNextList = false;
      return json(
        {
          code: 'UNAUTHENTICATED',
          requestId: 'r',
          retryable: false,
          messageKey: 'session.expired',
        },
        401,
      );
    }
    world.lists.push(world.session);
    const job = world.session === 'guest' ? null : JOB[world.session];
    return json({
      items: job
        ? [
            {
              ...job,
              kind: 'research',
              state: 'succeeded',
              createdAt: '2026-11-01T02:00:00Z',
              updatedAt: '2026-11-01T02:00:00Z',
              resultAvailable: true,
            },
          ]
        : [],
      nextCursor: null,
    });
  }
  if (path === '/api/v2/c03/settings-read')
    return json({ revision: 's1', appearance: 'system', onboarding: 'done' });
  return notFound();
}

/** A signed in, on 작업, with A's job cached and a private key set. */
async function openAsJobs() {
  const cache = new Map<string, unknown>();
  const world: World = {
    session: 'a',
    expireNextList: false,
    navigations: 0,
    heldAtNavigation: [],
    lists: [],
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) =>
      respond(world, cache, new URL(String(input), 'https://local.invalid').pathname),
    ),
  );
  render(
    <SWRConfig value={{ provider: () => cache as never }}>
      <App />
    </SWRConfig>,
  );
  fireEvent.click(await screen.findByTestId('nav-jobs'));
  expect(await screen.findByText(/질문 A/)).toBeInTheDocument();
  window.sessionStorage.setItem('docsuri.private.identity-flow', '{"provider":"google"}');
  // The page list sits under SWR's `$inf$` key, which a key filter cannot reach.
  expect(
    [...cache.keys()].some(
      (key) => key.startsWith('$inf$') && holdsA(new Map([[key, cache.get(key)]])),
    ),
  ).toBe(true);
  return {
    cache,
    world,
    navigationsBefore: world.navigations,
    heldBefore: world.heldAtNavigation.length,
  };
}

async function expectCleared(
  cache: Map<string, unknown>,
  world: World,
  navigationsBefore: number,
  heldBefore: number,
) {
  await waitFor(() => expect(world.navigations).toBeGreaterThan(navigationsBefore));
  await waitFor(() => expect(holdsA(cache)).toBe(false));
  const privateKeys = Object.keys(window.sessionStorage).filter((key) =>
    key.startsWith('docsuri.private.'),
  );
  expect(privateKeys).toEqual([]);
  expect(screen.queryByText(/질문 A/)).toBeNull();
  // At each navigation request after the boundary, the cache already held nothing of A's.
  expect(world.heldAtNavigation.slice(heldBefore)).not.toContain(true);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  window.history.replaceState(null, '', '/');
});

describe('drops cached private responses and resolves navigation again at every boundary', () => {
  it('at sign-out', async () => {
    const { cache, world, navigationsBefore, heldBefore } = await openAsJobs();
    world.session = 'guest';
    fireEvent.click(screen.getByTestId('logout'));
    expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
    await expectCleared(cache, world, navigationsBefore, heldBefore);
  });

  it('at a 401 to the next list read', async () => {
    const { cache, world, navigationsBefore, heldBefore } = await openAsJobs();
    world.expireNextList = true;
    fireEvent.click(screen.getByTestId('jobs-filter-research'));
    await expectCleared(cache, world, navigationsBefore, heldBefore);
  });

  it("at another tab's authority notice, then shows B's own jobs", async () => {
    const { cache, world, navigationsBefore, heldBefore } = await openAsJobs();
    world.session = 'b';
    await act(async () => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: 'docsuri.authority-boundary',
          newValue: JSON.stringify({ kind: 'authority-changed', nonce: crypto.randomUUID() }),
        }),
      );
    });
    await waitFor(() =>
      expect(screen.getByTestId('app-shell')).toHaveAttribute('data-account', 'account-b'),
    );
    await expectCleared(cache, world, navigationsBefore, heldBefore);
    // One or two navigation reads, depending on whether the guest state renders between.
    expect(world.navigations - navigationsBefore).toBeLessThanOrEqual(2);
    // B's 작업 (still the view, remounted for B) sends its own list read.
    expect(await screen.findByTestId('jobs-view')).toBeInTheDocument();
    expect(await screen.findByText(/질문 B/)).toBeInTheDocument();
    expect(world.lists).toContain('b');
    expect(holdsA(cache)).toBe(false);
  });

  it('at a visibility recheck that finds the session ended, with no 401', async () => {
    const { cache, world, navigationsBefore, heldBefore } = await openAsJobs();
    world.session = 'guest';
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
    await expectCleared(cache, world, navigationsBefore, heldBefore);
  });
});

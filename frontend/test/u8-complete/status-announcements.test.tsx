// U8 plan Step 92(i) (L1-26): the shell's live region carries no message past its owner. An
// owner change empties it in that same render, and the message never returns with the owner.
// Step 94(e): 운영's capability, incident and recovery-request changes, and a research job's
// own view (L1-9), are each announced once through the shell's one region.
import React, { useEffect } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';
import type { Job } from '../../src/u4-research/api';
import { ResearchJob } from '../../src/u4-research/jobs';
import type { DashboardItem, Incident } from '../../src/u8-operations/api';
import { OperationsView } from '../../src/u8-operations/operations-view';
import { AnnouncerProvider, useAnnounce } from '../../src/u8-shell/announcer';
import { immediateFrames, serve } from './app-shell-scenarios';
import { apiError, fakeClient, Fresh } from './helpers';

function Announcing() {
  const { announce } = useAnnounce();
  useEffect(() => announce('테스트 안내'), [announce]);
  return null;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState(null, '', '/');
  window.sessionStorage.clear();
});

describe('an owner change clears the region and starts a new baseline', () => {
  it('drops the message at an owner change and does not bring it back', () => {
    const tree = (owner: string) => (
      <AnnouncerProvider owner={owner}>
        <Announcing />
      </AnnouncerProvider>
    );
    const view = render(tree('member:a'));
    expect(screen.getByTestId('announcer')).toHaveTextContent('테스트 안내');
    view.rerender(tree('guest:'));
    expect(screen.getByTestId('announcer')).toHaveTextContent('');
    expect(screen.getByTestId('announcer').textContent).toBe('');
    view.rerender(tree('member:a'));
    expect(screen.getByTestId('announcer').textContent).toBe('');
  });

  it("empties App's region at sign-out, and the next owner's capability read keeps it empty", async () => {
    immediateFrames();
    const world = serve('member');
    render(<App />);
    fireEvent.click(await screen.findByTestId('nav-operations'));
    fireEvent.click(await screen.findByTestId('recovery-open'));
    fireEvent.click(await screen.findByTestId('recovery-submit'));
    await waitFor(() =>
      expect(screen.getByTestId('announcer')).toHaveTextContent('백업 만들기 요청 상태: 요청됨'),
    );
    fireEvent.click(screen.getByTestId('logout'));
    expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
    expect(screen.getByTestId('announcer').textContent).toBe('');
    // The member comes back through a visibility recheck: the capability read moves from the
    // public projection to the catalog, and the region stays empty.
    const reads = () => world.calls.filter((path) => path === '/api/v2/capabilities').length;
    const before = reads();
    world.session = 'member';
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(await screen.findByTestId('logout')).toBeInTheDocument();
    await waitFor(() => expect(reads()).toBeGreaterThan(before));
    await screen.findByTestId('nav-operations');
    expect(screen.getByTestId('announcer').textContent).toBe('');
  });
});

const announcer = () => screen.getByTestId('announcer');

/** Lets pending reads answer and their renders commit. */
const settle = () =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

/** No live region but the announcer holds the text. */
function onlyTheAnnouncerHolds(text: string) {
  const others = Array.from(document.querySelectorAll('[role="status"], [aria-live]')).filter(
    (element) => element !== announcer(),
  );
  for (const element of others) expect(element.textContent).not.toContain(text);
}

function capability(name: string, overrides: Partial<DashboardItem> = {}): DashboardItem {
  return {
    observationId: `obs-${name}`,
    capability: name,
    component: name,
    observedAt: '2026-10-23T02:00:00Z',
    revision: 'r1',
    status: 'available',
    evidenceRef: `evidence-${name}`,
    limitations: [],
    freshness: 'current',
    ageSeconds: 30,
    ...overrides,
  };
}

function incidentOn(name: string, state: Incident['state']): Incident {
  return {
    incidentId: `inc-${name}`,
    revision: state === 'open' ? '1' : '2',
    capabilities: [name],
    correlationIds: [],
    state,
    evidenceRefs: ['opened:2026-10-23T01:00:00Z'],
    ...(state === 'resolved' ? { resolutionKind: 'capability-available' } : {}),
  };
}

describe('운영 announces each change once through the shell region (L1-26)', () => {
  it("announces capability, incident and recovery-request changes on 운영 once through the shell's region", async () => {
    const states: Record<string, Partial<DashboardItem>> = {
      'background.work': {},
      'discovery.search': {},
      'provider.resend': {},
    };
    let requestState = 'requested';
    let incidents: Incident[] = [];
    const fake = fakeClient((path) => {
      if (path === '/api/v2/c11/read-dashboard')
        return {
          items: [
            ...Object.entries(states).map(([name, overrides]) => capability(name, overrides)),
            capability('operations.recovery-request', {
              component: 'ServiceOperations',
              evidenceRef: 'request-3',
              limitations: [
                `state:${requestState}`,
                'operation:backup.create',
                'origin:administrator',
                'environment:live',
              ],
            }),
          ],
          page: { nextCursor: null, snapshotRevision: 's1' },
        };
      if (path === '/api/v2/c11/list-incidents')
        return { items: incidents, page: { nextCursor: null } };
      return apiError(404, 'NOT_FOUND');
    });
    const reads = () =>
      fake.read.mock.calls.filter(([path]) => path === '/api/v2/c11/list-incidents').length;
    const tree = (shown: boolean) => (
      <Fresh>
        {shown ? (
          <OperationsView
            client={fake.transport}
            account="account-admin"
            controlPolicy={{ policyId: 'u8-synthetic-v1', revision: '1' }}
            operationsPolicy={{ policyId: 'u8-operations-synthetic', revision: '1' }}
            onSignInAgain={() => undefined}
          />
        ) : null}
      </Fresh>
    );
    const view = render(tree(true));
    await screen.findByTestId('capability-table');
    await settle();
    expect(announcer().textContent).toBe('');

    const refresh = async () => {
      const before = reads();
      fireEvent.click(screen.getByTestId('capability-refresh'));
      await waitFor(() => expect(reads()).toBe(before + 1));
      await settle();
    };
    const expectAnnounced = (text: string) => {
      expect(announcer().textContent).toBe(text);
      onlyTheAnnouncerHolds(text);
    };

    states['background.work'] = { freshness: 'stale' };
    await refresh();
    expectAnnounced('기능 상태: background.work 오래됨');
    let span = announcer().firstElementChild;
    await refresh();
    expect(announcer().firstElementChild).toBe(span);

    states['background.work'] = {};
    await refresh();
    expectAnnounced('기능 상태: background.work 정상');
    span = announcer().firstElementChild;
    await refresh();
    expect(announcer().firstElementChild).toBe(span);

    states['discovery.search'] = { status: 'degraded' };
    states['provider.resend'] = { status: 'unavailable' };
    await refresh();
    expectAnnounced('기능 상태: discovery.search 제한, provider.resend 중단');

    states['background.work'] = { status: 'unavailable' };
    incidents = [incidentOn('background.work', 'open')];
    await refresh();
    expectAnnounced('기능 상태: background.work 중단. 사고 상태: background.work 열림');

    incidents = [...incidents, incidentOn('cutover', 'open')];
    await refresh();
    expectAnnounced('사고 상태: cutover 열림');
    incidents = [incidents[0]!, incidentOn('cutover', 'resolved')];
    await refresh();
    expectAnnounced('사고 상태: cutover 해결됨');

    requestState = 'awaiting-operator';
    await refresh();
    expectAnnounced('백업 만들기 요청 상태: 운영자 대기');

    // Unmounted and mounted again under the same provider, 운영 adds nothing.
    span = announcer().firstElementChild;
    view.rerender(tree(false));
    view.rerender(tree(true));
    await screen.findByTestId('capability-table');
    await settle();
    expect(announcer().firstElementChild).toBe(span);
    expectAnnounced('백업 만들기 요청 상태: 운영자 대기');
  });
});

describe("a research job's own view inside the complete shell (L1-9)", () => {
  const reference = { jobId: 'job-a', kind: 'research-turn' as const, contextId: 'context-a' };
  const running: Job = {
    jobId: 'job-a',
    kind: 'research-turn',
    state: 'running',
    revision: '2',
    seq: 2,
    ownerId: 'owner-a',
    progress: { mode: 'indeterminate' },
    result: null,
    error: null,
    acceptedAt: '2026-10-16T00:00:00Z',
  };
  const succeeded: Job = {
    ...running,
    state: 'succeeded',
    revision: '3',
    seq: 3,
    result: {
      resultId: 'artifact-a',
      revision: '1',
      contentHash: 'a'.repeat(64),
      mediaType: 'application/json',
    },
  };

  it("a research job's own view inside the complete shell announces each state once through the shell's region", async () => {
    let answer: Job = running;
    const fake = fakeClient((path) =>
      path === '/api/v2/c07/read-research-job' ? answer : apiError(404, 'NOT_FOUND'),
    );
    render(
      <Fresh>
        <ResearchJob client={fake.transport} reference={reference} />
      </Fresh>,
    );
    const line = screen.getByTestId('research-job-state');
    expect(line).not.toHaveAttribute('role');
    expect(line).not.toHaveAttribute('aria-live');
    await waitFor(() => expect(announcer().textContent).toBe('실행 중이에요'));
    const span = announcer().firstElementChild;
    const reads = fake.post.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: '진행 상태 새로고침' }));
    await waitFor(() => expect(fake.post.mock.calls.length).toBe(reads + 1));
    await settle();
    expect(announcer().firstElementChild).toBe(span);
    answer = succeeded;
    fireEvent.click(screen.getByRole('button', { name: '진행 상태 새로고침' }));
    await waitFor(() =>
      expect(announcer().textContent).toBe('완료됐어요 · 준비된 결과를 열 수 있어요'),
    );
    onlyTheAnnouncerHolds('완료됐어요');
  });

  it('keeps its own status role without the shell', async () => {
    const fake = fakeClient((path) =>
      path === '/api/v2/c07/read-research-job' ? running : apiError(404, 'NOT_FOUND'),
    );
    render(<ResearchJob client={fake.transport} reference={reference} />);
    const line = screen.getByTestId('research-job-state');
    expect(line).toHaveAttribute('role', 'status');
    await waitFor(() => expect(line).toHaveTextContent('실행 중이에요'));
  });
});

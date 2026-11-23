// U8 plan Step 42, OperationsView (A5; BR3.8, BR4.1, BR4.9): administrator-only access,
// the table's order and labels, the incidents' disabled descriptions, the recovery
// states and the conflict message, the submission id, and the idempotency key. Step 94(a)-(d):
// the one read of the dashboard and the incidents, its 30 s refresh and retry, the summaries
// (L1-41, L1-52), the announcements (L1-26), the diagnosis copy (L1-19) and keyboard parity.
import React from 'react';
import { createHash } from 'node:crypto';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { OperationsView } from '../../src/u8-operations/operations-view';
import { RecoveryPanel } from '../../src/u8-operations/recovery-panel';
import { limitationText, sortProblemsFirst } from '../../src/u8-operations/capability-table';
import {
  ageText,
  digestUuid,
  evidenceOf,
  idempotencyKey,
  type DashboardItem,
  type Incident,
  type Submission,
} from '../../src/u8-operations/api';
import { advance, apiError, fakeClient, Fresh } from './helpers';

const POLICY = { policyId: 'u8-operations-synthetic', revision: '1' };
const CONTROL = { policyId: 'u8-synthetic-v1', revision: '1' };

function item(capability: string, overrides: Partial<DashboardItem> = {}): DashboardItem {
  return {
    observationId: `obs-${capability}`,
    capability,
    component: capability,
    observedAt: '2026-10-23T02:00:00Z',
    revision: 'r1',
    status: 'available',
    evidenceRef: `evidence-${capability}`,
    limitations: [],
    freshness: 'current',
    ageSeconds: 30,
    ...overrides,
  };
}

const DASHBOARD: DashboardItem[] = [
  item('discovery.search', { limitations: ['error-rate-permille:0'] }),
  item('assistance.summary', { status: 'degraded', limitations: ['model-evidence-mismatch'] }),
  item('runtime.isolation', {
    status: 'unavailable',
    limitations: ['runtime-isolation-lapsed', 'isolation-filter'],
  }),
  item('provider.resend', { freshness: 'stale', ageSeconds: 7200 }),
  item('provider.notion', {
    status: 'unknown',
    ageSeconds: null,
    limitations: ['error-rate-permille:25'],
  }),
  item('operations.backup-set', {
    component: 'nightly',
    evidenceRef: 'backup-1',
    limitations: ['trigger:schedule', 'revision:4'],
  }),
  item('operations.backup-set', {
    component: 'failed-set',
    status: 'unavailable',
    evidenceRef: 'backup-0',
    limitations: ['revision:3'],
  }),
  item('operations.backup-revision', {
    evidenceRef: 'backup-revision:live',
    limitations: ['revision:2'],
  }),
  item('operations.recovery-request', {
    evidenceRef: 'request-1',
    limitations: [
      'state:awaiting-operator',
      'operation:restore.verify',
      'origin:administrator',
      'environment:rehearsal',
    ],
  }),
  item('operations.recovery-request', {
    evidenceRef: 'request-2',
    limitations: [
      'state:post-restore-pending',
      'operation:restore.production',
      'origin:schedule',
      'environment:live',
    ],
  }),
  item('operations.recovery-request', {
    evidenceRef: 'request-3',
    limitations: [
      'state:requested',
      'operation:backup.create',
      'origin:administrator',
      'environment:live',
    ],
  }),
  item('operations.email-allowance', { limitations: ['daily:3', 'monthly:41'] }),
  item('operations.latency', { component: 'interactive', limitations: ['p95-ms:180', 'count:20'] }),
  item('operations.latency', { component: 'stream', limitations: ['p95-ms:unknown', 'count:0'] }),
  item('operations.availability', {
    limitations: ['availability-permille:998', 'budget-left-seconds:600'],
  }),
];

const INCIDENTS: Incident[] = [
  {
    incidentId: 'inc-resolved',
    revision: '3',
    capabilities: ['provider.google'],
    correlationIds: [],
    state: 'resolved',
    evidenceRefs: ['opened:2026-10-22T01:00:00Z'],
    resolutionKind: 'capability-available',
  },
  {
    incidentId: 'inc-abort',
    revision: '1',
    capabilities: ['cutover'],
    correlationIds: [],
    state: 'open',
    evidenceRefs: [
      'opened:2026-10-23T01:00:00Z',
      'role:abort',
      'diagnosis:switch aborted',
      'recovery:request-1',
      'opaque-7',
    ],
  },
  {
    incidentId: 'inc-copy',
    revision: '1',
    capabilities: ['rollback'],
    correlationIds: [],
    state: 'investigating',
    evidenceRefs: ['role:rollback-copy'],
  },
  {
    incidentId: 'inc-plain',
    revision: '1',
    capabilities: ['runtime.isolation'],
    correlationIds: [],
    state: 'open',
    evidenceRefs: ['opened:not-a-date'],
  },
];

function answer(overrides: { dashboard?: unknown; recovery?: () => unknown } = {}) {
  return (path: string) => {
    if (path === '/api/v2/c11/read-dashboard')
      return (
        overrides.dashboard ?? {
          items: DASHBOARD,
          page: { nextCursor: null, snapshotRevision: 's1' },
        }
      );
    if (path === '/api/v2/c11/list-incidents')
      return { items: INCIDENTS, page: { nextCursor: null } };
    if (path === '/api/v2/c11/request-recovery')
      return overrides.recovery?.() ?? { jobId: 'request-9', revision: '1', state: 'accepted' };
    return apiError(404, 'NOT_FOUND');
  };
}

function mount(overrides: Parameters<typeof answer>[0] = {}) {
  const fake = fakeClient(answer(overrides));
  const onSignInAgain = vi.fn();
  render(
    <Fresh>
      <OperationsView
        client={fake.transport}
        account="account-admin"
        controlPolicy={CONTROL}
        operationsPolicy={POLICY}
        onSignInAgain={onSignInAgain}
      />
    </Fresh>,
  );
  return { ...fake, onSignInAgain };
}

const DASHBOARD_PATH = '/api/v2/c11/read-dashboard';
const INCIDENTS_PATH = '/api/v2/c11/list-incidents';

/** A fake whose answers the test changes between reads. */
function mountWorld(
  initial: {
    dashboard?: DashboardItem[];
    incidents?: Incident[];
  } = {},
) {
  const world = {
    dashboard: initial.dashboard ?? DASHBOARD,
    incidents: initial.incidents ?? INCIDENTS,
    incidentsFail: false,
  };
  const fake = fakeClient((path) => {
    if (path === DASHBOARD_PATH)
      return { items: world.dashboard, page: { nextCursor: null, snapshotRevision: 's1' } };
    if (path === INCIDENTS_PATH)
      return world.incidentsFail
        ? apiError(503, 'DEPENDENCY_UNAVAILABLE')
        : { items: world.incidents, page: { nextCursor: null } };
    if (path === '/api/v2/c11/request-recovery')
      return { jobId: 'request-9', revision: '1', state: 'accepted' };
    return apiError(404, 'NOT_FOUND');
  });
  render(
    <Fresh>
      <OperationsView
        client={fake.transport}
        account="account-admin"
        controlPolicy={CONTROL}
        operationsPolicy={POLICY}
        onSignInAgain={() => undefined}
      />
    </Fresh>,
  );
  const reads = (path: string) => fake.read.mock.calls.filter(([called]) => called === path).length;
  return { ...fake, world, reads };
}

/** Lets pending reads answer and their renders commit, with real timers. */
const settle = () =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

const announcer = () => screen.getByTestId('announcer');

/** Every live region but the shell's announcer. */
function otherLiveRegions(): Element[] {
  return Array.from(document.querySelectorAll('[role="status"], [aria-live]')).filter(
    (element) => element !== announcer(),
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('access', () => {
  it('shows the MFA prompt to an administrator without a current second factor', async () => {
    const { onSignInAgain } = mount({ dashboard: apiError(403, 'FORBIDDEN') });
    expect(await screen.findByTestId('admin-mfa-prompt')).toHaveTextContent(
      '추가 인증을 다시 완료해야 합니다',
    );
    fireEvent.click(screen.getByTestId('admin-mfa-sign-in-again'));
    expect(onSignInAgain).toHaveBeenCalledTimes(1);
  });

  it('shows the ordinary not-found page to anyone else', async () => {
    mount({ dashboard: apiError(404, 'NOT_FOUND') });
    expect(await screen.findByTestId('not-found')).toHaveTextContent('페이지를 찾을 수 없습니다');
    expect(screen.queryByTestId('capability-table')).toBeNull();
  });

  it('shows a failure other than access as a status, without data', async () => {
    mount({ dashboard: apiError(503, 'UNAVAILABLE') });
    await waitFor(() => expect(screen.getByTestId('operations-view')).toBeInTheDocument());
    expect(screen.queryByTestId('capability-table')).toBeNull();
  });
});

describe('the capability table', () => {
  it('lists problems first and labels each state, limitation and age', async () => {
    mount();
    const table = await screen.findByTestId('capability-table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getByRole('rowheader').textContent)).toEqual([
      'runtime.isolation',
      'provider.notion',
      'provider.resend',
      'assistance.summary',
      'discovery.search',
    ]);
    expect(screen.getByTestId('capability-row-runtime.isolation')).toHaveTextContent('중단');
    expect(screen.getByTestId('capability-row-runtime.isolation')).toHaveTextContent(
      '런타임 격리 확인 실패, 패킷 필터',
    );
    expect(screen.getByTestId('capability-row-assistance.summary')).toHaveTextContent(
      '모델 검증값 불일치',
    );
    expect(screen.getByTestId('capability-row-provider.resend')).toHaveTextContent('오래됨');
    expect(screen.getByTestId('capability-row-provider.notion')).toHaveTextContent(
      '확인한 적 없음',
    );
    expect(screen.getByTestId('capability-row-provider.notion')).toHaveTextContent(
      '오류율 2.5% (측정값)',
    );
    expect(screen.getByTestId('capability-row-discovery.search')).toHaveTextContent(
      '오류 0건 (측정값)',
    );
    expect(screen.getByTestId('capability-row-runtime.isolation')).toHaveTextContent(/1$/);
  });

  it('shows a measured figure, an estimate and unknown apart in the summaries', async () => {
    mount();
    expect(await screen.findByTestId('summary-allowance')).toHaveTextContent(
      '오늘 3건 · 이번 달 41건 (측정값)',
    );
    expect(screen.getByTestId('summary-availability')).toHaveTextContent(
      '99.8% · 남은 허용 중단 10분',
    );
    expect(screen.getByTestId('summary-latency')).toHaveTextContent(
      'interactive 180ms · stream 알 수 없음',
    );
  });

  it('refreshes every 30 s and on demand, and pauses', async () => {
    vi.useFakeTimers();
    const fake = mountWorld();
    const shown = () => {
      expect(screen.getAllByTestId(/^capability-row-/)).toHaveLength(5);
      expect(screen.getAllByTestId('incident-item')).toHaveLength(4);
      expect(screen.getAllByTestId('summary-backup')).toHaveLength(2);
      expect(screen.getAllByTestId('recovery-request')).toHaveLength(3);
    };
    await advance(0);
    shown();
    await advance(29_900);
    expect(fake.reads(DASHBOARD_PATH)).toBe(1);
    await advance(200);
    expect(fake.reads(DASHBOARD_PATH)).toBe(2);
    shown();
    await advance(30_000);
    expect(fake.reads(DASHBOARD_PATH)).toBe(3);
    // Each automatic refresh is one dashboard read without a cursor and one incidents read.
    expect(fake.reads(INCIDENTS_PATH)).toBe(3);
    expect(fake.read).toHaveBeenCalledTimes(6);
    for (const [path, body] of fake.read.mock.calls) {
      if (path === DASHBOARD_PATH) expect(body).toEqual({ page: { limit: 200 } });
    }
    expect(fake.post).not.toHaveBeenCalled();
    expect(fake.get).not.toHaveBeenCalled();
    shown();
    // 지금 새로 고침 adds exactly one of each, with no time advanced.
    fireEvent.click(screen.getByTestId('capability-refresh'));
    await advance(0);
    expect(fake.reads(DASHBOARD_PATH)).toBe(4);
    expect(fake.reads(INCIDENTS_PATH)).toBe(4);
    expect(fake.read).toHaveBeenCalledTimes(8);
    shown();
    // Paused, nothing is read; resumed, the next read comes within 30 s.
    const pause = screen.getByTestId('capability-pause');
    fireEvent.click(pause);
    expect(pause).toHaveAttribute('aria-pressed', 'true');
    await advance(60_000);
    expect(fake.read).toHaveBeenCalledTimes(8);
    fireEvent.click(pause);
    expect(pause).toHaveAttribute('aria-pressed', 'false');
    await advance(30_100);
    expect(fake.reads(DASHBOARD_PATH)).toBe(5);
    expect(fake.reads(INCIDENTS_PATH)).toBe(5);
    shown();
  });

  it('keeps the last answer beside one error line when the incidents fail, and reads again 30 s later', async () => {
    vi.useFakeTimers();
    const fake = mountWorld();
    await advance(0);
    const view = screen.getByTestId('operations-view');
    fake.world.incidentsFail = true;
    // The automatic refresh at 30 s fails at its incidents read.
    await advance(30_100);
    expect(fake.reads(DASHBOARD_PATH)).toBe(2);
    expect(fake.reads(INCIDENTS_PATH)).toBe(2);
    expect(within(view).getAllByTestId('status-line')).toHaveLength(1);
    expect(screen.getAllByTestId(/^capability-row-/)).toHaveLength(5);
    expect(screen.getAllByTestId('incident-item')).toHaveLength(4);
    expect(screen.queryByText('열린 사고가 없습니다')).toBeNull();
    fake.world.incidentsFail = false;
    await advance(29_800);
    expect(fake.reads(DASHBOARD_PATH)).toBe(2);
    expect(screen.queryByText('열린 사고가 없습니다')).toBeNull();
    await advance(200);
    expect(fake.reads(DASHBOARD_PATH)).toBe(3);
    expect(fake.reads(INCIDENTS_PATH)).toBe(3);
    expect(within(view).queryByTestId('status-line')).toBeNull();
    expect(screen.getAllByTestId('incident-item')).toHaveLength(4);
    // Paused, a failed 지금 새로 고침 is not read again.
    fireEvent.click(screen.getByTestId('capability-pause'));
    fake.world.incidentsFail = true;
    fireEvent.click(screen.getByTestId('capability-refresh'));
    await advance(0);
    expect(fake.reads(DASHBOARD_PATH)).toBe(4);
    expect(within(view).getAllByTestId('status-line')).toHaveLength(1);
    await advance(60_000);
    expect(fake.reads(DASHBOARD_PATH)).toBe(4);
    expect(screen.queryByText('열린 사고가 없습니다')).toBeNull();
  });

  it('formats ages and limitations', () => {
    expect(ageText(undefined)).toBe('확인한 적 없음');
    expect(ageText(5)).toMatch(/초/);
    expect(ageText(600)).toMatch(/분/);
    expect(ageText(7200)).toMatch(/시간/);
    expect(ageText(172_800)).toBe('그저께');
    expect(ageText(432_000)).toBe('5일 전');
    expect(limitationText('available')).toBe('');
    expect(limitationText('something-new')).toBe('something-new');
    expect(limitationText('missing-observations:1')).toBe('저장하지 못한 확인 기록 1건');
    expect(sortProblemsFirst([item('b'), item('a')]).map((row) => row.capability)).toEqual([
      'a',
      'b',
    ]);
  });

  it('shows unknown summaries when the dashboard has none', async () => {
    mount({
      dashboard: {
        items: [item('discovery.search')],
        page: { nextCursor: null, snapshotRevision: 's1' },
      },
    });
    expect(await screen.findByTestId('summary-allowance')).toHaveTextContent('알 수 없음');
    expect(screen.getByTestId('summary-availability')).toHaveTextContent('알 수 없음');
    expect(screen.getByTestId('summary-latency')).toHaveTextContent('알 수 없음');
    expect(screen.getByTestId('recovery-requests')).toBeEmptyDOMElement();
  });
});

describe('the incidents', () => {
  it('lists unresolved incidents first, with their own disabled descriptions', async () => {
    mount();
    await waitFor(() => expect(screen.getAllByTestId('incident-item')).toHaveLength(4));
    const items = screen.getAllByTestId('incident-item');
    expect(items[0]).toHaveTextContent('cutover · 열림');
    expect(items[0]).toHaveTextContent('진단: switch aborted');
    expect(items[0]).toHaveTextContent('연결된 복구 요청: request-1');
    expect(items[0]).toHaveTextContent('증거: opaque-7');
    expect(within(items[0]!).getByTestId('incident-resolve')).toHaveAttribute(
      'aria-disabled',
      'true',
    );
    expect(within(items[0]!).getByTestId('incident-resolve-reason')).toHaveTextContent(
      '전환 중단 검토가 기록되어야 합니다',
    );
    expect(within(items[1]!).getByTestId('incident-resolve-reason')).toHaveTextContent(
      '롤백 사본이 처리되어야 합니다',
    );
    expect(within(items[2]!).getByTestId('incident-resolve-reason')).toHaveTextContent(
      '해결을 기록합니다',
    );
    expect(items[2]).toHaveTextContent('열린 시각 알 수 없음');
    expect(within(items[0]!).getByTestId('incident-investigate')).toHaveAttribute(
      'aria-disabled',
      'true',
    );
    expect(within(items[3]!).getByTestId('incident-resolution')).toHaveTextContent('기능 복구됨');
    fireEvent.click(within(items[0]!).getByTestId('incident-recover'));
    expect(screen.getByTestId('recovery-incident')).toHaveTextContent(
      '사고 cutover에 대한 요청입니다',
    );
    expect(evidenceOf(INCIDENTS[1]!, 'role')).toEqual(['abort']);
  });
});

describe('the recovery requests', () => {
  it('labels every request state with its environment, origin and wait reason', async () => {
    mount();
    await waitFor(() => expect(screen.getAllByTestId('recovery-request')).toHaveLength(3));
    const requests = screen.getAllByTestId('recovery-request');
    expect(requests[0]).toHaveTextContent('복원 검증 · 리허설 · 관리자 · 운영자 대기');
    expect(requests[1]).toHaveTextContent(
      '운영 데이터 복원 요청 · 운영 · 예약 · 복원 후 백업 대기',
    );
    expect(requests[1]).toHaveTextContent(
      '복원된 데이터베이스의 백업이 통과해야 서비스가 다시 시작됩니다',
    );
    expect(requests[2]).toHaveTextContent('백업 만들기 · 운영 · 관리자 · 요청됨');
    expect(requests[2]).toHaveTextContent('같은 환경의 다른 복구 작업이 끝나면 진행됩니다');
  });

  it('records a backup request and announces it', async () => {
    const fake = mountWorld();
    fireEvent.click(await screen.findByTestId('recovery-open'));
    const before = fake.reads(DASHBOARD_PATH);
    fireEvent.click(screen.getByTestId('recovery-submit'));
    await waitFor(() => expect(announcer().textContent).toBe('백업 만들기 요청 상태: 요청됨'));
    expect(fake.reads(DASHBOARD_PATH)).toBe(before + 1);
    expect(screen.getByTestId('recovery-confirmation').textContent).toBe(
      '백업 만들기 요청 상태: 요청됨 · 요청 request-',
    );
    for (const region of otherLiveRegions()) {
      expect(region.textContent).not.toContain('백업 만들기 요청 상태: 요청됨');
    }
    const call = fake.post.mock.calls.find(([path]) => path === '/api/v2/c11/request-recovery');
    expect(call?.[1]).toMatchObject({
      operation: 'backup.create',
      targetId: 'live',
      expectedRevision: '2',
      origin: 'administrator',
      policy: POLICY,
    });
    // A later refresh that lists this request as requested announces nothing.
    const span = announcer().firstElementChild;
    expect(span).not.toBeNull();
    fake.world.dashboard = [
      ...DASHBOARD,
      item('operations.recovery-request', {
        evidenceRef: 'request-9',
        limitations: [
          'state:requested',
          'operation:backup.create',
          'origin:administrator',
          'environment:live',
        ],
      }),
    ];
    fireEvent.click(screen.getByTestId('capability-refresh'));
    await waitFor(() => expect(screen.getAllByTestId('recovery-request')).toHaveLength(4));
    await settle();
    expect(announcer().firstElementChild).toBe(span);
  });

  it('announces a new or resolved incident once', async () => {
    const fake = mountWorld({ incidents: [] });
    await screen.findByTestId('capability-table');
    await settle();
    expect(announcer().textContent).toBe('');
    const opened: Incident = {
      incidentId: 'inc-cutover',
      revision: '1',
      capabilities: ['cutover'],
      correlationIds: [],
      state: 'open',
      evidenceRefs: ['opened:2026-10-23T01:00:00Z'],
    };
    fake.world.incidents = [opened];
    fireEvent.click(screen.getByTestId('capability-refresh'));
    await waitFor(() => expect(announcer().textContent).toBe('사고 상태: cutover 열림'));
    const span = announcer().firstElementChild;
    const reads = fake.reads(INCIDENTS_PATH);
    fireEvent.click(screen.getByTestId('capability-refresh'));
    await waitFor(() => expect(fake.reads(INCIDENTS_PATH)).toBe(reads + 1));
    await settle();
    expect(announcer().firstElementChild).toBe(span);
    fake.world.incidents = [
      { ...opened, revision: '2', state: 'resolved', resolutionKind: 'capability-available' },
    ];
    fireEvent.click(screen.getByTestId('capability-refresh'));
    await waitFor(() => expect(announcer().textContent).toBe('사고 상태: cutover 해결됨'));
    for (const region of otherLiveRegions()) {
      expect(region.textContent).not.toContain('사고 상태: cutover');
    }
  });

  it('shows the conflict message and keeps the dialog for a retry', async () => {
    mount({ recovery: () => apiError(409, 'CONFLICT') });
    fireEvent.click(await screen.findByTestId('recovery-open'));
    fireEvent.click(screen.getByTestId('recovery-submit'));
    expect(
      await screen.findByText('다른 요청이 먼저 처리되었습니다. 새로 고친 뒤 다시 확인하세요'),
    ).toBeInTheDocument();
    expect(screen.getByTestId('recovery-confirm')).toBeInTheDocument();
  });

  it('asks for a passed backup set before a restore, and the acknowledgement for production', async () => {
    const fake = mount();
    fireEvent.click(await screen.findByTestId('recovery-operation-restore.production'));
    expect(screen.getByTestId('recovery-production-note')).toBeInTheDocument();
    expect(screen.getAllByTestId('recovery-set')).toHaveLength(1);
    fireEvent.click(screen.getByTestId('recovery-open'));
    expect(screen.getByTestId('recovery-set-error')).toHaveTextContent('복원할 백업을 선택하세요');
    fireEvent.click(screen.getByTestId('recovery-set'));
    expect(screen.queryByTestId('recovery-set-error')).toBeNull();
    fireEvent.click(screen.getByTestId('recovery-open'));
    fireEvent.click(screen.getByTestId('recovery-submit'));
    expect(screen.getByTestId('recovery-acknowledge-error')).toHaveTextContent(
      '내용을 확인했다는 항목을 선택하세요',
    );
    fireEvent.click(screen.getByTestId('recovery-acknowledge'));
    fireEvent.click(screen.getByTestId('recovery-submit'));
    await waitFor(() =>
      expect(fake.post).toHaveBeenCalledWith(
        '/api/v2/c11/request-recovery',
        expect.objectContaining({
          operation: 'restore.production',
          targetId: 'backup-1',
          expectedRevision: '4',
        }),
        expect.any(String),
      ),
    );
    fireEvent.click(screen.getByTestId('recovery-operation-restore.verify'));
    fireEvent.click(screen.getByTestId('recovery-open'));
    fireEvent.click(screen.getByTestId('recovery-cancel'));
    expect(screen.queryByTestId('recovery-confirm')).toBeNull();
  });
});

describe('the submission id and the idempotency key', () => {
  function panel(recovery: () => unknown) {
    const fake = fakeClient((path) =>
      path === '/api/v2/c11/request-recovery' ? recovery() : apiError(404, 'NOT_FOUND'),
    );
    let count = 0;
    const newSubmission = vi.fn(() => `submission-${(count += 1)}`);
    render(
      <Fresh>
        <RecoveryPanel
          client={fake.transport}
          account="account-admin"
          policy={POLICY}
          items={DASHBOARD}
          incident={null}
          newSubmission={newSubmission}
          onSubmitted={() => undefined}
        />
      </Fresh>,
    );
    return { ...fake, newSubmission };
  }

  it('makes a new submission id per deliberate submission and reuses it on retry', async () => {
    let fail = true;
    const fake = panel(() =>
      fail
        ? apiError(503, 'UNAVAILABLE')
        : { jobId: 'request-9', revision: '1', state: 'accepted' },
    );
    fireEvent.click(screen.getByTestId('recovery-open'));
    fireEvent.click(screen.getByTestId('recovery-submit'));
    await waitFor(() => expect(fake.post).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId('recovery-submit')).not.toBeDisabled());
    fail = false;
    fireEvent.click(screen.getByTestId('recovery-submit'));
    await waitFor(() => expect(fake.post).toHaveBeenCalledTimes(2));
    const ids = fake.post.mock.calls.map(([, body]) => (body as Submission).submissionId);
    expect(ids).toEqual(['submission-1', 'submission-1']);
    expect(fake.post.mock.calls[0]![2]).toBe(fake.post.mock.calls[1]![2]);
    await waitFor(() => expect(screen.queryByTestId('recovery-confirm')).toBeNull());
    fireEvent.click(screen.getByTestId('recovery-open'));
    fireEvent.click(screen.getByTestId('recovery-submit'));
    await waitFor(() => expect(fake.post).toHaveBeenCalledTimes(3));
    expect((fake.post.mock.calls[2]![1] as Submission).submissionId).toBe('submission-2');
    expect(fake.post.mock.calls[2]![2]).not.toBe(fake.post.mock.calls[0]![2]);
  });

  it('sends the SHA-256 of its fields as the idempotency key, in UUID form', async () => {
    const fake = panel(() => ({ jobId: 'request-9', revision: '1', state: 'accepted' }));
    fireEvent.click(screen.getByTestId('recovery-open'));
    fireEvent.click(screen.getByTestId('recovery-submit'));
    await waitFor(() => expect(fake.post).toHaveBeenCalledTimes(1));
    const [, body, key] = fake.post.mock.calls[0]!;
    const submission = body as Submission;
    const digest = createHash('sha256')
      .update(['관리자', 'account-admin', 'backup.create', 'live', '2', 'submission-1'].join('\n'))
      .digest('hex');
    const expected = digestUuid(digest);
    // The boundary reads the header as a UUID: version 8, RFC variant.
    expect(expected).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    expect(expected.replace(/-/g, '').slice(0, 12)).toBe(digest.slice(0, 12));
    expect(key).toBe(expected);
    expect(await idempotencyKey('account-admin', submission)).toBe(expected);
    expect(await idempotencyKey('account-other', submission)).not.toBe(expected);
  });
});

const texts = (testId: string) => screen.getAllByTestId(testId).map((node) => node.textContent);

function mountItems(items: DashboardItem[], incidents: Incident[] = INCIDENTS) {
  return mountWorld({ dashboard: items, incidents });
}

describe('the summaries (L1-41, L1-52)', () => {
  const BACKUPS: DashboardItem[] = [
    item('operations.backup-set', {
      component: 'docsuri:16384',
      observedAt: '2026-10-30T19:00:00Z',
      evidenceRef: 'backup-a',
      limitations: ['trigger:schedule', 'retain-until:2026-11-13T19:00:00Z', 'revision:1'],
    }),
    item('operations.backup-set', {
      component: 'docsuri:16384',
      observedAt: '2026-10-31T19:00:00Z',
      status: 'unavailable',
      evidenceRef: 'backup-b',
      limitations: ['trigger:schedule', 'retain-until:2026-11-14T19:00:00Z', 'revision:1'],
    }),
    item('operations.backup-set', {
      component: 'docsuri:24576',
      observedAt: '2026-11-01T01:00:00Z',
      evidenceRef: 'backup-c',
      limitations: ['trigger:administrator', 'retain-until:2026-11-15T01:00:00Z', 'revision:1'],
    }),
    item('operations.backup-revision', {
      evidenceRef: 'backup-revision:live',
      limitations: ['revision:3'],
    }),
  ];
  const verification = (
    observedAt: string,
    status: DashboardItem['status'],
    limitations: string[],
  ): DashboardItem =>
    item('operations.restore-verification', {
      component: 'ServiceOperations',
      observedAt,
      status,
      evidenceRef: `verification-${observedAt}`,
      limitations,
    });
  const VERIFICATIONS: DashboardItem[] = [
    verification('2026-11-01T20:40:00Z', 'available', [
      'backup:backup-c',
      'restore-bound-seconds:2700',
      'hnsw-rebuild-seconds:720',
      'hnsw-projected-seconds:2280',
    ]),
    verification('2026-10-25T20:50:00Z', 'available', [
      'backup:backup-a',
      'restore-bound-seconds:2700',
      'hnsw-rebuild-seconds:1200',
      'hnsw-projected-seconds:3120',
      'hnsw-projection-past-bound',
    ]),
    verification('2026-10-18T20:30:00Z', 'unavailable', [
      'backup:backup-a',
      'restore-bound-seconds:2700',
    ]),
    verification('2026-10-11T20:30:00Z', 'available', [
      'backup:backup-a',
      'restore-bound-seconds:2700',
      'hnsw-rebuild-seconds:540',
    ]),
  ];
  const ISOLATION = item('operations.isolation-result', {
    component: 'ServiceOperations',
    evidenceRef: 'isolation:result-1',
    limitations: [
      'stop:org.docsuri.v2.host:2026-11-02T01:30:00Z',
      'stop:dev.docsuri.api:2026-11-02T06:15:00Z',
    ],
  });

  it("shows each database's latest set, the verifications against the bound and the stop records", async () => {
    mountItems([...BACKUPS, ...VERIFICATIONS, ISOLATION]);
    await screen.findByTestId('capability-table');
    expect(texts('summary-backup')).toEqual([
      'docsuri (24576) · 2026. 11. 1. 오전 10:00 · 무결성 확인 통과 · 보관 기한 2026. 11. 15. 오전 10:00',
      'docsuri (16384) · 2026. 11. 1. 오전 4:00 · 무결성 확인 실패 · 보관 기한 2026. 11. 15. 오전 4:00',
    ]);
    expect(screen.getByTestId('summary-backups')).not.toHaveTextContent('2026. 10. 31.');
    expect(texts('summary-verification')).toEqual([
      '2026. 11. 2. 오전 5:40 · 검증 통과 · HNSW 재구성 12분 · 8 GiB 기준 예상 38분 · 복원 한도 45분',
      '2026. 10. 26. 오전 5:50 · 검증 통과 · HNSW 재구성 20분 · 8 GiB 기준 예상 52분 · 복원 한도 45분 초과',
      '2026. 10. 19. 오전 5:30 · 검증 실패 · HNSW 재구성 기록 없음',
      '2026. 10. 12. 오전 5:30 · 검증 통과 · HNSW 재구성 9분 · 8 GiB 기준 예상 알 수 없음 · 복원 한도 45분',
    ]);
    const lines = screen.getAllByTestId('summary-verification');
    expect(lines[0]).not.toHaveAttribute('data-over-bound');
    expect(lines[1]).toHaveAttribute('data-over-bound', 'true');
    expect(lines[2]).not.toHaveAttribute('data-over-bound');
    expect(lines[3]).not.toHaveAttribute('data-over-bound');
    expect(texts('summary-stop')).toEqual([
      'org.docsuri.v2.host · 만료 2026. 11. 2. 오전 10:30',
      'dev.docsuri.api · 만료 2026. 11. 2. 오후 3:15',
    ]);
    // A restore still offers every passed set.
    fireEvent.click(screen.getByTestId('recovery-operation-restore.verify'));
    expect(screen.getAllByTestId('recovery-set')).toHaveLength(2);
  });

  it('never reads an unreadable isolation result as no stops', async () => {
    mountItems([
      item('operations.isolation-result', {
        status: 'unknown',
        limitations: ['isolation-result-unreadable'],
      }),
    ]);
    expect((await screen.findByTestId('summary-stops')).textContent).toBe('알 수 없음');
    expect(screen.getByTestId('summary-backups').textContent).toBe('백업이 없습니다');
  });

  it('reads no stops as no stops, and no result as unknown', async () => {
    mountItems([item('operations.isolation-result', { limitations: [] })]);
    expect((await screen.findByTestId('summary-stops')).textContent).toBe('중지 기록 없음');
  });

  it('shows whole components without retain-until in the dashboard order for equal times', async () => {
    mount();
    await screen.findByTestId('capability-table');
    expect(texts('summary-backup')).toEqual([
      'nightly · 2026. 10. 23. 오전 11:00 · 무결성 확인 통과 · 보관 기한 알 수 없음',
      'failed-set · 2026. 10. 23. 오전 11:00 · 무결성 확인 실패 · 보관 기한 알 수 없음',
    ]);
    expect(screen.getByTestId('summary-stops').textContent).toBe('알 수 없음');
  });

  it("shows the standing job's last run and failures", async () => {
    const counts = ['failed-backups:1', 'failed-verifications:0', 'failed-disposals:2'];
    const standing = (overrides: Partial<DashboardItem>) =>
      item('operations.standing-job', { component: 'ServiceOperations', ...overrides });
    const cases: [DashboardItem[], (text: string | null) => void][] = [
      [
        [standing({ ageSeconds: 180, limitations: counts })],
        (text) =>
          expect(text).toBe(
            '마지막 실행 3분 전 · 최근 24시간 실패한 백업 1건 · 실패한 검증 0건 · 끝내지 못한 폐기 2건 (측정값)',
          ),
      ],
      [
        [standing({ status: 'unknown', limitations: ['standing-job-unrecorded', ...counts] })],
        (text) => expect(text).toBe('실행 기록이 아직 없습니다'),
      ],
      [[], (text) => expect(text).toBe('알 수 없음')],
      [
        [
          standing({
            status: 'degraded',
            ageSeconds: 660,
            limitations: ['standing-job-late', ...counts],
          }),
        ],
        (text) => {
          expect(text?.startsWith('마지막 실행 11분 전 · 지연 · ')).toBe(true);
          expect(text).toContain('최근 24시간 실패한 백업 1건');
        },
      ],
      [
        [
          standing({
            status: 'unknown',
            ageSeconds: null,
            limitations: ['availability-record-unreadable', ...counts],
          }),
        ],
        (text) => {
          expect(text?.startsWith('마지막 실행 알 수 없음 · ')).toBe(true);
          expect(text).toContain(
            '실패한 백업 1건 · 실패한 검증 0건 · 끝내지 못한 폐기 2건 (측정값)',
          );
        },
      ],
    ];
    for (const [items, check] of cases) {
      const view = mountItems(items);
      check((await screen.findByTestId('summary-standing-job')).textContent);
      expect(screen.queryByTestId('capability-row-operations.standing-job')).toBeNull();
      expect(view.read).toHaveBeenCalled();
      cleanup();
    }
  });

  it('shows failed jobs per lane', async () => {
    const lane = (component: string, limitations: string[], status = 'available') =>
      item('operations.lane', {
        component,
        status: status as DashboardItem['status'],
        evidenceRef: `lane:${component}`,
        limitations,
      });
    const research = lane('research', ['failed:1', 'terminal:12']);
    mountItems([research, lane('export', ['failed:0', 'terminal:0'])]);
    expect((await screen.findByTestId('summary-lanes')).textContent).toBe(
      'export 실패 0건 / 종료 0건 · research 실패 1건 / 종료 12건 (측정값)',
    );
    expect(screen.queryByTestId('capability-row-operations.lane')).toBeNull();
    cleanup();
    mountItems([research, lane('export', ['lane-count-unavailable'], 'unknown')]);
    expect((await screen.findByTestId('summary-lanes')).textContent).toBe(
      'export 알 수 없음 · research 실패 1건 / 종료 12건 (측정값)',
    );
    cleanup();
    mountItems([item('discovery.search')]);
    expect((await screen.findByTestId('summary-lanes')).textContent).toBe('알 수 없음');
    expect(screen.getAllByTestId(/^capability-row-/)).toHaveLength(1);
  });

  it("shows each route class's error rate beside its p95", async () => {
    mountItems([
      item('operations.latency', {
        component: 'interactive',
        limitations: ['p95-ms:180', 'count:100', 'errors-5xx:3', 'error-rate-permille:30'],
      }),
      item('operations.latency', {
        component: 'stream',
        limitations: ['p95-ms:unknown', 'count:0', 'errors-5xx:0'],
      }),
    ]);
    expect((await screen.findByTestId('summary-latency')).textContent).toBe(
      'interactive 180ms, 최근 5분 오류율 3% (측정값) · stream 알 수 없음',
    );
  });

  it('shows missing observations as missing evidence', async () => {
    mountItems([
      item('provider.notion', { status: 'unknown', limitations: ['missing-observations:3'] }),
    ]);
    const row = await screen.findByTestId('capability-row-provider.notion');
    expect(row).toHaveTextContent('저장하지 못한 확인 기록 3건');
    expect(row).not.toHaveTextContent('missing-observations');
  });
});

describe('the Korean texts (Step 93(e)-(f))', () => {
  it('gives every key the dashboard can list a Korean text', () => {
    const expected: Record<string, string> = {
      'semantic-search-unavailable': '의미 검색을 사용할 수 없음',
      'model-runtime-waiting': '모델 실행 대기 중',
      'digest-delivery-late': '요약 메일 발송 지연',
      'maintainer-address-pending': '관리자 주소 확인 대기',
      'export-effect-late': '내보내기 처리 지연',
      'ledger-damaged': '운영 기록 손상',
      'capacity-approaching': '저장 공간 한도에 가까움',
      'internal-disk-low': '내부 디스크 여유 공간 부족',
      'internal-disk-critical': '내부 디스크 여유 공간 위험',
      'capacity-exhausted': '저장 공간 한도 도달',
      'last-backup-held': '마지막 백업 보류',
      'backup-volume-unavailable': '백업 볼륨을 찾을 수 없음',
      'backup-volume-low': '백업 볼륨 여유 공간 부족',
      'backup-volume-shared-cleanup': '다른 도구의 정리 표시가 있음',
      'backup-catalogue-damaged': '백업 목록 손상',
      'backup-volume-mismatch': '다른 백업 볼륨이 연결됨',
      'lane-behind-deadline': '작업 처리 지연',
      'assistance-readiness-pending': '요약·번역 준비 확인 대기',
      'model-runtime-unavailable': '모델 실행 환경을 사용할 수 없음',
      'cutover-effect-unknown': '전환 작업 결과를 알 수 없음',
      'cutover-route-differs': '전환 경로가 기록과 다름',
      'sign-in-unverified': '실제 로그인 확인 전',
      'provider-unreachable': '외부 서비스에 연결할 수 없음',
      'first-effect-pending': '첫 외부 작업 승인 대기',
      'allowance-exhausted': '이메일 발송 한도 도달',
      'runtime-unreachable': '모델 실행 환경에 연결할 수 없음',
      'producer-failed': '상태 확인 실패',
      'store-unavailable': '상태 기록 저장소를 사용할 수 없음',
      'store-denied': '상태 기록 저장이 거부됨',
      'store-busy': '상태 기록 저장소가 바쁨',
      'evidence-unavailable': '상태 기록을 읽을 수 없음',
      'pre-switch-recipient-bound': '전환 전 수신자만 허용',
      unconfigured: '설정되지 않음',
      'dependency-unavailable': '필요한 구성 요소를 사용할 수 없음',
      missing: '구성 요소 없음',
      incompatible: '구성 요소 버전 불일치',
      'policy-unresolved': '정책을 확인할 수 없음',
      'backup-volume-ownership': '백업 볼륨 소유권 확인 실패',
      'backup-volume-unencrypted': '백업 볼륨이 암호화되지 않음',
      'backup-volume-unwritable': '백업 볼륨에 쓸 수 없음',
      'backup-volume-unreadable': '백업 볼륨을 읽을 수 없음',
      'backup-agent-unreachable': '백업 에이전트에 연결할 수 없음',
      'scheduler-pass-unrecorded': '스케줄러 실행 기록 없음',
      'standing-job-unrecorded': '실행 기록이 아직 없습니다',
      'standing-job-late': '상시 작업 지연',
      'availability-record-unreadable': '가용성 기록을 읽을 수 없음',
      'isolation-result-unreadable': '격리 확인 결과를 읽을 수 없음',
      'lane-count-unavailable': '작업 수를 읽을 수 없음',
    };
    expect(Object.keys(expected)).toHaveLength(48);
    for (const [key, text] of Object.entries(expected)) {
      expect(limitationText(key)).toBe(text);
      expect(limitationText(key)).not.toBe(key);
    }
  });

  it("shows a recovery request's diagnosis in Korean", async () => {
    mountItems(DASHBOARD, [
      {
        incidentId: 'inc-requested',
        revision: '2',
        capabilities: ['background.work'],
        correlationIds: [],
        state: 'recovering',
        evidenceRefs: [
          'opened:2026-10-23T01:00:00Z',
          'diagnosis:recovery-requested',
          'recovery:request-3',
        ],
      },
    ]);
    const [incident] = await screen.findAllByTestId('incident-item');
    expect(incident).toHaveTextContent('진단: 복구 요청됨');
    for (const node of screen.getAllByTestId('incident-item')) {
      expect(node.textContent).not.toContain('recovery-requested');
    }
  });

  it('says that a recovery request begins the investigation', async () => {
    mount();
    await waitFor(() => expect(screen.getAllByTestId('incident-item')).toHaveLength(4));
    const unresolved = screen
      .getAllByTestId('incident-item')
      .filter((node) => within(node).queryByTestId('incident-investigate'));
    expect(unresolved).toHaveLength(3);
    for (const node of unresolved) {
      const button = within(node).getByTestId('incident-investigate');
      expect(button).toHaveAttribute('aria-disabled', 'true');
      const described = document.getElementById(button.getAttribute('aria-describedby') ?? '');
      expect(described?.textContent).toBe('조사는 복구 요청과 함께 시작됩니다');
    }
    expect(document.body.textContent).not.toContain('조사 시작은 관리자 도구에서 기록합니다');
  });
});

describe('keyboard parity for every operations control', () => {
  it('acts by Enter and Space, reaches the disabled controls by Tab, and moves radios by arrows', async () => {
    const user = userEvent.setup();
    const fake = mountWorld();
    await screen.findByTestId('capability-table');
    const read = () => fake.reads(DASHBOARD_PATH);
    for (const key of ['{Enter}', ' ']) {
      const before = read();
      screen.getByTestId('capability-refresh').focus();
      await user.keyboard(key);
      await waitFor(() => expect(read()).toBe(before + 1));
    }
    const pause = screen.getByTestId('capability-pause');
    pause.focus();
    await user.keyboard('{Enter}');
    expect(pause).toHaveAttribute('aria-pressed', 'true');
    await user.keyboard(' ');
    expect(pause).toHaveAttribute('aria-pressed', 'false');
    // The disabled incident controls are reached by Tab and stay aria-disabled.
    const first = screen.getAllByTestId('incident-item')[0]!;
    within(first).getByTestId('incident-investigate').focus();
    expect(within(first).getByTestId('incident-investigate')).toHaveFocus();
    await user.tab();
    expect(within(first).getByTestId('incident-recover')).toHaveFocus();
    await user.tab();
    const resolve = within(first).getByTestId('incident-resolve');
    expect(resolve).toHaveFocus();
    expect(resolve).toHaveAttribute('aria-disabled', 'true');
    await user.tab({ shift: true });
    expect(within(first).getByTestId('incident-recover')).toHaveFocus();
    await user.tab({ shift: true });
    // Shift+Tab reaches the disabled incident-investigate itself.
    expect(within(first).getByTestId('incident-investigate')).toHaveFocus();
    expect(within(first).getByTestId('incident-investigate')).toHaveAttribute(
      'aria-disabled',
      'true',
    );
    // 복구 요청 by Enter, and by Space on another incident.
    within(first).getByTestId('incident-recover').focus();
    await user.keyboard('{Enter}');
    expect(screen.getByTestId('recovery-incident')).toHaveTextContent(
      '사고 cutover에 대한 요청입니다',
    );
    within(screen.getAllByTestId('incident-item')[1]!).getByTestId('incident-recover').focus();
    await user.keyboard(' ');
    expect(screen.getByTestId('recovery-incident')).toHaveTextContent(
      '사고 rollback에 대한 요청입니다',
    );
    // The operation radios move by the arrow keys.
    screen.getByTestId('recovery-operation-backup.create').focus();
    await user.keyboard('{ArrowDown}');
    expect(screen.getByTestId('recovery-operation-restore.verify')).toBeChecked();
    await user.keyboard('{ArrowDown}');
    expect(screen.getByTestId('recovery-operation-restore.production')).toBeChecked();
    await user.keyboard('{ArrowUp}');
    expect(screen.getByTestId('recovery-operation-restore.verify')).toBeChecked();
    await user.keyboard('{ArrowDown}');
    expect(screen.getByTestId('recovery-operation-restore.production')).toBeChecked();
    // The set radios move by the arrow keys too (two passed sets).
    fake.world.dashboard = [
      ...DASHBOARD,
      item('operations.backup-set', {
        component: 'weekly',
        evidenceRef: 'backup-2',
        observedAt: '2026-10-22T02:00:00Z',
        limitations: ['revision:5'],
      }),
    ];
    screen.getByTestId('capability-refresh').focus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(screen.getAllByTestId('recovery-set')).toHaveLength(2));
    const sets = screen.getAllByTestId('recovery-set');
    sets[0]!.focus();
    await user.keyboard(' ');
    expect(sets[0]).toBeChecked();
    await user.keyboard('{ArrowDown}');
    expect(screen.getAllByTestId('recovery-set')[1]).toBeChecked();
    // The acknowledgement toggles by Space, and the submission goes by Enter.
    screen.getByTestId('recovery-open').focus();
    await user.keyboard('{Enter}');
    const acknowledge = screen.getByTestId('recovery-acknowledge');
    acknowledge.focus();
    await user.keyboard(' ');
    expect(acknowledge).toBeChecked();
    await user.keyboard(' ');
    expect(acknowledge).not.toBeChecked();
    await user.keyboard(' ');
    screen.getByTestId('recovery-submit').focus();
    await user.keyboard('{Enter}');
    await waitFor(() =>
      expect(fake.post).toHaveBeenCalledWith(
        '/api/v2/c11/request-recovery',
        expect.objectContaining({ operation: 'restore.production', targetId: 'backup-2' }),
        expect.any(String),
      ),
    );
    await waitFor(() => expect(screen.queryByTestId('recovery-confirm')).toBeNull());
    // 취소 closes by Enter, and Escape closes the dialog.
    screen.getByTestId('recovery-open').focus();
    await user.keyboard('{Enter}');
    screen.getByTestId('recovery-cancel').focus();
    await user.keyboard('{Enter}');
    expect(screen.queryByTestId('recovery-confirm')).toBeNull();
    screen.getByTestId('recovery-open').focus();
    await user.keyboard('{Enter}');
    expect(screen.getByTestId('recovery-confirm')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByTestId('recovery-confirm')).toBeNull();
  });
});

describe('a late answer after the view or its owner has gone (Steps 91(e), 93(a))', () => {
  /** A view whose dashboard reads the test can hold open, and fail or answer later. */
  function heldWorld() {
    const held: { fail: () => void; answer: () => void }[] = [];
    const state = { hold: false };
    const page = { items: DASHBOARD, page: { nextCursor: null, snapshotRevision: 's1' } };
    const fake = fakeClient((path) => {
      if (path === DASHBOARD_PATH) {
        if (!state.hold) return page;
        return new Promise((resolve, reject) =>
          held.push({
            fail: () => reject(apiError(503, 'DEPENDENCY_UNAVAILABLE')),
            answer: () => resolve(page),
          }),
        );
      }
      if (path === INCIDENTS_PATH) return { items: INCIDENTS, page: { nextCursor: null } };
      if (path === '/api/v2/c11/request-recovery')
        return { jobId: 'request-9', revision: '1', state: 'accepted' };
      return apiError(404, 'NOT_FOUND');
    });
    function Host({ show }: { show: boolean }) {
      return show ? (
        <OperationsView
          client={fake.transport}
          account="account-admin"
          controlPolicy={CONTROL}
          operationsPolicy={POLICY}
          onSignInAgain={() => undefined}
        />
      ) : null;
    }
    const view = render(
      <Fresh>
        <Host show />
      </Fresh>,
    );
    const hide = () =>
      view.rerender(
        <Fresh>
          <Host show={false} />
        </Fresh>,
      );
    const reads = (path: string) =>
      fake.read.mock.calls.filter(([called]) => called === path).length;
    return { ...fake, held, state, hide, reads };
  }

  it('schedules no retry once the view has unmounted, even while paused', async () => {
    vi.useFakeTimers();
    const baseline = vi.getTimerCount();
    const world = heldWorld();
    await advance(0);
    expect(screen.getByTestId('capability-table')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('capability-pause'));
    world.state.hold = true;
    fireEvent.click(screen.getByTestId('capability-refresh'));
    await advance(0);
    expect(world.held).toHaveLength(1);
    world.hide();
    expect(screen.queryByTestId('operations-view')).toBeNull();
    await act(async () => {
      world.held.splice(0).forEach((read) => read.fail());
    });
    // A paused view's retry would re-arm itself every 30 s; past four of those, no timer of
    // the view remains (SWR's own zero-delay clean-up has run by then).
    await advance(120_000);
    expect(world.reads(DASHBOARD_PATH)).toBe(2);
    expect(vi.getTimerCount()).toBe(baseline);
  });

  it('never announces a submission to the next owner when the view unmounts first', async () => {
    const world = heldWorld();
    fireEvent.click(await screen.findByTestId('recovery-open'));
    world.state.hold = true;
    fireEvent.click(screen.getByTestId('recovery-submit'));
    await waitFor(() => expect(world.held).toHaveLength(1));
    world.hide();
    await act(async () => {
      world.held.splice(0).forEach((read) => read.answer());
    });
    await settle();
    expect(announcer().textContent).toBe('');
  });

  it('never announces a submission once the authority generation has moved', async () => {
    const world = heldWorld();
    fireEvent.click(await screen.findByTestId('recovery-open'));
    world.state.hold = true;
    fireEvent.click(screen.getByTestId('recovery-submit'));
    await waitFor(() => expect(world.held).toHaveLength(1));
    // A sign-out, a 401 boundary or another tab's authority notice moves the generation.
    (world.transport as unknown as { generation: number }).generation = 1;
    await act(async () => {
      world.held.splice(0).forEach((read) => read.answer());
    });
    await settle();
    expect(announcer().textContent).toBe('');
  });
});

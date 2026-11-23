/**
 * OperationsView 운영 (frontend-components.md; BR3.8): only an administrator whose second
 * factor is current sees its data. An administrator without one gets AdminMfaPrompt,
 * and anyone else the ordinary not-found page. The dashboard and the incidents are one
 * read, refreshed every 30 s (with a pause toggle) and on demand; a failed refresh keeps
 * the last answer beside its error line and is read again 30 s later. Each answer's
 * changes are announced once, as one message, through the shell's region (L1-26).
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import { ApiError, type PolicyRef, type Transport } from '../api';
import { describeError, Panel, StatusLine } from '../ui';
import { AdminMfaPrompt } from '../u8-entry/first-sign-in';
import { useAnnounce } from '../u8-shell/announcer';
import styles from '../u8-shell/shell.module.css';
import {
  AGGREGATES,
  DASHBOARD_REFRESH_MS,
  listIncidents,
  OPERATION_COPY,
  readDashboard,
  RECOVERY_STATE_COPY,
  STATUS_COPY,
  valueOf,
  type DashboardPage,
  type Incident,
  type IncidentPage,
  type RecoveryOperation,
  type RecoveryState,
} from './api';
import { CapabilityTable, shownState } from './capability-table';
import { INCIDENT_STATE_COPY, IncidentList } from './incident-list';
import { RecoveryPanel } from './recovery-panel';

export function NotFoundPage() {
  return (
    <Panel title="페이지를 찾을 수 없습니다" testId="not-found">
      <p>주소를 확인하거나 검색으로 돌아가 주세요.</p>
      <a href="/search" className={styles.target} data-testid="not-found-search">
        검색
      </a>
    </Panel>
  );
}

/** One refresh's answer: the dashboard, then the incidents. */
export type OperationsAnswer = { dashboard: DashboardPage; incidents: IncidentPage };

/** What an answer's announcement is compared against. */
export type OperationsBaseline = {
  states: ReadonlyMap<string, string>;
  requests: ReadonlyMap<string, string>;
  incidents: ReadonlyMap<string, string>;
};

const RETRY_MS = DASHBOARD_REFRESH_MS;
const PART_SEPARATOR = '. ';

/** The incidents are read only once the dashboard answered; a failure of either fails the
 * whole refresh. */
async function readOperations(client: Transport): Promise<OperationsAnswer> {
  const dashboard = await readDashboard(client);
  const incidents = await listIncidents(client);
  return { dashboard, incidents };
}

function isAccessFailure(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.envelope.code === 'FORBIDDEN' || error.envelope.code === 'NOT_FOUND')
  );
}

export function baselineOf(answer: OperationsAnswer): OperationsBaseline {
  const items = answer.dashboard.items;
  return {
    states: new Map(
      items
        .filter((item) => !AGGREGATES.has(item.capability))
        .map((item) => [item.capability, shownState(item)]),
    ),
    requests: new Map(
      items
        .filter((item) => item.capability === 'operations.recovery-request')
        .map((item) => [item.evidenceRef, valueOf(item, 'state') ?? 'unknown']),
    ),
    incidents: new Map(
      answer.incidents.items.map((incident) => [incident.incidentId, incident.state]),
    ),
  };
}

/** The announcement's parts for an answer against the last one, in the plan's order:
 * capability states, recovery requests, incidents (Step 93(a)). `own` holds this view's own
 * submissions, which are left out while they are 요청됨. */
export function changesBetween(
  before: OperationsBaseline,
  answer: OperationsAnswer,
  own: ReadonlySet<string> = new Set(),
): string[] {
  const after = baselineOf(answer);
  const parts: string[] = [];
  const capabilities = [...after.states.entries()]
    .filter(([capability, state]) => before.states.get(capability) !== state)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([capability, state]) => `${capability} ${STATUS_COPY[state] ?? state}`);
  if (capabilities.length) parts.push(`기능 상태: ${capabilities.join(', ')}`);
  for (const item of answer.dashboard.items) {
    if (item.capability !== 'operations.recovery-request') continue;
    const state = (valueOf(item, 'state') ?? 'unknown') as RecoveryState;
    if (before.requests.get(item.evidenceRef) === state) continue;
    if (state === 'requested' && own.has(item.evidenceRef)) continue;
    const operation = (valueOf(item, 'operation') ?? 'backup.create') as RecoveryOperation;
    parts.push(
      `${OPERATION_COPY[operation] ?? operation} 요청 상태: ${RECOVERY_STATE_COPY[state] ?? state}`,
    );
  }
  for (const incident of answer.incidents.items) {
    if (before.incidents.get(incident.incidentId) === incident.state) continue;
    parts.push(
      `사고 상태: ${incident.capabilities.join(', ')} ${INCIDENT_STATE_COPY[incident.state] ?? incident.state}`,
    );
  }
  return parts;
}

type Seen = { scope: string; answer: OperationsAnswer; baseline: OperationsBaseline };

export function OperationsView({
  client,
  account,
  controlPolicy,
  operationsPolicy,
  onSignInAgain,
}: {
  client: Transport;
  account: string;
  /** AccountAccess's control policy, for the MFA prompt. */
  controlPolicy: PolicyRef;
  /** ServiceOperations' policy, which a recovery request names. */
  operationsPolicy: PolicyRef;
  onSignInAgain: () => void;
}) {
  const { announce } = useAnnounce();
  const [paused, setPaused] = useState(false);
  const [incident, setIncident] = useState<Incident | null>(null);
  const pausedRef = useRef(paused);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seen = useRef<Seen | null>(null);
  const own = useRef<Set<string>>(new Set());
  const pending = useRef<string | null>(null);
  const scope = `${account}:${client.generation}`;

  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  // Whether this view is mounted, and its current scope: a late answer never schedules a
  // retry nor announces after the view or its owner has gone (Steps 91(e), 93(a)).
  const mounted = useRef(true);
  const currentScope = useRef(scope);
  useEffect(() => {
    currentScope.current = scope;
  }, [scope]);

  const clearRetry = useCallback(() => {
    if (retryTimer.current !== null) clearTimeout(retryTimer.current);
    retryTimer.current = null;
  }, []);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearRetry();
    };
  }, [clearRetry]);

  const read = useSWR(['u8-operations', client.generation], () => readOperations(client), {
    refreshInterval: paused ? 0 : DASHBOARD_REFRESH_MS,
    revalidateOnFocus: false,
    // SWR's refresh timer skips a key that holds an error, so a failure other than access
    // is read again 30 s later by this retry, never while 운영 is paused.
    shouldRetryOnError: (error: unknown) => !isAccessFailure(error),
    onErrorRetry: (_error, _key, _config, revalidate, options) => {
      clearRetry();
      if (!mounted.current) return;
      const attempt = () => {
        if (!mounted.current) {
          retryTimer.current = null;
          return;
        }
        if (pausedRef.current) {
          retryTimer.current = setTimeout(attempt, RETRY_MS);
          return;
        }
        retryTimer.current = null;
        void revalidate(options);
      };
      retryTimer.current = setTimeout(attempt, RETRY_MS);
    },
    onSuccess: clearRetry,
  });

  /** Compares an answer with the last one seen and keeps it as the new baseline. The first
   * answer, a remount and a new owner or client generation announce nothing. */
  const observe = useCallback(
    (answer: OperationsAnswer): string[] => {
      const before = seen.current;
      if (before && before.scope === scope && before.answer === answer) return [];
      const baseline = baselineOf(answer);
      seen.current = { scope, answer, baseline };
      if (!before || before.scope !== scope) {
        own.current = new Set();
        return [];
      }
      return changesBetween(before.baseline, answer, own.current);
    },
    [scope],
  );

  useEffect(() => {
    // A submission's refresh is announced by its own handler, with the submission's text.
    if (!read.data || pending.current !== null) return;
    const parts = observe(read.data);
    if (parts.length) announce(parts.join(PART_SEPARATOR));
  }, [read.data, observe, announce]);

  const failure = read.error;
  if (failure instanceof ApiError && failure.envelope.code === 'FORBIDDEN') {
    return (
      <AdminMfaPrompt
        client={client}
        policy={controlPolicy}
        mode="reverify"
        onSignInAgain={onSignInAgain}
      />
    );
  }
  if (failure instanceof ApiError && failure.envelope.code === 'NOT_FOUND') {
    return <NotFoundPage />;
  }
  const refresh = () => {
    void read.mutate();
  };
  const submitted = (jobId: string, text: string) => {
    own.current.add(jobId);
    pending.current = text;
    const submittedScope = scope;
    void read.mutate().then((answer) => {
      pending.current = null;
      // The prior owner's request is never announced to the next owner (L1-26).
      // The client's generation is read live: a boundary moves it before any re-render.
      const liveScope = `${account}:${client.generation}`;
      if (!mounted.current || currentScope.current !== submittedScope) return;
      if (liveScope !== submittedScope) return;
      // A failed refresh leaves the last answer, which holds no change: the text alone.
      const parts = answer ? observe(answer) : [];
      announce([text, ...parts].join(PART_SEPARATOR));
    });
  };
  const data = read.data;
  return (
    <Panel title="운영" testId="operations-view">
      {failure ? <StatusLine value={describeError(failure)} /> : null}
      {!data && !failure ? <p role="status">운영 상태를 불러오고 있습니다</p> : null}
      {data ? (
        <>
          <CapabilityTable
            items={data.dashboard.items}
            incidents={data.incidents.items}
            paused={paused}
            onTogglePause={() => setPaused((value) => !value)}
            onRefresh={refresh}
          />
          <IncidentList
            incidents={data.incidents.items}
            onRecover={(value) => setIncident(value)}
          />
          <RecoveryPanel
            client={client}
            account={account}
            policy={operationsPolicy}
            items={data.dashboard.items}
            incident={incident}
            onSubmitted={submitted}
          />
        </>
      ) : null}
    </Panel>
  );
}

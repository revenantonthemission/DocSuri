'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import { getJobState, subscribeJobEvents, type JobEvent } from '@/lib/api/contentJobApi';
import { UserFacingError } from '@/lib/api/errors';
import { isTerminalJobState } from '@/lib/api/contentJobContracts';
import ErrorBoundary from '@/components/ErrorBoundary';
import ErrorBoundaryFallback from '@/components/ErrorBoundaryFallback';
import { emitJobDiagnostic } from '@/lib/jobDiagnostics';
import {
  JOB_FALLBACK_INTERVAL_MS,
  adoptJobSnapshot,
  applyJobEvent,
  createJobProjection,
  jobStateLabel,
  type JobProjection,
} from '@/lib/jobState';

// JobStatus — live job projection with an honest fallback (Step 31/32).
//
// The native EventSource is the live path; when it cannot stay connected the
// panel falls back to a fixed two-second SWR poll so the status never silently
// freezes. The two paths never overlap: the poll key exists only while the
// fallback is active and the job is not terminal. Projection semantics
// (duplicate/stale/obsolete/terminal) live in lib/jobState; this component only
// renders them and announces state changes through one polite live region.

const STATE_COLORS: Record<string, string> = {
  SUBMITTED: 'text-blue-600',
  ACCEPTED: 'text-yellow-600',
  QUEUED: 'text-yellow-600',
  RUNNING: 'text-blue-600',
  COMPLETED: 'text-green-600',
  FAILED: 'text-red-600',
  ABSTAINED: 'text-gray-600',
};

export interface JobStatusProps {
  jobId: string;
  /** Stable-owner context for the contained fallback's safe return. */
  paperId?: string;
  onComplete?: (
    state: 'COMPLETED' | 'FAILED' | 'ABSTAINED',
    assetId?: string,
    error?: unknown,
  ) => void;
}

function JobStatusPanel({ jobId, onComplete }: JobStatusProps) {
  const [projection, setProjection] = useState<JobProjection>(() => createJobProjection(jobId));
  const [history, setHistory] = useState<string[]>([]);
  const [announcement, setAnnouncement] = useState<string | null>(null);
  const [streamMode, setStreamMode] = useState<'connecting' | 'live' | 'fallback'>('connecting');
  const [accessLost, setAccessLost] = useState(false);
  const projectionRef = useRef(projection);
  // Bounded measurement point: mount time, so the first stream open can record
  // its connection latency for later benchmark verification.
  const mountedAtRef = useRef<number>(Date.now());
  // Bounded measurement point: the first committed status, recorded once per
  // job identity so the mount-to-first-status timing is measurable too.
  const firstStatusRef = useRef(false);
  const recordFirstStatus = useCallback(() => {
    if (firstStatusRef.current) return;
    firstStatusRef.current = true;
    emitJobDiagnostic({ kind: 'status', latencyMs: Date.now() - mountedAtRef.current });
  }, []);

  // A new job identity resets the projection and cursors — never carry another
  // job's terminal state into a fresh submit.
  useEffect(() => {
    const fresh = createJobProjection(jobId);
    projectionRef.current = fresh;
    firstStatusRef.current = false;
    setProjection(fresh);
    setHistory([]);
    setAnnouncement(null);
    setStreamMode('connecting');
  }, [jobId]);

  const handleEvent = useCallback((event: JobEvent) => {
    const applied = applyJobEvent(projectionRef.current, event);
    if (applied.disposition !== 'applied') return;
    const becameTerminal = applied.projection.terminal && !projectionRef.current.terminal;
    projectionRef.current = applied.projection;
    setProjection(applied.projection);
    setHistory((previous) => [
      ...previous,
      `${event.state} @ ${new Date(event.timestampUs / 1000).toLocaleTimeString()}`,
    ]);
    if (applied.announcement) setAnnouncement(applied.announcement);
    const terminalState = applied.projection.snapshot?.state;
    if (becameTerminal && terminalState && isTerminalJobState(terminalState)) {
      emitJobDiagnostic({ kind: 'terminal', state: terminalState });
    }
    recordFirstStatus();
  }, [recordFirstStatus]);

  // Live stream. The verified cursor rides every (re)creation, so a browser
  // that gives up on its own reconnect still recovers: an error hands over to
  // the fallback poll and schedules one recreated EventSource carrying the last
  // accepted event id; a successful open returns to live and hides the note.
  const [reconnectNonce, setReconnectNonce] = useState(0);
  useEffect(() => {
    if (projectionRef.current.terminal || accessLost) return;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    const cursor = projectionRef.current.lastEventId ?? undefined;
    const unsubscribe = subscribeJobEvents(
      jobId,
      {
        onOpen: () => {
          setStreamMode('live');
          emitJobDiagnostic({
            kind: 'stream',
            mode: 'live',
            latencyMs: Date.now() - mountedAtRef.current,
          });
        },
        onEvent: handleEvent,
        onError: () => {
          setStreamMode('fallback');
          emitJobDiagnostic({ kind: 'stream', mode: 'fallback' });
          if (reconnectTimer === null && !projectionRef.current.terminal) {
            reconnectTimer = setTimeout(
              () => setReconnectNonce((nonce) => nonce + 1),
              JOB_FALLBACK_INTERVAL_MS,
            );
          }
        },
      },
      cursor,
    );
    return () => {
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      unsubscribe();
    };
  }, [handleEvent, jobId, projection.terminal, reconnectNonce, accessLost]);

  // Fallback poll — fixed two-second cadence, only while the stream is down and
  // the job has not settled. SWR owns caching/retry; the key gates the overlap.
  const fallbackKey =
    streamMode === 'fallback' && !projection.terminal && !accessLost
      ? (['job-state', jobId] as const)
      : null;
  const { data: polledState, error: pollError } = useSWR(fallbackKey, () => getJobState(jobId), {
    refreshInterval: JOB_FALLBACK_INTERVAL_MS,
    revalidateOnFocus: false,
    shouldRetryOnError: true,
  });

  // An access loss from the owner-scoped read clears the view and cancels the
  // work: polling stops, the stream is closed and no recreation is scheduled.
  // The human must re-authenticate. 403 (forbidden) is an access loss too; a
  // 404 stays retryable — the contract's generic not-owned/unknown body is
  // indistinguishable from propagation lag, so the owner keeps a transient
  // retry rather than a silent stop.
  useEffect(() => {
    if (
      pollError instanceof UserFacingError &&
      (pollError.kind === 'auth' || pollError.kind === 'forbidden')
    ) {
      setAccessLost(true);
    }
  }, [pollError]);

  useEffect(() => {
    if (!polledState) return;
    const applied = adoptJobSnapshot(projectionRef.current, polledState);
    if (applied.disposition !== 'applied' || !applied.changed) return;
    const becameTerminal = applied.projection.terminal && !projectionRef.current.terminal;
    projectionRef.current = applied.projection;
    setProjection(applied.projection);
    if (applied.announcement) setAnnouncement(applied.announcement);
    const terminalState = applied.projection.snapshot?.state;
    if (becameTerminal && terminalState && isTerminalJobState(terminalState)) {
      emitJobDiagnostic({ kind: 'terminal', state: terminalState });
    }
    recordFirstStatus();
  }, [polledState, recordFirstStatus]);

  const snapshot = projection.snapshot;
  if (accessLost) {
    return (
      <div role="status" className="rounded-lg border bg-white p-4 text-sm text-gray-700">
        접근 권한을 확인할 수 없어 작업 추적을 중지했습니다. 다시 로그인한 뒤 시도해 주세요.
      </div>
    );
  }
  if (!snapshot) {
    return (
      <div role="status" aria-live="polite" aria-busy="true" className="text-sm text-gray-500">
        작업 상태 로딩 중...
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border bg-white p-4">
      <div className="flex items-center justify-between">
        <span className="font-medium">작업 상태</span>
        <span
          data-testid="job-state-label"
          className={`font-medium ${STATE_COLORS[snapshot.state] ?? 'text-gray-600'}`}
        >
          {jobStateLabel(snapshot.state)}
        </span>
      </div>

      {/* The single polite live region: it announces state CHANGES only, so a
          repeated frame never re-announces. The visible label above is plain
          text for on-screen reading and navigation. */}
      <span className="sr-only" role="status" aria-live="polite" aria-busy={!projection.terminal}>
        {announcement ?? ''}
      </span>

      {streamMode === 'fallback' && !projection.terminal && (
        <p className="text-xs text-gray-500">
          연결이 끊겨 2초 간격으로 상태를 확인하고 있습니다.
        </p>
      )}

      {snapshot.assetId && (
        <div className="text-sm text-green-600">
          자산 ID: <code className="break-all">{snapshot.assetId}</code>
        </div>
      )}

      {snapshot.error && (
        <div className="text-sm text-red-600">
          오류: {snapshot.error.message} ({snapshot.error.errorType})
          {snapshot.error.retryable && <span className="ml-2 text-yellow-600">(재시도 가능)</span>}
        </div>
      )}

      {snapshot.abstainReason && (
        <div className="text-sm text-gray-600">기권 사유: {snapshot.abstainReason}</div>
      )}

      <details className="mt-2">
        <summary className="cursor-pointer text-sm text-gray-500">이벤트 히스토리</summary>
        <ul className="mt-1 space-y-1 text-xs text-gray-500">
          {history.map((entry, index) => (
            <li key={`${index}-${entry}`}>{entry}</li>
          ))}
        </ul>
      </details>

      {projection.terminal && onComplete && (
        <div className="mt-2 border-t pt-2">
          <button
            type="button"
            onClick={() =>
              onComplete(
                snapshot.state as 'COMPLETED' | 'FAILED' | 'ABSTAINED',
                snapshot.assetId,
                snapshot.error,
              )
            }
            className="text-sm text-blue-600 hover:underline"
          >
            계속하기
          </button>
        </div>
      )}
    </div>
  );
}

export function JobStatus(props: JobStatusProps) {
  // Containment wraps the whole SSE-consuming surface; the reset is
  // tracking-only (re-mount), never a resubmit.
  const [resetKey, setResetKey] = useState(0);
  return (
    <ErrorBoundary
      onReset={() => setResetKey((key) => key + 1)}
      fallback={({ reset }) => (
        <ErrorBoundaryFallback
          {...(props.paperId !== undefined ? { paperId: props.paperId } : {})}
          onReset={reset}
        />
      )}
    >
      <JobStatusPanel key={resetKey} {...props} />
    </ErrorBoundary>
  );
}

export default JobStatus;

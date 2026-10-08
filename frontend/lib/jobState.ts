// Job state projection — ordering, deduplication and terminal stickiness for
// the live job surface (plan Step 31/32).
//
// The stream is at-least-once and can interleave a recreated EventSource's
// replays with live frames, so the projection is the single place that decides
// what a frame MEANS: dedupe by eventId, drop older-than-watermark history,
// reject other jobs' events, and never regress a terminal state (ADR-013:
// recovered terminal states stay terminal). Announcements are deduplicated —
// the same state arriving twice must not re-announce.

import {
  isTerminalJobState,
  type ContentJobState,
  type JobEvent,
  type JobStateSnapshot,
} from './api/contentJobContracts';

export const JOB_FALLBACK_INTERVAL_MS = 2000;

export const JOB_STATE_LABELS: Record<ContentJobState, string> = {
  SUBMITTED: '접수됨',
  ACCEPTED: '대기중',
  QUEUED: '대기중',
  RUNNING: '처리중',
  COMPLETED: '완료',
  FAILED: '실패',
  ABSTAINED: '기권',
};

export function jobStateLabel(state: ContentJobState): string {
  return JOB_STATE_LABELS[state];
}

export interface JobProjection {
  jobId: string;
  snapshot: JobStateSnapshot | null;
  /** Cursor for a recreated EventSource (last accepted event's id). */
  lastEventId: string | null;
  /** Greatest accepted durable watermark (`seq`) — the ordering authority
   * (C1/C3: never regress below the greatest accepted watermark). */
  watermarkSeq: number;
  terminal: boolean;
  history: readonly JobEvent[];
  seenEventIds: ReadonlySet<string>;
}

export function createJobProjection(jobId: string): JobProjection {
  return {
    jobId,
    snapshot: null,
    lastEventId: null,
    watermarkSeq: -1,
    terminal: false,
    history: [],
    seenEventIds: new Set<string>(),
  };
}

export type JobEventDisposition =
  | 'applied'
  | 'duplicate'
  | 'stale'
  | 'obsolete'
  | 'after-terminal';

export interface JobEventApplication {
  projection: JobProjection;
  disposition: JobEventDisposition;
  /** True when the visible snapshot changed (a render/announcement trigger). */
  changed: boolean;
  /** Live-region text, present only when the STATE label changed. */
  announcement: string | null;
}

function snapshotFromEvent(jobId: string, event: JobEvent): JobStateSnapshot {
  const snapshot: JobStateSnapshot = { jobId, seq: event.seq, state: event.state };
  const { assetId, error, abstainReason } = event.payload ?? {};
  if (assetId !== undefined) snapshot.assetId = assetId;
  if (error !== undefined) snapshot.error = error;
  if (abstainReason !== undefined) snapshot.abstainReason = abstainReason;
  return snapshot;
}

function snapshotsEqual(a: JobStateSnapshot, b: JobStateSnapshot): boolean {
  // `seq` is the durable watermark, not visible content — a seq bump with an
  // unchanged state/payload is not a visible change.
  return (
    a.state === b.state &&
    a.assetId === b.assetId &&
    a.abstainReason === b.abstainReason &&
    JSON.stringify(a.error ?? null) === JSON.stringify(b.error ?? null)
  );
}

/** Apply one streamed event to the projection. Pure — returns a new projection. */
export function applyJobEvent(projection: JobProjection, event: JobEvent): JobEventApplication {
  if (event.jobId !== projection.jobId) {
    return { projection, disposition: 'obsolete', changed: false, announcement: null };
  }
  if (projection.seenEventIds.has(event.eventId)) {
    return { projection, disposition: 'duplicate', changed: false, announcement: null };
  }
  if (projection.terminal) {
    return { projection, disposition: 'after-terminal', changed: false, announcement: null };
  }
  if (event.seq < projection.watermarkSeq) {
    return { projection, disposition: 'stale', changed: false, announcement: null };
  }

  const snapshot = snapshotFromEvent(projection.jobId, event);
  const stateChanged = projection.snapshot?.state !== event.state;
  const changed = projection.snapshot === null || !snapshotsEqual(projection.snapshot, snapshot);
  const seenEventIds = new Set(projection.seenEventIds);
  seenEventIds.add(event.eventId);

  return {
    projection: {
      jobId: projection.jobId,
      snapshot,
      lastEventId: event.eventId,
      watermarkSeq: Math.max(projection.watermarkSeq, event.seq),
      terminal: isTerminalJobState(event.state),
      history: [...projection.history, event],
      seenEventIds,
    },
    disposition: 'applied',
    changed,
    announcement: stateChanged ? jobStateLabel(event.state) : null,
  };
}

/**
 * Adopt an authoritative polled state read (the SWR fallback) without
 * disturbing stream cursors: a poll may observe a state ahead of or behind the
 * stream, but it must never regress a terminal state, never regress below the
 * greatest accepted `seq` watermark, and never clear an existing snapshot.
 */
export function adoptJobSnapshot(
  projection: JobProjection,
  snapshot: JobStateSnapshot,
): JobEventApplication {
  if (snapshot.jobId !== projection.jobId) {
    return { projection, disposition: 'obsolete', changed: false, announcement: null };
  }
  if (projection.terminal && !isTerminalJobState(snapshot.state)) {
    return { projection, disposition: 'after-terminal', changed: false, announcement: null };
  }
  if (snapshot.seq < projection.watermarkSeq) {
    return { projection, disposition: 'stale', changed: false, announcement: null };
  }
  const stateChanged = projection.snapshot?.state !== snapshot.state;
  const changed = projection.snapshot === null || !snapshotsEqual(projection.snapshot, snapshot);
  return {
    projection: {
      ...projection,
      snapshot,
      watermarkSeq: Math.max(projection.watermarkSeq, snapshot.seq),
      terminal: projection.terminal || isTerminalJobState(snapshot.state),
    },
    disposition: 'applied',
    changed,
    announcement: stateChanged ? jobStateLabel(snapshot.state) : null,
  };
}

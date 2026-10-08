// JobDiagnostics — bounded, scrubbed lifecycle telemetry for the job surface
// (Step 37; NFR7).
//
// Only allowlisted, non-identifying fields ever leave a call site: never
// decoded content, code, data, request parameters, job/user identifiers or
// error stacks. The buffer is bounded, and a failing sender is swallowed —
// diagnostics must never break the UI, recurse, or grow without bound.

export type JobDiagnosticEvent =
  | {
      kind: 'submit';
      taskType: 'summarize' | 'translate';
      outcome: 'started' | 'sent' | 'uncertain' | 'rejected';
    }
  | {
      kind: 'stream';
      mode: 'connecting' | 'live' | 'fallback';
      /** Bounded measurement point: mount-to-open latency in ms (live only). */
      latencyMs?: number;
    }
  | {
      kind: 'status';
      /** Bounded measurement point: mount-to-first-committed-status latency in ms. */
      latencyMs?: number;
    }
  | { kind: 'terminal'; state: 'COMPLETED' | 'FAILED' | 'ABSTAINED' }
  | {
      kind: 'result-read';
      outcome: 'ready' | 'not-ready' | 'expired' | 'unavailable' | 'transient' | 'auth' | 'not-found';
    };

export interface JobDiagnosticRecord {
  event: JobDiagnosticEvent;
  at: number;
}

const MAX_BUFFER = 50;
const buffer: JobDiagnosticRecord[] = [];
let sender: ((records: readonly JobDiagnosticRecord[]) => void) | null = null;

/** A measurement is admitted only as a finite non-negative bounded value. */
function boundedLatency(value: unknown): number | null {
  if (
    typeof value === 'number' &&
    Number.isFinite(value) &&
    value >= 0 &&
    value <= 600000
  ) {
    return Math.round(value);
  }
  return null;
}

function sanitize(event: JobDiagnosticEvent): JobDiagnosticEvent {
  switch (event.kind) {
    case 'submit':
      return { kind: 'submit', taskType: event.taskType, outcome: event.outcome };
    case 'stream': {
      const latencyMs = boundedLatency(event.latencyMs);
      return latencyMs === null
        ? { kind: 'stream', mode: event.mode }
        : { kind: 'stream', mode: event.mode, latencyMs };
    }
    case 'status': {
      const latencyMs = boundedLatency(event.latencyMs);
      return latencyMs === null ? { kind: 'status' } : { kind: 'status', latencyMs };
    }
    case 'terminal':
      return { kind: 'terminal', state: event.state };
    case 'result-read':
      return { kind: 'result-read', outcome: event.outcome };
  }
}

/** Install (or clear) the delivery seam. A sender must never throw — and if it
 * does, the throw is swallowed here so diagnostics stay non-fatal. */
export function setJobDiagnosticSender(
  next: ((records: readonly JobDiagnosticRecord[]) => void) | null,
): void {
  sender = next;
}

export function emitJobDiagnostic(event: JobDiagnosticEvent, now = Date.now()): void {
  const record: JobDiagnosticRecord = { event: sanitize(event), at: now };
  buffer.push(record);
  if (buffer.length > MAX_BUFFER) buffer.splice(0, buffer.length - MAX_BUFFER);
  if (sender) {
    try {
      sender([record]);
    } catch {
      // A failed diagnostic delivery is never a user-facing failure.
    }
  }
}

/** The bounded, scrubbed tail — what a handoff/monitor may inspect. */
export function readJobDiagnostics(): readonly JobDiagnosticRecord[] {
  return [...buffer];
}

export function clearJobDiagnostics(): void {
  buffer.length = 0;
}

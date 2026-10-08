/** Content Job API — submit, state, events (C4).
 *
 * Every content-job call rides the same-origin BFF (`/bff/api/content-jobs/*`)
 * so the httpOnly session cookie reaches the gateway server-side and the
 * gateway URL never enters client JS (SEC-8/SEC-3). Native `fetch` only — no
 * retry stack, no cross-origin base, no cookie material in client code.
 */

import { normalizeHttpError, UserFacingError } from './errors';
import {
  isContentJobState,
  parseJobEvent,
  parseJobResult,
  parseJobState,
  type ContentJobState,
  type ContentJobTaskType,
  type JobEvent,
  type JobStateSnapshot,
  type PreparedResultEnvelope,
} from './contentJobContracts';

export type { JobEvent, JobStateSnapshot, PreparedResultEnvelope };
export type JobState = JobStateSnapshot;
export type { ContentJobState, ContentJobTaskType };

export const CONTENT_JOB_API_BASE = '/bff/api/content-jobs';

export interface SubmitJobRequest {
  taskType: ContentJobTaskType;
  input: Record<string, unknown>;
  idempotencyKey?: string;
}

export interface SubmitJobResponse {
  jobId: string;
  state: ContentJobState;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

async function readErrorBody(res: Response): Promise<unknown> {
  try {
    const text = await res.text();
    if (!text) return undefined;
    try {
      const parsed: unknown = JSON.parse(text);
      return isRecord(parsed) ? parsed.message : text;
    } catch {
      return text;
    }
  } catch {
    return undefined;
  }
}

/**
 * The single fetch seam for content-job calls: same-origin credentials and
 * no-store on every hop. Exported so tests can assert the boundary.
 */
export async function jobFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(path, {
    ...init,
    credentials: 'same-origin',
    cache: 'no-store',
  });
}

/** Submit a new content job. Returns the server-assigned identity. */
export async function submitJob(request: SubmitJobRequest): Promise<SubmitJobResponse> {
  const res = await jobFetch(`${CONTENT_JOB_API_BASE}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw normalizeHttpError(res.status, await readErrorBody(res));
  const body: unknown = await res.json().catch(() => null);
  if (!isRecord(body) || typeof body.jobId !== 'string' || body.jobId.trim().length === 0) {
    throw new UserFacingError('unknown');
  }
  const state = isContentJobState(body.state) ? body.state : 'SUBMITTED';
  return { jobId: body.jobId, state };
}

/** Read the authoritative current state for one job. */
export async function getJobState(jobId: string): Promise<JobStateSnapshot> {
  const res = await jobFetch(`${CONTENT_JOB_API_BASE}/${encodeURIComponent(jobId)}/state`);
  if (!res.ok) throw normalizeHttpError(res.status, await readErrorBody(res));
  const snapshot = parseJobState(await res.json().catch(() => null));
  if (!snapshot) throw new UserFacingError('unknown');
  return snapshot;
}

export type JobResultFailure =
  | 'not-ready'
  | 'expired'
  | 'unavailable'
  | 'auth'
  | 'not-found'
  | 'transient';

/** Distinct, non-generative failure reasons for a result read. */
export class JobResultError extends Error {
  readonly reason: JobResultFailure;

  constructor(reason: JobResultFailure, message: string) {
    super(message);
    this.name = 'JobResultError';
    this.reason = reason;
  }
}

/**
 * Read the exact prepared result for a completed job. This is a READ: it never
 * generates, enqueues or repairs — a non-COMPLETED job, an expired result or an
 * unsupported identity is surfaced as its own controlled state.
 */
export async function getJobResult(jobId: string): Promise<PreparedResultEnvelope> {
  const res = await jobFetch(`${CONTENT_JOB_API_BASE}/${encodeURIComponent(jobId)}/result`);
  if (res.status === 409) throw new JobResultError('not-ready', '아직 결과가 준비되지 않았습니다.');
  if (res.status === 410) {
    throw new JobResultError('expired', '결과 보관 기간이 지나 더 이상 표시할 수 없습니다.');
  }
  if (res.status === 422) throw new JobResultError('unavailable', '이 결과를 표시할 수 없습니다.');
  if (res.status === 401 || res.status === 403) {
    throw new JobResultError('auth', '로그인이 필요합니다. 다시 로그인해 주세요.');
  }
  if (res.status === 404) throw new JobResultError('not-found', '결과를 찾을 수 없습니다.');
  if (res.status >= 500) {
    throw new JobResultError('transient', '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.');
  }
  if (!res.ok) throw new UserFacingError('unknown');
  const envelope = parseJobResult(await res.json().catch(() => null), jobId);
  if (!envelope) throw new JobResultError('unavailable', '이 결과를 표시할 수 없습니다.');
  return envelope;
}

export interface JobSubscriptionHandlers {
  onEvent: (event: JobEvent) => void;
  onOpen?: () => void;
  onError?: (error: Event) => void;
}

/**
 * Subscribe to a job's SSE stream through the same-origin BFF. The native
 * EventSource owns reconnection; `lastEventId` resumes from the verified
 * cursor when a previous connection observed an event. The returned function
 * closes the stream (terminal/context/access cleanup).
 */
export function subscribeJobEvents(
  jobId: string,
  handlers: JobSubscriptionHandlers | ((event: JobEvent) => void),
  lastEventId?: string,
): () => void {
  const resolved: JobSubscriptionHandlers =
    typeof handlers === 'function' ? { onEvent: handlers } : handlers;
  const url = new URL(
    `${CONTENT_JOB_API_BASE}/${encodeURIComponent(jobId)}/events`,
    window.location.origin,
  );
  if (lastEventId) url.searchParams.set('lastEventId', lastEventId);

  const source = new EventSource(url.toString());
  source.onmessage = (message: MessageEvent<string>) => {
    let event: JobEvent | null = null;
    try {
      event = parseJobEvent(JSON.parse(message.data));
    } catch {
      event = null;
    }
    if (event) resolved.onEvent(event);
  };
  source.onopen = () => resolved.onOpen?.();
  source.onerror = (error) => resolved.onError?.(error);

  return () => source.close();
}

// --- Legacy (U3-owned) helpers -------------------------------------------------
// The asset helpers below still follow the pre-F07 redirect flow and are
// migrated with AssetViewer under u3-secure-assets (SECURITY-08). They are
// intentionally untouched by the u1 completion pass.

export interface TranslateResponse {
  assetId?: string;
  jobId?: string;
  state: string;
  source: 'cache' | 'job';
}

export interface AssetTokenResponse {
  token: string;
  expiresIn: number;
}

/** @deprecated superseded by content-job submit with taskType 'translate'. */
export async function translate(input: {
  paperId: string;
  version?: number;
  targetLang?: string;
  persona?: Record<string, unknown>;
}): Promise<TranslateResponse> {
  const res = await jobFetch(`${CONTENT_JOB_API_BASE}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw normalizeHttpError(res.status, await readErrorBody(res));
  return (await res.json()) as TranslateResponse;
}

/** @deprecated retireAssetRedirect: U3 moves delivery to `/bff/api/papers/{paperId}/assets/{assetId}`. */
export async function getAssetUrl(assetId: string, token: string): Promise<string> {
  const res = await jobFetch(`/bff/api/content-jobs/assets/${assetId}?token=${encodeURIComponent(token)}`, {
    redirect: 'manual', // Don't follow redirect automatically
  });
  if (res.status === 307) {
    return res.headers.get('Location') || '';
  }
  throw new UserFacingError('unknown');
}

/** @deprecated retired with the presigned asset flow (SECURITY-08). */
export async function issueAssetToken(
  assetId: string,
  action: 'view' = 'view',
): Promise<AssetTokenResponse> {
  const res = await jobFetch(`${CONTENT_JOB_API_BASE}/assets/${assetId}/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw normalizeHttpError(res.status, await readErrorBody(res));
  return (await res.json()) as AssetTokenResponse;
}

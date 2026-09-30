/** Content Job API — submit, events, assets */

export interface JobState {
  jobId: string;
  state: 'SUBMITTED' | 'ACCEPTED' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'ABSTAINED';
  assetId?: string;
  error?: { errorType: string; message: string; retryable: boolean; retryAfterSeconds?: number };
  abstainReason?: string;
}

export interface JobEvent {
  eventId: string;
  jobId: string;
  state: string;
  timestampUs: number;
  payload?: {
    assetId?: string;
    error?: { errorType: string; message: string; retryable: boolean };
    abstainReason?: string;
  };
}

export interface SubmitJobRequest {
  taskType: 'translate' | 'summarize' | 'novelty' | 'evidence' | 'ingest_userdoc';
  input: Record<string, unknown>;
  idempotencyKey?: string;
}

export interface SubmitJobResponse {
  jobId: string;
  state: string;
}

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

const API_BASE = '/api/content-jobs';

/** Submit a new content job */
export async function submitJob(request: SubmitJobRequest): Promise<SubmitJobResponse> {
  const res = await fetch(`${API_BASE}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Get job state */
export async function getJobState(jobId: string): Promise<JobState> {
  const res = await fetch(`${API_BASE}/${jobId}/state`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Subscribe to job events via SSE */
export function subscribeJobEvents(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  lastEventId?: string
): () => void {
  const url = new URL(`/api/content-jobs/${jobId}/events`, window.location.origin);
  if (lastEventId) url.searchParams.set('lastEventId', lastEventId);

  const es = new EventSource(url.toString());
  es.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data) as JobEvent;
      onEvent(event);
    } catch {
      // ignore parse errors
    }
  };
  es.onerror = () => {
    es.close();
  };

  return () => es.close();
}

/** Translate with cache support */
export async function translate(input: {
  paperId: string;
  version?: number;
  targetLang?: string;
  persona?: Record<string, unknown>;
}): Promise<{ assetId?: string; jobId?: string; state: string; source: 'cache' | 'job' }> {
  const res = await fetch(`${API_BASE}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Get asset via presigned URL */
export async function getAssetUrl(assetId: string, token: string): Promise<string> {
  const res = await fetch(`/api/content-jobs/assets/${assetId}?token=${encodeURIComponent(token)}`, {
    redirect: 'manual', // Don't follow redirect automatically
  });
  if (res.status === 307) {
    return res.headers.get('Location') || '';
  }
  throw new Error(`Failed to get asset URL: ${res.status}`);
}

/** Issue asset access token */
export async function issueAssetToken(assetId: string, action: 'view' = 'view'): Promise<{ token: string; expiresIn: number }> {
  const res = await fetch(`/api/content-jobs/assets/${assetId}/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

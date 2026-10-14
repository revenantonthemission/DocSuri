/**
 * Canonical C13 browser transport for the U1 workspace.
 *
 * Same-origin `/api/v2` calls only: server-derived principal, session/anonymous
 * bootstrap, Origin/CSRF and idempotency conventions. No storage paths, worker
 * routes or private identifiers are built here.
 */

export const API = '/api/v2';

export const SEARCH_POLICY = { policyId: 'synthetic-paper-search', revision: '1' };
export const READING_POLICY = { policyId: 'local-research', revision: '1' };
export const LIBRARY_POLICY = { policyId: 'synthetic-local-library', revision: '1' };
export const SETTINGS_POLICY = { policyId: 'synthetic-personal-settings', revision: '1' };
export const ENTRY_POLICY = { policyId: 'synthetic-local-entry', revision: '1' };
export const PROCESSING_POLICY = { policyId: 'local-research', revision: '1' };
export const VOCABULARY = 'synthetic-paper-options-1';

export type PaperRef = { paperId: string; versionId: string; eligibilityRevision: string };
export type PolicyRef = { policyId: string; revision: string };
export type Author = string;
export type QueryContext = {
  query: string;
  modeId: string;
  orderId: string;
  filters: { filterId: string; operatorId: string; values: (string | number | boolean)[] }[];
  vocabularyRevision: string;
  policyRef: PolicyRef;
};
export type ErrorEnvelope = {
  code: string;
  requestId: string;
  retryable: boolean;
  messageKey: string;
  retryAfterSeconds?: number;
};
export type SessionBootstrap = {
  signedIn: boolean;
  accountId?: string;
  authorityRevision?: string;
  csrfToken: string;
};
export type NavigationItem = {
  routeId: string;
  titleKey: string;
  path: string;
  capabilityId: string;
  available: boolean;
  reasonKey?: string;
};
export type SearchHit = {
  paper: PaperRef;
  title: string;
  authors: Author[];
  publishedAt?: string;
  snippet: string;
  sourceUrl: string;
  availability: string;
  matchExplanation: string;
};
export type SearchResponse = {
  executionId: string;
  query: QueryContext;
  hits: SearchHit[];
  page: { nextCursor?: string; snapshotRevision: string };
  outcome: string;
  effectiveModeId: string;
  limitations: string[];
};

export class ApiError extends Error {
  readonly envelope: ErrorEnvelope;
  readonly status: number;

  constructor(status: number, envelope: ErrorEnvelope) {
    super(envelope.code);
    this.status = status;
    this.envelope = envelope;
  }
}

/** Bounded retry for idempotent reads under transient dependency pressure. */
export async function retryTransient<T>(work: () => Promise<T>, attempts = 2): Promise<T> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await work();
    } catch (failure) {
      // Admission refusals are retryable only for the finite capacity message;
      // any other NOT_READY state stays visible for explicit manual recovery.
      const transient =
        failure instanceof ApiError &&
        (failure.envelope.code === 'DEPENDENCY_UNAVAILABLE' ||
          failure.envelope.code === 'RATE_LIMITED' ||
          (failure.envelope.code === 'NOT_READY' &&
            failure.envelope.messageKey === 'capacity.exhausted'));
      if (!transient || attempt >= attempts) throw failure;
      await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
    }
  }
}

const SAFE_CODES = new Set([
  'APPROVAL_REQUIRED',
  'CONFLICT',
  'DEADLINE_EXCEEDED',
  'DEPENDENCY_UNAVAILABLE',
  'FORBIDDEN',
  'IDEMPOTENCY_CONFLICT',
  'INVALID_ARGUMENT',
  'INVALID_CONTENT',
  'NOT_FOUND',
  'NOT_READY',
  'POLICY_UNRESOLVED',
  'QUOTA_EXCEEDED',
  'RATE_LIMITED',
  'SNAPSHOT_EXPIRED',
  'SOURCE_INELIGIBLE',
  'STALE_REVISION',
  'UNAUTHENTICATED',
  'UNKNOWN_OUTCOME',
]);

function envelope(value: unknown): ErrorEnvelope {
  if (typeof value === 'object' && value !== null) {
    const record = value as Record<string, unknown>;
    const code = typeof record.code === 'string' ? record.code : 'INTERNAL_ERROR';
    return {
      code: SAFE_CODES.has(code) ? code : 'INTERNAL_ERROR',
      requestId: typeof record.requestId === 'string' ? record.requestId : 'unknown',
      retryable: record.retryable === true,
      messageKey: typeof record.messageKey === 'string' ? record.messageKey : 'request.error',
      ...(typeof record.retryAfterSeconds === 'number'
        ? { retryAfterSeconds: record.retryAfterSeconds }
        : {}),
    };
  }
  return {
    code: 'INTERNAL_ERROR',
    requestId: 'unknown',
    retryable: false,
    messageKey: 'request.error',
  };
}

/** Every response is scoped to the authority generation that requested it. */
export class Transport {
  private csrf = '';
  private identity = '';
  private epoch = 0;
  private bootstrapFlight?: Promise<SessionBootstrap>;
  private listeners = new Set<() => void>();
  get generation(): number {
    return this.epoch;
  }
  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
  invalidateBoundary(): void {
    this.csrf = '';
    this.identity = '';
    this.bootstrapFlight = undefined;
    this.epoch += 1;
    this.listeners.forEach((listener) => listener());
  }
  bootstrap(): Promise<SessionBootstrap> {
    // A second anonymous bootstrap rotates the cookie behind the first CSRF token.
    // Share exactly one in-flight read until an authority boundary invalidates it.
    if (this.bootstrapFlight) return this.bootstrapFlight;
    const flight = this.readBootstrap();
    this.bootstrapFlight = flight;
    void flight
      .finally(() => {
        if (this.bootstrapFlight === flight) this.bootstrapFlight = undefined;
      })
      .catch(() => undefined);
    return flight;
  }
  private async readBootstrap(): Promise<SessionBootstrap> {
    const generation = this.epoch;
    const response = await fetch(`${API}/session`, {
      credentials: 'same-origin',
      cache: 'no-store',
    });
    if (!response.ok) throw new ApiError(response.status, envelope(await safeJson(response)));
    const value = (await response.json()) as SessionBootstrap;
    if (generation !== this.epoch) throw staleResponse();
    const identity = value.signedIn ? `${value.accountId}:${value.authorityRevision}` : 'guest';
    this.csrf = value.csrfToken;
    if (identity !== this.identity) {
      this.identity = identity;
      this.epoch += 1;
      this.listeners.forEach((listener) => listener());
    }
    return value;
  }
  async read<T>(path: string, body: unknown): Promise<T> {
    return this.call<T>('POST', path, body);
  }
  async post<T>(path: string, body: unknown, operationKey?: string): Promise<T> {
    return this.call<T>('POST', path, body, operationKey);
  }
  async get<T>(path: string): Promise<T> {
    return this.call<T>('GET', path, undefined);
  }
  private async call<T>(
    method: string,
    path: string,
    body: unknown,
    operationKey?: string,
  ): Promise<T> {
    if (!safeApiPath(path))
      throw new ApiError(422, {
        code: 'INVALID_ARGUMENT',
        requestId: 'local',
        retryable: false,
        messageKey: 'local.path',
      });
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (body !== undefined) {
      headers['X-CSRF-Token'] = await this.ensureCsrf();
      headers['Idempotency-Key'] = operationKey ?? crypto.randomUUID();
    }
    const generation = this.epoch;
    const scoped = path !== `${API}/capabilities`;
    let response: Response;
    try {
      response = await fetch(path, {
        method,
        credentials: 'same-origin',
        cache: 'no-store',
        headers,
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });
    } catch {
      if (scoped && generation !== this.epoch) throw staleResponse();
      throw new ApiError(0, {
        code: 'UNKNOWN_OUTCOME',
        requestId: operationKey ?? 'unobserved',
        retryable: false,
        messageKey: 'request.unknown',
      });
    }
    const value = response.status === 204 ? undefined : await safeJson(response);
    if (scoped && generation !== this.epoch) throw staleResponse();
    if (!response.ok) {
      const error = new ApiError(response.status, envelope(value));
      if (error.envelope.code === 'UNAUTHENTICATED') this.invalidateBoundary();
      throw error;
    }
    return value as T;
  }
  private async ensureCsrf(): Promise<string> {
    if (!this.csrf) await this.bootstrap();
    return this.csrf;
  }
}

function staleResponse(): ApiError {
  return new ApiError(401, {
    code: 'UNAUTHENTICATED',
    requestId: 'stale-response',
    retryable: false,
    messageKey: 'session.changed',
  });
}
export function safeApiPath(path: string): boolean {
  // Only registered versioned local routes; never provider URLs or dot segments.
  return (
    /^\/api\/v2\/(?:session|capabilities|jobs\/[a-zA-Z0-9-]+(?:\/(?:events|result))?|identity\/callback\/(?:google|orcid)|c(?:0[1-9]|1[0-3])\/[a-z][a-z0-9-]*(?:\/[a-zA-Z0-9-]+)?)(?:\?[^#\\]*)?$/.test(
      path,
    ) &&
    !/%(?:2e|2f|5c)/i.test(path) &&
    !path.includes('..')
  );
}

async function safeJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

/** Human copy is keyed by the bounded disposition, never raw server text. */
export function dispositionCopy(code: string): string {
  switch (code) {
    case 'UNAUTHENTICATED':
      return '다시 로그인해 주세요';
    case 'FORBIDDEN':
      return '이 작업을 사용할 수 없어요';
    case 'NOT_FOUND':
      return '찾을 수 없어요';
    case 'NOT_READY':
      return '아직 준비되지 않았어요';
    case 'POLICY_UNRESOLVED':
      return '현재 이 작업을 사용할 수 없어요';
    case 'QUOTA_EXCEEDED':
      return '사용 한도를 모두 사용했어요';
    case 'RATE_LIMITED':
      return '요청이 많아요. 잠시 후 다시 시도해 주세요';
    case 'SNAPSHOT_EXPIRED':
      return '검색 결과가 변경되었어요. 다시 검색해 주세요';
    case 'CONFLICT':
    case 'STALE_REVISION':
      return '다른 곳에서 변경되었어요';
    case 'DEPENDENCY_UNAVAILABLE':
      return '일시적으로 사용할 수 없어요';
    case 'UNKNOWN_OUTCOME':
      return '처리 결과를 확인하고 있어요';
    case 'DEADLINE_EXCEEDED':
      return '시간이 초과되었어요';
    case 'INVALID_ARGUMENT':
      return '입력을 확인해 주세요';
    default:
      return '문제가 발생했어요';
  }
}

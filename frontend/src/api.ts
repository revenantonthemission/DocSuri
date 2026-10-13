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
  return { code: 'INTERNAL_ERROR', requestId: 'unknown', retryable: false, messageKey: 'request.error' };
}

export class Transport {
  private csrf = '';

  async bootstrap(): Promise<SessionBootstrap> {
    const response = await fetch(`${API}/session`, { credentials: 'same-origin' });
    if (!response.ok) throw new ApiError(response.status, envelope(await safeJson(response)));
    const value = (await response.json()) as SessionBootstrap;
    this.csrf = value.csrfToken;
    return value;
  }

  /** Explicit read; navigation never submits work. */
  async read<T>(path: string, body: unknown): Promise<T> {
    return this.call<T>('POST', path, body);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.call<T>('POST', path, body);
  }

  async get<T>(path: string): Promise<T> {
    return this.call<T>('GET', path, undefined);
  }

  private async call<T>(method: string, path: string, body: unknown): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (body !== undefined) {
      headers['X-CSRF-Token'] = await this.ensureCsrf();
      headers['Idempotency-Key'] = crypto.randomUUID();
    }
    const response = await fetch(path.startsWith('http') ? path : path, {
      method,
      credentials: 'same-origin',
      headers,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    if (!response.ok) throw new ApiError(response.status, envelope(await safeJson(response)));
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  /** A reloaded page may act before its first bootstrap resolved; the caller's
   * own session/anonymous flow still supplies the current CSRF. */
  private async ensureCsrf(): Promise<string> {
    if (!this.csrf) await this.bootstrap();
    return this.csrf;
  }
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

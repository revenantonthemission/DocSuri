// Content-job wire contracts — typed, fail-closed validation for the job
// surface (C4, plan Step 21).
//
// The backend streams `{eventId, jobId, state, timestampUs, payload?}` JSON
// events and returns the same shape (minus eventId) for state reads. Nothing
// here trusts the wire: every field is checked before it reaches UI state, an
// unknown or malformed envelope is rejected (never coerced), and payload
// errors keep the exact `{errorType, message, retryable}` contract.
//
// Instants: wire timestamps arrive as microseconds since epoch
// (`timestampUs`). Stored/typed instants elsewhere are RFC 3339 strings, so a
// strict validator lives here for payload fields that carry them.

import type { SummaryVM, TranslationVM } from '@/types/generated';

export type ContentJobTaskType =
  | 'summarize'
  | 'translate'
  | 'novelty'
  | 'evidence'
  | 'ingest_userdoc';

export type ContentJobState =
  | 'SUBMITTED'
  | 'ACCEPTED'
  | 'QUEUED'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'ABSTAINED';

export const CONTENT_JOB_STATES: readonly ContentJobState[] = [
  'SUBMITTED',
  'ACCEPTED',
  'QUEUED',
  'RUNNING',
  'COMPLETED',
  'FAILED',
  'ABSTAINED',
];

export const TERMINAL_JOB_STATES: readonly ContentJobState[] = [
  'COMPLETED',
  'FAILED',
  'ABSTAINED',
];

const STATE_SET: ReadonlySet<string> = new Set(CONTENT_JOB_STATES);
const TERMINAL_SET: ReadonlySet<string> = new Set(TERMINAL_JOB_STATES);

export function isContentJobState(value: unknown): value is ContentJobState {
  return typeof value === 'string' && STATE_SET.has(value);
}

export function isTerminalJobState(
  value: unknown,
): value is 'COMPLETED' | 'FAILED' | 'ABSTAINED' {
  return typeof value === 'string' && TERMINAL_SET.has(value);
}

export interface JobErrorInfo {
  errorType: string;
  message: string;
  retryable: boolean;
  retryAfterSeconds?: number;
}

export interface JobStateSnapshot {
  jobId: string;
  /** Durable state/event watermark from the same transaction (C1 required). */
  seq: number;
  state: ContentJobState;
  assetId?: string;
  error?: JobErrorInfo;
  abstainReason?: string;
}

export interface JobEventPayload {
  assetId?: string;
  error?: { errorType: string; message: string; retryable: boolean };
  abstainReason?: string;
}

export interface JobEvent {
  eventId: string;
  jobId: string;
  /** Per-job ordering watermark (C3 required; the ordering authority). */
  seq: number;
  state: ContentJobState;
  timestampUs: number;
  payload?: JobEventPayload;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

const MAX_SAFE_SEQ = 9007199254740991;

function isSeq(value: unknown, minimum: number): value is number {
  return (
    typeof value === 'number' &&
    Number.isInteger(value) &&
    value >= minimum &&
    value <= MAX_SAFE_SEQ
  );
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function parseJobError(value: unknown): JobErrorInfo | undefined {
  if (!isRecord(value)) return undefined;
  if (
    !nonEmptyString(value.errorType) ||
    typeof value.message !== 'string' ||
    typeof value.retryable !== 'boolean'
  ) {
    return undefined;
  }
  const error: JobErrorInfo = {
    errorType: value.errorType,
    message: value.message,
    retryable: value.retryable,
  };
  if (typeof value.retryAfterSeconds === 'number' && Number.isFinite(value.retryAfterSeconds)) {
    error.retryAfterSeconds = value.retryAfterSeconds;
  }
  return error;
}

function parseOptionalString(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key];
  return typeof value === 'string' ? value : undefined;
}

/**
 * Parse a state read (`GET …/{jobId}/state`) — fail-closed: returns null on any
 * shape violation rather than coercing an unknown state, a missing watermark or
 * a partial body.
 */
export function parseJobState(raw: unknown): JobStateSnapshot | null {
  if (!isRecord(raw)) return null;
  if (!nonEmptyString(raw.jobId)) return null;
  if (!isSeq(raw.seq, 0)) return null;
  if (!isContentJobState(raw.state)) return null;
  const snapshot: JobStateSnapshot = { jobId: raw.jobId, seq: raw.seq, state: raw.state };
  const assetId = parseOptionalString(raw, 'assetId');
  if (assetId !== undefined) snapshot.assetId = assetId;
  const error = parseJobError(raw.error);
  if (error !== undefined) snapshot.error = error;
  const abstainReason = parseOptionalString(raw, 'abstainReason');
  if (abstainReason !== undefined) snapshot.abstainReason = abstainReason;
  return snapshot;
}

/**
 * Parse one streamed job event. The C3 envelope is the ordering authority:
 * `seq` (the durable per-job watermark) is required, and `timestampUs` must be
 * a finite non-negative integer.
 */
export function parseJobEvent(raw: unknown): JobEvent | null {
  if (!isRecord(raw)) return null;
  if (!nonEmptyString(raw.eventId)) return null;
  if (!nonEmptyString(raw.jobId)) return null;
  if (!isSeq(raw.seq, 1)) return null;
  if (!isContentJobState(raw.state)) return null;
  if (
    typeof raw.timestampUs !== 'number' ||
    !Number.isFinite(raw.timestampUs) ||
    raw.timestampUs < 0 ||
    !Number.isInteger(raw.timestampUs)
  ) {
    return null;
  }
  const event: JobEvent = {
    eventId: raw.eventId,
    jobId: raw.jobId,
    seq: raw.seq,
    state: raw.state,
    timestampUs: raw.timestampUs,
  };
  if (isRecord(raw.payload)) {
    const payload: JobEventPayload = {};
    const assetId = parseOptionalString(raw.payload, 'assetId');
    if (assetId !== undefined) payload.assetId = assetId;
    const abstainReason = parseOptionalString(raw.payload, 'abstainReason');
    if (abstainReason !== undefined) payload.abstainReason = abstainReason;
    const payloadError = parseJobError(raw.payload.error);
    if (payloadError !== undefined) {
      payload.error = {
        errorType: payloadError.errorType,
        message: payloadError.message,
        retryable: payloadError.retryable,
      };
    }
    event.payload = payload;
  }
  return event;
}

const RFC3339_RE =
  /^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$/;

/**
 * Strict RFC 3339 instant check for payload instants (active calendar and
 * offset validation, not a loose Date.parse fallback).
 */
export function isValidRfc3339Instant(value: unknown): value is string {
  if (typeof value !== 'string' || !RFC3339_RE.test(value)) return false;
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return false;
  // Reject impossible calendar dates that Date.parse normalizes silently
  // (e.g. 2026-02-30) by round-tripping the date portion.
  const datePart = value.slice(0, 10);
  const [year, month, day] = datePart.split('-').map((part) => Number(part));
  if (year === undefined || month === undefined || day === undefined) return false;
  const roundTrip = new Date(Date.UTC(year, month - 1, day));
  return (
    roundTrip.getUTCFullYear() === year &&
    roundTrip.getUTCMonth() === month - 1 &&
    roundTrip.getUTCDate() === day
  );
}

/** Coerce a state snapshot into user-visible text without leaking internals. */
export function jobErrorText(error: JobErrorInfo | undefined): string | null {
  if (!error) return null;
  const text = error.message.trim();
  return text.length > 0 ? text : null;
}

// --- Prepared result envelope (C2) ---------------------------------------------
// `GET …/{jobId}/result` returns the exact immutable prepared payload; nothing
// here generates, re-runs or repairs a result. The content branch is the
// allowlisted user-facing payload the existing views render.

export interface PreparedSummaryContent {
  status: 'ok';
  task: 'summary';
  meta?: Record<string, unknown>;
  cached?: boolean;
  summary: SummaryVM;
}

export interface PreparedTranslationContent {
  status: 'ok';
  task: 'translate';
  translation: TranslationVM;
}

export type PreparedResultContent = PreparedSummaryContent | PreparedTranslationContent;

export interface PreparedResultEnvelope {
  resultRef: string;
  preparedResult: {
    schemaVersion: 1;
    jobId: string;
    taskType: 'summarize' | 'translate';
    submittedLevel?: 'expert' | 'beginner';
    assetId?: string;
    preparedAt: string;
    expiresAt: string;
    content: PreparedResultContent;
  };
}

function hasSummaryShape(value: unknown): value is SummaryVM {
  if (!isRecord(value)) return false;
  return (
    typeof value.tldr === 'string' &&
    Array.isArray(value.contributions) &&
    typeof value.method === 'string' &&
    typeof value.results === 'string' &&
    typeof value.limitations === 'string' &&
    isRecord(value.reproducibility) &&
    typeof value.reproducibility.code === 'string' &&
    typeof value.reproducibility.data === 'string' &&
    Array.isArray(value.anchors)
  );
}

function parsePreparedContent(raw: unknown, taskType: 'summarize' | 'translate'): PreparedResultContent | null {
  if (!isRecord(raw) || raw.status !== 'ok') return null;
  if (taskType === 'summarize') {
    if (raw.task !== 'summary' || !hasSummaryShape(raw.summary)) return null;
    const content: PreparedSummaryContent = { status: 'ok', task: 'summary', summary: raw.summary };
    if (isRecord(raw.meta)) content.meta = raw.meta;
    if (typeof raw.cached === 'boolean') content.cached = raw.cached;
    return content;
  }
  if (raw.task !== 'translate' || !isRecord(raw.translation)) return null;
  const docModel = raw.translation.docModel;
  if (!isRecord(docModel)) return null;
  return {
    status: 'ok',
    task: 'translate',
    translation: raw.translation as unknown as TranslationVM,
  };
}

/**
 * Parse a prepared-result envelope for one exact job — fail-closed: envelope
 * identity must agree with the selected job and task, instants must be valid
 * RFC 3339, and the content branch must satisfy its contract shape.
 */
export function parseJobResult(raw: unknown, expectedJobId: string): PreparedResultEnvelope | null {
  if (!isRecord(raw)) return null;
  if (!nonEmptyString(raw.resultRef)) return null;
  if (!isRecord(raw.preparedResult)) return null;
  const prepared = raw.preparedResult;
  if (prepared.schemaVersion !== 1) return null;
  if (prepared.jobId !== expectedJobId) return null;
  if (prepared.taskType !== 'summarize' && prepared.taskType !== 'translate') return null;
  if (!isValidRfc3339Instant(prepared.preparedAt)) return null;
  if (!isValidRfc3339Instant(prepared.expiresAt)) return null;
  const content = parsePreparedContent(prepared.content, prepared.taskType);
  if (!content) return null;

  const envelope: PreparedResultEnvelope = {
    resultRef: raw.resultRef,
    preparedResult: {
      schemaVersion: 1,
      jobId: prepared.jobId,
      taskType: prepared.taskType,
      preparedAt: prepared.preparedAt,
      expiresAt: prepared.expiresAt,
      content,
    },
  };
  if (prepared.submittedLevel === 'expert' || prepared.submittedLevel === 'beginner') {
    envelope.preparedResult.submittedLevel = prepared.submittedLevel;
  }
  if (typeof prepared.assetId === 'string') envelope.preparedResult.assetId = prepared.assetId;
  return envelope;
}

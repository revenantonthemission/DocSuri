// IdempotencyService — deterministic, owner-bound job keys (BR1.3–BR1.5).
//
// The key is a SHA-256 over `userId:paperId:taskType:JSON.stringify(params)`
// (native crypto.subtle) so a same-parameter retry — page reload included —
// derives the identical key and the backend can deduplicate the submission.
// Storage is localStorage under `idempotency:{paperId}:{taskType}`; reads and
// writes are corrupt/quota-safe: a broken, missing, or unwritable store never
// throws into the UI, it degrades to "no stored original".

import type { ContentJobTaskType } from './api/contentJobContracts';

export interface IdempotencyKeyInput {
  userId: string;
  paperId: string;
  taskType: ContentJobTaskType;
  params: Record<string, unknown>;
}

const IDEMPOTENCY_KEY_RE = /^[a-f0-9]{64}$/;

export function idempotencyStorageKey(paperId: string, taskType: ContentJobTaskType): string {
  return `idempotency:${paperId}:${taskType}`;
}

/** SHA-256 hex of the canonical `userId:paperId:taskType:params` string. */
export async function buildIdempotencyKey(input: IdempotencyKeyInput): Promise<string> {
  const canonical = `${input.userId}:${input.paperId}:${input.taskType}:${JSON.stringify(input.params)}`;
  const bytes = new TextEncoder().encode(canonical);
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Read the stored key for this paper/task. Returns null when the store is
 * unavailable, empty, corrupt, or holds a value that is not a key — a bad
 * value must never be replayed as an idempotency identity.
 */
export function readStoredIdempotencyKey(
  paperId: string,
  taskType: ContentJobTaskType,
): string | null {
  try {
    const raw = window.localStorage.getItem(idempotencyStorageKey(paperId, taskType));
    if (raw === null || !IDEMPOTENCY_KEY_RE.test(raw)) return null;
    return raw;
  } catch {
    return null;
  }
}

/** Persist the key for reload recovery. Quota/unavailable failures are ignored. */
export function storeIdempotencyKey(
  paperId: string,
  taskType: ContentJobTaskType,
  key: string,
): void {
  if (!IDEMPOTENCY_KEY_RE.test(key)) return;
  try {
    window.localStorage.setItem(idempotencyStorageKey(paperId, taskType), key);
  } catch {
    // Storage unavailable or over quota — the in-memory key still governs this session.
  }
}

/** Drop the key once the job reached a terminal state (no replay of old work). */
export function clearStoredIdempotencyKey(paperId: string, taskType: ContentJobTaskType): void {
  try {
    window.localStorage.removeItem(idempotencyStorageKey(paperId, taskType));
  } catch {
    // Nothing to clear.
  }
}

// --- Captured original request -------------------------------------------------
// ADR-013/C4: the original request is captured BEFORE sending, and a same-key
// recovery replays those captured bytes — never a draft rebuilt from the
// current controls. A diverged draft is a NEW explicit submission with its own
// key; it must never ride the original key. The captured record is also
// OWNER-BOUND: a different session owner must never replay another owner's
// captured request (owner/request reconciliation).

export interface StoredOriginalRequest {
  key: string;
  taskType: ContentJobTaskType;
  owner: string;
  input: Record<string, unknown>;
}

export function originalRequestStorageKey(paperId: string, taskType: ContentJobTaskType): string {
  return `job-original:${paperId}:${taskType}`;
}

export function storeOriginalRequest(
  paperId: string,
  taskType: ContentJobTaskType,
  original: StoredOriginalRequest,
): void {
  if (!IDEMPOTENCY_KEY_RE.test(original.key) || original.owner.trim().length === 0) return;
  try {
    window.localStorage.setItem(
      originalRequestStorageKey(paperId, taskType),
      JSON.stringify({
        key: original.key,
        taskType,
        owner: original.owner,
        input: original.input,
      }),
    );
  } catch {
    // Storage unavailable or over quota — recovery is then unavailable, never wrong.
  }
}

/** Read the captured original for this paper/task; null when absent or unusable. */
export function readStoredOriginalRequest(
  paperId: string,
  taskType: ContentJobTaskType,
): StoredOriginalRequest | null {
  try {
    const raw = window.localStorage.getItem(originalRequestStorageKey(paperId, taskType));
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
    const record = parsed as Record<string, unknown>;
    if (
      typeof record.key !== 'string' ||
      !IDEMPOTENCY_KEY_RE.test(record.key) ||
      record.taskType !== taskType ||
      typeof record.owner !== 'string' ||
      record.owner.trim().length === 0 ||
      record.input === null ||
      typeof record.input !== 'object' ||
      Array.isArray(record.input)
    ) {
      return null;
    }
    return {
      key: record.key,
      taskType,
      owner: record.owner,
      input: record.input as Record<string, unknown>,
    };
  } catch {
    return null;
  }
}

/**
 * The captured original usable by THIS owner. A record captured by another
 * session owner is not a recovery source for this one — it reads as absent.
 */
export function readStoredOriginalRequestForOwner(
  paperId: string,
  taskType: ContentJobTaskType,
  owner: string,
): StoredOriginalRequest | null {
  const original = readStoredOriginalRequest(paperId, taskType);
  if (!original || owner.trim().length === 0 || original.owner !== owner) return null;
  return original;
}

export function clearStoredOriginalRequest(paperId: string, taskType: ContentJobTaskType): void {
  try {
    window.localStorage.removeItem(originalRequestStorageKey(paperId, taskType));
  } catch {
    // Nothing to clear.
  }
}

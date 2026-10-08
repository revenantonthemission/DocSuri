import { webcrypto } from 'node:crypto';
import { beforeAll, describe, expect, it } from 'vitest';
import {
  buildIdempotencyKey,
  clearStoredIdempotencyKey,
  idempotencyStorageKey,
  originalRequestStorageKey,
  readStoredOriginalRequest,
  readStoredOriginalRequestForOwner,
  readStoredIdempotencyKey,
  storeIdempotencyKey,
  storeOriginalRequest,
} from '@/lib/idempotencyService';

beforeAll(() => {
  // jsdom does not expose WebCrypto; the service mandates native crypto.subtle.
  if (!globalThis.crypto?.subtle) {
    Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
  }
});

describe('IdempotencyService', () => {
  it('derives the mandated SHA-256 over userId:paperId:taskType:params', async () => {
    const key = await buildIdempotencyKey({
      userId: 'user-1',
      paperId: 'paper-9',
      taskType: 'summarize',
      params: { a: 1 },
    });
    expect(key).toBe('2d0f62393606a5ded677d4f8b719fd487ab5c3cc9357c70a7d5db28acffa114e');
  });

  it('is deterministic per parameter set and distinct across owner/task/params', async () => {
    const base = { userId: 'user-1', paperId: 'paper-9', params: { a: 1 } };
    const [first, second, otherTask, otherUser, otherParams] = await Promise.all([
      buildIdempotencyKey({ ...base, taskType: 'summarize' }),
      buildIdempotencyKey({ ...base, taskType: 'summarize' }),
      buildIdempotencyKey({ ...base, taskType: 'translate' }),
      buildIdempotencyKey({ ...base, userId: 'user-2', taskType: 'summarize' }),
      buildIdempotencyKey({ ...base, taskType: 'summarize', params: { a: 2 } }),
    ]);
    expect(first).toBe(second);
    expect(first).not.toBe(otherTask);
    expect(first).not.toBe(otherUser);
    expect(first).not.toBe(otherParams);
    expect(otherTask).toBe('58e60cfe4eab7373066a28ad55919665bdeeca8e9e0d14ecbac0f8f992bb7527');
  });

  it('round-trips a key through the mandated localStorage slot', () => {
    const paperId = 'paper-roundtrip';
    expect(readStoredIdempotencyKey(paperId, 'summarize')).toBeNull();

    const key = 'a'.repeat(64);
    storeIdempotencyKey(paperId, 'summarize', key);

    expect(window.localStorage.getItem(idempotencyStorageKey(paperId, 'summarize'))).toBe(key);
    expect(readStoredIdempotencyKey(paperId, 'summarize')).toBe(key);
    // Per-task slots are isolated: a translate read must not see summarize's key.
    expect(readStoredIdempotencyKey(paperId, 'translate')).toBeNull();

    clearStoredIdempotencyKey(paperId, 'summarize');
    expect(readStoredIdempotencyKey(paperId, 'summarize')).toBeNull();
  });

  it('treats corrupt or malformed stored values as absent (never replays them)', () => {
    const paperId = 'paper-corrupt';
    window.localStorage.setItem(idempotencyStorageKey(paperId, 'summarize'), 'not-a-digest');
    expect(readStoredIdempotencyKey(paperId, 'summarize')).toBeNull();

    window.localStorage.setItem(
      idempotencyStorageKey(paperId, 'translate'),
      JSON.stringify({ key: 'x' }),
    );
    expect(readStoredIdempotencyKey(paperId, 'translate')).toBeNull();

    // The writer also refuses a non-key value.
    storeIdempotencyKey(paperId, 'summarize', 'short');
    expect(window.localStorage.getItem(idempotencyStorageKey(paperId, 'summarize'))).toBe(
      'not-a-digest',
    );
  });

  it('captures an owner-bound original request and reconciles owners on read', () => {
    const input = { paperId: 'paper-own', version: 1, targetLang: 'ko', persona: 'expert', scope: 'full' };
    storeOriginalRequest('paper-own', 'summarize', {
      key: 'e'.repeat(64),
      taskType: 'summarize',
      owner: 'user-1',
      input,
    });
    expect(readStoredOriginalRequest('paper-own', 'summarize')).toEqual({
      key: 'e'.repeat(64),
      taskType: 'summarize',
      owner: 'user-1',
      input,
    });
    expect(readStoredOriginalRequestForOwner('paper-own', 'summarize', 'user-1')).not.toBeNull();
    // Another owner (or no owner) never gets a recovery source.
    expect(readStoredOriginalRequestForOwner('paper-own', 'summarize', 'user-2')).toBeNull();
    expect(readStoredOriginalRequestForOwner('paper-own', 'summarize', '')).toBeNull();

    // A non-key or ownerless write is refused outright.
    storeOriginalRequest('paper-own', 'translate', {
      key: 'short',
      taskType: 'translate',
      owner: 'user-1',
      input,
    });
    expect(readStoredOriginalRequest('paper-own', 'translate')).toBeNull();
    storeOriginalRequest('paper-own', 'translate', {
      key: 'f'.repeat(64),
      taskType: 'translate',
      owner: '   ',
      input,
    });
    expect(readStoredOriginalRequest('paper-own', 'translate')).toBeNull();
    expect(window.localStorage.getItem(originalRequestStorageKey('paper-own', 'translate'))).toBeNull();
  });

  it('degrades quietly when storage is unwritable (quota) or unreadable', () => {
    const original = window.localStorage;
    const failingStorage = {
      getItem: () => {
        throw new DOMException('unavailable', 'SecurityError');
      },
      setItem: () => {
        throw new DOMException('quota', 'QuotaExceededError');
      },
      removeItem: () => {
        throw new DOMException('unavailable', 'SecurityError');
      },
    };
    Object.defineProperty(window, 'localStorage', { configurable: true, value: failingStorage });
    try {
      expect(() => storeIdempotencyKey('paper-quota', 'summarize', 'b'.repeat(64))).not.toThrow();
      expect(readStoredIdempotencyKey('paper-quota', 'summarize')).toBeNull();
      expect(() => clearStoredIdempotencyKey('paper-quota', 'summarize')).not.toThrow();
    } finally {
      Object.defineProperty(window, 'localStorage', { configurable: true, value: original });
    }
  });
});

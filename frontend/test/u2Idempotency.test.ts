import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  clearStoredOriginalRequest,
  originalRequestStorageKey,
  readStoredOriginalRequest,
  readStoredOriginalRequestForOwner,
  storeOriginalRequest,
} from '@/lib/idempotencyService';

const INPUT = {
  paperId: 'paper-9',
  version: 3,
  targetLang: 'ko',
  persona: 'expert',
  scope: 'full',
};

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe('captured-original storage behavior (u2)', () => {
  it('round-trips and clears the original slot', () => {
    storeOriginalRequest('paper-9', 'translate', {
      key: 'a'.repeat(64),
      taskType: 'translate',
      owner: 'user-1',
      input: INPUT,
    });
    expect(readStoredOriginalRequest('paper-9', 'translate')).toEqual({
      key: 'a'.repeat(64),
      taskType: 'translate',
      owner: 'user-1',
      input: INPUT,
    });

    clearStoredOriginalRequest('paper-9', 'translate');
    expect(readStoredOriginalRequest('paper-9', 'translate')).toBeNull();
  });

  it('treats corrupt JSON in the original slot as absent', () => {
    window.localStorage.setItem(originalRequestStorageKey('paper-9', 'translate'), '{not json');
    expect(readStoredOriginalRequest('paper-9', 'translate')).toBeNull();
    expect(readStoredOriginalRequestForOwner('paper-9', 'translate', 'user-1')).toBeNull();
  });

  it('rejects a record whose stored taskType differs from the requested slot', () => {
    window.localStorage.setItem(
      originalRequestStorageKey('paper-9', 'translate'),
      JSON.stringify({ key: 'b'.repeat(64), taskType: 'summarize', owner: 'user-1', input: INPUT }),
    );
    expect(readStoredOriginalRequest('paper-9', 'translate')).toBeNull();
  });

  it('rejects an ownerless record', () => {
    window.localStorage.setItem(
      originalRequestStorageKey('paper-9', 'translate'),
      JSON.stringify({ key: 'c'.repeat(64), taskType: 'translate', input: INPUT }),
    );
    expect(readStoredOriginalRequest('paper-9', 'translate')).toBeNull();
  });

  it('degrades quietly when storage throws on every operation', () => {
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
      expect(() =>
        storeOriginalRequest('paper-9', 'translate', {
          key: 'd'.repeat(64),
          taskType: 'translate',
          owner: 'user-1',
          input: INPUT,
        }),
      ).not.toThrow();
      expect(readStoredOriginalRequest('paper-9', 'translate')).toBeNull();
      expect(readStoredOriginalRequestForOwner('paper-9', 'translate', 'user-1')).toBeNull();
      expect(() => clearStoredOriginalRequest('paper-9', 'translate')).not.toThrow();
    } finally {
      Object.defineProperty(window, 'localStorage', { configurable: true, value: original });
    }
  });

  it('keeps owner scoping across two owners sharing one slot', () => {
    storeOriginalRequest('paper-9', 'translate', {
      key: 'e'.repeat(64),
      taskType: 'translate',
      owner: 'user-1',
      input: INPUT,
    });
    // Only the capturing owner can read it for recovery.
    expect(readStoredOriginalRequestForOwner('paper-9', 'translate', 'user-1')).not.toBeNull();
    expect(readStoredOriginalRequestForOwner('paper-9', 'translate', 'user-2')).toBeNull();
    // A later capture replaces the slot for the new owner.
    storeOriginalRequest('paper-9', 'translate', {
      key: 'f'.repeat(64),
      taskType: 'translate',
      owner: 'user-2',
      input: INPUT,
    });
    expect(readStoredOriginalRequestForOwner('paper-9', 'translate', 'user-1')).toBeNull();
    expect(readStoredOriginalRequestForOwner('paper-9', 'translate', 'user-2')?.key).toBe(
      'f'.repeat(64),
    );
  });
});

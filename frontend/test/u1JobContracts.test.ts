import { describe, expect, it } from 'vitest';
import {
  isContentJobState,
  isTerminalJobState,
  isValidRfc3339Instant,
  parseJobEvent,
  parseJobState,
} from '@/lib/api/contentJobContracts';

describe('content-job contracts', () => {
  it('parses a valid state read and keeps the optional fields', () => {
    const snapshot = parseJobState({
      jobId: 'job-1',
      seq: 4,
      state: 'RUNNING',
      assetId: 'asset-9',
      abstainReason: 'not enough evidence',
    });
    expect(snapshot).toEqual({
      jobId: 'job-1',
      seq: 4,
      state: 'RUNNING',
      assetId: 'asset-9',
      abstainReason: 'not enough evidence',
    });
  });

  it('rejects an unknown state instead of coercing it', () => {
    expect(parseJobState({ jobId: 'job-1', seq: 1, state: 'PROCESSING' })).toBeNull();
    expect(parseJobState({ jobId: '', seq: 1, state: 'RUNNING' })).toBeNull();
    expect(parseJobState({ jobId: 'job-1', state: 'RUNNING' })).toBeNull();
    expect(parseJobState({ jobId: 'job-1', seq: 1.5, state: 'RUNNING' })).toBeNull();
    expect(parseJobState('job-1')).toBeNull();
    expect(isContentJobState('PROCESSING')).toBe(false);
  });

  it('drops a malformed error object instead of leaking it into state', () => {
    const snapshot = parseJobState({
      jobId: 'job-1',
      seq: 2,
      state: 'FAILED',
      error: { errorType: 'worker_error', message: 'boom', retryable: 'yes' },
    });
    expect(snapshot).toEqual({ jobId: 'job-1', seq: 2, state: 'FAILED' });
  });

  it('keeps a well-formed error with retryAfterSeconds', () => {
    const snapshot = parseJobState({
      jobId: 'job-1',
      seq: 3,
      state: 'FAILED',
      error: { errorType: 'rate_limited', message: 'slow down', retryable: true, retryAfterSeconds: 30 },
    });
    expect(snapshot?.error).toEqual({
      errorType: 'rate_limited',
      message: 'slow down',
      retryable: true,
      retryAfterSeconds: 30,
    });
  });

  it('parses a valid event with its payload', () => {
    const event = parseJobEvent({
      eventId: 'evt-1',
      jobId: 'job-1',
      seq: 5,
      state: 'COMPLETED',
      timestampUs: 1791207141857,
      payload: { assetId: 'asset-1' },
    });
    expect(event).toEqual({
      eventId: 'evt-1',
      jobId: 'job-1',
      seq: 5,
      state: 'COMPLETED',
      timestampUs: 1791207141857,
      payload: { assetId: 'asset-1' },
    });
  });

  it('rejects malformed event envelopes (missing ids, bad instants)', () => {
    expect(
      parseJobEvent({ eventId: '', jobId: 'job-1', seq: 1, state: 'RUNNING', timestampUs: 1 }),
    ).toBeNull();
    expect(
      parseJobEvent({ eventId: 'e', jobId: 'job-1', seq: 1, state: 'RUNNING', timestampUs: -1 }),
    ).toBeNull();
    expect(
      parseJobEvent({ eventId: 'e', jobId: 'job-1', seq: 1, state: 'RUNNING', timestampUs: 1.5 }),
    ).toBeNull();
    // The C3 durable watermark is required and must be a positive integer.
    expect(
      parseJobEvent({ eventId: 'e', jobId: 'job-1', state: 'RUNNING', timestampUs: 1 }),
    ).toBeNull();
    expect(
      parseJobEvent({ eventId: 'e', jobId: 'job-1', seq: 0, state: 'RUNNING', timestampUs: 1 }),
    ).toBeNull();
    expect(
      parseJobEvent({ eventId: 'e', jobId: 'job-1', seq: 1, state: 'NOPE', timestampUs: 1 }),
    ).toBeNull();
  });

  it('classifies terminal states', () => {
    expect(isTerminalJobState('COMPLETED')).toBe(true);
    expect(isTerminalJobState('FAILED')).toBe(true);
    expect(isTerminalJobState('ABSTAINED')).toBe(true);
    expect(isTerminalJobState('RUNNING')).toBe(false);
  });

  it('validates RFC3339 instants, calendar included', () => {
    expect(isValidRfc3339Instant('2026-10-07T06:35:34Z')).toBe(true);
    expect(isValidRfc3339Instant('2026-10-07T15:35:34+09:00')).toBe(true);
    expect(isValidRfc3339Instant('2026-02-30T00:00:00Z')).toBe(false);
    expect(isValidRfc3339Instant('2026-10-07')).toBe(false);
    expect(isValidRfc3339Instant(1791207141857)).toBe(false);
  });
});

import { describe, expect, it } from 'vitest';
import {
  adoptJobSnapshot,
  applyJobEvent,
  createJobProjection,
  jobStateLabel,
} from '@/lib/jobState';
import type { JobEvent, JobStateSnapshot } from '@/lib/api/contentJobContracts';

function event(overrides: Partial<JobEvent> = {}): JobEvent {
  return {
    eventId: 'evt-1',
    jobId: 'job-1',
    seq: 5,
    state: 'RUNNING',
    timestampUs: 1,
    ...overrides,
  };
}

function snapshot(overrides: Partial<JobStateSnapshot> = {}): JobStateSnapshot {
  return { jobId: 'job-1', seq: 5, state: 'RUNNING', ...overrides };
}

describe('job projection restoration semantics (u2)', () => {
  it('orders by the seq watermark and drops stale history', () => {
    const first = applyJobEvent(createJobProjection('job-1'), event({ seq: 5 }));
    expect(first.disposition).toBe('applied');
    expect(first.projection.watermarkSeq).toBe(5);

    const stale = applyJobEvent(
      first.projection,
      event({ eventId: 'evt-old', seq: 3, state: 'QUEUED' }),
    );
    expect(stale.disposition).toBe('stale');
    expect(stale.projection).toBe(first.projection);

    const next = applyJobEvent(
      stale.projection,
      event({ eventId: 'evt-2', seq: 6, state: 'QUEUED' }),
    );
    expect(next.disposition).toBe('applied');
    expect(next.projection.watermarkSeq).toBe(6);
    expect(next.projection.snapshot && jobStateLabel(next.projection.snapshot.state)).toBe('대기중');
  });

  it('deduplicates a replayed event id after the stream is recreated', () => {
    const first = applyJobEvent(createJobProjection('job-1'), event({ seq: 5 }));
    const replay = applyJobEvent(first.projection, event({ seq: 5 }));
    expect(replay.disposition).toBe('duplicate');
    expect(replay.projection).toBe(first.projection);

    const resumed = applyJobEvent(
      replay.projection,
      event({ eventId: 'evt-2', seq: 5, state: 'ACCEPTED' }),
    );
    expect(resumed.disposition).toBe('applied');
    expect(resumed.projection.lastEventId).toBe('evt-2');
  });

  it('keeps the first terminal state sticky against later conflicts (ADR-013)', () => {
    const settled = applyJobEvent(
      createJobProjection('job-1'),
      event({ seq: 5, state: 'COMPLETED' }),
    );
    expect(settled.projection.terminal).toBe(true);

    const conflicted = applyJobEvent(
      settled.projection,
      event({ eventId: 'evt-2', seq: 6, state: 'FAILED' }),
    );
    expect(conflicted.disposition).toBe('after-terminal');
    expect(conflicted.projection.snapshot?.state).toBe('COMPLETED');

    const polledRegression = adoptJobSnapshot(
      conflicted.projection,
      snapshot({ seq: 7, state: 'RUNNING' }),
    );
    expect(polledRegression.disposition).toBe('after-terminal');
    expect(polledRegression.projection.snapshot?.state).toBe('COMPLETED');
  });

  it('adopts a poll snapshot at the watermark and rejects a stale or foreign one', () => {
    const first = applyJobEvent(createJobProjection('job-1'), event({ seq: 5 }));

    const stale = adoptJobSnapshot(first.projection, snapshot({ seq: 4, state: 'QUEUED' }));
    expect(stale.disposition).toBe('stale');

    const foreign = adoptJobSnapshot(first.projection, snapshot({ jobId: 'job-2' }));
    expect(foreign.disposition).toBe('obsolete');

    const adopted = adoptJobSnapshot(first.projection, snapshot({ seq: 6, state: 'ACCEPTED' }));
    expect(adopted.disposition).toBe('applied');
    expect(adopted.changed).toBe(true);
    expect(adopted.announcement).toBe('대기중');

    const unchanged = adoptJobSnapshot(adopted.projection, snapshot({ seq: 6, state: 'ACCEPTED' }));
    expect(unchanged.disposition).toBe('applied');
    expect(unchanged.changed).toBe(false);
    expect(unchanged.announcement).toBeNull();
  });

  it('announces a state change once and deduplicates repeated states', () => {
    const first = applyJobEvent(
      createJobProjection('job-1'),
      event({ seq: 5, state: 'RUNNING' }),
    );
    expect(first.announcement).toBe('처리중');

    const repeated = applyJobEvent(
      first.projection,
      event({ eventId: 'evt-2', seq: 6, state: 'RUNNING' }),
    );
    expect(repeated.disposition).toBe('applied');
    expect(repeated.changed).toBe(false);
    expect(repeated.announcement).toBeNull();
  });
});

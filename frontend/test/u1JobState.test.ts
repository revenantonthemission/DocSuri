import { describe, expect, it } from 'vitest';
import type { JobEvent } from '@/lib/api/contentJobContracts';
import {
  JOB_FALLBACK_INTERVAL_MS,
  adoptJobSnapshot,
  applyJobEvent,
  createJobProjection,
  jobStateLabel,
} from '@/lib/jobState';

function makeEvent(
  eventId: string,
  state: JobEvent['state'],
  seq: number,
  payload?: JobEvent['payload'],
  jobId = 'job-1',
): JobEvent {
  const event: JobEvent = { eventId, jobId, seq, state, timestampUs: seq * 100 };
  if (payload) event.payload = payload;
  return event;
}

describe('job state projection', () => {
  it('applies ordered events, tracks the cursor and announces only state changes', () => {
    let projection = createJobProjection('job-1');

    const first = applyJobEvent(projection, makeEvent('evt-1', 'RUNNING', 100));
    projection = first.projection;
    expect(first.disposition).toBe('applied');
    expect(first.changed).toBe(true);
    expect(first.announcement).toBe('처리중');
    expect(projection.lastEventId).toBe('evt-1');
    expect(projection.watermarkSeq).toBe(100);
    expect(projection.terminal).toBe(false);

    // Same state again (no new information) — no duplicate announcement.
    const repeat = applyJobEvent(projection, makeEvent('evt-2', 'RUNNING', 200));
    projection = repeat.projection;
    expect(repeat.disposition).toBe('applied');
    expect(repeat.changed).toBe(false);
    expect(repeat.announcement).toBeNull();

    // Payload-only change still updates visibility but does not re-announce.
    const withAsset = applyJobEvent(
      projection,
      makeEvent('evt-3', 'RUNNING', 300, { assetId: 'asset-1' }),
    );
    projection = withAsset.projection;
    expect(withAsset.changed).toBe(true);
    expect(withAsset.announcement).toBeNull();
    expect(projection.snapshot?.assetId).toBe('asset-1');
  });

  it('ignores duplicate event ids', () => {
    let projection = createJobProjection('job-1');
    projection = applyJobEvent(projection, makeEvent('evt-1', 'QUEUED', 100)).projection;

    const duplicate = applyJobEvent(projection, makeEvent('evt-1', 'RUNNING', 200));
    expect(duplicate.disposition).toBe('duplicate');
    expect(duplicate.projection).toBe(projection);
    expect(duplicate.changed).toBe(false);
  });

  it('orders by the durable seq watermark and drops older history as stale', () => {
    let projection = createJobProjection('job-1');
    projection = applyJobEvent(projection, makeEvent('evt-2', 'RUNNING', 200)).projection;

    const stale = applyJobEvent(projection, makeEvent('evt-1', 'QUEUED', 100));
    expect(stale.disposition).toBe('stale');
    expect(stale.projection).toBe(projection);
    expect(projection.watermarkSeq).toBe(200);
  });

  it('rejects another job\u2019s events as obsolete', () => {
    const projection = createJobProjection('job-1');
    const obsolete = applyJobEvent(projection, makeEvent('evt-1', 'RUNNING', 100, undefined, 'job-2'));
    expect(obsolete.disposition).toBe('obsolete');
    expect(obsolete.projection).toBe(projection);
  });

  it('keeps terminal states terminal (ADR-013)', () => {
    let projection = createJobProjection('job-1');
    projection = applyJobEvent(projection, makeEvent('evt-1', 'COMPLETED', 100, { assetId: 'a' }))
      .projection;
    expect(projection.terminal).toBe(true);

    const afterTerminal = applyJobEvent(projection, makeEvent('evt-2', 'RUNNING', 200));
    expect(afterTerminal.disposition).toBe('after-terminal');
    expect(afterTerminal.projection.snapshot?.state).toBe('COMPLETED');
    expect(afterTerminal.announcement).toBeNull();
  });

  it('adopts polled snapshots without regressing a terminal state', () => {
    let projection = createJobProjection('job-1');

    const polled = adoptJobSnapshot(projection, { jobId: 'job-1', seq: 1, state: 'ACCEPTED' });
    projection = polled.projection;
    expect(polled.announcement).toBe('대기중');
    expect(projection.snapshot?.state).toBe('ACCEPTED');
    expect(projection.watermarkSeq).toBe(1);

    // A stale poll below the accepted watermark never regresses the display.
    const stalePoll = adoptJobSnapshot(projection, { jobId: 'job-1', seq: 0, state: 'SUBMITTED' });
    expect(stalePoll.disposition).toBe('stale');
    expect(stalePoll.projection.snapshot?.state).toBe('ACCEPTED');

    projection = applyJobEvent(projection, makeEvent('evt-1', 'ABSTAINED', 100)).projection;

    const regression = adoptJobSnapshot(projection, { jobId: 'job-1', seq: 150, state: 'RUNNING' });
    expect(regression.disposition).toBe('after-terminal');
    expect(regression.projection.snapshot?.state).toBe('ABSTAINED');

    const otherJob = adoptJobSnapshot(projection, { jobId: 'job-2', seq: 1, state: 'RUNNING' });
    expect(otherJob.disposition).toBe('obsolete');
  });

  it('uses the mandated fixed two-second fallback cadence and readable labels', () => {
    expect(JOB_FALLBACK_INTERVAL_MS).toBe(2000);
    expect(jobStateLabel('SUBJECTIVELY_UNKNOWN' as never)).toBeUndefined();
    expect(jobStateLabel('COMPLETED')).toBe('완료');
  });
});

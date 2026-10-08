import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { SWRConfig } from 'swr';
import { JobStatus } from '@/components/JobStatus';
import {
  clearJobDiagnostics,
  emitJobDiagnostic,
  readJobDiagnostics,
  setJobDiagnosticSender,
} from '@/lib/jobDiagnostics';

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  close(): void {
    this.closed = true;
  }

  emit(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }
}

function renderStatus(jobId = 'job-1') {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <JobStatus jobId={jobId} onComplete={vi.fn()} />
    </SWRConfig>,
  );
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
  fetchMock = vi.fn(async () => {
    return new Response(JSON.stringify({ jobId: 'job-1', seq: 5, state: 'ACCEPTED' }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  clearJobDiagnostics();
  setJobDiagnosticSender(null);
});

afterEach(() => {
  setJobDiagnosticSender(null);
  clearJobDiagnostics();
  vi.unstubAllGlobals();
});

describe('job telemetry scenarios (u2)', () => {
  it('records the live → fallback → recreated-live sequence with a bounded latency value', async () => {
    const sent: unknown[] = [];
    setJobDiagnosticSender((records) => sent.push(...records.map((record) => record.event)));

    renderStatus();
    const first = FakeEventSource.instances[0]!;
    first.onopen?.();
    first.onerror?.(new Event('error'));

    await waitFor(() => expect(FakeEventSource.instances.length).toBe(2), { timeout: 3000 });
    FakeEventSource.instances[1]!.onopen?.();

    const streamEvents = readJobDiagnostics()
      .map((record) => record.event)
      .filter((event) => event.kind === 'stream');
    expect(streamEvents.map((event) => (event.kind === 'stream' ? event.mode : ''))).toEqual([
      'live',
      'fallback',
      'live',
    ]);
    const live = streamEvents[0]!;
    if (live.kind !== 'stream') throw new Error('unreachable');
    expect(typeof live.latencyMs).toBe('number');
    expect(live.latencyMs).toBeGreaterThanOrEqual(0);
    expect(live.latencyMs).toBeLessThanOrEqual(600000);
    // The status mount-to-first-commit measurement is recorded once, bounded.
    await waitFor(() =>
      expect(readJobDiagnostics().some((record) => record.event.kind === 'status')).toBe(true),
    );
    const status = readJobDiagnostics()
      .map((record) => record.event)
      .find((event) => event.kind === 'status');
    if (!status || status.kind !== 'status') throw new Error('unreachable');
    expect(
      status.latencyMs !== undefined && status.latencyMs >= 0 && status.latencyMs <= 600000,
    ).toBe(true);
    // Delivery reached the installed sender and no identifiers leak.
    expect(sent.length).toBeGreaterThanOrEqual(3);
    expect(JSON.stringify(readJobDiagnostics())).not.toContain('job-1');
  });

  it('a failing diagnostics sender never breaks stream handling', async () => {
    setJobDiagnosticSender(() => {
      throw new Error('sender down');
    });

    renderStatus();
    const first = FakeEventSource.instances[0]!;
    expect(() => {
      first.onopen?.();
      first.onerror?.(new Event('error'));
    }).not.toThrow();
    expect(readJobDiagnostics().length).toBeGreaterThanOrEqual(2);
  });

  it('records a terminal once and nothing after it', async () => {
    renderStatus();
    const first = FakeEventSource.instances[0]!;
    first.onopen?.();
    first.emit({ eventId: 'e1', jobId: 'job-1', seq: 5, state: 'COMPLETED', timestampUs: 1 });

    await waitFor(() =>
      expect(readJobDiagnostics().some((record) => record.event.kind === 'terminal')).toBe(true),
    );

    first.emit({ eventId: 'e2', jobId: 'job-1', seq: 6, state: 'FAILED', timestampUs: 2 });
    const terminals = readJobDiagnostics().filter((record) => record.event.kind === 'terminal');
    expect(terminals).toHaveLength(1);
  });

  it('drops invalid latency measurements and rounds valid ones', () => {
    emitJobDiagnostic({ kind: 'stream', mode: 'live', latencyMs: Number.NaN }, 1);
    emitJobDiagnostic({ kind: 'stream', mode: 'live', latencyMs: Number.POSITIVE_INFINITY }, 2);
    emitJobDiagnostic({ kind: 'stream', mode: 'live', latencyMs: -5 }, 3);
    emitJobDiagnostic({ kind: 'stream', mode: 'live', latencyMs: 700000 }, 4);
    emitJobDiagnostic({ kind: 'status', latencyMs: Number.NEGATIVE_INFINITY }, 5);
    emitJobDiagnostic({ kind: 'stream', mode: 'live', latencyMs: 12.6 }, 6);

    const events = readJobDiagnostics().map((record) => record.event);
    for (const invalid of events.slice(0, 5)) {
      const latency =
        invalid.kind === 'stream' || invalid.kind === 'status' ? invalid.latencyMs : undefined;
      expect(latency).toBeUndefined();
    }
    const rounded = events[5]!;
    expect(rounded.kind === 'stream' ? rounded.latencyMs : null).toBe(13);
  });
});

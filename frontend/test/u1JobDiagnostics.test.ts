import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clearJobDiagnostics,
  emitJobDiagnostic,
  readJobDiagnostics,
  setJobDiagnosticSender,
} from '@/lib/jobDiagnostics';

beforeEach(() => {
  clearJobDiagnostics();
  setJobDiagnosticSender(null);
});

afterEach(() => {
  setJobDiagnosticSender(null);
  clearJobDiagnostics();
});

describe('job diagnostics', () => {
  it('records only allowlisted fields and strips anything injected at runtime', () => {
    emitJobDiagnostic({ kind: 'submit', taskType: 'summarize', outcome: 'sent' }, 111);
    expect(readJobDiagnostics()).toEqual([
      { event: { kind: 'submit', taskType: 'summarize', outcome: 'sent' }, at: 111 },
    ]);

    // Untyped extra fields (content, ids, stacks) never survive sanitization.
    emitJobDiagnostic(
      {
        kind: 'terminal',
        state: 'FAILED',
        content: 'DECODED SECRET',
        jobId: 'job-1',
        stack: 'Error: boom\n  at x',
      } as never,
      222,
    );
    const serialized = JSON.stringify(readJobDiagnostics());
    expect(serialized).not.toContain('DECODED SECRET');
    expect(serialized).not.toContain('job-1');
    expect(serialized).not.toContain('at x');
    expect(readJobDiagnostics()[1]?.event).toEqual({ kind: 'terminal', state: 'FAILED' });
  });

  it('stays bounded — the oldest records drop past the cap', () => {
    for (let i = 0; i < 60; i += 1) {
      emitJobDiagnostic({ kind: 'stream', mode: 'live' }, i);
    }
    const tail = readJobDiagnostics();
    expect(tail).toHaveLength(50);
    expect(tail[0]?.at).toBe(10);
    expect(tail[49]?.at).toBe(59);
  });

  it('delivers sanitized records to an installed sender', () => {
    const sent: unknown[] = [];
    setJobDiagnosticSender((records) => sent.push(...records));
    emitJobDiagnostic({ kind: 'result-read', outcome: 'expired' }, 7);
    expect(sent).toEqual([{ event: { kind: 'result-read', outcome: 'expired' }, at: 7 }]);
  });

  it('a failing sender never breaks the caller and never recurses', () => {
    const failing = vi.fn(() => {
      throw new Error('diagnostic delivery failed');
    });
    setJobDiagnosticSender(failing);

    expect(() => emitJobDiagnostic({ kind: 'stream', mode: 'fallback' }, 1)).not.toThrow();
    expect(failing).toHaveBeenCalledTimes(1);
    expect(readJobDiagnostics()).toHaveLength(1);
  });
});

// F05 — the browser waits the DECLARED budget, not an arbitrary cutoff.
//
// The client used to fall back to a bare 10s for the summarize/translate POST. That is *below* the
// declared API budget (10s) — the browser could abandon a request the API was still intending to
// answer, so a slow-but-successful generation surfaced as a network error with no result and no
// poll handle. These tests pin the declared numbers, the ordering that makes them meaningful, and
// the parity between the client's copy and the platform declaration.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { API_BUDGET_MS, BROWSER_BUDGET_MS, browserBudgetMs, type BudgetTask } from '../lib/api/timeouts';
import { ApiClient } from '../lib/api/apiClient';
import type { Transport, TransportRequest } from '../lib/api/transport';

function transportOf(
  handler: (req: TransportRequest) => Promise<{ status: number; body: unknown }>,
): Transport {
  return { send: handler, abort: () => undefined } as unknown as Transport;
}

/** Parse the two-level int mapping in `ops/platform-integrity/timeouts.yaml`. */
function declaredBudgets(): Record<string, Record<string, number>> {
  const path = join(process.cwd(), '..', 'ops', 'platform-integrity', 'timeouts.yaml');
  const declared: Record<string, Record<string, number>> = {};
  let task: string | undefined;
  for (const raw of readFileSync(path, 'utf8').split('\n')) {
    const line = raw.split('#')[0];
    if (!line.trim()) continue;
    if (!/^\s/.test(line)) {
      task = line.trim().replace(/:$/, '');
      declared[task] = {};
      continue;
    }
    const [key, value] = line.trim().split(':');
    if (!task) throw new Error(`field before a task header: ${raw}`);
    declared[task][key.trim()] = Number(value.trim());
  }
  return declared;
}

describe('declared browser budget (REM-2 F05)', () => {
  it('mirrors the platform declaration exactly', () => {
    // The client copy is only trustworthy while it equals `timeouts.yaml`; the Python side has the
    // same guard, so a retune breaks a test on both sides of the wire rather than drifting.
    const declared = declaredBudgets();
    for (const [task, fields] of Object.entries(declared)) {
      const browserSec = fields.browser_sec;
      const apiSec = fields.api_sec;
      expect(browserSec, task).toBeGreaterThan(0);
      expect(apiSec, task).toBeGreaterThan(0);
      const key = task as BudgetTask;
      if (key in BROWSER_BUDGET_MS) {
        expect(BROWSER_BUDGET_MS[key], `${task} browser`).toBe(browserSec * 1000);
        expect(API_BUDGET_MS[key], `${task} api`).toBe(apiSec * 1000);
      }
    }
  });

  it('never cuts below the layer it wraps', () => {
    for (const task of Object.keys(BROWSER_BUDGET_MS) as BudgetTask[]) {
      expect(BROWSER_BUDGET_MS[task], task).toBeGreaterThan(API_BUDGET_MS[task]);
    }
  });

  it('leaves room for several polls inside the browser budget', () => {
    // A pending response sends the client back after 3s (POLL_BACKOFF_MS, declared server-side).
    // Fewer than three attempts inside the browser budget would make the pending path unusable.
    for (const task of Object.keys(BROWSER_BUDGET_MS) as BudgetTask[]) {
      expect(Math.floor(BROWSER_BUDGET_MS[task] / 3000), task).toBeGreaterThanOrEqual(3);
    }
  });

  it('falls back to the tightest declared budget for an unknown task', () => {
    expect(browserBudgetMs(undefined)).toBe(BROWSER_BUDGET_MS.SUMMARIZE);
    expect(browserBudgetMs('something-new')).toBe(BROWSER_BUDGET_MS.SUMMARIZE);
  });

  it('maps the wire task vocabulary onto the declared budgets', () => {
    expect(browserBudgetMs('summary')).toBe(15_000);
    expect(browserBudgetMs('translate')).toBe(15_000);
    expect(browserBudgetMs('novelty')).toBe(30_000);
    expect(browserBudgetMs('evidence')).toBe(30_000);
  });
});

describe('ApiClient summarize budget', () => {
  const okBody = { status: 'ok', task: 'summary', summary: null, translation: null, meta: {}, cached: false };

  it('sends a summary with the 15s declared browser budget, not the 10s client default', async () => {
    let seen: TransportRequest | undefined;
    const t = transportOf(async (req) => {
      seen = req;
      return { status: 200, body: okBody };
    });
    // A client constructed WITHOUT an explicit timeout is the case that used to fall back to 10s.
    const client = new ApiClient(t, { retryBackoffMs: 1 });
    await client.summarize({ paperId: '2401.1', version: 1, task: 'summary' });
    expect(seen?.timeoutMs).toBe(15_000);
  });

  it('keeps the declared budget even when the client default is larger', async () => {
    let seen: TransportRequest | undefined;
    const t = transportOf(async (req) => {
      seen = req;
      return { status: 200, body: okBody };
    });
    await new ApiClient(t, { timeoutMs: 60_000, retryBackoffMs: 1 }).summarize({
      paperId: '2401.1',
      version: 1,
      task: 'translate',
      targetLang: 'ko',
    });
    expect(seen?.timeoutMs).toBe(15_000);
  });

  it('still refuses to retry a cost-bearing summarize POST', async () => {
    // Aligning the timeout must not have relaxed the no-retry rule (a retry double-bills).
    let calls = 0;
    const t = transportOf(async () => {
      calls += 1;
      return { status: 500, body: null };
    });
    await expect(
      new ApiClient(t, { timeoutMs: 1, retryBackoffMs: 1 }).summarize({
        paperId: '2401.1',
        version: 1,
        task: 'summary',
      }),
    ).rejects.toBeTruthy();
    expect(calls).toBe(1);
  });
});

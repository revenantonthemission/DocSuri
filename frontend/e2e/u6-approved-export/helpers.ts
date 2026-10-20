// U6 browser journey helpers: owned fixtures, failure-only diagnostics, keyboard checks.
import { execFileSync } from 'node:child_process';
import { lstatSync, readFileSync, realpathSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, type Page, type Response, type TestInfo } from '@playwright/test';

const repositoryRoot = fileURLToPath(new URL('../../../', import.meta.url));
const exportRoute = /^\/api\/v2\/c09\/[a-z-]{1,64}$/;
const diagnosticCodes = new Set([
  'APPROVAL_REQUIRED',
  'CAPACITY_EXHAUSTED',
  'CONFLICT',
  'DEADLINE_EXCEEDED',
  'DEPENDENCY_UNAVAILABLE',
  'FORBIDDEN',
  'IDEMPOTENCY_CONFLICT',
  'INTERNAL_ERROR',
  'INVALID_ARGUMENT',
  'INVALID_CONTENT',
  'INVALID_TOKEN',
  'NOT_FOUND',
  'NOT_READY',
  'OUTCOME_UNKNOWN',
  'POLICY_UNRESOLVED',
  'RATE_LIMITED',
  'SOURCE_INELIGIBLE',
  'UNAUTHENTICATED',
  'UNKNOWN_OUTCOME',
]);

type Refusal = { method: string; path: string; status: number; code?: string };

/** Failure-only diagnostics: route, status and a fixed code; never bodies or headers. */
export function captureExportFailures(page: Page) {
  const records: Refusal[] = [];
  const pending: Promise<void>[] = [];
  const record = (response: Response) => {
    const path = new URL(response.url()).pathname;
    if (records.length >= 16 || response.status() < 400 || !exportRoute.test(path)) return;
    const item: Refusal = { method: response.request().method(), path, status: response.status() };
    records.push(item);
    pending.push(
      (async () => {
        try {
          const bytes = await response.body();
          if (bytes.length > 4096) return;
          const value: unknown = JSON.parse(bytes.toString('utf8'));
          if (typeof value !== 'object' || value === null) return;
          const code = (value as Record<string, unknown>).code;
          if (typeof code === 'string' && diagnosticCodes.has(code)) item.code = code;
        } catch {
          /* An unreadable envelope keeps only its route and status. */
        }
      })(),
    );
  };
  page.on('response', record);
  return async (info: TestInfo) => {
    page.off('response', record);
    if (info.status === info.expectedStatus) return;
    await Promise.allSettled(pending);
    if (records.length)
      await info.attach('c09-failure-metadata', {
        body: Buffer.from(JSON.stringify(records)),
        contentType: 'application/json',
      });
  };
}

export type Account = { email: string; password: string; accountId: string };
export type SpecNames = { cancel: string; settle: string };
export type Fixtures = {
  runId: string;
  accounts: { memberA: Account; memberB: Account };
  notionToken: string;
  novelty: { jobId: string; contextId: string };
  scenario: {
    practicePage: string;
    sameTitle: string;
    specs: Record<'journeys' | 'keyboard' | 'accessibility', SpecNames>;
  };
};

/** The run-bound fixture record, read only through its strict custody checks. */
export function fixtures(): Fixtures {
  const directory = realpathSync('/tmp/docsuri-u6-run');
  const path = join(directory, 'browser-fixtures.json'),
    info = lstatSync(path);
  if (
    !info.isFile() ||
    info.isSymbolicLink() ||
    info.uid !== process.getuid?.() ||
    info.mode & 0o077 ||
    info.nlink !== 1 ||
    info.size > 65_536
  )
    throw new Error('U6 private fixture boundary refused');
  const value = JSON.parse(readFileSync(path, 'utf8'));
  const environment = JSON.parse(readFileSync(join(directory, 'environment.json'), 'utf8'));
  const accountsReady = ['memberA', 'memberB'].every((key) => {
    const account = value.accounts?.[key];
    return (
      account &&
      ['email', 'password', 'accountId'].every(
        (field) => typeof account[field] === 'string' && account[field].length > 0,
      )
    );
  });
  if (
    value.runId !== environment.runId ||
    value.fixtureVersion !== 'u6-browser-v1' ||
    value.state !== 'ready' ||
    !accountsReady ||
    !/^u6-synthetic-[0-9a-f]{40}$/.test(value.notionToken) ||
    typeof value.novelty?.jobId !== 'string' ||
    typeof value.novelty?.contextId !== 'string' ||
    typeof value.scenario?.practicePage !== 'string'
  )
    throw new Error('U6 fixture identity or readiness mismatch');
  return value as Fixtures;
}

export async function login(page: Page, account: Account) {
  await page.goto('/');
  await page.getByLabel('이메일', { exact: true }).fill(account.email);
  await page.getByLabel('비밀번호', { exact: true }).fill(account.password);
  await page.getByTestId('entry-submit').click();
  await expect(page.getByTestId('logout')).toBeVisible();
}

/** Signs out and waits until the sign-in form is back, so nothing aborts the logout. */
export async function logout(page: Page) {
  await page.getByTestId('logout').click();
  await expect(page.getByLabel('이메일', { exact: true })).toBeVisible();
}

/** The export view, once both of its reads have settled. */
export async function openExportView(page: Page) {
  await page.getByTestId('nav-export').click();
  await expect(page.getByTestId('export-heading')).toBeVisible();
  await expect(page.getByTestId('export-view')).not.toHaveAttribute('data-view-state', 'loading');
}

export async function expectConnected(page: Page) {
  await expect(page.getByTestId('connection-state')).toContainText('연결됨');
  await expect(page.getByTestId('connection-workspace')).toContainText('DocSuri 합성 워크스페이스');
}

/** Leaves the owner without a usable connection, confirming through the dialog. */
export async function ensureDisconnected(page: Page) {
  const disconnect = page.getByTestId('connection-disconnect');
  if (!(await disconnect.isVisible())) return;
  await disconnect.click();
  await page.getByTestId('disconnect-confirm').click();
  await expect(page.getByTestId('connection-notice')).toHaveText('Notion 연결을 해제했습니다');
}

export async function connectNotion(page: Page, token: string) {
  await page.getByTestId('connect-token').fill(token);
  await page.getByTestId('connect-submit').click();
  await expectConnected(page);
  await expect(page.getByTestId('connect-token')).toHaveCount(0);
}

/** Connected at the start of a spec, whatever an earlier spec left. */
export async function ensureConnected(page: Page, token: string) {
  await openExportView(page);
  if (await page.getByTestId('connection-disconnect').isVisible()) return;
  await connectNotion(page, token);
}

export function noveltyLink(novelty: Fixtures['novelty']): string {
  const query = new URLSearchParams({
    jobId: novelty.jobId,
    kind: 'novelty-analysis',
    contextId: novelty.contextId,
  });
  return `/#research-job?${query}`;
}

/** The fixture's ready novelty result, opened through U4's own recovery link. */
export async function openNoveltyResult(page: Page, novelty: Fixtures['novelty']) {
  await gotoNoveltyLink(page, novelty);
  await page.getByRole('button', { name: '준비된 결과 열기' }).click();
  await expect(page.getByTestId('novelty-export-open')).toBeVisible();
}

/** A fresh document, then the recovery link, so a repeated visit reopens the job. */
export async function gotoNoveltyLink(page: Page, novelty: Fixtures['novelty']) {
  await page.goto('/');
  await expect(page.getByTestId('logout')).toBeVisible();
  await page.goto(noveltyLink(novelty));
}

/** One listed destination by its exact title (a child page's location names its parent). */
export function destinationOption(page: Page, title: string) {
  return page
    .getByTestId('destination-option')
    .filter({ has: page.locator('.export-destination-title').getByText(title, { exact: true }) });
}

export function historyRow(page: Page, title: string) {
  return page.getByTestId('history-row').filter({ hasText: title });
}

/** The current flow step, as the indicator exposes it (never by color). */
export async function expectStep(page: Page, step: 'destination' | 'preview' | 'outcome') {
  await expect(page.getByTestId(`flow-step-${step}`)).toHaveAttribute('aria-current', 'step');
}

/** One fixture-clock hour forward, through the parent's delegated capability. */
export function advanceExportClock() {
  execFileSync(
    join(repositoryRoot, 'backend/.venv/bin/python'),
    [
      join(repositoryRoot, 'scripts/u6_browser_fixtures.py'),
      '--environment-file',
      '/tmp/docsuri-u6-run/environment.json',
      '--action',
      'advance-clock',
    ],
    { cwd: repositoryRoot, timeout: 15_000, stdio: 'pipe' },
  );
}

/** Re-opens the export view until the unclear export's row offers settlement. */
export async function waitForSettlement(page: Page, title: string, reopen: () => Promise<void>) {
  await expect
    .poll(
      async () => {
        await reopen();
        return historyRow(page, title).getByTestId('history-settle').isVisible();
      },
      { timeout: 30_000, intervals: [1_000, 2_000] },
    )
    .toBe(true);
}

export async function reopenExportView(page: Page) {
  await page.getByTestId('nav-novelty').click();
  await openExportView(page);
}

type Focused = { testId: string | null; context: string; title: string; inDialog: boolean };

/** What has keyboard focus: its test id, its row's text and title, and whether it is in
a dialog. */
export function focused(page: Page): Promise<Focused> {
  return page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    const row = element?.closest('li') ?? element;
    return {
      testId: element?.getAttribute('data-testid') ?? null,
      context: row?.textContent ?? '',
      title: row?.querySelector('.export-destination-title')?.textContent ?? '',
      inDialog: !!element?.closest('[role="dialog"]'),
    };
  });
}

/** WCAG 2.4.7 and 2.4.11: the focused control shows an indicator and is not covered. */
export async function expectFocusVisibleAndUnobscured(page: Page) {
  const state = await page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    if (!element || element === document.body) return { indicator: false, unobscured: false };
    const style = window.getComputedStyle(element);
    const indicator =
      (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0) ||
      style.boxShadow !== 'none';
    const box = element.getBoundingClientRect();
    const x = Math.min(Math.max(box.left + box.width / 2, 0), window.innerWidth - 1);
    const y = Math.min(Math.max(box.top + box.height / 2, 0), window.innerHeight - 1);
    const hit = document.elementFromPoint(x, y);
    const inView = box.bottom > 0 && box.top < window.innerHeight && box.right > 0;
    const unobscured =
      inView && !!hit && (hit === element || element.contains(hit) || hit.contains(element));
    return { indicator, unobscured };
  });
  expect(state, 'focused control shows a focus indicator and is not obscured').toEqual({
    indicator: true,
    unobscured: true,
  });
}

/** Moves focus with Tab (or Shift+Tab) until the wanted control has it (WCAG 2.1.1). */
export async function tabTo(
  page: Page,
  testId: string,
  options: { context?: string; backward?: boolean; limit?: number } = {},
) {
  const key = options.backward ? 'Shift+Tab' : 'Tab';
  for (let step = 0; step < (options.limit ?? 120); step += 1) {
    const current = await focused(page);
    if (
      current.testId === testId &&
      (!options.context || current.context.includes(options.context))
    ) {
      await expectFocusVisibleAndUnobscured(page);
      return;
    }
    await page.keyboard.press(key);
  }
  throw new Error(`keyboard focus never reached ${testId}`);
}

/** Selects one destination with the arrow keys inside the radio group. */
export async function arrowToDestination(page: Page, title: string) {
  await tabTo(page, 'destination-radio', { backward: true });
  for (let step = 0; step < 30; step += 1) {
    const current = await focused(page);
    if (current.testId === 'destination-radio' && current.title === title) {
      await expect(destinationOption(page, title).getByTestId('destination-radio')).toBeChecked();
      await expectFocusVisibleAndUnobscured(page);
      return;
    }
    await page.keyboard.press('ArrowDown');
  }
  throw new Error('arrow keys never reached the destination');
}

/** Tab and Shift+Tab stay inside an open dialog (focus trap). */
export async function expectFocusTrapped(page: Page, presses = 6) {
  for (const key of ['Tab', 'Shift+Tab']) {
    for (let step = 0; step < presses; step += 1) {
      await page.keyboard.press(key);
      expect((await focused(page)).inDialog, `${key} keeps focus inside the dialog`).toBe(true);
    }
  }
}

export async function scrub(page: Page) {
  // Keep a failure's synthetic private inputs out of automatic DOM diagnostics.
  await page
    .evaluate(() => {
      document.querySelectorAll('input,textarea').forEach((element) => {
        (element as HTMLInputElement).value = '';
      });
    })
    .catch(() => undefined);
}

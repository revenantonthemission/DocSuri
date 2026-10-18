// U5 browser journey helpers; owned fixtures and failure-only diagnostics.
import { lstatSync, readFileSync, realpathSync } from 'node:fs';
import { join } from 'node:path';
import { expect, type Page, type Response, type TestInfo } from '@playwright/test';

const topicRoutes = /^\/api\/v2\/topics/;
const diagnosticCodes = new Set([
  'CONFLICT',
  'DEADLINE_EXCEEDED',
  'DEPENDENCY_UNAVAILABLE',
  'FORBIDDEN',
  'INTERNAL_ERROR',
  'INVALID_ARGUMENT',
  'NOT_FOUND',
  'NOT_READY',
  'POLICY_UNRESOLVED',
  'QUOTA_EXCEEDED',
  'RATE_LIMITED',
  'STALE_REVISION',
  'UNAUTHENTICATED',
  'UNKNOWN_OUTCOME',
]);

/** Failure-only diagnostics deliberately exclude inputs, identity and headers. */
export function captureTopicsFailures(page: Page) {
  const records: { method: string; path: string; status: number; code?: string }[] = [];
  const record = (response: Response) => {
    const path = new URL(response.url()).pathname;
    if (
      records.length >= 16 ||
      response.status() < 400 ||
      !topicRoutes.test(path)
    )
      return;
    const item: (typeof records)[number] = {
      method: response.request().method(),
      path,
      status: response.status(),
    };
    records.push(item);
    void response
      .body()
      .then((bytes) => {
        if (bytes.length > 4096) return;
        const value: unknown = JSON.parse(bytes.toString('utf8'));
        if (typeof value !== 'object' || value === null) return;
        const code = (value as Record<string, unknown>).code;
        if (typeof code === 'string' && diagnosticCodes.has(code)) item.code = code;
      })
      .catch(() => undefined);
  };
  page.on('response', record);
  return async (info: TestInfo) => {
    page.off('response', record);
    if (records.length > 0)
      info.annotations.push({ type: 'refusals', description: JSON.stringify(records) });
  };
}

export type Account = { email: string; password: string; accountId: string };
export function fixtures(): { runId: string; accounts: { memberA: Account; memberB: Account } } {
  const directory = realpathSync('/tmp/docsuri-u5-run');
  const path = join(directory, 'browser-fixtures.json'),
    info = lstatSync(path);
  if (
    !info.isFile() ||
    info.isSymbolicLink() ||
    info.uid !== process.getuid?.() ||
    info.mode & 0o077 ||
    info.size > 65_536
  )
    throw new Error('U5 private fixture boundary refused');
  const value = JSON.parse(readFileSync(path, 'utf8'));
  const environment = JSON.parse(readFileSync(join(directory, 'environment.json'), 'utf8'));
  if (
    value.runId !== environment.runId ||
    value.fixtureVersion !== 'u5-browser-v1' ||
    value.state !== 'ready' ||
    !['memberA', 'memberB'].every((key) => {
      const account = value.accounts?.[key];
      return (
        account &&
        ['email', 'password', 'accountId'].every(
          (field) => typeof account[field] === 'string' && account[field].length > 0,
        )
      );
    })
  )
    throw new Error('U5 fixture identity or readiness mismatch');
  return value;
}

export async function login(page: Page, account: Account) {
  await page.goto('/');
  await page.getByLabel('이메일', { exact: true }).fill(account.email);
  await page.getByLabel('비밀번호', { exact: true }).fill(account.password);
  await page.getByTestId('entry-submit').click();
  await expect(page.getByTestId('logout')).toBeVisible();
}

export async function openTopics(page: Page) {
  await page.getByTestId('nav-topics').click();
  await expect(page.getByTestId('topics-heading')).toBeVisible();
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

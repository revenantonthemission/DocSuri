import { lstatSync, readFileSync, realpathSync } from 'node:fs';
import { join } from 'node:path';
import { expect, type Page, type Response, type TestInfo } from '@playwright/test';

const diagnosticOperations = new Set([
  'create-research-context',
  'create-research-session',
  'read-research-session',
  'list-research-sessions',
  'delete-research-sessions',
  'accept-research-turn',
  'read-research-turn',
  'accept-novelty-analysis',
  'accept-novelty-discussion',
  'read-research-job',
  'cancel-novelty-analysis',
  'read-research-artifact',
  'save-draft',
  'restore-draft',
  'discard-draft',
  'begin-private-attachment',
  'finish-private-attachment',
  'read-private-attachment',
  'read-private-asset',
]);
const diagnosticCodes = new Set([
  'APPROVAL_REQUIRED',
  'CONFLICT',
  'DEADLINE_EXCEEDED',
  'DEPENDENCY_UNAVAILABLE',
  'FORBIDDEN',
  'IDEMPOTENCY_CONFLICT',
  'INTERNAL_ERROR',
  'INVALID_ARGUMENT',
  'INVALID_CONTENT',
  'NOT_FOUND',
  'NOT_READY',
  'POLICY_UNRESOLVED',
  'QUOTA_EXCEEDED',
  'RATE_LIMITED',
  'SNAPSHOT_EXPIRED',
  'SOURCE_INELIGIBLE',
  'STALE_REVISION',
  'UNAUTHENTICATED',
  'UNKNOWN_OUTCOME',
]);

/** Failure-only diagnostics deliberately exclude inputs, payloads, identity and headers. */
export function captureResearchFailures(page: Page) {
  const records: {
    method: 'POST';
    path: string;
    status: number;
    code?: string;
    requestId?: string;
  }[] = [];
  const pending: Promise<void>[] = [];
  const record = (response: Response) => {
    const path = new URL(response.url()).pathname;
    const operation = path.replace('/api/v2/c07/', '');
    if (
      records.length >= 16 ||
      response.status() < 400 ||
      response.request().method() !== 'POST' ||
      path !== `/api/v2/c07/${operation}` ||
      !diagnosticOperations.has(operation)
    )
      return;
    const item: (typeof records)[number] = { method: 'POST', path, status: response.status() };
    records.push(item);
    pending.push(
      (async () => {
        try {
          const bytes = await response.body();
          if (bytes.length > 4096) return;
          const value: unknown = JSON.parse(bytes.toString('utf8'));
          if (typeof value !== 'object' || value === null) return;
          const envelope = value as Record<string, unknown>;
          if (typeof envelope.code === 'string' && diagnosticCodes.has(envelope.code))
            item.code = envelope.code;
          if (
            typeof envelope.requestId === 'string' &&
            /^[a-f0-9-]{8,64}$/i.test(envelope.requestId)
          )
            item.requestId = envelope.requestId;
        } catch {
          /* Unreadable failure envelopes retain only route and status. */
        }
      })(),
    );
  };
  page.on('response', record);
  return async (info: TestInfo) => {
    page.off('response', record);
    if (info.status === info.expectedStatus) return;
    let deadline: ReturnType<typeof setTimeout> | undefined;
    await Promise.race([
      Promise.allSettled(pending),
      new Promise<void>((resolve) => {
        deadline = setTimeout(resolve, 1000);
      }),
    ]);
    clearTimeout(deadline);
    if (records.length)
      await info.attach('c07-failure-metadata', {
        body: Buffer.from(JSON.stringify(records)),
        contentType: 'application/json',
      });
  };
}

export type Account = { email: string; password: string; accountId: string };
export function fixtures(): { runId: string; accounts: { memberA: Account; memberB: Account } } {
  const directory = realpathSync('/tmp/docsuri-u4-run');
  const path = join(directory, 'browser-fixtures.json'),
    info = lstatSync(path);
  if (
    !info.isFile() ||
    info.isSymbolicLink() ||
    info.uid !== process.getuid?.() ||
    info.mode & 0o077 ||
    info.size > 65_536
  )
    throw new Error('U4 private fixture boundary refused');
  const value = JSON.parse(readFileSync(path, 'utf8'));
  const environment = JSON.parse(readFileSync(join(directory, 'environment.json'), 'utf8'));
  if (
    value.runId !== environment.runId ||
    value.fixtureVersion !== 'u4-browser-v1' ||
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
    throw new Error('U4 fixture identity or readiness mismatch');
  return value;
}
export async function login(page: Page, account: Account) {
  await page.goto('/');
  await page.getByLabel('이메일', { exact: true }).fill(account.email);
  await page.getByLabel('비밀번호', { exact: true }).fill(account.password);
  await page.getByTestId('entry-submit').click();
  await expect(page.getByTestId('logout')).toBeVisible();
}
export async function openResearch(page: Page) {
  await page.getByTestId('nav-research').click();
  await expect(page.getByTestId('workspace-research')).toBeVisible();
}
export async function createSession(page: Page, title: string) {
  await page.getByLabel('새 연구 이름').fill(title);
  await page.getByRole('button', { name: '새 연구 시작', exact: true }).click();
  await expect(page.getByLabel('연구 질문', { exact: true })).toBeVisible();
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

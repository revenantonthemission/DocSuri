/** Owned synthetic browser fixtures. Secret files never become test attachments. */
import { execFileSync } from 'node:child_process';
import { lstatSync, readFileSync, realpathSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHmac, randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { expect, Page } from '@playwright/test';
// Independent of the invoking working directory (runner runs from the root).
const root = fileURLToPath(new URL('../../..', import.meta.url));
const directory = realpathSync('/tmp/docsuri-u2-run');
export const policy = { policyId: 'u2-synthetic-v1', revision: '1' };
export type Account = { email: string; password: string; accountId: string; seed?: string };
export type Fixture = {
  accounts: Record<'memberA' | 'memberB' | 'admin' | 'lifecycle' | 'registration', Account>;
};
function privateJson(file: string) {
  const path = resolve(directory, file);
  const info = lstatSync(path);
  if (
    !info.isFile() ||
    info.isSymbolicLink() ||
    info.mode & 0o077 ||
    info.uid !== process.getuid?.() ||
    info.size > 65_536
  )
    throw new Error('private fixture boundary refused');
  return JSON.parse(readFileSync(path, 'utf8'));
}
export function helper(action: 'setup' | 'proof' | 'totp', alias?: string, purpose?: string) {
  const args = [
    resolve(root, 'scripts/u2_browser_fixtures.py'),
    '--environment-file',
    resolve(directory, 'environment.json'),
    '--action',
    action,
    ...(alias ? ['--alias', alias] : []),
    ...(purpose ? ['--purpose', purpose] : []),
  ];
  execFileSync(resolve(root, 'backend/.venv/bin/python'), args, {
    cwd: root,
    timeout: 30_000,
    maxBuffer: 4096,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return privateJson(action === 'setup' ? 'browser-fixtures.json' : 'browser-proof.json');
}
export const fixtures = (): Fixture => privateJson('browser-fixtures.json');
export async function login(page: Page, account: Account, admin = false) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      await page.goto('/');
      await page.getByLabel('이메일', { exact: true }).waitFor({ state: 'attached', timeout: 20_000 });
      await page.getByLabel('이메일', { exact: true }).fill(account.email);
      await page.getByLabel('비밀번호', { exact: true }).fill(account.password);
      await page.getByTestId('entry-submit').click();
      if (admin) {
        await page.getByLabel('인증 앱 코드').waitFor({ timeout: 10_000 });
        const value = helper('totp', 'admin');
        await page.getByLabel('인증 앱 코드').fill(value.proof);
        await page.getByTestId('entry-submit').click();
      }
      // The finite entry-admission bucket refills on the minute boundary; a
      // journey suite may legitimately consume it, so retry once within the
      // same bounded window instead of weakening the product limit.
      await page.getByTestId('logout').waitFor({ state: 'visible', timeout: 10_000 });
      return;
    } catch (failure) {
      // Bounded, secret-free diagnostics: no body text, credentials or codes.
      const diagnostics = await Promise.race([
        page
          .context()
          .cookies()
          .then((cookies) => ({ url: page.url(), cookies: cookies.map((cookie) => cookie.name) })),
        new Promise((resolve) => setTimeout(() => resolve('diagnostics-timeout'), 3000)),
      ]).catch(() => 'diagnostics-failed');
      if (attempt === 1) throw failure;
      // Retry after the next minute boundary, when the finite entry-admission
      // bucket refills; the wait is bounded by one minute window.
      const wait = Math.max(2_000, 61_000 - (Date.now() % 60_000));
      console.log(`login-retry ${JSON.stringify(diagnostics)}`);
      await page.waitForTimeout(wait);
    }
  }
}
export async function post(page: Page, path: string, body: unknown, key = randomUUID()) {
  return page.evaluate(
    async ({ path, body, key }) => {
      const bootstrap = await fetch('/api/v2/session').then((r) => r.json());
      const response = await fetch(path, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': bootstrap.csrfToken,
          'Idempotency-Key': key,
        },
        body: JSON.stringify(body),
      });
      return { status: response.status, value: await response.json() };
    },
    { path, body, key },
  );
}
export async function openControls(page: Page, view: 'account' | 'settings' | 'usage' | 'library') {
  await page.getByTestId(`nav-${view}`).click();
}
export async function verifyLink(page: Page, alias: string, purpose: string) {
  const proof = helper('proof', alias, purpose);
  const action = purpose === 'verify' ? 'verify-email' : purpose;
  // A protected delivered link is consumed transiently and immediately stripped by the app.
  await page.goto(
    '/?' +
      new URLSearchParams({
        action,
        challengeId: proof.challengeId,
        flowBinding: proof.flowBinding,
        proof: proof.proof,
      }),
  );
}
export function totp(seed: string, offset = 0) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const char of seed.replace(/=/g, '').toUpperCase()) {
    const digit = alphabet.indexOf(char);
    if (digit < 0) throw new Error('invalid fixture factor');
    bits += digit.toString(2).padStart(5, '0');
  }
  const key = Buffer.from((bits.match(/.{8}/g) ?? []).map((chunk) => parseInt(chunk, 2)));
  const tick = Buffer.alloc(8);
  tick.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30_000) + offset));
  const digest = createHmac('sha1', key).update(tick).digest();
  const index = digest[digest.length - 1]! & 15;
  return ((digest.readUInt32BE(index) & 0x7fffffff) % 1_000_000).toString().padStart(6, '0');
}
export async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
    ),
  ).toBe(true);
}

/** Scrub transient protected material before the runner creates failure context. */
export async function clearProtectedContext(page: Page) {
  await page
    .evaluate(() => {
      document.querySelectorAll('.protected-material').forEach((node) => node.remove());
      document
        .querySelectorAll<HTMLInputElement>(
          'input[type="password"], input[autocomplete="one-time-code"]',
        )
        .forEach((input) => {
          input.value = '';
          input.removeAttribute('value');
        });
      history.replaceState(null, '', location.pathname);
    })
    .catch(() => undefined);
}

export async function saveFixturePaper(page: Page) {
  await page.getByTestId('nav-search').click();
  await page.getByTestId('search-query').fill('Attention');
  await page.getByTestId('search-submit').click();
  const result = page.getByTestId('result-item').first();
  await expect(result).toBeVisible();
  await result.getByRole('button').click();
  await expect(page.getByTestId('reading-surface')).toBeVisible();
  if (await page.getByTestId('save-paper').isVisible())
    await page.getByTestId('save-paper').click();
  await expect(page.getByTestId('remove-paper')).toBeVisible();
}

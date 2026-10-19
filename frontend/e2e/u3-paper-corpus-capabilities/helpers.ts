/** Owned U3 browser fixtures over the mounted synthetic host. */
import { execFileSync } from 'node:child_process';
import { lstatSync, readFileSync, realpathSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, Page } from '@playwright/test';

const root = fileURLToPath(new URL('../../..', import.meta.url));
const directory = realpathSync('/tmp/docsuri-u3-run');

export type Account = { email: string; password: string; accountId: string };
export type Fixture = { runId: string; accounts: Record<'memberA' | 'memberB' | 'admin', Account> };

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

export function helper(
  // Mirrors ACTIONS in scripts/u3_browser_fixtures.py.
  action:
    | 'setup'
    | 'publish'
    | 'reset-corpus'
    | 'withdraw'
    | 'restore-eligible'
    | 'expire'
    | 'reset-jobs',
  paper?: string,
) {
  const args = [
    resolve(root, 'scripts/u3_browser_fixtures.py'),
    '--environment-file',
    resolve(directory, 'environment.json'),
    '--action',
    action,
    ...(paper ? ['--paper', paper] : []),
  ];
  execFileSync(resolve(root, 'backend/.venv/bin/python'), args, {
    cwd: root,
    timeout: 60_000,
    maxBuffer: 4096,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return action === 'setup' ? fixtures() : null;
}

export const fixtures = (): Fixture => privateJson('browser-fixtures.json');

export async function login(page: Page, account: Account) {
  await page.goto('/');
  await page.getByLabel('이메일', { exact: true }).waitFor({ state: 'attached', timeout: 20_000 });
  await page.getByLabel('이메일', { exact: true }).fill(account.email);
  await page.getByLabel('비밀번호', { exact: true }).fill(account.password);
  await page.getByTestId('entry-submit').click();
  await page.getByTestId('logout').waitFor({ state: 'visible', timeout: 15_000 });
}

export async function logout(page: Page) {
  await page.getByTestId('logout').click();
  await page.getByLabel('이메일', { exact: true }).waitFor({ state: 'attached', timeout: 15_000 });
}

export async function search(page: Page, query: string, mode: 'lexical' | 'semantic' = 'lexical') {
  await page.getByTestId('search-query').fill(query);
  await page.getByTestId('search-mode').selectOption(mode);
  await page.getByTestId('search-submit').click();
}

export async function openFirstResult(page: Page) {
  await page.getByTestId('result-row').first().locator('button').click();
  await expect(page.getByTestId('reading-surface').or(page.getByTestId('content-state'))).toBeVisible();
}

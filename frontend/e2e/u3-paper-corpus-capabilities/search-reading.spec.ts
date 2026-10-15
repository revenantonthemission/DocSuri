/** U3 journeys: search, refine, reopen; withdrawn and degraded content states. */
import { test, expect } from '@playwright/test';
import { helper, login, fixtures, openFirstResult, search } from './helpers';

test.describe.configure({ mode: 'serial' });

test.beforeAll(() => {
  helper('setup');
  helper('reset-corpus');
  helper('publish');
});

test('search finds a published fixture and opens its readable content', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await search(page, 'paper-alpha');
  await expect(page.getByTestId('result-row').first()).toBeVisible();
  await expect(page.getByTestId('result-availability').first()).toHaveText('readable');
  await openFirstResult(page);
  await expect(page.getByTestId('reading-surface')).toBeVisible();
  await expect(page.getByTestId('section-anchor').first()).toBeVisible();
});

test('refinement keeps the query and reopening returns the same version', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await search(page, 'paper-gamma');
  await expect(page.getByTestId('result-row').first()).toBeVisible();
  await openFirstResult(page);
  const identity = await page.getByTestId('paper-identity').textContent();
  await page.getByTestId('reading-back').click();
  await expect(page.getByTestId('search-query')).toHaveValue('paper-gamma');
  await openFirstResult(page);
  await expect(page.getByTestId('paper-identity')).toHaveText(identity ?? '');
});

test('a semantic request discloses the lexical fallback through the shell', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await search(page, 'paper-alpha', 'semantic');
  await expect(page.getByTestId('search-results')).toBeVisible();
  await expect(page.getByTestId('snapshot-notice')).toContainText('의미 검색');
});

test('withdrawn content shows its explicit state instead of text', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await search(page, 'paper-gamma');
  await openFirstResult(page);
  await expect(page.getByTestId('reading-surface')).toBeVisible();
  helper('withdraw', 'paper-gamma');
  await page.getByTestId('reading-back').click();
  await openFirstResult(page);
  await expect(page.getByTestId('content-state')).toContainText('게시가 중단된 자료예요');
});

/** U3 journeys: accepted assistance through progress, reconnect and results. */
import { test, expect } from '@playwright/test';
import { helper, login, fixtures, openFirstResult, search } from './helpers';

test.describe.configure({ mode: 'serial' });

test.beforeAll(() => {
  helper('setup');
  helper('reset-corpus');
  helper('reset-jobs');
  helper('publish');
});

test('accepting a summary reaches ordered progress and a prepared result', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await search(page, 'paper-alpha');
  await openFirstResult(page);
  await expect(page.getByTestId('reading-surface')).toBeVisible();
  await expect(page.getByTestId('assistance-options')).toBeVisible();
  await page.getByTestId('start-summary').click();
  await expect(page.getByTestId('activity-card')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId('prepared-result')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId('prepared-result')).toContainText('합성', { timeout: 10_000 });
});

test('a reload mid-flight recovers the same authoritative job state', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await search(page, 'paper-alpha');
  await openFirstResult(page);
  await page.getByTestId('start-summary').click();
  await expect(page.getByTestId('activity-card')).toBeVisible({ timeout: 20_000 });
  await page.reload();
  // The session survives the reload; the retained job state is read again.
  await search(page, 'paper-alpha');
  await openFirstResult(page);
  await expect(
    page.getByTestId('prepared-result').or(page.getByTestId('activity-card')),
  ).toBeVisible({ timeout: 60_000 });
});

test('an expired result explains that requesting again is explicit', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await search(page, 'paper-gamma');
  await openFirstResult(page);
  await expect(page.getByTestId('assistance-options')).toBeVisible();
  await page.getByTestId('start-summary').click();
  await expect(page.getByTestId('prepared-result')).toBeVisible({ timeout: 60_000 });
  helper('expire', 'paper-gamma');
  await page.reload();
  // The session survives the reload; the retained result now reads expired.
  await search(page, 'paper-gamma');
  await openFirstResult(page);
  await expect(page.getByTestId('result-expired')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('result-expired')).toContainText('보관 기간이 지난 결과예요');
});

test('assistance stays unavailable to guests', async ({ page }) => {
  await page.goto('/');
  await search(page, 'paper-alpha');
  await openFirstResult(page);
  // Reading is session-required, so a guest never binds content and the
  // assistance surface (options, progress, results) is not reachable at all.
  await expect(page.getByTestId('content-state')).toContainText('로그인하면 본문을 볼 수 있어요');
  await expect(page.getByTestId('assistance-panel')).toHaveCount(0);
  await expect(page.getByTestId('start-summary')).toHaveCount(0);
});

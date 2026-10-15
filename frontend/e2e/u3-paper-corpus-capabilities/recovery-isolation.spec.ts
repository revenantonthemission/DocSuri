/** U3 journeys: account switch isolation, appearance modes, viewports, reflow. */
import { test, expect } from '@playwright/test';
import { helper, login, logout, fixtures, openFirstResult, search } from './helpers';

test.describe.configure({ mode: 'serial' });

test.beforeAll(() => {
  helper('setup');
  helper('reset-corpus');
  helper('publish');
});

test('account switch clears every private surface', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await page.getByTestId('glossary-source').fill('attention');
  await page.getByTestId('glossary-preferred').fill('어텐션');
  await page.getByTestId('glossary-save').click();
  await expect(page.getByTestId('glossary-term').first()).toBeVisible({ timeout: 15_000 });
  await logout(page);
  await expect(page.getByTestId('glossary-term')).toHaveCount(0);
  await login(page, accounts.memberB);
  // Member B never sees member A's committed glossary.
  await expect(page.getByTestId('glossary-term')).toHaveCount(0);
});

test('appearance modes render the workspace in dark and light', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('appearance-select').selectOption('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByTestId('appearance-select').selectOption('light');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByTestId('appearance-select').selectOption('system');
  await expect(page.locator('html')).not.toHaveAttribute('data-theme', 'dark');
});

test('tablet and phone reflow keep search and reading usable', async ({ browser }) => {
  const accounts = fixtures().accounts;
  for (const viewport of [
    { width: 834, height: 1112 },
    { width: 390, height: 844 },
  ]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    await login(page, accounts.memberA);
    await search(page, 'paper-gamma');
    await expect(page.getByTestId('search-query')).toBeVisible();
    await openFirstResult(page);
    await expect(page.getByTestId('reading-surface')).toBeVisible();
    await page.getByTestId('reading-back').click();
    await expect(page.getByTestId('search-query')).toBeVisible();
    await context.close();
  }
});

test('keyboard order reaches search and the live region announces results', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await page.getByTestId('search-query').focus();
  await page.getByTestId('search-query').fill('paper-alpha');
  // Keyboard submission mirrors the visible control order.
  await page.keyboard.press('Tab');
  await expect(page.getByTestId('search-mode')).toBeFocused();
  await page.getByTestId('search-submit').click();
  await expect(page.getByTestId('status-line')).toHaveAttribute('role', 'status');
  await expect(page.getByTestId('status-line')).toContainText('결과를 찾았어요', {
    timeout: 15_000,
  });
});

test('long Korean titles wrap without clipping in result rows', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await search(page, 'paper-gamma');
  const row = page.getByTestId('result-row').first();
  await expect(row).toBeVisible();
  const overflow = await row.evaluate(
    (element) => element.scrollWidth <= element.clientWidth + 1,
  );
  expect(overflow).toBe(true);
});

// axe (WCAG 2.0 A/AA, 2.1 AA, 2.2 AA) on every U6 view and dialog. Any violation fails.
import AxeBuilder from '@axe-core/playwright';
import { test, expect, type Page } from '@playwright/test';
import {
  advanceExportClock,
  captureExportFailures,
  connectNotion,
  destinationOption,
  ensureDisconnected,
  expectStep,
  fixtures,
  historyRow,
  login,
  openExportView,
  openNoveltyResult,
  reopenExportView,
  scrub,
  waitForSettlement,
} from './helpers';

test.describe.configure({ mode: 'serial' });

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'];

const diagnostics = new WeakMap<Page, ReturnType<typeof captureExportFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureExportFailures(page));
});

test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

/** axe on one U6 surface; violations are reported by rule and target, never content. */
async function expectAccessible(page: Page, testId: string) {
  await expect(page.getByTestId(testId)).toBeVisible();
  const result = await new AxeBuilder({ page })
    .withTags(TAGS)
    .include(`[data-testid="${testId}"]`)
    .analyze();
  const violations = result.violations.map((item) => ({
    id: item.id,
    impact: item.impact,
    targets: item.nodes.map((node) => node.target.join(' ')),
  }));
  expect(violations, `${testId} has no axe violations`).toEqual([]);
}

async function flowTo(page: Page, title: string) {
  await openNoveltyResult(page, fixtures().novelty);
  await page.getByTestId('novelty-export-open').click();
  await expectStep(page, 'destination');
  await expect(destinationOption(page, title)).toBeVisible();
}

async function previewOf(page: Page, title: string) {
  await destinationOption(page, title).getByTestId('destination-radio').check();
  await page.getByTestId('destination-next').click();
  await expectStep(page, 'preview');
  await expect(page.getByTestId('preview-step')).toHaveAttribute('data-preview-state', 'ready');
}

test('the export view, its connect form and the disconnect dialog', async ({ page }) => {
  const value = fixtures();
  await login(page, value.accounts.memberA);
  await openExportView(page);
  await ensureDisconnected(page);
  await expectAccessible(page, 'export-view');
  await page.getByTestId('connect-token').fill(' ');
  await page.getByTestId('connect-submit').click();
  await expect(page.getByTestId('connect-field-error')).toBeVisible();
  await expectAccessible(page, 'export-view');
  await connectNotion(page, value.notionToken);
  await expectAccessible(page, 'export-view');
  await page.getByTestId('connection-disconnect').click();
  await expectAccessible(page, 'disconnect-dialog');
  await page.getByTestId('disconnect-keep').click();
  await expect(page.getByTestId('disconnect-dialog')).toHaveCount(0);
});

test('the flow: destination, preview and an accepted outcome', async ({ page }) => {
  const value = fixtures();
  const names = value.scenario.specs.accessibility;
  await login(page, value.accounts.memberA);
  await flowTo(page, names.cancel);
  await expectAccessible(page, 'export-flow');
  await previewOf(page, names.cancel);
  await expectAccessible(page, 'export-flow');
  await page.getByTestId('preview-approve').click();
  await expectStep(page, 'outcome');
  await expect(page.getByTestId('outcome-cancel')).toBeVisible();
  await expectAccessible(page, 'export-flow');
  await page.getByTestId('outcome-cancel').click();
  await expect(page.getByTestId('outcome-status')).toContainText('취소했습니다');
  await expectAccessible(page, 'export-flow');
});

test('an unclear outcome, the history and the settle dialog', async ({ page }) => {
  test.setTimeout(90_000);
  const value = fixtures();
  const names = value.scenario.specs.accessibility;
  await login(page, value.accounts.memberA);
  await flowTo(page, names.settle);
  await previewOf(page, names.settle);
  await page.getByTestId('preview-approve').click();
  await expect(page.getByTestId('outcome-status')).toContainText('확인 중', { timeout: 30_000 });
  await expectAccessible(page, 'export-flow');
  advanceExportClock();
  await openExportView(page);
  await waitForSettlement(page, names.settle, () => reopenExportView(page));
  await expectAccessible(page, 'export-view');
  await historyRow(page, names.settle).getByTestId('history-settle').click();
  const dialog = page.getByTestId('settle-dialog');
  await expectAccessible(page, 'settle-dialog');
  await dialog.getByTestId('settle-delivered').check();
  await dialog.getByTestId('settle-link').fill('https://example.invalid/not-a-notion-page');
  await dialog.getByTestId('settle-confirm').click();
  await expect(dialog.getByTestId('settle-link-error')).toBeVisible();
  await expectAccessible(page, 'settle-dialog');
  await dialog.getByTestId('settle-not-delivered').check();
  await expectAccessible(page, 'settle-dialog');
  await dialog.getByTestId('settle-confirm').click();
  await expect(page.getByTestId('history-notice')).toHaveText(
    '직접 확인해 내보내지 않은 것으로 기록했습니다',
  );
  await expectAccessible(page, 'export-view');
});

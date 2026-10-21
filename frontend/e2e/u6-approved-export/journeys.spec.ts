// Mounted U6 journeys over the real served app, database, lane and the fake Notion.
import { test, expect, type Page } from '@playwright/test';
import {
  advanceExportClock,
  captureExportFailures,
  connectNotion,
  destinationOption,
  ensureConnected,
  ensureDisconnected,
  expectStep,
  fixtures,
  historyRow,
  login,
  logout,
  openExportView,
  openNoveltyResult,
  reopenExportView,
  scrub,
  waitForSettlement,
} from './helpers';

test.describe.configure({ mode: 'serial' });

const diagnostics = new WeakMap<Page, ReturnType<typeof captureExportFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureExportFailures(page));
});

test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

/** Opens the flow from the novelty result and walks it to the preview of `title`. */
async function previewTo(page: Page, title: string) {
  await openNoveltyResult(page, fixtures().novelty);
  await page.getByTestId('novelty-export-open').click();
  await expectStep(page, 'destination');
  await destinationOption(page, title).getByTestId('destination-radio').check();
  await page.getByTestId('destination-next').click();
  await expectStep(page, 'preview');
  await expect(page.getByTestId('preview-step')).toHaveAttribute('data-preview-state', 'ready');
  await expect(page.getByTestId('preview-rendered')).toContainText('docsuri-export:v1:');
}

test('connect: a synthetic token connects and never stays in the field', async ({ page }) => {
  const value = fixtures();
  await login(page, value.accounts.memberA);
  await openExportView(page);
  await ensureDisconnected(page);
  await expect(page.getByTestId('connect-help')).toContainText('콘텐츠 삽입(Insert content)');
  await connectNotion(page, value.notionToken);
  await expect(page.getByTestId('export-live')).toContainText('DocSuri 합성 워크스페이스');
  // Another owner sees none of this connection.
  await logout(page);
  await login(page, value.accounts.memberB);
  await openExportView(page);
  await expect(page.getByTestId('connection-state')).toContainText('연결되지 않음');
});

test('export: an explicit approval writes one page and links to it', async ({ page }) => {
  const value = fixtures();
  await login(page, value.accounts.memberA);
  await ensureConnected(page, value.notionToken);
  await previewTo(page, value.scenario.practicePage);
  await page.getByTestId('preview-approve').click();
  await expectStep(page, 'outcome');
  await expect(page.getByTestId('outcome-status')).toContainText('내보냈습니다', {
    timeout: 30_000,
  });
  await expect(page.getByTestId('outcome-page-link')).toContainText('Notion에서 열기');
  await expect(page.getByTestId('flow-live')).toContainText('내보내기 상태: 내보냈습니다');
});

test('cancel: an accepted export waiting on its check is cancelled', async ({ page }) => {
  const value = fixtures();
  const names = value.scenario.specs.journeys;
  await login(page, value.accounts.memberA);
  await ensureConnected(page, value.notionToken);
  await previewTo(page, names.cancel);
  await page.getByTestId('preview-approve').click();
  await expectStep(page, 'outcome');
  await expect(page.getByTestId('outcome-status')).toContainText('내보내는 중');
  await expect(page.getByTestId('outcome-signout-note')).toBeVisible();
  await page.getByTestId('outcome-cancel').click();
  await expect(page.getByTestId('outcome-status')).toContainText('취소했습니다');
  await openExportView(page);
  await expect(historyRow(page, names.cancel).getByTestId('history-status')).toContainText(
    '취소했습니다',
  );
});

test('settle: an unclear export is settled by the owner after the checks', async ({ page }) => {
  test.setTimeout(90_000);
  const value = fixtures();
  const names = value.scenario.specs.journeys;
  await login(page, value.accounts.memberA);
  await ensureConnected(page, value.notionToken);
  await previewTo(page, names.settle);
  await page.getByTestId('preview-approve').click();
  await expectStep(page, 'outcome');
  await expect(page.getByTestId('outcome-status')).toContainText('확인 중', { timeout: 30_000 });
  await expect(page.getByTestId('outcome-next-check')).toBeVisible();
  advanceExportClock();
  await openExportView(page);
  await waitForSettlement(page, names.settle, () => reopenExportView(page));
  await historyRow(page, names.settle).getByTestId('history-settle').click();
  const dialog = page.getByTestId('settle-dialog');
  await expect(dialog).toContainText(names.settle);
  await dialog.getByTestId('settle-delivered').check();
  await expect(dialog.getByTestId('settle-assumption')).toContainText('성공으로 남습니다');
  await dialog.getByTestId('settle-confirm').click();
  await expect(page.getByTestId('history-notice')).toHaveText(
    '직접 확인해 내보낸 것으로 기록했습니다',
  );
  const row = historyRow(page, names.settle);
  await expect(row.getByTestId('history-owner-confirmed')).toHaveText('직접 확인됨');
  await expect(row.getByTestId('history-page-link')).toHaveCount(0);
});

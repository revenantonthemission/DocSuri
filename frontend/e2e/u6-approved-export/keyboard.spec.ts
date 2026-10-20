// Keyboard-only U6 journeys: connect, export, cancel and settle without a pointer.
// Checks WCAG 2.1.1 (keyboard), 2.4.3 (focus order), 2.4.7 (focus visible) and
// 2.4.11 (focus not obscured), with focus trapped in dialogs and returned to the trigger.
import { test, expect, type Page } from '@playwright/test';
import {
  advanceExportClock,
  arrowToDestination,
  captureExportFailures,
  destinationOption,
  expectConnected,
  expectFocusTrapped,
  expectFocusVisibleAndUnobscured,
  expectStep,
  fixtures,
  focused,
  gotoNoveltyLink,
  historyRow,
  login,
  scrub,
  tabTo,
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

async function keyboardExportView(page: Page) {
  await tabTo(page, 'nav-export', { backward: true });
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('export-view')).not.toHaveAttribute('data-view-state', 'loading');
  // 2.4.3: opening a view moves focus out of the navigation to the opened content (the
  // shell focuses its main region; the view focuses its own heading).
  await expect
    .poll(() =>
      page.evaluate(() => {
        const element = document.activeElement;
        return element?.id === 'main' || element?.getAttribute('data-testid') === 'export-heading';
      }),
    )
    .toBe(true);
}

async function keyboardConnect(page: Page, token: string) {
  await tabTo(page, 'connect-token');
  await page.keyboard.type(token);
  await tabTo(page, 'connect-submit');
  await page.keyboard.press('Enter');
  await expectConnected(page);
}

/** From the novelty result to the preview of `title`, by keyboard only. */
async function keyboardPreview(page: Page, title: string) {
  await gotoNoveltyLink(page, fixtures().novelty);
  const open = page.getByRole('button', { name: '준비된 결과 열기' });
  await expect(open).toBeVisible();
  await open.focus();
  await page.keyboard.press('Enter');
  // The result read is asynchronous: wait for the opened result and its export entry before
  // tabbing, so the bounded Tab walk never races it. 2.4.3: the pressed button keeps focus
  // while the read runs and afterwards, so Tab continues from it, not from the page top.
  await expect(page.getByRole('region', { name: '준비된 연구 결과' })).toBeVisible();
  await expect(page.getByTestId('novelty-export-open')).toBeVisible();
  await expect(open).toBeFocused();
  await tabTo(page, 'novelty-export-open');
  await page.keyboard.press('Enter');
  await expectStep(page, 'destination');
  // 2.4.3: a step change moves focus to the step heading, then Tab follows the page.
  await expect(page.getByTestId('flow-heading')).toBeFocused();
  await expect(destinationOption(page, title)).toBeVisible();
  const order: string[] = [];
  for (let step = 0; step < 40 && !order.includes('destination-radio'); step += 1) {
    await page.keyboard.press('Tab');
    const current = await focused(page);
    if (current.testId) order.push(current.testId);
  }
  expect(order).toContain('destination-radio');
  expect(order.indexOf('destination-refresh')).toBeGreaterThanOrEqual(0);
  expect(order.indexOf('destination-refresh')).toBeLessThan(order.indexOf('destination-radio'));
  await arrowToDestination(page, title);
  // The next control follows the chosen destination; it is enabled only once one is chosen.
  await page.keyboard.press('Tab');
  expect((await focused(page)).testId).toBe('destination-next');
  await expectFocusVisibleAndUnobscured(page);
  await page.keyboard.press('Enter');
  await expectStep(page, 'preview');
  await expect(page.getByTestId('flow-heading')).toBeFocused();
  await expect(page.getByTestId('preview-step')).toHaveAttribute('data-preview-state', 'ready');
}

async function keyboardApprove(page: Page) {
  await tabTo(page, 'preview-approve');
  await page.keyboard.press('Enter');
  await expectStep(page, 'outcome');
  await expect(page.getByTestId('flow-heading')).toBeFocused();
}

test('connect by keyboard, with the disconnect dialog trapping and returning focus', async ({
  page,
}) => {
  const value = fixtures();
  await login(page, value.accounts.memberA);
  await keyboardExportView(page);
  if (await page.getByTestId('connect-token').isVisible())
    await keyboardConnect(page, value.notionToken);
  await tabTo(page, 'connection-disconnect');
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('disconnect-dialog')).toBeVisible();
  expect((await focused(page)).inDialog).toBe(true);
  await expectFocusVisibleAndUnobscured(page);
  await expectFocusTrapped(page);
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('disconnect-dialog')).toHaveCount(0);
  await expect(page.getByTestId('connection-disconnect')).toBeFocused();
  await page.keyboard.press('Enter');
  await tabTo(page, 'disconnect-confirm');
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('connection-notice')).toHaveText('Notion 연결을 해제했습니다');
  await keyboardConnect(page, value.notionToken);
});

test('export and cancel by keyboard', async ({ page }) => {
  const value = fixtures();
  const names = value.scenario.specs.keyboard;
  await login(page, value.accounts.memberA);
  await keyboardPreview(page, value.scenario.practicePage);
  await keyboardApprove(page);
  await expect(page.getByTestId('outcome-status')).toContainText('내보냈습니다', {
    timeout: 30_000,
  });
  await keyboardPreview(page, names.cancel);
  await keyboardApprove(page);
  await expect(page.getByTestId('outcome-status')).toContainText('내보내는 중');
  await tabTo(page, 'outcome-cancel');
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('outcome-status')).toContainText('취소했습니다');
});

test('settle by keyboard, with the settle dialog trapping and returning focus', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const value = fixtures();
  const names = value.scenario.specs.keyboard;
  await login(page, value.accounts.memberA);
  await keyboardPreview(page, names.settle);
  await keyboardApprove(page);
  await expect(page.getByTestId('outcome-status')).toContainText('확인 중', { timeout: 30_000 });
  advanceExportClock();
  const settle = historyRow(page, names.settle).getByTestId('history-settle');
  await expect
    .poll(
      async () => {
        await tabTo(page, 'nav-novelty', { backward: true });
        await page.keyboard.press('Enter');
        await keyboardExportView(page);
        return settle.isVisible();
      },
      { timeout: 40_000, intervals: [1_000, 2_000] },
    )
    .toBe(true);
  await tabTo(page, 'history-settle', { context: names.settle });
  await page.keyboard.press('Enter');
  const dialog = page.getByTestId('settle-dialog');
  await expect(dialog).toBeVisible();
  expect((await focused(page)).inDialog).toBe(true);
  await expectFocusTrapped(page);
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(settle).toBeFocused();
  await page.keyboard.press('Enter');
  // An unchecked radio group is one tab stop: focus starts on its first choice and the
  // arrow keys move within it.
  await expect(dialog.getByTestId('settle-delivered')).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(dialog.getByTestId('settle-not-delivered')).toBeChecked();
  await expect(dialog.getByTestId('settle-not-delivered')).toBeFocused();
  await expect(dialog.getByTestId('settle-assumption')).toContainText('두 번째 사본');
  await tabTo(page, 'settle-confirm');
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('history-notice')).toHaveText(
    '직접 확인해 내보내지 않은 것으로 기록했습니다',
  );
});

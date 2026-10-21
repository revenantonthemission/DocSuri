// WCAG 1.4.10 reflow: at 320 CSS px every U6 view and dialog scrolls in one direction only.
import { test, expect, type Page } from '@playwright/test';
import {
  captureExportFailures,
  destinationOption,
  ensureConnected,
  expectStep,
  fixtures,
  login,
  openNoveltyResult,
  scrub,
} from './helpers';

const diagnostics = new WeakMap<Page, ReturnType<typeof captureExportFailures>>();
test.beforeEach(async ({ page }) => {
  diagnostics.set(page, captureExportFailures(page));
  await page.setViewportSize({ width: 320, height: 640 });
});

test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

/** Neither the page nor the U6 surface needs horizontal scrolling at this width. */
async function expectReflow(page: Page, testId: string) {
  const surface = page.getByTestId(testId);
  await expect(surface).toBeVisible();
  const overflow = await surface.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return {
      page: document.documentElement.scrollWidth > window.innerWidth,
      surface: element.scrollWidth > element.clientWidth + 1,
      offscreen: box.left < 0 || box.right > window.innerWidth + 1,
    };
  });
  expect(overflow, `${testId} reflows at 320 CSS px`).toEqual({
    page: false,
    surface: false,
    offscreen: false,
  });
}

test('the export view, the flow and the disconnect dialog reflow at 320 px', async ({ page }) => {
  const value = fixtures();
  await login(page, value.accounts.memberA);
  await ensureConnected(page, value.notionToken);
  await expectReflow(page, 'export-view');
  await page.getByTestId('connection-disconnect').click();
  await expectReflow(page, 'disconnect-dialog');
  await page.getByTestId('disconnect-keep').click();
  await openNoveltyResult(page, value.novelty);
  await page.getByTestId('novelty-export-open').click();
  await expectStep(page, 'destination');
  await expect(destinationOption(page, value.scenario.sameTitle)).toHaveCount(2);
  await expectReflow(page, 'export-flow');
  await destinationOption(page, value.scenario.practicePage)
    .getByTestId('destination-radio')
    .check();
  await page.getByTestId('destination-next').click();
  await expectStep(page, 'preview');
  await expect(page.getByTestId('preview-step')).toHaveAttribute('data-preview-state', 'ready');
  await expectReflow(page, 'export-flow');
});

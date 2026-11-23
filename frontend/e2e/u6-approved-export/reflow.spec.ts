// WCAG 1.4.10 reflow: at 320 CSS px every U6 view and dialog scrolls in one direction only.
import { test, expect, type Page } from '@playwright/test';
import {
  captureExportFailures,
  connectNotion,
  destinationOption,
  ensureConnected,
  ensureDisconnected,
  expectReflowAt320,
  expectStep,
  fixtures,
  historyRow,
  login,
  openExportView,
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

test('the export view reflows at 320 px: connect form, field error, connected and the disconnect dialog', async ({
  page,
}) => {
  const value = fixtures();
  await login(page, value.accounts.memberA);
  await openExportView(page);
  await ensureDisconnected(page);
  expect(
    await expectReflowAt320(page, 'export-view'),
    'the connect form reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
  await page.getByTestId('connect-token').fill(' ');
  await page.getByTestId('connect-submit').click();
  await expect(page.getByTestId('connect-field-error')).toBeVisible();
  expect(await expectReflowAt320(page, 'export-view'), 'the field error reflows at 320 px').toEqual(
    {
      width: 320,
      page: false,
      surface: false,
      offscreen: false,
      nested: [],
    },
  );
  await connectNotion(page, value.notionToken);
  expect(
    await expectReflowAt320(page, 'export-view'),
    'the connected view reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
  await page.getByTestId('connection-disconnect').click();
  expect(
    await expectReflowAt320(page, 'disconnect-dialog'),
    'the disconnect dialog reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
  await page.getByTestId('disconnect-keep').click();
});

test('the export flow reflows at 320 px: the destination list, the ready preview and a succeeded outcome', async ({
  page,
}) => {
  test.setTimeout(60_000);
  const value = fixtures();
  await login(page, value.accounts.memberA);
  await ensureConnected(page, value.notionToken);
  await openNoveltyResult(page, value.novelty);
  await page.getByTestId('novelty-export-open').click();
  await expectStep(page, 'destination');
  await expect(destinationOption(page, value.scenario.practicePage)).toBeVisible();
  expect(
    await expectReflowAt320(page, 'export-flow'),
    'the destination list reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
  await destinationOption(page, value.scenario.practicePage)
    .getByTestId('destination-radio')
    .check();
  await page.getByTestId('destination-next').click();
  await expectStep(page, 'preview');
  await expect(page.getByTestId('preview-step')).toHaveAttribute('data-preview-state', 'ready');
  await expect(page.getByTestId('preview-rendered')).toContainText('docsuri-export:v1:');
  // The rendered block's own nested scroller (.export-rendered) rides along in the walk.
  expect(
    await expectReflowAt320(page, 'export-flow'),
    'the ready preview reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
  await page.getByTestId('preview-approve').click();
  await expectStep(page, 'outcome');
  await expect(page.getByTestId('outcome-status')).toContainText('내보냈습니다', {
    timeout: 30_000,
  });
  await expect(page.getByTestId('outcome-page-link')).toBeVisible();
  expect(
    await expectReflowAt320(page, 'export-flow'),
    'the succeeded outcome reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
});

test('a cancelled outcome and its history row reflow at 320 px', async ({ page }) => {
  const value = fixtures();
  const names = value.scenario.specs.reflow;
  await login(page, value.accounts.memberA);
  await ensureConnected(page, value.notionToken);
  await openNoveltyResult(page, value.novelty);
  await page.getByTestId('novelty-export-open').click();
  await expectStep(page, 'destination');
  await expect(destinationOption(page, names.cancel)).toBeVisible();
  await destinationOption(page, names.cancel).getByTestId('destination-radio').check();
  await page.getByTestId('destination-next').click();
  await expect(page.getByTestId('preview-step')).toHaveAttribute('data-preview-state', 'ready');
  await page.getByTestId('preview-approve').click();
  await expectStep(page, 'outcome');
  await expect(page.getByTestId('outcome-signout-note')).toBeVisible();
  await expect(page.getByTestId('outcome-cancel')).toBeVisible();
  expect(
    await expectReflowAt320(page, 'export-flow'),
    'the accepted outcome reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
  await page.getByTestId('outcome-cancel').click();
  await expect(page.getByTestId('outcome-status')).toContainText('취소했습니다');
  expect(
    await expectReflowAt320(page, 'export-flow'),
    'the cancelled outcome reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
  await openExportView(page);
  await expect(historyRow(page, names.cancel)).toBeVisible();
  expect(
    await expectReflowAt320(page, 'export-view'),
    'the export view with its history reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
  expect(await expectReflowAt320(page, 'history'), 'the history row reflows at 320 px').toEqual({
    width: 320,
    page: false,
    surface: false,
    offscreen: false,
    nested: [],
  });
});

// Last in the file: memberA stays disconnected, and every other spec file reaches a
// connected state in its first test, so no later test relies on this one's state.
test('the export flow reflows at 320 px without a usable connection: the connection step and its field error', async ({
  page,
}) => {
  const value = fixtures();
  await login(page, value.accounts.memberA);
  await openExportView(page);
  await ensureDisconnected(page);
  await openNoveltyResult(page, value.novelty);
  await page.getByTestId('novelty-export-open').click();
  const step = page.getByTestId('connection-step');
  await expect(step.getByTestId('connect-form')).toBeVisible();
  await expect(step.getByTestId('flow-connection-state')).toBeVisible();
  await expectStep(page, 'connection');
  await expect(step.getByTestId('connect-token')).toHaveValue('');
  expect(
    await expectReflowAt320(page, 'export-flow'),
    'the connection step reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
  await step.getByTestId('connect-token').fill(' ');
  await step.getByTestId('connect-submit').click();
  await expect(step.getByTestId('connect-field-error')).toBeVisible();
  await expect(step.getByTestId('connect-token')).toHaveValue('');
  expect(
    await expectReflowAt320(page, 'export-flow'),
    'the connection step with a field error reflows at 320 px',
  ).toEqual({ width: 320, page: false, surface: false, offscreen: false, nested: [] });
});

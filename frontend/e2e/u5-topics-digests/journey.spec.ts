// Mounted U5 journeys over the real served app, database and scheduler.
import { test, expect, type Page } from '@playwright/test';
import { captureTopicsFailures, fixtures, login, openTopics, scrub } from './helpers';

const failures = new WeakMap<Page, ReturnType<typeof captureTopicsFailures>>();
test.beforeEach(({ page }) => {
  failures.set(page, captureTopicsFailures(page));
});

test.afterEach(async ({ page }, info) => {
  await failures.get(page)?.(info);
  await scrub(page);
});

test('follow, settings save and unsubscribe through the mounted surface', async ({ page }) => {
  const name = `여정-${Date.now()}`;
  await login(page, fixtures().accounts.memberA);
  await openTopics(page);
  await page.getByTestId('follow-input').fill(name);
  await page.getByTestId('follow-button').click();
  const row = page.getByTestId('topic-row').filter({ hasText: name });
  await expect(row).toBeVisible();
  await expect(row).toContainText('구독 중');
  // Settings: weekly cadence with the anchored day and the wide window.
  await row.getByTestId('settings-link').click();
  const form = page.getByTestId('settings-form');
  await expect(form).toBeVisible();
  await page.getByTestId('cadence-select').selectOption('weekly');
  await expect(page.getByTestId('delivery-day')).toBeVisible();
  await page.getByTestId('delivery-day').selectOption('mon');
  await page.getByTestId('window-select').selectOption('30');
  await page.getByTestId('save-button').click();
  await expect(page.getByText(/발송 설정을 저장했어요/)).toBeVisible();
  await expect(page.getByTestId('settings-form')).toHaveCount(0);
  // Unsubscribe: confirmed, names the topic, removes the row.
  await row.getByTestId('unsubscribe-button').click();
  const dialog = page.getByTestId('confirm-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText(name);
  await page.getByTestId('confirm-dialog-confirm').click();
  await expect(page.getByText(/구독을 해지했어요/)).toBeVisible();
  await expect(page.getByTestId('topic-row').filter({ hasText: name })).toHaveCount(0);
});

test('a follow reaches a delivered digest through the scheduler and local sink', async ({
  page,
}) => {
  test.setTimeout(60_000);
  const name = `스케줄러-${Date.now()}`;
  await login(page, fixtures().accounts.memberA);
  await openTopics(page);
  await page.getByTestId('follow-input').fill(name);
  await page.getByTestId('follow-button').click();
  const row = page.getByTestId('topic-row').filter({ hasText: name });
  await expect(row).toBeVisible();
  // Make the topic due at any hour, then let the bounded scheduler pass run.
  await row.getByTestId('settings-link').click();
  await page.getByTestId('cadence-select').selectOption('daily');
  await page.getByTestId('delivery-time').fill('00:00');
  await page.getByTestId('window-select').selectOption('30');
  await page.getByTestId('save-button').click();
  await expect(page.getByText(/발송 설정을 저장했어요/)).toBeVisible();
  // The synthetic local sink acknowledges: the indicator reports the delivery.
  await expect(row.getByTestId('last-digest')).toContainText('마지막 발송 완료', {
    timeout: 20_000,
  });
});

test('the resolve control resolves an unknown outcome with the assumption named', async ({
  page,
}) => {
  // The fixtures phase guarantees memberA's fixture topic carries one
  // unresolved unknown with no reconcilable evidence: silence never
  // reconciles, so only the owner's resolve control can close it.
  await login(page, fixtures().accounts.memberA);
  await openTopics(page);
  const row = page.getByTestId('topic-row').filter({ hasText: '해결 확인 주제' });
  await expect(row).toBeVisible();
  const control = row.getByTestId('resolve-control');
  await expect(control).toBeVisible();
  await control.getByTestId('resolve-delivered').click();
  await expect(page.getByText(/배달됨으로 표시했어요/)).toBeVisible();
  await expect(row.getByTestId('resolve-control')).toHaveCount(0);
  // The reconciled delivery applies the watermark like a direct send.
  await expect(row.getByTestId('last-digest')).toContainText('마지막 발송 완료');
});

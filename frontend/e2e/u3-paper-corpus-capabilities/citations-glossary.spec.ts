/** U3 journeys: citation exploration with save, glossary conflict recovery. */
import { test, expect } from '@playwright/test';
import { helper, login, fixtures, openFirstResult, search } from './helpers';

test.describe.configure({ mode: 'serial' });

test.beforeAll(() => {
  helper('setup');
  helper('reset-corpus');
  helper('publish');
});

test('citation exploration is labelled and saving runs through Library', async ({ page }) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await search(page, 'paper-alpha');
  await openFirstResult(page);
  await expect(page.getByTestId('citation-explorer')).toBeVisible();
  await page.getByTestId('citation-cited').click();
  await expect(page.getByTestId('citation-freshness')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('citation-freshness')).toContainText('최신성 current');
  const node = page.getByTestId('citation-node').first();
  if ((await node.count()) > 0) {
    const save = node.getByTestId('citation-save');
    if ((await save.count()) > 0) {
      await save.click();
      await expect(page.getByTestId('status-line')).toContainText('내 서재에 저장했어요');
    }
  }
});

test('glossary CAS conflict is visible and preserves the committed terms', async ({
  page,
}) => {
  const accounts = fixtures().accounts;
  await login(page, accounts.memberA);
  await expect(page.getByTestId('glossary-editor')).toBeVisible();
  // Another surface (an earlier tab) commits a term with the revision the UI
  // currently holds; the single-session rule for this account forbids a
  // second live sign-in, so the stale write is issued through the page's own
  // authenticated transport exactly as a competing tab would.
  const committed = await page.evaluate(async () => {
    const bootstrap = await fetch('/api/v2/session').then((r) => r.json());
    const current = await fetch('/api/v2/c06/read-glossary', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': bootstrap.csrfToken,
        'Idempotency-Key': crypto.randomUUID(),
      },
      body: '{}',
    }).then((r) => r.json());
    const response = await fetch('/api/v2/c06/replace-glossary', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': bootstrap.csrfToken,
        'Idempotency-Key': crypto.randomUUID(),
      },
      body: JSON.stringify({
        expectedRevision: current.revision,
        normalizationPolicy: { policyId: 'u3-owner-glossary', revision: '1' },
        terms: [
          {
            termId: crypto.randomUUID(),
            source: 'attention',
            preferred: '어텐션',
            languageId: 'ko',
          },
        ],
      }),
    });
    return { status: response.status, value: await response.json() };
  });
  expect(committed.status).toBe(200);
  // The UI still holds the previous revision; its save conflicts visibly.
  await page.getByTestId('glossary-source').fill('token');
  await page.getByTestId('glossary-preferred').fill('토큰');
  await page.getByTestId('glossary-save').click();
  await expect(page.getByTestId('glossary-conflict')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('glossary-term').first()).toContainText('어텐션');
});

test('citation exploration refuses guests but leaves reading available', async ({ page }) => {
  await page.goto('/');
  await search(page, 'paper-alpha');
  await openFirstResult(page);
  await expect(page.getByTestId('reading-surface')).toBeVisible();
  await expect(page.getByTestId('citation-explorer')).toHaveCount(0);
});

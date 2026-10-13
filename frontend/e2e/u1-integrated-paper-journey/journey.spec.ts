/**
 * U1 mounted browser scenarios over the real journey assembly.
 *
 * Six scenarios cover P1, P2, supported translation (truthfully refused while
 * the model-readiness marker is absent), fresh saved return, interrupted-state
 * recovery and cross-account denial with authorized positive controls. The
 * real backend, persistence and static workspace are used; nothing is mocked.
 * The synthetic realm admits two active accounts: one is registered here and
 * the established demo account is the second owner.
 */

import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';

const environment = process.env.DOCSURI_U1_ENVIRONMENT_FILE ?? '';
const root = dirname(environment);
const PASSWORD = 'JourneyBrowser!28-A';

type Mail = { email: string; challengeId: string; proof: string; flowBinding: string };

let ownerEmail = '';
let otherEmail = '';

function newestMail(email: string): Mail {
  const directory = join(root, 'verification-mail');
  const files = readdirSync(directory)
    .map((name) => ({ name, at: statSync(join(directory, name)).mtimeMs }))
    .sort((a, b) => b.at - a.at)
    .slice(0, 40);
  for (const file of files) {
    const value = JSON.parse(readFileSync(join(directory, file.name), 'utf8')) as Mail;
    if (value.email === email) return value;
  }
  throw new Error(`no local verification message for ${email}`);
}

async function signIn(page: Page, email: string, password: string) {
  await page.goto('/');
  // A prior owner's session is ended explicitly; the account switch clears all
  // private state before the new owner signs in.
  if (await page.getByTestId('logout').isVisible().catch(() => false)) {
    await page.getByTestId('logout').click();
  }
  await expect(page.getByTestId('entry-panel')).toBeVisible();
  await page.getByTestId('entry-email').fill(email);
  await page.getByTestId('entry-password').fill(password);
  await page.getByTestId('entry-submit').click();
  await expect(page.getByTestId('logout')).toBeVisible();
}

async function registerThroughUi(page: Page, email: string): Promise<void> {
  await page.goto('/');
  await expect(page.getByTestId('entry-panel')).toBeVisible();
  await page.getByTestId('entry-switch').click();
  await page.getByTestId('entry-email').fill(email);
  await page.getByTestId('entry-password').fill(PASSWORD);
  await page.getByTestId('entry-submit').click();
  await expect(page.getByTestId('entry-panel')).toContainText('인증 메일을 보냈어요');
  const mail = newestMail(email);
  await page.goto(
    `/verify-email?action=verify-email&challengeId=${mail.challengeId}` +
      `&proof=${encodeURIComponent(mail.proof)}&flowBinding=${encodeURIComponent(mail.flowBinding)}`,
  );
  await page.getByTestId('verification-form').getByRole('button', { name: '인증 완료' }).click();
  await expect(page.getByTestId('entry-panel')).toContainText('이메일 인증을 마쳤어요');
}

async function search(page: Page, query: string, expected: string) {
  await page.getByTestId('search-query').fill(query);
  await page.getByTestId('search-submit').click();
  await expect(page.getByTestId('search-results')).toContainText(expected);
}

async function openPaper(page: Page, title: string) {
  await page.getByRole('button', { name: title }).click();
  await expect(page.getByTestId('paper-workspace')).toBeVisible();
}

async function csrf(page: Page): Promise<string> {
  const bootstrap = await page.request.get('/api/v2/session');
  expect(bootstrap.status()).toBe(200);
  return ((await bootstrap.json()) as { csrfToken: string }).csrfToken;
}

function directHeaders(page: Page, token: string) {
  return {
    'X-CSRF-Token': token,
    'Idempotency-Key': crypto.randomUUID(),
    Origin: new URL(page.url()).origin,
  };
}

test.describe.serial('U1 mounted paper journey', () => {
  test.beforeAll(async ({ browser }) => {
    ownerEmail = `browser-${Date.now()}-${Math.floor(Math.random() * 1e6)}@journey.fixture.example.com`;
    otherEmail = `browser-${Date.now()}-${Math.floor(Math.random() * 1e6)}@journey.fixture.example.com`;
    const context = await browser.newContext({ ignoreHTTPSErrors: true });
    const page = await context.newPage();
    await registerThroughUi(page, ownerEmail);
    await page.context().clearCookies();
    await registerThroughUi(page, otherEmail);
    await context.close();
  });

  test('scenario 1 — P1: find, read, save and revisit after a fresh authenticated return', async ({
    page,
  }) => {
    await signIn(page, ownerEmail, PASSWORD);
    await search(page, 'transformer attention', 'Attention Is All You Need');
    await openPaper(page, 'Attention Is All You Need');
    await expect(page.getByTestId('paper-identity')).toContainText('1706.03762v7');
    await expect(page.getByTestId('reading-surface')).toContainText('softmax');
    await page.getByTestId('save-paper').click();
    await expect(page.getByText('저장됨')).toBeVisible();
    // A fresh authenticated return uses only owned lists, never a transient ID.
    await page.context().clearCookies();
    await signIn(page, ownerEmail, PASSWORD);
    await page.getByTestId('nav-library').click();
    await expect(page.getByTestId('saved-papers')).toContainText('Attention Is All You Need');
    await expect(screenText(page, 'saved-papers')).toContainText('available');
  });

  test('scenario 2 — P2: guest search then an authenticated read of the exact version', async ({
    page,
  }) => {
    await page.goto('/');
    await expect(page.getByTestId('search-workspace')).toBeVisible();
    await search(page, 'retrieval augmented generation', 'Retrieval-Augmented');
    await openPaper(page, 'Retrieval-Augmented Generation');
    // Private reading requires current authority: a guest is told to sign in
    // and no content is rendered.
    await expect(page.getByTestId('status-line')).toContainText('다시 로그인해 주세요');
    await expect(page.getByTestId('reading-surface')).toHaveCount(0);
    await signIn(page, otherEmail, PASSWORD);
    await search(page, 'retrieval augmented generation', 'Retrieval-Augmented');
    await openPaper(page, 'Retrieval-Augmented Generation');
    await expect(page.getByTestId('paper-identity')).toContainText('2005.11401v4');
    await expect(page.getByTestId('reading-surface')).toContainText('BART');
  });

  test('scenario 3 — assistance truthfully refuses new work while readiness is false', async ({
    page,
  }) => {
    await signIn(page, ownerEmail, PASSWORD);
    await search(page, 'transformer attention', 'Attention Is All You Need');
    await openPaper(page, 'Attention Is All You Need');
    // The reviewed P1/P2 model evidence is unresolved, so no option is offered
    // and no fabricated summary or translation can be started.
    await expect(page.getByTestId('assistance-unavailable')).toContainText(
      '현재 이 작업을 사용할 수 없어요',
    );
    await expect(page.getByTestId('start-summary')).toHaveCount(0);
    await expect(page.getByTestId('start-translation')).toHaveCount(0);
    await expect(page.getByTestId('activity-card')).toHaveCount(0);
  });

  test('scenario 4 — cross-account denial with an authorized positive control', async ({ page }) => {
    const marker = `browser-marker-${Date.now()}`;
    await signIn(page, ownerEmail, PASSWORD);
    await page.getByTestId('search-query').fill(marker);
    await page.getByTestId('search-submit').click();
    await expect(page.getByTestId('search-status')).toContainText('일치하는 논문이 없어요');
    await page.getByTestId('save-search').click();
    await expect(page.getByText('검색 조건을 저장했어요')).toBeVisible();
    const ownerCsrf = await csrf(page);
    const ownerList = await page.request.post('/api/v2/c03/library-list-saved-searches', {
      headers: directHeaders(page, ownerCsrf),
      data: { page: { limit: 20 } },
    });
    expect(ownerList.status()).toBe(200);
    const ownerItems = ((await ownerList.json()) as {
      items: { queryContext: { query: string } }[];
    }).items;
    expect(ownerItems.some((item) => item.queryContext.query === marker)).toBe(true);

    await page.context().clearCookies();
    await signIn(page, otherEmail, PASSWORD);
    await page.getByTestId('nav-library').click();
    await expect(screenText(page, 'saved-searches')).not.toContainText(marker);
    const otherCsrf = await csrf(page);
    const otherList = await page.request.post('/api/v2/c03/library-list-saved-searches', {
      headers: directHeaders(page, otherCsrf),
      data: { page: { limit: 20 } },
    });
    expect(otherList.status()).toBe(200);
    const otherItems = ((await otherList.json()) as {
      items: { queryContext: { query: string } }[];
    }).items;
    expect(otherItems.every((item) => item.queryContext.query !== marker)).toBe(true);
  });

  test('scenario 5 — interrupted state recovers to the same authoritative truth', async ({
    page,
  }) => {
    await signIn(page, ownerEmail, PASSWORD);
    await search(page, 'transformer attention', 'Attention Is All You Need');
    await openPaper(page, 'Attention Is All You Need');
    await expect(page.getByTestId('assistance-unavailable')).toBeVisible();
    // A reload is a real interruption: the workspace re-reads authoritative
    // state and never resumes from a locally asserted outcome.
    await page.reload();
    await expect(page.getByTestId('search-workspace')).toBeVisible();
    await search(page, 'transformer attention', 'Attention Is All You Need');
    await openPaper(page, 'Attention Is All You Need');
    await expect(page.getByTestId('assistance-unavailable')).toContainText(
      '현재 이 작업을 사용할 수 없어요',
    );
    await expect(page.getByTestId('activity-card')).toHaveCount(0);
    await expect(page.getByTestId('open-result')).toHaveCount(0);
  });

  test('scenario 6 — compact reflow, appearance persistence and keyboard focus', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 640 });
    await page.goto('/');
    await expect(page.getByTestId('search-query')).toBeVisible();
    // A clean focus start, then the keyboard path begins at the skip link and
    // moves the single main region into focus.
    await page.locator('body').click({ position: { x: 4, y: 4 } });
    await page.keyboard.press('Tab');
    const skip = page.getByRole('link', { name: '본문으로 건너뛰기' });
    await expect(skip).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('#main')).toBeFocused();
    await expect(page.getByTestId('search-submit')).toBeVisible();
    await page.getByTestId('appearance-select').selectOption('dark');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.getByTestId('appearance-select').selectOption('light');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    // 200% text: ordinary content reflows without two-dimensional scrolling.
    // The owned CSP refuses inline style tags, so the emulation is a bounded
    // CSSOM change on the document root.
    await page.evaluate(() => {
      document.documentElement.style.fontSize = '200%';
    });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    await expect(page.getByTestId('search-query')).toBeVisible();
    const results = await new AxeBuilder({ page }).analyze();
    const blocking = results.violations.filter(
      (violation) => violation.impact === 'serious' || violation.impact === 'critical',
    );
    // Automated evidence only; rendered/manual confirmation is still required.
    expect(
      blocking.map((violation) => `${violation.id}: ${violation.nodes.length}`),
      'rendered accessibility scan (requires manual confirmation as well)',
    ).toEqual([]);
  });
});

function screenText(page: Page, testId: string) {
  return page.getByTestId(testId);
}

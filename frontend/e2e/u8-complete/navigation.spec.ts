// J12: every navigation state of the complete workspace (BR5.1–BR5.5), as the server
// resolves it and the browser shows it: signed out, a member, the administrator, a
// capability gone stale while the realm's workers are stopped (shown as unavailable), and
// a degraded export whose oldest accepted effect is past its bound.
import { test, expect, type Page } from '@playwright/test';
import {
  assertNoViolations,
  captureFailures,
  ensureNotionConnected,
  expectAccessible,
  exportNoveltyTo,
  fixtures,
  go,
  harness,
  login,
  loginAdministrator,
  resolvedNavigation,
  scrub,
  watchPolicy,
  writeMeasurements,
} from './helpers';

// In file order on the one worker; a failure does not skip the journeys after it.
test.describe.configure({ mode: 'default' });

const diagnostics = new WeakMap<Page, ReturnType<typeof captureFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureFailures(page));
});
test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

const OWNER_ROUTES = ['library', 'research', 'novelty', 'jobs', 'topics', 'export', 'settings'];
// The realm's synthetic freshness bound is 6 s (`SYNTHETIC_OPERATIONS`); the producers
// renew every 2 s, so twice the bound plus a renewal is the longest wait for a change.
const STATE_CHANGE_MS = 30_000;

/** Reloads the page until the server's answer for `routeId` carries `reasonKey`. */
async function untilReason(page: Page, routeId: string, reasonKey: string | undefined) {
  await expect
    .poll(
      async () =>
        (await resolvedNavigation(page)).items.find((item) => item.routeId === routeId)
          ?.reasonKey ?? undefined,
      { timeout: STATE_CHANGE_MS, intervals: [1_000, 2_000] },
    )
    .toBe(reasonKey);
  await page.reload();
  await expect(page.getByTestId('logout')).toBeVisible();
}

/** axe over the navigation in its current state, in light and then in dark; the page is
 * returned to light (U8 plan Step 102(d)). */
async function expectNavigationAccessible(page: Page) {
  await page.emulateMedia({ colorScheme: 'light' });
  await expectAccessible(page, 'navigation');
  await page.emulateMedia({ colorScheme: 'dark' });
  try {
    await expectAccessible(page, 'navigation');
  } finally {
    await page.emulateMedia({ colorScheme: 'light' });
  }
}

test('[J12] signed out: search is open, owner entries ask for sign-in, operations is absent', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByTestId('navigation')).toBeVisible();
  await expect(page.getByTestId('nav-search')).not.toHaveAttribute('aria-disabled', 'true');
  for (const route of OWNER_ROUTES)
    await expect(page.getByTestId(`nav-reason-${route}`)).toHaveText(
      '로그인 후 이용할 수 있습니다',
    );
  await expect(page.getByTestId('nav-operations')).toHaveCount(0);
  await expect(page.getByTestId('footer-privacy')).toBeVisible();
  await expect(page.getByTestId('footer-terms')).toBeVisible();
  await expectNavigationAccessible(page);
  // An owner entry is a sign-in prompt, never the owner's view.
  await page.getByTestId('nav-library').click();
  await expect(page.getByTestId('entry-email')).toBeVisible();
  await expect(page.getByTestId('logout')).toHaveCount(0);
});

test('[J12] a member: every owner entry is available, operations is still absent', async ({
  page,
}) => {
  await login(page, fixtures().accounts.memberA);
  // Available to the member: never a sign-in prompt, never disabled. A capability may be
  // degraded (its entry stays usable, with its reason), which the last test shows.
  await expect(page.getByTestId('navigation')).not.toContainText('로그인 후 이용할 수 있습니다');
  for (const route of OWNER_ROUTES)
    await expect(page.getByTestId(`nav-${route}`)).not.toHaveAttribute('aria-disabled', 'true');
  await expect(page.getByTestId('nav-operations')).toHaveCount(0);
  const answer = await resolvedNavigation(page);
  expect(answer.items.find((item) => item.routeId === 'operations')?.reasonKey).toBe(
    'nav.administratorOnly',
  );
  await expectNavigationAccessible(page);
});

test('[J12] the administrator with a current second factor reaches operations', async ({
  page,
}) => {
  await loginAdministrator(page, fixtures().accounts.administrator);
  await expect(page.getByTestId('nav-operations')).toBeVisible();
  await go(page, 'operations');
  await expect(page.getByTestId('nav-operations')).toHaveAttribute('aria-current', 'page');
  await expect(page.getByTestId('capability-table')).toBeVisible();
  await expect(page.getByTestId('capability-row-background.work')).toBeVisible();
  await expectNavigationAccessible(page);
});

test('[J12] stopped workers: required capabilities go stale and their entries are unavailable', async ({
  page,
}) => {
  test.setTimeout(120_000);
  await login(page, fixtures().accounts.memberA);
  harness('service', { name: 'workers', action: 'stop' });
  try {
    // The realm's one clock stands still while an earlier journey moved it ahead of now;
    // moving it past the 6-second freshness bound makes the last observations stale
    // whichever way it stands.
    harness('advance-clock', { seconds: 20 });
    await untilReason(page, 'library', 'nav.capabilityStale');
    const library = page.getByTestId('nav-library');
    await expect(library).toHaveAttribute('aria-disabled', 'true');
    await expect(page.getByTestId('nav-reason-library')).toHaveText(
      '상태 정보가 오래되어 다시 확인하는 중입니다',
    );
    // Checked while the workers are stopped.
    await expectNavigationAccessible(page);
    // An unavailable entry is never opened. It stays focusable and clickable with
    // `aria-disabled` (a person can still reach its reason), so the click is the
    // person's, past Playwright's own enabled check.
    await library.click({ force: true });
    await expect(library).not.toHaveAttribute('aria-current', 'page');
  } finally {
    harness('service', { name: 'workers', action: 'start' });
  }
  await untilReason(page, 'library', undefined);
  await expect(page.getByTestId('nav-library')).not.toHaveAttribute('aria-disabled', 'true');
});

test('[J12] a late export degrades its entry, which stays usable, until the owner cancels', async ({
  page,
}) => {
  test.setTimeout(150_000);
  const value = fixtures();
  await login(page, value.accounts.memberA);
  await ensureNotionConnected(page);
  await exportNoveltyTo(page, value.notion.stuck);
  // Past the synthetic 24-hour bound (`export_degraded_after`) on the delegated clock.
  harness('advance-clock', { seconds: 86_400 });
  harness('advance-clock', { seconds: 120 });
  await untilReason(page, 'export', 'nav.capabilityDegraded');
  await expect(page.getByTestId('nav-reason-export')).toHaveText('일부 기능이 제한되어 있습니다');
  await expect(page.getByTestId('nav-export')).not.toHaveAttribute('aria-disabled', 'true');
  // Checked while the export is degraded.
  await expectNavigationAccessible(page);
  // The owner cancels the stuck effect; the entry recovers.
  await go(page, 'export');
  const row = page.getByTestId('history-row').filter({ hasText: value.notion.stuck }).first();
  await row.getByTestId('history-cancel').click();
  await expect(page.getByTestId('history-notice')).toContainText('내보내기를 취소했습니다');
  // The producers renew on the realm's one clock, which stands still while it is ahead
  // of now: past the export's 2-second renewal, it observes the cancelled effect afresh
  // (as the stopped-workers journey moves the clock to make observations stale).
  harness('advance-clock', { seconds: 5 });
  await untilReason(page, 'export', undefined);
  await expect(page.getByTestId('nav-reason-export')).toHaveCount(0);
});

// NFR8.2 and NFR8.5 from a real browser, run only by the `performance` phase (the journey
// phases leave it out with `--grep-invert`): the first load through the public address,
// from navigation start until the shell is rendered with navigation resolved; later
// navigation, from the click to the destination view rendered; one accepted request, from
// the request to its accepted answer. The search request the page sends is kept as the
// shape the phase's 20 users send.
const LOADS = 5;
const PERF_ROUTES = ['library', 'research', 'novelty', 'jobs', 'topics', 'export', 'settings'];

test('[PERF] first load, later navigation and an accept, as a person meets them', async ({
  page,
  browser,
}) => {
  test.setTimeout(120_000);
  const firstLoadMs: number[] = [];
  const origin = new URL(test.info().project.use.baseURL ?? 'https://127.0.0.1:18110').origin;
  for (let index = 0; index < LOADS; index += 1) {
    // A fresh browser context each time: nothing cached, nothing signed in.
    const fresh = await browser.newContext({ baseURL: origin });
    watchPolicy(fresh);
    const other = await fresh.newPage();
    const begun = Date.now();
    await other.goto('/');
    await expect(other.getByTestId('navigation')).toBeVisible();
    await expect(other.getByTestId('nav-search')).not.toHaveAttribute('aria-disabled', 'true');
    firstLoadMs.push(Date.now() - begun);
    assertNoViolations(other);
    await fresh.close();
  }
  await login(page, fixtures().accounts.memberA);
  const navigationMs: number[] = [];
  for (const route of PERF_ROUTES) {
    const begun = Date.now();
    await go(page, route);
    await expect(page.getByTestId(`nav-${route}`)).toHaveAttribute('aria-current', 'page');
    // The destination view rendered: its own heading is on screen.
    await expect(page.locator('#main h2:visible').first()).toBeVisible();
    navigationMs.push(Date.now() - begun);
  }
  // The search request's shape, as the page sends it.
  await go(page, 'search');
  const searched = page.waitForRequest(
    (request) => new URL(request.url()).pathname === '/api/v2/c05/search',
  );
  await page.getByTestId('search-query').fill('attention transformer');
  await page.getByTestId('search-submit').click();
  const searchBody = (await searched).postDataJSON() as object;
  await expect(page.getByTestId('result-row').first()).toBeVisible({ timeout: 20_000 });
  // One accepted request: a novelty analysis.
  await go(page, 'novelty');
  await page.getByRole('button', { name: '새 분석 준비' }).click();
  await page.getByLabel('분석할 주제 또는 원고 설명').fill('성능 측정용 합성 주제');
  const accepted = page.waitForResponse(
    (response) => new URL(response.url()).pathname === '/api/v2/c07/accept-novelty-analysis',
  );
  const begun = Date.now();
  await page.getByRole('button', { name: '참신성 분석 시작' }).click();
  const answer = await accepted;
  const acceptMs = [Date.now() - begun];
  expect(answer.status()).toBe(200);
  writeMeasurements('perf-browser.json', { firstLoadMs, navigationMs, acceptMs, searchBody });
});

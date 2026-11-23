// A11Y (NFR5.1 keyboard and focus, NFR5.2): every member and administrator action by the
// keyboard alone (U8 plan Step 101(c)). Only Tab, Shift+Tab, Enter, Space, Escape and the
// arrow keys inside radio groups and the select act (on macOS the select takes its option's
// first character instead, by typeahead), and each effect is asserted. Every
// control a test activates is first reached by Tab or Shift+Tab from wherever the keyboard
// (or the page's own focus move) left the focus; no test places the focus itself (no
// `locator.focus()`), so a control Tab cannot reach fails here. A staged answer is a
// `page.route` fulfilment in the page's own context: a changed read is the realm's own answer
// fetched first through the page, a state-changing request or a read about a staged job gets
// a literal answer in the contract's shape, and none is used to assert a server's answer.
import { test, expect, type Locator, type Page, type Route } from '@playwright/test';
import {
  apiCall,
  captureFailures,
  fixtures,
  freshEntryMinute,
  realmFactorCode,
  routeProviders,
  scrub,
  signInForm,
  signInFormWithProviders,
  type Account,
  type Administrator,
} from './helpers';

test.describe.configure({ mode: 'default' });

const diagnostics = new WeakMap<Page, ReturnType<typeof captureFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureFailures(page));
});
test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

const NAVIGATION = '/api/v2/c01/host-resolve-navigation';
const CAPABILITIES = '/api/v2/capabilities';
const JOBS = '/api/v2/c07/list-research-jobs';
const DASHBOARD = '/api/v2/c11/read-dashboard';
const INCIDENTS = '/api/v2/c11/list-incidents';
const RECOVERY = '/api/v2/c11/request-recovery';
const MAX_TABS = 80;
// The view's own page size (`u8-jobs/api.ts` PAGE_SIZE).
const LIST_LIMIT = 20;
const NARROW = 320;
const WIDE = 1280;
const VIEW_HEIGHT = 720;
const NAV_ERROR_WAIT_MS = 30_000;
const UNREGISTERED = 'a11y-unregistered@example.com';
const JOB_ONE = '00000000-0000-4000-8000-00000000b001';
const JOB_TWO = '00000000-0000-4000-8000-00000000b002';
const INCIDENT = '00000000-0000-4000-8000-00000000c001';
const AT = '2026-11-12T00:00:00Z';

// One matcher per path: `page.unroute` removes a route only when given the very matcher
// `page.route` was given.
const matchers = new Map<string, (url: URL) => boolean>();
function onPath(path: string): (url: URL) => boolean {
  const known = matchers.get(path);
  if (known) return known;
  const matcher = (url: URL) => url.pathname === path;
  matchers.set(path, matcher);
  return matcher;
}

/** The page once its first reads have settled: the navigation resolved (or refused) and no
 * request in flight, so a view mounting late cannot take the focus a test placed. */
async function settled(page: Page): Promise<void> {
  await expect(page.getByTestId('nav-loading')).toHaveCount(0);
  await page.waitForLoadState('networkidle');
}

/** The sign-in form, settled. */
async function entryReady(page: Page): Promise<void> {
  await signInForm(page);
  await settled(page);
}

/** A route answering `path` with one JSON body; returns its removal. */
async function stageJson(
  page: Page,
  path: string,
  body: unknown,
  status = 200,
): Promise<() => Promise<void>> {
  const handler = async (route: Route) => {
    await route.fulfill({
      status,
      contentType: 'application/json',
      headers: { 'cache-control': 'no-store' },
      body: JSON.stringify(body),
    });
  };
  await page.route(onPath(path), handler);
  return () => page.unroute(onPath(path), handler);
}

async function activeTestId(page: Page): Promise<string | null> {
  return page.evaluate(() => document.activeElement?.getAttribute('data-testid') ?? null);
}

/** Presses `key` (Tab or Shift+Tab) until the control with `testId` holds the focus. */
async function tabTo(page: Page, testId: string, key = 'Tab'): Promise<void> {
  for (let press = 0; press < MAX_TABS; press += 1) {
    if ((await activeTestId(page)) === testId) return;
    await page.keyboard.press(key);
  }
  expect(await activeTestId(page), `${key} reaches ${testId}`).toBe(testId);
}

/** Where `target` lies from the focus: 0 when it holds the focus, 1 when Tab moves toward it
 * (it follows the focused element, or nothing is focused and Tab starts the walk), -1 when it
 * precedes the focused element. */
async function directionTo(target: Locator): Promise<number> {
  return target.evaluate((element) => {
    const active = document.activeElement;
    if (active === element) return 0;
    if (active === null || active === document.body || active === document.documentElement)
      return 1;
    return active.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING ? 1 : -1;
  });
}

/** Moves the focus to `target` with Tab or Shift+Tab alone, from where the focus is now. */
async function reach(page: Page, target: Locator, name: string): Promise<void> {
  for (let step = 0; step < MAX_TABS; step += 1) {
    const direction = await directionTo(target);
    if (direction === 0) return;
    await page.keyboard.press(direction > 0 ? 'Tab' : 'Shift+Tab');
  }
  expect(await directionTo(target), `Tab or Shift+Tab reaches ${name}`).toBe(0);
}

/** The control with `testId` reached by Tab or Shift+Tab, then one key. */
async function press(page: Page, testId: string, key: string): Promise<void> {
  await reach(page, page.getByTestId(testId), testId);
  await page.keyboard.press(key);
}

/** `document.activeElement` is a visible element in the page's flow, never `body`. */
async function focusIsVisible(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    const active = document.activeElement;
    if (active === null || active === document.body || active === document.documentElement)
      return false;
    return active.closest('[hidden]') === null && active.getClientRects().length > 0;
  });
}

async function expectVisibleFocus(page: Page, after: string): Promise<void> {
  await expect
    .poll(() => focusIsVisible(page), { message: `after ${after}, focus is visible, never body` })
    .toBe(true);
}

/** Whether focus is on the first visible `h1` or `h2` inside `#main`. */
async function focusOnFirstHeading(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    const headings = [...document.querySelectorAll<HTMLElement>('#main h1, #main h2')];
    const first = headings.find(
      (heading) => heading.closest('[hidden]') === null && heading.getClientRects().length > 0,
    );
    return first !== undefined && document.activeElement === first;
  });
}

async function expectFocusOnFirstHeading(page: Page, after: string): Promise<void> {
  await expect
    .poll(() => focusOnFirstHeading(page), {
      message: `after ${after}, focus is on the first visible heading inside #main`,
    })
    .toBe(true);
}

/** The sign-in by keyboard: Tab to the address, type it, Tab, the password, Enter. */
async function keyboardSignIn(page: Page, account: Account): Promise<void> {
  await entryReady(page);
  await reach(page, page.getByTestId('entry-email'), 'entry-email');
  await page.keyboard.type(account.email);
  await page.keyboard.press('Tab');
  expect(await activeTestId(page)).toBe('entry-password');
  await page.keyboard.type(account.password);
  await page.keyboard.press('Enter');
}

/** The administrator's password by Enter, then the second factor typed and Enter. */
async function keyboardAdministrator(page: Page, administrator: Administrator): Promise<void> {
  await page.keyboard.type(administrator.email);
  await page.keyboard.press('Tab');
  expect(await activeTestId(page)).toBe('entry-password');
  await page.keyboard.type(administrator.password);
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('mfa-form')).toBeVisible();
  // The second factor is asked: focus is on its field.
  await expect(page.getByTestId('entry-factor')).toBeFocused();
  await page.keyboard.type(await realmFactorCode(administrator.totpSeed));
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('logout')).toBeVisible();
}

/** The navigation read answered 503 across a reload until `nav-error` shows; returns the
 * removal of that route. */
async function navigationRefused(page: Page): Promise<() => Promise<void>> {
  const remove = await stageJson(
    page,
    NAVIGATION,
    { code: 'DEPENDENCY_UNAVAILABLE', requestId: 'u8-a11y', retryable: true },
    503,
  );
  await page.reload();
  await expect(page.getByTestId('nav-error')).toBeVisible({ timeout: NAV_ERROR_WAIT_MS });
  return remove;
}

/** The job list read answered 503 until `jobs-error` shows; returns the route's removal. */
async function jobsRefused(page: Page): Promise<() => Promise<void>> {
  const remove = await stageJson(
    page,
    JOBS,
    { code: 'DEPENDENCY_UNAVAILABLE', requestId: 'u8-a11y', retryable: true },
    503,
  );
  await page.reload();
  await expect(page.getByTestId('logout')).toBeVisible();
  await settled(page);
  await press(page, 'nav-jobs', 'Enter');
  await expect(page.getByTestId('jobs-error')).toBeVisible();
  return remove;
}

function stagedJob(jobId: string, label: string) {
  return {
    jobId,
    kind: 'novelty',
    label,
    state: 'succeeded',
    createdAt: AT,
    updatedAt: AT,
    resultAvailable: true,
  };
}

type JobList = { items: unknown[]; nextCursor: string | null; [key: string]: unknown };

/** memberB's own first page of the list, read through the page with the view's body. */
async function memberList(page: Page): Promise<JobList> {
  const answer = await apiCall(page, JOBS, { limit: LIST_LIMIT });
  expect(answer.status, 'memberB reads the job list').toBe(200);
  return answer.body as JobList;
}

/** The list as two pages from memberB's own answer: one finished novelty job with a cursor,
 * then another and none. */
async function stageTwoPages(page: Page, own: JobList): Promise<() => Promise<void>> {
  const handler = async (route: Route) => {
    const body = (route.request().postDataJSON() ?? {}) as { cursor?: string };
    const answer = body.cursor
      ? { ...own, items: [stagedJob(JOB_TWO, '합성 작업 2')], nextCursor: null }
      : { ...own, items: [stagedJob(JOB_ONE, '합성 작업 1')], nextCursor: 'u8-a11y-next' };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: { 'cache-control': 'no-store' },
      body: JSON.stringify(answer),
    });
  };
  await page.route(onPath(JOBS), handler);
  return () => page.unroute(onPath(JOBS), handler);
}

/** The staged job's snapshot read and event stream, in the contract's shape. */
async function stageJobReads(page: Page): Promise<() => Promise<void>> {
  const snapshot = {
    jobId: JOB_ONE,
    kind: 'novelty',
    state: 'succeeded',
    seq: 1,
    revision: '1',
    acceptedAt: AT,
  };
  const read = `/api/v2/jobs/${JOB_ONE}`;
  const events = `${read}/events`;
  const removeRead = await stageJson(page, read, snapshot);
  const streamHandler = async (route: Route) => {
    await route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream', 'cache-control': 'no-store' },
      body: `id: 1\nevent: snapshot\ndata: ${JSON.stringify(snapshot)}\n\n`,
    });
  };
  await page.route(onPath(events), streamHandler);
  return async () => {
    await removeRead();
    await page.unroute(onPath(events), streamHandler);
  };
}

test('[A11Y] keyboard: every member action', async ({ page, context }) => {
  test.setTimeout(120_000);
  const member = fixtures().accounts.memberB;
  await routeProviders(context);
  await signInForm(page);
  await freshEntryMinute(page);
  await signInFormWithProviders(page);
  await settled(page);

  // The moved notice: Enter opens its details, Enter on 닫기 removes it.
  await press(page, 'moved-notice-more', 'Enter');
  await expect(page.getByTestId('moved-notice-details')).toHaveAttribute('open', '');
  await press(page, 'moved-notice-dismiss', 'Enter');
  await expect(page.getByTestId('moved-notice')).toHaveCount(0);

  // ORCID's one flow: its cancelled return, then back to the entry with no request.
  await press(page, 'provider-orcid', 'Enter');
  const cancelled = page.getByTestId('callback-cancelled');
  await expect(cancelled).toBeVisible({ timeout: 20_000 });
  const backRequests: string[] = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/v2/identity/')) {
      backRequests.push(new URL(request.url()).pathname);
    }
  });
  await press(page, 'callback-back', 'Enter');
  await expect(page.getByTestId('entry-email')).toBeVisible();
  expect(backRequests, 'callback-back sends no identity request').toEqual([]);

  // The footer's legal links.
  for (const [testId, h1] of [
    ['footer-privacy', '개인정보처리방침'],
    ['footer-terms', '서비스 이용약관'],
  ] as const) {
    await press(page, testId, 'Enter');
    await expect(page.locator('main h1')).toHaveText(h1);
    await entryReady(page);
  }

  await appearanceByKeys(page);

  // A reset for an unregistered synthetic address.
  await reach(page, page.getByTestId('entry-email'), 'entry-email');
  await page.keyboard.type(UNREGISTERED);
  await press(page, 'entry-reset', 'Enter');
  await expect(page.getByTestId('complete-entry').getByRole('status').first()).toContainText(
    '요청을 접수했습니다',
  );
  await memberSignedIn(page, member);
});

/** One key on the focused select: an arrow key, or on macOS one typed character. A Hangul
 * character is on no key of Playwright's layout, and `keyboard.type` inserts it as text,
 * which a closed select ignores; so the character is sent as the key event a keyboard
 * sends for it, with its text, through the browser's own input protocol. */
async function typeahead(page: Page, key: string): Promise<void> {
  if (key.startsWith('Arrow')) {
    await page.keyboard.press(key);
    return;
  }
  // The select joins characters typed within its typeahead window (one second in
  // Chromium) into one search, so each character is stamped a window after the last one:
  // each is a fresh search, with no waiting.
  typedAt = Math.max(Date.now() / 1000, typedAt + TYPEAHEAD_GAP_SECONDS);
  const session = await page.context().newCDPSession(page);
  try {
    const event = { key, text: key, unmodifiedText: key, timestamp: typedAt };
    await session.send('Input.dispatchKeyEvent', { type: 'keyDown', ...event });
    await session.send('Input.dispatchKeyEvent', { type: 'keyUp', key, timestamp: typedAt });
  } finally {
    await session.detach();
  }
}
const TYPEAHEAD_GAP_SECONDS = 2;
let typedAt = 0;

/** The appearance, signed out: only this browser's storage changes and no account setting
 * is written (`App.tsx:402-427`). */
async function appearanceByKeys(page: Page): Promise<void> {
  const settingsWrites: string[] = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/v2/c03/settings-update')
      settingsWrites.push(request.method());
  });
  const select = page.getByTestId('appearance-select');
  // On macOS, ArrowDown opens a native popup the headless browser never shows, so no key
  // reaches it. There the closed select is changed by typeahead: its option's first
  // character, as one key press (your answer of 2026-11-13, "Typeahead on macOS"). CI's
  // Linux run keeps the arrow keys.
  const darwin = process.platform === 'darwin';
  await reach(page, select, 'appearance-select');
  await typeahead(page, darwin ? '밝' : 'ArrowDown');
  await expect(select).toHaveValue('light');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(select, 'the closed select keeps the focus').toBeFocused();
  await typeahead(page, darwin ? '시' : 'ArrowUp');
  await expect(select).toHaveValue('system');
  await expect(page.locator('html')).not.toHaveAttribute('data-theme', /.*/);
  expect(settingsWrites, 'no settings-update is sent').toEqual([]);
}

/** memberB's actions by keyboard, from the sign-in to the sign-out. */
async function memberSignedIn(page: Page, member: Account): Promise<void> {
  await keyboardSignIn(page, member);
  await expect(page.getByTestId('logout')).toBeVisible();

  // The 320 px menu.
  await page.setViewportSize({ width: NARROW, height: VIEW_HEIGHT });
  const toggle = page.getByTestId('nav-menu-toggle');
  await press(page, 'nav-menu-toggle', 'Enter');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(toggle).toBeFocused();
  await page.setViewportSize({ width: WIDE, height: VIEW_HEIGHT });

  // The navigation's retry.
  const releaseNavigation = await navigationRefused(page);
  await releaseNavigation();
  await press(page, 'nav-retry', 'Enter');
  await expect(page.getByTestId('nav-error')).toHaveCount(0);
  await expect(page.getByTestId('nav-jobs')).toBeVisible();

  // 작업: the view, its filters and its pause.
  await press(page, 'nav-jobs', 'Enter');
  await expect(page.getByTestId('nav-jobs')).toHaveAttribute('aria-current', 'page');
  // 'all' is the default, so it is pressed last, after the others took its place.
  for (const filter of ['jobs-filter-research', 'jobs-filter-novelty', 'jobs-filter-all']) {
    await expect(page.getByTestId(filter)).toHaveAttribute('aria-pressed', 'false');
    await press(page, filter, ' ');
    await expect(page.getByTestId(filter)).toHaveAttribute('aria-pressed', 'true');
  }
  const pause = page.getByTestId('jobs-pause');
  const paused = await pause.getAttribute('aria-pressed');
  await press(page, 'jobs-pause', 'Enter');
  await expect(pause).toHaveAttribute('aria-pressed', paused === 'true' ? 'false' : 'true');

  // The list's retry.
  const releaseJobs = await jobsRefused(page);
  await releaseJobs();
  await press(page, 'jobs-retry', 'Enter');
  await expect(page.getByTestId('jobs-error')).toHaveCount(0);
  await expect(page.getByTestId('jobs-list').or(page.getByTestId('jobs-empty'))).toBeVisible();

  // Two staged pages, a staged job's status and its view.
  const own = await memberList(page);
  const removePages = await stageTwoPages(page, own);
  const removeReads = await stageJobReads(page);
  try {
    await page.reload();
    await expect(page.getByTestId('logout')).toBeVisible();
    await settled(page);
    await press(page, 'nav-jobs', 'Enter');
    await expect(page.getByTestId('jobs-item')).toHaveCount(1);
    await press(page, 'jobs-more', 'Enter');
    await expect(page.getByTestId('jobs-item')).toHaveCount(2);
    await reach(page, page.getByTestId('jobs-item-open').first(), 'the first jobs-item-open');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('jobs-selected')).toBeVisible();
    await expect(page.getByTestId('job-live-state')).toHaveText('완료');
    await press(page, 'jobs-open-view', 'Enter');
    await expect(page.getByTestId('nav-novelty')).toHaveAttribute('aria-current', 'page');
  } finally {
    await removePages();
    await removeReads();
  }

  // An empty list staged from memberB's own answer: memberB already holds J07's jobs.
  const removeEmpty = await stageJson(page, JOBS, { ...own, items: [], nextCursor: null });
  try {
    // A fresh page: the list cache would show the staged pages again first.
    await page.reload();
    await expect(page.getByTestId('logout')).toBeVisible();
    await settled(page);
    await press(page, 'nav-jobs', 'Enter');
    await expect(page.getByTestId('jobs-empty')).toBeVisible();
    await press(page, 'jobs-empty-research', 'Enter');
    await expect(page.getByTestId('nav-research')).toHaveAttribute('aria-current', 'page');
  } finally {
    await removeEmpty();
  }

  await press(page, 'logout', 'Enter');
  await expect(page.getByTestId('entry-email')).toBeVisible();
}

type DashboardItem = { capability: string; [key: string]: unknown };
type Incident = { incidentId: string; [key: string]: unknown };

function passedSet(index: number): DashboardItem {
  return {
    observationId: `00000000-0000-4000-8000-00000000d00${index}`,
    capability: 'operations.backup-set',
    component: `docsuri_u8-a11y-${index}`,
    observedAt: AT,
    revision: '1',
    status: 'available',
    evidenceRef: `backup-set:u8-a11y-${index}`,
    limitations: ['revision:1'],
    freshness: 'current',
    ageSeconds: 0,
  };
}

// The month figure the realm's own dashboard computes for one recorded month
// (`integration/test_operations_api.py:745`): 99.1% available, 210 minutes left.
const AVAILABILITY_PERMILLE = 'availability-permille:991';
const BUDGET_LEFT_SECONDS = 'budget-left-seconds:12600';

/** One `operations.availability` month item, in the dashboard's item shape (NFR9.13). */
function monthFigure(): DashboardItem {
  return {
    observationId: '00000000-0000-4000-8000-00000000d0a1',
    capability: 'operations.availability',
    component: 'ServiceOperations',
    observedAt: AT,
    revision: '1',
    status: 'available',
    evidenceRef: 'availability:u8-a11y',
    limitations: [AVAILABILITY_PERMILLE, BUDGET_LEFT_SECONDS],
    freshness: 'current',
    ageSeconds: 0,
  };
}

/** 운영's two reads staged from the realm's own answers: exactly two passed backup sets, one
 * month item (the served realm writes no availability line, so the dashboard adds none)
 * and exactly one open incident on `background.work`. */
async function stageOperations(page: Page): Promise<() => Promise<void>> {
  const dashboard = await apiCall(page, DASHBOARD, { page: { limit: 200 } });
  const incidents = await apiCall(page, INCIDENTS, { page: { limit: 50 } });
  expect(dashboard.status).toBe(200);
  expect(incidents.status).toBe(200);
  const board = dashboard.body as { items: DashboardItem[] };
  const list = incidents.body as { items: Incident[] };
  const removeDashboard = await stageJson(page, DASHBOARD, {
    ...board,
    items: [
      ...board.items.filter(
        (item) =>
          item.capability !== 'operations.backup-set' &&
          item.capability !== 'operations.availability',
      ),
      passedSet(1),
      passedSet(2),
      monthFigure(),
    ],
  });
  const removeIncidents = await stageJson(page, INCIDENTS, {
    ...list,
    items: [
      {
        incidentId: INCIDENT,
        revision: '1',
        capabilities: ['background.work'],
        correlationIds: [],
        state: 'open',
        evidenceRefs: [`opened:${AT}`],
        resolutionKind: null,
      },
    ],
  });
  return async () => {
    await removeDashboard();
    await removeIncidents();
  };
}

test('[A11Y] keyboard: every administrator action', async ({ page }) => {
  test.setTimeout(120_000);
  const administrator = fixtures().accounts.administrator;
  await entryReady(page);
  const realm = (await apiCall(page, CAPABILITIES)).body as {
    items: { capabilityId: string; reasonKey: string }[];
  };
  const removeCapabilities = await stageJson(page, CAPABILITIES, {
    ...realm,
    items: realm.items.map((item) =>
      item.capabilityId === 'account.entry'
        ? { ...item, reasonKey: 'admission-maintainer-only' }
        : item,
    ),
  });
  await page.reload();
  await expect(page.getByTestId('maintenance-banner')).toBeVisible();
  await settled(page);
  await press(page, 'maintenance-admin-sign-in', 'Enter');
  await expect(page.getByTestId('entry-email')).toBeFocused();
  // The staged public projection would read as a setup-only session after the second factor.
  await removeCapabilities();
  await keyboardAdministrator(page, administrator);

  const removeOperations = await stageOperations(page);
  const recoveries: string[] = [];
  const recoveryHandler = async (route: Route) => {
    recoveries.push(route.request().postData() ?? '');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        jobId: '00000000-0000-4000-8000-00000000e001',
        revision: '1',
        state: 'requested',
      }),
    });
  };
  await page.route(onPath(RECOVERY), recoveryHandler);
  try {
    await press(page, 'nav-operations', 'Enter');
    await expect(page.getByTestId('operations-view')).toBeVisible();
    await expect(page.getByTestId('recovery-set')).toHaveCount(0);
    await expect(page.getByTestId('incident-item')).toHaveCount(1);
    // NFR9.13 (observability-design § 12 line 199): 이번 달 가용성 reads the month figure.
    await expect(page.getByTestId('summary-availability')).toHaveText(
      '99.1% · 남은 허용 중단 210분',
    );

    // A refresh by Enter sends one new dashboard read; the pause flips by Space.
    const reads: string[] = [];
    const countRead = (request: { url: () => string }) => {
      if (new URL(request.url()).pathname === DASHBOARD) reads.push(request.url());
    };
    page.on('request', countRead);
    await press(page, 'capability-refresh', 'Enter');
    await expect.poll(() => reads.length).toBe(1);
    page.off('request', countRead);
    const pause = page.getByTestId('capability-pause');
    const paused = await pause.getAttribute('aria-pressed');
    await page.keyboard.press('Tab');
    expect(await activeTestId(page)).toBe('capability-pause');
    await page.keyboard.press(' ');
    await expect(pause).toHaveAttribute('aria-pressed', paused === 'true' ? 'false' : 'true');

    // The incident's two disabled controls are reached and described by their reasons.
    await tabTo(page, 'incident-investigate');
    await expect(page.getByTestId('incident-investigate')).toHaveAttribute('aria-disabled', 'true');
    await expect(page.getByTestId('incident-investigate')).toHaveAccessibleDescription(
      '조사는 복구 요청과 함께 시작됩니다',
    );
    await tabTo(page, 'incident-resolve');
    await expect(page.getByTestId('incident-resolve')).toHaveAttribute('aria-disabled', 'true');
    await expect(page.getByTestId('incident-resolve')).toHaveAccessibleDescription(
      '증거가 확인되면 관리자 도구에서 해결을 기록합니다',
    );
    await press(page, 'incident-recover', 'Enter');
    await expect(page.getByTestId('recovery-incident')).toHaveText(
      '사고 background.work에 대한 요청입니다',
    );

    // The operation radios and the two backup sets, by the arrow keys.
    const operation = (value: string) => page.getByTestId(`recovery-operation-${value}`);
    await reach(page, operation('backup.create'), 'recovery-operation-backup.create');
    await expect(operation('backup.create')).toBeChecked();
    await page.keyboard.press('ArrowDown');
    await expect(operation('restore.verify')).toBeChecked();
    await page.keyboard.press('ArrowDown');
    await expect(operation('restore.production')).toBeChecked();
    const sets = page.getByTestId('recovery-set');
    await expect(sets).toHaveCount(2);
    await page.keyboard.press('Tab');
    await expect(sets.first()).toBeFocused();
    await page.keyboard.press('ArrowDown');
    await expect(sets.nth(1)).toBeChecked();
    await page.keyboard.press('ArrowDown');
    await expect(sets.first()).toBeChecked();

    // restore.production: opened, acknowledged by Space, cancelled by Enter; nothing sent.
    await tabTo(page, 'recovery-open');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('recovery-confirm')).toBeVisible();
    await tabTo(page, 'recovery-acknowledge');
    await page.keyboard.press(' ');
    await expect(page.getByTestId('recovery-acknowledge')).toBeChecked();
    await tabTo(page, 'recovery-cancel');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('recovery-confirm')).toHaveCount(0);
    expect(recoveries, 'no request-recovery for the cancelled dialog').toEqual([]);

    // backup.create: opened and submitted by Enter; one request, intercepted.
    await reach(page, operation('restore.production'), 'recovery-operation-restore.production');
    await page.keyboard.press('ArrowUp');
    await page.keyboard.press('ArrowUp');
    await expect(operation('backup.create')).toBeChecked();
    await press(page, 'recovery-open', 'Enter');
    await expect(page.getByTestId('recovery-confirm')).toBeVisible();
    await tabTo(page, 'recovery-submit');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('recovery-confirm')).toHaveCount(0);
    await expect.poll(() => recoveries.length).toBe(1);
    const body = JSON.parse(recoveries[0]!) as {
      operation?: string;
      submissionId?: string;
      incidentId?: string;
    };
    expect(body.operation).toBe('backup.create');
    expect(typeof body.submissionId).toBe('string');
    expect(body.submissionId?.length ?? 0).toBeGreaterThan(0);
    expect(body.incidentId).toBe(INCIDENT);
  } finally {
    await page.unroute(onPath(RECOVERY), recoveryHandler);
    await removeOperations();
  }
});

test('[A11Y] focus stays in the dialog and lands on a visible element after every change', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const value = fixtures();
  await entryReady(page);

  // moved-notice-dismiss: the heading of the panel that holds the notice, else #main.
  const notice = page.getByTestId('moved-notice');
  expect(
    await notice.evaluate((element) => element.closest('[data-testid="complete-entry"]') !== null),
    'the notice sits inside complete-entry',
  ).toBe(true);
  const landing = await notice.evaluateHandle(
    (element) =>
      element.closest('.panel')?.querySelector('h1, h2') ?? document.getElementById('main'),
  );
  await press(page, 'moved-notice-dismiss', 'Enter');
  await expect(notice).toHaveCount(0);
  await expectVisibleFocus(page, 'moved-notice-dismiss');
  expect(
    await landing.evaluate((element) => element !== null && element === document.activeElement),
    "the notice leaves focus on its panel's heading, else #main",
  ).toBe(true);
  await landing.dispose();

  // Sign-in by Enter: the destination view's first visible heading inside #main.
  await keyboardSignIn(page, value.accounts.memberB);
  await expect(page.getByTestId('logout')).toBeVisible();
  await expectFocusOnFirstHeading(page, 'the sign-in');
  await expectVisibleFocus(page, 'the sign-in');

  // Escape on the open 320 px menu returns focus to its toggle.
  await page.setViewportSize({ width: NARROW, height: VIEW_HEIGHT });
  await press(page, 'nav-menu-toggle', 'Enter');
  await expect(page.getByTestId('nav-menu-toggle')).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('nav-menu-toggle')).toBeFocused();
  await page.setViewportSize({ width: WIDE, height: VIEW_HEIGHT });

  // nav-retry once the navigation loads.
  const releaseNavigation = await navigationRefused(page);
  await releaseNavigation();
  await press(page, 'nav-retry', 'Enter');
  await expect(page.getByTestId('nav-jobs')).toBeVisible();
  await expectVisibleFocus(page, 'nav-retry');

  // jobs-retry once the list loads.
  const releaseJobs = await jobsRefused(page);
  await releaseJobs();
  await press(page, 'jobs-retry', 'Enter');
  await expect(page.getByTestId('jobs-error')).toHaveCount(0);
  await expectVisibleFocus(page, 'jobs-retry');

  // logout from the search view.
  await press(page, 'nav-search', 'Enter');
  await expect(page.getByTestId('nav-search')).toHaveAttribute('aria-current', 'page');
  await press(page, 'logout', 'Enter');
  await expect(page.getByTestId('entry-email')).toBeVisible();
  await expectVisibleFocus(page, 'logout');

  // The administrator: the password by Enter (entry-factor), the factor by Enter.
  await reach(page, page.getByTestId('entry-email'), 'entry-email');
  await keyboardAdministrator(page, value.accounts.administrator);
  await expectFocusOnFirstHeading(page, 'the second factor');
  await expectVisibleFocus(page, 'the second factor');

  // In the recovery dialog, Tab and Shift+Tab wrap inside it; Escape returns focus.
  await press(page, 'nav-operations', 'Enter');
  await expect(page.getByTestId('operations-view')).toBeVisible();
  await press(page, 'recovery-open', 'Enter');
  const dialog = page.getByTestId('recovery-confirm');
  await expect(dialog).toBeVisible();
  const stops = dialog.locator('button:not([disabled]), input:not([disabled])');
  const last = stops.last();
  const first = stops.first();
  await reach(page, last, "the dialog's last stop");
  await page.keyboard.press('Tab');
  await expect(first).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(last).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('recovery-open')).toBeFocused();
});

// A11Y (NFR5.1, NFR5.2): every remaining screen of the complete application passes helpers'
// `checkScreen` (U8 plan Steps 96(i), 101(b)), and the legal pages and the maintenance notice
// work without scripts. A screen that needs a state the realm does not hold is staged: every
// staged answer is a `page.route` fulfilment in the page's own context, never `route.fetch`
// (its request leaves through Playwright's own client, which cannot use the pinned TLS). A
// changed read is the realm's own answer to the same read, fetched first through the page
// and served back changed; a state-changing request, and a read about what a staged request
// made, get a literal answer in the contract's shape and never reach the realm. No staged
// answer is used to assert a server's answer.
import { randomUUID } from 'node:crypto';
import { test, expect, type Page } from '@playwright/test';
import {
  apiCall,
  captureFailures,
  checkScreen,
  fixtures,
  freshEntryMinute,
  go,
  login,
  scrub,
  signInForm,
  signInFormWithProviders,
  takeViolations,
} from './helpers';
import {
  ARRIVAL_PROVIDERS,
  CANCELLED_ANSWERS,
  entryAddresses,
  expectNoticeAt,
  expectNoticeOnArrivals,
  expectNoticeOnProofForms,
  expectNoticeOnRequests,
  expectNoticeOnResetRequired,
  expectNoticeOnSecondFactor,
  expectNoticeOverSearch,
  expectPressFromArrivals,
  pressAdministratorSignIn,
  stageMaintainerOnly,
} from './notice-checks';
import {
  CAPABILITIES,
  JOB_LINK,
  changedCapabilities,
  expectOneNotice,
  holdRoute,
  openPlaceholderLink,
  realmCapabilities,
  settled,
  stageJson,
} from './staging';

test.describe.configure({ mode: 'default' });

const diagnostics = new WeakMap<Page, ReturnType<typeof captureFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureFailures(page));
});
test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

const KOREAN = { koreanNames: true };
// The two menu screens: the 320 px walk starts with the menu open and follows focus into
// the page, where the menu must have closed.
const MENU_OPEN = { koreanNames: true, menuOpen: true };
const NARROW = 320;
const WIDE = 1280;
const VIEW_HEIGHT = 720;
const NAVIGATION = '/api/v2/c01/host-resolve-navigation';
const MAINTENANCE = 'http://127.0.0.1:18111';
const REALM = 'https://127.0.0.1:18110';
const NAV_ERROR_WAIT_MS = 30_000;

type Navigation = { items: { routeId: string; available: boolean; reasonKey?: string | null }[] };

/** `checkScreen` from the top of the page: a reload restores the scroll position an earlier
 * walk left, under the sticky 320 px header, and each screen is checked as it first shows. */
async function checkFromTop(
  page: Page,
  screen: string,
  region: 'page' | 'main' | 'workspace',
  options: { koreanNames?: boolean; menuOpen?: boolean },
): Promise<void> {
  await page.evaluate(() => window.scrollTo(0, 0));
  await checkScreen(page, screen, region, options);
}

/** The 320 px navigation menu, opened. */
async function openNarrowMenu(page: Page): Promise<void> {
  await page.setViewportSize({ width: NARROW, height: VIEW_HEIGHT });
  const toggle = page.getByTestId('nav-menu-toggle');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
}

async function closeNarrowMenu(page: Page): Promise<void> {
  const toggle = page.getByTestId('nav-menu-toggle');
  await page.setViewportSize({ width: NARROW, height: VIEW_HEIGHT });
  if ((await toggle.getAttribute('aria-expanded')) === 'true') await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await page.setViewportSize({ width: WIDE, height: VIEW_HEIGHT });
}

test('[A11Y] every remaining screen: the navigation', async ({ page }) => {
  test.setTimeout(120_000);
  await signInForm(page);
  await freshEntryMinute(page);

  // navigation-loading: the navigation read is held, then continued once checked.
  const held = await holdRoute(page, NAVIGATION);
  await page.reload();
  await expect(page.getByTestId('nav-loading')).toBeVisible();
  await expect(page.getByTestId('entry-email')).toBeVisible();
  await checkFromTop(page, 'navigation-loading', 'workspace', KOREAN);
  await held.release();
  await expect(page.getByTestId('nav-loading')).toHaveCount(0);

  // navigation-error: the read is answered 503 until the check ends.
  const unrouteError = await stageJson(
    page,
    NAVIGATION,
    { code: 'DEPENDENCY_UNAVAILABLE', requestId: 'u8-a11y', retryable: true },
    503,
  );
  try {
    await page.reload();
    await expect(page.getByTestId('nav-error')).toBeVisible({ timeout: NAV_ERROR_WAIT_MS });
    await expect(page.getByTestId('nav-retry')).toBeVisible();
    await checkFromTop(page, 'navigation-error', 'workspace', KOREAN);
  } finally {
    await unrouteError();
  }

  // navigation-menu-guest: the 320 px menu open, signed out.
  await page.reload();
  await expect(page.getByTestId('nav-search')).toBeAttached();
  await settled(page);
  await openNarrowMenu(page);
  await checkFromTop(page, 'navigation-menu-guest', 'workspace', MENU_OPEN);
  await closeNarrowMenu(page);

  // navigation-disabled-entry: memberB, with `library` unavailable and stale.
  await login(page, fixtures().accounts.memberB);
  const realm = await apiCall(page, NAVIGATION, { routeId: 'search' });
  expect(realm.status).toBe(200);
  const answer = realm.body as Navigation;
  expect(answer.items.some((item) => item.routeId === 'library')).toBe(true);
  const unrouteStale = await stageJson(page, NAVIGATION, {
    ...answer,
    items: answer.items.map((item) =>
      item.routeId === 'library'
        ? { ...item, available: false, reasonKey: 'nav.capabilityStale' }
        : item,
    ),
  });
  try {
    await page.reload();
    await expect(page.getByTestId('logout')).toBeVisible();
    await expect(page.getByTestId('nav-library')).toHaveAttribute('aria-disabled', 'true');
    await expect(page.getByTestId('nav-reason-library')).toHaveText(
      '상태 정보가 오래되어 다시 확인하는 중입니다',
    );
    await settled(page);
    await checkFromTop(page, 'navigation-disabled-entry', 'workspace', KOREAN);
  } finally {
    await unrouteStale();
  }

  // navigation-menu-member: the 320 px menu open, signed in.
  await page.reload();
  await expect(page.getByTestId('logout')).toBeVisible();
  await expect(page.getByTestId('nav-library')).not.toHaveAttribute('aria-disabled', 'true');
  await settled(page);
  await openNarrowMenu(page);
  await checkFromTop(page, 'navigation-menu-member', 'workspace', MENU_OPEN);
  await closeNarrowMenu(page);
});

test('[A11Y] every remaining screen: the entry and sign-in', async ({ page }) => {
  test.setTimeout(120_000);
  await signInFormWithProviders(page);
  await settled(page);

  // provider-start-limit: the realm's own capabilities; the begin is answered 429.
  const unrouteBegin = await stageJson(
    page,
    '/api/v2/c02/access-begin-identity-flow',
    {
      code: 'RATE_LIMITED',
      requestId: 'u8-a11y-start-limit',
      retryable: true,
      messageKey: 'identity-start.site-places',
      retryAfterSeconds: 30,
    },
    429,
  );
  try {
    await page.getByTestId('provider-google').click();
    await expect(page.getByTestId('complete-entry').getByRole('alert')).toContainText(
      '지금 Google·ORCID 로그인을 하려는 사람이 많아요. 30초 뒤에 다시 시도하거나 이메일로 로그인해 주세요',
    );
    await checkFromTop(page, 'provider-start-limit', 'workspace', KOREAN);
  } finally {
    await unrouteBegin();
  }

  // moved-notice-open: the notice's details open.
  await signInForm(page);
  await settled(page);
  await page.getByTestId('moved-notice-more').click();
  await expect(page.getByTestId('moved-notice-details')).toHaveAttribute('open', '');
  await checkFromTop(page, 'moved-notice-open', 'workspace', KOREAN);

  // entry-maintenance-banner: admission is maintainer-only.
  const realm = await realmCapabilities(page);
  const unrouteMaintenance = await stageJson(
    page,
    CAPABILITIES,
    changedCapabilities(realm, { 'account.entry': { reasonKey: 'admission-maintainer-only' } }),
  );
  try {
    await page.reload();
    await expect(page.getByTestId('maintenance-banner')).toBeVisible();
    await settled(page);
    await checkFromTop(page, 'entry-maintenance-banner', 'workspace', KOREAN);
    // callback-maintenance-banner: the identity arrival page shows it too (NFR1.3).
    await page.goto('/sign-in/callback/google?error=access_denied&state=s');
    await expect(
      page.getByTestId('callback-cancelled').getByTestId('maintenance-banner'),
    ).toBeVisible();
    await settled(page);
    await checkFromTop(page, 'callback-maintenance-banner', 'workspace', KOREAN);
    // The next block's reload finds the entry.
    await signInForm(page);
  } finally {
    await unrouteMaintenance();
  }

  // provider-unavailable: Google and Resend do not serve.
  const unrouteProviders = await stageJson(
    page,
    CAPABILITIES,
    changedCapabilities(realm, {
      'provider.google': { state: 'unavailable' },
      // Signed out, the realm gives the mail provider as serving or not serving alone.
      'provider.resend': { state: 'unavailable', reasonKey: 'provider-unreachable' },
    }),
  );
  try {
    await page.reload();
    await expect(page.getByTestId('provider-google')).toBeDisabled();
    // The reason is tied to the button as its description.
    await expect(page.getByTestId('provider-google')).toHaveAccessibleDescription(
      '지금은 Google 로그인을 사용할 수 없습니다. 비밀번호로 로그인해 주세요.',
    );
    await expect(page.getByTestId('provider-notice-mail')).toHaveText(
      '지금은 이메일을 보낼 수 없습니다. 나중에 다시 시도해 주세요.',
    );
    await settled(page);
    await checkFromTop(page, 'provider-unavailable', 'workspace', KOREAN);
  } finally {
    await unrouteProviders();
  }

  // callback-pending: the callback read is held, then aborted, so nothing reaches the realm.
  const callback = await holdRoute(page, '/api/v2/identity/callback/google');
  try {
    await page.goto('/sign-in/callback/google?flow=f&state=s&code=c');
    await expect(page.getByTestId('callback-page')).toContainText('로그인을 확인하고 있습니다');
    await expect.poll(() => callback.count()).toBe(1);
    await checkFromTop(page, 'callback-pending', 'workspace', KOREAN);
  } finally {
    await callback.abort();
  }

  // mfa-form: the administrator's password step only; no factor is spent.
  const administrator = fixtures().accounts.administrator;
  await signInForm(page);
  await page.getByTestId('entry-email').fill(administrator.email);
  await page.getByTestId('entry-password').fill(administrator.password);
  await page.getByTestId('entry-submit').click();
  await expect(page.getByTestId('mfa-form')).toBeVisible();
  await checkFromTop(page, 'mfa-form', 'workspace', KOREAN);
});

test('[A11Y] every remaining screen: the signed-out proof forms', async ({ page }) => {
  test.setTimeout(120_000);
  for (const [path, screen] of [
    ['/account/password-reset', 'proof-password-reset'],
    ['/account/verify-email', 'proof-verify-email'],
    ['/account/reactivate', 'proof-reactivate'],
  ] as const) {
    await openPlaceholderLink(page, path);
    await expect(page.getByTestId('proof-form')).toBeVisible();
    await settled(page);
    // Nothing is submitted.
    await checkFromTop(page, screen, 'workspace', KOREAN);
  }
});

const CALLBACK = '/api/v2/identity/callback/google';
const ARRIVAL = '/sign-in/callback/google?flow=f&state=s&code=c';

test('[A11Y] the maintainer-only notice: the pending and failed arrivals, a proof form and a job link', async ({
  page,
}) => {
  // NFR1.3 (L2-10, L3-9): on staged maintainer-only capabilities, each page shows exactly
  // one notice inside its panel; the identity read never reaches the realm.
  test.setTimeout(120_000);
  await signInForm(page);
  await settled(page);
  const realm = await realmCapabilities(page);
  const unrouteMaintenance = await stageJson(
    page,
    CAPABILITIES,
    changedCapabilities(realm, { 'account.entry': { reasonKey: 'admission-maintainer-only' } }),
  );
  try {
    // Pending: the callback read is held, then aborted.
    const held = await holdRoute(page, CALLBACK);
    try {
      await page.goto('about:blank');
      await page.goto(ARRIVAL);
      const arrival = page.getByTestId('callback-page');
      await expect(arrival).toContainText('로그인을 확인하고 있습니다');
      await expect.poll(() => held.count()).toBe(1);
      await expectOneNotice(page, arrival);
      await arrival.getByTestId('maintenance-admin-sign-in').click();
      await expect(page.getByTestId('complete-entry').getByTestId('sign-in-form')).toBeVisible();
      await expect(page.getByTestId('maintenance-banner')).toHaveCount(1);
      await expect(page.getByTestId('entry-email')).toBeFocused();
    } finally {
      await held.abort();
    }

    // Failed: the callback read answers a literal 503 in the error envelope's shape.
    const unrouteFailed = await stageJson(
      page,
      CALLBACK,
      { code: 'DEPENDENCY_UNAVAILABLE', requestId: 'u8-a11y-callback-failed', retryable: true },
      503,
    );
    try {
      await page.goto('about:blank');
      await page.goto(ARRIVAL);
      const failed = page.getByTestId('callback-page');
      await expect(failed.getByTestId('callback-back')).toBeVisible();
      await expectOneNotice(page, failed);
    } finally {
      await unrouteFailed();
    }

    // A proof form: nothing is submitted.
    await openPlaceholderLink(page, '/account/verify-email');
    await expect(page.getByTestId('complete-entry').getByTestId('proof-form')).toBeVisible();
    await settled(page);
    await expectOneNotice(page, page.getByTestId('complete-entry'));

    // A job link, signed out: the sign-in form with the notice.
    await page.goto('about:blank');
    await page.goto(JOB_LINK);
    await expect(page.getByTestId('complete-entry').getByTestId('sign-in-form')).toBeVisible();
    await settled(page);
    await expectOneNotice(page, page.getByTestId('complete-entry'));
  } finally {
    await unrouteMaintenance();
  }
});

// --- NFR1.3 on every address and form of the shell (U8 plan Step 170(a); L4-15) ------------

// The checks themselves are in `notice-checks.ts`, so this file stays under 800 lines.

test('[A11Y] the maintainer-only notice: every address of the shell', async ({ page }) => {
  // NFR1.3: on staged maintainer-only capabilities, every address of the workspace shell
  // shows exactly one notice inside its panel. No screen is captured.
  test.setTimeout(180_000);
  const unrouteMaintenance = await stageMaintainerOnly(page);
  try {
    for (const address of entryAddresses()) await expectNoticeAt(page, address, 'complete-entry');
    for (const provider of ARRIVAL_PROVIDERS) {
      for (const answer of CANCELLED_ANSWERS)
        await expectNoticeAt(page, `/sign-in/callback/${provider}?${answer}`, 'callback-cancelled');
      await expectNoticeOnArrivals(page, provider);
    }
  } finally {
    await unrouteMaintenance();
  }
});

test('[A11Y] the maintainer-only notice: every form of the entry, and its 관리자 로그인', async ({
  page,
}) => {
  // NFR1.3, BR6.4: every form of the entry keeps the one notice, and 관리자 로그인 leads to
  // the sign-in form with the address field focused from every kind of panel.
  test.setTimeout(180_000);
  const unrouteMaintenance = await stageMaintainerOnly(page);
  try {
    await page.reload();
    await expectOneNotice(page, page.getByTestId('complete-entry'));
    await pressAdministratorSignIn(page);
    await expectNoticeOnRequests(page);
    await expectNoticeOnSecondFactor(page);
    await expectNoticeOnProofForms(page);
    await expectNoticeOnResetRequired(page);
    await expectPressFromArrivals(page);
    await expectNoticeOverSearch(page);
  } finally {
    await unrouteMaintenance();
  }
});

const RETAINED_UNTIL = '2026-12-12T00:00:00Z';
const LIFECYCLE_ID = '00000000-0000-4000-8000-0000000000a1';

test('[A11Y] every remaining screen: account and research', async ({ page }) => {
  test.setTimeout(120_000);
  await login(page, fixtures().accounts.memberB);

  // proof-email-change: shown only in a session (Step 91(l)); nothing is submitted.
  await openPlaceholderLink(page, '/account/email-change');
  await expect(page.getByTestId('email-change-proof')).toBeVisible();
  await expect(page.getByTestId('proof-binding-note')).toBeVisible();
  await settled(page);
  await checkFromTop(page, 'proof-email-change', 'workspace', KOREAN);
  await page.getByTestId('proof-back').click();
  await expect(page.getByTestId('email-change-proof')).toHaveCount(0);

  // lifecycle-retained: the lifecycle request's answers are staged, so nothing reaches the
  // realm; its inspection reports one scope kept by policy.
  const unroute = [
    await stageJson(page, '/api/v2/c02/access-prepare-lifecycle', {
      confirmationRef: 'u8-a11y-confirmation',
      action: 'withdraw',
    }),
    await stageJson(page, '/api/v2/c02/lifecycle-request', {
      lifecycleRequestId: LIFECYCLE_ID,
      state: 'accepted',
      revocation: 'pending',
      participants: [],
    }),
    await stageJson(page, '/api/v2/c02/lifecycle-inspect', {
      lifecycleRequestId: LIFECYCLE_ID,
      state: 'running',
      revocation: 'complete',
      participants: [
        {
          participantId: 'service-operations',
          state: 'complete',
          scopes: [
            {
              scope: 'backups',
              disposition: 'retained_by_policy',
              reasonKey: 'backup-retention',
              retainedUntil: RETAINED_UNTIL,
            },
          ],
        },
      ],
    }),
  ];
  try {
    await go(page, 'account');
    await expect(page.getByTestId('nav-account')).toHaveAttribute('aria-current', 'page');
    await page.locator('#main summary', { hasText: '탈퇴와 데이터 삭제' }).click();
    // Generated per run (L1-36); it never reaches the realm while the routes are staged.
    await page.locator('#lifecycle-proof').fill(`u8-${randomUUID()}`);
    await page.getByRole('button', { name: '처리 범위 확인 준비' }).click();
    await page.getByRole('button', { name: '확인하고 접수' }).click();
    await expect(page.getByText('정책에 따라 보관되는 부분이 있어요')).toBeVisible();
    await expect(page.getByTestId('logout')).toBeVisible();
    await checkFromTop(page, 'lifecycle-retained', 'workspace', KOREAN);
  } finally {
    for (const remove of unroute) await remove();
  }

  // research-limit: a new research context whose question is 33,000 UTF-8 bytes against
  // the realm policy's 32,768.
  await go(page, 'research');
  const workspace = page.getByTestId('workspace-research');
  await expect(workspace).toBeVisible();
  await workspace.getByRole('textbox', { name: '새 연구 이름' }).fill('접근성 점검');
  await workspace.getByRole('button', { name: '새 연구 시작' }).click();
  const question = workspace.getByRole('textbox', { name: '연구 질문' });
  await expect(question).toBeVisible({ timeout: 20_000 });
  await question.fill('가'.repeat(11_000));
  await expect(workspace.locator('p', { hasText: '입력 용량 33000' })).toHaveText(
    '입력 용량 33000 / 32768 UTF-8 바이트 · 한도를 초과했어요. 입력을 줄여 주세요.',
  );
  await checkFromTop(page, 'research-limit', 'workspace', KOREAN);
});

test('[A11Y] every remaining screen: the maintenance server', async ({ page }) => {
  test.setTimeout(120_000);
  for (const [path, screen, status] of [
    ['/', 'maintenance-18111', 503],
    ['/privacy', 'privacy-18111', 200],
    ['/terms', 'terms-18111', 200],
  ] as const) {
    const answer = await page.goto(`${MAINTENANCE}${path}`);
    expect(answer?.status(), `${path} on 18111`).toBe(status);
    await checkFromTop(page, screen, 'page', KOREAN);
  }
});

const STATIC_PAGES = [
  {
    url: `${REALM}/privacy`,
    status: 200,
    h1: '개인정보처리방침',
    text: '서비스는 다음의 개인정보를 수집합니다.',
  },
  { url: `${REALM}/terms`, status: 200, h1: '서비스 이용약관', text: '시행일: 2026년 7월 8일' },
  {
    url: `${MAINTENANCE}/privacy`,
    status: 200,
    h1: '개인정보처리방침',
    text: '서비스는 다음의 개인정보를 수집합니다.',
  },
  {
    url: `${MAINTENANCE}/terms`,
    status: 200,
    h1: '서비스 이용약관',
    text: '시행일: 2026년 7월 8일',
  },
  {
    url: `${MAINTENANCE}/`,
    status: 503,
    h1: 'DocSuri',
    text: 'DocSuri를 점검하고 있습니다. 잠시 후 다시 접속해 주세요.',
  },
] as const;

/** The stylesheets a raw page links, as absolute addresses. */
function linkedStylesheets(body: string, base: string): string[] {
  const links = body.match(/<link\b[^>]*>/gi) ?? [];
  return links
    .filter((tag) => /\brel\s*=\s*["']?stylesheet/i.test(tag))
    .map((tag) => /\bhref\s*=\s*["']([^"']+)["']/i.exec(tag)?.[1])
    .filter((href): href is string => typeof href === 'string')
    .map((href) => new URL(href, base).toString());
}

test.describe('without scripts', () => {
  test.use({ javaScriptEnabled: false });

  test('[A11Y] without scripts: the legal pages and the maintenance notice', async ({ page }) => {
    test.setTimeout(120_000);
    // Chromium shows a stylesheet opened as a document in its own text view, a `<pre>` with
    // an inline style, which the server's policy refuses. Each refusal is attributed to the
    // document that raised it (its console location, else the document being opened): a
    // legal page or the notice may raise none, and a stylesheet view only that inline-style
    // refusal. Only those are then taken; any other fails here.
    const refusals: { document: string; text: string }[] = [];
    let opening = '';
    page.on('console', (message) => {
      if (message.type() !== 'error' || !message.text().includes('Content Security Policy')) return;
      refusals.push({ document: message.location().url || opening, text: message.text() });
    });
    const sheetViews = new Set<string>();
    for (const item of STATIC_PAGES) {
      opening = item.url;
      const answer = await page.goto(item.url);
      expect(answer?.status(), item.url).toBe(item.status);
      await expect(page.locator('h1')).toHaveText(item.h1);
      await expect(page.getByText(item.text, { exact: false }).first()).toBeVisible();
      const body = (await answer?.text()) ?? '';
      expect(/<script/i.test(body), `${item.url} holds no script`).toBe(false);
      expect(/\son[a-z]+\s*=/i.test(body), `${item.url} holds no on… attribute`).toBe(false);
      expect(/javascript:/i.test(body), `${item.url} holds no javascript: address`).toBe(false);
      const sheets = linkedStylesheets(body, item.url);
      expect(sheets.length, `${item.url} links a stylesheet`).toBeGreaterThan(0);
      for (const sheet of sheets) {
        expect(new URL(sheet).origin, `${sheet} is on the same server`).toBe(
          new URL(item.url).origin,
        );
        // Read by page.goto: page.request cannot reach the pinned origin.
        opening = sheet;
        sheetViews.add(sheet);
        const style = await page.goto(sheet);
        expect(style?.status(), sheet).toBe(200);
        expect((await style?.allHeaders())?.['content-type'] ?? '', sheet).toMatch(/^text\/css/);
      }
    }
    opening = 'about:blank';
    await page.goto('about:blank');
    const pageRefusals = refusals.filter((refusal) => !sheetViews.has(refusal.document));
    expect(
      pageRefusals.map((refusal) => `${refusal.document}: ${refusal.text.slice(0, 120)}`),
      'no legal page or maintenance notice raises a policy refusal',
    ).toEqual([]);
    const otherViewerRefusals = refusals.filter(
      (refusal) => !refusal.text.startsWith('Refused to apply inline style'),
    );
    expect(
      otherViewerRefusals.map((refusal) => refusal.text.slice(0, 120)),
      "a stylesheet's text view raises only its inline-style refusal",
    ).toEqual([]);
    expect(takeViolations(page)).toHaveLength(refusals.length);
  });
});

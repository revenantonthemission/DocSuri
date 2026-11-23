// A11Y (NFR5.1, NFR5.2): helpers' `checkScreen` (U8 plan Step 96(i)) on every signed-in
// screen of the complete application (Step 101(a)): axe with wcag2a, wcag2aa, wcag21aa and
// wcag22aa at 1280 and 320 CSS px in both colour schemes, 24 by 24 targets, `lang` `ko`,
// Hangul control names, the 320 px reflow with its capture, the Tab walk at both widths and
// one read of the page's live regions, then its record. Beside them: focus after each route
// change (L1-25) and what the announcer says when a capability goes stale and comes back.
// Step 99(h)'s split rule through Step 101(e) moved the signed-out and keyboard tests into
// `accessibility-signed-out.spec.ts` (this phase peaked at 1,031,192,576 B, above 90% of
// 1 GiB); this phase keeps the member and the administrator.
import { test, expect, type Page } from '@playwright/test';
import {
  captureFailures,
  checkScreen,
  fixtures,
  freshEntryMinute,
  go,
  harness,
  login,
  loginAdministrator,
  scrub,
  signInForm,
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

const KOREAN = { koreanNames: true };
// The producers renew within twice the realm's 6 s freshness bound plus a renewal.
const STALE_WAIT_MS = 30_000;
const FOCUS_WAIT_MS = 10_000;
const MEMBER_VIEWS = [
  'library',
  'research',
  'novelty',
  'jobs',
  'topics',
  'export',
  'settings',
  'usage',
  'account',
] as const;

/** Whether focus is on the first visible `h1` or `h2` inside `#main`. A heading under a
 * `hidden` ancestor never counts (`research-workspace.tsx:142` hides the inactive one). */
async function focusOnFirstHeading(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    const headings = [...document.querySelectorAll<HTMLElement>('#main h1, #main h2')];
    const first = headings.find(
      (heading) => heading.closest('[hidden]') === null && heading.getClientRects().length > 0,
    );
    return first !== undefined && document.activeElement === first;
  });
}

async function expectFocusOnFirstHeading(page: Page, where: string): Promise<void> {
  await expect
    .poll(() => focusOnFirstHeading(page), {
      message: `${where}: focus is on the first visible heading inside #main`,
      timeout: FOCUS_WAIT_MS,
    })
    .toBe(true);
}

test('[A11Y] a member: every owner view, with its live regions', async ({ page }) => {
  test.setTimeout(150_000);
  await signInForm(page);
  // This spec's counted entry operations fall in a minute of their own (Step 101(f)).
  await freshEntryMinute(page);
  await login(page, fixtures().accounts.memberB);
  await go(page, 'search');
  await page.getByTestId('search-query').fill('attention transformer');
  await page.getByTestId('search-submit').click();
  await expect(page.getByTestId('result-row').first()).toBeVisible({ timeout: 20_000 });
  // The whole page once for the member: the header and the footer are checked too.
  await checkScreen(page, 'search', 'page', KOREAN);
  await page.getByTestId('result-row').first().getByTestId('result-open').click();
  await expect(page.getByTestId('paper-workspace')).toBeVisible();
  await expectFocusOnFirstHeading(page, 'paper');
  await checkScreen(page, 'paper', 'workspace', KOREAN);
  for (const route of MEMBER_VIEWS) {
    await go(page, route);
    await expect(page.getByTestId(`nav-${route}`)).toHaveAttribute('aria-current', 'page');
    await expectFocusOnFirstHeading(page, route);
    // The view has finished its first read before it is checked.
    await expect(page.locator('#main [aria-busy="true"]')).toHaveCount(0);
    await checkScreen(page, route, 'workspace', KOREAN);
  }
});

/** Records every text the announcer is given, one per message (each is a new keyed span). */
async function watchAnnouncer(page: Page): Promise<void> {
  await page.evaluate(() => {
    const region = document.querySelector('[data-testid="announcer"]');
    if (region === null) throw new Error('no announcer');
    const texts: string[] = [];
    Reflect.set(window, '__u8Announced', texts);
    new MutationObserver((mutations) => {
      for (const mutation of mutations)
        for (const node of mutation.addedNodes) {
          const text = node.textContent ?? '';
          if (text !== '') texts.push(text);
        }
    }).observe(region, { childList: true, subtree: true, characterData: false });
  });
}

async function announced(page: Page): Promise<string[]> {
  return page.evaluate(() => [...((Reflect.get(window, '__u8Announced') as string[]) ?? [])]);
}

/** Whether a live region other than the announcer holds `text` (checked as a boolean). */
async function otherRegionHolds(page: Page, text: string): Promise<boolean> {
  return page.evaluate(
    (needle) =>
      [...document.querySelectorAll('[aria-live], [role="status"], [role="alert"]')]
        .filter((element) => element.getAttribute('data-testid') !== 'announcer')
        .some((element) => (element.textContent ?? '').includes(needle)),
    text,
  );
}

/** Presses `capability-refresh` until the row's state reads `state`, within a bound. */
async function refreshUntil(page: Page, capability: string, state: string): Promise<void> {
  const cell = page.getByTestId(`capability-row-${capability}`).locator('td').first();
  await expect
    .poll(
      async () => {
        await page.getByTestId('capability-refresh').click();
        return (await cell.textContent())?.includes(state) ?? false;
      },
      { timeout: STALE_WAIT_MS, intervals: [1_000, 2_000] },
    )
    .toBe(true);
}

test('[A11Y] the administrator: operations and its recovery dialog', async ({ page }) => {
  test.setTimeout(120_000);
  await loginAdministrator(page, fixtures().accounts.administrator);
  await go(page, 'operations');
  await expect(page.getByTestId('operations-view')).toBeVisible();
  await expect(page.getByTestId('capability-table')).toBeVisible();
  await expectFocusOnFirstHeading(page, '운영');
  // The whole page once for the administrator.
  await checkScreen(page, 'operations', 'page', KOREAN);
  await page.getByTestId('recovery-open').click();
  await expect(page.getByTestId('recovery-submit')).toBeVisible();
  await checkScreen(page, 'recovery-dialog', 'workspace', KOREAN);
  // Escape closes the dialog and returns focus to the control that opened it.
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('recovery-submit')).toHaveCount(0);
  await expect(page.getByTestId('recovery-open')).toBeFocused();

  // A capability gone stale is announced once, through the announcer alone.
  await watchAnnouncer(page);
  const stale = 'background.work 오래됨';
  const fresh = 'background.work 정상';
  harness('service', { name: 'workers', action: 'stop' });
  try {
    harness('advance-clock', { seconds: 20 });
    await refreshUntil(page, 'background.work', '오래됨');
    await expect
      .poll(async () => (await announced(page)).filter((text) => text.includes(stale)).length, {
        message: 'one announcement names background.work 오래됨',
      })
      .toBe(1);
    expect(await otherRegionHolds(page, stale), 'no other live region holds it').toBe(false);
  } finally {
    harness('service', { name: 'workers', action: 'start' });
  }
  // Later than the stale announcement: every message after it.
  const before = (await announced(page)).findIndex((text) => text.includes(stale)) + 1;
  await refreshUntil(page, 'background.work', '정상');
  await expect
    .poll(
      async () =>
        (await announced(page)).slice(before).filter((text) => text.includes(fresh)).length,
      { message: 'one later announcement names background.work 정상' },
    )
    .toBe(1);
});

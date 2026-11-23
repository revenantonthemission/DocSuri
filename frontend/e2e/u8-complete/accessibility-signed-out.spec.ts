// A11Y (NFR5.1, NFR5.2), phase `accessibility-signed-out`: the signed-out and keyboard
// half of Step 101(a), split from `accessibility.spec.ts` by Step 99(h)'s split rule
// through Step 101(e) (that phase peaked at 1,031,192,576 B, above 90% of 1 GiB). Helpers'
// `checkScreen` (Step 96(i)) runs on each screen: axe with wcag2a, wcag2aa, wcag21aa and
// wcag22aa at 1280 and 320 CSS px in both colour schemes, 24 by 24 targets, `lang` `ko`,
// Hangul control names, the 320 px reflow with its capture, the Tab walk at both widths and
// one read of the page's live regions, then its record. Beside them: the skip link, the
// sign-in by keyboard alone, focus after a route change (L1-25) and the one announcer
// outside `#main` (L1-26).
import AxeBuilder from '@axe-core/playwright';
import { test, expect, type Page } from '@playwright/test';
import {
  captureFailures,
  checkScreen,
  fixtures,
  freshEntryMinute,
  scrub,
  signedInNavigation,
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
const FOCUS_WAIT_MS = 10_000;

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

/** The live regions outside `#main` by test id, never their text. */
async function liveRegionsOutsideMain(page: Page): Promise<(string | null)[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll('[aria-live], [role="status"], [role="alert"]')]
      .filter((element) => element.closest('#main') === null)
      .map((element) => element.getAttribute('data-testid')),
  );
}

/** Axe's `color-contrast` on a legal page's header link `검색` in the dark scheme: evaluated
 * (not inapplicable) and passing 4.5:1 (Step 91(h)'s `legal.css`). */
async function expectHeaderLinkContrastInDark(page: Page, path: string): Promise<void> {
  await page.emulateMedia({ colorScheme: 'dark' });
  const result = await new AxeBuilder({ page })
    .include('main header a')
    .withRules(['color-contrast'])
    .analyze();
  await page.emulateMedia({ colorScheme: null });
  const evaluated = [...result.passes, ...result.violations].some(
    (rule) => rule.id === 'color-contrast',
  );
  expect(evaluated, `${path}: color-contrast is evaluated on 검색 in dark`).toBe(true);
  expect(
    result.violations.map((violation) => violation.id),
    `${path}: 검색 reaches 4.5:1 in dark`,
  ).toEqual([]);
}

test('[A11Y] signed out: the entry, the legal pages and a cancelled provider return', async ({
  page,
}) => {
  await signInForm(page);
  // This spec's counted entry operations fall in a minute of their own (Step 101(f)).
  await freshEntryMinute(page);
  // The whole page once signed out: the skip link, header, navigation and footer too.
  await checkScreen(page, 'entry', 'page', KOREAN);
  for (const [path, screen] of [
    ['/privacy', 'privacy'],
    ['/terms', 'terms'],
  ] as const) {
    await page.goto(path);
    await expect(page.locator('main h1')).toBeVisible();
    await expect(page.getByRole('link', { name: '검색', exact: true })).toBeVisible();
    await expectHeaderLinkContrastInDark(page, path);
    // The static pages' <main> has no id.
    await checkScreen(page, screen, 'main', KOREAN);
  }
  await page.goto('/sign-in/callback/orcid?error=access_denied&state=s');
  await expect(page.getByTestId('callback-cancelled')).toBeVisible();
  await checkScreen(page, 'callback-cancelled', 'workspace', KOREAN);
});

test('[A11Y] keyboard: skip to main, sign in with the keyboard alone, and move between views', async ({
  page,
}) => {
  const member = fixtures().accounts.memberB;
  await signInForm(page);
  // The skip link is the first stop in the document's tab order (nothing precedes it),
  // and Enter on it moves focus to the main region.
  const skip = page.getByRole('link', { name: '본문으로 건너뛰기' });
  await skip.focus();
  await page.keyboard.press('Shift+Tab');
  await expect(skip).not.toBeFocused();
  await page.keyboard.press('Tab');
  await expect(skip).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main')).toBeFocused();
  // The form: type, tab and Enter only.
  await page.getByTestId('entry-email').focus();
  await page.keyboard.type(member.email);
  await page.keyboard.press('Tab');
  await expect(page.getByTestId('entry-password')).toBeFocused();
  await page.keyboard.type(member.password);
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('logout')).toBeVisible();
  await signedInNavigation(page);
  // Once the navigation has loaded, the announcer is the only live region outside #main.
  await expect(page.getByTestId('nav-loading')).toHaveCount(0);
  expect(await liveRegionsOutsideMain(page), 'only the announcer outside #main').toEqual([
    'announcer',
  ]);
  // A navigation entry opens its view from the keyboard; focus lands on the view's first
  // heading, the 작업 heading (L1-25).
  await page.getByTestId('nav-jobs').focus();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('nav-jobs')).toHaveAttribute('aria-current', 'page');
  await expect(
    page.locator('#main').getByRole('heading', { name: '작업', level: 2 }),
  ).toBeVisible();
  await expectFocusOnFirstHeading(page, '작업');
  await expect(
    page.locator('#main').getByRole('heading', { name: '작업', level: 2 }),
  ).toBeFocused();
  // Enter on the skip link still focuses #main.
  await skip.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main')).toBeFocused();
});

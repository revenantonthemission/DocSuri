// J10 (BR8.1–BR8.14, RC1): the synthetic v1 migrated through the cutover stage, its
// production stand-in and the public address; then the migrated accounts' first sign-ins
// in a real browser. The stage (`cutover_stage.py`) runs the migration and the switch as
// the operator, on your decisions (the harness acting as you); the browser is a person.
// - a dry run's report, as the stage reads it, names every misfit reason of the functional
//   spec's table, reached its report (the tool refuses a changed idempotency pass), and
//   reconciles; this first test opens no page;
// - the final run's report reconciles; with the cutover tool's profile at maintainer-only,
//   the administrator signs in, through the consent step, to the second factor's setup.
//   The stage's host is composed from the realm's synthetic profile, which states no
//   admission, so no test here shows that a member is held or that a notice is shown in
//   that window (a stated limit); the second test's title keeps "let in first" because
//   `required_items.py` pins it;
// - once the tool's profile says open, a migrated member meets the consent step and an
//   account with a legacy password meets reset-required.
import { test, expect, type Page } from '@playwright/test';
import { captureFailures, checkScreen, harness, scrub, signInForm, v1Dataset } from './helpers';

test.describe.configure({ mode: 'serial' });

const diagnostics = new WeakMap<Page, ReturnType<typeof captureFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureFailures(page));
});
test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});
test.afterAll(() => {
  harness('stage', { word: 'end' });
});

type Report = {
  runId: string;
  kind: string;
  state: string;
  reconciles: boolean | null;
  kinds: { kind: string; imported: number; reconciles: boolean }[];
  misfits: { kind: string; reasonKey: string; count: number }[];
};

// The functional spec's misfit table, its 26 kind:reason pairs copied literally
// (`functional-spec.md:253-268`), never derived from the tool's own lists (U8 plan
// Step 102(a)): 15 named pairs, then the 11 kinds outside Q13's scope.
const MISFITS = [
  'account:required-field-without-source',
  'account:unverified-in-v1',
  'account:locked-in-v1',
  'account:closed-in-v1',
  'account:no-email',
  'account:email-case-conflict',
  'identity-link:unconfirmed-link',
  'identity-link:duplicate-provider-link',
  'preferences:no-v2-home',
  'paper:exceeds-v2-limit',
  'paper:ineligible-in-v2',
  'paper-content:content-shape-unconvertible',
  'paper-embedding:embedding-provenance-unproven',
  'paper-figure:no-v2-home',
  'saved-paper:duplicate-by-version',
  'followed-topic:not-in-scope',
  'digest-settings:not-in-scope',
  'glossary:not-in-scope',
  'saved-search:not-in-scope',
  'search-history:not-in-scope',
  'behavior-event:not-in-scope',
  'plan-record:not-in-scope',
  'private-upload:not-in-scope',
  'research-history:not-in-scope',
  'novelty-history:not-in-scope',
  'summary:not-in-scope',
];
// Two synthetic accounts each (the deactivated and the pending-deletion account; the two
// accounts whose emails differ only in case).
const COUNTED_TWICE = ['account:closed-in-v1', 'account:email-case-conflict'];
const IMPORTING_KINDS = ['account', 'identity-link', 'preferences', 'saved-paper', 'paper'];

/** Whether focus is on the first visible `h1` or `h2` inside `#main` (never `body`); a
 * heading under a `hidden` ancestor never counts. */
async function focusOnFirstHeading(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    const main = document.querySelector('#main');
    if (main === null) return false;
    const first = [...main.querySelectorAll('h1, h2')].find((heading) => {
      const box = heading.getBoundingClientRect();
      return box.width > 0 && box.height > 0 && heading.closest('[hidden]') === null;
    });
    return first !== undefined && document.activeElement === first;
  });
}

function stage<T>(word: string, document: object = {}): T {
  return harness<T>('stage', { word, ...document });
}

async function firstSignIn(page: Page, email: string, password: string) {
  await signInForm(page);
  await page.getByTestId('entry-email').fill(email);
  await page.getByTestId('entry-password').fill(password);
  await page.getByTestId('entry-submit').click();
}

async function giveConsents(page: Page) {
  await expect(page.getByTestId('consent-step')).toBeVisible();
  await page.getByTestId('consent-local-research').check();
  await page.getByTestId('consent-continue').click();
}

test('[J10] the dry run meets every misfit reason, changes nothing on its second pass, and reconciles', async () => {
  test.setTimeout(150_000);
  const begun = stage<{ servedBy: string }>('begin');
  expect(begun.servedBy).toBe('v1-web');
  const dry = stage<Report & { decided: string }>('dry-run');
  // The run reached its report only through an idempotency pass that imported and
  // updated nothing (BR8.3); a changed pass would have refused it.
  expect(dry.kind).toBe('dry');
  expect(dry.state).toBe('reported');
  expect(dry.reconciles).toBe(true);
  expect(dry.kinds.every((kind) => kind.reconciles)).toBe(true);
  // Containment: the run also meets pairs outside the table.
  const counts = new Map(dry.misfits.map((item) => [`${item.kind}:${item.reasonKey}`, item.count]));
  for (const reason of MISFITS) expect([...counts.keys()], reason).toContain(reason);
  for (const reason of COUNTED_TWICE) expect(counts.get(reason), reason).toBe(2);
  for (const kind of IMPORTING_KINDS) {
    const imported = dry.kinds.find((entry) => entry.kind === kind)?.imported ?? 0;
    expect(imported, `${kind} imports a record`).toBeGreaterThanOrEqual(1);
  }
  expect(dry.decided).toBe('accepted');
});

test('[J10] the final run reconciles and the administrator is let in first', async ({ page }) => {
  test.setTimeout(200_000);
  const value = v1Dataset();
  const started = stage<{ result: { waiting?: string }; servedBy: string }>('start');
  expect(started.result.waiting).toBe('final-report');
  // v1 is stopped and the notice answers the public address while the final run imports.
  expect(started.servedBy).toBe('maintenance');
  const final = stage<Report>('report');
  expect(final.kind).toBe('final');
  expect(final.reconciles).toBe(true);
  const accepted = stage<{ servedBy: string; profile: { admission: string } }>('accept-final');
  expect(accepted.servedBy).toBe('v2-host');
  expect(accepted.profile.admission).toBe('maintainer-only');
  // The window in the cutover tool's profile: a member's sign-in is sent, and then the
  // administrator comes in. Nothing is claimed of the member's answer: the stage's host is
  // composed from the realm's synthetic profile, which states no admission, so it holds
  // no one (a stated limit; `integration/test_admission.py` shows the admission itself).
  await firstSignIn(page, value.accounts['member-a']!.email!, value.password);
  await firstSignIn(page, value.accounts.administrator!.email!, value.password);
  await giveConsents(page);
  // The administrator's consents end that session; what follows is the second factor's
  // setup, before any administrator action (BR8.6): at once, or at the next sign-in.
  const prompt = page.getByTestId('admin-mfa-prompt');
  await expect(prompt.or(page.getByTestId('entry-email'))).toBeVisible();
  if (!(await prompt.isVisible())) {
    await firstSignIn(page, value.accounts.administrator!.email!, value.password);
  }
  await expect(prompt).toBeVisible();
  // Whichever way it showed, its heading holds focus (`first-sign-in.tsx:150-153`), read
  // before checkScreen's walk moves it.
  await expect(prompt.getByRole('heading', { name: '관리자 추가 인증' })).toBeFocused();
  await expect(page.getByTestId('nav-operations')).toHaveCount(0);
  await expect(page.getByTestId('admin-mfa-prompt')).toContainText('등록해야');
  await checkScreen(page, 'admin-mfa-prompt', 'workspace', { koreanNames: true });
});

test('[J10] once open, a migrated member meets consent and a legacy password meets reset', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const value = v1Dataset();
  const opened = stage<{ servedBy: string; profile: { admission: string } }>('open');
  expect(opened.servedBy).toBe('v2-host');
  expect(opened.profile.admission).toBe('open');
  await firstSignIn(page, value.accounts['member-a']!.email!, value.password);
  await expect(page.getByTestId('consent-step')).toBeVisible();
  await checkScreen(page, 'consent-step', 'workspace', { koreanNames: true });
  await giveConsents(page);
  await expect(page.getByTestId('logout')).toBeVisible();
  // The completed sign-in lands on the destination's first heading (Step 91(g)), never
  // `body`, although the consent step unmounts with its disabled fieldset.
  await expect
    .poll(() => focusOnFirstHeading(page), { timeout: 10_000, intervals: [250, 500] })
    .toBe(true);
  await page.getByTestId('logout').click();
  await expect(page.getByTestId('entry-email')).toBeVisible();
  // A v1 password of the legacy scheme is never accepted; its reset mail is sent.
  await firstSignIn(page, value.accounts.legacy!.email!, value.password);
  await expect(page.getByTestId('reset-required')).toBeVisible();
  await expect(page.getByTestId('logout')).toHaveCount(0);
  await checkScreen(page, 'reset-required', 'workspace', { koreanNames: true });
});

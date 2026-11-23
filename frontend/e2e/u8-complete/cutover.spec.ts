// J11 (BR9.1–BR9.9): a switch, an abort, a rollback and a cancelled rollback, each its own
// cutover journey on the stage (`cutover_stage.py`) against the synthetic v1, the
// operator acting on your decisions (the harness acting as you). After every step the
// browser reads the public address, so what a person would meet there is checked as the
// stage's own probe says it: v1's web, the maintenance notice or v2's workspace.
import { test, expect, type BrowserContext, type Page } from '@playwright/test';
import {
  captureFailures,
  checkScreen,
  harness,
  scrub,
  v1Dataset,
  v1SessionActive,
  v1SessionCheck,
  v1SignIn,
} from './helpers';

test.describe.configure({ mode: 'default' });

const diagnostics = new WeakMap<Page, ReturnType<typeof captureFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureFailures(page));
});
test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
  harness('stage', { word: 'end' });
});

type Served = 'v2-host' | 'v1-web' | 'maintenance' | string;
type Step = { servedBy: Served; result?: Record<string, unknown>; productionTables?: number };

function stage<T = Step>(word: string, document: object = {}): T {
  return harness<T>('stage', { word, ...document });
}

/** Who answers the public address, as the browser itself meets it (its own navigations,
 * through the pinned certificate). */
async function servedInBrowser(page: Page): Promise<Served> {
  const live = await page.goto('/health/live');
  if (live?.status() === 200) {
    const body = (await live.json().catch(() => ({}))) as { process?: string };
    if (body.process === 'alive') return 'v2-host';
  }
  const bff = await page.goto('/bff/health');
  if (bff?.status() === 200 && ((await bff.allHeaders())['vary'] ?? '').includes('next-router'))
    return 'v1-web';
  const notice = await page.goto('/');
  if (notice?.status() === 503) return 'maintenance';
  return `other:${notice?.status()}`;
}

async function expectServed(page: Page, step: Step, wanted: Served) {
  expect(step.servedBy).toBe(wanted);
  expect(await servedInBrowser(page)).toBe(wanted);
  if (wanted === 'v2-host') {
    await page.goto('/');
    await expect(page.getByTestId('navigation')).toBeVisible();
  }
  if (wanted === 'maintenance') {
    const answer = await page.goto('/');
    expect(answer?.status()).toBe(503);
  }
}

test('[J11] a switch: v1, the notice while the final run imports, then only v2', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const begun = stage('begin');
  await expectServed(page, begun, 'v1-web');
  const started = stage('start');
  expect(started.result?.waiting).toBe('final-report');
  await expectServed(page, started, 'maintenance');
  // The notice a person meets at the public address while the final run imports: the
  // whole page, its two links included (Step 91(h)), checked as a screen of its own.
  await checkScreen(page, 'maintenance-notice', 'page', { koreanNames: true });
  const accepted = stage<Step & { profile: { admission: string } }>('accept-final');
  expect(accepted.profile.admission).toBe('maintainer-only');
  await expectServed(page, accepted, 'v2-host');
  const opened = stage<Step & { profile: { admission: string } }>('open');
  expect(opened.result?.state).toBe('switched');
  expect(opened.profile.admission).toBe('open');
  await expectServed(page, opened, 'v2-host');
  // Nothing of v1 answers any more: Next's router `vary` marks every v1 answer.
  for (const path of ['/', '/bff/health', '/login']) {
    const answer = await page.goto(path);
    expect((await answer?.allHeaders())?.['vary'] ?? '').not.toContain('next-router');
  }
});

test('[J11] an abort: v1 serves again before v2’s database is emptied', async ({ page }) => {
  test.setTimeout(120_000);
  stage('begin');
  const started = stage('start');
  await expectServed(page, started, 'maintenance');
  // The abort held at the moment its database recreate is about to run (L4-14): Chromium
  // itself meets v1's web at the public address. That v2's database is still whole then,
  // and empty after the release, is the stage's record of the operations it ran.
  const held = stage<Step & { held: boolean }>('abort', { hold: true });
  let servedWhileHeld: Served = '';
  let aborted: Step & { heldUntilRelease?: boolean };
  try {
    servedWhileHeld = await servedInBrowser(page);
  } finally {
    aborted = stage('release-abort');
  }
  expect(held.held).toBe(true);
  // The hold was still in place when Chromium read the address: it ended by this
  // release, not by its own bound.
  expect(aborted.heldUntilRelease, 'the abort was held until its release').toBe(true);
  expect(servedWhileHeld, 'Chromium meets v1 while the abort is held').toBe('v1-web');
  expect(held.servedBy).toBe('v1-web');
  expect(held.productionTables).toBeGreaterThan(0);
  expect(aborted.result?.state).toBe('rehearsing');
  expect(aborted.productionTables).toBe(0);
  await expectServed(page, aborted, 'v1-web');
});

// The synthetic v1's accounts of the rollback journey: one erased in v2, one withdrawn in
// v2, and one active account the journey leaves untouched.
const ERASED = 'member-b';
const WITHDRAWN = 'member-a';
const UNTOUCHED = 'orcid';
// v1's own refusal, of a sign-in and of a session check alike.
const V1_REFUSED = 401;

type Session = Awaited<ReturnType<BrowserContext['cookies']>>;

/** A v1 session made in this window through v1's own sign-in at the public address. Its
 * cookies are taken out of the window, so the next account signs in from a clean one and
 * one window carries the three sessions in turn (three windows of v1's web at once took
 * the phase past its 1 GiB limit). */
async function v1Session(page: Page, name: string): Promise<Session> {
  const dataset = v1Dataset();
  await page.context().clearCookies();
  const status = await v1SignIn(page, dataset.accounts[name]!.email!, dataset.password);
  expect(status, `${name} signs in to v1 before the switch`).toBe(200);
  expect(await v1SessionActive(page), `${name}'s v1 session answers`).toBe(true);
  const session = await page.context().cookies();
  await page.context().clearCookies();
  return session;
}

/** v1's own session check asked by the window with one earlier session's cookies. */
async function v1Answers(page: Page, session: Session): Promise<boolean> {
  await page.context().clearCookies();
  await page.context().addCookies(session);
  return v1SessionActive(page);
}

/** After the rollback, in Chromium at the public address: each earlier session is refused
 * by v1's own session check; the erased and the withdrawn account are refused by v1's own
 * sign-in; the untouched account is let in. */
async function expectV1AfterRollback(page: Page, earlier: Session[]) {
  const dataset = v1Dataset();
  // First that v1's own API answers at all: the untouched account signs in. A refusal
  // below is then v1's own 401, never a stand-in's 5xx or a limit's 429.
  await page.context().clearCookies();
  const status = await v1SignIn(page, dataset.accounts[UNTOUCHED]!.email!, dataset.password);
  expect(status, `${UNTOUCHED} is let in by v1's own sign-in`).toBe(200);
  expect(await v1SessionCheck(page)).toEqual({ status: 200, signedIn: true });
  for (const session of earlier) {
    await page.context().clearCookies();
    await page.context().addCookies(session);
    expect(await v1SessionCheck(page), 'an earlier v1 session is ended').toEqual({
      status: V1_REFUSED,
      signedIn: false,
    });
  }
  for (const name of [ERASED, WITHDRAWN]) {
    await page.context().clearCookies();
    const refused = await v1SignIn(page, dataset.accounts[name]!.email!, dataset.password);
    expect(refused, `${name} is refused by v1's own sign-in`).toBe(V1_REFUSED);
    expect(await v1SessionCheck(page)).toEqual({ status: V1_REFUSED, signedIn: false });
  }
}

test('[J11] a cancelled rollback returns v2, and then a rollback hands back v1', async ({
  page,
}) => {
  test.setTimeout(150_000);
  const begun = stage('begin');
  await expectServed(page, begun, 'v1-web');
  // Three sessions made in Chromium through v1's own sign-in, before the switch; each one
  // put back in the window answers v1's own session check.
  const earlier: Session[] = [];
  for (const name of [ERASED, WITHDRAWN, UNTOUCHED]) earlier.push(await v1Session(page, name));
  for (const session of earlier)
    expect(await v1Answers(page, session), 'a v1 session answers before the switch').toBe(true);
  await page.context().clearCookies();
  stage('start');
  stage('accept-final');
  const opened = stage('open');
  await expectServed(page, opened, 'v2-host');
  // A rollback whose v1 cannot start waits, the notice at the address; you cancel it.
  const waiting = stage('rollback', { v1Fails: true });
  expect(waiting.servedBy).not.toBe('v1-web');
  const cancelled = stage('cancel-rollback');
  await expectServed(page, cancelled, 'v2-host');
  // While v2 serves, the stage asks v2's own account services to erase one account and
  // withdraw another (J08 shows those pages on the served realm).
  stage('v2-lifecycle', { name: ERASED, action: 'erase' });
  stage('v2-lifecycle', { name: WITHDRAWN, action: 'withdraw' });
  // A rollback with v1 able to start: v1 answers the public address again.
  const rolledBack = stage<Step & { v1Deletions: Record<string, boolean> }>('rollback');
  await expectServed(page, rolledBack, 'v1-web');
  await expectV1AfterRollback(page, earlier);
  // The stage's record of v1's own rows: the erased account alone has a deletion record.
  expect(rolledBack.v1Deletions).toEqual({ [ERASED]: true, [WITHDRAWN]: false });
});

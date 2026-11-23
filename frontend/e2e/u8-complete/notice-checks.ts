// NFR1.3 on every address and form of the shell (U8 plan Step 170(a); L4-15): the checks
// the screens spec's two staged notice tests are made of. Each runs on the realm's own
// capability answer served back with one changed reason (`stageMaintainerOnly`). What is
// asserted is the notice, present once inside its panel, and where its 관리자 로그인 leads;
// no staged answer here is used to assert a server's answer.
import { randomUUID } from 'node:crypto';
import { expect, type Page } from '@playwright/test';
import { fixtures, isolationTable, signInForm } from './helpers';
import {
  CAPABILITIES,
  JOB_LINK,
  PLACEHOLDER_FRAGMENT,
  changedCapabilities,
  expectOneNotice,
  holdRoute,
  openPlaceholderLink,
  realmCapabilities,
  settled,
  stageJson,
} from './staging';

const LEGAL_PAGES = ['/privacy', '/terms'];
const LINK_PATHS = [
  '/account/password-reset',
  '/account/verify-email',
  '/account/email-change',
  '/account/reactivate',
];
const NOVELTY_LINK =
  '/#research-job?jobId=00000000-0000-4000-8000-0000000000b2&kind=novelty-analysis' +
  '&contextId=00000000-0000-4000-8000-0000000000c2';
export const ARRIVAL_PROVIDERS = ['google', 'orcid'] as const;
// An arrival that reads as cancelled: the provider's refusal, a missing or repeated answer,
// and a complete answer with no flow kept in this tab.
export const CANCELLED_ANSWERS = [
  'error=access_denied&state=s',
  'code=c',
  'state=s',
  'state=s&code=c',
  'state=s&state=t&code=c&flow=f',
  'state=s&code=c&code=d&flow=f',
  'flow=f&flow=g&state=s&code=c',
];
const MAINTAINER_ONLY = { 'account.entry': { reasonKey: 'admission-maintainer-only' } };
const SEARCH_TEXT = 'attention transformer';
const SEARCH_POLICY = { policyId: 'u3-paper-search', revision: '1' };

/** The signed-out entry on staged maintainer-only capabilities; returns the removal. */
export async function stageMaintainerOnly(page: Page): Promise<() => Promise<void>> {
  await signInForm(page);
  await settled(page);
  const realm = await realmCapabilities(page);
  return stageJson(page, CAPABILITIES, changedCapabilities(realm, MAINTAINER_ONLY));
}

/** Opens one address from a blank page; its panel holds the page's one notice. */
export async function expectNoticeAt(page: Page, address: string, panelId: string): Promise<void> {
  await page.goto('about:blank');
  await page.goto(address);
  const panel = page.getByTestId(panelId);
  await expect(panel, `${address} shows ${panelId}`).toBeVisible();
  await expectOneNotice(page, panel);
}

/** Every address that shows the entry: `/`, each destination of the registry but the two
 * legal pages (`/search` among them), an unknown path, both kinds of job link, the four
 * email links with a proof and the same four paths with none. */
export function entryAddresses(): string[] {
  const destinations = isolationTable().destinations.filter((path) => !LEGAL_PAGES.includes(path));
  return [
    '/',
    ...destinations,
    '/no-such-page',
    JOB_LINK,
    NOVELTY_LINK,
    ...LINK_PATHS.map((path) => `${path}${PLACEHOLDER_FRAGMENT}`),
    ...LINK_PATHS,
  ];
}

/** One provider's pending arrival (its callback read held, then aborted) and its failed
 * one (a literal 503 in the error envelope's shape); neither reaches the realm. */
export async function expectNoticeOnArrivals(page: Page, provider: string): Promise<void> {
  const callback = `/api/v2/identity/callback/${provider}`;
  const arrival = `/sign-in/callback/${provider}?flow=f&state=s&code=c`;
  const held = await holdRoute(page, callback);
  try {
    await page.goto('about:blank');
    await page.goto(arrival);
    const pending = page.getByTestId('callback-page');
    await expect(pending).toContainText('로그인을 확인하고 있습니다');
    await expect.poll(() => held.count()).toBe(1);
    await expectOneNotice(page, pending);
  } finally {
    await held.abort();
  }
  const unrouteFailed = await stageJson(
    page,
    callback,
    { code: 'DEPENDENCY_UNAVAILABLE', requestId: 'u8-a11y-arrival-failed', retryable: true },
    503,
  );
  try {
    await expectNoticeAt(page, arrival, 'callback-page');
    await expect(page.getByTestId('callback-back')).toBeVisible();
  } finally {
    await unrouteFailed();
  }
}

/** The notice's 관리자 로그인 pressed on the panel that holds it (the entry, or an arrival
 * page): the entry's sign-in form is shown with its address field focused, and the notice
 * is still there once. */
export async function pressAdministratorSignIn(page: Page, panelId = 'complete-entry') {
  await page.getByTestId(panelId).getByTestId('maintenance-admin-sign-in').click();
  await expect(page.getByTestId('complete-entry').getByTestId('sign-in-form')).toBeVisible();
  await expect(page.getByTestId('entry-email')).toBeFocused();
  await expect(page.getByTestId('maintenance-banner')).toHaveCount(1);
}

/** The press on each kind of arrival panel: cancelled, pending (its callback read held,
 * then aborted) and failed (a literal 503). Each leaves the arrival for the sign-in form. */
export async function expectPressFromArrivals(page: Page): Promise<void> {
  const callback = '/api/v2/identity/callback/google';
  const arrival = '/sign-in/callback/google?flow=f&state=s&code=c';
  const cancelled = '/sign-in/callback/google?error=access_denied&state=s';
  await expectNoticeAt(page, cancelled, 'callback-cancelled');
  await pressAdministratorSignIn(page, 'callback-cancelled');
  const held = await holdRoute(page, callback);
  try {
    await page.goto('about:blank');
    await page.goto(arrival);
    await expect(page.getByTestId('callback-page')).toContainText('로그인을 확인하고 있습니다');
    await pressAdministratorSignIn(page, 'callback-page');
  } finally {
    await held.abort();
  }
  const body = { code: 'DEPENDENCY_UNAVAILABLE', requestId: 'u8-a11y-press', retryable: true };
  const unroute = await stageJson(page, callback, body, 503);
  try {
    await expectNoticeAt(page, arrival, 'callback-page');
    await expect(page.getByTestId('callback-back')).toBeVisible();
    await pressAdministratorSignIn(page, 'callback-page');
  } finally {
    await unroute();
  }
}

/** One staged literal refusal in the error envelope's shape for a c02 entry request. */
function stageRefusal(page: Page, name: string, status: number, code: string) {
  const body = { code, requestId: `u8-a11y-${name}`, retryable: status !== 403 };
  return stageJson(page, `/api/v2/c02/${name}`, body, status);
}

function madeUpAddress(): string {
  return `u8-a11y-${randomUUID().slice(0, 8)}@example.com`;
}

/** The two request forms of the sign-in form, each answered by a staged refusal so that
 * no mail is asked of the realm: the message is shown and the notice stays. */
export async function expectNoticeOnRequests(page: Page): Promise<void> {
  const entry = page.getByTestId('complete-entry');
  for (const [request, button] of [
    ['access-request-password-reset', 'entry-reset'],
    ['access-request-reactivation', 'entry-reactivate'],
  ] as const) {
    const unroute = await stageRefusal(page, request, 503, 'DEPENDENCY_UNAVAILABLE');
    try {
      await page.getByTestId('entry-email').fill(madeUpAddress());
      await page.getByTestId(button).click();
      await expect(entry.getByRole('alert')).toBeVisible();
      await expectOneNotice(page, entry);
      await pressAdministratorSignIn(page);
    } finally {
      await unroute();
    }
  }
}

/** The second-factor form after the administrator's own password step (the realm's own
 * answer), then back to the sign-in form by the notice. */
export async function expectNoticeOnSecondFactor(page: Page): Promise<void> {
  const entry = page.getByTestId('complete-entry');
  const administrator = fixtures().accounts.administrator;
  await page.getByTestId('entry-email').fill(administrator.email);
  await page.getByTestId('entry-password').fill(administrator.password);
  await page.getByTestId('entry-submit').click();
  await expect(entry.getByTestId('mfa-form')).toBeVisible({ timeout: 20_000 });
  await expectOneNotice(page, entry);
  await pressAdministratorSignIn(page);
  await expect(entry.getByTestId('mfa-form')).toHaveCount(0);
}

/** The three proof forms, the signed-out email-change link's sign-in-first panel, and the
 * ask-again form after a refused link (a staged 403). */
export async function expectNoticeOnProofForms(page: Page): Promise<void> {
  const entry = page.getByTestId('complete-entry');
  await openPlaceholderLink(page, '/account/email-change');
  await expect(entry.getByTestId('email-change-sign-in-first')).toBeVisible();
  await expectOneNotice(page, entry);
  await pressAdministratorSignIn(page);
  for (const path of ['/account/password-reset', '/account/verify-email', '/account/reactivate']) {
    await openPlaceholderLink(page, path);
    await expect(entry.getByTestId('proof-form')).toBeVisible();
    await expectOneNotice(page, entry);
    await pressAdministratorSignIn(page);
    await expect(entry.getByTestId('proof-form')).toHaveCount(0);
  }
  const unroute = await stageRefusal(page, 'access-verify-email', 403, 'FORBIDDEN');
  try {
    await openPlaceholderLink(page, '/account/verify-email');
    await entry.getByTestId('proof-submit').click();
    await expect(entry.getByTestId('proof-ask')).toBeVisible();
    await expectOneNotice(page, entry);
    await pressAdministratorSignIn(page);
    await expect(entry.getByTestId('proof-ask')).toHaveCount(0);
  } finally {
    await unroute();
  }
}

/** The reset-required notice: the sign-in is answered by a staged literal in the
 * contract's shape, with a made-up address and password. */
export async function expectNoticeOnResetRequired(page: Page): Promise<void> {
  const entry = page.getByTestId('complete-entry');
  const unroute = await stageJson(page, '/api/v2/c02/access-login', {
    state: 'reset_required',
    delivery: 'held',
  });
  try {
    await page.goto('about:blank');
    await page.goto('/');
    await page.getByTestId('entry-email').fill(madeUpAddress());
    await page.getByTestId('entry-password').fill(randomUUID());
    await page.getByTestId('entry-submit').click();
    await expect(entry.getByTestId('reset-required')).toBeVisible();
    await expectOneNotice(page, entry);
    await pressAdministratorSignIn(page);
  } finally {
    await unroute();
  }
}

/** A literal search answer in the contract's shape with one hit: the fixtures' own
 * isolation paper, so the opened paper's reads are the realm's own. */
function stagedSearch(): object {
  const { paper } = fixtures().paperAsset.eligible;
  const hit = {
    paper,
    title: 'Synthetic isolation paper',
    authors: ['합성 저자'],
    snippet: '점검 안내 확인용 합성 검색 결과',
    sourceUrl: 'https://fixture.example.com/paper',
    availability: 'available',
    matchExplanation: 'lexical',
  };
  return {
    executionId: randomUUID(),
    query: {
      query: SEARCH_TEXT,
      modeId: 'lexical',
      orderId: 'relevance',
      filters: [],
      vocabularyRevision: 'synthetic-paper-options-1',
      policyRef: SEARCH_POLICY,
    },
    hits: [hit],
    page: { snapshotRevision: 'u8-a11y-staged-search' },
    publication: {
      generationId: randomUUID(),
      publicationRevision: randomUUID(),
      manifestHash: randomUUID().replaceAll('-', '').repeat(2),
      compatibilityRevision: randomUUID(),
      eligibilityRevision: paper.eligibilityRevision,
      publishedAt: new Date().toISOString(),
      complete: true,
    },
    outcome: 'complete',
    effectiveModeId: 'lexical',
    limitations: [],
  };
}

/** Search results and an opened paper under the entry, on a staged literal search answer
 * (a development realm holds no searchable paper): the notice stays, once. */
export async function expectNoticeOverSearch(page: Page): Promise<void> {
  const entry = page.getByTestId('complete-entry');
  const unroute = await stageJson(page, '/api/v2/c05/search', stagedSearch());
  try {
    await page.goto('about:blank');
    await page.goto('/search');
    await page.getByTestId('search-query').fill(SEARCH_TEXT);
    await page.getByTestId('search-submit').click();
    // The signed-out shell's own search view lists a hit as `result-item`.
    const hit = page.getByTestId('search-results').getByTestId('result-item').first();
    await expect(hit).toBeVisible({ timeout: 20_000 });
    await expectOneNotice(page, entry);
    await hit.getByRole('button').click();
    await expect(page.getByTestId('paper-workspace')).toBeVisible();
    await expectOneNotice(page, entry);
    await pressAdministratorSignIn(page);
  } finally {
    await unroute();
  }
}

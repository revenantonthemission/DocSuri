// The security journeys in a real browser (D3, D7, A8): a provider sign-in's cross-site
// arrival through the identity stand-in on https://localhost:18114, a provider's error
// return and a callback address with no provider answer, each email link opened in a browser that did
// not ask for it, and the Content Security Policy refusing an inline script.
import {
  test,
  expect,
  type Browser,
  type BrowserContext,
  type Page,
  type Request,
} from '@playwright/test';
import {
  STANDIN,
  apiCall,
  assertNoViolations,
  captureFailures,
  checkScreen,
  fixtures,
  freshEntryMinute,
  harness,
  routeProviders,
  scrub,
  signInForm,
  signInFormWithProviders,
  takeViolations,
  watchPolicy,
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

const REALM = 'https://127.0.0.1:18110';
const CALLBACK_PAGE = '/sign-in/callback/google';
const GOOGLE_PAGE = /^https:\/\/accounts\.google\.com\/o\/oauth2\/v2\/auth\?/;
// Step 91(c)'s refusal text for each kind, copied here (L1-1).
const RESET_REFUSED =
  '이 비밀번호 재설정 링크는 재설정을 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 비밀번호 재설정을 다시 요청해 주세요.';
const VERIFY_REFUSED =
  '이 이메일 인증 링크는 인증을 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 인증 메일을 다시 요청해 주세요.';
const CONFIRMED = '확인했습니다. 필요한 경우 다시 로그인해 주세요.';
// Step 91(c)'s on-arrival statement, copied here (L1-1).
const BINDING_NOTE = '이 링크는 요청한 브라우저에서만 쓸 수 있습니다.';
const CONTENT_SECURITY_POLICY =
  "default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self' https://accounts.google.com https://orcid.org";
const ENTRY_POLICY = { policyId: 'synthetic-local-entry', revision: '1' };
// Each new link waits for the served realm's sender (L1-69, at most 60 s per read).
const LINK_WAIT_MS = 70_000;
const MAX_TABS = 60;

type MailLink = { challengeId: string; flowBinding: string; proof: string };
type LocationRecord = {
  doc: string;
  startPath: string;
  kind: 'root' | 'fetch';
  seq: number;
  path: string;
  search: string;
};

/** Records `location.pathname` and `location.search` in every document of the page when
 * `#root` first gets a child, and at every `window.fetch` call. */
async function recordLocations(page: Page): Promise<LocationRecord[]> {
  const records: LocationRecord[] = [];
  await page.exposeFunction('__u8Location', (record: LocationRecord) => {
    records.push(record);
  });
  await page.addInitScript(() => {
    const doc = `${Date.now()}-${Math.random()}`;
    const startPath = location.pathname;
    let seq = 0;
    const report = (kind: 'root' | 'fetch') => {
      const send = Reflect.get(window, '__u8Location') as ((record: object) => unknown) | null;
      const record = {
        doc,
        startPath,
        kind,
        seq: seq++,
        path: location.pathname,
        search: location.search,
      };
      if (typeof send === 'function') void send(record);
    };
    const original = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      report('fetch');
      return original(input, init);
    };
    const observer = new MutationObserver(() => {
      if (document.getElementById('root')?.firstChild) {
        observer.disconnect();
        report('root');
      }
    });
    observer.observe(document, { childList: true, subtree: true });
  });
  return records;
}

/** The headers each request carried on the wire, from the browser's own network events.
 * While a route intercepts the context, Playwright reports an intercepted fetch with the
 * headers it was paused with, which leave out what the network layer adds (`Sec-Fetch-*`,
 * `Origin`); the network layer's own report names them. The answer reads one request by
 * path, which must have been sent exactly once. */
async function wireHeaders(
  context: BrowserContext,
  page: Page,
): Promise<(path: string) => Record<string, string>> {
  const session = await context.newCDPSession(page);
  await session.send('Network.enable');
  const paths = new Map<string, string>();
  const sent = new Map<string, Record<string, string>>();
  session.on('Network.requestWillBeSent', (event) => {
    paths.set(event.requestId, new URL(event.request.url).pathname);
  });
  session.on('Network.requestWillBeSentExtraInfo', (event) => {
    const headers = Object.fromEntries(
      Object.entries(event.headers).map(([name, value]) => [name.toLowerCase(), String(value)]),
    );
    sent.set(event.requestId, headers);
  });
  return (path: string) => {
    const ids = [...paths].filter(([, value]) => value === path).map(([id]) => id);
    expect(ids, `${path} was sent once`).toHaveLength(1);
    const headers = sent.get(ids[0]!);
    expect(headers, `${path}'s wire headers were reported`).toBeDefined();
    return headers ?? {};
  };
}

/** The account's newest delivered link, read until it is not the one before. */
function latestLink(email: string, purpose: string): MailLink | null {
  try {
    return harness<MailLink>('proof', { email, purpose });
  } catch {
    return null;
  }
}

async function newLink(email: string, purpose: string, before: string | null): Promise<MailLink> {
  let link: MailLink | null = null;
  await expect
    .poll(
      () => {
        link = latestLink(email, purpose);
        return link !== null && link.challengeId !== before;
      },
      { timeout: LINK_WAIT_MS, intervals: [1_000, 2_000] },
    )
    .toBe(true);
  if (link === null) throw new Error(`no new ${purpose} link`);
  return link;
}

/** The link as the mail carries it: the workspace page with the proof in its fragment. */
function linkPath(page: string, link: MailLink): string {
  const fragment = new URLSearchParams({
    challenge: link.challengeId,
    proof: link.proof,
    flow: link.flowBinding,
  });
  return `${page}#${fragment}`;
}

async function openProof(page: Page, path: string): Promise<void> {
  // From a page already at the link's path, only the fragment would change, which loads
  // nothing: the link opens as a new document, as from a mail.
  if (page.url() !== 'about:blank') await page.goto('about:blank');
  await page.goto(path);
  await expect(page.getByTestId('proof-form')).toBeVisible();
  // The link reached its own page, and the proof left the address at once (checked
  // without echoing the fragment).
  expect(new URL(page.url()).pathname).toBe(path.split('#')[0]);
  expect(new URL(page.url()).hash === '', 'the fragment is cleared').toBe(true);
  // Before anything is typed, the page says the link works only in the asking browser.
  await expect(page.getByTestId('proof-binding-note')).toHaveText(BINDING_NOTE);
}

/** The cookie names a `Cookie` header carries, never their values. */
function cookieNames(header: string | undefined): string[] {
  return (header ?? '')
    .split(';')
    .map((part) => part.split('=')[0]!.trim())
    .filter((name) => name !== '');
}

/** A `Set-Cookie` line reduced to its name and its attributes, never its value. */
function setCookieShape(line: string): { name: string; attributes: string[] } {
  const [pair = '', ...attributes] = line.split(';');
  return {
    name: pair.split('=')[0]!.trim(),
    // Lower-cased with every space removed: `Path=/`, `SameSite=Strict`, `Secure`.
    attributes: attributes.map((item) => item.toLowerCase().replace(/\s/g, '')),
  };
}

/** A fresh browser context, policy-watched before its first page (Step 100(e)). */
async function freshContext(browser: Browser): Promise<BrowserContext> {
  const context = await browser.newContext({ baseURL: REALM });
  watchPolicy(context);
  return context;
}

/** Closes a browser's tab while it waits: the asking browser's while a fresh one acts, and
 * a fresh one's while a harness read runs. Each browser context has renderer processes of
 * its own, so a tab left open would hold its renderer in the supervised tree beside the
 * other browser's, or beside the harness's own process. The context stays, with its entry
 * cookie: a later tab of it is still the same browser. */
async function leaveTab(page: Page): Promise<void> {
  await page.close();
}

async function activeTestId(page: Page): Promise<string | null> {
  return page.evaluate(() => document.activeElement?.getAttribute('data-testid') ?? null);
}

/** Presses Tab until the control with `testId` holds the focus, within a bound. */
async function tabTo(page: Page, testId: string): Promise<void> {
  for (let press = 0; press < MAX_TABS; press += 1) {
    await page.keyboard.press('Tab');
    if ((await activeTestId(page)) === testId) return;
  }
  expect(await activeTestId(page), `Tab reaches ${testId}`).toBe(testId);
}

function requestsTo(page: Page, operation: string): Request[] {
  const seen: Request[] = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === `/api/v2/c02/${operation}`) seen.push(request);
  });
  return seen;
}

test('[SEC] a Google sign-in arrives back cross-site and signs the linked account in', async ({
  page,
  context,
  browser,
}) => {
  await routeProviders(context);
  // The provider's own page commits before it sends the browser on, as the real consent
  // page does after its answer. A redirect at once would leave the realm's page as the
  // navigation's initiator, and Chromium sends a SameSite=Strict cookie on a redirect chain
  // its initiator's site starts; from the provider's page the arrival is cross-site.
  await page.route(GOOGLE_PAGE, async (route) => {
    const address = new URL(route.request().url());
    const target = `${STANDIN}${address.pathname}${address.search}`.replaceAll('&', '&amp;');
    await route.fulfill({
      status: 200,
      contentType: 'text/html; charset=utf-8',
      headers: { 'cache-control': 'no-store' },
      body: `<!doctype html><html lang="ko"><head><meta http-equiv="refresh" content="0;url=${target}"></head><body></body></html>`,
    });
  });
  const records = await recordLocations(page);
  const sentHeaders = await wireHeaders(context, page);
  const visited: string[] = [];
  const arrivals: Request[] = [];
  const callbacks: Request[] = [];
  const afterLanding: Request[] = [];
  const setCookies: Promise<string[]>[] = [];
  let landed = false;
  // The stand-in answers with a redirect at once, so its page is a request of the
  // top-level navigation's redirect chain, never a committed frame.
  page.on('request', (request) => {
    const address = new URL(request.url());
    if (request.isNavigationRequest()) visited.push(address.origin);
    if (landed) afterLanding.push(request);
    if (request.isNavigationRequest() && address.pathname === CALLBACK_PAGE && address.search) {
      arrivals.push(request);
      landed = true;
    }
    if (address.pathname === '/api/v2/identity/callback/google') callbacks.push(request);
  });
  page.on('response', (response) => {
    if (new URL(response.url()).origin !== REALM) return;
    setCookies.push(
      response
        .headersArray()
        .then((headers) =>
          headers
            .filter((header) => header.name.toLowerCase() === 'set-cookie')
            .map((header) => header.value),
        ),
    );
  });
  await signInFormWithProviders(page);
  await page.getByTestId('provider-google').click();
  await expect(page.getByTestId('logout')).toBeVisible({ timeout: 20_000 });

  // The cross-site arrival: no session or entry cookie travels with it. Cookies are
  // checked by name only, so a failure never writes a value into the kept report.
  expect(arrivals).toHaveLength(1);
  const arrival = arrivals[0]!;
  // Google's own answer (R-09): the arrival carries `scope`, `authuser` and `prompt` and no
  // `flow`, so the sign-in completed on it with the flow its tab kept. Keys only, never a
  // value, so no code or state reaches the kept report.
  const arrivalKeys = [...new URL(arrival.url()).searchParams.keys()];
  for (const key of ['scope', 'authuser', 'prompt'])
    expect(arrivalKeys.includes(key), `the arrival carries ${key}`).toBe(true);
  expect(arrivalKeys.includes('flow'), 'the arrival carries no flow').toBe(false);
  const arrivalHeaders = await arrival.allHeaders();
  expect(arrivalHeaders['sec-fetch-site']).toBe('cross-site');
  const arrivalCookies = cookieNames(arrivalHeaders.cookie);
  expect(arrivalCookies).not.toContain('docsuri_entry');
  expect(arrivalCookies).not.toContain('session_id');
  const landing = await arrival.response();
  expect(landing?.status()).toBe(200);
  expect((await landing?.allHeaders())?.['content-type'] ?? '').toMatch(/^text\/html/);

  // Step 91(b)'s first-render arrival: the answer left the address before anything ran.
  const arrivalRecords = records
    .filter((record) => record.startPath === CALLBACK_PAGE)
    .sort((a, b) => a.seq - b.seq);
  expect(arrivalRecords.length).toBeGreaterThan(0);
  expect(arrivalRecords[0]!.path).toBe(CALLBACK_PAGE);
  for (const record of arrivalRecords)
    expect(
      /(code|state|flow|scope|authuser|prompt)=/.test(`${record.path}${record.search}`),
      `the answer left the address before ${record.kind} ${record.seq}`,
    ).toBe(false);

  // The page's own same-origin callback read carries the entry cookie.
  expect(callbacks).toHaveLength(1);
  const callback = callbacks[0]!;
  // No key Google added reaches the route: its query holds exactly flow, state and code.
  expect([...new URL(callback.url()).searchParams.keys()].sort(), 'the callback keys').toEqual([
    'code',
    'flow',
    'state',
  ]);
  expect(callback.resourceType()).toBe('fetch');
  const callbackHeaders = sentHeaders('/api/v2/identity/callback/google');
  expect(callbackHeaders['sec-fetch-site']).toBe('same-origin');
  expect(cookieNames(callbackHeaders.cookie)).toContain('docsuri_entry');

  // Every cookie the realm set is strict, secure, script-free and host-only: each line
  // and each stored cookie is compared without its value.
  const cookieLines = (await Promise.all(setCookies)).flat();
  expect(cookieLines.length).toBeGreaterThan(0);
  for (const line of cookieLines) {
    const { name, attributes } = setCookieShape(line);
    expect(attributes, `${name} is SameSite=Strict`).toContain('samesite=strict');
    expect(attributes, `${name} is Secure`).toContain('secure');
    expect(attributes, `${name} is HttpOnly`).toContain('httponly');
    expect(attributes, `${name} has Path=/`).toContain('path=/');
    expect(
      attributes.some((item) => item.startsWith('domain=')),
      `${name} has no Domain`,
    ).toBe(false);
  }
  const cookies = await context.cookies(REALM);
  expect(cookies.length).toBeGreaterThan(0);
  for (const cookie of cookies)
    expect(
      {
        name: cookie.name,
        sameSite: cookie.sameSite,
        httpOnly: cookie.httpOnly,
        secure: cookie.secure,
        domain: cookie.domain,
      },
      cookie.name,
    ).toEqual({
      name: cookie.name,
      sameSite: 'Strict',
      httpOnly: true,
      secure: true,
      domain: '127.0.0.1',
    });

  // Nothing the arrival page sent after landing carries a referrer. Checked as a boolean,
  // so a failure names the path only, never the referrer (which would hold code and state).
  for (const request of afterLanding) {
    const path = new URL(request.url()).pathname;
    const headers = await request.allHeaders();
    expect(headers.referer === undefined, `${path} carries no referer`).toBe(true);
  }

  // As built: the browser left for the stand-in's site and came back signed in.
  expect(visited).toContain(STANDIN);
  expect(
    /[?&](code|state|scope|authuser|prompt)=/.test(page.url()),
    'no provider answer in the address',
  ).toBe(false);
  const session = await page.evaluate(async () =>
    (await fetch('/api/v2/session', { cache: 'no-store' })).json(),
  );
  expect(session.signedIn).toBe(true);

  // The first leg's tab closes, so its renderer leaves the supervised tree before the
  // second leg's browser opens (B100's memory finding).
  await leaveTab(page);
  await immediateRedirectLeg(browser);
});

/** The second leg (the lead's decision after build batch 10a): `routeProviders`' immediate
 * 302, with no committed provider page. Chromium may then send the SameSite=Strict entry
 * cookie on the arrival, because the realm's page stays the redirect chain's initiator; the
 * design tolerates it, since the arrival page needs no cookie and calls the API itself. So
 * the sign-in must still complete. Whether the arrival carried `docsuri_entry` is recorded
 * as a test annotation (by name, never a value) and asserted neither way. */
async function immediateRedirectLeg(browser: Browser): Promise<void> {
  const fresh = await freshContext(browser);
  try {
    await routeProviders(fresh);
    const page = await fresh.newPage();
    const arrivals: Request[] = [];
    const callbacks: Request[] = [];
    page.on('request', (request) => {
      const address = new URL(request.url());
      if (request.isNavigationRequest() && address.pathname === CALLBACK_PAGE && address.search)
        arrivals.push(request);
      if (address.pathname === '/api/v2/identity/callback/google') callbacks.push(request);
    });
    await signInFormWithProviders(page);
    await page.getByTestId('provider-google').click();
    await expect(page.getByTestId('logout')).toBeVisible({ timeout: 20_000 });
    expect(callbacks, 'one identity callback request').toHaveLength(1);
    expect((await callbacks[0]!.response())?.status(), 'the callback is answered').toBe(200);
    const session = await page.evaluate(async () =>
      (await fetch('/api/v2/session', { cache: 'no-store' })).json(),
    );
    expect(session.signedIn).toBe(true);
    expect(
      /[?&](code|state|scope|authuser|prompt)=/.test(page.url()),
      'no provider answer in the address',
    ).toBe(false);
    expect(arrivals, 'one arrival').toHaveLength(1);
    const carried = cookieNames((await arrivals[0]!.allHeaders()).cookie).includes('docsuri_entry');
    test.info().annotations.push({
      type: 'immediate-redirect-arrival-carried-docsuri_entry',
      description: String(carried),
    });
    assertNoViolations(page);
  } finally {
    await fresh.close();
  }
}

test('[SEC] an ORCID error return reads as cancelled and calls no identity callback route', async ({
  page,
  context,
}) => {
  await routeProviders(context);
  const callbacks: string[] = [];
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith('/api/v2/identity/callback/')) callbacks.push(path);
  });
  await signInFormWithProviders(page);
  await page.getByTestId('provider-orcid').click();
  const cancelled = page.getByTestId('callback-cancelled');
  await expect(cancelled).toBeVisible({ timeout: 20_000 });
  await expect(cancelled.getByRole('alert')).toHaveText('로그인이 취소되었습니다');
  expect(page.url()).not.toMatch(/[?&](error|state)=/);
  expect(callbacks).toEqual([]);
  await cancelled.getByTestId('callback-back').click();
  await expect(page.getByTestId('entry-email')).toBeVisible();
  await expect(page.getByTestId('logout')).toHaveCount(0);
});

test('[SEC] a callback address with no provider answer reads as cancelled and calls no identity callback route', async ({
  page,
}) => {
  const records = await recordLocations(page);
  const callbacks: string[] = [];
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith('/api/v2/identity/callback/')) callbacks.push(path);
  });
  // The page ignores keys it does not read; it cancels here because `?foo=1` holds no
  // answer (no state, code or flow).
  await page.goto(`${CALLBACK_PAGE}?foo=1`);
  const cancelled = page.getByTestId('callback-cancelled');
  await expect(cancelled).toBeVisible({ timeout: 20_000 });
  await expect(cancelled.getByRole('alert')).toHaveText('로그인이 취소되었습니다');
  expect(new URL(page.url()).search).toBe('');
  // L1-15's other half: the shell's own reads carry no provider answer.
  const fetches = records.filter((record) => record.kind === 'fetch');
  expect(fetches.length).toBeGreaterThan(0);
  for (const record of fetches) expect(record.search).not.toContain('foo=');
  await cancelled.getByTestId('callback-back').click();
  await expect(page.getByTestId('entry-email')).toBeVisible();
  await expect(page.getByTestId('logout')).toHaveCount(0);
  expect(callbacks).toEqual([]);
});

/** Reset, memberA: refused in a fresh browser, checked, asked again by keyboard alone, and
 * the new link confirmed there. The reset sets memberA's own password, so nothing changes. */
async function resetInFreshBrowser(page: Page, browser: Browser): Promise<void> {
  const member = fixtures().accounts.memberA;
  const before = latestLink(member.email, 'password-reset')?.challengeId ?? null;
  await page.getByTestId('entry-email').fill(member.email);
  await page.getByTestId('entry-reset').click();
  await expect(page.getByTestId('complete-entry').getByRole('status').first()).toContainText(
    '요청을 접수했습니다',
  );
  const first = await newLink(member.email, 'password-reset', before);
  await leaveTab(page);
  const fresh = await freshContext(browser);
  try {
    const other = await fresh.newPage();
    const askAgain = requestsTo(other, 'access-request-password-reset');
    await openProof(other, linkPath('/account/password-reset', first));
    await other.getByTestId('proof-password').fill(member.password);
    await other.getByTestId('proof-submit').click();
    await expect(other.getByTestId('complete-entry').getByRole('alert').first()).toContainText(
      RESET_REFUSED,
    );
    // A boolean poll, so a failure never prints the fixture password.
    const password = other.getByTestId('proof-password');
    await expect
      .poll(async () => (await password.inputValue()) === '', {
        message: 'the password field is cleared',
      })
      .toBe(true);
    await checkScreen(other, 'email-link-fresh-browser', 'page', { koreanNames: true });
    // The ask-again request by keyboard alone.
    await tabTo(other, 'proof-ask-email');
    await other.keyboard.type(member.email);
    await other.keyboard.press('Tab');
    expect(await activeTestId(other)).toBe('proof-ask-again');
    const answered = other.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/api/v2/c02/access-request-password-reset',
    );
    await other.keyboard.press('Enter');
    expect((await answered).status()).toBe(200);
    expect(askAgain).toHaveLength(1);
    await leaveTab(other);
    const second = await newLink(member.email, 'password-reset', first.challengeId);
    const again = await fresh.newPage();
    await openProof(again, linkPath('/account/password-reset', second));
    await again.getByTestId('proof-password').fill(member.password);
    await again.getByTestId('proof-submit').click();
    await expect(again.getByTestId('complete-entry')).toContainText(CONFIRMED);
    await expect(again.getByTestId('logout')).toHaveCount(0);
    assertNoViolations(again);
  } finally {
    await fresh.close();
  }
}

/** Verify-email, unverifiedA: refused in a fresh browser, asked again there, confirmed. */
async function verifyInFreshBrowser(context: BrowserContext, browser: Browser): Promise<void> {
  const account = fixtures().accounts.unverifiedA;
  const before = latestLink(account.email, 'verify')?.challengeId ?? null;
  const asking = await context.newPage();
  await signInForm(asking);
  const requested = await apiCall(asking, '/api/v2/c02/access-request-verification', {
    email: account.email,
    policyRef: ENTRY_POLICY,
  });
  expect(requested.status).toBe(200);
  await leaveTab(asking);
  const first = await newLink(account.email, 'verify', before);
  const fresh = await freshContext(browser);
  try {
    const other = await fresh.newPage();
    const askAgain = requestsTo(other, 'access-request-verification');
    await openProof(other, linkPath('/account/verify-email', first));
    await other.getByTestId('proof-submit').click();
    await expect(other.getByTestId('complete-entry').getByRole('alert').first()).toContainText(
      VERIFY_REFUSED,
    );
    await other.getByTestId('proof-ask-email').fill(account.email);
    const answered = other.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/v2/c02/access-request-verification',
    );
    await other.getByTestId('proof-ask-again').click();
    expect((await answered).status()).toBe(200);
    expect(askAgain).toHaveLength(1);
    await leaveTab(other);
    const second = await newLink(account.email, 'verify', first.challengeId);
    const again = await fresh.newPage();
    await openProof(again, linkPath('/account/verify-email', second));
    await again.getByTestId('proof-submit').click();
    await expect(again.getByTestId('complete-entry')).toContainText(CONFIRMED);
    assertNoViolations(again);
  } finally {
    await fresh.close();
  }
}

/** Verify-email, unverifiedB, in the asking browser: the link arrives cross-site from a
 * page on another site, is confirmed with the entry cookie, and is refused once spent. */
async function verifyInAskingBrowser(context: BrowserContext): Promise<Page> {
  const account = fixtures().accounts.unverifiedB;
  const before = latestLink(account.email, 'verify')?.challengeId ?? null;
  const page = await context.newPage();
  const sentHeaders = await wireHeaders(context, page);
  await signInForm(page);
  const requested = await apiCall(page, '/api/v2/c02/access-request-verification', {
    email: account.email,
    policyRef: ENTRY_POLICY,
  });
  expect(requested.status).toBe(200);
  const link = await newLink(account.email, 'verify', before);
  const path = linkPath('/account/verify-email', link);
  const mailPage = `${STANDIN}/u8-mail-link`;
  await context.route(mailPage, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/html; charset=utf-8',
      body: `<!doctype html><html lang="ko"><body><a data-testid="mail-link" href="${REALM}${path}">메일의 링크</a></body></html>`,
    });
  });
  try {
    await page.goto(mailPage);
    const navigation = page.waitForRequest(
      (request) =>
        request.isNavigationRequest() &&
        new URL(request.url()).pathname === '/account/verify-email',
    );
    await page.getByTestId('mail-link').click();
    await navigation;
  } finally {
    await context.unroute(mailPage);
  }
  await expect(page.getByTestId('proof-form')).toBeVisible();
  const arrival = sentHeaders('/account/verify-email');
  expect(arrival['sec-fetch-site']).toBe('cross-site');
  expect(cookieNames(arrival.cookie)).not.toContain('docsuri_entry');
  const verified = page.waitForResponse(
    (response) => new URL(response.url()).pathname === '/api/v2/c02/access-verify-email',
  );
  await page.getByTestId('proof-submit').click();
  await verified;
  expect(cookieNames(sentHeaders('/api/v2/c02/access-verify-email').cookie)).toContain(
    'docsuri_entry',
  );
  await expect(page.getByTestId('complete-entry')).toContainText(CONFIRMED);
  // The same link, now spent, explains itself like a fresh browser's.
  await openProof(page, path);
  await page.getByTestId('proof-submit').click();
  await expect(page.getByTestId('complete-entry').getByRole('alert').first()).toContainText(
    VERIFY_REFUSED,
  );
  return page;
}

test('[SEC] each email link opened in a fresh browser explains it and asks again here', async ({
  page,
  browser,
  context,
}) => {
  test.setTimeout(120_000);
  await signInForm(page);
  await freshEntryMinute(page);
  await resetInFreshBrowser(page, browser);
  await verifyInFreshBrowser(context, browser);
  const asking = await verifyInAskingBrowser(context);
  // memberA's own password still signs in in the asking browser.
  const member = fixtures().accounts.memberA;
  await signInForm(asking);
  await asking.getByTestId('entry-email').fill(member.email);
  await asking.getByTestId('entry-password').fill(member.password);
  await asking.getByTestId('entry-submit').click();
  await expect(asking.getByTestId('logout')).toBeVisible();
});

test('[SEC] a policy violation is caught', async ({ page }) => {
  const shell = await page.goto('/');
  const policy = (await shell?.allHeaders())?.['content-security-policy'] ?? '';
  expect(policy).toBe(CONTENT_SECURITY_POLICY);
  expect(policy).not.toContain('unsafe-inline');
  expect(policy).not.toContain('unsafe-eval');
  const inject = (flag: string) =>
    page.evaluate((name) => {
      const script = document.createElement('script');
      script.textContent = `window.${name} = true;`;
      document.body.append(script);
    }, flag);
  const refused = () =>
    page.waitForEvent('console', {
      predicate: (message) => message.text().startsWith('Refused to execute inline script'),
    });
  const firstReport = refused();
  await inject('__u8InlineFirst');
  await firstReport;
  expect(await page.evaluate(() => Reflect.get(window, '__u8InlineFirst'))).toBeUndefined();
  expect(takeViolations(page)).toEqual(["default-src 'self'"]);
  const secondReport = refused();
  await inject('__u8InlineSecond');
  await secondReport;
  expect(await page.evaluate(() => Reflect.get(window, '__u8InlineSecond'))).toBeUndefined();
  // Left untaken, the second makes the assertion fail and name it.
  expect(() => assertNoViolations(page)).toThrow("default-src 'self'");
  // The assertion took it as it failed: nothing is left for the afterEach.
  expect(takeViolations(page)).toEqual([]);
});

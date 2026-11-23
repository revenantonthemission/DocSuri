// U8 complete-verification helpers: the run-bound fixtures, sign-in, the operator's
// harness, axe, and failure-only diagnostics. Every journey goes through the public
// stand-in at https://127.0.0.1:18110 (real HTTP, a real browser, BR10.2).
import AxeBuilder from '@axe-core/playwright';
import { execFileSync } from 'node:child_process';
import { createHash, createHmac, randomBytes, randomUUID } from 'node:crypto';
import { lstatSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  expect,
  test,
  type BrowserContext,
  type ConsoleMessage,
  type Page,
  type Request,
  type Response,
  type TestInfo,
} from '@playwright/test';

const repositoryRoot = fileURLToPath(new URL('../../../', import.meta.url));
const runRoot = realpathSync('/tmp/docsuri-u8-run');
const python = join(repositoryRoot, 'backend/.venv/bin/python');

export type Account = { email: string; password: string; accountId: string };
export type Administrator = Account & { totpSeed: string };
export type NoveltyResult = {
  jobId: string;
  contextId: string;
  artifactId: string;
  revision: string;
  contentHash: string;
};

export type PaperAsset = {
  paper: { paperId: string; versionId: string; eligibilityRevision: string };
  contentRevision: string;
  assetId: string;
  sha256: string;
};

export type Fixtures = {
  runId: string;
  accounts: {
    memberA: Account;
    memberB: Account;
    memberC: Account;
    memberD: Account;
    memberE: Account;
    administrator: Administrator;
    // Unverified, one for each verify-email leg of the fresh-browser links (Step 100(c)).
    unverifiedA: Account;
    unverifiedB: Account;
  };
  novelty: NoveltyResult;
  // memberE's own ready result (J05), made by the fixtures like memberA's.
  noveltyMemberE: NoveltyResult;
  notionToken: string;
  notion: { workspace: string; practice: string; stuck: string; settle: string };
  // The isolation journeys' own paper (J03, J13): one eligible and one ineligible version.
  paperAsset: { paperId: string; eligible: PaperAsset; ineligible: PaperAsset };
  // memberA's ready paper-assistance job (Step 167; `scripts/u8_fixture_assistance.py`).
  assistanceJob: {
    jobId: string;
    paper: PaperAsset['paper'];
    resultId: string;
    revision: string;
    contentHash: string;
  };
};

/** A fixture's ready novelty result, memberA's by default, opened through U4's own
 * recovery link. */
export async function openNoveltyResult(page: Page, novelty: NoveltyResult = fixtures().novelty) {
  const query = new URLSearchParams({
    jobId: novelty.jobId,
    kind: 'novelty-analysis',
    contextId: novelty.contextId,
  });
  await page.goto('/');
  await expect(page.getByTestId('logout')).toBeVisible();
  await page.goto(`/#research-job?${query}`);
  await page.getByRole('button', { name: '준비된 결과 열기' }).click();
  await expect(page.getByTestId('novelty-export-open')).toBeVisible();
}

/** The export view with a usable Notion connection (the fake's run-bound token). */
export async function ensureNotionConnected(page: Page) {
  await page.getByTestId('nav-export').click();
  await expect(page.getByTestId('export-view')).not.toHaveAttribute('data-view-state', 'loading');
  if (await page.getByTestId('connection-disconnect').isVisible()) return;
  await page.getByTestId('connect-token').fill(fixtures().notionToken);
  await page.getByTestId('connect-submit').click();
  await expect(page.getByTestId('connection-state')).toContainText('연결됨');
}

/** From the novelty result to a chosen destination's ready preview, then approve. */
export async function exportNoveltyTo(page: Page, title: string) {
  await openNoveltyResult(page);
  await exportShownNoveltyTo(page, title);
}

/** From a novelty result already on screen to a chosen destination, then approve. */
export async function exportShownNoveltyTo(page: Page, title: string) {
  await page.getByTestId('novelty-export-open').click();
  await page
    .getByTestId('destination-option')
    .filter({ has: page.locator('.export-destination-title').getByText(title, { exact: true }) })
    .getByTestId('destination-radio')
    .check();
  await page.getByTestId('destination-next').click();
  await expect(page.getByTestId('preview-step')).toHaveAttribute('data-preview-state', 'ready');
  await page.getByTestId('preview-approve').click();
  await expect(page.getByTestId('flow-step-outcome')).toHaveAttribute('aria-current', 'step');
}

function privateJson(path: string, limit = 65_536): unknown {
  const info = lstatSync(path);
  if (
    !info.isFile() ||
    info.isSymbolicLink() ||
    info.uid !== process.getuid?.() ||
    info.mode & 0o077 ||
    info.nlink !== 1 ||
    info.size > limit
  )
    throw new Error('U8 private fixture boundary refused');
  return JSON.parse(readFileSync(path, 'utf8'));
}

/** The run-bound fixture record (`fixtures/browser.json`), read only through its checks. */
export function fixtures(): Fixtures {
  const value = privateJson(join(runRoot, 'fixtures', 'browser.json')) as Fixtures & {
    version: string;
    state: string;
  };
  const environment = privateJson(join(runRoot, 'environment.json')) as { runId: string };
  if (
    value.runId !== environment.runId ||
    value.version !== 'u8-fixtures-v1' ||
    value.state !== 'ready' ||
    typeof value.accounts?.administrator?.totpSeed !== 'string'
  )
    throw new Error('U8 fixture identity or readiness mismatch');
  return value;
}

/** A journey's measurements for the runner (`perf-browser.json`, 0600 in the run root):
 * timings and request shapes only, never content or a secret. */
export function writeMeasurements(name: string, value: object) {
  if (!/^[a-z-]+\.json$/.test(name)) throw new Error('measurement name outside its pattern');
  writeFileSync(join(runRoot, name), JSON.stringify(value), { mode: 0o600 });
}

/** The synthetic v1 dataset's record (`fixtures/v1-dataset.json`). */
export function v1Dataset(): {
  accounts: Record<string, { v1AccountId: string; email: string | null; state: string }>;
  password: string;
} {
  return privateJson(join(runRoot, 'fixtures', 'v1-dataset.json')) as ReturnType<typeof v1Dataset>;
}

/** RFC 6238 (SHA-1, six digits, 30-second steps), as U2's factor check computes it. */
export function totp(seed: string, at = Date.now()): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const char of seed.replace(/=+$/, '')) {
    const index = alphabet.indexOf(char);
    if (index < 0) throw new Error('seed outside base32');
    bits += index.toString(2).padStart(5, '0');
  }
  const key = Buffer.from(bits.match(/.{8}/g)!.map((byte) => parseInt(byte, 2)));
  const step = Buffer.alloc(8);
  step.writeBigUInt64BE(BigInt(Math.floor(at / 30_000)));
  const digest = createHmac('sha1', key).update(step).digest();
  const offset = digest[digest.length - 1]! & 15;
  const code = (digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return code.toString().padStart(6, '0');
}

const STEP_MS = 30_000;
const stepFile = join(runRoot, 'u8-factor-step.json');

/** A second-factor code for the current time step. U2's factor check reads the
 * database's own clock (`clock_timestamp()`), allows one step of drift, and refuses any
 * step at or before the last one it accepted; so a step an earlier sign-in spent (in
 * this spec, another, or a restarted worker: the run root keeps the last one) is waited
 * out to the next. */
export async function realmFactorCode(seed: string): Promise<string> {
  let last = -1;
  try {
    last = (privateJson(stepFile) as { step: number }).step;
  } catch {
    /* no sign-in spent a step yet in this run */
  }
  let step = Math.floor(Date.now() / STEP_MS);
  if (step <= last) {
    await new Promise((resolve) => setTimeout(resolve, (last + 1) * STEP_MS - Date.now() + 500));
    step = Math.floor(Date.now() / STEP_MS);
  }
  writeFileSync(stepFile, JSON.stringify({ step }), { mode: 0o600 });
  return totp(seed, step * STEP_MS + 1_000);
}

/** The operator's actions on the realm, through the test harness acting as you: the
 * realm's real operator, its bound operations, receipts and ledger. */
export function harness<T = Record<string, unknown>>(word: string, document: object = {}): T {
  let output: string;
  try {
    output = execFileSync(
      python,
      ['-m', 'tests.u8_service_operations_integration.browser_harness', word],
      {
        cwd: repositoryRoot,
        input: JSON.stringify(document),
        env: { ...process.env, PYTHONPATH: repositoryRoot },
        timeout: 150_000,
        maxBuffer: 1 << 20,
        stdio: ['pipe', 'pipe', 'ignore'],
      },
    ).toString();
  } catch (error) {
    // A refusal exits 1 with its one JSON line; anything else has no answer to read.
    const stdout = (error as { stdout?: Buffer }).stdout?.toString() ?? '';
    if (!stdout.trim()) throw error;
    output = stdout;
  }
  const value = JSON.parse(output.trim().split('\n').pop() ?? '{}') as {
    ok: boolean;
    result?: T;
    reason?: string;
  };
  if (!value.ok) throw new Error(`harness ${word} refused: ${value.reason ?? 'unknown'}`);
  return value.result as T;
}

// The workspace page each account mail's link opens (`account_mail.LINK_PATHS`).
const LINK_PAGES: Readonly<Record<string, string>> = {
  verify: '/account/verify-email',
  'password-reset': '/account/password-reset',
  'email-change': '/account/email-change',
  reactivate: '/account/reactivate',
};

/** Opens an account's newest delivered link from the realm's local mailbox, as the mail
 * carries it: the workspace page with the proof in its fragment. */
export async function openMailLink(page: Page, email: string, purpose: string) {
  const link = harness<{ challengeId: string; flowBinding: string; proof: string }>('proof', {
    email,
    purpose,
  });
  const fragment = new URLSearchParams({
    challenge: link.challengeId,
    proof: link.proof,
    flow: link.flowBinding,
  });
  await page.goto(`${LINK_PAGES[purpose]}#${fragment}`);
}

/** The next whole minute at least `minutes` ahead of the realm's delegated clock, as
 * `HH:MM` in `timeZone`; the clock moves by one second to be read. */
export function clockTimeAhead(minutes: number, timeZone: string): string {
  const { instant } = harness<{ instant: string }>('advance-clock', { seconds: 1 });
  const moment = new Date(Date.parse(instant) + (minutes + 1) * 60_000);
  return new Intl.DateTimeFormat('en-GB', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(moment);
}

// The identity stand-in plays the providers' pages at the real paths (`u8_identity_
// standin.page_target`): the realm's name resolution, done here by the browser's own
// routing, so no request ever leaves for Google or ORCID (U8 plan Step 100(f)).
export const STANDIN = 'https://localhost:18114';
const PROVIDER_PAGES =
  /^https:\/\/(accounts\.google\.com\/o\/oauth2\/v2\/auth|orcid\.org\/oauth\/authorize)\?/;

/** Routes the providers' authorization pages of a context to the identity stand-in. */
export async function routeProviders(context: BrowserContext): Promise<void> {
  await context.route(PROVIDER_PAGES, async (route) => {
    const address = new URL(route.request().url());
    await route.fulfill({
      status: 302,
      headers: {
        location: `${STANDIN}${address.pathname}${address.search}`,
        'cache-control': 'no-store',
      },
    });
  });
}

// The producers renew within twice the realm's 6 s freshness bound plus a renewal.
const FRESH_MINUTE_MS = 30_000;

/** Starts a minute of the realm's one clock for a spec's counted entry operations (U8 plan
 * Step 100(h)): AccountAccess counts them against 20 a minute per client address, on the
 * composition's clock. Called once the page has loaded the realm's origin. The jump leaves
 * the last observations 60 s old, so it waits until no navigation item is stale. */
export async function freshEntryMinute(page: Page): Promise<void> {
  harness('advance-clock', { seconds: 60 });
  await expect
    .poll(
      async () =>
        (await resolvedNavigation(page)).items.filter(
          (item) => item.reasonKey === 'nav.capabilityStale',
        ).length,
      { timeout: FRESH_MINUTE_MS, intervals: [1_000, 2_000] },
    )
    .toBe(0);
}

export async function signInForm(page: Page) {
  await page.goto('/');
  await expect(page.getByTestId('entry-email')).toBeVisible();
}

// The realm's providers serve once their observations land, which can follow the served
// realm's first `/health/live` answer, or a clock advance that left them stale. The
// producers renew within twice the 6 s freshness bound plus a renewal (FRESH_MINUTE_MS).
const PROVIDERS_SERVING_MS = 45_000;
const PROVIDERS = ['provider.google', 'provider.orcid'] as const;

/** Each identity provider that does not serve yet, as `capability:state`, from the
 * signed-out capability list read in the page's own session. */
async function providersNotServing(page: Page): Promise<string[]> {
  return page.evaluate(async (ids) => {
    const answer = await fetch('/api/v2/capabilities', { cache: 'no-store' });
    if (answer.status !== 200) return [`capabilities:${answer.status}`];
    const body = (await answer.json()) as {
      items?: { capabilityId: string; state: string }[];
    };
    const stateOf = (id: string) =>
      body.items?.find((item) => item.capabilityId === id)?.state ?? 'absent';
    return ids
      .map((id) => `${id}:${stateOf(id)}`)
      .filter((value) => !value.endsWith(':available') && !value.endsWith(':degraded'));
  }, PROVIDERS);
}

/** The sign-in form with both provider buttons enabled. The shell reads the capability
 * list once per page load (`App.tsx:246-248`) and disables a provider's button while its
 * capability is neither available nor degraded (`provider-notice.tsx:44-50`), so a page
 * loaded before the providers' observations land keeps them disabled. This polls the
 * signed-out list until both providers serve, within a bound, then loads the form again. */
export async function signInFormWithProviders(page: Page) {
  await signInForm(page);
  await expect
    .poll(() => providersNotServing(page), {
      timeout: PROVIDERS_SERVING_MS,
      intervals: [1_000, 2_000],
    })
    .toEqual([]);
  await signInForm(page);
  await expect(page.getByTestId('provider-google')).toBeEnabled();
  await expect(page.getByTestId('provider-orcid')).toBeEnabled();
}

export async function login(page: Page, account: Account) {
  await signInForm(page);
  await page.getByTestId('entry-email').fill(account.email);
  await page.getByTestId('entry-password').fill(account.password);
  await page.getByTestId('entry-submit').click();
  await expect(page.getByTestId('logout')).toBeVisible();
  await signedInNavigation(page);
}

/** The navigation re-resolved for the session: no entry is still a sign-in prompt, so
 * a click opens the owner's view instead of the sign-in it asked for a moment before. */
export async function signedInNavigation(page: Page) {
  await expect(page.getByTestId('navigation')).not.toContainText('로그인 후 이용할 수 있습니다');
}

/** The administrator's sign-in with the second factor (the fixture's own factor). */
export async function loginAdministrator(page: Page, account: Administrator) {
  await signInForm(page);
  await page.getByTestId('entry-email').fill(account.email);
  await page.getByTestId('entry-password').fill(account.password);
  await page.getByTestId('entry-submit').click();
  await expect(page.getByTestId('mfa-form')).toBeVisible();
  await page.getByTestId('entry-factor').fill(await realmFactorCode(account.totpSeed));
  await page.getByTestId('mfa-submit').click();
  await expect(page.getByTestId('logout')).toBeVisible();
  await signedInNavigation(page);
}

export async function logout(page: Page) {
  await page.getByTestId('logout').click();
  await expect(page.getByTestId('entry-email')).toBeVisible();
}

export async function go(page: Page, route: string) {
  await page.getByTestId(`nav-${route}`).click();
}

/** One API call in the page's own session, with the transport's own headers for a
 * body-carrying call (`src/api.ts`): its status and fixed error code only. */
export async function apiCall(
  page: Page,
  path: string,
  body?: object,
): Promise<{ status: number; code: string | null; body: unknown }> {
  return page.evaluate(
    async ({ path, body }) => {
      const session = await (await fetch('/api/v2/session', { cache: 'no-store' })).json();
      const answer = await fetch(path, {
        method: body === undefined ? 'GET' : 'POST',
        cache: 'no-store',
        headers:
          body === undefined
            ? {}
            : {
                'Content-Type': 'application/json',
                'X-CSRF-Token': session.csrfToken ?? '',
                'Idempotency-Key': crypto.randomUUID(),
              },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      const type = answer.headers.get('content-type') ?? '';
      let value: unknown = null;
      if (type.includes('application/json')) value = await answer.json();
      else if (type.includes('text/event-stream') && answer.body) {
        // An event stream's first frame only: what it opens with, then it is closed.
        const reader = answer.body.getReader();
        const first = await reader.read();
        await reader.cancel();
        value = { frames: first.value ? new TextDecoder().decode(first.value).slice(0, 2048) : '' };
      } else await answer.body?.cancel();
      const code =
        value && typeof (value as { code?: unknown }).code === 'string'
          ? ((value as { code: string }).code as string)
          : null;
      return { status: answer.status, code, body: value };
    },
    { path, body },
  );
}

/** The server's resolved navigation, read in the page's own session. */
export async function resolvedNavigation(page: Page) {
  const value = await page.evaluate(async () => {
    const session = await (await fetch('/api/v2/session', { cache: 'no-store' })).json();
    // The transport's own headers for a body-carrying call (`src/api.ts`).
    const answer = await fetch('/api/v2/c01/host-resolve-navigation', {
      method: 'POST',
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': session.csrfToken ?? '',
        'Idempotency-Key': crypto.randomUUID(),
      },
      body: JSON.stringify({ routeId: 'search' }),
    });
    return { status: answer.status, body: (await answer.json()) as Record<string, unknown> };
  });
  if (value.status !== 200)
    throw new Error(`navigation answered ${value.status} ${String(value.body.code ?? '')}`);
  return value.body as {
    items: { routeId: string; available: boolean; reasonKey?: string | null }[];
  };
}

/** axe (WCAG 2.0 A/AA, 2.1 AA, 2.2 AA) on one surface; any violation fails, reported by
 * rule and target only, never content. */
export async function expectAccessible(page: Page, testId: string) {
  await expect(page.getByTestId(testId)).toBeVisible();
  const result = await new AxeBuilder({ page })
    .include(`[data-testid="${testId}"]`)
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
    .analyze();
  const violations = result.violations.map((violation) => ({
    rule: violation.id,
    targets: violation.nodes.map((node) => node.target.join(' ')),
  }));
  expect(violations, `${testId} has no axe violations`).toEqual([]);
}

/** Nothing scrolls sideways at 320 CSS pixels (WCAG 1.4.10). */
export async function expectReflow(page: Page, testId: string) {
  await page.setViewportSize({ width: 320, height: 720 });
  const overflowing = await page
    .getByTestId(testId)
    .evaluate((element) => element.scrollWidth > element.clientWidth + 1);
  expect(overflowing, `${testId} reflows at 320 CSS px`).toBe(false);
  await page.setViewportSize({ width: 1280, height: 720 });
}

/** Failure-only diagnostics: a refused API call's route, status and fixed code. */
export function captureFailures(page: Page) {
  const records: { method: string; path: string; status: number; code?: string }[] = [];
  const pending: Promise<void>[] = [];
  const record = (response: Response) => {
    const path = new URL(response.url()).pathname;
    if (records.length >= 24 || response.status() < 400 || !path.startsWith('/api/')) return;
    const item: (typeof records)[number] = {
      method: response.request().method(),
      path,
      status: response.status(),
    };
    records.push(item);
    pending.push(
      (async () => {
        try {
          const bytes = await response.body();
          if (bytes.length > 4096) return;
          const value = JSON.parse(bytes.toString('utf8')) as { code?: unknown };
          if (typeof value.code === 'string' && /^[A-Z_]{3,40}$/.test(value.code))
            item.code = value.code;
        } catch {
          /* an unreadable envelope keeps only its route and status */
        }
      })(),
    );
  };
  // API requests still unanswered when a journey fails, by route only (a hung read).
  const open = new Map<Request, { method: string; path: string; since: number }>();
  const started = (request: Request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith('/api/') && open.size < 64)
      open.set(request, { method: request.method(), path, since: Date.now() });
  };
  const ended = (request: Request) => {
    open.delete(request);
  };
  page.on('response', record);
  page.on('request', started);
  page.on('requestfinished', ended);
  page.on('requestfailed', ended);
  // Policy violations on this page and on every page its context opens later.
  watchPolicy(page.context());
  return async (info: TestInfo) => {
    page.off('response', record);
    page.off('request', started);
    page.off('requestfinished', ended);
    page.off('requestfailed', ended);
    page.context().off('page', watchPage);
    if (info.status === info.expectedStatus) {
      // An untaken policy violation fails a passing test too.
      assertNoViolations(page);
      return;
    }
    await Promise.allSettled(pending);
    const unanswered = [...open.values()].map((item) => ({
      method: item.method,
      path: item.path,
      pendingMs: Date.now() - item.since,
    }));
    const violations = takeContextViolations(page.context());
    if (records.length || unanswered.length || violations.length) {
      const body = Buffer.from(JSON.stringify({ refused: records, unanswered, violations }));
      await info.attach('api-failure-metadata', { body, contentType: 'application/json' });
      // The JUnit reporter keeps no attachment body: the same metadata beside the
      // failure's error context, in the run root's private evidence folder.
      writeFileSync(info.outputPath('api-failures.json'), body, { mode: 0o600 });
    }
  };
}

// --- Content Security Policy violations (U8 plan Step 96(i)) ------------------------------
// Each page's records hold only the refused directive's text, never page content.

const violationsOf = new WeakMap<Page, readonly string[]>();
const pagesOf = new WeakMap<BrowserContext, ReadonlySet<Page>>();

function directiveOf(text: string): string {
  const quoted = /directive:\s*"([^"]{1,200})"/.exec(text);
  return quoted?.[1] ?? 'unnamed-directive';
}

function watchPage(page: Page): void {
  if (violationsOf.has(page)) return;
  violationsOf.set(page, []);
  const context = page.context();
  pagesOf.set(context, new Set([...(pagesOf.get(context) ?? []), page]));
  page.on('console', (message: ConsoleMessage) => {
    const text = message.text();
    if (message.type() !== 'error' || !text.startsWith('Refused to')) return;
    if (!text.includes('Content Security Policy')) return;
    violationsOf.set(page, [...(violationsOf.get(page) ?? []), directiveOf(text)]);
  });
}

/** Records policy violations on every page of a context a spec opens itself: the pages it
 * holds now and every page it opens later. */
export function watchPolicy(context: BrowserContext): void {
  for (const page of context.pages()) watchPage(page);
  context.off('page', watchPage);
  context.on('page', watchPage);
}

/** One page's recorded violations, which are then cleared. */
export function takeViolations(page: Page): string[] {
  const found = [...(violationsOf.get(page) ?? [])];
  if (violationsOf.has(page)) violationsOf.set(page, []);
  return found;
}

function takeContextViolations(context: BrowserContext): string[] {
  return [...(pagesOf.get(context) ?? [])].flatMap((page) => takeViolations(page));
}

/** Fails on any violation still recorded on the page or on another page of its context. */
export function assertNoViolations(page: Page): void {
  const found = [...takeViolations(page), ...takeContextViolations(page.context())];
  expect(found, 'no Content Security Policy violation was left untaken').toEqual([]);
}

// --- checkScreen (U8 plan Step 96(i); L1-40, L1-55) ---------------------------------------

/** The region a screen's checks cover: the whole page, a static page's `main`, or the
 * workspace's `#main` with its navigation. */
export type ScreenRegion = 'page' | 'main' | 'workspace';
/** `menuOpen`: the screen is the 320 px navigation menu open, so the 320 px walk starts with
 * the menu open and follows focus from it into the page. */
export type ScreenOptions = { koreanNames?: boolean; menuOpen?: boolean };
/** Where one Tab stop of a menu walk is: the menu's state and the focused element's place. */
type MenuStop = { expanded: boolean; inNavigation: boolean; inMain: boolean };
type LiveRegion = {
  role: string | null;
  ariaLive: string | null;
  testId: string | null;
  insideMain: boolean;
};
type LiveRead = { appShell: boolean; liveRegions: LiveRegion[] };

const SCREEN_NAME = /^[a-z0-9-]+$/;
const VISIT_KINDS = ['keyboard', 'focus'] as const;
type VisitKind = (typeof VISIT_KINDS)[number];
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'];
const WIDE = 1280;
const NARROW = 320;
const VIEW_HEIGHT = 720;
const MIN_TARGET_PX = 24;
const MAX_WALK_STOPS = 400;
const REGION_SELECTORS: Readonly<Record<ScreenRegion, readonly string[]>> = {
  page: ['body'],
  main: ['main'],
  workspace: ['#main', '[data-testid="navigation"]'],
};
const ANNOUNCER_NEIGHBOURS = new Set(['nav-loading', 'nav-error']);
const NAME_EXCEPTIONS = new Set(['Google', 'ORCID', 'Notion', 'DocSuri']);
const EMAIL_NAME = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const HANGUL = /[가-힣]/;
const INTERACTIVE_ROLES =
  'button|link|textbox|searchbox|checkbox|radio|combobox|listbox|option|menuitem|tab|switch|slider|spinbutton';
const FOCUSABLE =
  'a[href], button, input:not([type="hidden"]), select, textarea, summary, ' +
  '[tabindex]:not([tabindex="-1"]), [contenteditable="true"]';

function privateRecord(name: string, value: object): void {
  // Exclusive creation: one screen recorded twice in one test fails that test.
  writeFileSync(test.info().outputPath(name), JSON.stringify(value), { flag: 'wx', mode: 0o600 });
}

/** Records one visit of a screen (`a11y-<kind>-<screen>.json`) in the test's output. */
export function recordVisit(screen: string, kind: VisitKind): void {
  if (!SCREEN_NAME.test(screen)) throw new Error('screen name outside its pattern');
  if (!VISIT_KINDS.includes(kind)) throw new Error('visit kind outside its set');
  privateRecord(`a11y-${kind}-${screen}.json`, { screen, kind });
}

async function axeAtBothWidths(page: Page, selectors: readonly string[]) {
  const violations: { scheme: string; width: number; rule: string; targets: string[] }[] = [];
  let contrastEvaluated = true;
  for (const scheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    if (scheme === 'dark') {
      // A saved appearance would turn the dark pass into a second light pass.
      const themed = await page.evaluate(() => document.documentElement.hasAttribute('data-theme'));
      expect(themed, 'the dark pass meets no saved appearance').toBe(false);
    }
    for (const width of [WIDE, NARROW]) {
      await page.setViewportSize({ width, height: VIEW_HEIGHT });
      const builder = selectors.reduce(
        (axe, selector) => axe.include(selector),
        new AxeBuilder({ page }).withTags(AXE_TAGS),
      );
      const result = await builder.analyze();
      const evaluated = [...result.passes, ...result.violations].some(
        (rule) => rule.id === 'color-contrast',
      );
      contrastEvaluated = contrastEvaluated && evaluated;
      for (const violation of result.violations)
        violations.push({
          scheme,
          width,
          rule: violation.id,
          targets: violation.nodes.map((node) => node.target.join(' ')),
        });
    }
  }
  await page.emulateMedia({ colorScheme: null });
  await page.setViewportSize({ width: WIDE, height: VIEW_HEIGHT });
  return { violations, contrastEvaluated };
}

async function smallTargets(page: Page, selectors: readonly string[]): Promise<string[]> {
  const skip = page.locator('a[href="#main"]').first();
  if (await skip.count()) await skip.focus();
  return page.evaluate(
    ({ selectors, focusable, minimum }) => {
      const visible = (element: Element) => {
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return box.width > 0 && box.height > 0 && style.visibility !== 'hidden';
      };
      // A link inside prose is exempt (L1-40); separator punctuation such as ' · ' between
      // links is not prose, so only a sibling text holding a letter counts.
      const inSentence = (element: Element) =>
        element.tagName === 'A' &&
        [...(element.parentElement?.childNodes ?? [])].some(
          (node) => node.nodeType === Node.TEXT_NODE && /\p{L}/u.test(node.textContent ?? ''),
        );
      const boxOf = (element: Element) => {
        const own = element.getBoundingClientRect();
        const input = element as HTMLInputElement;
        if (element.tagName !== 'INPUT' || !['checkbox', 'radio'].includes(input.type))
          return { width: own.width, height: own.height };
        const labels = [...(input.labels ?? [])].map((label) => label.getBoundingClientRect());
        const boxes = [own, ...labels];
        const left = Math.min(...boxes.map((box) => box.left));
        const right = Math.max(...boxes.map((box) => box.right));
        const top = Math.min(...boxes.map((box) => box.top));
        const bottom = Math.max(...boxes.map((box) => box.bottom));
        return { width: right - left, height: bottom - top };
      };
      const small: string[] = [];
      for (const selector of selectors)
        for (const region of document.querySelectorAll(selector))
          for (const element of region.querySelectorAll(focusable)) {
            if (!visible(element) || inSentence(element)) continue;
            const box = boxOf(element);
            if (box.width >= minimum && box.height >= minimum) continue;
            small.push(element.getAttribute('data-testid') ?? element.tagName.toLowerCase());
          }
      return small;
    },
    { selectors, focusable: FOCUSABLE, minimum: MIN_TARGET_PX },
  );
}

async function nonKoreanNames(page: Page, selectors: readonly string[]): Promise<string[]> {
  // The role ends before its name, a colon or the line's end, so `table`, `tablist`,
  // `radiogroup` or `menuitemradio` is never read as `tab`, `radio` or `menuitem`.
  const line = new RegExp(
    `^\\s*- (?:${INTERACTIVE_ROLES})(?=[\\s:"]|$)(?: "((?:[^"\\\\]|\\\\.)*)")?`,
  );
  const refused: string[] = [];
  for (const selector of selectors) {
    const regions = page.locator(selector);
    for (let index = 0; index < (await regions.count()); index += 1) {
      for (const entry of (await regions.nth(index).ariaSnapshot()).split('\n')) {
        const match = line.exec(entry);
        if (match === null) continue;
        const name = match[1] ?? '';
        if (HANGUL.test(name) || NAME_EXCEPTIONS.has(name) || EMAIL_NAME.test(name)) continue;
        refused.push(name);
      }
    }
  }
  return refused;
}

/** The 320 CSS px reflow, through `#main` where the page has one or the document
 * otherwise, with its full-page capture `320-<screen>.png`. */
async function reflowAtNarrow(page: Page, screen: string) {
  await page.setViewportSize({ width: NARROW, height: VIEW_HEIGHT });
  const sideways = await page.evaluate(() => {
    const main = document.querySelector('#main');
    const pageOverflow = document.documentElement.scrollWidth > window.innerWidth + 1;
    return main === null ? pageOverflow : main.scrollWidth > main.clientWidth + 1 || pageOverflow;
  });
  const capture = `320-${screen}.png`;
  const bytes = await page.screenshot({ path: test.info().outputPath(capture), fullPage: true });
  await page.setViewportSize({ width: WIDE, height: VIEW_HEIGHT });
  return { sideways, capture, captureSha256: createHash('sha256').update(bytes).digest('hex') };
}

type Stop = { index: number; problems: string[] };

/** One Tab stop: the focused element's index among the region's controls (-1 outside it),
 * and what its focus indicator, viewport and hit test lack. */
async function readStop(page: Page): Promise<Stop | null> {
  return page.evaluate(() => {
    const active = document.activeElement;
    if (active === null || active === document.body) return null;
    const controls = (Reflect.get(window, '__u8WalkControls') ?? []) as Element[];
    const index = controls.indexOf(active);
    if (index < 0) return { index, problems: [] };
    const channels = (color: string) => (color.match(/[\d.]+/g) ?? []).map(Number);
    const luminance = ([r = 0, g = 0, b = 0]: number[]) => {
      const linear = (value: number) => {
        const unit = value / 255;
        return unit <= 0.03928 ? unit / 12.92 : ((unit + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
    };
    const background = () => {
      for (let node = active.parentElement; node; node = node.parentElement) {
        const value = channels(getComputedStyle(node).backgroundColor);
        if (value.length >= 3 && (value.length === 3 || value[3] === 1)) return value;
      }
      return [255, 255, 255];
    };
    const style = getComputedStyle(active);
    let indicator: number[] | null = null;
    if (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) >= 2)
      indicator = channels(style.outlineColor);
    else if (style.boxShadow !== 'none') {
      const lengths = (style.boxShadow.match(/-?[\d.]+px/g) ?? []).map(parseFloat);
      if (Math.max(lengths[2] ?? 0, lengths[3] ?? 0) >= 2)
        indicator = channels(/rgba?\([^)]*\)/.exec(style.boxShadow)?.[0] ?? '');
    }
    const problems: string[] = [];
    if (indicator === null) problems.push('no-focus-indicator');
    else {
      const levels = [luminance(indicator), luminance(background())];
      const [lighter = 0, darker = 0] = [...levels].sort((a, b) => b - a);
      if ((lighter + 0.05) / (darker + 0.05) < 3) problems.push('focus-contrast-below-3');
    }
    const box = active.getBoundingClientRect();
    const left = Math.max(box.left, 0);
    const right = Math.min(box.right, window.innerWidth);
    const top = Math.max(box.top, 0);
    const bottom = Math.min(box.bottom, window.innerHeight);
    if (right <= left || bottom <= top) problems.push('outside-the-viewport');
    else {
      const hit = document.elementFromPoint((left + right) / 2, (top + bottom) / 2);
      if (hit === null || !(hit === active || active.contains(hit))) problems.push('covered');
    }
    return { index, problems };
  });
}

const MENU_TOGGLE = '[data-testid="nav-menu-toggle"]';

/** Opens the 320 px menu where it is closed, through the toggle's own click handler and
 * without moving focus: `HTMLElement.click()` runs the handler and leaves the focused
 * element as it was. The menu is then asserted open. */
async function openMenuInPlace(page: Page): Promise<void> {
  const toggle = page.locator(MENU_TOGGLE);
  if ((await toggle.getAttribute('aria-expanded')) !== 'true')
    await toggle.evaluate((element) => (element as HTMLElement).click());
  await expect(toggle, 'the 320 px menu is open at the walk start').toHaveAttribute(
    'aria-expanded',
    'true',
  );
}

async function readMenuStop(page: Page): Promise<MenuStop> {
  return page.evaluate((selector) => {
    const active = document.activeElement;
    return {
      expanded: document.querySelector(selector)?.getAttribute('aria-expanded') === 'true',
      inNavigation: active?.closest('[data-testid="navigation"]') != null,
      inMain: active?.closest('#main') != null,
    };
  }, MENU_TOGGLE);
}

/** The open menu's walk: it visits the menu's controls with the menu open, and the menu
 * has closed by the first stop inside `#main`, so no later stop sits under it. */
function expectMenuClosesIntoPage(stops: readonly MenuStop[], width: number): void {
  const inMenu = stops.filter((stop) => stop.inNavigation);
  expect(inMenu.length, `the ${width}px walk visits the open menu`).toBeGreaterThan(1);
  expect(
    inMenu.every((stop) => stop.expanded),
    `the menu stays open while focus is in it at ${width}px`,
  ).toBe(true);
  const intoPage = stops.find((stop) => stop.inMain);
  expect(intoPage, `the ${width}px walk reaches #main`).toBeDefined();
  expect(intoPage?.expanded, `the menu has closed once focus is inside #main at ${width}px`).toBe(
    false,
  );
}

/** The Tab walk over the region at one width: DOM order until the walk returns to its
 * first stop, no `tabindex` above 0, and every enabled control of the region reached.
 * The region's controls are ordered by document position (the workspace's navigation
 * comes before `#main`), and only what Tab can reach is counted: one stop per radio
 * group, none for an element whose `tabindex` is negative.
 *
 * The walk starts from a fixed point, never from wherever focus was: blur() does not reset
 * Chromium's sequential focus starting point, so a walk begun after a blur would start
 * past the element last focused. The setup focuses the first reachable control of the
 * document (of the open modal dialog when there is one) and counts it as the first stop.
 * While a modal dialog is open, only its own controls count: its script traps Tab, so
 * nothing behind it is reachable.
 *
 * With `menuOpen`, the 320 px menu is open when the region's controls are collected, so every
 * entry of the open menu is a stop the walk must reach. The setup's Shift+Tab back to the
 * skip link moves focus out of the navigation, which closes the menu (N2), so the menu is
 * opened again before the first stop. The walk then asserts that the menu stays open while
 * focus is inside it and has closed by the first stop inside `#main`. */
async function walkFocus(
  page: Page,
  selectors: readonly string[],
  width: number,
  menuOpen = false,
) {
  await page.setViewportSize({ width, height: VIEW_HEIGHT });
  if (menuOpen) await openMenuInPlace(page);
  const walk = await page.evaluate(
    ({ selectors, focusable }) => {
      const reachable = (element: Element) => {
        const box = element.getBoundingClientRect();
        const disabled = (element as HTMLButtonElement).disabled === true;
        const skipped = (element as HTMLElement).tabIndex < 0;
        if (disabled || skipped || box.width <= 0 || box.height <= 0) return false;
        // A closed <details> keeps a box for its content, but Tab reaches only its summary.
        const closed = element.closest('details:not([open])');
        const summary = element.tagName === 'SUMMARY' && element.parentElement === closed;
        if (closed !== null && !summary) return false;
        return element.closest('[inert]') === null;
      };
      const modal = document.querySelector('[role="dialog"][aria-modal="true"]');
      const found = new Set<Element>();
      for (const selector of selectors)
        for (const region of document.querySelectorAll(selector))
          for (const element of region.querySelectorAll(focusable)) {
            if (!reachable(element)) continue;
            if (modal !== null && !modal.contains(element)) continue;
            found.add(element);
          }
      if (modal !== null && modal.matches(focusable) && reachable(modal)) found.add(modal);
      const controls = [...found].sort((a, b) =>
        a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
      );
      // Tab stops once per radio group (same name in the same form); every other control
      // is its own stop.
      const radioGroups = new Map<string, number>();
      const stopOf = controls.map((element, index) => {
        const input = element as HTMLInputElement;
        if (element.tagName !== 'INPUT' || input.type !== 'radio' || input.name === '')
          return index;
        const formIndex = input.form === null ? -1 : [...document.forms].indexOf(input.form);
        const key = `${formIndex}:${input.name}`;
        if (!radioGroups.has(key)) radioGroups.set(key, index);
        return radioGroups.get(key) ?? index;
      });
      Reflect.set(window, '__u8WalkControls', controls);
      // The fixed starting point: the first reachable control of the scope Tab moves in.
      const scope = modal ?? document;
      const start = [...scope.querySelectorAll<HTMLElement>(focusable)].find(reachable);
      if (start === undefined) Reflect.deleteProperty(window, '__u8WalkFirst');
      else {
        start.focus();
        Reflect.set(window, '__u8WalkFirst', start);
      }
      // Each control by test id, else tag and id: what a failure names, never content.
      const labels = controls.map(
        (element) =>
          element.getAttribute('data-testid') ??
          `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ''}`,
      );
      return { stopOf, labels };
    },
    { selectors, focusable: FOCUSABLE },
  );
  const groups = walk.stopOf;
  // A script's focus after a pointer press shows no `:focus-visible` indicator, so the
  // starting point is reached again by keyboard, as every later stop is: one Tab away and
  // one Shift+Tab back.
  if (await page.evaluate(() => Reflect.has(window, '__u8WalkFirst'))) {
    await page.keyboard.press('Tab');
    await page.keyboard.press('Shift+Tab');
  }
  if (menuOpen) await openMenuInPlace(page);
  const menuStops: MenuStop[] = [];
  const count = new Set(groups).size;
  const positive = await page.evaluate(() => {
    const ordered = [...document.querySelectorAll<HTMLElement>('[tabindex]')];
    return ordered.filter((element) => element.tabIndex > 0).length;
  });
  expect(positive, 'no element has a tabindex above 0').toBe(0);
  const order: number[] = [];
  const problems: string[] = [];
  const record = (stop: Stop) => {
    order.push(stop.index);
    problems.push(...stop.problems.map((problem) => `${width}px stop ${stop.index}: ${problem}`));
  };
  // The starting point is the walk's first stop.
  const first = await readStop(page);
  if (first !== null && first.index >= 0) record(first);
  for (let step = 0; step < MAX_WALK_STOPS; step += 1) {
    await page.keyboard.press('Tab');
    const stop = await readStop(page);
    if (stop === null) continue;
    // The first stop is recognised by the element itself, held on the window, never by a
    // tag, test id or sibling index another element may share.
    const returned = await page.evaluate(() => {
      const active = document.activeElement;
      const first = Reflect.get(window, '__u8WalkFirst') as Element | undefined;
      if (first === undefined) {
        Reflect.set(window, '__u8WalkFirst', active);
        return false;
      }
      return first === active;
    });
    if (returned) break;
    if (menuOpen) menuStops.push(await readMenuStop(page));
    if (stop.index < 0) continue;
    record(stop);
  }
  await page.evaluate(() => {
    Reflect.deleteProperty(window, '__u8WalkControls');
    Reflect.deleteProperty(window, '__u8WalkFirst');
  });
  await page.setViewportSize({ width: WIDE, height: VIEW_HEIGHT });
  if (menuOpen) expectMenuClosesIntoPage(menuStops, width);
  expect(problems, `every focus stop at ${width}px is visible, in view and on top`).toEqual([]);
  const ascending = [...order].sort((a, b) => a - b);
  expect(order, `the stops at ${width}px follow DOM order`).toEqual(ascending);
  const reached = new Set(order.map((index) => groups[index]));
  const unreached = walk.labels.filter((_, index) => !reached.has(groups[index]));
  expect(unreached, `every enabled control is reached at ${width}px`).toEqual([]);
  expect(reached.size, `every enabled control is reached at ${width}px`).toBe(count);
}

/** Every live region in the whole document, by role, politeness, test id and place, never
 * its text, and whether the page carries the app shell. */
async function readLiveRegions(page: Page): Promise<LiveRead> {
  return page.evaluate(() => ({
    appShell: document.querySelector('[data-testid="app-shell"]') !== null,
    liveRegions: [...document.querySelectorAll('[aria-live], [role="status"], [role="alert"]')].map(
      (element) => ({
        role: element.getAttribute('role'),
        ariaLive: element.getAttribute('aria-live'),
        testId: element.getAttribute('data-testid'),
        insideMain: element.closest('#main') !== null,
      }),
    ),
  }));
}

function expectOneAnnouncer(liveRegions: readonly LiveRegion[]): void {
  const outside = liveRegions.filter((region) => !region.insideMain);
  const announcers = outside.filter((region) => region.testId === 'announcer');
  expect(announcers, 'the app shell renders one announcer outside #main').toHaveLength(1);
  expect(announcers[0], 'the announcer is a polite status').toMatchObject({
    role: 'status',
    ariaLive: 'polite',
  });
  const others = outside.filter(
    (region) => region.testId !== 'announcer' && !ANNOUNCER_NEIGHBOURS.has(region.testId ?? ''),
  );
  expect(others, 'no other live region outside #main but nav-loading and nav-error').toEqual([]);
}

/** One screen's accessibility checks (Step 96(i)): axe with the four tags at 1280 and
 * 320 CSS px in both schemes; 24 by 24 targets; `<html lang="ko">`; Hangul control names
 * on screens U8 adds or changes; the 320 px reflow with its capture; the Tab walk at both
 * widths; and, last, one read of the page's live regions. It writes the check record
 * `a11y-check-<screen>.json`, then a keyboard and a focus visit. */
export async function checkScreen(
  page: Page,
  screen: string,
  region: ScreenRegion,
  options: ScreenOptions = {},
): Promise<void> {
  if (!SCREEN_NAME.test(screen)) throw new Error('screen name outside its pattern');
  const selectors = REGION_SELECTORS[region];
  await expect(page.locator(selectors[0] ?? 'body').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.lang), 'the page is Korean').toBe('ko');
  const { violations, contrastEvaluated } = await axeAtBothWidths(page, selectors);
  expect(violations, `${screen} has no axe violations`).toEqual([]);
  expect(await smallTargets(page, selectors), `${screen} has no target below 24 px`).toEqual([]);
  if (options.koreanNames) {
    const refused = await nonKoreanNames(page, selectors);
    expect(refused, `${screen} names its controls in Korean`).toEqual([]);
  }
  const reflow = await reflowAtNarrow(page, screen);
  expect(reflow.sideways, `${screen} reflows at 320 CSS px`).toBe(false);
  await walkFocus(page, selectors, WIDE);
  await walkFocus(page, selectors, NARROW, options.menuOpen === true);
  const { appShell, liveRegions } = await readLiveRegions(page);
  if (appShell) expectOneAnnouncer(liveRegions);
  privateRecord(`a11y-check-${screen}.json`, {
    violations,
    colorContrastEvaluated: contrastEvaluated,
    sidewaysScroll: reflow.sideways,
    capture: reflow.capture,
    captureSha256: reflow.captureSha256,
    appShell,
    liveRegions,
  });
  recordVisit(screen, 'keyboard');
  recordVisit(screen, 'focus');
}

/** Clears the page's storage after a spec, so nothing private outlives it. */
export async function scrub(page: Page) {
  await page.context().clearCookies();
  await page
    .evaluate(() => {
      try {
        window.localStorage.clear();
        window.sessionStorage.clear();
      } catch {
        /* storage may be unavailable; nothing to clear */
      }
    })
    .catch(() => undefined);
}

// --- The isolation table, made-up identifiers and the request log (Step 168(d); L4-13) ---

export type IsolationRow = {
  method: string;
  path: string;
  kind: string;
  probe?: string;
  reason?: string;
  notClaimed?: string;
  anonymous?: boolean;
};
export type IsolationTable = { routes: IsolationRow[]; destinations: string[] };

/** The isolation table `integration/test_route_inventory.py` ties to the host's own
 * inventory: one row for every route the composed host mounts. */
export function isolationTable(): IsolationTable {
  const path = join(
    repositoryRoot,
    'tests/u8_service_operations_integration/isolation_routes.json',
  );
  return JSON.parse(readFileSync(path, 'utf8')) as IsolationTable;
}

/** A made-up identifier of a UUID's shape, new on every call. */
export function madeUpId(): string {
  return randomUUID();
}

/** A made-up SHA-256 in hexadecimal, new on every call. */
export function madeUpHash(): string {
  return randomBytes(32).toString('hex');
}

export type Ask = { path: string; body?: object; method?: string };
export type Answer = { status: number; code: string | null; body: unknown };
export type Asked = { pass: string; probe: string; path: string; status: number };

/** One request in the page's own session with any method. GET and body-carrying POST go
 * through `apiCall`; PUT and DELETE carry the transport's same headers. */
export async function apiRequest(page: Page, ask: Ask): Promise<Answer> {
  const method = ask.method ?? (ask.body === undefined ? 'GET' : 'POST');
  if (method === 'GET') return apiCall(page, ask.path);
  if (method === 'POST') return apiCall(page, ask.path, ask.body ?? {});
  return page.evaluate(
    async ({ method, path, body }) => {
      const session = await (await fetch('/api/v2/session', { cache: 'no-store' })).json();
      const answer = await fetch(path, {
        method,
        cache: 'no-store',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': session.csrfToken ?? '',
          'Idempotency-Key': crypto.randomUUID(),
        },
        body: JSON.stringify(body),
      });
      const type = answer.headers.get('content-type') ?? '';
      const value: unknown = type.includes('application/json') ? await answer.json() : null;
      const code = (value as { code?: unknown } | null)?.code;
      return { status: answer.status, code: typeof code === 'string' ? code : null, body: value };
    },
    { method, path: ask.path, body: ask.body ?? {} },
  );
}

/** Whether a request path (its query set aside) is one the route template serves. */
export function servedBy(template: string, path: string): boolean {
  const pattern = template
    .split(/\{[^}]+\}/)
    .map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('[^/]+');
  return new RegExp(`^${pattern}$`).test(path.split('?')[0] ?? '');
}

/** The isolation journey's request log: every probe's request is sent through `ask`,
 * which refuses a request its row's route does not serve and records the pass, the
 * probe and the answer's status, so the run itself shows what was asked. */
export function requestLog() {
  const entries: Asked[] = [];
  return {
    entries,
    async ask(page: Page, pass: string, row: IsolationRow, ask: Ask): Promise<Answer> {
      const method = ask.method ?? (ask.body === undefined ? 'GET' : 'POST');
      if (method !== row.method || !servedBy(row.path, ask.path))
        throw new Error(`${method} ${ask.path} is not ${row.method} ${row.path}`);
      const answer = await apiRequest(page, ask);
      entries.push({ pass, probe: row.probe ?? '', path: row.path, status: answer.status });
      return answer;
    },
    /** A request sent by other means (the asset reads), recorded as asked. */
    note(pass: string, row: IsolationRow, status: number): void {
      entries.push({ pass, probe: row.probe ?? '', path: row.path, status });
    },
    asked(pass: string): Set<string> {
      return new Set(entries.filter((entry) => entry.pass === pass).map((entry) => entry.probe));
    },
  };
}

// --- The synthetic v1 at the public address (Step 168(e); L4-14) ---------------------------

/** v1's own sign-in, asked by the page at the public address while v1's web answers it
 * (v1's web relays `/bff/auth/login` and its session cookie to v1's API): the answer's
 * status. The address and password are the run's own (`v1Dataset`). */
export async function v1SignIn(page: Page, email: string, password: string): Promise<number> {
  await page.goto('/bff/health');
  return page.evaluate(
    async ({ email, password }) => {
      const answer = await fetch('/bff/auth/login', {
        method: 'POST',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      await answer.body?.cancel();
      return answer.status;
    },
    { email, password },
  );
}

/** v1's own session check in the page's session: the answer's status and whether it
 * names a user. v1 answers 200 with `userId` while signed in and 401 otherwise, and its
 * sign-in refuses with 401 (`backend/modules/accounts/controller.py`). */
export async function v1SessionCheck(page: Page): Promise<{ status: number; signedIn: boolean }> {
  await page.goto('/bff/health');
  return page.evaluate(async () => {
    const answer = await fetch('/bff/auth/session', { cache: 'no-store' });
    const body = (await answer.json().catch(() => null)) as { userId?: unknown } | null;
    return { status: answer.status, signedIn: answer.status === 200 && Boolean(body?.userId) };
  });
}

/** Whether v1's own session check answers this page's session as signed in. */
export async function v1SessionActive(page: Page): Promise<boolean> {
  return (await v1SessionCheck(page)).signedIn;
}

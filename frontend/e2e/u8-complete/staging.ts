// Staging helpers of the screens spec (`accessibility-screens.spec.ts`), moved here
// unchanged so that the spec and `notice-checks.ts` share them and each file stays under
// 800 lines. Every staged answer is a `page.route` fulfilment in the page's own context,
// never `route.fetch`. A changed read is the realm's own answer to the same read, fetched
// first through the page and served back changed.
import { expect, type Locator, type Page, type Route } from '@playwright/test';
import { apiCall } from './helpers';

export const CAPABILITIES = '/api/v2/capabilities';
// A syntactically valid email-link fragment whose proof no realm issued.
export const PLACEHOLDER_FRAGMENT =
  '#challenge=00000000-0000-4000-8000-000000000000&proof=u8-placeholder&flow=u8-placeholder';
export const NOTICE = 'DocSuri를 점검하고 있습니다. 잠시 후 다시 접속해 주세요.';
// A research job link in `readJobLink`'s form, with placeholder ids no realm job carries.
export const JOB_LINK =
  '/#research-job?jobId=00000000-0000-4000-8000-0000000000b1&kind=research-turn' +
  '&contextId=00000000-0000-4000-8000-0000000000c1';

export type Capabilities = {
  manifestRevision: string;
  items: { capabilityId: string; state: string; reasonKey: string }[];
};

// One matcher per path: `page.unroute` removes a route only when given the very matcher
// `page.route` was given.
const matchers = new Map<string, (url: URL) => boolean>();
export function onPath(path: string): (url: URL) => boolean {
  const known = matchers.get(path);
  if (known) return known;
  const matcher = (url: URL) => url.pathname === path;
  matchers.set(path, matcher);
  return matcher;
}

/** The page once its first reads have settled: the navigation resolved (or refused) and no
 * request in flight, so a view mounting late cannot move the focus during a walk. */
export async function settled(page: Page): Promise<void> {
  await expect(page.getByTestId('nav-loading')).toHaveCount(0);
  await page.waitForLoadState('networkidle');
}

/** A route answering `path` with one JSON body; returns its removal. */
export async function stageJson(
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

/** A route holding every request to `path` until it is released (continued to the realm)
 * or aborted. */
export async function holdRoute(page: Page, path: string) {
  const held: Route[] = [];
  let open = true;
  const handler = async (route: Route) => {
    if (!open) {
      await route.continue();
      return;
    }
    held.push(route);
  };
  await page.route(onPath(path), handler);
  const end = async (settle: (route: Route) => Promise<void>) => {
    open = false;
    await page.unroute(onPath(path), handler);
    for (const route of held.splice(0)) {
      try {
        await settle(route);
      } catch (error) {
        // A held request the page itself gave up (a reload, an unmount) is already ended.
        if (!String(error).includes('Route is already handled')) throw error;
      }
    }
  };
  return {
    count: () => held.length,
    release: () => end((route) => route.continue()),
    abort: () => end((route) => route.abort()),
  };
}

/** The realm's own signed-out capability answer, read through the page. */
export async function realmCapabilities(page: Page): Promise<Capabilities> {
  const answer = await apiCall(page, CAPABILITIES);
  expect(answer.status).toBe(200);
  return answer.body as Capabilities;
}

/** The realm's own answer with each named capability changed. A staged answer never adds
 * a capability the realm's answer lacks: a name it does not carry fails the test. */
export function changedCapabilities(
  answer: Capabilities,
  changes: Readonly<Record<string, { state?: string; reasonKey?: string }>>,
): Capabilities {
  const known = new Set(answer.items.map((item) => item.capabilityId));
  for (const id of Object.keys(changes))
    expect(known.has(id), `the realm's signed-out answer carries ${id}`).toBe(true);
  const items = answer.items.map((item) =>
    changes[item.capabilityId] ? { ...item, ...changes[item.capabilityId] } : item,
  );
  return { ...answer, items };
}

/** An email link's page with the placeholder fragment, opened as a new document. */
export async function openPlaceholderLink(page: Page, path: string): Promise<void> {
  await page.goto('about:blank');
  await page.goto(`${path}${PLACEHOLDER_FRAGMENT}`);
}

/** The panel holds the page's one maintenance notice, with its 관리자 로그인. */
export async function expectOneNotice(page: Page, panel: Locator): Promise<void> {
  const banner = panel.getByTestId('maintenance-banner');
  await expect(banner).toContainText(NOTICE);
  await expect(banner.getByTestId('maintenance-admin-sign-in')).toHaveText('관리자 로그인');
  await expect(page.getByTestId('maintenance-banner')).toHaveCount(1);
}

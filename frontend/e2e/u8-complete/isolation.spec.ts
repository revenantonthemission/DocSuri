// J03 and J13 (BR10.3, NFR1.1; U8 plan Step 168(d), L4-13): two owners are checked on
// every list, read, event and asset of the complete application, row by row of the
// isolation table (`tests/u8_service_operations_integration/isolation_routes.json`, which
// a Python test ties to the host's own inventory).
//
// memberA first comes to own a record on every owner list and reads every row as its
// owner: the positive control. memberB then gets lists without memberA's markers, and for
// every read by identifier exactly the answer a made-up identifier of the same shape
// gets. memberA asks for the records memberB holds in the reverse pass. Signed out, every
// guarded row is refused, a real and a made-up identifier alike. The last test shows from
// the run's own request log that every probed row was asked in each pass, and removes
// what can be removed. A paper's asset belongs to its paper, not to an owner: both owners
// read it and get the same answer (L3-4). The probes use soft assertions, so one run
// lists every row that failed.
import { test, expect, type Page } from '@playwright/test';
import {
  apiCall,
  captureFailures,
  ensureNotionConnected,
  exportNoveltyTo,
  fixtures,
  go,
  isolationTable,
  login,
  logout,
  madeUpHash,
  madeUpId,
  requestLog,
  scrub,
  writeMeasurements,
  type Answer,
  type Ask,
  type IsolationRow,
  type PaperAsset,
} from './helpers';
import {
  LIMIT,
  PROBES,
  firstMatch,
  firstTurn,
  heldTurn,
  listSessions,
  longestList,
  other,
  owner,
  plainRequest,
  reverseReads,
  sessionIds,
  suggestionsByLink,
  type Probe,
} from './isolation-probes';

test.describe.configure({ mode: 'serial' });

const diagnostics = new WeakMap<Page, ReturnType<typeof captureFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureFailures(page));
});
test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

const SIGNED_OUT = [401, 403];
// How long a record the journey just made may take to show in its owner's own read.
const RECORD_WAIT_MS = 20_000;
const TABLE = isolationTable();
const PROBED = TABLE.routes.filter((row) => row.probe !== undefined);
const OWNER_VIEWS = [
  'library',
  'research',
  'novelty',
  'jobs',
  'topics',
  'export',
  'settings',
  'usage',
  'account',
];
const log = requestLog();
const notClaimed: string[] = [];
let ownerAsset: AssetAnswers | null = null;
// The public address the first test signed in at, for the cleanup's own window.
let origin = '';

const READ_ASSET = '/api/v2/c04/read-asset';
const PRESIGNED_MARKERS = ['://', 'X-Amz-', 'Signature=', 'Expires='];

type ByteAnswer = {
  status: number;
  type: string;
  cacheControl: string;
  nosniff: string;
  code: string | null;
  sha256: string | null;
};
type AssetAnswers = {
  eligibleRead: { status: number; code: string | null; body: unknown };
  eligibleBytes: ByteAnswer;
  ineligibleRead: { status: number; code: string | null };
  ineligibleBytes: ByteAnswer;
};

function assetBody(asset: PaperAsset) {
  return { paper: asset.paper, contentRevision: asset.contentRevision, assetId: asset.assetId };
}

/** C13's byte route, each identifier encoded. */
function bytePath(asset: PaperAsset) {
  const { paperId, versionId } = asset.paper;
  return (
    `/api/v2/papers/${encodeURIComponent(paperId)}/versions/` +
    `${encodeURIComponent(versionId)}/assets/${encodeURIComponent(asset.assetId)}`
  );
}

/** An asset's bytes read in the page's own session (page.request cannot reach the pinned
 * origin): the answer's headers, and the refusal's code or the bytes' SHA-256. */
async function readAssetBytes(page: Page, path: string): Promise<ByteAnswer> {
  return page.evaluate(async (path) => {
    const answer = await fetch(path, { cache: 'no-store' });
    const type = answer.headers.get('content-type') ?? '';
    const head = {
      status: answer.status,
      type,
      cacheControl: answer.headers.get('cache-control') ?? '',
      nosniff: answer.headers.get('x-content-type-options') ?? '',
    };
    if (type.includes('application/json')) {
      const body = (await answer.json()) as { code?: unknown };
      return { ...head, code: typeof body.code === 'string' ? body.code : null, sha256: null };
    }
    const digest = await crypto.subtle.digest('SHA-256', await answer.arrayBuffer());
    const hex = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0'));
    return { ...head, code: null, sha256: hex.join('') };
  }, path);
}

/** The four asset requests of J03, in order: the eligible read and bytes, then the
 * ineligible read and bytes; each route is recorded as asked in `pass`. */
async function readOwnerAssets(page: Page, pass: string): Promise<AssetAnswers> {
  const { eligible, ineligible } = fixtures().paperAsset;
  const eligibleRead = await apiCall(page, READ_ASSET, assetBody(eligible));
  const eligibleBytes = await readAssetBytes(page, bytePath(eligible));
  const refused = await apiCall(page, READ_ASSET, assetBody(ineligible));
  const ineligibleBytes = await readAssetBytes(page, bytePath(ineligible));
  log.note(pass, rowOf('readAsset'), eligibleRead.status);
  log.note(pass, rowOf('assetBytes'), eligibleBytes.status);
  return {
    eligibleRead,
    eligibleBytes,
    ineligibleRead: { status: refused.status, code: refused.code },
    ineligibleBytes,
  };
}

// --- The probes are in `isolation-probes.ts`: one for every probed row of the table -------

/** Every probed row without a probe, and every probe without a row. */
function loadProblems(): string[] {
  const named = new Set(PROBED.map((row) => row.probe ?? ''));
  return [
    ...PROBED.filter((row) => PROBES[row.probe ?? ''] === undefined).map(
      (row) => `no probe for ${row.method} ${row.path} (${row.probe})`,
    ),
    ...Object.keys(PROBES)
      .filter((name) => !named.has(name))
      .map((name) => `probe ${name} belongs to no row`),
  ];
}

function rowOf(probe: string): IsolationRow {
  const row = PROBED.find((candidate) => candidate.probe === probe);
  if (row === undefined) throw new Error(`no row names the probe ${probe}`);
  return row;
}

function probeOf(row: IsolationRow): Probe {
  const probe = PROBES[row.probe ?? ''];
  if (probe === undefined) throw new Error(`no probe for ${row.method} ${row.path}`);
  return probe;
}

/** One logged request. A list read while its owner's records change answers
 * SNAPSHOT_EXPIRED (U4's consistent listing), and is read again. */
async function ask(page: Page, pass: string, row: IsolationRow, request: Ask): Promise<Answer> {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const answer = await log.ask(page, pass, row, request);
    if (answer.code !== 'SNAPSHOT_EXPIRED') return answer;
    await page.waitForTimeout(500);
  }
  throw new Error(`${row.path} never settled`);
}

/** What two answers must share to be alike: the status, the fixed code, and for an
 * event stream what its first frame is. */
function shape(answer: Answer): [number, string | null, string] {
  const frames = (answer.body as { frames?: unknown } | null)?.frames;
  if (typeof frames !== 'string') return [answer.status, answer.code, ''];
  const event = /event: ([a-z-]+)/.exec(frames)?.[1] ?? '';
  return [answer.status, answer.code, `${event}${/NOT_FOUND/.test(frames) ? ':NOT_FOUND' : ''}`];
}

/** Every account identifier in an answer that is not the caller's. */
function foreignAccounts(text: string, accountId: string): string[] {
  return [...text.matchAll(/"(?:accountId|ownerId)":"([0-9a-f-]{36})"/g)]
    .map((match) => match[1] ?? '')
    .filter((found) => found !== accountId);
}

// --- The passes ----------------------------------------------------------------------------

/** memberA's pass: every row answers its owner with its own data, except the rows the
 * table marks `notClaimed`, whose status is only recorded. */
async function ownerPass(page: Page, accountId: string) {
  for (const row of PROBED) {
    const probe = probeOf(row);
    for (const request of probe.real()) {
      const answer = await ask(page, 'owner', row, request);
      if (row.notClaimed !== undefined) {
        notClaimed.push(`${row.method} ${row.path}: its owner gets ${answer.status}`);
        continue;
      }
      const label = `${row.method} ${request.path} as its owner`;
      expect.soft(answer.status, label).toBe(200);
      const text = JSON.stringify(answer.body);
      const markers = probe.markers?.() ?? [];
      for (const marker of markers) {
        expect.soft(marker, `${label}: the record to look for was made`).not.toBe('');
        expect.soft(text, `${label} holds its owner's record`).toContain(marker);
      }
      expect.soft(foreignAccounts(text, accountId), `${label}: accounts`).toEqual([]);
      if (row.kind === 'owner-list' && markers.length === 0 && !probe.mayBeEmpty)
        expect.soft(longestList(answer.body), `${label} is not empty`).toBeGreaterThan(0);
    }
  }
}

/** Another member's pass over memberA's records: a list or an own read answers 200 with
 * none of memberA's markers; a read by identifier answers exactly as a made-up one. */
async function otherPass(page: Page, pass: string, accountId: string) {
  for (const row of PROBED) {
    const probe = probeOf(row);
    const wanted = probe.madeUp ? shape(await ask(page, pass, row, probe.madeUp())) : null;
    for (const request of probe.real()) {
      const answer = await ask(page, pass, row, request);
      const label = `${row.method} ${request.path} as the other member`;
      const text = JSON.stringify(answer.body);
      if (wanted !== null) {
        expect.soft(shape(answer), `${label} answers as a made-up identifier`).toEqual(wanted);
        expect.soft(answer.status, `${label} is never read`).not.toBe(200);
        expect.soft(foreignAccounts(text, accountId), `${label}: accounts`).toEqual([]);
        continue;
      }
      expect.soft(answer.status, label).toBe(200);
      for (const marker of probe.markers?.() ?? [])
        expect.soft(text, `${label} holds none of the owner's records`).not.toContain(marker);
      expect.soft(foreignAccounts(text, accountId), `${label}: accounts`).toEqual([]);
    }
  }
}

/** The signed-out pass: every guarded row refuses, and where a row takes an identifier a
 * real one and a made-up one are refused alike. */
async function signedOutPass(page: Page) {
  for (const row of TABLE.routes) {
    if (row.kind === 'public' || row.kind === 'token' || row.kind === 'asset') continue;
    const probe = row.probe === undefined ? undefined : probeOf(row);
    const requests = probe ? probe.real() : [plainRequest(row)];
    if (row.anonymous === true) {
      // Admitted with no session by its owner; an own read then names no account.
      for (const request of probe ? requests : []) {
        const answer = await ask(page, 'signedOut', row, request);
        expect
          .soft(foreignAccounts(JSON.stringify(answer.body), ''), `${row.path} signed out`)
          .toEqual([]);
      }
      continue;
    }
    const wanted = probe?.madeUp ? shape(await ask(page, 'signedOut', row, probe.madeUp())) : null;
    for (const request of requests) {
      const answer = await ask(page, 'signedOut', row, request);
      const label = `${row.method} ${request.path} signed out`;
      expect.soft(SIGNED_OUT, `${label} is refused (${answer.status})`).toContain(answer.status);
      if (wanted !== null) expect.soft(shape(answer), `${label} refuses alike`).toEqual(wanted);
    }
  }
}

// --- The records ---------------------------------------------------------------------------

/** The personalization consent set to `decision`; the recent-papers list refuses anyone
 * whose consent is off. */
async function setPersonalization(page: Page, decision: 'granted' | 'revoked') {
  const consents = (await apiCall(page, '/api/v2/c02/access-list-consents', LIMIT)).body as {
    items: { purposeId: string; decision: string; revision: string }[];
    policyRef: object;
  };
  const record = consents.items.find((item) => item.purposeId === 'personalization');
  expect(record, 'the personalization consent is listed').toBeDefined();
  if (record!.decision === decision) return;
  const answer = await apiCall(page, '/api/v2/c02/access-update-consent', {
    purposeId: 'personalization',
    decision,
    policyRef: consents.policyRef,
    expectedRevision: record!.revision,
  });
  expect(answer.status, `the personalization consent is ${decision}`).toBe(200);
}

/** Follows a topic in the topics view and returns its identifier. */
async function followTopic(page: Page, name: string): Promise<string> {
  await go(page, 'topics');
  await page.getByTestId('follow-input').fill(name);
  await page.getByTestId('follow-button').click();
  await expect(page.getByTestId('topic-row').filter({ hasText: name })).toContainText('구독 중');
  const topics = await apiCall(page, '/api/v2/topics');
  const followed = (
    topics.body as { topics: { topicId: string; displayName: string }[] }
  ).topics.find((topic) => topic.displayName === name);
  expect(followed).toBeDefined();
  return followed!.topicId;
}

/** A new research session, and a research turn: one memberA already holds, or, when it
 * holds none, one question sent in the new session (the journey's only usage place). */
async function startResearch(page: Page) {
  await go(page, 'research');
  const before = sessionIds(await listSessions(page));
  const held = await heldTurn(page, before);
  await page.getByLabel('새 연구 이름').fill(owner.sessionName);
  await page.getByRole('button', { name: '새 연구 시작', exact: true }).click();
  // The list names a session by its place, not its name: the new one is the id that
  // was not there before.
  await expect
    .poll(async () => sessionIds(await listSessions(page)).filter((id) => !before.includes(id)), {
      timeout: RECORD_WAIT_MS,
    })
    .toHaveLength(1);
  owner.sessionId = sessionIds(await listSessions(page)).find((id) => !before.includes(id)) ?? '';
  if (held !== null) {
    owner.turnSessionId = held.sessionId;
    owner.turnId = held.turnId;
    return;
  }
  await page.getByLabel('연구 질문', { exact: true }).fill('격리 확인용 합성 질문입니다');
  await page.getByRole('button', { name: '질문 보내기', exact: true }).click();
  await expect(page.getByRole('region', { name: '연구 작업 상태' })).toBeVisible();
  owner.turnSessionId = owner.sessionId;
  await expect
    .poll(
      async () => {
        owner.turnId = await firstTurn(page, owner.sessionId);
        return owner.turnId;
      },
      { timeout: RECORD_WAIT_MS },
    )
    .not.toBe('');
}

/** A saved paper through the library's own route; the saved record's id and revision. */
async function savePaper(page: Page, paper: PaperAsset['paper']) {
  const list = await apiCall(page, '/api/v2/c03/library-list-saved-papers', LIMIT);
  const policyRef = (list.body as { policyRef: object }).policyRef;
  await apiCall(page, '/api/v2/c03/library-save-paper', { paper, policyRef });
  // Saved now, or already saved by an earlier run on this realm: the list holds it.
  const saved = (await apiCall(page, '/api/v2/c03/library-list-saved-papers', LIMIT)).body as {
    items: { savedPaperId: string; revision: string; savedPaper: { paperId: string } }[];
  };
  const record = saved.items.find((item) => item.savedPaper.paperId === paper.paperId);
  expect(record, `the saved paper ${paper.paperId} is listed`).toBeDefined();
  return { id: record!.savedPaperId, revision: record!.revision, policyRef };
}

/** Reads `path` (a list by POST, a record by GET) until its answer satisfies `done` or
 * about 20 s pass. It asserts nothing: the passes assert what the record must hold. */
async function settled(page: Page, path: string, done: (text: string) => boolean) {
  const body = path.includes('settings-list-') ? LIMIT : undefined;
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (done(JSON.stringify((await apiCall(page, path, body)).body))) return;
    await page.waitForTimeout(500);
  }
}

/** A personalization reset prepared and accepted against the settings' current revision.
 * The consent just granted can move that revision between the two requests; the reset
 * then answers 409 `CONFLICT` and is prepared again from a fresh read, as the page does. */
async function acceptReset(page: Page, password: string, policyRef: object): Promise<string> {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const settings = (await apiCall(page, '/api/v2/c03/settings-read', {})).body as {
      revision: string;
    };
    const prepared = await apiCall(page, '/api/v2/c03/settings-prepare-reset', {
      action: 'reset_profile',
      currentProof: password,
      policyRef,
      expectedRevision: settings.revision,
    });
    expect(prepared.status, 'the reset is prepared').toBe(200);
    const confirmation = prepared.body as { confirmationRef: string; revision: string };
    const reset = await apiCall(page, '/api/v2/c03/settings-reset', {
      action: 'reset_profile',
      confirmationRef: confirmation.confirmationRef,
      expectedRevision: confirmation.revision,
      policyRef,
    });
    if (reset.status === 200) return firstMatch(reset.body, 'resetId');
    expect([reset.status, reset.code], 'the reset is accepted or in conflict').toEqual([
      409,
      'CONFLICT',
    ]);
    await page.waitForTimeout(500);
  }
  throw new Error('the reset stayed in conflict');
}

/** memberA's library and settings records: a history record from a search in the page,
 * a personalization reset, a saved paper (which also makes the recent-papers record) and
 * a saved search. */
async function makeLibraryRecords(page: Page, password: string) {
  await go(page, 'search');
  await page.getByTestId('search-query').fill(owner.query);
  await page.getByTestId('search-submit').click();
  await expect
    .poll(
      async () => {
        const history = await apiCall(page, '/api/v2/c03/library-list-history', LIMIT);
        owner.historyId = firstMatch(history.body, 'historyId');
        return owner.historyId;
      },
      { timeout: RECORD_WAIT_MS },
    )
    .not.toBe('');
  const settings = (await apiCall(page, '/api/v2/c03/settings-read', {})).body as {
    revision: string;
    searchDefaults: object;
  };
  const policyRef = (await apiCall(page, '/api/v2/c02/access-list-consents', LIMIT)).body as {
    policyRef: object;
  };
  // The reset comes before the save, so the recent-papers record is made after it.
  owner.resetId = await acceptReset(page, password, policyRef.policyRef);
  // The reset's cleanup removes the activity recorded before it ends: the save waits for
  // it, and the recent-papers record is then read back before the passes begin.
  await settled(page, `/api/v2/c03/settings-resets/${owner.resetId}`, (text) =>
    /"disposition":"(?!pending)/.test(text),
  );
  // A paper an earlier run on this realm left saved is saved anew, so that this run's own
  // save makes the recent-papers record.
  await removeSavedPaper(page, fixtures().assistanceJob.paper.paperId);
  const saved = await savePaper(page, fixtures().assistanceJob.paper);
  owner.savedPaperId = saved.id;
  await settled(page, '/api/v2/c03/settings-list-recent-papers', (text) => text.includes(saved.id));
  const search = await apiCall(page, '/api/v2/c03/library-save-search', {
    queryContext: { query: owner.query, ...settings.searchDefaults, policyRef: saved.policyRef },
    label: owner.searchLabel,
  });
  expect(search.status, 'the search is saved').toBe(200);
  owner.savedSearchId = firstMatch(search.body, 'savedSearchId');
}

/** memberA's Notion connection and one export of the fixtures' ready novelty result. */
async function makeExportRecords(page: Page) {
  await ensureNotionConnected(page);
  const connection = await apiCall(page, '/api/v2/c09/read-notion-connection', {});
  owner.connectionId = firstMatch(connection.body, 'connectionId');
  await exportNoveltyTo(page, fixtures().notion.practice);
  await expect
    .poll(
      async () => {
        const history = await apiCall(page, '/api/v2/c09/list-export-history', { limit: 20 });
        owner.effectId = firstMatch(history.body, 'effectId');
        return owner.effectId;
      },
      { timeout: 30_000 },
    )
    .not.toBe('');
}

/** The isolation paper's asset as its reader gets it, through both routes (L3-4). */
function expectOwnerAssets(assets: AssetAnswers) {
  const { eligible } = fixtures().paperAsset;
  expect(assets.eligibleRead.status, 'the eligible asset reads').toBe(200);
  const handle = assets.eligibleRead.body as {
    readHandle: string;
    asset: { assetId: string; contentHash: string };
  };
  expect(handle.readHandle).toBe(eligible.assetId);
  expect(handle.asset.assetId).toBe(eligible.assetId);
  expect(handle.asset.contentHash).toBe(eligible.sha256);
  const serialized = JSON.stringify(assets.eligibleRead.body);
  for (const marker of PRESIGNED_MARKERS) expect(serialized).not.toContain(marker);
  expect(assets.eligibleBytes).toEqual({
    status: 200,
    type: 'image/png',
    cacheControl: 'no-store',
    nosniff: 'nosniff',
    code: null,
    sha256: eligible.sha256,
  });
  expect([assets.ineligibleRead.status, assets.ineligibleRead.code]).toEqual([404, 'NOT_FOUND']);
  expect([assets.ineligibleBytes.status, assets.ineligibleBytes.code]).toEqual([404, 'FORBIDDEN']);
}

test('[J03] memberA owns a topic, a research session and a ready novelty result', async ({
  page,
}) => {
  test.setTimeout(200_000);
  // At load: every probed row has its probe and every probe its row.
  expect(loadProblems()).toEqual([]);
  const account = fixtures().accounts.memberA;
  await login(page, account);
  origin = new URL(page.url()).origin;
  await setPersonalization(page, 'granted');
  owner.topicId = await followTopic(page, owner.topicName);
  await startResearch(page);
  await makeLibraryRecords(page, account.password);
  await makeExportRecords(page);
  // Each of memberA's records reads for memberA, on every row of the table.
  await ownerPass(page, account.accountId);
  const assets = await readOwnerAssets(page, 'owner');
  expectOwnerAssets(assets);
  ownerAsset = assets;
  await logout(page);
});

/** memberB's own records: a saved paper, a topic, a Notion connection, and the fixture
 * Google link it already holds. memberB makes no saved search. */
async function makeOtherRecords(page: Page) {
  await setPersonalization(page, 'granted');
  other.savedPaperId = (await savePaper(page, fixtures().paperAsset.eligible.paper)).id;
  other.topicId = await followTopic(page, other.topicName);
  await ensureNotionConnected(page);
  const connection = await apiCall(page, '/api/v2/c09/read-notion-connection', {});
  other.connectionId = firstMatch(connection.body, 'connectionId');
  const links = await apiCall(page, '/api/v2/c02/access-list-identity-links', LIMIT);
  other.linkId = firstMatch(links.body, 'identityLinkId');
  for (const [name, value] of Object.entries(other))
    expect(value, `memberB's ${name} was made`).not.toBe('');
}

/** Every owner view opened in the page as memberB: none of memberA's names is shown. */
async function expectViewsWithoutOwner(page: Page) {
  for (const route of OWNER_VIEWS) {
    await go(page, route);
    await expect(page.getByTestId(`nav-${route}`)).toHaveAttribute('aria-current', 'page');
    await page.waitForLoadState('networkidle');
    for (const name of [owner.topicName, owner.sessionName, owner.searchLabel, owner.query])
      await expect.soft(page.locator('body'), `${route} as memberB`).not.toContainText(name);
  }
}

/** memberA's recovery link opened by memberB shows no result. */
async function expectNoResultThroughLink(page: Page) {
  const novelty = fixtures().novelty;
  const query = new URLSearchParams({
    jobId: novelty.jobId,
    kind: 'novelty-analysis',
    contextId: novelty.contextId,
  });
  const read = page.waitForResponse(
    (response) => new URL(response.url()).pathname === '/api/v2/c07/read-research-job',
  );
  await page.goto(`/#research-job?${query}`);
  expect((await read).status()).toBe(404);
  await expect(page.getByRole('button', { name: '준비된 결과 열기' })).toHaveCount(0);
  await expect(page.getByTestId('novelty-export-open')).toHaveCount(0);
}

test('[J03] memberB sees none of them in any list and reads none of them', async ({ page }) => {
  test.setTimeout(200_000);
  test.skip(
    !owner.topicId || !owner.sessionId || ownerAsset === null,
    'the previous journey did not record memberA’s records',
  );
  const account = fixtures().accounts.memberB;
  await login(page, account);
  await makeOtherRecords(page);
  await expectViewsWithoutOwner(page);
  await otherPass(page, 'other', account.accountId);
  // Where memberB holds a record, its own list holds that one.
  for (const [probe, marker] of [
    ['savedPapers', other.savedPaperId],
    ['topics', other.topicId],
    ['identityLinks', other.linkId],
    ['notionConnection', other.connectionId],
  ] as const) {
    const row = rowOf(probe);
    for (const request of probeOf(row).real()) {
      const answer = await ask(page, 'other', row, request);
      expect.soft(JSON.stringify(answer.body), `${row.path} holds memberB's own`).toContain(marker);
    }
  }
  await expectNoResultThroughLink(page);
  // The asset is the paper's, not memberA's: memberB's four answers equal memberA's.
  const assets = await readOwnerAssets(page, 'other');
  expect(assets.eligibleRead.status).toBe(ownerAsset!.eligibleRead.status);
  expect(assets.eligibleRead.body).toEqual(ownerAsset!.eligibleRead.body);
  expect(assets.eligibleBytes).toEqual(ownerAsset!.eligibleBytes);
  expect(assets.ineligibleRead).toEqual(ownerAsset!.ineligibleRead);
  expect(assets.ineligibleBytes).toEqual(ownerAsset!.ineligibleBytes);
});

test('[J03] memberA sees none of memberB’s records either', async ({ page }) => {
  test.setTimeout(120_000);
  test.skip(!other.topicId || !other.linkId, 'the previous journey did not record memberB’s');
  const account = fixtures().accounts.memberA;
  await login(page, account);
  for (const { probe, real, madeUp } of reverseReads()) {
    const row = rowOf(probe);
    const wanted = shape(await ask(page, 'reverse', row, madeUp));
    const answer = await ask(page, 'reverse', row, real);
    const label = `${row.method} ${real.path} with memberB's identifier`;
    expect.soft(shape(answer), `${label} answers as a made-up one`).toEqual(wanted);
    expect.soft(answer.status, `${label} is never read`).not.toBe(200);
  }
  // The suggestions read with memberB's link answers its own owner as anyone: asked and
  // reported, never claimed (the seventh probe that cannot fail).
  const byLink = suggestionsByLink();
  const suggestions = rowOf('suggestions');
  const madeUp = shape(await ask(page, 'reverse', suggestions, byLink.madeUp));
  const real = shape(await ask(page, 'reverse', suggestions, byLink.real));
  notClaimed.push(
    `POST ${suggestions.path} with an identityLinkId: memberB's ${real.join(' ')}, a made-up one ${madeUp.join(' ')}`,
  );
  // memberA's own lists hold none of memberB's records.
  const foreign = [other.topicId, other.topicName, other.linkId, other.connectionId];
  for (const probe of ['topics', 'identityLinks', 'notionConnection', 'exportDestinations']) {
    const row = rowOf(probe);
    for (const request of probeOf(row).real()) {
      const text = JSON.stringify((await ask(page, 'reverse', row, request)).body);
      for (const marker of foreign)
        expect.soft(text, `${row.path} holds none of memberB's`).not.toContain(marker);
      expect.soft(foreignAccounts(text, account.accountId), `${row.path}: accounts`).toEqual([]);
    }
  }
  for (const probe of ['savedPapers', 'recentPapers']) {
    const row = rowOf(probe);
    const [request] = probeOf(row).real();
    const text = JSON.stringify((await ask(page, 'reverse', row, request!)).body);
    expect.soft(text, `${row.path} holds none of memberB's`).not.toContain(other.savedPaperId);
  }
});

/** A real asset answers exactly like one that does not exist, on both routes (L3-4). */
async function expectAssetsRefuseAlike(page: Page) {
  const { eligible } = fixtures().paperAsset;
  const madeUp: PaperAsset = {
    paper: {
      paperId: 'u8-asset-none',
      versionId: madeUpId(),
      eligibilityRevision: madeUpId(),
    },
    contentRevision: madeUpHash(),
    assetId: madeUpId(),
    sha256: '',
  };
  for (const asset of [eligible, madeUp]) {
    const read = await apiCall(page, READ_ASSET, assetBody(asset));
    const bytes = await readAssetBytes(page, bytePath(asset));
    log.note('signedOut', rowOf('readAsset'), read.status);
    log.note('signedOut', rowOf('assetBytes'), bytes.status);
    expect([read.status, read.code], 'read-asset refuses alike').toEqual([401, 'UNAUTHENTICATED']);
    expect([bytes.status, bytes.code], 'the byte route refuses alike').toEqual([
      401,
      'UNAUTHENTICATED',
    ]);
  }
}

test('[J13] signed out, every private list, read, event and asset refuses', async ({ page }) => {
  test.setTimeout(120_000);
  const novelty = fixtures().novelty;
  await page.goto('/');
  await expect(page.getByTestId('entry-email')).toBeVisible();
  await signedOutPass(page);
  await expectAssetsRefuseAlike(page);
  // A private link signed out leads to the sign-in, never to the result.
  const query = new URLSearchParams({
    jobId: novelty.jobId,
    kind: 'novelty-analysis',
    contextId: novelty.contextId,
  });
  await page.goto(`/#research-job?${query}`);
  await expect(page.getByTestId('entry-email')).toBeVisible();
  await expect(page.getByRole('button', { name: '준비된 결과 열기' })).toHaveCount(0);
  await expect(page.getByTestId('logout')).toHaveCount(0);
});

/** Removes one member's saved paper by its current revision; a paper already gone is
 * left alone. */
async function removeSavedPaper(page: Page, savedPaperId: string) {
  const saved = (await apiCall(page, '/api/v2/c03/library-list-saved-papers', LIMIT)).body as {
    items: { savedPaperId: string; revision: string }[];
  };
  const record = saved.items.find((item) => item.savedPaperId === savedPaperId);
  if (record === undefined) return;
  const answer = await apiCall(page, '/api/v2/c03/library-remove-saved-paper', {
    savedPaperId,
    expectedRevision: record.revision,
  });
  expect.soft(answer.status, `the saved paper ${savedPaperId} is removed`).toBe(200);
}

/** L4-13's cleanup: both saved papers, memberA's saved search, memberB's topic and Notion
 * connection, and both personalization consents back to off. What stays is memberA's:
 * the followed topic and the named research session a run makes, the history record, the
 * reset, the recent-papers record, the research turn, the Notion connection, the export
 * effect and the usage records. */
async function cleanUp(page: Page) {
  const { memberA, memberB } = fixtures().accounts;
  await login(page, memberA);
  await removeSavedPaper(page, owner.savedPaperId);
  const searches = (await apiCall(page, '/api/v2/c03/library-list-saved-searches', LIMIT)).body as {
    items: { savedSearchId: string; revision: string }[];
  };
  for (const item of searches.items.filter((item) => item.savedSearchId === owner.savedSearchId)) {
    const answer = await apiCall(page, '/api/v2/c03/library-remove-saved-search', {
      savedSearchId: item.savedSearchId,
      expectedRevision: item.revision,
    });
    expect.soft(answer.status, 'the saved search is removed').toBe(200);
  }
  await setPersonalization(page, 'revoked');
  await logout(page);
  await login(page, memberB);
  await removeSavedPaper(page, other.savedPaperId);
  if (other.topicId) {
    const row = rowOfRoute('DELETE', '/api/v2/topics/{topic_id}');
    const path = `/api/v2/topics/${other.topicId}`;
    const answer = await log.ask(page, 'cleanup', row, { path, method: 'DELETE' });
    expect.soft(answer.status, 'memberB’s topic is removed').toBe(200);
  }
  if (other.connectionId) {
    const gone = await apiCall(page, '/api/v2/c09/disconnect-notion', {});
    expect.soft(gone.status, 'memberB’s Notion connection is removed').toBe(200);
  }
  await setPersonalization(page, 'revoked');
  await logout(page);
}

function rowOfRoute(method: string, path: string): IsolationRow {
  const row = TABLE.routes.find(
    (candidate) => candidate.method === method && candidate.path === path,
  );
  if (row === undefined) throw new Error(`no row for ${method} ${path}`);
  return row;
}

test('[J03] every owner row was asked as its owner, as the other member and signed out', async ({
  page,
}, info) => {
  test.setTimeout(120_000);
  try {
    const wanted = PROBED.map((row) => row.probe ?? '').sort();
    for (const pass of ['owner', 'other', 'signedOut']) {
      const asked = log.asked(pass);
      const missing = wanted.filter((probe) => !asked.has(probe));
      expect.soft(missing, `every probed row was asked in the ${pass} pass`).toEqual([]);
    }
    // The rows whose probe cannot fail in this realm: listed, and recorded as not claimed.
    const marked = PROBED.filter((row) => row.notClaimed !== undefined);
    expect.soft(marked).toHaveLength(8);
    await info.attach('isolation-not-claimed', {
      body: JSON.stringify({ rows: marked.map((row) => row.path), owner: notClaimed }, null, 2),
      contentType: 'application/json',
    });
    // The same in the run root, which outlives a passing test's own output: the rows not
    // claimed with what their owner got, and how many requests each pass sent.
    const passes = ['owner', 'other', 'reverse', 'signedOut', 'cleanup'];
    writeMeasurements('isolation-report.json', {
      notClaimedRows: marked.map((row) => `${row.method} ${row.path}`),
      ownerAnswers: notClaimed,
      requests: Object.fromEntries(
        passes.map((pass) => [pass, log.entries.filter((entry) => entry.pass === pass).length]),
      ),
    });
  } finally {
    await page.goto('/');
  }
});

// L4-13's cleanup, after the tests whatever happened to them: an earlier failure skips
// the serial tests that follow it, and must not leave memberB's records behind.
test.afterAll(async ({ browser }) => {
  if (origin === '') return;
  const context = await browser.newContext({ baseURL: origin });
  try {
    await cleanUp(await context.newPage());
  } finally {
    await context.close();
  }
});

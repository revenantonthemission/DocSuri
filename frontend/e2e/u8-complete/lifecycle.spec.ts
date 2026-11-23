// J04, J05 and J08 (BR2.2–BR2.6, NFR2.1): current authority and late effects in the
// complete application: J04 and J05 on memberE; J08 on memberD, whose account the last
// journey consumes.
// - J04: a session revoked in another window, during a job and during its event stream;
// - J05: consent revoked while a digest, an export and a job are in flight, none taking
//   effect after the revocation, with memberD's control topic delivered in the same pass;
// - J08: withdrawal racing an in-flight digest, export and job, none taking effect;
//   reactivation through the new entry and the mailbox link (your decision of
//   2026-10-23), reaching complete across every participant; then erasure, which
//   appends memberD's tombstone. Its restore-enforcement part completes with a restore
//   verification after it; the verification run's recovery journey comes first, so it
//   proves that part on memberC (recovery.spec.ts).
// The realm's workers (and scheduler) are stopped while work is in flight, so the race is
// decided by the order of events, not by timing.
import { test, expect, type Browser, type Page } from '@playwright/test';
import {
  apiCall,
  assertNoViolations,
  captureFailures,
  clockTimeAhead,
  ensureNotionConnected,
  exportShownNoveltyTo,
  fixtures,
  go,
  harness,
  login,
  logout,
  openMailLink,
  scrub,
  signInForm,
  signedInNavigation,
  watchPolicy,
  type Account,
} from './helpers';

// In file order on the one worker; a failure does not skip the journeys after it, so
// each one's own result is recorded.
test.describe.configure({ mode: 'default' });

const diagnostics = new WeakMap<Page, ReturnType<typeof captureFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureFailures(page));
});
test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

const REACTIVATION_REQUESTED = '탈퇴한 계정이 있으면 재활성화 링크를 이메일로 보냅니다';
const REACTIVATION_ACCEPTED = '재활성화를 접수했습니다';
const SETTLE_MS = 60_000;

// Each owner's usage allows three accepted jobs a period (`U8_SYNTHETIC_POLICY`): J04
// runs on memberE, whose password it changes and then gives back, and J05 runs on memberE
// too, opening memberE's own fixture-made ready result, so memberD has J08's two jobs.
// memberC is not used here: the verification run puts the recovery journey, which erases
// memberC, before this one.
function changedPassword(account: { password: string }): string {
  return `${account.password}-changed`;
}
function memberD() {
  return fixtures().accounts.memberD;
}

function stopBackground() {
  harness('service', { name: 'scheduler', action: 'stop' });
  harness('service', { name: 'workers', action: 'stop' });
}
function startBackground() {
  harness('service', { name: 'workers', action: 'start' });
  harness('service', { name: 'scheduler', action: 'start' });
}

type JobReference = { jobId: string; contextId: string };

/** Starts a novelty analysis in the novelty view and returns its job id. */
async function startNovelty(page: Page, topic: string): Promise<string> {
  return (await startNoveltyReference(page, topic)).jobId;
}

/** Starts a novelty analysis and returns its job and research context. */
async function startNoveltyReference(page: Page, topic: string): Promise<JobReference> {
  await go(page, 'novelty');
  await page.getByRole('button', { name: '새 분석 준비' }).click();
  await page.getByLabel('분석할 주제 또는 원고 설명').fill(topic);
  const accepted = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/api/v2/c07/accept-novelty-analysis' &&
      response.request().method() === 'POST',
    // An accept the page never sends (a spent usage allowance) fails here, not at the
    // phase's bound.
    { timeout: 20_000 },
  );
  await page.getByRole('button', { name: '참신성 분석 시작' }).click();
  const answer = await accepted;
  expect(answer.status()).toBe(200);
  const sent = answer.request().postDataJSON() as { scope: { contextId: string } };
  return {
    jobId: ((await answer.json()) as { jobId: string }).jobId,
    contextId: sent.scope.contextId,
  };
}

/** The owner's ready novelty result, opened through U4's own recovery link. */
async function openOwnNovelty(page: Page, reference: JobReference) {
  // By name, as `openNoveltyResult` does: U4's `readJobLink` refuses a query without
  // exactly these three keys.
  const query = new URLSearchParams({
    jobId: reference.jobId,
    kind: 'novelty-analysis',
    contextId: reference.contextId,
  });
  // The novelty view already kept this exact link in the address when it accepted the
  // job (`keepJobLink`), so going to it again changes no fragment, fires no `hashchange`
  // and leaves the current view in place. From the plain address first, as a link opened
  // later would be, the link is followed (as `openNoveltyResult` does).
  await page.goto('/');
  await expect(page.getByTestId('logout')).toBeVisible();
  await page.goto(`/#research-job?${query}`);
  await expect(page.getByTestId('logout')).toBeVisible();
  await page.getByRole('button', { name: '준비된 결과 열기' }).click();
  await expect(page.getByTestId('novelty-export-open')).toBeVisible();
}

/** The job's state as its owner reads it, once the realm has settled it. */
async function untilJobState(page: Page, jobId: string, wanted: RegExp) {
  await expect
    .poll(
      async () => {
        const answer = await apiCall(page, `/api/v2/jobs/${jobId}`);
        return answer.status === 200 ? (answer.body as { state: string }).state : '';
      },
      { timeout: SETTLE_MS, intervals: [1_000, 2_000] },
    )
    .toMatch(wanted);
}

async function openAccount(page: Page, section: string) {
  await go(page, 'account');
  await page.getByText(section, { exact: true }).click();
}

async function lifecycleRequests(accountId: string) {
  return harness<{
    requests: {
      action: string;
      disposition: string;
      scopes: { participant: string; scope: string; disposition: string }[];
    }[];
  }>('lifecycle', { accountId }).requests;
}

type DigestRun = {
  state: string;
  createdAt: string;
  items: number | null;
  outcomes: { observedState: string | null; reconciledState: string | null }[];
  sendLog: { pathKind: string } | null;
};
type DigestTopic = { topicId: string; status: string; runs: DigestRun[] };
type ExportRecord = {
  approvals: { approvalId: string; state: string; invalidationReason: string | null }[];
  effects: { approvalId: string; state: string; outcomeReason: string | null }[];
};

/** One followed topic, found by the `topicId` its follow answered (Step 96(b)). */
function digestTopic(accountId: string, topicId: string): DigestTopic | undefined {
  return harness<{ topics: DigestTopic[] }>('digests', { accountId }).topics.find(
    (topic) => topic.topicId === topicId,
  );
}

/** The newest run's state of a followed topic, or why there is none. */
function newestRunState(accountId: string, topicId: string): string {
  const topic = digestTopic(accountId, topicId);
  if (!topic) return 'no-topic';
  return topic.runs[topic.runs.length - 1]?.state ?? 'no-run';
}

/** The account's newest approval and its case, as `case:state:reason`: `effect` when the
 * approval has a bound effect (U6's history row then shows the effect's state), `approval`
 * when it has none; or `succeeded` when any effect succeeded. */
function newestExport(accountId: string): string {
  const record = harness<ExportRecord>('exports', { accountId });
  if (record.effects.some((effect) => effect.state === 'succeeded')) return 'succeeded';
  const approval = record.approvals[record.approvals.length - 1];
  if (!approval) return 'no-approval';
  const effect = record.effects.find((item) => item.approvalId === approval.approvalId);
  if (effect) return `effect:${effect.state}:${effect.outcomeReason ?? ''}`;
  return `approval:${approval.state}:${approval.invalidationReason ?? ''}`;
}

/** Step 99(e)'s one history copy for each case, as U6 renders it: a bound effect that is
 * invalidated, or an approval invalidated with no effect. */
const HISTORY_COPY = {
  effect: '변경되어 내보내지 않았습니다',
  approval: '변경되어 승인이 무효가 되었습니다',
} as const;

/** The history copy the newest export's case calls for, and the other one. */
function historyCopies(accountId: string): { shown: string; absent: string } {
  const value = newestExport(accountId);
  const kind = value.startsWith('effect:') ? 'effect' : 'approval';
  return {
    shown: HISTORY_COPY[kind],
    absent: HISTORY_COPY[kind === 'effect' ? 'approval' : 'effect'],
  };
}

/** Follows a topic in the topics view, daily at `due` with a 30-day window, and returns
 * the `topicId` its follow answered (`FollowResult`). */
async function followTopic(page: Page, name: string, due: string): Promise<string> {
  await go(page, 'topics');
  await page.getByTestId('follow-input').fill(name);
  const followed = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/api/v2/topics' &&
      response.request().method() === 'POST',
    { timeout: 20_000 },
  );
  await page.getByTestId('follow-button').click();
  const answer = await followed;
  expect(answer.status()).toBe(200);
  const topicId = ((await answer.json()) as { topicId: string }).topicId;
  const row = page.getByTestId('topic-row').filter({ hasText: name });
  await expect(row).toContainText('구독 중');
  await row.getByTestId('settings-link').click();
  await page.getByTestId('cadence-select').selectOption('daily');
  await page.getByTestId('delivery-time').fill(due);
  await page.getByTestId('window-select').selectOption('30');
  await page.getByTestId('save-button').click();
  await expect(page.getByText(/발송 설정을 저장했어요/)).toBeVisible();
  return topicId;
}

/** Signs out, lets `other` follow a control topic at `due` in this same browser context,
 * and signs the owner back in. No second context and no `APIRequestContext` opens: the
 * context's TLS pin is a Chromium launch flag (Step 99(e)). */
async function followControlTopic(
  page: Page,
  owner: Account,
  other: Account,
  name: string,
  due: string,
): Promise<string> {
  await logout(page);
  await login(page, other);
  const topicId = await followTopic(page, name, due);
  await logout(page);
  await login(page, owner);
  return topicId;
}

const WITHHELD_RUN_STATES = ['prepared', 'sending', 'sent', 'unknown'];

test('[J04] a session revoked in another window ends its stream and its job', async ({
  page,
  browser,
}) => {
  test.setTimeout(150_000);
  const original = fixtures().accounts.memberE;
  const changed = { ...original, password: changedPassword(original) };
  await login(page, original);
  const origin = new URL(page.url()).origin;
  // Set just before the change's submit: a change the realm applied counts even when its
  // window then misses the sign-in form (Step 99(d)).
  let changeSubmitted = false;
  try {
    stopBackground();
    let jobId = '';
    try {
      jobId = await startNovelty(page, '세션 철회 중인 합성 작업');
      // The job's event stream, open in this window while the job waits.
      await page.evaluate((id) => {
        const stream = new EventSource(`/api/v2/jobs/${id}/events`);
        (window as unknown as { u8Stream: EventSource }).u8Stream = stream;
      }, jobId);
      await expect
        .poll(() =>
          page.evaluate(() => (window as unknown as { u8Stream: EventSource }).u8Stream.readyState),
        )
        .toBe(1);
      // Another window: the same owner changes the password, which ends every session.
      await changePasswordElsewhere(browser, origin, original, changed, () => {
        changeSubmitted = true;
      });
      // The open stream ends, and its reconnection is refused: it closes for good.
      await expect
        .poll(
          () =>
            page.evaluate(
              () => (window as unknown as { u8Stream: EventSource }).u8Stream.readyState,
            ),
          { timeout: 30_000, intervals: [1_000] },
        )
        .toBe(2);
      const session = (await apiCall(page, '/api/v2/session')).body as { signedIn: boolean };
      expect(session.signedIn).toBe(false);
      expect([401, 403]).toContain((await apiCall(page, `/api/v2/jobs/${jobId}`)).status);
    } finally {
      startBackground();
    }
    // The job ran under the revoked session's authority: it fails, with no result.
    await page.goto('/');
    await login(page, changed);
    await untilJobState(page, jobId, /^failed$/);
    await go(page, 'jobs');
    await page.getByTestId('jobs-filter-novelty').click();
    const item = page.getByTestId('jobs-item').first();
    await expect(item.getByTestId('jobs-item-state')).toHaveText('실패');
  } finally {
    // memberE's own password back, for J05 and any later run on this realm.
    if (changeSubmitted) await restorePassword(browser, origin, changed, original);
  }
});

/** In a signed-in window, changes the password, which ends every session. `beforeSubmit`
 * runs just before the change is submitted. */
async function changePasswordIn(
  window2: Page,
  from: string,
  to: string,
  beforeSubmit: () => void = () => undefined,
) {
  await openAccount(window2, '비밀번호와 이메일');
  await window2.getByLabel('현재 비밀번호', { exact: true }).fill(from);
  await window2.getByLabel('새 비밀번호', { exact: true }).fill(to);
  beforeSubmit();
  await window2.getByRole('button', { name: '비밀번호 변경 후 다시 로그인' }).click();
  await expect(window2.getByTestId('entry-email')).toBeVisible({ timeout: 20_000 });
}

/** Another window: the owner changes the password, which ends every session. Its context
 * is watched for policy violations (Step 99(g)), and none may be left untaken. */
async function changePasswordElsewhere(
  browser: Browser,
  origin: string,
  from: Account,
  to: { password: string },
  beforeSubmit?: () => void,
) {
  const other = await browser.newContext({ baseURL: origin });
  watchPolicy(other);
  try {
    const window2 = await other.newPage();
    await login(window2, from);
    await changePasswordIn(window2, from.password, to.password, beforeSubmit);
    assertNoViolations(window2);
  } finally {
    await other.close();
  }
}

/** The end-of-test restore (Step 99(d)): in a fresh context, opened as
 * `changePasswordElsewhere` opens one, a sign-in with the changed password; only when it is
 * accepted is the password changed back, so a change that never took effect is left
 * alone. */
async function restorePassword(
  browser: Browser,
  origin: string,
  changed: Account,
  original: Account,
) {
  const other = await browser.newContext({ baseURL: origin });
  watchPolicy(other);
  try {
    const window2 = await other.newPage();
    await signInForm(window2);
    await window2.getByTestId('entry-email').fill(changed.email);
    await window2.getByTestId('entry-password').fill(changed.password);
    const answered = window2.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/api/v2/c02/access-login' &&
        response.request().method() === 'POST',
      { timeout: 20_000 },
    );
    await window2.getByTestId('entry-submit').click();
    const answer = await answered;
    if (answer.status() !== 200) {
      // Only the realm's wrong-credentials answer (403 with its fixed code) means the change
      // never took effect; any other refusal (a limit, a busy realm, a capability) fails J04.
      const code = ((await answer.json().catch(() => null)) as { code?: unknown } | null)?.code;
      expect({ status: answer.status(), code }, 'the restore sign-in').toEqual({
        status: 403,
        code: 'FORBIDDEN',
      });
      return;
    }
    await expect(window2.getByTestId('logout')).toBeVisible();
    await signedInNavigation(window2);
    await changePasswordIn(window2, changed.password, original.password);
    assertNoViolations(window2);
  } finally {
    await other.close();
  }
}

test('[J05] consent revoked while a digest, an export and a job are in flight: none takes effect', async ({
  page,
}) => {
  test.setTimeout(150_000);
  const value = fixtures();
  const owner = value.accounts.memberE;
  const control = memberD();
  const stamp = Date.now();
  await login(page, owner);
  const consent = page.locator('.control-row').filter({ hasText: 'local-research' });
  let jobId = '';
  let revoked = false;
  try {
    let topicId = '';
    let controlId = '';
    stopBackground();
    try {
      const due = clockTimeAhead(3, 'Asia/Seoul');
      // Both topics before the export, so no sign-out ends the export's approving session.
      topicId = await followTopic(page, `동의-철회-${stamp}`, due);
      controlId = await followControlTopic(page, owner, control, `동의-대조-${stamp}`, due);
      // memberE's fixture-made ready result, exported on an explicit approval while
      // `local-research` is still granted.
      await ensureNotionConnected(page);
      await openOwnNovelty(page, {
        jobId: value.noveltyMemberE.jobId,
        contextId: value.noveltyMemberE.contextId,
      });
      await exportShownNoveltyTo(page, value.notion.practice);
      jobId = await startNovelty(page, '동의 철회 중인 합성 작업');
      await openAccount(page, '개인정보와 처리 동의');
      await expect(consent).toContainText('동의함');
      await consent.getByRole('button', { name: '동의 철회' }).click();
      revoked = true;
      await expect(consent).toContainText('철회함');
      harness('advance-clock', { seconds: 600 });
    } finally {
      startBackground();
    }
    // Before any re-grant: the control topic's digest goes out in the same passes, and
    // nothing of memberE's takes effect.
    await expect
      .poll(() => newestRunState(control.accountId, controlId), {
        timeout: SETTLE_MS,
        intervals: [2_000, 3_000],
      })
      .toBe('sent');
    expect(digestTopic(owner.accountId, topicId)?.runs).toEqual([]);
    await expect
      .poll(() => harness<{ state: string }>('job', { jobId }).state, {
        timeout: SETTLE_MS,
        intervals: [1_000, 2_000],
      })
      .toBe('failed');
    expect(harness<{ artifacts: number }>('job', { jobId }).artifacts).toBe(0);
    await expect
      .poll(() => newestExport(owner.accountId), {
        timeout: SETTLE_MS,
        intervals: [1_000, 2_000],
      })
      .toMatch(/^(effect|approval):invalidated:authority-revoked$/);
  } finally {
    if (revoked) {
      await consent.getByRole('button', { name: '처리 동의' }).click();
      await expect(consent).toContainText('동의함');
    }
  }
  // Given back: the export's history row names the cause, offers a fresh preview and
  // nothing else; the job reads failed with no result.
  await go(page, 'export');
  const history = page.getByTestId('history-row').filter({ hasText: value.notion.practice });
  await expect(history.first()).toBeVisible({ timeout: 20_000 });
  const row = history.first();
  await expect(row).toContainText('승인한 로그인 세션이 끝났거나 처리 동의가 철회되었습니다');
  // The copy Step 99(e) assigns to the case the export poll resolved.
  const copies = historyCopies(owner.accountId);
  await expect(row).toContainText(copies.shown);
  await expect(row).not.toContainText(copies.absent);
  await expect(row).not.toContainText('내보냈습니다');
  await expect(row.getByTestId('history-fresh-preview')).toBeVisible();
  for (const testId of ['history-continue', 'history-cancel', 'history-settle'])
    await expect(row.getByTestId(testId)).toHaveCount(0);
  await untilJobState(page, jobId, /^failed$/);
  const job = await apiCall(page, `/api/v2/jobs/${jobId}`);
  expect(JSON.stringify(job.body)).not.toContain('"resultId"');
});

test('[J08] withdrawal racing a digest, an export and a job; reactivation by mail; erasure', async ({
  page,
}) => {
  // Within the phase's bound beside the other journeys and recovery, so a slow step
  // fails here with its own error context.
  test.setTimeout(150_000);
  const account = memberD();
  const control = fixtures().accounts.memberE;
  await login(page, account);
  // A ready result of memberD's own, to export while the workers are stopped.
  const result = await startNoveltyReference(page, '탈퇴 경합용 합성 결과');
  await untilJobState(page, result.jobId, /^succeeded$/);
  const stamp = Date.now();
  const topic = `탈퇴-경합-${stamp}`;
  let topicId = '';
  let controlId = '';
  stopBackground();
  let jobId = '';
  try {
    // In flight: a digest due, an export approved, and a job accepted. Both topics are
    // followed before the export, so no sign-out ends the export's approving session.
    const due = clockTimeAhead(3, 'Asia/Seoul');
    topicId = await followTopic(page, topic, due);
    controlId = await followControlTopic(page, account, control, `탈퇴-대조-${stamp}`, due);
    await ensureNotionConnected(page);
    await openOwnNovelty(page, result);
    await exportShownNoveltyTo(page, fixtures().notion.practice);
    jobId = await startNovelty(page, '탈퇴 경합 중인 합성 작업');
    // Withdrawal: access ends at once.
    await withdraw(page, account.password);
    // The digest's moment passes while the account is withdrawn.
    harness('advance-clock', { seconds: 600 });
  } finally {
    startBackground();
  }
  // Every participant acknowledges the withdrawal.
  await expect
    .poll(async () => (await lifecycleRequests(account.accountId))[0]?.disposition ?? 'missing', {
      timeout: SETTLE_MS,
      intervals: [2_000, 3_000],
    })
    .toBe('complete');
  const withdrawn = (await lifecycleRequests(account.accountId))[0]!;
  expect(withdrawn.action).toBe('withdraw');
  expect(withdrawn.scopes.length).toBeGreaterThan(0);
  expect(withdrawn.scopes.every((scope) => scope.disposition === 'complete')).toBe(true);
  // The control topic's digest goes out; only after that is memberD's topic read, ended
  // with no run that could carry a digest and no delivery outcome; the export is
  // invalidated and nothing succeeded.
  await expect
    .poll(() => newestRunState(control.accountId, controlId), {
      timeout: SETTLE_MS,
      intervals: [2_000, 3_000],
    })
    .toBe('sent');
  const withdrawnTopic = digestTopic(account.accountId, topicId);
  expect(withdrawnTopic?.status).toBe('unsubscribed');
  expect(withdrawnTopic?.runs.filter((run) => WITHHELD_RUN_STATES.includes(run.state))).toEqual([]);
  expect(withdrawnTopic?.runs.flatMap((run) => run.outcomes)).toEqual([]);
  await expect
    .poll(() => newestExport(account.accountId), {
      timeout: SETTLE_MS,
      intervals: [1_000, 2_000],
    })
    .toMatch(/^(effect|approval):invalidated:(account-withdrawn|authority-revoked)$/);

  // Reactivation through the entry and the mailbox link, in this same browser.
  await signInForm(page);
  await page.getByTestId('entry-email').fill(account.email);
  await page.getByTestId('entry-reactivate').click();
  await expect(page.getByTestId('complete-entry')).toContainText(REACTIVATION_REQUESTED);
  await openMailLink(page, account.email, 'reactivate');
  // The entry takes the proof from the address when it renders, after the session check
  // (as security.spec.ts waits for the password-reset proof form).
  await expect(page.getByTestId('proof-form')).toBeVisible();
  expect(new URL(page.url()).hash).toBe('');
  await page.getByTestId('proof-submit').click();
  await expect(page.getByTestId('complete-entry')).toContainText(REACTIVATION_ACCEPTED);
  await expect
    .poll(
      async () => {
        const newest = (await lifecycleRequests(account.accountId))[0];
        return newest ? `${newest.action}:${newest.disposition}` : 'missing';
      },
      { timeout: SETTLE_MS, intervals: [2_000, 3_000] },
    )
    .toBe('reactivate:complete');
  const reactivated = (await lifecycleRequests(account.accountId))[0]!;
  expect(reactivated.scopes.length).toBeGreaterThan(0);
  expect(reactivated.scopes.every((scope) => scope.disposition === 'complete')).toBe(true);

  // Back in, nothing that was in flight took effect after the withdrawal.
  await login(page, account);
  await untilJobState(page, jobId, /^(failed|cancelled)$/);
  await go(page, 'export');
  const history = page.getByTestId('history-row').filter({ hasText: fixtures().notion.practice });
  await expect(history.first()).toBeVisible({ timeout: 20_000 });
  const row = history.first();
  const copies = historyCopies(account.accountId);
  await expect(row).toContainText(copies.shown);
  await expect(row).not.toContainText(copies.absent);
  await expect(row).toContainText(
    /계정 사용이 중지되었습니다|승인한 로그인 세션이 끝났거나 처리 동의가 철회되었습니다/,
  );
  await expect(row.getByTestId('history-fresh-preview')).toBeVisible();
  const absent = [
    '내보냈습니다',
    '승인됨 · 아직 시작 전',
    '내보내는 중',
    '확인 중',
    '내보내기 시작됨',
  ];
  for (const text of absent) await expect(row).not.toContainText(text);
  await go(page, 'topics');
  await expect(page.getByTestId('topics-empty').or(page.getByTestId('topic-list'))).toBeVisible();
  await expect(page.getByTestId('topic-row').filter({ hasText: topic })).toHaveCount(0);

  // Erasure: accepted at once, and every participant but restore enforcement completes;
  // that one waits for a restore verification after it (recovery.spec.ts proves it).
  await go(page, 'account');
  await page.getByText('탈퇴와 데이터 삭제', { exact: true }).click();
  await page.getByLabel('처리 범위').selectOption('erase');
  await page.getByLabel('계정 처리용 현재 비밀번호').fill(account.password);
  await page.getByRole('button', { name: '처리 범위 확인 준비' }).click();
  await page.getByRole('button', { name: '확인하고 접수' }).click();
  // The session ends at once, as the withdrawal's did and as J09's erasure checks; the
  // erasure's progress is read through the harness, since an erased account keeps no
  // session to read its own status with.
  await expect(page.getByTestId('logout')).toHaveCount(0);
  await expect
    .poll(
      () => harness<{ accounts: string[] }>('tombstones').accounts.includes(account.accountId),
      { timeout: SETTLE_MS, intervals: [2_000, 3_000] },
    )
    .toBe(true);
  // Every participant's scope completes but restore enforcement, which completes with a
  // restore verification after the erasure (the verification run's comes first).
  await expect
    .poll(
      async () => {
        const newest = (await lifecycleRequests(account.accountId))[0];
        if (!newest || newest.action !== 'erase') return 'no-erasure';
        const pending = newest.scopes
          .filter((scope) => scope.scope !== 'restore_enforcement')
          .filter((scope) => scope.disposition !== 'complete')
          .map((scope) => `${scope.participant}:${scope.scope}`);
        return pending.length ? pending.join(',') : 'complete';
      },
      { timeout: SETTLE_MS, intervals: [2_000, 3_000] },
    )
    .toBe('complete');
});

async function withdraw(page: Page, password: string) {
  await go(page, 'account');
  await page.getByText('탈퇴와 데이터 삭제', { exact: true }).click();
  await page.getByLabel('처리 범위').selectOption('withdraw');
  await page.getByLabel('계정 처리용 현재 비밀번호').fill(password);
  await page.getByRole('button', { name: '처리 범위 확인 준비' }).click();
  await page.getByRole('button', { name: '확인하고 접수' }).click();
  await expect(page.getByTestId('logout')).toHaveCount(0);
}

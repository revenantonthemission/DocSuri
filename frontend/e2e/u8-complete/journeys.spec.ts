// BR10.3's cross-unit journeys in the complete application, through the public stand-in,
// the real host, workers, scheduler and database: J01 sign-in → library → search → paper
// → research → novelty → export; J02 topics → digest; J06 durable drafts; J07 the job
// lifecycle with the owner's job list.
import { test, expect, type Page } from '@playwright/test';
import {
  captureFailures,
  clockTimeAhead,
  ensureNotionConnected,
  exportNoveltyTo,
  fixtures,
  go,
  harness,
  login,
  logout,
  scrub,
} from './helpers';

// In file order on the one worker; a failure does not skip the journeys after it.
test.describe.configure({ mode: 'default' });

const diagnostics = new WeakMap<Page, ReturnType<typeof captureFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureFailures(page));
});
test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

/** The library view at either library step of J01: the owner's controls with the papers
 * view pressed, no signed-out panel, and, once the first read ends, the empty text or a
 * saved paper (U8 plan Step 99(a)). */
async function expectLibrary(page: Page) {
  const controls = page.getByTestId('library-controls');
  await expect(controls).toBeVisible();
  for (const view of ['papers', 'queries', 'history', 'recent'])
    await expect(controls.getByTestId(`library-view-${view}`)).toBeVisible();
  await expect(controls.getByTestId('library-view-papers')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('library-panel')).toHaveCount(0);
  const empty = controls.getByTestId('library-empty');
  const saved = controls.getByRole('list', { name: '저장한 논문' }).getByRole('listitem');
  await expect
    .poll(
      async () => {
        if ((await saved.count()) > 0) return 'a saved paper';
        if (await empty.isVisible()) return (await empty.textContent()) ?? '';
        return 'still reading';
      },
      { timeout: 20_000, intervals: [500, 1_000] },
    )
    .toMatch(/^(a saved paper|표시할 저장한 논문이 없습니다\.)$/);
  await expect(page.getByTestId('nav-library')).toHaveAttribute('aria-current', 'page');
}

/** Starts a novelty analysis in the novelty view and returns its job id, from the accept's
 * own answer. A first analysis prepares a research context; a later one is started in the
 * context the workspace still holds. */
async function startNoveltyJob(
  page: Page,
  topic: string,
  { inPreparedContext = false }: { inPreparedContext?: boolean } = {},
): Promise<string> {
  await go(page, 'novelty');
  const prepare = page.getByRole('button', { name: '새 분석 준비' });
  if (inPreparedContext) await expect(prepare).toBeDisabled();
  else await prepare.click();
  await page.getByLabel('분석할 주제 또는 원고 설명').fill(topic);
  const accepted = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/api/v2/c07/accept-novelty-analysis' &&
      response.request().method() === 'POST',
    { timeout: 20_000 },
  );
  await page.getByRole('button', { name: '참신성 분석 시작' }).click();
  const answer = await accepted;
  expect(answer.status()).toBe(200);
  return ((await answer.json()) as { jobId: string }).jobId;
}

type Frame = { seq: number; state: string };
const JOB_ORDER = ['accepted', 'running', 'succeeded'];

/** Refreshes a job's status until the wanted control or text appears. */
async function untilVisible(page: Page, target: ReturnType<Page['getByRole']>, seconds = 40) {
  await expect
    .poll(
      async () => {
        if (await target.isVisible()) return true;
        const refresh = page.getByRole('button', { name: '진행 상태 새로고침' });
        if (await refresh.isVisible()) await refresh.click();
        return target.isVisible();
      },
      { timeout: seconds * 1000, intervals: [1_000, 2_000] },
    )
    .toBe(true);
}

test('[J01] sign-in to library, search, paper, research, novelty and export', async ({ page }) => {
  test.setTimeout(150_000);
  const value = fixtures();
  await login(page, value.accounts.memberA);
  // Library: the signed-in owner's own library view.
  await go(page, 'library');
  await expectLibrary(page);
  // Search the production-size corpus and open a paper.
  await go(page, 'search');
  await page.getByTestId('search-query').fill('attention transformer');
  await page.getByTestId('search-submit').click();
  // The complete workspace's search is U3's (`u3-corpus/search-reading.tsx`).
  const first = page.getByTestId('result-row').first();
  await expect(first).toBeVisible({ timeout: 20_000 });
  await first.getByTestId('result-open').click();
  await expect(page.getByTestId('paper-workspace')).toBeVisible();
  await expect(page.getByTestId('paper-identity')).toContainText('Synthetic production-size paper');
  await expect(page.getByTestId('reading-surface')).toBeVisible({ timeout: 20_000 });
  // Back in the library, the owner's own view under the control service.
  await go(page, 'library');
  await expectLibrary(page);
  // Research: one explicit question, its source-bound result.
  await go(page, 'research');
  await page.getByLabel('새 연구 이름').fill(`여정 ${Date.now()}`);
  await page.getByRole('button', { name: '새 연구 시작', exact: true }).click();
  await page
    .getByLabel('연구 질문', { exact: true })
    .fill('합성 말뭉치의 근거와 한계를 설명해 주세요');
  await page.getByRole('button', { name: '질문 보내기', exact: true }).click();
  await expect(page.getByRole('region', { name: '연구 작업 상태' })).toBeVisible();
  const result = page.getByRole('button', { name: '준비된 결과 열기' });
  await untilVisible(page, result);
  await result.click();
  await expect(page.getByRole('region', { name: '준비된 연구 결과' })).toBeVisible();
  // Novelty: the fixture's ready result, exported to Notion on an explicit approval.
  await ensureNotionConnected(page);
  await exportNoveltyTo(page, value.notion.practice);
  await expect(page.getByTestId('outcome-status')).toContainText('내보냈습니다', {
    timeout: 40_000,
  });
  await expect(page.getByTestId('outcome-page-link')).toContainText('Notion에서 열기');
});

test('[J02] a followed topic reaches a delivered digest through the scheduler', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const name = `주제-${Date.now()}`;
  await login(page, fixtures().accounts.memberA);
  await go(page, 'topics');
  await page.getByTestId('follow-input').fill(name);
  await page.getByTestId('follow-button').click();
  const row = page.getByTestId('topic-row').filter({ hasText: name });
  await expect(row).toContainText('구독 중');
  await row.getByTestId('settings-link').click();
  await page.getByTestId('preferences-toggle').click();
  await page.getByTestId('digest-language').selectOption('ko');
  await page.getByTestId('digest-timezone').fill('Asia/Seoul');
  await page.getByTestId('preferences-save').click();
  await expect(page.getByText('계정 환경설정을 저장했어요')).toBeVisible();
  // The delivery moment a few minutes ahead of the realm's one delegated clock, so the
  // run spends minutes, not a day, of the clock's 48-hour allocation.
  await page.getByTestId('cadence-select').selectOption('daily');
  await page.getByTestId('delivery-time').fill(clockTimeAhead(3, 'Asia/Seoul'));
  await page.getByTestId('window-select').selectOption('30');
  await page.getByTestId('save-button').click();
  await expect(page.getByText(/발송 설정을 저장했어요/)).toBeVisible();
  harness('advance-clock', { seconds: 600 });
  await expect
    .poll(
      async () => {
        await go(page, 'search');
        await go(page, 'topics');
        return (await row.getByTestId('last-digest').textContent()) ?? '';
      },
      { timeout: 60_000, intervals: [2_000, 3_000] },
    )
    // The corpus is dated from the realm's creation day (Step 96(a)), so the 30-day
    // window holds papers and only a delivered digest ends the poll.
    .toMatch(/마지막 발송 완료/);
  await row.getByTestId('settings-link').click();
  const preview = page.getByTestId('digest-preview');
  await expect(preview).toBeVisible();
  await expect(preview.getByTestId('digest-empty')).toHaveCount(0);
  await expect(preview).toContainText('Synthetic production-size paper');
  await expect(preview).toContainText('로컬 시험 저장소');
});

// J06 as drafts ship today (the person's decision of 2026-10-23, "Test that drafts are
// off"): U4 keeps durable drafts switched off until their retention and conflict rules
// are decided, so the journey proves the switched-off state and the VerificationRun
// records drafts as a gap owed before release.
test('[J06] drafts are switched off: no save, no claim of saving, nothing carried across a reload or an account switch', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const value = fixtures();
  const text = `저장되지 않는 합성 초안 ${Date.now()}`;
  await login(page, value.accounts.memberA);
  await go(page, 'research');
  const title = `초안 ${Date.now()}`;
  await page.getByLabel('새 연구 이름').fill(title);
  await page.getByRole('button', { name: '새 연구 시작', exact: true }).click();
  await page.getByLabel('연구 질문', { exact: true }).fill(text);
  const drafts = page.getByRole('region', { name: '초안 저장' });
  // The save control stays disabled, and the page says the text lives only here.
  await expect(drafts.getByRole('button', { name: '초안 저장 사용 대기' })).toBeDisabled();
  await expect(drafts.getByRole('button', { name: '초안 저장', exact: true })).toHaveCount(0);
  await expect(drafts.getByRole('status')).toContainText(
    '브라우저를 닫거나 계정을 바꾸면 복구되지',
  );
  // Nothing claims to be saved.
  await expect(page.getByText('서버에서 저장을 확인했어요')).toHaveCount(0);
  // Nothing carries across a reload: the text is gone and nothing offers a saved copy.
  await page.reload();
  await expect(page.getByTestId('logout')).toBeVisible();
  await go(page, 'research');
  await expect(page.getByRole('region', { name: '내 연구 목록' })).toBeVisible();
  await expect(page.locator('body')).not.toContainText(text);
  await expect(page.getByRole('button', { name: '저장본 확인' })).toHaveCount(0);
  // Nothing carries across an account switch.
  await logout(page);
  await login(page, value.accounts.memberB);
  await go(page, 'research');
  await expect(page.getByRole('region', { name: '내 연구 목록' })).toBeVisible();
  await expect(page.locator('body')).not.toContainText(text);
  await expect(page.locator('body')).not.toContainText(title);
});

test('[J07] a job is accepted, progresses, is cancelled, an unknown outcome is reconciled, and the owner lists them', async ({
  page,
}) => {
  test.setTimeout(150_000);
  const value = fixtures();
  await login(page, value.accounts.memberB);
  const job = page.getByRole('region', { name: '연구 작업 상태' });
  // U4's job line, read by its test id under the complete shell (L1-9, Step 91(j)).
  const line = job.getByTestId('research-job-state');
  const refresh = job.getByRole('button', { name: '진행 상태 새로고침' });

  // Job P: accepted while the workers are stopped, then progressing to success, its event
  // stream's frames recorded across the stream's own reconnects.
  try {
    harness('service', { name: 'workers', action: 'stop' });
    const jobP = await startNoveltyJob(page, '합성 작업 수명 주제');
    await expect(line).toHaveText('접수됨 · 실행을 기다리고 있어요');
    await page.evaluate((id) => {
      const frames: { seq: number; state: string }[] = [];
      const stream = new EventSource(`/api/v2/jobs/${id}/events`);
      stream.addEventListener('snapshot', (event) => {
        const value = JSON.parse((event as MessageEvent<string>).data) as {
          seq: number;
          state: string;
        };
        frames.push({ seq: value.seq, state: value.state });
      });
      Reflect.set(window, 'u8JobStream', stream);
      Reflect.set(window, 'u8JobFrames', frames);
    }, jobP);
    await expect
      .poll(() => page.evaluate(() => (Reflect.get(window, 'u8JobFrames') as Frame[]).length), {
        timeout: 20_000,
      })
      .toBeGreaterThan(0);
  } finally {
    harness('service', { name: 'workers', action: 'start' });
  }
  await expect
    .poll(
      () =>
        page.evaluate(() => {
          const frames = Reflect.get(window, 'u8JobFrames') as Frame[];
          return frames[frames.length - 1]?.state ?? '';
        }),
      { timeout: 60_000, intervals: [1_000] },
    )
    .toBe('succeeded');
  const frames = await page.evaluate(() => {
    (Reflect.get(window, 'u8JobStream') as EventSource).close();
    return Reflect.get(window, 'u8JobFrames') as Frame[];
  });
  expect(frames[0]?.state, 'the first frame is the accepted job').toBe('accepted');
  for (let index = 1; index < frames.length; index += 1) {
    const before = frames[index - 1]!;
    const after = frames[index]!;
    expect(after.seq, 'each frame has a greater seq').toBeGreaterThan(before.seq);
    const order = `${after.state} after ${before.state}`;
    expect(JOB_ORDER.indexOf(after.state), order).toBeGreaterThanOrEqual(
      JOB_ORDER.indexOf(before.state),
    );
  }
  expect(frames.every((frame) => JOB_ORDER.includes(frame.state))).toBe(true);
  await refresh.click();
  await expect(line).toHaveText('완료됐어요 · 준비된 결과를 열 수 있어요');

  // Job C: accepted with the workers stopped again, and cancelled. It is started in the
  // research context Job P prepared, which the workspace keeps ("새 분석 준비" stays
  // disabled while a context is held).
  try {
    harness('service', { name: 'workers', action: 'stop' });
    await startNoveltyJob(page, '합성 작업 취소 주제', { inPreparedContext: true });
    await expect(line).toHaveText('접수됨 · 실행을 기다리고 있어요');
    await job.getByRole('checkbox').check();
    await job.getByRole('button', { name: '분석 취소 요청' }).click();
    await expect(line).toHaveText('취소 요청을 확인했어요 · 아직 취소 완료가 아니에요');
  } finally {
    harness('service', { name: 'workers', action: 'start' });
  }
  await expect
    .poll(
      async () => {
        await refresh.click();
        // The read's own answer, not the moment it starts ("현재 상태를 확인하고 있어요").
        await expect(refresh).not.toHaveAttribute('aria-disabled', 'true');
        return line.textContent();
      },
      { timeout: 40_000, intervals: [1_000, 2_000] },
    )
    .toBe('취소가 완료됐어요');

  // The owner's job list: both jobs, newest first, each with one link and no start, cancel
  // or retry control.
  await go(page, 'jobs');
  await page.getByTestId('jobs-filter-novelty').click();
  const list = page.getByTestId('jobs-list');
  const items = list.getByTestId('jobs-item');
  await expect(items).toHaveCount(2, { timeout: 20_000 });
  await expect(items.nth(0).getByTestId('jobs-item-state')).toHaveText('취소됨');
  await expect(items.nth(1).getByTestId('jobs-item-state')).toHaveText('완료');
  for (const index of [0, 1])
    await expect(items.nth(index).getByTestId('jobs-item-open')).toHaveCount(1);
  await expect(list.getByRole('button', { name: /시작|취소|다시 시도/ })).toHaveCount(0);
  const item = items.first();
  await item.getByTestId('jobs-item-open').click();
  await expect(page.getByTestId('jobs-selected')).toBeVisible();
  await expect(page.getByTestId('jobs-open-view')).toHaveText('참신성 분석 화면에서 열기');
  // An unknown outcome reconciled: an export whose outcome is unclear, settled by its owner.
  await logout(page);
  await login(page, value.accounts.memberA);
  await ensureNotionConnected(page);
  await exportNoveltyTo(page, value.notion.settle);
  await expect(page.getByTestId('outcome-status')).toContainText('확인 중', { timeout: 40_000 });
  harness('advance-clock', { seconds: 3_600 });
  const row = page.getByTestId('history-row').filter({ hasText: value.notion.settle });
  await expect
    .poll(
      async () => {
        await go(page, 'novelty');
        await go(page, 'export');
        return row.first().getByTestId('history-settle').isVisible();
      },
      { timeout: 60_000, intervals: [2_000, 3_000] },
    )
    .toBe(true);
  await row.first().getByTestId('history-settle').click();
  const dialog = page.getByTestId('settle-dialog');
  await dialog.getByTestId('settle-delivered').check();
  await dialog.getByTestId('settle-confirm').click();
  await expect(page.getByTestId('history-notice')).toHaveText(
    '직접 확인해 내보낸 것으로 기록했습니다',
  );
});

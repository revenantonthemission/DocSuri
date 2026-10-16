import { test, expect, type Page } from '@playwright/test';
import {
  captureResearchFailures,
  createSession,
  fixtures,
  login,
  openResearch,
  scrub,
} from './helpers';

const diagnostics = new WeakMap<Page, ReturnType<typeof captureResearchFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureResearchFailures(page));
});

test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

test('mounted session creation survives authenticated reload; reads do not submit work', async ({
  page,
}) => {
  await login(page, fixtures().accounts.memberA);
  await openResearch(page);
  const calls: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/c07/')) calls.push(new URL(request.url()).pathname);
  });
  await createSession(page, '합성 연구 여정');
  await page.reload();
  await openResearch(page);
  await page.getByRole('button', { name: /연구 1 열기/ }).click();
  await expect(page.getByLabel('연구 질문', { exact: true })).toBeVisible();
  expect(calls.filter((path) => /accept-|cancel-|delete-|save-draft/.test(path))).toEqual([]);
});

test('policy-suspended draft and attachment paths make no persistence promise', async ({
  page,
}) => {
  await login(page, fixtures().accounts.memberA);
  await openResearch(page);
  await createSession(page, '합성 정책 점검');
  await page.getByLabel('연구 질문', { exact: true }).fill('저장되지 않은 합성 질문');
  await expect(page.getByText(/브라우저를 닫거나 계정을 바꾸면 복구되지/)).toBeVisible();
  await expect(page.getByRole('button', { name: '초안 저장 사용 대기' })).toBeDisabled();
  await page.getByText('비공개 첨부 자료', { exact: true }).click();
  await expect(page.getByLabel('원고 파일')).toBeDisabled();
  await page.getByTestId('nav-novelty').click();
  await page.getByTestId('nav-research').click();
  await expect(page.getByLabel('연구 질문', { exact: true })).toHaveValue(
    '저장되지 않은 합성 질문',
  );
});

test('an explicit question reaches a real source-bound result; reload never accepts again', async ({
  page,
}) => {
  await login(page, fixtures().accounts.memberA);
  await openResearch(page);
  await createSession(page, '합성 질문 점검');
  const accepts: string[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/accept-research-turn')) accepts.push(request.url());
  });
  await page.getByText(/근거 범위 · 논문/).click();
  await page.getByLabel('논문 주소 또는 식별자').fill('u4-paper-alpha');
  await page.getByRole('button', { name: '논문 범위에 추가' }).click();
  await expect(page.getByRole('button', { name: 'u4-paper-alpha 범위에서 제외' })).toBeVisible();
  await page
    .getByLabel('연구 질문', { exact: true })
    .fill('읽은 자료의 근거와 한계를 설명해 주세요');
  await page.getByRole('button', { name: '질문 보내기', exact: true }).click();
  await expect(page.getByRole('region', { name: '연구 작업 상태' })).toBeVisible();
  const openResult = page.getByRole('button', { name: '준비된 결과 열기' });
  await expect
    .poll(
      async () => {
        if (await openResult.isVisible()) return true;
        await page.getByRole('button', { name: '진행 상태 새로고침' }).click();
        return openResult.isVisible();
      },
      { timeout: 20_000 },
    )
    .toBe(true);
  await openResult.click();
  const prepared = page.getByRole('region', { name: '준비된 연구 결과' });
  await expect(prepared).toBeVisible();
  await expect(prepared.getByRole('status')).toHaveText('일부 근거만으로 작성한 결과예요');
  await expect(prepared.getByRole('list', { name: '근거와 출처' })).toContainText(
    'u4-paper-alpha/v1',
  );
  await expect(
    prepared.getByRole('list', { name: '근거와 출처' }).locator('blockquote').first(),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByRole('region', { name: '연구 작업 상태' })).toBeVisible();
  await page.getByRole('button', { name: '준비된 결과 열기' }).click();
  await expect(page.getByRole('region', { name: '준비된 연구 결과' })).toBeVisible();
  expect(accepts).toHaveLength(1);
  const otherView = await page.context().newPage();
  try {
    await otherView.goto('/');
    await openResearch(otherView);
    await otherView.getByRole('button', { name: /연구 1 열기/ }).click();
    await otherView.getByText('현재 연구 삭제', { exact: true }).click();
    await otherView.getByLabel('현재 연구 삭제 범위를 확인했습니다').check();
    await otherView.getByRole('button', { name: '현재 연구 삭제 확인', exact: true }).click();
    await expect(otherView.getByText(/현재 연구.*삭제 경계/)).toBeVisible();
    await page.getByRole('button', { name: '진행 상태 새로고침' }).click();
    await expect(page.getByRole('region', { name: '연구 작업 상태' }).getByRole('alert')).toBeVisible();
    await expect(page.getByRole('region', { name: '준비된 연구 결과' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '준비된 결과 열기' })).toHaveCount(0);
  } finally {
    await otherView.close();
  }
});

test('novelty analysis and cancellation expose actual owner-committed progress', async ({
  page,
}) => {
  await login(page, fixtures().accounts.memberA);
  await page.getByTestId('nav-novelty').click();
  await page.getByRole('button', { name: '새 분석 준비' }).click();
  await page.getByLabel('분석할 주제 또는 원고 설명').fill('합성 참신성 주제');
  await page.getByRole('button', { name: '참신성 분석 시작' }).click();
  const job = page.getByRole('region', { name: '연구 작업 상태' });
  await expect(job).toBeVisible();
  await expect(job.getByRole('status').first()).toContainText(/접수됨|실행 중|완료됐어요/);
  const cancel = job.getByRole('button', { name: '분석 취소 요청' });
  if (await cancel.isVisible()) {
    await expect(cancel).toBeDisabled();
    await job.getByRole('checkbox').check();
    await cancel.click();
  }
  await expect
    .poll(
      async () => {
        const refresh = page.getByRole('button', { name: '진행 상태 새로고침' });
        await refresh.click();
        await expect(refresh).toBeEnabled();
        return job.getByRole('status').first().textContent();
      },
      { timeout: 20_000 },
    )
    .toMatch(/취소가 완료|완료됐어요/);
  const prepared = job.getByRole('button', { name: '준비된 결과 열기' });
  if (await prepared.isVisible()) {
    await prepared.click();
    await expect(
      page.getByRole('region', { name: '준비된 연구 결과' }).getByRole('status'),
    ).toHaveText('근거가 부족해 판단을 보류했어요');
  }
});

test('logout and another account clear unsent input and deny prior job recovery', async ({
  page,
}) => {
  await login(page, fixtures().accounts.memberA);
  await openResearch(page);
  await createSession(page, '합성 격리 점검');
  await page.getByLabel('연구 질문', { exact: true }).fill('이 계정의 합성 비공개 질문');
  await page.getByRole('button', { name: '질문 보내기', exact: true }).click();
  await expect(page.getByRole('region', { name: '연구 작업 상태' })).toBeVisible();
  const recoveryUrl = page.url();
  await page.getByLabel('연구 질문', { exact: true }).fill('전송되지 않은 합성 질문');
  await page.getByTestId('logout').click();
  await expect(page.getByTestId('workspace-research')).toHaveCount(0);
  await login(page, fixtures().accounts.memberB);
  await openResearch(page);
  await expect(page.getByText('저장된 연구가 없어요. 새 연구를 시작해 보세요.')).toBeVisible();
  await expect(page.getByLabel('연구 질문', { exact: true })).toHaveCount(0);
  await page.goto(recoveryUrl);
  await expect(
    page.getByRole('region', { name: '연구 작업 상태' }).getByRole('alert'),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: '준비된 결과 열기' })).toHaveCount(0);
});

test('keyboard, appearance and narrow viewport preserve usable research controls', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, fixtures().accounts.memberA);
  await openResearch(page);
  await page.getByLabel('새 연구 이름').fill('합성 키보드 점검');
  await page.getByLabel('새 연구 이름').press('Enter');
  await expect(page.getByLabel('연구 질문', { exact: true })).toBeVisible();
  await page.getByLabel('연구 질문', { exact: true }).focus();
  await expect(page.getByLabel('연구 질문', { exact: true })).toBeFocused();
  for (const appearance of ['dark', 'light', 'system']) {
    await page.getByTestId('appearance-select').selectOption(appearance);
    await expect(page.getByTestId('workspace-research')).toBeVisible();
  }
  const overflows = await page
    .getByTestId('workspace-research')
    .evaluate((element) => element.scrollWidth > element.clientWidth + 1);
  expect(overflows).toBe(false);
});

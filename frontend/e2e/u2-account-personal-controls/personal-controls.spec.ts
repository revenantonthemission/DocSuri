import { test, expect } from '@playwright/test';
import { clearProtectedContext } from './helpers';
test.afterEach(async ({ page }) => clearProtectedContext(page));
import { fixtures, login, openControls, saveFixturePaper } from './helpers';
test('profile, interests and appearance survive a fresh page', async ({ page }) => {
  await login(page, fixtures().accounts.memberA);
  await openControls(page, 'account');
  await page.getByLabel('표시 이름', { exact: true }).fill('한국어 연구자 브라우저 검증');
  await page.getByRole('button', { name: '프로필 저장' }).click();
  await expect(page.getByText('요청 결과를 확인했어요').first()).toBeVisible();
  await openControls(page, 'settings');
  await page.getByLabel('저장할 화면 모드').selectOption('dark');
  await page.getByRole('button', { name: '기본 설정 저장' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByText('관심 분야와 시작 설정', { exact: true }).click();
  await page.getByRole('checkbox', { name: /Transformer/ }).check();
  await page.getByRole('button', { name: '관심 분야 저장' }).click();
  await expect(page.getByText('요청 결과를 확인했어요').first()).toBeVisible();
  await page.reload();
  await openControls(page, 'settings');
  await page.getByText('관심 분야와 시작 설정', { exact: true }).click();
  await expect(page.getByRole('checkbox', { name: /Transformer/ })).toBeChecked();
  await expect(page.getByLabel('저장할 화면 모드')).toHaveValue('dark');
});
test('real search, save, revisit and scoped history clear', async ({ page }) => {
  await login(page, fixtures().accounts.memberA);
  await saveFixturePaper(page);
  await openControls(page, 'library');
  await expect(page.getByTestId('library-open-paper').first()).toBeVisible();
  await page.getByRole('button', { name: '검색 기록', exact: true }).click();
  await page.getByTestId('library-clear-history').click();
  await page.getByTestId('library-confirm').click();
  await expect(page.getByTestId('library-empty')).toBeVisible();
  await page.getByRole('button', { name: '저장한 논문', exact: true }).click();
  await expect(page.getByTestId('library-open-paper').first()).toBeVisible();
});
test('consent revocation leaves manual settings usable and is separately reversible', async ({
  page,
}) => {
  await login(page, fixtures().accounts.memberA);
  await openControls(page, 'account');
  await page.getByText('개인정보와 처리 동의', { exact: true }).click();
  const row = page.locator('.control-row').filter({ hasText: 'personalization' });
  if (await row.getByRole('button', { name: '처리 동의' }).isVisible()) {
    await row.getByRole('button', { name: '처리 동의' }).click();
    await expect(row).toContainText('동의함');
  }
  await row.getByRole('button', { name: '동의 철회' }).click();
  await expect(row).toContainText('철회함');
  await openControls(page, 'settings');
  await expect(page.getByRole('button', { name: '기본 설정 저장' })).toBeVisible();
  await openControls(page, 'account');
  await page.getByText('개인정보와 처리 동의', { exact: true }).click();
  await page
    .locator('.control-row')
    .filter({ hasText: 'personalization' })
    .getByRole('button', { name: '처리 동의' })
    .click();
  await expect(page.locator('.control-row').filter({ hasText: 'personalization' })).toContainText(
    '동의함',
  );
});
test('reset rediscovery after restart is read-only and keeps saved work', async ({ page }) => {
  const account = fixtures().accounts.memberA;
  await login(page, account);
  await saveFixturePaper(page);
  await openControls(page, 'settings');
  await page.getByText('활동 삭제와 추천 프로필 초기화', { exact: true }).click();
  await page.getByLabel('초기화용 현재 비밀번호').fill(account.password);
  await page.getByRole('button', { name: '초기화 범위 확인 준비' }).click();
  await page.getByRole('button', { name: '초기화 접수', exact: true }).click();
  await page.getByLabel('처리 기록 범위').selectOption('history');
  await page.getByRole('button', { name: '처리 기록 새로 읽기' }).click();
  await expect(
    page
      .getByRole('button', {
        name: /활동 데이터 삭제 · (정리 진행 중|전체 정리 완료|추가 확인 필요)/,
      })
      .first(),
  ).toBeVisible();
  let writes = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/settings-reset')) writes++;
  });
  await page.reload();
  await openControls(page, 'settings');
  await page.getByText('활동 삭제와 추천 프로필 초기화', { exact: true }).click();
  await page.getByLabel('처리 기록 범위').selectOption('history');
  await page
    .getByRole('button', {
      name: /활동 데이터 삭제 · (정리 진행 중|전체 정리 완료|추가 확인 필요)/,
    })
    .first()
    .click();
  await expect(page.getByText(/접수된 경계와 정리 완료는 별도/)).toBeVisible();
  expect(writes).toBe(0);
  await openControls(page, 'library');
  await expect(page.getByTestId('library-open-paper').first()).toBeVisible();
});
test('administrator MFA controls target-specific free allocation and revocation', async ({
  page,
}) => {
  const f = fixtures();
  await login(page, f.accounts.admin, true);
  await openControls(page, 'usage');
  await page.getByText('관리자 할당', { exact: true }).click();
  await page.getByLabel('대상 계정 ID').fill(f.accounts.memberB.accountId);
  await page.getByRole('button', { name: '대상 할당 읽기' }).click();
  await page.getByLabel('할당 변경 사유').fill('browser-verification');
  await page.getByRole('button', { name: '무료 시험 할당 적용' }).click();
  await expect(page.getByText(/현재 할당: synthetic-free/)).toBeVisible();
  await page.getByRole('button', { name: '할당 철회 준비' }).click();
  await page.getByRole('button', { name: '할당 철회 확인', exact: true }).click();
  await expect(page.getByText(/현재 할당: synthetic-free \/ revoked/)).toBeVisible();
});

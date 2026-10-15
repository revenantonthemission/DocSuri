import { test, expect } from '@playwright/test';
import { clearProtectedContext } from './helpers';
test.afterEach(async ({ page }) => clearProtectedContext(page));
import { fixtures, login, noOverflow, openControls, verifyLink } from './helpers';
test('logout and account switch clear the previous private form and do not replay it', async ({
  page,
}) => {
  const f = fixtures();
  await login(page, f.accounts.memberA);
  await openControls(page, 'account');
  await page.getByLabel('소속').fill('UNSAVED-PRIVATE-OWNER-A');
  await page.getByTestId('logout').click();
  await login(page, f.accounts.memberB);
  await openControls(page, 'account');
  await expect(page.getByLabel('소속')).not.toHaveValue('UNSAVED-PRIVATE-OWNER-A');
  await expect(page.locator('body')).not.toContainText(f.accounts.memberA.email);
  await page.goBack();
  await expect(page.locator('body')).not.toContainText('UNSAVED-PRIVATE-OWNER-A');
});
test('withdrawal and reactivation report observed progress through narrow access', async ({
  page,
}) => {
  const account = fixtures().accounts.lifecycle;
  await login(page, account);
  await openControls(page, 'account');
  await page.getByText('탈퇴와 데이터 삭제', { exact: true }).click();
  await page.getByLabel('계정 처리용 현재 비밀번호').fill(account.password);
  await page.getByRole('button', { name: '처리 범위 확인 준비' }).click();
  await page.getByRole('button', { name: '확인하고 접수' }).click();
  await expect(page.getByTestId('entry-panel')).toBeVisible();
  await expect(page.getByText(/처리가 아직 완료되지|모든 필수 범위의 처리가 완료/)).toBeVisible();
  await page.getByRole('button', { name: '탈퇴 계정 재활성화' }).click();
  await page.getByLabel('이메일', { exact: true }).fill(account.email);
  await page.getByTestId('entry-submit').click();
  await expect(page.getByText(/대상과 조건이 맞으면/)).toBeVisible();
  await verifyLink(page, 'lifecycle', 'reactivate');
  await page.getByTestId('entry-submit').click();
  await expect(page.getByText(/처리가 아직 완료되지|모든 필수 범위의 처리가 완료/)).toBeVisible();
  await expect(page.getByTestId('logout')).toHaveCount(0);
});
for (const [width, height, mode] of [
  [1440, 960, 'light'],
  [820, 1180, 'dark'],
  [390, 844, 'system'],
] as const)
  test(`Korean controls reflow and keyboard navigation ${width}px ${mode}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await login(page, fixtures().accounts.memberA);
    await page.getByTestId('appearance-select').selectOption(mode);
    await openControls(page, 'account');
    await page
      .getByLabel('표시 이름', { exact: true })
      .fill('긴 한국어 연구자 이름과 이해하기 쉬운 설명을 위한 화면 검증');
    await noOverflow(page);
    await page.getByLabel('표시 이름', { exact: true }).focus();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel('소속')).toBeFocused();
    await openControls(page, 'settings');
    await noOverflow(page);
    await openControls(page, 'usage');
    await expect(page.getByText(/결제나 구매가 발생하지/)).toBeVisible();
    await noOverflow(page);
  });

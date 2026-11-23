// J09: a backup and a restore verification, each requested by the administrator in 운영
// and performed by the operator (the harness acting as you), with an owner erased between
// them who the verification proves is not revived (BR4.1, BR4.2, BR2.6).
import { test, expect, type Page } from '@playwright/test';
import {
  captureFailures,
  fixtures,
  go,
  harness,
  login,
  loginAdministrator,
  logout,
  scrub,
} from './helpers';

test.describe.configure({ mode: 'serial' });

const diagnostics = new WeakMap<Page, ReturnType<typeof captureFailures>>();
test.beforeEach(({ page }) => {
  diagnostics.set(page, captureFailures(page));
});
test.afterEach(async ({ page }, info) => {
  await diagnostics.get(page)?.(info);
  await scrub(page);
});

type Verification = {
  integrity: string;
  erasedOwnersSurviving: number;
  result: string;
  registerHeadSequence: number;
};

/** In 운영, one recovery request confirmed in its dialog. */
async function requestRecovery(page: Page, operation: 'backup.create' | 'restore.verify') {
  await go(page, 'operations');
  const panel = page.getByTestId('recovery-panel');
  await expect(panel).toBeVisible();
  await panel.getByTestId(`recovery-operation-${operation}`).check();
  if (operation === 'restore.verify') {
    // The newest set that passed its integrity check, once the dashboard shows it.
    await expect
      .poll(
        async () => {
          if ((await panel.getByTestId('recovery-set').count()) > 0) return true;
          await page.reload();
          await go(page, 'operations');
          await panel.getByTestId(`recovery-operation-${operation}`).check();
          return (await panel.getByTestId('recovery-set').count()) > 0;
        },
        { timeout: 40_000, intervals: [2_000, 3_000] },
      )
      .toBe(true);
    await panel.getByTestId('recovery-set').last().check();
  }
  await panel.getByTestId('recovery-open').click();
  await expect(page.getByTestId('recovery-submit')).toBeVisible();
  // Only an operation that changes data asks for the acknowledgement; a backup does not.
  const acknowledge = page.getByTestId('recovery-acknowledge');
  if ((await acknowledge.count()) > 0) await acknowledge.check();
  await page.getByTestId('recovery-submit').click();
  // The panel's plain confirmation line (Step 93(b)); the announcement is OperationsView's.
  await expect(panel.getByTestId('recovery-confirmation')).toContainText('요청 상태: 요청됨');
}

/** The newest request's state as the administrator's panel shows it. */
async function untilRequestState(page: Page, text: string) {
  await expect
    .poll(
      async () => {
        await page.reload();
        await go(page, 'operations');
        // The panel lists the newest request first.
        return (await page.getByTestId('recovery-request').first().textContent()) ?? '';
      },
      { timeout: 40_000, intervals: [2_000, 3_000] },
    )
    .toContain(text);
}

test('[J09] a backup, an erased owner, and a restore verification that does not revive them', async ({
  page,
}) => {
  // Under the phase's 280 s suite bound (`browser-recovery`, this journey alone), so a
  // slow step fails here with its own error context rather than at the suite's bound.
  test.setTimeout(180_000);
  const value = fixtures();
  const erased = value.accounts.memberC;
  // 1. The administrator requests a backup; the operator performs it.
  await loginAdministrator(page, value.accounts.administrator);
  await requestRecovery(page, 'backup.create');
  const backup = harness<{ state: string }>('recovery', { word: 'backup' });
  expect(backup.state, JSON.stringify(backup).slice(0, 600)).toBe('succeeded');
  await untilRequestState(page, '완료');
  await logout(page);

  // 2. memberC, who is in that backup, erases their account in 계정.
  await login(page, erased);
  await go(page, 'account');
  await page.getByText('탈퇴와 데이터 삭제', { exact: true }).click();
  await page.getByLabel('처리 범위').selectOption('erase');
  await page.getByLabel('계정 처리용 현재 비밀번호').fill(erased.password);
  await page.getByRole('button', { name: '처리 범위 확인 준비' }).click();
  await page.getByRole('button', { name: '확인하고 접수' }).click();
  await expect(page.getByTestId('logout')).toHaveCount(0);
  // The erasure's restore-enforcement scope appends the owner's tombstone.
  await expect
    .poll(() => harness<{ accounts: string[] }>('tombstones').accounts.includes(erased.accountId), {
      timeout: 60_000,
      intervals: [2_000, 3_000],
    })
    .toBe(true);

  // 3. The administrator requests a verification of that backup; the operator runs it.
  await loginAdministrator(page, value.accounts.administrator);
  await requestRecovery(page, 'restore.verify');
  const verified = harness<{ state: string; verification: Verification }>('recovery', {
    word: 'verify',
  });
  expect(verified.state, JSON.stringify(verified).slice(0, 600)).toBe('succeeded');
  expect(verified.verification.integrity).toBe('passed');
  expect(verified.verification.result).toBe('verified');
  // The restored copy holds memberC's rows, and the register removes them: none survive.
  expect(verified.verification.erasedOwnersSurviving).toBe(0);
  await untilRequestState(page, '완료');
  await logout(page);
  // With the verification's register head at or above their tombstones, the erasures'
  // restore-enforcement parts complete across every participant: memberC's always, and
  // memberD's too when the lifecycle journey has already erased them. The verification
  // run puts this journey first, before the corpus loads (the person's decision of
  // 2026-10-23, "Smaller database"), so there memberD is not yet erased.
  const newestRequest = (accountId: string) =>
    harness<{
      requests: { action: string; disposition: string; scopes: { disposition: string }[] }[];
    }>('lifecycle', { accountId }).requests[0];
  const lifecycleErased = newestRequest(value.accounts.memberD.accountId)?.action === 'erase';
  const owners = lifecycleErased ? [erased, value.accounts.memberD] : [erased];
  for (const owner of owners) {
    await expect
      .poll(
        () => {
          const newest = newestRequest(owner.accountId);
          if (!newest || newest.action !== 'erase') return 'no-erasure';
          return newest.scopes.every((scope) => scope.disposition === 'complete')
            ? newest.disposition
            : 'parts-pending';
        },
        { timeout: 60_000, intervals: [2_000, 3_000] },
      )
      .toBe('complete');
  }

  // 4. The erased owner stays erased in the live service.
  await page.goto('/');
  await page.getByTestId('entry-email').fill(erased.email);
  await page.getByTestId('entry-password').fill(erased.password);
  await page.getByTestId('entry-submit').click();
  await expect(page.getByRole('alert').first()).toBeVisible();
  await expect(page.getByTestId('logout')).toHaveCount(0);
});

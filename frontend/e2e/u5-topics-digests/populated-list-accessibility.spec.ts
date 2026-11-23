// U5 NFR5.1 in Chromium (plan Step 37 (b)): a populated topic list passes axe (WCAG 2.0
// A/AA, 2.1 AA, 2.2 AA), reflows at 320 CSS px and shows a visible focus indicator on
// each of its controls in the four theme settings (a11y.ts), and the settings form's
// controls are found by role and Korean accessible name. Any finding fails.
//
// Playwright orders spec files by name and the realm runs one worker, so this file runs
// after journey.spec.ts: memberA's list then holds the fixture's topics and whatever the
// journeys left followed, and nothing here changes a topic or saves a form.
import { test, expect, type Page } from '@playwright/test';
import {
  applyTheme,
  axeFindings,
  currentAppearance,
  focusFindings,
  reflowFindings,
  restoreTheme,
  THEMES,
} from './a11y';
import { captureTopicsFailures, fixtures, login, openTopics, scrub } from './helpers';

const failures = new WeakMap<Page, ReturnType<typeof captureTopicsFailures>>();
test.beforeEach(({ page }) => {
  failures.set(page, captureTopicsFailures(page));
});

test.afterEach(async ({ page }, info) => {
  await failures.get(page)?.(info);
  await scrub(page);
});

test('a populated topic list passes axe, reflows at 320 CSS px and shows focus in every theme', async ({
  page,
}) => {
  await login(page, fixtures().accounts.memberA);
  await openTopics(page);
  const original = await currentAppearance(page);
  const list = page.getByTestId('topic-list');
  await expect(
    list.getByTestId('topic-row').filter({ hasText: '해결 확인 주제' }),
    'the fixture keeps memberA following at least one topic',
  ).toBeVisible();
  try {
    for (const theme of THEMES) {
      await applyTheme(page, theme);
      await expect(list).toBeVisible();
      expect.soft(await axeFindings(page, list), `${theme.label}: axe`).toEqual([]);
      expect.soft(await reflowFindings(page, list), `${theme.label}: reflow`).toEqual([]);
      // The list's first control follows the page heading in the tab order.
      const focus = await focusFindings(page, list, () =>
        page.getByTestId('topics-heading').focus(),
      );
      expect.soft(focus, `${theme.label}: focus`).toEqual([]);
    }
  } finally {
    await restoreTheme(page, original);
  }
});

test('the settings form names its dialog and every control in Korean', async ({ page }) => {
  await login(page, fixtures().accounts.memberA);
  await openTopics(page);
  const row = page.getByTestId('topic-row').filter({ hasText: '해결 확인 주제' });
  await row.getByTestId('settings-link').click();
  const form = page.getByRole('dialog', { name: "'해결 확인 주제' 발송 설정", exact: true });
  await expect(form).toHaveAttribute('data-testid', 'settings-form');
  const named = (role: 'combobox' | 'button', name: string) =>
    form.getByRole(role, { name, exact: true });
  await expect(named('combobox', '발송 주기')).toHaveAttribute('data-testid', 'cadence-select');
  await expect(named('combobox', '불러올 기간')).toHaveAttribute('data-testid', 'window-select');
  // A time field has no ARIA role of its own, so it is found by its Korean label.
  await expect(form.getByLabel(/^발송 시각 \(.+ 기준\)$/)).toHaveAttribute(
    'data-testid',
    'delivery-time',
  );
  await expect(named('button', '계정 환경설정 변경')).toHaveAttribute(
    'data-testid',
    'preferences-toggle',
  );
  await expect(named('button', '닫기')).toHaveAttribute('data-testid', 'settings-close');
  await expect(named('button', '구독 해지')).toHaveAttribute('data-testid', 'settings-unsubscribe');
  await expect(named('button', '저장')).toHaveAttribute('data-testid', 'save-button');
  // The weekly-only day select carries its own Korean name once it is shown; the draft
  // is never saved.
  await named('combobox', '발송 주기').selectOption('weekly');
  await expect(named('combobox', '발송 요일')).toHaveAttribute('data-testid', 'delivery-day');
  await named('button', '닫기').click();
  await expect(form).toHaveCount(0);
});

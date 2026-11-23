// U5 NFR5.1, the settings form: axe (WCAG 2.0 A/AA, 2.1 AA, 2.2 AA), 320 CSS px reflow
// and a visible focus indicator on each of its controls, in the light, dark and system
// themes (a11y.ts). The form is checked with every control it can show: the account
// preferences open and a weekly draft with its day, which is never saved. Any finding
// fails.
//
// The check reads no fixture state that a journey changes, so it runs after
// journey.spec.ts (Playwright orders spec files by name): a finding here never stops the
// journeys under the realm's one-failure limit.
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

test('the settings form passes axe, reflows at 320 CSS px and shows focus in every theme', async ({
  page,
}) => {
  await login(page, fixtures().accounts.memberA);
  await openTopics(page);
  const original = await currentAppearance(page);
  const row = page.getByTestId('topic-row').filter({ hasText: '해결 확인 주제' });
  try {
    for (const theme of THEMES) {
      await applyTheme(page, theme);
      await row.getByTestId('settings-link').click();
      const form = page.getByTestId('settings-form');
      await expect(form.getByTestId('cadence-select')).toBeVisible();
      await form.getByTestId('preferences-toggle').click();
      await expect(form.getByTestId('digest-language')).toBeVisible();
      await form.getByTestId('cadence-select').selectOption('weekly');
      await form.getByTestId('delivery-day').selectOption('mon');
      await expect(form.getByTestId('save-button')).toBeEnabled();
      expect.soft(await axeFindings(page, form), `${theme.label}: axe`).toEqual([]);
      expect.soft(await reflowFindings(page, form), `${theme.label}: reflow`).toEqual([]);
      // The form keeps Tab inside it: from its last control, Tab returns to the first.
      const focus = await focusFindings(page, form, () => form.getByTestId('save-button').focus());
      expect.soft(focus, `${theme.label}: focus`).toEqual([]);
      await form.getByTestId('settings-close').click();
      await expect(form).toHaveCount(0);
    }
  } finally {
    await restoreTheme(page, original);
  }
});

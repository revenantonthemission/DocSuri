// U5 NFR5.1, the resolve control: axe (WCAG 2.0 A/AA, 2.1 AA, 2.2 AA), 320 CSS px reflow
// and a visible focus indicator on each of its buttons, in the light, dark and system
// themes (a11y.ts). Any finding fails.
//
// Playwright orders spec files by name and the realm runs one worker, so this file runs
// before journey.spec.ts: the fixture's one open unknown outcome is still open here, and
// this check never presses a resolve button (the resolve journey settles it). The
// settings form has no such ordering need; settings-accessibility.spec.ts checks it.
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

test('the resolve control passes axe, reflows at 320 CSS px and shows focus in every theme', async ({
  page,
}) => {
  await login(page, fixtures().accounts.memberA);
  await openTopics(page);
  const original = await currentAppearance(page);
  const row = page.getByTestId('topic-row').filter({ hasText: '해결 확인 주제' });
  const control = row.getByTestId('resolve-control');
  await expect(control, 'the fixture keeps one open unknown outcome').toBeVisible();
  try {
    for (const theme of THEMES) {
      await applyTheme(page, theme);
      await expect(control).toBeVisible();
      expect.soft(await axeFindings(page, control), `${theme.label}: axe`).toEqual([]);
      expect.soft(await reflowFindings(page, control), `${theme.label}: reflow`).toEqual([]);
      // The control follows the row's own actions in the tab order.
      const focus = await focusFindings(page, control, () =>
        row.getByTestId('unsubscribe-button').focus(),
      );
      expect.soft(focus, `${theme.label}: focus`).toEqual([]);
    }
  } finally {
    await restoreTheme(page, original);
  }
  // Nothing here resolved the outcome: the resolve journey still finds it open.
  await expect(control).toBeVisible();
});

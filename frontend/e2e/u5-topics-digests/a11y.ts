// U5 NFR5.1 accessibility checks shared by the resolve-control and settings-form specs:
// axe with the WCAG 2.0 A/AA, 2.1 AA and 2.2 AA tags, 320 CSS px reflow (WCAG 1.4.10)
// and a keyboard walk that measures each control's focus indicator, in the light, dark
// and system themes. Each explicit theme is applied while the operating system prefers
// the other one, so the person's choice is shown to win, and the system theme under both
// preferences. A finding names its rule or control, never page content.
import { inflateSync } from 'node:zlib';
import AxeBuilder from '@axe-core/playwright';
import { expect, type JSHandle, type Locator, type Page } from '@playwright/test';

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'];
const NARROW = { width: 320, height: 720 };
const WIDE = { width: 1280, height: 720 };
// WCAG 1.4.11: the focus indicator keeps 3:1 against the colour it is drawn on.
const FOCUS_CONTRAST = 3;
// A focus change drawn inside a control's own (closed) parts, such as the highlighted
// part of a time field, is measured on screen: at least this many pixels must change by
// 3:1 or more between the focused and the unfocused control.
const VISIBLE_PIXELS = 64;

export type Appearance = 'light' | 'dark' | 'system';
export type Theme = { appearance: Appearance; scheme: 'light' | 'dark'; label: string };
export const THEMES: Theme[] = [
  { appearance: 'light', scheme: 'dark', label: 'light (system prefers dark)' },
  { appearance: 'dark', scheme: 'light', label: 'dark (system prefers light)' },
  { appearance: 'system', scheme: 'light', label: 'system (light)' },
  { appearance: 'system', scheme: 'dark', label: 'system (dark)' },
];

export async function currentAppearance(page: Page): Promise<Appearance> {
  return (await page.getByTestId('appearance-select').inputValue()) as Appearance;
}

/** The header's appearance choice, saved to the account before the check goes on. */
export async function chooseAppearance(page: Page, appearance: Appearance) {
  const select = page.getByTestId('appearance-select');
  if ((await select.inputValue()) === appearance) return;
  const saved = page.waitForResponse(
    (response) => new URL(response.url()).pathname === '/api/v2/c03/settings-update',
  );
  await select.selectOption(appearance);
  expect((await saved).ok(), `the ${appearance} appearance is saved`).toBe(true);
}

export async function applyTheme(page: Page, theme: Theme) {
  await page.emulateMedia({ colorScheme: theme.scheme });
  await chooseAppearance(page, theme.appearance);
  const root = page.locator('html');
  if (theme.appearance === 'system') await expect(root).not.toHaveAttribute('data-theme');
  else await expect(root).toHaveAttribute('data-theme', theme.appearance);
  const dark = await page.evaluate(() => window.matchMedia('(prefers-color-scheme: dark)').matches);
  expect(dark ? 'dark' : 'light', `${theme.label}: the emulated preference`).toBe(theme.scheme);
}

/** Back to the account's own appearance and the default preference. */
export async function restoreTheme(page: Page, appearance: Appearance) {
  await page.emulateMedia({ colorScheme: 'light' });
  await chooseAppearance(page, appearance);
}

/** axe over one surface; each violation as `rule target`, with the measured colours
 * for a contrast failure. axe cannot judge the colours of a control scrolled out of a
 * scrolling surface's view, so a surface taller than its view is checked at scroll steps
 * from top to bottom that overlap by more than any of its controls is tall: every
 * control is wholly in view at one of them. */
export async function axeFindings(page: Page, surface: Locator): Promise<string[]> {
  const selector = `[data-testid="${await surface.getAttribute('data-testid')}"]`;
  const steps = await surface.evaluate((element) => {
    const end = element.scrollHeight - element.clientHeight;
    if (end <= 0) return [0];
    const tallest = Math.max(
      0,
      ...Array.from(element.querySelectorAll('button, input, select, textarea, a[href]')).map(
        (control) => control.getBoundingClientRect().height,
      ),
    );
    const stride = Math.max(1, Math.floor(element.clientHeight - tallest - 16));
    const tops: number[] = [];
    for (let top = 0; top < end; top += stride) tops.push(top);
    return [...tops, end];
  });
  const found = new Set<string>();
  try {
    for (const top of steps) {
      await surface.evaluate((element, value) => {
        element.scrollTop = value;
      }, top);
      const result = await new AxeBuilder({ page })
        .options({ resultTypes: ['violations'] })
        .withTags(TAGS)
        .include(selector)
        .analyze();
      for (const violation of result.violations) {
        for (const node of violation.nodes) {
          const data = node.any.find((check) => check.id === 'color-contrast')?.data as
            | { contrastRatio?: number; fgColor?: string; bgColor?: string }
            | undefined;
          const measured =
            data?.contrastRatio !== undefined
              ? ` (${data.contrastRatio}:1, ${data.fgColor} on ${data.bgColor})`
              : '';
          found.add(`${violation.id} ${node.target.join(' ')}${measured}`);
        }
      }
    }
  } finally {
    await surface.evaluate((element) => {
      element.scrollTop = 0;
    });
  }
  return [...found];
}

/** At 320 CSS px: no sideways scroll, and every control inside the viewport. */
export async function reflowFindings(page: Page, surface: Locator): Promise<string[]> {
  await page.setViewportSize(NARROW);
  try {
    return await surface.evaluate((element) => {
      const found: string[] = [];
      const width = window.innerWidth;
      if (document.documentElement.scrollWidth > width + 1) found.push('the page scrolls sideways');
      if (element.scrollWidth > element.clientWidth + 1) found.push('the surface scrolls sideways');
      const controls = element.querySelectorAll<HTMLElement>(
        'button, input, select, textarea, a[href]',
      );
      for (const control of Array.from(controls)) {
        const box = control.getBoundingClientRect();
        if (box.width === 0 && box.height === 0) continue;
        if (box.left < -1 || box.right > width + 1) {
          found.push(
            `${control.dataset.testid || control.tagName.toLowerCase()} leaves the viewport`,
          );
        }
      }
      return found;
    });
  } finally {
    await page.setViewportSize(WIDE);
  }
}

/** The enabled, rendered controls a keyboard can reach in the surface. */
async function tabbable(surface: Locator): Promise<string[]> {
  return surface.evaluate((element) =>
    Array.from(
      element.querySelectorAll<HTMLElement>('button, input, select, textarea, a[href], [tabindex]'),
    )
      .filter(
        (control) =>
          control.tabIndex >= 0 &&
          !control.matches(':disabled') &&
          control.getClientRects().length > 0,
      )
      .map((control) => control.dataset.testid || control.id || control.tagName.toLowerCase()),
  );
}

type FocusStop = { control: string; problems: string[] };

/** The focused control inside the surface and what its focus indicator shows, or null
 * once focus has left the surface. */
async function focusStop(surface: Locator): Promise<FocusStop | null> {
  return surface.evaluate((element, threshold) => {
    const active = document.activeElement;
    if (!(active instanceof HTMLElement) || !element.contains(active)) return null;
    const rgba = (value: string): number[] | null => {
      const match = value.match(/rgba?\(([^)]+)\)/);
      if (!match?.[1]) return null;
      const parts = match[1]
        .split(/[\s,/]+/)
        .filter(Boolean)
        .map(Number);
      return parts.length >= 3
        ? [parts[0] ?? 0, parts[1] ?? 0, parts[2] ?? 0, parts[3] ?? 1]
        : null;
    };
    const luminance = (color: number[]) => {
      const [r, g, b] = color.slice(0, 3).map((channel) => {
        const value = channel / 255;
        return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
    };
    const problems: string[] = [];
    if (!active.matches(':focus-visible')) problems.push('does not match :focus-visible');
    const style = window.getComputedStyle(active);
    const outline = rgba(style.outlineColor);
    const outlined =
      style.outlineStyle !== 'none' &&
      Number.parseFloat(style.outlineWidth) >= 1 &&
      outline !== null &&
      (outline[3] ?? 0) > 0;
    if (!outlined && style.boxShadow === 'none') problems.push('shows no focus indicator');
    if (outlined && outline) {
      // The indicator is drawn, past its offset, on the nearest opaque surface behind.
      let backdrop = [255, 255, 255, 1];
      for (let node = active.parentElement; node; node = node.parentElement) {
        const color = rgba(window.getComputedStyle(node).backgroundColor);
        if (color && (color[3] ?? 0) >= 1) {
          backdrop = color;
          break;
        }
      }
      const [light, dark] = [luminance(outline), luminance(backdrop)].sort((a, b) => b - a);
      const ratio = ((light ?? 0) + 0.05) / ((dark ?? 0) + 0.05);
      if (ratio < threshold) problems.push(`indicator contrast ${ratio.toFixed(2)}:1`);
    }
    const box = active.getBoundingClientRect();
    const x = Math.min(Math.max(box.left + box.width / 2, 0), window.innerWidth - 1);
    const y = Math.min(Math.max(box.top + box.height / 2, 0), window.innerHeight - 1);
    const hit = document.elementFromPoint(x, y);
    if (!hit || !(hit === active || active.contains(hit) || hit.contains(active))) {
      problems.push('is obscured');
    }
    return {
      control: active.dataset.testid || active.id || active.tagName.toLowerCase(),
      problems,
    };
  }, FOCUS_CONTRAST);
}

type Pixels = { width: number; height: number; channels: number; data: Uint8Array };

/** The pixels of a Playwright screenshot: 8-bit RGB or RGBA, not interlaced. */
function decodePng(png: Buffer): Pixels {
  let offset = 8;
  let width = 0;
  let height = 0;
  let channels = 0;
  const parts: Buffer[] = [];
  while (offset + 8 <= png.length) {
    const length = png.readUInt32BE(offset);
    const type = png.toString('ascii', offset + 4, offset + 8);
    const data = png.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      if (data[8] !== 8 || (data[9] !== 2 && data[9] !== 6) || data[12] !== 0) {
        throw new Error('unsupported screenshot encoding');
      }
      channels = data[9] === 6 ? 4 : 3;
    } else if (type === 'IDAT') {
      parts.push(data);
    } else if (type === 'IEND') {
      break;
    }
    offset += 12 + length;
  }
  const raw = inflateSync(Buffer.concat(parts));
  const stride = width * channels;
  const pixels = new Uint8Array(height * stride);
  for (let y = 0; y < height; y += 1) {
    const filter = raw[y * (stride + 1)] ?? 0;
    const row = y * (stride + 1) + 1;
    for (let x = 0; x < stride; x += 1) {
      const left = x >= channels ? (pixels[y * stride + x - channels] ?? 0) : 0;
      const up = y > 0 ? (pixels[(y - 1) * stride + x] ?? 0) : 0;
      const corner = x >= channels && y > 0 ? (pixels[(y - 1) * stride + x - channels] ?? 0) : 0;
      let predicted = 0;
      if (filter === 1) predicted = left;
      else if (filter === 2) predicted = up;
      else if (filter === 3) predicted = (left + up) >> 1;
      else if (filter === 4) {
        const estimate = left + up - corner;
        const [toLeft, toUp, toCorner] = [left, up, corner].map((value) =>
          Math.abs(estimate - value),
        ) as [number, number, number];
        predicted = toLeft <= toUp && toLeft <= toCorner ? left : toUp <= toCorner ? up : corner;
      }
      pixels[y * stride + x] = ((raw[row + x] ?? 0) + predicted) & 0xff;
    }
  }
  return { width, height, channels, data: pixels };
}

function luminance(red: number, green: number, blue: number): number {
  const [r, g, b] = [red, green, blue].map((channel) => {
    const value = channel / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Pixels that differ by 3:1 or more between two same-size images. */
function strongChanges(before: Pixels, after: Pixels): number {
  if (before.width !== after.width || before.height !== after.height) return 0;
  let count = 0;
  for (let index = 0; index < before.width * before.height; index += 1) {
    const [p, q] = [index * before.channels, index * after.channels];
    const one = luminance(before.data[p] ?? 0, before.data[p + 1] ?? 0, before.data[p + 2] ?? 0);
    const two = luminance(after.data[q] ?? 0, after.data[q + 1] ?? 0, after.data[q + 2] ?? 0);
    if ((Math.max(one, two) + 0.05) / (Math.min(one, two) + 0.05) >= FOCUS_CONTRAST) count += 1;
  }
  return count;
}

/** One control's box on screen with room for its indicator, kept inside the viewport. */
async function shotOf(page: Page, control: JSHandle<Element | null>): Promise<Pixels> {
  const clip = await control.evaluate((element) => {
    const box = (element as HTMLElement).getBoundingClientRect();
    const x = Math.max(0, Math.floor(box.left) - 6);
    const y = Math.max(0, Math.floor(box.top) - 6);
    return {
      x,
      y,
      width: Math.max(1, Math.min(window.innerWidth - x, Math.ceil(box.width) + 12)),
      height: Math.max(1, Math.min(window.innerHeight - y, Math.ceil(box.height) + 12)),
    };
  });
  return decodePng(
    await page.screenshot({ clip, animations: 'disabled', caret: 'hide', scale: 'css' }),
  );
}

/** How the focused control looks against itself unfocused, by keyboard alone: Shift+Tab
 * moves focus to the previous stop, and Tab brings it back to the same part. */
async function renderedFocusChange(page: Page): Promise<number> {
  const control = await page.evaluateHandle(() => document.activeElement);
  try {
    const focused = await shotOf(page, control);
    await page.keyboard.press('Shift+Tab');
    const unfocused = await shotOf(page, control);
    await page.keyboard.press('Tab');
    return strongChanges(focused, unfocused);
  } finally {
    await control.dispose();
  }
}

/** Tab through the surface from `enter` until every control was reached or focus leaves
 * it. Each control's indicator is measured when Tab first reaches it; a date or time
 * field takes one Tab per part, so a control may keep focus for more than one press. A
 * control whose own styles show no indicator is measured on screen instead. */
export async function focusFindings(
  page: Page,
  surface: Locator,
  enter: () => Promise<void>,
): Promise<string[]> {
  const expected = await tabbable(surface);
  const reached: string[] = [];
  const found: string[] = [];
  await enter();
  for (let press = 0; press < expected.length * 4; press += 1) {
    await page.keyboard.press('Tab');
    const stop = await focusStop(surface);
    if (!stop) break;
    if (reached.includes(stop.control)) continue;
    reached.push(stop.control);
    let problems = stop.problems;
    if (problems.includes('shows no focus indicator')) {
      const changed = await renderedFocusChange(page);
      const styled = ['shows no focus indicator', 'does not match :focus-visible'];
      problems = problems.filter((problem) => !styled.includes(problem));
      if (changed < VISIBLE_PIXELS) problems.push(`shows no focus change (${changed} pixels)`);
    }
    found.push(...problems.map((problem) => `${stop.control} ${problem}`));
    if (expected.every((control) => reached.includes(control))) break;
  }
  const unreached = expected.filter((control) => !reached.includes(control));
  if (expected.length === 0) found.push('the surface has no keyboard-reachable control');
  return [...found, ...unreached.map((control) => `${control} is not reached by Tab`)];
}

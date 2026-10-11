// Run from the repository root. Uses an isolated browser profile and synthetic atlas data.
const { chromium } = require(process.cwd() + '/frontend/node_modules/@playwright/test');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { readFileSync } = require('node:fs');
const { pathToFileURL } = require('node:url');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.DOCSURI_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const page = await browser.newPage();
  const errors = [], requests = [];
  const contrasts = [];
  let renders = 0, recoveryRenders = 0;
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (/^https?:/.test(request.url())) requests.push(request.url()); });
  const screen = async id => { await page.selectOption('#screen-select', id); };
  const state = async id => { await page.selectOption('#state-select', id); };
  const fits = async () => assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Page overflow');
  try {
    await page.goto(pathToFileURL(path.join(__dirname, 'index.html')).href);
    const ids = await page.locator('#screen-select option').evaluateAll(nodes => nodes.map(node => node.value));
    assert.equal(ids.length, 18);
    for (const width of [1440, 1024, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const theme of ['light', 'dark']) {
        await page.selectOption('#theme-select', theme);
        for (const id of ids) {
          await screen(id); await fits();
          const unnamed = await page.locator('button,input,select,textarea').evaluateAll(nodes => nodes.filter(node => node.getClientRects().length && !node.textContent.trim() && !node.getAttribute('aria-label') && !node.getAttribute('aria-labelledby') && !node.labels?.length).map(node => node.outerHTML));
          assert.deepEqual(unnamed, [], id + ' unnamed controls');
          renders++;
        }
        await screen('M03');
        await page.fill('#research-query', 'retained search context');
        await page.locator('.filterbar select').first().selectOption({ index: 1 });
        for (const mode of ['loading', 'empty', 'error']) {
          await state(mode); await fits();
          assert.equal(await page.inputValue('#research-query'), 'retained search context');
          assert.equal(await page.locator('.filterbar select').first().inputValue(), '키워드 검색');
          assert.equal(await page.locator('#search-results .state-panel').count(), 1);
          assert.equal(await page.locator('#search-results [data-local="edit-query"]').count(), 1);
          await page.locator('#search-results [data-local="edit-query"]').click();
          assert(await page.locator('#research-query').evaluate(node => node === document.activeElement));
          recoveryRenders++;
        }
      }
    }
    await page.setViewportSize({ width: 390, height: 900 });
    for (const id of ['M08', 'M09']) {
      await screen(id);
      for (const mode of ['loading', 'error', 'interrupted', 'conflict', 'recovered']) {
        await state(mode); await fits();
        assert((await page.locator('.draft-helper').innerText()).includes('10:24'));
        if (mode !== 'recovered') {
          assert((await page.locator('.draft-helper').innerText()).includes('현재 변경 내용은 포함되지'));
          assert(!(await page.locator('.draft-status').innerText()).includes('✓ 저장됨'));
        }
      }
      await state('normal');
      await page.locator('textarea').fill('Edited unsaved draft');
      assert((await page.locator('.draft-status').innerText()).includes('저장되지'));
      if (id === 'M09') assert.equal(await page.locator('[data-demo="분석 시작"]').innerText(), '분석 시작');
      await state('unauthorized'); assert.equal(await page.locator('#content').innerText(), '');
    }
    await screen('M03'); await page.fill('#research-query', 'context survives return');
    await page.locator('.paper-row [data-screen="M04"]').nth(1).click();
    assert((await page.locator('#subtitle').innerText()).includes('2005.11401v4'));
    await page.locator('.context-return a').click();
    assert.equal(await page.inputValue('#research-query'), 'context survives return');
    await screen('M08'); await page.locator('[data-paper="P1"]').click();
    assert((await page.locator('#subtitle').innerText()).includes('1706.03762v7'));
    await screen('M03'); await page.locator('[data-demo="검색 저장"]').click();
    assert(await page.locator('#dialog-close').evaluate(node => node === document.activeElement));
    await page.keyboard.press('Shift+Tab');
    assert(await page.locator('#dialog-confirm').evaluate(node => node === document.activeElement));
    await page.keyboard.press('Tab');
    assert(await page.locator('#dialog-close').evaluate(node => node === document.activeElement));
    await page.keyboard.press('Escape');
    assert(await page.locator('[data-demo="검색 저장"]').evaluate(node => node === document.activeElement));
    await page.locator('#mobile-menu').click(); await page.keyboard.press('Escape');
    assert(await page.locator('#mobile-menu').evaluate(node => node === document.activeElement));
    await page.selectOption('#theme-select', 'system');
    for (const colorScheme of ['dark', 'light']) {
      await page.emulateMedia({ colorScheme });
      await page.waitForFunction(value => document.documentElement.dataset.theme === value, colorScheme);
    }
    for (const theme of ['light', 'dark']) {
      await page.selectOption('#theme-select', theme);
      const values = await page.evaluate(() => {
        const style = getComputedStyle(document.documentElement);
        return Object.fromEntries(['canvas','surface','text','muted','accent','accent-text','accent-soft','on-accent','control-border','danger','danger-bg','warning','warning-bg'].map(key => [key, style.getPropertyValue('--' + key).trim()]));
      });
      const luminance = hex => {
        const rgb = hex.slice(1).match(/../g).map(part => parseInt(part, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
        return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
      };
      for (const [fg,bg,target] of [['text','canvas',4.5],['text','surface',4.5],['muted','surface',4.5],['accent-text','surface',4.5],['accent-text','accent-soft',4.5],['on-accent','accent',4.5],['danger','danger-bg',4.5],['warning','warning-bg',4.5],...['canvas','surface','accent-soft','danger-bg','warning-bg'].map(bg => ['control-border',bg,3])]) {
        const a = luminance(values[fg]), b = luminance(values[bg]);
        const ratio = (Math.max(a,b) + .05) / (Math.min(a,b) + .05);
        assert(ratio >= target, `${theme} ${fg}/${bg}: ${ratio} < ${target}`);
        contrasts.push({ theme, fg, bg, ratio: +ratio.toFixed(3), target });
      }
    }
    await page.reload();
    for (const [id, mode, theme, width, name] of [
      ['M03', 'normal', 'light', 1440, 'search-desktop'],
      ['M03', 'error', 'light', 1440, 'search-recovery-desktop'],
      ['M04', 'normal', 'dark', 1440, 'reader-dark-desktop'],
      ['M08', 'normal', 'light', 390, 'research-phone'],
      ['M08', 'conflict', 'light', 390, 'draft-conflict-phone']
    ]) {
      await page.setViewportSize({ width, height: 1000 }); await page.selectOption('#theme-select', theme);
      await screen(id); await state(mode); await fits();
      await page.evaluate(() => document.activeElement.blur());
      await page.screenshot({ path: path.join(__dirname, 'previews', name + '.png'), fullPage: true });
    }
    assert.deepEqual(errors, []); assert.deepEqual(requests, []);
    const sha256 = createHash('sha256').update(readFileSync(path.join(__dirname, 'index.html'))).digest('hex');
    console.log(JSON.stringify({ normalRenders: renders, searchRecoveryRenders: recoveryRenders, draftStateChecks: 10, keyboardAndContextChecks: 'passed', browser: browser.version(), errors, networkRequests: requests, contrasts, sha256 }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

const fs = require('fs');
const path = require('path');

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (_) {
  ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright'));
}

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'rank-reading-20260829');
fs.mkdirSync(output, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function pageErrors(page) {
  const errors = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  return errors;
}

async function fit(page) {
  return page.evaluate(() => ({
    width: innerWidth,
    height: innerHeight,
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    scrollHeight: document.documentElement.scrollHeight,
  }));
}

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const report = { growth: {}, reading: {} };

  for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    const errors = await pageErrors(page);
    await page.goto(`${baseUrl}/growth`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.rank-ladder__button');
    assert(await page.locator('.rank-ladder__button').count() === 10, '段位长卷不是十个段位点');

    await page.locator('.rank-ladder__button[data-rank="5"]').hover();
    await page.waitForFunction(() => document.getElementById('g-selected-name')?.textContent === '解元');
    assert(await page.locator('#g-rank-tooltip').isVisible(), '桌面悬停没有显示段位简要浮层');

    await page.locator('.rank-ladder__button[data-rank="7"]').click();
    await page.mouse.move(10, 10);
    assert((await page.locator('#g-selected-name').textContent()).trim() === '进士', '点击后没有固定所选段位档案');

    const current = page.locator('.rank-ladder__step--current');
    await current.focus();
    await page.keyboard.press('ArrowRight');
    const focusedRank = await page.locator(':focus').getAttribute('data-rank');
    assert(Boolean(focusedRank), '方向键没有把焦点移动到相邻段位');
    await page.keyboard.press('Enter');
    await page.keyboard.press('Escape');
    assert(await page.locator('.rank-ladder__step--current').getAttribute('aria-selected') === 'true', 'Esc 没有返回当前段位');

    const metrics = await fit(page);
    assert(metrics.overflowX <= 1, `${viewport.width}px 成长页横向溢出 ${metrics.overflowX}px`);
    report.growth[viewport.width] = { ...metrics, errors };
    await page.screenshot({ path: path.join(output, `growth-${viewport.width}.png`), fullPage: false });
    assert(errors.length === 0, `成长页控制台错误：${errors.join(' | ')}`);
    await context.close();
  }

  for (const viewport of [{ width: 390, height: 844 }, { width: 360, height: 800 }]) {
    const context = await browser.newContext({ viewport, isMobile: true, hasTouch: true });
    const page = await context.newPage();
    const errors = await pageErrors(page);
    await page.goto(`${baseUrl}/growth`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.rank-ladder__button');
    await page.locator('.rank-ladder__button[data-rank="3"]').tap();
    const sheet = page.locator('#g-rank-dossier');
    assert(await sheet.isVisible(), '手机点击段位没有打开详情层');
    const box = await sheet.boundingBox();
    assert(box && box.height <= viewport.height * 0.76, '手机段位详情层超过视口 75%');
    await page.locator('#g-rank-dossier-close').tap();
    assert(!(await sheet.isVisible()), '手机段位详情层无法关闭');
    const metrics = await fit(page);
    assert(metrics.overflowX <= 1, `${viewport.width}px 成长页横向溢出 ${metrics.overflowX}px`);
    report.growth[viewport.width] = { ...metrics, errors, sheetHeight: Math.round(box.height) };
    await page.screenshot({ path: path.join(output, `growth-${viewport.width}.png`), fullPage: false });
    assert(errors.length === 0, `成长页手机控制台错误：${errors.join(' | ')}`);
    await context.close();
  }

  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport, isMobile: viewport.width < 600, hasTouch: viewport.width < 600 });
    const page = await context.newPage();
    const errors = await pageErrors(page);
    await page.goto(`${baseUrl}/reading`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.reading-task');
    const topics = await page.locator('#topic-tags button').allTextContents();
    assert(topics.length === 7, `阅读分类应为全部加六主题，实际 ${topics.length}`);
    assert(new Set(topics).size === topics.length, '阅读分类出现重复主题');
    assert(topics.filter(item => item.trim() === '教育').length === 1, '阅读分类仍有两个教育');
    const ready = Number((await page.locator('#reading-inventory-ready').textContent()).trim());
    assert(Number.isFinite(ready) && ready >= 6, '库存就绪数量没有正确显示');
    const metrics = await fit(page);
    assert(metrics.overflowX <= 1, `${viewport.width}px 阅读页横向溢出 ${metrics.overflowX}px`);
    report.reading[viewport.width] = { ...metrics, topics, ready, errors };
    await page.screenshot({ path: path.join(output, `reading-${viewport.width}.png`), fullPage: false });
    assert(errors.length === 0, `阅读页控制台错误：${errors.join(' | ')}`);
    await context.close();
  }

  fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});

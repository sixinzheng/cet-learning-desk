const fs = require('fs');
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); }
catch (_) { ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'reading-writing-layout');
const viewports = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'desktop-compact', width: 1366, height: 768 },
  { name: 'tablet', width: 1024, height: 768 },
  { name: 'mobile', width: 390, height: 844 },
  { name: 'mobile-small', width: 360, height: 800 },
];

function assert(value, message) {
  if (!value) throw new Error(message);
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const report = {};

  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport, isMobile: viewport.width < 768, hasTouch: viewport.width < 768 });
    const page = await context.newPage();
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));

    await page.goto(`${baseUrl}/reading`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.reading-task', { timeout: 8000 });
    const reading = await page.evaluate(() => {
      const disclosure = document.getElementById('reading-settings-disclosure');
      const body = document.getElementById('reading-settings-body');
      const sidebar = document.querySelector('.reading-settings');
      const bodyRect = body.getBoundingClientRect();
      const sidebarRect = sidebar.getBoundingClientRect();
      return {
        disclosureOpen: disclosure.open,
        settingsVisible: getComputedStyle(body).display !== 'none' && bodyRect.height > 0,
        settingsHeight: Math.round(bodyRect.height),
        sidebarWidth: Math.round(sidebarRect.width),
        overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      };
    });

    if (viewport.width < 768) {
      assert(!reading.disclosureOpen && !reading.settingsVisible, `${viewport.name}: 阅读设置应默认收起`);
      const before = Number((await page.locator('#reading-font-size').textContent()).replace('px', ''));
      const beforeComputed = await page.locator('#article-text').evaluate(element => parseFloat(getComputedStyle(element).fontSize));
      await page.locator('#reading-font-up').click();
      const after = Number((await page.locator('#reading-font-size').textContent()).replace('px', ''));
      const afterComputed = await page.locator('#article-text').evaluate(element => parseFloat(getComputedStyle(element).fontSize));
      await page.locator('#reading-font-down').click();
      const restored = Number((await page.locator('#reading-font-size').textContent()).replace('px', ''));
      reading.fontCycle = { before, beforeComputed, after, afterComputed, restored };
      assert(after === before + 1 && afterComputed === beforeComputed + 1, `${viewport.name}: 字号放大未改变正文`);
      assert(restored === before, `${viewport.name}: 字号缩小未恢复正文`);
    } else {
      assert(reading.disclosureOpen && reading.settingsVisible && reading.settingsHeight > 240, `${viewport.name}: 阅读侧栏未显示内容`);
    }
    assert(!reading.overflowX, `${viewport.name}: 阅读页出现横向溢出`);
    await page.screenshot({ path: path.join(output, `reading-${viewport.name}.png`), fullPage: false });

    await page.goto(`${baseUrl}/writing`, { waitUntil: 'domcontentloaded' });
    const writing = await page.evaluate(() => {
      const rect = selector => {
        const value = document.querySelector(selector)?.getBoundingClientRect();
        return value ? { x: Math.round(value.x), y: Math.round(value.y), width: Math.round(value.width), height: Math.round(value.height), right: Math.round(value.right) } : null;
      };
      return {
        editor: rect('.writing-editor'),
        result: rect('.writing-result-stage'),
        insight: rect('.writing-workbench .focus-insight'),
        cameraHidden: getComputedStyle(document.getElementById('essay-camera')).position === 'absolute' && document.getElementById('essay-camera').getBoundingClientRect().width <= 1,
        imageHidden: getComputedStyle(document.getElementById('essay-image')).position === 'absolute' && document.getElementById('essay-image').getBoundingClientRect().width <= 1,
        uploadLabels: [...document.querySelectorAll('.writing-ocr__actions label')].map(label => ({ text: label.textContent.trim(), width: Math.round(label.getBoundingClientRect().width), height: Math.round(label.getBoundingClientRect().height) })),
        overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        clientWidth: document.documentElement.clientWidth,
      };
    });
    assert(writing.cameraHidden && writing.imageHidden, `${viewport.name}: 原生文件输入未隐藏`);
    assert(writing.uploadLabels.length === 2 && writing.uploadLabels.every(item => item.width >= 44 && item.height >= 44), `${viewport.name}: 图片识别操作尺寸异常`);
    assert(!writing.overflowX, `${viewport.name}: 写作页出现横向溢出`);
    assert(writing.editor.right <= writing.clientWidth + 1 && writing.result.right <= writing.clientWidth + 1 && writing.insight.right <= writing.clientWidth + 1, `${viewport.name}: 写作区域被截断`);
    if (viewport.width >= 1200) {
      assert(writing.editor.width > writing.result.width && writing.result.width > writing.insight.width, `${viewport.name}: 桌面三栏主次顺序不清`);
      assert(Math.abs(writing.editor.y - writing.result.y) <= 1 && Math.abs(writing.result.y - writing.insight.y) <= 1, `${viewport.name}: 桌面三栏顶部未对齐`);
    } else if (viewport.width >= 768) {
      assert(writing.insight.y >= writing.editor.y + writing.editor.height - 1, `${viewport.name}: 平板说明区未落到主任务下方`);
    }
    report[viewport.name] = { reading, writing, errors };
    assert(errors.length === 0, `${viewport.name}: 页面脚本报错 ${errors.join(' | ')}`);
    await page.screenshot({ path: path.join(output, `writing-${viewport.name}.png`), fullPage: false });
    await context.close();
  }

  await browser.close();
  fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
})().catch(error => { console.error(error); process.exit(1); });

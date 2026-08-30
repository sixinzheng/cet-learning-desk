const fs = require('fs');
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); }
catch (_) { ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'v3-mobile');
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const report = {};
  for (const width of [390, 360]) {
    const context = await browser.newContext({ viewport: { width, height: width === 390 ? 844 : 800 } });
    const page = await context.newPage();
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));

    await page.goto(`${baseUrl}/reading`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.reading-task');
    const disclosure = page.locator('#reading-settings-disclosure');
    const initiallyClosed = !(await disclosure.getAttribute('open'));
    await page.locator('#reading-settings-toggle').click();
    await page.waitForTimeout(150);
    const opened = await disclosure.getAttribute('open') !== null;
    const expanded = await page.locator('#reading-settings-toggle').getAttribute('aria-expanded');
    const readingOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

    await page.goto(`${baseUrl}/writing`, { waitUntil: 'domcontentloaded' });
    const camera = await page.locator('#essay-camera').getAttribute('capture');
    const accept = await page.locator('#essay-image').getAttribute('accept');
    const writingOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

    await page.goto(`${baseUrl}/growth`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1700);
    const growthText = await page.locator('body').innerText();
    const growthOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

    report[width] = {
      initiallyClosed, opened, expanded,
      camera, accept,
      sixDimensionCopy: growthText.includes('六维'),
      noEightDimensionCopy: !growthText.includes('八维'),
      readingOverflow, writingOverflow, growthOverflow,
      errors,
    };
    await page.screenshot({ path: path.join(output, `writing-${width}.png`), fullPage: false });
    await context.close();
  }

  const api = await fetch(`${baseUrl}/api/level/detail`).then(response => response.json());
  report.levelApi = {
    algorithm: api.algorithm_version,
    dimensions: (api.dimensions || []).map(item => item.key),
    thresholdCount: Object.keys(api.rank_thresholds || {}).length,
    referenceAnchor: api.reference_anchor,
  };
  await browser.close();
  fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  const failed = Object.values(report).some(item => item && item.errors?.length) ||
    [390, 360].some(width => !report[width].initiallyClosed || !report[width].opened || report[width].expanded !== 'true' ||
      !report[width].sixDimensionCopy || !report[width].noEightDimensionCopy ||
      report[width].readingOverflow > 1 || report[width].writingOverflow > 1 || report[width].growthOverflow > 1) ||
    report.levelApi.algorithm !== '3.0' || report.levelApi.dimensions.length !== 6;
  console.log(JSON.stringify(report, null, 2));
  process.exit(failed ? 1 : 0);
})().catch(error => { console.error(error); process.exit(1); });

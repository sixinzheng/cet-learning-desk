const fs = require('fs');
const path = require('path');

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (_) {
  ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright'));
}

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = path.join(process.cwd(), 'docs', 'images');
const captures = [
  { route: '/', name: 'home-desktop.png', wait: 1200 },
  { route: '/study', name: 'study-desktop.png', wait: 900 },
  { route: '/reading', name: 'reading-desktop.png', wait: 1200, selector: '.reading-task' },
  { route: '/growth', name: 'growth-desktop.png', wait: 2200 },
];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await context.addInitScript(() => {
    localStorage.setItem('cet-onboarding-v1', JSON.stringify({
      version: 2,
      welcome_seen: true,
      status: 'completed',
      saved_at: new Date().toISOString(),
    }));
  });
  const page = await context.newPage();

  for (const capture of captures) {
    const response = await page.goto(`${baseUrl}${capture.route}`, { waitUntil: 'domcontentloaded' });
    if (!response || response.status() !== 200) throw new Error(`${capture.route} returned ${response?.status()}`);
    if (capture.selector) await page.waitForSelector(capture.selector, { timeout: 10000 });
    await page.waitForTimeout(capture.wait);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, capture.name), type: 'png', fullPage: false, scale: 'css' });
    console.log(`captured ${capture.route} -> docs/images/${capture.name}`);
  }

  await context.close();
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});

const fs = require('fs');
const path = require('path');

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (_) {
  ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright'));
}

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5412';
const artifactDir = path.join(__dirname, '..', 'browser-artifacts', 'rank-portraits-20260829-final');
fs.mkdirSync(artifactDir, { recursive: true });

async function inspect(page, name, url, viewport, selector) {
  await page.setViewportSize(viewport);
  await page.goto(`${baseUrl}${url}`, { waitUntil: 'networkidle' });
  await page.waitForSelector(selector, { state: 'visible' });
  await page.waitForFunction((target) => {
    const image = document.querySelector(target);
    return image && image.complete && image.naturalWidth > 0;
  }, selector);

  const result = await page.evaluate((target) => {
    const image = document.querySelector(target);
    const rect = image.getBoundingClientRect();
    const root = document.documentElement;
    return {
      src: image.getAttribute('src'),
      alt: image.getAttribute('alt'),
      naturalWidth: image.naturalWidth,
      naturalHeight: image.naturalHeight,
      renderedWidth: Math.round(rect.width),
      renderedHeight: Math.round(rect.height),
      overflowX: root.scrollWidth - root.clientWidth,
    };
  }, selector);

  if (!result.src || result.naturalWidth < 100 || result.naturalHeight < 100) {
    throw new Error(`${name}: rank portrait did not load`);
  }
  if (result.overflowX > 1) {
    throw new Error(`${name}: horizontal overflow ${result.overflowX}px`);
  }

  await page.screenshot({
    path: path.join(artifactDir, `${name}.png`),
    fullPage: true,
  });
  return result;
}

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(error.message));

  const results = {};
  results.homeDesktop = await inspect(page, 'home-desktop', '/', { width: 1440, height: 900 }, '#rank-portrait-home');
  results.homeMobile = await inspect(page, 'home-mobile', '/', { width: 390, height: 844 }, '#rank-portrait-home');
  results.growthDesktop = await inspect(page, 'growth-desktop', '/growth', { width: 1440, height: 900 }, '#g-rank-portrait');
  results.growthMobile = await inspect(page, 'growth-mobile', '/growth', { width: 390, height: 844 }, '#g-rank-portrait');

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${baseUrl}/growth`, { waitUntil: 'networkidle' });
  const switched = await page.evaluate(async () => {
    const image = document.getElementById('g-rank-portrait');
    setRankPortrait(image, 10);
    if (!image.complete) await new Promise((resolve) => image.addEventListener('load', resolve, { once: true }));
    return { src: image.getAttribute('src'), alt: image.getAttribute('alt'), width: image.naturalWidth };
  });
  if (!switched.src.includes('rank-10-zhuangyuan') || switched.width < 100) {
    throw new Error('rank 10 portrait switching failed');
  }
  await page.screenshot({ path: path.join(artifactDir, 'growth-rank10-preview.png'), fullPage: false });

  if (consoleErrors.length) {
    throw new Error(`browser console errors: ${consoleErrors.join(' | ')}`);
  }

  console.log(JSON.stringify({ artifactDir, results, switched }, null, 2));
  await browser.close();
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});

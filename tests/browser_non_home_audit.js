const fs = require('fs');
const path = require('path');
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (_) {
  ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright'));
}

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'non-home-20260828');
const routes = [
  '/learn', '/study', '/review', '/reading', '/listening', '/writing', '/cloze',
  '/control', '/notes', '/growth', '/profile', '/export', '/diagnostic',
];
const viewports = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'desktop-compact', width: 1366, height: 768 },
  { name: 'tablet', width: 1024, height: 768 },
  { name: 'mobile', width: 390, height: 844 },
  { name: 'mobile-small', width: 360, height: 800 },
];

function screenshotName(route, viewport) {
  return `${route.slice(1)}-${viewport}.png`;
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const results = [];

  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport });
    for (const route of routes) {
      const page = await context.newPage();
      const errors = [];
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      page.on('pageerror', error => errors.push(error.message));
      const response = await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(route === '/growth' ? 2400 : 900);

      const metrics = await page.evaluate(({ route, viewportName }) => {
        const visible = element => {
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
        };
        const nav = document.querySelector('.mobile-nav');
        const navRect = nav && visible(nav) ? nav.getBoundingClientRect() : null;
        const navItems = [...document.querySelectorAll('.mobile-nav__item')].filter(visible);
        const h1 = document.querySelector('h1');
        const h1Rect = h1?.getBoundingClientRect();
        const lineHeight = h1 ? parseFloat(getComputedStyle(h1).lineHeight) : 0;
        const coreControls = [...document.querySelectorAll(
          '.focus-stage button, .focus-stage input, .focus-stage textarea, .cloze-workbench button, .cloze-workbench input, .writing-editor button, .writing-editor textarea, .learn-workspaces a, .note-editor button, .note-editor textarea'
        )].filter(visible);
        const tooSmall = coreControls.filter(element => {
          const rect = element.getBoundingClientRect();
          return rect.width < 44 || rect.height < 44;
        }).map(element => element.id || element.textContent.trim().slice(0, 24) || element.tagName);
        const main = document.querySelector('.focus-stage, .study-main, .review-main, .cloze-passage, .writing-editor, .learn-workspaces, .note-editor');
        const context = document.querySelector('.focus-context, .study-sidebar, .review-sidebar, .cloze-side');
        const mainRect = main?.getBoundingClientRect();
        const contextRect = context?.getBoundingClientRect();
        const manager = document.getElementById('note-manager-drawer');
        const historyList = document.getElementById('note-history-list');
        return {
          route,
          viewport: viewportName,
          title: document.title,
          h1: h1?.textContent.trim() || '',
          h1Lines: h1Rect && lineHeight ? Math.round(h1Rect.height / lineHeight) : 0,
          overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          navVisible: Boolean(navRect),
          navRows: navItems.length ? new Set(navItems.map(item => Math.round(item.getBoundingClientRect().top))).size : 0,
          mainBeforeContextOnMobile: viewportName.startsWith('mobile') && mainRect && contextRect ? mainRect.top <= contextRect.top : true,
          navDoesNotCoverInitialMain: !navRect || !mainRect || mainRect.top < navRect.top,
          noteManagerInternallyScrollable: route !== '/notes' || viewportName.startsWith('mobile') || !manager || (historyList && getComputedStyle(historyList).overflowY === 'auto'),
          tooSmall,
          articleLoaded: route !== '/reading' || Boolean(document.querySelector('.reading-task')),
          readingStateCount: route !== '/reading' ? 0 : Number(Boolean(window._ra)),
          listeningReady: route !== '/listening' || Boolean(document.querySelector('#listen-card:not([hidden])')),
          clozeReady: route !== '/cloze' || Boolean(document.querySelector('#cloze-content input')),
        };
      }, { route, viewportName: viewport.name });

      if (viewport.name === 'desktop' || viewport.name === 'mobile') {
        await page.screenshot({ path: path.join(output, screenshotName(route, viewport.name)), fullPage: false });
      }
      results.push({ status: response?.status(), errors, ...metrics });
      await page.close();
    }
    await context.close();
  }

  const interactionContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const interactionPage = await interactionContext.newPage();
  const interactions = {};

  await interactionPage.goto(`${baseUrl}/listening`, { waitUntil: 'domcontentloaded' });
  await interactionPage.waitForSelector('#listen-options .choice-button', { timeout: 8000 });
  await interactionPage.locator('#listen-options .choice-button').first().click();
  interactions.listeningNextEnabled = await interactionPage.locator('#listen-next').isEnabled();
  const beforeIndex = await interactionPage.locator('#listen-index').textContent();
  await interactionPage.keyboard.press('Enter');
  await interactionPage.waitForTimeout(250);
  const afterIndex = await interactionPage.locator('#listen-index').textContent();
  interactions.listeningEnterAdvanced = beforeIndex !== afterIndex || (await interactionPage.locator('#listen-next').textContent()).includes('完成');

  await interactionPage.goto(`${baseUrl}/reading`, { waitUntil: 'domcontentloaded' });
  await interactionPage.waitForSelector('.reading-task', { timeout: 8000 });
  interactions.readingAutoLoaded = true;
  interactions.readingSingleState = await interactionPage.evaluate(() => Boolean(window._ra) && document.querySelectorAll('[x-data*="readingApp"]').length === 1);

  await interactionPage.goto(`${baseUrl}/notes`, { waitUntil: 'domcontentloaded' });
  interactions.notesPageLoaded = await interactionPage.locator('#note-content').isVisible();
  interactions.notesHistoryLoaded = await interactionPage.locator('#note-history-list').isVisible();

  await interactionContext.close();
  await browser.close();

  const failures = results.filter(item =>
    item.status !== 200 || item.errors.length || item.overflowX || item.tooSmall.length ||
    (item.viewport.startsWith('mobile') && (!item.navVisible || item.navRows !== 1 || item.h1Lines > 2 || !item.navDoesNotCoverInitialMain)) ||
    !item.noteManagerInternallyScrollable || !item.articleLoaded || item.readingStateCount > 1 || !item.listeningReady || !item.clozeReady
  );
  const interactionFailures = Object.entries(interactions).filter(([, passed]) => !passed);
  const report = { checked: results.length, failures, interactions, interactionFailures };
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({ results, ...report }, null, 2));
  console.log(JSON.stringify(report, null, 2));
  process.exit(failures.length || interactionFailures.length ? 1 : 0);
})().catch(error => {
  console.error(error);
  process.exit(1);
});

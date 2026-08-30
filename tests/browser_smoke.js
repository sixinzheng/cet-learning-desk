const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts');
  const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const routeFilter = (process.env.ROUTES || '').split(',').map(value => value.trim()).filter(Boolean);
  const pages = ['/', '/learn', '/growth', '/profile', '/study', '/review', '/reading', '/listening', '/grammar', '/writing', '/notes', '/export']
    .filter(route => !routeFilter.length || routeFilter.includes(route));
  const viewportFilter = (process.env.VIEWPORTS || '').split(',').map(value => value.trim()).filter(Boolean);
  const viewports = [
    { name: 'desktop', width: 1440, height: 900 },
    { name: 'desktop-compact', width: 1366, height: 768 },
    { name: 'tablet', width: 1024, height: 768 },
    { name: 'mobile', width: 390, height: 844 },
    { name: 'mobile-small', width: 360, height: 800 }
  ].filter(viewport => !viewportFilter.length || viewportFilter.includes(viewport.name));
  const results = [];
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport });
    for (const route of pages) {
      const page = await context.newPage();
      const errors = [];
      page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
      page.on('pageerror', error => errors.push(error.message));
      const response = await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(900);
      const metrics = await page.evaluate(() => {
        const navItems = [...document.querySelectorAll('.mobile-nav__item')].filter(el => getComputedStyle(el).display !== 'none');
        const navRows = new Set(navItems.map(el => Math.round(el.getBoundingClientRect().top))).size;
        const task = document.querySelector('.vocab-command')?.getBoundingClientRect();
        const chat = document.querySelector('.ai-quick-chat')?.getBoundingClientRect();
        const rank = document.querySelector('.rank-card--summary')?.getBoundingClientRect();
        const intro = document.querySelector('.home-intro--compact');
        const workspace = document.querySelector('.vocab-command__workspace')?.getBoundingClientRect();
        const cover = document.querySelector('.vocab-command .task-book-cover')?.getBoundingClientRect();
        const progress = document.querySelector('.daily-progress-pair')?.getBoundingClientRect();
        const actions = document.querySelector('.vocab-command .primary-actions')?.getBoundingClientRect();
        const actionButtons = [...document.querySelectorAll('.vocab-command .primary-actions .btn')].map(item => item.getBoundingClientRect());
        const mobileNav = document.querySelector('.mobile-nav')?.getBoundingClientRect();
        const studyMain = document.querySelector('.main-grid > main')?.getBoundingClientRect();
        const studyAside = document.querySelector('.main-grid > aside')?.getBoundingClientRect();
        return {
          title: document.title,
          overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          h1: document.querySelector('h1')?.textContent.trim() || '',
          navVisible: [...document.querySelectorAll('.mobile-nav')].some(el => getComputedStyle(el).display !== 'none'),
          navRows,
          homeTaskBeforeChat: !task || !chat || task.top < chat.top,
          homeChatBeforeRank: !chat || !rank || chat.top < rank.top,
          homeBottomAligned: !chat || !rank || Math.abs(chat.bottom - rank.bottom) <= 1,
          homeRankAttached: !task || !rank || Math.abs(task.bottom - rank.top) <= 1,
          coverProgressBottomAligned: !cover || !progress || Math.abs(cover.bottom - progress.bottom) <= 1,
          tabletAuxAligned: !chat || !rank || Math.abs(chat.bottom - rank.bottom) <= 1,
          homeIntroHidden: !task || !intro || getComputedStyle(intro).display === 'none',
          homeActionsSameRow: !actions || actionButtons.length < 2 || Math.abs(actionButtons[0].top - actionButtons[1].top) <= 1,
          homeActionsInFirstView: !actions || actions.bottom <= window.innerHeight - (mobileNav?.height || 0),
          homeCoverRatio: !cover || !workspace ? 0 : cover.width / workspace.width,
          studyMainBeforeAside: !studyMain || !studyAside || studyMain.top < studyAside.top,
        };
      });
      const slug = route === '/' ? 'home' : route.slice(1);
      if (['home', 'growth', 'profile', 'study', 'grammar', 'notes'].includes(slug)) {
        await page.screenshot({ path: path.join(output, `${slug}-${viewport.name}.png`), fullPage: true });
      }
      results.push({ route, viewport: viewport.name, status: response?.status(), ...metrics, errors });
      await page.close();
    }
    await context.close();
  }
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(results, null, 2));
  const failures = results.filter(item => item.status !== 200 || item.overflow || item.errors.length
    || (['desktop','desktop-compact'].includes(item.viewport) && (!item.homeBottomAligned || !item.homeRankAttached || !item.coverProgressBottomAligned))
    || (item.viewport === 'tablet' && !item.tabletAuxAligned)
    || (item.viewport.startsWith('mobile') && (!item.navVisible || item.navRows !== 1 || !item.homeTaskBeforeChat || !item.homeChatBeforeRank || !item.homeIntroHidden || !item.homeActionsSameRow || !item.homeActionsInFirstView || item.homeCoverRatio > .35 || !item.studyMainBeforeAside)));
  console.log(JSON.stringify({ checked: results.length, failures }, null, 2));
  await Promise.race([browser.close(), new Promise(resolve => setTimeout(resolve, 5000))]);
  process.exit(failures.length ? 1 : 0);
})().catch(error => { console.error(error); process.exit(1); });

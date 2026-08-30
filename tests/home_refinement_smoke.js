const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const output = process.argv[2] || path.join(process.cwd(), 'home-refinement-artifacts');
  const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const viewports = [
    { name: 'desktop', width: 1440, height: 900 },
    { name: 'desktop-compact', width: 1366, height: 768 },
    { name: 'tablet', width: 1024, height: 768 },
    { name: 'mobile', width: 390, height: 844 },
    { name: 'mobile-small', width: 360, height: 800 }
  ];
  const results = [];
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    const errors = [];
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
    page.on('pageerror', error => errors.push(error.message));
    const response = await page.goto(`${baseUrl}/`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    await page.locator('#rank-ladder button[data-rank="5"]').dispatchEvent('mouseenter');
    const metrics = await page.evaluate(() => {
      const left = document.querySelector('.home-rail--left').getBoundingClientRect();
      const center = document.querySelector('.home-center').getBoundingClientRect();
      const right = document.querySelector('.home-rail--right').getBoundingClientRect();
      return {
        overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        rankDetail: document.querySelector('#rank-hover-detail').textContent.trim(),
        coverTitle: document.querySelector('#task-book-title').textContent.trim(),
        taskAdvice: document.querySelector('#task-advice-counts')?.textContent.trim() || '',
        achievementSentence: document.querySelector('#achievement-sentence')?.textContent.trim() || '',
        achievementMilestone: document.querySelector('#achievement-milestone-copy')?.textContent.trim() || '',
        cellWidth: document.querySelector('#calendar-heatmap canvas')?.width || 0,
        columnBottomDelta: Math.max(left.bottom, center.bottom, right.bottom) - Math.min(left.bottom, center.bottom, right.bottom)
      };
    });
    if (['desktop', 'mobile'].includes(viewport.name)) await page.screenshot({ path: path.join(output, `home-${viewport.name}.png`), fullPage: true });
    results.push({ viewport: viewport.name, status: response?.status(), errors, ...metrics });
    await context.close();
  }
  await browser.close();
  const failures = results.filter(item => item.status !== 200 || item.overflow || item.errors.length || !item.rankDetail.includes('解元') || !item.coverTitle || !item.taskAdvice.includes('建议新学') || !item.achievementSentence || !item.achievementMilestone || (item.viewport.startsWith('desktop') && item.columnBottomDelta > 2));
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(results, null, 2));
  console.log(JSON.stringify({ results, failures }, null, 2));
  process.exitCode = failures.length ? 1 : 0;
})().catch(error => { console.error(error); process.exit(1); });

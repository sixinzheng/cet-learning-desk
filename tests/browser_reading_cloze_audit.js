const fs = require('fs');
const path = require('path');
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (_) {
  ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright'));
}

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'reading-cloze-20260829');

async function installAnnotationShield(page) {
  await page.route('**/api/reading/articles/*/annotations', async route => {
    if (route.request().method() === 'GET') return route.continue();
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
}

async function dragAcross(page, first, last) {
  const from = await first.boundingBox();
  const to = await last.boundingBox();
  if (!from || !to) throw new Error('无法取得标注单词坐标');
  await page.mouse.move(from.x + 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(to.x + to.width - 2, to.y + to.height / 2, { steps: 12 });
  await page.mouse.up();
  await page.waitForTimeout(180);
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const report = {};

  const desktopContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const desktop = await desktopContext.newPage();
  await installAnnotationShield(desktop);
  const desktopErrors = [];
  desktop.on('console', message => { if (message.type() === 'error') desktopErrors.push(message.text()); });
  desktop.on('pageerror', error => desktopErrors.push(error.message));
  await desktop.goto(`${baseUrl}/reading`, { waitUntil: 'domcontentloaded' });
  await desktop.waitForSelector('.reading-task', { timeout: 8000 });

  const words = desktop.locator('.article-word-ann');
  const wordCount = await words.count();
  const lastWord = words.nth(wordCount - 1);
  report.sentenceFinalWordWrapped = wordCount > 1 && Boolean((await lastWord.getAttribute('data-word')) || '');

  await dragAcross(desktop, words.nth(0), words.nth(2));
  report.dragSelectionMarked = (await desktop.locator('.article-word-ann.mark-green,.article-word-ann.mark-both').count()) >= 2;
  await desktop.locator('.mark-btn[data-mark="erase"]').click();
  await dragAcross(desktop, words.nth(0), words.nth(2));

  await lastWord.dblclick();
  await desktop.waitForSelector('#word-modal.is-open');
  report.finalWordLookupWorks = await desktop.locator('#word-modal.is-open').isVisible();
  report.lookupHasPronunciation = await desktop.locator('#lookup-pronounce').isVisible();
  await desktop.locator('#word-modal-close').click();

  const fabTopBefore = await desktop.locator('#reading-answer-card-fab').evaluate(element => element.getBoundingClientRect().top);
  await desktop.evaluate(() => window.scrollTo(0, Math.min(document.documentElement.scrollHeight, 1000)));
  await desktop.waitForTimeout(120);
  const fabTopAfter = await desktop.locator('#reading-answer-card-fab').evaluate(element => element.getBoundingClientRect().top);
  report.answerCardButtonFixed = Math.abs(fabTopBefore - fabTopAfter) <= 1
    && await desktop.locator('#reading-answer-card-fab').evaluate(element => getComputedStyle(element).position === 'fixed');
  await desktop.locator('#reading-answer-card-fab').click();
  await desktop.waitForSelector('#answer-card-modal.is-open');
  report.answerCardIsDialog = await desktop.locator('#answer-card-modal [role="dialog"]').isVisible();
  report.answerCardContainsQuestions = (await desktop.locator('#answer-card-modal .answer-card-question').count()) > 0;
  const countBefore = await desktop.locator('#reading-answer-card-count').textContent();
  await desktop.locator('#answer-card-modal .reading-choice').first().click();
  const countAfter = await desktop.locator('#reading-answer-card-count').textContent();
  report.answerPersistsInCard = countBefore !== countAfter;
  await desktop.screenshot({ path: path.join(output, 'reading-desktop-answer-card.png'), fullPage: false });
  await desktop.locator('#answer-card-close').click();

  await desktop.evaluate(() => showToast('这是一个紧凑提示。', 'info'));
  await desktop.waitForSelector('.toast.is-visible');
  report.toastMetrics = await desktop.locator('.toast.is-visible').evaluate(element => {
    const rect = element.getBoundingClientRect();
    return { width: Math.round(rect.width), height: Math.round(rect.height) };
  });
  report.toastCompact = report.toastMetrics.height <= 80 && report.toastMetrics.width <= 320;
  report.desktopErrors = desktopErrors;

  await desktop.goto(`${baseUrl}/cloze`, { waitUntil: 'domcontentloaded' });
  await desktop.waitForSelector('.cloze-input', { timeout: 8000 });
  const clozePayload = await desktop.evaluate(async () => (await fetch('/api/practice/cloze/content')).json());
  const firstCloze = clozePayload.items?.[0] || {};
  report.clozeApiDoesNotLeakPerBlank = Array.isArray(firstCloze.blanks)
    && firstCloze.blanks.every(blank => !('base_word' in blank) && !('hint' in blank) && !('answer' in blank));
  report.clozeOnlyShowsBlanks = await desktop.evaluate(() => (
    !document.querySelector('.cloze-gap__base')
    && !document.querySelector('.cloze-gap small')
    && [...document.querySelectorAll('.cloze-input')].every(input => input.readOnly)
  ));
  report.clozeHasWordBank = (await desktop.locator('#cloze-bank .bank-chip').count()) > 0;
  const initialBlankValue = await desktop.locator('.cloze-input').first().inputValue();
  const chosenCandidate = await desktop.locator('#cloze-bank .bank-chip').first().textContent();
  await desktop.locator('.cloze-input').first().click();
  await desktop.locator('#cloze-bank .bank-chip').first().click();
  report.clozeSelectionFillsBlank = initialBlankValue === ''
    && (await desktop.locator('.cloze-input').first().inputValue()) === chosenCandidate.trim();
  await desktop.screenshot({ path: path.join(output, 'cloze-desktop.png'), fullPage: false });

  await desktop.goto(`${baseUrl}/study`, { waitUntil: 'domcontentloaded' });
  await desktop.waitForTimeout(1000);
  report.studyHasPronunciation = (await desktop.locator('.pronounce-button').count()) > 0;

  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const mobile = await mobileContext.newPage();
  await installAnnotationShield(mobile);
  const mobileErrors = [];
  mobile.on('console', message => { if (message.type() === 'error') mobileErrors.push(message.text()); });
  mobile.on('pageerror', error => mobileErrors.push(error.message));
  await mobile.goto(`${baseUrl}/reading`, { waitUntil: 'domcontentloaded' });
  await mobile.waitForSelector('.reading-task', { timeout: 8000 });
  report.mobile = await mobile.evaluate(() => {
    const article = document.getElementById('article-text').getBoundingClientRect();
    const fab = document.getElementById('reading-answer-card-fab').getBoundingClientRect();
    const nav = document.querySelector('.mobile-nav').getBoundingClientRect();
    return {
      articleTop: Math.round(article.top),
      compactBeforeArticle: article.top < 590,
      fabAboveNavigation: fab.bottom <= nav.top + 1,
      noHorizontalOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
      masteryIsProgressbar: document.querySelector('.reading-mastery-track')?.getAttribute('role') === 'progressbar',
    };
  });
  report.mobileErrors = mobileErrors;
  await mobile.screenshot({ path: path.join(output, 'reading-mobile-initial.png'), fullPage: false });

  await mobileContext.close();
  await desktopContext.close();
  await browser.close();

  const booleanFailures = Object.entries(report).filter(([, value]) => value === false).map(([key]) => key);
  const nestedFailures = Object.entries(report.mobile || {}).filter(([, value]) => value === false).map(([key]) => `mobile.${key}`);
  const errors = [...(report.desktopErrors || []), ...(report.mobileErrors || [])];
  const failures = [...booleanFailures, ...nestedFailures, ...errors.map(error => `console:${error}`)];
  const result = { ...report, failures };
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  process.exit(failures.length ? 1 : 0);
})().catch(error => {
  console.error(error);
  process.exit(1);
});

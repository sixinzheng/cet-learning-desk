const fs = require('fs');
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); }
catch (_) { ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'onboarding-support');
fs.mkdirSync(output, {recursive: true});

async function auditViewport(browser, width, height) {
    const context = await browser.newContext({viewport: {width, height}});
    const page = await context.newPage();
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));

    await page.goto(`${baseUrl}/`, {waitUntil: 'domcontentloaded'});
    await page.locator('#onboarding-overlay').waitFor({state: 'visible'});
    const first = {
        panelCount: await page.locator('[data-onboarding-panel]').count(),
        firstTitle: await page.locator('[data-onboarding-panel="0"] h2').textContent(),
        stepLabel: await page.locator('#onboarding-step-label').textContent(),
        viewportOverflow: await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth),
        dialog: await page.locator('.onboarding-dialog').boundingBox(),
    };
    await page.screenshot({path: path.join(output, `onboarding-${width}.png`), fullPage: false});

    for (let index = 0; index < 3; index += 1) await page.locator('#onboarding-next').click();
    const lastTitle = await page.locator('[data-onboarding-panel="3"] h2').textContent();
    await page.locator('#onboarding-next').click();
    await page.locator('#onboarding-overlay').waitFor({state: 'hidden'});
    const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('cet-onboarding-v1') || '{}'));
    await page.reload({waitUntil: 'domcontentloaded'});
    await page.waitForTimeout(450);
    const stayedDismissed = await page.locator('#onboarding-overlay').isHidden();

    await page.goto(`${baseUrl}/profile`, {waitUntil: 'domcontentloaded'});
    await page.locator('#open-onboarding').click();
    await page.locator('#onboarding-overlay').waitFor({state: 'visible'});
    await page.locator('#onboarding-skip').click();
    await page.locator('#support-author-button').click();
    await page.locator('#support-modal').waitFor({state: 'visible'});
    const support = {
        imageCount: await page.locator('.support-code img').count(),
        imagesLoaded: await page.locator('.support-code img').evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0)),
        modalOverflow: await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth),
    };
    await page.screenshot({path: path.join(output, `support-${width}.png`), fullPage: false});
    await page.keyboard.press('Escape');
    const supportClosed = await page.locator('#support-modal').isHidden();
    const focusReturned = await page.evaluate(() => document.activeElement?.id === 'support-author-button');
    await context.close();
    return {first, lastTitle, stored, stayedDismissed, support, supportClosed, focusReturned, errors};
}

(async () => {
    const browser = await chromium.launch({channel: 'msedge', headless: true, args: ['--disable-gpu']});
    const desktop = await auditViewport(browser, 1440, 900);
    const mobile = await auditViewport(browser, 390, 844);
    await browser.close();
    const report = {desktop, mobile};
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    const failed = [desktop, mobile].some(result =>
        result.first.panelCount !== 4 ||
        !result.first.firstTitle.includes('词汇任务') ||
        !result.lastTitle.includes('尊重你的边界') ||
        result.stored.status !== 'completed' ||
        !result.stayedDismissed ||
        result.first.viewportOverflow > 1 ||
        result.support.imageCount !== 2 ||
        !result.support.imagesLoaded ||
        result.support.modalOverflow > 1 ||
        !result.supportClosed ||
        !result.focusReturned ||
        result.errors.length
    );
    process.exit(failed ? 1 : 0);
})().catch(error => { console.error(error); process.exit(1); });

const fs = require('fs');
const path = require('path');

let chromium;
try { ({ chromium } = require('playwright')); }
catch (_) { ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'mobile-study-control-20260829');
fs.mkdirSync(output, { recursive: true });

function assert(condition, message) { if (!condition) throw new Error(message); }
function watchErrors(page) {
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));
    return errors;
}

(async () => {
    const browser = await chromium.launch({channel:'msedge', headless:true, args:['--disable-gpu']});
    const report = {desktop:{}, mobile:{}};

    const desktopContext = await browser.newContext({viewport:{width:1440,height:900}});
    const desktopPage = await desktopContext.newPage();
    await desktopPage.route('**/api/study/start-learning', route => route.fulfill({status:200, contentType:'application/json', body:'{"success":true}'}));
    await desktopPage.route('**/api/study/answer', route => route.fulfill({status:200, contentType:'application/json', body:'{"success":true}'}));
    await desktopPage.goto(`${baseUrl}/study`, {waitUntil:'networkidle'});
    await desktopPage.waitForSelector('.quiz-opt-btn:visible');
    await desktopPage.locator('.quiz-opt-btn:visible').first().click();
    await desktopPage.waitForSelector('#study-card-actions:visible');
    const desktopStudyOrder = await desktopPage.evaluate(() => {
        const action = document.getElementById('study-card-actions');
        return action.previousElementSibling?.classList.contains('study-card-sentences') && action.getBoundingClientRect().top > document.querySelector('.answer-followup').getBoundingClientRect().bottom;
    });
    assert(desktopStudyOrder, '桌面背词页原有答后操作顺序被移动端改造改变');
    await desktopPage.goto(`${baseUrl}/control`, {waitUntil:'networkidle'});
    assert(await desktopPage.locator('.control-page .page-heading').isVisible(), '桌面控制台标题被移动端规则误隐藏');
    report.desktop = {studyOrderPreserved:desktopStudyOrder, controlHeadingVisible:true};
    await desktopContext.close();

    for (const viewport of [{width:390,height:844},{width:360,height:800}]) {
        const context = await browser.newContext({viewport, isMobile:true, hasTouch:true});
        const page = await context.newPage();
        const errors = watchErrors(page);

        await page.route('**/api/study/start-learning', route => route.fulfill({
            status:200, contentType:'application/json', body:JSON.stringify({success:true}),
        }));
        await page.route('**/api/study/answer', route => route.fulfill({
            status:200, contentType:'application/json', body:JSON.stringify({success:true}),
        }));

        await page.goto(`${baseUrl}/study`, {waitUntil:'networkidle'});
        await page.waitForSelector('.quiz-opt-btn:visible');
        assert(await page.locator('.study-page .topbar-left').isHidden(), '手机背词页顶部标题说明仍可见');

        await page.locator('.quiz-opt-btn:visible').first().click();
        await page.waitForSelector('#study-card-actions:visible');
        const study = await page.evaluate(() => {
            const rect = selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height};
            };
            const nav = rect('.mobile-nav');
            return {
                overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                card: rect('.study-card-word'),
                actions: rect('#study-card-actions'),
                followup: rect('.answer-followup'),
                continueButton: rect('#study-card-continue'),
                favoriteButton: rect('#study-card-favorite'),
                nav,
            };
        });
        assert(study.overflowX <= 1, `${viewport.width}px 背词页横向溢出 ${study.overflowX}px`);
        assert(study.actions.top >= study.card.bottom - 1, '答后操作没有放在单词卡下方');
        assert(study.actions.bottom <= study.followup.top + 1, '答后操作没有放在熟悉度调整之前');
        assert(study.actions.bottom <= study.nav.top, `收藏和继续按钮没有出现在首屏可见区：${JSON.stringify(study)}`);
        assert(study.continueButton.height >= 44 && study.favoriteButton.height >= 44, '答后按钮触控区域不足 44px');
        await page.screenshot({path:path.join(output, `study-card-${viewport.width}.png`), fullPage:false});

        await page.goto(`${baseUrl}/control`, {waitUntil:'networkidle'});
        await page.waitForSelector('.control-chat');
        const control = await page.evaluate(() => {
            const box = selector => {
                const element = document.querySelector(selector);
                const r = element.getBoundingClientRect();
                return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height,display:getComputedStyle(element).display};
            };
            return {
                overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                heading: box('.control-page .page-heading'),
                header: box('.site-header'),
                workbench: box('.control-workbench'),
                chat: box('.control-chat'),
                composer: box('.control-composer'),
                nav: box('.mobile-nav'),
            };
        });
        assert(control.heading.display === 'none', '手机控制台大标题仍可见');
        assert(control.overflowX <= 1, `${viewport.width}px 控制台横向溢出 ${control.overflowX}px`);
        assert(Math.abs(control.workbench.top - control.header.bottom) <= 1, '控制台没有紧接站点顶栏');
        assert(Math.abs(control.workbench.bottom - control.nav.top) <= 2, '控制台没有填满顶栏与底部导航之间的空间');
        assert(control.composer.bottom <= control.nav.top + 1, '控制台输入区被底部导航遮挡');
        await page.screenshot({path:path.join(output, `control-${viewport.width}.png`), fullPage:false});

        assert(errors.length === 0, `${viewport.width}px 出现控制台错误：${errors.join(' | ')}`);
        report.mobile[viewport.width] = {study, control};
        await context.close();
    }

    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

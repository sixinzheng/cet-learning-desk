const fs = require('fs');
const path = require('path');
let chromium;
try { ({chromium} = require('playwright')); }
catch (_) { ({chromium} = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5411';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'sync-learn-layout');
fs.mkdirSync(output, {recursive:true});
function assert(value, message) { if (!value) throw new Error(message); }

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
  const report = {mobile:{},desktop:{}};
  for (const viewport of [{width:360,height:800},{width:390,height:844}]) {
    const context = await browser.newContext({viewport,isMobile:true,hasTouch:true});
    const page = await context.newPage();
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/study/difficulty-setting', async route => {
      if (route.request().method() === 'GET') await route.fulfill({json:{difficulty:null,label:'未设置'}});
      else await route.continue();
    });
    await page.goto(`${baseUrl}/learn`, {waitUntil:'networkidle'});
    const prompt = page.locator('#difficulty-prompt');
    assert(await prompt.isVisible(), `${viewport.width}px 未设置难度没有弹窗`);
    const buttonHeights = await page.locator('.difficulty-prompt__actions button').evaluateAll(nodes => nodes.map(node => Math.round(node.getBoundingClientRect().height)));
    assert(buttonHeights.every(value => value >= 48), `${viewport.width}px 难度弹窗触控目标不足 48px`);
    await page.locator('#difficulty-prompt-later').tap();
    assert(!(await prompt.isVisible()), `${viewport.width}px 稍后按钮未关闭弹窗`);
    await page.reload({waitUntil:'networkidle'});
    assert(await prompt.isVisible(), `${viewport.width}px 稍后后再次进入未提醒`);
    await page.locator('#difficulty-prompt-go').tap();
    await page.waitForTimeout(650);
    const target = await page.evaluate(() => ({
      top:Math.round(document.getElementById('training-difficulty').getBoundingClientRect().top),
      focused:document.activeElement === document.querySelector('input[name="training-difficulty"]'),
      overflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth,
    }));
    assert(target.top >= 55 && target.top <= 200 && target.focused, `${viewport.width}px 难度定位或焦点失败：${JSON.stringify(target)}`);
    assert(target.overflowX <= 1, `${viewport.width}px 学习页横向溢出`);

    await page.goto(`${baseUrl}/reading`, {waitUntil:'networkidle'});
    await page.waitForSelector('#article-list .article-item', {state:'attached'});
    if (!(await page.locator('#article-list').isVisible())) await page.locator('#reading-settings-toggle').tap();
    const mobileList = await page.locator('#article-list').evaluate(node => {
      const style=getComputedStyle(node);
      return {maxBlockSize:style.maxBlockSize,overflowY:style.overflowY,clientHeight:node.clientHeight,scrollHeight:node.scrollHeight};
    });
    assert(mobileList.maxBlockSize === 'none' && mobileList.overflowY === 'visible', `${viewport.width}px 手机文章列表出现嵌套滚动：${JSON.stringify(mobileList)}`);
    assert(Math.abs(mobileList.scrollHeight-mobileList.clientHeight) <= 1, `${viewport.width}px 手机文章列表没有保持自然高度`);
    assert(errors.length === 0, `${viewport.width}px 控制台错误：${errors.join(' | ')}`);
    await page.screenshot({path:path.join(output, `mobile-learn-${viewport.width}.png`),fullPage:false});
    report.mobile[viewport.width] = {buttonHeights,target,mobileList};
    await context.close();
  }

  for (const viewport of [{width:1024,height:768},{width:1366,height:768},{width:1440,height:900}]) {
    const context = await browser.newContext({viewport});
    const page = await context.newPage();
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${baseUrl}/reading`, {waitUntil:'networkidle'});
    await page.waitForSelector('#article-list .article-item', {state:'attached'});
    if (!(await page.locator('#article-list').isVisible())) await page.locator('#reading-settings-toggle').click();
    const list = page.locator('#article-list');
    const before = await list.evaluate(node => {
      const style=getComputedStyle(node);
      return {overflowY:style.overflowY,maxBlockSize:style.maxBlockSize,clientHeight:node.clientHeight,scrollHeight:node.scrollHeight};
    });
    assert(before.overflowY === 'auto', `${viewport.width}px 桌面文章列表未启用纵向滚动`);
    assert(before.clientHeight <= 544 && before.scrollHeight >= before.clientHeight, `${viewport.width}px 桌面文章列表高度异常：${JSON.stringify(before)}`);
    const items = page.locator('#article-list .article-item');
    await items.last().click();
    await page.waitForFunction(() => document.querySelector('#article-list .article-item:last-child')?.getAttribute('aria-current') === 'true');
    await page.waitForTimeout(100);
    const selectedVisible = await items.last().evaluate(node => {
      const item=node.getBoundingClientRect(); const box=node.parentElement.getBoundingClientRect();
      return node.getAttribute('aria-current') === 'true' && item.top >= box.top-1 && item.bottom <= box.bottom+1;
    });
    assert(selectedVisible, `${viewport.width}px 当前文章没有自动滚入列表可见区域`);
    assert(errors.length === 0, `${viewport.width}px 控制台错误：${errors.join(' | ')}`);
    await page.screenshot({path:path.join(output, `desktop-reading-${viewport.width}.png`),fullPage:false});
    report.desktop[viewport.width] = {before,selectedVisible};
    await context.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
})().catch(error => { console.error(error); process.exit(1); });

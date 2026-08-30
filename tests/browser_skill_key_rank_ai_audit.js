const fs = require('fs');
const path = require('path');

let chromium;
try { ({ chromium } = require('playwright')); }
catch (_) { ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'skill-key-rank-ai-20260829');
fs.mkdirSync(output, { recursive: true });

function assert(condition, message) { if (!condition) throw new Error(message); }
async function metrics(page) {
  return page.evaluate(() => ({
    width: innerWidth,
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    scrollHeight: document.documentElement.scrollHeight,
  }));
}
function watchErrors(page) {
  const errors = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  return errors;
}

(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true, args:['--disable-gpu']});
  const report = {desktop:{}, mobile:{}};

  for (const viewport of [{width:1440,height:900},{width:1024,height:768}]) {
    const context = await browser.newContext({viewport});
    const page = await context.newPage();
    const errors = watchErrors(page);
    await page.goto(`${baseUrl}/growth`, {waitUntil:'networkidle'});
    await page.waitForSelector('.rank-ladder__button');
    assert(await page.locator('.rank-ladder__volume').count() === 2, '桌面段位长卷没有拆成两卷');
    assert(await page.locator('.rank-ladder__button').count() === 10, '段位按钮不是十个');
    const volumeCounts = await page.locator('.rank-ladder__volume').evaluateAll(volumes => volumes.map(volume => volume.querySelectorAll('.rank-ladder__button').length));
    assert(volumeCounts.join(',') === '5,5', '两卷不是各五个段位');
    await page.locator('.rank-ladder__button[data-rank="5"]').hover();
    assert(await page.locator('#g-rank-tooltip').isVisible(), '悬停未显示段位信息');
    assert((await page.locator('#g-selected-name').textContent()).trim() === '解元', '悬停未联动段位档案');
    await page.locator('.rank-ladder__button[data-rank="6"]').click();
    assert((await page.locator('#g-selected-name').textContent()).trim() === '贡士', '点击未固定段位档案');
    await page.locator('.rank-ladder__button[data-rank="6"]').focus();
    await page.keyboard.press('ArrowRight');
    assert(await page.locator(':focus').getAttribute('data-rank') === '7', '方向键未移动段位焦点');
    assert(await page.locator('#g-ai-outcomes article').count() === 6, 'AI 成果账单不是六项真实成果');
    assert(await page.locator('#g-ai-heatmap').isVisible(), 'AI 调用热力图不可见');
    const fit = await metrics(page);
    assert(fit.overflowX <= 1, `${viewport.width}px 成长页横向溢出 ${fit.overflowX}px`);
    await page.screenshot({path:path.join(output,`growth-${viewport.width}.png`),fullPage:false});
    if (viewport.width === 1440) await page.locator('#g-ai-usage').screenshot({path:path.join(output,'growth-ai-outcomes-1440.png')});
    assert(errors.length === 0, `成长页控制台错误：${errors.join(' | ')}`);
    report.desktop[`growth-${viewport.width}`] = {...fit, volumeCounts, outcomeCount:6};

    await page.goto(`${baseUrl}/profile`, {waitUntil:'networkidle'});
    await page.waitForSelector('.skill-item');
    assert(await page.locator('.skill-item').count() >= 5, 'Skill 目录不足五项');
    assert(!(await page.locator('#wordbooks').getAttribute('open')), '词库目录没有默认收起');
    const recoveryText = await page.locator('#ai-service-status').textContent();
    assert(recoveryText.includes('重新验证一次'), '损坏旧密钥没有给出一次性恢复提示');
    if (viewport.width === 1440) await page.screenshot({path:path.join(output,'profile-initial-1440.png'),fullPage:false});
    const skillSwitch = page.locator('[data-skill-toggle="learning-assistant"]');
    const initial = await skillSwitch.getAttribute('aria-checked');
    await skillSwitch.click();
    await page.waitForFunction(value => document.querySelector('[data-skill-toggle="learning-assistant"]')?.getAttribute('aria-checked') !== value, initial);
    await page.locator('[data-skill-toggle="learning-assistant"]').click();
    await page.waitForFunction(value => document.querySelector('[data-skill-toggle="learning-assistant"]')?.getAttribute('aria-checked') === value, initial);
    await page.locator('.skill-create > summary').click();
    await page.fill('#skill-name','浏览器验收 Skill');
    await page.fill('#skill-description','仅用于验证新增和删除流程');
    await page.fill('#skill-instructions','回答时列出证据。');
    await page.click('#skill-create-form button[type="submit"]');
    await page.waitForFunction(() => [...document.querySelectorAll('.skill-item__index strong')].some(node => node.textContent.includes('浏览器验收 Skill')));
    page.once('dialog', dialog => dialog.accept());
    const custom = page.locator('.skill-item').filter({hasText:'浏览器验收 Skill'});
    await custom.locator('[data-skill-delete]').click();
    await page.waitForFunction(() => ![...document.querySelectorAll('.skill-item__index strong')].some(node => node.textContent.includes('浏览器验收 Skill')));
    const profileFit = await metrics(page);
    assert(profileFit.overflowX <= 1, `${viewport.width}px 我的页面横向溢出 ${profileFit.overflowX}px`);
    await page.screenshot({path:path.join(output,`profile-${viewport.width}.png`),fullPage:false});
    assert(errors.length === 0, `我的页面控制台错误：${errors.join(' | ')}`);
    report.desktop[`profile-${viewport.width}`] = {...profileFit, recovery:true, skillToggleCycle:true};

    await page.goto(`${baseUrl}/control?skill=reading-curator`, {waitUntil:'networkidle'});
    assert(await page.locator('#skill-workbench').isVisible(), 'Skill 深链接没有打开优化台');
    assert((await page.locator('#skill-workbench-title').textContent()).includes('四六级阅读编辑'), '优化台没有加载所选 Skill');
    assert((await page.locator('#control-chat-context').textContent()).includes('正在优化 Skill'), '对话未绑定 Skill 上下文');
    assert((await metrics(page)).overflowX <= 1, `${viewport.width}px 控制台横向溢出`);
    assert(errors.length === 0, `控制台错误：${errors.join(' | ')}`);
    await context.close();
  }

  for (const viewport of [{width:390,height:844},{width:360,height:800}]) {
    const context = await browser.newContext({viewport,isMobile:true,hasTouch:true});
    const page = await context.newPage();
    const errors = watchErrors(page);
    await page.goto(`${baseUrl}/profile`, {waitUntil:'networkidle'});
    await page.waitForSelector('.skill-item');
    assert((await metrics(page)).overflowX <= 1, `${viewport.width}px 我的页面横向溢出`);
    assert(!(await page.locator('#wordbooks').getAttribute('open')), '手机词库目录没有默认收起');
    await page.screenshot({path:path.join(output,`profile-${viewport.width}.png`),fullPage:false});
    await page.goto(`${baseUrl}/growth`, {waitUntil:'networkidle'});
    await page.waitForSelector('.rank-ladder__button');
    await page.locator('.rank-ladder__button[data-rank="3"]').tap();
    const sheet = page.locator('#g-rank-dossier');
    assert(await sheet.isVisible(), '手机段位详情层未打开');
    const box = await sheet.boundingBox();
    assert(box && box.height <= viewport.height * .76, '手机段位详情层超过视口 75%');
    await page.locator('#g-rank-dossier-close').tap();
    assert((await metrics(page)).overflowX <= 1, `${viewport.width}px 成长页横向溢出`);
    await page.screenshot({path:path.join(output,`growth-${viewport.width}.png`),fullPage:false});
    assert(errors.length === 0, `手机页面控制台错误：${errors.join(' | ')}`);
    report.mobile[viewport.width] = {sheetHeight:Math.round(box.height),overflowX:0};
    await context.close();
  }

  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

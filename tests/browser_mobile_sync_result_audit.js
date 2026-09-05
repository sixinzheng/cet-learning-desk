const fs = require('fs');
const path = require('path');
let chromium;
try { ({chromium} = require('playwright')); }
catch (_) { ({chromium} = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5099';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'mobile-sync-result');
fs.mkdirSync(output, {recursive:true});
function assert(value, message) { if (!value) throw new Error(message); }

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
  const report = {mobile:{},desktop:{}};
  for (const viewport of [{width:320,height:720},{width:360,height:800},{width:390,height:844}]) {
    const context = await browser.newContext({viewport,isMobile:true,hasTouch:true});
    const page = await context.newPage();
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));

    await page.goto(`${baseUrl}/control`, {waitUntil:'networkidle'});
    const control = await page.evaluate(() => {
      const buttons = [...document.querySelectorAll('#control-notes-toggle,#control-note-toggle,[data-control-language]')];
      const rects = buttons.map(button => {
        const r=button.getBoundingClientRect(); return {text:button.textContent.trim(),top:r.top,height:r.height,left:r.left,right:r.right};
      });
      return {
        titleHidden:getComputedStyle(document.querySelector('.control-chat__head > .section-heading')).display==='none',
        contextHidden:getComputedStyle(document.querySelector('.control-chat__context')).display==='none',
        rects, rows:new Set(rects.map(item=>Math.round(item.top))).size,
        overflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth,
        messagesHeight:document.querySelector('.control-messages').getBoundingClientRect().height,
      };
    });
    assert(control.titleHidden && control.contextHidden, `${viewport.width}px 控制页标题说明未隐藏`);
    assert(control.rows === 1, `${viewport.width}px 四个控制按钮没有保持同一行：${JSON.stringify(control.rects)}`);
    assert(control.rects.every(item => item.height >= 44), `${viewport.width}px 控制按钮触控目标不足`);
    assert(control.overflowX <= 1 && control.messagesHeight >= 180, `${viewport.width}px 控制页溢出或聊天区过短`);
    const languageTarget = page.locator('[data-control-language][aria-pressed="false"]').first();
    const targetLanguage = await languageTarget.getAttribute('data-control-language');
    await languageTarget.tap();
    await page.waitForFunction(language => document.querySelector(`[data-control-language="${language}"]`)?.getAttribute('aria-pressed') === 'true', targetLanguage);
    assert(await page.locator(`[data-control-language="${targetLanguage}"]`).getAttribute('aria-pressed') === 'true', '语言切换状态未更新');
    await page.screenshot({path:path.join(output,`control-${viewport.width}.png`),fullPage:false});

    await page.goto(`${baseUrl}/profile`, {waitUntil:'networkidle'});
    const profile = await page.evaluate(() => ({
      introHidden:getComputedStyle(document.querySelector('.settings-page > .page-heading > div')).display==='none',
      rankButtonVisible:document.querySelector('.settings-page > .page-heading > .btn').getBoundingClientRect().height >= 48,
      overflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth,
    }));
    assert(profile.introHidden && profile.rankButtonVisible && profile.overflowX <= 1, `${viewport.width}px 我的页精简失败`);
    await page.evaluate(() => {
      document.getElementById('profile-app').dataset.appPlatform='android';
      window.CETDeviceSync.onProgress({stage:'completed',sync_report:{
        transaction_id:`audit-${innerWidth}`,completed_at:'2026-09-05T00:00:00Z',
        devices:[{device_name:'电脑'},{device_name:'手机'}],
        mobile:{vocabulary:{added:8,updated:3,deleted:0,conflicts:0,total_after:1539},notes:{added:1,updated:0,deleted:0,conflicts:1,total_after:4}},
        snapshots:{mobile:{before:{rank:1,rank_name:'童生',mastered_words:10},after:{rank:2,rank_name:'生员',mastered_words:21}}},
      }});
    });
    const modal = await page.locator('#device-sync-result-modal');
    assert(await modal.isVisible(), `${viewport.width}px 同步成功弹窗未出现`);
    const modalFit = await modal.locator('[role="dialog"]').evaluate(node => {
      const r=node.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,width:r.width,viewport:innerHeight};
    });
    assert(modalFit.top >= 0 && modalFit.bottom <= modalFit.viewport + 1, `${viewport.width}px 同步弹窗超出视口`);
    await page.screenshot({path:path.join(output,`sync-result-${viewport.width}.png`),fullPage:false});
    await page.locator('[data-device-sync-result-close]').tap();
    assert(!(await modal.isVisible()), '同步弹窗关闭失败');

    await page.goto(`${baseUrl}/`, {waitUntil:'networkidle'});
    const facts = await page.evaluate(() => {
      const label=document.querySelector('.vocab-command__facts div:last-child dt');
      const value=document.querySelector('.vocab-command__facts div:last-child dd');
      const style=getComputedStyle(label); const valueStyle=getComputedStyle(value);
      return {labelHeight:label.getBoundingClientRect().height,lineHeight:parseFloat(style.lineHeight),labelWhiteSpace:style.whiteSpace,valueWhiteSpace:valueStyle.whiteSpace,overflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth};
    });
    assert(facts.labelHeight <= facts.lineHeight * 1.25 && facts.labelWhiteSpace === 'nowrap' && facts.valueWhiteSpace === 'nowrap', `${viewport.width}px 词库指标仍发生孤字换行`);
    assert(facts.overflowX <= 1, `${viewport.width}px 首页横向溢出`);
    assert(errors.length === 0, `${viewport.width}px 控制台错误：${errors.join(' | ')}`);
    report.mobile[viewport.width]={control,profile,modalFit,facts};
    await context.close();
  }

  const context = await browser.newContext({viewport:{width:1440,height:900}});
  const page = await context.newPage();
  await page.goto(`${baseUrl}/control`,{waitUntil:'networkidle'});
  const controlHeadingVisible = await page.locator('.control-chat__head > .section-heading').isVisible();
  await page.goto(`${baseUrl}/profile`,{waitUntil:'networkidle'});
  const profileHeadingVisible = await page.locator('.settings-page > .page-heading > div').isVisible();
  assert(controlHeadingVisible && profileHeadingVisible, '桌面页头被手机规则误隐藏');
  await page.evaluate(() => {
    document.getElementById('profile-app').dataset.appPlatform='windows';
    window.CETDeviceSync.onProgress({stage:'completed',sync_report:{
      transaction_id:'audit-desktop',completed_at:'2026-09-05T00:00:00Z',
      devices:[{device_name:'电脑'},{device_name:'手机'}],
      desktop:{vocabulary:{added:2,updated:1,deleted:0,conflicts:0,total_after:1539}},
      snapshots:{desktop:{before:{rank:1,rank_name:'童生',mastered_words:10},after:{rank:2,rank_name:'生员',mastered_words:13}}},
    }});
  });
  const desktopModal = page.locator('#device-sync-result-modal');
  assert(await desktopModal.isVisible(), '桌面同步成功弹窗未出现');
  const desktopModalFit = await desktopModal.locator('[role="dialog"]').evaluate(node => {
    const r=node.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,width:r.width,viewport:innerHeight};
  });
  assert(desktopModalFit.top >= 0 && desktopModalFit.bottom <= desktopModalFit.viewport + 1, '桌面同步弹窗超出视口');
  await page.locator('[data-device-sync-result-close]').click();
  assert(!(await desktopModal.isVisible()), '桌面同步弹窗关闭失败');
  report.desktop={controlHeadingVisible,profileHeadingVisible,modalFit:desktopModalFit};
  await context.close();
  await browser.close();
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
})().catch(error => { console.error(error); process.exit(1); });

const fs = require('fs');
const path = require('path');
let chromium;
try { ({chromium} = require('playwright')); }
catch (_) { ({chromium} = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5411';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'growth-reading-vocabulary-20260901');
fs.mkdirSync(output, {recursive:true});

function assert(value, message) { if (!value) throw new Error(message); }
function watchErrors(page) {
  const errors = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  return errors;
}
async function touchDrag(page, from, to) {
  const cdp = await page.context().newCDPSession(page);
  const point = (x, y) => [{x, y, radiusX:4, radiusY:4, force:1, id:1}];
  await cdp.send('Input.dispatchTouchEvent', {type:'touchStart', touchPoints:point(from.x, from.y)});
  for (let step = 1; step <= 10; step += 1) {
    const ratio = step / 10;
    await cdp.send('Input.dispatchTouchEvent', {type:'touchMove', touchPoints:point(
      from.x + (to.x - from.x) * ratio, from.y + (to.y - from.y) * ratio
    )});
  }
  await cdp.send('Input.dispatchTouchEvent', {type:'touchEnd', touchPoints:[]});
  await cdp.detach();
  await page.waitForTimeout(220);
}
async function sameLineSpan(page) {
  return page.locator('.article-word-ann').evaluateAll(nodes => {
    const items = nodes.slice(0, 60).map((node, index) => ({index, rect:node.getBoundingClientRect()}));
    for (let i = 0; i < items.length; i += 1) {
      for (let j = Math.min(items.length - 1, i + 4); j > i; j -= 1) {
        if (Math.abs(items[i].rect.top - items[j].rect.top) < 3) {
          return {
            first:items[i].index, last:items[j].index,
            from:{x:items[i].rect.left + 2,y:items[i].rect.top + items[i].rect.height / 2},
            to:{x:items[j].rect.right - 2,y:items[j].rect.top + items[j].rect.height / 2},
          };
        }
      }
    }
    throw new Error('没有找到同一行的连续词');
  });
}

(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true, args:['--disable-gpu']});
  const report = {mobile:{}, desktop:{}};

  for (const viewport of [{width:360,height:800},{width:390,height:844}]) {
    const context = await browser.newContext({viewport,isMobile:true,hasTouch:true});
    const page = await context.newPage();
    const errors = watchErrors(page);

    let difficultyRouteHits = 0;
    await page.route('**/api/study/difficulty-setting', async route => {
      difficultyRouteHits += 1;
      if (route.request().method() === 'GET') {
        await route.fulfill({json:{difficulty:null,label:'未设置'}});
      } else {
        await route.continue();
      }
    });
    await page.goto(`${baseUrl}/learn`, {waitUntil:'networkidle'});
    const difficultyPrompt = page.locator('#difficulty-prompt');
    const promptState = await page.evaluate(() => ({
      width:innerWidth,
      mobile:matchMedia('(max-width: 767px)').matches,
      hidden:document.getElementById('difficulty-prompt')?.hidden,
      display:getComputedStyle(document.getElementById('difficulty-prompt')).display,
      summary:document.getElementById('learn-difficulty-summary')?.textContent,
    }));
    assert(await difficultyPrompt.isVisible(), `${viewport.width}px 未设置难度时没有显示提醒；route=${difficultyRouteHits} state=${JSON.stringify(promptState)}`);
    const promptHeights = await page.locator('.difficulty-prompt__actions button').evaluateAll(nodes => nodes.map(node => Math.round(node.getBoundingClientRect().height)));
    assert(promptHeights.every(value => value >= 48), `${viewport.width}px 难度提醒按钮触控高度不足 48px`);
    await page.locator('#difficulty-prompt-later').tap();
    assert(!(await difficultyPrompt.isVisible()), `${viewport.width}px “稍后”没有关闭本次提醒`);
    await page.reload({waitUntil:'networkidle'});
    assert(await difficultyPrompt.isVisible(), `${viewport.width}px “稍后”后下次进入没有再次提醒`);
    await page.locator('#difficulty-prompt-go').tap();
    await page.waitForTimeout(650);
    const difficultyTarget = await page.evaluate(() => {
      const section = document.getElementById('training-difficulty').getBoundingClientRect();
      const radio = document.querySelector('input[name="training-difficulty"]');
      return {top:Math.round(section.top),focused:document.activeElement === radio};
    });
    assert(difficultyTarget.top >= 55 && difficultyTarget.top <= 200, `${viewport.width}px 没有定位到难度区域：${JSON.stringify(difficultyTarget)}`);
    assert(difficultyTarget.focused, `${viewport.width}px 定位后未聚焦第一个难度选项`);

    await page.goto(`${baseUrl}/growth`, {waitUntil:'networkidle'});
    await page.waitForSelector('#g-achievements canvas', {timeout:10000});
    const growth = await page.evaluate(() => {
      const box = selector => {
        const r = document.querySelector(selector).getBoundingClientRect();
        return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};
      };
      const panels = [...document.querySelectorAll('.achievement-chart-block')].map(node => node.getBoundingClientRect());
      const rhythm = [...document.querySelectorAll('.achievement-rhythm figure')].map(node => node.getBoundingClientRect());
      return {
        overflowX:document.documentElement.scrollWidth - document.documentElement.clientWidth,
        chart:box('#g-achievements'),
        chartCanvas:box('#g-achievements canvas'),
        panelsSingleColumn:panels.length >= 2 && panels[1].top >= panels[0].bottom - 1,
        rhythmSingleColumn:rhythm.length >= 2 && rhythm[1].top >= rhythm[0].bottom - 1,
        rhythmWidths:rhythm.map(item => Math.round(item.width)),
      };
    });
    assert(growth.overflowX <= 1, `${viewport.width}px 成长页横向溢出`);
    assert(growth.panelsSingleColumn, `${viewport.width}px 词汇成果与专项训练没有单列`);
    assert(growth.rhythmSingleColumn, `${viewport.width}px 学习节奏没有单列`);
    assert(growth.chart.width >= viewport.width - 90, `${viewport.width}px 图表没有使用内容区可用宽度`);
    assert(growth.chartCanvas.right <= growth.chart.right + 1, `${viewport.width}px ECharts 画布超出容器`);
    await page.locator('#g-achievements').scrollIntoViewIfNeeded();
    await page.waitForTimeout(180);
    await page.screenshot({path:path.join(output, `growth-${viewport.width}.png`), fullPage:false});

    let batchRequests = 0;
    page.on('request', request => {
      if (request.url().includes('/annotations/batch') && request.method() === 'POST') batchRequests += 1;
    });
    await page.goto(`${baseUrl}/reading`, {waitUntil:'networkidle'});
    await page.waitForSelector('.reading-task');
    const header = await page.evaluate(() => {
      const source = [...document.querySelectorAll('.reading-source-actions > *')].map(node => node.getBoundingClientRect());
      const font = document.querySelector('.reading-toolbar').getBoundingClientRect();
      const stage = document.querySelector('.focus-stage').getBoundingClientRect();
      return {
        sourceCount:source.length,
        sourceSameRow:source.length === 2 && Math.abs(source[0].top - source[1].top) <= 2,
        sourceHeights:source.map(item => Math.round(item.height)),
        fontCentered:Math.abs((font.left + font.width / 2) - (stage.left + stage.width / 2)) <= 3,
        fontButtonHeights:[...document.querySelectorAll('.reading-toolbar button')].map(node => Math.round(node.getBoundingClientRect().height)),
        overflowX:document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    assert(header.sourceCount === 2 && header.sourceSameRow, `${viewport.width}px 来源按钮没有同行`);
    assert(header.sourceHeights.every(value => value >= 48), `${viewport.width}px 来源按钮触控高度不足 48px`);
    assert(header.fontCentered && header.fontButtonHeights.every(value => value >= 48), `${viewport.width}px 字号控制未居中或触控高度不足`);
    assert(header.overflowX <= 1, `${viewport.width}px 阅读页横向溢出`);
    const mobileArticleList = await page.locator('#article-list').evaluate(node => ({
      maxBlockSize:getComputedStyle(node).maxBlockSize,
      overflowY:getComputedStyle(node).overflowY,
    }));
    assert(mobileArticleList.maxBlockSize === 'none' && mobileArticleList.overflowY === 'visible', `${viewport.width}px 手机文章列表被错误改成嵌套滚动`);

    const mark = page.locator('.mark-btn[data-mark="green"]');
    assert((await mark.getAttribute('aria-pressed')) === 'false', '标注模式没有默认退出');
    await mark.tap();
    assert((await mark.getAttribute('aria-pressed')) === 'true', '重点模式没有启用');
    const span = await sameLineSpan(page);
    await touchDrag(page, span.from, span.to);
    const marked = await page.locator('.article-word-ann.mark-green,.article-word-ann.mark-both').count();
    assert(marked >= 2, `${viewport.width}px 触摸滑动未连续标注`);
    assert(batchRequests === 1, `${viewport.width}px 一次滑动产生了 ${batchRequests} 次批量请求`);
    await page.screenshot({path:path.join(output, `reading-mark-${viewport.width}.png`), fullPage:false});
    await page.waitForTimeout(450);
    await mark.tap();
    await page.waitForTimeout(120);
    assert((await mark.getAttribute('aria-pressed')) === 'false', '再次点击没有退出标注模式');
    assert(!(await page.locator('#article-text').evaluate(node => node.classList.contains('is-marking'))), '退出后正文仍阻止滚动');
    await page.locator('.article-word-ann').first().tap();
    assert(await page.locator('#word-modal.is-open').isVisible(), '纯预览模式下手机单击没有打开查词');
    await page.locator('#word-modal-close').tap();

    const mastery = page.locator('#reading-mastery-toggle');
    await mastery.tap();
    assert((await mastery.getAttribute('aria-pressed')) === 'true', '掌握标色没有开启');
    assert((await page.locator('.article-word-ann[class*="mastery-"]').count()) > 0, '正文没有显示词汇状态');
    assert(await page.locator('#reading-mastery-legend').isVisible(), '六态图例没有显示');
    await mastery.tap();
    assert((await mastery.getAttribute('aria-pressed')) === 'false', '掌握标色没有关闭');
    assert((await page.locator('.article-word-ann[class*="mastery-"]').count()) === 0, '关闭后仍残留掌握标色');

    await page.locator('#reading-vocabulary-list').tap();
    assert(await page.locator('#vocabulary-modal.is-open').isVisible(), '本文词表弹窗没有打开');
    assert((await page.locator('.vocabulary-tabs button').count()) === 2, '词表缺少待掌握/已掌握分组');
    const favorite = page.locator('.vocabulary-favorite').first();
    if (await favorite.count()) {
      const oldPressed = await favorite.getAttribute('aria-pressed');
      await favorite.tap();
      assert((await favorite.getAttribute('aria-pressed')) !== oldPressed, '词表行内收藏没有切换');
    }
    await page.screenshot({path:path.join(output, `vocabulary-mobile-${viewport.width}.png`), fullPage:false});
    await page.locator('#vocabulary-modal-close').tap();

    let enrichmentCalls = 0;
    await page.route('**/api/ai/config/status', route => route.fulfill({json:{configured:true,csrf_token:'browser-csrf'}}));
    await page.route('**/api/ai/enrich-word', async route => {
      enrichmentCalls += 1;
      const request = route.request().postDataJSON();
      const surface = request.surface_word;
      await route.fulfill({json:{
        found:true,id:999001,word:surface,surface_form:surface,match_type:'ai_generated',
        phonetic:'/test/',part_of_speech:'n.',meanings:['浏览器测试释义'],frequency:1,
        status:'陌生',is_mastered:false,is_favorite:false,cached:false,
        ai_detail:{headword:surface,phonetic:'/test/',part_of_speech:'n.',context_meaning:'当前语境中的准确含义',
          additional_meanings:['另一常见含义'],form_note:'文中词形与词头相同。',
          context_example:{en:`The ${surface} remains useful here.`,zh:'这个词在这里仍然有用。'},
          other_example:{meaning:'另一常见含义',en:`Another ${surface} appears in a complete sentence.`,zh:'另一个完整例句。'}}
      }});
    });
    await page.locator('#reading-vocabulary-list').tap();
    const aiComplete = page.locator('.vocabulary-enrich').first();
    if (await aiComplete.count()) {
      await aiComplete.tap();
      await page.locator('#lookup-enrich').tap();
      await page.waitForSelector('.lookup-ai-detail');
      assert(enrichmentCalls === 1, 'AI 补全没有严格按用户点击调用一次');
      assert(await page.locator('.lookup-ai-detail').isVisible(), 'AI 补充详情没有独立展示');
      await page.screenshot({path:path.join(output, `word-ai-detail-${viewport.width}.png`), fullPage:false});
      await page.locator('#word-modal-close').tap();
    } else {
      await page.locator('#vocabulary-modal-close').tap();
    }

    await page.evaluate(() => window.scrollTo(0, document.querySelector('#article-text').offsetTop + 500));
    await page.waitForTimeout(100);
    const sticky = await page.locator('.mark-toolbar').evaluate(node => ({
      top:Math.round(node.getBoundingClientRect().top), position:getComputedStyle(node).position,
    }));
    assert(sticky.position === 'sticky' && sticky.top >= 55 && sticky.top <= 80, `${viewport.width}px 标注栏没有吸附到站点栏下方：${JSON.stringify(sticky)}`);
    await page.screenshot({path:path.join(output, `reading-sticky-${viewport.width}.png`), fullPage:false});

    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await page.route('**/api/study/new-words', route => route.fulfill({json:{words:[
      {id:91001,word:'brief',phonetic:'/briːf/',meanings:'["简短的"]',frequency:5,status:'陌生'},
      {id:91002,word:'stable',phonetic:'/ˈsteɪbəl/',meanings:'["稳定的"]',frequency:4,status:'陌生'},
      {id:91003,word:'context',phonetic:'/ˈkɒntekst/',meanings:'["语境"]',frequency:4,status:'陌生'},
      {id:91004,word:'review',phonetic:'/rɪˈvjuː/',meanings:'["复习"]',frequency:3,status:'陌生'},
    ]}}));
    await page.route('**/api/words/word/*', route => route.fulfill({json:{sentences:[],links:[],is_favorite:false}}));
    await page.route('**/api/study/start-learning', route => route.fulfill({json:{success:true}}));
    await page.route('**/api/study/answer', route => route.fulfill({json:{success:true}}));
    await page.goto(`${baseUrl}/study`, {waitUntil:'networkidle'});
    await page.waitForSelector('.quiz-opt-btn:visible');
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await page.locator('.quiz-opt-btn:visible').last().tap();
    await page.waitForSelector('#study-card-phase:visible');
    await page.waitForTimeout(650);
    const study = await page.evaluate(() => {
      const card = document.getElementById('study-card-phase').getBoundingClientRect();
      return {top:Math.round(card.top),scrollY:Math.round(window.scrollY),overflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth};
    });
    assert(study.top >= 50 && study.top <= 125, `${viewport.width}px 答后未自动定位到学习卡顶部：${JSON.stringify(study)}`);
    assert(study.overflowX <= 1, `${viewport.width}px 背词页横向溢出`);
    await page.screenshot({path:path.join(output, `study-answer-top-${viewport.width}.png`), fullPage:false});

    assert(errors.length === 0, `${viewport.width}px 控制台错误：${errors.join(' | ')}`);
    report.mobile[viewport.width] = {growth,header,marked,batchRequests,sticky,study};
    await context.close();
  }

  const desktopContext = await browser.newContext({viewport:{width:1440,height:900}});
  const desktop = await desktopContext.newPage();
  const desktopErrors = watchErrors(desktop);
  await desktop.goto(`${baseUrl}/reading`, {waitUntil:'networkidle'});
  await desktop.waitForSelector('.reading-task');
  const desktopToolbarPosition = await desktop.locator('.mark-toolbar').evaluate(node => getComputedStyle(node).position);
  assert(desktopToolbarPosition !== 'sticky', '手机吸顶规则误影响桌面');
  await desktop.locator('.mark-btn[data-mark="red"]').click();
  const pair = await sameLineSpan(desktop);
  await desktop.mouse.move(pair.from.x,pair.from.y); await desktop.mouse.down();
  await desktop.mouse.move(pair.to.x,pair.to.y,{steps:10}); await desktop.mouse.up();
  assert((await desktop.locator('.article-word-ann.mark-red,.article-word-ann.mark-both').count()) >= 2, '桌面鼠标拖动标注失败');
  await desktop.locator('.mark-btn[data-mark="red"]').click();
  await desktop.locator('#reading-mastery-toggle').click();
  assert((await desktop.locator('.article-word-ann[class*="mastery-"]').count()) > 0, '桌面掌握状态标色失败');
  await desktop.locator('.article-word-ann').last().dblclick();
  assert(await desktop.locator('#word-modal.is-open').isVisible(), '桌面双击查词失败');
  await desktop.locator('#word-modal-close').click();
  await desktop.locator('#reading-vocabulary-list').click();
  assert(await desktop.locator('#vocabulary-modal.is-open').isVisible(), '桌面词表弹窗失败');
  const desktopFit = await desktop.evaluate(() => ({
    overflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth,
    sourceDisplay:getComputedStyle(document.querySelector('.reading-source-actions')).display,
    articleList:(() => {
      const node=document.getElementById('article-list'); const style=getComputedStyle(node);
      return {overflowY:style.overflowY,clientHeight:node.clientHeight,scrollHeight:node.scrollHeight,maxBlockSize:style.maxBlockSize};
    })(),
  }));
  assert(desktopFit.overflowX <= 1, '桌面阅读页横向溢出');
  assert(desktopFit.articleList.overflowY === 'auto', '桌面文章列表没有独立纵向滚动');
  assert(desktopFit.articleList.clientHeight <= 544, `桌面文章列表过高：${desktopFit.articleList.clientHeight}px`);
  assert(desktopFit.articleList.scrollHeight >= desktopFit.articleList.clientHeight, '桌面文章列表尺寸异常');
  assert(desktopErrors.length === 0, `桌面控制台错误：${desktopErrors.join(' | ')}`);
  report.desktop = {desktopToolbarPosition,desktopFit};
  await desktop.screenshot({path:path.join(output,'reading-desktop-vocabulary.png'),fullPage:false});

  await desktop.addInitScript(() => {
    window.__scrollIntoViewCalls = 0;
    const original = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = function (...args) {
      window.__scrollIntoViewCalls += 1;
      return original.apply(this,args);
    };
  });
  await desktop.route('**/api/study/new-words', route => route.fulfill({json:{words:[
    {id:92001,word:'brief',phonetic:'/briːf/',meanings:'["简短的"]',frequency:5,status:'陌生'},
    {id:92002,word:'stable',phonetic:'/ˈsteɪbəl/',meanings:'["稳定的"]',frequency:4,status:'陌生'},
    {id:92003,word:'context',phonetic:'/ˈkɒntekst/',meanings:'["语境"]',frequency:4,status:'陌生'},
    {id:92004,word:'review',phonetic:'/rɪˈvjuː/',meanings:'["复习"]',frequency:3,status:'陌生'},
  ]}}));
  await desktop.route('**/api/words/word/*', route => route.fulfill({json:{sentences:[],links:[],is_favorite:false}}));
  await desktop.route('**/api/study/start-learning', route => route.fulfill({json:{success:true}}));
  await desktop.route('**/api/study/answer', route => route.fulfill({json:{success:true}}));
  await desktop.goto(`${baseUrl}/study`, {waitUntil:'networkidle'});
  await desktop.waitForSelector('.quiz-opt-btn:visible');
  await desktop.locator('.quiz-opt-btn:visible').first().click();
  await desktop.waitForSelector('#study-card-phase:visible');
  await desktop.waitForTimeout(450);
  const desktopStudy = await desktop.evaluate(() => ({
    scrollIntoViewCalls:window.__scrollIntoViewCalls,
    orderPreserved:document.getElementById('study-card-actions').previousElementSibling?.classList.contains('study-card-sentences'),
  }));
  assert(desktopStudy.scrollIntoViewCalls === 0, '答后自动定位误影响桌面');
  assert(desktopStudy.orderPreserved, '桌面答后内容顺序被手机规则改变');
  report.desktop.study = desktopStudy;

  await desktopContext.close();
  report.desktopViewports = {};
  for (const viewport of [{width:1024,height:768},{width:1366,height:768}]) {
    const extraContext = await browser.newContext({viewport});
    const extra = await extraContext.newPage();
    const extraErrors = watchErrors(extra);
    await extra.goto(`${baseUrl}/reading`, {waitUntil:'networkidle'});
    await extra.waitForSelector('.reading-task');
    const fit = await extra.evaluate(() => ({
      overflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth,
      toolbarPosition:getComputedStyle(document.querySelector('.mark-toolbar')).position,
      articleWidth:Math.round(document.querySelector('.reading-task').getBoundingClientRect().width),
    }));
    assert(fit.overflowX <= 1, `${viewport.width}px 桌面阅读页横向溢出`);
    assert(fit.toolbarPosition !== 'sticky', `${viewport.width}px 被误套用手机吸顶规则`);
    await extra.locator('#reading-mastery-toggle').click();
    assert((await extra.locator('.article-word-ann[class*="mastery-"]').count()) > 0, `${viewport.width}px 掌握标色失败`);
    await extra.locator('#reading-vocabulary-list').click();
    assert(await extra.locator('#vocabulary-modal.is-open').isVisible(), `${viewport.width}px 词表弹窗失败`);
    assert(extraErrors.length === 0, `${viewport.width}px 控制台错误：${extraErrors.join(' | ')}`);
    await extra.screenshot({path:path.join(output, `reading-desktop-${viewport.width}.png`),fullPage:false});
    report.desktopViewports[viewport.width] = fit;
    await extraContext.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
})().catch(error => { console.error(error); process.exit(1); });

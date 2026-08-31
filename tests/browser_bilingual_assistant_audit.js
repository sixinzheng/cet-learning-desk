const assert = require('assert');
const fs = require('fs');
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); }
catch (_) { ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const artifacts = path.join(process.cwd(), 'browser-artifacts', 'bilingual-assistant');
fs.mkdirSync(artifacts, {recursive: true});
const scenes = [
  ['casual','随便聊聊','Just chat'], ['daily','日常闲聊','Daily life'],
  ['travel','旅行出行','Travel'], ['campus','校园学习','Campus'],
  ['workplace','职场沟通','Workplace'], ['culture','兴趣文化','Culture & interests'],
  ['opinions','观点讨论','Opinions'],
].map(([key,label_zh,label_en]) => ({key,label_zh,label_en}));

async function mockAssistant(page) {
  let language = 'zh';
  await page.addInitScript(() => {
    localStorage.removeItem('cet-ai-conversation');
    localStorage.setItem('cet-onboarding-v1', JSON.stringify({version:2,welcome_seen:true,status:'completed'}));
  });
  await page.route('**/api/ai/config/status', route => route.fulfill({json:{configured:false,csrf_token:'browser-test'}}));
  await page.route('**/api/ai/preferences', async route => {
    if (route.request().method() === 'PUT') language = (await route.request().postDataJSON()).language;
    await route.fulfill({json:{ok:true,language,english_variant:'en-US',scenes,csrf_token:'browser-test'}});
  });
  await page.route('**/api/ai/greeting**', route => {
    const en = new URL(route.request().url()).searchParams.get('language') === 'en';
    route.fulfill({json:{language:en?'en':'zh',source:'local',date:'2026-08-30',greeting:en?'You reviewed 12 words this week. Want to warm up with a quick chat?':'你本周完成了 12 次复习，今天可以轻松开始。'}});
  });
  await page.route('**/api/ai/conversations**', route => {
    if (/\/messages$/.test(route.request().url())) return route.fulfill({json:{conversation:{id:1,language,scenario_key:'travel'},messages:[]}});
    return route.fulfill({json:{conversations:[]}});
  });
  await page.route('**/api/ai/chat', async route => {
    const body = await route.request().postDataJSON();
    const text = body.start_scene
      ? 'Your train just got delayed, but the station café smells amazing. Would you wait or explore nearby?'
      : 'That sounds like a fun direction. What happened next?';
    const result = {conversation_id:91,message:text,citations:[],action:null,memory_candidate:null,usage:{},model:'mock',language:body.language||language,scenario_key:body.scenario_key||'casual'};
    const sse = `event: meta\ndata: ${JSON.stringify({conversation_id:91})}\n\nevent: delta\ndata: ${JSON.stringify({delta:text,conversation_id:91})}\n\nevent: done\ndata: ${JSON.stringify(result)}\n\n`;
    await route.fulfill({status:200,contentType:'text/event-stream',body:sse});
  });
}

async function checkDesktop(browser) {
  const context = await browser.newContext({viewport:{width:1440,height:900}});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await mockAssistant(page);

  await page.goto(`${baseUrl}/profile`, {waitUntil:'domcontentloaded'});
  const navLabels = await page.locator('.settings-index a').allTextContents();
  assert.equal(navLabels.at(-1).trim(), '支持作者');
  const order = await page.evaluate(() => ({books:document.getElementById('wordbooks').offsetTop,support:document.getElementById('support').offsetTop}));
  assert(order.books < order.support);
  await page.screenshot({path:path.join(artifacts,'profile-desktop.png'),fullPage:true});

  await page.goto(baseUrl, {waitUntil:'domcontentloaded'});
  await page.locator('#ai-quick-chat').waitFor();
  await page.getByRole('button',{name:'English'}).click();
  await page.locator('#home-english-scenes').waitFor({state:'visible'});
  assert.equal(await page.locator('#home-scene-select option').count(), 7);
  await page.locator('#home-scene-select').selectOption('travel');
  await page.locator('#home-scene-start').click();
  await page.waitForFunction(() => [...document.querySelectorAll('.ai-message--assistant')].some(node => node.textContent.includes('explore nearby')));
  await page.waitForFunction(() => document.querySelector('#ai-chat-form button')?.textContent.trim() === 'Send');
  assert.equal(await page.locator('.ai-message--user').count(), 0);
  assert((await page.locator('.ai-message--assistant').last().innerText()).includes('train'));
  assert(!(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)));
  await page.screenshot({path:path.join(artifacts,'home-english-desktop.png')});
  await page.getByRole('button',{name:'中文'}).click();
  await page.locator('#home-english-scenes').waitFor({state:'hidden'});
  assert.equal((await page.locator('#ai-chat-title').innerText()).trim(), '带着你的数据，回答今天的问题');

  await page.goto(`${baseUrl}/control`, {waitUntil:'domcontentloaded'});
  await page.locator('#control-language-switch').waitFor();
  await page.locator('[data-control-language="en"]').click();
  await page.locator('#control-english-scenes').waitFor({state:'visible'});
  assert.equal(await page.locator('#control-scene-select option').count(), 7);
  await page.locator('#control-scene-select').selectOption('travel');
  await page.locator('#control-scene-start').click();
  await page.waitForFunction(() => [...document.querySelectorAll('.control-msg--assistant')].some(node => node.textContent.includes('explore nearby')));
  assert.equal(await page.locator('.control-msg--user').count(), 0);
  assert(!(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)));
  await page.screenshot({path:path.join(artifacts,'control-english-desktop.png')});

  await page.goto(`${baseUrl}/notes#assistant`, {waitUntil:'domcontentloaded'});
  await page.locator('#assistant').waitFor();
  await page.getByRole('button',{name:'English'}).click();
  assert.equal(await page.locator('#notes-scene-grid button').count(), 7);
  await page.locator('[data-scene-key="travel"]').click();
  await page.waitForFunction(() => [...document.querySelectorAll('.assistant-message--assistant')].some(node => node.textContent.includes('explore nearby')));
  await page.waitForFunction(() => document.querySelector('#notes-chat-form button')?.textContent.trim() === 'Send');
  assert.equal(await page.locator('.assistant-message--user').count(), 0);
  assert(await page.locator('#notes-english-controls').isVisible());
  assert(!(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)));
  await page.screenshot({path:path.join(artifacts,'notes-english-desktop.png')});
  await page.locator('#notes-new-chat').click();
  await page.locator('#notes-english-scenes').waitFor({state:'visible'});
  assert.deepEqual(errors, []);
  await context.close();
}

async function checkMobile(browser, width, height) {
  const context = await browser.newContext({viewport:{width,height},isMobile:true,hasTouch:true});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await mockAssistant(page);
  await page.goto(`${baseUrl}/notes#assistant`, {waitUntil:'domcontentloaded'});
  await page.locator('#assistant').waitFor();
  await page.getByRole('button',{name:'English'}).tap();
  await page.locator('#notes-english-scenes').waitFor({state:'visible'});
  assert.equal(await page.locator('#notes-scene-grid button').count(), 7);
  const minimum = await page.locator('#notes-scene-grid button').evaluateAll(nodes => Math.min(...nodes.map(node => node.getBoundingClientRect().height)));
  assert(minimum >= 44);
  assert(!(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)));
  await page.locator('#notes-english-scenes').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(artifacts,`notes-english-${width}.png`)});
  assert.deepEqual(errors, []);

  if (width === 390) {
    await page.goto(`${baseUrl}/control`, {waitUntil:'domcontentloaded'});
    await page.locator('[data-control-language="en"]').tap();
    await page.locator('#control-english-scenes').waitFor({state:'visible'});
    assert.equal(await page.locator('#control-scene-select option').count(), 7);
    const languageTarget = await page.locator('[data-control-language="en"]').boundingBox();
    assert(languageTarget && languageTarget.height >= 44);
    assert(!(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)));
    await page.screenshot({path:path.join(artifacts,'control-english-mobile.png')});
  }
  await context.close();
}

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
  try {
    await checkDesktop(browser);
    await checkMobile(browser,390,844);
    await checkMobile(browser,360,800);
    console.log(JSON.stringify({ok:true,artifacts},null,2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });

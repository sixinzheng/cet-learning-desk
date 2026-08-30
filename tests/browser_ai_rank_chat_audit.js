const fs = require('fs');
const path = require('path');

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (_) {
  ({ chromium } = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright'));
}

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'ai-rank-chat-audit');
fs.mkdirSync(output, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function installMockChat(page) {
  await page.route('**/api/ai/chat', async route => {
    const payload = {
      conversation_id: 991,
      message: '你的当前段位是童生。我会结合段位、复习量和近期训练证据回答。',
      citations: [],
    };
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream; charset=utf-8',
      body: `data: ${JSON.stringify(payload)}\n\n`,
    });
  });
}

async function fit(page) {
  return page.evaluate(() => ({
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    width: innerWidth,
    height: innerHeight,
  }));
}

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const report = {};

  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport, isMobile: viewport.width < 600, hasTouch: viewport.width < 600 });
    const page = await context.newPage();
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));
    await installMockChat(page);

    await page.goto(`${baseUrl}/control`, { waitUntil: 'networkidle' });
    await page.fill('#control-chat-input', '我的段位是什么？');
    await page.click('#control-chat-form button[type="submit"]');
    await page.waitForSelector('.control-msg--assistant');
    const user = page.locator('.control-msg--user').last();
    const assistant = page.locator('.control-msg--assistant').last();
    const userBox = await user.boundingBox();
    const assistantBox = await assistant.boundingBox();
    const userRank = (await user.locator('.control-msg__bubble strong').textContent()).trim();
    const userAvatarAlt = await user.locator('.chat-avatar').getAttribute('alt');
    assert(userRank && userRank !== '你' && userAvatarAlt.includes(userRank), '用户头像仍显示“你”，没有使用当前段位');
    assert(userBox && assistantBox && userBox.x > assistantBox.x, '用户与 AI 消息没有形成左右角色区分');
    assert((await assistant.locator('.chat-avatar').getAttribute('alt')) === '学习助理头像', 'AI 消息没有使用首页学习助理头像');
    assert((await assistant.textContent()).includes('当前段位'), 'AI 回答没有呈现段位上下文');
    const accept = await page.locator('#control-file').getAttribute('accept');
    assert(accept.includes('image/png') && accept.includes('image/webp'), '附件入口没有开放官方视觉模型支持的图片格式');
    await page.locator('#control-file').setInputFiles({
      name: 'english-question.png',
      mimeType: 'image/png',
      buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'),
    });
    await page.waitForSelector('.control-attachment');
    assert((await page.locator('.control-attachment').textContent()).includes('english-question.png'), '图片附件没有进入待发送列表');
    const metrics = await fit(page);
    assert(metrics.overflowX <= 1, `${viewport.width}px 对话页横向溢出 ${metrics.overflowX}px`);
    assert(errors.length === 0, `对话页控制台错误：${errors.join(' | ')}`);
    await page.screenshot({ path: path.join(output, `control-${viewport.width}.png`), fullPage: false });
    report[viewport.width] = { userRank, ...metrics, errors };
    await context.close();
  }

  const writingContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const writingPage = await writingContext.newPage();
  await writingPage.goto(`${baseUrl}/writing`, { waitUntil: 'networkidle' });
  assert(await writingPage.locator('#writing-image').count() === 0, '写作页仍显示不可用的图片上传控件');
  assert((await writingPage.locator('body').textContent()).includes('作文评分只接收可核对的文字'), '写作页缺少评分输入边界提示');
  await writingContext.close();

  fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});

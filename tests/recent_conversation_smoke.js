const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto('http://127.0.0.1:5400/notes', { waitUntil: 'networkidle' });
  const recent = page.locator('.conversation-link').first();
  await recent.waitFor({ state: 'visible' });
  await recent.click();
  await page.waitForFunction(() => document.querySelectorAll('#notes-ai-chat .assistant-message').length >= 2);
  const history = await page.locator('#notes-ai-chat').textContent();

  if (process.env.HISTORY_ONLY === '1') {
    console.log(JSON.stringify({ historyLoaded: history.trim().length > 0, errors }, null, 2));
    await browser.close();
    if (!history.trim() || errors.length) process.exit(1);
    return;
  }

  await page.click('#notes-new-chat');
  await page.fill('#notes-chat-input', '你好，请用一句中文确认连接正常。');
  await page.click('#notes-chat-form button[type="submit"]');
  await page.waitForFunction(() => {
    const button = document.querySelector('#notes-chat-form button[type="submit"]');
    return button && !button.disabled && document.querySelectorAll('#notes-ai-chat .assistant-message').length >= 2;
  }, null, { timeout: 60000 });
  const reply = await page.locator('#notes-ai-chat').textContent();
  const failed = /Failed to fetch|本地服务不可用|尚未配置 DeepSeek/.test(reply);
  console.log(JSON.stringify({ historyLoaded: history.trim().length > 0, freshReplyReceived: !failed, errors }, null, 2));
  await browser.close();
  if (!history.trim() || failed || errors.length) process.exit(1);
})().catch(error => { console.error(error); process.exit(1); });

const { chromium } = require('playwright');

(async () => {
  const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));

  await page.goto(`${baseUrl}/`, { waitUntil: 'networkidle' });
  await page.fill('#ai-chat-input', '请告诉我今天先做什么');
  await page.click('#ai-chat-form button[type="submit"]');
  await page.waitForFunction(() => document.querySelector('#ai-chat-messages').textContent.includes('尚未配置'));
  const homeFallback = await page.locator('#ai-chat-messages').textContent();

  await page.goto(`${baseUrl}/profile#ai-settings`, { waitUntil: 'networkidle' });
  await page.click('#ai-key-toggle');
  const keyType = await page.locator('#ai-key-input').getAttribute('type');
  await page.click('#ai-key-save');
  await page.waitForFunction(() => document.querySelector('#ai-config-message').textContent.includes('请先填写'));
  const profileValidation = await page.locator('#ai-config-message').textContent();

  await page.goto(`${baseUrl}/growth`, { waitUntil: 'networkidle' });
  const radarCount = await page.locator('.radar-triptych figure').count();
  const aiUsageTitle = await page.locator('#g-ai-usage').textContent();

  await page.goto(`${baseUrl}/grammar`, { waitUntil: 'networkidle' });
  await page.locator('.grammar-category').nth(1).click();
  const categoryTitle = await page.locator('#grammar-current-name').textContent();
  const directoryCount = await page.locator('.grammar-category').count();

  const result = {
    homeFallback: homeFallback.includes('尚未配置'),
    keyToggleWorks: keyType === 'text',
    profileValidation: profileValidation.includes('请先填写'),
    radarCount,
    aiUsageVisible: aiUsageTitle.includes('过去84天'),
    grammarCategories: directoryCount,
    categoryChanged: categoryTitle.trim().length > 0,
    errors,
  };
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
  if (!result.homeFallback || !result.keyToggleWorks || !result.profileValidation || radarCount !== 3 || !result.aiUsageVisible || directoryCount !== 12 || !result.categoryChanged || errors.length) process.exit(1);
})().catch(error => { console.error(error); process.exit(1); });

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
  const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'ui-refinement');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-gpu'] });
  const failures = [];
  const check = (condition, message) => { if (!condition) failures.push(message); };

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(`${baseUrl}/`, { waitUntil: 'networkidle' });
  const home = await mobile.evaluate(() => ({
    navRows: new Set([...document.querySelectorAll('.mobile-nav__item')].map(item => Math.round(item.getBoundingClientRect().top))).size,
    taskTop: document.querySelector('.vocab-command').getBoundingClientRect().top,
    chatTop: document.querySelector('.ai-quick-chat').getBoundingClientRect().top,
  }));
  check(home.navRows === 1, '390px 底部导航没有保持单行');
  check(home.taskTop < home.chatTop, '手机首页核心任务没有排在 AI 对话之前');

  await mobile.route('**/api/study/start-learning', route => route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }));
  await mobile.route('**/api/study/answer', route => route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }));
  await mobile.goto(`${baseUrl}/study`, { waitUntil: 'networkidle' });
  const study = await mobile.evaluate(() => {
    const option = document.querySelector('.quiz-opt-btn');
    return {
      word: document.querySelector('.quiz-word-big')?.textContent.trim(),
      firstQueueWord: document.querySelector('.queue-word-text')?.textContent.trim(),
      letters: [...document.querySelectorAll('.opt-letter')].map(item => item.textContent.trim()),
      optionDisplay: option ? getComputedStyle(option).display : '',
      optionWidth: option?.getBoundingClientRect().width || 0,
      optionsWidth: document.querySelector('.quiz-options')?.getBoundingClientRect().width || 0,
      mainTop: document.querySelector('.main-grid > main').getBoundingClientRect().top,
      asideTop: document.querySelector('.main-grid > aside').getBoundingClientRect().top,
    };
  });
  check(study.word === study.firstQueueWord, '学习页首次显示的不是队列第一个单词');
  check(study.letters.join('') === 'ABCD', '学习选项没有显示 A-D');
  check(study.optionDisplay === 'grid', '学习选项没有使用两列网格排版');
  check(Math.abs(study.optionWidth - study.optionsWidth) <= 1, '手机学习选项没有占满可用宽度');
  check(study.mainTop < study.asideTop, '手机学习主区域没有排在单词列表之前');
  await mobile.screenshot({ path: path.join(output, 'study-mobile.png'), fullPage: true });
  await mobile.keyboard.press('a');
  await mobile.waitForTimeout(400);
  check(await mobile.locator('[x-show="phase === \'card\'"]').isVisible(), 'A-D 键盘答题没有进入学习卡片');
  await mobile.reload({ waitUntil: 'networkidle' });
  await mobile.keyboard.press('1');
  await mobile.waitForTimeout(400);
  check(await mobile.locator('[x-show="phase === \'card\'"]').isVisible(), '原有 1-4 键盘答题兼容失效');
  await mobile.close();

  const desktop = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await desktop.goto(`${baseUrl}/profile`, { waitUntil: 'networkidle' });
  const collapsed = await desktop.locator('.wb-accordion__trigger').evaluateAll(items => items.every(item => item.getAttribute('aria-expanded') === 'false'));
  check(collapsed, '词书没有默认全部收起');
  check(await desktop.locator('.wb-cover').count() === await desktop.locator('.wb-accordion__trigger').count(), '并非每本词书都有封面');
  await desktop.locator('.wb-accordion__trigger').nth(0).click();
  await desktop.locator('.wb-accordion__trigger').nth(1).click();
  const openCount = await desktop.locator('.wb-accordion__trigger[aria-expanded="true"]').count();
  check(openCount === 1, '词书手风琴同时展开了多本');

  await desktop.goto(`${baseUrl}/notes`, { waitUntil: 'networkidle' });
  if (await desktop.locator('.note-history-item').count()) {
    await desktop.locator('.note-history-item').first().click();
    await desktop.waitForFunction(() => document.querySelector('#note-modal-preview')?.textContent.trim().length > 0);
    check(await desktop.locator('#note-manager-modal').isVisible(), '历史笔记预览弹窗没有打开');
    await desktop.screenshot({ path: path.join(output, 'note-preview-desktop.png'), fullPage: false });
    await desktop.locator('#note-modal-edit').click();
    await desktop.locator('#note-modal-editor').fill(`${await desktop.locator('#note-modal-editor').inputValue()}（未保存测试）`);
    desktop.once('dialog', dialog => dialog.dismiss());
    await desktop.keyboard.press('Escape');
    check(await desktop.locator('#note-manager-modal').isVisible(), '存在未保存修改时没有阻止弹窗关闭');
    await desktop.locator('#note-modal-editor').fill(await desktop.locator('#note-modal-preview').textContent());
    await desktop.keyboard.press('Escape');
    check(!(await desktop.locator('#note-manager-modal').isVisible()), 'Escape 没有关闭笔记预览弹窗');
  }
  await desktop.close();
  await browser.close();

  console.log(JSON.stringify({ checked: 14, failures }, null, 2));
  process.exitCode = failures.length ? 1 : 0;
})().catch(error => { console.error(error); process.exit(1); });

const fs = require('fs');
const path = require('path');
let chromium;
try { ({chromium} = require('playwright')); }
catch (_) { ({chromium} = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5400';
const output = process.argv[2] || path.join(process.cwd(), 'browser-artifacts', 'safe-update-skill-20260831');
fs.mkdirSync(output, {recursive: true});

function assert(value, message) {
  if (!value) throw new Error(message);
}

async function installMocks(page, state) {
  await page.addInitScript(() => localStorage.setItem('cet-onboarding-v1', JSON.stringify({version: 1, status: 'completed'})));
  await page.route('**/api/words/wordbooks', route => route.fulfill({json: {wordbooks: [{
    id: 1, name: '四级完整词库', description: 'CET-4 大纲词汇全集', total_words: 3849,
    mastered: 42, known: 118, learning: 73, is_current: true,
  }]}}));
  await page.route('**/api/ai/config/status', route => route.fulfill({json: {
    configured: false, key_material_present: false, csrf_token: 'browser-csrf', model: 'deepseek-v4-flash',
  }}));
  await page.route('**/api/ai/skills', route => route.fulfill({json: {csrf_token: 'browser-csrf', skills: [
    {slug: 'reading', display_name: '阅读策展', description: '筛选权威材料并生成阅读题。', enabled: true, is_builtin: true, user_instructions: ''},
    {slug: 'english-chat', display_name: '地道英语陪练', description: '用自然、健谈的英语陪用户练习。', enabled: false, is_builtin: false, user_instructions: '保持幽默但不牺牲准确性。'},
  ]}}));
  await page.route('**/api/app/update/status', route => {
    state.statusCalls += 1;
    if (state.mode === 'error') return route.fulfill({status: 503, json: {error: '暂时无法连接 GitHub，请稍后重试。'}});
    const available = state.mode === 'available';
    return route.fulfill({json: {
      platform: state.platform, current_version: '0.3.0', latest_version: available ? '0.3.1' : '0.3.0',
      update_available: available, install_supported: state.platform !== 'source', csrf_token: 'browser-csrf',
      release_name: '稳定版 v0.3.1', release_notes: '修复更新流程，并保留本地学习数据。',
      published_at: '2026-08-31T00:00:00Z', download_size: 41390842,
      release_url: 'https://github.com/sixinzheng/cet-learning-desk/releases/tag/v0.3.1',
      progress: {stage: available ? 'available' : 'current', percent: available ? 10 : 100, message: available ? '发现稳定版 0.3.1。' : '已经是最新稳定版。'},
    }});
  });
  await page.route('**/api/app/update/prepare', async route => {
    state.prepareBody = route.request().postDataJSON();
    await route.fulfill({json: {
      ok: true, latest_version: '0.3.1', backup_name: 'vocab-before-0.3.0-to-0.3.1.db',
      native_action: '#updates', progress: {stage: 'ready_for_native', percent: 50, message: '备份已完成。'},
    }});
  });
}

async function verifyViewport(browser, width, height) {
  const context = await browser.newContext({viewport: {width, height}, isMobile: width <= 767, hasTouch: width <= 767});
  const page = await context.newPage();
  const errors = [];
  const state = {mode: 'current', platform: 'source', statusCalls: 0, prepareBody: null};
  page.on('console', message => {
    const expectedUpdateFailure = state.mode === 'error'
      && message.text().includes('503 (Service Unavailable)');
    if (message.type() === 'error' && !expectedUpdateFailure) errors.push(message.text());
  });
  page.on('pageerror', error => errors.push(error.message));
  await installMocks(page, state);
  await page.goto(`${baseUrl}/profile`, {waitUntil: 'networkidle'});

  assert(state.statusCalls === 0, `${width}: 页面加载时不应自动联网检查更新`);
  assert(!(await page.locator('#skills').getAttribute('open')), `${width}: Skill 整区应默认收起`);
  assert(await page.locator('#skills > summary').getAttribute('aria-expanded') === 'false', `${width}: Skill 摘要初始 aria-expanded 错误`);
  assert(await page.locator('#skill-summary-count').textContent() === '已启用 1 / 共 2 个', `${width}: Skill 启用计数错误`);

  await page.locator('.settings-index a[href="#skills"]').click();
  assert(await page.locator('#skills').getAttribute('open') !== null, `${width}: 侧栏锚点没有展开 Skill`);
  await page.waitForFunction(() => document.querySelector('#skills > summary')?.getAttribute('aria-expanded') === 'true');
  assert(await page.locator('#skills > summary').getAttribute('aria-expanded') === 'true', `${width}: 外层 aria-expanded 未同步`);
  const items = page.locator('.skill-item');
  await items.nth(0).locator('summary').click();
  await items.nth(1).locator('summary').click();
  await page.waitForFunction(() => {
    const current = [...document.querySelectorAll('.skill-item')];
    return current.length === 2
      && !current[0].open
      && current[0].querySelector('summary')?.getAttribute('aria-expanded') === 'false'
      && current[1].open
      && current[1].querySelector('summary')?.getAttribute('aria-expanded') === 'true';
  });
  assert(await items.nth(0).getAttribute('open') === null, `${width}: Skill 手风琴没有关闭上一项`);
  assert(await items.nth(1).getAttribute('open') !== null, `${width}: Skill 手风琴没有打开当前项`);
  assert(await items.nth(0).locator('summary').getAttribute('aria-expanded') === 'false', `${width}: 上一项 aria-expanded 未复位`);
  assert(await items.nth(1).locator('summary').getAttribute('aria-expanded') === 'true', `${width}: 当前项 aria-expanded 未更新`);
  assert(await page.locator('.skill-create').getAttribute('open') === null, `${width}: 新建 Skill 应默认收起`);

  const order = await page.evaluate(() => ({
    wordbooks: document.getElementById('wordbooks').offsetTop,
    updates: document.getElementById('updates').offsetTop,
    support: document.getElementById('support').offsetTop,
  }));
  assert(order.wordbooks < order.updates && order.updates < order.support, `${width}: 词库、安全更新、支持作者顺序错误`);

  await page.locator('#update-check').click();
  assert(state.statusCalls === 1, `${width}: 用户点击后应恰好检查一次`);
  await page.waitForFunction(() => document.getElementById('update-state-title')?.textContent.includes('最新稳定版'));
  assert((await page.locator('#update-state-title').textContent()).includes('最新稳定版'), `${width}: 最新版状态未显示`);

  state.mode = 'available';
  state.platform = 'windows';
  await page.locator('#update-check').click();
  await page.locator('#update-modal').waitFor({state: 'visible'});
  assert(await page.locator('#update-modal').isVisible(), `${width}: 新版确认弹窗未打开`);
  assert((await page.locator('#update-modal-meta').textContent()).includes('0.3.1'), `${width}: 新版信息不完整`);
  await page.keyboard.press('Escape');
  assert(await page.locator('#update-modal').isHidden(), `${width}: Esc 未关闭更新弹窗`);
  assert(await page.evaluate(() => document.activeElement?.id === 'update-check'), `${width}: 弹窗关闭后焦点未恢复`);

  await page.locator('#update-check').click();
  await page.locator('#update-install').click();
  await page.waitForFunction(() => location.hash === '#updates');
  assert(state.prepareBody?.confirm === true, `${width}: 安装准备请求缺少显式确认`);

  state.mode = 'error';
  await page.locator('#update-check').click();
  await page.waitForFunction(() => document.getElementById('update-state-title')?.textContent === '检查失败');
  assert((await page.locator('#update-state-title').textContent()) === '检查失败', `${width}: 网络失败状态未显示`);
  assert((await page.locator('#update-check').textContent()) === '重试检查', `${width}: 网络失败后没有重试入口`);

  const metrics = await page.evaluate(() => ({
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    skillSummaryHeight: document.querySelector('#skills > summary').getBoundingClientRect().height,
    updateButtonHeight: document.getElementById('update-check').getBoundingClientRect().height,
    supportButtonHeight: document.getElementById('support-author-button').getBoundingClientRect().height,
    overflowers: [...document.querySelectorAll('body *')].map(element => {
      const rect = element.getBoundingClientRect();
      return {tag: element.tagName, id: element.id, className: String(element.className || ''), left: rect.left, right: rect.right, width: rect.width};
    }).filter(item => item.right > document.documentElement.clientWidth + 1 || item.left < -1).slice(0, 12),
  }));
  await page.screenshot({path: path.join(output, `profile-${width}x${height}.png`), fullPage: true});
  assert(metrics.overflowX <= 1, `${width}: 存在横向溢出 ${metrics.overflowX}px ${JSON.stringify(metrics.overflowers)}`);
  if (width <= 767) {
    assert(metrics.skillSummaryHeight >= 48, `${width}: Skill 摘要触控区域不足 48px`);
    assert(metrics.updateButtonHeight >= 48, `${width}: 更新按钮触控区域不足 48px`);
    assert(metrics.supportButtonHeight >= 48, `${width}: 支持按钮触控区域不足 48px`);
  }
  await context.close();
  return {width, height, order, metrics, errors, statusCalls: state.statusCalls};
}

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true, args: ['--disable-gpu']});
  try {
    const results = [];
    for (const [width, height] of [[1440, 900], [1024, 768], [390, 844], [360, 800]]) {
      results.push(await verifyViewport(browser, width, height));
    }
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(results, null, 2));
    const errors = results.flatMap(result => result.errors);
    assert(errors.length === 0, `浏览器控制台错误：${errors.join(' | ')}`);
    console.log(JSON.stringify(results, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.stack || error); process.exit(1); });

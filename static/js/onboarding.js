(function () {
    const overlay = document.getElementById('onboarding-overlay');
    if (!overlay) return;

    const dialog = overlay.querySelector('.onboarding-dialog');
    const panels = [...overlay.querySelectorAll('[data-onboarding-panel]')];
    const markers = [...overlay.querySelectorAll('[data-onboarding-marker]')];
    const backButton = document.getElementById('onboarding-back');
    const nextButton = document.getElementById('onboarding-next');
    const skipButton = document.getElementById('onboarding-skip');
    const stepLabel = document.getElementById('onboarding-step-label');
    const keyInput = document.getElementById('onboarding-api-key');
    const keyToggle = document.getElementById('onboarding-key-toggle');
    const keySave = document.getElementById('onboarding-key-save');
    const keyMessage = document.getElementById('onboarding-key-message');
    const aiState = document.getElementById('onboarding-ai-state');
    const guideOverlay = document.getElementById('deepseek-guide-overlay');
    const guideDialog = guideOverlay?.querySelector('.deepseek-guide-dialog');
    const guideOpen = document.getElementById('open-deepseek-guide');
    const guideClose = document.getElementById('close-deepseek-guide');
    const guideBack = document.getElementById('deepseek-guide-back');
    const guideNext = document.getElementById('deepseek-guide-next');
    const guideCount = document.getElementById('deepseek-guide-count');
    const guideTitle = document.getElementById('deepseek-guide-title');
    const guideImage = document.getElementById('deepseek-guide-image');
    const guideDescription = document.getElementById('deepseek-guide-description');
    const guideWarning = document.getElementById('deepseek-guide-warning');
    const guideDots = document.getElementById('deepseek-guide-dots');
    const storageKey = 'cet-onboarding-v1';
    let step = 0;
    let csrf = '';
    let configured = false;
    let lastFocus = null;
    let opened = false;
    let guideStep = 0;
    let guideLastFocus = null;
    const guideSteps = [
        {
            title: '进入 DeepSeek 开放平台',
            description: '打开 DeepSeek 官网，选择“API 开放平台”。如果尚未登录，请先注册或登录 DeepSeek 账户。',
            warning: '普通聊天与开放平台属于同一 DeepSeek 服务，但本站需要开放平台创建的 API Key。',
            alt: 'DeepSeek 官网首页，页面下方有 API 开放平台入口',
        },
        {
            title: '在左侧找到 API keys',
            description: '登录开放平台后，在左侧导航中选择“API keys”，进入密钥管理页面。',
            warning: '如果手机页面没有显示左侧导航，先打开页面菜单，再选择 API keys。',
            alt: 'DeepSeek 开放平台左侧导航，其中包含 API keys 入口',
        },
        {
            title: '创建并立即复制 API Key',
            description: '点击“创建 API key”，填写便于识别的名称。创建后立即复制以 sk- 开头的完整内容，再回到学习台粘贴。',
            warning: '完整 Key 通常只在创建时显示一次。不要截图、公开或发给他人；本站也不会再次回显完整 Key。',
            alt: 'DeepSeek API keys 页面，右上角有创建 API key 按钮',
        },
        {
            title: '确认账户余额可以调用',
            description: '在“用量信息”查看余额。余额不足时前往充值页补充；回到学习台后点击“验证并保存”。',
            warning: '充值金额由你自行决定。本站会记录本机调用用量与估算费用，但不等同于 DeepSeek 的完整账单。',
            alt: 'DeepSeek 用量信息页面，显示账户余额与充值入口',
        },
    ];

    function readState() {
        try { return localStorage.getItem(storageKey); }
        catch (_) { return window.__cetOnboardingSeen ? 'session' : ''; }
    }

    function saveState(status) {
        const value = JSON.stringify({version: 1, status, saved_at: new Date().toISOString()});
        try { localStorage.setItem(storageKey, value); }
        catch (_) { window.__cetOnboardingSeen = true; }
    }

    function focusableElements() {
        return [...dialog.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),summary,[tabindex]:not([tabindex="-1"])')]
            .filter(element => !element.closest('[hidden]') && element.offsetParent !== null);
    }

    function guideFocusableElements() {
        if (!guideDialog) return [];
        return [...guideDialog.querySelectorAll('a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])')]
            .filter(element => element.offsetParent !== null);
    }

    function renderGuideStep(nextStep) {
        guideStep = Math.min(guideSteps.length - 1, Math.max(0, Number(nextStep) || 0));
        const item = guideSteps[guideStep];
        const source = guideDialog?.getAttribute(`data-guide-src-${guideStep}`) || '';
        guideCount.textContent = `第 ${guideStep + 1} 步，共 ${guideSteps.length} 步`;
        guideTitle.textContent = item.title;
        guideDescription.textContent = item.description;
        guideWarning.textContent = item.warning;
        guideImage.src = source;
        guideImage.alt = item.alt;
        guideBack.disabled = guideStep === 0;
        guideNext.textContent = guideStep === guideSteps.length - 1 ? '我已了解，返回填写' : '下一步';
        guideDots.innerHTML = guideSteps.map((_, index) => `<span${index === guideStep ? ' class="is-current" aria-current="step"' : ''}><span class="sr-only">第 ${index + 1} 步</span></span>`).join('');
    }

    function openGuide() {
        if (!guideOverlay || !guideDialog) return;
        guideLastFocus = document.activeElement;
        dialog.inert = true;
        dialog.setAttribute('aria-hidden', 'true');
        renderGuideStep(0);
        guideOverlay.hidden = false;
        requestAnimationFrame(() => guideDialog.focus({preventScroll: true}));
    }

    function closeGuide() {
        if (!guideOverlay || guideOverlay.hidden) return;
        guideOverlay.hidden = true;
        dialog.inert = false;
        dialog.removeAttribute('aria-hidden');
        if (guideLastFocus && document.contains(guideLastFocus)) guideLastFocus.focus();
    }

    function updateStep(nextStep) {
        step = Math.min(panels.length - 1, Math.max(0, Number(nextStep) || 0));
        panels.forEach((panel, index) => {
            const active = index === step;
            panel.hidden = !active;
            panel.classList.toggle('is-active', active);
            panel.setAttribute('aria-hidden', active ? 'false' : 'true');
            const title = panel.querySelector('h2');
            if (title) {
                title.id = `onboarding-step-title-${index}`;
                title.setAttribute('tabindex', '-1');
                if (active) dialog.setAttribute('aria-labelledby', title.id);
            }
        });
        markers.forEach((marker, index) => {
            marker.classList.toggle('is-current', index === step);
            marker.classList.toggle('is-complete', index < step);
            if (index === step) marker.setAttribute('aria-current', 'step');
            else marker.removeAttribute('aria-current');
        });
        stepLabel.textContent = `第 ${step + 1} 步，共 ${panels.length} 步`;
        backButton.disabled = step === 0;
        nextButton.textContent = step === panels.length - 1 ? '完成引导' : '下一步';
        requestAnimationFrame(() => {
            const activePanel = panels[step];
            if (step === 1 && !configured) keyInput.focus();
            else activePanel.querySelector('h2')?.focus({preventScroll: true});
        });
    }

    function renderAIStatus(status) {
        configured = Boolean(status?.configured);
        aiState.classList.toggle('is-ready', configured);
        const strong = aiState.querySelector('strong');
        const help = aiState.querySelector('p');
        if (status?.recovery_required) {
            strong.textContent = '旧密钥需要重新验证';
            help.textContent = status.key_suffix ? `原密钥尾号 ${status.key_suffix}，重新填写后即可恢复。` : '重新填写后即可恢复 AI 能力。';
        } else if (configured) {
            strong.textContent = `DeepSeek 已连接${status.key_suffix ? ` · 尾号 ${status.key_suffix}` : ''}`;
            help.textContent = `${status.model || '当前模型'} 已在全站生效，可以直接进入下一步。`;
            keyMessage.textContent = '现有配置保持不变，也可以在“我的”中替换。';
        } else {
            strong.textContent = '尚未配置 DeepSeek';
            help.textContent = '基础学习不受影响；填写后 AI 功能会立即生效。';
        }
    }

    async function loadAIStatus() {
        try {
            const status = await api('/api/ai/config/status');
            csrf = status.csrf_token || '';
            renderAIStatus(status);
        } catch (error) {
            aiState.querySelector('strong').textContent = '暂时无法读取 AI 配置';
            aiState.querySelector('p').textContent = '可以继续浏览引导，稍后到“我的”中配置。';
        }
    }

    function open(options = {}) {
        if (opened) return;
        opened = true;
        lastFocus = document.activeElement;
        overlay.hidden = false;
        document.body.classList.add('has-modal-open');
        updateStep(options.step || 0);
        dialog.focus({preventScroll: true});
        loadAIStatus();
    }

    function close(status = '') {
        if (!opened) return;
        if (status) saveState(status);
        overlay.hidden = true;
        document.body.classList.remove('has-modal-open');
        opened = false;
        if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
    }

    nextButton.addEventListener('click', () => {
        if (step < panels.length - 1) updateStep(step + 1);
        else {
            close('completed');
            showToast('引导已完成，先从今天最重要的任务开始吧。', 'success');
        }
    });
    backButton.addEventListener('click', () => updateStep(step - 1));
    skipButton.addEventListener('click', () => {
        close('skipped');
        showToast('已跳过，可随时在“我的”中重新查看。', 'info');
    });

    keyToggle.addEventListener('click', () => {
        const willShow = keyInput.type === 'password';
        keyInput.type = willShow ? 'text' : 'password';
        keyToggle.textContent = willShow ? '隐藏' : '显示';
        keyToggle.setAttribute('aria-pressed', willShow ? 'true' : 'false');
    });

    keySave.addEventListener('click', async () => {
        const value = keyInput.value.trim();
        if (!value) {
            keyMessage.textContent = '请先填写完整的 API Key，或直接进入下一步。';
            keyInput.focus();
            return;
        }
        if (!csrf) await loadAIStatus();
        if (!csrf) {
            keyMessage.textContent = '本地安全令牌读取失败，请稍后到“我的”中配置。';
            return;
        }
        keySave.disabled = true;
        keyMessage.textContent = '正在通过 DeepSeek 余额接口验证…';
        try {
            const result = await api('/api/ai/config/verify-save', {
                method: 'POST',
                headers: {'X-CSRF-Token': csrf},
                body: JSON.stringify({api_key: value}),
            });
            keyInput.value = '';
            renderAIStatus(result);
            keyMessage.textContent = '验证成功，AI 已在全站即时启用。';
            showToast('DeepSeek 已连接。', 'success');
        } catch (error) {
            keyMessage.textContent = error.message || '验证失败，原有配置没有改变。';
        } finally {
            keySave.disabled = false;
        }
    });

    guideOpen?.addEventListener('click', openGuide);
    guideClose?.addEventListener('click', closeGuide);
    guideBack?.addEventListener('click', () => renderGuideStep(guideStep - 1));
    guideNext?.addEventListener('click', () => {
        if (guideStep < guideSteps.length - 1) renderGuideStep(guideStep + 1);
        else closeGuide();
    });
    guideOverlay?.addEventListener('click', event => { if (event.target === guideOverlay) closeGuide(); });
    guideOverlay?.addEventListener('keydown', event => {
        if (event.key === 'Escape') { event.preventDefault(); closeGuide(); return; }
        if (event.key !== 'Tab') return;
        const focusable = guideFocusableElements();
        if (!focusable.length) return;
        const first = focusable[0], last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });

    overlay.addEventListener('click', event => {
        if (event.target === overlay) close('skipped');
    });
    overlay.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            event.preventDefault();
            close('skipped');
            return;
        }
        if (event.key !== 'Tab') return;
        const focusable = focusableElements();
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });

    window.CETOnboarding = {open, close};
    document.addEventListener('cet:open-onboarding', () => open({step: 0}));
    document.addEventListener('DOMContentLoaded', () => {
        document.getElementById('open-onboarding')?.addEventListener('click', () => open({step: 0}));
        const manual = new URLSearchParams(window.location.search).get('onboarding') === '1';
        const isHome = window.location.pathname === '/';
        if (manual || (isHome && !readState())) window.setTimeout(() => open({step: 0}), manual ? 0 : 260);
    });
})();

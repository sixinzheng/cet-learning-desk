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
    const storageKey = 'cet-onboarding-v1';
    let step = 0;
    let csrf = '';
    let configured = false;
    let lastFocus = null;
    let opened = false;

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

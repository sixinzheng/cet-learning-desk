(async function () {
    const root = document.getElementById('profile-app');
    if (!root) return;
    const $ = id => document.getElementById(id);
    let csrf = '';
    let wordbookPreview = null;
    let previewWords = [];
    let previewLastFocus = null;
    let skills = [];

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>'"]/g, char => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
        })[char]);
    }

    function wordbookVisual(book) {
        const name = String(book.name || '学习词库');
        if (name === '我的收藏') return {code: 'FAV', kind: 'fav', subtitle: 'PERSONAL COLLECTION'};
        const exam = name.includes('专八') ? 'TEM-8' : (name.includes('六级') ? 'CET-6' : (name.includes('四级') ? 'CET-4' : 'VOC'));
        const edition = name.includes('完整') ? 'COMPLETE' : (name.includes('高频') ? 'CORE' : 'STUDY');
        return {code: exam, kind: exam.toLowerCase().replace('-', ''), subtitle: edition + ' VOCABULARY'};
    }

    function ensureWordbookPreview() {
        if (wordbookPreview) return wordbookPreview;
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.hidden = true;
        overlay.innerHTML = '<div class="modal-card wb-modal" role="dialog" aria-modal="true" aria-labelledby="wb-modal-title" tabindex="-1"><div class="modal-header"><h3 class="wb-modal-title" id="wb-modal-title">词库预览</h3><button type="button" class="icon-button" data-close="1" aria-label="关闭">×</button></div><div class="wb-modal-search"><input type="search" class="spelling-input" placeholder="搜索词库中的单词…" aria-label="搜索单词"></div><div class="wb-modal-body"><p class="muted">加载中…</p></div></div>';
        document.body.appendChild(overlay);
        const close = () => { overlay.hidden = true; if (previewLastFocus && document.contains(previewLastFocus)) previewLastFocus.focus(); };
        overlay.querySelector('[data-close]').addEventListener('click', close);
        overlay.addEventListener('click', event => { if (event.target === overlay) close(); });
        overlay.addEventListener('keydown', event => {
            if (event.key === 'Escape') { event.preventDefault(); close(); return; }
            if (event.key !== 'Tab') return;
            const focusable = [...overlay.querySelectorAll('button:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])')].filter(element => element.offsetParent !== null);
            if (!focusable.length) return;
            const first = focusable[0], last = focusable.at(-1);
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        });
        overlay.querySelector('.wb-modal-search input').addEventListener('input', event => {
            const query = event.target.value.trim().toLowerCase();
            renderPreviewRows(query ? previewWords.filter(word => word.word.toLowerCase().includes(query)) : previewWords);
        });
        wordbookPreview = overlay;
        return overlay;
    }

    function renderPreviewRows(list) {
        const overlay = ensureWordbookPreview();
        const body = overlay.querySelector('.wb-modal-body');
        if (!list.length) {
            body.innerHTML = '<div class="empty-state wb-preview-empty"><h3>没有匹配的单词</h3><p>换一个英文关键词再试试。</p></div>';
            return;
        }
        const meaningOf = word => {
            try { return JSON.parse(word.meanings || '[]').slice(0, 2).join('；'); }
            catch (_) { return word.meanings || ''; }
        };
        const statusTag = word => {
            const status = word.status || '陌生';
            const className = status === '熟记' ? ' wb-status--mastered' : (status === '陌生' ? ' wb-status--new' : '');
            return '<span class="wb-status' + className + '">' + escapeHtml(status) + '</span>';
        };
        body.innerHTML = '<div class="wb-word-list">' + list.map(word => (
            '<div class="wb-word-row"><div class="wb-word-main"><span class="wb-word-en">' + escapeHtml(word.word) + '</span>' +
            (word.phonetic ? '<span class="wb-word-phonetic">' + escapeHtml(word.phonetic) + '</span>' : '') +
            '<button class="pronounce-button wb-pronounce" type="button" data-pronounce="' + escapeHtml(word.word) + '" aria-label="播放 ' + escapeHtml(word.word) + ' 的发音">发音</button>' +
            '</div><div class="wb-word-detail"><p class="wb-word-meaning">' + escapeHtml(meaningOf(word)) + '</p></div>' + statusTag(word) + '</div>'
        )).join('') + '</div><p class="muted wb-count-note">共 ' + list.length + ' 词</p>';
        body.querySelectorAll('[data-pronounce]').forEach(button => button.addEventListener('click', () => speakEnglish(button.dataset.pronounce)));
    }

    function renderStatus(status) {
        root.dataset.aiConfigured = status.configured ? 'true' : 'false';
        if (status.recovery_required) {
            $('ai-state').textContent = `需要重新验证一次${status.key_suffix ? ` · 原尾号 ${status.key_suffix}` : ''}`;
            $('ai-help').textContent = '旧密钥记录仍在，但 Windows 已无法解密。重新填写并验证后会改由 Windows 凭据管理器持久保存。';
        } else {
            $('ai-state').textContent = status.configured ? `已连接 · 密钥尾号 ${status.key_suffix}` : '尚未配置 DeepSeek';
            $('ai-help').textContent = status.configured
                ? `全站 AI 已启用 · ${status.storage_backend === 'credential_manager' ? 'Windows 凭据管理器持久保存' : '本机加密存储'}`
                : '基础学习不受影响；配置后，全站 AI 功能会立即生效。';
        }
        $('ai-model').textContent = status.model || 'deepseek-v4-flash';
        $('ai-tracked-cost').textContent = `¥${Number(status.tracked_cost_cny_84 || 0).toFixed(6)}`;
        $('ai-verified-at').textContent = status.verified_at ? status.verified_at.replace('T', ' ') : '尚未验证';
        $('ai-service-status').classList.toggle('is-ready', Boolean(status.configured));
        $('ai-balance-refresh').disabled = !status.configured;
        $('ai-key-delete').disabled = !status.key_material_present;
    }

    function renderSkills(items) {
        skills = items || [];
        const box = $('profile-skills');
        if (!skills.length) {
            box.innerHTML = '<div class="empty-state"><h3>暂无 Skill</h3><p>可先创建一个自定义 Skill。</p></div>';
            return;
        }
        box.innerHTML = skills.map(skill => {
            const tag = skill.is_builtin ? '内置' : '自定义';
            const instructions = skill.user_instructions
                ? `<p class="skill-item__rules">已补充规则：${escapeHtml(skill.user_instructions.slice(0, 90))}${skill.user_instructions.length > 90 ? '…' : ''}</p>`
                : '<p class="skill-item__rules">尚未添加个人补充规则</p>';
            return `<article class="skill-item${skill.enabled ? ' is-enabled' : ''}" data-skill="${escapeHtml(skill.slug)}">
                <div class="skill-item__index"><span>${tag}</span><strong>${escapeHtml(skill.display_name)}</strong></div>
                <div class="skill-item__copy"><p>${escapeHtml(skill.description)}</p>${instructions}</div>
                <div class="skill-item__actions">
                    <button class="skill-switch" type="button" role="switch" aria-checked="${skill.enabled}" data-skill-toggle="${escapeHtml(skill.slug)}"><span>${skill.enabled ? '已启用' : '已关闭'}</span></button>
                    <a class="text-link" href="/control?skill=${encodeURIComponent(skill.slug)}">去控制优化</a>
                    ${skill.is_builtin ? '' : `<button class="text-button skill-delete" type="button" data-skill-delete="${escapeHtml(skill.slug)}">删除</button>`}
                </div>
            </article>`;
        }).join('');
        box.querySelectorAll('[data-skill-toggle]').forEach(button => button.addEventListener('click', async () => {
            const current = skills.find(skill => skill.slug === button.dataset.skillToggle);
            if (!current) return;
            button.disabled = true;
            try {
                await api(`/api/ai/skills/${encodeURIComponent(current.slug)}`, {
                    method: 'PUT', headers: {'X-CSRF-Token': csrf},
                    body: JSON.stringify({enabled: !current.enabled}),
                });
                await loadSkills();
                showToast(`${current.display_name}已${current.enabled ? '关闭' : '启用'}。`, 'success');
            } catch (error) { showToast(error.message || 'Skill 状态保存失败。', 'error'); }
            finally { button.disabled = false; }
        }));
        box.querySelectorAll('[data-skill-delete]').forEach(button => button.addEventListener('click', async () => {
            const current = skills.find(skill => skill.slug === button.dataset.skillDelete);
            if (!current || !window.confirm(`删除自定义 Skill“${current.display_name}”？`)) return;
            try {
                await api(`/api/ai/skills/${encodeURIComponent(current.slug)}`, {method: 'DELETE', headers: {'X-CSRF-Token': csrf}});
                await loadSkills(); showToast('自定义 Skill 已删除。', 'success');
            } catch (error) { showToast(error.message || '删除失败。', 'error'); }
        }));
    }

    async function loadSkills() {
        const data = await api('/api/ai/skills');
        csrf = csrf || data.csrf_token;
        renderSkills(data.skills || []);
    }

    function renderWordbooks(books) {
        var box = $('profile-wordbooks');
        if (!books.length) { box.innerHTML = '<div class="empty-state"><h3>暂无词库</h3><p>当前数据库中还没有可用词库。</p></div>'; return; }
        box.innerHTML = '<div class="wb-accordion">' + books.map(function (book) {
            var pct = book.total_words ? Math.round((book.mastered + book.known) / book.total_words * 100) : 0;
            var curTag = book.is_current ? '<span class="wb-current">当前</span>' : '';
            var extra = book.name === '我的收藏' ? ' wb-card--fav' : '';
            var visual = wordbookVisual(book);
            var panelId = 'wordbook-panel-' + book.id;
            return '<article class="wb-card' + (book.is_current ? ' wb-card--current' : '') + extra + '">' +
                '<button class="wb-accordion__trigger" type="button" aria-expanded="false" aria-controls="' + panelId + '">' +
                '<span class="wb-cover wb-cover--' + visual.kind + '" aria-hidden="true"><span>' + visual.code + '</span><strong>' + escapeHtml(book.name) + '</strong><small>' + visual.subtitle + '</small></span>' +
                '<span class="wb-card-summary"><span class="wb-card-title"><strong>' + escapeHtml(book.name) + '</strong>' + curTag + '</span><span class="wb-card-desc">' + escapeHtml(book.description || '本地词库') + '</span><span class="wb-progress" aria-label="总进度 ' + pct + '%"><span style="width:' + pct + '%"></span></span></span>' +
                '<span class="wb-card-measure"><strong>' + book.total_words + '</strong><small>词</small><span class="wb-chevron" aria-hidden="true"></span></span></button>' +
                '<div class="wb-accordion__panel" id="' + panelId + '" hidden><div class="wb-status-row"><span>熟记 <b>' + book.mastered + '</b></span><span>掌握 <b>' + book.known + '</b></span><span>学习中 <b>' + book.learning + '</b></span><span>总进度 <b>' + pct + '%</b></span></div><div class="wb-actions"><button class="btn btn-secondary btn-sm" type="button" data-preview="' + book.id + '" data-name="' + escapeHtml(book.name) + '">预览词汇</button>' + (book.is_current ? '<span class="wb-current-note">今日学习正在使用</span>' : '<button class="btn btn-primary btn-sm" type="button" data-current="' + book.id + '">设为当前</button>') + '</div></div></article>';
        }).join('') + '</div>';
        box.querySelectorAll('.wb-accordion__trigger').forEach(function (trigger) {
            trigger.addEventListener('click', function () {
                var willOpen = trigger.getAttribute('aria-expanded') !== 'true';
                box.querySelectorAll('.wb-accordion__trigger').forEach(function (other) {
                    other.setAttribute('aria-expanded', 'false');
                    document.getElementById(other.getAttribute('aria-controls')).hidden = true;
                });
                if (willOpen) {
                    trigger.setAttribute('aria-expanded', 'true');
                    document.getElementById(trigger.getAttribute('aria-controls')).hidden = false;
                }
            });
        });
        // 设为当前词库
        box.querySelectorAll('[data-current]').forEach(function (btn) {
            btn.addEventListener('click', async function () {
                btn.disabled = true;
                try {
                    await api('/api/words/current-wordbook', {method: 'PUT', body: JSON.stringify({book_id: Number(btn.dataset.current)})});
                    showToast('已设为当前学习词库。', 'success');
                    // 重新拉取词库列表刷新
                    var fresh = await api('/api/words/wordbooks');
                    renderWordbooks(fresh.wordbooks || []);
                } catch (_) { showToast('设置失败，请重试。', 'error'); }
                finally { btn.disabled = false; }
            });
        });
        var overlay = ensureWordbookPreview();
        var searchInput = overlay.querySelector('.wb-modal-search input');
        box.querySelectorAll('[data-preview]').forEach(function (btn) {
            btn.addEventListener('click', async function () {
                var id = btn.dataset.preview;
                overlay.querySelector('.wb-modal-title').textContent = btn.dataset.name;
                var body = overlay.querySelector('.wb-modal-body');
                searchInput.value = '';
                body.innerHTML = '<p class="muted">加载中…</p>';
                previewLastFocus = btn;
                overlay.hidden = false;
                requestAnimationFrame(() => overlay.querySelector('.wb-modal')?.focus());
                btn.disabled = true;
                try {
                    var data = await api('/api/words/wordbooks/' + id + '/words?limit=10000');
                    previewWords = data.words || [];
                    overlay.querySelector('.wb-modal-title').textContent = btn.dataset.name + '（共 ' + previewWords.length + ' 词）';
                    renderPreviewRows(previewWords);
                } catch (_) { body.innerHTML = '<p class="muted">加载失败，请重试。</p>'; }
                finally { btn.disabled = false; }
            });
        });
    }

    function renderBalance(balance) {
        const items = balance?.balances || [];
        $('ai-balance').textContent = items.length
            ? items.map(item => `${item.currency === 'CNY' ? '¥' : '$'}${item.total}`).join(' / ')
            : '未返回余额';
    }

    async function refreshStatus(withBalance = false) {
        const status = await api('/api/ai/config/status');
        csrf = status.csrf_token;
        renderStatus(status);
        if (withBalance && status.configured) renderBalance(await api('/api/ai/balance'));
        return status;
    }

    try {
        const [books] = await Promise.all([
            api('/api/words/wordbooks'), refreshStatus(true), loadSkills(),
        ]);
        renderWordbooks(books.wordbooks || []);
        setRegionState(root, 'ready');
    } catch (_) {
        setRegionState(root, 'error', '部分设置加载失败，请刷新页面重试。');
    }

    $('ai-key-toggle').addEventListener('click', () => {
        const visible = $('ai-key-input').type === 'text';
        $('ai-key-input').type = visible ? 'password' : 'text';
        $('ai-key-toggle').textContent = visible ? '显示' : '隐藏';
        $('ai-key-toggle').setAttribute('aria-pressed', visible ? 'false' : 'true');
    });
    $('ai-key-save').addEventListener('click', async () => {
        const key = $('ai-key-input').value.trim(), message = $('ai-config-message');
        if (!key) { message.textContent = '请先填写完整的 API Key。'; return; }
        $('ai-key-save').disabled = true; message.textContent = '正在通过 DeepSeek 验证余额与密钥…';
        try {
            const result = await api('/api/ai/config/verify-save', {method: 'POST', headers: {'X-CSRF-Token': csrf}, body: JSON.stringify({api_key: key})});
            $('ai-key-input').value = ''; renderBalance(result.balance); await refreshStatus(false);
            message.textContent = '验证成功，AI 已在全站即时启用。'; showToast('DeepSeek 已连接。', 'success');
        } catch (error) { message.textContent = error.message || '验证失败，原配置未改变。'; }
        finally { $('ai-key-save').disabled = false; }
    });
    $('ai-balance-refresh').addEventListener('click', async () => {
        $('ai-balance-refresh').disabled = true;
        try { renderBalance(await api('/api/ai/balance')); $('ai-config-message').textContent = '余额已刷新。'; }
        catch (error) { $('ai-config-message').textContent = error.message; }
        finally { $('ai-balance-refresh').disabled = false; }
    });
    $('ai-key-delete').addEventListener('click', async () => {
        if (!window.confirm('删除本机保存的 API Key？历史对话、记忆和调用账单会保留。')) return;
        try {
            await api('/api/ai/config', {method: 'DELETE', headers: {'X-CSRF-Token': csrf}});
            $('ai-balance').textContent = '未读取'; await refreshStatus(false);
            $('ai-config-message').textContent = '密钥已删除，后续 AI 调用已关闭。'; showToast('AI 配置已删除。', 'success');
        } catch (error) { $('ai-config-message').textContent = error.message; }
    });
    $('skill-create-form').addEventListener('submit', async event => {
        event.preventDefault();
        const form = event.currentTarget;
        const state = $('skill-create-state');
        const payload = {
            display_name: $('skill-name').value.trim(),
            description: $('skill-description').value.trim(),
            user_instructions: $('skill-instructions').value.trim(),
        };
        if (!payload.display_name) { state.textContent = '请填写 Skill 名称。'; return; }
        const button = event.submitter || form.querySelector('button[type="submit"]');
        button.disabled = true; state.textContent = '正在创建…';
        try {
            const result = await api('/api/ai/skills', {method: 'POST', headers: {'X-CSRF-Token': csrf}, body: JSON.stringify(payload)});
            form.reset(); await loadSkills(); state.textContent = '已创建，可进入控制台继续优化。';
            showToast('自定义 Skill 已创建。', 'success');
            const link = document.querySelector(`[data-skill="${CSS.escape(result.skill.slug)}"] a`);
            link?.focus();
        } catch (error) { state.textContent = error.message || '创建失败，请重试。'; }
        finally { button.disabled = false; }
    });
})();

(async function () {
    const root = document.getElementById('profile-app');
    if (!root) return;
    const $ = id => document.getElementById(id);
    let csrf = '';
    let wordbookPreview = null;
    let previewWords = [];
    let previewLastFocus = null;
    let skills = [];
    let supportLastFocus = null;
    let updateLastFocus = null;
    let updateRelease = null;
    let deviceSyncResultLastFocus = null;
    let lastShownSyncTransaction = '';

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

    function initSupportModal() {
        const overlay = $('support-modal');
        const trigger = $('support-author-button');
        if (!overlay || !trigger) return;
        const dialog = overlay.querySelector('[role="dialog"]');
        const close = () => {
            overlay.hidden = true;
            document.body.classList.remove('has-modal-open');
            if (supportLastFocus && document.contains(supportLastFocus)) supportLastFocus.focus();
        };
        const open = () => {
            supportLastFocus = document.activeElement;
            overlay.hidden = false;
            document.body.classList.add('has-modal-open');
            requestAnimationFrame(() => dialog.focus());
        };
        trigger.addEventListener('click', open);
        overlay.querySelectorAll('[data-support-close]').forEach(button => button.addEventListener('click', close));
        overlay.addEventListener('click', event => { if (event.target === overlay) close(); });
        overlay.addEventListener('keydown', event => {
            if (event.key === 'Escape') { event.preventDefault(); close(); return; }
            if (event.key !== 'Tab') return;
            const focusable = [...dialog.querySelectorAll('button:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])')]
                .filter(element => element.offsetParent !== null);
            if (!focusable.length) return;
            const first = focusable[0], last = focusable.at(-1);
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        });
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
            '<button class="pronounce-button wb-pronounce" type="button" data-pronounce="' + escapeHtml(word.word) + '" data-word-id="' + Number(word.id) + '" data-audio-url="' + escapeHtml(word.audio_url || '') + '" aria-label="播放 ' + escapeHtml(word.word) + ' 的发音">发音</button>' +
            '</div><div class="wb-word-detail"><p class="wb-word-meaning">' + escapeHtml(meaningOf(word)) + '</p></div>' + statusTag(word) + '</div>'
        )).join('') + '</div><p class="muted wb-count-note">共 ' + list.length + ' 词</p>';
        body.querySelectorAll('[data-pronounce]').forEach(button => button.addEventListener('click', () => speakEnglish(button.dataset.pronounce, {wordId: button.dataset.wordId, audioUrl: button.dataset.audioUrl})));
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
        const enabledCount = skills.filter(skill => skill.enabled).length;
        const count = $('skill-summary-count');
        if (count) count.textContent = `已启用 ${enabledCount} / 共 ${skills.length} 个`;
        if (!skills.length) {
            box.innerHTML = '<div class="empty-state"><h3>暂无 Skill</h3><p>可先创建一个自定义 Skill。</p></div>';
            return;
        }
        box.innerHTML = skills.map(skill => {
            const tag = skill.is_builtin ? '内置' : '自定义';
            const instructions = skill.user_instructions
                ? `<p class="skill-item__rules">已补充规则：${escapeHtml(skill.user_instructions.slice(0, 90))}${skill.user_instructions.length > 90 ? '…' : ''}</p>`
                : '<p class="skill-item__rules">尚未添加个人补充规则</p>';
            const panelId = `skill-panel-${escapeHtml(skill.slug)}`;
            return `<details class="skill-item${skill.enabled ? ' is-enabled' : ''}" data-skill="${escapeHtml(skill.slug)}">
                <summary aria-controls="${panelId}" aria-expanded="false">
                    <span class="skill-item__index"><span>${tag}</span><strong>${escapeHtml(skill.display_name)}</strong></span>
                    <span class="skill-item__purpose">${escapeHtml(skill.description)}</span>
                    <span class="skill-item__state${skill.enabled ? ' is-on' : ''}">${skill.enabled ? '已启用' : '已关闭'}</span>
                    <span class="skill-item__chevron" aria-hidden="true"></span>
                </summary>
                <div class="skill-item__panel" id="${panelId}">
                    <div class="skill-item__copy"><p>${escapeHtml(skill.description)}</p>${instructions}</div>
                    <div class="skill-item__actions">
                        <button class="skill-switch" type="button" role="switch" aria-checked="${skill.enabled}" data-skill-toggle="${escapeHtml(skill.slug)}"><span>${skill.enabled ? '已启用' : '已关闭'}</span></button>
                        <a class="text-link" href="/control?skill=${encodeURIComponent(skill.slug)}">去控制优化</a>
                        ${skill.is_builtin ? '' : `<button class="text-button skill-delete" type="button" data-skill-delete="${escapeHtml(skill.slug)}">删除</button>`}
                    </div>
                </div>
            </details>`;
        }).join('');
        box.querySelectorAll('.skill-item').forEach(item => {
            const summary = item.querySelector(':scope > summary');
            const syncExpanded = () => summary?.setAttribute('aria-expanded', item.open ? 'true' : 'false');
            item.addEventListener('toggle', () => {
                syncExpanded();
                if (!item.open) return;
                box.querySelectorAll('.skill-item[open]').forEach(other => {
                    if (other !== item) other.open = false;
                });
            });
            syncExpanded();
        });
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

    function platformLabel(platform) {
        return platform === 'windows' ? 'Windows 安装版' : (platform === 'android' ? 'Android 安装版' : '源码浏览器版');
    }

    function formatBytes(value) {
        const bytes = Number(value || 0);
        if (!bytes) return '未提供体积';
        if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
        return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    function renderUpdateProgress(progress) {
        if (!progress) return;
        const holder = $('update-progress');
        holder.hidden = !['backing_up', 'backup_ready', 'ready_for_native', 'checking_manifest', 'manifest_retry', 'downloading', 'download_retry', 'verifying', 'installing'].includes(progress.stage);
        const percent = Math.max(0, Math.min(100, Number(progress.percent || 0)));
        holder.setAttribute('aria-valuenow', String(Math.round(percent)));
        $('update-progress-bar').style.setProperty('--update-progress-scale', String(percent / 100));
        if (progress.message) $('update-state-copy').textContent = progress.message;
        $('update-state').dataset.state = progress.stage || 'idle';
    }

    function renderUpdateStatus(data) {
        $('update-current-version').textContent = `v${data.current_version || root.dataset.appVersion}`;
        $('update-platform').textContent = platformLabel(data.platform || root.dataset.appPlatform);
        $('update-release-link').href = data.release_url || 'https://github.com/sixinzheng/cet-learning-desk/releases';
        $('update-release-link').hidden = false;
        if (!data.update_available) {
            $('update-state-title').textContent = '已经是最新稳定版';
            $('update-state-copy').textContent = `当前 v${data.current_version}，没有发现更高的稳定版本。`;
            $('update-check').textContent = '重新检查';
        } else if (!data.install_supported) {
            $('update-state-title').textContent = `稳定版 v${data.latest_version} 可用`;
            $('update-state-copy').textContent = '源码浏览器版不会改动 Git 工作区，请从 Release 页面下载安装包。';
            $('update-check').textContent = '重新检查';
        } else {
            $('update-state-title').textContent = `发现稳定版 v${data.latest_version}`;
            $('update-state-copy').textContent = `发布于 ${String(data.published_at || '').slice(0, 10) || '日期未提供'} · ${formatBytes(data.download_size)}`;
            showUpdateModal(data);
        }
        renderUpdateProgress(data.progress);
    }

    function closeUpdateModal() {
        const overlay = $('update-modal');
        overlay.hidden = true;
        document.body.classList.remove('has-modal-open');
        if (updateLastFocus && document.contains(updateLastFocus)) updateLastFocus.focus();
    }

    function showUpdateModal(data) {
        updateRelease = data;
        if (document.activeElement && document.activeElement !== document.body) {
            updateLastFocus = document.activeElement;
        }
        updateLastFocus ||= $('update-check');
        $('update-modal-meta').textContent = `v${data.current_version} → v${data.latest_version} · ${formatBytes(data.download_size)} · ${String(data.published_at || '').slice(0, 10) || '发布日期未提供'}`;
        $('update-modal-notes').textContent = data.release_notes || '本次发布未提供更新说明。';
        $('update-modal').hidden = false;
        document.body.classList.add('has-modal-open');
        requestAnimationFrame(() => $('update-modal').querySelector('[role="dialog"]')?.focus());
    }

    function initUpdateCenter() {
        const overlay = $('update-modal');
        const dialog = overlay?.querySelector('[role="dialog"]');
        if (!overlay || !dialog) return;
        overlay.querySelectorAll('[data-update-close]').forEach(button => button.addEventListener('click', closeUpdateModal));
        overlay.addEventListener('click', event => { if (event.target === overlay) closeUpdateModal(); });
        overlay.addEventListener('keydown', event => {
            if (event.key === 'Escape') { event.preventDefault(); closeUpdateModal(); return; }
            if (event.key !== 'Tab') return;
            const focusable = [...dialog.querySelectorAll('button:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])')].filter(element => element.offsetParent !== null);
            if (!focusable.length) return;
            const first = focusable[0], last = focusable.at(-1);
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        });
        $('update-check').addEventListener('click', async () => {
            const button = $('update-check');
            updateLastFocus = button;
            button.disabled = true;
            button.textContent = '正在检查…';
            $('update-state-title').textContent = '连接 GitHub 稳定发布通道';
            $('update-state-copy').textContent = '只读取公开 Release，不会下载或安装。';
            try {
                const data = await api('/api/app/update/status');
                csrf = csrf || data.csrf_token;
                renderUpdateStatus(data);
            } catch (error) {
                $('update-state').dataset.state = 'error';
                $('update-state-title').textContent = '检查失败';
                $('update-state-copy').textContent = error.message || '暂时无法读取 GitHub Release，请稍后重试。';
                button.textContent = '重试检查';
            } finally { button.disabled = false; }
        });
        $('update-install').addEventListener('click', async () => {
            if (!updateRelease) return;
            const button = $('update-install');
            button.disabled = true;
            button.textContent = '正在校验并备份…';
            $('update-state-title').textContent = '正在保护学习数据';
            $('update-state-copy').textContent = '备份通过完整性检查前不会下载更新。';
            renderUpdateProgress({stage: 'backing_up', percent: 20});
            try {
                const prepared = await api('/api/app/update/prepare', {
                    method: 'POST', headers: {'X-CSRF-Token': csrf}, body: JSON.stringify({confirm: true}),
                });
                closeUpdateModal();
                $('update-state-title').textContent = '备份已验证';
                renderUpdateProgress(prepared.progress);
                window.location.href = prepared.native_action;
            } catch (error) {
                $('update-state').dataset.state = 'error';
                $('update-state-title').textContent = '已安全停止更新';
                $('update-state-copy').textContent = error.message || '更新准备失败，当前程序和数据均未修改。';
                button.disabled = false;
                button.textContent = '重试安全更新';
            }
        });
    }

    function initSkillDisclosure() {
        const disclosure = $('skills');
        if (!disclosure) return;
        const summary = disclosure.querySelector(':scope > summary');
        const syncExpanded = () => summary?.setAttribute('aria-expanded', disclosure.open ? 'true' : 'false');
        const revealHash = () => {
            if (window.location.hash !== '#skills') return;
            disclosure.open = true;
            requestAnimationFrame(() => disclosure.scrollIntoView({block: 'start'}));
        };
        disclosure.addEventListener('toggle', syncExpanded);
        document.querySelector('a[href="#skills"]')?.addEventListener('click', () => { disclosure.open = true; });
        window.addEventListener('hashchange', revealHash);
        syncExpanded();
        revealHash();
    }

    let deviceSyncPoll = 0;
    let pendingPairingCode = '';
    let deviceSyncCsrfPromise = null;

    const syncCategoryLabels = {
        vocabulary: '词汇状态', favorites: '收藏与词库', learning: '学习与复习',
        annotations: '阅读标注', settings: '难度与设置', notes: '笔记', ai: 'AI 内容',
    };

    function initDeviceSyncResultModal() {
        const overlay = $('device-sync-result-modal');
        if (!overlay) return;
        const dialog = overlay.querySelector('[role="dialog"]');
        const close = () => {
            overlay.hidden = true;
            document.body.classList.remove('has-modal-open');
            pollDeviceSync();
            if (deviceSyncResultLastFocus && document.contains(deviceSyncResultLastFocus)) deviceSyncResultLastFocus.focus();
        };
        overlay.querySelectorAll('[data-device-sync-result-close]').forEach(button => button.addEventListener('click', close));
        overlay.addEventListener('click', event => { if (event.target === overlay) close(); });
        overlay.addEventListener('keydown', event => {
            if (event.key === 'Escape') { event.preventDefault(); close(); return; }
            if (event.key !== 'Tab') return;
            const focusable = [...dialog.querySelectorAll('button:not([disabled]),a[href]')]
                .filter(element => element.offsetParent !== null);
            if (!focusable.length) return;
            const first = focusable[0], last = focusable.at(-1);
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        });
    }

    function openDeviceSyncResult(report) {
        if (!report) return;
        const transactionId = String(report.transaction_id || '');
        if (transactionId && transactionId === lastShownSyncTransaction) return;
        lastShownSyncTransaction = transactionId;
        const platform = root.dataset.appPlatform || 'source';
        const changes = report[platform === 'windows' ? 'desktop' : 'mobile'] || {};
        const snapshots = report.snapshots?.[platform === 'windows' ? 'desktop' : 'mobile'] || {};
        const before = snapshots.before || {};
        const after = snapshots.after || {};
        const changedRows = Object.entries(syncCategoryLabels).map(([key, label]) => {
            const item = changes[key] || {};
            const changed = Number(item.added || 0) + Number(item.updated || 0) + Number(item.deleted || 0);
            if (!changed && !Number(item.conflicts || 0)) return '';
            const details = [
                item.added ? `新增 ${Number(item.added)}` : '',
                item.updated ? `更新 ${Number(item.updated)}` : '',
                item.deleted ? `删除 ${Number(item.deleted)}` : '',
                item.conflicts ? `冲突副本 ${Number(item.conflicts)}` : '',
            ].filter(Boolean).join(' · ');
            return `<div><strong>${label}</strong><span>${escapeHtml(details)}</span><b>同步后 ${Number(item.total_after || 0)}</b></div>`;
        }).filter(Boolean);
        $('device-sync-result-list').innerHTML = changedRows.length
            ? changedRows.join('')
            : '<div class="device-sync-result-empty"><strong>两端数据已经一致</strong><span>本次检查没有发现需要新增或更新的记录。</span></div>';
        const rankBefore = before.rank_name || `Lv.${Number(before.rank || 1)}`;
        const rankAfter = after.rank_name || `Lv.${Number(after.rank || before.rank || 1)}`;
        $('device-sync-result-hero').innerHTML = `
            <div><span>段位</span><strong>${escapeHtml(rankBefore)} → ${escapeHtml(rankAfter)}</strong></div>
            <div><span>已掌握词汇</span><strong>${Number(before.mastered_words || 0)} → ${Number(after.mastered_words || 0)}</strong></div>`;
        const names = (report.devices || []).map(item => item?.device_name).filter(Boolean).join(' ↔ ');
        $('device-sync-result-meta').textContent = `${names || '电脑与手机'} · ${String(report.completed_at || '').replace('T',' ').replace('Z','')}`;
        const overlay = $('device-sync-result-modal');
        deviceSyncResultLastFocus = document.activeElement;
        overlay.hidden = false;
        document.body.classList.add('has-modal-open');
        requestAnimationFrame(() => overlay.querySelector('[role="dialog"]')?.focus());
    }

    async function ensureDeviceSyncCsrf() {
        if (csrf) return csrf;
        if (!deviceSyncCsrfPromise) {
            deviceSyncCsrfPromise = api('/api/device-sync/status')
                .then(data => {
                    csrf = data.csrf_token || '';
                    if (!csrf) throw new Error('没有取得设备同步安全令牌，请刷新页面后重试。');
                    return csrf;
                })
                .finally(() => { deviceSyncCsrfPromise = null; });
        }
        return deviceSyncCsrfPromise;
    }

    function renderDeviceSyncState(stage, title, message) {
        const state = $('device-sync-state');
        if (!state) return;
        state.dataset.state = stage || 'idle';
        $('device-sync-title').textContent = title || '设备同步';
        $('device-sync-copy').textContent = message || '';
    }

    function renderDeviceSyncPreview(payload) {
        const summary = payload?.summary || {};
        const device = payload?.device || {};
        $('device-sync-peer').textContent = `电脑：${device.device_name || '未命名设备'} · 临时连接将在 10 分钟内关闭`;
        ['words','favorites','notes','practice','conversations'].forEach(key => {
            const field = $(`device-sync-preview-${key}`);
            if (field) field.textContent = String(Number(summary[key] || 0));
        });
        $('device-sync-preview').hidden = false;
    }

    async function inspectDeviceSyncCode() {
        const code = String($('device-sync-manual-code')?.value || pendingPairingCode).trim();
        if (!code) { showToast('请先扫描或粘贴完整配对码。','warning'); return; }
        if (!window.CETNativeSync || typeof window.CETNativeSync.inspect !== 'function') {
            showToast('设备同步需要 Android 安装版。','error'); return;
        }
        const button = $('device-sync-inspect');
        button.disabled = true;
        renderDeviceSyncState('inspecting','正在验证电脑','正在申请一次性本机票据并核对临时证书。');
        try {
            await ensureDeviceSyncCsrf();
            const result = await api('/api/device-sync/mobile-ticket', {
                method:'POST',headers:{'X-CSRF-Token':csrf},body:'{}',
            });
            pendingPairingCode = code;
            window.CETNativeSync.inspect(code,result.ticket);
        } catch (error) {
            renderDeviceSyncState('error','无法开始验证',error.message || '本机同步票据创建失败。');
            button.disabled = false;
        }
    }

    function renderDesktopPairing(data) {
        $('device-sync-pairing').hidden = false;
        $('device-sync-qr').src = data.qr_data_url || '';
        $('device-sync-code').value = data.pairing_code || '';
        $('device-sync-address').textContent = `${(data.addresses || []).join(' / ')}:${data.port} · 到期后自动关闭`;
        $('device-sync-start').hidden = true;
        renderDeviceSyncState('waiting','等待手机连接','请在 Android 版“我的 → 设备同步”扫描二维码。');
    }

    async function pollDeviceSync() {
        try {
            const data = await api('/api/device-sync/status');
            csrf = csrf || data.csrf_token || '';
            if (data.stage === 'completed') {
                renderDeviceSyncState('completed','两台设备已同步','合并结果已写入并通过数据库完整性检查。');
                $('device-sync-start').hidden = false;
                $('device-sync-start').textContent = '再次同步';
                $('device-sync-pairing').hidden = true;
                clearInterval(deviceSyncPoll); deviceSyncPoll = 0;
                openDeviceSyncResult(data.sync_report);
            } else if (data.stage === 'awaiting_mobile_confirmation' || data.awaiting_peer_confirmation) {
                renderDeviceSyncState('confirming','等待手机最终确认','电脑已写入合并结果；手机完成落库和校验后才会显示成功。');
            } else if (data.stage === 'error') {
                renderDeviceSyncState('error','同步未完成',data.error || '两端备份已经保留，请重试。');
            }
        } catch (_) {}
    }

    function initDeviceSync() {
        const platform = root.dataset.appPlatform || 'source';
        $('device-sync-desktop').hidden = platform !== 'windows';
        $('device-sync-mobile').hidden = platform !== 'android';
        $('device-sync-source').hidden = platform === 'windows' || platform === 'android';
        if (platform === 'windows') {
            $('device-sync-start').addEventListener('click',async()=>{
                const button=$('device-sync-start'); button.disabled=true;
                renderDeviceSyncState('starting','正在开启临时连接','正在生成临时证书、一次性令牌和二维码。');
                try {
                    await ensureDeviceSyncCsrf();
                    const data=await api('/api/device-sync/sessions',{method:'POST',headers:{'X-CSRF-Token':csrf},body:'{}'});
                    csrf=csrf||data.csrf_token||''; renderDesktopPairing(data);
                    if(deviceSyncPoll)clearInterval(deviceSyncPoll);
                    deviceSyncPoll=window.setInterval(pollDeviceSync,2000);
                } catch(error){renderDeviceSyncState('error','无法开启同步',error.message||'请确认电脑已连接专用 Wi-Fi。');}
                finally{button.disabled=false;}
            });
            $('device-sync-cancel').addEventListener('click',async()=>{
                try{await ensureDeviceSyncCsrf();await api('/api/device-sync/sessions/current',{method:'DELETE',headers:{'X-CSRF-Token':csrf}});}catch(_){}
                if(deviceSyncPoll)clearInterval(deviceSyncPoll);deviceSyncPoll=0;
                $('device-sync-pairing').hidden=true;$('device-sync-start').hidden=false;
                renderDeviceSyncState('idle','临时连接已关闭','没有数据被发送。');
            });
            $('device-sync-copy-code').addEventListener('click',async()=>{
                const code=$('device-sync-code').value;
                try{await navigator.clipboard.writeText(code);showToast('完整配对码已复制。','success');}
                catch(_){$('device-sync-code').select();document.execCommand('copy');showToast('完整配对码已复制。','success');}
            });
        } else if (platform === 'android') {
            $('device-sync-scan').addEventListener('click',()=>{
                if(window.CETNativeSync?.scanPairingCode)window.CETNativeSync.scanPairingCode();
                else showToast('当前环境不能调用扫码功能，请粘贴配对码。','warning');
            });
            $('device-sync-inspect').addEventListener('click',inspectDeviceSyncCode);
            $('device-sync-confirm').addEventListener('click',()=>{
                $('device-sync-confirm').disabled=true;
                window.CETNativeSync?.confirm?.();
            });
            $('device-sync-mobile-cancel').addEventListener('click',()=>{
                window.CETNativeSync?.cancel?.();$('device-sync-preview').hidden=true;
                $('device-sync-inspect').disabled=false;$('device-sync-confirm').disabled=false;
                renderDeviceSyncState('idle','已取消本次同步','电脑的临时连接会在到期后自动关闭。');
            });
        }
        api('/api/device-sync/status').then(data=>{csrf=csrf||data.csrf_token||'';}).catch(()=>{});
    }

    window.CETDeviceSync = {
        onPairingCode(code){
            pendingPairingCode=String(code||'');$('device-sync-manual-code').value=pendingPairingCode;
            inspectDeviceSyncCode();
        },
        onProgress(payload){
            let data=payload||{};
            if(typeof payload==='string'){
                try{data=JSON.parse(payload);}catch(_){data={stage:'error',title:'同步状态异常',message:'手机返回了无法识别的同步状态。'};}
            }
            renderDeviceSyncState(data.stage,data.title,data.message);
            if(data.stage==='preview'){
                renderDeviceSyncPreview(data);$('device-sync-inspect').disabled=false;
            } else if(data.stage==='completed'){
                $('device-sync-preview').hidden=true;$('device-sync-confirm').disabled=false;
                openDeviceSyncResult(data.sync_report);
            } else if(data.stage==='error'||data.stage==='cancelled'){
                $('device-sync-inspect').disabled=false;$('device-sync-confirm').disabled=false;
            }
        },
    };

    window.CETUpdateNative = {
        onProgress(payload) {
            let progress = payload;
            if (typeof payload === 'string') {
                try {
                    progress = JSON.parse(payload);
                } catch (_error) {
                    progress = {message: payload};
                }
            }
            renderUpdateProgress(progress || {});
            if (progress?.title) $('update-state-title').textContent = progress.title;
            if (progress?.message) $('update-state-copy').textContent = progress.message;
            if (progress?.stage === 'error') {
                $('update-check').disabled = false;
                $('update-check').textContent = progress?.resumable ? '继续安全更新' : '重新检查';
            }
        },
    };

    async function refreshStatus(withBalance = false) {
        const status = await api('/api/ai/config/status');
        csrf = status.csrf_token;
        renderStatus(status);
        if (withBalance && status.configured) renderBalance(await api('/api/ai/balance'));
        return status;
    }

    initSupportModal();
    initUpdateCenter();
    initSkillDisclosure();
    initDeviceSyncResultModal();
    initDeviceSync();

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

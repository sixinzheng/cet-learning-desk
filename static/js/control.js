(function () {
    const root = document.getElementById('control-app');
    if (!root) return;
    const $ = id => document.getElementById(id);
    const state = { categories: [], notes: [], currentCategoryId: null, currentNoteId: null, aiCsrf: '', conversationId: null, aiAbort: null, assistantLanguage: 'zh', scenarioKey: 'casual', scenes: [], color: '', attachments: [], skillSlug: '', currentSkill: null, rankIdentity: getRankChatIdentity(1, '童生'), rankPromise: null, noteOriginal: {title:'', content:'', color:''} };

    function escapeHtml(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

    function renderAssistantMode() {
        root.querySelectorAll('[data-control-language]').forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.controlLanguage === state.assistantLanguage));
        });
        const english = state.assistantLanguage === 'en';
        $('control-english-scenes').hidden = !english;
        $('control-chat-input').placeholder = english
            ? 'Ask anything, or start a scene…'
            : '向 AI 提问…（可上传文本或图片，或让它整理进笔记）';
        const select = $('control-scene-select');
        if (select && state.scenes.length) {
            select.innerHTML = state.scenes.map(scene => `<option value="${escapeHtml(scene.key)}">${escapeHtml(scene.label_zh)} · ${escapeHtml(scene.label_en)}</option>`).join('');
            select.value = state.scenarioKey;
        }
    }

    async function loadAssistantPreferences() {
        try {
            const preferences = await api('/api/ai/preferences');
            state.aiCsrf = preferences.csrf_token || state.aiCsrf;
            state.assistantLanguage = preferences.language === 'en' ? 'en' : 'zh';
            state.scenes = preferences.scenes || [];
            renderAssistantMode();
        } catch (_) { renderAssistantMode(); }
    }

    async function switchAssistantLanguage(language) {
        const next = language === 'en' ? 'en' : 'zh';
        if (next === state.assistantLanguage) return;
        if (state.aiAbort) state.aiAbort.abort();
        root.querySelectorAll('[data-control-language]').forEach(button => { button.disabled = true; });
        try {
            if (!state.aiCsrf) await loadAssistantPreferences();
            await api('/api/ai/preferences', {method:'PUT', headers:{'X-CSRF-Token':state.aiCsrf}, body:JSON.stringify({language:next})});
            state.assistantLanguage = next;
            state.scenarioKey = 'casual';
            state.conversationId = null;
            $('control-messages').innerHTML = `<div class="assistant-empty"><strong>${next === 'en' ? 'New English conversation' : '开始一段新对话'}</strong><p>${next === 'en' ? 'Pick a scene below, or just say hi—awkward small talk is optional. 🙂' : '语言已切换，旧对话保持原样。'}</p></div>`;
            renderAssistantMode();
        } catch (error) { showToast(error.message || '语言设置保存失败。', 'error'); }
        finally { root.querySelectorAll('[data-control-language]').forEach(button => { button.disabled = false; }); }
    }

    async function loadCategories() {
        try {
            const data = await api('/api/notes/categories');
            state.categories = data.categories || [];
            renderCategories();
        } catch (error) {
            $('control-categories').innerHTML = '<div class="region-state region-state--error"><strong>分类加载失败</strong><button id="control-category-retry" class="text-button" type="button">重试</button></div>';
            $('control-category-retry')?.addEventListener('click', loadCategories);
        }
    }

    function renderCategories() {
        const el = $('control-categories');
        el.innerHTML = '<button type="button" class="cat-item cat-item--all' + (state.currentCategoryId == null ? ' is-active' : '') + '" data-cat="all" aria-pressed="' + (state.currentCategoryId == null) + '"><b>全部笔记</b></button>' +
            state.categories.map(cat => {
                const child = (cat.children || []).map(c => '<button type="button" class="cat-item cat-item--child' + (state.currentCategoryId === c.id ? ' is-active' : '') + '" data-cat="' + c.id + '" aria-pressed="' + (state.currentCategoryId === c.id) + '"><b>' + escapeHtml(c.name) + '</b></button>').join('');
                return '<button type="button" class="cat-item cat-item--parent' + (state.currentCategoryId === cat.id ? ' is-active' : '') + '" data-cat="' + cat.id + '" aria-pressed="' + (state.currentCategoryId === cat.id) + '"><b>' + escapeHtml(cat.name) + '</b></button>' + child;
            }).join('');
        el.querySelectorAll('.cat-item').forEach(item => item.addEventListener('click', () => { state.currentCategoryId = item.dataset.cat === 'all' ? null : Number(item.dataset.cat); renderCategories(); loadNotes(); }));
    }

    async function loadNotes() {
        try {
            const url = state.currentCategoryId != null ? '/api/notes/notes?category_id=' + state.currentCategoryId : '/api/notes/notes';
            const data = await api(url);
            state.notes = data.notes || [];
            renderNotes();
        } catch (_) { $('control-notes').innerHTML = '<p class="muted">笔记加载失败。</p>'; }
    }

    function renderNotes() {
        const el = $('control-notes');
        if (!state.notes.length) { el.innerHTML = '<p class="muted">暂无笔记，点右上角「＋新建笔记」。</p>'; return; }
        el.innerHTML = state.notes.map(note => '<button type="button" class="note-item' + (state.currentNoteId === note.id ? ' is-active' : '') + '" data-id="' + note.id + '" aria-pressed="' + (state.currentNoteId === note.id) + '"><b>' + escapeHtml(note.title || '未命名') + '</b><span>' + escapeHtml(note.note_date || '') + '</span></button>').join('');
        el.querySelectorAll('.note-item').forEach(item => item.addEventListener('click', () => selectNote(Number(item.dataset.id))));
    }

    async function selectNote(id) {
        if (isNoteDirty() && !window.confirm('当前笔记还有未保存修改，仍要切换吗？')) return;
        try {
            const note = await api('/api/notes/notes/' + id);
            state.currentNoteId = id;
            $('note-title').value = note.title || '';
            $('note-content').value = note.content || '';
            $('note-date-label').textContent = note.note_date || '--';
            state.color = note.color || '';
            state.noteOriginal = {title: note.title || '', content: note.content || '', color: note.color || ''};
            $('control-note-state').textContent = '已载入，尚未修改';
            $('control-note-editor').dataset.color = state.color || 'black';
            renderNotes();
            $('control-note-editor').querySelectorAll('.color-dot').forEach(dot => dot.classList.toggle('is-active', dot.dataset.color === state.color));
        } catch (_) { showToast('笔记读取失败。', 'error'); }
    }

    async function addNote() {
        if (isNoteDirty() && !window.confirm('当前笔记还有未保存修改，仍要新建吗？')) return;
        try {
            const r = await api('/api/notes/notes', { method: 'POST', body: JSON.stringify({ title: '新笔记', content: '', category_id: state.currentCategoryId || 0 }) });
            await loadNotes();
            await selectNote(r.id);
        } catch (_) { showToast('新建失败。', 'error'); }
    }

    async function saveNote() {
        if (!state.currentNoteId) { showToast('请先选择或新建一篇笔记。', 'warning'); return; }
        try {
            await api('/api/notes/notes/' + state.currentNoteId, { method: 'PUT', body: JSON.stringify({ title: $('note-title').value, content: $('note-content').value, color: state.color }) });
            state.noteOriginal = {title:$('note-title').value, content:$('note-content').value, color:state.color};
            $('control-note-state').textContent = '已保存';
            showToast('笔记已保存。', 'success');
            await loadNotes();
        } catch (_) { showToast('保存失败。', 'error'); }
    }

    async function deleteNote() {
        if (!state.currentNoteId) { showToast('请先选择一篇笔记。', 'warning'); return; }
        if (!confirm('确定删除这篇笔记？')) return;
        try {
            await api('/api/notes/notes/' + state.currentNoteId, { method: 'DELETE' });
            state.currentNoteId = null; $('note-title').value = ''; $('note-content').value = '';
            state.noteOriginal = {title:'', content:'', color:''}; $('control-note-state').textContent = '请选择或新建笔记';
            showToast('已删除。', 'success'); await loadNotes();
        } catch (_) { showToast('删除失败。', 'error'); }
    }

    function openCategoryForm() {
        const form = $('category-form'), select = $('category-parent');
        select.innerHTML = '<option value="0">顶级分类</option>' + state.categories.map(category => `<option value="${category.id}">${escapeHtml(category.name)}</option>`).join('');
        form.hidden = false; $('category-name').focus(); $('category-form-state').textContent = '';
    }
    function closeCategoryForm() { $('category-form').hidden = true; $('category-name').value = ''; $('category-add').focus(); }
    async function addCategory(event) {
        event.preventDefault();
        const name = $('category-name').value.trim(), parent_id = Number($('category-parent').value || 0);
        if (!name) { $('category-form-state').textContent = '请输入分类名称。'; $('category-name').focus(); return; }
        try { await api('/api/notes/categories', { method: 'POST', body: JSON.stringify({ parent_id, name }) }); await loadCategories(); closeCategoryForm(); showToast('分类已建。', 'success'); }
        catch (error) { $('category-form-state').textContent = error.message || '创建失败，请重试。'; }
    }

    function chatAvatar(role) {
        const image = document.createElement('img');
        image.className = `chat-avatar chat-avatar--${role}`;
        if (role === 'assistant') { image.src = CET_AI_AVATAR; image.alt = '学习助理头像'; }
        else { image.src = state.rankIdentity.src; image.alt = `${state.rankIdentity.name}段位头像`; image.classList.add(state.rankIdentity.className); }
        return image;
    }

    function appendMessage(role, text) {
        const area = $('control-messages');
        area.querySelector('.assistant-empty')?.remove();
        const article = document.createElement('article');
        article.className = 'control-msg control-msg--' + role;
        const avatar = chatAvatar(role);
        const bubble = document.createElement('div'); bubble.className = 'control-msg__bubble';
        const b = document.createElement('strong'); b.textContent = role === 'user' ? state.rankIdentity.name : '学习助理';
        const p = document.createElement('p'); p.textContent = String(text || '');
        bubble.append(b, p); article.append(avatar, bubble); area.appendChild(article); area.scrollTop = area.scrollHeight;
        return {article, bubble, copy:p};
    }

    function renderAttachments() {
        const el = $('control-attachments');
        el.innerHTML = state.attachments.map((att, i) => '<span class="control-attachment">' + escapeHtml(att.name) + '<button data-i="' + i + '" aria-label="移除附件" type="button">×</button></span>').join('');
        el.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => { state.attachments.splice(Number(btn.dataset.i), 1); renderAttachments(); }));
    }

    function handleFile(file) {
        if (!file) return;
        if (state.attachments.length >= 3) { showToast('一次最多添加 3 个附件。', 'warning'); return; }
        const name = file.name || '';
        const ext = (name.split('.').pop() || '').toLowerCase();
        const textExts = ['txt', 'md', 'json', 'csv'];
        if (textExts.includes(ext)) {
            const reader = new FileReader();
            reader.onload = () => { state.attachments.push({ name, text: String(reader.result || '').slice(0, 12000) }); renderAttachments(); };
            reader.readAsText(file);
        } else if (['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(file.type)) {
            if (file.size > 6 * 1024 * 1024) { showToast('单张图片不能超过 6 MB。', 'error'); return; }
            const reader = new FileReader();
            reader.onload = () => { state.attachments.push({ name, image: String(reader.result || ''), kind: 'image' }); renderAttachments(); };
            reader.readAsDataURL(file);
        } else {
            showToast('仅支持 TXT、MD、JSON、CSV 或 JPEG、PNG、GIF、WebP。', 'error');
        }
    }

    async function resolveAction(id, decision, box) {
        try {
            await api('/api/ai/actions/' + id + '/' + decision, { method: 'POST', headers: { 'X-CSRF-Token': state.aiCsrf }, body: '{}' });
            box.textContent = decision === 'confirm' ? '已整理进笔记。' : '已取消。';
            showToast(decision === 'confirm' ? '内容已存入笔记。' : '已取消。', decision === 'confirm' ? 'success' : 'info');
        } catch (e) { showToast(e.message || '操作失败。', 'error'); }
    }

    function appendAssistant(result) {
        const area = $('control-messages');
        const article = document.createElement('article');
        article.className = 'control-msg control-msg--assistant';
        const avatar = chatAvatar('assistant');
        const bubble = document.createElement('div'); bubble.className = 'control-msg__bubble';
        const b = document.createElement('strong'); b.textContent = '学习助理';
        const p = document.createElement('p'); p.textContent = String(result.message || '');
        bubble.append(b, p);
        if (result.action) {
            const box = document.createElement('div'); box.className = 'ai-action-preview';
            const pre = document.createElement('p'); pre.textContent = result.action.preview;
            const rows = document.createElement('div');
            const confirm = document.createElement('button'); confirm.type = 'button'; confirm.className = 'btn btn-primary'; confirm.textContent = '确认整理到笔记';
            const reject = document.createElement('button'); reject.type = 'button'; reject.className = 'btn btn-secondary'; reject.textContent = '取消';
            confirm.addEventListener('click', () => resolveAction(result.action.id, 'confirm', box));
            reject.addEventListener('click', () => resolveAction(result.action.id, 'reject', box));
            rows.append(confirm, reject); box.append(pre, rows); bubble.appendChild(box);
        }
        article.append(avatar, bubble); area.appendChild(article); area.scrollTop = area.scrollHeight;
    }

    function decorateStreamedAssistant(node, result) {
        if (!node?.bubble || !result.action) return;
        const box = document.createElement('div'); box.className = 'ai-action-preview';
        const pre = document.createElement('p'); pre.textContent = result.action.preview;
        const rows = document.createElement('div');
        const confirm = document.createElement('button'); confirm.type = 'button'; confirm.className = 'btn btn-primary'; confirm.textContent = '确认整理到笔记';
        const reject = document.createElement('button'); reject.type = 'button'; reject.className = 'btn btn-secondary'; reject.textContent = '取消';
        confirm.addEventListener('click', () => resolveAction(result.action.id, 'confirm', box));
        reject.addEventListener('click', () => resolveAction(result.action.id, 'reject', box));
        rows.append(confirm, reject); box.append(pre, rows); node.bubble.appendChild(box);
    }

    function addChatRetry(node, message, attachments) {
        const status = document.createElement('p'); status.className = 'assistant-stream-status';
        status.textContent = '连接中断，以上内容已保留。';
        const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'text-button'; retry.textContent = '重试回答';
        retry.addEventListener('click', () => { retry.disabled = true; sendChat(message, {showUser: false, attachments}); });
        node.bubble.append(status, retry);
    }

    async function sendChat(message, options = {}) {
        if (state.rankPromise) await state.rankPromise;
        let attachments = options.attachments ? options.attachments.slice() : [];
        if (!options.attachments && state.articleContext) attachments.push({ name: '文章《' + state.articleContext.title + '》', text: state.articleContext.content });
        if (!options.attachments) attachments = attachments.concat(state.attachments.slice());
        if (!message && !attachments.length && !options.start_scene) return;
        const input = $('control-chat-input'), button = $('control-chat-form').querySelector('button[type="submit"]');
        const visibleAttachmentNames = attachments.map(item => item.name).filter(Boolean).join('、');
        if (options.showUser !== false && !options.start_scene) appendMessage('user', message || (visibleAttachmentNames ? `请分析：${visibleAttachmentNames}` : '(附件)'));
        input.value = '';
        const node = appendMessage('assistant', '');
        state.aiAbort = new AbortController();
        button.disabled = false; button.textContent = state.assistantLanguage === 'en' ? 'Stop' : '停止生成';
        const writer = createAITypewriter(node.copy, {onUpdate: () => { node.article.parentElement.scrollTop = node.article.parentElement.scrollHeight; }});
        try {
            const status = await api('/api/ai/config/status');
            state.aiCsrf = status.csrf_token;
            const resp = await fetch('/api/ai/chat', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': state.aiCsrf }, body: JSON.stringify({ message, attachments, conversation_id: state.conversationId, skill_slug: state.skillSlug, language: state.assistantLanguage, scenario_key: options.scenario_key || state.scenarioKey, start_scene: Boolean(options.start_scene) }), signal: state.aiAbort.signal });
            if (!resp.ok) { const e = await resp.json().catch(() => ({})); throw new Error(e.error || 'AI 请求失败。'); }
            const result = await consumeAIStream(resp, {onDelta: text => writer.append(text), onDone: data => writer.finish(data.message)});
            state.conversationId = result.conversation_id;
            state.scenarioKey = result.scenario_key || state.scenarioKey;
            state.attachments = []; renderAttachments();
            await writer.finish(result.message); renderSafeMarkdown(node.copy, result.message); decorateStreamedAssistant(node, result);
        } catch (e) {
            writer.stop();
            if (e.name === 'AbortError') node.copy.textContent += node.copy.textContent ? '\n（已停止生成）' : '已停止生成。';
            else {
                if (!node.copy.textContent) node.copy.textContent = e.message || '这次没有连接上 AI。';
                addChatRetry(node, message, attachments);
            }
        } finally { state.aiAbort = null; button.disabled = false; button.textContent = state.assistantLanguage === 'en' ? 'Send' : '发送'; input.focus(); }
    }

    function isNoteDirty() {
        if (!state.currentNoteId) return false;
        return $('note-title').value !== state.noteOriginal.title || $('note-content').value !== state.noteOriginal.content || state.color !== state.noteOriginal.color;
    }
    function updateNoteState() { if (state.currentNoteId) $('control-note-state').textContent = isNoteDirty() ? '有未保存修改' : '已保存'; }
    $('category-add').addEventListener('click', openCategoryForm);
    $('category-form').addEventListener('submit', addCategory);
    $('category-cancel').addEventListener('click', closeCategoryForm);
    $('note-add').addEventListener('click', addNote);
    $('note-save').addEventListener('click', saveNote);
    $('note-delete').addEventListener('click', deleteNote);
    $('control-chat-form').addEventListener('submit', e => { e.preventDefault(); if (state.aiAbort) { state.aiAbort.abort(); return; } sendChat($('control-chat-input').value.trim()); });
    root.querySelectorAll('[data-control-language]').forEach(button => button.addEventListener('click', () => switchAssistantLanguage(button.dataset.controlLanguage)));
    $('control-scene-start').addEventListener('click', () => {
        state.scenarioKey = $('control-scene-select').value || 'casual';
        state.conversationId = null;
        $('control-messages').innerHTML = '';
        sendChat('', {showUser:false, start_scene:true, scenario_key:state.scenarioKey});
    });
    $('control-attach').addEventListener('click', () => $('control-file').click());
    $('control-file').addEventListener('change', e => { handleFile(e.target.files[0]); e.target.value = ''; });
    $('note-title').addEventListener('input', updateNoteState); $('note-content').addEventListener('input', updateNoteState);
    $('control-note-editor').querySelectorAll('.color-dot').forEach(dot => dot.addEventListener('click', () => { state.color = dot.dataset.color; $('control-note-editor').dataset.color = state.color; $('control-note-editor').querySelectorAll('.color-dot').forEach(d => d.classList.toggle('is-active', d === dot)); updateNoteState(); }));
    function toggleDrawer(target, button) {
        const open = !target.classList.contains('is-open');
        document.querySelectorAll('.control-sidebar,.control-preview').forEach(panel => panel.classList.remove('is-open'));
        target.classList.toggle('is-open', open);
        $('control-notes-toggle').setAttribute('aria-expanded', String(open && target.id === 'control-sidebar'));
        $('control-note-toggle').setAttribute('aria-expanded', String(open && target.id === 'control-preview'));
        $('control-drawer-backdrop').hidden = !open;
        if (open) requestAnimationFrame(() => target.querySelector('button,input,textarea')?.focus()); else button?.focus();
    }
    function closeDrawers() { document.querySelectorAll('.control-sidebar,.control-preview').forEach(panel => panel.classList.remove('is-open')); $('control-notes-toggle').setAttribute('aria-expanded','false'); $('control-note-toggle').setAttribute('aria-expanded','false'); $('control-drawer-backdrop').hidden=true; }
    $('control-notes-toggle').addEventListener('click', () => toggleDrawer($('control-sidebar'), $('control-notes-toggle')));
    $('control-note-toggle').addEventListener('click', () => toggleDrawer($('control-preview'), $('control-note-toggle')));
    $('control-drawer-backdrop').addEventListener('click', closeDrawers);
    document.addEventListener('keydown', event => { if (event.key === 'Escape') closeDrawers(); });
    window.addEventListener('beforeunload', event => { if (!isNoteDirty()) return; event.preventDefault(); event.returnValue = ''; });
    const rs1 = $('control-resizer-1');
    if (rs1) {
        rs1.addEventListener('mousedown', e => {
            e.preventDefault();
            const board = document.querySelector('.control-workbench');
            const onMove = ev => {
                const rect = board.getBoundingClientRect();
                const w = Math.max(170, Math.min(420, ev.clientX - rect.left));
                board.style.setProperty('--sidebar-w', w + 'px');
            };
            const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
            window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp);
        });
    }
    const resizer = $('control-resizer');
    if (resizer) {
        resizer.addEventListener('mousedown', e => {
            e.preventDefault();
            const board = document.querySelector('.control-workbench');
            const onMove = ev => {
                const rect = board.getBoundingClientRect();
                const w = Math.max(280, Math.min(620, rect.right - ev.clientX));
                board.style.setProperty('--preview-w', w + 'px');
            };
            const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
            window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp);
        });
    }

    async function loadArticleContext() {
        const params = new URLSearchParams(window.location.search);
        const aid = params.get('article_id');
        if (!aid) return;
        try {
            const article = await api('/api/reading/articles/' + aid);
            state.articleContext = { id: article.id, title: article.title, content: article.content };
            $('control-chat-context').textContent = '已绑定文章：《' + article.title + '》';
            $('control-chat-context').classList.add('is-bound');
        } catch (error) {
            $('control-chat-context').textContent = '文章上下文加载失败，可重新从阅读页进入';
            $('control-chat-context').classList.add('is-error');
        }
    }

    async function loadRankIdentity() {
        try { const data = await api('/api/level/detail'); state.rankIdentity = getRankChatIdentity(data.level?.rank, data.level?.name); }
        catch (_) { state.rankIdentity = getRankChatIdentity(1, '童生'); }
    }

    async function loadSkillContext() {
        const slug = new URLSearchParams(window.location.search).get('skill');
        if (!slug) return;
        const panel = $('skill-workbench');
        panel.hidden = false;
        try {
            const data = await api('/api/ai/skills');
            state.aiCsrf = data.csrf_token || state.aiCsrf;
            const skill = (data.skills || []).find(item => item.slug === slug);
            if (!skill) throw new Error('没有找到这个 Skill。');
            state.skillSlug = skill.slug;
            state.currentSkill = skill;
            $('skill-workbench-title').textContent = skill.display_name;
            $('skill-workbench-description').textContent = skill.description;
            $('skill-workbench-rules').value = skill.user_instructions || '';
            $('skill-workbench-rules').disabled = !skill.enabled;
            $('skill-workbench-save').disabled = !skill.enabled;
            $('skill-workbench-state').textContent = skill.enabled
                ? '对话会携带这个 Skill 的项目规则；AI 的建议不会自动写入。'
                : '这个 Skill 已关闭，请先回“我的”启用。';
            $('control-chat-context').textContent = `正在优化 Skill：${skill.display_name}`;
            $('control-chat-input').placeholder = `询问如何改进“${skill.display_name}”的规则…`;
        } catch (error) {
            $('skill-workbench-title').textContent = 'Skill 加载失败';
            $('skill-workbench-description').textContent = error.message || '请返回“我的”重新选择。';
            $('skill-workbench-save').disabled = true;
        }
    }

    $('skill-workbench-save').addEventListener('click', async () => {
        if (!state.currentSkill) return;
        const button = $('skill-workbench-save'), status = $('skill-workbench-state');
        button.disabled = true;
        status.textContent = '正在保存…';
        try {
            const result = await api(`/api/ai/skills/${encodeURIComponent(state.currentSkill.slug)}`, {
                method: 'PUT', headers: {'X-CSRF-Token': state.aiCsrf},
                body: JSON.stringify({user_instructions: $('skill-workbench-rules').value}),
            });
            state.currentSkill = result.skill;
            status.textContent = '补充规则已保存，下一次对话立即生效。';
            showToast('Skill 规则已保存。', 'success');
        } catch (error) {
            status.textContent = error.message || '保存失败，请重试。';
        } finally { button.disabled = false; }
    });

    state.rankPromise = loadRankIdentity();
    loadCategories(); loadNotes(); loadArticleContext(); loadSkillContext(); loadAssistantPreferences();
    setRegionState(root, 'ready');
})();

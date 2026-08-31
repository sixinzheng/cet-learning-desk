(function () {
    const root = document.getElementById('dashboard-app');
    if (!root) return;
    const $ = id => document.getElementById(id);
    let books = [];
    let currentWords = [];
    let dashboardState = {};
    let aiCsrf = '';
    let aiConversation = null;
    let aiAbort = null;
    let aiLanguage = 'zh';
    let aiScenes = [];
    let currentRankIdentity = getRankChatIdentity(1, '童生');
    const AI_AVATAR = (document.querySelector('#ai-avatar') && document.querySelector('#ai-avatar').src) || '/static/images/ai-avatar.png';
    const userAvatar = () => currentRankIdentity.src;

    function intro() {
        const hour = new Date().getHours();
        const greeting = hour < 6 ? '夜深了' : hour < 12 ? '早上好' : hour < 14 ? '中午好' : hour < 18 ? '下午好' : '晚上好';
        $('greeting-text').textContent = `${greeting}，先完成今天的词汇任务`;
        fitTextToLine($('greeting-text'));
        $('today-date').textContent = new Intl.DateTimeFormat('zh-CN', {month: 'long', day: 'numeric', weekday: 'short'}).format(new Date());
    }

    function renderDailyProgress(data) {
        const target = Number(data.daily_target || $('daily-count').value || 20);
        const learned = Number(data.learned_today || 0);
        const reviewed = Number(data.reviewed_today || 0);
        const due = Number(data.review_due_remaining ?? data.today_review ?? 0);
        const newRemaining = Number(data.new_task_remaining ?? data.today_new ?? 0);
        $('learned-today').textContent = learned;
        $('learn-goal').textContent = target;
        $('reviewed-today').textContent = reviewed;
        $('review-goal').textContent = Number(data.review_goal || target);
        $('remaining-new').textContent = `${newRemaining} 个`;
        $('remaining-review').textContent = `${due} 个`;
        $('core-minutes').textContent = Math.max(0, Math.ceil(newRemaining + due * 0.5));
        if ($('setting-remaining') && data.wordbook_unmastered_remaining != null) {
            $('setting-remaining').textContent = `${Number(data.wordbook_unmastered_remaining) || 0} 个`;
        }
        $('learn-progress-note').textContent = learned >= target ? `今日目标已完成${learned > target ? `，超额 ${learned - target} 个` : ''}` : `还差 ${Math.max(0, target - learned)} 个完成目标`;
        if (!due) {
            $('review-progress-note').textContent = reviewed >= target ? `今日目标已完成${reviewed > target ? `，超额 ${reviewed - target} 个` : ''}` : '今日到期已清空';
        } else {
            $('review-progress-note').textContent = reviewed >= target ? `已达目标，仍有 ${due} 个到期词` : `仍有 ${due} 个到期词`;
        }
        taskAdvice(target, due, newRemaining, learned, reviewed);
    }

    function taskAdvice(daily, due, availableNew, learned, reviewed) {
        const newCount = Math.max(0, Number(availableNew) || 0);
        const reviewDue = Math.max(0, Number(due) || 0);
        let title = '今日建议：均衡推进';
        let detail = '新词与复习任务接近，先完成较短的一组，再集中处理另一组。';
        if (!newCount && !reviewDue) {
            title = '今天的词汇任务已经清空';
            detail = learned || reviewed ? '你已经完成今天可处理的任务，可以去学习页选择一项专项训练。' : '今天暂时没有新词或到期复习任务。';
        } else if (reviewDue > newCount) {
            title = '今日建议：先复习为主';
            detail = '到期词更多，先保护已经形成的记忆，再学习新词。';
        } else if (newCount > reviewDue) {
            title = '今日建议：以学新词为主';
            detail = '到期复习较轻，可以把主要精力放在扩充词汇。';
        }
        $('task-advice-title').textContent = title;
        $('task-advice-counts').textContent = `每日目标 ${daily} 个 · 待学 ${newCount} 个 · 到期复习 ${reviewDue} 个。${detail}`;
        document.querySelector('#primary-study-action span').textContent = newCount ? `继续学习 ${newCount} 个新词` : '新词任务已完成';
        document.querySelector('.btn-review span').textContent = reviewDue ? `处理 ${reviewDue} 个到期词` : '今日到期已清空';
    }

    async function loadBook(id) {
        const currentBook = books.find(book => book.id === Number(id));
        try {
            const data = await api(`/api/words/wordbooks/${id}/words?limit=10000`);
            currentWords = data.words || [];
            const count = status => currentWords.filter(word => word.status === status).length;
            const mastered = count('熟记');
            const known = count('掌握');
            const learning = currentWords.filter(word => !['陌生', '熟记', '掌握'].includes(word.status)).length;
            const done = mastered + known;
            const total = Number(currentBook?.total_words || currentWords.length);
            const pct = total ? Math.round(done / total * 100) : 0;
            $('wb-mastered').textContent = mastered;
            $('wb-known').textContent = known;
            $('wb-learning').textContent = learning;
            $('wb-pct').textContent = `${pct}%`;
            $('wb-fill').style.width = `${pct}%`;
            $('task-book-title').textContent = currentBook?.name || '当前词库';
            $('wordbook-description').textContent = currentBook?.description || `本词库共 ${total} 个词，已稳定掌握 ${done} 个。`;
        } catch (_) {
            $('wordbook-description').textContent = '词库数据加载失败，请刷新后重试。';
        }
    }

    function renderRank(level) {
        const rank = Number(level.level.rank || 1);
        currentRankIdentity = getRankChatIdentity(rank, level.level.name);
        const stage = Math.min(10, Math.max(1, Math.floor(level.level.total_score % 10) + 1));
        $('plate-rank').textContent = `Lv.${rank}`;
        $('plate-name').textContent = level.level.name;
        $('plate-stage').textContent = stage;
        $('plate-next-name').textContent = level.next_level.name;
        $('level-gap-display').textContent = `${level.next_level.gap} 分`;
        $('level-confidence-display').textContent = `${level.level.confidence}%`;
        $('level-progress-fill').style.width = `${stage * 10}%`;
        $('rank-capability').textContent = level.assessment?.sentence || '学习证据还少，完成更多训练后会形成更可靠的现实能力结论。';
        $('home-rank-advice').textContent = (level.quantified_suggestions && level.quantified_suggestions[0]?.text) || (level.suggestions && level.suggestions[0]) || '保持稳定学习节奏，完成更多可核验专项训练。';
        const circumference = 351.86;
        $('rank-ring-progress').style.strokeDashoffset = String(circumference * (1 - stage / 10));
        setRankPortrait($('rank-portrait-home'), rank);
        refreshUserAvatars();
    }

    async function load() {
        setRegionState(root, 'loading', '正在读取今日学习数据…');
        try {
            const [dashboard, bookData, setting, level] = await Promise.all([
                api('/api/study/dashboard'),
                api('/api/words/wordbooks'),
                api('/api/study/daily-setting'),
                api('/api/level/detail'),
            ]);
            dashboardState = dashboard;
            $('daily-count').value = dashboard.daily_target || setting.count || 20;
            renderDailyProgress(dashboard);
            books = bookData.wordbooks || [];
            $('wb-select').innerHTML = books.length ? books.map(book => `<option value="${book.id}">${book.name}</option>`).join('') : '<option value="">暂无词库</option>';
            if (books.length) {
                let saved = null;
                try { saved = (await api('/api/words/current-wordbook')).book_id; } catch (_) {}
                const target = books.some(book => book.id === saved) ? saved : books[0].id;
                $('wb-select').value = target;
                await loadBook(target);
            } else {
                $('task-book-title').textContent = '暂无词库';
                $('wordbook-description').textContent = '当前没有可用词库，请到“我的”检查本地数据。';
            }
            renderRank(level);
            setRegionState(root, 'ready');
        } catch (_) {
            setRegionState(root, 'error', '首页数据加载失败。请确认本地服务正常后刷新页面。');
        }
    }

    function refreshUserAvatars() {
        document.querySelectorAll('.home-triad .chat-avatar--user').forEach(img => {
            img.src = userAvatar();
            img.className = `chat-avatar chat-avatar--user ${currentRankIdentity.className}`;
            img.alt = `${currentRankIdentity.name}段位头像`;
            const label = img.closest('.ai-message')?.querySelector('.ai-message__bubble > strong');
            if (label) label.textContent = currentRankIdentity.name;
        });
    }

    function buildAvatar(role) {
        const img = document.createElement('img');
        img.className = `chat-avatar chat-avatar--${role}`;
        img.alt = role === 'user' ? '你的头像' : '学习助理';
        if (role === 'user') {
            img.src = userAvatar();
            img.classList.add(currentRankIdentity.className);
            img.alt = `${currentRankIdentity.name}段位头像`;
        } else {
            img.src = AI_AVATAR;
        }
        return img;
    }

    function addChatMessage(role, text, citations = [], action = null) {
        const area = $('ai-chat-messages');
        if (!area) return null;
        const article = document.createElement('article');
        article.className = `ai-message ai-message--${role}`;
        const avatar = buildAvatar(role);
        const bubble = document.createElement('div');
        bubble.className = 'ai-message__bubble';
        const label = document.createElement('strong');
        label.textContent = role === 'user' ? currentRankIdentity.name : (aiLanguage === 'en' ? 'Study buddy' : '学习助理');
        const copy = document.createElement('p');
        copy.textContent = String(text || '').replace(/\*\*(.*?)\*\*/g, '$1');
        bubble.append(label, copy);
        if (citations.length) {
            const sources = document.createElement('div');
            sources.className = 'ai-citations';
            citations.forEach(item => { const span = document.createElement('span'); span.textContent = `${item.date} · ${item.excerpt}`; sources.appendChild(span); });
            bubble.appendChild(sources);
        }
        if (action) {
            const box = document.createElement('div');
            box.className = 'ai-action-preview';
            const preview = document.createElement('p');
            preview.textContent = action.preview;
            const actions = document.createElement('div');
            const confirm = document.createElement('button');
            confirm.type = 'button'; confirm.className = 'btn btn-primary'; confirm.textContent = '确认追加到今日笔记';
            const reject = document.createElement('button');
            reject.type = 'button'; reject.className = 'btn btn-secondary'; reject.textContent = '取消';
            confirm.addEventListener('click', () => resolveAction(action.id, 'confirm', box));
            reject.addEventListener('click', () => resolveAction(action.id, 'reject', box));
            actions.append(confirm, reject); box.append(preview, actions); bubble.appendChild(box);
        }
        article.append(avatar, bubble);
        area.appendChild(article);
        area.scrollTop = area.scrollHeight;
        return {article, bubble, copy};
    }

    function decorateStreamedMessage(node, result) {
        const bubble = node?.bubble;
        if (!bubble) return;
        (result.citations || []).forEach(item => {
            let sources = bubble.querySelector('.ai-citations');
            if (!sources) { sources = document.createElement('div'); sources.className = 'ai-citations'; bubble.appendChild(sources); }
            const span = document.createElement('span'); span.textContent = `${item.date} · ${item.excerpt}`; sources.appendChild(span);
        });
        if (result.action) {
            const box = document.createElement('div'); box.className = 'ai-action-preview';
            const preview = document.createElement('p'); preview.textContent = result.action.preview;
            const actions = document.createElement('div');
            const confirm = document.createElement('button'); confirm.type = 'button'; confirm.className = 'btn btn-primary'; confirm.textContent = '确认追加到今日笔记';
            const reject = document.createElement('button'); reject.type = 'button'; reject.className = 'btn btn-secondary'; reject.textContent = '取消';
            confirm.addEventListener('click', () => resolveAction(result.action.id, 'confirm', box));
            reject.addEventListener('click', () => resolveAction(result.action.id, 'reject', box));
            actions.append(confirm, reject); box.append(preview, actions); bubble.appendChild(box);
        }
    }

    async function resolveAction(id, decision, box) {
        try {
            await api(`/api/ai/actions/${id}/${decision}`, {method: 'POST', headers: {'X-CSRF-Token': aiCsrf}, body: '{}'});
            box.textContent = decision === 'confirm' ? '已追加到今天的笔记。' : '已取消，不会修改笔记。';
            showToast(decision === 'confirm' ? '笔记已追加。' : '已取消。', 'success');
        } catch (error) { showToast(error.message || '操作失败。', 'error'); }
    }

    async function loadAssistant() {
        try {
            const [status, preferences] = await Promise.all([
                api('/api/ai/config/status'), api('/api/ai/preferences'),
            ]);
            aiCsrf = status.csrf_token;
            aiLanguage = preferences.language || 'zh';
            aiScenes = preferences.scenes || [];
            renderAssistantLanguageUI();
            const [greeting, conversationData] = await Promise.all([
                api(`/api/ai/greeting?language=${encodeURIComponent(aiLanguage)}`),
                api(`/api/ai/conversations?language=${encodeURIComponent(aiLanguage)}`),
            ]);
            $('ai-greeting').querySelector('p').textContent = greeting.greeting;
            $('ai-greeting').dataset.source = greeting.source;
            $('ai-chat-messages').innerHTML = '';
            const latest = conversationData.conversations?.[0];
            if (latest) {
                aiConversation = latest.id;
                const messageData = await api(`/api/ai/conversations/${latest.id}/messages`);
                (messageData.messages || []).slice(-2).forEach(message => addChatMessage(message.role, message.content, message.citations || []));
            } else if (!status.configured) {
                addChatMessage('assistant', aiLanguage === 'en'
                    ? 'DeepSeek is not configured yet. Your data greeting still works; add an API Key under “我的” when you want to start chatting.'
                    : 'DeepSeek 尚未配置。你仍能看到本地数据问候；到“我的”填写 API Key 后即可开始完整问答。');
            }
        } catch (_) {
            $('ai-greeting').querySelector('p').textContent = aiLanguage === 'en'
                ? 'I could not load today’s learning greeting. Please refresh and try again.'
                : '暂时没能读取学习问候，请刷新页面重试。';
        }
    }

    function renderAssistantLanguageUI() {
        document.querySelectorAll('#ai-quick-chat [data-assistant-language]').forEach(button => {
            button.setAttribute('aria-pressed', button.dataset.assistantLanguage === aiLanguage ? 'true' : 'false');
        });
        const english = aiLanguage === 'en';
        $('home-english-scenes').hidden = !english;
        $('ai-chat-title').textContent = english ? 'A real conversation, tuned to your learning' : '带着你的数据，回答今天的问题';
        $('ai-chat-input').placeholder = english ? 'Say anything—or ask about your notes and learning…' : '例如：我前几天的笔记里是不是记过定语从句？';
        $('ai-chat-form').querySelector('button[type="submit"]').textContent = english ? 'Send' : '发送问题';
        const select = $('home-scene-select');
        select.innerHTML = aiScenes.map(scene => `<option value="${scene.key}">${scene.label} · ${scene.label_en}</option>`).join('');
        const prompts = $('home-ai-prompts');
        prompts.innerHTML = english
            ? '<button type="button" data-ai-prompt="What should we talk about today based on my recent learning?">Pick a topic</button><button type="button" data-ai-prompt="Can you help me find a useful idea from my recent notes?">Find a note</button><button type="button" data-ai-prompt="Give me one natural English expression I can use today, then chat with me about it.">Useful expression</button>'
            : '<button type="button" data-ai-prompt="根据我最近的数据，今天先学什么？">今天先学什么</button><button type="button" data-ai-prompt="帮我找找笔记里和从句有关的内容。">查找从句笔记</button><button type="button" data-ai-prompt="请解释一个我最近最需要巩固的英语知识点。">解释薄弱点</button>';
    }

    async function switchAssistantLanguage(language) {
        if (language === aiLanguage) return;
        if (aiAbort) aiAbort.abort();
        document.querySelectorAll('#ai-quick-chat [data-assistant-language]').forEach(button => button.disabled = true);
        try {
            await api('/api/ai/preferences', {
                method: 'PUT', headers: {'X-CSRF-Token': aiCsrf},
                body: JSON.stringify({language}),
            });
            aiLanguage = language; aiConversation = null;
            $('ai-chat-messages').innerHTML = '';
            $('ai-greeting').querySelector('p').textContent = language === 'en'
                ? 'Loading a greeting from your recent learning…'
                : '正在结合你最近的学习记录准备今天的第一句话…';
            await loadAssistant();
        } catch (error) {
            showToast(error.message || '语言切换失败，请重试。', 'error');
        } finally {
            document.querySelectorAll('#ai-quick-chat [data-assistant-language]').forEach(button => button.disabled = false);
        }
    }

    function addAssistantRetry(node, message, options = {}) {
        const status = document.createElement('p');
        status.className = 'assistant-stream-status';
        status.textContent = '连接中断，以上内容已保留。';
        const retry = document.createElement('button');
        retry.type = 'button'; retry.className = 'text-button'; retry.textContent = '重试回答';
        retry.addEventListener('click', () => { retry.disabled = true; sendAssistant(message, false, options); });
        node.bubble.append(status, retry);
    }

    async function sendAssistant(message, showUser = true, options = {}) {
        const input = $('ai-chat-input');
        const button = $('ai-chat-form').querySelector('button[type="submit"]');
        if (showUser && message) addChatMessage('user', message);
        input.value = '';
        const node = addChatMessage('assistant', '');
        aiAbort = new AbortController();
        button.disabled = false; button.textContent = '停止生成';
        const writer = createAITypewriter(node.copy, {onUpdate: () => { node.article.parentElement.scrollTop = node.article.parentElement.scrollHeight; }});
        try {
            const response = await fetch('/api/ai/chat', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': aiCsrf}, body: JSON.stringify({message, conversation_id: aiConversation, language: aiLanguage, ...options}), signal: aiAbort.signal});
            if (!response.ok) { const err = await response.json().catch(() => ({})); throw new Error(err.error || 'AI 请求失败。'); }
            const result = await consumeAIStream(response, {onDelta: text => writer.append(text), onDone: data => writer.finish(data.message)});
            aiConversation = result.conversation_id;
            await writer.finish(result.message); renderSafeMarkdown(node.copy, result.message); decorateStreamedMessage(node, result);
        } catch (error) {
            writer.stop();
            if (error.name === 'AbortError') node.copy.textContent += node.copy.textContent ? '\n（已停止生成）' : '已停止生成。';
            else {
                if (!node.copy.textContent) node.copy.textContent = error.message || '这次没有连接上 AI。';
                addAssistantRetry(node, message, options);
            }
        } finally { aiAbort = null; button.disabled = false; button.textContent = aiLanguage === 'en' ? 'Send' : '发送问题'; input.focus(); }
    }

    $('ai-chat-form')?.addEventListener('submit', event => { event.preventDefault(); if (aiAbort) { aiAbort.abort(); return; } const message = $('ai-chat-input').value.trim(); if (message) sendAssistant(message); });
    $('home-ai-prompts')?.addEventListener('click', event => { const button = event.target.closest('[data-ai-prompt]'); if (!button) return; $('ai-chat-input').value = button.dataset.aiPrompt; sendAssistant(button.dataset.aiPrompt); });
    document.querySelectorAll('#ai-quick-chat [data-assistant-language]').forEach(button => button.addEventListener('click', () => switchAssistantLanguage(button.dataset.assistantLanguage)));
    $('home-scene-start')?.addEventListener('click', () => {
        aiConversation = null; $('ai-chat-messages').innerHTML = '';
        sendAssistant('', false, {start_scene: true, scenario_key: $('home-scene-select').value, language: 'en'});
    });
    $('wb-select').addEventListener('change', async event => {
        try {
            await api('/api/words/current-wordbook', {method: 'PUT', body: JSON.stringify({book_id: Number(event.target.value)})});
            const [dashboard] = await Promise.all([api('/api/study/dashboard'), loadBook(event.target.value)]);
            dashboardState = dashboard;
            renderDailyProgress(dashboardState);
            showToast('当前词库已切换。', 'success');
        }
        catch (_) { showToast('词库切换失败，请重试。', 'error'); }
    });
    $('save-daily').addEventListener('click', async () => {
        const count = Number($('daily-count').value);
        $('save-daily').disabled = true;
        try {
            await api('/api/study/daily-setting', {method: 'PUT', body: JSON.stringify({count})});
            dashboardState = await api('/api/study/dashboard');
            renderDailyProgress(dashboardState);
            showToast(`每日新词和复习目标已调整为 ${count} 个。`, 'success');
        } catch (_) { showToast('每日目标保存失败，请重试。', 'error'); }
        finally { $('save-daily').disabled = false; }
    });

    intro();
    load();
    loadAssistant();
})();

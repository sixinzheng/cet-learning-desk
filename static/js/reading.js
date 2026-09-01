function readingApp() {
    return {
        articles: [], currentArticle: null, selectedAnswers: {}, annotations: {},
        markMode: null, masteryVisible: false, vocabularyTab: 'learning',
        currentLookup: null, paintStroke: null,
        fontSize: 17, activeTopic: '', startedAt: 0,
        sessionSaved: false, modalLastFocus: null, lastResultHtml: '', inventory: null,

        async init() {
            const disclosure = document.getElementById('reading-settings-disclosure');
            const toggle = document.getElementById('reading-settings-toggle');
            const mobileLayout = window.matchMedia('(max-width: 767px)');
            if (disclosure && !mobileLayout.matches) disclosure.open = true;
            try {
                const savedFontValue = window.localStorage.getItem('reading-font-size');
                const savedFontSize = savedFontValue === null ? NaN : Number(savedFontValue);
                if (Number.isFinite(savedFontSize)) this.fontSize = Math.min(24, Math.max(14, savedFontSize));
            } catch (_) {
                // Local storage can be unavailable in privacy-restricted WebViews; the in-memory default still works.
            }
            const syncDisclosure = () => {
                const open = Boolean(disclosure?.open);
                toggle?.setAttribute('aria-expanded', String(open));
                const label = toggle?.querySelector('b');
                if (label) label.textContent = open ? '收起' : '展开';
                if (open && matchMedia('(max-width: 767px)').matches) {
                    requestAnimationFrame(() => toggle.scrollIntoView({block:'nearest', behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'}));
                }
            };
            const syncDisclosureForViewport = event => {
                if (disclosure && !event.matches) disclosure.open = true;
                syncDisclosure();
            };
            disclosure?.addEventListener('toggle', syncDisclosure);
            mobileLayout.addEventListener?.('change', syncDisclosureForViewport);
            syncDisclosure();
            document.getElementById('answer-card-close')?.addEventListener('click', () => this.closeDialog('answer-card-modal'));
            document.getElementById('reading-answer-card-fab')?.addEventListener('click', () => this.openAnswerCard());
            document.getElementById('word-modal-close')?.addEventListener('click', () => this.closeDialog('word-modal'));
            document.getElementById('vocabulary-modal-close')?.addEventListener('click', () => this.closeDialog('vocabulary-modal'));
            document.querySelectorAll('[data-vocabulary-tab]').forEach(button => button.addEventListener('click', () => this.setVocabularyTab(button.dataset.vocabularyTab)));
            ['answer-card-modal', 'word-modal', 'vocabulary-modal'].forEach(id => document.getElementById(id)?.addEventListener('click', event => {
                if (event.target.id === id) this.closeDialog(id);
            }));
            document.addEventListener('keydown', event => this.handleGlobalKey(event));
            document.getElementById('reading-refill-start')?.addEventListener('click', () => this.startRefill());
            await Promise.all([this.loadArticles(), this.loadInventory()]);
            if (this.articles.length) await this.loadArticle(this.articles[0].id);
            window.setInterval(() => {
                if (this.inventory?.refill?.enabled && Number(this.inventory?.totals?.pending)) {
                    this.loadInventory();
                }
            }, 15000);
        },

        escapeHtml(value) {
            return String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
        },

        displayLabel(value) {
            return String(value ?? '').trim();
        },

        async loadInventory() {
            try {
                const previousReady = this.inventory ? Number(this.inventory?.totals?.ready) || 0 : null;
                this.inventory = await api('/api/reading/refill/status');
                this.renderInventory();
                const nextReady = Number(this.inventory?.totals?.ready) || 0;
                if (previousReady !== null && nextReady > previousReady) {
                    await this.loadArticles(this.activeTopic);
                }
            } catch (error) {
                const note = document.getElementById('reading-inventory-note');
                if (note) note.textContent = `库存状态读取失败：${error.message || '请稍后重试'}`;
            }
        },

        renderInventory() {
            const totals = this.inventory?.totals || {}, refill = this.inventory?.refill || {};
            const curation = this.inventory?.curation || {approved: false, approved_articles: 0, target: 180};
            const ready = Number(totals.ready) || 0, target = Number(totals.target) || 180;
            const output = document.getElementById('reading-inventory-ready');
            const progress = document.getElementById('reading-inventory-progress');
            const note = document.getElementById('reading-inventory-note');
            const button = document.getElementById('reading-refill-start');
            if (output) output.textContent = ready;
            if (progress) {
                progress.setAttribute('aria-valuenow', String(ready));
                progress.setAttribute('aria-valuemax', String(target));
                const bar = progress.querySelector('span'); if (bar) bar.style.width = `${Math.min(100, ready / Math.max(1, target) * 100)}%`;
            }
            if (note) {
                const pending = Number(totals.pending) || 0, failed = Number(totals.failed) || 0;
                const statuses = refill.status_counts || {};
                const pause = statuses.paused_budget ? '；已因余额或月度预算暂停'
                    : statuses.paused_config ? '；已因 AI 配置暂停' : '';
                const failedJob = (this.inventory?.recent_jobs || []).find(job => job.status === 'failed' && job.last_error);
                const reason = failedJob
                    ? ` 最近一次未通过：${String(failedJob.last_error).replace(/[。.]?$/, '。')}`
                    : '';
                note.textContent = !curation.approved
                    ? `首批题库人工策展中：当前 ${ready} 篇可用，${Number(curation.approved_articles) || 0} / ${Number(curation.target) || target} 篇已完成全量审批。期间不会自动调用 AI 或产生新费用。`
                    : ready >= target
                    ? `首批 ${target} 篇未读文章已经就绪${failed ? `；此前有 ${failed} 个生成任务未通过校验，不影响当前库存` : ''}。`
                    : (!refill.enabled && pending
                        ? `首批题库正在人工策展与来源核验：当前 ${ready} 篇已就绪，另有 ${pending} 个库存槽位尚未批准。期间不会自动调用 AI 或产生新费用。`
                        : `待生成 ${pending} 篇${failed ? `，${failed} 个任务未通过校验` : ''}${pause}；本月站内 AI 追踪花费 ¥${Number(refill.month_spend_cny || 0).toFixed(4)} / ¥5。${reason}`);
            }
            if (button) {
                if (!curation.approved) {
                    button.textContent = '首批题库人工策展中'; button.disabled = true;
                } else if (ready >= target) {
                    button.textContent = '未读库存已满'; button.disabled = true;
                } else if (!refill.enabled && Number(totals.pending)) {
                    button.textContent = '首批题库人工策展中'; button.disabled = true;
                } else if (Number(totals.failed)) {
                    button.textContent = '重试未通过任务'; button.disabled = false;
                } else if (refill.enabled) {
                    button.textContent = '自动补库已开启'; button.disabled = true;
                } else {
                    button.textContent = '开启 AI 自动补库'; button.disabled = false;
                }
            }
        },

        async startRefill() {
            const button = document.getElementById('reading-refill-start');
            if (button) { button.disabled = true; button.textContent = '正在启动…'; }
            try {
                const status = await api('/api/ai/config/status');
                if (!status.configured) throw new Error('请先在“我的 → AI 服务”配置 DeepSeek API Key。');
                const response = await fetch('/api/reading/refill/retry', {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':status.csrf_token},body:'{}'});
                const data = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(data.error || '自动补库启动失败。');
                this.inventory = data.inventory; this.renderInventory();
                showToast('自动补库已启动，生成任务会在后台继续。', 'success');
            } catch (error) {
                showToast(error.message || '自动补库启动失败。', 'error');
                if (button) { button.disabled = false; button.textContent = '重试 AI 自动补库'; }
            }
        },

        async loadArticles(topic = '') {
            const list = document.getElementById('article-list');
            if (list) list.innerHTML = '<div class="skeleton-lines">正在加载文章…</div>';
            try {
                const url = topic ? `/api/reading/articles?topic=${encodeURIComponent(topic)}` : '/api/reading/articles';
                const data = await api(url);
                this.articles = data.articles || [];
                this.renderTopicTags(data.topics || []);
                this.renderArticleList();
                if (!this.articles.length && list) list.innerHTML = '<div class="region-state region-state--empty"><strong>没有匹配文章</strong><span>换一个话题，或稍后再试。</span></div>';
            } catch (_) {
                if (list) list.innerHTML = '<div class="region-state region-state--error"><strong>文章列表加载失败</strong><button type="button" class="text-button" id="reading-list-retry">重新加载</button></div>';
                document.getElementById('reading-list-retry')?.addEventListener('click', () => this.loadArticles(topic));
            }
        },

        renderTopicTags(topics) {
            const element = document.getElementById('topic-tags');
            if (!element) return;
            element.innerHTML = '';
            ['', ...topics].forEach(topic => {
                const button = document.createElement('button');
                button.type = 'button'; button.className = 'topic-tag'; button.textContent = this.displayLabel(topic) || '全部';
                button.setAttribute('aria-pressed', String(this.activeTopic === topic));
                button.classList.toggle('active', this.activeTopic === topic);
                button.addEventListener('click', () => this.filterTopic(topic));
                element.appendChild(button);
            });
        },

        async filterTopic(topic) { this.activeTopic = topic; await this.loadArticles(topic); },

        renderArticleList() {
            const element = document.getElementById('article-list');
            if (!element) return;
            element.innerHTML = '';
            this.articles.forEach(article => {
                const button = document.createElement('button');
                button.type = 'button'; button.className = 'article-item';
                button.setAttribute('aria-current', this.currentArticle?.id === article.id ? 'true' : 'false');
                button.innerHTML = `<span class="article-item-title">${this.escapeHtml(article.title)}</span><span class="article-item-meta"><span>${this.escapeHtml(article.source)}</span><span>${Number(article.word_count) || 0} 词</span><span>${this.escapeHtml(article.stars || '')}</span></span>`;
                button.addEventListener('click', () => this.loadArticle(article.id));
                element.appendChild(button);
            });
        },

        async loadArticle(id) {
            const area = document.getElementById('article-area');
            if (area) area.innerHTML = '<div class="region-state region-state--loading">正在打开文章与题目…</div>';
            try {
                const [data, annotationData] = await Promise.all([
                    api(`/api/reading/articles/${id}`), api(`/api/reading/articles/${id}/annotations`),
                ]);
                this.currentArticle = data; this.annotations = annotationData.annotations || {};
                this.markMode = null; this.masteryVisible = false; this.currentLookup = null;
                this.selectedAnswers = {}; this.startedAt = Date.now(); this.sessionSaved = false; this.lastResultHtml = '';
                this.renderArticleList(); this.renderArticle();
                requestAnimationFrame(() => {
                    const current = document.querySelector('#article-list .article-item[aria-current="true"]');
                    current?.scrollIntoView({block:'nearest',inline:'nearest'});
                });
            } catch (error) {
                if (area) area.innerHTML = `<div class="region-state region-state--error"><strong>文章加载失败</strong><span>${this.escapeHtml(error.message || '请检查本地服务后重试。')}</span><button type="button" class="btn btn-secondary" id="reading-article-retry">重新加载</button></div>`;
                document.getElementById('reading-article-retry')?.addEventListener('click', () => this.loadArticle(id));
            }
        },

        renderArticle() {
            const article = this.currentArticle;
            if (!article) return;
            const area = document.getElementById('article-area'), stats = article.word_stats || {};
            const total = Number(stats.total_vocab || article.word_count || 0), mastered = Number(stats.mastered || 0);
            const percentage = total > 0 ? Math.round(mastered / total * 100) : 0;
            const difficulty = Math.max(0, Math.min(6, Number(article.difficulty) || 0));
            const sourceLink = article.source_url ? `<a class="reading-source-link" href="${this.escapeHtml(article.source_url)}" target="_blank" rel="noopener noreferrer">查看题材参考</a>` : '';
            const sourceMeta = article.source_url ? `<button class="reading-source-toggle" id="reading-source-toggle" type="button" aria-expanded="false" aria-controls="reading-source-panel">来源与原创说明</button>` : '';
            const sourcePanel = article.source_url ? `<div class="reading-source-panel" id="reading-source-panel" hidden><dl><div><dt>来源</dt><dd>${this.escapeHtml(article.source_name || article.source)}</dd></div><div><dt>原题</dt><dd>${this.escapeHtml(article.source_title || '未提供')}</dd></div><div><dt>发布</dt><dd>${this.escapeHtml(article.source_published_at || '未提供')}</dd></div><div><dt>检索</dt><dd>${this.escapeHtml(article.retrieved_at || '未提供')}</dd></div><div><dt>核验</dt><dd>${this.escapeHtml(article.source_verification || '未提供')}</dd></div><div><dt>说明</dt><dd>${this.escapeHtml(article.adaptation_note || article.adaptation_notes || '本站原创改写')}</dd></div></dl></div>` : '';
            area.innerHTML = `<article class="reading-task" aria-labelledby="reading-article-title">
                <header class="practice-context-bar reading-context-bar"><div class="reading-context-main"><p class="task-kicker">ARTICLE / 当前文章</p><h2 id="reading-article-title">${this.escapeHtml(article.title)}</h2><p>${this.escapeHtml(article.source)} · ${Number(article.word_count) || 0} 词 · 难度 ${difficulty} · ${this.escapeHtml(this.displayLabel(article.topic) || '未分类')}</p><div class="reading-source-actions">${sourceLink}${sourceMeta}</div>${sourcePanel}</div><div class="reading-toolbar" aria-label="正文字号"><button class="btn btn-secondary" type="button" id="reading-font-down" aria-label="缩小正文字号">A−</button><output id="reading-font-size" aria-live="polite">${this.fontSize}px</output><button class="btn btn-secondary" type="button" id="reading-font-up" aria-label="放大正文字号">A＋</button></div></header>
                <div class="reading-vocabulary-tools"><button class="reading-evidence-toggle" id="reading-mastery-toggle" type="button" aria-pressed="false"><span class="reading-evidence-copy"><span>本文词汇掌握</span><strong id="reading-mastery-percentage">${percentage}%</strong><small id="reading-mastery-count">已掌握 ${mastered} / ${total || 0}</small></span><span class="reading-mastery-track" role="progressbar" aria-label="本文词汇掌握程度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percentage}"><span style="width:${percentage}%"></span></span><b id="reading-mastery-action">显示正文标色</b></button><button class="reading-vocabulary-list-button" id="reading-vocabulary-list" type="button">查看本文词表</button></div>
                <div class="reading-mastery-legend" id="reading-mastery-legend" hidden aria-label="词汇掌握状态图例"><span data-status="unlisted">未收录</span><span data-status="stranger">陌生</span><span data-status="vague">模糊</span><span data-status="consolidating">巩固</span><span data-status="mastered">掌握</span><span data-status="familiar">熟记</span></div>
                <div class="mark-toolbar" role="toolbar" aria-label="正文标注模式"><span class="mark-toolbar__label">选择模式后滑动涂抹；再次点击退出</span><button class="mark-btn" data-mark="green" type="button" aria-pressed="false">重点理解</button><button class="mark-btn" data-mark="red" type="button" aria-pressed="false">陌生表达</button><button class="mark-btn" data-mark="erase" type="button" aria-pressed="false">清除标注</button></div>
                <div class="article-content" style="font-size:${this.fontSize}px" id="article-text">${this.renderArticleText(article.content)}</div>
                <section class="reading-after-article" aria-label="文章后续操作"><p>阅读过程中可随时使用右下角答题卡作答，已选答案会自动保留。</p><div><button class="btn btn-secondary" id="reading-ai-generate" type="button">AI 生成更多题目</button><a class="btn btn-secondary" href="/control?article_id=${Number(article.id)}">和 AI 聊本篇</a></div><div id="reading-page-result" class="answer-panel" hidden aria-live="polite"></div></section>
            </article>`;
            this.bindArticleTools(); this.updateAnswerProgress();
        },

        renderArticleText(content) {
            let wordIndex = 0;
            let tokenIndex = 0;
            const occurrences = {};
            return String(content || '').split(/(\s+)/).map(part => {
                if (/^\s+$/.test(part)) return part;
                const token = tokenIndex++;
                const match = part.match(/^([^A-Za-z]*)([A-Za-z]+(?:['’\-][A-Za-z]+)*)([^A-Za-z]*)$/);
                if (!match) return this.escapeHtml(part);
                const [, prefix, word, suffix] = match;
                const index = prefix || suffix ? 100000 + token : wordIndex++;
                const normalized = word.toLowerCase().replace('’', "'");
                const occurrence = occurrences[normalized] || 0;
                occurrences[normalized] = occurrence + 1;
                return `${this.escapeHtml(prefix)}<span class="article-word-ann${this.wordMarkClass(index)}" data-widx="${index}" data-word="${this.escapeHtml(word)}" data-occurrence="${occurrence}" tabindex="0" aria-label="${this.escapeHtml(word)}，回车查词">${this.escapeHtml(word)}</span>${this.escapeHtml(suffix)}`;
            }).join('');
        },

        bindArticleTools() {
            document.getElementById('reading-font-down')?.addEventListener('click', () => this.changeFont(-1));
            document.getElementById('reading-font-up')?.addEventListener('click', () => this.changeFont(1));
            document.getElementById('reading-ai-generate')?.addEventListener('click', () => this.generateAIQuestions());
            document.querySelectorAll('.mark-btn').forEach(button => button.addEventListener('click', () => this.setMarkMode(button.dataset.mark)));
            document.getElementById('reading-mastery-toggle')?.addEventListener('click', () => this.toggleMasteryOverlay());
            document.getElementById('reading-vocabulary-list')?.addEventListener('click', () => this.openVocabularyModal());
            document.getElementById('reading-source-toggle')?.addEventListener('click', event => {
                const panel = document.getElementById('reading-source-panel');
                if (!panel) return;
                const open = panel.hidden;
                panel.hidden = !open;
                event.currentTarget.setAttribute('aria-expanded', String(open));
            });
            const article = document.getElementById('article-text');
            article?.addEventListener('pointerdown', event => this.startPaintStroke(event));
            article?.addEventListener('pointermove', event => this.continuePaintStroke(event));
            article?.addEventListener('pointerup', event => this.finishPaintStroke(event));
            article?.addEventListener('pointercancel', event => this.finishPaintStroke(event));
            document.querySelectorAll('.article-word-ann').forEach(word => {
                word.addEventListener('dblclick', event => { event.preventDefault(); this.lookupWordClick(word.dataset.word, Number(word.dataset.occurrence) || 0); });
                word.addEventListener('click', event => {
                    if (this.markMode || !matchMedia('(pointer: coarse)').matches) return;
                    event.preventDefault();
                    this.lookupWordClick(word.dataset.word, Number(word.dataset.occurrence) || 0);
                });
                word.addEventListener('keydown', event => {
                    if (event.key === 'Enter') { event.preventDefault(); this.lookupWordClick(word.dataset.word, Number(word.dataset.occurrence) || 0); }
                    if (event.key === ' ') { event.preventDefault(); this.markWord(Number(word.dataset.widx)); }
                });
            });
            this.syncMarkMode();
            this.applyMasteryOverlay();
        },

        renderAnswerQuestions(container) {
            const questions = this.currentArticle?.questions || [];
            if (!container) return;
            if (!questions.length) { container.innerHTML = '<div class="empty-state"><h3>本文还没有题目</h3><p>可以更换文章，或在 AI 可用时生成补充题目。</p></div>'; return; }
            const typeNames = {main_idea:'主旨大意', detail:'细节理解', inference:'推理判断', word_guess:'词义猜测', attitude:'观点态度'};
            container.innerHTML = questions.map((question, questionIndex) => `<fieldset class="practice-question answer-card-question" data-question="${questionIndex}"><legend><span class="question-type">${this.escapeHtml(typeNames[question.type] || question.type || '阅读理解')}</span><strong>${questionIndex + 1}. ${this.escapeHtml(question.question)}</strong></legend><div class="practice-choice-list">${(question.options || []).map((option, optionIndex) => `<button class="choice-button reading-choice${this.selectedAnswers[questionIndex] === optionIndex ? ' is-selected' : ''}" type="button" data-question="${questionIndex}" data-option="${optionIndex}" aria-pressed="${this.selectedAnswers[questionIndex] === optionIndex}" ${this.sessionSaved ? 'disabled' : ''}><span class="choice-button__letter" aria-hidden="true">${String.fromCharCode(65 + optionIndex)}</span><span class="choice-button__copy">${this.escapeHtml(option)}</span></button>`).join('')}</div></fieldset>`).join('');
            container.querySelectorAll('.reading-choice').forEach(button => button.addEventListener('click', () => this.selectAnswer(Number(button.dataset.question), Number(button.dataset.option))));
        },

        selectAnswer(questionIndex, optionIndex) {
            if (this.sessionSaved) return;
            this.selectedAnswers[questionIndex] = optionIndex;
            document.querySelectorAll(`.reading-choice[data-question="${questionIndex}"]`).forEach(button => {
                const selected = Number(button.dataset.option) === optionIndex;
                button.classList.toggle('is-selected', selected); button.setAttribute('aria-pressed', String(selected));
            });
            this.updateAnswerProgress();
        },

        updateAnswerProgress() {
            const total = this.currentArticle?.questions?.length || 0;
            const completed = Object.keys(this.selectedAnswers).length;
            const label = `${completed} / ${total}`;
            const count = document.getElementById('reading-answer-card-count');
            const progress = document.getElementById('answer-card-progress');
            const button = document.getElementById('reading-answer-card-fab');
            if (count) count.textContent = `${completed}/${total}`;
            if (progress) progress.textContent = label;
            if (button) { button.hidden = total === 0; button.setAttribute('aria-label', `打开阅读答题卡，已答 ${completed} 题，共 ${total} 题`); }
            const submit = document.getElementById('reading-submit');
            if (submit) submit.disabled = this.sessionSaved || completed !== total;
        },

        wordMarkClass(index) {
            const marks = this.annotations[index] || [];
            if (marks.includes('green') && marks.includes('red')) return ' mark-both';
            if (marks.includes('green')) return ' mark-green';
            if (marks.includes('red')) return ' mark-red';
            return '';
        },

        applyWordMark(element, index) {
            if (!element) return;
            element.classList.remove('mark-green', 'mark-red', 'mark-both');
            const className = this.wordMarkClass(index); if (className) element.classList.add(className.trim());
        },

        setMarkMode(mode) {
            this.markMode = this.markMode === mode ? null : mode;
            this.syncMarkMode();
        },

        syncMarkMode() {
            document.querySelectorAll('.mark-btn').forEach(button => {
                const active = button.dataset.mark === this.markMode;
                button.classList.toggle('is-active', active); button.setAttribute('aria-pressed', String(active));
            });
            const article = document.getElementById('article-text');
            article?.classList.toggle('is-marking', Boolean(this.markMode));
            const toolbar = document.querySelector('.mark-toolbar');
            toolbar?.classList.toggle('is-engaged', Boolean(this.markMode));
        },

        startPaintStroke(event) {
            if (!this.markMode || event.button !== 0) return;
            const word = event.target.closest?.('.article-word-ann');
            if (!word) return;
            event.preventDefault();
            event.currentTarget.setPointerCapture?.(event.pointerId);
            this.paintStroke = {pointerId:event.pointerId, mode:this.markMode, indices:new Set()};
            this.paintWordAt(word);
        },

        continuePaintStroke(event) {
            if (!this.paintStroke || this.paintStroke.pointerId !== event.pointerId) return;
            event.preventDefault();
            const word = document.elementFromPoint(event.clientX, event.clientY)?.closest?.('.article-word-ann');
            if (word) this.paintWordAt(word);
        },

        paintWordAt(word) {
            if (!this.paintStroke || !word) return;
            const index = Number(word.dataset.widx);
            if (!Number.isFinite(index) || this.paintStroke.indices.has(index)) return;
            this.paintStroke.indices.add(index);
            const marks = this.annotations[index] || [];
            if (this.paintStroke.mode === 'erase') this.annotations[index] = [];
            else if (!marks.includes(this.paintStroke.mode)) this.annotations[index] = marks.concat(this.paintStroke.mode);
            this.applyWordMark(word, index);
        },

        finishPaintStroke(event) {
            if (!this.paintStroke || this.paintStroke.pointerId !== event.pointerId) return;
            event.preventDefault();
            const stroke = this.paintStroke;
            this.paintStroke = null;
            this.saveWordsMark([...stroke.indices], stroke.mode);
        },

        async saveWordsMark(indices, mode) {
            if (!this.currentArticle || !indices.length || !mode) return;
            try {
                await api(`/api/reading/articles/${this.currentArticle.id}/annotations/batch`, {
                    method:'POST', body:JSON.stringify({word_indices:indices, mode}),
                });
            } catch (_) {
                showToast('标注暂未保存，已恢复上次状态。', 'error');
                try {
                    const data = await api(`/api/reading/articles/${this.currentArticle.id}/annotations`);
                    this.annotations = data.annotations || {};
                    document.querySelectorAll('.article-word-ann').forEach(word => this.applyWordMark(word, Number(word.dataset.widx)));
                } catch (_) {}
            }
        },

        async setWordsMark(indices) {
            if (!this.currentArticle || !this.markMode) return;
            const mode = this.markMode;
            [...new Set(indices)].forEach(index => {
                const marks = this.annotations[index] || [];
                if (mode === 'erase') {
                    this.annotations[index] = [];
                } else if (!marks.includes(mode)) {
                    this.annotations[index] = marks.concat(mode);
                }
                this.applyWordMark(document.querySelector(`.article-word-ann[data-widx="${index}"]`), index);
            });
            await this.saveWordsMark(indices, mode);
        },

        markWord(index) {
            if (!this.currentArticle || !this.markMode) {
                showToast('请先选择一种标注模式。', 'info');
                return;
            }
            const mode = this.markMode, element = document.querySelector(`.article-word-ann[data-widx="${index}"]`), marks = this.annotations[index] || [];
            let request;
            if (mode === 'erase') { request = Promise.all(marks.map(mark => api(`/api/reading/articles/${this.currentArticle.id}/annotations`, {method:'DELETE', body:JSON.stringify({word_index:index, mark_type:mark})}))); this.annotations[index] = []; }
            else if (marks.includes(mode)) { this.annotations[index] = marks.filter(mark => mark !== mode); request = api(`/api/reading/articles/${this.currentArticle.id}/annotations`, {method:'DELETE', body:JSON.stringify({word_index:index, mark_type:mode})}); }
            else { this.annotations[index] = marks.concat(mode); request = api(`/api/reading/articles/${this.currentArticle.id}/annotations`, {method:'POST', body:JSON.stringify({word_index:index, mark_type:mode})}); }
            this.applyWordMark(element, index);
            Promise.resolve(request).catch(() => { showToast('标注暂未保存，请重试。', 'error'); this.loadArticle(this.currentArticle.id); });
        },

        masteryClass(status) {
            return ({'未收录':'unlisted','陌生':'stranger','模糊':'vague','巩固':'consolidating','掌握':'mastered','熟记':'familiar'})[status] || 'unlisted';
        },

        toggleMasteryOverlay() {
            this.masteryVisible = !this.masteryVisible;
            this.applyMasteryOverlay();
        },

        applyMasteryOverlay() {
            document.querySelectorAll('.article-word-ann').forEach(word => {
                word.classList.remove('mastery-unlisted','mastery-stranger','mastery-vague','mastery-consolidating','mastery-mastered','mastery-familiar');
                word.removeAttribute('data-mastery');
            });
            if (this.masteryVisible) {
                (this.currentArticle?.vocabulary?.words || []).forEach(item => {
                    const statusClass = this.masteryClass(item.status);
                    (item.positions || []).forEach(index => {
                        const word = document.querySelector(`.article-word-ann[data-widx="${index}"]`);
                        word?.classList.add(`mastery-${statusClass}`);
                        word?.setAttribute('data-mastery', item.status);
                    });
                });
            }
            const toggle = document.getElementById('reading-mastery-toggle');
            toggle?.setAttribute('aria-pressed', String(this.masteryVisible));
            toggle?.classList.toggle('is-active', this.masteryVisible);
            const action = document.getElementById('reading-mastery-action');
            if (action) action.textContent = this.masteryVisible ? '隐藏正文标色' : '显示正文标色';
            const legend = document.getElementById('reading-mastery-legend');
            if (legend) legend.hidden = !this.masteryVisible;
        },

        openVocabularyModal() {
            this.vocabularyTab = 'learning';
            this.renderVocabularyList();
            this.openDialog('vocabulary-modal');
        },

        renderVocabularyList() {
            const words = this.currentArticle?.vocabulary?.words || [];
            const learning = words.filter(item => !item.is_mastered);
            const mastered = words.filter(item => item.is_mastered);
            document.querySelectorAll('[data-vocabulary-tab]').forEach(button => {
                const active = button.dataset.vocabularyTab === this.vocabularyTab;
                button.classList.toggle('is-active', active);
                button.setAttribute('aria-selected', String(active));
            });
            const counts = document.getElementById('vocabulary-modal-counts');
            if (counts) counts.textContent = `待掌握 ${learning.length} · 已掌握 ${mastered.length}`;
            const list = document.getElementById('vocabulary-word-list');
            if (!list) return;
            const selected = this.vocabularyTab === 'mastered' ? mastered : learning;
            if (!selected.length) {
                list.innerHTML = `<div class="region-state region-state--empty"><strong>${this.vocabularyTab === 'mastered' ? '还没有已掌握词汇' : '本文词汇已经全部掌握'}</strong><span>切换上方分类可查看另一组词汇。</span></div>`;
                return;
            }
            list.innerHTML = selected.map(item => `<article class="vocabulary-word-row"><button class="vocabulary-word-open" type="button" data-open-word="${this.escapeHtml(item.display_word)}" data-occurrence="0"><span><strong>${this.escapeHtml(item.display_word)}</strong>${item.headword !== item.display_word ? `<small>词头 ${this.escapeHtml(item.headword)}</small>` : ''}</span><b data-status="${this.masteryClass(item.status)}">${this.escapeHtml(item.status)}</b></button>${item.found ? `<button class="vocabulary-favorite${item.is_favorite ? ' is-active' : ''}" type="button" data-favorite-word="${Number(item.id)}" aria-pressed="${Boolean(item.is_favorite)}">${item.is_favorite ? '已收藏' : '收藏'}</button>` : `<button class="vocabulary-enrich" type="button" data-open-word="${this.escapeHtml(item.display_word)}" data-occurrence="0">AI 补全</button>`}</article>`).join('');
            list.querySelectorAll('[data-open-word]').forEach(button => button.addEventListener('click', () => {
                this.closeDialog('vocabulary-modal');
                this.lookupWordClick(button.dataset.openWord, Number(button.dataset.occurrence) || 0);
            }));
            list.querySelectorAll('[data-favorite-word]').forEach(button => button.addEventListener('click', () => this.toggleVocabularyFavorite(Number(button.dataset.favoriteWord))));
        },

        setVocabularyTab(tab) {
            if (!['learning','mastered'].includes(tab)) return;
            this.vocabularyTab = tab;
            this.renderVocabularyList();
        },

        async toggleVocabularyFavorite(wordId) {
            try {
                const result = await api('/api/words/favorite', {method:'PUT', body:JSON.stringify({word_id:wordId})});
                (this.currentArticle?.vocabulary?.words || []).forEach(item => {
                    if (Number(item.id) === wordId) item.is_favorite = Boolean(result.is_favorite);
                });
                if (this.currentLookup && Number(this.currentLookup.id) === wordId) this.currentLookup.is_favorite = Boolean(result.is_favorite);
                this.renderVocabularyList();
                showToast(result.is_favorite ? '已收藏本词。' : '已取消收藏。', 'success');
            } catch (error) {
                showToast(error.message || '收藏状态保存失败。', 'error');
            }
        },

        async refreshVocabulary() {
            if (!this.currentArticle) return;
            const fresh = await api(`/api/reading/articles/${this.currentArticle.id}`);
            this.currentArticle.vocabulary = fresh.vocabulary;
            this.currentArticle.word_stats = fresh.word_stats;
            const stats = fresh.word_stats || {};
            const percentage = Number(stats.percentage) || 0;
            const percentageNode = document.getElementById('reading-mastery-percentage');
            const countNode = document.getElementById('reading-mastery-count');
            const track = document.querySelector('.reading-mastery-track');
            if (percentageNode) percentageNode.textContent = `${percentage}%`;
            if (countNode) countNode.textContent = `已掌握 ${Number(stats.mastered) || 0} / ${Number(stats.total_vocab) || 0}`;
            if (track) {
                track.setAttribute('aria-valuenow', String(percentage));
                const bar = track.querySelector('span'); if (bar) bar.style.width = `${percentage}%`;
            }
            this.applyMasteryOverlay();
        },

        changeFont(delta) {
            this.fontSize = Math.min(24, Math.max(14, this.fontSize + delta));
            const article = document.getElementById('article-text');
            const output = document.getElementById('reading-font-size');
            if (article) article.style.fontSize = `${this.fontSize}px`;
            if (output) output.textContent = `${this.fontSize}px`;
            try { window.localStorage.setItem('reading-font-size', String(this.fontSize)); } catch (_) {}
        },

        async lookupWordClick(word, occurrence = 0) {
            const detail = document.getElementById('lookup-detail');
            document.getElementById('lookup-word-title').textContent = word;
            const pronounce = document.getElementById('lookup-pronounce');
            if (pronounce) { pronounce.setAttribute('aria-label', `播放 ${word} 的发音`); pronounce.onclick = () => speakEnglish(word); }
            detail.innerHTML = '<div class="region-state region-state--loading">正在查询词库…</div>';
            this.openDialog('word-modal');
            try {
                const data = await api(`/api/reading/lookup-word?word=${encodeURIComponent(word)}`);
                this.currentLookup = {...data, surface_word:word, occurrence};
                if (pronounce && data.found) pronounce.onclick = () => speakEnglish(word, {wordId: data.id, audioUrl: data.audio_url});
                this.renderLookupDetail();
            } catch (error) { detail.innerHTML = `<div class="region-state region-state--error"><strong>查词失败</strong><span>${this.escapeHtml(error.message || '请稍后重试。')}</span></div>`; }
        },

        renderLookupDetail() {
            const detail = document.getElementById('lookup-detail');
            const data = this.currentLookup;
            if (!detail || !data) return;
            if (!data.found) {
                detail.innerHTML = `<div class="lookup-empty"><strong>当前词库没有收录</strong><p>可以继续使用设备英文语音，也可以按需调用一次 AI；成功后详情会保存在本机，下次直接读取。</p><button class="btn btn-primary" id="lookup-enrich" type="button">AI 补全这个词</button></div>`;
                document.getElementById('lookup-enrich')?.addEventListener('click', () => this.enrichCurrentWord(false));
                return;
            }
            const ai = data.ai_detail;
            const matchNote = data.match_type === 'inflection' ? `<p class="lookup-match-note">文中词形 <b>${this.escapeHtml(data.surface_word)}</b> 已匹配词头 <b>${this.escapeHtml(data.word)}</b>，无需 AI 也能读取基础词义。</p>` : '';
            const aiBlock = ai ? `<section class="lookup-ai-detail"><div class="lookup-ai-heading"><div><span>AI 补充 · 已缓存在本机</span><strong>${this.escapeHtml(ai.context_meaning)}</strong></div><button class="text-button" id="lookup-refresh-ai" type="button">重新完善</button></div>${ai.form_note ? `<p>${this.escapeHtml(ai.form_note)}</p>` : ''}<dl><div><dt>当前语境例句</dt><dd><b>${this.escapeHtml(ai.context_example?.en || '')}</b><span>${this.escapeHtml(ai.context_example?.zh || '')}</span></dd></div><div><dt>其他常见词义</dt><dd>${(ai.additional_meanings || []).map(item => `<span>${this.escapeHtml(item)}</span>`).join('') || '<span>没有额外高频词义</span>'}</dd></div><div><dt>${this.escapeHtml(ai.other_example?.meaning || '其他词义例句')}</dt><dd><b>${this.escapeHtml(ai.other_example?.en || '')}</b><span>${this.escapeHtml(ai.other_example?.zh || '')}</span></dd></div></dl></section>` : `<section class="lookup-ai-offer"><strong>需要更完整的语境解释？</strong><p>AI 会补充当前语境词义、其他常见词义和两条例句，并只保存为独立补充，不改动基础词库。</p><button class="btn btn-secondary" id="lookup-enrich" type="button">让 AI 完善</button></section>`;
            detail.innerHTML = `<div class="lookup-result"><div class="lookup-result__facts"><p>${this.escapeHtml(data.phonetic || '')} ${this.escapeHtml(data.part_of_speech || '')}</p><strong>${this.escapeHtml((data.meanings || []).join('；'))}</strong><small>考频 ${Number(data.frequency) || 0} / 5 · 当前状态 ${this.escapeHtml(data.status || '陌生')}</small></div>${matchNote}<button class="lookup-favorite${data.is_favorite ? ' is-active' : ''}" id="lookup-favorite" type="button" aria-pressed="${Boolean(data.is_favorite)}">${data.is_favorite ? '已收藏' : '收藏本词'}</button>${aiBlock}</div>`;
            document.getElementById('lookup-favorite')?.addEventListener('click', async () => {
                await this.toggleVocabularyFavorite(Number(data.id));
                this.renderLookupDetail();
            });
            document.getElementById('lookup-enrich')?.addEventListener('click', () => this.enrichCurrentWord(false));
            document.getElementById('lookup-refresh-ai')?.addEventListener('click', event => {
                if (event.currentTarget.dataset.confirmed !== 'true') {
                    event.currentTarget.dataset.confirmed = 'true';
                    event.currentTarget.textContent = '再次点击确认调用 AI';
                    window.setTimeout(() => {
                        if (event.currentTarget?.isConnected) {
                            event.currentTarget.dataset.confirmed = 'false';
                            event.currentTarget.textContent = '重新完善';
                        }
                    }, 5000);
                    return;
                }
                this.enrichCurrentWord(true);
            });
        },

        async enrichCurrentWord(refresh) {
            if (!this.currentLookup || !this.currentArticle) return;
            const button = document.getElementById(refresh ? 'lookup-refresh-ai' : 'lookup-enrich');
            if (button) { button.disabled = true; button.textContent = 'AI 正在整理…'; }
            try {
                const status = await api('/api/ai/config/status');
                if (!status.configured) throw new Error('请先到“我的 → AI 服务”配置 DeepSeek API Key。');
                const response = await fetch('/api/ai/enrich-word', {
                    method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':status.csrf_token},
                    body:JSON.stringify({article_id:this.currentArticle.id,surface_word:this.currentLookup.surface_word,occurrence:this.currentLookup.occurrence,refresh:Boolean(refresh)}),
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(data.error || 'AI 单词详情生成失败。');
                this.currentLookup = {...data, surface_word:this.currentLookup.surface_word, occurrence:this.currentLookup.occurrence};
                document.getElementById('lookup-word-title').textContent = this.currentLookup.surface_word;
                const pronounce = document.getElementById('lookup-pronounce');
                if (pronounce && data.found) pronounce.onclick = () => speakEnglish(data.surface_form || data.word, {wordId:data.id,audioUrl:data.audio_url});
                this.renderLookupDetail();
                await this.refreshVocabulary();
                showToast(data.cached ? '已读取本机缓存。' : 'AI 详情已保存到本机。', 'success');
            } catch (error) {
                showToast(error.message || 'AI 单词详情生成失败。', 'error');
                this.renderLookupDetail();
            }
        },

        openAnswerCard() {
            const questions = this.currentArticle?.questions || [];
            if (!questions.length) { showToast('本文还没有可作答题目。', 'warning'); return; }
            const body = document.getElementById('answer-card-body');
            body.innerHTML = `<div id="reading-questions" class="answer-card-question-list"></div><div id="reading-result" class="answer-panel" ${this.lastResultHtml ? '' : 'hidden'} aria-live="polite">${this.lastResultHtml}</div><div class="answer-card-actions"><button class="btn btn-primary" id="reading-submit" type="button">${this.sessionSaved ? '本轮已完成' : '提交本轮成绩'}</button></div>`;
            this.renderAnswerQuestions(document.getElementById('reading-questions'));
            document.getElementById('reading-submit')?.addEventListener('click', () => this.completeSession());
            this.updateAnswerProgress();
            this.openDialog('answer-card-modal');
        },

        openDialog(id) {
            const modal = document.getElementById(id); if (!modal) return;
            this.modalLastFocus = document.activeElement; modal.hidden = false; modal.classList.add('is-open');
            requestAnimationFrame(() => modal.querySelector('[role="dialog"]')?.focus());
        },

        closeDialog(id) {
            const modal = document.getElementById(id); if (!modal) return;
            modal.hidden = true; modal.classList.remove('is-open');
            if (this.modalLastFocus && document.contains(this.modalLastFocus)) this.modalLastFocus.focus();
        },

        handleGlobalKey(event) {
            const openModal = document.querySelector('.modal-overlay.is-open');
            if (openModal) {
                if (event.key === 'Escape') { event.preventDefault(); this.closeDialog(openModal.id); return; }
                if (openModal.id === 'answer-card-modal' && !this.sessionSaved && /^[a-d1-4]$/i.test(event.key)) {
                    const unanswered = (this.currentArticle?.questions || []).findIndex((_, index) => !Object.hasOwn(this.selectedAnswers, index));
                    const optionIndex = /^[1-4]$/.test(event.key) ? Number(event.key) - 1 : event.key.toUpperCase().charCodeAt(0) - 65;
                    const option = openModal.querySelector(`.reading-choice[data-question="${unanswered}"][data-option="${optionIndex}"]`);
                    if (option) { event.preventDefault(); option.click(); option.focus(); }
                    return;
                }
                if (event.key === 'Tab') this.trapFocus(event, openModal);
                return;
            }
            if (!this.currentArticle || this.sessionSaved || !/^[a-d1-4]$/i.test(event.key)) return;
            const unanswered = (this.currentArticle.questions || []).findIndex((_, index) => !Object.hasOwn(this.selectedAnswers, index));
            if (unanswered < 0) return;
            const optionIndex = /^[1-4]$/.test(event.key) ? Number(event.key) - 1 : event.key.toUpperCase().charCodeAt(0) - 65;
            const option = document.querySelector(`.reading-choice[data-question="${unanswered}"][data-option="${optionIndex}"]`);
            if (option) { event.preventDefault(); option.click(); option.focus(); }
        },

        trapFocus(event, modal) {
            const focusable = Array.from(modal.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])')).filter(element => !element.disabled && !element.hidden);
            if (!focusable.length) return;
            const first = focusable[0], last = focusable.at(-1);
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        },

        async completeSession() {
            if (this.sessionSaved || !this.currentArticle) return;
            const questions = this.currentArticle.questions || [];
            if (Object.keys(this.selectedAnswers).length !== questions.length) return;
            const submit = document.getElementById('reading-submit'), resultArea = document.getElementById('reading-result');
            if (!submit || !resultArea) return;
            submit.disabled = true; submit.textContent = '正在核对并保存…';
            const answers = {}; questions.forEach((question, index) => { answers[String(question.id)] = String.fromCharCode(65 + this.selectedAnswers[index]); });
            try {
                const result = await api('/api/practice/reading/complete', {method:'POST', body:JSON.stringify({article_id:this.currentArticle.id, answers, duration_seconds:Math.max(60, Math.round((Date.now() - this.startedAt) / 1000)), idempotency_key:`reading-${this.currentArticle.id}-${this.startedAt}`})});
                this.sessionSaved = true; resultArea.hidden = false;
                this.lastResultHtml = `<strong>本轮能力分 ${this.escapeHtml(result.score)}</strong><p>成绩已进入阅读理解与段位可信度计算。</p><a class="text-link" href="/growth#score-ledger">查看计分账单</a><div id="reading-ai-comments"></div>`;
                resultArea.innerHTML = this.lastResultHtml;
                const pageResult = document.getElementById('reading-page-result');
                if (pageResult) { pageResult.hidden = false; pageResult.innerHTML = `<strong>本轮已完成 · ${this.escapeHtml(result.score)} 分</strong><p>可再次打开答题卡查看本轮结果。</p>`; }
                document.querySelectorAll('.reading-choice').forEach(button => { button.disabled = true; });
                submit.textContent = '本轮已完成'; this.updateAnswerProgress(); showToast('阅读成绩已进入段位账单。', 'success'); this.loadAIGradeComments(answers);
                this.loadArticles(this.activeTopic); this.loadInventory();
            } catch (error) {
                submit.disabled = false; submit.textContent = '重新提交本轮成绩'; resultArea.hidden = false;
                resultArea.innerHTML = `<div class="region-state region-state--error"><strong>成绩暂未保存</strong><span>${this.escapeHtml(error.message || '请检查本地服务后重试。')}</span></div>`;
            }
        },

        async loadAIGradeComments(answers) {
            try {
                const status = await api('/api/ai/config/status'); if (!status.configured) return;
                const response = await fetch('/api/ai/grade-reading', {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':status.csrf_token}, body:JSON.stringify({article_id:this.currentArticle.id, answers})});
                if (!response.ok) return;
                const data = await response.json(), area = document.getElementById('reading-ai-comments');
                if (!area || !(data.comments || []).length) return;
                area.innerHTML = `<div class="grade-comments"><h3>AI 逐题点评</h3>${data.comments.map((comment, index) => `<article class="grade-comment ${comment.correct ? 'is-correct' : 'is-wrong'}"><strong>第 ${index + 1} 题 · ${comment.correct ? '正确' : '需要订正'}</strong><p>${this.escapeHtml(comment.comment || '')}</p></article>`).join('')}</div>`;
            } catch (_) {
                const area = document.getElementById('reading-ai-comments'); if (area) area.innerHTML = '<p class="muted">AI 点评暂时不可用，不影响本轮成绩。</p>';
            }
        },

        async generateAIQuestions() {
            if (!this.currentArticle) return;
            const button = document.getElementById('reading-ai-generate'); button.disabled = true; button.textContent = 'AI 生成中…';
            try {
                const status = await api('/api/ai/config/status');
                const response = await fetch('/api/ai/generate-reading', {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':status.csrf_token}, body:JSON.stringify({article_id:this.currentArticle.id, count:5})});
                if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.error || '生成失败'); }
                const result = await response.json(); showToast(`已新增 ${result.generated} 道题。`, 'success'); await this.loadArticle(this.currentArticle.id);
            } catch (error) { showToast(error.message || 'AI 生成失败，请稍后重试。', 'error'); }
            finally { const current = document.getElementById('reading-ai-generate'); if (current) { current.disabled = false; current.textContent = 'AI 生成更多题目'; } }
        },
    };
}

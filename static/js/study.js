function studyApp() {
    return {
        phase: 'loading',   // loading | quiz | card | spelling | done | empty
        words: [],
        wordState: {},      // {id: {consecutive, passed, wrongs}}
        wordSentences: {},  // id → sentences[] 缓存（例句展示/批次反馈共用）
        currentWordId: null,
        currentWord: '',
        currentPhonetic: '',
        currentMeanings: '',
        currentStars: '',
        currentTag: '',
        currentTagClass: '',
        currentStatus: '',
        hasLinks: false,
        quizSentence: '',
        quizSentenceFull: '',
        quizSentenceZh: '',
        quizOptions: [],
        quizAnswer: 0,
        sentences: [],
        spellingSentence: '',
        spellingZh: '',
        spellingInput: '',
        spellingResult: null,
        spellingAnswer: '',
        spellingLocked: false,   // 提交拼写后锁定输入框，防止继续修改
        spellingQueue: [],
        spellingIdx: 0,
        done: 0,
        total: 0,
        quizAnswered: false,
        selectedIdx: -1,
        lastAnswerCorrect: true,
        // goNext() 始终从当前项的下一项开始，因此初次加载要位于首项之前。
        currentIndex: -1,
        popupVisible: false,
        popupWord: '', popupPhonetic: '', popupMeanings: '', popupSentences: [],
        popupWordId: null,         // 弹窗展示的词 id（可能与当前学习词不同）
        popupLinks: [],            // 当前词已关联的标签组 [{tag_name, words:[...]}]
        isFavorite: false,         // 当前学习词是否已收藏
        popupFavorite: false,      // 弹窗词的收藏态
        linkPanelOpen: false,      // 是否展开「创建关联标签」表单
        linkTagName: '',
        linkSearchQ: '',
        linkSearchResults: [],
        linkSelected: {},          // {word_id: true} 已勾选的关联词
        _keyBound: null,

        get ringPct() { return this.total ? Math.round(this.done / this.total * 100) : 0; },
        get ringStyle() {
            const c = 2 * Math.PI * 27;
            const off = c * (1 - (this.total ? this.done / this.total : 0));
            return 'stroke-dashoffset:' + off.toFixed(1);
        },
        get batchItems() {
            return this.words.map(w => {
                const sen = (this.wordSentences[w.id] && this.wordSentences[w.id][0]) ? this.wordSentences[w.id][0].content : '';
                return {
                    id: w.id, word: w.word,
                    meaning: (()=>{try{return JSON.parse(w.meanings||'[]').join('；');}catch{return w.meanings||'';}})(),
                    sentence: sen,
                    wrongs: (this.wordState[w.id] && this.wordState[w.id].wrongs) || 0,
                };
            });
        },
        get wrongBatchCount() { return this.batchItems.filter(i => i.wrongs > 0).length; },

        playPronunciation(word) {
            const item = this.words.find(candidate => candidate.word === word) || {};
            speakEnglish(word, {wordId: item.id, audioUrl: item.audio_url});
        },

        async init() {
            if (!this._keyBound) {
                this._keyBound = this.onKeydown.bind(this);
                window.addEventListener('keydown', this._keyBound);
            }
            try {
                const data = await api('/api/study/new-words');
                this.words = data.words || [];
                this.total = this.words.length;
                if (this.words.length === 0) { this.phase = 'empty'; return; }
                this.words.forEach(w => {
                    this.wordState[w.id] = { consecutive: 0, passed: false, wrongs: 0 };
                });
                this.currentIndex = -1;
                this.done = 0;
                this.goNext();
            } catch (e) { this.phase = 'empty'; showToast(e.message || '新词加载失败，请刷新页面重试。', 'error'); }
        },

        // 队列推进：找下一个未过关的词；全过 → 拼写验证
        goNext() {
            this.phase = 'loading';
            const len = this.words.length;
            let next = -1;
            for (let k = 1; k <= len; k++) {
                const i = (this.currentIndex + k) % len;
                if (!this.wordState[this.words[i].id].passed) { next = i; break; }
            }
            if (next === -1) {
                this.spellingQueue = [...this.words];
                this.spellingIdx = 0;
                this.phase = 'spelling';
                this.loadSpellingWord();
                showToast('全部通过! 进入拼写验证', 'success');
                return;
            }
            this.currentIndex = next;
            setTimeout(() => this.loadWord(this.words[next]), 50);
        },

        // 答错/标模糊 → 当日即时复现：插到当前位置后 4~5 位，不打断过关节奏
        requeueCurrent() {
            const from = this.currentIndex;
            if (this.words.length <= 1) return;
            const w = this.words.splice(from, 1)[0];
            const pos = Math.min(from + 4 + Math.floor(Math.random() * 2), this.words.length);
            this.words.splice(pos, 0, w);
            this.currentIndex = from;  // 从原位置继续，被移走的词 4~5 位后再现
        },

        escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); },

        async loadWord(w) {
            this.currentWordId = w.id;
            this.currentWord = w.word;
            this.currentPhonetic = w.phonetic || '';
            this.currentMeanings = (() => { try { return JSON.parse(w.meanings||'[]').join('；'); } catch { return w.meanings||''; } })();
            // 考频星级
            const freq = w.frequency || 1;
            this.currentStars = '★'.repeat(freq);
            // 匹配度标签
            const status = w.status || '陌生';
            this.currentStatus = status;
            if (freq >= 4 && status === '陌生') { this.currentTag = '必学'; this.currentTagClass = 'must'; }
            else if (freq >= 3 && status === '模糊') { this.currentTag = '优先'; this.currentTagClass = 'priority'; }
            else if (status === '巩固') { this.currentTag = '巩固'; this.currentTagClass = 'follow'; }
            else if (freq >= 3 && status === '掌握') { this.currentTag = '跟进'; this.currentTagClass = 'follow'; }
            else if (status === '熟记') { this.currentTag = '已收割'; this.currentTagClass = 'done-tag'; }
            else if (freq <= 2 && (status === '陌生' || status === '模糊')) { this.currentTag = '搁置'; this.currentTagClass = 'skip'; }
            else { this.currentTag = ''; this.currentTagClass = ''; }
            this.sentences = [];
            this.quizSentence = '';
            this.quizSentenceFull = '';
            this.quizSentenceZh = '';
            const esc = this.escapeRe(w.word);
            try {
                const detail = await api('/api/words/word/' + w.id);
                this.wordSentences[w.id] = detail.sentences || [];
                this.sentences = this.wordSentences[w.id];
                const ex = detail.spelling_example;
                if (ex && ex.en) {
                    // 干净例句：挖空词形变化，避免泄露答案/不雅短语
                    this.quizSentence = ex.en;
                    this.quizSentenceFull = ex.full || ex.en.replace(/____/g, w.word);
                    this.quizSentenceZh = ex.zh || '';
                } else if (this.sentences.length > 0) {
                    this.quizSentenceFull = this.sentences[0].content;
                    this.quizSentenceZh = this.sentences[0].translation || '';
                    this.quizSentence = this.sentences[0].content.replace(new RegExp(esc,'gi'), '____');
                }
                this.hasLinks = (detail.links || []).length > 0;
                this.isFavorite = !!detail.is_favorite;
            } catch(e) { showToast('例句与收藏状态暂未加载，不影响继续答题。', 'warning'); }
            if (!this.quizSentence) {
                this.quizSentence = '请选出 "' + w.word + '" 的正确释义：';
                this.quizSentenceFull = this.quizSentence;
            }

            // 选项
            const allM = (()=>{try{return JSON.parse(w.meanings||'[]');}catch{return[w.meanings];}})();
            const correct = allM.join('；');
            this.quizOptions = [correct];
            const distractors = this.words.filter(x=>x.id!==w.id).sort(()=>Math.random()-0.5).slice(0,3)
                .map(x=>{try{return JSON.parse(x.meanings||'[]').join('；');}catch{return x.meanings;}});
            this.quizOptions.push(...distractors);
            this.quizOptions = this.shuffle(this.quizOptions);
            this.quizAnswer = this.quizOptions.indexOf(correct);
            if (this.quizAnswer < 0) this.quizAnswer = 0;

            this.spellingInput = ''; this.spellingResult = null; this.spellingAnswer = '';
            this.quizAnswered = false; this.selectedIdx = -1; this.lastAnswerCorrect = true;
            try { await api('/api/study/start-learning', {method:'POST', body:JSON.stringify({word_id:w.id})}); }
            catch(e) { showToast('本词开始状态暂未保存，答题仍可继续。', 'warning'); }
            this.phase = 'quiz';
        },

        async answerQuiz(idx) {
            if (this.quizAnswered) return;
            this.quizAnswered = true; this.selectedIdx = idx;
            const correct = idx === this.quizAnswer;
            playSound(correct ? 'correct' : 'wrong');
            this.lastAnswerCorrect = correct;
            const st = this.wordState[this.currentWordId];
            if (correct) {
                st.consecutive++;
                if (st.consecutive >= 3) { st.passed = true; this.done++; showToast(this.currentWord+' 已掌握!', 'success'); }
                else { showToast(`正确! 还需${3 - st.consecutive}次`, 'success'); }
            } else {
                st.consecutive = 0;
                st.wrongs = (st.wrongs||0) + 1;
                this.requeueCurrent();
                showToast('选错了，这个词稍后再现', 'warning');
            }
            try { await api('/api/study/answer', {method:'POST', body:JSON.stringify({word_id:this.currentWordId, correct, mode:'learn'})}); }
            catch(e) { showToast('本题结果暂未计入记录，请稍后重试。', 'error'); }
            setTimeout(() => {
                this.phase = 'card';
                requestAnimationFrame(() => requestAnimationFrame(() => this.focusAnswerCardOnMobile()));
            }, 300);
        },

        focusAnswerCardOnMobile() {
            if (!window.matchMedia('(max-width: 767px)').matches) return;
            const card = document.getElementById('study-card-phase');
            if (!card) return;
            const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            card.scrollIntoView({block:'start', behavior:reduceMotion ? 'auto' : 'smooth'});
            card.querySelector('.mode-header')?.focus({preventScroll:true});
        },

        retryQuiz() {
            this.quizAnswered = false; this.selectedIdx = -1;
            this.quizOptions = this.shuffle(this.quizOptions);
            const w = this.words.find(w=>w.id===this.currentWordId);
            const allM = (()=>{try{return JSON.parse(w.meanings||'[]').join('；');}catch{return w.meanings;}})();
            this.quizAnswer = this.quizOptions.indexOf(allM);
            if (this.quizAnswer < 0) this.quizAnswer = 0;
            this.phase = 'quiz';
        },

        nextAfterCard() { this.goNext(); },

        slayWord() {
            const btn = document.querySelector('.btn-slay');
            if (btn) { btn.classList.add('slain'); setTimeout(() => btn.classList.remove('slain'), 600); }
            playSlaySound();
            this.setStatus('熟记');
        },

        async setStatus(status) {
            const previous = this.currentStatus;
            this.currentStatus = status;
            try { await api('/api/words/word/' + this.currentWordId + '/status', {method:'PUT', body:JSON.stringify({status})}); }
            catch(e) { this.currentStatus = previous; showToast('熟悉度保存失败，请重试。', 'error'); return; }
            const st = this.wordState[this.currentWordId];
            if (status === '熟记') {
                if (st && !st.passed) { st.passed = true; this.done++; }
                this.spellingQueue = this.spellingQueue.filter(w => w.id !== this.currentWordId);
                showToast('已标记为 熟记', 'info');
                this.goNext();
            } else {
                if (st && st.passed) { st.passed = false; st.consecutive = 0; this.done = Math.max(0, this.done - 1); }
                if (st && (status === '陌生' || status === '模糊')) { st.consecutive = 0; this.requeueCurrent(); }
                showToast('已标记为 ' + status, 'info');
            }
        },

        async showWordPopup(wordId) {
            const w = this.words.find(w=>w.id===wordId);
            if (!w) return;
            this.popupWordId = wordId;
            this.popupWord = w.word;
            this.popupPhonetic = w.phonetic || '';
            this.popupMeanings = (()=>{try{return JSON.parse(w.meanings||'[]').join('；');}catch{return w.meanings||'';}})();
            this.popupSentences = [];
            this.popupLinks = [];
            this.linkPanelOpen = false;
            this.linkTagName = '';
            this.linkSearchQ = '';
            this.linkSearchResults = [];
            this.linkSelected = {};
            this.popupVisible = true;
            try {
                const detail = await api('/api/words/word/' + wordId);
                this.popupSentences = (detail.sentences || []).slice(0, 4);
                this.popupLinks = detail.links || [];
                this.popupFavorite = !!detail.is_favorite;
                // 默认把弹窗词本身也加入关联（创建标签时以弹窗词为主体）
                this.linkSelected = { [wordId]: true };
            } catch(e) {}
        },

        // === 收藏 ===
        async toggleFavorite() {
            const wid = this.currentWordId;
            try {
                const resp = await api('/api/words/favorite', {method:'PUT', body:JSON.stringify({word_id: wid})});
                this.isFavorite = !!resp.is_favorite;
                this.popupFavorite = this.popupWordId === wid ? !!resp.is_favorite : this.popupFavorite;
                showToast(this.isFavorite ? '已加入收藏词库' : '已取消收藏', this.isFavorite ? 'success' : 'info');
            } catch(e) { showToast('操作失败', 'error'); }
        },
        async togglePopupFavorite() {
            const wid = this.popupWordId;
            if (!wid) return;
            try {
                const resp = await api('/api/words/favorite', {method:'PUT', body:JSON.stringify({word_id: wid})});
                this.popupFavorite = !!resp.is_favorite;
                if (wid === this.currentWordId) this.isFavorite = !!resp.is_favorite;
                showToast(resp.is_favorite ? '已加入收藏词库' : '已取消收藏', resp.is_favorite ? 'success' : 'info');
            } catch(e) { showToast('操作失败', 'error'); }
        },

        // === 相关单词标签：创建交互 ===
        async searchLinkWords() {
            const q = (this.linkSearchQ || '').trim();
            if (!q) { this.linkSearchResults = []; return; }
            try {
                const data = await api('/api/words/search?q=' + encodeURIComponent(q));
                this.linkSearchResults = (data.words || []).slice(0, 8)
                    .filter(w => !this.linkSelected[w.id]);
            } catch(e) { this.linkSearchResults = []; }
        },
        toggleLinkSel(id) {
            if (this.linkSelected[id]) { delete this.linkSelected[id]; }
            else { this.linkSelected[id] = true; }
        },
        async saveLink() {
            const tag = (this.linkTagName || '').trim();
            const ids = Object.keys(this.linkSelected).map(Number).filter(Boolean);
            if (!tag) { showToast('请输入标签名', 'error'); return; }
            if (ids.length < 2) { showToast('请至少选择 1 个关联词', 'error'); return; }
            const baseId = this.popupWordId || this.currentWordId;
            try {
                await api('/api/words/word/' + baseId + '/link', {
                    method: 'POST',
                    body: JSON.stringify({ tag_name: tag, word_ids: ids })
                });
                showToast('已创建关联标签「' + tag + '」', 'success');
                this.linkPanelOpen = false;
                // 刷新弹窗词的 links
                try {
                    const detail = await api('/api/words/word/' + baseId);
                    this.popupLinks = detail.links || [];
                } catch(e) {}
                // 若弹窗词即当前学习词，同步遇词提示
                if (baseId === this.currentWordId) this.hasLinks = this.popupLinks.length > 0;
            } catch(e) { showToast('创建失败：' + (e.message || ''), 'error'); }
        },
        openLinkPanel() {
            this.linkPanelOpen = true;
            this.linkTagName = '';
            this.linkSearchQ = '';
            this.linkSearchResults = [];
            this.linkSelected = { [this.popupWordId || this.currentWordId]: true };
        },

        // === 拼写阶段 ===
        async loadSpellingWord() {
            if (this.spellingIdx >= this.spellingQueue.length) { this.phase = 'done'; return; }
            const w = this.spellingQueue[this.spellingIdx];
            this.currentWordId = w.id; this.currentWord = w.word;
            this.currentMeanings = (() => { try { return JSON.parse(w.meanings||'[]').join('；'); } catch { return w.meanings||''; } })();
            this.spellingInput = ''; this.spellingResult = null; this.spellingAnswer = '';
            this.spellingLocked = false;
            this.spellingSentence = '';
            this.spellingZh = '';
            let sentences = this.wordSentences[w.id];
            if (!sentences) {
                try {
                    const detail = await api('/api/words/word/' + w.id);
                    sentences = detail.sentences || [];
                    this.wordSentences[w.id] = sentences;
                    // 干净拼写例句（后端已挖空词形变化）
                    const ex = detail.spelling_example;
                    if (ex && ex.en) {
                        this.spellingSentence = ex.en;
                        this.spellingZh = ex.zh || '';
                    }
                } catch(e) { sentences = []; }
            }
            if (!this.spellingSentence && sentences.length > 0) {
                const esc = this.escapeRe(w.word);
                this.spellingSentence = sentences[0].content.replace(new RegExp(esc,'gi'), '____');
                this.spellingZh = sentences[0].translation || '';
            }
            if (!this.spellingSentence) {
                this.spellingSentence = this.currentMeanings;
            }
            setTimeout(() => document.getElementById('spell-input')?.focus(), 60);
        },
        async checkSpelling() {
            const input = this.spellingInput.trim().toLowerCase();
            if (!input) return;
            const el = document.getElementById('spell-input');
            try {
                const resp = await api('/api/study/spelling-check', {method:'POST', body:JSON.stringify({word_id:this.currentWordId, spelling:input})});
                const st = this.wordState[this.currentWordId];
                this.spellingLocked = true;  // 提交后锁定输入框，不能继续修改
                if (resp.correct) {
                    // 输对 → 显示正确并允许继续
                    this.spellingResult = true;
                    playSound('correct');
                    if (el) el.blur();  // 失焦，让全局键盘接管「学下一个」
                } else {
                    // 输错 → 显示正确拼写 + 记错次数+1；通过「重新输入」按钮解锁重输
                    this.spellingResult = false;
                    this.spellingAnswer = resp.word || '';
                    if (st) st.wrongs = (st.wrongs||0) + 1;
                    playSound('wrong');
                }
            } catch(e) { showToast('验证失败','error'); }
        },
        nextWord() { this.spellingIdx++; this.loadSpellingWord(); },
        retrySpelling() {
            this.spellingLocked = false;
            this.spellingResult = null;
            this.spellingInput = '';
            const el = document.getElementById('spell-input');
            if (el) el.focus();
        },
        get spellingWrongs() {
            const st = this.wordState[this.currentWordId];
            return st ? (st.wrongs || 0) : 0;
        },

        // === 键盘 ===
        onKeydown(e) {
            const tag = document.activeElement && document.activeElement.tagName;
            const typing = tag === 'INPUT' || tag === 'TEXTAREA';
            const k = e.key;
            if (typing) return;
            const upper = k.toUpperCase();
            const letterIndex = upper >= 'A' && upper <= 'D' ? upper.charCodeAt(0) - 65 : -1;
            const numberIndex = k >= '1' && k <= '4' ? parseInt(k, 10) - 1 : -1;
            const optionIndex = letterIndex >= 0 ? letterIndex : numberIndex;
            if (optionIndex >= 0) {
                if (this.phase === 'quiz' && !this.quizAnswered) this.answerQuiz(optionIndex);
            } else if (k === ' ' || k === 'Enter') {
                e.preventDefault();
                if (this.phase === 'card') this.nextAfterCard();
                else if (this.phase === 'spelling' && this.spellingResult === true) this.nextWord();
            }
        },

        splitMeanings(value) {
            const items = String(value || '')
                .replace(/\\n/g, '\n')
                .split(/[；;\n]+/)
                .map(item => item.trim())
                .filter(Boolean);
            return items.reduce((result, item) => {
                if (/^[\u3400-\u9fff]$/.test(item) && result.length) {
                    result[result.length - 1] += `；${item}`;
                } else {
                    result.push(item);
                }
                return result;
            }, []);
        },
        shuffle(arr) { const a=[...arr]; for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];} return a; },
    };
}

function reviewApp() {
    return {
        mode: 'flashcard',
        words: [],
        idx: 0,
        loaded: false,
        flipped: false,
        ratingLocked: false,
        wordMode: {},      // {wordId: {flashcard:0, choice:0, listening:0, spelling:0}}
        wordFlags: {},     // {wordId: {vague:bool, forget:bool}} — 本轮内标记过即触发当日即时复现
        sessionLog: [],    // 本批次完成词 [{word_id, word, meanings, forgot}]
        batchVisible: false,
        doneCount: 0,
        totalCount: 0,
        preview: {},       // review-preview 结果（四档预期间隔）
        wordSentences: {}, // word_id → sentences[] 缓存，选择语境/看义打词共用
        // 例句（英文先显，中文在用户下一步操作后显示）
        flashSentence: '',     // 闪卡例句英文（挖空）
        flashSentenceZh: '',   // 闪卡例句中文
        choiceSentence: '',
        choiceSentenceZh: '',
        listenSentence: '',
        listenSentenceZh: '',
        // 选择模式
        choiceMade: false,
        choiceSelected: -1,
        correctIdx: 0,
        currentOptions: [],
        // 听力模式
        audioPlayed: false,
        listenMade: false,
        listenSelected: -1,
        listenAnswer: 0,
        listenOptions: [],
        // 看义打词
        spellPrompt: '',
        spellZh: '',
        spellingInput: '',
        spellingResult: null,
        spellingAnswer: '',
        isFavorite: false,   // 当前复习词是否已收藏
        _keyBound: null,

        get current() { return this.words[this.idx] || {}; },
        get currentId() { return this.current.word_id; },
        get currentMeanings() {
            try { return JSON.parse(this.current.meanings || '[]').join('；'); }
            catch { return this.current.meanings || ''; }
        },
        get currentStars() { return '★'.repeat(this.current.frequency || 1); },
        get modeState() { return this.wordMode[this.currentId] || {flashcard:0,choice:0,listening:0,spelling:0}; },
        get wordDone() {
            const s = this.modeState;
            return (s.flashcard>=3?1:0) + (s.choice>=3?1:0) + (s.listening>=3?1:0) + (s.spelling>=3?1:0) >= 2;
        },
        get completedModes() {
            const state = this.modeState;
            return ['flashcard','choice','listening','spelling'].filter(key => state[key] >= 3).length;
        },
        get recommendedModeLabel() {
            const names = {flashcard:'闪卡', choice:'选择', listening:'听力', spelling:'打词'};
            const key = ['flashcard','choice','listening','spelling'].sort((a,b)=>(this.modeState[a]||0)-(this.modeState[b]||0))[0];
            return names[key];
        },
        get ringPct() { return this.totalCount ? Math.round(this.doneCount / this.totalCount * 100) : 0; },
        get ringStyle() {
            const c = 2 * Math.PI * 27;
            const off = c * (1 - (this.totalCount ? this.doneCount / this.totalCount : 0));
            return 'stroke-dashoffset:' + off.toFixed(1);
        },
        get forgotCount() { return this.sessionLog.filter(r => r.forgot).length; },

        async init() {
            if (!this._keyBound) {
                this._keyBound = this.onKeydown.bind(this);
                window.addEventListener('keydown', this._keyBound);
            }
            this.doneCount = 0;
            this.batchVisible = false;
            this.sessionLog = [];
            this.wordFlags = {};
            this.loaded = false;
            try {
                const data = await api('/api/study/review-words?limit=30');
                this.words = data.words || [];
                this.totalCount = this.words.length;
                this.idx = 0;
                // 初始化每词的四模式状态与标记
                this.words.forEach(w => {
                    this.wordMode[w.word_id] = {flashcard:0, choice:0, listening:0, spelling:0};
                    this.wordFlags[w.word_id] = {vague:false, forget:false};
                });
                this.loaded = true;
                if (this.words.length > 0) this.prepWord();
            } catch (e) { this.loaded = true; showToast(e.message || '复习队列加载失败，请刷新重试。', 'error'); }
        },

        async prepWord() {
            this.flipped = false;
            this.ratingLocked = false;
            this.choiceMade = false;
            this.choiceSelected = -1;
            this.audioPlayed = false;
            this.listenMade = false;
            this.listenSelected = -1;
            this.spellingInput = '';
            this.spellingResult = null;
            this.spellingAnswer = '';
            this.spellPrompt = '';
            this.spellZh = '';
            this.preview = {};
            if (!this.currentId) return;
            const wid = this.currentId;
            this.prepSentences();
            this.prepChoiceOptions();
            this.prepListenOptions();
            // 预期间隔（纯计算）
            try {
                const p = await api('/api/study/review-preview?word_id=' + wid);
                if (wid !== this.currentId) return;  // 已切到下一词，丢弃过期预览
                this.preview = p || {};
            } catch (e) {}
        },

        // ===== 闪卡（四档） =====
        flipFlashcard() { if (!this.ratingLocked) this.flipped = !this.flipped; },
        answerFlashcard(feedback) {
            if (!this.flipped || this.ratingLocked) return;
            this.ratingLocked = true;
            playSound(feedback === 'forget' ? 'wrong' : 'correct');
            this.recordResult('flashcard', feedback);
            setTimeout(() => this.advanceWord(), 260);
        },

        // ===== 例句：统一加载（英文挖空 + 中文），各模式共用 =====
        async prepSentences() {
            const wid = this.currentId;
            let sentences = this.wordSentences[wid];
            let clean = null;  // 后端干净例句（完整句优先 + 挖空词形变化）
            if (!sentences) {
                try {
                    const detail = await api('/api/words/word/' + wid);
                    if (wid !== this.currentId) return;
                    sentences = detail.sentences || [];
                    this.wordSentences[wid] = sentences;
                    clean = detail.spelling_example || null;
                    this.isFavorite = !!detail.is_favorite;
                } catch(e) { sentences = []; }
            }
            let en, zh;
            if (clean && clean.en) {
                en = clean.en;
                zh = clean.zh || '';
            } else if (sentences.length > 0) {
                en = sentences[0].content.replace(new RegExp(this.current.word, 'gi'), '____');
                zh = sentences[0].translation || '';
            } else {
                en = '请选出 "' + this.current.word + '" 的正确含义';
                zh = '';
            }
            this.flashSentence = en;
            this.flashSentenceZh = zh;
            this.choiceSentence = en;
            this.choiceSentenceZh = zh;
            this.listenSentence = en;
            this.listenSentenceZh = zh;
            this.spellPrompt = en;
            this.spellZh = zh;
        },

        // ===== 选择 =====
        prepChoiceOptions() {
            const meanings = (() => { try { return JSON.parse(this.current.meanings||'[]'); } catch { return [this.current.meanings]; } })();
            const correct = meanings.join('；');
            this.currentOptions = [correct];
            this.words.forEach((w, i) => {
                if (i !== this.idx && this.currentOptions.length < 4) {
                    try { this.currentOptions.push(JSON.parse(w.meanings||'[]').join('；')); }
                    catch { this.currentOptions.push(w.meanings); }
                }
            });
            this.currentOptions = this.shuffle(this.currentOptions);
            this.correctIdx = this.currentOptions.indexOf(correct);
            if (this.correctIdx < 0) this.correctIdx = 0;
        },
        answerChoice(idx) {
            if (this.choiceMade) return;
            this.choiceMade = true;
            this.choiceSelected = idx;
            const correct = idx === this.correctIdx;
            playSound(correct ? 'correct' : 'wrong');
            this.recordResult('choice', correct);
        },

        // ===== 听力 =====
        prepListenOptions() {
            const correct = this.current.word;
            this.listenOptions = [correct];
            this.words.forEach((w, i) => {
                if (i !== this.idx && this.listenOptions.length < 4) this.listenOptions.push(w.word);
            });
            this.listenOptions = this.shuffle(this.listenOptions);
            this.listenAnswer = this.listenOptions.indexOf(correct);
            if (this.listenAnswer < 0) this.listenAnswer = 0;
        },
        playAudio() {
            if (!window.speechSynthesis) { showToast('浏览器不支持语音合成', 'error'); return; }
            window.speechSynthesis.cancel();
            const utter = new SpeechSynthesisUtterance(this.current.word);
            utter.lang = 'en-US'; utter.rate = 0.85;
            window.speechSynthesis.speak(utter);
            this.audioPlayed = true;
        },
        answerListening(idx) {
            if (this.listenMade) return;
            this.listenMade = true;
            this.listenSelected = idx;
            const correct = idx === this.listenAnswer;
            playSound(correct ? 'correct' : 'wrong');
            this.recordResult('listening', correct);
        },

        // ===== 看义打词（例句由 prepSentences 统一加载） =====
        async checkSpelling() {
            const input = this.spellingInput.trim().toLowerCase();
            if (!input) return;
            const el = document.getElementById('spell-input');
            if (el) el.blur();  // 失焦，让全局键盘（空格/回车）接管「继续」
            try {
                const resp = await api('/api/study/spelling-check', {method:'POST', body:JSON.stringify({word_id: this.currentId, spelling: input, mode:'review'})});
                this.spellingResult = !!resp.correct;
                playSound(resp.correct ? 'correct' : 'wrong');
                if (!resp.correct) this.spellingAnswer = resp.word;
                this.recordResult('spelling', !!resp.correct);
            } catch(e) { showToast('验证失败', 'error'); }
        },

        // ===== 通用逻辑 =====
        recordResult(mode, feedback) {
            const wid = this.currentId;
            const s = this.wordMode[wid];
            if (!s) return;
            const isString = typeof feedback === 'string';
            const isMastered = feedback === 'mastered';
            const isVague = feedback === 'vague';
            const isForget = isString ? feedback === 'forget' : !feedback;
            const isCorrect = isString ? feedback !== 'forget' : feedback;

            if (isMastered) {
                // 熟记 → 四模式全满，直接毕业
                s.flashcard = 3; s.choice = 3; s.listening = 3; s.spelling = 3;
            } else if (isVague) {
                // 模糊 → 软过关，标当日复现
                s[mode]++;
                if (this.wordFlags[wid]) this.wordFlags[wid].vague = true;
            } else if (isForget) {
                // 忘记 → 清零，错词必复现
                s[mode] = 0;
                if (this.wordFlags[wid]) this.wordFlags[wid].forget = true;
            } else {
                s[mode]++;
            }

            // 完成判定：任意 2 模式各连对 3 次
            const passed = (s.flashcard>=3?1:0) + (s.choice>=3?1:0) + (s.listening>=3?1:0) + (s.spelling>=3?1:0) >= 2;
            if (passed && !s._done) {
                s._done = true;
                this.doneCount++;
                if (!this.sessionLog.some(r => r.word_id === wid)) {
                    this.sessionLog.push({
                        word_id: wid,
                        word: this.current.word,
                        meanings: this.currentMeanings,
                        forgot: !!(this.wordFlags[wid] && this.wordFlags[wid].forget),
                    });
                }
                showToast(this.current.word + ' 复习完成!', 'success');
                if (!isMastered) {
                    // 熟记已由 /answer 直接毕业，无需再推进
                    api('/api/study/review-word-complete', {method:'POST',
                        body:JSON.stringify({word_id: wid})
                    }).catch(()=>{});
                }
            }

            // 后端记录（闪卡四档 / 其余对错）
            const body = isString
                ? {word_id: wid, mode:'review', feedback}
                : {word_id: wid, mode:'review', correct: isCorrect};
            api('/api/study/answer', {method:'POST', body:JSON.stringify(body)}).catch(()=>{});
        },

        async toggleFavorite() {
            const wid = this.currentId;
            if (!wid) return;
            try {
                const resp = await api('/api/words/favorite', {method:'PUT', body:JSON.stringify({word_id: wid})});
                this.isFavorite = !!resp.is_favorite;
                showToast(this.isFavorite ? '已加入收藏词库' : '已取消收藏', this.isFavorite ? 'success' : 'info');
            } catch(e) { showToast('操作失败', 'error'); }
        },

        advanceWord() {
            if (this.words.length === 0) return;
            if (this.wordDone) {
                // 完成 → 出队
                this.words = this.words.filter(w => w.word_id !== this.currentId);
                delete this.wordFlags[this.currentId];
                if (this.words.length === 0) { this.batchVisible = true; return; }
                this.idx = Math.min(this.idx, this.words.length - 1);
            } else {
                const flags = this.wordFlags[this.currentId] || {};
                const len = this.words.length;
                if (flags.forget) {
                    // 忘记 → 今日即时复现：插到队列后 1/3 处（至少隔 7 个词，避免短期记忆假象）
                    const w = this.words.splice(this.idx, 1)[0];
                    const pos = Math.min(this.idx + Math.max(7, Math.round(len * 0.35)), this.words.length);
                    this.words.splice(pos, 0, w);
                    delete this.wordFlags[this.currentId];
                } else if (flags.vague) {
                    // 模糊 → 软过关后当日复现：插到队列后半（至少隔 10 个词）
                    const w = this.words.splice(this.idx, 1)[0];
                    const pos = Math.min(this.idx + Math.max(10, Math.round(len * 0.5)), this.words.length);
                    this.words.splice(pos, 0, w);
                    delete this.wordFlags[this.currentId];
                } else {
                    this.idx = (this.idx + 1) % this.words.length;
                }
            }
            this.prepWord();
        },

        jumpTo(w) {
            const i = this.words.indexOf(w);
            if (i >= 0) { this.idx = i; this.prepWord(); }
        },

        // ===== 键盘 =====
        onKeydown(e) {
            const tag = document.activeElement && document.activeElement.tagName;
            const typing = tag === 'INPUT' || tag === 'TEXTAREA';
            const k = e.key;

            const upper = k.toUpperCase();
            const optionIndex = upper >= 'A' && upper <= 'D' ? upper.charCodeAt(0) - 65 : (k >= '1' && k <= '4' ? parseInt(k, 10) - 1 : -1);
            if (optionIndex >= 0) {
                if (typing) return;
                const n = optionIndex + 1;
                if (this.mode === 'flashcard' && k >= '1' && k <= '4' && this.flipped && !this.ratingLocked) {
                    this.answerFlashcard(['recognize','vague','forget','mastered'][n-1]);
                } else if (this.mode === 'choice' && !this.choiceMade) {
                    this.answerChoice(n-1);
                } else if (this.mode === 'listening' && this.audioPlayed && !this.listenMade) {
                    this.answerListening(n-1);
                }
            } else if (k === ' ' || k === 'Enter') {
                if (typing) return;
                e.preventDefault();
                if (this.mode === 'flashcard' && !this.flipped) {
                    this.flipFlashcard();
                } else if (this.mode === 'choice' && this.choiceMade) {
                    this.advanceWord();
                } else if (this.mode === 'listening' && this.listenMade) {
                    this.advanceWord();
                } else if (this.mode === 'spelling' && this.spellingResult !== null) {
                    this.advanceWord();
                }
            }
        },

        shuffle(arr) {
            const a = [...arr];
            for (let i = a.length-1; i>0; i--) { const j = Math.floor(Math.random()*(i+1)); [a[i], a[j]] = [a[j], a[i]]; }
            return a;
        },
        splitMeanings(value) {
            return String(value || '').replace(/\\n/g, '\n').split(/[；;\n]+/).map(item => item.trim()).filter(Boolean);
        },
    };
}

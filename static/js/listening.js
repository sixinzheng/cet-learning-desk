(function () {
    const root = document.getElementById('listening-app');
    if (!root) return;

    const $ = id => document.getElementById(id);
    const state = {
        layer: 'word', items: [], index: 0, correct: 0, answered: false,
        answers: [], startedAt: 0, itemStartedAt: 0, sessionKey: ''
    };
    const layerMeta = {
        word: {label: '第一层 · 单词听辨', prompt: '只听声音，选出你听到的单词', limit: 10},
        sentence: {label: '第二层 · 句子理解', prompt: '听完整句子，选出最符合句意的中文解释', limit: 8},
        dialogue: {label: '第三层 · 短对话理解', prompt: '听短对话和问题，选择最合适的答案', limit: 6}
    };

    function newSessionKey() {
        return `${state.layer}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    }
    function meanings(word) {
        const value = parseJSON(word.meanings);
        return Array.isArray(value)
            ? value.map(item => typeof item === 'string' ? item : item.meaning || item.zh || '').filter(Boolean).join('；')
            : String(value || word.meaning || '暂无释义');
    }
    function setStatus(message, type) {
        const el = root.querySelector('[data-region-status]');
        el.hidden = false;
        el.className = `region-state region-state--${type || 'loading'}`;
        el.textContent = message;
    }
    function hideStatus() { root.querySelector('[data-region-status]').hidden = true; }
    function setEmpty(title, copy, action) {
        $('listen-card').hidden = true;
        $('listen-empty').hidden = false;
        $('listen-empty').innerHTML = `<h2>${title}</h2><p>${copy}</p>${action || ''}`;
    }
    function shuffled(items) { return [...items].sort(() => Math.random() - .5); }
    function speak(text) {
        if (!text) return;
        const item = state.items[state.index] || {};
        speakEnglish(text.replace(/^[A-Z]:\s*/gm, ''), {
            wordId: state.layer === 'word' ? item.id : null,
            audioUrl: item.audio_url,
            rate: state.layer === 'word' ? .78 : .9,
            onStart: () => { $('listen-playback-state').textContent = '正在播放'; },
            onEnd: () => { $('listen-playback-state').textContent = '播放结束，可以作答或重新播放'; },
            onError: () => { $('listen-playback-state').textContent = '播放失败，请重新播放'; },
        });
    }
    function currentAudioText() {
        const item = state.items[state.index] || {};
        if (state.layer === 'word') return item.word;
        if (state.layer === 'sentence') return item.script || item.sentence;
        return [item.script, item.question].filter(Boolean).join('. ');
    }
    function optionButton(label, value, index) {
        const letter = String.fromCharCode(65 + index);
        return `<button class="choice-button" type="button" data-value="${String(value)}" data-key="${letter}" aria-label="${letter}，${label}"><span class="choice-button__letter" aria-hidden="true">${letter}</span><span class="choice-button__copy">${label}</span></button>`;
    }
    function bindOptions() {
        $('listen-options').querySelectorAll('button').forEach(button => {
            button.addEventListener('click', () => answer(button.dataset.value));
        });
    }
    function renderOptions(item) {
        if (state.layer === 'word') {
            const alternatives = shuffled(state.items.filter(entry => entry.id !== item.id)).slice(0, 3);
            $('listen-options').innerHTML = shuffled([item, ...alternatives]).map((entry, index) => optionButton(entry.word, entry.id, index)).join('');
        } else if (state.layer === 'sentence') {
            const alternatives = shuffled(state.items.filter(entry => entry.word_id !== item.word_id)).slice(0, 3);
            $('listen-options').innerHTML = shuffled([item, ...alternatives]).map((entry, index) => optionButton(entry.meaning || meanings(entry), entry.word_id, index)).join('');
        } else if (state.layer === 'dialogue') {
            $('listen-options').innerHTML = (item.options || []).map((label, index) => optionButton(label, String.fromCharCode(65 + index), index)).join('');
        }
        bindOptions();
    }
    function render() {
        const item = state.items[state.index];
        if (!item) return finishListening();
        state.answered = false;
        state.itemStartedAt = Date.now();
        $('listen-index').textContent = state.index + 1;
        $('listen-total').textContent = state.items.length;
        $('listen-answer').hidden = true;
        $('listen-playback-state').textContent = '即将自动播放';
        document.querySelector('.listening-action-bar')?.classList.remove('is-ready');
        $('listen-next').disabled = true;
        $('listen-next').textContent = state.index === state.items.length - 1 ? '完成本轮' : '下一题';
        $('listen-layer-label').textContent = layerMeta[state.layer].label;
        $('listen-prompt').textContent = state.layer === 'dialogue' ? (item.prompt || item.question || layerMeta[state.layer].prompt) : layerMeta[state.layer].prompt;
        $('listen-difficulty').textContent = `难度 ${item.difficulty || 1}`;
        renderOptions(item);
        setTimeout(() => speak(currentAudioText()), 220);
    }
    function correctValue(item) {
        if (state.layer === 'word') return String(item.id);
        if (state.layer === 'sentence') return String(item.word_id);
        return null;
    }
    function answer(value) {
        if (state.answered) return;
        state.answered = true;
        const item = state.items[state.index];
        const knownCorrect = correctValue(item);
        const isCorrect = knownCorrect === null ? null : value === knownCorrect;
        if (isCorrect) state.correct += 1;
        $('listen-correct').textContent = state.correct;
        $('listen-options').querySelectorAll('button').forEach(button => {
            button.disabled = true;
            if (knownCorrect !== null) {
                button.classList.toggle('is-correct', button.dataset.value === knownCorrect);
                button.classList.toggle('is-wrong', button.dataset.value === value && !isCorrect);
            } else if (button.dataset.value === value) button.classList.add('is-selected');
        });
        const responseMs = Date.now() - state.itemStartedAt;
        if (state.layer === 'dialogue') state.answers.push({scenario_id: item.id, answer: value, response_ms: responseMs});
        else state.answers.push({word_id: item.word_id || item.id, selected_word_id: Number(value), difficulty: item.difficulty || 1, response_ms: responseMs});
        $('listen-word').textContent = isCorrect === null ? '本轮结束后由服务端统一核对' : (isCorrect ? '判断正确' : '答案已订正');
        $('listen-phonetic').textContent = item.phonetic || '';
        $('listen-meaning').textContent = state.layer === 'word' ? meanings(item) : (item.meaning || '请继续完成本轮训练。');
        $('listen-answer').hidden = false;
        $('listen-next').disabled = false;
        document.querySelector('.listening-action-bar')?.classList.add('is-ready');
        if (isCorrect !== null) playSound(isCorrect ? 'correct' : 'wrong');
    }
    async function finishListening() {
        $('listen-next').disabled = true;
        setStatus('正在由服务端核对整轮答案……');
        try {
            const result = await api('/api/practice/listening/complete', {
                method: 'POST',
                body: JSON.stringify({
                    layer: state.layer, answers: state.answers,
                    duration_seconds: Math.max(1, Math.round((Date.now() - state.startedAt) / 1000)),
                    idempotency_key: state.sessionKey
                })
            });
            hideStatus();
            $('listen-evidence').textContent = result.duplicate ? '已结算' : '新增证据';
            setEmpty('本轮听力已结算', `服务端核对 ${result.total_count || 0} 题，答对 ${result.correct_count || 0} 题，表现分 ${Math.round(result.raw_score || 0)}。这条记录会按难度、样本量和近期性进入段位评价。`, '<a class="btn btn-primary" href="/growth#score-ledger">查看段位计分账单</a>');
        } catch (error) {
            setStatus(`本轮暂未保存：${error.message || '请检查连接后重试。'}`, 'error');
            $('listen-next').disabled = false;
            $('listen-next').textContent = '重新提交本轮';
            document.querySelector('.listening-action-bar')?.classList.add('is-ready');
        }
    }
    async function loadLayer(layer) {

        state.layer = layer;
        state.index = 0; state.correct = 0; state.answers = [];
        state.startedAt = Date.now(); state.sessionKey = newSessionKey();
        $('listen-index').textContent = '0'; $('listen-total').textContent = '0';
        $('listen-correct').textContent = '0'; $('listen-evidence').textContent = '尚未结算';
        $('listen-empty').hidden = true; $('listen-card').hidden = true;
        root.querySelectorAll('[data-layer]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.layer === layer)));
        setStatus('正在准备训练内容……');
        try {
            const data = await api(`/api/practice/listening/content?layer=${encodeURIComponent(layer)}`);
            state.items = (data.items || []).slice(0, layerMeta[layer].limit);
            $('listen-selection-basis').textContent = data.selection_basis || '本轮内容已固定，答题过程中不会更换。';
            hideStatus();
            if (!state.items.length) {
                setEmpty('暂时没有可用内容', layer === 'word' ? '请先在词库中学习几个单词，再回来做听辨训练。' : '这一层训练内容暂未准备好。', '<a class="btn btn-primary" href="/learn">返回学习中心</a>');
                return;
            }
            $('listen-card').hidden = false;
            render();
        } catch (error) {
            setStatus(`训练内容加载失败：${error.message || '请刷新页面重试。'}`, 'error');
        }
    }

    root.querySelectorAll('[data-layer]').forEach(button => button.addEventListener('click', () => loadLayer(button.dataset.layer)));
    $('listen-play').addEventListener('click', () => speak(currentAudioText()));

    $('listen-next').addEventListener('click', () => {
        if (!state.answered) return;
        state.index += 1;
        render();
    });
    document.addEventListener('keydown', event => {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        if (/^[a-d1-4]$/i.test(event.key) && !state.answered) {
            const index = /^[1-4]$/.test(event.key) ? Number(event.key) - 1 : event.key.toUpperCase().charCodeAt(0) - 65;
            const button = $('listen-options').querySelectorAll('button')[index];
            if (button && !button.disabled) { event.preventDefault(); button.click(); }
        } else if (event.key === 'Enter' && state.answered && !$('listen-next').disabled) {
            event.preventDefault(); $('listen-next').click();
        }
    });
    loadLayer('word');
})();

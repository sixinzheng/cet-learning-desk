(function () {
    const root = document.getElementById('diagnostic-app');
    if (!root) return;
    const $ = id => document.getElementById(id);
    const state = {step: 0, content: {}, answers: {}, sessionIds: [], key: 'diagnostic-' + Date.now(), startedAt: 0};
    const steps = ['阅读语境', '听力理解'];

    function status(message, type) {
        const node = root.querySelector('[data-diagnostic-status]');
        node.hidden = false; node.className = 'region-state region-state--' + (type || 'loading'); node.textContent = message;
    }
    function optionList(name, questionId, options) {
        return '<div class="diagnostic-question" data-question="' + questionId + '">' + options.map((option, index) => {
            const value = String.fromCharCode(65 + index);
            return '<label><input type="radio" name="' + name + '-' + questionId + '" value="' + value + '"><span><b>' + value + '</b>' + option + '</span></label>';
        }).join('') + '</div>';
    }
    function collect(container) {
        const result = {};
        container.querySelectorAll('[data-question]').forEach(group => {
            const checked = group.querySelector('input:checked');
            if (checked) result[group.dataset.question] = checked.value;
        });
        return result;
    }
    async function loadContent() {
        const [articleList, dialogues] = await Promise.all([
            api('/api/reading/articles?difficulty=3'), api('/api/practice/listening/content?layer=dialogue')
        ]);
        const article = (articleList.articles || [])[0];
        if (!article) throw new Error('当前题库还没有可用于诊断的阅读文章');
        state.content.reading = await api('/api/reading/articles/' + article.id);
        state.content.dialogue = (dialogues.items || []).slice(0, 3);
        if (!state.content.dialogue.length) throw new Error('诊断题库暂不完整');
    }
    function renderReading() {
        const item = state.content.reading;
        $('diagnostic-task').innerHTML = '<p class="eyebrow">READ IN CONTEXT</p><h2>' + item.title + '</h2><div class="diagnostic-reading">' + item.content + '</div>' + (item.questions || []).map(q => '<section><h3>' + q.question + '</h3>' + optionList('reading', q.id, q.options || []) + '</section>').join('');
    }
    function renderDialogue() {
        $('diagnostic-task').innerHTML = '<p class="eyebrow">LISTENING</p><h2>听三段对话，选择最合适的答案</h2>' + state.content.dialogue.map((item, i) => '<section class="diagnostic-dialogue"><button type="button" class="text-link" data-play="' + i + '">播放第 ' + (i + 1) + ' 段</button><h3>' + item.question + '</h3>' + optionList('dialogue', item.id, item.options || []) + '</section>').join('');
        $('diagnostic-task').querySelectorAll('[data-play]').forEach(button => button.addEventListener('click', () => speakDialogue(state.content.dialogue[Number(button.dataset.play)])));
    }
    function renderStep() {
        $('diagnostic-task').hidden = false;
        root.querySelector('[data-diagnostic-status]').hidden = true;
        $('diagnostic-step-label').textContent = steps[state.step];
        $('diagnostic-step-count').textContent = (state.step + 1) + '/2';
        $('diagnostic-progress-bar').style.width = ((state.step + 1) * 50) + '%';
        [renderReading, renderDialogue][state.step]();
    }
    async function submitStep() {
        $('diagnostic-submit').disabled = true;
        try {
            let result;
            const duration = Math.max(1, Math.round((Date.now() - state.startedAt) / 1000));
            if (state.step === 0) {
                const answers = collect($('diagnostic-task'));
                if (Object.keys(answers).length < state.content.reading.questions.length) throw new Error('请完成本页全部阅读题');
                result = await api('/api/practice/reading/complete', {method: 'POST', body: JSON.stringify({article_id: state.content.reading.id, answers, duration_seconds: duration, origin: 'diagnostic', idempotency_key: state.key + '-reading'})});
            } else if (state.step === 1) {
                const map = collect($('diagnostic-task'));
                if (Object.keys(map).length < state.content.dialogue.length) throw new Error('请完成全部听力题');
                const answers = Object.entries(map).map(([scenario_id, answer]) => ({scenario_id: Number(scenario_id), answer: answer}));
                result = await api('/api/practice/listening/complete', {method: 'POST', body: JSON.stringify({layer: 'dialogue', answers, duration_seconds: duration, origin: 'diagnostic', idempotency_key: state.key + '-listening'})});
            }
            if (result && result.session_id) state.sessionIds.push(result.session_id);
            state.step += 1;
            if (state.step >= steps.length) return finish();
            renderStep();
        } catch (error) {
            showToast(error.message || '提交失败，请重试。', 'error');
        } finally { $('diagnostic-submit').disabled = false; }
    }
    function speakDialogue(item) {
        if (!('speechSynthesis' in window)) return showToast('当前浏览器不支持语音朗读。', 'warning');
        speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(item.script + '. ' + item.question); utterance.lang = 'en-US'; utterance.rate = .9;
        utterance.onstart = () => showToast('正在播放第 ' + (state.content.dialogue.indexOf(item) + 1) + ' 段对话。', 'info');
        utterance.onerror = () => showToast('播放失败，请重新播放。', 'error');
        speechSynthesis.speak(utterance);
    }
    async function finish() {
        $('diagnostic-workspace').hidden = true;
        $('diagnostic-result').hidden = false;
        $('diagnostic-result').innerHTML = '<div class="region-state region-state--loading">正在生成初始能力画像……</div>';
        try {
            await api('/api/practice/diagnostic/complete', {method: 'POST', body: JSON.stringify({session_ids: state.sessionIds})});
            const detail = await api('/api/level/detail');
            $('diagnostic-result').innerHTML = '<p class="eyebrow">DIAGNOSTIC COMPLETE</p><h2>初始证据已写入段位账单</h2><p class="diagnostic-can-do">' + (detail.assessment && detail.assessment.sentence ? detail.assessment.sentence : '你已经建立了第一组可以复核的能力证据。') + '</p><div class="diagnostic-result-score"><span>当前综合分</span><strong>' + (detail.level.total_score || 0) + '</strong><span>可信度 ' + (detail.level.confidence || 0) + '%</span></div><div class="action-row"><a class="btn btn-primary" href="/growth#score-ledger">查看完整计分账单</a><a class="btn btn-secondary" href="/learn">开始日常学习</a></div>';
        } catch (error) { $('diagnostic-result').innerHTML = '<div class="region-state region-state--error"><strong>结果生成失败</strong><span>' + (error.message || '请稍后重试。') + '</span><button id="diagnostic-finish-retry" class="btn btn-secondary" type="button">重新生成结果</button><a class="text-link" href="/learn">进入日常学习</a></div>'; $('diagnostic-finish-retry').addEventListener('click', finish); }
    }
    async function start() {
        $('diagnostic-intro').hidden = true; $('diagnostic-workspace').hidden = false; state.startedAt = Date.now(); status('正在抽取诊断内容……');
        try { await loadContent(); renderStep(); } catch (error) { status((error.message || '') + '。你仍可直接进入日常学习。', 'error'); const node=root.querySelector('[data-diagnostic-status]'); const retry=document.createElement('button'); retry.type='button'; retry.className='btn btn-secondary'; retry.textContent='重新加载诊断'; retry.addEventListener('click',start); node.appendChild(retry); }
    }
    $('diagnostic-start').addEventListener('click', start);
    $('diagnostic-submit').addEventListener('click', submitStep);
})();

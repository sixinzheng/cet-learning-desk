(function () {
    const root = document.getElementById('cloze-app');
    if (!root) return;
    const $ = id => document.getElementById(id);
    let items = [];
    let currentBlank = null;
    let startedAt = 0;

    function updateProgress() {
        const inputs = Array.from($('cloze-content').querySelectorAll('.cloze-input'));
        const filled = inputs.filter(input => input.value.trim()).length;
        $('cloze-progress').textContent = `已填 ${filled}/${inputs.length}`;
        $('cloze-submit').disabled = !inputs.length || filled !== inputs.length;
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    function shuffle(list) {
        for (let i = list.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [list[i], list[j]] = [list[j], list[i]];
        }
        return list;
    }

    function render(item) {
        $('cloze-title').textContent = item.title;
        $('cloze-difficulty').textContent = '难度 ' + item.difficulty;
        $('cloze-result').hidden = true;
        $('cloze-result').textContent = '';
        const parts = String(item.content || '').split(/(\{\{\d+\}\})/);
        let marked = '';
        parts.forEach(part => {
            const match = part.match(/^\{\{(\d+)\}\}$/);
            if (match) {
                const order = Number(match[1]);
                marked += '<span class="cloze-gap">'
                    + '<input class="cloze-input" data-blank="' + order + '" autocomplete="off" readonly inputmode="none" placeholder="' + order + '" aria-label="第' + order + '空，从候选词中选择">'
                    + '</span>';
            } else {
                marked += escapeHtml(part);
            }
        });
        $('cloze-content').innerHTML = marked;
        $('cloze-content').querySelectorAll('.cloze-input').forEach(input => {
            input.addEventListener('focus', () => {
                currentBlank = Number(input.dataset.blank);
                $('cloze-content').querySelectorAll('.cloze-gap').forEach(gap => gap.classList.toggle('is-current', gap.contains(input)));
                $('cloze-current-hint').textContent = `当前第 ${currentBlank} 空：请从候选词中选择。`;
            });
            input.addEventListener('input', () => { updateProgress(); updateBankUsage(); });
            input.addEventListener('keydown', event => {
                if (event.key === 'Enter' && event.target.tagName === 'INPUT') { event.preventDefault(); submit(); }
            });
        });
        const bank = shuffle([...(item.candidates || [])]);
        $('cloze-bank').innerHTML = bank.map(word => '<button type="button" class="bank-chip" data-word="' + escapeHtml(word) + '" aria-pressed="false">' + escapeHtml(word) + '</button>').join('');
        $('cloze-bank').querySelectorAll('.bank-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                if (currentBlank == null) { showToast('先在文章的空格处点击，再选词。'); return; }
                const input = $('cloze-content').querySelector('.cloze-input[data-blank="' + currentBlank + '"]');
                if (input) { input.value = chip.dataset.word; input.focus(); }
                updateProgress(); updateBankUsage();
            });
        });
        updateProgress();
        startedAt = Date.now();
    }

    function updateBankUsage() {
        const values = Array.from($('cloze-content').querySelectorAll('.cloze-input')).map(input => input.value.trim().toLowerCase()).filter(Boolean);
        $('cloze-bank').querySelectorAll('.bank-chip').forEach(chip => {
            const used = values.includes(String(chip.dataset.word || '').toLowerCase());
            chip.classList.toggle('is-used', used); chip.setAttribute('aria-pressed', String(used));
        });
    }

    async function load() {
        setRegionState(root, 'loading', '正在准备选词填空…');
        try {
            const data = await api('/api/practice/cloze/content');
            items = data.items || [];
            setRegionState(root, 'ready');
            if (!items.length) {
                $('cloze-content').innerHTML = '<p class="muted">暂无选词填空文章，请检查本地题库。</p>';
                return;
            }
            render(items[0]);
        } catch (error) {
            setRegionState(root, 'error', (error && error.message) || '选词填空加载失败，请刷新重试。');
        }
    }

    async function submit() {
        const inputs = Array.from($('cloze-content').querySelectorAll('.cloze-input'));
        if (!inputs.length) { showToast('请先加载一篇文章。'); return; }
        const answers = inputs.map(input => ({ blank_order: Number(input.dataset.blank), answer: input.value.trim() }));
        if (answers.some(answer => !answer.answer)) { showToast('请先填写所有的空。', 'error'); return; }
        const item = items[0];
        if (!item) return;
        try {
            const result = await api('/api/practice/cloze/complete', {
                method: 'POST', body: JSON.stringify({
                    passage_id: item.id, answers,
                    duration_seconds: Math.max(1, Math.round((Date.now() - startedAt) / 1000)),
                }),
            });
            const answerMap = {};
            (result.answers || []).forEach(entry => { answerMap[entry.blank_order] = entry.answer; });
            inputs.forEach(input => {
                const order = Number(input.dataset.blank);
                const correct = answerMap[order] || '';
                const ok = input.value.trim().toLowerCase() === correct.toLowerCase();
                input.classList.toggle('is-correct', ok);
                input.classList.toggle('is-wrong', !ok);
                input.disabled = true;
            });
            $('cloze-result').hidden = false;
            $('cloze-result').innerHTML = '<p>答对 <strong>' + result.correct_count + '</strong> / ' + result.total_count
                + '，本轮 <strong>' + result.score + '</strong> 分。</p><div class="cloze-result__details">' + (result.answers || []).map(a => {
                    const source = answers.find(item => item.blank_order === a.blank_order) || {};
                    const ok = String(source.answer || '').toLowerCase() === String(a.answer || '').toLowerCase();
                    const reason = a.base_word && a.base_word !== a.answer
                        ? `由 ${a.base_word} 根据句子结构变为 ${a.answer}。`
                        : '根据上下文语义与句子结构选择该词。';
                    return `<article class="${ok ? 'is-correct' : 'is-wrong'}"><strong>第 ${a.blank_order} 空 · ${ok ? '正确' : '需要订正'}</strong><span>你的答案：${escapeHtml(source.answer || '—')}</span><span>正确答案：${escapeHtml(a.answer || '—')}</span><small>${escapeHtml(reason)}</small></article>`;
                }).join('') + '</div>';
            showToast('批改完成：' + result.correct_count + '/' + result.total_count, 'success');
        } catch (error) { showToast((error && error.message) || '批改失败，请重试。', 'error'); }
    }

    async function generateCloze() {
        const btn = $('cloze-ai-generate');
        if (!btn) return;
        btn.disabled = true; btn.textContent = 'AI 生成中…';
        try {
            const status = await api('/api/ai/config/status');
            const resp = await fetch('/api/ai/generate-cloze', { method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': status.csrf_token}, body: JSON.stringify({}) });
            if (!resp.ok) { const e = await resp.json().catch(() => ({})); throw new Error(e.error || '生成失败'); }
            const r = await resp.json();
            showToast('已生成新文章《' + r.title + '》。', 'success');
            await load();
        } catch (e) { showToast(e.message || 'AI 生成失败，请稍后重试。', 'error'); }
        finally { btn.disabled = false; btn.textContent = 'AI 生成新文章'; }
    }

    $('cloze-submit').addEventListener('click', submit);
    $('cloze-refresh').addEventListener('click', load);
    $('cloze-ai-generate')?.addEventListener('click', generateCloze);
    load();
})();

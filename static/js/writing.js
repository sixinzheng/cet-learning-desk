(function () {
    const root = document.getElementById('writing-app');
    if (!root) return;
    const $ = id => document.getElementById(id);
    let startedAt = Date.now(), dirty = false, submitting = false, recognizing = false;
    const imageTypes = new Set(['image/jpeg', 'image/png', 'image/webp']);

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
    }
    function words(text) { return String(text || '').trim().match(/[A-Za-z]+(?:['’-][A-Za-z]+)*/g)?.length || 0; }
    function updateEditorState() {
        const count = words($('essay-input').value);
        $('writing-count').textContent = `${count} 词`;
        $('writing-save-state').textContent = count ? '尚未提交' : '尚未输入';
        dirty = count > 0;
    }
    function updateStandard() {
        const cet6 = $('writing-level').value === 'cet6';
        $('writing-target').textContent = cet6 ? '150–200 词' : '120–180 词';
        $('writing-level').dataset.touched = 'true';
    }
    function errorState(error) {
        const message = String(error?.message || '');
        let title = '批改服务暂时不可用', copy = message || '请检查本地服务后重试。';
        if (/key|配置|401|unauthorized/i.test(message)) { title = 'DeepSeek 尚未配置或验证失败'; copy = '请到“我的 → AI 服务”验证并保存 API Key，然后返回重试。'; }
        else if (/fetch|network|连接|timeout|超时/i.test(message)) { title = '网络连接失败'; copy = '作文仍保留在编辑区。检查网络后可以直接重新提交。'; }
        $('essay-result').innerHTML = `<div class="region-state region-state--error"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(copy)}</span><button id="writing-retry" class="btn btn-secondary" type="button">重新提交</button></div>`;
        $('writing-retry').addEventListener('click', submitEssay);
    }
    function setOcrState(type, title, copy, warnings) {
        const state = $('writing-ocr-state');
        state.hidden = false;
        state.className = `writing-ocr__state region-state region-state--${type}`;
        const warningList = Array.isArray(warnings) && warnings.length
            ? `<ul>${warnings.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : '';
        state.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(copy || '')}</span>${warningList}`;
    }
    function readAsDataUrl(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error('无法读取这张图片，请重新选择。'));
            reader.readAsDataURL(file);
        });
    }
    async function recognizeEssay(file) {
        if (!file || recognizing) return;
        if (!imageTypes.has(String(file.type || '').toLowerCase())) {
            setOcrState('error', '图片格式不支持', '请选择 JPEG、PNG 或 WebP 图片。');
            return;
        }
        if (file.size > 6 * 1024 * 1024) {
            setOcrState('error', '图片超过 6MB', '请压缩图片或重新拍摄后再上传。');
            return;
        }
        recognizing = true;
        root.querySelectorAll('#essay-camera, #essay-image').forEach(input => { input.disabled = true; });
        setOcrState('loading', '正在识别作文', '请保持页面打开，原图不会保存到本站。');
        try {
            const image = await readAsDataUrl(file);
            const result = await api('/api/writing/ocr', {
                method: 'POST',
                body: JSON.stringify({image, request_id: `ocr-${Date.now()}-${file.size}`})
            });
            $('essay-input').value = result.text || '';
            updateEditorState();
            dirty = true;
            setOcrState('success', '识别完成，请先核对文字', '已把识别结果放入作文编辑框。请检查拼写、段落和 [unclear] 标记，确认后再提交批改。', result.warnings);
            $('essay-input').focus();
            showToast('图片已转成文字，请核对后再提交批改。', 'success');
        } catch (error) {
            setOcrState('error', '图片识别失败', String(error?.message || '请稍后重试。'));
        } finally {
            recognizing = false;
            root.querySelectorAll('#essay-camera, #essay-image').forEach(input => { input.disabled = false; input.value = ''; });
        }
    }
    async function submitEssay() {
        if (submitting) return;
        const text = $('essay-input').value.trim();
        if (!text) { showToast('请先输入作文正文。', 'warning'); $('essay-input').focus(); return; }
        const count = words(text);
        if (count < 40 && !window.confirm(`当前只有 ${count} 词，可能不足以形成可靠批改。仍然提交吗？`)) return;
        submitting = true;
        const button = $('writing-submit'); button.disabled = true; button.textContent = '正在批改…';
        $('essay-result').innerHTML = '<div class="region-state region-state--loading"><strong>AI 正在批改作文</strong><span>正在检查内容、结构、词汇、语法与连贯性，请保持页面打开。</span></div>';
        const examLevel = $('writing-level').value || 'cet4';
        const difficulty = window.__writingDifficulty || (examLevel === 'cet6' ? 5 : 3);
        try {
            const result = await api('/api/writing/correct', {method:'POST', body:JSON.stringify({essay:text, exam_level:examLevel, difficulty, duration_seconds:Math.max(60, Math.round((Date.now() - startedAt) / 1000)), idempotency_key:`writing-${Date.now()}-${text.length}`})});
            renderResult(result); dirty = false; $('writing-save-state').textContent = '已成功批改并计入段位';
            showToast('批改完成，写作成绩已进入段位账单。', 'success');
        } catch (error) { errorState(error); }
        finally { submitting = false; button.disabled = false; button.textContent = '提交批改并计入段位'; }
    }
    function renderResult(data) {
        const metrics = [['内容','content_score'],['结构','structure_score'],['词汇','vocabulary_score'],['语法','grammar_score'],['连贯','coherence_score']];
        const errors = Array.isArray(data.errors) ? data.errors : [];
        const highlights = Array.isArray(data.highlights) ? data.highlights : [];
        $('essay-result').innerHTML = `<article class="writing-report"><header><div><p class="task-kicker">WRITING REPORT / 批改结果</p><h2>本次写作能力分</h2></div><strong class="writing-total-score">${escapeHtml(data.total_score ?? '--')}</strong></header><div class="writing-score-grid">${metrics.map(([label,key]) => `<div><span>${label}</span><strong>${escapeHtml(data[key] ?? '--')}</strong></div>`).join('')}</div>${errors.length ? `<section><h3>错误纠正</h3><div class="writing-feedback-list">${errors.map(item => `<article><strong>${escapeHtml(item.location || '需要修改')}</strong><p>${escapeHtml(item.correction || '')}</p><span>${escapeHtml(item.explanation || '')}</span></article>`).join('')}</div></section>` : ''}${highlights.length ? `<section><h3>表达亮点</h3><ul class="writing-highlight-list">${highlights.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></section>` : ''}${data.overall_comment ? `<blockquote>${escapeHtml(data.overall_comment)}</blockquote>` : ''}</article>`;
    }

    $('essay-input').addEventListener('input', updateEditorState);
    $('writing-level').addEventListener('change', updateStandard);
    $('writing-submit').addEventListener('click', submitEssay);
    ['essay-camera', 'essay-image'].forEach(id => $(id).addEventListener('change', event => recognizeEssay(event.target.files?.[0])));
    window.addEventListener('beforeunload', event => { if (!dirty || submitting) return; event.preventDefault(); event.returnValue = ''; });
    document.addEventListener('DOMContentLoaded', async () => {
        updateEditorState(); updateStandard();
        try {
            const data = await api('/api/study/difficulty-setting');
            if (!data.difficulty) return;
            window.__writingDifficulty = Number(data.difficulty);
            if (!$('writing-level').dataset.touched) $('writing-level').value = window.__writingDifficulty <= 3 ? 'cet4' : 'cet6';
            updateStandard(); delete $('writing-level').dataset.touched;
        } catch (_) { /* 默认标准仍可使用 */ }
    });
})();

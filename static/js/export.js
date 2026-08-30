(function () {
    const queue = [], $ = id => document.getElementById(id);
    function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
    async function loadItems() {
        $('export-items').innerHTML = '<div class="region-state region-state--loading">正在读取题库…</div>';
        try {
            const data = await api('/api/reading/articles');
            const items = data.articles || [];
            if (!items.length) { $('export-items').innerHTML = '<div class="empty-state"><h3>题库暂时为空</h3><p>添加阅读文章后即可生成打印练习。</p></div>'; return; }
            $('export-items').innerHTML = items.map(item => {
                const selected = queue.some(entry => entry.id === item.id);
                return `<article class="export-question-item"><div><h3>${escapeHtml(item.title || '未命名文章')}</h3><p>${escapeHtml(item.source || '来源未记录')} · ${Number(item.word_count) || 0} 词</p></div><button class="btn ${selected ? 'btn-secondary' : 'btn-primary'}" type="button" data-id="${item.id}" data-title="${escapeHtml(item.title || '未命名文章')}" data-source="${escapeHtml(item.source || '来源未记录')}">${selected ? '移除' : '添加'}</button></article>`;
            }).join('');
            $('export-items').querySelectorAll('[data-id]').forEach(button => button.addEventListener('click', () => toggle({type:'reading', id:Number(button.dataset.id), title:button.dataset.title, source:button.dataset.source})));
        } catch (error) {
            $('export-items').innerHTML = `<div class="region-state region-state--error"><strong>题库加载失败</strong><span>${escapeHtml(error.message || '请检查本地服务后重试。')}</span><button id="export-retry" class="btn btn-secondary" type="button">重新加载</button></div>`;
            $('export-retry').addEventListener('click', loadItems);
        }
    }
    function toggle(item) {
        const index = queue.findIndex(entry => entry.type === item.type && entry.id === item.id);
        if (index >= 0) queue.splice(index, 1); else queue.push(item);
        updateQueue(); loadItems();
    }
    function updateQueue() {
        $('export-count').textContent = queue.length;
        $('export-submit').disabled = queue.length === 0;
        $('export-state').textContent = queue.length ? `已选择 ${queue.length} 篇，导出时将按当前顺序排列。` : '至少选择一篇文章后才能导出。';
        $('export-list').innerHTML = queue.length ? queue.map((item,index) => `<div class="selection-item"><span>${index + 1}</span><div><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.source)}</small></div></div>`).join('') : '暂未选择题目';
    }
    async function exportWord() {
        if (!queue.length) return;
        const button = $('export-submit'); button.disabled = true; button.textContent = '正在生成 Word…'; $('export-state').textContent = '正在整理题目和分页，请稍候。';
        try {
            const result = await api('/api/export/word', {method:'POST', body:JSON.stringify({items:queue.map(({type,id}) => ({type,id}))})});
            $('export-state').innerHTML = result.download_url ? `<a class="text-link" href="${escapeHtml(result.download_url)}">下载生成的 Word 文件</a>` : '导出完成。';
            showToast('Word 文件已生成。', 'success');
        } catch (error) { $('export-state').textContent = error.message || '导出失败，请重试。'; showToast('导出失败，请重试。', 'error'); }
        finally { button.disabled = false; button.textContent = '导出 Word'; }
    }
    $('export-submit').addEventListener('click', exportWord);
    loadItems(); updateQueue();
})();

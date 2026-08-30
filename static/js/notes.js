const notesState = {
    csrf: '',
    conversationId: Number(localStorage.getItem('cet-ai-conversation')) || null,
    calendarChart: null,
    noteHistory: [],
    modalDate: null,
    modalOriginal: '',
    currentOriginal: '',
    modalLastFocus: null,
    drawerLastFocus: null,
    drawerTouchStart: null,
    aiAbort: null,
    rankIdentity: getRankChatIdentity(1, '童生'),
};
const noteEl = id => document.getElementById(id);

document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([loadTodayNote(), loadCalendar(), loadNoteHistory(), loadAIState(), loadRankIdentity(), loadMemories(), loadConversations()]);
    if (notesState.conversationId) loadConversation(notesState.conversationId);
    noteEl('notes-chat-form').addEventListener('submit', event => { event.preventDefault(); if (notesState.aiAbort) { notesState.aiAbort.abort(); return; } sendNoteChat(noteEl('notes-chat-input').value.trim()); });
    noteEl('notes-search-send').addEventListener('click', () => {
        const query = noteEl('notes-ai-search').value.trim();
        if (query) sendNoteChat(`请在我的历史笔记中查找与“${query}”有关的内容，并标出日期和原文。`);
    });
    noteEl('notes-new-chat').addEventListener('click', () => {
        notesState.conversationId = null; localStorage.removeItem('cet-ai-conversation');
        noteEl('notes-ai-chat').innerHTML = '<div class="assistant-empty"><strong>新的对话已经准备好</strong><p>这次可以从另一个问题开始。</p></div>';
    });
    noteEl('memory-clear').addEventListener('click', clearMemories);
    noteEl('note-history-search').addEventListener('input', event => renderNoteHistory(event.target.value));
    noteEl('note-modal-close').addEventListener('click', () => closeNoteModal());
    noteEl('note-manager-modal').addEventListener('click', event => { if (event.target === event.currentTarget) closeNoteModal(); });
    noteEl('note-modal-edit').addEventListener('click', beginNoteEdit);
    noteEl('note-modal-save').addEventListener('click', saveManagedNote);
    noteEl('note-modal-delete').addEventListener('click', deleteManagedNote);
    noteEl('note-manager-modal').addEventListener('keydown', handleNoteModalKeydown);
    noteEl('note-manager-open').addEventListener('click', openNoteManagerDrawer);
    noteEl('note-manager-close').addEventListener('click', closeNoteManagerDrawer);
    noteEl('note-manager-backdrop').addEventListener('click', closeNoteManagerDrawer);
    noteEl('note-manager-drawer').addEventListener('keydown', handleNoteDrawerKeydown);
    noteEl('note-content').addEventListener('input', () => {
        noteEl('note-save-state').textContent = noteEl('note-content').value === notesState.currentOriginal ? '已保存到本机。' : '有未保存修改';
    });
    window.addEventListener('beforeunload', event => {
        if (noteEl('note-content').value === notesState.currentOriginal) return;
        event.preventDefault(); event.returnValue = '';
    });
    noteEl('note-manager-handle').addEventListener('touchstart', event => { notesState.drawerTouchStart = event.touches[0]?.clientY ?? null; }, {passive:true});
    noteEl('note-manager-handle').addEventListener('touchend', event => {
        const end = event.changedTouches[0]?.clientY;
        if (notesState.drawerTouchStart !== null && end - notesState.drawerTouchStart > 64) closeNoteManagerDrawer();
        notesState.drawerTouchStart = null;
    }, {passive:true});
});

function openNoteManagerDrawer() {
    if (!window.matchMedia('(max-width: 767px)').matches) return;
    const drawer = noteEl('note-manager-drawer'), backdrop = noteEl('note-manager-backdrop');
    notesState.drawerLastFocus = document.activeElement;
    drawer.classList.add('is-open');
    backdrop.hidden = false;
    requestAnimationFrame(() => backdrop.classList.add('is-open'));
    noteEl('note-manager-open').setAttribute('aria-expanded', 'true');
    document.body.classList.add('note-drawer-open');
    drawer.focus();
}

function closeNoteManagerDrawer() {
    const drawer = noteEl('note-manager-drawer'), backdrop = noteEl('note-manager-backdrop');
    drawer.classList.remove('is-open');
    backdrop.classList.remove('is-open');
    noteEl('note-manager-open').setAttribute('aria-expanded', 'false');
    document.body.classList.remove('note-drawer-open');
    window.setTimeout(() => { if (!backdrop.classList.contains('is-open')) backdrop.hidden = true; }, 180);
    if (notesState.drawerLastFocus && document.contains(notesState.drawerLastFocus)) notesState.drawerLastFocus.focus();
}

function handleNoteDrawerKeydown(event) {
    if (event.key === 'Escape') { event.preventDefault(); closeNoteManagerDrawer(); return; }
    if (event.key !== 'Tab') return;
    const focusable = [...noteEl('note-manager-drawer').querySelectorAll('button:not([disabled]), input:not([disabled])')].filter(element => element.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

async function loadAIState() { try { const status = await api('/api/ai/config/status'); notesState.csrf = status.csrf_token; if (!status.configured) noteEl('notes-ai-chat').insertAdjacentHTML('afterbegin','<div class="region-state region-state--empty"><strong>AI 尚未配置</strong><span>笔记编辑仍可使用；到“我的 → AI 服务”配置后即可开始对话。</span></div>'); } catch (_) { notesState.csrf = ''; } }
async function loadRankIdentity() { try { const data = await api('/api/level/detail'); notesState.rankIdentity = getRankChatIdentity(data.level?.rank, data.level?.name); } catch (_) { notesState.rankIdentity = getRankChatIdentity(1, '童生'); } }
async function loadTodayNote() { try { const data = await api('/api/notes/today'); noteEl('note-content').value = data.content || ''; notesState.currentOriginal = data.content || ''; noteEl('note-date-title').textContent = `今日笔记 · ${data.date}`; } catch (error) { noteEl('note-save-state').textContent = error.message || '今日笔记加载失败，请刷新重试。'; } }
async function saveNote() { const state = noteEl('note-save-state'); state.textContent = '正在保存…'; try { await api('/api/notes/save', {method: 'POST', body: JSON.stringify({content: noteEl('note-content').value})}); notesState.currentOriginal = noteEl('note-content').value; state.textContent = '已保存到本机。'; await Promise.all([loadNoteHistory(), loadCalendar()]); showToast('笔记已保存。', 'success'); } catch (_) { state.textContent = '保存失败，请重试。'; } }

function todayLocalISO() {
    const now = new Date(), offset = now.getTimezoneOffset() * 60000;
    return new Date(now.getTime() - offset).toISOString().slice(0,10);
}

function readableNoteDate(value) {
    const parts = String(value).split('-').map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return value;
    return new Intl.DateTimeFormat('zh-CN', {year:'numeric', month:'short', day:'numeric', weekday:'short'}).format(new Date(parts[0], parts[1] - 1, parts[2]));
}

async function loadNoteHistory() {
    const list = noteEl('note-history-list');
    list.innerHTML = '<p class="muted">正在读取历史笔记…</p>';
    try {
        notesState.noteHistory = await api('/api/notes/history');
        noteEl('note-history-count').textContent = `${notesState.noteHistory.length} 篇`;
        noteEl('note-drawer-count').textContent = `${notesState.noteHistory.length} 篇`;
        renderNoteHistory(noteEl('note-history-search').value);
    } catch (error) {
        list.innerHTML = '<div class="note-history-empty"><strong>历史笔记加载失败</strong><p>请确认本地服务正常后刷新页面。</p></div>';
    }
}

function renderNoteHistory(query = '') {
    const list = noteEl('note-history-list');
    const keyword = String(query).trim().toLowerCase();
    const records = notesState.noteHistory.filter(item => !keyword || item.date.includes(keyword) || item.preview.toLowerCase().includes(keyword));
    list.innerHTML = '';
    if (!records.length) {
        const empty = document.createElement('div');
        empty.className = 'note-history-empty';
        const strong = document.createElement('strong');
        const p = document.createElement('p');
        strong.textContent = notesState.noteHistory.length ? '没有匹配的笔记' : '还没有历史笔记';
        p.textContent = notesState.noteHistory.length ? '换一个关键词或日期再试试。' : '保存今日笔记后，它会出现在这里。';
        empty.append(strong, p); list.appendChild(empty); return;
    }
    records.forEach(item => {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'note-history-item';
        const heading = document.createElement('span'); heading.className = 'note-history-item__heading';
        const dateText = document.createElement('strong'); dateText.textContent = readableNoteDate(item.date);
        const count = document.createElement('small'); count.textContent = `${item.length} 字${item.has_ai_summary ? ' · 有 AI 总结' : ''}`;
        const preview = document.createElement('span'); preview.className = 'note-history-item__preview'; preview.textContent = item.preview;
        heading.append(dateText, count); button.append(heading, preview);
        button.addEventListener('click', () => openNoteModal(item.date, button));
        list.appendChild(button);
    });
}

async function openNoteModal(noteDate, trigger) {
    const overlay = noteEl('note-manager-modal');
    notesState.modalLastFocus = trigger || document.activeElement;
    notesState.modalDate = noteDate;
    noteEl('note-modal-title').textContent = readableNoteDate(noteDate);
    noteEl('note-modal-state').textContent = '正在读取完整笔记…';
    noteEl('note-modal-preview').textContent = '';
    noteEl('note-modal-summary-wrap').hidden = true;
    noteEl('note-modal-delete').disabled = true;
    noteEl('note-modal-edit').disabled = true;
    overlay.hidden = false;
    noteEl('note-modal-close').focus();
    try {
        const data = await api(`/api/notes/detail/${noteDate}`);
        notesState.modalOriginal = data.content || '';
        noteEl('note-modal-preview').textContent = notesState.modalOriginal;
        noteEl('note-modal-preview').hidden = false;
        noteEl('note-modal-editor').value = notesState.modalOriginal;
        noteEl('note-modal-editor').hidden = true;
        noteEl('note-modal-edit').hidden = false;
        noteEl('note-modal-save').hidden = true;
        noteEl('note-modal-state').textContent = `${notesState.modalOriginal.length} 字 · 内容保存在本机`;
        if (data.ai_summary) {
            noteEl('note-modal-summary').textContent = data.ai_summary;
            noteEl('note-modal-summary-wrap').hidden = false;
        }
        noteEl('note-modal-delete').disabled = false;
        noteEl('note-modal-edit').disabled = false;
    } catch (error) {
        noteEl('note-modal-state').textContent = error.message || '笔记加载失败，请关闭后重试。';
    }
}

function beginNoteEdit() {
    noteEl('note-modal-preview').hidden = true;
    noteEl('note-modal-editor').hidden = false;
    noteEl('note-modal-edit').hidden = true;
    noteEl('note-modal-save').hidden = false;
    noteEl('note-modal-state').textContent = '正在编辑；保存前不会修改本地笔记。';
    noteEl('note-modal-editor').focus();
}

async function saveManagedNote() {
    const content = noteEl('note-modal-editor').value;
    const button = noteEl('note-modal-save');
    button.disabled = true; noteEl('note-modal-state').textContent = '正在保存修改…';
    try {
        await api(`/api/notes/${notesState.modalDate}`, {method:'PUT', body:JSON.stringify({content})});
        notesState.modalOriginal = content;
        noteEl('note-modal-preview').textContent = content;
        noteEl('note-modal-preview').hidden = false;
        noteEl('note-modal-editor').hidden = true;
        noteEl('note-modal-edit').hidden = false;
        noteEl('note-modal-save').hidden = true;
        noteEl('note-modal-state').textContent = `${content.length} 字 · 修改已保存`;
        await Promise.all([loadNoteHistory(), loadCalendar()]);
        if (notesState.modalDate === todayLocalISO()) await loadTodayNote();
        showToast('历史笔记已更新。', 'success');
    } catch (error) {
        noteEl('note-modal-state').textContent = error.message || '保存失败，请重试。';
    } finally { button.disabled = false; }
}

async function deleteManagedNote() {
    if (!window.confirm(`删除 ${notesState.modalDate} 的笔记？此操作不可恢复。`)) return;
    const button = noteEl('note-modal-delete');
    button.disabled = true; noteEl('note-modal-state').textContent = '正在删除笔记…';
    try {
        const deletedDate = notesState.modalDate;
        await api(`/api/notes/${deletedDate}`, {method:'DELETE'});
        closeNoteModal(true);
        await Promise.all([loadNoteHistory(), loadCalendar()]);
        if (deletedDate === todayLocalISO()) await loadTodayNote();
        showToast('笔记已删除。', 'success');
    } catch (error) {
        noteEl('note-modal-state').textContent = error.message || '删除失败，请重试。';
        button.disabled = false;
    }
}

function closeNoteModal(force = false) {
    const editor = noteEl('note-modal-editor');
    if (!force && !editor.hidden && editor.value !== notesState.modalOriginal && !window.confirm('修改尚未保存，确定关闭吗？')) return false;
    noteEl('note-manager-modal').hidden = true;
    notesState.modalDate = null;
    if (notesState.modalLastFocus && document.contains(notesState.modalLastFocus)) notesState.modalLastFocus.focus();
    return true;
}

function handleNoteModalKeydown(event) {
    if (event.key === 'Escape') { event.preventDefault(); closeNoteModal(); return; }
    if (event.key !== 'Tab') return;
    const focusable = [...noteEl('note-manager-modal').querySelectorAll('button:not([disabled]), textarea:not([hidden])')].filter(element => !element.hidden);
    if (!focusable.length) return;
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
async function generateAISummary() { const area = noteEl('ai-summary'); area.innerHTML = '<p class="muted">AI 正在结合今日记录整理…</p>'; try { const data = await api('/api/notes/ai-summary', {method: 'POST'}), summary = data.summary || data; area.innerHTML = ''; [['今日概览', summary.overview], ['知识关联', summary.connections], ['继续延伸', summary.extension], ['薄弱提醒', summary.weakness_alert]].forEach(([label, value]) => { if (!value) return; const item = document.createElement('article'); const strong = document.createElement('strong'); const p = document.createElement('p'); strong.textContent = label; p.textContent = value; item.append(strong, p); area.appendChild(item); }); } catch (error) { area.textContent = error.message || 'AI 服务不可用。'; } }

async function loadCalendar() {
    const element = noteEl('note-calendar');
    if (!element || !window.echarts) return;
    try {
        const data = await api('/api/notes/calendar');
        notesState.calendarChart = notesState.calendarChart || echarts.init(element);
        const max = Math.max(...data.data.map(item => item[1]), 1);
        notesState.calendarChart.setOption({
            tooltip:{formatter:params=>`${params.data[0]}：${params.data[1] ? '有笔记记录' : '无记录'}`},
            visualMap:{min:0,max,inRange:{color:['#eee7db','#b7bacb','#303b67']},show:false},
            calendar:{range:[data.data[0]?.[0],data.data.at(-1)?.[0]],cellSize:[14,14],itemStyle:{borderWidth:2,borderColor:'#fffaf1'},dayLabel:{fontSize:11,color:'#777482'},monthLabel:{fontSize:12,color:'#777482'}},
            series:[{type:'heatmap',coordinateSystem:'calendar',data:data.data}],
        }, true);
    } catch (_) {}
}
window.addEventListener('resize', () => notesState.calendarChart?.resize());

function messageAvatar(role) { const image = document.createElement('img'); image.className = `chat-avatar chat-avatar--${role}`; if (role === 'assistant') { image.src = CET_AI_AVATAR; image.alt = '学习助理头像'; } else { image.src = notesState.rankIdentity.src; image.alt = `${notesState.rankIdentity.name}段位头像`; image.classList.add(notesState.rankIdentity.className); } return image; }
function messageNode(role, text, citations = [], action = null, memoryCandidate = null) { const article = document.createElement('article'); article.className = `assistant-message assistant-message--${role}`; const avatar = messageAvatar(role); const bubble = document.createElement('div'); bubble.className = 'assistant-message__bubble'; const name = document.createElement('strong'); name.textContent = role === 'user' ? notesState.rankIdentity.name : '学习助理'; const copy = document.createElement('p'); copy.textContent = String(text || '').replace(/\*\*(.*?)\*\*/g, '$1'); bubble.append(name, copy); if (citations.length) { const sources = document.createElement('div'); sources.className = 'assistant-citations'; citations.forEach(item => { const quote = document.createElement('blockquote'); quote.textContent = `${item.date} · ${item.excerpt}`; sources.appendChild(quote); }); bubble.appendChild(sources); } if (action) bubble.appendChild(actionNode(action)); if (memoryCandidate) bubble.appendChild(memoryNode(memoryCandidate)); article.append(avatar, bubble); return article; }
function actionNode(action) { const box = document.createElement('div'); box.className = 'assistant-action'; const label = document.createElement('strong'); label.textContent = '待写入笔记'; const preview = document.createElement('p'); preview.textContent = action.preview; const row = document.createElement('div'); const yes = document.createElement('button'); yes.type='button'; yes.className='btn btn-primary'; yes.textContent='确认追加'; const no=document.createElement('button'); no.type='button'; no.className='btn btn-secondary'; no.textContent='取消'; yes.onclick=()=>resolveDraft(action.id,'confirm',box); no.onclick=()=>resolveDraft(action.id,'reject',box); row.append(yes,no); box.append(label,preview,row); return box; }
function memoryNode(candidate) { const box=document.createElement('div'); box.className='assistant-action'; const p=document.createElement('p'); p.textContent=`是否允许 AI 记住：${candidate.content}`; const yes=document.createElement('button'); yes.type='button'; yes.className='btn btn-secondary'; yes.textContent='确认记住'; yes.onclick=async()=>{try{await api('/api/ai/memories/confirm',{method:'POST',headers:{'X-CSRF-Token':notesState.csrf},body:JSON.stringify({content:candidate.content,idempotency_key:`memory-${Date.now()}`})});box.textContent='已保存为只读记忆。';loadMemories()}catch(error){showToast(error.message,'error')}}; box.append(p,yes); return box; }
async function resolveDraft(id, decision, box) { try { await api(`/api/ai/actions/${id}/${decision}`, {method:'POST',headers:{'X-CSRF-Token':notesState.csrf},body:'{}'}); box.textContent = decision === 'confirm' ? '已追加到今日笔记。' : '已取消。'; if (decision === 'confirm') loadTodayNote(); } catch(error) { showToast(error.message,'error'); } }
function appendMessage(role, text, citations, action, memoryCandidate) { const thread=noteEl('notes-ai-chat'); thread.querySelector('.assistant-empty')?.remove(); const article=messageNode(role,text,citations,action,memoryCandidate); thread.appendChild(article); thread.scrollTop=thread.scrollHeight; return {article,bubble:article.querySelector('.assistant-message__bubble'),copy:article.querySelector('.assistant-message__bubble > p')}; }

function decorateStreamedNoteMessage(node, result) {
    if (!node?.bubble) return;
    if (result.citations?.length) {
        const sources=document.createElement('div');sources.className='assistant-citations';
        result.citations.forEach(item=>{const quote=document.createElement('blockquote');quote.textContent=`${item.date} · ${item.excerpt}`;sources.appendChild(quote);});
        node.bubble.appendChild(sources);
    }
    if (result.action) node.bubble.appendChild(actionNode(result.action));
    if (result.memory_candidate) node.bubble.appendChild(memoryNode(result.memory_candidate));
}

function addNoteChatRetry(node,message) {
    const status=document.createElement('p');status.className='assistant-stream-status';status.textContent='连接中断，以上内容已保留。';
    const retry=document.createElement('button');retry.type='button';retry.className='text-button';retry.textContent='重试回答';
    retry.onclick=()=>{retry.disabled=true;sendNoteChat(message,false);};node.bubble.append(status,retry);
}
async function sendNoteChat(message,showUser=true) {
    if (!message) return;
    const input=noteEl('notes-chat-input'), button=noteEl('notes-chat-form').querySelector('button');
    if(showUser)appendMessage('user',message); input.value='';
    const node=appendMessage('assistant','');
    notesState.aiAbort=new AbortController();button.disabled=false;button.textContent='停止生成';
    const writer=createAITypewriter(node.copy,{onUpdate:()=>{node.article.parentElement.scrollTop=node.article.parentElement.scrollHeight;}});
    try {
        const response=await fetch('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':notesState.csrf},body:JSON.stringify({message,conversation_id:notesState.conversationId}),signal:notesState.aiAbort.signal});
        if(!response.ok){const error=await response.json().catch(()=>({}));throw new Error(error.error||'AI 请求失败。');}
        const result=await consumeAIStream(response,{onDelta:text=>writer.append(text),onDone:data=>writer.finish(data.message)});
        notesState.conversationId=result.conversation_id;localStorage.setItem('cet-ai-conversation',String(result.conversation_id));
        await writer.finish(result.message);renderSafeMarkdown(node.copy,result.message);decorateStreamedNoteMessage(node,result);loadConversations();
    } catch(error) {
        writer.stop();
        if(error.name==='AbortError')node.copy.textContent+=node.copy.textContent?'\n（已停止生成）':'已停止生成。';
        else {if(!node.copy.textContent)node.copy.textContent=error.message||'这次没有连接上 AI。';addNoteChatRetry(node,message);}
    } finally {notesState.aiAbort=null;button.disabled=false;button.textContent='发送';input.focus();}
}

async function loadConversations() { try { const data=await api('/api/ai/conversations'), area=noteEl('notes-conversations'); area.innerHTML=''; if(!data.conversations.length){area.innerHTML='<p class="muted">还没有 AI 对话。</p>';return;} data.conversations.forEach(item=>{const wrap=document.createElement('div');wrap.className='conversation-item';const button=document.createElement('button');button.type='button';button.className='conversation-link';button.dataset.id=item.id;button.setAttribute('aria-pressed',notesState.conversationId===item.id?'true':'false');const strong=document.createElement('strong');strong.textContent=item.title;const span=document.createElement('span');span.textContent=`${item.message_count} 条消息 · ${item.updated_at.slice(0,16)}`;button.append(strong,span);button.onclick=()=>selectConversation(item.id);const del=document.createElement('button');del.type='button';del.className='conversation-delete';del.setAttribute('aria-label',`删除对话：${item.title}`);del.textContent='删除';del.onclick=(event)=>{event.stopPropagation();deleteConversation(item.id);};wrap.append(button,del);if(notesState.conversationId===item.id)wrap.classList.add('is-active');area.appendChild(wrap)}); } catch(_){} }
async function selectConversation(id) { try { await loadConversation(id); document.querySelectorAll('.conversation-item').forEach(wrap=>{const button=wrap.querySelector('.conversation-link');const active=Number(button.dataset.id)===notesState.conversationId;wrap.classList.toggle('is-active',active);button.setAttribute('aria-pressed',active?'true':'false');}); } catch(_){} }
async function deleteConversation(id) { if(!window.confirm('删除这条对话？对话中的消息也会一并删除，且不可恢复。'))return; try { await api(`/api/ai/conversations/${id}`,{method:'DELETE',headers:{'X-CSRF-Token':notesState.csrf}}); if(notesState.conversationId===id){notesState.conversationId=null;localStorage.removeItem('cet-ai-conversation');noteEl('notes-ai-chat').innerHTML='<div class="assistant-empty"><strong>新的对话已经准备好</strong><p>这次可以从另一个问题开始。</p></div>';} loadConversations(); showToast('对话已删除。','success'); } catch(error){ showToast(error.message,'error'); } }
async function loadConversation(id) { try { const data=await api(`/api/ai/conversations/${id}/messages`), thread=noteEl('notes-ai-chat'); notesState.conversationId=id;localStorage.setItem('cet-ai-conversation',String(id));thread.innerHTML='';data.messages.forEach(item=>thread.appendChild(messageNode(item.role,item.content,item.citations||[])));thread.scrollTop=thread.scrollHeight; } catch(_){} }
async function loadMemories() { try { const data=await api('/api/ai/memories'), area=noteEl('memory-list'); area.innerHTML=''; noteEl('memory-clear').disabled=!data.memories.length; if(!data.memories.length){area.innerHTML='<p class="muted">暂无已确认记忆。学习一段时间或在对话中确认后会出现在这里。</p>';return;} data.memories.forEach(item=>{const article=document.createElement('article');const copy=document.createElement('div');const type=document.createElement('span');const p=document.createElement('p');type.textContent=item.memory_type==='system_fact'?'学习事实':'你确认的信息';p.textContent=item.content;copy.append(type,p);const remove=document.createElement('button');remove.type='button';remove.textContent='删除';remove.onclick=()=>deleteMemory(item.id);article.append(copy,remove);area.appendChild(article)}); } catch(_){} }
async function deleteMemory(id) { try { await api(`/api/ai/memories/${id}`,{method:'DELETE',headers:{'X-CSRF-Token':notesState.csrf}});loadMemories(); } catch(error){showToast(error.message,'error')} }
async function clearMemories() { if(!window.confirm('清空全部 AI 记忆？原始学习记录和笔记不会被删除。'))return;try{await api('/api/ai/memories',{method:'DELETE',headers:{'X-CSRF-Token':notesState.csrf}});loadMemories();showToast('AI 记忆已清空。','success')}catch(error){showToast(error.message,'error')} }

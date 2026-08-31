async function api(url, options = {}) {
    const config = {...options, headers: {'Content-Type': 'application/json', ...(options.headers || {})}};
    try {
        const response = await fetch(url, config);
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || `请求失败（${response.status}）`);
        return payload;
    } catch (error) {
        if (error instanceof TypeError) showToast('暂时无法连接本地服务，请稍后重试。', 'error');
        throw error;
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('is-visible'));
    setTimeout(() => {
        toast.classList.remove('is-visible');
        setTimeout(() => toast.remove(), 220);
    }, 2800);
}

let activeEnglishAudio = null;

function speakEnglish(text, options = {}) {
    const value = String(text || '').trim();
    if (!value) return false;
    let fallbackStarted = false;
    const fallback = () => {
        if (fallbackStarted) return false;
        fallbackStarted = true;
        if (window.CETNativeSpeech && typeof window.CETNativeSpeech.speak === 'function') {
            try {
                const accepted = window.CETNativeSpeech.speak(value, Number(options.rate) || 0.88);
                if (accepted !== false) {
                    options.onStart?.();
                    return true;
                }
            } catch (_) {}
        }
        if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
            showToast('本站离线发音暂不可用，请检查资源包或更新应用。', 'warning');
            options.onError?.();
            return false;
        }
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(value);
        utterance.lang = options.lang || 'en-US';
        utterance.rate = Number(options.rate) || 0.88;
        utterance.pitch = Number(options.pitch) || 1;
        const voices = window.speechSynthesis.getVoices();
        const voice = voices.find(item => item.lang === utterance.lang)
            || voices.find(item => /^en[-_]/i.test(item.lang || ''));
        if (voice) utterance.voice = voice;
        utterance.onstart = () => options.onStart?.();
        utterance.onend = () => options.onEnd?.();
        utterance.onerror = () => {
            options.onError?.();
            showToast('发音播放失败，请检查设备的语音服务。', 'error');
        };
        window.speechSynthesis.speak(utterance);
        return true;
    };

    const audioUrl = options.audioUrl || (options.wordId ? `/api/words/${Number(options.wordId)}/audio` : '');
    if (audioUrl) {
        try {
            if (activeEnglishAudio) {
                activeEnglishAudio.pause();
                activeEnglishAudio.src = '';
            }
            const audio = new Audio(audioUrl);
            activeEnglishAudio = audio;
            audio.preload = 'auto';
            audio.onplay = () => options.onStart?.();
            audio.onended = () => { if (activeEnglishAudio === audio) activeEnglishAudio = null; options.onEnd?.(); };
            audio.onerror = () => { if (activeEnglishAudio === audio) activeEnglishAudio = null; fallback(); };
            const started = audio.play();
            if (started && typeof started.catch === 'function') started.catch(() => fallback());
            return true;
        } catch (_) {
            return fallback();
        }
    }
    return fallback();
}

function setRegionState(element, state, message = '') {
    if (!element) return;
    element.dataset.state = state;
    element.setAttribute('aria-busy', state === 'loading' ? 'true' : 'false');
    const status = element.querySelector('[data-region-status]');
    if (status) {
        status.hidden = state === 'ready';
        status.className = `region-state region-state--${state}`;
        status.textContent = message;
    }
}

function fmtMinutes(value) {
    const minutes = Math.max(0, Number(value) || 0);
    if (minutes < 60) return `${minutes} 分钟`;
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return rest ? `${hours} 小时 ${rest} 分钟` : `${hours} 小时`;
}

function createAITypewriter(target, options = {}) {
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    let queue = '', received = '', timer = null, stopped = false, finishResolve = null;
    const scroll = typeof options.onUpdate === 'function' ? options.onUpdate : () => {};
    const clean = value => String(value || '').replace(/\*\*(.*?)\*\*/g, '$1');
    const settle = () => {
        if (!queue && finishResolve) {
            const resolve = finishResolve; finishResolve = null; resolve();
        }
    };
    const pump = () => {
        timer = null;
        if (stopped || !queue) { settle(); return; }
        const burst = queue.length > 180 ? 8 : queue.length > 80 ? 4 : 1;
        const next = queue.slice(0, burst); queue = queue.slice(burst);
        target.textContent += clean(next);
        scroll();
        const punctuation = /[。！？；.!?;\n]$/.test(next);
        timer = window.setTimeout(pump, punctuation ? 70 : queue.length > 80 ? 4 : 17);
    };
    return {
        append(value) {
            const text = String(value || '');
            if (!text || stopped) return;
            received += text;
            if (reduceMotion) { target.textContent = clean(received); scroll(); return; }
            queue += text;
            if (!timer) pump();
        },
        finish(finalText = '') {
            const finalValue = String(finalText || '');
            if (finalValue && finalValue !== received) {
                received = finalValue; queue = '';
                target.textContent = clean(finalValue); scroll();
            }
            if (reduceMotion || !queue) return Promise.resolve();
            return new Promise(resolve => { finishResolve = resolve; if (!timer) pump(); });
        },
        stop() {
            stopped = true; queue = ''; if (timer) window.clearTimeout(timer); timer = null; settle();
        },
        text() { return received; },
    };
}

async function consumeAIStream(response, handlers = {}) {
    if (!response.body || !response.body.getReader) throw new Error('当前浏览器不支持流式回答。');
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '', finalResult = null;
    const dispatch = async block => {
        const lines = block.split(/\r?\n/);
        let event = 'message';
        const dataLines = [];
        lines.forEach(line => {
            if (line.startsWith('event:')) event = line.slice(6).trim();
            else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
        });
        if (!dataLines.length) return;
        let payload;
        try { payload = JSON.parse(dataLines.join('\n')); } catch (_) { return; }
        if (event === 'delta') handlers.onDelta?.(payload.delta || '');
        else if (event === 'meta') handlers.onMeta?.(payload);
        else if (event === 'error') {
            handlers.onError?.(payload);
            throw new Error(payload.error || 'AI 流式回答中断。');
        } else if (event === 'done' || event === 'message') {
            finalResult = payload;
            if (event === 'done') await handlers.onDone?.(payload);
        }
    };
    while (true) {
        const {value, done} = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), {stream: !done}).replace(/\r\n/g, '\n');
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) >= 0) {
            const block = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
            if (block.trim()) await dispatch(block);
        }
        if (done) break;
    }
    if (buffer.trim()) await dispatch(buffer);
    if (!finalResult) throw new Error('AI 没有返回完整结果。');
    return finalResult;
}

function renderSafeMarkdown(target, value) {
    if (!target) return;
    const escaped = String(value || '').replace(/[&<>"']/g, character => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[character]));
    const formatted = escaped
        .replace(/`([^`\n]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
        .replace(/^[-•]\s+(.+)$/gm, '<span class="ai-list-item">• $1</span>')
        .replace(/\n/g, '<br>');
    target.innerHTML = formatted;
}

const CET_RANK_PORTRAITS = Object.freeze([
    null,
    {name: '童生', src: '/static/images/ranks/rank-01-tongsheng.png'},
    {name: '生员', src: '/static/images/ranks/rank-02-shengyuan.png'},
    {name: '秀才', src: '/static/images/ranks/rank-03-xiucai.png'},
    {name: '举人', src: '/static/images/ranks/rank-04-juren.png'},
    {name: '解元', src: '/static/images/ranks/rank-05-jieyuan.png'},
    {name: '贡士', src: '/static/images/ranks/rank-06-gongshi.png'},
    {name: '进士', src: '/static/images/ranks/rank-07-jinshi.png'},
    {name: '翰林', src: '/static/images/ranks/rank-08-hanlin.png'},
    {name: '学士', src: '/static/images/ranks/rank-09-xueshi.png'},
    {name: '状元', src: '/static/images/ranks/rank-10-zhuangyuan.png'},
]);

const CET_RANK_NAMES = Object.freeze([
    null, '童生', '生员', '秀才', '举人', '解元', '贡士', '进士', '翰林', '学士', '状元',
]);

function getRankChatIdentity(rank, name = '') {
    const safeRank = Math.min(10, Math.max(1, Number(rank) || 1));
    const rankName = String(name || CET_RANK_NAMES[safeRank] || '童生');
    const palette = [
        null,
        ['#ece3d5', '#75654f', '#303b67'],
        ['#e6e7ef', '#69728f', '#303b67'],
        ['#f2ddd5', '#c4553e', '#303b67'],
        ['#dde0e9', '#4f5b84', '#303b67'],
        ['#efd4ca', '#a94734', '#303b67'],
        ['#e4ded2', '#665c4d', '#303b67'],
        ['#d7dbe8', '#303b67', '#303b67'],
        ['#ecd1c7', '#963d2d', '#303b67'],
        ['#dfe1ea', '#222d59', '#222d59'],
        ['#303b67', '#c4553e', '#fffaf1'],
    ][safeRank];
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect x="3" y="3" width="90" height="90" rx="45" fill="${palette[0]}" stroke="${palette[1]}" stroke-width="6"/><circle cx="48" cy="48" r="34" fill="none" stroke="${palette[1]}" stroke-width="1" opacity=".55"/><text x="48" y="58" text-anchor="middle" font-family="Microsoft YaHei UI,serif" font-size="24" font-weight="700" fill="${palette[2]}">${rankName}</text></svg>`;
    return {
        rank: safeRank,
        name: rankName,
        src: `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`,
        className: `chat-avatar--rank-${safeRank}`,
    };
}

function setRankPortrait(image, rank) {
    if (!image) return;
    const safeRank = Math.min(10, Math.max(1, Number(rank) || 1));
    const portrait = CET_RANK_PORTRAITS[safeRank];
    const frame = image.closest('.rank-figure, .rank-legacy-figure');
    image.classList.remove('is-revealed');
    image.hidden = false;
    image.src = portrait.src;
    image.alt = `${portrait.name}段位人物形象`;
    image.dataset.rank = String(safeRank);
    if (frame) {
        frame.dataset.rank = String(safeRank);
        frame.classList.remove('is-image-missing');
    }
    const reveal = () => requestAnimationFrame(() => image.classList.add('is-revealed'));
    image.addEventListener('load', reveal, {once: true});
    image.addEventListener('error', () => {
        image.hidden = true;
        if (frame) frame.classList.add('is-image-missing');
    }, {once: true});
    if (image.complete && image.naturalWidth) reveal();
}

function parseJSON(value) {
    if (!value) return [];
    if (typeof value === 'object') return value;
    try { return JSON.parse(value); } catch (_) { return []; }
}

function playSound(type) {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        window.__cetAudioContext = window.__cetAudioContext || new AudioContext();
        const context = window.__cetAudioContext;
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.connect(gain); gain.connect(context.destination);
        oscillator.frequency.value = type === 'correct' ? 760 : 190;
        gain.gain.setValueAtTime(.08, context.currentTime);
        gain.gain.exponentialRampToValueAtTime(.001, context.currentTime + .22);
        oscillator.start(); oscillator.stop(context.currentTime + .22);
    } catch (_) {}
}

function playSlaySound() { playSound('correct'); }

async function applyDifficultyChips() {
    const chips = document.querySelectorAll('[data-difficulty-chip]');
    if (!chips.length) return;
    try {
        const data = await api('/api/study/difficulty-setting');
        const label = data.difficulty ? data.label : '';
        chips.forEach(chip => {
            chip.textContent = label ? `当前难度：${label}` : '当前难度：全部';
            chip.classList.toggle('is-set', !!label);
        });
    } catch (_) { /* 读取失败时保留初始占位文本 */ }
}

document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    const groups = {
        home: ['/'],
        learn: ['/learn', '/study', '/review', '/reading', '/listening', '/grammar', '/writing'],
        control: ['/control', '/notes'],
        growth: ['/growth', '/level', '/summary'],
        profile: ['/profile', '/export']
    };
    const active = Object.entries(groups).find(([, paths]) => paths.includes(path))?.[0];
    document.querySelectorAll('[data-nav]').forEach(link => {
        const selected = link.dataset.nav === active;
        link.classList.toggle('is-active', selected);
        if (selected) link.setAttribute('aria-current', 'page');
    });
    applyDifficultyChips();
});

/* ---- 头像工具（首页 AI 对话 & 全站广播）---- */
// 本站只有两类发言者：学习助理（AI，站点静态头像）与用户（可上传本地头像，localStorage 持久化）。
const CET_AVATAR_KEY = 'cet-user-avatar';
const CET_AI_AVATAR = '/static/images/ai-avatar.png';
const CET_AVATAR_SIZE = 96;

function getUserAvatar() {
    try { return localStorage.getItem(CET_AVATAR_KEY) || ''; } catch (_) { return ''; }
}

function saveUserAvatar(dataUrl) {
    try { localStorage.setItem(CET_AVATAR_KEY, dataUrl); } catch (_) { /* 本地存储超限时静默忽略 */ }
}

// 读取一张本地图片，居中裁成方图并压缩到 96px；失败返回空字符串。
function pickAndEncodeAvatar(input, size = CET_AVATAR_SIZE) {
    const file = input && input.files && input.files[0];
    if (!file) return Promise.resolve('');
    if (!/^image\/(png|jpe?g|webp|gif)$/i.test(file.type)) { showToast('请选择 PNG / JPG / WebP 图片。', 'error'); return Promise.resolve(''); }
    return new Promise(resolve => {
        const reader = new FileReader();
        reader.onerror = () => { showToast('图片读取失败，请重试。', 'error'); resolve(''); };
        reader.onload = () => {
            const img = new Image();
            img.onerror = () => { showToast('图片读取失败，请重试。', 'error'); resolve(''); };
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                canvas.width = size; canvas.height = size;
                ctx.fillStyle = '#303b67';
                ctx.fillRect(0, 0, size, size);
                const side = Math.min(img.width, img.height);
                const sx = (img.width - side) / 2;
                const sy = (img.height - side) / 2;
                ctx.drawImage(img, sx, sy, side, side, 0, 0, size, size);
                resolve(canvas.toDataURL('image/png'));
            };
            img.src = reader.result;
        };
        reader.readAsDataURL(file);
    });
}

// 把 file input 绑定到“点击头像即更换”：弹出选择、压缩、保存并回调。
function bindAvatarUpload(input, previewEl, onSaved) {
    if (!input) return;
    input.addEventListener('change', async () => {
        const dataUrl = await pickAndEncodeAvatar(input);
        if (!dataUrl) return;
        saveUserAvatar(dataUrl);
        if (previewEl) previewEl.src = dataUrl;
        if (onSaved) onSaved(dataUrl);
        showToast('你的头像已更新。', 'success');
    });
}

/* ---- 标题单行自适应：内容多一两个字就缩小字号，保持完整显示在一行 ---- */
// 目标：标题永不折成两行；当文本稍长超出可用宽度时，逐级缩小 font-size 直到单行放下。
function fitTextToLine(el, minFontPx = 16) {
    if (!el) return;
    el.style.whiteSpace = 'nowrap';
    const width = el.clientWidth;
    if (!width) return;
    let size = parseFloat(getComputedStyle(el).fontSize) || 32;
    const minSize = Math.max(minFontPx, size * 0.58);
    let guard = 0;
    while (el.scrollWidth > width && size > minSize && guard < 90) {
        size -= 1;
        el.style.fontSize = size + 'px';
        guard += 1;
    }
}

function initFitText(selector, minFontPx) {
    const els = Array.from(document.querySelectorAll(selector));
    if (!els.length) return;
    const run = () => els.forEach(el => { el.style.fontSize = ''; fitTextToLine(el, minFontPx); });
    run();
    let t;
    window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(run, 160); });
}

// 页面标题在手机端允许自然换成两行，避免为了单行而缩到难以阅读。
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.page-heading h1').forEach(element => {
        element.style.whiteSpace = '';
        element.style.fontSize = '';
    });
});

(function () {
    const root = document.getElementById('growth-app');
    if (!root) return;
    const charts = [];
    const $ = id => document.getElementById(id);
    const dimensionKeys = ['vocabulary','reading','listening','writing','retention','investment'];
    const labels = {vocabulary:'词汇',reading:'阅读',listening:'听力',writing:'写作',retention:'记忆',investment:'投入'};
    const colors = {indigo:'#303b67',red:'#c4553e',grid:'#d6cbbd',paper:'#fffaf1',muted:'#777482'};
    const axis = {axisLine:{lineStyle:{color:colors.grid}},axisTick:{show:false},axisLabel:{color:colors.muted},splitLine:{lineStyle:{color:'#e9e1d4'}}};
    function chart(id, option) { const instance = echarts.init($(id)); instance.setOption(option); charts.push(instance); return instance; }
    function safeNumber(value) { return Number(value) || 0; }
    function escapeHtml(value) { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
    function ledgerItem(level, key) {
        return level.score_ledger?.[key] || {
            label: labels[key] || key, score: 0, reliability: 0,
            effective_score: 0, weight: 0, contribution: 0,
            evidence: {summary: '暂无直接证据，当前算法暂不计入贡献'},
        };
    }

    function radarChart(id, textId, indicators, values, lineColor, summaryText) {
        chart(id, {
            tooltip: { formatter: params => indicators.map((item, index) => `${item.name} ${values[index]}`).join('<br>') },
            radar: {
                indicator: indicators, radius: '63%', splitNumber: 4,
                axisName: { color: colors.muted, fontSize: 12 },
                splitLine: { lineStyle: { color: '#d9cfbf' } },
                splitArea: { areaStyle: { color: ['rgba(245,240,231,.18)','rgba(255,250,241,.65)'] } },
            },
            series: [{ type: 'radar', data: [{ value: values, areaStyle: { color: 'rgba(48,59,103,.12)' }, lineStyle: { color: lineColor, width: 3 }, itemStyle: { color: colors.red } }] }],
        });
        $(textId).textContent = summaryText;
    }

    function radar(level, summary, dashboard) {
        // 1. 能力表现 —— V3 六维综合账本里的表现分
        const scoreValues = dimensionKeys.map(key => safeNumber(ledgerItem(level, key).score));
        const scoreIndicators = dimensionKeys.map(key => ({ name: labels[key], max: 100 }));
        const strongScore = Math.max(...scoreValues), weakScore = Math.min(...scoreValues);
        radarChart(
            'g-radar-performance', 'g-radar-performance-text', scoreIndicators, scoreValues, colors.indigo,
            `表现最高为${labels[dimensionKeys[scoreValues.indexOf(strongScore)]]} ${strongScore}，最低为${labels[dimensionKeys[scoreValues.indexOf(weakScore)]]} ${weakScore}。`
        );

        // 2. 专项练习表现 —— 各专项整轮平均分
        const practiceKeys = ['reading','listening','writing','diagnostic'];
        const practiceLabels = {reading:'阅读',listening:'听力',writing:'写作',diagnostic:'诊断'};
        const practiceValues = practiceKeys.map(key => safeNumber(summary.module_scores?.[key]));
        const practiceIndicators = practiceKeys.map(key => ({ name: practiceLabels[key], max: 100 }));
        const practiced = practiceValues.filter(value => value > 0);
        const practiceText = practiced.length
            ? (() => {
                const maxV = Math.max(...practiceValues), minV = Math.min(...practiceValues);
                const maxKey = practiceKeys[practiceValues.indexOf(maxV)], minKey = practiceKeys[practiceValues.indexOf(minV)];
                return `整轮平均分最高是${practiceLabels[maxKey]} ${maxV}，最低是${practiceLabels[minKey]} ${minV}。`;
            })()
            : '还没有整轮专项练习记录，完成一次阅读、听力、写作或单词专练训练后会出现在这里。';
        radarChart('g-radar-practice', 'g-radar-practice-text', practiceIndicators, practiceValues, colors.red, practiceText);

        // 3. 词库掌握 —— 各词频层级的掌握率
        const masteryKeys = ['five','four','three','two','one'];
        const masteryLabels = {five:'核心',four:'高频',three:'常见',two:'低频',one:'罕见'};
        const masteryValues = masteryKeys.map(key => safeNumber(dashboard.freq_stats?.[key]));
        const masteryIndicators = masteryKeys.map(key => ({ name: masteryLabels[key], max: 100 }));
        radarChart(
            'g-radar-mastery', 'g-radar-mastery-text', masteryIndicators, masteryValues, colors.indigo,
            masteryKeys.map(key => `${masteryLabels[key]}词掌握 ${safeNumber(dashboard.freq_stats?.[key])}%`).join('，') + '。'
        );

        $('g-ability-text').textContent = dimensionKeys.map(key=>{const item=ledgerItem(level,key);return `${labels[key]}表现 ${item.score} 分，可靠度 ${item.reliability}%，有效分 ${item.effective_score}`;}).join('；')+'。';
    }

    function achievements(summary) {
        var wordEntries = [
            ['已学单词', safeNumber(summary.learned_words)],
            ['已掌握单词', safeNumber(summary.mastered_words)],
        ];
        var practiceEntries = [
            ['阅读篇数', safeNumber(summary.reading)],
            ['听力篇数', safeNumber(summary.listening)],
            ['作文篇数', safeNumber(summary.writing)],
            ['语法练习', safeNumber(summary.grammar)],
            ['笔记篇数', safeNumber(summary.notes)],
        ];
        function barOption(entries) {
            var maxValue = Math.max.apply(null, entries.map(function (e) { return e[1]; }).concat([1]));
            return {
                animationDuration: 360,
                grid: { left: 8, right: 28, top: 12, bottom: 24, containLabel: true },
                xAxis: {
                    type: 'value',
                    max: Math.max(5, Math.ceil(maxValue * 1.18)),
                    minInterval: 1,
                    splitNumber: 4,
                    axisLine: { lineStyle: { color: colors.grid } },
                    axisTick: { show: false },
                    axisLabel: { color: colors.muted, hideOverlap: true },
                    splitLine: { lineStyle: { color: '#e9e1d4' } },
                },
                yAxis: {
                    type: 'category',
                    data: entries.map(function (e) { return e[0]; }),
                    axisLine: { lineStyle: { color: colors.grid } },
                    axisTick: { show: false },
                    axisLabel: { color: colors.muted, width: 86, overflow: 'truncate' },
                },
                tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: function (params) { return params[0].name + '：累计 ' + params[0].value; } },
                series: [{ type: 'bar', data: entries.map(function (e) { return e[1]; }), itemStyle: { color: colors.indigo }, barWidth: 14, label: { show: true, position: 'right', color: colors.muted } }],
            };
        }
        var activeDays = safeNumber(summary.active_days);
        var reviewCount = safeNumber(summary.review_count);
        chart('g-achievements', barOption(wordEntries));
        chart('g-achievements-freq', barOption(practiceEntries));
        chart('g-achievements-active', barOption([['活跃', activeDays]]));
        chart('g-achievements-review', barOption([['复习', reviewCount]]));
        $('g-active-days-value').textContent = activeDays + ' 天';
        $('g-review-count-value').textContent = reviewCount + ' 次';
        var total = wordEntries.concat(practiceEntries).reduce(function (sum, e) { return sum + e[1]; }, 0) + activeDays + reviewCount;
        $('g-achievements-text').textContent = total
            ? '已学 ' + wordEntries[0][1] + ' 个单词，其中 ' + wordEntries[1][1] + ' 个进入稳定掌握。'
            : '还没有任何学习记录，完成第一次训练后这里会填满。';
        $('g-achievements-freq-text').textContent = total
            ? '专项成果：阅读 ' + practiceEntries[0][1] + ' 篇、听力 ' + practiceEntries[1][1] + ' 篇、作文 ' + practiceEntries[2][1] + ' 篇、语法 ' + practiceEntries[3][1] + ' 次、笔记 ' + practiceEntries[4][1] + ' 篇。'
            : '';
        $('g-achievements-rhythm-text').textContent = activeDays || reviewCount
            ? '累计活跃 ' + activeDays + ' 天，完成复习 ' + reviewCount + ' 次；两项使用独立坐标范围。'
            : '还没有活跃天数或复习记录。';
    }

    function aiUsage(data,balanceData) {
        const totals=data.totals||{};$('g-ai-calls').textContent=totals.calls||0;$('g-ai-success').textContent=totals.successful||0;$('g-ai-tokens').textContent=new Intl.NumberFormat('zh-CN').format(totals.tokens||0);$('g-ai-cost').textContent=`¥${safeNumber(totals.tracked_cost_cny).toFixed(6)}`;
        const balances=balanceData?.balances||[];$('g-ai-balance').textContent=balances.length?balances.map(item=>`${item.currency==='CNY'?'¥':'$'}${item.total}`).join(' / '):'未配置';
        const outcomes=data.outcomes||[];
        const outcomeMax=Math.max(...outcomes.map(item=>safeNumber(item.count)),1);
        $('g-ai-outcomes').innerHTML=outcomes.map(item=>`<article><div><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.basis)}</small></div><span><b>${new Intl.NumberFormat('zh-CN').format(item.count||0)}</b>${escapeHtml(item.unit)}</span><i aria-hidden="true"><em style="width:${Math.max(item.count?7:0,safeNumber(item.count)/outcomeMax*100)}%"></em></i></article>`).join('')||'<p class="muted">还没有可核验的 AI 成果记录。</p>';
        const strongest=outcomes.reduce((best,item)=>safeNumber(item.count)>safeNumber(best?.count)?item:best,null);
        $('g-ai-outcome-summary').textContent=strongest&&strongest.count?`本期留下最多的是“${strongest.label}”，共 ${strongest.count}${strongest.unit}；每项都可以从本地记录反查。`:'本期还没有形成可核验成果；未追踪的历史不会被反推。';
        const daily=data.daily||[],max=Math.max(...daily.map(item=>item.calls),1);
        const dailyMap=new Map(daily.map(item=>[item.date,item]));
        const heatCell=matchMedia('(max-width: 767px)').matches?[22,22]:[28,28];
        const usageChart=chart('g-ai-heatmap',{tooltip:{formatter:p=>`${p.data[0]}：${p.data[1]} 次调用`},visualMap:{show:false,min:0,max,inRange:{color:['#eee7db','#c6c8d7',colors.indigo]}},calendar:{left:'center',range:[daily[0]?.date||new Date().toISOString().slice(0,10),daily.at(-1)?.date||new Date().toISOString().slice(0,10)],cellSize:heatCell,itemStyle:{borderWidth:2,borderColor:colors.paper},dayLabel:{color:colors.muted,fontSize:11},monthLabel:{color:colors.muted,fontSize:12}},series:[{type:'heatmap',coordinateSystem:'calendar',data:daily.map(item=>[item.date,item.calls])}]});
        usageChart.on('click',function(params){
            const item=dailyMap.get(params.data?.[0]);
            if(!item)return;
            $('g-ai-day-detail').textContent=`${item.date}：调用 ${item.calls} 次，处理 ${new Intl.NumberFormat('zh-CN').format(item.tokens||0)} token，本站追踪花费 ¥${safeNumber(item.cost_cny).toFixed(6)}。`;
        });
        $('g-ai-history-note').textContent=data.history_complete?'所选84天均处于本站用量追踪范围。':data.tracking_started?`本站从 ${String(data.tracking_started).slice(0,10)} 开始追踪；更早的调用没有可靠记录。`:'还没有产生可追踪的 AI 调用，历史数据不会被反推为零。';
    }
    const RANK_NAMES = ['童生','生员','秀才','举人','解元','贡士','进士','翰林','学士','状元'];
    let rankCatalog = [];
    let currentRank = 1;
    let pinnedRank = 1;

    // 左侧段位面板：显示与当前段位一致的“学者/官员”形象。
    function renderRankFigure(rank) {
        setRankPortrait(document.getElementById('g-rank-portrait'), rank);
    }

    function rankStateLabel(state) {
        return {reached:'已达到',current:'当前段位',next:'下一级',locked:'待解锁'}[state] || '段位档案';
    }

    function renderDossier(rank, openOnMobile) {
        const entry = rankCatalog.find(item => item.rank === rank);
        if (!entry) return;
        $('g-selected-portrait').src = entry.portrait;
        $('g-selected-portrait').alt = `${entry.name}段位代表人物`;
        $('g-selected-kicker').textContent = `LV.${entry.rank} / RANK DOSSIER`;
        $('g-selected-name').textContent = entry.name;
        $('g-selected-state').textContent = rankStateLabel(entry.state);
        $('g-selected-state').className = `rank-state-badge rank-state-badge--${entry.state}`;
        $('g-selected-positioning').textContent = [entry.cet_anchor, entry.positioning].filter(Boolean).join(' · ');
        $('g-selected-summary').textContent = entry.summary;
        $('g-selected-capability').textContent = `当该级证据完整时：${entry.representative_capability}`;
        $('g-selected-score').textContent = `${entry.target_score} 分`;
        $('g-selected-gap').textContent = entry.score_gap ? `${entry.score_gap} 分` : '分数已达到';
        $('g-thresholds').innerHTML = (entry.word_thresholds || []).map(item =>
            `<span class="threshold ${item.met ? 'is-met' : ''}">${escapeHtml(item.level)}词 ${item.current}% / ${item.required}%</span>`
        ).join('') || '<span class="threshold is-met">该级无额外词频门槛</span>';
        $('g-selected-advice-title').textContent = `${entry.state === 'current' ? '守住' : '达成'}${entry.name}`;
        const conditions = entry.unmet_conditions || [];
        $('g-selected-conditions').innerHTML = conditions.length
            ? conditions.map((text, index) => `<p><span>${index + 1}</span>${escapeHtml(text)}</p>`).join('')
            : '<p class="is-met"><span>完成</span>当前证据已满足该级的分数与词频门槛。</p>';
        document.querySelectorAll('.rank-ladder__button').forEach(button => {
            const selected = Number(button.dataset.rank) === rank;
            button.classList.toggle('is-selected', selected);
            button.setAttribute('aria-selected', String(selected));
        });
        if (openOnMobile && matchMedia('(max-width: 767px)').matches) {
            $('g-rank-dossier').classList.add('is-open');
            document.body.classList.add('rank-dossier-open');
            $('g-rank-dossier-close').focus();
        }
    }

    function closeRankDossier() {
        $('g-rank-dossier').classList.remove('is-open');
        document.body.classList.remove('rank-dossier-open');
        document.querySelector(`.rank-ladder__button[data-rank="${pinnedRank}"]`)?.focus();
    }

    // 十级长卷：悬停/聚焦预览，点击固定，手机点击打开底部档案。
    function renderLadder(level) {
        currentRank = Number(level.level.rank) || 1;
        rankCatalog = (level.rank_catalog || []).length ? level.rank_catalog : RANK_NAMES.map((name, index) => ({
            rank:index + 1,name,target_score:[0,40,48,56,64,70,76,82,88,94][index],score_gap:Math.max(0,[0,40,48,56,64,70,76,82,88,94][index] - safeNumber(level.level.total_score)),
            portrait:`/static/images/ranks/rank-${String(index + 1).padStart(2,'0')}-${['tongsheng','shengyuan','xiucai','juren','jieyuan','gongshi','jinshi','hanlin','xueshi','zhuangyuan'][index]}.png`,
            positioning:'段位档案',summary:'暂无详细段位资料。',representative_capability:'继续积累可核验学习证据。',word_thresholds:[],unmet_conditions:[],
            state:index + 1 < currentRank?'reached':index + 1===currentRank?'current':index + 1===currentRank + 1?'next':'locked',
        }));
        pinnedRank = Math.min(10, currentRank + (currentRank < 10 ? 1 : 0));
        const step = entry => `
            <button class="rank-ladder__step rank-ladder__button rank-ladder__step--${entry.state}" type="button"
                role="option" data-rank="${entry.rank}" aria-selected="false" aria-describedby="g-rank-tooltip">
                <span class="rank-ladder__node">${entry.rank}</span>
                <strong>${escapeHtml(entry.name)}</strong>
                <small>${entry.target_score}分</small>
            </button>`;
        const volumes=[rankCatalog.slice(0,5),rankCatalog.slice(5,10)];
        $('g-ladder').innerHTML = volumes.map((entries,index)=>`<section class="rank-ladder__volume" role="group" aria-label="${index===0?'入门五阶':'进阶五阶'}"><header><span>${index===0?'卷一':'卷二'}</span><strong>${entries[0]?.name||''} 至 ${entries.at(-1)?.name||''}</strong></header><div class="rank-ladder__track">${entries.map(step).join('')}</div></section>`).join('');
        const buttons = Array.from(document.querySelectorAll('.rank-ladder__button'));
        const preview = button => {
            const rank = Number(button.dataset.rank);
            const entry = rankCatalog.find(item => item.rank === rank);
            $('g-rank-tooltip').hidden = false;
            $('g-rank-tooltip').textContent = `${entry.name} · ${entry.positioning} · ${entry.target_score}分起`;
            renderDossier(rank, false);
        };
        const restore = () => {
            $('g-rank-tooltip').hidden = true;
            renderDossier(pinnedRank, false);
        };
        buttons.forEach((button, index) => {
            button.addEventListener('mouseenter', () => preview(button));
            button.addEventListener('mouseleave', restore);
            button.addEventListener('focus', () => preview(button));
            button.addEventListener('click', () => {
                pinnedRank = Number(button.dataset.rank);
                $('g-rank-tooltip').hidden = true;
                renderDossier(pinnedRank, true);
            });
            button.addEventListener('keydown', event => {
                if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
                    event.preventDefault(); buttons[(index + 1) % buttons.length].focus();
                } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
                    event.preventDefault(); buttons[(index - 1 + buttons.length) % buttons.length].focus();
                } else if (event.key === 'Escape') {
                    event.preventDefault(); pinnedRank = currentRank; restore();
                    document.querySelector(`.rank-ladder__button[data-rank="${currentRank}"]`)?.focus();
                }
            });
        });
        renderDossier(pinnedRank, false);
    }

    function contribution(level) {
        const values = dimensionKeys.map(key => safeNumber(ledgerItem(level, key).contribution));
        const maxValue = Math.max(...values, 0);
        chart('g-contribution', {grid:{left:62,right:34,top:18,bottom:30},xAxis:{type:'value',max:Math.max(5, Math.ceil(maxValue*1.15)),...axis},yAxis:{type:'category',data:dimensionKeys.map(key=>labels[key]),...axis},tooltip:{trigger:'axis',axisPointer:{type:'shadow'},formatter:params=>`${params[0].name}：贡献 ${params[0].value} 分`},series:[{type:'bar',data:values.map((value,index)=>({value,itemStyle:{color:index<5?colors.indigo:colors.red}})),barWidth:16,label:{show:true,position:'right',color:colors.muted}}]});
        $('g-contribution-text').textContent = `当前六个计分维度贡献合计 ${safeNumber(level.level.total_score)} 分；段位 V3 只使用词汇、阅读、听力、写作、记忆保持与有效投入，投入维度权重仅 6%。`;
    }
    function ledger(level) {
        const rows = dimensionKeys.map(key => {
            const item = ledgerItem(level, key);
            return `<div class="score-ledger__row"><div class="score-ledger__dimension"><strong>${item.label}</strong><span>${item.evidence.summary || '暂无可核验证据'}</span></div><span data-label="表现分">${item.score}</span><span data-label="可靠度">${item.reliability}%</span><span data-label="有效分">${item.effective_score}</span><span data-label="权重">${item.weight}%</span><strong data-label="贡献">${item.contribution}</strong></div>`;
        }).join('');
        $('g-score-ledger').innerHTML = `<div class="score-ledger__head"><span>维度与原始证据</span><span>表现分</span><span>可靠度</span><span>有效分</span><span>权重</span><span>贡献</span></div>${rows}<div class="score-ledger__total"><span>当前综合分</span><strong>${level.level.total_score}</strong></div>`;
    }
    function review(data) {
        const names=['准时率','完成度','曲线吻合','覆盖度']; const values=[data.on_time_rate,data.completion_rate,data.forget_curve,data.coverage_rate].map(safeNumber);
        chart('g-review',{grid:{left:46,right:14,top:14,bottom:30},xAxis:{type:'category',data:names,...axis},yAxis:{type:'value',max:100,...axis},series:[{type:'bar',data:values,itemStyle:{color:colors.indigo},barWidth:22}]});
        const weakest=Math.min(...values),weakestName=names[values.indexOf(weakest)];
        $('g-review-text').textContent=names.map((name,index)=>`${name} ${values[index]}%`).join('，')+`。下一步：优先改善${weakestName}。`;
    }
    function vocab(stats) {
        const names=['罕见','低频','常见','高频','核心']; const keys=['one','two','three','four','five']; const values=keys.map(key=>safeNumber(stats[key]));
        chart('g-vocab-chart',{grid:{left:46,right:14,top:14,bottom:30},xAxis:{type:'category',data:names,...axis},yAxis:{type:'value',max:100,...axis},series:[{type:'line',data:values,symbolSize:8,lineStyle:{color:colors.red,width:3},itemStyle:{color:colors.red},areaStyle:{color:'rgba(196,85,62,.08)'}}]});
        const coreIndex=names.indexOf('核心');
        $('g-vocab-text').textContent=names.map((name,index)=>`${name}词掌握 ${values[index]}%`).join('，')+`。下一步：${values[coreIndex] < 80 ? '先把核心词掌握率补到 80%' : '继续巩固高频词层'}。`;
    }
    function weekly(data) {
        const values=(data.values||[]).map(safeNumber);
        chart('g-weekly',{grid:{left:40,right:12,top:14,bottom:30},xAxis:{type:'category',data:data.days||[],...axis},yAxis:{type:'value',...axis},series:[{type:'bar',data:values,itemStyle:{color:colors.indigo},barWidth:18}]});
        const best=Math.max(...values,0),at=values.indexOf(best); $('g-weekly-text').textContent=best?`本周投入最多的是 ${(data.days||[])[at]}，共 ${best} 分钟。下一步：在空白日安排一组 10 分钟训练。`:'本周还没有学习时长记录，从今天完成一次短训练开始。';
    }
    function heatmap(data) {
        const values=data||[],max=Math.max(...values.map(item=>item[1]),1);
        chart('g-heatmap',{tooltip:{formatter:p=>`${p.data[0]}：${p.data[1]} 分钟`},visualMap:{show:false,min:0,max,inRange:{color:['#eee7db','#c6c8d7',colors.indigo]}},calendar:{range:[values[0]?.[0]||new Date().toISOString().slice(0,10),values.at(-1)?.[0]||new Date().toISOString().slice(0,10)],cellSize:[18,18],itemStyle:{borderWidth:2,borderColor:colors.paper},dayLabel:{color:colors.muted},monthLabel:{color:colors.muted}},series:[{type:'heatmap',coordinateSystem:'calendar',data:values}]});
        const active=values.filter(item=>item[1]>0); $('g-heatmap-text').textContent=active.length?`近 84 天中有 ${active.length} 天产生学习记录；84 天只是滚动可视窗口，不是强制学习周期。`:'近 84 天还没有学习时长记录。';
    }
    async function load() {
        setRegionState(root,'loading','正在整理本地学习记录…');
        try {
            const [level,summary,dashboard,health,weeklyData,usageData,aiStatus]=await Promise.all([api('/api/level/detail'),api('/api/study/summary'),api('/api/study/dashboard'),api('/api/study/review-health'),api('/api/study/weekly-rhythm'),api('/api/ai/usage?days=84'),api('/api/ai/config/status')]);
            $('g-rank').textContent=`Lv.${level.level.rank}`; $('g-name').textContent=level.level.name; $('g-confidence').textContent=level.level.confidence; $('g-score').textContent=level.level.total_score; $('g-next').textContent=level.next_level.name; $('g-gap').textContent=`${level.next_level.gap} 分`; renderRankFigure(level.level.rank); renderLadder(level);
            const thresholds=level.rank_thresholds||{1:0,2:40,3:48,4:56,5:64,6:70,7:76,8:82,9:88,10:94};
            const lower=safeNumber(thresholds[level.level.rank]),span=Math.max(1,level.next_level.target_score-lower); $('g-progress').style.width=`${Math.min(100,Math.max(0,(level.level.total_score-lower)/span*100))}%`;
            $('g-suggestions').innerHTML=(level.quantified_suggestions||[]).map(item=>`<p>${item.text}</p>`).join('')||'<p>当前没有额外建议，保持稳定学习节奏。</p>';
            $('g-capability').textContent=level.assessment.sentence; $('g-capability-evidence').textContent=`${level.assessment.scope} · ${level.assessment.evidence_level==='established'?'证据较完整':level.assessment.evidence_level==='developing'?'初步判断':'证据有限'} · 非官方等级等效声明`;
            $('g-diagnostic').hidden=!level.calibration.diagnostic_recommended;
            $('g-historical-rank').textContent=level.historical_best.name; $('g-practice').textContent=level.calibration.practice_sessions; $('g-hours').textContent=`${safeNumber(summary.hours)}h`; $('g-recent-minutes').textContent=`${level.score_ledger.investment.evidence.effective_minutes_28}m`; $('g-streak').textContent=dashboard.streak||0;
            $('g-timeline').innerHTML=(level.timeline||[]).map(item=>`<li><time>${item.date||'日期未记录'} · 算法 ${item.version||'1.0'}</time><strong>${item.name}</strong><span>Lv.${item.rank} · ${item.score} 分${item.reason?` · ${item.reason}`:''}</span></li>`).join('')||'<li>还没有段位变化记录。</li>';
            radar(level,summary,dashboard); achievements(summary); contribution(level); ledger(level); aiUsage(usageData,null); review(health); vocab(dashboard.freq_stats||{}); weekly(weeklyData); heatmap(dashboard.heatmap||[]); setRegionState(root,'ready');
            if(aiStatus.configured){
                $('g-ai-balance').textContent='查询中';
                api('/api/ai/balance').then(balanceData=>{
                    const balances=balanceData?.balances||[];
                    $('g-ai-balance').textContent=balances.length?balances.map(item=>`${item.currency==='CNY'?'¥':'$'}${item.total}`).join(' / '):'暂无余额数据';
                }).catch(()=>{$('g-ai-balance').textContent='查询失败';});
            }
        } catch(error) { setRegionState(root,'error',`段位数据加载失败：${error.message||'请检查本地服务后重试。'}`); }
    }
    $('growth-refresh').addEventListener('click',async()=>{try{await api('/api/level/recalculate',{method:'POST',body:'{}'});charts.splice(0).forEach(instance=>instance.dispose());await load();showToast('段位已按最新证据重新计算。','success');}catch(error){showToast(error.message||'重新计算失败。','error');}});
    $('g-rank-dossier-close').addEventListener('click', closeRankDossier);
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && $('g-rank-dossier').classList.contains('is-open')) closeRankDossier();
    });
    window.addEventListener('resize',()=>charts.forEach(instance=>instance.resize()));
    load();
})();

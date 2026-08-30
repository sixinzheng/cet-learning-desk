(async function(){
    const root=document.getElementById('learn-hub');
    if(!root)return;
    const $=id=>document.getElementById(id);
    const radios=()=>document.querySelectorAll('input[name="training-difficulty"]');

    // 今日专项进度 + 当前节奏 + 专项目录计数
    try{
        const [d,s]=await Promise.all([api('/api/study/dashboard'),api('/api/study/summary')]);
        ['reading','listening','cloze','writing'].forEach(k=>{$('lm-'+k).textContent=d.today_modules[k]||0;});
        const rec=d.recommend||{module:'reading',label:'阅读训练',href:'/reading',today_done:0};
        const todayCount=d.today_modules?.[rec.module]||0;
        $('learn-plan-copy').textContent=todayCount>0
            ?`最该补的是 ${rec.label}——今天已练 ${todayCount} 次，保持住就好。`
            :`最该补的是 ${rec.label}——今天还没有练过。`;
        const btn=$('learn-recommend-btn');
        btn.textContent=`开始${rec.label}`;
        btn.href=rec.href;
        const workspace=document.querySelector(`[data-workspace="${rec.module}"]`);
        if(workspace){workspace.classList.add('is-recommended');const action=document.createElement('span');action.className='training-recommend-action';action.textContent='今日首选 · 立即开始';workspace.appendChild(action);}
        $('learn-streak').textContent=d.streak||0;
        $('learn-hours').textContent=s.hours||0;
        $('learn-notes').textContent=s.notes||0;
        ['reading','listening','cloze','writing'].forEach(k=>$('count-'+k).textContent=`${s[k]||0} 次记录`);
        setRegionState(root,'ready');
    }catch(_){setRegionState(root,'error','今日计划加载失败，请刷新页面重试。')}

    // 训练难度：读取当前设置
    try{
        const data=await api('/api/study/difficulty-setting');
        radios().forEach(r=>r.checked=String(r.value)===String(data.difficulty||''));
        const summary=$('learn-difficulty-summary');
        summary.textContent=data.difficulty?`当前按「${data.label}」档位出题。`:'当前未设置，按全部难度出题。';
        $('difficulty-hint').textContent=data.difficulty?`已保存为「${data.label}」，专项将按此难度出题。`:'当前未设置，按全部难度出题。';
    }catch(_){
        $('learn-difficulty-summary').textContent='难度设置读取失败，请刷新重试。';
    }

    // 保存难度
    $('difficulty-save').addEventListener('click',async()=>{
        const checked=document.querySelector('input[name="training-difficulty"]:checked');
        if(!checked){showToast('请先选择一个难度档位。','warning');return;}
        try{
            const data=await api('/api/study/difficulty-setting',{method:'PUT',body:JSON.stringify({difficulty:Number(checked.value)})});
            $('difficulty-hint').textContent=`已保存为「${data.label}」，阅读、听力、单词专练将按此难度出题，写作按对应标准批改。`;
            const summary=$('learn-difficulty-summary');
            if(summary)summary.textContent=`当前按「${data.label}」档位出题。`;
            showToast(`训练难度已保存为「${data.label}」。`,'success');
        }catch(error){showToast(error.message||'保存失败，请重试。','error');}
    });
})();

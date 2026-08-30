function levelApp() {
    return {
        levelName: '--',
        icon: '',
        score: 0,
        confidence: 0,
        confLevel: '',
        confColor: '',
        gap: 0,
        nextName: '',
        currentRank: 1,
        rangeLow: '',
        rangeHigh: '',
        thresholds: [],
        suggestions: [],
        timeline: [],

        async init() {
            try {
                const data = await api('/api/level/detail');
                const lv = data.level;
                this.levelName = lv.name;
                this.icon = lv.icon;
                this.score = lv.total_score;
                this.confidence = lv.confidence;
                this.currentRank = lv.rank;
                this.gap = data.next_level.gap;
                this.nextName = data.next_level.name;
                this.thresholds = data.thresholds || [];
                this.suggestions = data.suggestions || [];
                this.timeline = data.timeline || [];

                // 浮动区间
                const margin = Math.round((100 - this.confidence) * 0.4);
                const rankNames = ['','童生','生员','秀才','举人','解元','贡士','进士','翰林','学士','状元'];
                this.rangeLow = rankNames[Math.max(1, this.currentRank - Math.floor(margin/10))] || '--';
                this.rangeHigh = rankNames[Math.min(10, this.currentRank + Math.floor(margin/10))] || '--';

                // 可信度等级
                if (this.confidence < 40) { this.confLevel = '仅供参考'; this.confColor = 'text-red-400'; }
                else if (this.confidence < 70) { this.confLevel = '较为可信'; this.confColor = 'text-yellow-500'; }
                else if (this.confidence < 90) { this.confLevel = '可信'; this.confColor = 'text-green-500'; }
                else { this.confLevel = '高度可靠'; this.confColor = 'text-indigo-600'; }

                // 雷达图
                setTimeout(() => this.renderRadar(data.scores), 300);
            } catch (e) {
                showToast('段位数据加载失败', 'error');
            }
        },

        renderRadar(scores) {
            const el = document.getElementById('radar-chart');
            if (!el) return;
            const chart = echarts.init(el);
            chart.setOption({
                radar: {
                    indicator: [
                        {name:'词汇',max:100},{name:'阅读',max:100},{name:'听力',max:100},
                        {name:'写作',max:100},{name:'语法',max:100},{name:'坚持',max:100},
                    ],
                    shape:'circle', center:['50%','55%'], radius:'65%',
                    axisName:{fontSize:10},
                },
                series: [{
                    type:'radar',
                    data:[{value:[scores.vocabulary,scores.reading,scores.listening,
                                  scores.writing,scores.grammar,scores.persistence],
                           areaStyle:{color:'rgba(79,70,229,0.15)'},
                           lineStyle:{color:'#4f46e5',width:2},
                           itemStyle:{color:'#4f46e5'}}],
                }],
            });
        },

        async recalculate() {
            try {
                const resp = await api('/api/level/recalculate', {method:'POST'});
                showToast('段位已刷新', 'success');
                this.init();
            } catch (e) {
                showToast('刷新失败', 'error');
            }
        },
    };
}

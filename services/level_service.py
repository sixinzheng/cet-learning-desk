"""科举段位 V3：六维真实表现、证据可靠度与 CET 参考画像。"""

import json
import math
from collections import OrderedDict
from datetime import date, datetime, timedelta

from database import get_db


ALGORITHM_VERSION = '3.0'
LEVEL_NAMES = ['', '童生', '生员', '秀才', '举人', '解元', '贡士', '进士', '翰林', '学士', '状元']
LEVEL_ICONS = ['', '(童)', '(生)', '(秀)', '(举)', '(解)', '(贡)', '(进)', '(翰)', '(学)', '(状)']

LEVEL_SCORE_THRESHOLDS = {1: 0, 2: 40, 3: 48, 4: 56, 5: 64, 6: 70, 7: 76, 8: 82, 9: 88, 10: 94}

LEVEL_PROFILES = {
    1: {'positioning': '四级基础尚未形成', 'cet_anchor': '四级基础尚未形成',
        'summary': '正在建立高频词、基础句式和短信息辨识能力。'},
    2: {'positioning': '四级基础目标', 'cet_anchor': '四级 425 参考水平',
        'summary': '能处理四级基础材料，抓住明确主旨和关键细节。'},
    3: {'positioning': '四级常规应用', 'cet_anchor': '四级约 460 参考水平',
        'summary': '能较稳定完成常规四级阅读、听力和基础写作任务。'},
    4: {'positioning': '四级中高阶', 'cet_anchor': '四级约 500 参考水平',
        'summary': '能理解信息较密集的四级材料，并完成结构清楚的表达。'},
    5: {'positioning': '四级优秀', 'cet_anchor': '四级约 550 参考水平',
        'summary': '四级表现优秀，可处理一般报道、说明和入门科普。'},
    6: {'positioning': '六级基础应用', 'cet_anchor': '六级 425 参考水平',
        'summary': '进入六级应用阶段，能够理解更长、更复杂的论述。'},
    7: {'positioning': '六级稳定应用', 'cet_anchor': '六级约 475 参考水平',
        'summary': '能比较观点、识别隐含信息并完成较完整论证。'},
    8: {'positioning': '六级中高阶', 'cet_anchor': '六级约 530 参考水平',
        'summary': '能稳定处理复杂报道、课程材料和中高难度写作。'},
    9: {'positioning': '六级十分优秀', 'cet_anchor': '六级约 580 参考水平',
        'summary': '六级表现十分优秀，可独立处理高信息密度材料。'},
    10: {'positioning': '六级高阶驾驭', 'cet_anchor': '六级约 620 以上参考水平',
         'summary': '能深入理解复杂英文材料并进行准确、成熟的书面表达。'},
}

LEVEL_PORTRAITS = {
    1: 'rank-01-tongsheng.png', 2: 'rank-02-shengyuan.png',
    3: 'rank-03-xiucai.png', 4: 'rank-04-juren.png',
    5: 'rank-05-jieyuan.png', 6: 'rank-06-gongshi.png',
    7: 'rank-07-jinshi.png', 8: 'rank-08-hanlin.png',
    9: 'rank-09-xueshi.png', 10: 'rank-10-zhuangyuan.png',
}

LEVEL_WEIGHTS = OrderedDict((
    ('vocabulary', 26), ('reading', 24), ('listening', 21), ('writing', 18),
    ('retention', 5), ('investment', 6),
))
EVIDENCE_TARGETS = {
    'reading': 30, 'listening': 40, 'writing': 5,
    'retention': 30,
}
DIMENSION_LABELS = {
    'vocabulary': '词汇运用', 'reading': '阅读理解', 'listening': '听力理解',
    'writing': '写作表达', 'retention': '记忆保持', 'investment': '有效投入',
}

# 晋升词汇门槛保持兼容；综合分达到后仍需通过对应词频层门槛。
LEVEL_WORD_THRESHOLDS = {
    2:  {'five':20, 'four':0,  'three':0,  'two':0,  'one':0},
    3:  {'five':50, 'four':25, 'three':0,  'two':0,  'one':0},
    4:  {'five':75, 'four':50, 'three':25, 'two':0,  'one':0},
    5:  {'five':85, 'four':70, 'three':45, 'two':0,  'one':0},
    6:  {'five':92, 'four':80, 'three':60, 'two':30, 'one':0},
    7:  {'five':96, 'four':88, 'three':72, 'two':50, 'one':0},
    8:  {'five':98, 'four':93, 'three':82, 'two':65, 'one':35},
    9:  {'five':100,'four':97, 'three':90, 'two':78, 'one':55},
    10: {'five':100,'four':100,'three':96, 'two':88, 'one':72},
}


# 十个段位 × 五个可核验任务方向。V3 不推断口语、对话或发音能力。
CAPABILITY_TEMPLATES = {
    1: {
        'exam': '你正在建立完成四级基础任务所需的第一批词汇与短信息证据。',
        'listening': '你已经能从慢速、清晰的材料中辨认少量学过的高频词。',
        'life': '你已经能从常见标识和简短提示中辨认少量学过的信息。',
        'reading': '你已经能从短标识和简单句中认出学过的高频信息。',
        'study': '你已经能跟随非常简短的英文学习指令完成基础任务。',
        'writing': '你已经能用学过的词写出少量完整、可理解的简单句。',
    },
    2: {
        'exam': '你的本站证据开始达到四级 425 基础目标的参考范围。',
        'listening': '你能够抓住四级基础听力中明确出现的人物、地点和关键动作。',
        'life': '你已经能看懂车站、酒店和餐厅里最常见的英文文字提示。',
        'reading': '你已经能理解围绕熟悉事物展开的简短英语说明。',
        'study': '你已经能读懂简单作业要求，并抓住其中的核心动作。',
        'writing': '你已经能填写基础英文信息，并写出简短的个人介绍。',
    },
    3: {
        'exam': '你能够较稳定地处理常规四级基础题目，但复杂信息仍需要更多证据。',
        'listening': '你能够从常规四级短材料中抓住明确主旨与关键细节。',
        'life': '你可以理解行程、菜单和住宿说明中的常见书面信息。',
        'reading': '你已经能独立读懂主题明确、句式简单的生活类短文。',
        'study': '你已经能理解一段简短课程说明，并找出明确要求。',
        'writing': '你已经能围绕熟悉话题写出意思连贯的简短段落。',
    },
    4: {
        'exam': '你能够应对信息密度更高的四级材料，并维持较稳定的综合表现。',
        'listening': '你可以跟随结构清楚的四级听力材料，区分主要信息与补充细节。',
        'life': '你可以独立理解常见公共服务说明、行程变更和书面指引。',
        'reading': '你可以理解结构清晰的英语新闻短讯和公共说明。',
        'study': '你可以抓住一般英文学习材料的主旨和关键步骤。',
        'writing': '你可以写出结构清楚、能够完成基本沟通目的的英文短文。',
    },
    5: {
        'exam': '你的四级相关能力已达到优秀参考区间，并开始具备六级材料的基础。',
        'listening': '你能够理解一般报道式听力的主要逻辑，并定位多数关键事实。',
        'life': '你能够理解较完整的公共说明、产品信息和服务条款要点。',
        'reading': '你可以独立理解一般新闻、产品说明和入门科普文章的主旨。',
        'study': '你可以阅读普通英文课程资料并整理其中的关键信息。',
        'writing': '你可以就熟悉主题写出观点明确、段落完整的英语文章。',
    },
    6: {
        'exam': '你的本站证据进入六级 425 基础目标的参考范围。',
        'listening': '你能够跟随较长的六级基础听力材料，提取观点、原因和结果。',
        'life': '你能够从较长的英文指南和政策说明中提取需要执行的信息。',
        'reading': '你可以独立理解大多数一般英文报道和中等难度科普内容。',
        'study': '你可以跟随英文课程材料学习，并概括主要观点和证据。',
        'writing': '你可以写出结构完整、论点清楚并有基本论证的英语短文。',
    },
    7: {
        'exam': '你能稳定处理六级常规材料，并识别部分隐含观点与同义替换。',
        'listening': '你能够比较听力材料中的不同观点，并判断说话者的基本态度。',
        'life': '你能够独立理解较复杂的课程通知、服务规则和办事材料。',
        'reading': '你现在可以独立理解语言较直接的英文科学与社会类刊物文章。',
        'study': '你可以理解较长的英文学习材料，并比较其中不同观点。',
        'writing': '你可以写出论证较充分、衔接自然的英语议论性文章。',
    },
    8: {
        'exam': '你能稳定完成六级中高难度任务，并整合多处证据形成判断。',
        'listening': '你能跟随结构较复杂的报道和讲座片段，理解论证关系与态度。',
        'life': '你能够处理高信息密度的课程、产品和公共事务书面材料。',
        'reading': '你可以理解结构复杂的一般英文报告和较深入的科普文章。',
        'study': '你可以独立处理较复杂的英文课程资料并形成系统笔记。',
        'writing': '你可以针对复杂主题写出层次清晰、论证连贯的英语文章。',
    },
    9: {
        'exam': '你的六级相关能力进入十分优秀的参考区间，复杂任务表现较稳定。',
        'listening': '你可以理解高信息密度听力中的观点变化、隐含关系和关键例证。',
        'life': '你能够独立比较多份英文规则、报告或说明并形成可靠结论。',
        'reading': '你可以独立理解多数专业入门文章、评论和长篇英文报道。',
        'study': '你可以综合多份英文材料，提炼观点并判断论证差异。',
        'writing': '你可以写出语言准确、结构成熟并能适应不同目的的英文文本。',
    },
    10: {
        'exam': '你的本站证据达到六级高阶参考区间，能稳定处理综合性复杂任务。',
        'listening': '你能够深入理解复杂听力材料的结构、立场、证据与细微态度。',
        'life': '你能够独立处理复杂英文政策、专业说明和跨来源信息。',
        'reading': '你可以独立处理语言密集、观点细腻的学术或专业英文材料。',
        'study': '你可以批判性整合复杂英文资料，并用英语重构核心论证。',
        'writing': '你可以针对复杂受众写出精确、自然且具有说服力的英语文本。',
    },
}


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))


def _age_weight(completed_at, origin='practice'):
    try:
        stamp = datetime.fromisoformat(completed_at)
        age = max(0, (datetime.now() - stamp).days)
    except (TypeError, ValueError):
        age = 0
    weight = max(.3, .5 ** (age / 60))
    if origin == 'diagnostic':
        weight *= max(.25, .5 ** (age / 30)) * .6
    return weight


def _vocabulary_dimension(db):
    rows = db.execute('''
        SELECT w.frequency, COALESCE(uw.status, '陌生') AS status
        FROM words w LEFT JOIN user_words uw ON uw.word_id=w.id
    ''').fetchall()
    status_factor = {'陌生': 0, '模糊': .35, '巩固': .5, '掌握': .75, '熟记': 1}
    frequency_weight = {1: .5, 2: .8, 3: 1, 4: 1.3, 5: 1.6}
    denominator = sum(frequency_weight.get(row['frequency'], 1) for row in rows)
    numerator = sum(
        frequency_weight.get(row['frequency'], 1) * status_factor.get(row['status'], 0)
        for row in rows
    )
    performance = round(numerator / denominator * 100, 1) if denominator else 0
    studied = sum(1 for row in rows if row['status'] != '陌生')
    target = min(100, len(rows)) if rows else 100
    reliability = round(_clamp(studied / max(1, target), 0, 1), 3)
    mastered = sum(1 for row in rows if row['status'] in ('巩固', '掌握', '熟记'))
    # 单词专练（选词填空）表现并入词汇运用：权重三成，并提升该维度可信度
    cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
    cloze_rows = db.execute('''
        SELECT raw_score, total_count, completed_at FROM practice_sessions
        WHERE module='vocabulary' AND completed_at>=? ORDER BY completed_at DESC, id DESC LIMIT 20
    ''', (cutoff,)).fetchall()
    cloze_perf = 0.0
    cloze_sessions = len(cloze_rows)
    if cloze_rows:
        weighted = 0.0
        weight_sum = 0.0
        for row in cloze_rows:
            sample_weight = max(1, row['total_count'])
            weight = sample_weight * _age_weight(row['completed_at'], 'practice')
            weighted += row['raw_score'] * weight
            weight_sum += weight
        cloze_perf = round(weighted / max(1, weight_sum), 1)
    if cloze_perf:
        performance = round(performance * 0.7 + cloze_perf * 0.3, 1)
        reliability = round(_clamp(reliability + 0.15, 0, 1), 3)
    summary = f'已学习 {studied} 词，稳定掌握 {mastered} 词'
    if cloze_sessions:
        summary += f'；单词运用 {cloze_perf} 分'
    return performance, reliability, {
        'studied_words': studied, 'mastered_words': mastered, 'total_words': len(rows),
        'cloze_sessions': cloze_sessions, 'cloze_performance': cloze_perf,
        'summary': summary,
    }


def _practice_dimension(db, module):
    cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
    rows = db.execute('''
        SELECT * FROM practice_sessions
        WHERE module=? AND completed_at>=?
        ORDER BY completed_at DESC, id DESC LIMIT 30
    ''', (module, cutoff)).fetchall()
    if not rows:
        return 0.0, 0.0, {'sessions': 0, 'samples': 0, 'max_difficulty': 0, 'summary': '暂无可核验表现'}
    weighted_total = 0
    weight_sum = 0
    samples = 0
    max_difficulty = 0
    for row in rows:
        sample_weight = max(1, row['total_count'])
        decay = _age_weight(row['completed_at'], row['origin'])
        weight = sample_weight * decay
        weighted_total += row['raw_score'] * weight
        weight_sum += weight
        samples += max(1, row['total_count'])
        max_difficulty = max(max_difficulty, row['difficulty'])
    performance = round(weighted_total / max(1, weight_sum), 1)
    target = EVIDENCE_TARGETS[module]
    reliability = round(_clamp(samples / target, 0, 1), 3)
    return performance, reliability, {
        'sessions': len(rows), 'samples': samples, 'max_difficulty': max_difficulty,
        'summary': f'{len(rows)} 轮 / {samples} 个有效样本，最高难度 {max_difficulty}',
    }


def _retention_dimension(db):
    row = db.execute('''
        SELECT COALESCE(SUM(review_count),0) AS reviews,
               COALESCE(SUM(correct_count),0) AS correct,
               COALESCE(AVG(CASE WHEN review_count>0 THEN ebbinghaus_stage END),0) AS stage,
               COALESCE(SUM(CASE WHEN wrong_streak>0 THEN 1 ELSE 0 END),0) AS forgetting,
               COALESCE(SUM(CASE WHEN review_count>0 THEN 1 ELSE 0 END),0) AS reviewed_words
        FROM user_words
    ''').fetchone()
    reviews = row['reviews'] or 0
    if not reviews:
        return 0.0, 0.0, {'reviews': 0, 'summary': '尚未形成复习样本'}
    accuracy = _clamp((row['correct'] or 0) / reviews * 100)
    maturity = _clamp((row['stage'] or 0) / 5 * 100)
    forgetting_control = 100 - _clamp((row['forgetting'] or 0) / max(1, row['reviewed_words']) * 100)
    performance = round(accuracy * .5 + maturity * .3 + forgetting_control * .2, 1)
    reliability = round(_clamp(reviews / EVIDENCE_TARGETS['retention'], 0, 1), 3)
    return performance, reliability, {
        'reviews': reviews, 'accuracy': round(accuracy), 'average_stage': round(row['stage'] or 0, 1),
        'summary': f'{reviews} 次复习，正确率 {round(accuracy)}%',
    }


def _investment_dimension(db):
    cutoff = (date.today() - timedelta(days=27)).isoformat()
    rows = db.execute('''
        SELECT study_date, MIN(120, COALESCE(total_minutes,0)) AS minutes
        FROM study_logs WHERE study_date>=? ORDER BY study_date
    ''', (cutoff,)).fetchall()
    active = [row for row in rows if row['minutes'] > 0]
    minutes = sum(row['minutes'] for row in active)
    streak = 0
    longest = 0
    previous = None
    for row in active:
        current = date.fromisoformat(row['study_date'])
        streak = streak + 1 if previous and current == previous + timedelta(days=1) else 1
        longest = max(longest, streak)
        previous = current
    performance = round(
        _clamp(len(active) / 20, 0, 1) * 45
        + _clamp(minutes / 600, 0, 1) * 35
        + _clamp(longest / 7, 0, 1) * 20,
        1,
    )
    reliability = round(_clamp((len(active) + minutes / 120) / 12, 0, 1), 3)
    lifetime = db.execute("SELECT COALESCE(SUM(total_minutes),0) AS m FROM study_logs").fetchone()['m']
    return performance, reliability, {
        'active_days_28': len(active), 'effective_minutes_28': minutes,
        'longest_streak_28': longest, 'lifetime_minutes': lifetime,
        'summary': f'近28天有效学习 {len(active)} 天 / {minutes} 分钟',
    }


def build_score_ledger(db):
    raw = OrderedDict()
    raw['vocabulary'] = _vocabulary_dimension(db)
    for module in ('reading', 'listening', 'writing'):
        raw[module] = _practice_dimension(db, module)
    raw['retention'] = _retention_dimension(db)
    raw['investment'] = _investment_dimension(db)
    ledger = OrderedDict()
    for key, weight in LEVEL_WEIGHTS.items():
        performance, reliability, evidence = raw[key]
        effective = round(performance * reliability, 1)
        contribution = round(effective * weight / 100, 2)
        ledger[key] = {
            'label': DIMENSION_LABELS[key], 'score': round(performance, 1),
            'reliability': round(reliability * 100), 'effective_score': effective,
            'weight': weight, 'contribution': contribution, 'evidence': evidence,
        }
    return ledger


def _check_word_thresholds(db, rank):
    if rank not in LEVEL_WORD_THRESHOLDS:
        return True
    thresholds = LEVEL_WORD_THRESHOLDS[rank]
    for frequency, key in ((5,'five'),(4,'four'),(3,'three'),(2,'two'),(1,'one')):
        required = thresholds[key]
        if not required:
            continue
        total = db.execute("SELECT COUNT(*) AS c FROM words WHERE frequency=?", (frequency,)).fetchone()['c']
        if not total:
            continue
        mastered = db.execute('''
            SELECT COUNT(*) AS c FROM user_words uw JOIN words w ON w.id=uw.word_id
            WHERE w.frequency=? AND uw.status IN ('巩固','掌握','熟记')
        ''', (frequency,)).fetchone()['c']
        if round(mastered / total * 100) < required:
            return False
    return True


def _rank_for_score(db, score):
    rank = 1
    for candidate, threshold in LEVEL_SCORE_THRESHOLDS.items():
        if score >= threshold:
            rank = candidate
    while rank > 1 and not _check_word_thresholds(db, rank):
        rank -= 1
    return rank


def _confidence(db, ledger):
    ability_keys = [key for key in ledger if key != 'investment']
    evidence = sum(ledger[key]['reliability'] for key in ability_keys) / len(ability_keys)
    cutoff = (date.today() - timedelta(days=13)).isoformat()
    recent = db.execute(
        "SELECT COUNT(*) AS c FROM study_logs WHERE study_date>=? AND total_minutes>0", (cutoff,)
    ).fetchone()['c']
    legacy = db.execute('''
        SELECT COALESCE(SUM(reading_count+listening_count+writing_count+grammar_count),0) AS c
        FROM study_logs
    ''').fetchone()['c']
    return round(min(99, evidence * .8 + min(15, recent / 14 * 15) + min(5, legacy / 20 * 5)))


def _capability_assessment(rank, ledger):
    candidates = []
    def eligible(family, keys, min_score=45, min_reliability=25, min_difficulty=1):
        items = [ledger[key] for key in keys]
        if any(item['score'] < min_score or item['reliability'] < min_reliability for item in items):
            return
        difficulties = [item['evidence'].get('max_difficulty', 6) for item in items if 'max_difficulty' in item['evidence']]
        if difficulties and min(difficulties) < min_difficulty:
            return
        strength = sum(item['effective_score'] for item in items) / len(items)
        candidates.append((strength, family, keys))

    required_difficulty = max(1, min(6, rank - 1))
    eligible('reading', ['reading', 'vocabulary'], min_difficulty=required_difficulty)
    eligible('listening', ['listening', 'vocabulary'], min_difficulty=max(1, min(6, rank - 2)))
    eligible('writing', ['writing', 'vocabulary'])
    eligible('study', ['reading', 'listening', 'vocabulary'], min_difficulty=max(1, min(6, rank - 2)))
    eligible('exam', ['reading', 'listening', 'writing', 'vocabulary'], min_score=48,
             min_reliability=35, min_difficulty=max(1, min(6, rank - 2)))
    eligible('life', ['reading', 'vocabulary'], min_score=50, min_reliability=35,
             min_difficulty=max(1, min(6, rank - 2)))
    if candidates:
        _, family, keys = max(candidates, key=lambda item: (item[0], item[1]))
        return {
            'sentence': CAPABILITY_TEMPLATES[rank][family], 'family': family,
            'evidence_level': 'established' if min(ledger[key]['reliability'] for key in keys) >= 70 else 'developing',
            'scope': '基于本站学习记录', 'evidence_dimensions': keys,
        }

    vocabulary = ledger['vocabulary']['evidence']
    mastered = vocabulary.get('mastered_words', 0)
    if mastered:
        sentence = '你已经能够稳定辨认一小批学过的高频词，这是把英语真正用于现实任务的第一块基石；由于证据有限，暂不能判断是否达到四级或六级水平。'
    else:
        sentence = '你正在建立第一批可稳定识别的英语信息；完成几轮真实训练后，系统会给出更具体的现实能力判断，目前暂不能判断是否达到四级或六级水平。'
    return {
        'sentence': sentence, 'family': 'foundation', 'evidence_level': 'limited',
        'scope': '基于本站学习记录', 'evidence_dimensions': ['vocabulary'],
    }


def evaluate_level(db):
    ledger = build_score_ledger(db)
    total = round(sum(item['contribution'] for item in ledger.values()), 1)
    rank = _rank_for_score(db, total)
    confidence = _confidence(db, ledger)
    return {
        'name': LEVEL_NAMES[rank], 'rank': rank, 'total_score': total,
        'confidence': confidence, 'ledger': ledger,
        'assessment': _capability_assessment(rank, ledger),
    }


def calculate_level(reason='recalculate'):
    """全量重算并写入历史快照；允许当前段位升降。"""
    db = get_db()
    result = evaluate_level(db)
    ledger = result['ledger']
    previous = db.execute(
        'SELECT level_rank, algorithm_version FROM user_level ORDER BY id DESC LIMIT 1'
    ).fetchone()
    is_manual_snapshot = reason in ('diagnostic', 'manual_recalculate', 'algorithm_upgrade')
    same_rank = previous and previous['level_rank'] == result['rank']
    same_version = previous and previous['algorithm_version'] == ALGORITHM_VERSION
    if same_rank and same_version and not is_manual_snapshot:
        db.close()
        return {key: result[key] for key in ('name', 'rank', 'total_score', 'confidence')}
    if not same_version:
        reason = 'algorithm_upgrade'
    elif previous and previous['level_rank'] != result['rank']:
        reason = 'rank_up' if result['rank'] > previous['level_rank'] else 'rank_down'
    db.execute('''
        INSERT INTO user_level
        (level_name, level_rank, total_score, vocabulary_score, reading_score,
         listening_score, writing_score, retention_score, investment_score,
         confidence, algorithm_version, change_reason, updated_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,date('now'))
    ''', (
        result['name'], result['rank'], result['total_score'],
        ledger['vocabulary']['score'], ledger['reading']['score'], ledger['listening']['score'],
        ledger['writing']['score'], ledger['retention']['score'], ledger['investment']['score'],
        result['confidence'], ALGORITHM_VERSION, reason,
    ))
    db.commit(); db.close()
    return {key: result[key] for key in ('name', 'rank', 'total_score', 'confidence')}


def get_level_summary():
    db = get_db()
    result = evaluate_level(db)
    next_rank = min(result['rank'] + 1, 10)
    next_boundary = LEVEL_SCORE_THRESHOLDS[next_rank] if result['rank'] < 10 else 100
    db.close()
    return {
        'name': result['name'], 'rank': result['rank'],
        'icon': LEVEL_ICONS[result['rank']], 'total_score': result['total_score'],
        'confidence': result['confidence'],
        'gap': round(max(0, next_boundary - result['total_score']), 1),
    }

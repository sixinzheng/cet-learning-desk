from flask import Blueprint, jsonify

from database import get_db
from services.level_service import (
    ALGORITHM_VERSION,
    CAPABILITY_TEMPLATES,
    DIMENSION_LABELS,
    EVIDENCE_TARGETS,
    LEVEL_ICONS,
    LEVEL_NAMES,
    LEVEL_PORTRAITS,
    LEVEL_PROFILES,
    LEVEL_SCORE_THRESHOLDS,
    LEVEL_WORD_THRESHOLDS,
    calculate_level,
    evaluate_level,
)

bp = Blueprint('level', __name__)


def _next_level(result):
    rank = result['rank']
    next_rank = min(rank + 1, 10)
    boundary = LEVEL_SCORE_THRESHOLDS[next_rank] if rank < 10 else 100
    return {
        'name': LEVEL_NAMES[next_rank], 'rank': next_rank,
        'target_score': boundary,
        'gap': round(max(0, boundary - result['total_score']), 1),
    }


@bp.get('/detail')
def detail():
    db = get_db()
    result = evaluate_level(db)
    rank = result['rank']
    ledger = result['ledger']
    thresholds = _get_threshold_status(db, rank)
    rank_catalog = _build_rank_catalog(db, result)
    quantified = _generate_quantified_suggestions(ledger, thresholds)
    best_row = db.execute('''
        SELECT level_name, level_rank, total_score, updated_date
        FROM user_level ORDER BY level_rank DESC, total_score DESC, id DESC LIMIT 1
    ''').fetchone()
    timeline = db.execute('''
        SELECT level_name, level_rank, total_score, confidence, updated_date,
               COALESCE(change_reason,'') AS change_reason, COALESCE(algorithm_version,'1.0') AS version
        FROM user_level ORDER BY id DESC LIMIT 30
    ''').fetchall()
    total_sessions = db.execute("SELECT COUNT(*) AS c FROM practice_sessions").fetchone()['c']
    legacy = db.execute('''
        SELECT COUNT(CASE WHEN total_minutes>0 OR new_words_count>0 OR review_words_count>0 THEN 1 END) AS active_days,
               COALESCE(SUM(total_minutes),0) AS total_minutes,
               COALESCE(SUM(reading_count),0) AS reading_count,
               COALESCE(SUM(listening_count),0) AS listening_count,
               COALESCE(SUM(writing_count),0) AS writing_count,
               COALESCE(SUM(grammar_count),0) AS grammar_count
        FROM study_logs
    ''').fetchone()
    word_evidence = db.execute('''
        SELECT COUNT(CASE WHEN status IN ('巩固','掌握','熟记') THEN 1 END) AS mastered_words,
               COALESCE(SUM(review_count),0) AS review_count FROM user_words
    ''').fetchone()
    db.close()

    historical_best = {
        'name': best_row['level_name'] if best_row else result['name'],
        'rank': best_row['level_rank'] if best_row else rank,
        'score': round(best_row['total_score'], 1) if best_row else result['total_score'],
        'date': best_row['updated_date'] if best_row else None,
    }
    scores = {key: item['score'] for key, item in ledger.items()}
    scores['persistence'] = scores['investment']
    return jsonify({
        'level': {
            'name': result['name'], 'rank': rank, 'icon': LEVEL_ICONS[rank],
            'total_score': result['total_score'], 'confidence': result['confidence'],
        },
        'scores': scores,
        'score_ledger': ledger,
        'next_level': _next_level(result),
        'historical_best': historical_best,
        'thresholds': thresholds,
        'suggestions': [item['text'] for item in quantified],
        'quantified_suggestions': quantified,
        'assessment': {
            **result['assessment'],
            'basis': {
                'active_days': legacy['active_days'], 'total_minutes': legacy['total_minutes'],
                'mastered_words': word_evidence['mastered_words'], 'review_count': word_evidence['review_count'],
                'reading_count': legacy['reading_count'], 'listening_count': legacy['listening_count'],
                'writing_count': legacy['writing_count'],
                'covered_dimensions': sum(1 for item in ledger.values() if item['reliability'] > 0),
            },
            'detailed_evidence': {key: item['evidence'] for key, item in ledger.items()},
        },
        'timeline': [{
            'name': row['level_name'], 'rank': row['level_rank'],
            'score': round(row['total_score'], 1), 'confidence': round(row['confidence']),
            'date': row['updated_date'], 'reason': row['change_reason'], 'version': row['version'],
        } for row in reversed(timeline)],
        'algorithm_version': ALGORITHM_VERSION,
        'rank_thresholds': LEVEL_SCORE_THRESHOLDS,
        'reference_anchor': LEVEL_PROFILES[rank]['cet_anchor'],
        'dimensions': [{
            'key': key, 'label': item['label'], 'weight': item['weight'],
            'score': item['score'], 'reliability': item['reliability'],
            'effective_score': item['effective_score'], 'contribution': item['contribution'],
        } for key, item in ledger.items()],
        'evidence_constraints': {
            'official_score_prediction': False,
            'speaking_inference': False,
            'grammar_dimension': False,
            'note': '分数仅是本站学习证据的能力参考，不预测真实 CET 成绩。',
        },
        'calibration': {
            'status': 'ready' if result['confidence'] >= 60 else 'collecting',
            'practice_sessions': total_sessions,
            'diagnostic_recommended': result['confidence'] < 45,
        },
        'rank_catalog': rank_catalog,
    })


@bp.post('/recalculate')
def recalculate():
    return jsonify(calculate_level(reason='manual_recalculate'))


def _threshold_status_for_rank(db, target_rank):
    required = LEVEL_WORD_THRESHOLDS.get(target_rank, {})
    result = []
    for frequency, key in ((5,'five'),(4,'four'),(3,'three'),(2,'two'),(1,'one')):
        target = required.get(key, 0)
        if not target:
            continue
        total = db.execute("SELECT COUNT(*) AS c FROM words WHERE frequency=?", (frequency,)).fetchone()['c']
        mastered = db.execute('''
            SELECT COUNT(*) AS c FROM user_words uw JOIN words w ON w.id=uw.word_id
            WHERE w.frequency=? AND uw.status IN ('巩固','掌握','熟记')
        ''', (frequency,)).fetchone()['c']
        current = round(mastered / total * 100) if total else 0
        result.append({
            'frequency': frequency, 'level': f'{frequency}星', 'required': target,
            'current': current, 'met': current >= target,
        })
    return result


def _get_threshold_status(db, current_rank):
    return _threshold_status_for_rank(db, min(current_rank + 1, 10))


def _build_rank_catalog(db, result):
    current_rank = result['rank']
    current_score = float(result['total_score'])
    catalog = []
    for rank in range(1, 11):
        target_score = LEVEL_SCORE_THRESHOLDS[rank]
        word_thresholds = _threshold_status_for_rank(db, rank)
        unmet = []
        score_gap = round(max(0, target_score - current_score), 1)
        if score_gap:
            unmet.append(f'综合分还差 {score_gap} 分')
        for item in word_thresholds:
            if not item['met']:
                unmet.append(
                    f'{item["level"]}词掌握率需 {item["required"]}%，当前 {item["current"]}%'
                )
        if rank < current_rank:
            state = 'reached'
        elif rank == current_rank:
            state = 'current'
        elif rank == min(10, current_rank + 1):
            state = 'next'
        else:
            state = 'locked'
        profile = LEVEL_PROFILES[rank]
        catalog.append({
            'rank': rank,
            'name': LEVEL_NAMES[rank],
            'target_score': target_score,
            'score_gap': score_gap,
            'portrait': f'/static/images/ranks/{LEVEL_PORTRAITS[rank]}',
            'positioning': profile['positioning'],
            'cet_anchor': profile['cet_anchor'],
            'summary': profile['summary'],
            'representative_capability': CAPABILITY_TEMPLATES[rank]['reading'],
            'capabilities': {
                'exam': CAPABILITY_TEMPLATES[rank]['exam'],
                'reading': CAPABILITY_TEMPLATES[rank]['reading'],
                'listening': CAPABILITY_TEMPLATES[rank]['listening'],
                'writing': CAPABILITY_TEMPLATES[rank]['writing'],
                'life': CAPABILITY_TEMPLATES[rank]['life'],
            },
            'word_thresholds': word_thresholds,
            'unmet_conditions': unmet,
            'state': state,
            'eligible_by_current_evidence': not unmet,
        })
    return catalog


def _generate_quantified_suggestions(ledger, thresholds):
    suggestions = []
    ability_keys = [key for key in ledger if key != 'investment']
    priority = sorted(
        ability_keys,
        key=lambda key: (ledger[key]['effective_score'], ledger[key]['reliability']),
    )
    for key in priority:
        item = ledger[key]
        if key in EVIDENCE_TARGETS:
            samples = item['evidence'].get('samples', item['evidence'].get('reviews', 0))
            remaining = max(0, EVIDENCE_TARGETS[key] - samples)
            if remaining:
                unit = '次写作' if key == 'writing' else '个有效样本'
                text = (
                    f'再完成 {remaining} {unit}，让{DIMENSION_LABELS[key]}可靠度从 '
                    f'{item["reliability"]}% 向完整证据推进。'
                )
            else:
                text = f'{DIMENSION_LABELS[key]}证据已较完整，下一轮尝试更高一级难度并保持70%以上正确率。'
        elif key == 'vocabulary':
            remaining = max(0, 100 - item['evidence'].get('studied_words', 0))
            text = f'再把 {min(remaining, 20)} 个核心词推进到“掌握”或“熟记”，提高词汇覆盖与升段门槛进度。'
        else:
            text = f'继续补充{DIMENSION_LABELS[key]}记录，让当前判断更稳定。'
        suggestions.append({'dimension': key, 'text': text, 'priority': len(suggestions) + 1})
        if len(suggestions) == 2:
            break
    unmet = next((item for item in thresholds if not item['met']), None)
    if unmet:
        suggestions.append({
            'dimension': 'vocabulary_threshold', 'priority': 3,
            'text': f'下一段还要求{unmet["level"]}词掌握率达到 {unmet["required"]}%（当前 {unmet["current"]}%）。',
        })
    else:
        investment = ledger['investment']
        suggestions.append({
            'dimension': 'investment', 'priority': 3,
            'text': f'近28天有效投入为 {investment["evidence"].get("effective_minutes_28",0)} 分钟；保持短时高质量训练即可，无需靠堆时长刷分。',
        })
    return suggestions[:3]

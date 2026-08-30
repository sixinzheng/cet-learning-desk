"""专项整轮结算与听说内容接口。"""

import json
import uuid

from flask import Blueprint, jsonify, request

from database import get_db
from services.difficulty_service import get_training_difficulty
from services.practice_service import (
    adjusted_objective_score,
    record_practice_session,
)
from services.review_service import get_listening_review_candidates

bp = Blueprint('practice', __name__)


def _key(data, prefix):
    value = str(data.get('idempotency_key') or '').strip()
    return value or f'{prefix}-{uuid.uuid4()}'


def _session_response(row):
    return {
        'ok': True,
        'session_id': row['id'],
        'score': round(row['raw_score'], 1),
        'raw_score': round(row['raw_score'], 1),
        'correct_count': row['correct_count'],
        'total_count': row['total_count'],
        'duplicate': bool(row.get('duplicate')),
    }


@bp.post('/reading/complete')
def complete_reading():
    data = request.get_json(silent=True) or {}
    article_id = data.get('article_id')
    answers = data.get('answers') or {}
    if not article_id or not isinstance(answers, dict):
        return jsonify({'error': '缺少文章或答题结果'}), 400
    db = get_db()
    article = db.execute(
        "SELECT id,difficulty,topic,question_type FROM reading_articles WHERE id=?", (article_id,)
    ).fetchone()
    questions = db.execute(
        "SELECT id, answer FROM reading_questions WHERE article_id=? ORDER BY id", (article_id,)
    ).fetchall()
    db.close()
    if not article or not questions:
        return jsonify({'error': '阅读内容不存在'}), 404
    # 正式前端使用问题主键；同时兼容旧客户端按题目顺序提交 1..N。
    # 只有当前文章的主键在提交中一个都不存在时才启用顺序兼容，避免混用。
    uses_question_ids = any(str(question['id']) in answers for question in questions)
    correct = sum(
        1 for index, question in enumerate(questions, start=1)
        if str(answers.get(
            str(question['id']) if uses_question_ids else str(index), ''
        )).upper() == question['answer'].upper()
    )
    score = adjusted_objective_score(correct, len(questions), article['difficulty'])
    row = record_practice_session(
        module='reading', activity_type='article', source_id=article_id,
        difficulty=article['difficulty'], correct_count=correct, total_count=len(questions),
        raw_score=score, duration_seconds=data.get('duration_seconds', 0),
        metadata={'question_ids': [q['id'] for q in questions]},
        origin=data.get('origin', 'practice'), idempotency_key=_key(data, 'reading'),
    )
    if not row.get('duplicate') and article['question_type'] == 'careful_reading':
        from services.reading_inventory_service import schedule_replacement
        schedule_replacement(article['id'], article['topic'], article['difficulty'])
    return jsonify(_session_response(row))


@bp.get('/listening/content')
def listening_content():
    layer = request.args.get('layer', 'dialogue')
    db = get_db()
    selection_basis = '本轮使用当前难度的本地情景题'
    if layer == 'dialogue':
        base = '''
            SELECT id, layer, topic, difficulty, prompt, script, question,
                   options_json, sample_response
            FROM listening_scenarios
            WHERE layer=? AND is_active=1
        '''
        saved = get_training_difficulty(db)
        if saved is not None:
            # 保存了训练难度 → 精确筛选，不足放宽 ±1，再不足回到全部
            rows = db.execute(base + " AND difficulty=? ORDER BY difficulty, id", (layer, saved)).fetchall()
            if not rows:
                rows = db.execute(
                    base + " AND difficulty BETWEEN ? AND ? ORDER BY difficulty, id",
                    (layer, max(1, saved - 1), min(6, saved + 1)),
                ).fetchall()
            if not rows:
                rows = db.execute(base + " ORDER BY difficulty, id", (layer,)).fetchall()
        else:
            rows = db.execute(base + " ORDER BY difficulty, id", (layer,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item['options'] = json.loads(item.pop('options_json') or '[]')
            result.append(item)
    elif layer == 'sentence':
        candidates = get_listening_review_candidates(60)
        result = []
        for candidate in candidates:
            row = db.execute('''
                SELECT s.id, s.word_id, s.content AS script, s.translation, w.word, w.frequency
                FROM sentences s JOIN words w ON w.id=s.word_id
                WHERE s.word_id=? AND s.translation!=''
                ORDER BY s.id LIMIT 1
            ''', (candidate['word_id'],)).fetchone()
            if not row:
                continue
            item = dict(row)
            item['meaning'] = item.pop('translation')
            item['difficulty'] = max(1, min(6, 6 - int(item.get('frequency') or 3)))
            item['priority_reason'] = candidate.get('priority_reason')
            result.append(item)
            if len(result) >= 20:
                break
        selection_basis = '本轮优先使用到期词与薄弱词的例句'
    else:
        rows = get_listening_review_candidates(20)
        result = []
        for row in rows:
            item = dict(row)
            item['id'] = item.get('word_id') or item.get('id')
            item['difficulty'] = max(1, min(6, 6 - int(item.get('frequency') or 3)))
            result.append(item)
        selection_basis = '本轮优先复习到期词，其次补充近期答错和长期未复习词'
    db.close()
    return jsonify({'layer': layer, 'items': result, 'selection_basis': selection_basis})


@bp.post('/listening/complete')
def complete_listening():
    data = request.get_json(silent=True) or {}
    layer = data.get('layer', 'word')
    answers = data.get('answers') or []
    if not isinstance(answers, list) or not answers:
        return jsonify({'error': '缺少听力答题结果'}), 400
    db = get_db()
    correct = 0
    difficulties = []
    if layer == 'dialogue':
        ids = [int(item['scenario_id']) for item in answers if item.get('scenario_id')]
        if not ids:
            db.close(); return jsonify({'error': '听力内容无效'}), 400
        placeholders = ','.join('?' for _ in ids)
        rows = db.execute(
            f"SELECT id, answer, difficulty FROM listening_scenarios WHERE layer='dialogue' AND id IN ({placeholders})",
            tuple(ids),
        ).fetchall()
        submitted = {int(item['scenario_id']): str(item.get('answer', '')).upper() for item in answers}
        correct = sum(1 for row in rows if submitted.get(row['id']) == row['answer'].upper())
        difficulties = [row['difficulty'] for row in rows]
        total = len(rows)
    else:
        expected_ids = [int(item.get('word_id') or 0) for item in answers if int(item.get('word_id') or 0)]
        if not expected_ids:
            db.close(); return jsonify({'error': '听力内容无效'}), 400
        placeholders = ','.join('?' for _ in expected_ids)
        rows = db.execute(
            f"SELECT DISTINCT w.id, w.frequency FROM words w JOIN user_words uw ON uw.word_id=w.id WHERE w.id IN ({placeholders})",
            tuple(expected_ids),
        ).fetchall()
        allowed = {row['id']: max(1, min(6, 6 - int(row['frequency'] or 3))) for row in rows}
        submitted = {int(item.get('word_id') or 0): int(item.get('selected_word_id') or 0) for item in answers}
        correct = sum(1 for word_id in allowed if submitted.get(word_id) == word_id)
        difficulties = list(allowed.values())
        total = len(allowed)
    db.close()
    if not total:
        return jsonify({'error': '听力内容不存在'}), 404
    difficulty = round(sum(difficulties) / len(difficulties)) if difficulties else 2
    score = adjusted_objective_score(correct, total, difficulty)
    row = record_practice_session(
        module='listening', activity_type=layer, difficulty=difficulty,
        correct_count=correct, total_count=total, raw_score=score,
        duration_seconds=data.get('duration_seconds', 0),
        response_ms=data.get('response_ms', 0), metadata={'layer': layer},
        origin=data.get('origin', 'practice'), idempotency_key=_key(data, f'listening-{layer}'),
    )
    return jsonify(_session_response(row))


@bp.post('/diagnostic/complete')
def complete_diagnostic():
    """诊断由各模块结果组成；只接受已经由服务端结算的专项记录ID。"""
    data = request.get_json(silent=True) or {}
    ids = [int(value) for value in data.get('session_ids', []) if str(value).isdigit()]
    if not ids:
        return jsonify({'error': '尚未完成诊断题目'}), 400
    db = get_db()
    placeholders = ','.join('?' for _ in ids)
    db.execute(
        f"UPDATE practice_sessions SET origin='diagnostic' WHERE id IN ({placeholders})",
        tuple(ids),
    )
    db.commit(); db.close()
    from services.level_service import calculate_level
    result = calculate_level(reason='diagnostic')
    return jsonify({'ok': True, 'level': result})

"""单词专练（四六级选词填空）内容与整轮结算。

题面只下发挖空文章和统一候选词，不向客户端暴露每空原形、提示或答案映射。
整轮结算写入 practice_sessions（module='vocabulary'），供段位「词汇运用」维度读取。
"""
import json
import uuid

from flask import Blueprint, jsonify, request

from database import get_db
from services.difficulty_service import get_training_difficulty
from services.practice_service import adjusted_objective_score, record_practice_session

bp = Blueprint('cloze', __name__)


def _key(data, prefix):
    value = str(data.get('idempotency_key') or '').strip()
    return value or f'{prefix}-{uuid.uuid4()}'


def _pick_passages(db):
    """按训练难度选文章；未设置则返回全部。"""
    saved = get_training_difficulty(db)
    if saved is not None:
        rows = db.execute(
            'SELECT * FROM cloze_passages WHERE difficulty=? ORDER BY id',
            (saved,),
        ).fetchall()
        if not rows:
            rows = db.execute(
                'SELECT * FROM cloze_passages WHERE difficulty BETWEEN ? AND ? ORDER BY id',
                (max(1, saved - 1), min(6, saved + 1)),
            ).fetchall()
        if not rows:
            rows = db.execute('SELECT * FROM cloze_passages ORDER BY id').fetchall()
    else:
        rows = db.execute('SELECT * FROM cloze_passages ORDER BY id').fetchall()
    return rows


@bp.get('/cloze/content')
def cloze_content():
    db = get_db()
    passages = _pick_passages(db)
    db.close()
    result = []
    for passage in passages:
        db = get_db()
        blanks = db.execute(
            'SELECT blank_order, answer FROM cloze_blanks '
            'WHERE passage_id=? ORDER BY blank_order',
            (passage['id'],),
        ).fetchall()
        db.close()
        distractors = json.loads(passage['distractors'] or '[]')
        candidates = [b['answer'] for b in blanks] + list(distractors)
        result.append({
            'id': passage['id'],
            'title': passage['title'],
            'difficulty': passage['difficulty'],
            'level': passage['level'],
            'content': passage['content'],
            'blanks': [{'blank_order': b['blank_order']} for b in blanks],
            'candidates': candidates,
            'blank_count': len(blanks),
        })
    return jsonify({'items': result})


@bp.post('/cloze/complete')
def cloze_complete():
    data = request.get_json(silent=True) or {}
    passage_id = data.get('passage_id')
    answers = data.get('answers') or []
    if not passage_id or not isinstance(answers, list) or not answers:
        return jsonify({'error': '缺少文章或填空结果'}), 400
    db = get_db()
    passage = db.execute(
        'SELECT id, title, difficulty FROM cloze_passages WHERE id=?', (passage_id,)
    ).fetchone()
    blanks = db.execute(
        'SELECT blank_order, base_word, answer FROM cloze_blanks WHERE passage_id=? ORDER BY blank_order',
        (passage_id,),
    ).fetchall()
    db.close()
    if not passage or not blanks:
        return jsonify({'error': '选词填空文章不存在'}), 404
    submitted = {int(item['blank_order']): str(item.get('answer', '')).strip().lower()
                 for item in answers if item.get('blank_order') is not None}
    correct = sum(1 for blank in blanks
                  if submitted.get(blank['blank_order']) == blank['answer'].lower())
    difficulty = passage['difficulty']
    score = adjusted_objective_score(correct, len(blanks), difficulty)
    row = record_practice_session(
        module='vocabulary', activity_type='cloze', source_id=str(passage_id),
        difficulty=difficulty, correct_count=correct, total_count=len(blanks),
        raw_score=score, duration_seconds=data.get('duration_seconds', 0),
        metadata={'passage_id': passage_id, 'title': passage['title'],
                  'base_words': [b['base_word'] for b in blanks]},
        origin=data.get('origin', 'practice'), idempotency_key=_key(data, 'cloze'),
    )
    return jsonify({
        'ok': True,
        'session_id': row['id'],
        'score': round(row['raw_score'], 1),
        'correct_count': correct,
        'total_count': len(blanks),
        'duplicate': bool(row.get('duplicate')),
        'answers': [
            {
                'blank_order': b['blank_order'],
                'answer': b['answer'],
                'base_word': b['base_word'],
            }
            for b in blanks
        ],
    })

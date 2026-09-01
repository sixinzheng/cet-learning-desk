from functools import wraps
import secrets

from flask import Blueprint, jsonify, request, session
from database import get_db
from seed.reading_catalog import TOPICS
from services.difficulty_service import get_training_difficulty
from services.reading_inventory_service import enable_refill, inventory_snapshot
from services.word_enrichment_service import article_vocabulary, lookup_word as lookup_article_word

bp = Blueprint('reading', __name__)


def _require_csrf(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = session.get('ai_csrf_token', '')
        supplied = request.headers.get('X-CSRF-Token', '')
        if not expected or not supplied or not secrets.compare_digest(supplied, expected):
            return jsonify({'error': '页面安全令牌已过期，请刷新后重试。'}), 403
        return view(*args, **kwargs)
    return wrapped


@bp.route('/articles')
def list_articles():
    topic = request.args.get('topic', '')
    requested = request.args.get('difficulty', type=int)
    db = get_db()
    saved = get_training_difficulty(db)
    include_completed = request.args.get('include_completed') == '1'
    base_query = """SELECT id,title,source,word_count,difficulty,topic,question_type,date_added,
                           source_url,source_title,source_published_at,origin,inventory_status
                    FROM reading_articles"""

    def fetch(diff_clause, diff_params):
        parts, params = ["question_type='careful_reading'"], []
        if not include_completed:
            parts.append("inventory_status='available'")
            parts.append("NOT EXISTS (SELECT 1 FROM practice_sessions p WHERE p.module='reading' AND CAST(p.source_id AS TEXT)=CAST(reading_articles.id AS TEXT))")
        if topic:
            parts.append("topic = ?")
            params.append(topic)
        if diff_clause:
            parts.append(diff_clause)
            params.extend(diff_params)
        where = (" WHERE " + " AND ".join(parts)) if parts else ""
        return db.execute(base_query + where + " ORDER BY date_added DESC", tuple(params)).fetchall()

    if requested is not None:
        # 前端显式指定 → 维持原有 ±1 窗口
        rows = fetch("difficulty BETWEEN ? AND ?", [max(1, requested - 1), min(6, requested + 1)])
    elif saved is not None:
        # 保存了训练难度 → 精确筛选，不足时放宽 ±1，再不足回到全部
        rows = fetch("difficulty = ?", [saved])
        if not rows:
            rows = fetch("difficulty BETWEEN ? AND ?", [max(1, saved - 1), min(6, saved + 1)])
        if not rows:
            rows = fetch(None, [])
    else:
        rows = fetch(None, [])
    articles = []
    for r in rows:
        articles.append({
            'id': r['id'], 'title': r['title'], 'source': r['source'],
            'word_count': r['word_count'], 'difficulty': r['difficulty'],
            'topic': r['topic'], 'question_type': r['question_type'] or 'careful_reading',
            'date': r['date_added'],
            'source_url': r['source_url'], 'source_title': r['source_title'],
            'source_published_at': r['source_published_at'], 'origin': r['origin'],
            'inventory_status': r['inventory_status'],
            'stars': '★' * r['difficulty'] + '☆' * max(0, 6 - r['difficulty']),
        })
    db.close()
    return jsonify({
        'articles': articles,
        'topics': list(TOPICS),
    })


@bp.route('/articles/<int:article_id>')
def article_detail(article_id):
    db = get_db()
    article = db.execute("SELECT * FROM reading_articles WHERE id=?", (article_id,)).fetchone()
    if not article:
        db.close()
        return jsonify({'error': '文章不存在'}), 404

    questions = db.execute(
        "SELECT * FROM reading_questions WHERE article_id=? ORDER BY id", (article_id,)
    ).fetchall()

    import json
    vocabulary = article_vocabulary(article)
    word_stats = {
        'mastered': vocabulary['mastered'],
        'total_vocab': vocabulary['total_vocab'],
        'percentage': vocabulary['percentage'],
    }

    question_items = [{
        'id': q['id'],
        'type': q['question_type'],
        'question': q['question'],
        'options': json.loads(q['options']),
        'answer': q['answer'],
        'explanation': q['explanation'],
        'evidence_text': q['evidence_text'],
    } for q in questions]
    response = {
        'id': article['id'],
        'title': article['title'],
        'source': article['source'],
        'content': article['content'],
        'word_count': article['word_count'],
        'difficulty': article['difficulty'],
        'topic': article['topic'],
        'question_type': article['question_type'] or 'careful_reading',
        'source_url': article['source_url'],
        'source_title': article['source_title'],
        'source_published_at': article['source_published_at'],
        'retrieved_at': article['retrieved_at'],
        'adaptation_notes': article['adaptation_notes'],
        'adaptation_note': article['adaptation_note'],
        'source_name': article['source_name'],
        'source_verification': article['source_verification'],
        'origin': article['origin'],
        'word_stats': word_stats,
        'vocabulary': vocabulary,
        'questions': question_items,
    }
    db.close()
    return jsonify(response)


@bp.get('/inventory')
def reading_inventory():
    return jsonify(inventory_snapshot())


@bp.get('/refill/status')
def refill_status():
    snapshot = inventory_snapshot()
    db = get_db()
    rows = db.execute(
        """SELECT id,topic,difficulty,status,attempts,max_attempts,last_error,
                  source_domain,source_url,actual_cost_cny,updated_at
           FROM reading_generation_jobs ORDER BY id DESC LIMIT 20"""
    ).fetchall()
    db.close()
    snapshot['recent_jobs'] = [dict(row) for row in rows]
    return jsonify(snapshot)


@bp.post('/refill/retry')
@_require_csrf
def retry_refill():
    started = enable_refill()
    inventory = inventory_snapshot()
    if not inventory['curation']['approved']:
        return jsonify({
            'ok': False,
            'started': False,
            'error': '首批题库人工策展中，审批完成前不会启动 AI 补库。',
            'inventory': inventory,
        }), 409
    return jsonify({'ok': True, 'started': started, 'inventory': inventory})


@bp.route('/lookup-word')
def lookup_word():
    word = request.args.get('word', '').strip().lower()
    if not word:
        return jsonify({'found': False})
    result = lookup_article_word(word)
    if result.get('found'):
        result['audio_url'] = f'/api/words/{int(result["id"])}/audio'
    return jsonify(result)


@bp.route('/articles/<int:article_id>/annotations')
def article_annotations(article_id):
    db = get_db()
    rows = db.execute(
        "SELECT word_index, mark_type FROM article_annotations WHERE article_id=?", (article_id,)
    ).fetchall()
    db.close()
    ann = {}
    for row in rows:
        ann.setdefault(row['word_index'], []).append(row['mark_type'])
    return jsonify({'annotations': ann})


@bp.route('/articles/<int:article_id>/annotations', methods=['POST'])
def save_annotation(article_id):
    data = request.get_json(silent=True) or {}
    idx = int(data.get('word_index', -1))
    mark_type = str(data.get('mark_type') or '')
    if idx < 0 or mark_type not in ('green', 'red'):
        return jsonify({'error': '标注参数无效。'}), 400
    db = get_db()
    db.execute(
        "INSERT INTO article_annotations (article_id,word_index,mark_type) VALUES (?,?,?) "
        "ON CONFLICT(article_id,word_index,mark_type) DO UPDATE SET mark_type=excluded.mark_type",
        (article_id, idx, mark_type),
    )
    db.commit(); db.close()
    return jsonify({'ok': True})


@bp.route('/articles/<int:article_id>/annotations', methods=['DELETE'])
def delete_annotation(article_id):
    data = request.get_json(silent=True) or {}
    idx = int(data.get('word_index', -1))
    mark_type = str(data.get('mark_type') or 'green')
    if idx < 0:
        return jsonify({'error': '标注参数无效。'}), 400
    db = get_db()
    db.execute("DELETE FROM article_annotations WHERE article_id=? AND word_index=? AND mark_type=?", (article_id, idx, mark_type))
    db.commit(); db.close()
    return jsonify({'ok': True})


@bp.route('/articles/<int:article_id>/annotations/batch', methods=['POST'])
def save_annotations_batch(article_id):
    data = request.get_json(silent=True) or {}
    mode = str(data.get('mode') or '')
    raw_indices = data.get('word_indices') or []
    if mode not in ('green', 'red', 'erase') or not isinstance(raw_indices, list):
        return jsonify({'error': '批量标注参数无效。'}), 400
    try:
        indices = sorted({int(value) for value in raw_indices if int(value) >= 0})
    except (TypeError, ValueError):
        return jsonify({'error': '标注位置无效。'}), 400
    if not indices or len(indices) > 500:
        return jsonify({'error': '请选择 1–500 个词进行标注。'}), 400
    db = get_db()
    exists = db.execute("SELECT 1 FROM reading_articles WHERE id=?", (article_id,)).fetchone()
    if not exists:
        db.close()
        return jsonify({'error': '文章不存在。'}), 404
    if mode == 'erase':
        marks = ','.join('?' for _ in indices)
        db.execute(
            f"DELETE FROM article_annotations WHERE article_id=? AND word_index IN ({marks})",
            (article_id, *indices),
        )
    else:
        db.executemany(
            "INSERT OR IGNORE INTO article_annotations (article_id,word_index,mark_type) VALUES (?,?,?)",
            [(article_id, index, mode) for index in indices],
        )
    db.commit(); db.close()
    return jsonify({'ok': True, 'mode': mode, 'word_indices': indices})

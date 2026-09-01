from flask import Blueprint, jsonify, request, send_file
import io
from models.word import Word
from database import get_db
from services.pronunciation_service import audio_url, read_word_audio, PronunciationUnavailable
import json

bp = Blueprint('words', __name__)


@bp.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 1:
        return jsonify({'words': []})
    rows = Word.search(q)
    words = []
    for w in rows:
        uw = get_db().execute("SELECT status FROM user_words WHERE word_id=?", (w['id'],)).fetchone()
        words.append({
            'id': w['id'], 'word': w['word'], 'phonetic': w['phonetic'],
            'part_of_speech': w['part_of_speech'], 'meanings': w['meanings'],
            'frequency': w['frequency'],
            'status': uw['status'] if uw else '陌生',
            'audio_url': audio_url(w['id']),
        })
    return jsonify({'words': words})


@bp.route('/word/<int:word_id>')
def word_detail(word_id):
    detail = Word.get_detail(word_id)
    if not detail:
        return jsonify({'error': '单词不存在'}), 404
    detail = dict(detail)
    detail['audio_url'] = audio_url(word_id)
    return jsonify(detail)


@bp.route('/<int:word_id>/audio')
def word_audio(word_id):
    """Return a packaged MP3 by internal word id; never expose archive paths."""
    db = get_db()
    exists = db.execute("SELECT 1 FROM words WHERE id=?", (word_id,)).fetchone()
    db.close()
    if not exists:
        return jsonify({'error': '单词不存在'}), 404
    try:
        data, etag = read_word_audio(word_id)
    except PronunciationUnavailable as exc:
        return jsonify({'error': str(exc), 'fallback': True}), 404
    response = send_file(
        io.BytesIO(data),
        mimetype='audio/mpeg',
        conditional=True,
        etag=etag,
        max_age=31536000,
        download_name=f'word-{word_id}.mp3',
    )
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


@bp.route('/word/<int:word_id>/status', methods=['PUT'])
def update_status(word_id):
    data = request.json or {}
    new_status = data.get('status')
    allowed = ['陌生', '模糊', '巩固', '掌握', '熟记']
    if new_status not in allowed:
        return jsonify({'error': '无效状态'}), 400

    from datetime import date
    today = date.today().isoformat()

    db = get_db()
    # 幂等计数：仅当词从未知/陌生毕业（首次进入 模糊/巩固/掌握/熟记）时，计入今日已学新词。
    # 变更前已是非陌生（如复习推进、再次改状态）则不重复计数。
    old_row = db.execute("SELECT status FROM user_words WHERE word_id=?", (word_id,)).fetchone()
    was_unknown = old_row is None or (old_row['status'] or '') == '陌生'
    db.execute('''
        INSERT INTO user_words (word_id, status) VALUES (?, ?)
        ON CONFLICT(word_id) DO UPDATE SET status=?
    ''', (word_id, new_status, new_status))

    if new_status == '模糊':
        # 标记为模糊 → 立即纳入今日复习队列
        db.execute('''
            UPDATE user_words SET ebbinghaus_stage=0, next_review=?
            WHERE word_id=?
        ''', (today, word_id))
    elif new_status == '巩固':
        # 巩固 → 30天后复查（长期巩固期第 1 格）
        from datetime import timedelta
        next30 = (date.today() + timedelta(days=30)).isoformat()
        db.execute('''
            UPDATE user_words SET ebbinghaus_stage=0, next_review=?
            WHERE word_id=?
        ''', (next30, word_id))
    elif new_status == '掌握':
        # 掌握 → 180天后复查（极长复查）
        from datetime import timedelta
        next180 = (date.today() + timedelta(days=180)).isoformat()
        db.execute('''
            UPDATE user_words SET ebbinghaus_stage=0, next_review=?
            WHERE word_id=?
        ''', (next180, word_id))
    elif new_status == '熟记':
        db.execute('''
            UPDATE user_words SET ebbinghaus_stage=99, next_review=NULL
            WHERE word_id=?
        ''', (word_id,))

    # 首次从陌生毕业（含标记熟记/手动升级）→ 计入今日已学新词（幂等）
    if new_status != '陌生' and was_unknown:
        db.execute('''
            INSERT INTO study_logs (study_date, new_words_count)
            VALUES (?, 1)
            ON CONFLICT(study_date) DO UPDATE SET new_words_count = new_words_count + 1
        ''', (today,))

    db.commit()
    return jsonify({'ok': True, 'status': new_status})


@bp.route('/word/<int:word_id>/link', methods=['POST'])
def link_words(word_id):
    """创建/添加到相关单词标签"""
    data = request.json or {}
    tag_name = data.get('tag_name', '').strip()
    add_word_ids = data.get('word_ids', [])

    if not tag_name or not add_word_ids:
        return jsonify({'error': '参数不完整'}), 400

    db = get_db()
    all_ids = list(set([word_id] + [int(w) for w in add_word_ids]))
    db.execute(
        "INSERT INTO word_links (tag_name, word_ids) VALUES (?,?)",
        (tag_name, json.dumps(all_ids, ensure_ascii=False))
    )
    db.commit()
    return jsonify({'ok': True, 'tag_name': tag_name, 'word_ids': all_ids})


@bp.route('/favorite', methods=['GET', 'PUT'])
def favorite():
    """单词收藏：GET 查状态（?word_id=），PUT 切换（body: {word_id}）。"""
    db = get_db()
    if request.method == 'GET':
        word_id = request.args.get('word_id', type=int)
        fav = Word.get_favorite_book()
        words = Word.list_by_wordbook(fav, 0, 10000)
        ids = [w['id'] for w in words]
        if word_id is not None:
            db.close()
            return jsonify({'is_favorite': word_id in ids, 'favorite_book_id': fav, 'favorite_count': len(ids)})
        # 无 word_id → 返回收藏词库全部词
        result = [{
            'id': w['id'], 'word': w['word'], 'phonetic': w['phonetic'],
            'part_of_speech': w['part_of_speech'], 'meanings': w['meanings'],
            'frequency': w['frequency'], 'status': w['status'] or '陌生',
            'audio_url': audio_url(w['id']),
        } for w in words]
        db.close()
        return jsonify({'favorite_book_id': fav, 'favorite_count': len(result), 'words': result})

    data = request.json or {}
    word_id = data.get('word_id')
    if not word_id:
        db.close()
        return jsonify({'error': '缺少word_id'}), 400
    result = Word.toggle_favorite(word_id)
    if result is None:
        db.close()
        return jsonify({'error': '单词不存在'}), 404
    is_fav, fav_id = result
    db.close()
    return jsonify({'is_favorite': is_fav, 'favorite_book_id': fav_id})


@bp.route('/wordbooks')
def wordbooks():
    """词库列表，附带每本词库的掌握统计与当前词库标记（词库概览用）。"""
    books = Word.get_wordbooks()
    db = get_db()
    # 当前词库 id（学习新词跟随）
    current = None
    saved = db.execute("SELECT value FROM user_settings WHERE key='current_wordbook'").fetchone()
    if saved and saved['value'].isdigit():
        current = int(saved['value'])
    result = []
    for b in books:
        total = db.execute("SELECT COUNT(*) as c FROM wordbook_words WHERE wordbook_id=?", (b['id'],)).fetchone()['c']
        # 各状态统计（按用户学习进度 user_words）
        stats = db.execute('''
            SELECT
                SUM(CASE WHEN uw.status='熟记' THEN 1 ELSE 0 END) AS mastered,
                SUM(CASE WHEN uw.status='掌握' THEN 1 ELSE 0 END) AS known,
                SUM(CASE WHEN uw.status IN ('模糊','巩固') THEN 1 ELSE 0 END) AS learning
            FROM wordbook_words wbw
            LEFT JOIN user_words uw ON uw.word_id = wbw.word_id
            WHERE wbw.wordbook_id=?
        ''', (b['id'],)).fetchone()
        result.append({
            'id': b['id'], 'name': b['name'], 'description': b['description'],
            'is_builtin': bool(b['is_builtin']), 'total_words': total,
            'mastered': int(stats['mastered'] or 0),
            'known': int(stats['known'] or 0),
            'learning': int(stats['learning'] or 0),
            'is_current': b['id'] == current,
        })
    db.close()
    return jsonify({'wordbooks': result})


@bp.route('/current-wordbook', methods=['GET', 'PUT'])
def current_wordbook():
    """当前学习词书（user_settings.current_wordbook）：学习新词跟随它。"""
    db = get_db()
    if request.method == 'GET':
        value = db.execute("SELECT value FROM user_settings WHERE key='current_wordbook'").fetchone()
        book_id = int(value['value']) if value and value['value'].isdigit() else None
        name = None
        if book_id:
            book = db.execute(
                "SELECT id, name FROM wordbooks WHERE id=? AND COALESCE(is_hidden,0)=0",
                (book_id,),
            ).fetchone()
            if not book:
                book_id = None
            else:
                name = book['name']
        if book_id is None:
            book = db.execute(
                "SELECT id, name FROM wordbooks WHERE is_builtin=1 AND COALESCE(is_hidden,0)=0 ORDER BY id LIMIT 1"
            ).fetchone()
            if book:
                book_id, name = book['id'], book['name']
        db.close()
        return jsonify({'book_id': book_id, 'book_name': name})

    data = request.json or {}
    book_id = data.get('book_id')
    if not book_id:
        db.close()
        return jsonify({'error': '缺少book_id'}), 400
    book = db.execute(
        "SELECT id, name FROM wordbooks WHERE id=? AND COALESCE(is_hidden,0)=0",
        (book_id,),
    ).fetchone()
    if not book:
        db.close()
        return jsonify({'error': '词库不存在'}), 404
    db.execute("INSERT OR REPLACE INTO user_settings (key, value) VALUES ('current_wordbook', ?)",
               (str(book_id),))
    db.commit()
    db.close()
    return jsonify({'ok': True, 'book_id': book_id, 'book_name': book['name']})


@bp.route('/wordbooks', methods=['POST'])
def create_wordbook():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': '词库名不能为空'}), 400
    wid = Word.create_wordbook(name, data.get('description', ''))
    return jsonify({'id': wid, 'name': name})


@bp.route('/wordbooks/<int:book_id>/words')
def wordbook_words(book_id):
    db = get_db()
    visible = db.execute(
        "SELECT 1 FROM wordbooks WHERE id=? AND COALESCE(is_hidden,0)=0", (book_id,)
    ).fetchone()
    db.close()
    if not visible:
        return jsonify({'error': '词库不存在'}), 404
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 50, type=int)
    rows = Word.list_by_wordbook(book_id, offset, limit)

    words = []
    for w in rows:
        words.append({
            'id': w['id'], 'word': w['word'], 'phonetic': w['phonetic'],
            'part_of_speech': w['part_of_speech'], 'meanings': w['meanings'],
            'frequency': w['frequency'],
            'status': w['status'] or '陌生',
            'review_count': w['review_count'] or 0,
            'next_review': w['next_review'],
            'audio_url': audio_url(w['id']),
        })
    return jsonify({'words': words})

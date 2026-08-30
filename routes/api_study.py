from flask import Blueprint, jsonify, request
from database import get_db
from services.level_service import get_level_summary, calculate_level
from datetime import date, timedelta
from services.review_service import (
    get_due_reviews, get_due_count, record_review,
    init_new_word, promote_to_fuzzy, advance_word, preview_review,
)
from services.difficulty_service import (
    get_training_difficulty, save_training_difficulty,
    difficulty_label, LEVELS,
)

bp = Blueprint('study', __name__)


@bp.route('/dashboard')
def dashboard():
    """首页仪表盘数据"""
    db = get_db()
    from datetime import date
    today = date.today().isoformat()

    # 今日应学新词（从用户设置读取）
    setting = db.execute("SELECT value FROM user_settings WHERE key='daily_count'").fetchone()
    daily_new = int(setting['value']) if setting else 20
    # 今日已学新词数 = study_logs 今日 new_words_count 的实际累计值（不是行数）
    learned_row = db.execute(
        "SELECT new_words_count FROM study_logs WHERE study_date=?", (today,)
    ).fetchone()
    learned_today = int(learned_row['new_words_count'] or 0) if learned_row else 0
    new_words = db.execute(
        "SELECT COUNT(*) as c FROM user_words WHERE status='陌生'"
    ).fetchone()['c']
    # 累计已学单词数（进入过学习流程的词，任务3：首页展示）
    learned_words = db.execute("SELECT COUNT(*) as c FROM user_words").fetchone()['c']

    # 今日待复习词数
    due_review = db.execute(
        "SELECT COUNT(*) as c FROM user_words WHERE next_review <= ? AND status IN ('模糊','巩固','掌握')",
        (today,)
    ).fetchone()['c']
    reviewed_today = db.execute(
        "SELECT COUNT(*) AS c FROM daily_word_completions "
        "WHERE completion_date=? AND completion_type='review'",
        (today,)
    ).fetchone()['c']

    # 连续打卡天数
    streak = 0
    logs = db.execute(
        "SELECT study_date FROM study_logs ORDER BY study_date DESC LIMIT 365"
    ).fetchall()
    from datetime import date, timedelta
    check = date.today()
    for row in logs:
        if row['study_date'] == check.isoformat():
            streak += 1
            check = check - timedelta(days=1)
        elif row['study_date'] == (check - timedelta(days=1)).isoformat() and streak == 0:
            streak += 1
            check = date.fromisoformat(row['study_date'])
        else:
            break

    # 段位摘要
    level = get_level_summary()

    # 热力图数据（近12周）
    heatmap = []
    for i in range(84):
        d = date.today() - timedelta(days=83 - i)
        log = db.execute(
            "SELECT total_minutes FROM study_logs WHERE study_date=?", (d.isoformat(),)
        ).fetchone()
        mins = log['total_minutes'] if log else 0
        heatmap.append([d.isoformat(), mins])

    # 词汇层级统计
    freq_stats = {}
    for star, label in [(1,'one'),(2,'two'),(3,'three'),(4,'four'),(5,'five')]:
        total = db.execute("SELECT COUNT(*) as c FROM words WHERE frequency=?", (star,)).fetchone()['c']
        if total > 0:
            mastered = db.execute('''
                SELECT COUNT(*) as c FROM user_words uw
                JOIN words w ON uw.word_id = w.id
                WHERE w.frequency=? AND uw.status IN ('巩固','掌握','熟记')
            ''', (star,)).fetchone()['c']
            freq_stats[label] = round(mastered / total * 100) if total > 0 else 0
        else:
            freq_stats[label] = 0

    # 今日专项训练完成情况（学习页专用，不含单词）
    today_log = db.execute(
        "SELECT reading_count, listening_count, writing_count, grammar_count, vocabulary_count "
        "FROM study_logs WHERE study_date=?", (today,)
    ).fetchone()
    today_modules = {
        'reading': int(today_log['reading_count'] or 0) if today_log else 0,
        'listening': int(today_log['listening_count'] or 0) if today_log else 0,
        'cloze': int(today_log['vocabulary_count'] or 0) if today_log else 0,
        'writing': int(today_log['writing_count'] or 0) if today_log else 0,
    }

    # 最该补的一项：优先从未有整轮记录的模块开始，否则取平均分最低的模块
    practice_rows = db.execute(
        "SELECT module, ROUND(AVG(raw_score),1) AS score, COUNT(*) AS rounds "
        "FROM practice_sessions GROUP BY module"
    ).fetchall()
    rounds = {row['module']: row['rounds'] for row in practice_rows}
    scores = {row['module']: row['score'] for row in practice_rows}
    order = ['reading', 'listening', 'cloze', 'writing']
    recommend_module = next((m for m in order if not rounds.get(m)), None)
    if recommend_module is None:
        recommend_module = min(order, key=lambda m: scores.get(m, 100))
    labels = {'reading': '阅读训练', 'listening': '听力训练', 'cloze': '单词专练', 'writing': '写作批改'}
    hrefs = {'reading': '/reading', 'listening': '/listening', 'cloze': '/cloze', 'writing': '/writing'}

    db.close()

    return jsonify({
        'today_new': min(max(daily_new - learned_today, 0), new_words),
        'today_review': due_review,
        'daily_target': daily_new,
        'learned_today': learned_today,
        'reviewed_today': reviewed_today,
        'review_goal': daily_new,
        'review_due_remaining': due_review,
        'learned_words': learned_words,
        'streak': streak,
        'level': level,
        'heatmap': heatmap,
        'freq_stats': freq_stats,
        'today_modules': today_modules,
        'recommend': {
            'module': recommend_module,
            'label': labels[recommend_module],
            'href': hrefs[recommend_module],
            'today_done': today_modules[recommend_module],
        },
    })


@bp.route('/new-words')
def get_new_words():
    """获取今日待学新词列表（跟随当前所选词书）"""
    db = get_db()
    setting = db.execute("SELECT value FROM user_settings WHERE key='daily_count'").fetchone()
    default_limit = int(setting['value']) if setting else 20
    limit = request.args.get('limit', default_limit, type=int)

    # 显式 book_id > 已保存的 current_wordbook > 默认第一本内置词书
    book_id = request.args.get('book_id', type=int)
    book_name = None
    if not book_id:
        saved = db.execute("SELECT value FROM user_settings WHERE key='current_wordbook'").fetchone()
        if saved and saved['value'].isdigit():
            candidate = int(saved['value'])
            if db.execute("SELECT id FROM wordbooks WHERE id=?", (candidate,)).fetchone():
                book_id = candidate
    if book_id:
        row = db.execute("SELECT id, name FROM wordbooks WHERE id=?", (book_id,)).fetchone()
        book_name = row['name'] if row else None
    if not book_id:
        book = db.execute("SELECT id, name FROM wordbooks WHERE is_builtin=1 ORDER BY id LIMIT 1").fetchone()
        if not book:
            return jsonify({'words': [], 'book_id': None, 'book_name': None})
        book_id, book_name = book['id'], book['name']

    rows = db.execute('''
        SELECT w.*, uw.status
        FROM words w
        JOIN wordbook_words wbw ON w.id = wbw.word_id
        LEFT JOIN user_words uw ON w.id = uw.word_id
        WHERE wbw.wordbook_id = ?
          AND (uw.status IS NULL OR uw.status = '陌生')
        ORDER BY w.frequency DESC
        LIMIT ?
    ''', (book_id, limit)).fetchall()

    words = [{
        'id': r['id'], 'word': r['word'], 'phonetic': r['phonetic'],
        'part_of_speech': r['part_of_speech'], 'meanings': r['meanings'],
        'frequency': r['frequency'], 'status': r['status'] or '陌生',
    } for r in rows]
    return jsonify({'words': words, 'book_id': book_id, 'book_name': book_name})


@bp.route('/start-learning', methods=['POST'])
def start_learning():
    """开始学习一个单词：初始化艾宾浩斯"""
    data = request.json or {}
    word_id = data.get('word_id')
    if not word_id:
        return jsonify({'error': '缺少word_id'}), 400
    init_new_word(word_id)
    return jsonify({'ok': True})


@bp.route('/answer', methods=['POST'])
def submit_answer():
    """提交学习/复习答题结果

    学习模式（mode='learn'）：correct 布尔，连对 3 过关。
    复习模式（mode='review'）：四档 feedback（recognize/vague/forget/mastered）；
    选择/听力/看义打词等对错型仍可传 correct 布尔，自动映射 recognize/forget。
    """
    data = request.json or {}
    word_id = data.get('word_id')
    mode = data.get('mode', 'review')  # 'learn' or 'review'

    if not word_id:
        return jsonify({'error': '缺少word_id'}), 400

    db = get_db()
    uw = db.execute("SELECT * FROM user_words WHERE word_id=?", (word_id,)).fetchone()

    if mode == 'learn':
        # 学习模式：处理连续选对逻辑
        correct = data.get('correct', False)
        consec = (uw['consecutive_correct'] or 0) if uw else 0
        if correct:
            consec += 1
            db.execute('''
                UPDATE user_words SET consecutive_correct=?, last_reviewed=date('now')
                WHERE word_id=?
            ''', (consec, word_id))
            db.commit()

            if consec >= 3:
                # 连续3次选对 → 升级为模糊
                promote_to_fuzzy(word_id)
                return jsonify({'passed': True, 'next': 'spelling', 'consecutive': consec})

            return jsonify({'passed': False, 'next': 'retry', 'consecutive': consec})
        else:
            # 选错 → 重置连续计数
            db.execute(
                "UPDATE user_words SET consecutive_correct=0 WHERE word_id=?",
                (word_id,)
            )
            db.commit()
            return jsonify({'passed': False, 'next': 'learn_card', 'consecutive': 0})

    # 复习模式：四档反馈，或布尔 correct 自动映射
    feedback = data.get('feedback')
    if feedback not in ('recognize', 'vague', 'forget', 'mastered'):
        correct = data.get('correct', True)
        feedback = 'recognize' if correct else 'forget'
    result = record_review(word_id, feedback)

    # 更新今日学习记录
    from datetime import date
    today = date.today().isoformat()
    db.execute('''
        INSERT INTO study_logs (study_date, review_words_count)
        VALUES (?, 1)
        ON CONFLICT(study_date) DO UPDATE SET review_words_count = review_words_count + 1
    ''', (today,))
    db.commit()

    # 更新段位
    calculate_level()

    return jsonify({'ok': True, 'result': result})


@bp.route('/review-preview')
def review_preview():
    """当前单词四档反馈的预期间隔预览（纯计算，不写库）"""
    word_id = request.args.get('word_id', type=int)
    if not word_id:
        return jsonify({'error': '缺少word_id'}), 400
    result = preview_review(word_id)
    if result is None:
        return jsonify({'error': '单词不存在'}), 404
    return jsonify(result)


@bp.route('/review-words')
def get_review_words():
    """获取今日待复习单词（到期必抽）"""
    limit = request.args.get('limit', 30, type=int)
    words = get_due_reviews(limit)
    return jsonify({'words': words})


@bp.route('/review-word-complete', methods=['POST'])
def review_word_complete():
    """一轮复习完成 → 推进 1 格（幂等：同词同天只推进一次）"""
    data = request.json or {}
    word_id = data.get('word_id')
    if not word_id:
        return jsonify({'error': '缺少word_id'}), 400
    result = advance_word(word_id)
    if result is None:
        return jsonify({'error': '单词不存在或状态不可推进'}), 400
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO daily_word_completions "
        "(completion_date, word_id, completion_type) VALUES (date('now','localtime'), ?, 'review')",
        (word_id,)
    )
    db.commit()
    db.close()
    calculate_level()
    return jsonify(result)


@bp.route('/summary')
def study_summary():
    """学习成果总览"""
    db = get_db()
    totals = db.execute('''
        SELECT COALESCE(SUM(reading_count),0) as reading,
               COALESCE(SUM(listening_count),0) as listening,
               COALESCE(SUM(writing_count),0) as writing,
               COALESCE(SUM(grammar_count),0) as grammar,
               COALESCE(SUM(review_words_count),0) as reviews,
               COALESCE(SUM(total_minutes),0) as minutes
        FROM study_logs
    ''').fetchone()

    note_count = db.execute("SELECT COUNT(*) as c FROM notes").fetchone()['c']
    learned_words = db.execute("SELECT COUNT(*) as c FROM user_words").fetchone()['c']
    mastered_words = db.execute(
        "SELECT COUNT(*) as c FROM user_words WHERE status IN ('巩固','掌握','熟记')"
    ).fetchone()['c']
    active_days = db.execute(
        "SELECT COUNT(*) as c FROM ("
        "SELECT study_date FROM study_logs WHERE "
        "new_words_count+review_words_count+reading_count+listening_count+writing_count+grammar_count+total_minutes>0 "
        "GROUP BY study_date)"
    ).fetchone()['c']
    module_rows = db.execute(
        "SELECT module, ROUND(AVG(raw_score),1) AS score, COUNT(*) AS rounds "
        "FROM practice_sessions GROUP BY module"
    ).fetchall()

    db.close()
    return jsonify({
        'reading': totals['reading'],
        'listening': totals['listening'],
        'writing': totals['writing'],
        'grammar': totals['grammar'],
        'hours': round((totals['minutes'] or 0) / 60, 1),
        'notes': note_count,
        'learned_words': learned_words,
        'mastered_words': mastered_words,
        'review_count': totals['reviews'],
        'active_days': active_days,
        'module_scores': {row['module']: row['score'] for row in module_rows},
    })


@bp.route('/log-reading', methods=['POST'])
def log_reading():
    data = request.json or {}
    seconds = data.get('seconds', 0)
    minutes = max(1, round(seconds / 60))
    today = date.today().isoformat()
    db = get_db()
    db.execute('''
        INSERT INTO study_logs (study_date, reading_count, total_minutes)
        VALUES (?, 1, ?)
        ON CONFLICT(study_date) DO UPDATE SET
            reading_count = reading_count + 1,
            total_minutes = total_minutes + ?
    ''', (today, minutes, minutes))
    db.commit()
    from services.level_service import calculate_level
    calculate_level()
    return jsonify({'ok': True, 'minutes': minutes})


@bp.route('/log-listening', methods=['POST'])
def log_listening():
    today = date.today().isoformat()
    db = get_db()
    db.execute('''
        INSERT INTO study_logs (study_date, listening_count, total_minutes)
        VALUES (?, 1, 2)
        ON CONFLICT(study_date) DO UPDATE SET
            listening_count = listening_count + 1,
            total_minutes = total_minutes + 2
    ''', (today,))
    db.commit()
    from services.level_service import calculate_level
    calculate_level()
    return jsonify({'ok': True})


@bp.route('/log-grammar', methods=['POST'])
def log_grammar():
    today = date.today().isoformat()
    db = get_db()
    db.execute('''
        INSERT INTO study_logs (study_date, grammar_count, total_minutes)
        VALUES (?, 1, 1)
        ON CONFLICT(study_date) DO UPDATE SET
            grammar_count = grammar_count + 1,
            total_minutes = total_minutes + 1
    ''', (today,))
    db.commit()
    from services.level_service import calculate_level
    calculate_level()
    return jsonify({'ok': True})


@bp.route('/log-writing', methods=['POST'])
def log_writing():
    today = date.today().isoformat()
    db = get_db()
    db.execute('''
        INSERT INTO study_logs (study_date, writing_count, total_minutes)
        VALUES (?, 1, 3)
        ON CONFLICT(study_date) DO UPDATE SET
            writing_count = writing_count + 1,
            total_minutes = total_minutes + 3
    ''', (today,))
    db.commit()
    from services.level_service import calculate_level
    calculate_level()
    return jsonify({'ok': True})


@bp.route('/daily-setting', methods=['GET', 'PUT'])
def daily_setting():
    db = get_db()
    if request.method == 'GET':
        row = db.execute("SELECT value FROM user_settings WHERE key='daily_count'").fetchone()
        count = int(row['value']) if row else 20
        return jsonify({'count': count})
    else:
        data = request.json or {}
        count = data.get('count', 20)
        db.execute("INSERT OR REPLACE INTO user_settings (key, value) VALUES ('daily_count', ?)", (str(count),))
        db.commit()
        return jsonify({'ok': True, 'count': count})


@bp.route('/difficulty-setting', methods=['GET', 'PUT'])
def difficulty_setting():
    """训练难度档位：1–6（四级及格…六级优秀）。保存后阅读/语法/听力自动筛题，写作按对应标准批改。"""
    db = get_db()
    if request.method == 'GET':
        value = get_training_difficulty(db)
        result = {
            'difficulty': value,
            'label': difficulty_label(value) if value else '',
            'levels': [{'value': item['value'], 'label': item['label']} for item in LEVELS],
        }
        db.close()
        return jsonify(result)
    data = request.json or {}
    value = data.get('difficulty')
    if value is None:
        db.close()
        return jsonify({'error': '缺少 difficulty'}), 400
    try:
        value = save_training_difficulty(value, db)
    except ValueError as exc:
        db.close()
        return jsonify({'error': str(exc)}), 400
    db.close()
    return jsonify({'ok': True, 'difficulty': value, 'label': difficulty_label(value)})


@bp.route('/achievement-84')
def achievement_84():
    """近84天成就统计，仅聚合现有学习记录。"""
    db = get_db()
    start_date = (date.today() - timedelta(days=83)).isoformat()
    rows = db.execute('''
        SELECT study_date, new_words_count, review_words_count, total_minutes
        FROM study_logs
        WHERE study_date >= ?
        ORDER BY study_date
    ''', (start_date,)).fetchall()

    active_rows = [row for row in rows if any((
        row['new_words_count'] or 0,
        row['review_words_count'] or 0,
        row['total_minutes'] or 0,
    ))]
    active_dates = {row['study_date'] for row in active_rows}
    longest_streak = 0
    running_streak = 0
    previous = None
    for value in sorted(active_dates):
        current = date.fromisoformat(value)
        running_streak = running_streak + 1 if previous and current == previous + timedelta(days=1) else 1
        longest_streak = max(longest_streak, running_streak)
        previous = current

    best = max(active_rows, key=lambda row: row['total_minutes'] or 0, default=None)
    mastered_words = db.execute(
        "SELECT COUNT(*) AS c FROM user_words WHERE status IN ('巩固','掌握','熟记')"
    ).fetchone()['c']
    milestones = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
    target = next((value for value in milestones if value > mastered_words),
                  ((mastered_words // 1000) + 1) * 1000)
    previous_target = max([value for value in milestones if value <= mastered_words] or [0])
    span = max(1, target - previous_target)
    progress = round((mastered_words - previous_target) / span * 100)

    result = {
        'active_days': len(active_rows),
        'total_minutes': sum(row['total_minutes'] or 0 for row in rows),
        'review_count': sum(row['review_words_count'] or 0 for row in rows),
        'longest_streak': longest_streak,
        'best_day': {
            'date': best['study_date'] if best else None,
            'minutes': best['total_minutes'] or 0 if best else 0,
        },
        'mastered_words': mastered_words,
        'milestone': {
            'target': target,
            'progress': max(0, min(100, progress)),
            'remaining': max(0, target - mastered_words),
        },
    }
    db.close()
    return jsonify(result)


@bp.route('/spelling-check', methods=['POST'])
def spelling_check():
    """拼写验证"""
    data = request.json or {}
    word_id = data.get('word_id')
    user_input = data.get('spelling', '').strip().lower()
    mode = data.get('mode', 'learn')  # 'learn'=学习拼写（计入新词）；'review'=看义打词（仅校验）
    if not word_id:
        return jsonify({'error': '缺少word_id'}), 400

    db = get_db()
    w = db.execute("SELECT word FROM words WHERE id=?", (word_id,)).fetchone()
    if not w:
        return jsonify({'error': '单词不存在'}), 404

    is_correct = user_input == w['word'].lower()

    if is_correct and mode != 'review':
        # 陌生→模糊 首次生效时由 promote_to_fuzzy 幂等计入今日已学新词，
        # 这里不再重复 +1（避免同一词在 quiz 过关与拼写验证时重复计数）。
        promote_to_fuzzy(word_id)
        db.commit()
        calculate_level()

    return jsonify({'correct': is_correct, 'word': w['word'] if not is_correct else None})


@bp.route('/review-health')
def review_health():
    """艾宾浩斯健康度 — 四维数据"""
    db = get_db()
    today = date.today().isoformat()

    # 今日到期总数
    due_total = db.execute(
        "SELECT COUNT(*) as c FROM user_words WHERE next_review <= ? AND status IN ('模糊','巩固','掌握')",
        (today,)
    ).fetchone()['c']

    # 今日已复习数（last_reviewed = today）
    reviewed_today = db.execute(
        "SELECT COUNT(*) as c FROM user_words WHERE last_reviewed = ? AND status IN ('模糊','巩固','掌握')",
        (today,)
    ).fetchone()['c']

    # 复习完成度：复习过的词中，ebbinghaus_stage 分布
    stage_stats = db.execute('''
        SELECT ebbinghaus_stage, COUNT(*) as c FROM user_words
        WHERE status IN ('模糊','巩固','掌握')
        GROUP BY ebbinghaus_stage
    ''').fetchall()
    stage_map = {r['ebbinghaus_stage']: r['c'] for r in stage_stats}
    total_reviewed = sum(stage_map.values())
    # 走完全部节点的词（已自动毕业为熟记）
    completed = db.execute(
        "SELECT COUNT(*) as c FROM user_words WHERE status='熟记'"
    ).fetchone()['c']

    # 模糊词池覆盖度
    fuzzy_total = db.execute(
        "SELECT COUNT(*) as c FROM user_words WHERE status='模糊'"
    ).fetchone()['c']
    fuzzy_reviewed = db.execute(
        "SELECT COUNT(*) as c FROM user_words WHERE status='模糊' AND review_count > 0"
    ).fetchone()['c']

    # 遗忘率：wrong_streak > 0 的词占比
    wrong_count = db.execute(
        "SELECT COUNT(*) as c FROM user_words WHERE wrong_streak > 0 AND status IN ('模糊','巩固','掌握')"
    ).fetchone()['c']

    db.close()

    return jsonify({
        'on_time_rate': round(reviewed_today / due_total * 100) if due_total > 0 else 100,
        'completion_rate': round(completed / total_reviewed * 100) if total_reviewed > 0 else 0,
        'forget_curve': max(0, 100 - round(wrong_count / total_reviewed * 100)) if total_reviewed > 0 else 100,
        'coverage_rate': round(fuzzy_reviewed / fuzzy_total * 100) if fuzzy_total > 0 else 0,
        'metrics': {
            'reviewed_today': reviewed_today,
            'due_total': due_total,
            'completed': completed,
            'total_reviewed': total_reviewed,
            'fuzzy_reviewed': fuzzy_reviewed,
            'fuzzy_total': fuzzy_total,
        }
    })


@bp.route('/weekly-rhythm')
def weekly_rhythm():
    """学习节奏分布 — 周一到周日活跃分钟数"""
    db = get_db()
    # 近28天的学习记录，按weekday聚合
    rows = db.execute('''
        SELECT study_date, total_minutes FROM study_logs
        WHERE study_date >= ?
        ORDER BY study_date
    ''', ((date.today() - timedelta(days=27)).isoformat(),)).fetchall()

    from datetime import datetime
    day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    day_totals = {d: 0 for d in day_names}
    day_counts = {d: 0 for d in day_names}

    for r in rows:
        dt = datetime.strptime(r['study_date'], '%Y-%m-%d')
        dname = day_names[dt.weekday()]
        day_totals[dname] += r['total_minutes'] or 0
        day_counts[dname] += 1

    return jsonify({
        'days': day_names,
        'values': [round(day_totals[d] / max(day_counts[d], 1)) for d in day_names],
    })

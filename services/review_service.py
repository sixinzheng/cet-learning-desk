"""
艾宾浩斯复习调度服务（五态状态机）
状态流：陌生 → 模糊 → 巩固 → 掌握 → 熟记（自动毕业）

- 模糊：活跃间隔期，走完 → 巩固
- 巩固：长期巩固期，走完 → 掌握
- 掌握：极长复查，走完 → 熟记自动毕业

间隔按考频分档：高频（frequency 4~5）走快线、低频（frequency 1~3）走慢线。
ebbinghaus_stage 语义：当前状态内的阶段序号。

复习反馈四档（record_review）：
- recognize  认识 → 答对路径（清连错、计连对）
- vague      模糊 → 软过关（连对 +1、不打断、不计连错），标记当日模糊 → 完成时原地巩固
- forget     忘记 → 答错路径（首错 next_review=今天，错词必复现；连错 2 次降级）
- mastered   熟记 → 直接毕业（next_review=NULL 彻底出队）
"""
from database import get_db
from datetime import date, timedelta

# 高频（frequency 4~5）快线间隔表（天）
FAST_INTERVALS = {
    '模糊': [1, 2, 4, 7, 15],      # 活跃间隔期
    '巩固': [30, 60, 90],          # 长期巩固期
    '掌握': [180],                 # 极长复查
}
# 低频（frequency 1~3）慢线间隔表（天）
SLOW_INTERVALS = {
    '模糊': [2, 4, 8, 15, 30],
    '巩固': [60, 120, 180],
    '掌握': [365],
}

HIGH_FREQ_MIN = 4  # frequency >= 4 视为高频

INTERVAL_STATUSES = ('模糊', '巩固', '掌握')

# 走完当前状态全部节点后进入的状态
PROMOTE_STATUS = {
    '模糊': '巩固',
    '巩固': '掌握',
    '掌握': '熟记',  # 自动毕业
}

# 连续答错 2 次后的降级目标（模糊为重置第 1 天）
DEGRADE_STATUS = {
    '模糊': '模糊',
    '巩固': '模糊',
    '掌握': '巩固',
}

REVIEW_STATUSES = ('模糊', '巩固', '掌握')
MASTERED_STATUSES = ('巩固', '掌握', '熟记')

FEEDBACKS = ('recognize', 'vague', 'forget', 'mastered')


def _intervals_for(status, frequency):
    """按考频分档取间隔表：高频快线 / 低频慢线（纯函数，供预览复用）。"""
    return FAST_INTERVALS[status] if (frequency or 0) >= HIGH_FREQ_MIN else SLOW_INTERVALS[status]


def _word_frequency(db, word_id):
    row = db.execute("SELECT frequency FROM words WHERE id=?", (word_id,)).fetchone()
    return row['frequency'] if row else 1


def get_due_reviews(limit=50):
    """获取今日待复习的单词（到期必抽，取消随机抽样；模糊优先、到期升序）"""
    db = get_db()
    today = date.today().isoformat()

    rows = db.execute('''
        SELECT uw.*, w.word, w.phonetic, w.part_of_speech, w.meanings, w.frequency
        FROM user_words uw
        JOIN words w ON uw.word_id = w.id
        WHERE uw.status IN ('模糊', '巩固', '掌握')
          AND uw.next_review <= ?
        ORDER BY
            CASE uw.status
                WHEN '模糊' THEN 0
                WHEN '巩固' THEN 1
                WHEN '掌握' THEN 2
            END,
            uw.next_review ASC
        LIMIT ?
    ''', (today, limit)).fetchall()

    result = [_row_to_dict(r) for r in rows]
    db.close()
    return result


def get_listening_review_candidates(limit=40):
    """Return a stable priority snapshot for listening practice.

    Due words always come first.  When there are not enough due words we fill
    the round with recently missed, long-unreviewed, and still-learning words.
    This function only reads scheduling evidence; it never advances a review.
    """
    db = get_db()
    today = date.today().isoformat()
    rows = db.execute('''
        SELECT uw.*, w.word, w.phonetic, w.part_of_speech, w.meanings, w.frequency,
               CASE
                   WHEN uw.next_review IS NOT NULL AND uw.next_review <= ? THEN '到期复习'
                   WHEN COALESCE(uw.wrong_streak, 0) > 0 THEN '近期答错'
                   WHEN uw.status = '模糊' THEN '模糊词巩固'
                   WHEN uw.status = '巩固' THEN '巩固中'
                   ELSE '长期未复习'
               END AS priority_reason
        FROM user_words uw
        JOIN words w ON uw.word_id = w.id
        WHERE uw.status IN ('模糊', '巩固', '掌握')
        ORDER BY
            CASE WHEN uw.next_review IS NOT NULL AND uw.next_review <= ? THEN 0 ELSE 1 END,
            CASE WHEN COALESCE(uw.wrong_streak, 0) > 0 THEN 0 ELSE 1 END,
            CASE uw.status WHEN '模糊' THEN 0 WHEN '巩固' THEN 1 ELSE 2 END,
            CASE WHEN uw.last_reviewed IS NULL OR uw.last_reviewed = '' THEN 0 ELSE 1 END,
            uw.next_review ASC,
            uw.last_reviewed ASC,
            COALESCE(uw.wrong_streak, 0) DESC,
            w.frequency DESC,
            w.id ASC
        LIMIT ?
    ''', (today, today, limit)).fetchall()
    result = []
    for row in rows:
        item = _row_to_dict(row)
        item['priority_reason'] = row['priority_reason']
        result.append(item)

    # 证据词不足时才从当前词库补入尚未掌握的词，确保到期词始终优先。
    if len(result) < limit:
        saved = db.execute(
            "SELECT value FROM user_settings WHERE key='current_wordbook'"
        ).fetchone()
        book_id = int(saved['value']) if saved and str(saved['value']).isdigit() else None
        if not book_id:
            book = db.execute(
                "SELECT id FROM wordbooks WHERE is_builtin=1 ORDER BY id LIMIT 1"
            ).fetchone()
            book_id = book['id'] if book else None

        if book_id:
            used_ids = [item['word_id'] for item in result]
            placeholders = ','.join('?' for _ in used_ids)
            exclusion = f"AND w.id NOT IN ({placeholders})" if used_ids else ''
            supplements = db.execute(f'''
                SELECT uw.*, w.id AS word_id, w.word, w.phonetic,
                       w.part_of_speech, w.meanings, w.frequency,
                       '当前词库补充' AS priority_reason
                FROM wordbook_words wbw
                JOIN words w ON w.id = wbw.word_id
                LEFT JOIN user_words uw ON uw.word_id = w.id
                WHERE wbw.wordbook_id = ?
                  AND (uw.status IS NULL OR uw.status != '熟记')
                  {exclusion}
                ORDER BY
                    CASE COALESCE(uw.status, '陌生')
                        WHEN '模糊' THEN 0 WHEN '巩固' THEN 1
                        WHEN '掌握' THEN 2 ELSE 3
                    END,
                    w.frequency DESC,
                    w.id ASC
                LIMIT ?
            ''', (book_id, *used_ids, limit - len(result))).fetchall()
            for row in supplements:
                item = _row_to_dict(row)
                item['word_id'] = row['word_id']
                item['priority_reason'] = row['priority_reason']
                item['status'] = item.get('status') or '陌生'
                result.append(item)
    db.close()
    return result


def get_due_count():
    """获取今日应复习单词总数（用于仪表盘）"""
    db = get_db()
    today = date.today().isoformat()
    count = db.execute(
        "SELECT COUNT(*) as c FROM user_words WHERE next_review <= ? AND status IN ('模糊','巩固','掌握')",
        (today,)
    ).fetchone()['c']
    return count


def record_review(word_id, feedback):
    """记录一次复习反馈（四档），更新次数与连对/连错，不推进节点。

    - recognize → 答对：连对 +1、连错清零
    - vague     → 软过关：连对 +1、不打断连错；标记当日模糊 vague_flagged=1
    - forget    → 答错：首错 next_review=今天（错词必复现），连错 2 次降级
    - mastered  → 直接毕业：status=熟记, stage=99, next_review=NULL
    推进由 review-word-complete（advance_word）触发。
    返回 dict 或 None（词不存在）。
    """
    db = get_db()
    uw = db.execute("SELECT * FROM user_words WHERE word_id=?", (word_id,)).fetchone()
    if not uw:
        return None

    today = date.today()
    today_iso = today.isoformat()

    # 清理隔日的陈旧模糊标记（标记只在“当日一轮”内有效）
    if (uw['last_reviewed'] or '') != today_iso and uw['vague_flagged']:
        db.execute("UPDATE user_words SET vague_flagged=0 WHERE word_id=?", (word_id,))
        db.commit()

    if feedback == 'mastered':
        # 直接毕业，彻底出队
        db.execute('''
            UPDATE user_words SET status='熟记', ebbinghaus_stage=99, next_review=NULL,
                review_count=review_count+1, correct_count=correct_count+1,
                wrong_streak=0, last_reviewed=?
            WHERE word_id=?
        ''', (today_iso, word_id))
        db.commit()
        return {'status': '熟记', 'graduated': True, 'degraded': False}

    if feedback == 'vague':
        # 软过关：连对 +1、不打断 wrong_streak，标记当日模糊
        db.execute('''
            UPDATE user_words SET
                review_count = review_count + 1,
                consecutive_correct = consecutive_correct + 1,
                last_reviewed = ?,
                vague_flagged = 1
            WHERE word_id = ?
        ''', (today_iso, word_id))
        db.commit()
        return {'status': uw['status'], 'soft_pass': True, 'wrong_streak': uw['wrong_streak'] or 0}

    if feedback == 'recognize':
        db.execute('''
            UPDATE user_words SET
                review_count = review_count + 1,
                correct_count = correct_count + 1,
                wrong_streak = 0,
                last_reviewed = ?
            WHERE word_id = ?
        ''', (today_iso, word_id))
        db.commit()
        return {'status': uw['status'], 'degraded': False, 'wrong_streak': 0}

    # forget：答错路径
    wrong_streak = (uw['wrong_streak'] or 0) + 1
    if wrong_streak >= 2:
        result = degrade_word(word_id)
        return {
            'status': result['status'],
            'degraded': True,
            'wrong_streak': wrong_streak,
            'next_review': result['next_review'],
        }

    # 首错：错词必复现兜底 → next_review=今天（当日持续在到期队列，直到答对）
    db.execute('''
        UPDATE user_words SET
            review_count = review_count + 1,
            consecutive_correct = 0,
            wrong_streak = ?,
            last_reviewed = ?,
            next_review = ?
        WHERE word_id = ?
    ''', (wrong_streak, today_iso, today_iso, word_id))
    db.commit()
    return {'status': uw['status'], 'degraded': False, 'wrong_streak': wrong_streak, 'next_review': today_iso}


def advance_word(word_id):
    """完成一轮复习 → 推进 1 格（幂等：同词同天只推进一次）。

    若本轮标过模糊（vague_flagged）：不推进 stage，next_review 取当前 stage 的间隔
    （原地巩固，下次间隔不增长），并清除标记。
    否则正常推进：当前状态内最后一格通过 → 升入下一状态（模糊→巩固→掌握）；
    掌握最后一格 → 熟记自动毕业（next_review=NULL 彻底出队）。
    仅当词今天仍到期（尚未推进过）时推进，重复调用返回 skipped。
    返回 dict 或 None（词不存在 / 状态不可推进）。
    """
    db = get_db()
    uw = db.execute("SELECT * FROM user_words WHERE word_id=?", (word_id,)).fetchone()
    if not uw:
        return None
    status = uw['status']
    if status not in INTERVAL_STATUSES:
        return None

    today = date.today()
    # 幂等 / 每日上限：今天已推进过的词 next_review 在未来，直接跳过
    if uw['next_review'] and uw['next_review'] > today.isoformat():
        return {'skipped': True, 'status': status}

    freq = _word_frequency(db, word_id)
    stage = uw['ebbinghaus_stage'] or 0
    intervals = _intervals_for(status, freq)

    # 本轮标过模糊 → 原地巩固（下次间隔取当前 stage 间隔、不推进），并清标记
    if uw['vague_flagged'] and (uw['last_reviewed'] or '') == today.isoformat():
        next_review = (today + timedelta(days=intervals[stage])).isoformat()
        db.execute('''
            UPDATE user_words SET next_review=?, vague_flagged=0
            WHERE word_id=?
        ''', (next_review, word_id))
        db.commit()
        return {'status': status, 'stage': stage, 'next_review': next_review,
                'graduated': False, 'consolidated': True}

    new_stage = stage + 1
    if new_stage >= len(intervals):
        # 走完当前状态全部节点 → 升入下一状态
        next_status = PROMOTE_STATUS[status]
        if next_status == '熟记':
            db.execute('''
                UPDATE user_words SET status='熟记', ebbinghaus_stage=99, next_review=NULL
                WHERE word_id=?
            ''', (word_id,))
            db.commit()
            return {'status': '熟记', 'stage': 99, 'next_review': None, 'graduated': True}

        next_intervals = _intervals_for(next_status, freq)
        next_review = (today + timedelta(days=next_intervals[0])).isoformat()
        db.execute('''
            UPDATE user_words SET status=?, ebbinghaus_stage=0, next_review=?
            WHERE word_id=?
        ''', (next_status, next_review, word_id))
        db.commit()
        return {'status': next_status, 'stage': 0, 'next_review': next_review, 'graduated': False}

    # 状态内推进 1 格
    next_review = (today + timedelta(days=intervals[new_stage])).isoformat()
    db.execute('''
        UPDATE user_words SET ebbinghaus_stage=?, next_review=?
        WHERE word_id=?
    ''', (new_stage, next_review, word_id))
    db.commit()
    return {'status': status, 'stage': new_stage, 'next_review': next_review, 'graduated': False}


def degrade_word(word_id):
    """连续答错 2 次 → 降级：模糊重置第 1 天 / 巩固降回模糊 / 掌握降回巩固。"""
    db = get_db()
    uw = db.execute("SELECT * FROM user_words WHERE word_id=?", (word_id,)).fetchone()
    if not uw:
        return None

    target = DEGRADE_STATUS.get(uw['status'], uw['status'])
    next_review = (date.today() + timedelta(days=1)).isoformat()
    db.execute('''
        UPDATE user_words SET status=?, ebbinghaus_stage=0, next_review=?, wrong_streak=0
        WHERE word_id=?
    ''', (target, next_review, word_id))
    db.commit()
    return {'status': target, 'stage': 0, 'next_review': next_review}


def init_new_word(word_id):
    """新学单词：初始化艾宾浩斯，按考频定首个间隔（高频快线 / 低频慢线）"""
    db = get_db()
    freq = _word_frequency(db, word_id)
    today = date.today()
    next_review = (today + timedelta(days=_intervals_for('模糊', freq)[0])).isoformat()

    db.execute('''
        INSERT INTO user_words (word_id, status, ebbinghaus_stage, next_review, last_reviewed, consecutive_correct)
        VALUES (?, '陌生', 0, ?, ?, 0)
        ON CONFLICT(word_id) DO UPDATE SET
            ebbinghaus_stage = 0,
            next_review = ?,
            last_reviewed = ?,
            consecutive_correct = 0
    ''', (word_id, next_review, today.isoformat(), next_review, today.isoformat()))
    db.commit()


def promote_to_fuzzy(word_id):
    """学习板块：陌生 → 模糊，明天起纳入复习。

    首次生效（陌生→模糊）时把该词计入「今日已学新词」（study_logs.new_words_count+1），
    重复调用（已非陌生）不重复计数，保证幂等。
    """
    db = get_db()
    today = date.today()
    next_review = (today + timedelta(days=1)).isoformat()
    cursor = db.execute('''
        UPDATE user_words SET status='模糊', ebbinghaus_stage=0, next_review=?
        WHERE word_id=? AND status='陌生'
    ''', (next_review, word_id))
    if cursor.rowcount > 0:
        today_iso = today.isoformat()
        db.execute('''
            INSERT INTO study_logs (study_date, new_words_count)
            VALUES (?, 1)
            ON CONFLICT(study_date) DO UPDATE SET new_words_count = new_words_count + 1
        ''', (today_iso,))
    db.commit()


def preview_review(word_id):
    """四档反馈的预期间隔预览（纯计算，不写库）。

    按当前 status/stage/freq 计算：
    - recognize → 正常推进 1 格后的下次间隔
    - vague     → 原地巩固（当前 stage 间隔）
    - forget    → 今日复现（错词必复现）
    - mastered  → 毕业
    返回 dict 或 None（词不存在）。
    """
    db = get_db()
    uw = db.execute("SELECT * FROM user_words WHERE word_id=?", (word_id,)).fetchone()
    if not uw:
        return None
    status = uw['status']
    freq = _word_frequency(db, word_id)
    today = date.today()
    stage = uw['ebbinghaus_stage'] or 0

    result = {
        'status': status,
        'stage': stage,
        'frequency': freq,
    }
    if status not in INTERVAL_STATUSES:
        result.update({
            'recognize': {'days': None, 'label': '—'},
            'vague': {'days': None, 'label': '—'},
            'forget': {'days': 0, 'label': '今日复现'},
            'mastered': {'days': None, 'label': '毕业'},
        })
        return result

    intervals = _intervals_for(status, freq)

    # recognize：正常推进 1 格
    new_stage = stage + 1
    if new_stage >= len(intervals):
        next_status = PROMOTE_STATUS[status]
        if next_status == '熟记':
            recognize = {'status': '熟记', 'days': None, 'label': '毕业'}
        else:
            days = _intervals_for(next_status, freq)[0]
            recognize = {'status': next_status, 'days': days, 'label': f'{days} 天后'}
    else:
        recognize = {'status': status, 'days': intervals[new_stage], 'label': f'{intervals[new_stage]} 天后'}

    vague_days = intervals[stage]
    result.update({
        'recognize': recognize,
        'vague': {'status': status, 'days': vague_days, 'label': f'{vague_days} 天后'},
        'forget': {'days': 0, 'label': '今日复现'},
        'mastered': {'status': '熟记', 'days': None, 'label': '毕业'},
    })
    return result


def _row_to_dict(r):
    import json
    return {
        'word_id': r['word_id'],
        'word': r['word'],
        'phonetic': r['phonetic'],
        'part_of_speech': r['part_of_speech'],
        'meanings': r['meanings'],
        'frequency': r['frequency'],
        'status': r['status'],
        'review_count': r['review_count'],
        'ebbinghaus_stage': r['ebbinghaus_stage'],
        'next_review': r['next_review'],
    }

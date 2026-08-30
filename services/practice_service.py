"""专项整轮记录与可审计评分。"""

import json
from datetime import date

from database import get_db


MODULE_LOG_COLUMNS = {
    'reading': 'reading_count',
    'listening': 'listening_count',
    'writing': 'writing_count',
    'vocabulary': 'vocabulary_count',
}


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def adjusted_objective_score(correct_count, total_count, difficulty):
    """客观题正确率按难度1-6进行最多12分的小幅校正。"""
    if not total_count:
        return 0.0
    accuracy = correct_count / total_count * 100
    return round(clamp(accuracy + (clamp(int(difficulty), 1, 6) - 3) * 4), 1)


def record_practice_session(*, module, activity_type, source_id='', difficulty=3,
                            correct_count=0, total_count=0, raw_score=0,
                            duration_seconds=0, response_ms=0, metadata=None,
                            origin='practice', idempotency_key):
    """幂等写入一次完整训练，并更新每日历史汇总。"""
    db = get_db()
    existing = db.execute(
        "SELECT * FROM practice_sessions WHERE idempotency_key=?", (idempotency_key,)
    ).fetchone()
    if existing:
        result = dict(existing)
        db.close()
        result['duplicate'] = True
        return result

    difficulty = int(clamp(int(difficulty or 3), 1, 6))
    duration_seconds = int(clamp(int(duration_seconds or 0), 0, 7200))
    response_ms = int(clamp(int(response_ms or 0), 0, 300000))
    db.execute('''
        INSERT INTO practice_sessions
        (module, activity_type, source_id, difficulty, correct_count, total_count,
         raw_score, duration_seconds, response_ms, metadata_json, origin, idempotency_key)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        module, activity_type, str(source_id or ''), difficulty,
        max(0, int(correct_count or 0)), max(0, int(total_count or 0)),
        round(clamp(float(raw_score or 0)), 1), duration_seconds, response_ms,
        json.dumps(metadata or {}, ensure_ascii=False), origin, idempotency_key,
    ))
    session_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
    column = MODULE_LOG_COLUMNS.get(module)
    if column:
        minutes = min(120, max(1, round(duration_seconds / 60))) if duration_seconds else 1
        today = date.today().isoformat()
        db.execute(f'''
            INSERT INTO study_logs (study_date, {column}, total_minutes)
            VALUES (?, 1, ?)
            ON CONFLICT(study_date) DO UPDATE SET
                {column} = {column} + 1,
                total_minutes = total_minutes + ?
        ''', (today, minutes, minutes))
    db.commit()
    row = db.execute("SELECT * FROM practice_sessions WHERE id=?", (session_id,)).fetchone()
    result = dict(row)
    db.close()

    from services.level_service import calculate_level
    calculate_level(reason=f'{module}:{activity_type}')
    result['duplicate'] = False
    return result


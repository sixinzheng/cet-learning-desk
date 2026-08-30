"""仔细阅读未读库存、校验与 DeepSeek 后台补库。"""

from datetime import datetime
import hashlib
import json
import os
import re
import threading

from config import get_api_key
from database import BASE_DIR, get_db
from seed.reading_catalog import (
    DIFFICULTIES,
    GENERATOR_VERSION,
    TARGET_UNREAD_PER_CELL,
    TOPICS,
    ensure_reading_inventory_jobs,
)
from seed.reading_corpus_loader import approved_reading_corpus_available
from services.ai_service import (
    AIServiceError,
    calculate_usage_cost,
    current_month_tracked_cost,
    generate_reading_article_package,
)
from services.reading_sources import SourceFetchError, discover_candidates, fetch_fact_brief


MONTHLY_BUDGET_CNY = 5.0
PREFLIGHT_RESERVE_CNY = 0.02
_worker_lock = threading.Lock()
_worker = None


def _policy():
    path = os.path.join(BASE_DIR, 'resources', 'reading_generation_policy.json')
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def _setting(db, key, default=''):
    row = db.execute("SELECT value FROM user_settings WHERE key=?", (key,)).fetchone()
    return row['value'] if row else default


def _set_setting(db, key, value):
    db.execute("INSERT OR REPLACE INTO user_settings (key,value) VALUES (?,?)", (key, str(value)))


def _article_is_unread_sql(alias='a'):
    return (
        f"{alias}.inventory_status='available' AND NOT EXISTS ("
        f"SELECT 1 FROM practice_sessions p WHERE p.module='reading' "
        f"AND CAST(p.source_id AS TEXT)=CAST({alias}.id AS TEXT))"
    )


def inventory_snapshot(db=None):
    close = db is None
    db = db or get_db()
    ensure_reading_inventory_jobs(db)
    db.commit()
    cells = []
    for topic in TOPICS:
        for difficulty in DIFFICULTIES:
            ready = db.execute(
                f"""SELECT COUNT(*) AS c FROM reading_articles a
                    WHERE a.question_type='careful_reading' AND a.topic=? AND a.difficulty=?
                      AND {_article_is_unread_sql('a')}
                      AND (SELECT COUNT(*) FROM reading_questions q WHERE q.article_id=a.id)=5""",
                (topic, difficulty),
            ).fetchone()['c']
            job_rows = db.execute(
                """SELECT status,COUNT(*) AS c FROM reading_generation_jobs
                   WHERE topic=? AND difficulty=? AND question_type='careful_reading'
                   GROUP BY status""",
                (topic, difficulty),
            ).fetchall()
            jobs = {row['status']: row['c'] for row in job_rows}
            cells.append({
                'topic': topic, 'difficulty': difficulty, 'ready': ready,
                'target': TARGET_UNREAD_PER_CELL,
                'pending': sum(jobs.get(key, 0) for key in ('pending', 'running', 'paused_budget', 'paused_config')),
                'failed': jobs.get('failed', 0),
            })
    completed = db.execute(
        "SELECT COUNT(DISTINCT source_id) AS c FROM practice_sessions WHERE module='reading'"
    ).fetchone()['c']
    statuses = db.execute(
        "SELECT status,COUNT(*) AS c FROM reading_generation_jobs GROUP BY status"
    ).fetchall()
    status_counts = {row['status']: row['c'] for row in statuses}
    corpus_approved = approved_reading_corpus_available()
    corpus_target = len(TOPICS) * len(DIFFICULTIES) * TARGET_UNREAD_PER_CELL
    result = {
        'topics': list(TOPICS), 'difficulties': list(DIFFICULTIES), 'cells': cells,
        'totals': {
            'target': len(TOPICS) * len(DIFFICULTIES) * TARGET_UNREAD_PER_CELL,
            'ready': sum(cell['ready'] for cell in cells),
            'pending': sum(cell['pending'] for cell in cells),
            'failed': sum(cell['failed'] for cell in cells),
            'completed_history': completed,
        },
        'refill': {
            'enabled': corpus_approved and _setting(db, 'reading_refill_enabled', '0') == '1',
            'monthly_budget_cny': MONTHLY_BUDGET_CNY,
            'month_spend_cny': current_month_tracked_cost(),
            'status_counts': status_counts,
        },
        'curation': {
            'approved': corpus_approved,
            'approved_articles': corpus_target if corpus_approved else 0,
            'target': corpus_target,
        },
    }
    if close:
        db.close()
    return result


def enable_refill():
    if not approved_reading_corpus_available():
        return False
    db = get_db()
    _set_setting(db, 'reading_refill_enabled', '1')
    ensure_reading_inventory_jobs(db)
    db.execute(
        """UPDATE reading_generation_jobs AS j
           SET status='pending',last_error='',updated_at=datetime('now','localtime')
           WHERE status IN ('paused_budget','paused_config') AND attempts<max_attempts
             AND (SELECT COUNT(*) FROM reading_articles a
                  WHERE a.question_type='careful_reading' AND a.topic=j.topic AND a.difficulty=j.difficulty
                    AND a.inventory_status='available'
                    AND NOT EXISTS (
                        SELECT 1 FROM practice_sessions p WHERE p.module='reading'
                          AND CAST(p.source_id AS TEXT)=CAST(a.id AS TEXT)
                    )
                    AND (SELECT COUNT(*) FROM reading_questions q WHERE q.article_id=a.id)=5
                 ) < ?""",
        (TARGET_UNREAD_PER_CELL,),
    )
    db.commit()
    db.close()
    return start_refill_worker()


def schedule_replacement(article_id, topic, difficulty):
    db = get_db()
    db.execute(
        "UPDATE reading_articles SET inventory_status='completed' WHERE id=?",
        (article_id,),
    )
    db.execute(
        """INSERT OR IGNORE INTO reading_generation_jobs
           (topic,difficulty,question_type,idempotency_key)
           VALUES (?,?,'careful_reading',?)""",
        (topic, difficulty, f'replace:{article_id}'),
    )
    enabled = _setting(db, 'reading_refill_enabled', '0') == '1'
    db.commit()
    db.close()
    if enabled:
        start_refill_worker()


def _source_overlap(content, source_text, window=8):
    def words(value):
        return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", value.lower())
    generated, source = words(content), words(source_text)
    source_windows = {tuple(source[index:index + window]) for index in range(max(0, len(source) - window + 1))}
    return any(
        tuple(generated[index:index + window]) in source_windows
        for index in range(max(0, len(generated) - window + 1))
    )


def _validate_package(package, difficulty, source_brief, db):
    policy = _policy()
    title = str(package.get('title') or '').strip()
    content = str(package.get('content') or '').strip()
    questions = package.get('questions') or []
    if not title or not content:
        raise ValueError('文章标题或正文为空。')
    word_count = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", content))
    bounds = policy['difficulty_levels'][str(difficulty)]['target_words']
    if word_count < bounds[0] or word_count > bounds[1]:
        raise ValueError(f'文章长度 {word_count} 词，不在该难度 {bounds[0]}–{bounds[1]} 词范围。')
    digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
    if db.execute("SELECT 1 FROM reading_articles WHERE content_hash=? LIMIT 1", (digest,)).fetchone():
        raise ValueError('文章内容与现有题库重复。')
    if _source_overlap(content, source_brief.get('fact_brief', ''), 8):
        raise ValueError('文章保留了过长的来源原句。')
    if len(questions) != 5:
        raise ValueError('仔细阅读必须恰好包含 5 道题。')
    cleaned, seen = [], set()
    allowed_types = set(policy['question_types']['careful_reading']['formats'])
    for item in questions:
        question = str(item.get('question') or '').strip()
        options = [str(value).strip() for value in item.get('options') or []]
        answer = str(item.get('answer') or '').strip().upper()
        explanation = str(item.get('explanation') or '').strip()
        evidence = str(item.get('evidence_text') or '').strip()
        question_type = str(item.get('type') or 'detail').strip()
        if question_type not in allowed_types:
            raise ValueError('题型不在仔细阅读允许范围内。')
        if not question or question.lower() in seen:
            raise ValueError('题干为空或重复。')
        if len(options) != 4 or any(not value for value in options) or len(set(options)) != 4:
            raise ValueError('每题必须有 4 个不重复的选项。')
        if answer not in ('A', 'B', 'C', 'D') or not explanation or not evidence:
            raise ValueError('答案、中文解析或原文证据不完整。')
        if not re.search(r'[\u4e00-\u9fff]', explanation):
            raise ValueError('每题解析必须包含中文说明。')
        if content.count(evidence) != 1:
            raise ValueError('题目证据必须在原创文章中精确且唯一定位。')
        seen.add(question.lower())
        cleaned.append({
            'type': question_type, 'question': question, 'options': options,
            'answer': answer, 'explanation': explanation, 'evidence_text': evidence,
        })
    if len({item['type'] for item in cleaned}) < 4:
        raise ValueError('单篇仔细阅读必须覆盖至少四类认知题型。')
    inference_count = sum(item['type'] == 'inference' for item in cleaned)
    inference_bounds = policy['difficulty_levels'][str(difficulty)]['inference_questions']
    if not inference_bounds[0] <= inference_count <= inference_bounds[1]:
        raise ValueError('推理题数量不符合该难度要求。')
    return {'title': title, 'content': content, 'word_count': word_count, 'content_hash': digest, 'questions': cleaned}


def _claim_job():
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    row = db.execute(
        """SELECT * FROM reading_generation_jobs
           WHERE status='pending' AND attempts<max_attempts ORDER BY created_at,id LIMIT 1"""
    ).fetchone()
    if not row:
        db.commit(); db.close()
        return None
    db.execute(
        """UPDATE reading_generation_jobs SET status='running',attempts=attempts+1,
           updated_at=datetime('now','localtime') WHERE id=?""",
        (row['id'],),
    )
    db.commit(); db.close()
    return dict(row)


def _pause_job(job_id, status, message):
    db = get_db()
    if status in ('paused_config', 'paused_budget'):
        db.execute(
            """UPDATE reading_generation_jobs SET status=?,last_error=?,
               attempts=CASE WHEN attempts>0 THEN attempts-1 ELSE 0 END,
               updated_at=datetime('now','localtime') WHERE id=?""",
            (status, message[:500], job_id),
        )
    else:
        db.execute(
            """UPDATE reading_generation_jobs SET status=?,last_error=?,updated_at=datetime('now','localtime')
               WHERE id=?""",
            (status, message[:500], job_id),
        )
    db.commit(); db.close()


def _fail_job(job, message):
    attempts = int(job['attempts']) + 1
    status = 'failed' if attempts >= int(job.get('max_attempts') or 3) else 'pending'
    _pause_job(job['id'], status, message)


def _reference_samples(db, topic, difficulty, job_id):
    rows = []
    if approved_reading_corpus_available():
        rows = db.execute(
        """SELECT title,content FROM reading_articles
           WHERE origin='curated_corpus' AND topic=? AND difficulty=?
             AND inventory_status='available'
           ORDER BY ((id * 1103515245 + ?) % 2147483647),id LIMIT 2""",
            (topic, difficulty, int(job_id)),
        ).fetchall()
    if not rows:
        rows = db.execute(
            """SELECT title,content FROM reading_articles
               WHERE origin='golden_sample' AND difficulty=? ORDER BY id LIMIT 1""",
            (difficulty,),
        ).fetchall()
    return [{'title': row['title'], 'content': row['content']} for row in rows]


def process_next_job():
    job = _claim_job()
    if not job:
        return False
    if not get_api_key():
        _pause_job(job['id'], 'paused_config', '请先在“我的”配置 DeepSeek API Key。')
        return False
    spend = current_month_tracked_cost()
    if spend + PREFLIGHT_RESERVE_CNY > MONTHLY_BUDGET_CNY:
        _pause_job(job['id'], 'paused_budget', '已达到本月 5 元站内 AI 追踪上限。')
        return False
    db = get_db()
    excluded = [row['source_url'] for row in db.execute(
        "SELECT source_url FROM reading_articles WHERE COALESCE(source_url,'')!=''"
    ).fetchall()]
    sample = _reference_samples(db, job['topic'], job['difficulty'], job['id'])
    db.close()
    try:
        candidates = discover_candidates(job['topic'], excluded)
        if not candidates:
            raise SourceFetchError('白名单来源中暂时没有匹配的新题材。')
        source_brief = None
        for candidate in candidates[:4]:
            try:
                source_brief = fetch_fact_brief(candidate)
                break
            except SourceFetchError:
                continue
        if not source_brief:
            raise SourceFetchError('候选来源均无法提取有效事实。')
        package = generate_reading_article_package(
            topic=job['topic'], difficulty=job['difficulty'], source_brief=source_brief,
            policy=_policy(), golden_sample=sample,
        )
        db = get_db()
        db.execute('BEGIN IMMEDIATE')
        live_job = db.execute("SELECT status FROM reading_generation_jobs WHERE id=?", (job['id'],)).fetchone()
        ready = db.execute(
            f"""SELECT COUNT(*) AS c FROM reading_articles a
                WHERE a.question_type='careful_reading' AND a.topic=? AND a.difficulty=?
                  AND {_article_is_unread_sql('a')}
                  AND (SELECT COUNT(*) FROM reading_questions q WHERE q.article_id=a.id)=5""",
            (job['topic'], job['difficulty']),
        ).fetchone()['c']
        if not live_job or live_job['status'] != 'running' or ready >= TARGET_UNREAD_PER_CELL:
            if live_job and live_job['status'] == 'running':
                db.execute(
                    """UPDATE reading_generation_jobs SET status='completed',
                       last_error='库存已由静态语料补足，未调用本次生成结果',
                       updated_at=datetime('now','localtime'),completed_at=datetime('now','localtime')
                       WHERE id=? AND status='running'""",
                    (job['id'],),
                )
            db.commit(); db.close()
            return True
        validated = _validate_package(package, job['difficulty'], source_brief, db)
        cursor = db.execute(
            """INSERT INTO reading_articles
               (title,source,source_name,content,word_count,difficulty,topic,question_type,date_added,
                source_url,source_title,source_published_at,retrieved_at,adaptation_notes,adaptation_note,
                content_hash,generator_version,origin,inventory_status)
               VALUES (?,?,?,?,?,?,?,'careful_reading',date('now'),?,?,?,datetime('now','localtime'),?,?,?,?,?, 'available')""",
            (
                validated['title'], f'题材参考：{source_brief["source_name"]}', source_brief['source_name'], validated['content'],
                validated['word_count'], job['difficulty'], job['topic'], source_brief['source_url'],
                source_brief['source_title'], source_brief['source_published_at'],
                '依据白名单来源的事实摘要原创改写；非媒体原文，非真题。',
                '依据白名单来源的事实摘要原创改写；非媒体原文，非真题。',
                validated['content_hash'], GENERATOR_VERSION, 'ai_adapted',
            ),
        )
        article_id = cursor.lastrowid
        db.executemany(
            """INSERT INTO reading_questions
               (article_id,question_type,question,options,answer,explanation,evidence_text)
               VALUES (?,?,?,?,?,?,?)""",
            [
                (article_id, item['type'], item['question'], json.dumps(item['options'], ensure_ascii=False),
                 item['answer'], item['explanation'], item['evidence_text'])
                for item in validated['questions']
            ],
        )
        actual_cost = calculate_usage_cost(package.get('_usage'))
        updated = db.execute(
            """UPDATE reading_generation_jobs SET status='completed',source_domain=?,source_url=?,
               actual_cost_cny=?,last_error='',updated_at=datetime('now','localtime'),
               completed_at=datetime('now','localtime') WHERE id=? AND status='running'""",
            (source_brief['source_name'], source_brief['source_url'], actual_cost, job['id']),
        )
        if updated.rowcount != 1:
            db.rollback(); db.close()
            return True
        db.commit(); db.close()
        return True
    except AIServiceError as exc:
        if exc.code in ('not_configured', 'invalid_key'):
            _pause_job(job['id'], 'paused_config', str(exc))
            return False
        if exc.code == 'insufficient_balance':
            _pause_job(job['id'], 'paused_budget', str(exc))
            return False
        _fail_job(job, str(exc))
        return True
    except (SourceFetchError, ValueError, OSError, json.JSONDecodeError) as exc:
        _fail_job(job, str(exc))
        return True


def _worker_main():
    try:
        while True:
            db = get_db()
            enabled = _setting(db, 'reading_refill_enabled', '0') == '1'
            db.close()
            if not enabled or not process_next_job():
                break
    finally:
        global _worker
        with _worker_lock:
            _worker = None


def start_refill_worker():
    global _worker
    with _worker_lock:
        if _worker and _worker.is_alive():
            return False
        _worker = threading.Thread(target=_worker_main, name='reading-refill', daemon=True)
        _worker.start()
        return True


def resume_refill_worker_if_enabled():
    db = get_db()
    enabled = _setting(db, 'reading_refill_enabled', '0') == '1'
    db.close()
    if enabled:
        start_refill_worker()

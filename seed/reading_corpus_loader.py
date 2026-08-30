"""Idempotent loader for the six-shard first-batch reading corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse
import itertools


CORPUS_DIR = Path(__file__).with_name("reading_corpus")
CORPUS_ORIGIN = "curated_corpus"
CORPUS_VERSION = "cet-reading-curator/static-180-v1"
APPROVAL_PATH = CORPUS_DIR / "APPROVED.json"
CORPUS_TOPICS = ("健康", "教育", "文化", "环境", "社会", "科技")
BOUNDS = {1: (180, 230), 2: (210, 260), 3: (240, 300), 4: (270, 330), 5: (300, 370), 6: (330, 420)}
ALLOWED_HOSTS = {"english.news.cn", "www.news.cn", "news.cn", "english.www.gov.cn", "www.gov.cn", "global.chinadaily.com.cn", "www.chinadaily.com.cn", "chinadaily.com.cn", "news.cgtn.com", "www.cgtn.com", "cgtn.com"}


def _hash(content):
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def _word_count(content):
    return len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", content))


def corpus_sha256():
    """Bind approval to the exact six reviewed shards, independent of formatting."""
    digest = hashlib.sha256()
    for topic in CORPUS_TOPICS:
        path = CORPUS_DIR / f"{topic}.json"
        if not path.exists():
            return ""
        payload = json.loads(path.read_text(encoding="utf-8"))
        digest.update(topic.encode("utf-8"))
        digest.update(b"\0")
        digest.update(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        digest.update(b"\0")
    return digest.hexdigest()


def approved_reading_corpus_available():
    if not APPROVAL_PATH.exists():
        return False
    try:
        with APPROVAL_PATH.open(encoding="utf-8") as handle:
            approval = json.load(handle)
    except (OSError, ValueError):
        return False
    return (
        approval.get("corpus_version") == CORPUS_VERSION
        and approval.get("approved_articles") == 180
        and approval.get("corpus_sha256") == corpus_sha256()
    )


def load_reading_corpus(topics):
    articles = []
    for topic in topics:
        path = CORPUS_DIR / f"{topic}.json"
        with path.open(encoding="utf-8") as handle:
            shard = json.load(handle)
        if len(shard) != 30 or any(article.get("topic") != topic for article in shard):
            raise ValueError(f"阅读语料分片结构错误：{path}")
        articles.extend(shard)
    validate_reading_corpus(articles, topics)
    return articles


def validate_reading_corpus(articles, topics):
    """Validate the complete manifest before the first database write."""
    if len(articles) != len(topics) * len(BOUNDS) * 5:
        raise ValueError("静态仔细阅读语料必须恰好包含 180 篇。")
    ids, titles, hashes, source_urls, source_titles, question_stems, question_gram_sets, cells = (
        set(), set(), set(), set(), set(), set(), [], {}
    )
    for article in articles:
        required = ("corpus_id", "title", "content", "topic", "difficulty", "source_name", "source_url", "source_title", "source_published_at", "retrieved_at", "source_verification", "adaptation_note", "questions")
        if any(not article.get(field) for field in required):
            raise ValueError(f"静态语料字段不完整：{article.get('corpus_id') or article.get('title')}")
        corpus_id, title, digest = article["corpus_id"], article["title"], _hash(article["content"])
        if corpus_id in ids or title in titles or digest in hashes:
            raise ValueError(f"静态语料存在重复：{corpus_id}")
        ids.add(corpus_id); titles.add(title); hashes.add(digest)
        topic, difficulty = article["topic"], int(article["difficulty"])
        if topic not in topics or difficulty not in BOUNDS:
            raise ValueError(f"静态语料主题或难度错误：{corpus_id}")
        cells[(topic, difficulty)] = cells.get((topic, difficulty), 0) + 1
        low, high = BOUNDS[difficulty]
        if not low <= _word_count(article["content"]) <= high:
            raise ValueError(f"静态语料词数越界：{corpus_id}")
        parsed = urlparse(article["source_url"])
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise ValueError(f"静态语料来源不在白名单：{corpus_id}")
        normalized_source_title = re.sub(r"\s+", " ", article["source_title"].strip()).casefold()
        if article["source_url"] in source_urls or normalized_source_title in source_titles:
            raise ValueError(f"静态语料必须一篇对应一个独立事实来源：{corpus_id}")
        source_urls.add(article["source_url"])
        source_titles.add(normalized_source_title)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", article["source_published_at"]):
            raise ValueError(f"静态语料来源发布日期错误：{corpus_id}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", article["retrieved_at"]):
            raise ValueError(f"静态语料检索日期错误：{corpus_id}")
        if "本站" not in article["adaptation_note"] or "非历年真题" not in article["adaptation_note"]:
            raise ValueError(f"静态语料原创声明不完整：{corpus_id}")
        questions = article["questions"]
        if len(questions) != 5 or len({item.get("type") for item in questions}) < 4:
            raise ValueError(f"静态语料题型结构错误：{corpus_id}")
        inference_count = sum(item.get("type") == "inference" for item in questions)
        expected = {1: (0, 1), 2: (1, 1), 3: (1, 2), 4: (1, 2), 5: (2, 2), 6: (2, 3)}[difficulty]
        if not expected[0] <= inference_count <= expected[1]:
            raise ValueError(f"静态语料推理题数量错误：{corpus_id}")
        for question_index, item in enumerate(questions, start=1):
            normalized_stem = re.sub(r"[^a-z0-9]+", " ", (item.get("question") or "").casefold()).strip()
            if not normalized_stem or normalized_stem in question_stems:
                raise ValueError(f"静态语料题干重复：{corpus_id}")
            question_stems.add(normalized_stem)
            stem_tokens = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", (item.get("question") or "").casefold())
            question_gram_sets.append(
                (f"{corpus_id}:Q{question_index}", set(zip(*(stem_tokens[offset:] for offset in range(5)))))
            )
            options = item.get("options") or []
            if len(options) != 4 or len(set(options)) != 4 or item.get("answer") not in "ABCD":
                raise ValueError(f"静态语料选项契约错误：{corpus_id}")
            if not re.search(r"[\u4e00-\u9fff]", item.get("explanation") or ""):
                raise ValueError(f"静态语料缺少中文解析：{corpus_id}")
            if article["content"].count(item.get("evidence_text") or "") != 1:
                raise ValueError(f"静态语料证据无法精确唯一定位：{corpus_id}")
    if set(cells) != {(topic, level) for topic in topics for level in BOUNDS} or any(value != 5 for value in cells.values()):
        raise ValueError("静态语料矩阵不是 6×6×5。")
    gram_sets = []
    for article in articles:
        tokens = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", article["content"].lower())
        gram_sets.append((article["corpus_id"], set(zip(*(tokens[offset:] for offset in range(5))))))
    for (left_id, left), (right_id, right) in itertools.combinations(gram_sets, 2):
        similarity = len(left & right) / max(1, len(left | right))
        if similarity > 0.12:
            raise ValueError(f"静态语料近重复：{left_id} / {right_id} ({similarity:.3f})")
    for (left_id, left), (right_id, right) in itertools.combinations(question_gram_sets, 2):
        similarity = len(left & right) / max(1, len(left | right))
        if similarity > 0.12:
            raise ValueError(f"静态语料题干近重复：{left_id} / {right_id} ({similarity:.3f})")


def seed_static_reading_corpus(conn, topics, difficulties, target_per_cell):
    """Import all 180 references while preserving completed rows and user history."""
    corpus = load_reading_corpus(topics)
    by_cell = {(topic, level): [] for topic in topics for level in difficulties}
    for article in corpus:
        by_cell[(article["topic"], int(article["difficulty"]))].append(article)

    inserted = 0
    conn.execute("SAVEPOINT static_reading_corpus")
    try:
      # Once the reviewed 180 is approved, legacy/golden rows stay queryable as
      # references but must not inflate the five-unread-per-cell inventory.
      conn.execute(
          """UPDATE reading_articles SET inventory_status='reference_only'
             WHERE origin!=? AND inventory_status='available'
               AND NOT EXISTS (
                   SELECT 1 FROM practice_sessions p WHERE p.module='reading'
                     AND CAST(p.source_id AS TEXT)=CAST(reading_articles.id AS TEXT)
               )""",
          (CORPUS_ORIGIN,),
      )
      for topic in topics:
        for difficulty in difficulties:
          for article in by_cell[(topic, difficulty)]:
            digest = _hash(article["content"])
            exists = conn.execute(
                    "SELECT 1 FROM reading_articles WHERE corpus_id=? OR content_hash=? LIMIT 1",
                    (article["corpus_id"], digest),
                ).fetchone()
            if exists:
                continue
            cursor = conn.execute(
                    """INSERT INTO reading_articles
                       (corpus_id,title,source,source_name,source_verification,content,word_count,difficulty,topic,question_type,date_added,
                        source_url,source_title,source_published_at,retrieved_at,adaptation_notes,adaptation_note,
                        content_hash,generator_version,origin,inventory_status)
                       VALUES (?,?,?,?,?, ?,?,?,?,'careful_reading',date('now'), ?,?,?,?,?,?, ?,?,?, 'available')""",
                    (
                        article["corpus_id"], article["title"], f'题材参考：{article["source_name"]}', article["source_name"],
                        article["source_verification"], article["content"], _word_count(article["content"]), difficulty, topic,
                        article["source_url"], article["source_title"], article["source_published_at"],
                        article["retrieved_at"], article["adaptation_note"], article["adaptation_note"],
                        digest, CORPUS_VERSION, CORPUS_ORIGIN,
                    ),
                )
            article_id = cursor.lastrowid
            conn.executemany(
                    """INSERT INTO reading_questions
                       (article_id,question_type,question,options,answer,explanation,evidence_text)
                       VALUES (?,?,?,?,?,?,?)""",
                    [
                        (
                            article_id, item["type"], item["question"],
                            json.dumps(item["options"], ensure_ascii=False), item["answer"],
                            item["explanation"], item["evidence_text"],
                        )
                        for item in article["questions"]
                    ],
                )
            inserted += 1

            # Static rows can satisfy jobs created by an older application run.
            # Keep those rows as audit history instead of deleting the queue.
          ready = conn.execute(
                """SELECT COUNT(*) AS c FROM reading_articles a
                   WHERE a.question_type='careful_reading' AND a.topic=? AND a.difficulty=?
                     AND a.origin=? AND a.inventory_status='available'
                     AND NOT EXISTS (
                         SELECT 1 FROM practice_sessions p WHERE p.module='reading'
                           AND CAST(p.source_id AS TEXT)=CAST(a.id AS TEXT)
                     )
                     AND (SELECT COUNT(*) FROM reading_questions q WHERE q.article_id=a.id)=5""",
                (topic, difficulty, CORPUS_ORIGIN),
            ).fetchone()["c"]
          remaining_need = max(0, target_per_cell - ready)
          active = conn.execute(
                """SELECT id FROM reading_generation_jobs
                   WHERE topic=? AND difficulty=? AND question_type='careful_reading'
                     AND status IN ('pending','running','paused_budget','paused_config')
                   ORDER BY CASE WHEN idempotency_key LIKE 'bootstrap:%' THEN 0 ELSE 1 END,id""",
                (topic, difficulty),
            ).fetchall()
          close_count = max(0, len(active) - remaining_need)
          for row in active[:close_count]:
            conn.execute(
                    """UPDATE reading_generation_jobs
                       SET status='completed',last_error='静态首批语料已满足该库存槽位',
                           updated_at=datetime('now','localtime'),completed_at=datetime('now','localtime')
                       WHERE id=?""",
                (row["id"],),
            )
      conn.execute("RELEASE SAVEPOINT static_reading_corpus")
    except Exception:
      conn.execute("ROLLBACK TO SAVEPOINT static_reading_corpus")
      conn.execute("RELEASE SAVEPOINT static_reading_corpus")
      raise
    return inserted

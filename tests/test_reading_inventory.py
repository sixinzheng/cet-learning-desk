import os
import json
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import database
from app import create_app
from seed.reading_catalog import DIFFICULTIES, GOLDEN_ARTICLES, TARGET_UNREAD_PER_CELL, TOPICS
from seed.reading_corpus_loader import CORPUS_ORIGIN, approved_reading_corpus_available, load_reading_corpus, seed_static_reading_corpus
from services.reading_inventory_service import _reference_samples, enable_refill, inventory_snapshot, process_next_job, schedule_replacement
from services.reading_sources import SourceFetchError, secure_fetch


class ReadingInventoryContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "reading-inventory.db")
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_rank_catalog_contains_ten_traceable_levels(self):
        response = self.client.get("/api/level/detail")
        self.assertEqual(response.status_code, 200)
        catalog = response.get_json()["rank_catalog"]
        self.assertEqual([item["rank"] for item in catalog], list(range(1, 11)))
        for item in catalog:
            self.assertTrue(item["name"])
            self.assertTrue(item["positioning"])
            self.assertIn("target_score", item)
            self.assertIn("word_thresholds", item)
            self.assertIn(item["state"], {"reached", "current", "next", "locked"})

    def test_bootstrap_matrix_has_six_topics_six_levels_and_180_target_slots(self):
        snapshot = inventory_snapshot()
        self.assertEqual(snapshot["topics"], list(TOPICS))
        self.assertEqual(snapshot["difficulties"], list(DIFFICULTIES))
        self.assertEqual(len(snapshot["cells"]), 36)
        self.assertEqual(snapshot["totals"]["target"], 180)
        if approved_reading_corpus_available():
            self.assertEqual(snapshot["totals"]["ready"], 180)
            self.assertEqual(snapshot["totals"]["pending"], 0)
        else:
            self.assertEqual(snapshot["totals"]["ready"], 6)
            self.assertEqual(snapshot["totals"]["pending"], 174)
        self.assertTrue(all(
            cell["ready"] + cell["pending"] == TARGET_UNREAD_PER_CELL
            for cell in snapshot["cells"]
        ))
        self.assertEqual(snapshot["curation"]["target"], 180)
        self.assertEqual(snapshot["curation"]["approved"], approved_reading_corpus_available())
        self.assertEqual(
            snapshot["curation"]["approved_articles"],
            180 if approved_reading_corpus_available() else 0,
        )

    @unittest.skipIf(approved_reading_corpus_available(), "正式语料批准后自动补库恢复正常")
    def test_refill_cannot_be_enabled_before_corpus_approval(self):
        self.assertFalse(enable_refill())
        snapshot = inventory_snapshot()
        self.assertFalse(snapshot["curation"]["approved"])
        self.assertFalse(snapshot["refill"]["enabled"])
        db = database.get_db()
        value = db.execute(
            "SELECT value FROM user_settings WHERE key='reading_refill_enabled'"
        ).fetchone()["value"]
        db.close()
        self.assertEqual(value, "0")

    def test_six_careful_reading_samples_meet_level_bounds_and_evidence_contract(self):
        with open(os.path.join(os.path.dirname(database.__file__), "resources", "reading_generation_policy.json"), encoding="utf-8") as handle:
            policy = json.load(handle)
        self.assertEqual(len(GOLDEN_ARTICLES), 6)
        for article in GOLDEN_ARTICLES:
            words = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", article["content"]))
            low, high = policy["difficulty_levels"][str(article["difficulty"])]["target_words"]
            self.assertGreaterEqual(words, low, article["title"])
            self.assertLessEqual(words, high, article["title"])
            self.assertEqual(len(article["questions"]), 5)
            for _, _, options, answer, explanation, evidence in article["questions"]:
                self.assertEqual(len(options), 4)
                self.assertEqual(len(set(options)), 4)
                self.assertIn(answer, "ABCD")
                self.assertTrue(explanation)
                self.assertIn(evidence.lower(), article["content"].lower())

    @unittest.skipUnless(approved_reading_corpus_available(), "180篇人工策展语料尚未批准，不得作为正式 corpus 测试")
    def test_static_corpus_has_exact_matrix_and_full_contract(self):
        with open(os.path.join(os.path.dirname(database.__file__), "resources", "reading_generation_policy.json"), encoding="utf-8") as handle:
            policy = json.load(handle)
        corpus = load_reading_corpus(TOPICS)
        self.assertEqual(len(corpus), 180)
        self.assertEqual(len({article["title"] for article in corpus}), 180)
        self.assertEqual(len({article["content"] for article in corpus}), 180)
        counts = {}
        answer_counts = {letter: 0 for letter in "ABCD"}
        for article in corpus:
            cell = (article["topic"], article["difficulty"])
            counts[cell] = counts.get(cell, 0) + 1
            words = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", article["content"]))
            low, high = policy["difficulty_levels"][str(article["difficulty"])]["target_words"]
            self.assertGreaterEqual(words, low, article["title"])
            self.assertLessEqual(words, high, article["title"])
            self.assertTrue(article["source_url"].startswith("https://"))
            self.assertIn(article["source_url"].split("/")[2], policy["source_policy"]["allowed_hosts"])
            for field in ("source_name", "source_title", "source_published_at", "retrieved_at", "adaptation_note"):
                self.assertTrue(article[field], f'{article["title"]}: {field}')
            self.assertIn("本站", article["adaptation_note"])
            self.assertIn("非历年真题", article["adaptation_note"])
            questions = article["questions"]
            self.assertEqual(len(questions), 5)
            self.assertGreaterEqual(len({item["type"] for item in questions}), 4)
            inference_count = sum(item["type"] == "inference" for item in questions)
            expected = policy["difficulty_levels"][str(article["difficulty"])]["inference_questions"]
            self.assertGreaterEqual(inference_count, expected[0])
            self.assertLessEqual(inference_count, expected[1])
            for item in questions:
                self.assertEqual(len(item["options"]), 4)
                self.assertEqual(len(set(item["options"])), 4)
                self.assertIn(item["answer"], "ABCD")
                answer_counts[item["answer"]] += 1
                self.assertRegex(item["explanation"], r"[\u4e00-\u9fff]")
                self.assertEqual(article["content"].count(item["evidence_text"]), 1)
        self.assertEqual(set(counts), {(topic, level) for topic in TOPICS for level in DIFFICULTIES})
        self.assertTrue(all(value == 5 for value in counts.values()))
        self.assertLessEqual(max(answer_counts.values()) - min(answer_counts.values()), 10)

    @unittest.skipUnless(approved_reading_corpus_available(), "180篇人工策展语料尚未批准，不得执行正式导入测试")
    def test_static_seed_is_idempotent_and_keeps_completed_history(self):
        db = database.get_db()
        before = db.execute("SELECT COUNT(*) AS c FROM reading_articles WHERE question_type='careful_reading'").fetchone()["c"]
        questions_before = db.execute("SELECT COUNT(*) AS c FROM reading_questions").fetchone()["c"]
        article = db.execute(
            "SELECT id,topic,difficulty,title FROM reading_articles WHERE origin=? ORDER BY id LIMIT 1",
            (CORPUS_ORIGIN,),
        ).fetchone()
        db.execute(
            """INSERT INTO practice_sessions
               (module,source_id,difficulty,correct_count,total_count,raw_score,idempotency_key)
               VALUES ('reading',?,?,5,5,100,?)""",
            (str(article["id"]), article["difficulty"], f'test:completed:{article["id"]}'),
        )
        db.execute("UPDATE reading_articles SET inventory_status='completed' WHERE id=?", (article["id"],))
        db.commit()
        db.close()
        database.init_db()
        db = database.get_db()
        completed = db.execute("SELECT inventory_status FROM reading_articles WHERE id=?", (article["id"],)).fetchone()
        after = db.execute("SELECT COUNT(*) AS c FROM reading_articles WHERE question_type='careful_reading'").fetchone()["c"]
        questions_after = db.execute("SELECT COUNT(*) AS c FROM reading_questions").fetchone()["c"]
        ready = db.execute(
            """SELECT COUNT(*) AS c FROM reading_articles a WHERE topic=? AND difficulty=?
               AND inventory_status='available' AND NOT EXISTS (
                 SELECT 1 FROM practice_sessions p WHERE p.module='reading' AND CAST(p.source_id AS TEXT)=CAST(a.id AS TEXT))""",
            (article["topic"], article["difficulty"]),
        ).fetchone()["c"]
        db.close()
        self.assertEqual(completed["inventory_status"], "completed")
        # All 180 curated rows were imported on the first pass. Re-running the
        # loader never clones a completed corpus row; a replacement job owns the
        # new fifth unread slot.
        self.assertEqual(ready, 4)
        self.assertEqual(after, before)
        self.assertEqual(questions_after, questions_before)
        db = database.get_db()
        pending = db.execute(
            """SELECT COUNT(*) AS c FROM reading_generation_jobs
               WHERE topic=? AND difficulty=? AND status IN ('pending','running','paused_budget','paused_config')""",
            (article["topic"], article["difficulty"]),
        ).fetchone()["c"]
        db.close()
        self.assertEqual(pending, 1)

    @unittest.skipUnless(approved_reading_corpus_available(), "180篇人工策展语料尚未批准，不得执行原子导入测试")
    def test_static_seed_rolls_back_every_write_when_a_question_insert_fails(self):
        db = database.get_db()
        db.execute(
            "DELETE FROM reading_questions WHERE article_id IN "
            "(SELECT id FROM reading_articles WHERE origin=?)",
            (CORPUS_ORIGIN,),
        )
        db.execute("DELETE FROM reading_articles WHERE origin=?", (CORPUS_ORIGIN,))
        legacy_id = db.execute(
            """SELECT id FROM reading_articles WHERE origin='golden_sample' ORDER BY id LIMIT 1"""
        ).fetchone()['id']
        db.execute("UPDATE reading_articles SET inventory_status='available' WHERE id=?", (legacy_id,))
        db.execute(
            """CREATE TEMP TRIGGER reject_static_questions
               BEFORE INSERT ON reading_questions BEGIN
                 SELECT RAISE(ABORT, 'forced question failure');
               END"""
        )
        with self.assertRaises(sqlite3.IntegrityError):
            seed_static_reading_corpus(db, TOPICS, DIFFICULTIES, TARGET_UNREAD_PER_CELL)
        curated = db.execute(
            "SELECT COUNT(*) AS c FROM reading_articles WHERE origin=?", (CORPUS_ORIGIN,)
        ).fetchone()['c']
        legacy_status = db.execute(
            "SELECT inventory_status FROM reading_articles WHERE id=?", (legacy_id,)
        ).fetchone()['inventory_status']
        db.close()
        self.assertEqual(curated, 0)
        self.assertEqual(legacy_status, 'available')

    def test_topic_migration_collapses_legacy_education_aliases(self):
        db = database.get_db()
        db.execute(
            "INSERT INTO reading_articles(title,content,topic,difficulty) VALUES ('Legacy','Body','教育📚',3)"
        )
        db.commit()
        db.close()
        database.init_db()
        db = database.get_db()
        row = db.execute("SELECT topic,source,origin FROM reading_articles WHERE title='Legacy'").fetchone()
        db.close()
        self.assertEqual(row["topic"], "教育")
        self.assertEqual(row["source"], "历史题库／本站整理")
        self.assertEqual(row["origin"], "legacy")

    def test_same_article_creates_only_one_replacement_job(self):
        db = database.get_db()
        article = db.execute(
            "SELECT id,topic,difficulty FROM reading_articles WHERE origin='golden_sample' ORDER BY id LIMIT 1"
        ).fetchone()
        db.close()
        schedule_replacement(article["id"], article["topic"], article["difficulty"])
        schedule_replacement(article["id"], article["topic"], article["difficulty"])
        db = database.get_db()
        count = db.execute(
            "SELECT COUNT(*) AS c FROM reading_generation_jobs WHERE idempotency_key=?",
            (f'replace:{article["id"]}',),
        ).fetchone()["c"]
        status = db.execute(
            "SELECT inventory_status FROM reading_articles WHERE id=?", (article["id"],)
        ).fetchone()["inventory_status"]
        db.close()
        self.assertEqual(count, 1)
        self.assertEqual(status, "completed")

    def test_future_refill_prefers_same_cell_curated_references(self):
        if not approved_reading_corpus_available():
            self.skipTest('正式180篇未批准时必须回退 golden sample')
        db = database.get_db()
        for index in range(2):
            db.execute(
                """INSERT INTO reading_articles
                   (title,content,topic,difficulty,origin,inventory_status)
                   VALUES (?,?,?,?, 'curated_corpus','available')""",
                (f'Curated reference {index}', f'Unique curated structure {index}.', '健康', 1),
            )
        db.commit()
        samples = _reference_samples(db, '健康', 1, 37)
        curated_titles = {
            row['title'] for row in db.execute(
                """SELECT title FROM reading_articles
                   WHERE origin='curated_corpus' AND topic='健康' AND difficulty=1
                     AND inventory_status='available'"""
            ).fetchall()
        }
        db.close()
        self.assertEqual(len(samples), 2)
        self.assertTrue(all(item['title'] in curated_titles for item in samples))
        self.assertTrue(all(item['content'] for item in samples))

    @unittest.skipUnless(approved_reading_corpus_available(), "180篇人工策展语料尚未批准")
    def test_enabling_refill_does_not_revive_failed_jobs_for_full_cells(self):
        db = database.get_db()
        job_id = db.execute(
            """INSERT INTO reading_generation_jobs
               (topic,difficulty,question_type,idempotency_key,status,attempts,max_attempts)
               VALUES ('健康',1,'careful_reading','test:full-cell-failure','failed',1,3)"""
        ).lastrowid
        db.commit(); db.close()
        with patch('services.reading_inventory_service.start_refill_worker', return_value=False):
            enable_refill()
        db = database.get_db()
        status = db.execute(
            "SELECT status FROM reading_generation_jobs WHERE id=?", (job_id,)
        ).fetchone()['status']
        enabled = db.execute(
            "SELECT value FROM user_settings WHERE key='reading_refill_enabled'"
        ).fetchone()['value']
        db.close()
        self.assertEqual(status, 'failed')
        self.assertEqual(enabled, '1')

    @unittest.skipIf(approved_reading_corpus_available(), "正式语料批准后不执行草稿隔离迁移")
    def test_unapproved_curated_rows_are_quarantined_without_deletion(self):
        db = database.get_db()
        plain = db.execute(
            """INSERT INTO reading_articles
               (title,content,topic,difficulty,origin,inventory_status)
               VALUES ('Rejected draft','Draft body','社会',3,'curated_corpus','available')"""
        ).lastrowid
        learned = db.execute(
            """INSERT INTO reading_articles
               (title,content,topic,difficulty,origin,inventory_status)
               VALUES ('Learned draft','Learned body','科技',4,'curated_corpus','available')"""
        ).lastrowid
        db.execute(
            """INSERT INTO practice_sessions
               (module,source_id,difficulty,correct_count,total_count,raw_score,idempotency_key)
               VALUES ('reading',?,4,4,5,80,'test:quarantine-history')""",
            (str(learned),),
        )
        db.commit(); db.close()
        database.init_db()
        db = database.get_db()
        rows = db.execute(
            "SELECT id,inventory_status FROM reading_articles WHERE id IN (?,?) ORDER BY id",
            (plain, learned),
        ).fetchall()
        count = db.execute(
            "SELECT COUNT(*) AS c FROM reading_articles WHERE id IN (?,?)",
            (plain, learned),
        ).fetchone()['c']
        db.close()
        self.assertEqual(count, 2)
        self.assertEqual([row['inventory_status'] for row in rows], ['quarantined', 'completed'])

    def test_terminal_bootstrap_key_does_not_block_a_new_deficit_job(self):
        db = database.get_db()
        article = db.execute(
            """SELECT id FROM reading_articles
               WHERE origin='curated_corpus' AND topic='健康' AND difficulty=1
                 AND inventory_status='available' ORDER BY id LIMIT 1"""
        ).fetchone()
        db.execute(
            "UPDATE reading_articles SET inventory_status='completed' WHERE id=?",
            (article['id'],),
        )
        db.commit(); db.close()
        database.init_db()
        db = database.get_db()
        row = db.execute(
            """SELECT id,idempotency_key FROM reading_generation_jobs
               WHERE topic='健康' AND difficulty=1 AND status='pending' ORDER BY id LIMIT 1"""
        ).fetchone()
        db.execute("UPDATE reading_generation_jobs SET status='failed',attempts=max_attempts WHERE id=?", (row['id'],))
        db.commit(); db.close()
        database.init_db()
        db = database.get_db()
        active = db.execute(
            """SELECT COUNT(*) AS c FROM reading_generation_jobs
               WHERE topic='健康' AND difficulty=1
                 AND status IN ('pending','running','paused_budget','paused_config')"""
        ).fetchone()['c']
        failed = db.execute(
            "SELECT COUNT(*) AS c FROM reading_generation_jobs WHERE id=? AND status='failed'",
            (row['id'],),
        ).fetchone()['c']
        db.close()
        self.assertEqual(failed, 1)
        self.assertEqual(active, 1)

    def test_inventory_routes_do_not_expose_answers_or_provider_secrets(self):
        response = self.client.get("/api/reading/inventory")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["totals"]["target"], 180)
        serialized = response.get_data(as_text=True).lower()
        self.assertNotIn("api_key", serialized)
        self.assertNotIn('"answer"', serialized)

    def test_source_fetch_rejects_non_https_unlisted_and_local_urls(self):
        for url in (
            "http://english.news.cn/example",
            "https://example.com/article",
            "https://localhost/article",
        ):
            with self.subTest(url=url), self.assertRaises(SourceFetchError):
                secure_fetch(url)

    @patch("services.reading_sources._is_public_host", return_value=True)
    @patch("services.reading_sources.requests.get")
    def test_source_redirect_is_revalidated_before_second_request(self, request_get, _public):
        class RedirectResponse:
            status_code = 302
            headers = {"Location": "https://127.0.0.1/private"}

        request_get.return_value = RedirectResponse()
        with self.assertRaises(SourceFetchError):
            secure_fetch("https://english.news.cn/example")
        self.assertEqual(request_get.call_count, 1)

    @patch("services.reading_inventory_service.get_api_key", return_value="")
    def test_worker_pauses_without_key_before_source_or_ai_call(self, _api_key):
        db = database.get_db()
        db.execute("INSERT INTO reading_generation_jobs(topic,difficulty,idempotency_key) VALUES ('健康',1,'test:no-key')")
        db.commit(); db.close()
        with patch("services.reading_inventory_service.discover_candidates") as discover:
            self.assertFalse(process_next_job())
            discover.assert_not_called()
        db = database.get_db()
        row = db.execute(
            "SELECT status,last_error,attempts FROM reading_generation_jobs ORDER BY id LIMIT 1"
        ).fetchone()
        db.close()
        self.assertEqual(row["status"], "paused_config")
        self.assertEqual(row["attempts"], 0)
        self.assertIn("API Key", row["last_error"])

    @patch("services.reading_inventory_service.current_month_tracked_cost", return_value=5.0)
    @patch("services.reading_inventory_service.get_api_key", return_value="configured")
    def test_worker_pauses_at_shared_monthly_budget_before_network(self, _api_key, _spend):
        db = database.get_db()
        db.execute("INSERT INTO reading_generation_jobs(topic,difficulty,idempotency_key) VALUES ('健康',1,'test:budget')")
        db.commit(); db.close()
        with patch("services.reading_inventory_service.discover_candidates") as discover:
            self.assertFalse(process_next_job())
            discover.assert_not_called()
        db = database.get_db()
        row = db.execute(
            "SELECT status,last_error,attempts FROM reading_generation_jobs ORDER BY id LIMIT 1"
        ).fetchone()
        db.close()
        self.assertEqual(row["status"], "paused_budget")
        self.assertEqual(row["attempts"], 0)
        self.assertIn("5 元", row["last_error"])


if __name__ == "__main__":
    unittest.main()

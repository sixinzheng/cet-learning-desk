import json
import os
import tempfile
import unittest
from unittest.mock import patch

import database
from app import create_app


class LevelV2ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def seed_words_and_article(self):
        db = database.get_db()
        for index in range(1, 11):
            db.execute(
                "INSERT INTO words (word, meanings, frequency) VALUES (?, '[]', ?)",
                (f"word{index}", 5 if index <= 5 else 4),
            )
            db.execute(
                "INSERT INTO user_words (word_id, status, review_count, correct_count, ebbinghaus_stage) "
                "VALUES (?, ?, ?, ?, ?)",
                (index, "掌握" if index <= 7 else "陌生", 2 if index <= 7 else 0,
                 2 if index <= 6 else 0, 3 if index <= 7 else 0),
            )
        db.execute(
            "INSERT INTO reading_articles (title, content, difficulty) VALUES ('Test', 'Body', 4)"
        )
        article_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.execute(
            "INSERT INTO reading_questions (article_id, question_type, question, options, answer) "
            "VALUES (?, 'detail', 'Question 1', '[\"A\",\"B\"]', 'A')",
            (article_id,),
        )
        db.execute(
            "INSERT INTO reading_questions (article_id, question_type, question, options, answer) "
            "VALUES (?, 'detail', 'Question 2', '[\"A\",\"B\"]', 'B')",
            (article_id,),
        )
        db.commit()
        db.close()
        return article_id

    def test_schema_migration_is_idempotent_and_preserves_legacy_rows(self):
        db = database.get_db()
        db.execute("INSERT INTO study_logs (study_date, reading_count, total_minutes) VALUES ('2026-01-01', 3, 25)")
        db.commit()
        db.close()

        database.init_db()
        database.init_db()

        db = database.get_db()
        tables = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        level_columns = {row["name"] for row in db.execute("PRAGMA table_info(user_level)")}
        legacy = db.execute("SELECT reading_count, total_minutes FROM study_logs WHERE study_date='2026-01-01'").fetchone()
        db.close()
        self.assertIn("practice_sessions", tables)
        self.assertIn("listening_scenarios", tables)
        for column in ("speaking_score", "retention_score", "investment_score", "algorithm_version"):
            self.assertIn(column, level_columns)
        self.assertEqual((legacy["reading_count"], legacy["total_minutes"]), (3, 25))

    def test_level_detail_exposes_six_dimensions_that_sum_to_one_hundred_percent(self):
        response = self.client.get("/api/level/detail")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        ledger = data["score_ledger"]
        self.assertEqual(
            list(ledger),
            ["vocabulary", "reading", "listening", "writing", "retention", "investment"],
        )
        self.assertEqual(sum(item["weight"] for item in ledger.values()), 100)
        self.assertAlmostEqual(
            data["level"]["total_score"],
            sum(item["contribution"] for item in ledger.values()),
            places=1,
        )
        self.assertIn("historical_best", data)
        self.assertEqual(data["algorithm_version"], "3.0")
        self.assertEqual(data["rank_thresholds"]["2"], 40)
        self.assertFalse(data["evidence_constraints"]["speaking_inference"])
        self.assertFalse(data["evidence_constraints"]["grammar_dimension"])

    def test_next_level_gap_uses_v3_nonlinear_boundary(self):
        from routes.api_level import _next_level
        data = _next_level({"rank": 1, "total_score": 2.9})
        self.assertEqual(data["rank"], 2)
        self.assertEqual(data["gap"], 37.1)

    def test_reading_completion_is_server_scored_and_idempotent(self):
        article_id = self.seed_words_and_article()
        payload = {
            "article_id": article_id,
            "answers": {"1": "A", "2": "A"},
            "duration_seconds": 180,
            "idempotency_key": "reading-test-1",
            "claimed_score": 100,
        }
        first = self.client.post("/api/practice/reading/complete", json=payload)
        second = self.client.post("/api/practice/reading/complete", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["score"], 54.0)
        self.assertFalse(first.get_json()["duplicate"])
        self.assertTrue(second.get_json()["duplicate"])
        db = database.get_db()
        count = db.execute("SELECT COUNT(*) AS c FROM practice_sessions WHERE idempotency_key='reading-test-1'").fetchone()["c"]
        db.close()
        self.assertEqual(count, 1)

    def test_capability_claim_never_mentions_conversation_without_speaking_evidence(self):
        self.seed_words_and_article()
        data = self.client.get("/api/level/detail").get_json()
        claim = data["assessment"]["sentence"]
        self.assertNotIn("对话", claim)
        self.assertNotIn("外国人", claim)
        self.assertIn("高频词", claim)

    @patch("routes.api_writing.analyze_essay")
    def test_writing_is_recorded_only_after_successful_ai_scoring(self, analyze):
        analyze.return_value = {
            "total_score": 78, "content_score": 80, "structure_score": 76,
            "vocabulary_score": 75, "grammar_score": 77, "coherence_score": 79,
            "errors": [], "highlights": [], "overall_comment": "Good",
        }
        response = self.client.post("/api/writing/correct", json={
            "essay": "This is a complete test essay with a clear main idea.",
            "exam_level": "cet4", "difficulty": 3, "duration_seconds": 600,
            "idempotency_key": "writing-test-1",
        })
        self.assertEqual(response.status_code, 200)
        db = database.get_db()
        row = db.execute("SELECT raw_score, metadata_json FROM practice_sessions WHERE idempotency_key='writing-test-1'").fetchone()
        db.close()
        self.assertEqual(row["raw_score"], 78)
        self.assertEqual(json.loads(row["metadata_json"])["scores"]["content"], 80)

    @patch("routes.api_writing.call_multimodal")
    def test_writing_ocr_returns_editable_text_without_creating_score(self, vision):
        vision.return_value = {
            "content": json.dumps({"text": "This is my original essay.", "warnings": ["第二行略微模糊"]}, ensure_ascii=False),
            "usage": {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
            "model": "deepseek-v4-flash-vision-exp",
        }
        response = self.client.post("/api/writing/ocr", json={
            "image": "data:image/png;base64,AAAA", "request_id": "ocr-test-1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["text"], "This is my original essay.")
        db = database.get_db()
        count = db.execute("SELECT COUNT(*) AS c FROM practice_sessions WHERE module='writing'").fetchone()["c"]
        db.close()
        self.assertEqual(count, 0)
        self.assertEqual(vision.call_args.kwargs["image_detail"], "high")

    def test_listening_word_round_prioritizes_due_review_words(self):
        db = database.get_db()
        db.execute("INSERT INTO words (word, meanings, frequency) VALUES ('laterword', '[]', 5)")
        later_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.execute("INSERT INTO words (word, meanings, frequency) VALUES ('dueword', '[]', 2)")
        due_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.execute("INSERT INTO user_words (word_id,status,next_review,last_reviewed) VALUES (?,'模糊','2099-01-01','2026-08-20')", (later_id,))
        db.execute("INSERT INTO user_words (word_id,status,next_review,last_reviewed) VALUES (?,'巩固','2020-01-01','2026-08-29')", (due_id,))
        db.commit(); db.close()
        data = self.client.get('/api/practice/listening/content?layer=word').get_json()
        self.assertEqual(data['items'][0]['id'], due_id)
        self.assertEqual(data['items'][0]['priority_reason'], '到期复习')
        self.assertIn('到期词', data['selection_basis'])

    def test_training_frontends_submit_complete_sessions(self):
        root = os.path.dirname(os.path.dirname(__file__))
        expectations = {
            "reading.js": "/api/practice/reading/complete",
            "cloze.js": "/api/practice/cloze/complete",
            "writing.js": "idempotency_key",
        }
        for filename, marker in expectations.items():
            with self.subTest(filename=filename):
                with open(os.path.join(root, "static", "js", filename), encoding="utf-8") as handle:
                    self.assertIn(marker, handle.read())

    def test_listening_has_three_layers_and_no_per_answer_legacy_logging(self):
        root = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root, "templates", "listening.html"), encoding="utf-8") as handle:
            template = handle.read()
        with open(os.path.join(root, "static", "js", "listening.js"), encoding="utf-8") as handle:
            script = handle.read()
        for layer in ("word", "sentence", "dialogue"):
            self.assertIn(f'data-layer="{layer}"', template)
        for removed in ('data-layer="speaking"', 'speaking-panel', 'speaking-record'):
            self.assertNotIn(removed, template)
        self.assertIn("/api/practice/listening/complete", script)
        self.assertNotIn("/api/practice/speaking/complete", script)
        self.assertNotIn("/api/study/log-listening", script)

    def test_dialogue_session_is_server_scored_once(self):
        items = self.client.get("/api/practice/listening/content?layer=dialogue").get_json()["items"]
        item = items[0]
        response = self.client.post("/api/practice/listening/complete", json={
            "layer": "dialogue",
            "answers": [{"scenario_id": item["id"], "answer": "B"}],
            "duration_seconds": 45,
            "idempotency_key": "dialogue-test-1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.get_json()["score"], 90)
        db = database.get_db()
        count = db.execute("SELECT COUNT(*) AS c FROM practice_sessions WHERE module='listening'").fetchone()["c"]
        db.close()
        self.assertEqual(count, 1)

    def test_diagnostic_page_is_optional_and_submits_server_scored_modules(self):
        response = self.client.get('/diagnostic')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="diagnostic-start"', html)
        root = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root, 'static', 'js', 'diagnostic.js'), encoding='utf-8') as handle:
            script = handle.read()
        self.assertIn("origin: 'diagnostic'", script)
        self.assertIn('/api/practice/diagnostic/complete', script)

    def test_growth_page_exposes_eight_dimension_bill_and_capability_summary(self):
        html = self.client.get('/growth').get_data(as_text=True)
        self.assertIn('id="g-capability"', html)
        self.assertIn('id="g-contribution"', html)
        self.assertIn('id="g-score-ledger"', html)
        self.assertIn('id="g-historical-rank"', html)
        self.assertIn('id="g-diagnostic"', html)
        root = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root, 'static', 'js', 'growth.js'), encoding='utf-8') as handle:
            script = handle.read()
        for key in ('vocabulary', 'reading', 'listening', 'writing', 'retention', 'investment'):
            self.assertIn(key, script)

    def test_home_rank_summary_has_capability_and_priority_advice(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('id="rank-capability"', html)
        self.assertIn('id="home-rank-advice"', html)
        self.assertIn('查看完整段位账单', html)

    def test_level_timeline_records_rank_changes_not_every_practice(self):
        db = database.get_db()
        db.execute("INSERT INTO reading_articles (title, content, difficulty) VALUES ('Small', 'Body', 2)")
        article_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
        db.execute("INSERT INTO reading_questions (article_id, question_type, question, options, answer) VALUES (?, 'detail', 'Q', '[\"A\",\"B\"]', 'A')", (article_id,))
        question_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
        db.commit(); db.close()
        before = database.get_db()
        before_count = before.execute('SELECT COUNT(*) AS n FROM user_level').fetchone()['n']
        before.close()
        self.client.post('/api/practice/reading/complete', json={
            'article_id': article_id,
            'answers': {str(question_id): 'A'},
            'idempotency_key': 'timeline-same-rank',
        })
        after = database.get_db()
        after_count = after.execute('SELECT COUNT(*) AS n FROM user_level').fetchone()['n']
        after.close()
        self.assertEqual(after_count, before_count)


if __name__ == "__main__":
    unittest.main()

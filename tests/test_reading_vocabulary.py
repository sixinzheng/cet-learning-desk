import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

import database
from app import create_app
from services.ai_service import AIServiceError
from services.word_enrichment_service import enrich_word


def valid_ai_detail(headword="cacheword"):
    return {
        "content": json.dumps({
            "headword": headword,
            "phonetic": "/kæʃ/",
            "part_of_speech": "n.",
            "context_meaning": "语境中的测试词",
            "additional_meanings": ["常见的另一含义"],
            "context_example": {
                "en": f"The {headword} remains clear in this context.",
                "zh": "这个词在当前语境中含义清楚。",
            },
            "other_example": {
                "meaning": "另一常见含义",
                "en": f"They used {headword} in another complete sentence.",
                "zh": "他们在另一个完整句子中使用了这个词。",
            },
            "form_note": "文中词形与词头相同。",
        }, ensure_ascii=False),
        "model": "deepseek-test",
    }


class ReadingVocabularyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "reading-vocabulary.db")
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

        db = database.get_db()
        db.execute(
            "INSERT OR IGNORE INTO words (word,phonetic,part_of_speech,meanings,frequency) "
            "VALUES ('develop','/dɪˈveləp/','v.',?,5)",
            (json.dumps(["发展", "开发"], ensure_ascii=False),),
        )
        self.develop_id = db.execute("SELECT id FROM words WHERE word='develop'").fetchone()["id"]
        db.execute(
            "INSERT OR REPLACE INTO user_words (word_id,status) VALUES (?, '掌握')",
            (self.develop_id,),
        )
        self.article_id = db.execute(
            "INSERT INTO reading_articles (title,content,word_count,difficulty,topic) VALUES (?,?,?,?,?)",
            ("Vocabulary contract", "A developed system uses cacheword twice. Cacheword stays useful. Brokenword and networkword remain examples.", 12, 2, "科技"),
        ).lastrowid
        db.commit()
        db.close()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def csrf(self):
        return self.client.get("/api/ai/config/status").get_json()["csrf_token"]

    def test_hidden_cache_book_contains_existing_words_and_is_never_listed(self):
        database.init_db()
        db = database.get_db()
        hidden = db.execute(
            "SELECT id FROM wordbooks WHERE name='阅读词汇缓存' AND is_hidden=1"
        ).fetchone()
        word_count = db.execute("SELECT COUNT(*) AS c FROM words").fetchone()["c"]
        hidden_count = db.execute(
            "SELECT COUNT(*) AS c FROM wordbook_words WHERE wordbook_id=?", (hidden["id"],)
        ).fetchone()["c"]
        db.execute(
            "INSERT OR REPLACE INTO user_settings (key,value) VALUES ('current_wordbook',?)",
            (str(hidden["id"]),),
        )
        db.commit()
        db.close()
        self.assertEqual(hidden_count, word_count)
        books = self.client.get("/api/words/wordbooks").get_json()["wordbooks"]
        self.assertNotIn("阅读词汇缓存", [book["name"] for book in books])
        current = self.client.get("/api/words/current-wordbook").get_json()
        self.assertNotEqual(current.get("book_id"), hidden["id"])
        self.assertEqual(
            self.client.get(f"/api/words/wordbooks/{hidden['id']}/words").status_code,
            404,
        )
        learning = self.client.get(f"/api/study/new-words?book_id={hidden['id']}").get_json()
        self.assertNotEqual(learning.get("book_id"), hidden["id"])

    def test_inflected_form_matches_core_word_without_ai(self):
        response = self.client.get("/api/reading/lookup-word?word=developed")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["found"])
        self.assertEqual(payload["word"], "develop")
        self.assertEqual(payload["match_type"], "inflection")
        self.assertIsNone(payload["ai_detail"])

    def test_article_vocabulary_is_live_and_exposes_mastered_and_unlisted(self):
        payload = self.client.get(f"/api/reading/articles/{self.article_id}").get_json()
        by_headword = {item["headword"]: item for item in payload["vocabulary"]["words"]}
        self.assertEqual(by_headword["develop"]["status"], "掌握")
        self.assertTrue(by_headword["develop"]["is_mastered"])
        self.assertEqual(by_headword["cacheword"]["status"], "未收录")
        self.assertFalse(by_headword["cacheword"]["found"])
        self.assertEqual(payload["word_stats"]["mastered"], 1)
        self.assertGreaterEqual(payload["word_stats"]["total_vocab"], 2)

    def test_batch_annotation_saves_once_and_erase_clears_both_types(self):
        created = self.client.post(
            f"/api/reading/articles/{self.article_id}/annotations/batch",
            json={"mode": "green", "word_indices": [1, 2, 2]},
        )
        self.assertEqual(created.status_code, 200)
        self.client.post(
            f"/api/reading/articles/{self.article_id}/annotations/batch",
            json={"mode": "red", "word_indices": [2]},
        )
        before = self.client.get(
            f"/api/reading/articles/{self.article_id}/annotations"
        ).get_json()["annotations"]
        self.assertEqual(sorted(before["2"]), ["green", "red"])
        erased = self.client.post(
            f"/api/reading/articles/{self.article_id}/annotations/batch",
            json={"mode": "erase", "word_indices": [2]},
        )
        self.assertEqual(erased.status_code, 200)
        after = self.client.get(
            f"/api/reading/articles/{self.article_id}/annotations"
        ).get_json()["annotations"]
        self.assertNotIn("2", after)
        self.assertEqual(after["1"], ["green"])

    def test_enrichment_requires_csrf_then_caches_and_explicit_refreshes(self):
        endpoint = "/api/ai/enrich-word"
        payload = {"article_id": self.article_id, "surface_word": "cacheword", "occurrence": 0}
        self.assertEqual(self.client.post(endpoint, json=payload).status_code, 403)
        headers = {"X-CSRF-Token": self.csrf()}
        with patch("services.word_enrichment_service.call_deepseek", return_value=valid_ai_detail()) as mocked:
            first = self.client.post(endpoint, json=payload, headers=headers)
            second = self.client.post(endpoint, json=payload, headers=headers)
            refreshed = self.client.post(endpoint, json={**payload, "refresh": True}, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.get_json()["cached"])
        self.assertTrue(second.get_json()["cached"])
        self.assertFalse(refreshed.get_json()["cached"])
        self.assertEqual(mocked.call_count, 2)
        db = database.get_db()
        word = db.execute("SELECT id,source FROM words WHERE word='cacheword'").fetchone()
        hidden = db.execute("SELECT id FROM wordbooks WHERE is_hidden=1").fetchone()
        self.assertEqual(word["source"], "ai_reading")
        self.assertIsNotNone(db.execute(
            "SELECT 1 FROM word_ai_details WHERE word_id=?", (word["id"],)
        ).fetchone())
        self.assertIsNotNone(db.execute(
            "SELECT 1 FROM wordbook_words WHERE wordbook_id=? AND word_id=?",
            (hidden["id"], word["id"]),
        ).fetchone())
        db.close()

    def test_existing_word_enrichment_never_overwrites_core_meanings(self):
        db = database.get_db()
        before = db.execute("SELECT meanings FROM words WHERE id=?", (self.develop_id,)).fetchone()["meanings"]
        db.close()
        with patch(
            "services.word_enrichment_service.call_deepseek",
            return_value=valid_ai_detail("develop"),
        ):
            response = self.client.post(
                "/api/ai/enrich-word",
                json={"article_id": self.article_id, "surface_word": "developed", "occurrence": 0},
                headers={"X-CSRF-Token": self.csrf()},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["word"], "develop")
        db = database.get_db()
        after = db.execute("SELECT meanings FROM words WHERE id=?", (self.develop_id,)).fetchone()["meanings"]
        self.assertEqual(after, before)
        self.assertIsNotNone(db.execute(
            "SELECT 1 FROM word_ai_details WHERE word_id=?", (self.develop_id,)
        ).fetchone())
        db.close()

    def test_invalid_ai_response_leaves_no_word_or_cache(self):
        with patch(
            "services.word_enrichment_service.call_deepseek",
            return_value={"content": "not-json", "model": "test"},
        ):
            response = self.client.post(
                "/api/ai/enrich-word",
                json={"article_id": self.article_id, "surface_word": "brokenword"},
                headers={"X-CSRF-Token": self.csrf()},
            )
        self.assertEqual(response.status_code, 502)
        db = database.get_db()
        self.assertIsNone(db.execute("SELECT 1 FROM words WHERE word='brokenword'").fetchone())
        self.assertEqual(db.execute("SELECT COUNT(*) AS c FROM word_ai_details").fetchone()["c"], 0)
        db.close()

    def test_concurrent_requests_share_one_generation(self):
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def worker():
            try:
                barrier.wait()
                results.append(enrich_word(
                    article_id=self.article_id, surface_word="cacheword", occurrence=0
                ))
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        with patch("services.word_enrichment_service.call_deepseek", return_value=valid_ai_detail()) as mocked:
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertFalse(errors)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(sorted(item["cached"] for item in results), [False, True])

    def test_ai_service_error_does_not_write_partial_state(self):
        with patch(
            "services.word_enrichment_service.call_deepseek",
            side_effect=AIServiceError("network down", "network_error", 502),
        ):
            response = self.client.post(
                "/api/ai/enrich-word",
                json={"article_id": self.article_id, "surface_word": "networkword"},
                headers={"X-CSRF-Token": self.csrf()},
            )
        self.assertEqual(response.status_code, 502)
        db = database.get_db()
        self.assertIsNone(db.execute("SELECT 1 FROM words WHERE word='networkword'").fetchone())
        db.close()

    def test_unconfigured_ai_is_reported_before_any_network_request(self):
        with patch("services.ai_service.get_api_key", return_value=""), patch(
            "services.ai_service.requests.post"
        ) as network:
            response = self.client.post(
                "/api/ai/enrich-word",
                json={"article_id": self.article_id, "surface_word": "networkword"},
                headers={"X-CSRF-Token": self.csrf()},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["code"], "not_configured")
        network.assert_not_called()

    def test_disabled_language_analyst_blocks_enrichment_before_network(self):
        db = database.get_db()
        db.execute("UPDATE site_skills SET enabled=0 WHERE slug='language-analyst'")
        db.commit()
        db.close()
        with patch("services.ai_service.requests.post") as network:
            response = self.client.post(
                "/api/ai/enrich-word",
                json={"article_id": self.article_id, "surface_word": "networkword"},
                headers={"X-CSRF-Token": self.csrf()},
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "skill_disabled")
        network.assert_not_called()

    def test_enrichment_rejects_word_outside_article(self):
        with patch("services.word_enrichment_service.call_deepseek") as mocked:
            response = self.client.post(
                "/api/ai/enrich-word",
                json={"article_id": self.article_id, "surface_word": "notinthearticle"},
                headers={"X-CSRF-Token": self.csrf()},
            )
        self.assertEqual(response.status_code, 400)
        mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()

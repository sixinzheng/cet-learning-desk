"""训练难度档位（1–6）的读写、映射与自动筛题契约测试。

所有测试共用真实数据库（与现有测试一致），改动 user_settings 后会在 tearDown
还原原档位，避免污染运行中的站点。
"""

import unittest

from app import create_app
from database import get_db
from services.difficulty_service import (
    difficulty_criteria,
    difficulty_exam_level,
    difficulty_label,
    get_training_difficulty,
    save_training_difficulty,
)

LABELS = ["四级及格", "四级普通", "四级优秀", "六级及格", "六级普通", "六级优秀"]


class TrainingDifficultyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True
        cls.client = cls.app.test_client()

    def setUp(self):
        self._previous = get_training_difficulty()

    def tearDown(self):
        if self._previous is None:
            db = get_db()
            db.execute("DELETE FROM user_settings WHERE key='training_difficulty'")
            db.commit()
            db.close()
        else:
            save_training_difficulty(self._previous)

    def _save(self, value):
        response = self.client.put("/api/study/difficulty-setting", json={"difficulty": value})
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_level_catalog_matches_learn_page_options(self):
        data = self.client.get("/api/study/difficulty-setting").get_json()
        self.assertEqual([item["value"] for item in data["levels"]], [1, 2, 3, 4, 5, 6])
        self.assertEqual([item["label"] for item in data["levels"]], LABELS)

    def test_save_and_read_round_trip(self):
        self._save(4)
        data = self.client.get("/api/study/difficulty-setting").get_json()
        self.assertEqual(data["difficulty"], 4)
        self.assertEqual(data["label"], "六级及格")
        self.assertEqual(get_training_difficulty(), 4)

    def test_reject_out_of_range(self):
        for bad in (0, 7, -1, 100):
            with self.subTest(value=bad):
                response = self.client.put("/api/study/difficulty-setting", json={"difficulty": bad})
                self.assertEqual(response.status_code, 400)

    def test_service_mappings(self):
        self.assertEqual(difficulty_label(1), "四级及格")
        self.assertEqual(difficulty_label(6), "六级优秀")
        self.assertEqual(difficulty_exam_level(1), "cet4")
        self.assertEqual(difficulty_exam_level(3), "cet4")
        self.assertEqual(difficulty_exam_level(4), "cet6")
        self.assertEqual(difficulty_exam_level(6), "cet6")
        self.assertIn("四级及格", difficulty_criteria(1))
        self.assertIn("六级优秀", difficulty_criteria(6))
        self.assertEqual(difficulty_criteria(0), "")

    def test_cloze_passages_filter_to_saved_difficulty(self):
        self._save(3)
        data = self.client.get("/api/practice/cloze/content").get_json()
        items = data["items"]
        self.assertGreaterEqual(len(items), 1)
        for item in items:
            self.assertEqual(item["difficulty"], 3)

    def test_cloze_content_does_not_expose_per_blank_answer_hints(self):
        data = self.client.get("/api/practice/cloze/content").get_json()
        self.assertGreaterEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertGreaterEqual(len(item["candidates"]), item["blank_count"])
        for blank in item["blanks"]:
            self.assertEqual(set(blank), {"blank_order"})

    def test_cloze_falls_back_when_saved_level_has_no_exact_hit(self):
        # 真实题库会持续增加内容，动态寻找当前没有精确题目的档位，
        # 避免把“难度 1 永远为空”写成过时前提。
        db = get_db()
        available = {
            row['difficulty']
            for row in db.execute("SELECT DISTINCT difficulty FROM cloze_passages").fetchall()
        }
        db.close()
        missing = next((level for level in range(1, 7) if level not in available), None)
        if missing is None:
            self.skipTest('当前 1–6 档均有精确完形题，无需触发回退。')
        self._save(missing)
        data = self.client.get("/api/practice/cloze/content").get_json()
        items = data["items"]
        self.assertGreaterEqual(len(items), 1)
        for item in items:
            self.assertIn(item["difficulty"], available)
            self.assertNotEqual(item["difficulty"], missing)

    def test_reading_articles_filter_to_saved_difficulty(self):
        self._save(2)
        data = self.client.get("/api/reading/articles").get_json()
        articles = data["articles"]
        self.assertGreaterEqual(len(articles), 1)
        for article in articles:
            self.assertEqual(article["difficulty"], 2)

    def test_listening_dialogue_falls_back_to_all_when_saved_level_missing(self):
        # 对话库只有难度 2/3/4；保存难度 6 时精确无命中，应回到全部
        self._save(6)
        data = self.client.get("/api/practice/listening/content?layer=dialogue").get_json()
        difficulties = {item["difficulty"] for item in data["items"]}
        self.assertGreaterEqual(len(data["items"]), 1)
        self.assertEqual(difficulties, {2, 3, 4})

    def test_dashboard_exposes_today_modules_and_recommendation(self):
        data = self.client.get("/api/study/dashboard").get_json()
        self.assertEqual(
            set(data["today_modules"]),
            {"reading", "listening", "cloze", "writing"},
        )
        for key in ("module", "label", "href", "today_done"):
            self.assertIn(key, data["recommend"])
        self.assertIn(data["recommend"]["module"], {"reading", "listening", "cloze", "writing"})
        self.assertIn(data["recommend"]["href"], {"/reading", "/listening", "/cloze", "/writing"})


if __name__ == "__main__":
    unittest.main()

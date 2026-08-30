"""背单词机制重设计（艾宾浩斯全链路）契约测试。

覆盖：五态状态机全流转、学习连对 3 过关、复习每词每天最多推进 1 格、
连续错 2 次降级、到期必抽（取消随机抽样）、词库维度巩固态系数。
每个测试用临时数据库隔离，不触碰真实 vocab.db。
"""

import os
import tempfile
import unittest
from datetime import date, timedelta

import database
from app import create_app
from services import review_service as rs
from services.level_service import _vocabulary_dimension

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)


def _iso(day):
    return day.isoformat()


class WordScheduleTests(unittest.TestCase):
    def setUp(self):
        # 路由/服务函数沿用本项目"开连接不显式 close"的既有模式，
        # Windows 下会锁住临时库文件，忽略清理失败（各测试用独立库文件，互不影响）。
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()
        self._counter = 0

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    # ---- 工具 ----

    def seed_word(self, status, stage, next_review, frequency=5):
        """默认 frequency=5（高频快线），与既有间隔断言一致；低频测试显式传 1~3。"""
        db = database.get_db()
        self._counter += 1
        word = f"word{self._counter}"
        db.execute(
            "INSERT INTO words (word, meanings, frequency) VALUES (?, '[]', ?)",
            (word, frequency),
        )
        wid = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.execute(
            "INSERT INTO user_words (word_id, status, ebbinghaus_stage, next_review) "
            "VALUES (?, ?, ?, ?)",
            (wid, status, stage, _iso(next_review) if next_review else None),
        )
        db.commit()
        db.close()
        return wid

    def get_word(self, word_id):
        db = database.get_db()
        row = db.execute("SELECT * FROM user_words WHERE word_id=?", (word_id,)).fetchone()
        db.close()
        return dict(row) if row else None

    def make_due(self, word_id):
        """模拟第二天到期：把 next_review 改回今天"""
        db = database.get_db()
        db.execute("UPDATE user_words SET next_review=? WHERE word_id=?", (_iso(TODAY), word_id))
        db.commit()
        db.close()

    # ---- 学习：连对 3 过关 ----

    def test_learn_requires_three_consecutive(self):
        wid = self.seed_word("陌生", 0, None)
        for consec in (1, 2):
            resp = self.client.post("/api/study/answer", json={
                "word_id": wid, "correct": True, "mode": "learn",
            })
            data = resp.get_json()
            self.assertFalse(data["passed"])
            self.assertEqual(data["consecutive"], consec)
            self.assertEqual(self.get_word(wid)["status"], "陌生")
        # 第 3 次连续选对 → 过关，升级为模糊
        resp = self.client.post("/api/study/answer", json={
            "word_id": wid, "correct": True, "mode": "learn",
        })
        data = resp.get_json()
        self.assertTrue(data["passed"])
        self.assertEqual(data["consecutive"], 3)
        row = self.get_word(wid)
        self.assertEqual(row["status"], "模糊")
        self.assertEqual(row["ebbinghaus_stage"], 0)

    def test_learn_wrong_resets_streak(self):
        wid = self.seed_word("陌生", 0, None)
        self.client.post("/api/study/answer", json={"word_id": wid, "correct": True, "mode": "learn"})
        self.client.post("/api/study/answer", json={"word_id": wid, "correct": True, "mode": "learn"})
        resp = self.client.post("/api/study/answer", json={"word_id": wid, "correct": False, "mode": "learn"})
        self.assertEqual(resp.get_json()["consecutive"], 0)
        self.assertEqual(self.get_word(wid)["status"], "陌生")

    def test_promote_to_fuzzy_sets_next_review_tomorrow(self):
        wid = self.seed_word("陌生", 0, None)
        rs.promote_to_fuzzy(wid)
        row = self.get_word(wid)
        self.assertEqual(row["status"], "模糊")
        self.assertEqual(row["ebbinghaus_stage"], 0)
        self.assertEqual(row["next_review"], _iso(TOMORROW))

    # ---- 状态机全流转 ----

    def test_fuzzy_chain_promotes_to_consolidating(self):
        wid = self.seed_word("模糊", 0, TODAY)
        expected = [(1, TODAY + timedelta(days=2)), (2, TODAY + timedelta(days=4)),
                    (3, TODAY + timedelta(days=7)), (4, TODAY + timedelta(days=15))]
        for stage, nxt in expected:
            self.make_due(wid)
            r = rs.advance_word(wid)
            self.assertEqual(r["status"], "模糊")
            self.assertEqual(r["stage"], stage)
            self.assertEqual(r["next_review"], _iso(nxt))
            self.assertFalse(r.get("graduated"))
            self.assertNotIn("skipped", r)
        # 最后一格 → 升入巩固（第 30 天）
        self.make_due(wid)
        r = rs.advance_word(wid)
        self.assertEqual(r["status"], "巩固")
        self.assertEqual(r["stage"], 0)
        self.assertEqual(r["next_review"], _iso(TODAY + timedelta(days=30)))

    def test_consolidating_chain_promotes_to_mastered(self):
        wid = self.seed_word("巩固", 0, TODAY)
        expected = [(1, TODAY + timedelta(days=60)), (2, TODAY + timedelta(days=90))]
        for stage, nxt in expected:
            self.make_due(wid)
            r = rs.advance_word(wid)
            self.assertEqual(r["status"], "巩固")
            self.assertEqual(r["stage"], stage)
            self.assertEqual(r["next_review"], _iso(nxt))
        # 最后一格 → 升入掌握（第 180 天）
        self.make_due(wid)
        r = rs.advance_word(wid)
        self.assertEqual(r["status"], "掌握")
        self.assertEqual(r["stage"], 0)
        self.assertEqual(r["next_review"], _iso(TODAY + timedelta(days=180)))

    def test_mastered_advance_graduates(self):
        wid = self.seed_word("掌握", 0, TODAY)
        r = rs.advance_word(wid)
        self.assertEqual(r["status"], "熟记")
        self.assertTrue(r["graduated"])
        self.assertEqual(r["stage"], 99)
        row = self.get_word(wid)
        self.assertEqual(row["status"], "熟记")
        self.assertIsNone(row["next_review"])

    def test_advance_rejects_unknown_status(self):
        wid = self.seed_word("陌生", 0, TODAY)
        self.assertIsNone(rs.advance_word(wid))

    # ---- 每词每天最多 +1 ----

    def test_advance_idempotent_same_day(self):
        wid = self.seed_word("模糊", 0, TODAY)
        r1 = rs.advance_word(wid)
        self.assertEqual(r1["stage"], 1)
        r2 = rs.advance_word(wid)  # next_review 已是未来 → 跳过
        self.assertTrue(r2.get("skipped"))
        self.assertEqual(self.get_word(wid)["ebbinghaus_stage"], 1)

    def test_advance_skipped_when_not_due(self):
        wid = self.seed_word("模糊", 0, TODAY + timedelta(days=10))
        r = rs.advance_word(wid)
        self.assertTrue(r.get("skipped"))
        self.assertEqual(self.get_word(wid)["ebbinghaus_stage"], 0)

    # ---- 复习：只记次数不推进；连错 2 次降级 ----

    def test_review_records_counts_without_advance(self):
        wid = self.seed_word("模糊", 0, TODAY)
        resp = self.client.post("/api/study/answer", json={
            "word_id": wid, "correct": True, "mode": "review",
        })
        self.assertEqual(resp.status_code, 200)
        row = self.get_word(wid)
        self.assertEqual(row["review_count"], 1)
        self.assertEqual(row["correct_count"], 1)
        self.assertEqual(row["wrong_streak"], 0)
        # 节点未推进，到期日不变
        self.assertEqual(row["ebbinghaus_stage"], 0)
        self.assertEqual(row["next_review"], _iso(TODAY))

    def test_review_two_wrongs_degrade_consolidating_to_fuzzy(self):
        wid = self.seed_word("巩固", 1, TODAY)
        self.client.post("/api/study/answer", json={"word_id": wid, "correct": False, "mode": "review"})
        row = self.get_word(wid)
        self.assertEqual(row["status"], "巩固")  # 第一次答错不降级
        self.assertEqual(row["wrong_streak"], 1)
        resp = self.client.post("/api/study/answer", json={"word_id": wid, "correct": False, "mode": "review"})
        self.assertEqual(resp.status_code, 200)
        row = self.get_word(wid)
        self.assertEqual(row["status"], "模糊")  # 连错 2 次 → 降回模糊
        self.assertEqual(row["ebbinghaus_stage"], 0)
        self.assertEqual(row["next_review"], _iso(TOMORROW))
        self.assertEqual(row["wrong_streak"], 0)

    def test_review_wrong_then_correct_clears_streak(self):
        wid = self.seed_word("模糊", 0, TODAY)
        self.client.post("/api/study/answer", json={"word_id": wid, "correct": False, "mode": "review"})
        self.client.post("/api/study/answer", json={"word_id": wid, "correct": True, "mode": "review"})
        row = self.get_word(wid)
        self.assertEqual(row["wrong_streak"], 0)

    def test_degrade_rules_by_status(self):
        # 模糊 → 重置第 1 天（状态不变）
        w1 = self.seed_word("模糊", 3, TODAY)
        r = rs.degrade_word(w1)
        self.assertEqual(r["status"], "模糊")
        self.assertEqual(r["stage"], 0)
        self.assertEqual(r["next_review"], _iso(TOMORROW))
        # 巩固 → 模糊
        w2 = self.seed_word("巩固", 1, TODAY)
        r = rs.degrade_word(w2)
        self.assertEqual(r["status"], "模糊")
        # 掌握 → 巩固
        w3 = self.seed_word("掌握", 0, TODAY)
        r = rs.degrade_word(w3)
        self.assertEqual(r["status"], "巩固")

    def test_review_word_complete_endpoint_advances_once(self):
        wid = self.seed_word("模糊", 0, TODAY)
        r1 = self.client.post("/api/study/review-word-complete", json={"word_id": wid})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.get_json()["stage"], 1)
        r2 = self.client.post("/api/study/review-word-complete", json={"word_id": wid})
        self.assertTrue(r2.get_json().get("skipped"))
        self.assertEqual(self.get_word(wid)["ebbinghaus_stage"], 1)

    # ---- 到期必抽（取消随机抽样）----

    def test_get_due_reviews_pulls_all_due_no_sampling(self):
        w_fuzzy = self.seed_word("模糊", 2, TODAY)
        w_cons = self.seed_word("巩固", 0, TODAY)
        w_mast = self.seed_word("掌握", 0, TODAY)
        self.seed_word("掌握", 0, TODAY + timedelta(days=180))  # 未到期 → 排除
        words = rs.get_due_reviews(limit=10)
        ids = [w["word_id"] for w in words]
        self.assertEqual(ids, [w_fuzzy, w_cons, w_mast])  # 模糊优先、全部拉取
        self.assertEqual([w["status"] for w in words], ["模糊", "巩固", "掌握"])

    def test_get_due_count_counts_all_statuses(self):
        self.seed_word("模糊", 0, TODAY)
        self.seed_word("巩固", 0, TODAY)
        self.seed_word("掌握", 0, TODAY)
        self.seed_word("掌握", 0, TODAY + timedelta(days=180))
        self.assertEqual(rs.get_due_count(), 3)

    # ---- 四档反馈：recognize / vague / forget / mastered ----

    def test_review_recognize_clears_streak_and_counts(self):
        wid = self.seed_word("模糊", 0, TODAY)
        self.client.post("/api/study/answer", json={
            "word_id": wid, "feedback": "recognize", "mode": "review",
        })
        row = self.get_word(wid)
        self.assertEqual(row["correct_count"], 1)
        self.assertEqual(row["wrong_streak"], 0)
        self.assertFalse(row["vague_flagged"])
        # recognize 不推进节点、不改到期日
        self.assertEqual(row["ebbinghaus_stage"], 0)
        self.assertEqual(row["next_review"], _iso(TODAY))

    def test_review_vague_soft_pass_marks_flag(self):
        wid = self.seed_word("模糊", 0, TODAY)
        resp = self.client.post("/api/study/answer", json={
            "word_id": wid, "feedback": "vague", "mode": "review",
        })
        self.assertTrue(resp.get_json()["result"]["soft_pass"])
        row = self.get_word(wid)
        self.assertEqual(row["vague_flagged"], 1)   # 当日模糊标记
        self.assertFalse(row["wrong_streak"])        # 不打断连错
        self.assertEqual(row["ebbinghaus_stage"], 0)  # 不推进
        self.assertEqual(row["next_review"], _iso(TODAY))  # 到期日不变

    def test_review_forget_first_error_due_today(self):
        wid = self.seed_word("模糊", 0, TODAY)
        self.client.post("/api/study/answer", json={
            "word_id": wid, "feedback": "forget", "mode": "review",
        })
        row = self.get_word(wid)
        self.assertEqual(row["wrong_streak"], 1)
        # 错词必复现兜底：首错后当天仍在到期队列
        self.assertEqual(row["next_review"], _iso(TODAY))
        self.assertEqual(row["consecutive_correct"], 0)

    def test_review_mastered_graduates_immediately(self):
        wid = self.seed_word("掌握", 1, TODAY)
        resp = self.client.post("/api/study/answer", json={
            "word_id": wid, "feedback": "mastered", "mode": "review",
        })
        self.assertTrue(resp.get_json()["result"]["graduated"])
        row = self.get_word(wid)
        self.assertEqual(row["status"], "熟记")
        self.assertEqual(row["ebbinghaus_stage"], 99)
        self.assertIsNone(row["next_review"])

    def test_bool_correct_maps_to_recognize_forget(self):
        wid = self.seed_word("模糊", 0, TODAY)
        self.client.post("/api/study/answer", json={"word_id": wid, "correct": True, "mode": "review"})
        self.assertEqual(self.get_word(wid)["wrong_streak"], 0)
        self.client.post("/api/study/answer", json={"word_id": wid, "correct": False, "mode": "review"})
        self.assertEqual(self.get_word(wid)["wrong_streak"], 1)

    # ---- 模糊软过关 → 完成时原地巩固（不推进 stage）----

    def test_vague_then_complete_consolidates_in_place(self):
        wid = self.seed_word("模糊", 0, TODAY, frequency=5)
        self.client.post("/api/study/answer", json={
            "word_id": wid, "feedback": "vague", "mode": "review",
        })
        r = self.client.post("/api/study/review-word-complete", json={"word_id": wid}).get_json()
        self.assertTrue(r.get("consolidated"))
        self.assertEqual(r["stage"], 0)  # 原地巩固，stage 不推进
        # 下次间隔取当前 stage（模糊[1]）→ 明天；若推进应是 2 天（快线 intervals[1]）
        self.assertEqual(r["next_review"], _iso(TODAY + timedelta(days=1)))
        row = self.get_word(wid)
        self.assertFalse(row["vague_flagged"])  # 推进后清标记

    def test_recognize_after_vague_keeps_consolidation(self):
        # 同轮内标过模糊 → 即使后面答对，完成仍原地巩固
        wid = self.seed_word("模糊", 1, TODAY, frequency=5)
        self.client.post("/api/study/answer", json={"word_id": wid, "feedback": "vague", "mode": "review"})
        self.client.post("/api/study/answer", json={"word_id": wid, "feedback": "recognize", "mode": "review"})
        r = self.client.post("/api/study/review-word-complete", json={"word_id": wid}).get_json()
        self.assertTrue(r.get("consolidated"))
        self.assertEqual(r["stage"], 1)
        # 原地巩固：next_review = today + 快线[1] = today+2；若推进则 today+4
        self.assertEqual(r["next_review"], _iso(TODAY + timedelta(days=2)))

    # ---- 分档间隔：低频慢线 ----

    def test_low_freq_slow_line_fuzzy_chain(self):
        wid = self.seed_word("模糊", 0, TODAY, frequency=2)
        expected = [(1, TODAY + timedelta(days=4)), (2, TODAY + timedelta(days=8)),
                    (3, TODAY + timedelta(days=15)), (4, TODAY + timedelta(days=30))]
        for stage, nxt in expected:
            self.make_due(wid)
            r = rs.advance_word(wid)
            self.assertEqual(r["stage"], stage)
            self.assertEqual(r["next_review"], _iso(nxt))
        # 最后一格 → 升入巩固（慢线首间隔 60 天）
        self.make_due(wid)
        r = rs.advance_word(wid)
        self.assertEqual(r["status"], "巩固")
        self.assertEqual(r["next_review"], _iso(TODAY + timedelta(days=60)))

    def test_low_freq_mastered_interval_365(self):
        wid = self.seed_word("巩固", 2, TODAY, frequency=1)
        self.make_due(wid)
        r = rs.advance_word(wid)  # 巩固走完 → 掌握，慢线首间隔 365
        self.assertEqual(r["status"], "掌握")
        self.assertEqual(r["next_review"], _iso(TODAY + timedelta(days=365)))

    def test_high_freq_fast_line_keeps_classic(self):
        wid = self.seed_word("模糊", 0, TODAY, frequency=5)
        self.make_due(wid)
        r = rs.advance_word(wid)
        self.assertEqual(r["next_review"], _iso(TODAY + timedelta(days=2)))  # 快线[1]=2

    # ---- preview_review 预期间隔预览 ----

    def test_preview_review_four_outcomes(self):
        wid = self.seed_word("模糊", 1, TODAY, frequency=5)
        p = rs.preview_review(wid)
        self.assertEqual(p["status"], "模糊")
        self.assertEqual(p["stage"], 1)
        # recognize → 推进到 stage2 → 快线[2]=4 天后
        self.assertEqual(p["recognize"]["days"], 4)
        # vague → 原地巩固 → 当前 stage 间隔 快线[1]=2 天后
        self.assertEqual(p["vague"]["days"], 2)
        # forget → 今日复现
        self.assertEqual(p["forget"]["days"], 0)
        self.assertIn("今日复现", p["forget"]["label"])
        # mastered → 毕业
        self.assertEqual(p["mastered"]["status"], "熟记")

    def test_preview_review_low_freq_line(self):
        wid = self.seed_word("模糊", 0, TODAY, frequency=2)
        p = rs.preview_review(wid)
        self.assertEqual(p["vague"]["days"], 2)      # 慢线[0]=2
        self.assertEqual(p["recognize"]["days"], 4)  # 慢线[1]=4

    def test_preview_review_endpoint(self):
        wid = self.seed_word("巩固", 0, TODAY, frequency=5)
        resp = self.client.get(f"/api/study/review-preview?word_id={wid}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["recognize"]["days"], 60)  # 巩固快线[1]=60

    # ---- 词库维度系数 ----

    def test_vocabulary_dimension_consolidating_factor(self):
        expected = {"陌生": 0, "模糊": 35, "巩固": 50, "掌握": 75, "熟记": 100}
        for status, score in expected.items():
            with self.subTest(status=status):
                wid = self.seed_word(status, 0, TODAY)
                db = database.get_db()
                performance, _, evidence = _vocabulary_dimension(db)
                db.close()
                self.assertEqual(performance, score)
                self.assertEqual(evidence["studied_words"], 1 if status != "陌生" else 0)
                self.assertEqual(evidence["mastered_words"],
                                 1 if status in ("巩固", "掌握", "熟记") else 0)
                # 清掉本轮种子，避免污染下一个 subTest
                db = database.get_db()
                db.execute("DELETE FROM user_words WHERE word_id=?", (wid,))
                db.execute("DELETE FROM words WHERE id=?", (wid,))
                db.commit()
                db.close()


if __name__ == "__main__":
    unittest.main()

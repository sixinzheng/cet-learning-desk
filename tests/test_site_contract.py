import pathlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import config
from app import create_app
from config import get_api_key
from database import get_db


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RouteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True
        cls.client = cls.app.test_client()

    def test_primary_pages_render(self):
        for path in (
            "/",
            "/learn",
            "/growth",
            "/profile",
            "/study",
            "/review",
            "/reading",
            "/listening",
            "/cloze",
            "/writing",
            "/notes",
            "/export",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_legacy_growth_routes_redirect_to_growth_sections(self):
        expected = {
            "/level": "/growth#rank",
            "/summary": "/growth#summary",
        }
        for path, location in expected.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers["Location"].endswith(location))

    def test_unknown_page_returns_branded_404(self):
        response = self.client.get("/page-that-does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn("页面没有找到".encode("utf-8"), response.data)

    def test_notes_blueprint_is_registered(self):
        response = self.client.get("/api/notes/history")
        self.assertEqual(response.status_code, 200)

    def test_historical_note_update_and_delete_are_scoped(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute(
            "CREATE TABLE notes (note_date TEXT PRIMARY KEY, content TEXT, ai_summary TEXT DEFAULT '', has_ai_summary INTEGER DEFAULT 0)"
        )
        db.execute(
            "INSERT INTO notes (note_date, content, ai_summary, has_ai_summary) VALUES (?, ?, ?, 1)",
            ("2026-08-01", "原始笔记", "原有总结"),
        )
        db.commit()
        with patch("routes.api_notes.get_db", return_value=db):
            updated = self.client.put("/api/notes/2026-08-01", json={"content": "修改后的笔记"})
            self.assertEqual(updated.status_code, 200)
            detail = self.client.get("/api/notes/detail/2026-08-01").get_json()
            self.assertEqual(detail["content"], "修改后的笔记")
            self.assertEqual(detail["ai_summary"], "原有总结")
            invalid = self.client.put("/api/notes/08-01-2026", json={"content": "无效"})
            self.assertEqual(invalid.status_code, 400)
            deleted = self.client.delete("/api/notes/2026-08-01")
            self.assertEqual(deleted.status_code, 200)
            self.assertEqual(self.client.get("/api/notes/detail/2026-08-01").status_code, 404)
        db.close()

    def test_export_word_writes_plain_text_and_downloads(self):
        db = get_db()
        question = db.execute("SELECT id FROM reading_questions LIMIT 1").fetchone()
        db.close()
        self.assertIsNotNone(question)
        with tempfile.TemporaryDirectory() as tmp:
            original = config.DATA_DIR
            config.DATA_DIR = tmp
            try:
                response = self.client.post(
                    "/api/export/word",
                    json={"items": [{"type": "reading", "id": question["id"]}]},
                )
                self.assertEqual(response.status_code, 200)
                filename = response.get_json()["file"]
                content = (pathlib.Path(tmp) / filename).read_text(encoding="utf-8")
                self.assertIn("[阅读]", content)
                self.assertIn("导出日期:", content)
                download = self.client.get(f"/api/export/download/{filename}")
                self.assertEqual(download.status_code, 200)
                self.assertIn("text/plain", download.headers.get("Content-Type", ""))
                self.assertIn("[阅读]".encode("utf-8"), download.data)
                download.close()
            finally:
                config.DATA_DIR = original

    def test_profile_reports_ai_state_without_exposing_secret(self):
        response = self.client.get("/profile")
        self.assertIn(b'data-ai-configured=', response.data)
        secret = get_api_key()
        if secret:
            self.assertNotIn(secret.encode("utf-8"), response.data)

    def test_daily_setting_round_trip_keeps_current_value(self):
        current = self.client.get("/api/study/daily-setting").get_json()["count"]
        saved = self.client.put("/api/study/daily-setting", json={"count": current})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["count"], current)
        self.assertEqual(self.client.get("/api/study/daily-setting").get_json()["count"], current)

    def test_dashboard_exposes_home_task_progress_fields(self):
        response = self.client.get("/api/study/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        for key in ("daily_target", "learned_today", "reviewed_today", "review_goal", "review_due_remaining"):
            with self.subTest(key=key):
                self.assertIn(key, data)
        self.assertEqual(data["daily_target"], data["review_goal"])

    def test_achievement_84_returns_real_visualization_metrics(self):
        response = self.client.get("/api/study/achievement-84")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(
            set(data),
            {"active_days", "total_minutes", "review_count", "longest_streak", "best_day", "mastered_words", "milestone"},
        )
        for key in ("active_days", "total_minutes", "review_count", "longest_streak", "mastered_words"):
            self.assertGreaterEqual(data[key], 0)
        self.assertIn("date", data["best_day"])
        self.assertIn("minutes", data["best_day"])
        self.assertGreater(data["milestone"]["target"], 0)
        self.assertGreaterEqual(data["milestone"]["progress"], 0)
        self.assertLessEqual(data["milestone"]["progress"], 100)

    def test_level_detail_exposes_evidence_bounded_assessment(self):
        response = self.client.get("/api/level/detail")
        self.assertEqual(response.status_code, 200)
        assessment = response.get_json()["assessment"]
        self.assertIn(assessment["evidence_level"], {"limited", "developing", "established"})
        self.assertTrue(assessment["sentence"])
        self.assertIn("scope", assessment)
        self.assertEqual(assessment["scope"], "基于本站学习记录")
        self.assertEqual(
            set(assessment["basis"]),
            {
                "active_days",
                "total_minutes",
                "mastered_words",
                "review_count",
                "reading_count",
                "listening_count",
                "writing_count",
                "covered_dimensions",
            },
        )

        if assessment["evidence_level"] == "limited":
            self.assertIn("暂不能判断是否达到四级或六级水平", assessment["sentence"])


class StaticDesignContractTests(unittest.TestCase):
    def test_base_uses_local_assets_and_four_primary_destinations(self):
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertNotIn("cdn.jsdelivr.net", base)
        for href in ('href="/"', 'href="/learn"', 'href="/growth"', 'href="/profile"'):
            self.assertIn(href, base)
        self.assertIn('class="mobile-nav"', base)
        self.assertIn('class="skip-link"', base)
        self.assertEqual(base.count('class="mobile-nav__item"'), 5)

    def test_first_run_onboarding_is_optional_replayable_and_covers_core_concepts(self):
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        script = (ROOT / "static" / "js" / "onboarding.js").read_text(encoding="utf-8")
        self.assertIn('id="onboarding-overlay"', base)
        self.assertEqual(base.count("data-onboarding-panel="), 4)
        for copy in ("从今天的词汇任务开始", "连接 DeepSeek", "六维成绩", "AI 负责提效"):
            self.assertIn(copy, base)
        self.assertIn("跳过引导", base)
        self.assertIn("cet-onboarding-v1", script)
        self.assertIn("window.location.pathname === '/'", script)
        self.assertIn("cet:open-onboarding", script)
        self.assertIn("/api/ai/config/verify-save", script)
        self.assertIn('id="open-deepseek-guide"', base)
        self.assertIn('id="deepseek-guide-overlay"', base)
        self.assertIn("https://platform.deepseek.com/api_keys", base)
        for image in (
            "images/onboarding/deepseek/01-home.png",
            "images/onboarding/deepseek/02-api-keys.png",
            "images/onboarding/deepseek/03-create-key.png",
            "images/onboarding/deepseek/04-balance.png",
        ):
            self.assertIn(image, base)
            self.assertTrue((ROOT / "static" / image).is_file())
        self.assertIn("const guideSteps", script)
        self.assertIn("data-guide-src-${guideStep}", script)

    def test_profile_supports_onboarding_replay_and_author_support_codes(self):
        profile = (ROOT / "templates" / "profile.html").read_text(encoding="utf-8")
        for element_id in ("open-onboarding", "support-author-button", "support-modal"):
            self.assertIn(f'id="{element_id}"', profile)
        self.assertIn("images/support/wechat-pay.png", profile)
        self.assertIn("images/support/alipay.jpg", profile)
        self.assertTrue((ROOT / "static" / "images" / "support" / "wechat-pay.png").is_file())
        self.assertTrue((ROOT / "static" / "images" / "support" / "alipay.jpg").is_file())
        self.assertIn("量力而行", profile)

    def test_profile_wordbooks_precede_support_in_navigation_and_content(self):
        profile = (ROOT / "templates" / "profile.html").read_text(encoding="utf-8")
        navigation = profile[profile.index('<nav class="settings-index"'):profile.index('</nav>')]
        self.assertLess(navigation.index('href="#wordbooks"'), navigation.index('href="#support"'))
        self.assertLess(profile.index('id="wordbooks"'), profile.index('id="support"'))

    def test_bilingual_assistant_controls_exist_on_home_and_notes_only(self):
        home = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        notes = (ROOT / "templates" / "notes.html").read_text(encoding="utf-8")
        control = (ROOT / "templates" / "control.html").read_text(encoding="utf-8")
        for document in (home, notes):
            self.assertIn('data-assistant-language="zh"', document)
            self.assertIn('data-assistant-language="en"', document)
        self.assertNotIn('data-assistant-language', control)
        self.assertIn('notes-scene-grid', notes)
        self.assertIn('home-scene-select', home)

    def test_design_tokens_and_breakpoints_are_declared(self):
        css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn("--indigo: #303b67", css.lower())
        self.assertIn("--vermilion: #c4553e", css.lower())
        self.assertIn("--paper: #f5f0e7", css.lower())
        self.assertIn("@media (min-width: 1200px)", css)
        self.assertIn("@media (max-width: 767px)", css)
        self.assertNotIn("backdrop-filter", css)

    def test_home_contains_only_three_core_business_blocks(self):
        home = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        required_ids = (
            "vocab-command-title",
            "wb-select",
            "daily-count",
            "learned-today",
            "reviewed-today",
            "plate-name",
            "ai-quick-chat",
        )
        for element_id in required_ids:
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', home)
        for element_id in ("ai-greeting", "ai-chat-messages", "ai-chat-form", "ai-chat-input"):
            self.assertIn(f'id="{element_id}"', home)
        for removed_id in ("freq-chart", "calendar-heatmap", "achievement-84", "special-training"):
            self.assertNotIn(f'id="{removed_id}"', home)

    def test_home_rank_and_task_have_requested_hierarchy(self):
        home = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        for element_id in (
            "task-book-cover",
            "task-book-title",
            "rank-figure",
            "rank-ring-progress",
            "home-rank-advice",
            "ai-quick-chat",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', home)
        vocab_start = home.index('class="vocab-command"')
        chat_start = home.index('id="ai-quick-chat"')
        rank_start = home.index('class="rank-card rank-card--summary"')
        self.assertLess(vocab_start, chat_start)
        self.assertLess(chat_start, rank_start)

    def test_ai_surfaces_are_visible_and_growth_has_three_radars(self):
        profile = (ROOT / "templates" / "profile.html").read_text(encoding="utf-8")
        notes = (ROOT / "templates" / "notes.html").read_text(encoding="utf-8")
        growth = (ROOT / "templates" / "growth.html").read_text(encoding="utf-8")
        cloze = (ROOT / "templates" / "cloze.html").read_text(encoding="utf-8")
        for marker in ("ai-key-input", "ai-key-save", "ai-balance", "ai-key-delete"):
            self.assertIn(f'id="{marker}"', profile)
        for marker in ("profile-skills", "skill-create-form", "wordbooks"):
            self.assertIn(f'id="{marker}"', profile)
        for marker in ("notes-ai-chat", "notes-ai-memories", "notes-ai-search", "note-history-list", "note-manager-modal", "note-manager-drawer", "note-manager-open"):
            self.assertIn(f'id="{marker}"', notes)
        for marker in ("g-radar-performance", "g-radar-practice", "g-radar-mastery", "g-ai-usage", "g-achievements", "g-achievements-active", "g-achievements-review"):
            self.assertIn(f'id="{marker}"', growth)
        self.assertIn('id="cloze-submit"', cloze)

        for marker in ("g-ai-calls", "g-ai-success", "g-ai-tokens", "g-ai-cost", "g-ai-balance", "g-ai-heatmap", "g-ai-day-detail", "g-ai-outcomes"):
            self.assertIn(f'id="{marker}"', growth)
        for removed_marker in ("g-ai-features", "g-ai-greetings", "g-ai-topics"):
            self.assertNotIn(f'id="{removed_marker}"', growth)

    def test_home_has_task_progress_and_dynamic_advice(self):
        home = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        for element_id in (
            "learned-today",
            "learn-goal",
            "reviewed-today",
            "review-goal",
            "remaining-review",
            "task-advice-title",
            "task-advice-counts",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', home)

    def test_home_uses_condensed_level_assessment(self):
        home = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("学习热力图", home)
        for element_id in ("rank-capability", "level-confidence-display", "home-rank-advice"):
            self.assertIn(f'id="{element_id}"', home)

    def test_javascript_files_do_not_contain_template_closing_tags(self):
        for path in (ROOT / "static" / "js").glob("*.js"):
            with self.subTest(path=path.name):
                self.assertNotIn("</script>", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

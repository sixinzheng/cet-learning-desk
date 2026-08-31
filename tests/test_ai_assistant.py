import json
import os
import re
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

import config
import database
from app import create_app
from services.ai_service import AIServiceError, VISION_MODEL, call_multimodal


class AIAssistantContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        self.original_config_path = config.CONFIG_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        config.CONFIG_PATH = os.path.join(self.temp_dir.name, "config.json")
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        config.delete_api_key()
        database.DB_PATH = self.original_db_path
        config.CONFIG_PATH = self.original_config_path
        self.temp_dir.cleanup()

    def csrf(self):
        response = self.client.get("/api/ai/config/status")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["csrf_token"]

    def test_api_key_is_encrypted_and_round_trips_for_current_windows_user(self):
        secret = "test-secret-value"
        config.save_api_key(secret)
        with open(config.CONFIG_PATH, encoding="utf-8") as handle:
            raw = handle.read()
        self.assertNotIn(secret, raw)
        self.assertIn("deepseek_api_key_encrypted", raw)
        self.assertEqual(config.get_api_key(), secret)

    def test_ai_schema_migration_is_idempotent(self):
        database.init_db()
        database.init_db()
        db = database.get_db()
        tables = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        db.close()
        self.assertTrue({
            "ai_usage_events", "ai_conversations", "ai_messages", "ai_memories",
            "ai_daily_greetings", "ai_action_drafts", "site_skills",
        }.issubset(tables))

    def test_unreadable_legacy_key_reports_one_time_recovery(self):
        cfg = config.load_config()
        cfg["deepseek_api_key_encrypted"] = "not-a-valid-dpapi-blob"
        cfg["deepseek_key_suffix"] = "7788"
        config.save_config(cfg)
        with mock.patch.object(config, "_read_credential", return_value=""):
            status = config.get_api_key_status()
        self.assertFalse(status["configured"])
        self.assertTrue(status["key_material_present"])
        self.assertTrue(status["recovery_required"])
        self.assertEqual(status["storage_backend"], "unreadable_dpapi")

    def test_skill_directory_can_toggle_and_manage_custom_skills(self):
        token = self.csrf()
        listing = self.client.get("/api/ai/skills").get_json()["skills"]
        self.assertGreaterEqual(len(listing), 5)
        reading = next(item for item in listing if item["slug"] == "reading-curator")
        disabled = self.client.put(
            "/api/ai/skills/reading-curator",
            json={"enabled": False}, headers={"X-CSRF-Token": token},
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.get_json()["skill"]["enabled"])
        created = self.client.post(
            "/api/ai/skills", json={"display_name": "翻译复盘", "user_instructions": "引用原句。"},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(created.status_code, 201)
        slug = created.get_json()["skill"]["slug"]
        removed = self.client.delete(f"/api/ai/skills/{slug}", headers={"X-CSRF-Token": token})
        self.assertEqual(removed.status_code, 200)
        protected = self.client.delete(
            "/api/ai/skills/reading-curator", headers={"X-CSRF-Token": token}
        )
        self.assertEqual(protected.status_code, 409)

    def test_usage_returns_only_verifiable_outcomes(self):
        db = database.get_db()
        db.execute(
            """INSERT INTO reading_articles
               (title,content,word_count,difficulty,topic,origin,date_added)
               VALUES ('AI article','Original facts.',2,3,'科技','ai_adapted',date('now','localtime'))"""
        )
        article_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.execute(
            """INSERT INTO reading_questions
               (article_id,question_type,question,options,answer,explanation,evidence_text)
               VALUES (?,?,?,?,?,?,?)""",
            (article_id, "detail", "Q?", '["a","b","c","d"]', "A", "解析", "Original facts."),
        )
        db.execute(
            """INSERT INTO ai_usage_events (feature,model,status,total_tokens,cost_cny)
               VALUES ('quick_chat','deepseek-v4-flash','success',20,0.0001)"""
        )
        db.execute(
            """INSERT INTO ai_action_drafts
               (action_type,payload_json,status,idempotency_key,confirmed_at)
               VALUES ('append_note','{}','confirmed','usage-note-1',datetime('now','localtime'))"""
        )
        db.commit(); db.close()
        outcomes = {item["key"]: item for item in self.client.get("/api/ai/usage?days=84").get_json()["outcomes"]}
        self.assertEqual(outcomes["curated_articles"]["count"], 1)
        self.assertEqual(outcomes["curated_questions"]["count"], 1)
        self.assertEqual(outcomes["notes_confirmed"]["count"], 1)
        self.assertEqual(outcomes["questions_answered"]["count"], 1)

    def test_config_status_never_exposes_full_key(self):
        config.save_api_key("test-visible-only-at-provider-1234")
        response = self.client.get("/api/ai/config/status")
        data = response.get_json()
        self.assertTrue(data["configured"])
        self.assertEqual(data["key_suffix"], "1234")
        self.assertNotIn("test-visible-only-at-provider", response.get_data(as_text=True))
        self.assertEqual(data["model"], "deepseek-v4-flash")

    def test_chat_context_contains_current_official_rank(self):
        config.save_api_key("test-rank-context")
        headers = {"X-CSRF-Token": self.csrf()}
        stream_result = iter([
            {"type": "delta", "text": "你当前是童生。"},
            {"type": "done", "content": "你当前是童生。", "usage": {}, "model": "deepseek-v4-flash"},
        ])
        with mock.patch("routes.api_ai.stream_deepseek", return_value=stream_result) as model:
            response = self.client.post(
                "/api/ai/chat", json={"message": "我现在是什么段位？"}, headers=headers,
            )
        self.assertEqual(response.status_code, 200)
        prompt = model.call_args.args[0][1]["content"]
        self.assertIn('"name": "童生"', prompt)
        self.assertIn('"rank": 1', prompt)
        self.assertIn("你当前是童生", response.get_data(as_text=True))

    def test_assistant_language_preference_persists_and_rejects_invalid_value(self):
        initial = self.client.get('/api/ai/preferences').get_json()
        self.assertEqual(initial['language'], 'zh')
        self.assertEqual(len(initial['scenes']), 7)
        token = initial['csrf_token']
        saved = self.client.put('/api/ai/preferences', json={'language': 'en'}, headers={'X-CSRF-Token': token})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.client.get('/api/ai/preferences').get_json()['language'], 'en')
        invalid = self.client.put('/api/ai/preferences', json={'language': 'fr'}, headers={'X-CSRF-Token': token})
        self.assertEqual(invalid.status_code, 400)

    def test_english_scene_starts_without_fake_user_message_and_keeps_metadata(self):
        config.save_api_key('test-english-scene')
        headers = {'X-CSRF-Token': self.csrf()}
        stream_result = iter([
            {'type': 'delta', 'text': 'Your train is late—plot twist! 🚆'},
            {'type': 'done', 'content': 'Your train is late—plot twist! 🚆 What would you do first?', 'usage': {}, 'model': 'deepseek-v4-flash'},
        ])
        with mock.patch('routes.api_ai.stream_deepseek', return_value=stream_result) as model:
            response = self.client.post('/api/ai/chat', json={'language': 'en', 'scenario_key': 'travel', 'start_scene': True}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('"language": "en"', response.get_data(as_text=True))
        system_prompt = model.call_args.args[0][0]['content']
        self.assertIn('English Conversation Companion', system_prompt)
        self.assertIn('active scene is Travel', system_prompt)
        db = database.get_db()
        conversation = db.execute('SELECT * FROM ai_conversations').fetchone()
        roles = [row['role'] for row in db.execute('SELECT role FROM ai_messages ORDER BY id')]
        db.close()
        self.assertEqual(conversation['language'], 'en')
        self.assertEqual(conversation['scenario_key'], 'travel')
        self.assertEqual(roles, ['assistant'])

    def test_control_skill_chat_can_follow_global_english_mode(self):
        config.save_api_key('test-english-skill')
        stream_result = iter([
            {'type': 'done', 'content': 'Let’s sharpen that rule. ✍️', 'usage': {}, 'model': 'deepseek-v4-flash'},
        ])
        with mock.patch('routes.api_ai.stream_deepseek', return_value=stream_result) as model:
            response = self.client.post(
                '/api/ai/chat',
                json={'message': 'Help me refine this.', 'language': 'en', 'skill_slug': 'reading-curator'},
                headers={'X-CSRF-Token': self.csrf()},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn('"language": "en"', response.get_data(as_text=True))
        system_prompt = model.call_args.args[0][0]['content']
        self.assertIn('English Conversation Companion', system_prompt)
        self.assertIn('Skill', system_prompt)

    def test_chat_sends_only_the_latest_six_rounds_of_context(self):
        config.save_api_key('test-context-window')
        db = database.get_db()
        db.execute("INSERT INTO ai_conversations (title,language,scenario_key) VALUES ('Context','en','casual')")
        conversation_id = db.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
        for index in range(8):
            db.execute("INSERT INTO ai_messages (conversation_id,role,content) VALUES (?,'user',?)", (conversation_id, f'user-{index}'))
            db.execute("INSERT INTO ai_messages (conversation_id,role,content) VALUES (?,'assistant',?)", (conversation_id, f'assistant-{index}'))
        db.commit(); db.close()
        stream_result = iter([{'type': 'done', 'content': 'Got it.', 'usage': {}, 'model': 'deepseek-v4-flash'}])
        with mock.patch('routes.api_ai.stream_deepseek', return_value=stream_result) as model:
            self.client.post('/api/ai/chat', json={'message': 'latest-user', 'conversation_id': conversation_id, 'language': 'en'}, headers={'X-CSRF-Token': self.csrf()})
        messages = model.call_args.args[0]
        history_text = '\n'.join(item['content'] for item in messages[1:])
        self.assertLessEqual(len(messages[1:]), 12)
        self.assertIn('latest-user', history_text)
        self.assertIn('assistant-7', history_text)
        self.assertNotIn('user-0', history_text)

    def test_daily_greetings_are_cached_separately_by_language(self):
        zh = self.client.get('/api/ai/greeting?language=zh').get_json()
        en = self.client.get('/api/ai/greeting?language=en').get_json()
        self.assertEqual(zh['language'], 'zh')
        self.assertEqual(en['language'], 'en')
        self.assertNotEqual(zh['greeting'], en['greeting'])
        db = database.get_db()
        rows = db.execute('SELECT language,COUNT(*) AS n FROM ai_daily_greetings GROUP BY language').fetchall()
        db.close()
        self.assertEqual({row['language']: row['n'] for row in rows}, {'zh': 1, 'en': 1})

    def test_english_note_intent_creates_a_confirm_only_draft(self):
        response = self.client.post('/api/ai/chat', json={'message': 'Save this to my notes: use a softer transition.', 'language': 'en'}, headers={'X-CSRF-Token': self.csrf()})
        text = response.get_data(as_text=True)
        self.assertIn('"type": "append_note"', text)
        db = database.get_db()
        draft = db.execute('SELECT status,payload_json FROM ai_action_drafts').fetchone()
        note_count = db.execute('SELECT COUNT(*) AS n FROM notes').fetchone()['n']
        db.close()
        self.assertEqual(draft['status'], 'pending')
        self.assertEqual(note_count, 0)

    def test_existing_conversation_language_and_scene_are_immutable(self):
        db = database.get_db()
        db.execute("INSERT INTO ai_conversations (title,language,scenario_key) VALUES ('旧对话','zh','casual')")
        conversation_id = db.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
        db.commit(); db.close()
        response = self.client.post(
            '/api/ai/chat',
            json={'message': 'Please switch this old thread.', 'conversation_id': conversation_id, 'language': 'en', 'scenario_key': 'travel'},
            headers={'X-CSRF-Token': self.csrf()},
        )
        self.assertEqual(response.status_code, 200)
        db = database.get_db()
        conversation = db.execute('SELECT language,scenario_key FROM ai_conversations WHERE id=?', (conversation_id,)).fetchone()
        db.close()
        self.assertEqual((conversation['language'], conversation['scenario_key']), ('zh', 'casual'))

    def test_chinese_rescue_changes_one_reply_without_changing_english_mode(self):
        config.save_api_key('test-one-turn-rescue')
        headers = {'X-CSRF-Token': self.csrf()}
        streams = [
            iter([{'type':'done','content':'这句话的意思是……','usage':{},'model':'deepseek-v4-flash'}]),
            iter([{'type':'done','content':'Back to English.','usage':{},'model':'deepseek-v4-flash'}]),
        ]
        with mock.patch('routes.api_ai.stream_deepseek', side_effect=streams) as model:
            first = self.client.post('/api/ai/chat', json={'message':'Please explain the last point in Chinese for this reply only.', 'language':'en'}, headers=headers)
            conversation_id = int(re.search(r'"conversation_id": (\d+)', first.get_data(as_text=True)).group(1))
            self.client.post('/api/ai/chat', json={'message':'Thanks—keep going.', 'conversation_id':conversation_id, 'language':'en'}, headers=headers)
        first_system = model.call_args_list[0].args[0][0]['content']
        second_system = model.call_args_list[1].args[0][0]['content']
        self.assertIn('For this reply only', first_system)
        self.assertNotIn('For this reply only', second_system)
        db = database.get_db()
        language = db.execute('SELECT language FROM ai_conversations WHERE id=?', (conversation_id,)).fetchone()['language']
        db.close()
        self.assertEqual(language, 'en')

    def test_disabled_english_companion_does_not_create_empty_conversation(self):
        token = self.csrf()
        self.client.put('/api/ai/skills/english-conversation-companion', json={'enabled':False}, headers={'X-CSRF-Token':token})
        response = self.client.post('/api/ai/chat', json={'language':'en','scenario_key':'daily','start_scene':True}, headers={'X-CSRF-Token':token})
        self.assertEqual(response.status_code, 409)
        db = database.get_db()
        count = db.execute('SELECT COUNT(*) AS n FROM ai_conversations').fetchone()['n']
        db.close()
        self.assertEqual(count, 0)

    def test_deepseek_image_input_uses_official_experimental_vision_model(self):
        config.save_api_key("sk-test")
        response = mock.Mock(status_code=200)
        response.json.return_value = {
            "model": VISION_MODEL,
            "choices": [{"message": {"content": "图片里是一道英语题。"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
        }
        with mock.patch("services.ai_service.requests.post", return_value=response) as post:
            answer = call_multimodal("请看图", ["data:image/png;base64,AAAA"])
        self.assertEqual(answer, "图片里是一道英语题。")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], VISION_MODEL)
        self.assertEqual(body["messages"][1]["content"][1]["type"], "image_url")

    def test_deepseek_image_input_rejects_unsupported_type_before_network(self):
        config.save_api_key("sk-test")
        with mock.patch("services.ai_service.requests.post") as post:
            with self.assertRaises(AIServiceError) as raised:
                call_multimodal("请看图", ["data:image/svg+xml;base64,AAAA"])
        self.assertEqual(raised.exception.code, "invalid_image_type")
        post.assert_not_called()

    def test_daily_greeting_is_reused_on_repeated_home_visits(self):
        first = self.client.get("/api/ai/greeting")
        second = self.client.get("/api/ai/greeting")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["greeting"], second.get_json()["greeting"])
        db = database.get_db()
        count = db.execute("SELECT COUNT(*) AS n FROM ai_daily_greetings").fetchone()["n"]
        db.close()
        self.assertEqual(count, 1)
        self.assertIn(first.get_json()["source"], {"ai", "local"})

    def test_greeting_for_long_absence_uses_caring_tone(self):
        old = (date.today() - timedelta(days=10)).isoformat()
        db = database.get_db()
        db.execute(
            "INSERT INTO study_logs (study_date, total_minutes) VALUES (?, 15)",
            (old,),
        )
        db.commit()
        db.close()
        greeting = self.client.get("/api/ai/greeting").get_json()["greeting"]
        self.assertIn("这么久", greeting)
        self.assertIn("聊聊", greeting)
        self.assertNotIn("追进度", greeting)
        self.assertNotIn("建议先", greeting)

    def test_confirm_note_action_appends_once_and_never_overwrites(self):
        today = date.today().isoformat()
        db = database.get_db()
        db.execute("INSERT INTO notes (note_date, content) VALUES (?, '原有笔记')", (today,))
        db.execute(
            "INSERT INTO ai_action_drafts (action_type, payload_json, status, idempotency_key) "
            "VALUES ('append_note', ?, 'pending', 'draft-once')",
            (json.dumps({"content": "新增知识点"}, ensure_ascii=False),),
        )
        draft_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.commit()
        db.close()
        headers = {"X-CSRF-Token": self.csrf()}
        first = self.client.post(f"/api/ai/actions/{draft_id}/confirm", headers=headers)
        second = self.client.post(f"/api/ai/actions/{draft_id}/confirm", headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        db = database.get_db()
        content = db.execute("SELECT content FROM notes WHERE note_date=?", (today,)).fetchone()["content"]
        db.close()
        self.assertEqual(content.count("新增知识点"), 1)
        self.assertTrue(content.startswith("原有笔记"))

    def test_usage_summary_distinguishes_tracked_spend_and_failures(self):
        db = database.get_db()
        db.execute(
            "INSERT INTO ai_usage_events "
            "(feature, model, status, prompt_tokens, completion_tokens, cache_hit_tokens, "
            "cache_miss_tokens, total_tokens, cost_cny, latency_ms, created_at) "
            "VALUES ('essay_correction','deepseek-v4-flash','success',100,50,40,60,150,0.002,900,datetime('now'))"
        )
        db.execute(
            "INSERT INTO ai_usage_events "
            "(feature, model, status, total_tokens, cost_cny, latency_ms, created_at) "
            "VALUES ('quick_chat','deepseek-v4-flash','error',0,0,300,datetime('now'))"
        )
        db.commit()
        db.close()
        data = self.client.get("/api/ai/usage?days=84").get_json()
        self.assertEqual(data["totals"]["calls"], 2)
        self.assertEqual(data["totals"]["successful"], 1)
        self.assertEqual(data["totals"]["failed"], 1)
        self.assertEqual(data["totals"]["tokens"], 150)
        self.assertAlmostEqual(data["totals"]["tracked_cost_cny"], 0.002)
        self.assertFalse(data["history_complete"])

    def test_usage_reports_recent_greetings_and_conversation_topics(self):
        db = database.get_db()
        db.execute(
            "INSERT INTO ai_daily_greetings (greeting_date, greeting, source) "
            "VALUES (date('now'), '今天也要加油呀', 'local')"
        )
        db.execute("INSERT INTO ai_conversations (title) VALUES ('定语从句怎么用')")
        db.commit()
        db.close()
        data = self.client.get("/api/ai/usage?days=84").get_json()
        self.assertEqual(len(data["recent_greetings"]), 1)
        self.assertEqual(data["recent_greetings"][0]["greeting"], "今天也要加油呀")
        self.assertEqual(len(data["recent_conversations"]), 1)
        self.assertEqual(data["recent_conversations"][0]["title"], "定语从句怎么用")

    def test_conversation_can_be_deleted_with_cascade(self):
        db = database.get_db()
        db.execute("INSERT INTO ai_conversations (title) VALUES ('阅读里不懂的长难句')")
        conversation_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.execute(
            "INSERT INTO ai_messages (conversation_id, role, content) VALUES (?, 'user', '什么是长难句')",
            (conversation_id,),
        )
        db.commit()
        db.close()
        listed = self.client.get("/api/ai/conversations").get_json()["conversations"]
        self.assertEqual(len(listed), 1)
        response = self.client.delete(
            f"/api/ai/conversations/{conversation_id}", headers={"X-CSRF-Token": self.csrf()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/ai/conversations").get_json()["conversations"], [])
        db = database.get_db()
        count = db.execute("SELECT COUNT(*) AS n FROM ai_messages").fetchone()["n"]
        db.close()
        self.assertEqual(count, 0)

    def test_memory_is_read_only_but_can_be_deleted(self):
        db = database.get_db()
        db.execute(
            "INSERT INTO ai_memories (memory_type, content, evidence_json, confirmed, active) "
            "VALUES ('system_fact','最近更常练习语法','{}',1,1)"
        )
        memory_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.commit()
        db.close()
        listed = self.client.get("/api/ai/memories").get_json()["memories"]
        self.assertEqual(listed[0]["content"], "最近更常练习语法")
        response = self.client.delete(
            f"/api/ai/memories/{memory_id}", headers={"X-CSRF-Token": self.csrf()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/ai/memories").get_json()["memories"], [])

    def test_conversation_memory_requires_explicit_confirmation(self):
        headers = {"X-CSRF-Token": self.csrf()}
        response = self.client.post(
            "/api/ai/memories/confirm", headers=headers,
            json={"content": "我的四级考试目标是十二月", "idempotency_key": "memory-once"},
        )
        self.assertEqual(response.status_code, 200)
        second = self.client.post(
            "/api/ai/memories/confirm", headers=headers,
            json={"content": "我的四级考试目标是十二月", "idempotency_key": "memory-once"},
        )
        self.assertEqual(second.status_code, 200)
        memories = self.client.get("/api/ai/memories").get_json()["memories"]
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["memory_type"], "conversation_fact")


if __name__ == "__main__":
    unittest.main()

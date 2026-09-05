import json
import http.client
import os
import shutil
import socket
import sqlite3
import ssl
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

import database
from app import create_app
from runtime_paths import SEED_DB_PATH
from services import device_sync_service
from services.device_sync_data import (
    DeviceSyncError,
    apply_package,
    build_sync_report,
    commit_prepared_package,
    export_package,
    merge_packages,
    prepare_package,
    validate_package,
)


class DeviceSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        self.paths = [os.path.join(self.temp_dir.name, f"device-{index}.db") for index in (1, 2)]
        for path in self.paths:
            shutil.copy2(SEED_DB_PATH, path)
            database.DB_PATH = path
            database.init_db()

    def tearDown(self):
        device_sync_service.stop_session()
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _db(self, index):
        database.DB_PATH = self.paths[index]
        return database.get_db()

    def test_bidirectional_merge_is_idempotent_and_excludes_secrets(self):
        db = self._db(0)
        word = db.execute("SELECT id FROM words ORDER BY id LIMIT 1").fetchone()[0]
        db.execute("INSERT OR REPLACE INTO user_words(word_id,status,review_count,last_reviewed) VALUES(?,?,?,?)", (word, "掌握", 3, "2026-09-01T09:00:00Z"))
        db.execute("INSERT INTO notes(category_id,title,content,note_date,created_at,updated_at) VALUES(0,'电脑笔记','desktop','2026-09-01','2026-09-01T08:00:00Z','2026-09-01T08:00:00Z')")
        db.execute("INSERT OR REPLACE INTO user_settings(key,value) VALUES('training_difficulty','4')")
        db.execute("INSERT OR REPLACE INTO user_settings(key,value) VALUES('session_secret','must-not-sync')")
        db.commit(); db.close()
        desktop = export_package()

        db = self._db(1)
        word = db.execute("SELECT id FROM words ORDER BY id LIMIT 1 OFFSET 1").fetchone()[0]
        favorite = db.execute("SELECT id FROM wordbooks WHERE name='我的收藏'").fetchone()[0]
        db.execute("INSERT OR IGNORE INTO wordbook_words(wordbook_id,word_id) VALUES(?,?)", (favorite, word))
        db.execute("INSERT INTO notes(category_id,title,content,note_date,created_at,updated_at) VALUES(0,'手机笔记','mobile','2026-09-02','2026-09-02T08:00:00Z','2026-09-02T08:00:00Z')")
        db.commit(); db.close()
        mobile = export_package()

        raw = json.dumps([desktop, mobile], ensure_ascii=False).lower()
        self.assertNotIn("must-not-sync", raw)
        self.assertNotIn("session_secret", raw)
        merged = merge_packages(desktop, mobile)
        self.assertEqual(len(merged["data"]["notes"]), 2)
        self.assertEqual(len(merged["data"]["favorites"]), 1)

        for index in (0, 1):
            database.DB_PATH = self.paths[index]
            apply_package(merged, peer=merged["merged_devices"][1 - index])
            apply_package(merged, peer=merged["merged_devices"][1 - index])
            db = database.get_db()
            self.assertEqual(db.execute("SELECT COUNT(*) FROM notes WHERE title IN ('电脑笔记','手机笔记')").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM wordbook_words wbw JOIN wordbooks wb ON wb.id=wbw.wordbook_id WHERE wb.name='我的收藏'").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA quick_check").fetchone()[0], "ok")
            db.close()

    def test_checksum_tamper_and_protocol_mismatch_are_rejected(self):
        database.DB_PATH = self.paths[0]
        package = export_package()
        package["data"]["favorites"].append("tampered")
        with self.assertRaises(DeviceSyncError) as caught:
            validate_package(package)
        self.assertEqual(caught.exception.code, "checksum_failed")

        package = export_package()
        package["protocol_version"] = 99
        with self.assertRaises(DeviceSyncError) as caught:
            validate_package(package)
        self.assertEqual(caught.exception.code, "protocol_mismatch")

    def test_device_and_record_uuids_are_stable_across_exports(self):
        database.DB_PATH = self.paths[0]
        first = export_package()
        second = export_package()
        self.assertEqual(first["device"]["device_id"], second["device"]["device_id"])
        first_meta = {
            (item["entity_type"], item["entity_key"]): item["record_uuid"]
            for item in first["data"]["record_meta"]
        }
        second_meta = {
            (item["entity_type"], item["entity_key"]): item["record_uuid"]
            for item in second["data"]["record_meta"]
        }
        self.assertTrue(first_meta)
        self.assertEqual(first_meta, second_meta)
        for item in second["data"]["record_meta"]:
            uuid.UUID(item["record_uuid"])
            self.assertTrue(item["modified_at_utc"].endswith("Z"))

    def test_record_metadata_controls_word_and_setting_conflicts(self):
        packages = []
        for index, (status, reviews, difficulty, changed_at) in enumerate((
            ("掌握", 7, "3", "2026-09-01T08:00:00Z"),
            ("模糊", 2, "5", "2026-09-02T08:00:00Z"),
        )):
            db = self._db(index)
            word_id = db.execute("SELECT id FROM words ORDER BY id LIMIT 1").fetchone()[0]
            db.execute(
                "INSERT OR REPLACE INTO user_words(word_id,status,review_count) VALUES(?,?,?)",
                (word_id, status, reviews),
            )
            db.execute("INSERT OR REPLACE INTO user_settings(key,value) VALUES('training_difficulty',?)", (difficulty,))
            db.commit(); db.close()
            export_package()
            db = self._db(index)
            db.execute("UPDATE device_sync_records SET modified_at_utc=? WHERE entity_type IN ('user_words','user_settings')", (changed_at,))
            db.commit(); db.close()
            packages.append(export_package())

        merged = merge_packages(*packages)
        word = merged["data"]["user_words"][0]
        setting = next(item for item in merged["data"]["user_settings"] if item["key"] == "training_difficulty")
        self.assertEqual(word["status"], "模糊")
        self.assertEqual(word["review_count"], 7)
        self.assertEqual(setting["value"], "5")

        report = build_sync_report(packages[0], packages[1], merged)
        self.assertGreaterEqual(report["desktop"]["vocabulary"]["updated"], 1)
        self.assertGreaterEqual(report["desktop"]["settings"]["updated"], 1)
        for index in (0, 1):
            database.DB_PATH = self.paths[index]
            result = apply_package(merged)
            self.assertIn("before", result)
            self.assertIn("after", result)
            db = database.get_db()
            saved = db.execute("SELECT status,review_count FROM user_words ORDER BY word_id LIMIT 1").fetchone()
            self.assertEqual((saved["status"], saved["review_count"]), ("模糊", 7))
            db.close()

    def test_prepare_does_not_touch_live_database_before_atomic_commit(self):
        database.DB_PATH = self.paths[1]
        db = database.get_db()
        db.execute("INSERT INTO notes(category_id,title,content,note_date) VALUES(0,'手机新增','只在手机','2026-09-05')")
        db.commit(); db.close()
        incoming = export_package()

        database.DB_PATH = self.paths[0]
        local = export_package()
        merged = merge_packages(local, incoming)
        transaction_id = "test-atomic-prepare"
        prepared = prepare_package(merged, transaction_id, peer=incoming["device"])
        self.assertTrue(prepared["prepared"])
        db = database.get_db()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM notes WHERE title='手机新增'").fetchone()[0], 0)
        db.close()

        committed = commit_prepared_package(transaction_id)
        self.assertTrue(committed["committed"])
        db = database.get_db()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM notes WHERE title='手机新增'").fetchone()[0], 1)
        self.assertEqual(db.execute("PRAGMA quick_check").fetchone()[0], "ok")
        db.close()

    def test_custom_wordbooks_and_diverged_notes_are_preserved(self):
        packages = []
        for index, content in enumerate(("电脑修改", "手机修改")):
            db = self._db(index)
            word_id = int(db.execute("SELECT id FROM words ORDER BY id LIMIT 1 OFFSET ?", (index,)).fetchone()[0])
            book_id = int(db.execute(
                "INSERT INTO wordbooks(name,description,is_builtin,is_hidden) VALUES('我的生词本','个人词库',0,0)"
            ).lastrowid)
            db.execute("INSERT INTO wordbook_words(wordbook_id,word_id) VALUES(?,?)", (book_id, word_id))
            db.execute("""
                INSERT INTO notes(category_id,title,content,note_date,color,created_at,updated_at)
                VALUES(0,'同一篇笔记',?,'2026-09-01','','2026-09-01T08:00:00Z',?)
            """, (content, f"2026-09-01T0{8 + index}:00:00Z"))
            db.commit(); db.close()
            packages.append(export_package())

        merged = merge_packages(*packages)
        self.assertEqual(len(merged["data"]["wordbooks"]), 1)
        self.assertEqual(len(merged["data"]["wordbooks"][0]["words"]), 2)
        self.assertEqual(len(merged["data"]["notes"]), 2)
        self.assertTrue(any("同步冲突副本" in item["title"] for item in merged["data"]["notes"]))

        for index in (0, 1):
            database.DB_PATH = self.paths[index]
            apply_package(merged)
            db = database.get_db()
            self.assertEqual(db.execute("SELECT COUNT(*) FROM notes WHERE title LIKE '%同步冲突副本%'").fetchone()[0], 1)
            self.assertEqual(db.execute("""
                SELECT COUNT(DISTINCT w.word) FROM wordbook_words wbw
                JOIN wordbooks wb ON wb.id=wbw.wordbook_id
                JOIN words w ON w.id=wbw.word_id WHERE wb.name='我的生词本'
            """).fetchone()[0], 2)
            db.close()

    def test_sync_routes_require_csrf_and_native_routes_are_ticketed(self):
        database.DB_PATH = self.paths[0]
        app = create_app(); app.testing = True
        client = app.test_client()
        status = client.get("/api/device-sync/status")
        self.assertEqual(status.status_code, 200)
        token = status.get_json()["csrf_token"]
        self.assertEqual(client.post("/api/device-sync/sessions", json={}).status_code, 403)
        with mock.patch("routes.api_device_sync.start_session", return_value={"active": True, "stage": "waiting"}):
            started = client.post("/api/device-sync/sessions", json={}, headers={"X-CSRF-Token": token})
        self.assertEqual(started.status_code, 200)
        ticket = client.post("/api/device-sync/mobile-ticket", json={}, headers={"X-CSRF-Token": token}).get_json()["ticket"]
        exported = client.get(f"/api/device-sync/native-package/{ticket}")
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(client.get(f"/api/device-sync/native-package/{ticket}").status_code, 403)
        transaction_id = "route-prepare-commit"
        prepared = client.post(f"/api/device-sync/native-prepare/{ticket}", json={
            "package": exported.get_json()["package"],
            "transaction_id": transaction_id,
        })
        self.assertEqual(prepared.status_code, 200)
        committed = client.post(f"/api/device-sync/native-commit/{ticket}", json={
            "transaction_id": transaction_id,
        })
        self.assertEqual(committed.status_code, 200)
        for expected_status in (200, 200, 403):
            retried = client.post(f"/api/device-sync/native-commit/{ticket}", json={
                "transaction_id": transaction_id,
            })
            self.assertEqual(retried.status_code, expected_status)

    def test_tls_session_uses_one_time_pairing_material_and_closes(self):
        database.DB_PATH = self.paths[0]
        with mock.patch.object(device_sync_service, "_private_addresses", return_value=["127.0.0.1"]):
            session = device_sync_service.start_session()
        self.assertTrue(session["pairing_code"].startswith("cet-sync:"))
        self.assertTrue(session["qr_data_url"].startswith("data:image/png;base64,"))
        directory = Path(device_sync_service._SESSION["temp_dir"])
        self.assertTrue((directory / "session-cert.pem").is_file())
        device_sync_service.stop_session()
        self.assertFalse(directory.exists())

    def test_tls_exchange_applies_once_then_closes_listener(self):
        database.DB_PATH = self.paths[0]
        package = export_package()
        with mock.patch.object(device_sync_service, "_private_addresses", return_value=["127.0.0.1"]):
            session = device_sync_service.start_session()
        pairing = device_sync_service.decode_pairing_code(session["pairing_code"])
        context = ssl._create_unverified_context()
        def post(path, value):
            connection = http.client.HTTPSConnection("127.0.0.1", session["port"], context=context, timeout=10)
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            connection.request("POST", path, body=body, headers={
                "Authorization": "Bearer " + pairing["token"],
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            })
            response = connection.getresponse()
            result = response.status, json.loads(response.read().decode("utf-8"))
            connection.close()
            return result

        status, exchanged = post("/sync/v2/exchange", package)
        self.assertEqual(status, 200)
        self.assertTrue(exchanged["ok"])
        transaction_id = exchanged["transaction_id"]
        self.assertNotEqual(device_sync_service.session_snapshot()["stage"], "completed")
        status, committed = post("/sync/v2/commit", {"transaction_id": transaction_id})
        self.assertEqual(status, 200)
        self.assertEqual(device_sync_service.session_snapshot()["stage"], "awaiting_mobile_confirmation")
        status, retried_commit = post("/sync/v2/commit", {"transaction_id": transaction_id})
        self.assertEqual(status, 200)
        self.assertEqual(
            committed["desktop"]["backup_name"],
            retried_commit["desktop"]["backup_name"],
        )
        status, completed = post("/sync/v2/complete", {
            "transaction_id": transaction_id,
            "mobile": {"before": {}, "after": {}, "counts": {}},
        })
        self.assertEqual(status, 200)
        self.assertTrue(completed["ok"])
        self.assertIn("sync_report", completed)
        deadline = time.time() + 4
        listener_closed = False
        while time.time() < deadline:
            try:
                probe = socket.create_connection(("127.0.0.1", session["port"]), timeout=0.2)
                probe.close()
                time.sleep(0.05)
            except OSError:
                listener_closed = True
                break
        self.assertTrue(listener_closed)
        self.assertIsNone(device_sync_service._SESSION)
        self.assertEqual(device_sync_service.session_snapshot()["stage"], "completed")


if __name__ == "__main__":
    unittest.main()

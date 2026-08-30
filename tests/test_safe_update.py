import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import database
from app import create_app
from services import update_service


class FakeResponse:
    def __init__(self, payload, status=200):
        import json
        self.payload = payload
        self.status_code = status
        self.content = json.dumps(payload).encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self.payload


def stable_release(version="0.3.1"):
    return {
        "tag_name": f"v{version}",
        "name": f"稳定版 v{version}",
        "body": "修复与体验更新",
        "published_at": "2026-08-30T00:00:00Z",
        "html_url": f"https://github.com/sixinzheng/cet-learning-desk/releases/tag/v{version}",
        "draft": False,
        "prerelease": False,
        "assets": [{"name": f"CETLearningDesk-v{version}.exe", "size": 123456}],
    }


class SafeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "vocab.db")
        db = sqlite3.connect(database.DB_PATH)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE facts (id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO facts(value) VALUES ('学习记录')")
        db.commit()
        db.close()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_release_channel_accepts_only_stable_official_release(self):
        release = update_service.fetch_latest_release(
            http_get=lambda *args, **kwargs: FakeResponse(stable_release())
        )
        self.assertEqual(release["tag_name"], "v0.3.1")

        candidate = stable_release()
        candidate["prerelease"] = True
        with self.assertRaises(update_service.UpdateServiceError) as caught:
            update_service.fetch_latest_release(
                http_get=lambda *args, **kwargs: FakeResponse(candidate)
            )
        self.assertEqual(caught.exception.code, "unstable_release")

        candidate = stable_release()
        candidate["html_url"] = "https://example.com/releases/v0.3.1"
        with self.assertRaises(update_service.UpdateServiceError) as caught:
            update_service.fetch_latest_release(
                http_get=lambda *args, **kwargs: FakeResponse(candidate)
            )
        self.assertEqual(caught.exception.code, "untrusted_release")

    def test_online_backup_is_consistent_and_keeps_only_three(self):
        paths = []
        for index in range(4):
            db = sqlite3.connect(database.DB_PATH)
            db.execute("INSERT INTO facts(value) VALUES (?)", (f"记录 {index}",))
            db.commit()
            db.close()
            paths.append(update_service.create_verified_backup("0.3.0", f"0.3.{index + 1}"))

        backups = list((Path(self.temp_dir.name) / "update-backups").glob("vocab-before-*.db"))
        self.assertEqual(len(backups), 3)
        newest = sqlite3.connect(paths[-1])
        try:
            self.assertEqual(newest.execute("PRAGMA quick_check").fetchone()[0], "ok")
            self.assertEqual(newest.execute("SELECT COUNT(*) FROM facts").fetchone()[0], 5)
        finally:
            newest.close()

    def test_source_mode_never_prepares_an_installer(self):
        with mock.patch.object(update_service, "current_platform", return_value="source"):
            with self.assertRaises(update_service.UpdateServiceError) as caught:
                update_service.prepare_update(
                    http_get=lambda *args, **kwargs: FakeResponse(stable_release())
                )
        self.assertEqual(caught.exception.code, "source_mode")

    def test_update_routes_require_csrf_and_expose_source_status(self):
        app = create_app()
        app.testing = True
        client = app.test_client()
        payload = {
            "platform": "source",
            "current_version": "0.3.0",
            "latest_version": "0.3.1",
            "update_available": True,
            "install_supported": False,
            "release_url": "https://github.com/sixinzheng/cet-learning-desk/releases/tag/v0.3.1",
            "progress": {"stage": "available", "percent": 10, "message": "发现更新"},
        }
        with mock.patch("routes.api_update.update_status", return_value=payload):
            status = client.get("/api/app/update/status")
        self.assertEqual(status.status_code, 200)
        token = status.get_json()["csrf_token"]
        rejected = client.post("/api/app/update/prepare", json={})
        self.assertEqual(rejected.status_code, 403)
        with mock.patch(
            "routes.api_update.prepare_update",
            side_effect=update_service.UpdateServiceError("源码模式", code="source_mode", status=409),
        ):
            source = client.post(
                "/api/app/update/prepare",
                json={},
                headers={"X-CSRF-Token": token},
            )
        self.assertEqual(source.status_code, 409)
        self.assertEqual(source.get_json()["code"], "source_mode")


if __name__ == "__main__":
    unittest.main()

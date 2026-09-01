"""Portable, deterministic device-data export and merge for local Wi-Fi sync.

The wire format deliberately contains logical keys instead of SQLite row ids.  It
never reads config.json or any credential backend, so API keys and session
secrets cannot enter a sync package by accident.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import database


PROTOCOL_VERSION = 1
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
_SYNC_BACKUP_KEEP = 5
_SECRET_SETTING_PARTS = (
    "api_key", "secret", "token", "csrf", "credential", "password", "session",
)


class DeviceSyncError(RuntimeError):
    def __init__(self, message: str, *, code: str = "sync_failed", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except (TypeError, ValueError):
        return fallback


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _word_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _record_time(item: dict[str, Any]) -> str:
    for key in ("modified_at_utc", "updated_at", "last_reviewed", "completed_at", "created_at", "study_date", "date"):
        if item.get(key):
            return str(item[key])
    return ""


def _row_dicts(db: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(sql, tuple(params)).fetchall()]


def _ensure_sync_tables(db: sqlite3.Connection) -> None:
    """Keep legacy/minimal test databases compatible with sync-aware mutations."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS device_sync_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS device_sync_peers (
            device_id TEXT PRIMARY KEY,
            device_name TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL DEFAULT '',
            last_sync_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS device_sync_tombstones (
            entity_type TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            deleted_at TEXT NOT NULL,
            origin_device_id TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(entity_type, entity_key)
        );
        CREATE TABLE IF NOT EXISTS device_sync_records (
            entity_type TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            record_uuid TEXT NOT NULL UNIQUE,
            modified_at_utc TEXT NOT NULL,
            origin_device_id TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(entity_type, entity_key)
        );
    """)


def device_identity(db: sqlite3.Connection | None = None) -> dict[str, str]:
    owned = db is None
    db = db or database.get_db()
    _ensure_sync_tables(db)
    row = db.execute("SELECT value FROM device_sync_state WHERE key='device_id'").fetchone()
    device_id = str(row[0]) if row and row[0] else str(uuid.uuid4())
    if not row:
        db.execute("INSERT INTO device_sync_state(key,value) VALUES('device_id',?)", (device_id,))
    name_row = db.execute("SELECT value FROM device_sync_state WHERE key='device_name'").fetchone()
    device_name = str(name_row[0]) if name_row and name_row[0] else socket.gethostname()[:80]
    if not name_row:
        db.execute("INSERT INTO device_sync_state(key,value) VALUES('device_name',?)", (device_name,))
    if owned:
        db.commit()
        db.close()
    return {"device_id": device_id, "device_name": device_name, "platform": platform.system().lower()}


def _article_key(row: dict[str, Any]) -> str:
    stable = str(row.get("corpus_id") or row.get("content_hash") or "").strip()
    return stable or "title:" + str(row.get("title") or "").strip().lower()


def _category_paths(db: sqlite3.Connection) -> dict[int, str]:
    rows = _row_dicts(db, "SELECT id,parent_id,name FROM note_categories")
    by_id = {int(row["id"]): row for row in rows}
    result = {0: ""}
    for category_id, row in by_id.items():
        if category_id == 0:
            continue
        parent = by_id.get(int(row.get("parent_id") or 0))
        result[category_id] = (
            f"{str(parent['name']).strip()} / {str(row['name']).strip()}"
            if parent and int(parent["id"]) != 0 else str(row["name"]).strip()
        )
    return result


def note_key(item: dict[str, Any]) -> str:
    identity = "|".join((
        str(item.get("created_at") or item.get("note_date") or ""),
        str(item.get("title") or "").strip(),
        str(item.get("category_path") or "").strip(),
    ))
    return "note:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _portable_entity_key(entity_type: str, item: Any) -> str:
    if entity_type == "favorites":
        return _word_key(item)
    if not isinstance(item, dict):
        return _hash(item)
    keys = {
        "words": lambda value: _word_key(value.get("word")),
        "user_words": lambda value: _word_key(value.get("word")),
        "wordbooks": lambda value: str(value.get("_key") or value.get("name") or "").strip().lower(),
        "study_logs": lambda value: str(value.get("study_date") or ""),
        "daily_word_completions": lambda value: f"{value.get('completion_date')}|{_word_key(value.get('word'))}|{value.get('completion_type')}",
        "practice_sessions": lambda value: str(value.get("idempotency_key") or ""),
        "article_annotations": lambda value: f"{value.get('article_key')}|{value.get('word_index')}|{value.get('mark_type')}",
        "notes": lambda value: str(value.get("_key") or note_key(value)),
        "user_settings": lambda value: str(value.get("key") or ""),
        "word_ai_details": lambda value: _word_key(value.get("word")),
        "ai_conversations": lambda value: str(value.get("_key") or ""),
        "ai_daily_greetings": lambda value: f"{value.get('greeting_date')}|{value.get('language')}",
        "site_skills": lambda value: str(value.get("slug") or ""),
    }
    key = keys.get(entity_type, lambda value: "")(item)
    return key or _hash({k: v for k, v in item.items() if k != "id"})


def _sync_record_metadata(
    db: sqlite3.Connection,
    identity: dict[str, str],
    data: dict[str, Any],
) -> list[dict[str, str]]:
    now = utc_now()
    for entity_type, items in data.items():
        if entity_type in {"record_meta", "tombstones"} or not isinstance(items, list):
            continue
        for item in items:
            entity_key = _portable_entity_key(entity_type, item)
            if not entity_key:
                continue
            content_hash = _hash(item)
            row = db.execute("""
                SELECT content_hash FROM device_sync_records
                WHERE entity_type=? AND entity_key=?
            """, (entity_type, entity_key)).fetchone()
            if row is None:
                record_uuid = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"cet-learning-desk:{identity['device_id']}:{entity_type}:{entity_key}",
                ))
                db.execute("""
                    INSERT INTO device_sync_records(
                        entity_type,entity_key,record_uuid,modified_at_utc,origin_device_id,content_hash
                    ) VALUES(?,?,?,?,?,?)
                """, (entity_type, entity_key, record_uuid, now, identity["device_id"], content_hash))
            elif str(row["content_hash"] or "") != content_hash:
                db.execute("""
                    UPDATE device_sync_records SET modified_at_utc=?,origin_device_id=?,content_hash=?
                    WHERE entity_type=? AND entity_key=?
                """, (now, identity["device_id"], content_hash, entity_type, entity_key))
    return _row_dicts(db, """
        SELECT entity_type,entity_key,record_uuid,modified_at_utc,origin_device_id,content_hash
        FROM device_sync_records ORDER BY entity_type,entity_key
    """)


def record_tombstone(
    entity_type: str,
    entity_key: str,
    *,
    db: sqlite3.Connection | None = None,
) -> None:
    """Record a portable deletion without owning or closing a caller connection."""
    owned = db is None
    db = db or database.get_db()
    identity = device_identity(db)
    db.execute("""
        INSERT INTO device_sync_tombstones(entity_type,entity_key,deleted_at,origin_device_id)
        VALUES(?,?,?,?) ON CONFLICT(entity_type,entity_key) DO UPDATE SET
        deleted_at=excluded.deleted_at,origin_device_id=excluded.origin_device_id
    """, (str(entity_type), str(entity_key), utc_now(), identity["device_id"]))
    if owned:
        db.commit(); db.close()


def clear_tombstone(entity_type: str, entity_key: str, *, db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM device_sync_tombstones WHERE entity_type=? AND entity_key=?", (entity_type, entity_key))


def export_package() -> dict[str, Any]:
    db = database.get_db()
    try:
        identity = device_identity(db)
        categories = _category_paths(db)
        words = _row_dicts(db, """
            SELECT DISTINCT w.* FROM words w
            LEFT JOIN user_words uw ON uw.word_id=w.id
            LEFT JOIN word_ai_details ad ON ad.word_id=w.id
            LEFT JOIN wordbook_words wbw ON wbw.word_id=w.id
            LEFT JOIN wordbooks wb ON wb.id=wbw.wordbook_id
            WHERE uw.id IS NOT NULL OR ad.id IS NOT NULL OR (
                wb.id IS NOT NULL AND COALESCE(wb.is_hidden,0)=0
                AND (COALESCE(wb.is_builtin,0)=0 OR wb.name='我的收藏')
            )
        """)
        word_payload = [{
            "word": row["word"], "corpus_id": row.get("corpus_id") or "",
            "phonetic": row.get("phonetic") or "", "part_of_speech": row.get("part_of_speech") or "",
            "meanings": _json(row.get("meanings"), []), "source": row.get("source") or "",
            "frequency": int(row.get("frequency") or 1),
        } for row in words]

        user_words = _row_dicts(db, """
            SELECT w.word,uw.status,uw.review_count,uw.correct_count,uw.consecutive_correct,
                   uw.wrong_streak,uw.last_reviewed,uw.next_review,uw.ebbinghaus_stage,
                   COALESCE(uw.vague_flagged,0) AS vague_flagged
            FROM user_words uw JOIN words w ON w.id=uw.word_id
        """)
        favorites = [row["word"] for row in db.execute("""
            SELECT w.word FROM wordbook_words wbw
            JOIN wordbooks wb ON wb.id=wbw.wordbook_id
            JOIN words w ON w.id=wbw.word_id
            WHERE wb.name='我的收藏' AND COALESCE(wb.is_hidden,0)=0 ORDER BY w.word
        """).fetchall()]
        wordbooks = []
        for row in _row_dicts(db, """
            SELECT id,name,description,created_date FROM wordbooks
            WHERE COALESCE(is_builtin,0)=0 AND COALESCE(is_hidden,0)=0
              AND name!='我的收藏' ORDER BY lower(name),id
        """):
            wordbook_id = row.pop("id")
            row["words"] = [item[0] for item in db.execute("""
                SELECT w.word FROM wordbook_words wbw
                JOIN words w ON w.id=wbw.word_id
                WHERE wbw.wordbook_id=? ORDER BY lower(w.word)
            """, (wordbook_id,)).fetchall()]
            row["_key"] = str(row.get("name") or "").strip().lower()
            wordbooks.append(row)
        completions = _row_dicts(db, """
            SELECT d.completion_date,w.word,d.completion_type,d.created_at
            FROM daily_word_completions d JOIN words w ON w.id=d.word_id
        """)
        annotations = _row_dicts(db, """
            SELECT a.corpus_id,a.content_hash,a.title,n.word_index,n.mark_type,n.created_at
            FROM article_annotations n JOIN reading_articles a ON a.id=n.article_id
        """)
        for item in annotations:
            item["article_key"] = _article_key(item)
            item.pop("corpus_id", None); item.pop("content_hash", None); item.pop("title", None)

        notes = []
        for row in _row_dicts(db, "SELECT * FROM notes"):
            row["category_path"] = categories.get(int(row.get("category_id") or 0), "")
            row.pop("id", None); row.pop("category_id", None)
            row["_key"] = note_key(row)
            notes.append(row)

        settings = []
        for row in _row_dicts(db, "SELECT key,value FROM user_settings"):
            lowered = row["key"].lower()
            if lowered.startswith("device_sync") or any(part in lowered for part in _SECRET_SETTING_PARTS):
                continue
            row["updated_at"] = ""
            settings.append(row)

        ai_details = _row_dicts(db, """
            SELECT w.word,d.surface_form,d.context_excerpt,d.detail_json,d.model,
                   d.prompt_version,d.generated_at,d.updated_at,
                   a.corpus_id,a.content_hash,a.title
            FROM word_ai_details d JOIN words w ON w.id=d.word_id
            LEFT JOIN reading_articles a ON a.id=d.article_id
        """)
        for item in ai_details:
            item["article_key"] = _article_key(item) if item.get("title") else ""
            item.pop("corpus_id", None); item.pop("content_hash", None); item.pop("title", None)

        conversations = []
        for conversation in _row_dicts(db, "SELECT * FROM ai_conversations"):
            cid = conversation.pop("id")
            key = "conversation:" + hashlib.sha256(
                f"{conversation.get('created_at','')}|{conversation.get('title','')}".encode("utf-8")
            ).hexdigest()[:24]
            messages = _row_dicts(db, """
                SELECT role,content,citations_json,created_at FROM ai_messages
                WHERE conversation_id=? ORDER BY id
            """, (cid,))
            for message in messages:
                message["_key"] = "message:" + _hash(message)[:24]
            conversation["_key"] = key
            conversation["messages"] = messages
            conversations.append(conversation)

        tombstones = _row_dicts(db, "SELECT * FROM device_sync_tombstones")
        payload = {
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": int(db.execute("PRAGMA user_version").fetchone()[0]),
            "exported_at": utc_now(),
            "device": identity,
            "data": {
                "words": word_payload,
                "user_words": user_words,
                "favorites": favorites,
                "wordbooks": wordbooks,
                "study_logs": _row_dicts(db, "SELECT * FROM study_logs"),
                "daily_word_completions": completions,
                "practice_sessions": _row_dicts(db, "SELECT * FROM practice_sessions"),
                "article_annotations": annotations,
                "notes": notes,
                "user_settings": settings,
                "word_ai_details": ai_details,
                "ai_conversations": conversations,
                "ai_memories": _row_dicts(db, "SELECT memory_type,content,evidence_json,confirmed,active,first_observed,last_observed,created_at FROM ai_memories"),
                "ai_daily_greetings": _row_dicts(db, "SELECT greeting_date,language,greeting,source,snapshot_json,created_at FROM ai_daily_greetings"),
                "ai_usage_events": _row_dicts(db, "SELECT * FROM ai_usage_events"),
                "site_skills": _row_dicts(db, "SELECT slug,display_name,description,user_instructions,feature_prefixes_json,enabled,is_builtin,created_at,updated_at FROM site_skills"),
                "tombstones": tombstones,
            },
        }
        for item in payload["data"]["practice_sessions"] + payload["data"]["study_logs"] + payload["data"]["ai_usage_events"]:
            item.pop("id", None)
        payload["data"]["record_meta"] = _sync_record_metadata(db, identity, payload["data"])
        # Persist the device identity and record metadata generated during this export.
        db.commit()
        encoded = _canonical(payload).encode("utf-8")
        if len(encoded) > MAX_PACKAGE_BYTES:
            raise DeviceSyncError("个人数据包超过 32MB 安全限制，请先清理超长 AI 对话。", code="package_too_large", status=413)
        payload["checksum"] = hashlib.sha256(encoded).hexdigest()
        return payload
    finally:
        db.close()


def validate_package(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("protocol_version") != PROTOCOL_VERSION:
        raise DeviceSyncError("两台设备的同步协议版本不一致，请先更新应用。", code="protocol_mismatch", status=409)
    data = payload.get("data")
    device = payload.get("device")
    if not isinstance(data, dict) or not isinstance(device, dict) or not device.get("device_id"):
        raise DeviceSyncError("同步数据包缺少设备身份或数据主体。", code="invalid_package")
    raw = dict(payload)
    checksum = str(raw.pop("checksum", ""))
    encoded = _canonical(raw).encode("utf-8")
    if len(encoded) > MAX_PACKAGE_BYTES or not checksum or not hashlib.sha256(encoded).hexdigest() == checksum:
        raise DeviceSyncError("同步数据包校验失败。", code="checksum_failed")
    serialized = encoded.lower()
    if any(marker in serialized for marker in (b"deepseek_api_key", b"session_secret", b"csrf_token")):
        raise DeviceSyncError("同步数据包包含禁止传输的敏感字段。", code="secret_detected")
    return payload


def _keyed(items: list[dict[str, Any]], key) -> dict[str, dict[str, Any]]:
    return {str(key(item)): item for item in items if str(key(item))}


def _merge_lww(left: list[dict[str, Any]], right: list[dict[str, Any]], key) -> list[dict[str, Any]]:
    result = _keyed(left, key)
    for item_key, item in _keyed(right, key).items():
        existing = result.get(item_key)
        if existing is None or (_record_time(item), _hash(item)) >= (_record_time(existing), _hash(existing)):
            result[item_key] = item
    return [result[key] for key in sorted(result)]


def _merge_union(left: list[dict[str, Any]], right: list[dict[str, Any]], key) -> list[dict[str, Any]]:
    result = _keyed(left, key)
    result.update({k: v for k, v in _keyed(right, key).items() if k not in result})
    return [result[key] for key in sorted(result)]


def _merge_notes(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep both bodies when the same logical note diverged on two devices."""
    result = _keyed(left, lambda item: item.get("_key") or note_key(item))
    for item_key, incoming in _keyed(right, lambda item: item.get("_key") or note_key(item)).items():
        existing = result.get(item_key)
        if existing is None:
            result[item_key] = incoming
            continue
        if _hash({k: v for k, v in existing.items() if k != "_key"}) == _hash({k: v for k, v in incoming.items() if k != "_key"}):
            continue
        winner, conflict = sorted(
            (existing, incoming),
            key=lambda value: (_record_time(value), _hash(value)),
            reverse=True,
        )
        result[item_key] = winner
        conflict = dict(conflict)
        suffix = "（同步冲突副本）"
        title = str(conflict.get("title") or "未命名笔记")
        if not title.endswith(suffix):
            conflict["title"] = title + suffix
        conflict["_key"] = note_key(conflict)
        result[conflict["_key"]] = conflict
    return [result[key] for key in sorted(result)]


def _merge_wordbooks(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in left + right:
        key = str(item.get("_key") or item.get("name") or "").strip().lower()
        if key:
            grouped.setdefault(key, []).append(item)
    result = []
    for key in sorted(grouped):
        candidates = grouped[key]
        winner = max(candidates, key=lambda item: (_record_time(item), _hash(item)))
        merged = dict(winner)
        merged["_key"] = key
        merged["words"] = sorted({
            _word_key(word)
            for candidate in candidates
            for word in candidate.get("words", [])
            if _word_key(word)
        })
        result.append(merged)
    return result


def _complete_merged_metadata(merged: dict[str, Any], origin_device_id: str) -> list[dict[str, str]]:
    now = utc_now()
    existing = {
        f"{item.get('entity_type')}|{item.get('entity_key')}": dict(item)
        for item in merged.get("record_meta", [])
        if item.get("entity_type") and item.get("entity_key")
    }
    for entity_type, items in merged.items():
        if entity_type in {"record_meta", "tombstones"} or not isinstance(items, list):
            continue
        for item in items:
            entity_key = _portable_entity_key(entity_type, item)
            if not entity_key:
                continue
            compound = f"{entity_type}|{entity_key}"
            content_hash = _hash(item)
            meta = existing.get(compound)
            if meta is None:
                meta = {
                    "entity_type": entity_type,
                    "entity_key": entity_key,
                    "record_uuid": str(uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"cet-learning-desk:{origin_device_id}:{entity_type}:{entity_key}",
                    )),
                    "modified_at_utc": now,
                    "origin_device_id": origin_device_id,
                    "content_hash": content_hash,
                }
                existing[compound] = meta
            elif str(meta.get("content_hash") or "") != content_hash:
                meta["modified_at_utc"] = now
                meta["origin_device_id"] = origin_device_id
                meta["content_hash"] = content_hash
    return [existing[key] for key in sorted(existing)]


def merge_packages(local: dict[str, Any], remote: dict[str, Any]) -> dict[str, Any]:
    local = validate_package(local)
    remote = validate_package(remote)
    ld, rd = local["data"], remote["data"]
    merged: dict[str, Any] = {}
    merged["words"] = _merge_lww(ld.get("words", []), rd.get("words", []), lambda x: _word_key(x.get("word")))
    merged["user_words"] = _merge_lww(ld.get("user_words", []), rd.get("user_words", []), lambda x: _word_key(x.get("word")))
    merged["favorites"] = sorted({_word_key(item) for item in ld.get("favorites", []) + rd.get("favorites", []) if _word_key(item)})
    merged["wordbooks"] = _merge_wordbooks(ld.get("wordbooks", []), rd.get("wordbooks", []))
    merged["study_logs"] = _merge_lww(ld.get("study_logs", []), rd.get("study_logs", []), lambda x: x.get("study_date"))
    merged["daily_word_completions"] = _merge_union(ld.get("daily_word_completions", []), rd.get("daily_word_completions", []), lambda x: f"{x.get('completion_date')}|{_word_key(x.get('word'))}|{x.get('completion_type')}")
    merged["practice_sessions"] = _merge_union(ld.get("practice_sessions", []), rd.get("practice_sessions", []), lambda x: x.get("idempotency_key"))
    merged["article_annotations"] = _merge_union(ld.get("article_annotations", []), rd.get("article_annotations", []), lambda x: f"{x.get('article_key')}|{x.get('word_index')}|{x.get('mark_type')}")
    merged["notes"] = _merge_notes(ld.get("notes", []), rd.get("notes", []))
    merged["user_settings"] = _merge_lww(ld.get("user_settings", []), rd.get("user_settings", []), lambda x: x.get("key"))
    merged["word_ai_details"] = _merge_lww(ld.get("word_ai_details", []), rd.get("word_ai_details", []), lambda x: _word_key(x.get("word")))
    merged["ai_conversations"] = _merge_lww(ld.get("ai_conversations", []), rd.get("ai_conversations", []), lambda x: x.get("_key"))
    merged["ai_memories"] = _merge_union(ld.get("ai_memories", []), rd.get("ai_memories", []), lambda x: _hash({k:v for k,v in x.items() if k != 'id'}))
    merged["ai_daily_greetings"] = _merge_lww(ld.get("ai_daily_greetings", []), rd.get("ai_daily_greetings", []), lambda x: f"{x.get('greeting_date')}|{x.get('language')}")
    merged["ai_usage_events"] = _merge_union(ld.get("ai_usage_events", []), rd.get("ai_usage_events", []), lambda x: _hash({k:v for k,v in x.items() if k != 'id'}))
    merged["site_skills"] = _merge_lww(ld.get("site_skills", []), rd.get("site_skills", []), lambda x: x.get("slug"))
    merged["record_meta"] = _merge_lww(ld.get("record_meta", []), rd.get("record_meta", []), lambda x: f"{x.get('entity_type')}|{x.get('entity_key')}")
    merged["tombstones"] = _merge_lww(ld.get("tombstones", []), rd.get("tombstones", []), lambda x: f"{x.get('entity_type')}|{x.get('entity_key')}")
    tombstone_keys = {
        (str(item.get("entity_type")), str(item.get("entity_key")))
        for item in merged["tombstones"]
    }
    merged["favorites"] = [
        word for word in merged["favorites"]
        if ("favorite", "favorite:" + _word_key(word)) not in tombstone_keys
    ]
    merged["notes"] = [
        item for item in merged["notes"]
        if ("note", str(item.get("_key") or note_key(item))) not in tombstone_keys
    ]
    merged["record_meta"] = _complete_merged_metadata(merged, str(local["device"].get("device_id") or ""))

    package = {
        "protocol_version": PROTOCOL_VERSION,
        "schema_version": max(int(local.get("schema_version") or 0), int(remote.get("schema_version") or 0)),
        "exported_at": utc_now(),
        "device": local["device"],
        "merged_devices": [local["device"], remote["device"]],
        "data": merged,
    }
    package["checksum"] = hashlib.sha256(_canonical(package).encode("utf-8")).hexdigest()
    return package


def create_sync_backup(label: str = "sync") -> Path:
    source = Path(database.DB_PATH).resolve()
    directory = source.parent / "sync-backups"
    directory.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(ch for ch in label if ch.isalnum() or ch in "-_")[:32] or "sync"
    destination = directory / f"vocab-before-{safe_label}-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True, timeout=20)
    dst = sqlite3.connect(str(destination), timeout=20)
    try:
        src.backup(dst, pages=256)
        dst.commit()
        check = dst.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise DeviceSyncError("同步前备份未通过完整性检查。", code="backup_check_failed", status=500)
    finally:
        dst.close(); src.close()
    backups = sorted(directory.glob("vocab-before-sync-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old in backups[_SYNC_BACKUP_KEEP:]:
        old.unlink(missing_ok=True)
    return destination


def _ensure_word(db: sqlite3.Connection, word: str, catalog: dict[str, dict[str, Any]]) -> int:
    row = db.execute("SELECT id FROM words WHERE lower(word)=?", (_word_key(word),)).fetchone()
    if row:
        return int(row[0])
    item = catalog.get(_word_key(word), {"word": word})
    cursor = db.execute("""
        INSERT INTO words(corpus_id,word,phonetic,part_of_speech,meanings,source,frequency)
        VALUES(?,?,?,?,?,?,?)
    """, (
        item.get("corpus_id", ""), item.get("word") or word, item.get("phonetic", ""),
        item.get("part_of_speech", ""), _canonical(item.get("meanings", [])),
        item.get("source") or "device-sync", int(item.get("frequency") or 1),
    ))
    return int(cursor.lastrowid)


def _article_id(db: sqlite3.Connection, key: str) -> int | None:
    row = db.execute("SELECT id FROM reading_articles WHERE corpus_id=? OR content_hash=? LIMIT 1", (key, key)).fetchone()
    if not row and key.startswith("title:"):
        row = db.execute("SELECT id FROM reading_articles WHERE lower(title)=? LIMIT 1", (key[6:],)).fetchone()
    return int(row[0]) if row else None


def _category_id(db: sqlite3.Connection, path: str) -> int:
    parts = [part.strip() for part in str(path or "").split("/") if part.strip()]
    parent = 0
    for part in parts[:2]:
        row = db.execute("SELECT id FROM note_categories WHERE parent_id=? AND name=? LIMIT 1", (parent, part)).fetchone()
        if row:
            parent = int(row[0])
        else:
            parent = int(db.execute("INSERT INTO note_categories(parent_id,name) VALUES(?,?)", (parent, part)).lastrowid)
    return parent


def apply_package(package: dict[str, Any], *, peer: dict[str, Any] | None = None) -> dict[str, Any]:
    package = validate_package(package)
    backup = create_sync_backup("sync")
    data = package["data"]
    db = database.get_db()
    counts: dict[str, int] = {}
    try:
        _ensure_sync_tables(db)
        db.execute("BEGIN IMMEDIATE")
        catalog = {_word_key(item.get("word")): item for item in data.get("words", [])}
        for item in data.get("user_words", []):
            word_id = _ensure_word(db, item.get("word", ""), catalog)
            db.execute("""
                INSERT INTO user_words(word_id,status,review_count,correct_count,consecutive_correct,
                    wrong_streak,last_reviewed,next_review,ebbinghaus_stage,vague_flagged)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(word_id) DO UPDATE SET status=excluded.status,
                    review_count=MAX(user_words.review_count,excluded.review_count),
                    correct_count=MAX(user_words.correct_count,excluded.correct_count),
                    consecutive_correct=excluded.consecutive_correct,wrong_streak=excluded.wrong_streak,
                    last_reviewed=excluded.last_reviewed,next_review=excluded.next_review,
                    ebbinghaus_stage=excluded.ebbinghaus_stage,vague_flagged=excluded.vague_flagged
            """, (word_id, item.get("status", "陌生"), int(item.get("review_count") or 0),
                  int(item.get("correct_count") or 0), int(item.get("consecutive_correct") or 0),
                  int(item.get("wrong_streak") or 0), item.get("last_reviewed"), item.get("next_review"),
                  int(item.get("ebbinghaus_stage") or 0), int(item.get("vague_flagged") or 0)))
        counts["user_words"] = len(data.get("user_words", []))

        favorite = db.execute("SELECT id FROM wordbooks WHERE name='我的收藏' LIMIT 1").fetchone()
        if not favorite:
            favorite_id = int(db.execute("INSERT INTO wordbooks(name,description,is_builtin,is_hidden) VALUES('我的收藏','收藏的单词自动收进这里',1,0)").lastrowid)
        else:
            favorite_id = int(favorite[0])
        desired_favorites = {_word_key(word) for word in data.get("favorites", [])}
        db.execute("DELETE FROM wordbook_words WHERE wordbook_id=?", (favorite_id,))
        for word in sorted(desired_favorites):
            word_id = _ensure_word(db, word, catalog)
            db.execute("INSERT OR IGNORE INTO wordbook_words(wordbook_id,word_id) VALUES(?,?)", (favorite_id, word_id))
        counts["favorites"] = len(desired_favorites)

        for item in data.get("wordbooks", []):
            name = str(item.get("name") or "").strip()[:120]
            if not name or name == "我的收藏":
                continue
            row = db.execute("""
                SELECT id,is_builtin FROM wordbooks
                WHERE lower(name)=lower(?) AND COALESCE(is_hidden,0)=0 LIMIT 1
            """, (name,)).fetchone()
            if row and int(row["is_builtin"] or 0):
                continue
            if row:
                wordbook_id = int(row["id"])
                db.execute(
                    "UPDATE wordbooks SET name=?,description=? WHERE id=?",
                    (name, str(item.get("description") or "")[:500], wordbook_id),
                )
            else:
                wordbook_id = int(db.execute("""
                    INSERT INTO wordbooks(name,description,is_builtin,is_hidden,created_date)
                    VALUES(?,?,0,0,?)
                """, (
                    name,
                    str(item.get("description") or "")[:500],
                    item.get("created_date") or datetime.now().date().isoformat(),
                )).lastrowid)
            db.execute("DELETE FROM wordbook_words WHERE wordbook_id=?", (wordbook_id,))
            for word in sorted({_word_key(value) for value in item.get("words", []) if _word_key(value)}):
                word_id = _ensure_word(db, word, catalog)
                db.execute(
                    "INSERT OR IGNORE INTO wordbook_words(wordbook_id,word_id) VALUES(?,?)",
                    (wordbook_id, word_id),
                )
        counts["wordbooks"] = len(data.get("wordbooks", []))

        for item in data.get("study_logs", []):
            columns = [key for key in item if key != "id"]
            update = ",".join(f"{key}=excluded.{key}" for key in columns if key != "study_date")
            db.execute(f"INSERT INTO study_logs({','.join(columns)}) VALUES({','.join('?' for _ in columns)}) ON CONFLICT(study_date) DO UPDATE SET {update}", tuple(item[key] for key in columns))
        for item in data.get("daily_word_completions", []):
            word_id = _ensure_word(db, item.get("word", ""), catalog)
            db.execute("INSERT OR IGNORE INTO daily_word_completions(completion_date,word_id,completion_type,created_at) VALUES(?,?,?,?)", (item.get("completion_date"), word_id, item.get("completion_type"), item.get("created_at") or utc_now()))
        for item in data.get("practice_sessions", []):
            columns = list(item)
            db.execute(f"INSERT OR IGNORE INTO practice_sessions({','.join(columns)}) VALUES({','.join('?' for _ in columns)})", tuple(item[key] for key in columns))

        for item in data.get("article_annotations", []):
            article_id = _article_id(db, str(item.get("article_key") or ""))
            if article_id:
                db.execute("INSERT OR IGNORE INTO article_annotations(article_id,word_index,mark_type,created_at) VALUES(?,?,?,?)", (article_id, int(item.get("word_index") or 0), item.get("mark_type") or "green", item.get("created_at") or utc_now()))

        current_notes = {}
        categories = _category_paths(db)
        for row in _row_dicts(db, "SELECT * FROM notes"):
            row["category_path"] = categories.get(int(row.get("category_id") or 0), "")
            current_notes[note_key(row)] = int(row["id"])
        for item in data.get("notes", []):
            key = str(item.get("_key") or note_key(item))
            category_id = _category_id(db, item.get("category_path", ""))
            values = (category_id, item.get("title", ""), item.get("content", ""), item.get("note_date", ""), item.get("color", ""), item.get("created_at") or utc_now(), item.get("updated_at") or utc_now())
            if key in current_notes:
                db.execute("UPDATE notes SET category_id=?,title=?,content=?,note_date=?,color=?,created_at=?,updated_at=? WHERE id=?", values + (current_notes[key],))
            else:
                db.execute("INSERT INTO notes(category_id,title,content,note_date,color,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", values)
        counts["notes"] = len(data.get("notes", []))

        for item in data.get("user_settings", []):
            key = str(item.get("key") or "")
            if key and not any(part in key.lower() for part in _SECRET_SETTING_PARTS):
                db.execute("INSERT INTO user_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(item.get("value") or "")))

        for item in data.get("word_ai_details", []):
            word_id = _ensure_word(db, item.get("word", ""), catalog)
            article_id = _article_id(db, str(item.get("article_key") or ""))
            db.execute("""
                INSERT INTO word_ai_details(word_id,surface_form,article_id,context_excerpt,detail_json,model,prompt_version,generated_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(word_id) DO UPDATE SET
                surface_form=excluded.surface_form,article_id=excluded.article_id,
                context_excerpt=excluded.context_excerpt,detail_json=excluded.detail_json,
                model=excluded.model,prompt_version=excluded.prompt_version,
                generated_at=excluded.generated_at,updated_at=excluded.updated_at
            """, (word_id, item.get("surface_form", ""), article_id, item.get("context_excerpt", ""),
                  item.get("detail_json", "{}"), item.get("model", ""), item.get("prompt_version", "reading-word-v1"),
                  item.get("generated_at") or utc_now(), item.get("updated_at") or utc_now()))

        for conversation in data.get("ai_conversations", []):
            row = db.execute("SELECT id FROM ai_conversations WHERE created_at=? AND title=? LIMIT 1", (conversation.get("created_at"), conversation.get("title"))).fetchone()
            if row:
                conversation_id = int(row[0])
                db.execute("UPDATE ai_conversations SET language=?,scenario_key=?,updated_at=? WHERE id=?", (conversation.get("language", "zh"), conversation.get("scenario_key", "casual"), conversation.get("updated_at") or utc_now(), conversation_id))
            else:
                conversation_id = int(db.execute("INSERT INTO ai_conversations(title,language,scenario_key,created_at,updated_at) VALUES(?,?,?,?,?)", (conversation.get("title", "英语学习对话"), conversation.get("language", "zh"), conversation.get("scenario_key", "casual"), conversation.get("created_at") or utc_now(), conversation.get("updated_at") or utc_now())).lastrowid)
            existing_messages = {_hash(dict(row)) for row in db.execute("SELECT role,content,citations_json,created_at FROM ai_messages WHERE conversation_id=?", (conversation_id,)).fetchall()}
            for message in conversation.get("messages", []):
                clean = {key: message.get(key) for key in ("role", "content", "citations_json", "created_at")}
                if _hash(clean) not in existing_messages:
                    db.execute("INSERT INTO ai_messages(conversation_id,role,content,citations_json,created_at) VALUES(?,?,?,?,?)", (conversation_id, clean["role"], clean["content"], clean["citations_json"] or "[]", clean["created_at"] or utc_now()))

        for item in data.get("ai_memories", []):
            exists = db.execute("SELECT 1 FROM ai_memories WHERE memory_type=? AND content=? AND created_at=?", (item.get("memory_type"), item.get("content"), item.get("created_at"))).fetchone()
            if not exists:
                columns = list(item)
                db.execute(f"INSERT INTO ai_memories({','.join(columns)}) VALUES({','.join('?' for _ in columns)})", tuple(item[key] for key in columns))
        for item in data.get("ai_daily_greetings", []):
            db.execute("INSERT INTO ai_daily_greetings(greeting_date,language,greeting,source,snapshot_json,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(greeting_date,language) DO UPDATE SET greeting=excluded.greeting,source=excluded.source,snapshot_json=excluded.snapshot_json,created_at=excluded.created_at", tuple(item.get(key) for key in ("greeting_date","language","greeting","source","snapshot_json","created_at")))
        for item in data.get("ai_usage_events", []):
            columns = [key for key in item if key != "id"]
            values = tuple(item[key] for key in columns)
            where = " AND ".join(f"{key} IS ?" for key in columns)
            if not db.execute(f"SELECT 1 FROM ai_usage_events WHERE {where} LIMIT 1", values).fetchone():
                db.execute(f"INSERT INTO ai_usage_events({','.join(columns)}) VALUES({','.join('?' for _ in columns)})", values)
        for item in data.get("site_skills", []):
            db.execute("""
                INSERT INTO site_skills(slug,display_name,description,user_instructions,feature_prefixes_json,enabled,is_builtin,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET display_name=excluded.display_name,
                description=excluded.description,user_instructions=excluded.user_instructions,
                feature_prefixes_json=excluded.feature_prefixes_json,enabled=excluded.enabled,updated_at=excluded.updated_at
            """, tuple(item.get(key) for key in ("slug","display_name","description","user_instructions","feature_prefixes_json","enabled","is_builtin","created_at","updated_at")))

        for item in data.get("record_meta", []):
            if not item.get("entity_type") or not item.get("entity_key") or not item.get("record_uuid"):
                continue
            db.execute("""
                INSERT INTO device_sync_records(
                    entity_type,entity_key,record_uuid,modified_at_utc,origin_device_id,content_hash
                ) VALUES(?,?,?,?,?,?) ON CONFLICT(entity_type,entity_key) DO UPDATE SET
                    record_uuid=excluded.record_uuid,
                    modified_at_utc=excluded.modified_at_utc,
                    origin_device_id=excluded.origin_device_id,
                    content_hash=excluded.content_hash
            """, tuple(item.get(key) or "" for key in (
                "entity_type", "entity_key", "record_uuid", "modified_at_utc",
                "origin_device_id", "content_hash",
            )))

        for item in data.get("tombstones", []):
            db.execute("INSERT INTO device_sync_tombstones(entity_type,entity_key,deleted_at,origin_device_id) VALUES(?,?,?,?) ON CONFLICT(entity_type,entity_key) DO UPDATE SET deleted_at=MAX(device_sync_tombstones.deleted_at,excluded.deleted_at),origin_device_id=excluded.origin_device_id", (item.get("entity_type"), item.get("entity_key"), item.get("deleted_at"), item.get("origin_device_id", "")))
            if item.get("entity_type") == "note":
                categories = _category_paths(db)
                for row in _row_dicts(db, "SELECT * FROM notes"):
                    row["category_path"] = categories.get(int(row.get("category_id") or 0), "")
                    if note_key(row) == item.get("entity_key"):
                        db.execute("DELETE FROM notes WHERE id=?", (row["id"],))
        if peer:
            db.execute("INSERT INTO device_sync_peers(device_id,device_name,platform,last_sync_at) VALUES(?,?,?,?) ON CONFLICT(device_id) DO UPDATE SET device_name=excluded.device_name,platform=excluded.platform,last_sync_at=excluded.last_sync_at", (peer.get("device_id"), peer.get("device_name", ""), peer.get("platform", ""), utc_now()))
        db.commit()
        check = db.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise DeviceSyncError("同步后的数据库未通过完整性检查。", code="apply_check_failed", status=500)
        return {"ok": True, "backup_name": backup.name, "counts": counts}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def package_summary(package: dict[str, Any]) -> dict[str, int]:
    data = validate_package(package)["data"]
    return {
        "words": len(data.get("user_words", [])),
        "favorites": len(data.get("favorites", [])),
        "wordbooks": len(data.get("wordbooks", [])),
        "notes": len(data.get("notes", [])),
        "practice": len(data.get("practice_sessions", [])),
        "conversations": len(data.get("ai_conversations", [])),
    }

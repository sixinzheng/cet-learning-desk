"""Versioned, read-only pronunciation pack access.

The distributable keeps thousands of MP3 entries inside one ZIP so Android and
Windows installers do not need to copy a directory containing 12k tiny files.
No user supplied path is ever used to select an archive member.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import zipfile

from runtime_paths import resource_path


PACK_DIR = Path(resource_path("resources", "pronunciation"))
MANIFEST_PATH = PACK_DIR / "manifest.json"
PACK_PATH = PACK_DIR / "pronunciation-pack-v1.zip"


class PronunciationUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=2)
def _load_manifest_versioned(modified_ns: int, size: int) -> dict:
    if not MANIFEST_PATH.is_file():
        return {"version": 1, "entries": {}}
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        raise PronunciationUnavailable("发音索引格式无效。")
    return payload


def load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        return {"version": 1, "entries": {}}
    stat = MANIFEST_PATH.stat()
    return _load_manifest_versioned(stat.st_mtime_ns, stat.st_size)


def audio_url(word_id: int) -> str:
    return f"/api/words/{int(word_id)}/audio"


def has_word_audio(word_id: int) -> bool:
    return str(int(word_id)) in load_manifest().get("entries", {}) and PACK_PATH.is_file()


@lru_cache(maxsize=96)
def read_word_audio(word_id: int) -> tuple[bytes, str]:
    key = str(int(word_id))
    entry = load_manifest().get("entries", {}).get(key)
    if not entry or not PACK_PATH.is_file():
        raise PronunciationUnavailable("该单词的离线发音尚未安装。")
    member = str(entry.get("path") or "") if isinstance(entry, dict) else str(entry)
    expected_prefix = f"words/{int(word_id)}."
    if not member.startswith(expected_prefix) or not member.endswith(".mp3"):
        raise PronunciationUnavailable("发音索引包含无效路径。")
    try:
        with zipfile.ZipFile(PACK_PATH, "r") as archive:
            data = archive.read(member)
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise PronunciationUnavailable("离线发音包损坏或缺少文件。") from exc
    if not data:
        raise PronunciationUnavailable("离线发音文件为空。")
    etag = hashlib.sha256(data).hexdigest()
    return data, etag


@lru_cache(maxsize=64)
def read_listening_audio(category: str, item_id: int) -> tuple[bytes, str]:
    safe_category = 'sentences' if category == 'sentences' else 'scenarios' if category == 'scenarios' else ''
    if not safe_category:
        raise PronunciationUnavailable("听力发音分类无效。")
    key = str(int(item_id))
    listening = load_manifest().get('listening') or {}
    entry = (listening.get(safe_category) or {}).get(key)
    if not entry or not PACK_PATH.is_file():
        raise PronunciationUnavailable("该听力材料的离线发音尚未安装。")
    member = str(entry.get('path') or '') if isinstance(entry, dict) else str(entry)
    expected = f'listening/{safe_category}/{int(item_id)}.mp3'
    if member != expected:
        raise PronunciationUnavailable("听力发音索引包含无效路径。")
    try:
        with zipfile.ZipFile(PACK_PATH, 'r') as archive:
            data = archive.read(member)
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise PronunciationUnavailable("离线发音包损坏或缺少文件。") from exc
    if not data:
        raise PronunciationUnavailable("离线发音文件为空。")
    return data, hashlib.sha256(data).hexdigest()


def reset_manifest_cache() -> None:
    _load_manifest_versioned.cache_clear()
    read_word_audio.cache_clear()
    read_listening_audio.cache_clear()

"""稳定 GitHub Release 检查与更新前数据库保护。"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

import database
from app_version import (
    APP_VERSION,
    GITHUB_LATEST_RELEASE_API,
    GITHUB_RELEASES_URL,
    GITHUB_REPOSITORY_URL,
)
from runtime_paths import IS_ANDROID, IS_DESKTOP


_MAX_RELEASE_RESPONSE = 2 * 1024 * 1024
_BACKUP_KEEP_COUNT = 3
_TICKET_TTL_SECONDS = 10 * 60
_STATE_LOCK = threading.RLock()
_PROGRESS: dict[str, Any] = {
    "stage": "idle",
    "percent": 0,
    "message": "尚未开始更新。",
    "updated_at": "",
}
_TICKETS: dict[str, dict[str, Any]] = {}


class UpdateServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "update_failed", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def current_platform() -> str:
    if IS_ANDROID:
        return "android"
    if IS_DESKTOP:
        return "windows"
    return "source"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _set_progress(stage: str, percent: int, message: str, **extra: Any) -> None:
    with _STATE_LOCK:
        _PROGRESS.clear()
        _PROGRESS.update({
            "stage": stage,
            "percent": max(0, min(100, int(percent))),
            "message": message,
            "updated_at": _now_iso(),
            **extra,
        })


def progress_snapshot() -> dict[str, Any]:
    with _STATE_LOCK:
        return dict(_PROGRESS)


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value or "").strip())
    if not match:
        raise UpdateServiceError(
            "发布版本号格式不正确，已停止更新。",
            code="invalid_release_version",
            status=502,
        )
    return tuple(int(part) for part in match.groups())


def _release_asset_size(release: dict[str, Any], platform: str) -> int:
    assets = release.get("assets") if isinstance(release.get("assets"), list) else []
    suffixes = (".apk",) if platform == "android" else (".exe", ".msi")
    sizes = [
        int(asset.get("size") or 0)
        for asset in assets
        if isinstance(asset, dict)
        and str(asset.get("name") or "").lower().endswith(suffixes)
    ]
    return max(sizes, default=0)


def _validate_release(release: Any) -> dict[str, Any]:
    if not isinstance(release, dict):
        raise UpdateServiceError("GitHub 返回了无法识别的发布信息。", code="invalid_release", status=502)
    if release.get("draft") or release.get("prerelease"):
        raise UpdateServiceError("最新发布不是稳定版本，当前不会安装。", code="unstable_release", status=409)
    tag = str(release.get("tag_name") or "").strip()
    _version_tuple(tag)
    html_url = str(release.get("html_url") or "")
    if not html_url.startswith(GITHUB_REPOSITORY_URL + "/releases/"):
        raise UpdateServiceError("发布地址不属于官方仓库，已停止更新。", code="untrusted_release", status=502)
    return release


def fetch_latest_release(
    *,
    http_get: Callable[..., Any] = requests.get,
    timeout: tuple[int, int] = (4, 12),
) -> dict[str, Any]:
    try:
        response = http_get(
            GITHUB_LATEST_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"CETLearningDesk/{APP_VERSION}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        content = response.content
    except requests.Timeout as exc:
        raise UpdateServiceError("检查更新超时，请确认网络后重试。", code="timeout", status=504) from exc
    except requests.HTTPError as exc:
        response_status = getattr(getattr(exc, "response", None), "status_code", 0)
        if response_status in {403, 429}:
            raise UpdateServiceError(
                "GitHub 暂时限制了检查频率，请稍后重试。",
                code="rate_limited",
                status=503,
            ) from exc
        raise UpdateServiceError("暂时无法连接 GitHub，请稍后重试。", code="network_error", status=503) from exc
    except requests.RequestException as exc:
        raise UpdateServiceError("暂时无法连接 GitHub，请稍后重试。", code="network_error", status=503) from exc
    if len(content) > _MAX_RELEASE_RESPONSE:
        raise UpdateServiceError("发布信息异常过大，已停止更新。", code="oversized_release", status=502)
    try:
        return _validate_release(response.json())
    except ValueError as exc:
        raise UpdateServiceError("GitHub 返回的发布信息无法解析。", code="invalid_json", status=502) from exc


def _release_payload(release: dict[str, Any]) -> dict[str, Any]:
    platform = current_platform()
    latest = str(release.get("tag_name") or "").lstrip("v")
    available = _version_tuple(latest) > _version_tuple(APP_VERSION)
    install_supported = platform in {"windows", "android"}
    return {
        "platform": platform,
        "current_version": APP_VERSION,
        "latest_version": latest,
        "update_available": available,
        "install_supported": install_supported,
        "requires_manual_bootstrap": not install_supported or _version_tuple(APP_VERSION) < (0, 3, 0),
        "release_name": str(release.get("name") or release.get("tag_name") or latest),
        "release_notes": str(release.get("body") or "本次发布未提供更新说明。")[:12000],
        "published_at": str(release.get("published_at") or ""),
        "download_size": _release_asset_size(release, platform),
        "release_url": str(release.get("html_url") or GITHUB_RELEASES_URL),
        "channel": "stable",
        "progress": progress_snapshot(),
    }


def update_status(*, http_get: Callable[..., Any] = requests.get) -> dict[str, Any]:
    _set_progress("checking", 5, "正在检查稳定版 Release…")
    try:
        payload = _release_payload(fetch_latest_release(http_get=http_get))
    except UpdateServiceError as exc:
        _set_progress("error", 0, str(exc), error_code=exc.code)
        raise
    if payload["update_available"]:
        _set_progress("available", 10, f"发现稳定版 {payload['latest_version']}。")
    else:
        _set_progress("current", 100, "已经是最新稳定版。")
    payload["progress"] = progress_snapshot()
    return payload


def _safe_backup_name(from_version: str, to_version: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    clean_from = re.sub(r"[^0-9A-Za-z._-]", "-", from_version)[:24]
    clean_to = re.sub(r"[^0-9A-Za-z._-]", "-", to_version)[:24]
    return f"vocab-before-{clean_from}-to-{clean_to}-{timestamp}.db"


def create_verified_backup(from_version: str, to_version: str) -> Path:
    source_path = Path(database.DB_PATH).resolve()
    if not source_path.is_file():
        raise UpdateServiceError("没有找到学习数据库，无法开始安全更新。", code="database_missing", status=500)
    backup_dir = source_path.parent / "update-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    required = max(source_path.stat().st_size * 2, 20 * 1024 * 1024)
    if shutil.disk_usage(backup_dir).free < required:
        raise UpdateServiceError("磁盘空间不足，无法创建更新前备份。", code="insufficient_space", status=507)

    final_path = backup_dir / _safe_backup_name(from_version, to_version)
    temporary_path = backup_dir / f".{final_path.name}.{secrets.token_hex(6)}.tmp"
    _set_progress("backing_up", 25, "正在创建一致性数据库备份…")
    try:
        source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True, timeout=20)
        destination = sqlite3.connect(str(temporary_path), timeout=20)
        try:
            source.backup(destination, pages=256)
            destination.commit()
        finally:
            destination.close()
            source.close()

        with temporary_path.open("r+b") as handle:
            os.fsync(handle.fileno())
        check = sqlite3.connect(str(temporary_path))
        try:
            result = check.execute("PRAGMA quick_check").fetchone()
        finally:
            check.close()
        if not result or result[0] != "ok":
            raise UpdateServiceError("数据库备份未通过完整性检查，已取消更新。", code="backup_check_failed", status=500)
        os.replace(temporary_path, final_path)

        backups = sorted(backup_dir.glob("vocab-before-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
        for old_backup in backups[_BACKUP_KEEP_COUNT:]:
            old_backup.unlink(missing_ok=True)
        _set_progress("backup_ready", 45, "数据库备份已通过校验。", backup_name=final_path.name)
        return final_path
    except UpdateServiceError:
        temporary_path.unlink(missing_ok=True)
        raise
    except (OSError, sqlite3.Error) as exc:
        temporary_path.unlink(missing_ok=True)
        raise UpdateServiceError("数据库备份失败，现有程序与数据均未修改。", code="backup_failed", status=500) from exc


def _prune_tickets() -> None:
    cutoff = time.time() - _TICKET_TTL_SECONDS
    expired = [token for token, item in _TICKETS.items() if item["created_at"] < cutoff]
    for token in expired:
        _TICKETS.pop(token, None)


def prepare_update(*, http_get: Callable[..., Any] = requests.get) -> dict[str, Any]:
    platform = current_platform()
    if platform == "source":
        raise UpdateServiceError(
            "源码运行模式不会修改 Git 工作区，请到 GitHub Release 手动下载安装版。",
            code="source_mode",
            status=409,
        )
    release = fetch_latest_release(http_get=http_get)
    payload = _release_payload(release)
    if not payload["update_available"]:
        raise UpdateServiceError("当前已经是最新稳定版。", code="already_current", status=409)

    backup_path = create_verified_backup(APP_VERSION, payload["latest_version"])
    with _STATE_LOCK:
        _prune_tickets()
        ticket = secrets.token_urlsafe(32)
        _TICKETS[ticket] = {
            "created_at": time.time(),
            "platform": platform,
            "version": payload["latest_version"],
            "backup_name": backup_path.name,
        }
    _set_progress("ready_for_native", 50, "备份已完成，等待系统安全安装。", backup_name=backup_path.name)
    return {
        "ok": True,
        "ticket": ticket,
        "native_action": f"cetlearningdesk://update/install?ticket={ticket}",
        "latest_version": payload["latest_version"],
        "backup_name": backup_path.name,
        "release_url": payload["release_url"],
        "progress": progress_snapshot(),
    }


def validate_native_ticket(ticket: str, platform: str) -> bool:
    """供原生桥在需要时验证短期票据；验证成功后立即失效。"""
    with _STATE_LOCK:
        _prune_tickets()
        item = _TICKETS.pop(str(ticket or ""), None)
    return bool(item and item.get("platform") == platform)

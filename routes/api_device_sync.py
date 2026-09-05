"""Local control plane for one-shot encrypted device synchronization."""

from __future__ import annotations

import secrets
from functools import wraps

from flask import Blueprint, jsonify, request, session

from services.device_sync_data import (
    DeviceSyncError,
    apply_package,
    commit_prepared_package,
    export_package,
    package_summary,
    prepare_package,
)
from services.device_sync_service import (
    authorize_mobile_ticket,
    issue_mobile_ticket,
    session_snapshot,
    start_session,
    stop_session,
)
from services.level_service import calculate_level


bp = Blueprint("device_sync", __name__)


def _csrf_token() -> str:
    if not session.get("ai_csrf_token"):
        session["ai_csrf_token"] = secrets.token_urlsafe(24)
    return session["ai_csrf_token"]


def _require_csrf(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
            return jsonify({"error": "请求来源不受信任。", "code": "untrusted_origin"}), 403
        supplied = request.headers.get("X-CSRF-Token", "")
        if not supplied or not secrets.compare_digest(supplied, _csrf_token()):
            return jsonify({"error": "安全令牌已失效，请刷新后重试。", "code": "csrf_failed"}), 403
        return view(*args, **kwargs)
    return wrapped


def _local_only() -> bool:
    return request.remote_addr in {"127.0.0.1", "::1"}


@bp.get("/status")
def status():
    payload = session_snapshot()
    payload["csrf_token"] = _csrf_token()
    return jsonify(payload)


@bp.post("/sessions")
@_require_csrf
def create_session():
    try:
        payload = start_session()
        payload["csrf_token"] = _csrf_token()
        return jsonify(payload)
    except DeviceSyncError as exc:
        return jsonify({"error": str(exc), "code": exc.code}), exc.status


@bp.delete("/sessions/current")
@_require_csrf
def delete_session():
    stop_session()
    return jsonify({"ok": True, "active": False})


@bp.post("/mobile-ticket")
@_require_csrf
def mobile_ticket():
    if not _local_only():
        return jsonify({"error": "原生同步票据仅供本机使用。"}), 403
    return jsonify({"ticket": issue_mobile_ticket()})


@bp.get("/native-package/<ticket>")
def native_package(ticket: str):
    if not _local_only() or not authorize_mobile_ticket(ticket, "export"):
        return jsonify({"error": "同步票据无效或已使用。", "code": "invalid_ticket"}), 403
    try:
        payload = export_package()
        return jsonify({"package": payload, "summary": package_summary(payload)})
    except DeviceSyncError as exc:
        return jsonify({"error": str(exc), "code": exc.code}), exc.status


@bp.post("/native-apply/<ticket>")
def native_apply(ticket: str):
    if not _local_only() or not authorize_mobile_ticket(ticket, "apply"):
        return jsonify({"error": "同步票据无效或已使用。", "code": "invalid_ticket"}), 403
    body = request.get_json(silent=True) or {}
    try:
        package = body.get("package")
        result = apply_package(package, peer=body.get("peer"))
        calculate_level(reason="device_sync")
        return jsonify(result)
    except DeviceSyncError as exc:
        return jsonify({"error": str(exc), "code": exc.code}), exc.status
    except Exception:
        return jsonify({"error": "手机端应用同步数据失败，备份已经保留。", "code": "apply_failed"}), 500


@bp.post("/native-prepare/<ticket>")
def native_prepare(ticket: str):
    if not _local_only() or not authorize_mobile_ticket(ticket, "prepare"):
        return jsonify({"error": "同步票据无效或已使用。", "code": "invalid_ticket"}), 403
    body = request.get_json(silent=True) or {}
    try:
        result = prepare_package(
            body.get("package"),
            str(body.get("transaction_id") or ""),
            peer=body.get("peer"),
        )
        return jsonify(result)
    except DeviceSyncError as exc:
        return jsonify({"error": str(exc), "code": exc.code}), exc.status
    except Exception:
        return jsonify({"error": "手机端准备同步副本失败，正式数据没有修改。", "code": "prepare_failed"}), 500


@bp.post("/native-commit/<ticket>")
def native_commit(ticket: str):
    if not _local_only() or not authorize_mobile_ticket(ticket, "commit"):
        return jsonify({"error": "同步票据无效或已使用。", "code": "invalid_ticket"}), 403
    body = request.get_json(silent=True) or {}
    try:
        result = commit_prepared_package(str(body.get("transaction_id") or ""))
        try:
            calculate_level(reason="device_sync")
        except Exception:
            result["recalculation_warning"] = "段位历史将在下次打开页面时自动补算。"
        return jsonify(result)
    except DeviceSyncError as exc:
        return jsonify({"error": str(exc), "code": exc.code}), exc.status
    except Exception:
        return jsonify({"error": "手机端提交同步结果失败，可使用备份恢复。", "code": "commit_failed"}), 500

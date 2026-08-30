"""应用更新状态、备份准备与原生票据接口。"""

from __future__ import annotations

import secrets
from functools import wraps

from flask import Blueprint, jsonify, request, session

from services.update_service import (
    UpdateServiceError,
    prepare_update,
    progress_snapshot,
    update_status,
    validate_native_ticket,
)


bp = Blueprint("app_update", __name__)


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
            return jsonify({"error": "安全令牌已失效，请刷新页面后重试。", "code": "csrf_failed"}), 403
        return view(*args, **kwargs)
    return wrapped


@bp.get("/status")
def status():
    try:
        payload = update_status()
    except UpdateServiceError as exc:
        return jsonify({
            "error": str(exc),
            "code": exc.code,
            "csrf_token": _csrf_token(),
            "progress": progress_snapshot(),
        }), exc.status
    payload["csrf_token"] = _csrf_token()
    return jsonify(payload)


@bp.post("/prepare")
@_require_csrf
def prepare():
    try:
        payload = prepare_update()
        print(f"CET_UPDATE_TICKET={payload['ticket']}", flush=True)
        return jsonify(payload)
    except UpdateServiceError as exc:
        return jsonify({"error": str(exc), "code": exc.code, "progress": progress_snapshot()}), exc.status


@bp.get("/progress")
def progress():
    return jsonify(progress_snapshot())


@bp.get("/native-ticket/<ticket>")
def native_ticket(ticket: str):
    platform = request.args.get("platform", "")
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return jsonify({"valid": False}), 403
    valid = validate_native_ticket(ticket, platform)
    return jsonify({"valid": valid}), (200 if valid else 404)

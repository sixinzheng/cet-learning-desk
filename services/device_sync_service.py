"""Short-lived, TLS-pinned LAN transport for Windows <-> Android sync."""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import secrets
import socket
import ssl
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from services.device_sync_data import (
    MAX_PACKAGE_BYTES,
    DeviceSyncError,
    apply_package,
    device_identity,
    export_package,
    merge_packages,
    package_summary,
    validate_package,
)


SESSION_TTL_SECONDS = 10 * 60
_LOCK = threading.RLock()
_SESSION: dict[str, Any] | None = None
_LAST_SNAPSHOT: dict[str, Any] | None = None
_MOBILE_TICKETS: dict[str, dict[str, Any]] = {}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def decode_pairing_code(code: str) -> dict[str, Any]:
    value = str(code or "").strip()
    if value.startswith("cet-sync:"):
        value = value[9:]
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeviceSyncError("配对码无法识别，请重新扫描。", code="invalid_pairing_code") from exc
    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise DeviceSyncError("配对码版本不受支持，请更新两台设备。", code="pairing_version")
    return payload


def _private_addresses() -> list[str]:
    candidates: set[str] = set()
    try:
        candidates.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.0.2.1", 9))
            candidates.add(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    result = []
    for value in sorted(candidates):
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if address.version == 4 and address.is_private and not address.is_loopback and not address.is_link_local:
            result.append(value)
    return result


def _certificate(addresses: list[str], directory: Path) -> tuple[Path, Path, str]:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
    except ImportError as exc:
        raise DeviceSyncError(
            "本地安装缺少加密同步组件，请安装修复版后重试。",
            code="crypto_unavailable",
            status=503,
        ) from exc
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CET Device Sync")])
    now = datetime.now(timezone.utc)
    alt_names = [x509.IPAddress(ipaddress.ip_address(value)) for value in addresses]
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(minutes=15))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = directory / "session-cert.pem"
    key_path = directory / "session-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    fingerprint = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
    return cert_path, key_path, fingerprint


def _qr_data_url(value: str) -> str:
    try:
        import qrcode
    except ImportError as exc:
        raise DeviceSyncError(
            "本地安装缺少二维码组件，请安装修复版后重试。",
            code="qr_unavailable",
            status=503,
        ) from exc
    from io import BytesIO
    image = qrcode.make(value)
    output = BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _authorized(handler: BaseHTTPRequestHandler, token: str) -> bool:
    supplied = handler.headers.get("Authorization", "")
    return secrets.compare_digest(supplied, "Bearer " + token)


def _write_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    handler.wfile.write(body)


class _SyncServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


class _Handler(BaseHTTPRequestHandler):
    server_version = "CETDeviceSync/1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _session(self) -> dict[str, Any] | None:
        with _LOCK:
            return _SESSION

    def do_GET(self) -> None:  # noqa: N802
        session = self._session()
        if not session or time.time() >= session["expires_epoch"]:
            _write_json(self, 410, {"error": "同步会话已过期。", "code": "session_expired"})
            return
        if not _authorized(self, session["token"]):
            _write_json(self, 401, {"error": "配对令牌不正确。", "code": "unauthorized"})
            return
        if self.path != "/sync/v1/handshake":
            _write_json(self, 404, {"error": "接口不存在。"})
            return
        package = export_package()
        _write_json(self, 200, {
            "protocol_version": 1,
            "session_id": session["session_id"],
            "device": package["device"],
            "summary": package_summary(package),
            "expires_at": session["expires_at"],
        })

    def do_POST(self) -> None:  # noqa: N802
        session = self._session()
        if not session or time.time() >= session["expires_epoch"]:
            _write_json(self, 410, {"error": "同步会话已过期。", "code": "session_expired"})
            return
        if not _authorized(self, session["token"]):
            _write_json(self, 401, {"error": "配对令牌不正确。", "code": "unauthorized"})
            return
        if self.path != "/sync/v1/exchange":
            _write_json(self, 404, {"error": "接口不存在。"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_PACKAGE_BYTES + 1024 * 1024:
            _write_json(self, 413, {"error": "同步数据包体积异常。", "code": "package_too_large"})
            return
        with _LOCK:
            if session.get("used"):
                _write_json(self, 409, {"error": "该一次性同步会话已使用。", "code": "session_used"})
                return
            session["stage"] = "merging"
        try:
            incoming = json.loads(self.rfile.read(length).decode("utf-8"))
            validate_package(incoming)
            local = export_package()
            merged = merge_packages(local, incoming)
            applied = apply_package(merged, peer=incoming["device"])
            with _LOCK:
                session["stage"] = "completed"
                session["used"] = True
                session["peer"] = incoming["device"]
                session["summary"] = package_summary(merged)
            _write_json(self, 200, {"ok": True, "merged": merged, "desktop": applied})
            # Close the LAN listener as soon as the response has left the socket.
            closer = threading.Timer(0.5, stop_session, kwargs={"preserve_status": True})
            closer.daemon = True
            closer.start()
        except DeviceSyncError as exc:
            with _LOCK:
                session["stage"] = "error"; session["error"] = str(exc)
            _write_json(self, exc.status, {"error": str(exc), "code": exc.code})
        except Exception:
            with _LOCK:
                session["stage"] = "error"; session["error"] = "合并学习数据失败。"
            _write_json(self, 500, {"error": "合并学习数据失败，两端备份均保留。", "code": "merge_failed"})


def start_session() -> dict[str, Any]:
    global _SESSION, _LAST_SNAPSHOT
    stop_session(preserve_status=False)
    with _LOCK:
        _LAST_SNAPSHOT = None
    addresses = _private_addresses()
    if not addresses:
        raise DeviceSyncError("没有找到可用的同一 Wi-Fi 私网地址。", code="lan_address_missing", status=503)
    session_id = secrets.token_urlsafe(12)
    token = secrets.token_urlsafe(32)
    temp_dir = Path(tempfile.mkdtemp(prefix="cet-device-sync-"))
    cert_path, key_path, fingerprint = _certificate(addresses, temp_dir)
    server = _SyncServer(("0.0.0.0", 0), _Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(cert_path), str(key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    port = int(server.server_address[1])
    expires_epoch = time.time() + SESSION_TTL_SECONDS
    expires_at = datetime.fromtimestamp(expires_epoch, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    pairing_payload = {
        "v": 1, "url": f"https://{addresses[0]}:{port}", "token": token,
        "fingerprint": fingerprint, "session_id": session_id, "expires_at": expires_at,
    }
    pairing_code = "cet-sync:" + _b64url(json.dumps(pairing_payload, separators=(",", ":")).encode("utf-8"))
    thread = threading.Thread(target=server.serve_forever, name="cet-device-sync", daemon=True)
    with _LOCK:
        _SESSION = {
            "session_id": session_id, "token": token, "fingerprint": fingerprint,
            "addresses": addresses, "port": port, "expires_epoch": expires_epoch,
            "expires_at": expires_at, "pairing_code": pairing_code, "stage": "waiting",
            "used": False, "server": server, "thread": thread, "temp_dir": temp_dir,
            "device": device_identity(),
        }
    thread.start()
    timer = threading.Timer(SESSION_TTL_SECONDS, stop_session)
    timer.daemon = True
    timer.start()
    with _LOCK:
        if _SESSION:
            _SESSION["timer"] = timer
    return session_snapshot(include_pairing=True)


def session_snapshot(*, include_pairing: bool = False) -> dict[str, Any]:
    with _LOCK:
        session = _SESSION
        if not session:
            return dict(_LAST_SNAPSHOT or {"active": False, "stage": "idle"})
        payload = {
            "active": time.time() < session["expires_epoch"] and not session.get("used", False),
            "stage": session.get("stage", "waiting"),
            "session_id": session["session_id"], "expires_at": session["expires_at"],
            "addresses": session["addresses"], "port": session["port"],
            "device": session["device"], "peer": session.get("peer"),
            "summary": session.get("summary"), "error": session.get("error", ""),
        }
        if include_pairing:
            payload["pairing_code"] = session["pairing_code"]
            payload["qr_data_url"] = _qr_data_url(session["pairing_code"])
        return payload


def stop_session(*, preserve_status: bool = False) -> None:
    global _SESSION, _LAST_SNAPSHOT
    with _LOCK:
        session, _SESSION = _SESSION, None
        if preserve_status and session:
            _LAST_SNAPSHOT = {
                "active": False,
                "stage": session.get("stage", "completed"),
                "session_id": session.get("session_id", ""),
                "expires_at": session.get("expires_at", ""),
                "addresses": session.get("addresses", []),
                "port": session.get("port", 0),
                "device": session.get("device"),
                "peer": session.get("peer"),
                "summary": session.get("summary"),
                "error": session.get("error", ""),
            }
        elif not preserve_status:
            _LAST_SNAPSHOT = None
    if not session:
        return
    timer = session.get("timer")
    if timer:
        timer.cancel()
    server = session.get("server")
    if server:
        try:
            server.shutdown(); server.server_close()
        except OSError:
            pass
    directory = session.get("temp_dir")
    if directory:
        for child in Path(directory).glob("*"):
            child.unlink(missing_ok=True)
        Path(directory).rmdir()


def issue_mobile_ticket() -> str:
    token = secrets.token_urlsafe(32)
    with _LOCK:
        now = time.time()
        expired = [key for key, item in _MOBILE_TICKETS.items() if item["expires"] <= now]
        for key in expired:
            _MOBILE_TICKETS.pop(key, None)
        _MOBILE_TICKETS[token] = {"expires": now + 5 * 60, "uses": set()}
    return token


def authorize_mobile_ticket(token: str, purpose: str) -> bool:
    with _LOCK:
        item = _MOBILE_TICKETS.get(str(token or ""))
        if not item or item["expires"] <= time.time() or purpose in item["uses"]:
            return False
        item["uses"].add(purpose)
        if purpose == "apply":
            _MOBILE_TICKETS.pop(str(token or ""), None)
        return True

"""Android WebView 内嵌的本地 Flask 服务入口。"""

from __future__ import annotations

import os
import socket
import sys
import threading


_server = None


def _activate_resource_imports(resource_root: str) -> str:
    """Expose unpacked Android resources to Python imports before Flask loads.

    Chaquopy packages the application modules separately from the read-only
    website resources.  The latter also contain the ``seed`` package and its
    reviewed reading corpus, so Android must add that unpacked directory to
    ``sys.path`` before importing :mod:`app` / :mod:`database`.
    """
    resolved = os.path.abspath(str(resource_root))
    if not os.path.isdir(resolved):
        raise RuntimeError(f'Android 资源目录不存在：{resolved}')
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    return resolved


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(('127.0.0.1', 0))
        return int(probe.getsockname()[1])


def start(data_dir: str, resource_root: str) -> str:
    """启动仅监听手机本机的学习服务，并返回 WebView 入口。"""
    global _server
    if _server is not None:
        return f'http://127.0.0.1:{_server.server_port}/'

    resolved_resource_root = _activate_resource_imports(resource_root)

    os.environ['CET_ANDROID'] = '1'
    os.environ['CET_DATA_DIR'] = os.path.abspath(str(data_dir))
    os.environ['CET_RESOURCE_ROOT'] = resolved_resource_root

    # 路径变量必须在导入应用模块之前设置。
    from app import create_app
    from werkzeug.serving import make_server

    port = _free_port()
    app = create_app()
    _server = make_server('127.0.0.1', port, app, threaded=True)
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{port}/'

"""安装版桌面外壳使用的 Flask sidecar 入口。"""

from __future__ import annotations

import argparse
import ctypes
import os
import socket
import sys
import threading
import time
import traceback


DEFAULT_DESKTOP_PORT = 5099
PORT_RELEASE_WAIT_SECONDS = 8.0


def _parse_args(argv=None):
    parser = argparse.ArgumentParser()
    # 桌面 WebView 的 localStorage 以 origin（包含端口）隔离。使用随机端口会让
    # 新手引导、字号、头像等本地状态在每次启动时看起来被重置。
    parser.add_argument('--port', type=int, default=DEFAULT_DESKTOP_PORT)
    parser.add_argument('--parent-pid', type=int, default=0)
    parser.add_argument('--data-dir', default='')
    return parser.parse_args(argv)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(('127.0.0.1', 0))
        return int(probe.getsockname()[1])


def _wait_for_port_release(port: int, timeout: float = PORT_RELEASE_WAIT_SECONDS) -> None:
    """短暂等待上一个 sidecar 退出，避免快速重启时误报端口占用。"""
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(('127.0.0.1', port))
                return
            except OSError as error:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f'桌面学习服务固定端口 {port} 被其他程序占用，请关闭占用程序后重试。'
                    ) from error
        time.sleep(0.2)


def _parent_alive(pid: int) -> bool:
    if pid <= 0 or os.name != 'nt':
        return True
    process_query_limited_information = 0x1000
    synchronize = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(
        process_query_limited_information | synchronize, False, pid
    )
    if not handle:
        return False
    try:
        wait_timeout = 0x00000102
        return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == wait_timeout
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _watch_parent(pid: int):
    while _parent_alive(pid):
        time.sleep(2)
    os._exit(0)


def main() -> int:
    args = _parse_args()
    os.environ['CET_DESKTOP'] = '1'
    if args.data_dir:
        os.environ['CET_DATA_DIR'] = os.path.abspath(args.data_dir)

    # 路径环境必须在导入应用模块前设置。
    from app import create_app
    from waitress import create_server

    port = args.port if args.port > 0 else _free_port()
    if args.port > 0:
        _wait_for_port_release(port)
    app = create_app()
    server = create_server(app, host='127.0.0.1', port=port, threads=8)
    if args.parent_pid:
        threading.Thread(target=_watch_parent, args=(args.parent_pid,), daemon=True).start()
    print(f'CET_BACKEND_READY=http://127.0.0.1:{port}', flush=True)
    server.run()
    return 0


def _write_crash_log() -> str:
    local_app_data = os.environ.get('LOCALAPPDATA', '').strip()
    if not local_app_data:
        local_app_data = os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    log_dir = os.path.join(local_app_data, 'CETLearningDesk', 'logs')
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'backend-error.log')
        with open(log_path, 'w', encoding='utf-8') as stream:
            traceback.print_exc(file=stream)
        return log_path
    except OSError:
        return ''


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        log_path = _write_crash_log()
        suffix = f' 错误记录：{log_path}' if log_path else ''
        print(
            'CET_BACKEND_ERROR=本地学习服务启动失败，请关闭后重新打开。'
            + suffix,
            flush=True,
        )
        sys.exit(1)

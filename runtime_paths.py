"""开发环境与安装版共享的资源、用户数据路径规则。"""

from __future__ import annotations

import os
import sqlite3
import shutil
import sys
import time


APP_ID = "CETLearningDesk"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RESOURCE_ROOT = os.path.abspath(
    os.environ.get("CET_RESOURCE_ROOT")
    or getattr(sys, "_MEIPASS", PROJECT_ROOT)
)
IS_PACKAGED = bool(getattr(sys, "frozen", False))
IS_ANDROID = os.environ.get("CET_ANDROID", "").strip() == "1"
IS_DESKTOP = IS_PACKAGED or os.environ.get("CET_DESKTOP", "").strip() == "1"


def resource_path(*parts: str) -> str:
    return os.path.join(RESOURCE_ROOT, *parts)


def _default_user_data_dir() -> str:
    explicit = os.environ.get("CET_DATA_DIR", "").strip()
    if explicit:
        return os.path.abspath(os.path.expandvars(os.path.expanduser(explicit)))
    if IS_DESKTOP:
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if not local_app_data:
            local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(local_app_data, APP_ID, "data")
    return os.path.join(PROJECT_ROOT, "data")


USER_DATA_DIR = _default_user_data_dir()
SEED_DB_PATH = resource_path("resources", "distribution", "vocab.seed.db")


def _database_is_valid(path: str) -> bool:
    """只读式检查首次安装结果，避免把半份数据库当作可用数据。"""
    if not os.path.isfile(path) or os.path.getsize(path) < 512:
        return False
    try:
        connection = sqlite3.connect(path)
        try:
            result = connection.execute('PRAGMA quick_check').fetchone()
            return bool(result and result[0] == 'ok')
        finally:
            connection.close()
    except sqlite3.Error:
        return False


def _unlink_with_retry(path: str) -> None:
    for attempt in range(10):
        try:
            os.unlink(path)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.25 * (attempt + 1))


def _install_seed(seed_path: str, target: str) -> None:
    """直接写入种子库并用标记恢复中断安装，不执行跨卷 rename/replace。"""
    marker = f'{target}.installing'

    # 上次若在写完数据库后、删除标记前退出，直接认可已校验的数据。
    if os.path.exists(target):
        if not os.path.exists(marker):
            return
        if _database_is_valid(target):
            _unlink_with_retry(marker)
            return
        _unlink_with_retry(target)

    with open(marker, 'w', encoding='utf-8') as marker_file:
        marker_file.write('CETLearningDesk seed installation in progress\n')
        marker_file.flush()
        os.fsync(marker_file.fileno())

    try:
        with open(seed_path, 'rb') as source, open(target, 'xb') as destination:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
            destination.flush()
            os.fsync(destination.fileno())
        if not _database_is_valid(target):
            raise RuntimeError('发行种子库复制后未通过 SQLite 完整性检查。')
    except Exception:
        # 保留安装标记；下次启动会识别并替换不完整文件。
        raise
    else:
        _unlink_with_retry(marker)


def ensure_user_data() -> str:
    """创建用户数据目录；安装版首次启动时复制干净发行种子库。"""
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    target = os.path.join(USER_DATA_DIR, "vocab.db")
    marker = f'{target}.installing'
    if (IS_DESKTOP or IS_ANDROID) and (not os.path.exists(target) or os.path.exists(marker)):
        if not os.path.isfile(SEED_DB_PATH):
            raise RuntimeError(
                "安装包缺少发行种子库 resources/distribution/vocab.seed.db，"
                "请重新安装或联系发布者。"
            )
        _install_seed(SEED_DB_PATH, target)
    return USER_DATA_DIR

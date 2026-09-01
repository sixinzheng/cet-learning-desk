"""将已有源码版学习数据库安全迁移到 Windows 桌面应用数据目录。"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


REQUIRED_TABLES = {
    'words', 'user_words', 'study_logs', 'notes', 'ai_conversations',
    'ai_messages', 'user_level', 'user_settings',
}


def _snapshot(source: Path, destination: Path) -> None:
    destination.unlink(missing_ok=True)
    source_db = sqlite3.connect(source)
    destination_db = sqlite3.connect(destination)
    try:
        source_db.backup(destination_db)
    finally:
        destination_db.close()
        source_db.close()


def _inspect(path: Path) -> dict:
    connection = sqlite3.connect(path)
    try:
        integrity = connection.execute('PRAGMA quick_check').fetchone()[0]
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = sorted(REQUIRED_TABLES - tables)
        if integrity != 'ok' or missing:
            raise RuntimeError(
                f'数据库校验失败：quick_check={integrity}，缺少表={missing}'
            )
        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in sorted(REQUIRED_TABLES)
        }
        return {'quick_check': integrity, 'counts': counts}
    finally:
        connection.close()


def migrate(source: Path, target: Path) -> dict:
    source = source.resolve()
    target = target.resolve()
    if not source.is_file():
        raise FileNotFoundError(f'原网站数据库不存在：{source}')
    source_info = _inspect(source)

    target.parent.mkdir(parents=True, exist_ok=True)
    backup_dir = target.parent.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = backup_dir / f'vocab-before-source-import-{stamp}.db'
    importing = target.with_suffix(target.suffix + '.importing')

    if target.exists():
        _snapshot(target, backup)
        _inspect(backup)

    _snapshot(source, importing)
    imported_info = _inspect(importing)
    if imported_info['counts'] != source_info['counts']:
        importing.unlink(missing_ok=True)
        raise RuntimeError('迁移快照的核心表计数与原网站数据库不一致。')

    # 目标应用已经关闭时清除旧 WAL 辅助文件，避免它们附着到新主库。
    for suffix in ('-wal', '-shm'):
        Path(str(target) + suffix).unlink(missing_ok=True)
    os.replace(importing, target)
    final_info = _inspect(target)
    return {
        'status': 'ok',
        'source': str(source),
        'target': str(target),
        'backup': str(backup) if backup.exists() else '',
        **final_info,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    target = args.target or (
        Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        / 'CETLearningDesk' / 'data' / 'vocab.db'
    )
    try:
        result = migrate(args.source, target)
    except Exception as error:
        result = {'status': 'error', 'error': str(error)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())

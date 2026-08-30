"""从当前内容库生成不含任何个人数据的安装版种子数据库。"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


PUBLIC_TABLES = {
    'cloze_blanks', 'cloze_passages', 'grammar_lessons', 'grammar_questions',
    'listening_scenarios', 'reading_articles', 'reading_questions', 'sentences',
    'site_skills', 'wordbook_words', 'wordbooks', 'words',
}

PERSONAL_TABLES = {
    'ai_action_drafts', 'ai_conversations', 'ai_daily_greetings', 'ai_memories',
    'ai_messages', 'ai_usage_events', 'article_annotations',
    'daily_word_completions', 'export_queue', 'note_categories', 'notes',
    'practice_sessions', 'reading_generation_jobs', 'study_logs', 'user_level',
    'user_settings', 'user_words', 'word_links',
}


def _tables(db: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def build_seed(source: Path, output: Path) -> dict[str, int]:
    if not source.is_file():
        raise FileNotFoundError(f'源数据库不存在：{source}')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.building')
    if temporary.exists():
        temporary.unlink()

    source_db = sqlite3.connect(source)
    target_db = sqlite3.connect(temporary)
    try:
        source_db.backup(target_db)
    finally:
        source_db.close()
        target_db.close()

    db = sqlite3.connect(temporary)
    try:
        actual = _tables(db)
        unknown = actual - PUBLIC_TABLES - PERSONAL_TABLES
        missing = (PUBLIC_TABLES | PERSONAL_TABLES) - actual
        if unknown or missing:
            raise RuntimeError(
                f'数据库隐私分类需要更新；未知表={sorted(unknown)}，缺失表={sorted(missing)}'
            )

        db.execute('PRAGMA foreign_keys=OFF')
        for table in sorted(PERSONAL_TABLES):
            db.execute(f'DELETE FROM "{table}"')

        # 仅发布内置 Skill，并清除用户为其追加的提示词和开关状态。
        db.execute('DELETE FROM site_skills WHERE COALESCE(is_builtin, 0)=0')
        db.execute(
            "UPDATE site_skills SET user_instructions='', enabled=1, updated_at=datetime('now','localtime')"
        )

        # 仅发布内置词书；“我的收藏”保留为空入口，不携带发布者收藏。
        custom_wordbooks = [
            row[0] for row in db.execute('SELECT id FROM wordbooks WHERE COALESCE(is_builtin,0)=0')
        ]
        if custom_wordbooks:
            marks = ','.join('?' for _ in custom_wordbooks)
            db.execute(f'DELETE FROM wordbook_words WHERE wordbook_id IN ({marks})', custom_wordbooks)
            db.execute(f'DELETE FROM wordbooks WHERE id IN ({marks})', custom_wordbooks)
        favorite = db.execute("SELECT id FROM wordbooks WHERE name='我的收藏' LIMIT 1").fetchone()
        if favorite:
            db.execute('DELETE FROM wordbook_words WHERE wordbook_id=?', (favorite[0],))

        # “已完成”属于发布者使用状态；发行库重新回到未读池。隔离/参考文章保持原状态。
        db.execute("UPDATE reading_articles SET inventory_status='available' WHERE inventory_status='completed'")
        db.execute("INSERT OR IGNORE INTO note_categories (id,parent_id,name,sort_order) VALUES (0,0,'未分类',-1)")

        for table in sorted(PERSONAL_TABLES):
            if table == 'note_categories':
                continue
            db.execute('DELETE FROM sqlite_sequence WHERE name=?', (table,))
        db.commit()
        db.execute('PRAGMA foreign_keys=ON')

        violations = db.execute('PRAGMA foreign_key_check').fetchall()
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
        if violations or integrity != 'ok':
            raise RuntimeError(f'种子库校验失败：foreign_keys={violations[:3]} integrity={integrity}')

        counts = {
            'words': db.execute('SELECT COUNT(*) FROM words').fetchone()[0],
            'reading_articles': db.execute('SELECT COUNT(*) FROM reading_articles').fetchone()[0],
            'personal_rows': sum(
                db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                for table in PERSONAL_TABLES if table != 'note_categories'
            ),
            'custom_skills': db.execute(
                'SELECT COUNT(*) FROM site_skills WHERE COALESCE(is_builtin,0)=0'
            ).fetchone()[0],
            'custom_wordbooks': db.execute(
                'SELECT COUNT(*) FROM wordbooks WHERE COALESCE(is_builtin,0)=0'
            ).fetchone()[0],
        }
        if any(counts[key] for key in ('personal_rows', 'custom_skills', 'custom_wordbooks')):
            raise RuntimeError(f'种子库仍含个人内容：{counts}')
        db.execute('VACUUM')
    except Exception:
        db.close()
        temporary.unlink(missing_ok=True)
        raise
    else:
        db.close()
        os.replace(temporary, output)
        return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('data/vocab.db'))
    parser.add_argument(
        '--output', type=Path,
        default=Path('resources/distribution/vocab.seed.db'),
    )
    args = parser.parse_args()
    counts = build_seed(args.source.resolve(), args.output.resolve())
    print('发行种子库已生成：' + str(args.output.resolve()))
    print('；'.join(f'{key}={value}' for key, value in counts.items()))
    return 0


if __name__ == '__main__':
    sys.exit(main())

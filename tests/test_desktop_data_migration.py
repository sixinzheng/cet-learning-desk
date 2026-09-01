import pathlib
import sqlite3
import tempfile
import unittest
from contextlib import closing

from scripts.migrate_desktop_user_data import migrate


TABLES = (
    'words', 'user_words', 'study_logs', 'notes', 'ai_conversations',
    'ai_messages', 'user_level', 'user_settings',
)


def create_database(path: pathlib.Path, marker: str) -> None:
    connection = sqlite3.connect(path)
    for table in TABLES:
        connection.execute(f'CREATE TABLE "{table}" (value TEXT)')
    connection.execute('INSERT INTO user_words(value) VALUES (?)', (marker,))
    connection.execute('INSERT INTO study_logs(value) VALUES (?)', (marker,))
    connection.commit()
    connection.close()


class DesktopDataMigrationTests(unittest.TestCase):
    def test_migration_replaces_target_only_after_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source = root / 'source.db'
            target = root / 'profile' / 'data' / 'vocab.db'
            target.parent.mkdir(parents=True)
            create_database(source, 'source-history')
            create_database(target, 'desktop-before-import')

            result = migrate(source, target)

            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['quick_check'], 'ok')
            backup = pathlib.Path(result['backup'])
            self.assertTrue(backup.is_file())
            with closing(sqlite3.connect(target)) as database:
                self.assertEqual(
                    database.execute('SELECT value FROM user_words').fetchone()[0],
                    'source-history',
                )
            with closing(sqlite3.connect(backup)) as database:
                self.assertEqual(
                    database.execute('SELECT value FROM user_words').fetchone()[0],
                    'desktop-before-import',
                )


if __name__ == '__main__':
    unittest.main()

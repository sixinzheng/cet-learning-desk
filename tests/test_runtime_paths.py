import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from runtime_paths import _install_seed


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RuntimePathTests(unittest.TestCase):
    def run_probe(self, env):
        result = subprocess.run(
            [sys.executable, '-c', 'import runtime_paths; print(runtime_paths.USER_DATA_DIR)'],
            cwd=ROOT,
            env={**os.environ, **env},
            check=True,
            capture_output=True,
            text=True,
        )
        return pathlib.Path(result.stdout.strip())

    def test_development_keeps_project_data_directory(self):
        path = self.run_probe({'CET_DESKTOP': '', 'CET_DATA_DIR': ''})
        self.assertEqual(path, ROOT / 'data')

    def test_desktop_uses_explicit_isolated_data_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / 'desktop-user-data'
            path = self.run_probe({'CET_DESKTOP': '1', 'CET_DATA_DIR': str(target)})
            self.assertEqual(path, target)

    @staticmethod
    def create_seed(path, value='clean-seed'):
        connection = sqlite3.connect(path)
        connection.execute('CREATE TABLE marker (value TEXT NOT NULL)')
        connection.execute('INSERT INTO marker (value) VALUES (?)', (value,))
        connection.commit()
        connection.close()

    @staticmethod
    def read_marker(path):
        connection = sqlite3.connect(path)
        try:
            return connection.execute('SELECT value FROM marker').fetchone()[0]
        finally:
            connection.close()

    def test_seed_install_writes_valid_database_without_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            seed = root / 'seed.db'
            target = root / 'vocab.db'
            self.create_seed(seed)
            _install_seed(str(seed), str(target))
            self.assertEqual(self.read_marker(target), 'clean-seed')
            self.assertFalse((root / 'vocab.db.installing').exists())

    def test_seed_install_recovers_invalid_interrupted_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            seed = root / 'seed.db'
            target = root / 'vocab.db'
            self.create_seed(seed)
            target.write_bytes(b'incomplete')
            (root / 'vocab.db.installing').write_text('interrupted', encoding='utf-8')
            _install_seed(str(seed), str(target))
            self.assertEqual(self.read_marker(target), 'clean-seed')
            self.assertFalse((root / 'vocab.db.installing').exists())

    def test_seed_install_keeps_valid_completed_copy_after_marker_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            seed = root / 'seed.db'
            target = root / 'vocab.db'
            self.create_seed(seed, 'new-seed')
            self.create_seed(target, 'already-complete')
            (root / 'vocab.db.installing').write_text('interrupted', encoding='utf-8')
            _install_seed(str(seed), str(target))
            self.assertEqual(self.read_marker(target), 'already-complete')
            self.assertFalse((root / 'vocab.db.installing').exists())


if __name__ == '__main__':
    unittest.main()

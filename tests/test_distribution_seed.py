import pathlib
import sqlite3
import tempfile
import unittest

from scripts.build_distribution_seed import PERSONAL_TABLES, build_seed


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DistributionSeedTests(unittest.TestCase):
    def test_seed_contains_content_but_no_personal_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / 'vocab.seed.db'
            counts = build_seed(ROOT / 'data' / 'vocab.db', output)
            self.assertGreater(counts['words'], 1000)
            self.assertEqual(counts['personal_rows'], 0)
            db = sqlite3.connect(output)
            try:
                for table in PERSONAL_TABLES - {'note_categories'}:
                    with self.subTest(table=table):
                        self.assertEqual(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0], 0)
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM note_categories WHERE id!=0").fetchone()[0],
                    0,
                )
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM site_skills WHERE is_builtin=0").fetchone()[0],
                    0,
                )
            finally:
                db.close()


if __name__ == '__main__':
    unittest.main()

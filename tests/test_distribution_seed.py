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
            # CI intentionally never receives data/vocab.db because that file is
            # the developer's private working database.  Exercise the sanitizer
            # against the checked-in, already-sanitized distribution source so
            # this release gate is reproducible on a clean checkout.
            counts = build_seed(
                ROOT / 'resources' / 'distribution' / 'vocab.seed.db',
                output,
            )
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
                hidden = db.execute(
                    "SELECT id,is_builtin,is_hidden FROM wordbooks WHERE name='阅读词汇缓存'"
                ).fetchone()
                self.assertIsNotNone(hidden)
                self.assertEqual(hidden[1:], (1, 1))
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) FROM wordbook_words WHERE wordbook_id=?", (hidden[0],)
                    ).fetchone()[0],
                    db.execute("SELECT COUNT(*) FROM words").fetchone()[0],
                )
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM words WHERE source='ai_reading'").fetchone()[0],
                    0,
                )
            finally:
                db.close()


if __name__ == '__main__':
    unittest.main()

import os
import tempfile
import unittest
from datetime import date as real_date, timedelta
from unittest import mock

import database
from app import create_app


class DashboardQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, 'test.db')
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()
        db = database.get_db()
        db.execute("INSERT INTO wordbooks (name,description,is_builtin) VALUES ('测试词书','',1)")
        self.book_id = db.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
        for index in range(14):
            db.execute("INSERT INTO words (word,meanings,frequency) VALUES (?, '[]', ?)", (f'alpha{index:02d}', 5))
            word_id = db.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
            db.execute('INSERT INTO wordbook_words (wordbook_id,word_id) VALUES (?,?)', (self.book_id, word_id))
        db.execute("INSERT OR REPLACE INTO user_settings (key,value) VALUES ('current_wordbook',?)", (str(self.book_id),))
        db.execute("INSERT OR REPLACE INTO user_settings (key,value) VALUES ('daily_count','10')")
        db.commit()
        self.word_ids = [row['id'] for row in db.execute('SELECT id FROM words ORDER BY id')]
        db.close()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_dashboard_counts_unstarted_and_stranger_words_as_available(self):
        db = database.get_db()
        for word_id in self.word_ids[:4]:
            db.execute("INSERT INTO user_words (word_id,status) VALUES (?, '陌生')", (word_id,))
        db.commit(); db.close()
        data = self.client.get('/api/study/dashboard').get_json()
        self.assertEqual(data['new_goal_remaining'], 10)
        self.assertEqual(data['new_available_count'], 14)
        self.assertEqual(data['new_task_remaining'], 10)
        self.assertEqual(data['today_new'], 10)

    def test_dashboard_reduces_task_only_after_words_graduate(self):
        db = database.get_db()
        db.execute(
            "INSERT INTO study_logs (study_date,new_words_count) VALUES (?,4)",
            (real_date.today().isoformat(),),
        )
        for word_id in self.word_ids[:4]:
            db.execute("INSERT INTO user_words (word_id,status) VALUES (?, '模糊')", (word_id,))
        db.commit(); db.close()
        data = self.client.get('/api/study/dashboard').get_json()
        self.assertEqual(data['new_goal_remaining'], 6)
        self.assertEqual(data['new_task_remaining'], 6)
        self.assertEqual(data['wordbook_unmastered_remaining'], 14)

    def test_new_word_order_is_stable_for_a_day_and_changes_next_day(self):
        first = self.client.get('/api/study/new-words?limit=10').get_json()['words']
        second = self.client.get('/api/study/new-words?limit=10').get_json()['words']
        self.assertEqual([item['id'] for item in first], [item['id'] for item in second])
        self.assertNotEqual([item['word'] for item in first], sorted(item['word'] for item in first))

        tomorrow = real_date.today() + timedelta(days=1)
        class Tomorrow(real_date):
            @classmethod
            def today(cls):
                return cls(tomorrow.year, tomorrow.month, tomorrow.day)
        with mock.patch('routes.api_study.date', Tomorrow):
            changed = self.client.get('/api/study/new-words?limit=10').get_json()['words']
        self.assertNotEqual([item['id'] for item in first], [item['id'] for item in changed])
        self.assertTrue(all(item['audio_url'].endswith('/audio') for item in first))

    def test_audio_endpoint_is_id_scoped_and_cacheable(self):
        word_id = self.word_ids[0]
        with mock.patch('routes.api_words.read_word_audio', return_value=(b'ID3mock', 'a' * 64)):
            response = self.client.get(f'/api/words/{word_id}/audio')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'audio/mpeg')
        self.assertIn('immutable', response.headers.get('Cache-Control', ''))
        with mock.patch('routes.api_words.read_word_audio', return_value=(b'ID3mock', 'a' * 64)):
            ranged = self.client.get(
                f'/api/words/{word_id}/audio', headers={'Range': 'bytes=0-2'}
            )
        self.assertEqual(ranged.status_code, 206)
        self.assertEqual(ranged.data, b'ID3')
        self.assertEqual(ranged.headers.get('Content-Range'), 'bytes 0-2/7')
        self.assertEqual(self.client.get('/api/words/999999/audio').status_code, 404)

    def test_fixed_listening_audio_is_id_scoped_and_cacheable(self):
        db = database.get_db()
        db.execute(
            "INSERT INTO sentences (word_id,sentence_type,content,translation) "
            "VALUES (?, 'example', 'A fixed sentence.', '固定例句。')",
            (self.word_ids[0],),
        )
        sentence_id = db.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
        db.commit(); db.close()
        with mock.patch('routes.api_practice.read_listening_audio', return_value=(b'ID3listen', 'b' * 64)):
            response = self.client.get(f'/api/practice/listening/sentences/{sentence_id}/audio')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'audio/mpeg')
        self.assertIn('immutable', response.headers.get('Cache-Control', ''))
        with mock.patch('routes.api_practice.read_listening_audio', return_value=(b'ID3listen', 'b' * 64)):
            ranged = self.client.get(
                f'/api/practice/listening/sentences/{sentence_id}/audio',
                headers={'Range': 'bytes=0-2'},
            )
        self.assertEqual(ranged.status_code, 206)
        self.assertEqual(ranged.data, b'ID3')
        self.assertEqual(
            self.client.get('/api/practice/listening/sentences/999999/audio').status_code,
            404,
        )


if __name__ == '__main__':
    unittest.main()

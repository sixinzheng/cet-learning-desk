from database import get_db
from services.device_sync_data import clear_tombstone, record_tombstone


class Word:
    @staticmethod
    def get_by_id(word_id):
        db = get_db()
        return db.execute("SELECT * FROM words WHERE id=?", (word_id,)).fetchone()

    @staticmethod
    def search(query, limit=20):
        db = get_db()
        return db.execute(
            "SELECT * FROM words WHERE word LIKE ? LIMIT ?",
            (f"%{query}%", limit)
        ).fetchall()

    @staticmethod
    def list_by_wordbook(wordbook_id, offset=0, limit=50):
        db = get_db()
        rows = db.execute('''
            SELECT w.*, uw.status, uw.review_count, uw.correct_count,
                   uw.next_review, uw.ebbinghaus_stage, uw.consecutive_correct
            FROM words w
            JOIN wordbook_words wbw ON w.id = wbw.word_id
            LEFT JOIN user_words uw ON w.id = uw.word_id
            WHERE wbw.wordbook_id = ?
            ORDER BY w.frequency DESC
            LIMIT ? OFFSET ?
        ''', (wordbook_id, limit, offset)).fetchall()
        db.close()
        return rows

    @staticmethod
    def get_sentences(word_id):
        db = get_db()
        return db.execute(
            "SELECT * FROM sentences WHERE word_id=? ORDER BY sentence_type",
            (word_id,)
        ).fetchall()

    @staticmethod
    def _word_variants(word):
        """生成目标词的常见词形变化（含规则变化与常见不规则过去式），用于例句挖空。"""
        import re
        w = word.lower()
        variants = {w}
        # 规则变化：第三人称单数 / 过去式 / 现在分词
        if w.endswith('e'):
            variants.update({w + 's', w + 'd', w[:-1] + 'ing'})
        else:
            variants.update({w + 's', w + 'es', w + 'ed', w + 'ing'})
        # 常见不规则过去式/过去分词（覆盖高频动词，避免例句泄露答案）
        irregular = {
            'sweep': {'swept'}, 'sleep': {'slept'}, 'keep': {'kept'}, 'feel': {'felt'},
            'deal': {'dealt'}, 'mean': {'meant'}, 'lead': {'led'}, 'read': {'read'},
            'rise': {'rose', 'risen'}, 'write': {'wrote', 'written'}, 'drive': {'drove', 'driven'},
            'take': {'took', 'taken'}, 'give': {'gave', 'given'}, 'see': {'saw', 'seen'},
            'go': {'went', 'gone'}, 'do': {'did', 'done'}, 'have': {'had'},
            'make': {'made'}, 'come': {'came'}, 'become': {'became'}, 'think': {'thought'},
            'buy': {'bought'}, 'bring': {'brought'}, 'catch': {'caught'}, 'teach': {'taught'},
            'build': {'built'}, 'send': {'sent'}, 'spend': {'spent'}, 'lend': {'lent'},
            'meet': {'met'}, 'get': {'got', 'gotten'}, 'forget': {'forgot', 'forgotten'},
            'sit': {'sat'}, 'win': {'won'}, 'run': {'ran'}, 'swim': {'swam'},
            'sing': {'sang', 'sung'}, 'begin': {'began', 'begun'}, 'drink': {'drank', 'drunk'},
            'know': {'knew', 'known'}, 'throw': {'threw', 'thrown'}, 'draw': {'drew', 'drawn'},
            'fly': {'flew', 'flown'}, 'grow': {'grew', 'grown'}, 'blow': {'blew', 'blown'},
            'break': {'broke', 'broken'}, 'speak': {'spoke', 'spoken'}, 'steal': {'stole', 'stolen'},
            'choose': {'chose', 'chosen'}, 'freeze': {'froze', 'frozen'}, 'wake': {'woke', 'woken'},
            'bear': {'bore', 'born', 'borne'}, 'tear': {'tore', 'torn'}, 'wear': {'wore', 'worn'},
            'swear': {'swore', 'sworn'}, 'fall': {'fell', 'fallen'}, 'eat': {'ate', 'eaten'},
            'bite': {'bit', 'bitten'}, 'hide': {'hid', 'hidden'}, 'ride': {'rode', 'ridden'},
            'lie': {'lay', 'lain'}, 'lay': {'laid'}, 'pay': {'paid'}, 'say': {'said'},
            'find': {'found'}, 'bind': {'bound'}, 'wind': {'wound'}, 'stand': {'stood'},
            'understand': {'understood'}, 'hold': {'held'}, 'sell': {'sold'}, 'tell': {'told'},
            'fight': {'fought'}, 'seek': {'sought'}, 'stick': {'stuck'}, 'strike': {'struck'},
            'dig': {'dug'}, 'hang': {'hung'}, 'shine': {'shone'}, 'shoot': {'shot'},
            'slide': {'slid'}, 'smell': {'smelt', 'smelled'}, 'spell': {'spelt', 'spelled'},
            'burn': {'burnt', 'burned'}, 'learn': {'learnt', 'learned'}, 'dream': {'dreamt', 'dreamed'},
        }
        variants.update(irregular.get(w, set()))
        # 句首大写形式
        variants.update(v.capitalize() for v in list(variants))
        return sorted(variants, key=len, reverse=True)

    @staticmethod
    def _blank_variants(text, word):
        """把句子中目标词的所有词形变化挖空为 ____（避免例句泄露答案）。"""
        import re
        variants = Word._word_variants(word)
        pattern = re.compile(r'\b(?:' + '|'.join(re.escape(v) for v in variants) + r')\b')
        return pattern.sub('____', text)

    @staticmethod
    def pick_spelling_example(word, sentences):
        """挑选适合拼写验证的干净例句：完整句优先、过滤不雅短语、挖空词形变化。

        返回 {'en': 挖空后英文, 'zh': 中文, 'source': 来源} 或 None。
        """
        import re
        bad_keywords = ('sexual', 'sex ', 'orgasm', 'penis', 'vagina', 'breast', 'naked', 'porn')
        seen = set()
        candidates = []
        for s in sentences or []:
            content = (s['content'] or '').strip()
            if not content or content in seen:
                continue
            seen.add(content)
            lower = content.lower()
            # 过滤：不雅关键词 / 过短的短语（无空格=单词短语）
            if any(b in lower for b in bad_keywords):
                continue
            if ' ' not in content or len(content) < 12:
                continue
            candidates.append(s)
        # 优先更长更完整的句子
        candidates.sort(key=lambda s: len(s['content'] or ''), reverse=True)
        for s in candidates:
            blanked = Word._blank_variants(s['content'], word)
            if '____' in blanked:
                return {
                    'en': blanked,
                    'full': s['content'],
                    'zh': s['translation'] or '',
                    'source': s['source_info'] or '',
                }
        return None

    @staticmethod
    def get_linked_words(word_id):
        """获取与该单词相关的标签组"""
        db = get_db()
        links = db.execute(
            "SELECT * FROM word_links WHERE word_ids LIKE ?",
            (f'%{word_id}%',)
        ).fetchall()
        result = []
        import json
        for link in links:
            try:
                ids = json.loads(link['word_ids'])
            except:
                ids = []
            tag_words = []
            for wid in ids:
                if wid == word_id:
                    continue
                w = db.execute("SELECT id, word, phonetic, part_of_speech, meanings FROM words WHERE id=?", (wid,)).fetchone()
                if w:
                    uw = db.execute("SELECT status FROM user_words WHERE word_id=?", (wid,)).fetchone()
                    tag_words.append({
                        'id': w['id'], 'word': w['word'],
                        'phonetic': w['phonetic'],
                        'part_of_speech': w['part_of_speech'],
                        'meanings': w['meanings'],
                        'status': uw['status'] if uw else '陌生',
                    })
            result.append({
                'tag_id': link['id'],
                'tag_name': link['tag_name'],
                'words': tag_words,
            })
        return result

    @staticmethod
    def get_detail(word_id):
        """获取单词完整信息（含例句、状态、关联标签）"""
        w = Word.get_by_id(word_id)
        if not w:
            return None
        db = get_db()
        uw = db.execute("SELECT * FROM user_words WHERE word_id=?", (word_id,)).fetchone()
        sentences = Word.get_sentences(word_id)
        links = Word.get_linked_words(word_id)
        return {
            'id': w['id'],
            'word': w['word'],
            'phonetic': w['phonetic'],
            'part_of_speech': w['part_of_speech'],
            'meanings': w['meanings'],
            'audio_file': w['audio_file'],
            'source': w['source'],
            'frequency': w['frequency'],
            'status': uw['status'] if uw else '陌生',
            'review_count': uw['review_count'] if uw else 0,
            'correct_count': uw['correct_count'] if uw else 0,
            'consecutive_correct': uw['consecutive_correct'] if uw else 0,
            'next_review': uw['next_review'] if uw else None,
            'ebbinghaus_stage': uw['ebbinghaus_stage'] if uw else 0,
            'sentences': [{
                'id': s['id'], 'type': s['sentence_type'],
                'content': s['content'], 'translation': s['translation'],
                'source': s['source_info'],
            } for s in sentences],
            # 干净拼写例句：完整句优先 + 挖空词形变化（避免不雅例句/泄露答案）
            'spelling_example': Word.pick_spelling_example(w['word'], sentences),
            'links': links,
            'is_favorite': Word.is_favorite(word_id),
        }

    @staticmethod
    def get_wordbooks():
        db = get_db()
        rows = db.execute(
            "SELECT * FROM wordbooks WHERE COALESCE(is_hidden,0)=0 "
            "ORDER BY is_builtin DESC, id"
        ).fetchall()
        db.close()
        return rows

    @staticmethod
    def create_wordbook(name, description=''):
        db = get_db()
        cur = db.execute(
            "INSERT INTO wordbooks (name, description) VALUES (?,?)",
            (name, description)
        )
        db.commit()
        wordbook_id = cur.lastrowid
        db.close()
        return wordbook_id

    @staticmethod
    def get_favorite_book():
        """定位内置「我的收藏」词库（不存在则自动创建），返回 id。"""
        db = get_db()
        row = db.execute(
            "SELECT id FROM wordbooks WHERE name='我的收藏' AND COALESCE(is_hidden,0)=0 LIMIT 1"
        ).fetchone()
        if row:
            favorite_id = row['id']
            db.close()
            return favorite_id
        cur = db.execute(
            "INSERT INTO wordbooks (name, description, is_builtin, is_hidden) VALUES ('我的收藏', '收藏的单词自动收进这里', 1, 0)"
        )
        db.commit()
        favorite_id = cur.lastrowid
        db.close()
        return favorite_id

    @staticmethod
    def is_favorite(word_id):
        """判断单词是否已收藏。"""
        db = get_db()
        fav = Word.get_favorite_book()
        row = db.execute(
            "SELECT 1 FROM wordbook_words WHERE wordbook_id=? AND word_id=?",
            (fav, word_id)
        ).fetchone()
        db.close()
        return bool(row)

    @staticmethod
    def toggle_favorite(word_id):
        """切换收藏状态：已收藏则移除，未收藏则加入「我的收藏」。返回 (is_favorite, book_id)。"""
        db = get_db()
        fav = Word.get_favorite_book()
        exists = db.execute(
            "SELECT 1 FROM wordbook_words WHERE wordbook_id=? AND word_id=?",
            (fav, word_id)
        ).fetchone()
        word_row = db.execute("SELECT word FROM words WHERE id=?", (word_id,)).fetchone()
        word_key = str(word_row['word']).strip().lower() if word_row else ''
        if exists:
            db.execute("DELETE FROM wordbook_words WHERE wordbook_id=? AND word_id=?", (fav, word_id))
            if word_key:
                record_tombstone('favorite', 'favorite:' + word_key, db=db)
            db.commit()
            db.close()
            return False, fav
        # 确保词存在
        w = db.execute("SELECT id FROM words WHERE id=?", (word_id,)).fetchone()
        if not w:
            db.close()
            return None, fav
        db.execute(
            "INSERT OR IGNORE INTO wordbook_words (wordbook_id, word_id) VALUES (?,?)",
            (fav, word_id)
        )
        if word_key:
            clear_tombstone('favorite', 'favorite:' + word_key, db=db)
        db.commit()
        db.close()
        return True, fav

    @staticmethod
    def add_word_to_book(wordbook_id, word_id):
        db = get_db()
        try:
            db.execute("INSERT INTO wordbook_words (wordbook_id, word_id) VALUES (?,?)",
                       (wordbook_id, word_id))
            db.commit()
            return True
        except:
            return False
        finally:
            db.close()

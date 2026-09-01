"""阅读页词汇解析、词形回退与按单词缓存的 AI 补充。"""

from __future__ import annotations

import json
import re
import threading

from database import get_db
from services.ai_service import AIServiceError, call_deepseek


PROMPT_VERSION = 'reading-word-v1'
MASTERED_STATUSES = {'巩固', '掌握', '熟记'}
WORD_PATTERN = re.compile(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*")
PART_PATTERN = re.compile(r"^([^A-Za-z]*)([A-Za-z]+(?:['’\-][A-Za-z]+)*)([^A-Za-z]*)$")
_ENRICH_LOCK = threading.RLock()

_IRREGULAR_BASES = {
    'went': 'go', 'gone': 'go', 'did': 'do', 'done': 'do', 'had': 'have',
    'made': 'make', 'came': 'come', 'became': 'become', 'thought': 'think',
    'bought': 'buy', 'brought': 'bring', 'caught': 'catch', 'taught': 'teach',
    'built': 'build', 'sent': 'send', 'spent': 'spend', 'met': 'meet',
    'got': 'get', 'gotten': 'get', 'forgot': 'forget', 'forgotten': 'forget',
    'sat': 'sit', 'won': 'win', 'ran': 'run', 'swam': 'swim', 'sang': 'sing',
    'sung': 'sing', 'began': 'begin', 'begun': 'begin', 'drank': 'drink',
    'drunk': 'drink', 'knew': 'know', 'known': 'know', 'wrote': 'write',
    'written': 'write', 'took': 'take', 'taken': 'take', 'gave': 'give',
    'given': 'give', 'saw': 'see', 'seen': 'see', 'rose': 'rise', 'risen': 'rise',
    'led': 'lead', 'read': 'read', 'slept': 'sleep', 'kept': 'keep',
    'felt': 'feel', 'meant': 'mean', 'dealt': 'deal', 'stood': 'stand',
    'understood': 'understand', 'held': 'hold', 'sold': 'sell', 'told': 'tell',
}


def normalize_word(value):
    match = WORD_PATTERN.search(str(value or '').replace('’', "'"))
    return match.group(0).lower() if match else ''


def _candidate_headwords(surface):
    word = normalize_word(surface)
    candidates = [word]
    irregular = _IRREGULAR_BASES.get(word)
    if irregular:
        candidates.append(irregular)
    if len(word) > 4 and word.endswith('ies'):
        candidates.append(word[:-3] + 'y')
    if len(word) > 4 and word.endswith('ied'):
        candidates.append(word[:-3] + 'y')
    if len(word) > 5 and word.endswith('ing'):
        stem = word[:-3]
        candidates.extend([stem, stem + 'e'])
        if len(stem) > 2 and stem[-1] == stem[-2]:
            candidates.append(stem[:-1])
    if len(word) > 4 and word.endswith('ed'):
        stem = word[:-2]
        candidates.extend([stem, word[:-1]])
        if len(stem) > 2 and stem[-1] == stem[-2]:
            candidates.append(stem[:-1])
    if len(word) > 4 and word.endswith('es'):
        candidates.extend([word[:-2], word[:-1]])
    elif len(word) > 3 and word.endswith('s'):
        candidates.append(word[:-1])
    result = []
    for candidate in candidates:
        if candidate and candidate not in result:
            result.append(candidate)
    return result


def _find_word(db, surface):
    normalized = normalize_word(surface)
    for index, candidate in enumerate(_candidate_headwords(normalized)):
        row = db.execute(
            "SELECT * FROM words WHERE word=? COLLATE NOCASE LIMIT 1", (candidate,)
        ).fetchone()
        if row:
            return row, ('exact' if index == 0 else 'inflection')
    alias = db.execute(
        "SELECT w.* FROM word_ai_details d JOIN words w ON w.id=d.word_id "
        "WHERE d.surface_form=? COLLATE NOCASE LIMIT 1",
        (normalized,),
    ).fetchone()
    if alias:
        return alias, 'ai_alias'
    return None, 'missing'


def _article_tokens(content):
    """复刻前端既有 widx 规则，确保旧标注位置不漂移。"""
    word_index = 0
    token_index = 0
    offset = 0
    occurrences = {}
    tokens = []
    for part in re.split(r'(\s+)', str(content or '')):
        start = offset
        offset += len(part)
        if not part or part.isspace():
            continue
        token = token_index
        token_index += 1
        match = PART_PATTERN.match(part)
        if not match:
            continue
        prefix, surface, suffix = match.groups()
        normalized = normalize_word(surface)
        occurrence = occurrences.get(normalized, 0)
        occurrences[normalized] = occurrence + 1
        widx = 100000 + token if prefix or suffix else word_index
        if not prefix and not suffix:
            word_index += 1
        tokens.append({
            'surface': surface, 'normalized': normalized, 'widx': widx,
            'occurrence': occurrence, 'start': start + len(prefix),
            'end': start + len(prefix) + len(surface),
        })
    return tokens


def _favorite_book_id(db):
    row = db.execute(
        "SELECT id FROM wordbooks WHERE name='我的收藏' AND COALESCE(is_hidden,0)=0 LIMIT 1"
    ).fetchone()
    return int(row['id']) if row else None


def _load_ai_detail(db, word_id):
    row = db.execute("SELECT * FROM word_ai_details WHERE word_id=?", (word_id,)).fetchone()
    if not row:
        return None
    try:
        detail = json.loads(row['detail_json'] or '{}')
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(detail, dict):
        return None
    detail['generated_at'] = row['generated_at']
    detail['updated_at'] = row['updated_at']
    detail['model'] = row['model']
    detail['prompt_version'] = row['prompt_version']
    detail['context_excerpt'] = row['context_excerpt']
    return detail


def _word_payload(db, row, match_type, surface):
    if not row:
        return {
            'found': False, 'word': normalize_word(surface), 'surface_form': str(surface or ''),
            'match_type': 'missing', 'status': '未收录', 'is_mastered': False,
            'is_favorite': False, 'ai_detail': None, 'can_enrich': True,
        }
    user = db.execute("SELECT status FROM user_words WHERE word_id=?", (row['id'],)).fetchone()
    favorite_id = _favorite_book_id(db)
    favorite = bool(favorite_id and db.execute(
        "SELECT 1 FROM wordbook_words WHERE wordbook_id=? AND word_id=?",
        (favorite_id, row['id']),
    ).fetchone())
    status = (user['status'] if user else '') or '陌生'
    try:
        meanings = json.loads(row['meanings'] or '[]')
    except (TypeError, json.JSONDecodeError):
        meanings = [str(row['meanings'] or '')]
    return {
        'found': True, 'id': int(row['id']), 'word': row['word'],
        'surface_form': str(surface or row['word']), 'phonetic': row['phonetic'] or '',
        'part_of_speech': row['part_of_speech'] or '', 'meanings': meanings,
        'frequency': int(row['frequency'] or 0), 'match_type': match_type,
        'status': status, 'is_mastered': status in MASTERED_STATUSES,
        'is_favorite': favorite, 'ai_detail': _load_ai_detail(db, row['id']),
        'can_enrich': True,
    }


def lookup_word(surface):
    db = get_db()
    try:
        row, match_type = _find_word(db, surface)
        return _word_payload(db, row, match_type, surface)
    finally:
        db.close()


def article_vocabulary(article):
    db = get_db()
    try:
        groups = {}
        for token in _article_tokens(article['content']):
            if len(token['normalized']) <= 2:
                continue
            row, match_type = _find_word(db, token['normalized'])
            key = f"word:{row['id']}" if row else f"missing:{token['normalized']}"
            if key not in groups:
                payload = _word_payload(db, row, match_type, token['surface'])
                groups[key] = {
                    **payload,
                    'display_word': token['normalized'],
                    'headword': row['word'] if row else token['normalized'],
                    'positions': [], 'forms': [],
                }
            group = groups[key]
            group['positions'].append(token['widx'])
            if token['normalized'] not in group['forms']:
                group['forms'].append(token['normalized'])
        words = list(groups.values())
        order = {'未收录': 0, '陌生': 1, '模糊': 2, '巩固': 3, '掌握': 4, '熟记': 5}
        words.sort(key=lambda item: (order.get(item['status'], 9), item['display_word']))
        mastered = sum(1 for item in words if item['is_mastered'])
        total = len(words)
        return {
            'mastered': mastered, 'total_vocab': total,
            'percentage': round(mastered / total * 100) if total else 0,
            'words': words,
        }
    finally:
        db.close()


def _context_excerpt(content, surface, occurrence):
    normalized = normalize_word(surface)
    matches = [token for token in _article_tokens(content) if token['normalized'] == normalized]
    selected = next((token for token in matches if token['occurrence'] == occurrence), None)
    if not selected:
        selected = matches[0] if matches else None
    if not selected:
        return str(content or '')[:400].strip()
    text = str(content or '')
    left_candidates = [text.rfind(mark, 0, selected['start']) for mark in ('.', '!', '?', '\n')]
    left = max(left_candidates) + 1
    right_candidates = [text.find(mark, selected['end']) for mark in ('.', '!', '?', '\n')]
    right_candidates = [value for value in right_candidates if value >= 0]
    right = min(right_candidates) + 1 if right_candidates else min(len(text), selected['end'] + 240)
    excerpt = text[left:right].strip()
    return excerpt[:500] or text[max(0, selected['start'] - 160):selected['end'] + 240].strip()[:500]


def _clean_text(value, field, maximum, required=True):
    text = str(value or '').strip()
    if required and not text:
        raise AIServiceError(f'AI 返回的 {field} 为空。', 'invalid_word_enrichment', 502)
    if len(text) > maximum:
        raise AIServiceError(f'AI 返回的 {field} 过长。', 'invalid_word_enrichment', 502)
    return text


def _validate_detail(raw, requested_word):
    if not isinstance(raw, dict):
        raise AIServiceError('AI 未返回有效的单词详情。', 'invalid_word_enrichment', 502)
    headword = normalize_word(raw.get('headword'))
    if not headword:
        raise AIServiceError('AI 未返回有效词头。', 'invalid_word_enrichment', 502)
    additional = raw.get('additional_meanings') or []
    if not isinstance(additional, list) or len(additional) > 5:
        raise AIServiceError('AI 返回的补充词义格式无效。', 'invalid_word_enrichment', 502)
    additional = [_clean_text(item, '补充词义', 160) for item in additional]

    def example(name):
        value = raw.get(name)
        if not isinstance(value, dict):
            raise AIServiceError('AI 返回的例句格式无效。', 'invalid_word_enrichment', 502)
        result = {
            'en': _clean_text(value.get('en'), '英文例句', 320),
            'zh': _clean_text(value.get('zh'), '例句翻译', 320),
        }
        if name == 'other_example':
            result['meaning'] = _clean_text(value.get('meaning'), '例句词义', 160)
        return result

    context_example = example('context_example')
    other_example = example('other_example')
    expected = {normalize_word(requested_word), headword}
    if not any(re.search(rf"\b{re.escape(word)}\b", context_example['en'], re.I) for word in expected if word):
        raise AIServiceError('AI 语境例句没有包含目标词。', 'invalid_word_enrichment', 502)
    return {
        'headword': headword,
        'phonetic': _clean_text(raw.get('phonetic'), '音标', 80, required=False),
        'part_of_speech': _clean_text(raw.get('part_of_speech'), '词性', 80),
        'context_meaning': _clean_text(raw.get('context_meaning'), '语境词义', 240),
        'additional_meanings': additional,
        'context_example': context_example,
        'other_example': other_example,
        'form_note': _clean_text(raw.get('form_note'), '词形说明', 240, required=False),
    }


def _parse_ai_content(content, requested_word):
    text = str(content or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.I | re.S).strip()
    try:
        raw = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise AIServiceError('AI 未返回可解析的单词详情。', 'invalid_word_enrichment', 502) from exc
    return _validate_detail(raw, requested_word)


def _hidden_book_id(db):
    row = db.execute("SELECT id FROM wordbooks WHERE COALESCE(is_hidden,0)=1 ORDER BY id LIMIT 1").fetchone()
    if row:
        return int(row['id'])
    return int(db.execute(
        "INSERT INTO wordbooks (name,description,is_builtin,is_hidden) "
        "VALUES ('阅读词汇缓存','阅读查词与 AI 补充使用的内部全量词库',1,1)"
    ).lastrowid)


def enrich_word(*, article_id, surface_word, occurrence=0, refresh=False):
    normalized = normalize_word(surface_word)
    if not normalized or len(normalized) > 80:
        raise ValueError('单词格式无效。')
    try:
        article_id = int(article_id)
        occurrence = max(0, int(occurrence or 0))
    except (TypeError, ValueError) as exc:
        raise ValueError('文章或词语位置无效。') from exc

    with _ENRICH_LOCK:
        db = get_db()
        try:
            article = db.execute(
                "SELECT id,title,content FROM reading_articles WHERE id=?", (article_id,)
            ).fetchone()
            if not article:
                raise LookupError('文章不存在。')
            occurrences = [
                token for token in _article_tokens(article['content'])
                if token['normalized'] == normalized
            ]
            if not occurrences or occurrence >= len(occurrences):
                raise ValueError('这个词或出现位置不属于当前文章。')
            row, match_type = _find_word(db, normalized)
            if row and not refresh:
                cached = _load_ai_detail(db, row['id'])
                if cached:
                    return {**_word_payload(db, row, match_type, surface_word), 'cached': True}
            core_meanings = []
            if row:
                try:
                    core_meanings = json.loads(row['meanings'] or '[]')
                except (TypeError, json.JSONDecodeError):
                    core_meanings = [str(row['meanings'] or '')]
            excerpt = _context_excerpt(article['content'], normalized, occurrence)
        finally:
            db.close()

        prompt = f'''请为阅读中的英语词汇生成严谨的中文学习详情。
文中词形：{normalized}
已有词头：{row['word'] if row else '未收录'}
已有可信释义：{json.dumps(core_meanings, ensure_ascii=False)}
文章标题：{article['title']}
当前语境：{excerpt}

要求：
1. 判断标准词头和词性，解释当前语境中的准确含义。
2. additional_meanings 最多 5 条，只写其他常见中文词义，不重复当前词义。
3. context_example 新写一条与当前语境同义的英文例句及中文翻译。
4. other_example 用另一个常见词义新写英文例句、中文翻译，并注明该词义。
5. form_note 简述文中词形与词头的关系；若相同可为空。
6. 不声称例句来自真题、媒体或本文。

只返回 JSON：{{"headword":"","phonetic":"","part_of_speech":"","context_meaning":"","additional_meanings":[""],"context_example":{{"en":"","zh":""}},"other_example":{{"meaning":"","en":"","zh":""}},"form_note":""}}'''
        result = call_deepseek(
            [
                {'role': 'system', 'content': '你是严谨的四六级词汇教师，只输出合法 JSON。'},
                {'role': 'user', 'content': prompt},
            ],
            feature='word_enrichment', temperature=0.25, max_tokens=900,
            metadata={'article_id': article_id, 'word': normalized, 'refresh': bool(refresh)},
        )
        detail = _parse_ai_content(result.get('content'), normalized)

        db = get_db()
        try:
            db.execute('BEGIN IMMEDIATE')
            row, match_type = _find_word(db, normalized)
            if not row:
                row = db.execute(
                    "SELECT * FROM words WHERE word=? COLLATE NOCASE LIMIT 1",
                    (detail['headword'],),
                ).fetchone()
            if not row:
                meanings = [detail['context_meaning'], *detail['additional_meanings']]
                word_id = db.execute(
                    "INSERT INTO words (word,phonetic,part_of_speech,meanings,source,frequency) "
                    "VALUES (?,?,?,?,?,1)",
                    (detail['headword'], detail['phonetic'], detail['part_of_speech'],
                     json.dumps(meanings, ensure_ascii=False), 'ai_reading'),
                ).lastrowid
                row = db.execute("SELECT * FROM words WHERE id=?", (word_id,)).fetchone()
                match_type = 'ai_generated'
            hidden_id = _hidden_book_id(db)
            db.execute(
                "INSERT OR IGNORE INTO wordbook_words (wordbook_id,word_id) VALUES (?,?)",
                (hidden_id, row['id']),
            )
            db.execute(
                """INSERT INTO word_ai_details
                   (word_id,surface_form,article_id,context_excerpt,detail_json,model,prompt_version)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(word_id) DO UPDATE SET
                       surface_form=excluded.surface_form,article_id=excluded.article_id,
                       context_excerpt=excluded.context_excerpt,detail_json=excluded.detail_json,
                       model=excluded.model,prompt_version=excluded.prompt_version,
                       updated_at=datetime('now','localtime')""",
                (row['id'], normalized, article_id, excerpt,
                 json.dumps(detail, ensure_ascii=False), result.get('model', ''), PROMPT_VERSION),
            )
            db.commit()
            payload = _word_payload(db, row, match_type, surface_word)
            return {**payload, 'cached': False}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

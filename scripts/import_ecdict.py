"""ECDICT + Level8 词库导入脚本（六本词书）

数据源：
- 四级 / 六级：skywind3000/ECDICT 的 ecdict.csv，按 tag 含 cet4 / cet6 过滤
  （tag 无 tem8，专八改由下方 Level8 数据源提供）
- 专八：ALILIYES/English-word-dataset-and-reptile 的 Level8 JSONL
  （12,881 词，含音标/中文释义/例句；音标与词频回查 ECDICT 补齐）

产出：替换旧的 2 本种子词书，新建 6 本词书：
    四级/六级/专八 各分为「高频词库」（frq 前 40%）+「完整词库」。
words 表与 user_words 学习进度不受影响（词按 word 去重保留）。

用法： python scripts/import_ecdict.py
     可重复执行（幂等：managed 词书成员先清后写；已存在词用 INSERT OR IGNORE 保留）。
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import urllib3

from database import get_db, BASE_DIR

urllib3.disable_warnings()

DATA_DIR = os.path.join(BASE_DIR, 'data', 'ecdict')
CSV_PATH = os.path.join(DATA_DIR, 'ecdict.csv')
TEM8_FILES = ['Level8_1.json', 'Level8luan_2.json.wydl']

CSV_SOURCES = [
    'https://ghproxy.net/https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv',
    'https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv',
]
TEM8_BASE = 'https://ghproxy.net/https://raw.githubusercontent.com/ALILIYES/English-word-dataset-and-reptile/master/专四专八词汇/'

HIGH_FREQ_RATIO = 0.40   # 高频词库 = 该级 frq 最靠前的前 40%

# 词书名 → (考试级别 key, 描述)
BOOKS = [
    ('四级高频词库', 'cet4', 'CET-4 核心高频词汇（ECDICT，词频前 40%）'),
    ('四级完整词库', 'cet4', 'CET-4 大纲词汇全集（ECDICT）'),
    ('六级高频词库', 'cet6', 'CET-6 核心高频词汇（ECDICT，词频前 40%）'),
    ('六级完整词库', 'cet6', 'CET-6 大纲词汇全集（ECDICT）'),
    ('专八高频词库', 'tem8', 'TEM-8 核心高频词汇（Level8 词表，词频前 40%）'),
    ('专八完整词库', 'tem8', 'TEM-8 大纲词汇全集（Level8 词表）'),
]

_POS_PREFIX = re.compile(r'^[a-z]{1,6}\.\s*')


def ensure_download():
    """下载缺失的数据文件（公开词典数据，本脚本按需使用 verify=False）。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not (os.path.exists(CSV_PATH) and os.path.getsize(CSV_PATH) > 20_000_000):
        last_err = None
        for url in CSV_SOURCES:
            try:
                r = requests.get(url, stream=True, timeout=120, verify=False)
                r.raise_for_status()
                with open(CSV_PATH, 'wb') as f:
                    for chunk in r.iter_content(1024 * 512):
                        f.write(chunk)
                print(f'[下载] ecdict.csv {os.path.getsize(CSV_PATH)} bytes')
                break
            except Exception as exc:
                last_err = exc
                print(f'  ! {url[:60]} 失败: {exc}')
        else:
            raise RuntimeError(f'ecdict.csv 下载失败: {last_err}')
    for fn in TEM8_FILES:
        path = os.path.join(DATA_DIR, fn)
        if not os.path.exists(path):
            r = requests.get(TEM8_BASE + fn, timeout=120, verify=False)
            r.raise_for_status()
            with open(path, 'wb') as f:
                f.write(r.content)
            print(f'[下载] {fn} {len(r.content)} bytes')


def load_tem8():
    """解析 Level8 JSONL → [(word, phonetic, meanings(list), pos, sentences)]"""
    out = []
    for fn in TEM8_FILES:
        path = os.path.join(DATA_DIR, fn)
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                hw = d.get('headWord', '').strip().lower()
                if not hw:
                    continue
                c = (d.get('content') or {}).get('word') or {}
                body = (c.get('content') or {})
                trans = body.get('trans') or []
                meanings = [t.get('tranCn', '').strip() for t in trans if t.get('tranCn')]
                pos = [t.get('pos', '') for t in trans if t.get('pos')]
                sentences = []
                for s in (body.get('sentence') or {}).get('sentences') or []:
                    en = (s.get('sContent') or '').strip()
                    zh = (s.get('sCn') or '').strip()
                    if en:
                        sentences.append((en, zh))
                if meanings or sentences:
                    out.append({
                        'word': hw,
                        'phonetic': (body.get('usphone') or body.get('ukphone') or '').strip(),
                        'meanings': meanings,
                        'pos': '/'.join(dict.fromkeys(p for p in pos if p)),
                        'sentences': sentences,
                    })
    return out


def _parse_meanings(translation):
    """ECDICT translation → 中文释义列表（按行拆分，去掉行首词性前缀）"""
    out = []
    for line in (translation or '').replace('\r', '').split('\n'):
        line = line.strip()
        if not line:
            continue
        line = _POS_PREFIX.sub('', line).strip()
        if line:
            out.append(line)
    return out


def _stars_by_frq(ordered):
    """按 frq 升序（越前越常用）的单词列表 → {word: 1..5 星级}"""
    stars = {}
    n = len(ordered)
    for idx, word in enumerate(ordered):
        pct = idx / n if n else 0
        stars[word] = max(1, 5 - int(pct * 5))
    return stars


def main():
    ensure_download()

    # 1) 读专八词表
    tem8 = load_tem8()
    tem8_by_word = {w['word']: w for w in tem8}
    print(f'[专八] {len(tem8)} 词')

    # 2) 单遍扫 ecdict.csv，只留需要的词（cet4/cet6 全集 + tem8 词表交集，用于补音标/词频）
    needed = set(tem8_by_word.keys())
    cet4_words, cet6_words = set(), set()
    rows = {}
    with open(CSV_PATH, encoding='utf-8-sig', errors='replace', newline='') as f:
        rd = csv.reader(f)
        next(rd)  # header
        for row in rd:
            if len(row) < 10:
                continue
            word = row[0].strip().lower()
            if not word:
                continue
            tags = row[7].split()
            if 'cet4' in tags:
                cet4_words.add(word)
            if 'cet6' in tags:
                cet6_words.add(word)
            if word in needed or 'cet4' in tags or 'cet6' in tags:
                rows[word] = row
    print(f'[ECDICT] cet4={len(cet4_words)} cet6={len(cet6_words)} 交集缓存 {len(rows)}')

    # 3) 合并全集，算词频星级（frq 越小越常用；frq=0 无数据取中间值 3）
    all_words = set(cet4_words) | set(cet6_words) | set(tem8_by_word.keys())
    with_frq = []
    for word in all_words:
        row = rows.get(word)
        if row:
            frq = row[9]
            if frq.isdigit() and int(frq) > 0:
                with_frq.append((int(frq), word))
    with_frq.sort()
    stars = _stars_by_frq([w for _, w in with_frq])
    print(f'[词频] {len(with_frq)} 词有 frq，其余默认 3 星')

    # 4) 高频划分（frq 前 40%）
    def high_freq_words(words):
        ranked = []
        for word in words:
            row = rows.get(word)
            frq = int(row[9]) if row and row[9].isdigit() else 0
            ranked.append((frq, word))
        ranked.sort()
        return {word for _, word in ranked[: max(1, int(len(ranked) * HIGH_FREQ_RATIO))]}

    high = {level: high_freq_words(words) for level, words in
            (('cet4', cet4_words), ('cet6', cet6_words), ('tem8', set(tem8_by_word.keys())))}

    db = get_db()

    # 5) 清理旧内置词书 + 建立 6 本 managed 词书（name 无 UNIQUE 约束，须先查后插并清理同名多余行）
    managed_names = [b[0] for b in BOOKS]
    placeholders = ','.join('?' for _ in managed_names)
    db.execute(f"DELETE FROM wordbooks WHERE is_builtin=1 AND name NOT IN ({placeholders})", managed_names)
    book_ids = {}
    for name, level, desc in BOOKS:
        existing = db.execute("SELECT id FROM wordbooks WHERE name=?", (name,)).fetchone()
        if existing:
            book_id = existing['id']
            db.execute("UPDATE wordbooks SET description=?, is_builtin=1 WHERE id=?", (desc, book_id))
        else:
            cur = db.execute("INSERT INTO wordbooks (name, description, is_builtin) VALUES (?,?,1)", (name, desc))
            book_id = cur.lastrowid
        # 清理历史遗留的同名行（早期版本按 INSERT OR IGNORE 建书产生）
        db.execute("DELETE FROM wordbooks WHERE name=? AND id<>?", (name, book_id))
        book_ids[name] = book_id
        db.execute("DELETE FROM wordbook_words WHERE wordbook_id=?", (book_id,))
    print('[词书] 6 本 managed 词书就绪')

    # 6) 写词（保留已有词；新词带 computed 星级）
    def insert_word(word, meanings, phonetic, pos, source):
        cur = db.execute(
            "INSERT OR IGNORE INTO words (word, phonetic, part_of_speech, meanings, source, frequency) "
            "VALUES (?,?,?,?,?,?)",
            (word, phonetic or '', pos or '', json.dumps(meanings, ensure_ascii=False), source,
             stars.get(word, 3)),
        )
        return cur.lastrowid if cur.rowcount else db.execute(
            "SELECT id FROM words WHERE word=?", (word,)).fetchone()['id']

    inserted_tem8_ids = set()
    for word in cet4_words:
        row = rows[word]
        insert_word(word, _parse_meanings(row[3]), row[1], row[4], 'cet4')
    for word in cet6_words:
        row = rows[word]
        insert_word(word, _parse_meanings(row[3]), row[1], row[4], 'cet6')
    for w in tem8:
        row = rows.get(w['word'])
        phonetic = (row[1] if row and row[1] else w['phonetic'])
        meanings = _parse_meanings(row[3]) if row else w['meanings']
        if not meanings:
            meanings = w['meanings']
        wid = insert_word(w['word'], meanings, phonetic, (row[4] if row else w['pos']), 'tem8')
        if w['sentences']:
            inserted_tem8_ids.add(wid)
    print(f'[写入] cet4={len(cet4_words)} cet6={len(cet6_words)} tem8={len(tem8)}')

    # 7) 词书成员
    level_words = {
        'cet4': cet4_words,
        'cet6': cet6_words,
        'tem8': set(tem8_by_word.keys()),
    }
    total_links = 0
    for name, level, _desc in BOOKS:
        is_high = '高频' in name
        words = level_words[level] if not is_high else (level_words[level] & high[level])
        pairs = [(book_ids[name], db.execute("SELECT id FROM words WHERE word=?", (w,)).fetchone()['id']) for w in words]
        db.executemany("INSERT OR IGNORE INTO wordbook_words (wordbook_id, word_id) VALUES (?,?)", pairs)
        total_links += len(pairs)
        print(f'  - {name}: {len(pairs)} 词')
    print(f'[词书成员] 共 {total_links} 条关联')

    # 8) 专八例句（只给本次新写入的 tem8 词插入，避免重复执行时重复）
    n_sent = 0
    for w in tem8:
        wid = db.execute("SELECT id FROM words WHERE word=?", (w['word'],)).fetchone()['id']
        if wid not in inserted_tem8_ids or not w['sentences']:
            continue
        for en, zh in w['sentences']:
            db.execute(
                "INSERT OR IGNORE INTO sentences (word_id, sentence_type, content, translation, source_info) "
                "VALUES (?, 'example', ?, ?, 'tem8-level8')",
                (wid, en, zh),
            )
            n_sent += 1
    print(f'[例句] 新增专八例句 {n_sent} 条')

    db.commit()
    db.close()

    # 9) 汇总
    db = get_db()
    counts = {}
    for name in managed_names:
        counts[name] = db.execute(
            "SELECT COUNT(*) AS c FROM wordbook_words WHERE wordbook_id=?", (book_ids[name],)
        ).fetchone()['c']
    total_words = db.execute("SELECT COUNT(*) AS c FROM words WHERE source IN ('cet4','cet6','tem8')").fetchone()['c']
    db.close()
    print('\n[完成] words 词表总量(考试词):', total_words)
    for name, c in counts.items():
        print(f'  {name}: {c}')


if __name__ == '__main__':
    main()

"""训练难度档位：1–6 星对应四级/六级三档，读写 user_settings。

难度从低到高：四级及格(1) → 四级普通(2) → 四级优秀(3) → 六级及格(4) → 六级普通(5) → 六级优秀(6)。
阅读 / 语法 / 听力按所选档位筛题；写作按对应评判标准批改。
"""

from database import get_db

SETTING_KEY = 'training_difficulty'

# criteria 会写入 AI 批改提示词，直接影响打分尺度。
LEVELS = [
    {
        'value': 1, 'label': '四级及格', 'exam_level': 'cet4',
        'criteria': '按大学英语四级及格线标准（425 分左右）批改，重点检查基本句型、常用词汇与达意是否准确，容忍少量基础错误，但不虚高。',
    },
    {
        'value': 2, 'label': '四级普通', 'exam_level': 'cet4',
        'criteria': '按大学英语四级中等水平标准批改，要求常用词汇与句式使用基本准确、表达连贯，结构清楚。',
    },
    {
        'value': 3, 'label': '四级优秀', 'exam_level': 'cet4',
        'criteria': '按大学英语四级优秀标准批改，要求词汇较丰富、句式有一定变化、结构清晰、论述有层次，评分从严。',
    },
    {
        'value': 4, 'label': '六级及格', 'exam_level': 'cet6',
        'criteria': '按大学英语六级及格线标准（425 分左右）批改，要求语言基本准确、逻辑清楚，能使用较复杂的词汇和句式，不虚高。',
    },
    {
        'value': 5, 'label': '六级普通', 'exam_level': 'cet6',
        'criteria': '按大学英语六级中等水平标准批改，要求用词较地道、句式多样、论证较深入，对基础性错误从严。',
    },
    {
        'value': 6, 'label': '六级优秀', 'exam_level': 'cet6',
        'criteria': '按大学英语六级优秀标准批改，要求用词地道丰富、句式灵活多样、逻辑严密、论述深入，全面从严评分。',
    },
]

_BY_VALUE = {item['value']: item for item in LEVELS}


def get_training_difficulty(db=None):
    """返回已保存的训练难度档位（1–6）；未设置返回 None。"""
    close = db is None
    if db is None:
        db = get_db()
    try:
        row = db.execute("SELECT value FROM user_settings WHERE key=?", (SETTING_KEY,)).fetchone()
    finally:
        if close:
            db.close()
    if not row or not row['value']:
        return None
    try:
        value = int(row['value'])
    except (TypeError, ValueError):
        return None
    return value if value in _BY_VALUE else None


def save_training_difficulty(value, db=None):
    """持久化训练难度档位，返回保存后的档位。"""
    value = int(value)
    if value not in _BY_VALUE:
        raise ValueError('训练难度需为 1–6 之间的档位')
    close = db is None
    if db is None:
        db = get_db()
    try:
        db.execute(
            "INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)",
            (SETTING_KEY, str(value)),
        )
        db.commit()
    finally:
        if close:
            db.close()
    return value


def difficulty_label(value):
    item = _BY_VALUE.get(int(value))
    return item['label'] if item else ''


def difficulty_exam_level(value):
    item = _BY_VALUE.get(int(value))
    return item['exam_level'] if item else 'cet4'


def difficulty_criteria(value):
    item = _BY_VALUE.get(int(value))
    return item['criteria'] if item else ''

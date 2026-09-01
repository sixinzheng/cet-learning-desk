"""站内 AI Skill 目录、启停规则与对话上下文。"""
import json
import os
import re
import uuid

from database import BASE_DIR, get_db


BUILTIN_SKILLS = (
    {
        'slug': 'learning-assistant',
        'display_name': '学习助理',
        'description': '负责快速问答、数据化问候、图片提问与学习建议。',
        'feature_prefixes': ['quick_chat', 'daily_greeting', 'chat_image'],
        'source_path': '',
    },
    {
        'slug': 'english-conversation-companion',
        'display_name': '地道英语陪聊',
        'description': '以当代美式英语进行场景陪聊，按当前段位调节难度并提供轻量表达优化。',
        'feature_prefixes': [],
        'source_path': 'skills/english-conversation-companion/SKILL.md',
    },
    {
        'slug': 'writing-coach',
        'display_name': '写作教练',
        'description': '按四六级标准批改作文，解释问题并给出可执行修改。',
        'feature_prefixes': ['essay_correction', 'writing_ocr', 'grammar_sentence'],
        'source_path': '',
    },
    {
        'slug': 'reading-curator',
        'display_name': '四六级阅读编辑',
        'description': '获取合规题材、生成原创阅读文章、命题并核验答案证据。',
        'feature_prefixes': ['reading_library', 'generate_reading', 'grade_reading'],
        'source_path': 'skills/cet-reading-curator/SKILL.md',
    },
    {
        'slug': 'note-librarian',
        'display_name': '笔记管理员',
        'description': '检索历史笔记、生成学习总结与待确认的笔记草稿。',
        'feature_prefixes': ['daily_summary'],
        'source_path': '',
    },
    {
        'slug': 'language-analyst',
        'display_name': '语言分析师',
        'description': '分析长难句、生成例句、选词填空与词汇融合练习。',
        'feature_prefixes': ['sentence_analysis', 'word_sentences', 'word_enrichment', 'fusion_sentence', 'generate_cloze'],
        'source_path': '',
    },
)


def seed_site_skills(conn):
    for item in BUILTIN_SKILLS:
        conn.execute(
            """INSERT OR IGNORE INTO site_skills
               (slug,display_name,description,feature_prefixes_json,source_path,enabled,is_builtin)
               VALUES (?,?,?,?,?,1,1)""",
            (
                item['slug'], item['display_name'], item['description'],
                json.dumps(item['feature_prefixes'], ensure_ascii=False), item['source_path'],
            ),
        )
        conn.execute(
            """UPDATE site_skills SET display_name=?,description=?,feature_prefixes_json=?,source_path=?
               WHERE slug=? AND is_builtin=1""",
            (
                item['display_name'], item['description'],
                json.dumps(item['feature_prefixes'], ensure_ascii=False), item['source_path'], item['slug'],
            ),
        )


def _row_payload(row):
    try:
        prefixes = json.loads(row['feature_prefixes_json'] or '[]')
    except (TypeError, json.JSONDecodeError):
        prefixes = []
    return {
        'slug': row['slug'], 'display_name': row['display_name'],
        'description': row['description'], 'user_instructions': row['user_instructions'],
        'feature_prefixes': prefixes, 'source_path': row['source_path'],
        'enabled': bool(row['enabled']), 'is_builtin': bool(row['is_builtin']),
        'updated_at': row['updated_at'],
    }


def list_site_skills():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM site_skills ORDER BY is_builtin DESC, created_at, display_name"
    ).fetchall()
    db.close()
    return [_row_payload(row) for row in rows]


def get_site_skill(slug):
    db = get_db()
    row = db.execute("SELECT * FROM site_skills WHERE slug=?", (slug,)).fetchone()
    db.close()
    return _row_payload(row) if row else None


def create_custom_skill(display_name, description='', instructions=''):
    name = str(display_name or '').strip()[:60]
    if not name:
        raise ValueError('请输入 Skill 名称。')
    base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:32] or 'custom'
    slug = f'{base}-{uuid.uuid4().hex[:6]}'
    db = get_db()
    db.execute(
        """INSERT INTO site_skills
           (slug,display_name,description,user_instructions,feature_prefixes_json,enabled,is_builtin)
           VALUES (?,?,?,?,?,1,0)""",
        (slug, name, str(description or '').strip()[:240], str(instructions or '').strip()[:12000], '[]'),
    )
    db.commit()
    row = db.execute("SELECT * FROM site_skills WHERE slug=?", (slug,)).fetchone()
    db.close()
    return _row_payload(row)


def update_site_skill(slug, payload):
    current = get_site_skill(slug)
    if not current:
        return None
    enabled = 1 if payload.get('enabled', current['enabled']) else 0
    instructions = str(payload.get('user_instructions', current['user_instructions']) or '').strip()[:12000]
    display_name = current['display_name'] if current['is_builtin'] else str(payload.get('display_name', current['display_name']) or '').strip()[:60]
    description = current['description'] if current['is_builtin'] else str(payload.get('description', current['description']) or '').strip()[:240]
    if not display_name:
        raise ValueError('Skill 名称不能为空。')
    db = get_db()
    db.execute(
        """UPDATE site_skills SET display_name=?,description=?,user_instructions=?,enabled=?,
           updated_at=datetime('now','localtime') WHERE slug=?""",
        (display_name, description, instructions, enabled, slug),
    )
    db.commit()
    row = db.execute("SELECT * FROM site_skills WHERE slug=?", (slug,)).fetchone()
    db.close()
    return _row_payload(row)


def delete_custom_skill(slug):
    db = get_db()
    row = db.execute("SELECT is_builtin FROM site_skills WHERE slug=?", (slug,)).fetchone()
    if not row:
        db.close()
        return False, 'not_found'
    if row['is_builtin']:
        db.close()
        return False, 'builtin'
    db.execute("DELETE FROM site_skills WHERE slug=?", (slug,))
    db.commit()
    db.close()
    return True, ''


def skill_for_feature(feature):
    feature = str(feature or '')
    for item in list_site_skills():
        if item['is_builtin'] and any(feature == prefix or feature.startswith(prefix + '_') for prefix in item['feature_prefixes']):
            return item
    return None


def ensure_feature_enabled(feature):
    skill = skill_for_feature(feature)
    if skill and not skill['enabled']:
        from services.ai_service import AIServiceError
        raise AIServiceError(
            f'“{skill["display_name"]}”Skill 已在“我的”中关闭。',
            'skill_disabled', 409,
        )
    return skill


def skill_prompt(slug):
    skill = get_site_skill(slug)
    if not skill or not skill['enabled']:
        return skill, ''
    parts = [
        f'当前启用的站内 Skill：{skill["display_name"]}',
        f'职责：{skill["description"]}',
    ]
    source_path = skill.get('source_path') or ''
    if source_path:
        absolute = os.path.abspath(os.path.join(BASE_DIR, source_path))
        allowed_root = os.path.abspath(os.path.join(BASE_DIR, 'skills'))
        if absolute.startswith(allowed_root + os.sep) and os.path.isfile(absolute):
            with open(absolute, 'r', encoding='utf-8') as handle:
                parts.append('项目规则：\n' + handle.read()[:16000])
    if skill.get('user_instructions'):
        parts.append('用户补充规则：\n' + skill['user_instructions'])
    return skill, '\n\n'.join(parts)

import sqlite3
import os

from runtime_paths import RESOURCE_ROOT, USER_DATA_DIR, ensure_user_data


BASE_DIR = RESOURCE_ROOT
DATA_DIR = USER_DATA_DIR
DB_PATH = os.path.join(DATA_DIR, 'vocab.db')


def get_db():
    """获取数据库连接"""
    ensure_user_data()
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化所有数据库表"""
    conn = get_db()
    conn.executescript('''
        -- 单词总库
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            corpus_id TEXT DEFAULT '',
            word TEXT NOT NULL UNIQUE,
            phonetic TEXT DEFAULT '',
            part_of_speech TEXT DEFAULT '',
            meanings TEXT DEFAULT '[]',
            audio_file TEXT DEFAULT '',
            source TEXT DEFAULT 'cet4',
            frequency INTEGER DEFAULT 1,
            added_date TEXT DEFAULT (date('now'))
        );

        -- 词库（内置 / 用户自建）
        CREATE TABLE IF NOT EXISTS wordbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            is_builtin INTEGER DEFAULT 0,
            is_hidden INTEGER DEFAULT 0,
            created_date TEXT DEFAULT (date('now'))
        );

        -- 词库-单词关联
        CREATE TABLE IF NOT EXISTS wordbook_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wordbook_id INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            FOREIGN KEY (wordbook_id) REFERENCES wordbooks(id) ON DELETE CASCADE,
            FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE,
            UNIQUE(wordbook_id, word_id)
        );

        -- 例句库（真题 + AI融合 + 经典例句，缓存AI结果）
        CREATE TABLE IF NOT EXISTS sentences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            sentence_type TEXT NOT NULL,
            content TEXT NOT NULL,
            translation TEXT DEFAULT '',
            source_info TEXT DEFAULT '',
            FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
        );

        -- 用户与单词的关系（状态、艾宾浩斯节点、复习记录）
        CREATE TABLE IF NOT EXISTS user_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL UNIQUE,
            status TEXT DEFAULT '陌生',
            review_count INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            consecutive_correct INTEGER DEFAULT 0,
            wrong_streak INTEGER DEFAULT 0,
            last_reviewed TEXT,
            next_review TEXT,
            ebbinghaus_stage INTEGER DEFAULT 0,
            FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
        );

        -- 相关单词标签组
        CREATE TABLE IF NOT EXISTS word_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT NOT NULL,
            word_ids TEXT DEFAULT '[]',
            created_date TEXT DEFAULT (date('now'))
        );

        -- 阅读文章
        CREATE TABLE IF NOT EXISTS reading_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source TEXT DEFAULT '',
            source_name TEXT DEFAULT '',
            source_verification TEXT DEFAULT '',
            content TEXT NOT NULL,
            word_count INTEGER DEFAULT 0,
            difficulty INTEGER DEFAULT 3,
            topic TEXT DEFAULT '',
            question_type TEXT DEFAULT 'careful_reading',
            word_stats TEXT DEFAULT '{}',
            date_added TEXT DEFAULT (date('now')),
            source_url TEXT DEFAULT '',
            source_title TEXT DEFAULT '',
            source_published_at TEXT DEFAULT '',
            retrieved_at TEXT DEFAULT '',
            adaptation_notes TEXT DEFAULT '',
            adaptation_note TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            generator_version TEXT DEFAULT '',
            origin TEXT DEFAULT 'legacy',
            inventory_status TEXT DEFAULT 'available'
        );

        -- 阅读题目
        CREATE TABLE IF NOT EXISTS reading_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            question_type TEXT NOT NULL,
            question TEXT NOT NULL,
            options TEXT DEFAULT '[]',
            answer TEXT NOT NULL,
            explanation TEXT DEFAULT '',
            evidence_text TEXT DEFAULT '',
            FOREIGN KEY (article_id) REFERENCES reading_articles(id) ON DELETE CASCADE
        );

        -- 阅读文章补库任务：单机队列可跨重启恢复，不在页面请求中等待 AI。
        CREATE TABLE IF NOT EXISTS reading_generation_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            difficulty INTEGER NOT NULL,
            question_type TEXT NOT NULL DEFAULT 'careful_reading',
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            idempotency_key TEXT NOT NULL UNIQUE,
            source_domain TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            last_error TEXT DEFAULT '',
            estimated_cost_cny REAL NOT NULL DEFAULT 0.02,
            actual_cost_cny REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            completed_at TEXT
        );

        -- 阅读单词标注（做题=green，陌生=red；widx=文章单词序号）
        CREATE TABLE IF NOT EXISTS article_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            word_index INTEGER NOT NULL DEFAULT 0,
            mark_type TEXT NOT NULL DEFAULT 'green',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(article_id, word_index, mark_type)
        );

        -- 阅读查词 AI 补充：与可信基础词义分离，按单词缓存并可明确刷新。
        CREATE TABLE IF NOT EXISTS word_ai_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL UNIQUE,
            surface_form TEXT NOT NULL DEFAULT '',
            article_id INTEGER,
            context_excerpt TEXT NOT NULL DEFAULT '',
            detail_json TEXT NOT NULL DEFAULT '{}',
            model TEXT NOT NULL DEFAULT '',
            prompt_version TEXT NOT NULL DEFAULT 'reading-word-v1',
            generated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE,
            FOREIGN KEY (article_id) REFERENCES reading_articles(id) ON DELETE SET NULL
        );

        -- 单选题库
        CREATE TABLE IF NOT EXISTS grammar_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            question TEXT NOT NULL,
            options TEXT DEFAULT '[]',
            answer TEXT NOT NULL,
            explanation TEXT DEFAULT '',
            difficulty INTEGER DEFAULT 3
        );

        -- 语法知识点（历史保留，新版本不再作为专项训练使用）
        CREATE TABLE IF NOT EXISTS grammar_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            example_sentences TEXT DEFAULT '[]'
        );

        -- 单词专练：选词填空题库（文章 + 挖空变形）
        CREATE TABLE IF NOT EXISTS cloze_passages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 3,
            level TEXT DEFAULT 'cet4',
            content TEXT NOT NULL,
            distractors TEXT DEFAULT '[]',
            date_added TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS cloze_blanks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            passage_id INTEGER NOT NULL,
            blank_order INTEGER NOT NULL,
            base_word TEXT NOT NULL,
            answer TEXT NOT NULL,
            hint TEXT DEFAULT '',
            FOREIGN KEY (passage_id) REFERENCES cloze_passages(id) ON DELETE CASCADE
        );

        -- 每日学习记录
        CREATE TABLE IF NOT EXISTS study_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_date TEXT NOT NULL UNIQUE,
            new_words_count INTEGER DEFAULT 0,
            review_words_count INTEGER DEFAULT 0,
            reading_count INTEGER DEFAULT 0,
            listening_count INTEGER DEFAULT 0,
            writing_count INTEGER DEFAULT 0,
            grammar_count INTEGER DEFAULT 0,
            total_minutes INTEGER DEFAULT 0
        );

        -- 每日完成词去重记录：只补充首页进度展示，不改变学习或复习调度。
        CREATE TABLE IF NOT EXISTS daily_word_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            completion_date TEXT NOT NULL,
            word_id INTEGER NOT NULL,
            completion_type TEXT NOT NULL CHECK(completion_type IN ('learn','review')),
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE,
            UNIQUE(completion_date, word_id, completion_type)
        );

        -- 专项训练整轮记录：能力计分只读取有正确率和难度证据的记录
        CREATE TABLE IF NOT EXISTS practice_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module TEXT NOT NULL,
            activity_type TEXT NOT NULL DEFAULT '',
            source_id TEXT DEFAULT '',
            difficulty INTEGER NOT NULL DEFAULT 3,
            correct_count INTEGER NOT NULL DEFAULT 0,
            total_count INTEGER NOT NULL DEFAULT 0,
            raw_score REAL NOT NULL DEFAULT 0,
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            response_ms INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            origin TEXT NOT NULL DEFAULT 'practice',
            idempotency_key TEXT NOT NULL UNIQUE,
            completed_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- 本地听说情景题库；不保存用户原始音频
        CREATE TABLE IF NOT EXISTS listening_scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            layer TEXT NOT NULL,
            topic TEXT NOT NULL DEFAULT '',
            difficulty INTEGER NOT NULL DEFAULT 3,
            prompt TEXT NOT NULL DEFAULT '',
            script TEXT NOT NULL DEFAULT '',
            question TEXT NOT NULL DEFAULT '',
            options_json TEXT NOT NULL DEFAULT '[]',
            answer TEXT NOT NULL DEFAULT '',
            accepted_intents_json TEXT NOT NULL DEFAULT '[]',
            sample_response TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1
        );

        -- 工作台笔记分类目录（一级/二级树）
        CREATE TABLE IF NOT EXISTS note_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL DEFAULT 0,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        -- 工作台笔记（多篇，支持分类与日期）
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            note_date TEXT DEFAULT '',
            color TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (category_id) REFERENCES note_categories(id) ON DELETE SET NULL
        );

        -- 段位评估数据
        CREATE TABLE IF NOT EXISTS user_level (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level_name TEXT DEFAULT '童生',
            level_rank INTEGER DEFAULT 1,
            total_score REAL DEFAULT 0,
            vocabulary_score REAL DEFAULT 0,
            reading_score REAL DEFAULT 0,
            listening_score REAL DEFAULT 0,
            writing_score REAL DEFAULT 0,
            grammar_score REAL DEFAULT 0,
            persistence_score REAL DEFAULT 0,
            confidence REAL DEFAULT 0,
            updated_date TEXT DEFAULT (date('now'))
        );

        -- 用户设置（键值对）
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );

        -- 导出打印队列
        CREATE TABLE IF NOT EXISTS export_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            added_date TEXT DEFAULT (date('now'))
        );

        -- AI 调用账单：只保存用量与用途，不保存 API Key。
        CREATE TABLE IF NOT EXISTS ai_usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT 'deepseek-v4-flash',
            status TEXT NOT NULL DEFAULT 'success',
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            cache_hit_tokens INTEGER NOT NULL DEFAULT 0,
            cache_miss_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            input_hit_price_cny REAL NOT NULL DEFAULT 0,
            input_miss_price_cny REAL NOT NULL DEFAULT 0,
            output_price_cny REAL NOT NULL DEFAULT 0,
            cost_cny REAL NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            result_count INTEGER NOT NULL DEFAULT 1,
            error_code TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS ai_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '英语学习对话',
            language TEXT NOT NULL DEFAULT 'zh',
            scenario_key TEXT NOT NULL DEFAULT 'casual',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS ai_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            citations_json TEXT NOT NULL DEFAULT '[]',
            action_draft_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (conversation_id) REFERENCES ai_conversations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ai_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            evidence_json TEXT NOT NULL DEFAULT '{}',
            confirmed INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            first_observed TEXT NOT NULL DEFAULT (date('now','localtime')),
            last_observed TEXT NOT NULL DEFAULT (date('now','localtime')),
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS ai_daily_greetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            greeting_date TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'zh',
            greeting TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'local',
            snapshot_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(greeting_date, language)
        );

        CREATE TABLE IF NOT EXISTS ai_action_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            action_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            idempotency_key TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            confirmed_at TEXT,
            FOREIGN KEY (conversation_id) REFERENCES ai_conversations(id) ON DELETE SET NULL
        );

        -- 全站 AI Skill 开关与用户补充规则。内置规则文件仍以项目 skills/ 为源码。
        CREATE TABLE IF NOT EXISTS site_skills (
            slug TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            user_instructions TEXT NOT NULL DEFAULT '',
            feature_prefixes_json TEXT NOT NULL DEFAULT '[]',
            source_path TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            is_builtin INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_ai_usage_created ON ai_usage_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_ai_messages_conversation ON ai_messages(conversation_id, id);
        CREATE INDEX IF NOT EXISTS idx_ai_memories_active ON ai_memories(active, last_observed);
        CREATE INDEX IF NOT EXISTS idx_site_skills_enabled ON site_skills(enabled, is_builtin);
        CREATE INDEX IF NOT EXISTS idx_daily_word_completions_date
            ON daily_word_completions(completion_date, completion_type);
        CREATE INDEX IF NOT EXISTS idx_reading_jobs_status
            ON reading_generation_jobs(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_word_ai_details_article
            ON word_ai_details(article_id, updated_at);
    ''')
    wordbook_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(wordbooks)").fetchall()
    }
    if 'is_hidden' not in wordbook_columns:
        conn.execute("ALTER TABLE wordbooks ADD COLUMN is_hidden INTEGER DEFAULT 0")
    # 迁移：为旧数据库添加 question_type 列
    try:
        conn.execute("ALTER TABLE reading_articles ADD COLUMN question_type TEXT DEFAULT 'careful_reading'")
    except:
        pass
    existing_reading_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(reading_articles)").fetchall()
    }
    for name, definition in (
        ('corpus_id', "TEXT DEFAULT ''"),
        ('source_url', "TEXT DEFAULT ''"),
        ('source_name', "TEXT DEFAULT ''"),
        ('source_verification', "TEXT DEFAULT ''"),
        ('source_title', "TEXT DEFAULT ''"),
        ('source_published_at', "TEXT DEFAULT ''"),
        ('retrieved_at', "TEXT DEFAULT ''"),
        ('adaptation_notes', "TEXT DEFAULT ''"),
        ('adaptation_note', "TEXT DEFAULT ''"),
        ('content_hash', "TEXT DEFAULT ''"),
        ('generator_version', "TEXT DEFAULT ''"),
        ('origin', "TEXT DEFAULT 'legacy'"),
        ('inventory_status', "TEXT DEFAULT 'available'"),
    ):
        if name not in existing_reading_columns:
            conn.execute(f"ALTER TABLE reading_articles ADD COLUMN {name} {definition}")
    existing_question_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(reading_questions)").fetchall()
    }
    if 'evidence_text' not in existing_question_columns:
        conn.execute("ALTER TABLE reading_questions ADD COLUMN evidence_text TEXT DEFAULT ''")

    # 旧数据库必须先补齐 inventory_status，再创建依赖该列的索引。
    # 若把索引放在首次 executescript 中，旧库会在迁移开始前直接启动失败。
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_reading_inventory
        ON reading_articles(question_type, topic, difficulty, inventory_status)
    ''')
    conn.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_reading_corpus_id
        ON reading_articles(corpus_id) WHERE COALESCE(corpus_id,'')!=''
    ''')

    # 话题使用稳定的六类标识，不再依赖前端删除 emoji 后猜测。
    topic_aliases = {
        '健康💊': '健康', '教育📚': '教育', '文化🎭': '文化',
        '环境🌍': '环境', '社会🏙️': '社会', '科技🔬': '科技',
    }
    for old_topic, canonical_topic in topic_aliases.items():
        conn.execute("UPDATE reading_articles SET topic=? WHERE topic=?", (canonical_topic, old_topic))
    conn.execute("UPDATE reading_articles SET topic='教育' WHERE topic LIKE '教育%'")
    conn.execute("""UPDATE reading_articles
                    SET source_name=CASE
                        WHEN COALESCE(source_name,'')!='' THEN source_name
                        WHEN source LIKE '题材参考：%' THEN substr(source,6)
                        ELSE source END,
                        adaptation_note=CASE WHEN COALESCE(adaptation_note,'')=''
                            THEN COALESCE(adaptation_notes,'') ELSE adaptation_note END""")

    # 历史数据没有 URL 证据时不继续冒用媒体来源；原标签保留在 source_title。
    conn.execute("""
        UPDATE reading_articles
        SET source_title=CASE WHEN COALESCE(source_title,'')='' THEN COALESCE(source,'') ELSE source_title END,
            source='历史题库／本站整理', origin='legacy'
        WHERE COALESCE(source_url,'')='' AND COALESCE(origin,'legacy')='legacy'
    """)
    # 段位 V2：保留旧列以兼容现有页面和历史快照。
    existing_level_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(user_level)").fetchall()
    }
    for name, definition in (
        ('speaking_score', 'REAL DEFAULT 0'),
        ('retention_score', 'REAL DEFAULT 0'),
        ('investment_score', 'REAL DEFAULT 0'),
        ('algorithm_version', "TEXT DEFAULT '1.0'"),
        ('change_reason', "TEXT DEFAULT ''"),
    ):
        if name not in existing_level_columns:
            conn.execute(f"ALTER TABLE user_level ADD COLUMN {name} {definition}")

    # 迁移：user_words 增加「当日模糊」标记列（四档反馈软过关，完成时原地巩固用）
    existing_user_words_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(user_words)").fetchall()
    }
    if 'vague_flagged' not in existing_user_words_columns:
        conn.execute("ALTER TABLE user_words ADD COLUMN vague_flagged INTEGER DEFAULT 0")

    # 单词专练计入每日词汇统计（供有效投入与进度展示使用）
    existing_study_logs_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(study_logs)").fetchall()
    }
    if 'vocabulary_count' not in existing_study_logs_columns:
        conn.execute("ALTER TABLE study_logs ADD COLUMN vocabulary_count INTEGER DEFAULT 0")

    # 双语学习助理：旧对话保持中文普通场景；会话语言与场景创建后不可变。
    conversation_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(ai_conversations)").fetchall()
    }
    if 'language' not in conversation_columns:
        conn.execute("ALTER TABLE ai_conversations ADD COLUMN language TEXT NOT NULL DEFAULT 'zh'")
    if 'scenario_key' not in conversation_columns:
        conn.execute("ALTER TABLE ai_conversations ADD COLUMN scenario_key TEXT NOT NULL DEFAULT 'casual'")
    conn.execute(
        "INSERT OR IGNORE INTO user_settings (key,value) VALUES ('assistant_language','zh')"
    )

    # 旧问候表的 greeting_date 带单列 UNIQUE，无法同日缓存中英文；一次性无损重建。
    greeting_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(ai_daily_greetings)").fetchall()
    }
    greeting_table = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='ai_daily_greetings'"
    ).fetchone()
    greeting_sql = (greeting_table[0] if greeting_table else '') or ''
    needs_greeting_rebuild = (
        'language' not in greeting_columns
        or 'UNIQUE(greeting_date, language)' not in greeting_sql.replace('\n', ' ')
    )
    if needs_greeting_rebuild:
        conn.execute("DROP TABLE IF EXISTS ai_daily_greetings_language_legacy")
        conn.execute("ALTER TABLE ai_daily_greetings RENAME TO ai_daily_greetings_language_legacy")
        conn.execute('''
            CREATE TABLE ai_daily_greetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                greeting_date TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'zh',
                greeting TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'local',
                snapshot_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                UNIQUE(greeting_date, language)
            )
        ''')
        legacy_columns = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(ai_daily_greetings_language_legacy)"
            ).fetchall()
        }
        language_expr = "COALESCE(language,'zh')" if 'language' in legacy_columns else "'zh'"
        conn.execute(f'''
            INSERT OR IGNORE INTO ai_daily_greetings
            (id,greeting_date,language,greeting,source,snapshot_json,created_at)
            SELECT id,greeting_date,{language_expr},greeting,source,snapshot_json,created_at
            FROM ai_daily_greetings_language_legacy
        ''')
        conn.execute("DROP TABLE ai_daily_greetings_language_legacy")

    # 隐藏的「未分类」根节点让 category_id=0 始终满足外键约束；
    # 页面分类树会过滤它，用户只会看到自己创建的目录。
    conn.execute(
        "INSERT OR IGNORE INTO note_categories (id,parent_id,name,sort_order) VALUES (0,0,'未分类',-1)"
    )

    # 工作台迁移：只在检测到旧「每日一记」表（没有 id 列）时迁移，
    # 并完整保留历史内容。旧逻辑仅凭 note_date 存在就每次删表，会在每次启动时清空笔记。
    existing_notes_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(notes)").fetchall()
    }
    if existing_notes_columns and 'id' not in existing_notes_columns:
        conn.execute("ALTER TABLE notes RENAME TO notes_legacy_daily")
        conn.execute('''
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                note_date TEXT DEFAULT '',
                color TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (category_id) REFERENCES note_categories(id) ON DELETE SET NULL
            )
        ''')
        legacy_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(notes_legacy_daily)").fetchall()
        }
        if {'note_date', 'content'}.issubset(legacy_columns):
            conn.execute('''
                INSERT INTO notes (category_id,title,content,note_date)
                SELECT 0, note_date || ' 学习笔记', content, note_date
                FROM notes_legacy_daily
                WHERE COALESCE(content, '') != ''
            ''')
        conn.execute("DROP TABLE notes_legacy_daily")

    # 标注表词级标记（word_index + per-type）：检测到旧列结构则重建为词级
    ann_cols = {row[1] for row in conn.execute("PRAGMA table_info(article_annotations)").fetchall()}
    if ann_cols and 'word_index' not in ann_cols:
        conn.execute("DROP TABLE article_annotations")
        conn.execute('''
            CREATE TABLE article_annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                word_index INTEGER NOT NULL DEFAULT 0,
                mark_type TEXT NOT NULL DEFAULT 'green',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                UNIQUE(article_id, word_index, mark_type)
            )
        ''')

    _seed_listening_scenarios(conn)
    try:
        from seed.cloze_catalog import seed_cloze_catalog
        seed_cloze_catalog(conn)
    except ImportError:
        pass
    from seed.reading_catalog import seed_reading_catalog, ensure_reading_inventory_jobs
    seed_reading_catalog(conn)
    ensure_reading_inventory_jobs(conn)
    from services.skill_service import seed_site_skills
    seed_site_skills(conn)

    # 内置「我的收藏」词库：首次初始化时自动创建（收藏单词统一收进这里）
    if not conn.execute("SELECT id FROM wordbooks WHERE name='我的收藏' LIMIT 1").fetchone():
        conn.execute(
            "INSERT INTO wordbooks (name, description, is_builtin, is_hidden) VALUES ('我的收藏', '收藏的单词自动收进这里', 1, 0)"
        )

    # 隐藏的全量词汇缓存不出现在词书选择中；每次启动幂等补齐未来新增词。
    hidden_book = conn.execute(
        "SELECT id FROM wordbooks WHERE name='阅读词汇缓存' LIMIT 1"
    ).fetchone()
    if hidden_book:
        hidden_book_id = hidden_book['id']
        conn.execute(
            "UPDATE wordbooks SET is_builtin=1,is_hidden=1 WHERE id=?",
            (hidden_book_id,),
        )
    else:
        hidden_book_id = conn.execute(
            "INSERT INTO wordbooks (name,description,is_builtin,is_hidden) "
            "VALUES ('阅读词汇缓存','阅读查词与 AI 补充使用的内部全量词库',1,1)"
        ).lastrowid
    conn.execute(
        "INSERT OR IGNORE INTO wordbook_words (wordbook_id,word_id) "
        "SELECT ?,id FROM words",
        (hidden_book_id,),
    )

    conn.commit()
    conn.close()


def _seed_listening_scenarios(conn):
    """写入可离线使用的短对话和口语情景；重复启动不会重复插入。"""
    if conn.execute("SELECT COUNT(*) FROM listening_scenarios").fetchone()[0]:
        return
    rows = [
        ('dialogue','校园',2,'',"A: Excuse me, where is the language lab? B: It is on the second floor.",'Where is the language lab?','["On the first floor","On the second floor","Beside the library","Across the street"]','B','[]',''),
        ('dialogue','旅行',2,'',"A: What time does the train leave? B: At a quarter past nine.",'When does the train leave?','["8:45","9:00","9:15","9:30"]','C','[]',''),
        ('dialogue','餐饮',2,'',"A: Would you like tea or coffee? B: Tea, please, without sugar.",'What does the customer want?','["Coffee with sugar","Tea without sugar","Tea with milk","Water"]','B','[]',''),
        ('dialogue','公共服务',3,'',"A: I would like to return this book. B: It is two days overdue, so there is a small fine.",'Why is there a fine?','["The book is damaged","The card expired","The book is overdue","The book is lost"]','C','[]',''),
        ('dialogue','学习',3,'',"A: Have you finished the science report? B: Not yet. I still need to check the final experiment.",'What remains to be done?','["Choose a topic","Check an experiment","Write the introduction","Print the report"]','B','[]',''),
        ('dialogue','工作',4,'',"A: The meeting has been moved forward by thirty minutes. B: Then I will send everyone the revised schedule.",'What will the second speaker do?','["Cancel the meeting","Book another room","Revise the report","Send the new schedule"]','D','[]',''),
    ]
    conn.executemany('''
        INSERT INTO listening_scenarios
        (layer, topic, difficulty, prompt, script, question, options_json, answer,
         accepted_intents_json, sample_response)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    ''', rows)

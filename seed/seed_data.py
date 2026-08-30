"""内置词库 & 题库初始化"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db, init_db
import json


CET4_WORDS = [
    ("abandon", "əˈbændən", "v.", '["抛弃，放弃", "遗弃"]', 5),
    ("ability", "əˈbɪləti", "n.", '["能力，才能"]', 4),
    ("abolish", "əˈbɑːlɪʃ", "v.", '["废除，废止（法律、制度等）"]', 4),
    ("absorb", "əbˈzɔːrb", "v.", '["吸收", "吸引…的注意"]', 4),
    ("abstract", "ˈæbstrækt", "adj./n.", '["抽象的", "摘要"]', 3),
    ("abundant", "əˈbʌndənt", "adj.", '["丰富的，充裕的"]', 3),
    ("abuse", "əˈbjuːz", "v./n.", '["滥用", "虐待", "辱骂"]', 4),
    ("academic", "ˌækəˈdemɪk", "adj.", '["学术的", "学院的"]', 5),
    ("accelerate", "əkˈseləreɪt", "v.", '["加速，促进"]', 3),
    ("access", "ˈækses", "n./v.", '["进入，通道", "访问", "获取"]', 5),
    ("accommodate", "əˈkɑːmədeɪt", "v.", '["容纳", "为…提供住宿", "适应"]', 3),
    ("accompany", "əˈkʌmpəni", "v.", '["陪伴", "伴随", "为…伴奏"]', 4),
    ("accomplish", "əˈkɑːmplɪʃ", "v.", '["完成，实现"]', 4),
    ("account", "əˈkaʊnt", "n./v.", '["账户", "描述", "解释(account for)"]', 5),
    ("accumulate", "əˈkjuːmjəleɪt", "v.", '["积累，积聚"]', 3),
    ("accurate", "ˈækjərət", "adj.", '["准确的，精确的"]', 4),
    ("achieve", "əˈtʃiːv", "v.", '["实现，达到", "获得"]', 5),
    ("acknowledge", "əkˈnɑːlɪdʒ", "v.", '["承认", "确认收到", "感谢"]', 4),
    ("acquire", "əˈkwaɪər", "v.", '["获得，习得"]', 4),
    ("adapt", "əˈdæpt", "v.", '["适应", "改编"]', 4),
    ("adequate", "ˈædɪkwət", "adj.", '["足够的，充分的"]', 4),
    ("adjust", "əˈdʒʌst", "v.", '["调整，适应"]', 3),
    ("administration", "ədˌmɪnɪˈstreɪʃn", "n.", '["管理", "行政", "政府"]', 3),
    ("admire", "ədˈmaɪər", "v.", '["钦佩，赞赏"]', 3),
    ("adopt", "əˈdɑːpt", "v.", '["采纳", "收养"]', 4),
    ("advance", "ədˈvæns", "v./n.", '["前进", "进步", "预先的"]', 4),
    ("advantage", "ədˈvæntɪdʒ", "n.", '["优势，有利条件"]', 5),
    ("advertise", "ˈædvərtaɪz", "v.", '["做广告", "宣传"]', 3),
    ("affect", "əˈfekt", "v.", '["影响", "感动"]', 5),
    ("afford", "əˈfɔːrd", "v.", '["负担得起", "提供"]', 4),
    ("agency", "ˈeɪdʒənsi", "n.", '["代理机构", "中介"]', 3),
    ("aggressive", "əˈɡresɪv", "adj.", '["侵略的", "好斗的", "积极进取的"]', 3),
    ("agree", "əˈɡriː", "v.", '["同意，赞成"]', 5),
    ("agriculture", "ˈæɡrɪkʌltʃər", "n.", '["农业"]', 3),
    ("aim", "eɪm", "n./v.", '["目标", "瞄准", "旨在"]', 4),
    ("alcohol", "ˈælkəhɔːl", "n.", '["酒精", "含酒精饮料"]', 3),
    ("allow", "əˈlaʊ", "v.", '["允许", "使能够"]', 5),
    ("alter", "ˈɔːltər", "v.", '["改变，修改"]', 3),
    ("alternative", "ɔːlˈtɜːrnətɪv", "n./adj.", '["替代方案", "可替代的"]', 4),
    ("amaze", "əˈmeɪz", "v.", '["使惊奇，使惊愕"]', 3),
    ("amount", "əˈmaʊnt", "n.", '["数量，金额"]', 5),
    ("analyze", "ˈænəlaɪz", "v.", '["分析"]', 4),
    ("anniversary", "ˌænɪˈvɜːrsəri", "n.", '["周年纪念日"]', 3),
    ("annual", "ˈænjuəl", "adj.", '["年度的，每年的"]', 3),
    ("anxiety", "æŋˈzaɪəti", "n.", '["焦虑，忧虑"]', 3),
    ("apparent", "əˈpærənt", "adj.", '["明显的，表面上的"]', 3),
    ("appeal", "əˈpiːl", "v./n.", '["呼吁", "吸引", "上诉"]', 4),
    ("apply", "əˈplaɪ", "v.", '["申请", "应用", "适用于"]', 5),
    ("appreciate", "əˈpriːʃieɪt", "v.", '["欣赏", "感激", "理解"]', 4),
    ("approach", "əˈproʊtʃ", "v./n.", '["接近", "方法"]', 5),
]

CET6_WORDS = [
    ("abolish", "əˈbɑːlɪʃ", "v.", '["废除，废止"]', 4),
    ("absurd", "əbˈsɜːrd", "adj.", '["荒谬的，荒唐的"]', 3),
    ("abundance", "əˈbʌndəns", "n.", '["丰富，充裕"]', 3),
    ("accessory", "əkˈsesəri", "n.", '["附件，配件", "从犯"]', 2),
    ("accommodate", "əˈkɑːmədeɪt", "v.", '["容纳", "适应"]', 4),
    ("acquaint", "əˈkweɪnt", "v.", '["使熟悉，使认识"]', 3),
    ("adhere", "ədˈhɪr", "v.", '["黏附", "坚持，遵守"]', 3),
    ("adjacent", "əˈdʒeɪsnt", "adj.", '["邻近的，毗连的"]', 2),
    ("administer", "ədˈmɪnɪstər", "v.", '["管理", "执行", "给予"]', 3),
    ("adolescent", "ˌædəˈlesnt", "n./adj.", '["青少年", "青春期的"]', 3),
    ("agenda", "əˈdʒendə", "n.", '["议程"]', 4),
    ("aggravate", "ˈæɡrəveɪt", "v.", '["加重", "使恶化", "激怒"]', 3),
    ("allege", "əˈledʒ", "v.", '["断言，宣称"]', 3),
    ("alleviate", "əˈliːvieɪt", "v.", '["减轻，缓解"]', 3),
    ("allocate", "ˈæləkeɪt", "v.", '["分配，拨出"]', 3),
    ("ambiguous", "æmˈbɪɡjuəs", "adj.", '["含糊的，模棱两可的"]', 4),
    ("amend", "əˈmend", "v.", '["修改，修订"]', 3),
    ("analogy", "əˈnælədʒi", "n.", '["类比，类推"]', 2),
    ("anonymous", "əˈnɑːnɪməs", "adj.", '["匿名的"]', 3),
    ("apparatus", "ˌæpəˈrætəs", "n.", '["设备，仪器", "机构"]', 2),
    ("applaud", "əˈplɔːd", "v.", '["鼓掌", "称赞"]', 3),
    ("appraisal", "əˈpreɪzl", "n.", '["评估，评价"]', 3),
    ("apt", "æpt", "adj.", '["恰当的", "易于…的", "聪明的"]', 2),
    ("array", "əˈreɪ", "n.", '["一系列", "数组", "排列"]', 3),
    ("articulate", "ɑːrˈtɪkjuleɪt", "v./adj.", '["清楚表达", "口才好的"]', 3),
    ("ascend", "əˈsend", "v.", '["上升，攀登"]', 2),
    ("ascribe", "əˈskraɪb", "v.", '["归因于，归咎于"]', 2),
    ("assault", "əˈsɔːlt", "n./v.", '["攻击，袭击"]', 2),
    ("assert", "əˈsɜːrt", "v.", '["断言", "坚持，维护"]', 3),
    ("assimilate", "əˈsɪməleɪt", "v.", '["同化", "吸收，理解"]', 3),
]


def seed():
    """初始化内置数据"""
    init_db()
    db = get_db()

    # --- 词库 ---
    for wb_name, wb_desc in [('四级高频词库', 'CET-4 核心高频词汇'), ('六级高频词库', 'CET-6 核心高频词汇')]:
        existing = db.execute("SELECT id FROM wordbooks WHERE name=?", (wb_name,)).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO wordbooks (name, description, is_builtin) VALUES (?,?,1)",
                (wb_name, wb_desc)
            )

    cet4_id = db.execute("SELECT id FROM wordbooks WHERE name='四级高频词库'").fetchone()['id']
    cet6_id = db.execute("SELECT id FROM wordbooks WHERE name='六级高频词库'").fetchone()['id']

    # --- 四级单词 ---
    for word, phonetic, pos, meanings, freq in CET4_WORDS:
        wid = _insert_word(db, word, phonetic, pos, meanings, 'cet4', freq)
        try:
            db.execute("INSERT INTO wordbook_words (wordbook_id, word_id) VALUES (?,?)", (cet4_id, wid))
        except:
            pass
        db.execute("INSERT OR IGNORE INTO user_words (word_id, status) VALUES (?, '陌生')", (wid,))

    # --- 六级单词 ---
    for word, phonetic, pos, meanings, freq in CET6_WORDS:
        wid = _insert_word(db, word, phonetic, pos, meanings, 'cet6', freq)
        try:
            db.execute("INSERT INTO wordbook_words (wordbook_id, word_id) VALUES (?,?)", (cet6_id, wid))
        except:
            pass
        db.execute("INSERT OR IGNORE INTO user_words (word_id, status) VALUES (?, '陌生')", (wid,))

    # --- 语法题库 ---
    _seed_grammar(db)

    # --- 阅读文章 ---
    _seed_reading(db)

    # --- 初始段位 ---
    if not db.execute("SELECT id FROM user_level LIMIT 1").fetchone():
        db.execute("INSERT INTO user_level DEFAULT VALUES")

    # --- 今日学习记录（没有则创建） ---
    from datetime import date
    today = date.today().isoformat()
    db.execute("INSERT OR IGNORE INTO study_logs (study_date) VALUES (?)", (today,))

    # --- 为每个词添加一条基础例句 ---
    _seed_sentences(db)

    db.commit()
    db.close()
    print("[OK] Seed data initialized successfully!")


def _seed_sentences(db):
    example_sentences = {
        'abandon': [('They had to abandon the project due to lack of funding.', '由于缺乏资金，他们不得不放弃这个项目。')],
        'ability': [('She has the ability to solve complex problems quickly.', '她有能力快速解决复杂问题。')],
        'abolish': [('The government decided to abolish the outdated law.', '政府决定废除这项过时的法律。')],
        'absorb': [('Plants absorb carbon dioxide from the atmosphere.', '植物从大气中吸收二氧化碳。')],
        'academic': [('His academic performance has improved significantly this semester.', '这学期他的学业成绩显著提高。')],
        'access': [('Students have free access to the online library resources.', '学生可以免费访问在线图书馆资源。')],
        'achieve': [('To achieve your goals, you need consistent effort every day.', '要实现目标，你需要每天持续努力。')],
        'account': [('How do you account for the sudden change in his attitude?', '你如何解释他态度的突然转变？')],
    }
    for word, sentences in example_sentences.items():
        w = db.execute("SELECT id FROM words WHERE word=?", (word,)).fetchone()
        if w:
            for en, zh in sentences:
                db.execute(
                    "INSERT OR IGNORE INTO sentences (word_id, sentence_type, content, translation, source_info) VALUES (?, 'example', ?, ?, 'seed')",
                    (w['id'], en, zh)
                )


def _insert_word(db, word, phonetic, pos, meanings, source, freq):
    try:
        cur = db.execute(
            "INSERT INTO words (word, phonetic, part_of_speech, meanings, source, frequency) VALUES (?,?,?,?,?,?)",
            (word.lower().strip(), phonetic, pos, meanings, source, freq)
        )
        return cur.lastrowid
    except:
        row = db.execute("SELECT id FROM words WHERE word=?", (word.lower().strip(),)).fetchone()
        return row['id'] if row else None


def _seed_grammar(db):
    questions = [
        # 四级基础 (difficulty=1)
        ("时态", "I ___ to school every day.", '["A. go","B. goes","C. going","D. gone"]', "A", "一般现在时：主语I用动词原形。", 1),
        ("时态", "She ___ her homework yesterday.", '["A. do","B. does","C. did","D. doing"]', "C", "一般过去时：yesterday提示过去时间，用过去式。", 1),
        ("固定搭配", "I am looking forward ___ you.", '["A. to see","B. to seeing","C. see","D. seeing"]', "B", "look forward to doing，to是介词后接动名词。", 1),
        # 四级进阶 (difficulty=2)
        ("时态", "By the end of this month, we ___ the project.", '["A. finish","B. will finish","C. will have finished","D. finished"]', "C", "将来完成时：by+将来时间点，表示到那时已完成的动作。", 2),
        ("虚拟语气", "If I ___ you, I would accept the offer.", '["A. am","B. was","C. were","D. be"]', "C", "与现在事实相反的虚拟语气，be一律用were。", 2),
        ("非谓语", "___ in the rain, he caught a cold.", '["A. Caught","B. Catching","C. Being caught","D. Having caught"]', "A", "过去分词作原因状语，be caught in the rain淋雨。", 2),
        # 四级高阶 (difficulty=3)
        ("时态", "By the time he arrives, we ___ for two hours.", '["A. will wait","B. will have been waiting","C. waited","D. have waited"]', "B", "将来完成进行时：持续到将来某时的动作。", 3),
        ("虚拟语气", "It is essential that every student ___ the rules.", '["A. follows","B. follow","C. followed","D. following"]', "B", "It is essential that后接(should)+动词原形。", 3),
        ("非谓语", "___ from the top, the city looks beautiful.", '["A. Seeing","B. To see","C. Seen","D. Having seen"]', "C", "过去分词表被动，逻辑主语city与see是被动关系。", 3),
        ("从句", "___ is known to all, the earth moves around the sun.", '["A. That","B. Which","C. As","D. It"]', "C", "as引导非限制性定语从句，可放句首。", 3),
        # 六级基础 (difficulty=4)
        ("虚拟语气", "But for his help, I ___ the exam.", '["A. wouldn\'t pass","B. wouldn\'t have passed","C. didn\'t pass","D. haven\'t passed"]', "B", "But for=Without，对过去虚拟，主句用would have done。", 4),
        ("非谓语", "The meeting ___ tomorrow is important.", '["A. held","B. holding","C. to be held","D. being held"]', "C", "不定式被动表将来：明天要举行的会议。", 4),
        # 六级进阶 (difficulty=5)
        ("从句", "I had no idea ___ was going on.", '["A. what","B. that","C. which","D. how"]', "A", "what引导同位语从句，在从句中作主语。", 5),
        ("虚拟语气", "It is high time we ___ action.", '["A. take","B. took","C. have taken","D. will take"]', "B", "It is high time that从句用过去式表虚拟。", 5),
        # 六级高阶 (difficulty=6)
        ("非谓语", "He is said ___ abroad last year.", '["A. to go","B. going","C. to have gone","D. having gone"]', "C", "be said to have done表示已发生的动作。", 6),
        ("从句", "There is no doubt ___ he will succeed.", '["A. whether","B. if","C. that","D. what"]', "C", "There is no doubt that...同位语从句，用that引导。", 6),
    ]
    # Keep old questions too (for backward compat)
    old_questions = [
        ("时态", "By the time he arrives, we ___ for two hours.", '["A. will wait","B. will have been waiting","C. waited","D. have waited"]', "B", "将来完成进行时。", 3),
        ("时态", "I ___ in this city since I was a child.", '["A. lived","B. have been living","C. was living","D. live"]', "B", "现在完成进行时。", 3),
        ("虚拟语气", "If I ___ you, I would accept the offer.", '["A. am","B. was","C. were","D. be"]', "C", "与现在事实相反的虚拟语气。", 2),
        ("虚拟语气", "It is essential that every student ___ the rules.", '["A. follows","B. follow","C. followed","D. following"]', "B", "It is essential that用原形。", 3),
        ("非谓语", "___ from the top of the mountain, the city looks beautiful.", '["A. Seeing","B. To see","C. Seen","D. Having seen"]', "C", "过去分词表被动。", 3),
        ("非谓语", "He avoided ___ the same mistake again.", '["A. to make","B. making","C. made","D. make"]', "B", "avoid后接动名词。", 2),
        ("固定搭配", "We should take advantage ___ this opportunity.", '["A. with","B. for","C. of","D. to"]', "C", "take advantage of。", 1),
        ("固定搭配", "He is accustomed ___ early.", '["A. to get up","B. getting up","C. to getting up","D. get up"]', "C", "be accustomed to doing。", 2),
        ("从句", "This is the house ___ I grew up.", '["A. which","B. where","C. that","D. what"]', "B", "关系副词where。", 3),
        ("从句", "___ is known to all, the earth moves around the sun.", '["A. That","B. Which","C. As","D. It"]', "C", "as引导非限制性定语从句。", 3),
    ]
    for cat, q, opts, ans, exp, diff in questions:
        existing = db.execute("SELECT id FROM grammar_questions WHERE question=? AND difficulty=?", (q, diff)).fetchone()
        if not existing:
            db.execute("INSERT INTO grammar_questions (category, question, options, answer, explanation, difficulty) VALUES (?,?,?,?,?,?)", (cat, q, opts, ans, exp, diff))
    for cat, q, opts, ans, exp, diff in old_questions:
        existing = db.execute("SELECT id FROM grammar_questions WHERE question=? AND difficulty=?", (q, diff)).fetchone()
        if not existing:
            db.execute("INSERT INTO grammar_questions (category, question, options, answer, explanation, difficulty) VALUES (?,?,?,?,?,?)", (cat, q, opts, ans, exp, diff))
    db.commit()


def _seed_reading_questions(db, article_id, questions):
    for qtype, question, options, answer, explanation in questions:
        db.execute(
            "INSERT INTO reading_questions (article_id, question_type, question, options, answer, explanation) VALUES (?,?,?,?,?,?)",
            (article_id, qtype, question, options, answer, explanation)
        )


def _seed_reading(db):
    articles = [
        # === 仔细阅读 (careful_reading) ===
        # 四级基础 (diff=1)
        ("The Benefits of Reading", "China Daily",
         "Reading is one of the most important skills for college students. When you read regularly, you improve your vocabulary and grammar naturally. Reading also helps you understand different cultures and ideas. Many successful people say that reading helped them achieve their goals. You can start with short articles and gradually read longer books. The key is to make reading a daily habit. Even fifteen minutes a day can make a big difference over time.",
         1, "教育", "careful_reading"),
        ("Healthy Eating Habits", "BBC Learning",
         "Eating well is essential for students who need energy for studying. A good breakfast with bread, eggs, and milk can help you focus in the morning. Fruits and vegetables provide important vitamins. Try to avoid too much fast food and sugary drinks. Drinking enough water is also very important for your brain to work well. Small changes in your diet can lead to better health and better grades.",
         1, "健康", "careful_reading"),
        # 四级进阶 (diff=2)
        ("Climate Change and Global Action", "The Economist",
         "Climate change remains one of the most pressing challenges facing humanity today. Scientists have long warned that rising global temperatures will lead to severe consequences, including more frequent extreme weather events, rising sea levels, and disruptions to agriculture. Despite decades of international negotiations, global carbon emissions continue to rise. However, recent developments in renewable energy technology offer hope. Solar and wind power have become increasingly cost-effective, and many countries are now investing heavily in green energy infrastructure.",
         2, "环境", "careful_reading"),
        ("The Impact of Social Media on Education", "The Guardian",
         "Social media has transformed the way students interact with information and each other. Platforms like WeChat and Weibo have become integral parts of daily life for millions of college students. On one hand, social media provides unprecedented access to educational resources and facilitates collaboration among learners. On the other hand, excessive use of social media can lead to distraction, reduced attention spans, and increased anxiety. The key lies in finding a healthy balance between leveraging the benefits of these platforms while minimizing their drawbacks.",
         2, "教育", "careful_reading"),
        # 四级高阶 (diff=3)
        ("The Future of Artificial Intelligence", "Scientific American",
         "Artificial intelligence is rapidly changing the landscape of modern education. From personalized learning algorithms to automated grading systems, AI technologies are being integrated into classrooms worldwide. While some educators worry about the potential for AI to replace human teachers, most experts believe that AI will serve as a powerful tool to enhance rather than replace traditional instruction. The challenge lies in ensuring that AI systems are designed ethically and that all students have equal access to these technologies regardless of their economic background.",
         3, "科技", "careful_reading"),
        # 六级基础 (diff=4)
        ("Global Trade and Economic Development", "Financial Times",
         "International trade has been a driving force behind global economic growth for decades. However, recent geopolitical tensions and supply chain disruptions have led many countries to reconsider their reliance on foreign markets. The concept of economic sovereignty has gained traction, with nations seeking to protect critical industries and reduce dependency on external suppliers. This shift presents both opportunities and risks for developing economies that have historically benefited from globalization.",
         4, "社会", "careful_reading"),
        # 六级进阶 (diff=5)
        ("The Philosophy of Science in Modern Research", "Nature",
         "The epistemological foundations of scientific inquiry have undergone significant revision in the past century. Kuhn's paradigm shift theory challenged the Whig interpretation of scientific progress as linear accumulation. Contemporary philosophers argue that scientific knowledge is socially constructed yet empirically constrained. This tension between constructivism and realism continues to shape debates about research methodology, peer review, and the demarcation problem between science and pseudoscience.",
         5, "文化", "careful_reading"),
        # 六级高阶 (diff=6)
        ("Quantum Computing and Cryptographic Security", "IEEE Spectrum",
         "The advent of scalable quantum computers poses an existential threat to current public-key cryptographic systems. Shor's algorithm demonstrates that sufficiently powerful quantum processors could factor large integers in polynomial time, effectively breaking RSA encryption. Post-quantum cryptography aims to develop algorithms resistant to both classical and quantum attacks. The National Institute of Standards and Technology has been leading efforts to standardize quantum-resistant algorithms, with lattice-based cryptography emerging as a promising candidate.",
         6, "科技", "careful_reading"),
        # === 词汇理解 / 选词填空 (banked_cloze) ===
        # 四级基础 (diff=1)
        ("Smartphones and Modern Life", "The Atlantic",
         "Smartphones have become an ____(1)____ part of modern life. While they provide easy ____(2)____ to information and help us stay connected, many experts worry about their ____(3)____ on our mental health. Studies show that people who ____(4)____ check their phones throughout the day tend to have ____(5)____ concentration levels. To maintain a healthy ____(6)____ between technology and real life, experts suggest that we should learn to ____(7)____ from our devices regularly. Setting aside phone-free time each day can ____(8)____ improve our productivity and well-being. The key is to ____(9)____ our screen time wisely and make ____(10)____ use of technology rather than letting it control us.",
         1, "科技", "banked_cloze"),
        # 四级进阶 (diff=2)
        ("Effective Study Strategies", "The Times Higher Education",
         "College students who ____(1)____ strong study habits tend to ____(2)____ better academically. Research suggests that the most ____(3)____ learning method is to ____(4)____ study sessions over time rather than cramming. When you ____(5)____ material at regular intervals, your brain can better ____(6)____ the information. Creating a study ____(7)____ that fits your daily routine is essential for long-term success. It is also important to choose a quiet ____(8)____ free from distractions. Students who ____(9)____ their notes after each class typically develop deeper ____(10)____ of the subject matter.",
         2, "教育", "banked_cloze"),
        # 六级基础 (diff=3)
        ("Green Energy Revolution", "National Geographic",
         "The global ____(1)____ to renewable energy has gained significant momentum in recent years. Governments worldwide are beginning to ____(2)____ policies that promote clean energy ____(3)____. Solar and wind power now offer ____(4)____ alternatives to fossil fuels at increasingly competitive prices. Reducing carbon ____(5)____ has become a priority for many nations committed to ____(6)____ development. Experts predict that countries that ____(7)____ heavily in green technology will enjoy both environmental and economic benefits. The ____(8)____ from coal and oil to clean energy requires ____(9)____ cooperation between governments, businesses, and individuals. However, the long-term rewards of this energy ____(10)____ far outweigh the short-term costs.",
         3, "环境", "banked_cloze"),
    ]
    reading_qs = {
        "Climate Change and Global Action": [
            ("main_idea", "What is the main idea of this article?",
             '["A. Climate change is unsolvable","B. International cooperation is needed to transition to a low-carbon economy","C. Renewable energy is too expensive","D. Scientists disagree about climate change"]', "B",
             "文章主要讨论气候变化需要国际合作向低碳经济转型，强调可再生能源的进步和全球合作的必要性。"),
            ("detail", "According to the article, what offers hope in addressing climate change?",
             '["A. International negotiations","B. Rising carbon emissions","C. Renewable energy technology","D. Agricultural disruptions"]', "C",
             "文章明确指出renewable energy technology的发展带来了希望，太阳能和风能变得更加经济有效。"),
            ("inference", "What can be inferred about the transition to a low-carbon economy?",
             '["A. It will be easy and quick","B. It requires cooperation from multiple sectors","C. Only governments need to act","D. It has already been completed"]', "B",
             "文章提到需要政府、企业和个人之间前所未有的合作，可以推断需要多方共同努力。"),
            ("word_guess", 'The word "cost-effective" in paragraph 2 most likely means:',
             '["A. expensive","B. providing good value for money","C. difficult to produce","D. environmentally harmful"]', "B",
             "cost-effective意为'具有成本效益的'，在花费方面物有所值。"),
            ("attitude", "What is the author\'s attitude toward the future of climate action?",
             '["A. Completely pessimistic","B. Cautiously optimistic","C. Indifferent","D. Extremely angry"]', "B",
             "作者虽然承认挑战，但对可再生能源发展和低碳转型持谨慎乐观态度。"),
        ],
        "The Impact of Social Media on Education": [
            ("main_idea", "What is the main idea of this article?",
             '["A. Social media should be banned in schools","B. Social media has both positive and negative effects on education","C. Students spend too much time online","D. Social media is the best learning tool"]', "B",
             "文章讨论了社交媒体对教育的积极和消极两方面影响。"),
            ("detail", "According to studies, students who spend more than three hours per day on social media:",
             '["A. Have better academic performance","B. Are more social","C. Tend to have lower academic performance","D. Learn faster"]', "C",
             "文章明确指出每天使用社交媒体超过3小时的学生往往学业成绩较低。"),
            ("inference", "What can be inferred about the author\'s view on social media?",
             '["A. It should be completely avoided","B. It should be used without any restrictions","C. A balanced approach is needed","D. Only college students should use it"]', "C",
             "作者提到关键在于找到平衡，说明应采取平衡的方式来使用社交媒体。"),
            ("word_guess", 'The word "integral" in paragraph 1 most likely means:',
             '["A. unimportant","B. essential","C. temporary","D. optional"]', "B",
             "integral意为'不可或缺的、必需的'，文中指社交媒体已成为日常生活的重要组成部分。"),
            ("attitude", "What is the author\'s tone in this article?",
             '["A. Highly emotional","B. Objective and balanced","C. Sarcastic","D. Aggressively critical"]', "B",
             "作者客观分析了社交媒体的利弊，语气客观平衡。"),
        ],
        # === 词汇理解题目 ===
        "Smartphones and Modern Life": [
            ("banked_cloze", "第1空",
             '["essential","access","impact","constantly","reduced","balance","disconnect","significantly","manage","conscious","gradually","temporary","specific","academic","permanent"]', "essential",
             "essential part意为'不可或缺的部分'，智能手机已成为现代生活不可或缺的一部分。"),
            ("banked_cloze", "第2空",
             '["essential","access","impact","constantly","reduced","balance","disconnect","significantly","manage","conscious","gradually","temporary","specific","academic","permanent"]', "access",
             "easy access to information 意为'轻松获取信息'，access to 是固定搭配。"),
            ("banked_cloze", "第3空",
             '["essential","access","impact","constantly","reduced","balance","disconnect","significantly","manage","conscious","gradually","temporary","specific","academic","permanent"]', "impact",
             "impact on mental health 意为'对心理健康的影响'，impact on是常用搭配。"),
            ("banked_cloze", "第4空",
             '["essential","access","impact","constantly","reduced","balance","disconnect","significantly","manage","conscious","gradually","temporary","specific","academic","permanent"]', "constantly",
             "constantly check phones意为'频繁查看手机'，副词修饰动词check。"),
            ("banked_cloze", "第5空",
             '["essential","access","impact","constantly","reduced","balance","disconnect","significantly","manage","conscious","gradually","temporary","specific","academic","permanent"]', "reduced",
             "reduced concentration levels意为'注意力降低'，过去分词作形容词修饰名词。"),
            ("banked_cloze", "第6空",
             '["essential","access","impact","constantly","reduced","balance","disconnect","significantly","manage","conscious","gradually","temporary","specific","academic","permanent"]', "balance",
             "healthy balance between A and B意为'A与B之间的健康平衡'。"),
            ("banked_cloze", "第7空",
             '["essential","access","impact","constantly","reduced","balance","disconnect","significantly","manage","conscious","gradually","temporary","specific","academic","permanent"]', "disconnect",
             "disconnect from devices意为'从电子设备中抽离'，learn to do sth.后接动词原形。"),
            ("banked_cloze", "第8空",
             '["essential","access","impact","constantly","reduced","balance","disconnect","significantly","manage","conscious","gradually","temporary","specific","academic","permanent"]', "significantly",
             "significantly improve意为'显著改善'，副词修饰动词improve。"),
            ("banked_cloze", "第9空",
             '["essential","access","impact","constantly","reduced","balance","disconnect","significantly","manage","conscious","gradually","temporary","specific","academic","permanent"]', "manage",
             "manage our screen time wisely意为'明智地管理屏幕时间'，to后接动词原形。"),
            ("banked_cloze", "第10空",
             '["essential","access","impact","constantly","reduced","balance","disconnect","significantly","manage","conscious","gradually","temporary","specific","academic","permanent"]', "conscious",
             "make conscious use of意为'有意识地使用'，形容词修饰名词use。"),
        ],
        "Effective Study Strategies": [
            ("banked_cloze", "第1空",
             '["develop","perform","effective","distribute","review","retain","schedule","environment","organize","comprehension","abandon","complicate","neglect","exaggerate","postpone"]', "develop",
             "develop study habits意为'培养学习习惯'，动词develop表示'发展、培养'。"),
            ("banked_cloze", "第2空",
             '["develop","perform","effective","distribute","review","retain","schedule","environment","organize","comprehension","abandon","complicate","neglect","exaggerate","postpone"]', "perform",
             "perform better academically意为'学业表现更好'，perform表示'表现'。"),
            ("banked_cloze", "第3空",
             '["develop","perform","effective","distribute","review","retain","schedule","environment","organize","comprehension","abandon","complicate","neglect","exaggerate","postpone"]', "effective",
             "the most effective learning method意为'最有效的学习方法'，形容词最高级。"),
            ("banked_cloze", "第4空",
             '["develop","perform","effective","distribute","review","retain","schedule","environment","organize","comprehension","abandon","complicate","neglect","exaggerate","postpone"]', "distribute",
             "distribute study sessions over time意为'将学习时段分散在一段时间内'，distribute表示'分散、分布'。"),
            ("banked_cloze", "第5空",
             '["develop","perform","effective","distribute","review","retain","schedule","environment","organize","comprehension","abandon","complicate","neglect","exaggerate","postpone"]', "review",
             "review material at regular intervals意为'定期复习材料'，review表示'复习'。"),
            ("banked_cloze", "第6空",
             '["develop","perform","effective","distribute","review","retain","schedule","environment","organize","comprehension","abandon","complicate","neglect","exaggerate","postpone"]', "retain",
             "retain information意为'记住信息'，retain表示'保持、记住'。"),
            ("banked_cloze", "第7空",
             '["develop","perform","effective","distribute","review","retain","schedule","environment","organize","comprehension","abandon","complicate","neglect","exaggerate","postpone"]', "schedule",
             "study schedule意为'学习计划表'，名词。"),
            ("banked_cloze", "第8空",
             '["develop","perform","effective","distribute","review","retain","schedule","environment","organize","comprehension","abandon","complicate","neglect","exaggerate","postpone"]', "environment",
             "a quiet environment意为'安静的环境'，形容词+名词搭配。"),
            ("banked_cloze", "第9空",
             '["develop","perform","effective","distribute","review","retain","schedule","environment","organize","comprehension","abandon","complicate","neglect","exaggerate","postpone"]', "organize",
             "organize notes意为'整理笔记'，动词。"),
            ("banked_cloze", "第10空",
             '["develop","perform","effective","distribute","review","retain","schedule","environment","organize","comprehension","abandon","complicate","neglect","exaggerate","postpone"]', "comprehension",
             "deep comprehension of the subject意为'对学科的深刻理解'，名词。"),
        ],
        "Green Energy Revolution": [
            ("banked_cloze", "第1空",
             '["transition","implement","consumption","sustainable","emissions","alternative","invest","shift","unprecedented","revolution","abolish","decline","fluctuate","tolerate","withdraw"]', "transition",
             "global transition to renewable energy意为'全球向可再生能源的转型'，transition to是固定搭配。注意：词表中有两个sustainable，实际使用时应去重；此处sustainable为正确答案之一——更正：第1空应为transition。"),
            ("banked_cloze", "第2空",
             '["transition","implement","consumption","sustainable","emissions","alternative","invest","shift","unprecedented","revolution","abolish","decline","fluctuate","tolerate","withdraw"]', "implement",
             "implement policies意为'实施政策'，动词implement常与policy搭配。"),
            ("banked_cloze", "第3空",
             '["transition","implement","consumption","sustainable","emissions","alternative","invest","shift","unprecedented","revolution","abolish","decline","fluctuate","tolerate","withdraw"]', "consumption",
             "energy consumption意为'能源消耗'，名词短语。"),
            ("banked_cloze", "第4空",
             '["transition","implement","consumption","sustainable","emissions","alternative","invest","shift","unprecedented","revolution","abolish","decline","fluctuate","tolerate","withdraw"]', "sustainable",
             "sustainable alternatives意为'可持续的替代方案'，形容词修饰名词。"),
            ("banked_cloze", "第5空",
             '["transition","implement","consumption","sustainable","emissions","alternative","invest","shift","unprecedented","revolution","abolish","decline","fluctuate","tolerate","withdraw"]', "emissions",
             "carbon emissions意为'碳排放'，固定搭配。"),
            ("banked_cloze", "第6空",
             '["transition","implement","consumption","sustainable","emissions","alternative","invest","shift","unprecedented","revolution","abolish","decline","fluctuate","tolerate","withdraw"]', "sustainable",
             "sustainable development意为'可持续发展'，UN标准术语。注意：词表应去重，该空和4空均用sustainable。"),
            ("banked_cloze", "第7空",
             '["transition","implement","consumption","sustainable","emissions","alternative","invest","shift","unprecedented","revolution","abolish","decline","fluctuate","tolerate","withdraw"]', "invest",
             "invest heavily in green technology意为'大力投资绿色技术'，invest in是固定搭配。"),
            ("banked_cloze", "第8空",
             '["transition","implement","consumption","sustainable","emissions","alternative","invest","shift","unprecedented","revolution","abolish","decline","fluctuate","tolerate","withdraw"]', "shift",
             "the shift from A to B意为'从A到B的转变'，名词。"),
            ("banked_cloze", "第9空",
             '["transition","implement","consumption","sustainable","emissions","alternative","invest","shift","unprecedented","revolution","abolish","decline","fluctuate","tolerate","withdraw"]', "unprecedented",
             "unprecedented cooperation意为'前所未有的合作'，形容词修饰名词。"),
            ("banked_cloze", "第10空",
             '["transition","implement","consumption","sustainable","emissions","alternative","invest","shift","unprecedented","revolution","abolish","decline","fluctuate","tolerate","withdraw"]', "revolution",
             "energy revolution意为'能源革命'，名词总结全文主题。"),
        ],
    }
    for title, source, content, diff, topic, qtype in articles:
        existing = db.execute("SELECT id FROM reading_articles WHERE title=? LIMIT 1", (title,)).fetchone()
        if not existing:
            cur = db.execute(
                "INSERT INTO reading_articles (title, source, content, word_count, difficulty, topic, question_type) VALUES (?,?,?,?,?,?,?)",
                (title, source, content, len(content.split()), diff, topic, qtype)
            )
            article_id = cur.lastrowid
        else:
            article_id = existing['id']
            # 更新已有文章的 question_type
            db.execute("UPDATE reading_articles SET question_type=? WHERE id=?", (qtype, article_id))
        # Add questions if not exist
        if title in reading_qs:
            has_qs = db.execute("SELECT COUNT(*) as c FROM reading_questions WHERE article_id=?", (article_id,)).fetchone()['c']
            if has_qs == 0:
                _seed_reading_questions(db, article_id, reading_qs[title])


if __name__ == '__main__':
    seed()

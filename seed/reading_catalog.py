"""六话题×六难度阅读库的标杆样本与库存任务。

样本是根据公开权威信息重新撰写的本站原创练习，不是媒体原文或历年真题。
"""

import hashlib
import json


TOPICS = ('健康', '教育', '文化', '环境', '社会', '科技')
DIFFICULTIES = tuple(range(1, 7))
TARGET_UNREAD_PER_CELL = 5
GENERATOR_VERSION = 'cet-reading-curator/1.0.1'


GOLDEN_ARTICLES = [
    {
        'title': 'Small Health Choices That Last', 'topic': '健康', 'difficulty': 1,
        'source': '题材参考：新华社英文网',
        'source_url': 'https://english.news.cn/20260102/7750bcffbde844d885326071652da381/c.html',
        'source_title': 'China Focus: Healthy living trending in China',
        'source_published_at': '2026-01-02',
        'content': (
            'Many people try to become healthier by making a long list of difficult rules. '
            'However, small actions are often easier to repeat. A short walk after lunch, a glass '
            'of water before a sweet drink, or an earlier bedtime can fit into an ordinary day. '
            'The value of these actions does not come from doing them once. It comes from turning '
            'them into habits. Keeping a simple record can make progress visible without turning '
            'health into a competition.\n\nA useful plan begins with one clear goal. Someone who wants to '
            'move more may decide to walk for ten minutes every evening. The goal is simple enough '
            'to remember and easy to measure. After several weeks, the person can add more time if '
            'the habit feels natural. Missing one day is not a reason to stop. Returning the next '
            'day matters more than being perfect.\n\nHealth information is everywhere, but not every '
            'suggestion suits every person. People with medical concerns should ask a qualified '
            'professional before making major changes. For most people, a modest action that can be '
            'continued is more useful than an extreme plan that is quickly abandoned.'
        ),
        'questions': [
            ('main_idea', 'What is the passage mainly about?', ['Why strict diets always fail', 'How small repeatable actions support health', 'Why people need expensive equipment', 'How to become perfect in one week'], 'B', '文章反复强调小而可持续的行动。', 'small actions are often easier to repeat'),
            ('detail', 'What does the passage suggest doing after a habit feels natural?', ['Stopping the plan', 'Choosing a new doctor', 'Adding more time gradually', 'Writing more rules'], 'C', '第二段说习惯自然后可以增加时间。', 'the person can add more time'),
            ('inference', 'Why is a ten-minute walk used as an example?', ['It is a manageable and measurable goal', 'It replaces all medical treatment', 'It is the only useful exercise', 'It guarantees quick weight loss'], 'A', '该例子用来说明目标需要简单、易记且可测量。', 'simple enough to remember and easy to measure'),
            ('word_guess', 'The word "modest" in the last paragraph is closest in meaning to:', ['costly', 'limited and reasonable', 'secret', 'unusual'], 'B', '根据与 extreme plan 的对比，modest 表示适度的。', 'a modest action'),
            ('attitude', 'What is the author\'s attitude toward missing one day?', ['It ruins the whole plan', 'It should be hidden', 'It is acceptable if the person returns', 'It proves the goal is wrong'], 'C', '作者认为偶尔中断并不意味着失败，重要的是恢复。', 'Returning the next day matters more'),
        ],
    },
    {
        'title': 'Using AI in Class with Clear Boundaries', 'topic': '教育', 'difficulty': 2,
        'source': '题材参考：中国政府网英文版',
        'source_url': 'https://english.www.gov.cn/news/202503/19/content_WS67dac09fc6d0868f4e8f0f94.html',
        'source_title': 'AI innovates China\'s education landscape',
        'source_published_at': '2025-03-19',
        'content': (
            'Artificial intelligence can help teachers notice patterns that are difficult to see '
            'during a busy lesson. If many students make the same mistake, a digital system can '
            'collect the answers and show the teacher where extra explanation is needed. It can '
            'also provide additional practice at different levels.\n\nThese advantages do not mean '
            'that software should make every classroom decision. A score cannot always explain why '
            'a learner is confused, and a suggested exercise may not fit the mood or needs of a '
            'particular class. Teachers still have to interpret the information, talk with students '
            'and decide what to do next. The same pattern can have different causes: one student '
            'may have missed an earlier idea, while another may understand the idea but misread the '
            'question. A useful report should begin a conversation, not end it.\n\nClear rules are therefore important. Students should know '
            'when AI assistance is allowed, what data a tool collects and which work must remain '
            'their own. Schools also need alternatives for learners who cannot or do not wish to use '
            'a particular service. Used in this way, AI becomes a supporting instrument rather than '
            'a replacement for judgment. The goal is not to automate learning, but to give teachers '
            'more time for the human parts of education.'
        ),
        'questions': [
            ('detail', 'What can an AI system show when many students make the same mistake?', ['Which students should leave school', 'Where more explanation may be needed', 'How to remove the lesson', 'Why scores should be hidden'], 'B', '第一段明确说系统能帮教师发现需要额外讲解的地方。', 'where extra explanation is needed'),
            ('inference', 'Why must teachers interpret AI information?', ['Digital systems never collect answers', 'A score may not reveal the cause of confusion', 'Students dislike all technology', 'Every class uses the same method'], 'B', '分数无法总是解释学生困惑的原因。', 'A score cannot always explain why'),
            ('detail', 'Which issue should students understand before using an AI tool?', ['The tool\'s office address', 'The teacher\'s private notes', 'What data the tool collects', 'The price of every computer'], 'C', '第三段列出了数据收集的透明要求。', 'what data a tool collects'),
            ('word_guess', 'The word "alternatives" most nearly means:', ['other available choices', 'final examinations', 'strict punishments', 'technical errors'], 'A', '语境表明学校需为不使用特定服务的学生提供其他选择。', 'Schools also need alternatives'),
            ('main_idea', 'Which statement best expresses the author\'s view?', ['AI should replace classroom teachers', 'AI is useful when guided by human judgment and clear rules', 'Schools should avoid collecting any learning data', 'Students should use AI for every assignment'], 'B', '全文主张把 AI 作为有边界的辅助工具。', 'a supporting instrument rather than a replacement'),
        ],
    },
    {
        'title': 'Why Free Museums Still Need Good Design', 'topic': '文化', 'difficulty': 3,
        'source': '题材参考：China Daily',
        'source_url': 'https://global.chinadaily.com.cn/a/202505/19/WS682a8789a310a04af22c01e3.html',
        'source_title': 'Museums celebrated around the country',
        'source_published_at': '2025-05-19',
        'content': (
            'Free admission can remove an important barrier between museums and the public, but an '
            'open door does not automatically create a meaningful visit. People also need clear '
            'signs, understandable explanations and places where they can pause. Without these '
            'features, a large collection may feel like a room full of unrelated objects.\n\nGood '
            'museum design builds a path through the material. A short introduction gives visitors '
            'a question to keep in mind. Carefully chosen objects then provide evidence, while maps '
            'or digital displays help connect one period with another. Interactive technology can '
            'be useful, but only when it serves the story. A bright screen that competes with an '
            'artifact may reduce attention instead of increasing it.\n\nMuseums also serve people '
            'with different amounts of time and background knowledge. A family may want a clear '
            'forty-minute route, while a specialist may spend an afternoon with one gallery. Layered '
            'information can support both: a short label offers the main point, and optional detail '
            'rewards closer study. This approach also helps visitors who are unfamiliar with the '
            'language or context of a collection. Instead of forcing everyone through the same '
            'amount of text, the exhibition lets each person choose a workable route and still '
            'understand the central story.\n\nThe success of a public museum should therefore be measured by '
            'more than visitor numbers. It should also ask whether people can explain what they saw, '
            'connect it with a larger history and feel that the collection belongs in public life.'
        ),
        'questions': [
            ('main_idea', 'What is the passage mainly concerned with?', ['How museums can make free access meaningful', 'Why all artifacts should be digital', 'How specialists avoid family visitors', 'Why museum tickets should be expensive'], 'A', '文章讨论免费之后如何通过设计使参观真正有价值。', 'an open door does not automatically create a meaningful visit'),
            ('detail', 'What role does a short introduction play?', ['It replaces all object labels', 'It gives visitors a guiding question', 'It advertises the museum shop', 'It limits the time in each room'], 'B', '第二段说简短导言会给观众一个贯穿参观的问题。', 'gives visitors a question to keep in mind'),
            ('inference', 'Why can a bright screen be unhelpful?', ['It may draw attention away from the artifact', 'It is always difficult to operate', 'It contains too much historical evidence', 'It makes admission more expensive'], 'A', '原文说屏幕与文物争夺注意力时会降低而非增加关注。', 'competes with an artifact'),
            ('word_guess', 'The word "Layered" in paragraph 3 suggests information that:', ['is hidden from all visitors', 'is offered at different depths', 'is arranged only by date', 'is printed in several colors'], 'B', '后文用简标签与可选详情说明分层信息。', 'a short label offers the main point, and optional detail'),
            ('attitude', 'How does the author view visitor numbers?', ['They are the only reliable measure', 'They should never be recorded', 'They matter but are not enough', 'They mainly help specialists'], 'C', '末段明确表示成功不应只看参观人数。', 'measured by more than visitor numbers'),
        ],
    },
    {
        'title': 'Wetlands as Working Urban Infrastructure', 'topic': '环境', 'difficulty': 4,
        'source': '题材参考：新华社英文网',
        'source_url': 'https://english.news.cn/20250926/630fa17fd60a428bb29335a8157db6ca/dac35695fa1e47a3b05737d70ca6e82b.pdf',
        'source_title': 'Public information on ecological restoration in the Yangtze River basin',
        'source_published_at': '2025-09-26',
        'content': (
            'Urban wetlands are sometimes treated as empty land waiting for construction. In fact, '
            'they can perform several jobs that cities would otherwise have to pay for separately. '
            'Wetland soil and plants slow storm water, store part of it and reduce pressure on '
            'drainage systems. The same area may cool nearby neighborhoods and provide habitat for '
            'birds and insects.\n\nThese benefits, however, do not appear simply because a project is '
            'called a wetland park. A healthy wetland depends on water moving through it at suitable '
            'times and in suitable amounts. If designers isolate it from the wider river system, '
            'decorate it with a few plants and rely heavily on pumps, the result may require constant '
            'maintenance while offering limited ecological value.\n\nSuccessful restoration therefore '
            'begins with the landscape rather than with a visual plan. Engineers, ecologists and '
            'local residents need to understand where water came from, where it can safely go and '
            'how the site changes between wet and dry seasons. Public access should also be managed. '
            'Paths and observation areas can help people enjoy the wetland without disturbing its '
            'most sensitive parts. Monitoring must continue after construction because a site that '
            'works during one rainy season may behave differently after nearby roads or buildings '
            'change the direction of water. Long-term measurements allow managers to adjust gates, '
            'planting and visitor routes before a small problem becomes a costly failure across '
            'several years and storms.\n\nThinking '
            'of wetlands as infrastructure changes how decisions are '
            'made. The question is no longer whether a city can spare land for nature, but which '
            'combination of natural and built systems can manage risk most effectively over time.'
        ),
        'questions': [
            ('detail', 'Which urban problem can wetlands help reduce?', ['A shortage of office buildings', 'Pressure on drainage systems', 'The cost of public transport', 'Noise inside factories'], 'B', '首段说湿地可减慢并储存雨水，减轻排水压力。', 'reduce pressure on drainage systems'),
            ('inference', 'What is implied about a wetland that relies heavily on pumps?', ['It may be ecologically weak and costly to maintain', 'It will always attract more birds', 'It cannot be visited by the public', 'It is naturally connected to a river'], 'A', '第二段将重度依靠水泵与持续维护、生态价值有限联系起来。', 'require constant maintenance while offering limited ecological value'),
            ('detail', 'What should restoration teams study first?', ['The color of park signs', 'The history and seasonal movement of water', 'The number of nearby offices', 'The price of imported plants'], 'B', '第三段要求首先理解水的来源、去向与季节变化。', 'understand where water came from'),
            ('word_guess', 'The word "spare" in the last paragraph is closest in meaning to:', ['protect by law', 'make available', 'measure exactly', 'sell quickly'], 'B', '语境中 spare land 指城市是否能腾出、提供土地。', 'whether a city can spare land'),
            ('main_idea', 'Which title best captures the author\'s argument?', ['Wetlands Should Be Designed Only for Visitors', 'Natural Systems Can Be Part of City Infrastructure', 'Pumps Are the Best Answer to Urban Flooding', 'All Empty Urban Land Should Become Parks'], 'B', '全文核心是把湿地视为可执行城市功能的基础设施。', 'Thinking of wetlands as infrastructure'),
        ],
    },
    {
        'title': 'Digital Services Are Useful Only When People Can Reach Them', 'topic': '社会', 'difficulty': 5,
        'source': '题材参考：中国政府网英文版',
        'source_url': 'https://english.www.gov.cn/news/202504/27/content_WS680de811c6d0868f4e8f21c2.html',
        'source_title': 'China unveils 2025 plan to boost digital literacy, skills',
        'source_published_at': '2025-04-27',
        'content': (
            'Moving public services online can save time for both citizens and institutions. A '
            'resident may renew a document without travelling across town, while staff can process '
            'routine requests more efficiently. Yet the apparent convenience of a digital service '
            'can conceal a difficult question: convenient for whom?\n\nAccess involves more than '
            'owning a phone. Users must understand the instructions, trust the way their information '
            'is handled and recover when they press the wrong button. Older residents, people with '
            'limited literacy and those who depend on accessibility tools may encounter different '
            'barriers. A system designed around a confident, experienced user can turn an ordinary '
            'task into a chain of avoidable failures.\n\nInclusive services offer several routes to '
            'the same result. Clear language and visible progress help everyone, while staffed '
            'telephone lines or physical counters remain essential for cases that cannot be solved '
            'online. Community training can build confidence, but it should not shift the entire '
            'burden onto the user. Institutions still have a duty to test whether their systems work '
            'for the people most likely to struggle. Such testing should follow complete journeys '
            'rather than isolated screens. A form may look clear but still fail if a verification '
            'message arrives too late, if help disappears after an error, or if the final document '
            'cannot be downloaded on an older device. Feedback also needs to reach the team that can '
            'change the service. Otherwise, a complaint becomes another task for the user rather '
            'than evidence for institutional improvement. Accessibility is therefore not a final '
            'technical check. It is an ongoing way of measuring whether a public promise can be '
            'completed in practice.\n\nThe aim of digital government is not to '
            'maximize the number of online forms. It is to make public help easier to obtain. A '
            'service should therefore be judged by completed tasks, error recovery and equal access, '
            'not merely by how modern its interface appears.'
        ),
        'questions': [
            ('main_idea', 'What central question does the passage raise about digital public services?', ['Whether they reduce the number of government workers', 'Whether their convenience is accessible to different users', 'Whether every form should use the same color', 'Whether phones should replace computers'], 'B', '文章围绕数字便利是否真正对不同人群可达展开。', 'convenient for whom'),
            ('inference', 'Why does the author mention pressing the wrong button?', ['To show that users need a way to recover from errors', 'To argue that phones are poorly manufactured', 'To recommend removing all buttons', 'To prove physical counters are faster'], 'A', '该细节说明可恢复性是真实可用性的一部分。', 'recover when they press the wrong button'),
            ('detail', 'According to the passage, why should physical counters remain?', ['They make interfaces appear modern', 'Some cases cannot be completed online', 'They collect more personal data', 'They eliminate the need for clear language'], 'B', '第三段直接说有些情况无法在线解决。', 'cases that cannot be solved online'),
            ('word_guess', 'The word "burden" in paragraph 3 most nearly refers to:', ['the responsibility and difficulty', 'the financial profit', 'the software update', 'the public building'], 'A', '上下文指机构不能把适应系统的全部责任压给用户。', 'shift the entire burden onto the user'),
            ('attitude', 'Which measure would the author most likely support?', ['Counting online forms as the main sign of success', 'Closing every offline channel immediately', 'Testing whether vulnerable users can finish real tasks', 'Designing only for experienced users'], 'C', '作者主张用任务完成、错误恢复和平等可达性评估服务。', 'test whether their systems work for the people most likely to struggle'),
        ],
    },
    {
        'title': 'When Robots Leave Controlled Spaces', 'topic': '科技', 'difficulty': 6,
        'source': '题材参考：新华社英文网',
        'source_url': 'https://english.news.cn/20260413/1b987d983a0f4d94af1583f1872a8326/c.html',
        'source_title': 'China Focus: How technology is rewiring China\'s health system',
        'source_published_at': '2026-04-13',
        'content': (
            'Industrial robots became reliable partly because factories were reorganized around '
            'them. Floors were level, objects arrived in predictable positions and people were kept '
            'outside carefully marked zones. New service robots face the opposite environment. A '
            'hospital corridor, railway station or apartment contains moving people, incomplete '
            'information and countless exceptions to any prepared rule.\n\nThis difference shifts '
            'the engineering challenge from repeating a precise motion to managing uncertainty. A '
            'robot must recognize when its map is outdated, decide when confidence is too low and '
            'hand control to a person before a minor error becomes dangerous. Improving average '
            'accuracy is not enough if the remaining failures are rare but severe. Designers need '
            'to know which mistakes occur, under what conditions and whether users can understand '
            'the machine\'s limits.\n\nDeployment therefore changes the technology itself. Data from '
            'real environments reveals situations that laboratory tests did not anticipate, but '
            'collecting such data raises questions about privacy and consent. Rules for storage, '
            'review and deletion must be part of the system rather than an afterthought. Human '
            'workers also need authority to pause the robot without being penalized for slowing an '
            'automated process. Responsibility cannot be assigned only after an accident. Before '
            'deployment, an organization must decide who reviews warnings, who can approve a change '
            'and how an affected person can challenge an automated action. Those arrangements may '
            'seem less exciting than a demonstration, yet they determine whether technical feedback '
            'actually improves the system. They also prevent a familiar problem: every participant '
            'assumes that someone else is watching the machine.\n\nEvaluation should therefore use '
            'more than a single success rate. Researchers can examine near misses, recovery time, '
            'the quality of handovers and the ability of workers to predict robot behavior. A system '
            'that completes slightly fewer tasks but fails transparently may be safer than one with '
            'a higher average score and poorly understood exceptions. This broader evidence makes '
            'comparisons slower, but it makes them far more useful outside the laboratory.\n\nThe most '
            'successful service robot may not be the one that appears '
            'most independent. It may be the one that communicates uncertainty clearly, requests '
            'help at the right moment and fits into a wider network of human responsibility.'
        ),
        'questions': [
            ('inference', 'Why were early industrial robots easier to make reliable?', ['They could understand every exception', 'Their environments were made predictable', 'They collected personal data', 'They worked without precise movement'], 'B', '首段说工厂为机器人重组，环境平整且可预测。', 'factories were reorganized around them'),
            ('main_idea', 'What is the passage mainly arguing?', ['Service robots should copy factory robots exactly', 'Robot autonomy matters more than human responsibility', 'Reliable service robots must manage uncertainty within human systems', 'Laboratory testing should be abandoned'], 'C', '全文强调现实不确定性、人机交接与责任网络。', 'fits into a wider network of human responsibility'),
            ('detail', 'What should a robot do when its confidence becomes too low?', ['Increase its speed', 'Delete its map', 'Transfer control to a person', 'Ignore unusual conditions'], 'C', '第二段明确要求信心不足时向人交接。', 'hand control to a person'),
            ('inference', 'Why is average accuracy an incomplete measure?', ['Some uncommon errors may have serious consequences', 'Users never care about accuracy', 'Robots make only frequent mistakes', 'Accuracy cannot be calculated in factories'], 'A', '原文指出剩余错误即使少见也可能后果严重。', 'remaining failures are rare but severe'),
            ('attitude', 'Which robot would the author probably consider most successful?', ['One that hides uncertainty from users', 'One that never allows workers to pause it', 'One that appears independent in demonstrations', 'One that seeks human help appropriately'], 'D', '末段直接把正确求助与明确表达不确定性视为成功标志。', 'requests help at the right moment'),
        ],
    },
]


def _content_hash(content):
    return hashlib.sha256(content.strip().encode('utf-8')).hexdigest()


def seed_reading_catalog(conn):
    for article in GOLDEN_ARTICLES:
        existing = conn.execute(
            "SELECT id,origin,content_hash,inventory_status FROM reading_articles WHERE content_hash=? OR title=? LIMIT 1",
            (_content_hash(article['content']), article['title']),
        ).fetchone()
        if existing:
            completed = conn.execute(
                "SELECT 1 FROM practice_sessions WHERE module='reading' AND CAST(source_id AS TEXT)=CAST(? AS TEXT) LIMIT 1",
                (existing['id'],),
            ).fetchone()
            if existing['origin'] != 'golden_sample' or completed or existing['inventory_status'] == 'completed' or existing['content_hash'] == _content_hash(article['content']):
                continue
            article_id = existing['id']
            conn.execute(
                """UPDATE reading_articles SET source=?,content=?,word_count=?,difficulty=?,topic=?,
                   source_url=?,source_title=?,source_published_at=?,adaptation_notes=?,content_hash=?,
                   generator_version=?,inventory_status='available' WHERE id=?""",
                (
                    article['source'], article['content'], len(article['content'].split()),
                    article['difficulty'], article['topic'], article['source_url'], article['source_title'],
                    article['source_published_at'], '题材参考所列公开信息；本站原创改写，非媒体原文，非历年真题。',
                    _content_hash(article['content']), GENERATOR_VERSION, article_id,
                ),
            )
            conn.execute("DELETE FROM reading_questions WHERE article_id=?", (article_id,))
        else:
            cursor = conn.execute(
                """INSERT INTO reading_articles
                   (title,source,content,word_count,difficulty,topic,question_type,date_added,
                    source_url,source_title,source_published_at,retrieved_at,adaptation_notes,
                    content_hash,generator_version,origin,inventory_status)
                   VALUES (?,?,?,?,?,?,'careful_reading',date('now'),?,?,?,datetime('now','localtime'),?,?,?,?, 'available')""",
                (
                    article['title'], article['source'], article['content'], len(article['content'].split()),
                    article['difficulty'], article['topic'], article['source_url'], article['source_title'],
                    article['source_published_at'], '题材参考所列公开信息；本站原创改写，非媒体原文，非历年真题。',
                    _content_hash(article['content']), GENERATOR_VERSION, 'golden_sample',
                ),
            )
            article_id = cursor.lastrowid
        conn.executemany(
            """INSERT INTO reading_questions
               (article_id,question_type,question,options,answer,explanation,evidence_text)
               VALUES (?,?,?,?,?,?,?)""",
            [
                (article_id, qtype, question, json.dumps(options, ensure_ascii=False), answer, explanation, evidence)
                for qtype, question, options, answer, explanation, evidence in article['questions']
            ],
        )
    conn.execute("""UPDATE reading_articles
                    SET source_name=CASE WHEN COALESCE(source_name,'')=''
                        THEN replace(source,'题材参考：','') ELSE source_name END,
                        adaptation_note=CASE WHEN COALESCE(adaptation_note,'')=''
                            THEN adaptation_notes ELSE adaptation_note END
                    WHERE origin='golden_sample'""")
    from seed.reading_corpus_loader import approved_reading_corpus_available, seed_static_reading_corpus
    if approved_reading_corpus_available():
        seed_static_reading_corpus(conn, TOPICS, DIFFICULTIES, TARGET_UNREAD_PER_CELL)
    else:
        # A rejected draft corpus may already exist in a user's database from
        # an earlier build.  Preserve every row for audit, but never expose it
        # as unread inventory.  Rows with learning history are frozen rather
        # than rewritten or removed.
        conn.execute(
            """UPDATE reading_articles
               SET inventory_status=CASE WHEN EXISTS (
                     SELECT 1 FROM practice_sessions p WHERE p.module='reading'
                       AND CAST(p.source_id AS TEXT)=CAST(reading_articles.id AS TEXT)
                   ) THEN 'completed' ELSE 'quarantined' END
               WHERE origin='curated_corpus'"""
        )


def ensure_reading_inventory_jobs(conn):
    conn.execute(
        "INSERT OR IGNORE INTO user_settings (key,value) VALUES ('reading_refill_enabled','0')"
    )
    for topic in TOPICS:
        for difficulty in DIFFICULTIES:
            ready = conn.execute(
                """SELECT COUNT(*) AS c FROM reading_articles a
                   WHERE a.question_type='careful_reading' AND a.topic=? AND a.difficulty=?
                     AND a.inventory_status='available'
                     AND NOT EXISTS (
                         SELECT 1 FROM practice_sessions p
                         WHERE p.module='reading' AND CAST(p.source_id AS TEXT)=CAST(a.id AS TEXT)
                     )
                     AND (SELECT COUNT(*) FROM reading_questions q WHERE q.article_id=a.id)=5""",
                (topic, difficulty),
            ).fetchone()['c']
            active_jobs = conn.execute(
                """SELECT COUNT(*) AS c FROM reading_generation_jobs
                   WHERE topic=? AND difficulty=? AND question_type='careful_reading'
                     AND status IN ('pending','running','paused_budget','paused_config')""",
                (topic, difficulty),
            ).fetchone()['c']
            missing = max(0, TARGET_UNREAD_PER_CELL - ready - active_jobs)
            key_prefix = f'bootstrap:v2:{topic}:{difficulty}:'
            prior_v2 = conn.execute(
                "SELECT COUNT(*) AS c FROM reading_generation_jobs WHERE idempotency_key LIKE ?",
                (key_prefix + '%',),
            ).fetchone()['c']
            for slot in range(missing):
                # Versioned monotonic keys let a terminal failed/completed job
                # keep its audit identity without permanently blocking a new
                # deficit job for the same cell.
                key = f'{key_prefix}{prior_v2 + slot + 1}'
                conn.execute(
                    """INSERT OR IGNORE INTO reading_generation_jobs
                       (topic,difficulty,question_type,idempotency_key)
                       VALUES (?,?,'careful_reading',?)""",
                    (topic, difficulty, key),
                )

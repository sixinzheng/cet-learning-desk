"""四六级「单词专练」选词填空题库种子（Banked Cloze）。

每篇为一篇文章，挖空处用 {{序号}} 占位；每个空给出原形词 base_word，
用户需填入该词的正确变形 answer（词形变化）。候选词池 = 所有 base_word + 2 个干扰词 distractor。
hint 只给出原形词的中文词义，绝不含变形/时态/比较级等提示，避免泄露答案。
重复启动不会重复插入。
"""
import json


# blanks: (顺序号, base_word 原形词, answer 正确变形, hint 纯词义提示)
CLOZE_PASSAGES = [
    {
        'title': 'The Value of Daily Reading',
        'difficulty': 3,
        'level': 'cet4',
        'content':
            'Many students find it hard to keep a reading habit, yet the benefits are easy to {{1}}. '
            'Research shows that people who read for twenty minutes a day {{2}} their vocabulary faster '
            'than those who do not. When we read, we are {{3}} to words in real sentences rather than in '
            'word lists. This helps us remember them for a {{4}} time. A daily reading routine also {{5}} '
            'our attention span, which is a key skill for study and work. In addition, reading exposes us '
            'to different {{6}} and ways of thinking. Even a short story can provide a {{7}} look at another '
            "person's life. If you want to improve your English, make reading a {{8}} part of your day.",
        'blanks': [
            (1, 'benefit', 'benefits', '使受益；好处'),
            (2, 'expand', 'expand', '扩大；扩充'),
            (3, 'expose', 'exposed', '使接触；使暴露'),
            (4, 'long', 'longer', '长的'),
            (5, 'improve', 'improves', '改进；提高'),
            (6, 'culture', 'cultures', '文化'),
            (7, 'close', 'closer', '近的；亲密的'),
            (8, 'regular', 'regularly', '有规律的；定期的'),
        ],
        'distractors': ['interfere', 'assemble'],
    },
    {
        'title': 'Why Sleep Matters',
        'difficulty': 4,
        'level': 'cet4',
        'content':
            'Most students know that sleep is important, but few realize how much it {{1}} their learning. '
            'During sleep, the brain {{2}} the information gained during the day and moves it into long-term '
            'memory. A tired mind is far less {{3}} than a rested one. When we stay up late to study, we '
            'often {{4}} ourselves from the very time we need. One study found that students who slept '
            'enough scored {{5}} on tests than those who did not. Researchers also {{6}} that a short nap '
            'in the afternoon can {{7}} the effect of a lost night. Sleep, in other words, is not a waste '
            'of time but a {{8}} part of learning.',
        'blanks': [
            (1, 'affect', 'affects', '影响'),
            (2, 'process', 'processes', '处理；加工'),
            (3, 'effective', 'effective', '有效的'),
            (4, 'rob', 'rob', '剥夺'),
            (5, 'high', 'higher', '高的'),
            (6, 'find', 'found', '发现'),
            (7, 'reduce', 'reduce', '减少'),
            (8, 'necessary', 'necessary', '必要的'),
        ],
        'distractors': ['assume', 'decline'],
    },
    {
        'title': 'The Rise of Online Learning',
        'difficulty': 5,
        'level': 'cet6',
        'content':
            'The growth of online learning has {{1}} the way people think about education. No longer are '
            'students {{2}} to a single classroom. With a laptop and a connection, a learner can access '
            'courses from universities around the world. Yet this freedom also {{3}} a new set of problems. '
            'Without a fixed schedule, many students find it difficult to remain {{4}}. Some researchers '
            '{{5}} that the lack of face-to-face interaction may {{6}} social skills. Nevertheless, the '
            'trend is unlikely to be {{7}} back. The challenge, then, is to combine the {{8}} of online '
            'study with the discipline of traditional learning.',
        'blanks': [
            (1, 'transform', 'transformed', '改变；转变'),
            (2, 'limit', 'limited', '限制'),
            (3, 'create', 'creates', '创造'),
            (4, 'discipline', 'disciplined', '纪律；自律'),
            (5, 'warn', 'warn', '警告'),
            (6, 'weaken', 'weaken', '削弱'),
            (7, 'turn', 'turned', '扭转'),
            (8, 'flexible', 'flexibility', '灵活的；可变通的'),
        ],
        'distractors': ['overlook', 'emerge'],
    },
    {
        'title': 'The Science of Motivation',
        'difficulty': 6,
        'level': 'cet6',
        'content':
            'Motivation is often described as an internal fire, but psychologists {{1}} it as a more '
            'complicated process. In one view, we are driven by a need to {{2}} our goals, while in another, '
            'we are pushed by a fear of {{3}}. The difference matters, because external pressure tends to '
            'produce {{4}} results. Studies of language learners show that those who study for pleasure '
            '{{5}} longer and remember more than those who study only for exams. A practical lesson is that '
            'motivation works best when it is {{6}} into small, daily actions. When we set a goal we '
            'can actually meet, the effort feels {{7}} rather than painful, and progress becomes easier '
            'to {{8}}.',
        'blanks': [
            (1, 'describe', 'describe', '描述'),
            (2, 'achieve', 'achieve', '达到；实现'),
            (3, 'fail', 'failure', '失败'),
            (4, 'bad', 'worse', '坏的；差的'),
            (5, 'persist', 'persist', '坚持'),
            (6, 'break', 'broken', '打破；分解'),
            (7, 'manage', 'manageable', '管理；掌控'),
            (8, 'track', 'track', '追踪'),
        ],
        'distractors': ['imply', 'withdraw'],
    },
]


def seed_cloze_catalog(conn):
    """写入选词填空题库；重复启动不会重复插入。"""
    if conn.execute("SELECT COUNT(*) FROM cloze_passages").fetchone()[0]:
        return
    for passage in CLOZE_PASSAGES:
        cur = conn.execute(
            'INSERT INTO cloze_passages (title, difficulty, level, content, distractors) '
            'VALUES (?, ?, ?, ?, ?)',
            (passage['title'], passage['difficulty'], passage['level'],
             passage['content'], json.dumps(passage['distractors'], ensure_ascii=False)),
        )
        passage_id = cur.lastrowid
        for order, base_word, answer, hint in passage['blanks']:
            conn.execute(
                'INSERT INTO cloze_blanks (passage_id, blank_order, base_word, answer, hint) '
                'VALUES (?, ?, ?, ?, ?)',
                (passage_id, order, base_word, answer, hint),
            )

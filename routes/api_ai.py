import json
import re
import secrets
import uuid
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, Response, jsonify, request, session, stream_with_context

from config import delete_api_key, get_api_key, get_api_key_status, load_config, save_api_key
from database import get_db
from services.ai_service import AIServiceError, MODEL, call_deepseek, stream_deepseek, fetch_deepseek_balance, generate_reading_questions, generate_cloze_questions, call_multimodal, grade_reading_questions
from services.level_service import LEVEL_NAMES, evaluate_level
from services.skill_service import (
    create_custom_skill, delete_custom_skill, get_site_skill, list_site_skills,
    skill_prompt, update_site_skill,
)


bp = Blueprint('ai', __name__)


def _csrf_token():
    if not session.get('ai_csrf_token'):
        session['ai_csrf_token'] = secrets.token_urlsafe(24)
    return session['ai_csrf_token']


def _require_csrf(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        origin = request.headers.get('Origin')
        if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
            return jsonify({'error': '请求来源不受信任。'}), 403
        if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), _csrf_token()):
            return jsonify({'error': '安全令牌已失效，请刷新页面后重试。'}), 403
        return view(*args, **kwargs)
    return wrapped


def _balance_payload(data):
    balances = []
    for item in data.get('balance_infos', []):
        balances.append({
            'currency': item.get('currency', ''),
            'total': item.get('total_balance', '0'),
            'granted': item.get('granted_balance', '0'),
            'topped_up': item.get('topped_up_balance', '0'),
        })
    return {'available': bool(data.get('is_available')), 'balances': balances}


@bp.route('/config/status')
def config_status():
    cfg = load_config()
    storage = get_api_key_status()
    db = get_db()
    spend = db.execute(
        "SELECT COALESCE(SUM(cost_cny),0) AS cost FROM ai_usage_events "
        "WHERE created_at >= datetime('now','localtime','-83 days','start of day')"
    ).fetchone()['cost']
    db.close()
    return jsonify({
        **storage,
        'model': MODEL,
        'verified_at': cfg.get('deepseek_verified_at', ''),
        'tracked_cost_cny_84': round(float(spend or 0), 6),
        'csrf_token': _csrf_token(),
    })


@bp.route('/config/verify-save', methods=['POST'])
@_require_csrf
def verify_and_save():
    value = str((request.json or {}).get('api_key', '')).strip()
    if len(value) < 12:
        return jsonify({'error': '请输入完整的 DeepSeek API Key。'}), 400
    try:
        balance = fetch_deepseek_balance(value)
        verified_at = datetime.now().isoformat(timespec='seconds')
        storage = save_api_key(value, verified_at)
        return jsonify({
            'ok': True, 'configured': True, 'key_suffix': value[-4:],
            'model': MODEL, 'verified_at': verified_at,
            'balance': _balance_payload(balance),
            'storage_backend': storage.get('storage_backend', 'dpapi_fallback'),
            'recovery_required': False,
        })
    except AIServiceError as exc:
        return jsonify({'error': str(exc), 'code': exc.code}), exc.status


@bp.route('/config', methods=['DELETE'])
@_require_csrf
def remove_config():
    delete_api_key()
    return jsonify({'ok': True, 'configured': False})


@bp.route('/skills')
def skills_index():
    return jsonify({'skills': list_site_skills(), 'csrf_token': _csrf_token()})


@bp.route('/skills', methods=['POST'])
@_require_csrf
def create_skill():
    payload = request.json or {}
    try:
        item = create_custom_skill(
            payload.get('display_name'), payload.get('description', ''),
            payload.get('user_instructions', ''),
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'ok': True, 'skill': item}), 201


@bp.route('/skills/<slug>', methods=['PUT'])
@_require_csrf
def update_skill(slug):
    try:
        item = update_site_skill(slug, request.json or {})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if not item:
        return jsonify({'error': '没有找到这个 Skill。'}), 404
    return jsonify({'ok': True, 'skill': item})


@bp.route('/skills/<slug>', methods=['DELETE'])
@_require_csrf
def delete_skill(slug):
    deleted, reason = delete_custom_skill(slug)
    if deleted:
        return jsonify({'ok': True})
    if reason == 'builtin':
        return jsonify({'error': '内置 Skill 不能删除，可以关闭。'}), 409
    return jsonify({'error': '没有找到这个 Skill。'}), 404


@bp.route('/balance')
def balance():
    try:
        return jsonify(_balance_payload(fetch_deepseek_balance()))
    except AIServiceError as exc:
        return jsonify({'error': str(exc), 'code': exc.code}), exc.status


def _learning_snapshot():
    db = get_db()
    today = date.today().isoformat()
    recent_7 = db.execute(
        "SELECT COUNT(*) AS days, COALESCE(SUM(total_minutes),0) AS minutes, "
        "COALESCE(SUM(new_words_count),0) AS new_words, COALESCE(SUM(review_words_count),0) AS reviews "
        "FROM study_logs WHERE study_date >= date('now','localtime','-6 days')"
    ).fetchone()
    recent_28 = db.execute(
        "SELECT COUNT(*) AS days, COALESCE(SUM(total_minutes),0) AS minutes FROM study_logs "
        "WHERE study_date >= date('now','localtime','-27 days')"
    ).fetchone()
    last = db.execute(
        "SELECT study_date FROM study_logs WHERE "
        "new_words_count+review_words_count+reading_count+listening_count+writing_count+grammar_count+total_minutes>0 "
        "ORDER BY study_date DESC LIMIT 1"
    ).fetchone()
    due = db.execute(
        "SELECT COUNT(*) AS n FROM user_words WHERE next_review IS NOT NULL AND date(next_review)<=?",
        (today,),
    ).fetchone()['n']
    mastered = db.execute("SELECT COUNT(*) AS n FROM user_words WHERE status IN ('巩固','掌握','熟记')").fetchone()['n']
    modules = db.execute(
        "SELECT module, COUNT(*) AS rounds, ROUND(AVG(raw_score),1) AS score FROM practice_sessions "
        "WHERE completed_at >= datetime('now','localtime','-27 days') GROUP BY module"
    ).fetchall()
    level = evaluate_level(db)
    db.close()
    last_date = last['study_date'] if last else ''
    gap = (date.today() - date.fromisoformat(last_date)).days if last_date else None
    return {
        'today': today,
        'active_days_7': recent_7['days'], 'minutes_7': recent_7['minutes'],
        'new_words_7': recent_7['new_words'], 'reviews_7': recent_7['reviews'],
        'active_days_28': recent_28['days'], 'minutes_28': recent_28['minutes'],
        'days_since_last_activity': gap, 'due_reviews': due, 'mastered_words': mastered,
        'recent_modules': [dict(row) for row in modules],
        'level': {
            'name': level['name'],
            'rank': level['rank'],
            'total_score': level['total_score'],
            'confidence': level['confidence'],
            'assessment': level['assessment']['sentence'],
            'next_name': LEVEL_NAMES[min(10, level['rank'] + 1)],
            'next_score_gap': round(max(0, (level['rank'] * 10 if level['rank'] < 10 else 100) - level['total_score']), 1),
        },
    }


def _local_greeting(snapshot):
    gap = snapshot['days_since_last_activity']
    due = snapshot['due_reviews']
    if gap is None:
        return f"欢迎你来到第一段学习记录，很高兴见到你。现在有 {due} 个到期复习词在等你，不用着急，先挑一小组试试，之后我才能更懂你的节奏。"
    if gap >= 7:
        return f"好久没见到你了，已经 {gap} 天没有学习记录了。这么久没来，是遇上什么烦心事了吗，还是最近放假了都没空来看我了？你有什么想说的，我们都可以聊聊。不着急的话，先把 {due} 个到期复习词过一遍就好，我在这儿等你。"
    if snapshot['active_days_7'] >= 4:
        return f"你近 7 天学习了 {snapshot['active_days_7']} 天、投入 {snapshot['minutes_7']} 分钟，这个节奏我很为你高兴。今天还有 {due} 个词到期，累了就歇歇，想学了随时回来。"
    if snapshot['new_words_7'] > snapshot['reviews_7'] * 1.5 and due:
        return f"我注意到你近 7 天学新词 {snapshot['new_words_7']} 个，比复习 {snapshot['reviews_7']} 个多不少，看来学习劲头很足。不过复习和学新词一样重要，今天 {due} 个到期词等着你，慢慢来，别给自己压力。"
    return f"你近 7 天完成了 {snapshot['new_words_7']} 个新词和 {snapshot['reviews_7']} 次复习，做得不错！今天有 {due} 个词等待巩固，随时回来，我陪着你。"


@bp.route('/greeting')
def greeting():
    today = date.today().isoformat()
    db = get_db()
    cached = db.execute("SELECT * FROM ai_daily_greetings WHERE greeting_date=?", (today,)).fetchone()
    if cached:
        result = {'greeting': cached['greeting'], 'source': cached['source'], 'date': today}
        db.close()
        return jsonify(result)
    db.close()
    snapshot = _learning_snapshot()
    text = _local_greeting(snapshot)
    source = 'local'
    if get_api_key():
        try:
            answer = call_deepseek([
                {'role': 'system', 'content': '你是用户贴心温暖的学习伙伴，不是老师。用一到两句中文打招呼，先关心对方的近况和心情，再自然地提到学习数据，给出一个轻松的小建议；语气像朋友聊天，温暖平实，不要用命令、催促或"建议你""你需要"这类说教口吻。'},
                {'role': 'user', 'content': json.dumps(snapshot, ensure_ascii=False)},
            ], feature='daily_greeting', temperature=0.6, max_tokens=200)
            if answer['content'].strip():
                text = answer['content'].strip()
                source = 'ai'
        except AIServiceError:
            pass
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO ai_daily_greetings (greeting_date,greeting,source,snapshot_json) VALUES (?,?,?,?)",
        (today, text, source, json.dumps(snapshot, ensure_ascii=False)),
    )
    db.commit()
    stored = db.execute("SELECT greeting,source FROM ai_daily_greetings WHERE greeting_date=?", (today,)).fetchone()
    db.close()
    return jsonify({'greeting': stored['greeting'], 'source': stored['source'], 'date': today})


def _conversation(conversation_id, first_message):
    db = get_db()
    row = None
    if conversation_id:
        row = db.execute("SELECT id FROM ai_conversations WHERE id=?", (conversation_id,)).fetchone()
    if not row:
        title = first_message.strip().replace('\n', ' ')[:28] or '英语学习对话'
        db.execute("INSERT INTO ai_conversations (title) VALUES (?)", (title,))
        conversation_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
        db.commit()
    db.close()
    return int(conversation_id)


def _save_message(conversation_id, role, content, citations=None, action_draft_id=None):
    db = get_db()
    db.execute(
        "INSERT INTO ai_messages (conversation_id,role,content,citations_json,action_draft_id) VALUES (?,?,?,?,?)",
        (conversation_id, role, content, json.dumps(citations or [], ensure_ascii=False), action_draft_id),
    )
    db.execute("UPDATE ai_conversations SET updated_at=datetime('now','localtime') WHERE id=?", (conversation_id,))
    db.commit()
    db.close()


def _search_notes(query, limit=5):
    terms = [term for term in re.findall(r'[A-Za-z]{3,}|[\u4e00-\u9fff]{2,}', query) if term not in {'笔记', '前几天', '相关知识', '帮我', '是不是'}]
    db = get_db()
    rows = db.execute(
        "SELECT id,note_date,title,content FROM notes WHERE content!='' ORDER BY updated_at DESC,id DESC LIMIT 80"
    ).fetchall()
    db.close()
    found = []
    for row in rows:
        content = (row['title'] or '') + ' ' + (row['content'] or '')
        if not terms or any(term.lower() in content.lower() for term in terms):
            found.append({'id': row['id'], 'date': row['note_date'], 'excerpt': (row['content'] or '')[:180]})
        if len(found) >= limit:
            break
    return found


def _make_note_draft(conversation_id, content):
    key = f'note-{conversation_id}-{uuid.uuid4()}'
    db = get_db()
    db.execute(
        "INSERT INTO ai_action_drafts (conversation_id,action_type,payload_json,status,idempotency_key) VALUES (?,?,?,'pending',?)",
        (conversation_id, 'append_note', json.dumps({'content': content}, ensure_ascii=False), key),
    )
    draft_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
    db.commit()
    db.close()
    return draft_id


@bp.route('/chat', methods=['POST'])
@_require_csrf
def chat():
    payload = request.json or {}
    message = str(payload.get('message', '')).strip()
    attachments = payload.get('attachments') or []
    if not message and attachments:
        message = '请分析这些附件中的英语内容。'
    if not message:
        return jsonify({'error': '请输入想问的问题。'}), 400
    selected_skill = None
    selected_skill_prompt = ''
    skill_slug = str(payload.get('skill_slug', '') or '').strip()
    if skill_slug:
        selected_skill, selected_skill_prompt = skill_prompt(skill_slug)
        if not selected_skill:
            return jsonify({'error': '没有找到要使用的 Skill。'}), 404
        if not selected_skill['enabled']:
            return jsonify({'error': f'“{selected_skill["display_name"]}”Skill 已关闭。'}), 409
    conversation_id = _conversation(payload.get('conversation_id'), message)
    _save_message(conversation_id, 'user', message)
    citations = _search_notes(message) if any(word in message for word in ('笔记', '前几天', '记得', '相关')) else []
    db = get_db()
    previous = db.execute(
        "SELECT content FROM ai_messages WHERE conversation_id=? AND role='assistant' ORDER BY id DESC LIMIT 1",
        (conversation_id,),
    ).fetchone()
    memories = db.execute(
        "SELECT content FROM ai_memories WHERE active=1 AND confirmed=1 ORDER BY last_observed DESC LIMIT 8"
    ).fetchall()
    db.close()
    action = None
    stream = None
    if '记进笔记' in message or '写进笔记' in message:
        draft_content = previous['content'] if previous else re.sub(r'.*?(记进笔记|写进笔记)[：:，, ]*', '', message).strip()
        if not draft_content:
            draft_content = message
        draft_id = _make_note_draft(conversation_id, draft_content)
        content = '我已经整理成一条待写入笔记的内容。请先核对预览，确认后才会追加到今天的笔记。'
        action = {'id': draft_id, 'type': 'append_note', 'preview': draft_content, 'status': 'pending'}
    elif not get_api_key():
        content = 'DeepSeek 还没有配置。你可以先到“我的 → AI 服务”填写 API Key；现有学习、复习和笔记仍可正常使用。'
    else:
        context = {'learning': _learning_snapshot(), 'memories': [row['content'] for row in memories], 'note_matches': citations}
        attach_text = ''
        for att in attachments:
            if isinstance(att, dict) and (att.get('text') or att.get('content')):
                attach_text += f"\n\n【上传文件 {att.get('name') or '附件'}】\n{att.get('text') or att.get('content')}"
        try:
            skill_context = f"\n\n{selected_skill_prompt}" if selected_skill_prompt else ''
            user_text = f"学习上下文：{json.dumps(context, ensure_ascii=False)}{skill_context}\n\n{attach_text}\n\n用户问题：{message}"
            images = [att['image'] for att in attachments if isinstance(att, dict) and att.get('image')]
            if images:
                content = call_multimodal(user_text, images, feature='chat_image', metadata={'conversation_id': conversation_id})
            else:
                system_text = ('你是四六级英语学习助理。只能依据提供的数据描述用户状态；引用笔记时标明日期。'
                               '当用户询问当前段位、综合分或可信度时，必须准确引用 learning.level，不能用笼统的“入门阶段”代替正式科举段位名称。'
                               '回答简明、准确，并给出下一步。不得声称已写入或修改任何数据。')
                if selected_skill_prompt:
                    system_text += '\n\n' + selected_skill_prompt + '\n\n如果用户要求优化该 Skill，请给出可复制到“用户补充规则”的新版本，不得声称已经保存。'
                stream = stream_deepseek([
                    {'role': 'system', 'content': system_text},
                    {'role': 'user', 'content': user_text},
                ], feature='skill_dialogue' if skill_slug else 'quick_chat', temperature=0.45, max_tokens=1200, metadata={'conversation_id': conversation_id, 'skill_slug': skill_slug})
        except AIServiceError as exc:
            content = f'这次没有连接上 AI：{exc}'
    memory_candidate = None
    if any(marker in message for marker in ('请记住', '我的目标是', '我总是')):
        memory_candidate = {'content': message[:240], 'requires_confirmation': True}
    def events():
        final_content = content if stream is None else ''
        usage = {}
        model = MODEL
        yield f"event: meta\ndata: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
        try:
            if stream is None:
                if final_content:
                    yield f"event: delta\ndata: {json.dumps({'delta': final_content, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
            else:
                for item in stream:
                    if item['type'] == 'delta':
                        yield f"event: delta\ndata: {json.dumps({'delta': item['text'], 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
                    elif item['type'] == 'done':
                        final_content = item['content']
                        usage = item.get('usage') or {}
                        model = item.get('model') or MODEL
            if not final_content:
                raise AIServiceError('AI 没有返回有效内容。', 'empty_stream', 502)
            _save_message(conversation_id, 'assistant', final_content, citations, action['id'] if action else None)
            result = {
                'conversation_id': conversation_id, 'message': final_content,
                'citations': citations, 'action': action, 'memory_candidate': memory_candidate,
                'usage': usage, 'model': model,
            }
            yield f"event: message\ndata: {json.dumps(result, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps(result, ensure_ascii=False)}\n\n"
        except AIServiceError as exc:
            payload = {'error': str(exc), 'code': exc.code, 'retryable': exc.status >= 500,
                       'conversation_id': conversation_id}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
    return Response(
        stream_with_context(events()), mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no'},
    )


@bp.route('/conversations/<int:conversation_id>/messages')
def conversation_messages(conversation_id):
    db = get_db()
    rows = db.execute(
        "SELECT id,role,content,citations_json,action_draft_id,created_at FROM ai_messages "
        "WHERE conversation_id=? ORDER BY id", (conversation_id,),
    ).fetchall()
    db.close()
    return jsonify({'messages': [{**dict(row), 'citations': json.loads(row['citations_json'] or '[]')} for row in rows]})


@bp.route('/conversations')
def conversations():
    db = get_db()
    rows = db.execute(
        "SELECT c.id,c.title,c.created_at,c.updated_at,COUNT(m.id) AS message_count "
        "FROM ai_conversations c LEFT JOIN ai_messages m ON m.conversation_id=c.id "
        "GROUP BY c.id ORDER BY c.updated_at DESC LIMIT 50"
    ).fetchall()
    db.close()
    return jsonify({'conversations': [dict(row) for row in rows]})


@bp.route('/conversations/<int:conversation_id>', methods=['DELETE'])
@_require_csrf
def delete_conversation(conversation_id):
    db = get_db()
    db.execute("DELETE FROM ai_conversations WHERE id=?", (conversation_id,))
    db.commit()
    db.close()
    return jsonify({'ok': True})


@bp.route('/memories')
def memories():
    db = get_db()
    rows = db.execute(
        "SELECT id,memory_type,content,evidence_json,confirmed,first_observed,last_observed "
        "FROM ai_memories WHERE active=1 AND confirmed=1 ORDER BY last_observed DESC,id DESC"
    ).fetchall()
    db.close()
    return jsonify({'memories': [{**dict(row), 'evidence': json.loads(row['evidence_json'] or '{}')} for row in rows]})


@bp.route('/memories/confirm', methods=['POST'])
@_require_csrf
def confirm_memory():
    content = str((request.json or {}).get('content', '')).strip()[:500]
    if not content:
        return jsonify({'error': '记忆内容不能为空。'}), 400
    db = get_db()
    existing = db.execute(
        "SELECT id FROM ai_memories WHERE memory_type='conversation_fact' AND content=? AND active=1",
        (content,),
    ).fetchone()
    if existing:
        memory_id = existing['id']
        duplicate = True
    else:
        db.execute(
            "INSERT INTO ai_memories (memory_type,content,evidence_json,confirmed,active) VALUES (?,?,?,1,1)",
            ('conversation_fact', content, json.dumps({'source': 'confirmed_conversation'}, ensure_ascii=False)),
        )
        memory_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
        duplicate = False
    db.commit()
    db.close()
    return jsonify({'ok': True, 'id': memory_id, 'duplicate': duplicate})


@bp.route('/memories/<int:memory_id>', methods=['DELETE'])
@_require_csrf
def delete_memory(memory_id):
    db = get_db()
    db.execute("UPDATE ai_memories SET active=0 WHERE id=?", (memory_id,))
    db.commit()
    db.close()
    return jsonify({'ok': True})


@bp.route('/memories', methods=['DELETE'])
@_require_csrf
def clear_memories():
    db = get_db()
    db.execute("UPDATE ai_memories SET active=0")
    db.commit()
    db.close()
    return jsonify({'ok': True})


@bp.route('/actions/<int:draft_id>/confirm', methods=['POST'])
@_require_csrf
def confirm_action(draft_id):
    db = get_db()
    draft = db.execute("SELECT * FROM ai_action_drafts WHERE id=?", (draft_id,)).fetchone()
    if not draft:
        db.close()
        return jsonify({'error': '待确认内容不存在。'}), 404
    if draft['status'] == 'confirmed':
        db.close()
        return jsonify({'ok': True, 'duplicate': True})
    if draft['status'] != 'pending' or draft['action_type'] != 'append_note':
        db.close()
        return jsonify({'error': '这项操作已经失效。'}), 409
    content = str(json.loads(draft['payload_json']).get('content', '')).strip()
    today = date.today().isoformat()
    existing = db.execute(
        "SELECT id,content FROM notes WHERE note_date=? ORDER BY updated_at DESC,id DESC LIMIT 1",
        (today,),
    ).fetchone()
    if existing:
        current = str(existing['content'] or '').rstrip()
        appended = f'{current}\n\n{content}' if current else content
        db.execute(
            "UPDATE notes SET content=?,updated_at=datetime('now','localtime') WHERE id=?",
            (appended, existing['id']),
        )
    else:
        title = content.strip().replace('\n', ' ')[:24] or 'AI 整理笔记'
        db.execute(
            "INSERT INTO notes (category_id,title,content,note_date) VALUES (0,?,?,?)",
            (title, content, today),
        )
    db.execute(
        "UPDATE ai_action_drafts SET status='confirmed',confirmed_at=datetime('now','localtime') WHERE id=? AND status='pending'",
        (draft_id,),
    )
    db.commit()
    db.close()
    return jsonify({'ok': True, 'duplicate': False, 'date': today})


@bp.route('/actions/<int:draft_id>/reject', methods=['POST'])
@_require_csrf
def reject_action(draft_id):
    db = get_db()
    db.execute("UPDATE ai_action_drafts SET status='rejected' WHERE id=? AND status='pending'", (draft_id,))
    db.commit()
    db.close()
    return jsonify({'ok': True})


@bp.route('/generate-reading', methods=['POST'])
@_require_csrf
def generate_reading_questions_endpoint():
    payload = request.json or {}
    article_id = payload.get('article_id')
    count = max(1, min(10, int(payload.get('count') or 5)))
    if not article_id:
        return jsonify({'error': '缺少文章'}), 400
    if not get_api_key():
        return jsonify({'error': '请先到“我的 → AI 服务”配置 DeepSeek API Key。'}), 400
    db = get_db()
    article = db.execute(
        "SELECT id,title,content,difficulty FROM reading_articles WHERE id=? AND question_type='careful_reading'",
        (article_id,),
    ).fetchone()
    db.close()
    if not article:
        return jsonify({'error': '文章不存在'}), 404
    try:
        result = generate_reading_questions(article['title'], article['content'], count, article['difficulty'])
    except AIServiceError as exc:
        return jsonify({'error': str(exc), 'code': exc.code}), exc.status
    questions = (result or {}).get('questions', [])
    if not questions:
        return jsonify({'error': 'AI 未能生成有效题目，请稍后重试。'}), 502
    db = get_db()
    inserted = 0
    for q in questions:
        qtype = str(q.get('type') or 'detail')
        question = str(q.get('question') or '').strip()
        options = [str(opt) for opt in (q.get('options') or [])]
        answer = str(q.get('answer') or '').strip().upper()
        explanation = str(q.get('explanation') or '').strip()
        evidence = str(q.get('evidence_text') or '').strip()
        if (not question or len(options) != 4 or len(set(options)) != 4
                or answer not in ('A', 'B', 'C', 'D') or not explanation
                or not evidence or evidence.lower() not in article['content'].lower()
                or inserted >= count):
            continue
        db.execute(
            "INSERT INTO reading_questions (article_id,question_type,question,options,answer,explanation,evidence_text) VALUES (?,?,?,?,?,?,?)",
            (article_id, qtype, question, json.dumps(options, ensure_ascii=False), answer, explanation, evidence),
        )
        inserted += 1
    db.commit(); db.close()
    return jsonify({'ok': True, 'generated': inserted, 'count': count})


@bp.route('/generate-cloze', methods=['POST'])
@_require_csrf
def generate_cloze_questions_endpoint():
    payload = request.json or {}
    if not get_api_key():
        return jsonify({'error': '请先到“我的 → AI 服务”配置 DeepSeek API Key。'}), 400
    article_id = payload.get('article_id')
    db = get_db()
    if article_id:
        article = db.execute(
            "SELECT id,title,content,difficulty FROM reading_articles WHERE id=? AND question_type='careful_reading'",
            (article_id,),
        ).fetchone()
    else:
        article = db.execute(
            "SELECT id,title,content,difficulty FROM reading_articles WHERE question_type='careful_reading' ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    db.close()
    if not article:
        return jsonify({'error': '没有可用于生成选词填空的文章。'}), 404
    try:
        result = generate_cloze_questions(article['title'], article['content'], 8)
    except AIServiceError as exc:
        return jsonify({'error': str(exc), 'code': exc.code}), exc.status
    if not result or not result.get('blanks'):
        return jsonify({'error': 'AI 未能生成有效题目，请稍后重试。'}), 502
    title = str(result.get('title') or article['title'])
    content = str(result.get('content') or '').strip()
    # 前端要求 {{n}} 占位；兼容 AI 偶发输出的 {n}
    content = re.sub(r'(?<!\{)\{\d+\}(?!\})', lambda m: '{{' + m.group(0).strip('{}') + '}}', content)
    blanks = [b for b in result.get('blanks', [])
              if str(b.get('base_word') or '').strip() and str(b.get('answer') or '').strip()]
    distractors = [str(d) for d in (result.get('distractors') or []) if str(d).strip()][:2]
    if not content or not blanks:
        return jsonify({'error': 'AI 生成内容不完整，请重试。'}), 502
    db = get_db()
    level = 'cet6' if int(article['difficulty']) >= 4 else 'cet4'
    cur = db.execute(
        "INSERT INTO cloze_passages (title,difficulty,level,content,distractors) VALUES (?,?,?,?,?)",
        (title, article['difficulty'], level, content, json.dumps(distractors, ensure_ascii=False)),
    )
    pid = cur.lastrowid
    for b in blanks:
        order = int(b.get('blank_order') or 0)
        if order <= 0:
            continue
        db.execute(
            "INSERT INTO cloze_blanks (passage_id,blank_order,base_word,answer,hint) VALUES (?,?,?,?,?)",
            (pid, order, str(b.get('base_word')).strip(), str(b.get('answer')).strip(), str(b.get('hint') or '').strip()),
        )
    db.commit(); db.close()
    return jsonify({'ok': True, 'id': pid, 'title': title, 'blanks': len(blanks)})


@bp.route('/grade-reading', methods=['POST'])
@_require_csrf
def grade_reading_questions_endpoint():
    payload = request.json or {}
    article_id = payload.get('article_id')
    answers = payload.get('answers') or {}
    if not article_id or not isinstance(answers, dict):
        return jsonify({'error': '缺少文章或作答结果。'}), 400
    if not get_api_key():
        return jsonify({'error': '请先到“我的 → AI 服务”配置 DeepSeek API Key。'}), 400
    db = get_db()
    article = db.execute("SELECT id,title,content FROM reading_articles WHERE id=?", (article_id,)).fetchone()
    questions = db.execute(
        "SELECT id,question_type,question,options,answer,explanation FROM reading_questions WHERE article_id=? ORDER BY id",
        (article_id,),
    ).fetchall()
    db.close()
    if not article or not questions:
        return jsonify({'error': '文章或题目不存在。'}), 404
    qlist = []
    for row in questions:
        item = dict(row)
        item['options'] = json.loads(item['options'] or '[]')
        qlist.append(item)
    user_map = {str(q['id']): answers.get(str(q['id']), '') for q in questions}
    try:
        comments = grade_reading_questions(article['title'], article['content'], qlist, user_map)
    except AIServiceError as exc:
        return jsonify({'error': str(exc), 'code': exc.code}), exc.status
    result = comments.get('comments', []) if isinstance(comments, dict) else []
    return jsonify({'comments': result})


@bp.route('/usage')
def usage():
    days = min(365, max(1, request.args.get('days', 84, type=int)))
    start = date.today() - timedelta(days=days - 1)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM ai_usage_events WHERE date(created_at)>=? ORDER BY created_at",
        (start.isoformat(),),
    ).fetchall()
    tracking = db.execute("SELECT value FROM user_settings WHERE key='ai_tracking_started'").fetchone()
    recent_greetings = db.execute(
        "SELECT greeting_date, greeting, source FROM ai_daily_greetings ORDER BY greeting_date DESC LIMIT 7"
    ).fetchall()
    recent_conversations = db.execute(
        "SELECT c.id, c.title, c.updated_at, COUNT(m.id) AS message_count "
        "FROM ai_conversations c LEFT JOIN ai_messages m ON m.conversation_id=c.id "
        "GROUP BY c.id ORDER BY c.updated_at DESC LIMIT 6"
    ).fetchall()
    curated_articles = db.execute(
        "SELECT COUNT(*) AS c FROM reading_articles WHERE origin='ai_adapted' AND date(date_added)>=?",
        (start.isoformat(),),
    ).fetchone()['c']
    curated_questions = db.execute(
        """SELECT COUNT(*) AS c FROM reading_questions q
           JOIN reading_articles a ON a.id=q.article_id
           WHERE a.origin='ai_adapted' AND date(a.date_added)>=?""",
        (start.isoformat(),),
    ).fetchone()['c']
    confirmed_notes = db.execute(
        """SELECT COUNT(*) AS c FROM ai_action_drafts
           WHERE action_type='append_note' AND status='confirmed' AND date(confirmed_at)>=?""",
        (start.isoformat(),),
    ).fetchone()['c']
    db.close()
    events = [dict(row) for row in rows]
    daily = []
    for offset in range(days):
        current = (start + timedelta(days=offset)).isoformat()
        matches = [item for item in events if str(item['created_at'])[:10] == current]
        daily.append({
            'date': current, 'calls': len(matches),
            'tokens': sum(item['total_tokens'] for item in matches),
            'cost_cny': round(sum(item['cost_cny'] for item in matches), 8),
        })
    features = {}
    for item in events:
        bucket = features.setdefault(item['feature'], {'calls': 0, 'successful': 0, 'tokens': 0, 'cost_cny': 0})
        bucket['calls'] += 1
        bucket['successful'] += item['status'] == 'success'
        bucket['tokens'] += item['total_tokens']
        bucket['cost_cny'] = round(bucket['cost_cny'] + item['cost_cny'], 8)
    def successful(feature):
        return sum(item['status'] == 'success' and item['feature'] == feature for item in events)
    outcomes = [
        {'key': 'curated_articles', 'label': '原创阅读入库', 'count': curated_articles, 'unit': '篇', 'basis': '已通过来源与结构校验的实际文章'},
        {'key': 'curated_questions', 'label': '阅读题完成命制', 'count': curated_questions, 'unit': '题', 'basis': '已写入题库且附答案、解析与证据'},
        {'key': 'essays_corrected', 'label': '作文完成批改', 'count': successful('essay_correction'), 'unit': '篇', 'basis': 'DeepSeek 成功返回的批改结果'},
        {'key': 'reading_graded', 'label': '阅读答题复盘', 'count': successful('grade_reading'), 'unit': '轮', 'basis': '已成功生成的逐题点评'},
        {'key': 'notes_confirmed', 'label': '确认写入笔记', 'count': confirmed_notes, 'unit': '条', 'basis': '由用户二次确认的真实写入'},
        {'key': 'questions_answered', 'label': '学习问题解答', 'count': successful('quick_chat'), 'unit': '次', 'basis': '已成功完成的学习助理问答'},
    ]
    return jsonify({
        'days': days, 'tracking_started': tracking['value'] if tracking else None,
        'history_complete': bool(tracking and str(tracking['value'])[:10] <= start.isoformat()),
        'totals': {
            'calls': len(events), 'successful': sum(item['status'] == 'success' for item in events),
            'failed': sum(item['status'] != 'success' for item in events),
            'tokens': sum(item['total_tokens'] for item in events),
            'tracked_cost_cny': round(sum(item['cost_cny'] for item in events), 8),
        },
        'daily': daily, 'features': features, 'outcomes': outcomes,
        'recent_greetings': [dict(row) for row in recent_greetings],
        'recent_conversations': [dict(row) for row in recent_conversations],
    })

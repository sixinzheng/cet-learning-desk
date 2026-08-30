"""工作台分类笔记与独立笔记页的兼容接口。"""
from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from database import get_db
from services.ai_service import generate_daily_summary

bp = Blueprint('notes', __name__)


def _notes_columns(db):
    return {row[1] for row in db.execute("PRAGMA table_info(notes)").fetchall()}


def _close_owned_db(db):
    """关闭项目自己的文件连接；保留调用方注入的共享内存连接。"""
    database_path = db.execute("PRAGMA database_list").fetchone()[2]
    if database_path:
        db.close()


def _valid_note_date(value):
    try:
        return date.fromisoformat(str(value)).isoformat() == str(value)
    except (TypeError, ValueError):
        return False


def _daily_row(db, note_date):
    columns = _notes_columns(db)
    order = " ORDER BY updated_at DESC, id DESC" if {'updated_at', 'id'}.issubset(columns) else ""
    return db.execute(
        f"SELECT * FROM notes WHERE note_date=?{order} LIMIT 1", (note_date,)
    ).fetchone()


def _daily_payload(row, note_date):
    data = dict(row) if row else {}
    content = str(data.get('content') or '')
    summary = str(data.get('ai_summary') or '')
    return {
        'date': note_date,
        'title': str(data.get('title') or f'{note_date} 学习笔记'),
        'content': content,
        'ai_summary': summary,
        'has_ai_summary': bool(data.get('has_ai_summary') or summary),
    }


# ---------- 分类目录（一级/二级树） ----------
@bp.get('/categories')
def list_categories():
    db = get_db()
    rows = db.execute(
        "SELECT id,parent_id,name,sort_order FROM note_categories WHERE id!=0 ORDER BY sort_order,id"
    ).fetchall()
    db.close()
    top = []
    children = {}
    for row in rows:
        node = dict(row)
        if node['parent_id'] == 0:
            top.append(node)
        else:
            children.setdefault(node['parent_id'], []).append(node)
    for node in top:
        node['children'] = children.get(node['id'], [])
    return jsonify({'categories': top})


@bp.post('/categories')
def create_category():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip()
    parent_id = int(data.get('parent_id') or 0)
    if not name:
        return jsonify({'error': '分类名称不能为空。'}), 400
    db = get_db()
    cur = db.execute("INSERT INTO note_categories (parent_id,name) VALUES (?,?)", (parent_id, name))
    cid = cur.lastrowid
    db.commit(); db.close()
    return jsonify({'ok': True, 'id': cid})


@bp.put('/categories/<int:cid>')
def update_category(cid):
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM note_categories WHERE id=?", (cid,)).fetchone()
    if not row:
        db.close(); return jsonify({'error': '分类不存在。'}), 404
    name = str(data.get('name') or row['name']).strip()
    parent_id = int(data.get('parent_id', row['parent_id']))
    db.execute("UPDATE note_categories SET name=?, parent_id=? WHERE id=?", (name, parent_id, cid))
    db.commit(); db.close()
    return jsonify({'ok': True})


@bp.delete('/categories/<int:cid>')
def delete_category(cid):
    db = get_db()
    row = db.execute("SELECT * FROM note_categories WHERE id=?", (cid,)).fetchone()
    if not row:
        db.close(); return jsonify({'error': '分类不存在。'}), 404
    db.execute("UPDATE notes SET category_id=0 WHERE category_id=?", (cid,))
    db.execute("UPDATE note_categories SET parent_id=0 WHERE parent_id=?", (cid,))
    db.execute("DELETE FROM note_categories WHERE id=?", (cid,))
    db.commit(); db.close()
    return jsonify({'ok': True})


# ---------- 笔记 ----------
@bp.get('/notes')
def list_notes():
    category_id = request.args.get('category_id', type=int)
    query = request.args.get('q', '')
    where = []
    params = []
    if category_id is not None:
        where.append("category_id=?")
        params.append(category_id)
    if query:
        where.append("(title LIKE ? OR content LIKE ?)")
        like = f'%{query}%'
        params += [like, like]
    sql = "SELECT id,category_id,title,note_date,color,updated_at FROM notes"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC"
    db = get_db()
    rows = db.execute(sql, tuple(params)).fetchall()
    db.close()
    return jsonify({'notes': [dict(row) for row in rows]})


@bp.post('/notes')
def create_note():
    data = request.get_json(silent=True) or {}
    title = str(data.get('title') or '').strip()
    content = str(data.get('content') or '').strip()
    category_id = int(data.get('category_id') or 0)
    note_date = str(data.get('note_date') or date.today().isoformat())
    color = str(data.get('color') or '').strip()
    if not title and not content:
        return jsonify({'error': '标题或内容不能都为空。'}), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO notes (category_id,title,content,note_date,color) VALUES (?,?,?,?,?)",
        (category_id, title, content, note_date, color),
    )
    nid = cur.lastrowid
    db.commit(); db.close()
    return jsonify({'ok': True, 'id': nid})


@bp.get('/notes/<int:nid>')
def note_detail(nid):
    db = get_db()
    row = db.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
    db.close()
    if not row:
        return jsonify({'error': '笔记不存在。'}), 404
    return jsonify(dict(row))


@bp.put('/notes/<int:nid>')
def update_note(nid):
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
    if not row:
        db.close(); return jsonify({'error': '笔记不存在。'}), 404
    title = str(data.get('title', row['title'])).strip()
    content = str(data.get('content', row['content'])).strip()
    category_id = int(data.get('category_id', row['category_id']))
    note_date = str(data.get('note_date', row['note_date'] or date.today().isoformat()))
    color = str(data.get('color', row['color'] or '')).strip()
    db.execute(
        "UPDATE notes SET title=?,content=?,category_id=?,note_date=?,color=?,updated_at=datetime('now','localtime') WHERE id=?",
        (title, content, category_id, note_date, color, nid),
    )
    db.commit(); db.close()
    return jsonify({'ok': True, 'id': nid})


@bp.delete('/notes/<int:nid>')
def delete_note(nid):
    db = get_db()
    cur = db.execute("DELETE FROM notes WHERE id=?", (nid,))
    if cur.rowcount == 0:
        db.close(); return jsonify({'error': '笔记不存在。'}), 404
    db.commit(); db.close()
    return jsonify({'ok': True})


# ---------- 独立笔记页：按日期管理每日学习记录 ----------
@bp.get('/today')
def today_note():
    note_date = date.today().isoformat()
    db = get_db()
    row = _daily_row(db, note_date)
    _close_owned_db(db)
    return jsonify(_daily_payload(row, note_date))


@bp.post('/save')
def save_today_note():
    data = request.get_json(silent=True) or {}
    content = str(data.get('content') or '')
    note_date = date.today().isoformat()
    db = get_db()
    columns = _notes_columns(db)
    row = _daily_row(db, note_date)
    if row:
        identity = "id=?" if 'id' in columns else "note_date=?"
        identity_value = row['id'] if 'id' in columns else note_date
        updated = ",updated_at=datetime('now','localtime')" if 'updated_at' in columns else ""
        db.execute(f"UPDATE notes SET content=?{updated} WHERE {identity}", (content, identity_value))
    elif content.strip():
        if 'id' in columns:
            db.execute(
                "INSERT INTO notes (category_id,title,content,note_date) VALUES (0,?,?,?)",
                (f'{note_date} 学习笔记', content, note_date),
            )
        else:
            db.execute("INSERT INTO notes (note_date,content) VALUES (?,?)", (note_date, content))
    db.commit(); _close_owned_db(db)
    return jsonify({'ok': True, 'date': note_date})


@bp.get('/history')
def note_history():
    db = get_db()
    columns = _notes_columns(db)
    order = "updated_at DESC,id DESC" if {'updated_at', 'id'}.issubset(columns) else "note_date DESC"
    rows = db.execute(f"SELECT * FROM notes WHERE COALESCE(content,'')!='' ORDER BY {order}").fetchall()
    _close_owned_db(db)
    records = []
    seen_dates = set()
    for row in rows:
        payload = _daily_payload(row, str(row['note_date'] or ''))
        if not payload['date'] or payload['date'] in seen_dates:
            continue
        seen_dates.add(payload['date'])
        records.append({
            'date': payload['date'],
            'preview': payload['content'].replace('\n', ' ')[:96],
            'length': len(payload['content']),
            'has_ai_summary': payload['has_ai_summary'],
        })
    records.sort(key=lambda item: item['date'], reverse=True)
    return jsonify(records)


@bp.get('/detail/<note_date>')
def note_detail_by_date(note_date):
    if not _valid_note_date(note_date):
        return jsonify({'error': '日期格式必须为 YYYY-MM-DD。'}), 400
    db = get_db()
    row = _daily_row(db, note_date)
    _close_owned_db(db)
    if not row:
        return jsonify({'error': '该日期没有笔记。'}), 404
    return jsonify(_daily_payload(row, note_date))


@bp.put('/<note_date>')
def update_note_by_date(note_date):
    if not _valid_note_date(note_date):
        return jsonify({'error': '日期格式必须为 YYYY-MM-DD。'}), 400
    data = request.get_json(silent=True) or {}
    if 'content' not in data:
        return jsonify({'error': '缺少笔记正文。'}), 400
    db = get_db()
    columns = _notes_columns(db)
    row = _daily_row(db, note_date)
    if not row:
        _close_owned_db(db)
        return jsonify({'error': '该日期没有笔记。'}), 404
    identity = "id=?" if 'id' in columns else "note_date=?"
    identity_value = row['id'] if 'id' in columns else note_date
    updated = ",updated_at=datetime('now','localtime')" if 'updated_at' in columns else ""
    db.execute(f"UPDATE notes SET content=?{updated} WHERE {identity}", (str(data['content']), identity_value))
    db.commit(); _close_owned_db(db)
    return jsonify({'ok': True, 'date': note_date})


@bp.delete('/<note_date>')
def delete_note_by_date(note_date):
    if not _valid_note_date(note_date):
        return jsonify({'error': '日期格式必须为 YYYY-MM-DD。'}), 400
    db = get_db()
    cur = db.execute("DELETE FROM notes WHERE note_date=?", (note_date,))
    if cur.rowcount == 0:
        _close_owned_db(db)
        return jsonify({'error': '该日期没有笔记。'}), 404
    db.commit(); _close_owned_db(db)
    return jsonify({'ok': True, 'date': note_date})


@bp.get('/calendar')
def note_calendar():
    end = date.today()
    start = end - timedelta(days=83)
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT note_date FROM notes WHERE note_date BETWEEN ? AND ? AND COALESCE(content,'')!=''",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    _close_owned_db(db)
    noted = {row['note_date'] for row in rows}
    return jsonify({'data': [
        [(start + timedelta(days=offset)).isoformat(), int((start + timedelta(days=offset)).isoformat() in noted)]
        for offset in range(84)
    ]})


@bp.post('/ai-summary')
def ai_daily_summary():
    note_date = date.today().isoformat()
    db = get_db()
    row = _daily_row(db, note_date)
    log = db.execute("SELECT * FROM study_logs WHERE study_date=?", (note_date,)).fetchone()
    _close_owned_db(db)
    content = str(dict(row).get('content') or '') if row else ''
    if not content.strip():
        return jsonify({'error': '请先保存今天的笔记，再生成总结。'}), 400
    result = generate_daily_summary(dict(log) if log else {}, content)
    if not result:
        return jsonify({'error': 'AI 服务暂时不可用，请检查配置或稍后重试。'}), 503
    return jsonify({'summary': result})

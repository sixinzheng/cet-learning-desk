import os
import json
from datetime import date

from flask import Blueprint, jsonify, request, send_file

import config
from database import get_db

bp = Blueprint('export', __name__)


@bp.route('/word', methods=['POST'])
def export_word():
    data = request.json or {}
    items = data.get('items', [])
    if not items:
        return jsonify({'error': '请选择题目'}), 400

    db = get_db()
    lines = []
    lines.append('四六级单词助手 - 导出练习')
    lines.append(f'导出日期: {date.today().isoformat()}')
    lines.append('=' * 50)
    lines.append('')

    for idx, item in enumerate(items):
        prefix = f'{idx+1}. '
        if item['type'] == 'reading':
            q = db.execute("SELECT * FROM reading_questions WHERE id=?", (item['id'],)).fetchone()
            if q:
                lines.append(f"{prefix}[阅读] {q['question']}")
                opts = json.loads(q['options'] or '[]')
                for oi, opt in enumerate(opts):
                    lines.append(f'   {chr(65+oi)}. {opt}')
                lines.append(f'   答案: {q["answer"]}    解析: {q["explanation"]}')
                lines.append('')

    filename = f'export_{date.today().isoformat()}.txt'
    filepath = os.path.join(config.DATA_DIR, filename)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return jsonify({'ok': True, 'file': filename, 'download_url': f'/api/export/download/{filename}'})


@bp.route('/download/<filename>')
def download(filename):
    filepath = os.path.join(config.DATA_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return jsonify({'error': '文件不存在'}), 404

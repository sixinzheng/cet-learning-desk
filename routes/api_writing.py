import json
import re
import uuid

from flask import Blueprint, jsonify, request
from services.ai_service import AIServiceError, analyze_essay, call_multimodal
from services.practice_service import record_practice_session
from services.difficulty_service import (
    difficulty_criteria, difficulty_exam_level, get_training_difficulty,
)

bp = Blueprint('writing', __name__)


def _parse_ocr_payload(value):
    text = str(value or '').strip()
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, re.S | re.I)
    candidate = fenced.group(1).strip() if fenced else text
    try:
        payload = json.loads(candidate)
    except (TypeError, json.JSONDecodeError):
        return {'text': text, 'warnings': ['识别结果未能结构化，请逐行核对后再提交。']}
    essay = str(payload.get('text') or '').strip()
    warnings = payload.get('warnings') if isinstance(payload.get('warnings'), list) else []
    return {'text': essay, 'warnings': [str(item)[:180] for item in warnings[:6]]}


@bp.post('/ocr')
def ocr_essay():
    """Transcribe one essay image without storing it or creating practice evidence."""
    data = request.get_json(silent=True) or {}
    image = data.get('image')
    if not isinstance(image, str) or not image:
        return jsonify({'error': '请选择一张作文图片。', 'code': 'missing_image'}), 400
    request_id = str(data.get('request_id') or uuid.uuid4())
    prompt = '''请逐字识别图片中的英文作文。严格遵守：
1. 只转写图片中实际可见的英文正文，保留段落和原有拼写、大小写、标点与语法错误；不要改写、纠错或补全。
2. 忽略稿纸线、页码、中文说明和批改符号。
3. 如图片模糊、旋转、缺页、不是英文作文或有无法辨认的片段，在 warnings 中具体说明；无法辨认处用 [unclear]。
4. 只返回 JSON：{"text":"英文正文","warnings":["提示"]}。'''
    try:
        details = call_multimodal(
            prompt, [image], feature='writing_ocr', temperature=0.0, max_tokens=2200,
            metadata={'request_id': request_id}, image_detail='high', return_details=True,
        )
    except AIServiceError as exc:
        return jsonify({'error': str(exc), 'code': exc.code, 'request_id': request_id}), exc.status
    parsed = _parse_ocr_payload(details.get('content'))
    if not parsed['text']:
        return jsonify({'error': '没有识别到可确认的英文作文，请重新拍摄或手动输入。',
                        'code': 'empty_ocr', 'warnings': parsed['warnings'],
                        'request_id': request_id}), 422
    return jsonify({
        'text': parsed['text'], 'warnings': parsed['warnings'], 'request_id': request_id,
        'model': details.get('model'), 'usage': details.get('usage') or {},
    })

@bp.route('/analyze-sentence', methods=['POST'])
def analyze_sentence():
    from services.ai_service import analyze_sentence_structure
    data = request.json or {}
    sentence = data.get('sentence', '').strip()
    if not sentence: return jsonify({'error': '请提供句子'}), 400
    result = analyze_sentence_structure(sentence)
    if not result: return jsonify({'error': 'AI服务不可用'}), 503
    return jsonify(result)

@bp.route('/correct', methods=['POST'])
def correct():
    data = request.json or {}
    essay = data.get('essay', '').strip()
    if not essay: return jsonify({'error': '请输入作文内容'}), 400
    difficulty = data.get('difficulty') or get_training_difficulty()
    exam_level = data.get('exam_level', '') or ''
    if not exam_level and difficulty:
        exam_level = difficulty_exam_level(difficulty)
    criteria = difficulty_criteria(difficulty) if difficulty else ''
    result = analyze_essay(essay, criteria=criteria)
    if not result: return jsonify({'error': 'AI 服务不可用'}), 503
    total_score = result.get('total_score')
    if isinstance(total_score, (int, float)) and total_score > 0:
        scores = {
            'content': result.get('content_score', 0),
            'structure': result.get('structure_score', 0),
            'vocabulary': result.get('vocabulary_score', 0),
            'grammar': result.get('grammar_score', 0),
            'coherence': result.get('coherence_score', 0),
        }
        session = record_practice_session(
            module='writing', activity_type=exam_level or 'cet4',
            source_id=data.get('prompt_id', ''), difficulty=difficulty or 3,
            correct_count=1, total_count=1, raw_score=total_score,
            duration_seconds=data.get('duration_seconds', 0),
            metadata={'scores': scores, 'word_count': len(essay.split())},
            idempotency_key=data.get('idempotency_key') or f'writing-{uuid.uuid4()}',
        )
        result['practice_session'] = {'id': session['id'], 'duplicate': session['duplicate']}
    return jsonify(result)

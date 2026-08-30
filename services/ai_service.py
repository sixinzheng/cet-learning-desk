"""DeepSeek 统一调用层：配置、用量、费用与错误都在这里收口。"""
import json
import time

import requests

from config import get_api_key, load_config
from database import get_db


MODEL = 'deepseek-v4-flash'
VISION_MODEL = 'deepseek-v4-flash-vision-exp'
PRICE_VERSION = '2026-07-24'
PRICE_CNY_PER_MILLION = {
    'input_cache_hit': 0.02,
    'input_cache_miss': 1.0,
    'output': 2.0,
}


class AIServiceError(RuntimeError):
    def __init__(self, message, code='service_error', status=503):
        super().__init__(message)
        self.code = code
        self.status = status


def _endpoint(path):
    base = load_config().get('deepseek_base_url', 'https://api.deepseek.com').rstrip('/')
    return f'{base}/{path.lstrip("/")}'


def _calculate_cost(usage):
    hit = int(usage.get('prompt_cache_hit_tokens', 0) or 0)
    miss = int(usage.get('prompt_cache_miss_tokens', 0) or 0)
    prompt = int(usage.get('prompt_tokens', 0) or 0)
    if not hit and not miss:
        miss = prompt
    completion = int(usage.get('completion_tokens', 0) or 0)
    cost = (
        hit * PRICE_CNY_PER_MILLION['input_cache_hit']
        + miss * PRICE_CNY_PER_MILLION['input_cache_miss']
        + completion * PRICE_CNY_PER_MILLION['output']
    ) / 1_000_000
    return round(cost, 8)


def calculate_usage_cost(usage):
    """对外暴露与账单一致的费用计算，供后台补库任务记录单次实际费用。"""
    return _calculate_cost(usage or {})


def current_month_tracked_cost():
    db = get_db()
    row = db.execute(
        """SELECT COALESCE(SUM(cost_cny),0) AS cost FROM ai_usage_events
           WHERE date(created_at)>=date('now','start of month','localtime')"""
    ).fetchone()
    db.close()
    return round(float(row['cost'] or 0), 8)


def _record_usage(feature, status, usage=None, latency_ms=0, error_code='', metadata=None, model=None):
    usage = usage or {}
    hit = int(usage.get('prompt_cache_hit_tokens', 0) or 0)
    miss = int(usage.get('prompt_cache_miss_tokens', 0) or 0)
    prompt = int(usage.get('prompt_tokens', 0) or 0)
    if not hit and not miss:
        miss = prompt
    completion = int(usage.get('completion_tokens', 0) or 0)
    total = int(usage.get('total_tokens', prompt + completion) or 0)
    db = get_db()
    db.execute(
        '''INSERT INTO ai_usage_events
           (feature, model, status, prompt_tokens, completion_tokens,
            cache_hit_tokens, cache_miss_tokens, total_tokens,
            input_hit_price_cny, input_miss_price_cny, output_price_cny,
            cost_cny, latency_ms, error_code, metadata_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (
            feature, model or MODEL, status, prompt, completion, hit, miss, total,
            PRICE_CNY_PER_MILLION['input_cache_hit'],
            PRICE_CNY_PER_MILLION['input_cache_miss'],
            PRICE_CNY_PER_MILLION['output'], _calculate_cost(usage),
            max(0, int(latency_ms or 0)), error_code,
            json.dumps({'price_version': PRICE_VERSION, **(metadata or {})}, ensure_ascii=False),
        ),
    )
    db.execute(
        "INSERT OR IGNORE INTO user_settings (key,value) VALUES ('ai_tracking_started', datetime('now','localtime'))"
    )
    db.commit()
    db.close()


def fetch_deepseek_balance(api_key=None):
    key = (api_key or get_api_key()).strip()
    if not key:
        raise AIServiceError('请先填写 DeepSeek API Key。', 'not_configured', 400)
    try:
        response = requests.get(
            _endpoint('/user/balance'),
            headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'},
            timeout=12,
        )
    except requests.RequestException as exc:
        raise AIServiceError('暂时无法连接 DeepSeek，请检查网络后重试。', 'network_error') from exc
    if response.status_code == 401:
        raise AIServiceError('API Key 无效，请重新检查。', 'invalid_key', 401)
    if response.status_code != 200:
        raise AIServiceError(f'DeepSeek 余额验证失败（{response.status_code}）。', f'http_{response.status_code}')
    data = response.json()
    if 'is_available' not in data or 'balance_infos' not in data:
        raise AIServiceError('DeepSeek 返回了无法识别的余额数据。', 'invalid_response')
    return data


def call_deepseek(messages, feature='quick_chat', temperature=0.5, max_tokens=1200, metadata=None):
    from services.skill_service import ensure_feature_enabled
    ensure_feature_enabled(feature)
    key = get_api_key().strip()
    if not key:
        raise AIServiceError('尚未配置 DeepSeek API Key。', 'not_configured', 503)
    started = time.perf_counter()
    try:
        response = requests.post(
            _endpoint('/chat/completions'),
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={
                'model': MODEL,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'thinking': {'type': 'disabled'},
            },
            timeout=45,
        )
        latency = round((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            code_map = {401: 'invalid_key', 402: 'insufficient_balance', 429: 'rate_limited'}
            code = code_map.get(response.status_code, f'http_{response.status_code}')
            _record_usage(feature, 'error', latency_ms=latency, error_code=code, metadata=metadata)
            messages_map = {
                401: 'API Key 已失效，请到“我的”重新配置。',
                402: 'DeepSeek 账户余额不足。',
                429: 'AI 请求过于频繁，请稍后再试。',
            }
            raise AIServiceError(messages_map.get(response.status_code, 'DeepSeek 服务暂时不可用。'), code)
        data = response.json()
        content = data['choices'][0]['message']['content']
        usage = data.get('usage') or {}
        _record_usage(feature, 'success', usage, latency, metadata=metadata)
        return {'content': content, 'usage': usage, 'model': data.get('model', MODEL)}
    except AIServiceError:
        raise
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        latency = round((time.perf_counter() - started) * 1000)
        _record_usage(feature, 'error', latency_ms=latency, error_code='network_or_response', metadata=metadata)
        raise AIServiceError('AI 请求失败，请稍后重试。', 'network_or_response') from exc


def stream_deepseek(messages, feature='quick_chat', temperature=0.5, max_tokens=1200, metadata=None):
    """逐块转发 DeepSeek SSE；仅在完整结束时登记一次成功用量。"""
    from services.skill_service import ensure_feature_enabled
    ensure_feature_enabled(feature)
    key = get_api_key().strip()
    if not key:
        raise AIServiceError('尚未配置 DeepSeek API Key。', 'not_configured', 503)
    started = time.perf_counter()
    response = None
    recorded = False
    try:
        response = requests.post(
            _endpoint('/chat/completions'),
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={
                'model': MODEL,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'thinking': {'type': 'disabled'},
                'stream': True,
                'stream_options': {'include_usage': True},
            },
            timeout=(12, 75),
            stream=True,
        )
        latency = round((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            code_map = {401: 'invalid_key', 402: 'insufficient_balance', 429: 'rate_limited'}
            code = code_map.get(response.status_code, f'http_{response.status_code}')
            _record_usage(feature, 'error', latency_ms=latency, error_code=code, metadata=metadata)
            recorded = True
            messages_map = {
                401: 'API Key 已失效，请到“我的”重新配置。',
                402: 'DeepSeek 账户余额不足。',
                429: 'AI 请求过于频繁，请稍后再试。',
            }
            raise AIServiceError(messages_map.get(response.status_code, 'DeepSeek 服务暂时不可用。'), code)

        full_text = []
        usage = {}
        model = MODEL
        for raw_line in response.iter_lines(decode_unicode=True):
            line = (raw_line or '').strip()
            if not line or not line.startswith('data:'):
                continue
            payload = line[5:].strip()
            if payload == '[DONE]':
                break
            try:
                chunk = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                continue
            model = chunk.get('model') or model
            if chunk.get('usage'):
                usage = chunk['usage']
            choices = chunk.get('choices') or []
            if choices:
                delta = (choices[0].get('delta') or {}).get('content') or ''
                if delta:
                    full_text.append(delta)
                    yield {'type': 'delta', 'text': delta}

        content = ''.join(full_text).strip()
        if not content:
            raise AIServiceError('DeepSeek 没有返回有效内容。', 'empty_stream', 502)
        latency = round((time.perf_counter() - started) * 1000)
        _record_usage(feature, 'success', usage, latency, metadata=metadata, model=model)
        recorded = True
        yield {'type': 'done', 'content': content, 'usage': usage, 'model': model}
    except GeneratorExit:
        latency = round((time.perf_counter() - started) * 1000)
        if not recorded:
            _record_usage(feature, 'cancelled', latency_ms=latency, error_code='client_cancelled', metadata=metadata)
        raise
    except AIServiceError:
        if not recorded:
            latency = round((time.perf_counter() - started) * 1000)
            _record_usage(feature, 'error', latency_ms=latency, error_code='stream_error', metadata=metadata)
        raise
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        latency = round((time.perf_counter() - started) * 1000)
        if not recorded:
            _record_usage(feature, 'error', latency_ms=latency, error_code='network_or_response', metadata=metadata)
        raise AIServiceError('AI 流式请求中断，请稍后重试。', 'network_or_response') from exc
    finally:
        if response is not None:
            response.close()


def _call_deepseek(messages, temperature=0.7, max_tokens=2000, feature='other'):
    try:
        return call_deepseek(messages, feature, temperature, max_tokens)['content']
    except AIServiceError:
        return None


def _json_result(content, fallback_key=None):
    if not content:
        return None
    cleaned = content.strip().strip('`').strip()
    if cleaned.startswith('json'):
        cleaned = cleaned[4:].strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return {fallback_key: content} if fallback_key else None


def generate_fusion_sentence(recent_words, count=5):
    word_list = ', '.join([word['word'] for word in recent_words[:count]])
    meanings = '\n'.join([f"{word['word']}: {word['meanings']}" for word in recent_words[:count]])
    prompt = f'''请将以下英语单词自然融合进一个适合四六级语境的句子，并提供翻译。
单词：{word_list}\n释义：\n{meanings}
只返回 JSON：{{"sentence":"英文句子","translation":"中文翻译"}}'''
    result = _call_deepseek([
        {'role': 'system', 'content': '你是专业英语教师，只输出合法 JSON。'},
        {'role': 'user', 'content': prompt},
    ], 0.7, 500, 'fusion_sentence')
    return _json_result(result, 'sentence')


def analyze_essay(essay_text, criteria=''):
    """批改作文。criteria 传入难度对应的评判标准（如六级优秀），未传则按默认四六级标准。"""
    standard = criteria if criteria else '四六级真实阅卷标准'
    prompt = f'''请按{standard}严格批改下列作文，不要虚高评分。\n\n{essay_text}
只返回 JSON，字段包括 total_score、content_score、structure_score、vocabulary_score、grammar_score、coherence_score、errors、highlights、improvements、overall_comment。'''
    result = _call_deepseek([
        {'role': 'system', 'content': '你是严格的四六级阅卷老师，只输出合法 JSON。'},
        {'role': 'user', 'content': prompt},
    ], 0.3, 2000, 'essay_correction')
    return _json_result(result, 'overall_comment')


def analyze_sentence_structure(sentence):
    prompt = f'''分析英语句子“{sentence}”的成分、主干、从句和中文翻译。
只返回 JSON：{{"structure":"","main_clause":"","clauses":"","translation":""}}'''
    result = _call_deepseek([
        {'role': 'system', 'content': '你是英语语法专家，只输出合法 JSON。'},
        {'role': 'user', 'content': prompt},
    ], 0.3, 800, 'sentence_analysis')
    return _json_result(result, 'translation')


def generate_word_sentences(word, meaning, exam_type='cet4'):
    prompt = f'''为 {word}（{meaning}）生成两条 {exam_type} 真题风格例句及翻译。
只返回 JSON：{{"sentences":[{{"en":"","zh":""}},{{"en":"","zh":""}}]}}'''
    result = _call_deepseek([
        {'role': 'system', 'content': '你是英语教师，只输出合法 JSON。'},
        {'role': 'user', 'content': prompt},
    ], 0.6, 600, 'word_sentences')
    return _json_result(result)


def generate_grammar_sentence_score(sentence, grammar_point):
    prompt = f'''目标语法点：{grammar_point}\n用户句子：{sentence}
只返回 JSON：{{"score":0,"comment":"","correction":""}}'''
    result = _call_deepseek([
        {'role': 'system', 'content': '客观评估语法使用，只输出合法 JSON。'},
        {'role': 'user', 'content': prompt},
    ], 0.3, 400, 'grammar_sentence')
    return _json_result(result)


def generate_daily_summary(study_data, user_note):
    prompt = f'''基于今日数据和用户笔记生成学习总结。
数据：{json.dumps(study_data, ensure_ascii=False)}\n笔记：{user_note or '无'}
只返回 JSON：{{"overview":"","connections":"","extension":"","weakness_alert":""}}'''
    result = _call_deepseek([
        {'role': 'system', 'content': '你是重证据的英语学习助手，只输出合法 JSON。'},
        {'role': 'user', 'content': prompt},
    ], 0.4, 1000, 'daily_summary')
    return _json_result(result, 'overview')


def generate_reading_questions(article_title, article_content, count=5, difficulty=3):
    """基于一篇文章，由 DeepSeek 生成四六级风格的四选一阅读理解题。"""
    prompt = (
        f'请基于下面这篇文章，为四六级考试编写 {count} 道阅读理解选择题（每题 4 个选项 A/B/C/D）。\n'
        f'题型尽量覆盖：主旨题(main_idea)、细节题(detail)、推断题(inference)、词义猜测题(word_guess)、作者态度题(attitude)，每种各一道。\n'
        f'命题要求：\n'
        f'1) 题干顺序按原文行文顺序（先主旨，再按段落细节、推断）。\n'
        f'2) 题干用英文，但不得整句照抄原文；解析用中文。\n'
        f'3) 正确答案 = 原文同义替换（近义改写/词性转换/正话反说）；干扰项遵循：原词复现但答非所问、偷换概念/张冠李戴、以偏概全/过度概括、无中生有、与原文矛盾/绝对化。\n'
        f'4) 正确项与干扰项都要和题干、原文语义相关，不能与题干重复。\n'
        f'5) 每题 evidence_text 必须逐字取自文章，能够直接支持正确答案。\n'
        f'6) 正确答案字母尽量分散（A/B/C/D 不连续重复）。\n'
        f'7) 语言难度与本文一致：文章为{"六级" if difficulty >= 4 else "四级"}难度，题干与选项难度相应。\n\n'
        f'文章标题：{article_title}\n文章内容：\n{article_content}\n\n'
        f'只返回 JSON：{{"questions":[{{"type":"main_idea","question":"题干","options":["选项A","选项B","选项C","选项D"],"answer":"B","explanation":"解析","evidence_text":"原文精确证据"}}]}}'
    )
    result = _call_deepseek([
        {'role': 'system', 'content': '你是专业四六级命题教师，只输出合法 JSON。'},
        {'role': 'user', 'content': prompt},
    ], 0.6, 1800, 'generate_reading')
    return _json_result(result)


def generate_reading_article_package(*, topic, difficulty, source_brief, policy, golden_sample=None):
    """根据权威来源的有限事实摘要，生成原创仔细阅读文章与5题。"""
    difficulty_rules = (policy.get('difficulty_levels') or {}).get(str(difficulty), {})
    sample_text = ''
    if golden_sample:
        sample_text = (
            '\n同主题同难度策展库的结构样本（只能参考难度、篇章结构、信息密度和题型节奏；不得复制标题、中心问题、句式、措辞、题干或选项）：\n'
            + json.dumps(golden_sample, ensure_ascii=False)[:5000]
        )
    prompt = f'''为本地四六级学习网站生成一篇全新的仔细阅读练习。
话题：{topic}
难度：{difficulty}/6
难度标准：{json.dumps(difficulty_rules, ensure_ascii=False)}
来源标题：{source_brief.get('source_title','')}
来源事实摘要：
{source_brief.get('fact_brief','')}

强制要求：
1. 只使用摘要中能核验的事实，不添加人名、数据或引语。
2. 必须重新组织论述与句子，不连续复制来源 8 个以上英文单词。
3. 文章适合四六级仔细阅读，有清晰逻辑，不写成新闻摘要。
4. 生成恰好 5 道四选一题，覆盖主旨、细节、推断、语境词义、态度中至少 4 类。
5. 每题只有一个最佳答案；解析用中文；evidence_text 是文章内支持答案的精确短句。
6. 正确选项字母分散，干扰项与原文相关但分别体现偷换概念、以偏概全、无中生有或答非所问。
{sample_text}

只返回 JSON：
{{"title":"","content":"","questions":[{{"type":"detail","question":"","options":["","","",""],"answer":"A","explanation":"","evidence_text":""}}]}}
'''
    result = call_deepseek(
        [
            {'role': 'system', 'content': '你是严谨的四六级阅读编辑，只输出合法 JSON，不冒充真题或媒体原文。'},
            {'role': 'user', 'content': prompt},
        ],
        feature='reading_library', temperature=0.45, max_tokens=3600,
        metadata={'topic': topic, 'difficulty': difficulty, 'source_url': source_brief.get('source_url', '')},
    )
    parsed = _json_result(result.get('content'))
    if not isinstance(parsed, dict):
        raise AIServiceError('AI 未返回可验证的阅读文章 JSON。', 'invalid_reading_package', 502)
    parsed['_usage'] = result.get('usage') or {}
    parsed['_model'] = result.get('model', MODEL)
    return parsed


def generate_cloze_questions(article_title, article_content, count=8):
    """基于一篇文章，由 DeepSeek 生成四六级风格的选词填空题（文章挖空 + 原形/变形 + 干扰词）。"""
    prompt = (
        f'请把下面这篇文章改写成四六级选词填空题（banked cloze）。\n'
        f'命题要求：\n'
        f'1) 从文中挖出 {count} 个空，挖空处用 {{序号}} 占位（从 1 开始、连续编号）。\n'
        f'2) 每个空给出该处所需单词的原形 base_word，以及它在句中的正确变形 answer（变形必须与该句的句法匹配，如主谓一致、时态、单复数、比较级、分词、副词）。\n'
        f'3) 优先挖取句中需要形态变化的词（过去式/三单、单复数、比较级、分词、副词等），尽量让多数 base_word 与 answer 不同、有实际变化，避免全用原形；挖空的词性覆盖 名词/动词/形容词/副词 等，变形常见、不超出四六级词表。\n'
        f'4) 另给恰好 2 个干扰词 distractor：与挖空词【词性相同或相近、但语义不符】（或形近/反义），且不能与任何一个空匹配，也不能与任何 base_word 相同。\n'
        f'5) blanks 的 hint 只填该词的中文词义，绝不提示变形、时态、单复数或词性，避免泄露答案。\n\n'
        f'文章标题：{article_title}\n文章内容：\n{article_content}\n\n'
        f'只返回 JSON：{{"title":"标题","content":"带{{{{1}}}}{{{{2}}}}...占位的文章",'
        f'"blanks":[{{"blank_order":1,"base_word":"write","answer":"writes","hint":"写"}}],'
        f'"distractors":["interfere","assemble"]}}'
    )
    result = _call_deepseek([
        {'role': 'system', 'content': '你是专业四六级命题教师，只输出合法 JSON。'},
        {'role': 'user', 'content': prompt},
    ], 0.6, 2200, 'generate_cloze')
    return _json_result(result)


def call_multimodal(text, images, feature='chat_image', temperature=0.4, max_tokens=900,
                    metadata=None, image_detail='low', return_details=False):
    """使用 DeepSeek 官方实验视觉模型处理本地图片；图片不在本站落盘。"""
    from services.skill_service import ensure_feature_enabled
    ensure_feature_enabled(feature)
    key = get_api_key().strip()
    if not key:
        raise AIServiceError('尚未配置 DeepSeek API Key。', 'not_configured', 503)
    if not isinstance(images, list) or not images:
        raise AIServiceError('请至少选择一张图片。', 'missing_image', 400)
    if len(images) > 3:
        raise AIServiceError('一次最多分析 3 张图片。', 'too_many_images', 400)

    detail = image_detail if image_detail in ('low', 'high', 'auto') else 'low'
    content = [{'type': 'text', 'text': str(text or '请分析图片中的英语内容。')}]
    allowed_prefixes = ('data:image/jpeg;base64,', 'data:image/png;base64,',
                        'data:image/gif;base64,', 'data:image/webp;base64,')
    for image in images:
        value = str(image or '')
        if not value.startswith(allowed_prefixes):
            raise AIServiceError('图片必须是 JPEG、PNG、GIF 或 WebP 格式。', 'invalid_image_type', 400)
        encoded = value.split(',', 1)[1]
        if len(encoded) > 8_400_000:
            raise AIServiceError('单张图片不能超过 6 MB。', 'image_too_large', 413)
        content.append({'type': 'image_url', 'image_url': {'url': value, 'detail': detail}})

    started = time.perf_counter()
    try:
        response = requests.post(
            _endpoint('/chat/completions'),
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={
                'model': VISION_MODEL,
                'messages': [
                    {'role': 'system', 'content': '你是四六级英语学习助理。准确阅读用户图片，只描述图片中可见的内容；不确定时明确说明。结合随附学习数据回答，但不得声称已修改任何学习记录。'},
                    {'role': 'user', 'content': content},
                ],
                'temperature': temperature,
                'max_tokens': max_tokens,
                'thinking': {'type': 'disabled'},
            },
            timeout=75,
        )
        latency = round((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            code_map = {400: 'invalid_image_request', 401: 'invalid_key', 402: 'insufficient_balance', 429: 'rate_limited'}
            code = code_map.get(response.status_code, f'http_{response.status_code}')
            _record_usage(feature, 'error', latency_ms=latency, error_code=code,
                          metadata=metadata, model=VISION_MODEL)
            messages_map = {
                400: 'DeepSeek 未能读取这张图片，请确认格式后重试。',
                401: 'API Key 已失效，请到“我的”重新配置。',
                402: 'DeepSeek 账户余额不足。',
                429: '视觉请求过于频繁，请稍后再试。',
            }
            raise AIServiceError(messages_map.get(response.status_code, 'DeepSeek 视觉服务暂时不可用。'), code)
        data = response.json()
        answer = data['choices'][0]['message']['content']
        usage = data.get('usage') or {}
        _record_usage(feature, 'success', usage, latency, metadata=metadata, model=VISION_MODEL)
        answer = str(answer).strip()
        if return_details:
            return {'content': answer, 'usage': usage, 'model': VISION_MODEL}
        return answer
    except AIServiceError:
        raise
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        latency = round((time.perf_counter() - started) * 1000)
        _record_usage(feature, 'error', latency_ms=latency, error_code='network_or_response',
                      metadata=metadata, model=VISION_MODEL)
        raise AIServiceError('图片分析失败，请稍后重试。', 'network_or_response') from exc


def grade_reading_questions(article_title, article_content, questions, user_answers):
    """逐题点评阅读理解结果：答对简评、答错详评。questions 为 list[dict]，user_answers 为 {question_id: letter}。"""
    qtext = '\n'.join([
        f"题目{i + 1}（{q.get('question_type', '')}）: {q.get('question', '')}\n"
        f"选项: {json.dumps(q.get('options') or [], ensure_ascii=False)}\n"
        f"正确答案: {q.get('answer', '')}\n解析: {q.get('explanation', '') or ''}\n"
        f"用户作答: {user_answers.get(str(q.get('id')), '未作答')}"
        for i, q in enumerate(questions)
    ])
    prompt = (
        '请逐题点评下面的阅读理解答题结果。\n'
        '要求：\n'
        '1) 答对的题【简要点评】：用一句话说明为何正确（如定位准确/同义替换），不展开。\n'
        '2) 答错的题【详细点评】：给出 (a) 错因（用户所选选项为什么不对）、(b) 定位原文关键句、(c) 正确答案与解析。\n'
        '3) 用中文；每题返回 index（从 1 开始）、correct（是否答对）、comment（点评）。\n\n'
        f'文章标题：{article_title}\n文章内容：\n{article_content}\n\n题目与作答：\n{qtext}\n\n'
        '只返回 JSON：{"comments":[{"index":1,"correct":true,"comment":"点评"}]}'
    )
    result = _call_deepseek([
        {'role': 'system', 'content': '你是严格又细致的四六级阅卷老师，只输出合法 JSON。'},
        {'role': 'user', 'content': prompt},
    ], 0.4, 1800, 'grade_reading')
    return _json_result(result)

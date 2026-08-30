import os
import json
import base64
import ctypes
import hashlib
import secrets
from ctypes import wintypes

from runtime_paths import APP_ID, RESOURCE_ROOT, USER_DATA_DIR


BASE_DIR = RESOURCE_ROOT
DATA_DIR = USER_DATA_DIR
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')

DEFAULTS = {
    'deepseek_base_url': 'https://api.deepseek.com',
    'deepseek_model': 'deepseek-v4-flash',
    'daily_new_words': 20,
    'port': 5099,
}


if os.name == 'nt':
    class _DataBlob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]


    class _CredentialW(ctypes.Structure):
        _fields_ = [
            ('Flags', wintypes.DWORD),
            ('Type', wintypes.DWORD),
            ('TargetName', wintypes.LPWSTR),
            ('Comment', wintypes.LPWSTR),
            ('LastWritten', wintypes.FILETIME),
            ('CredentialBlobSize', wintypes.DWORD),
            ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)),
            ('Persist', wintypes.DWORD),
            ('AttributeCount', wintypes.DWORD),
            ('Attributes', ctypes.c_void_p),
            ('TargetAlias', wintypes.LPWSTR),
            ('UserName', wintypes.LPWSTR),
        ]
else:
    _DataBlob = None
    _CredentialW = None


_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2


def _is_android():
    return os.environ.get('CET_ANDROID', '').strip() == '1'


def _android_secure_store():
    from java import jclass
    return jclass('cn.cet.learningdesk.SecureStore')


def _credential_target():
    """为生产配置和测试临时配置生成彼此隔离的凭据名称。"""
    if os.environ.get('CET_DESKTOP', '').strip() == '1' or getattr(__import__('sys'), 'frozen', False):
        return f'{APP_ID}:DeepSeek'
    normalized = os.path.normcase(os.path.abspath(CONFIG_PATH)).encode('utf-8')
    suffix = hashlib.sha256(normalized).hexdigest()[:12]
    return f'CET-English-Learning-DeepSeek:{suffix}'


def _read_credential():
    if _is_android():
        return str(_android_secure_store().getApiKey() or '')
    if os.name != 'nt':
        return ''
    pointer = ctypes.POINTER(_CredentialW)()
    ok = ctypes.windll.advapi32.CredReadW(
        _credential_target(), _CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)
    )
    if not ok:
        error = ctypes.windll.kernel32.GetLastError()
        if error in (0, 1168):
            return ''
        raise ctypes.WinError(error)
    try:
        credential = pointer.contents
        if not credential.CredentialBlob or not credential.CredentialBlobSize:
            return ''
        raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        return raw.decode('utf-8')
    finally:
        ctypes.windll.advapi32.CredFree(pointer)


def _write_credential(value):
    if _is_android():
        _android_secure_store().setApiKey(value)
        return
    if os.name != 'nt':
        raise RuntimeError('Windows 凭据管理器仅支持 Windows。')
    raw = value.encode('utf-8')
    blob = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    credential = _CredentialW()
    credential.Type = _CRED_TYPE_GENERIC
    credential.TargetName = _credential_target()
    credential.Comment = '四六级学习台 DeepSeek API Key'
    credential.CredentialBlobSize = len(raw)
    credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
    credential.UserName = 'DeepSeek API Key'
    if not ctypes.windll.advapi32.CredWriteW(ctypes.byref(credential), 0):
        raise ctypes.WinError(ctypes.windll.kernel32.GetLastError())


def _delete_credential():
    if _is_android():
        _android_secure_store().deleteApiKey()
        return
    if os.name != 'nt':
        return
    if ctypes.windll.advapi32.CredDeleteW(_credential_target(), _CRED_TYPE_GENERIC, 0):
        return
    error = ctypes.windll.kernel32.GetLastError()
    if error not in (0, 1168):
        raise ctypes.WinError(error)


def _blob_from_bytes(value):
    buffer = ctypes.create_string_buffer(value)
    return _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _protect(value):
    if _is_android():
        return 'android-keystore:' + str(_android_secure_store().encrypt(value))
    if os.name != 'nt':
        raise RuntimeError('API Key 加密仅支持 Windows 当前用户。')
    source, source_buffer = _blob_from_bytes(value.encode('utf-8'))
    output = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), 'CET AI Key', None, None, None, 0,
        ctypes.byref(output),
    ):
        raise ctypes.WinError()
    try:
        encrypted = ctypes.string_at(output.pbData, output.cbData)
        return base64.b64encode(encrypted).decode('ascii')
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)
        del source_buffer


def _unprotect(value):
    if not value:
        return ''
    if _is_android():
        prefix = 'android-keystore:'
        if not str(value).startswith(prefix):
            return ''
        return str(_android_secure_store().decrypt(str(value)[len(prefix):]) or '')
    encrypted = base64.b64decode(value)
    source, source_buffer = _blob_from_bytes(encrypted)
    output = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0,
        ctypes.byref(output),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData).decode('utf-8')
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)
        del source_buffer


def load_config():
    """加载配置文件，不存在则创建默认配置"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(DEFAULTS, f, indent=2, ensure_ascii=False)
        return dict(DEFAULTS)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)
    legacy_key = str(cfg.pop('deepseek_api_key', '') or '').strip()
    if legacy_key and not cfg.get('deepseek_api_key_encrypted'):
        cfg['deepseek_api_key_encrypted'] = _protect(legacy_key)
        cfg['deepseek_key_suffix'] = legacy_key[-4:]
        try:
            _write_credential(legacy_key)
        except (OSError, RuntimeError):
            pass
        save_config(cfg)
    return cfg


def save_config(cfg):
    """保存配置到文件"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_api_key():
    try:
        credential_key = _read_credential().strip()
    except (OSError, RuntimeError, UnicodeError):
        credential_key = ''
    if credential_key:
        return credential_key
    cfg = load_config()
    encrypted = cfg.get('deepseek_api_key_encrypted', '')
    if not encrypted:
        return ''
    try:
        key = _unprotect(encrypted).strip()
        if key:
            try:
                _write_credential(key)
            except (OSError, RuntimeError):
                pass
        return key
    except (ValueError, OSError):
        return ''


def get_api_key_status():
    """只返回存储健康度，不泄露密钥内容。"""
    cfg = load_config()
    encrypted_present = bool(cfg.get('deepseek_api_key_encrypted'))
    credential_present = False
    key = ''
    try:
        key = _read_credential().strip()
        credential_present = bool(key)
    except (OSError, RuntimeError, UnicodeError):
        pass
    backend = 'credential_manager' if credential_present else ''
    if not key and encrypted_present:
        try:
            key = _unprotect(cfg.get('deepseek_api_key_encrypted', '')).strip()
        except (ValueError, OSError, UnicodeError):
            key = ''
        if key:
            backend = 'dpapi_fallback'
            try:
                _write_credential(key)
                credential_present = True
                backend = 'credential_manager'
            except (OSError, RuntimeError):
                pass
    return {
        'configured': bool(key),
        'key_suffix': cfg.get('deepseek_key_suffix', key[-4:] if key else ''),
        'key_material_present': encrypted_present or credential_present,
        'credential_present': credential_present,
        'encrypted_present': encrypted_present,
        'storage_backend': backend or ('unreadable_dpapi' if encrypted_present else 'none'),
        'recovery_required': bool(encrypted_present and not key),
    }


def save_api_key(api_key, verified_at=''):
    value = str(api_key or '').strip()
    if not value:
        raise ValueError('API Key 不能为空。')
    cfg = load_config()
    cfg.pop('deepseek_api_key', None)
    cfg['deepseek_api_key_encrypted'] = _protect(value)
    cfg['deepseek_key_suffix'] = value[-4:]
    if verified_at:
        cfg['deepseek_verified_at'] = verified_at
    save_config(cfg)
    # 某些无交互 Windows 会话没有 Credential Manager 登录上下文；此时保留
    # 当前用户 DPAPI 密文作为可用兜底，而不是让一次成功验证因存储失败而丢失。
    try:
        _write_credential(value)
    except (OSError, RuntimeError):
        pass
    return get_api_key_status()


def delete_api_key():
    try:
        _delete_credential()
    except (OSError, RuntimeError):
        pass
    cfg = load_config()
    for key in ('deepseek_api_key', 'deepseek_api_key_encrypted', 'deepseek_key_suffix', 'deepseek_verified_at'):
        cfg.pop(key, None)
    save_config(cfg)


def get_session_secret():
    cfg = load_config()
    secret = cfg.get('session_secret')
    if not secret:
        secret = secrets.token_hex(32)
        cfg['session_secret'] = secret
        save_config(cfg)
    return secret

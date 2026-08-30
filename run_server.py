"""以单进程方式启动本地网站，避免 Flask 调试重载器留下旧服务。"""
import os
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEPS_DIR = os.path.join(BASE_DIR, '.deps')
RUNTIME_DEPS_DIR = os.path.join(BASE_DIR, '.runtime_deps')
for project_path in (BASE_DIR, DEPS_DIR, RUNTIME_DEPS_DIR):
    if not os.path.isdir(project_path):
        continue
    while project_path in sys.path:
        sys.path.remove(project_path)
    sys.path.insert(0, project_path)

from app import create_app
from config import load_config


if __name__ == '__main__':
    config = load_config()
    port = int(config.get('port', 5099))
    print(f'[四六级学习台] http://127.0.0.1:{port}', flush=True)
    create_app().run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

"""生成 Android 构建所需的 Python 源码与只读站点资源快照。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_ROOT = ROOT / 'android'
PYTHON_TARGET = ANDROID_ROOT / 'app' / 'src' / 'main' / 'python'
ASSET_TARGET = ANDROID_ROOT / 'app' / 'src' / 'main' / 'assets' / 'app_resources'

PYTHON_FILES = (
    'app.py',
    'config.py',
    'database.py',
    'runtime_paths.py',
    'android_backend.py',
)
PYTHON_DIRECTORIES = ('routes', 'services', 'models')
ASSET_DIRECTORIES = ('templates', 'static', 'resources', 'skills', 'seed')


def _reset_generated(path: Path) -> None:
    resolved = path.resolve()
    android_resolved = ANDROID_ROOT.resolve()
    if android_resolved not in resolved.parents:
        raise RuntimeError(f'拒绝清理 Android 工程之外的目录：{resolved}')
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _copy_python_tree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'),
    )


def main() -> None:
    _reset_generated(PYTHON_TARGET)
    _reset_generated(ASSET_TARGET)

    for relative in PYTHON_FILES:
        shutil.copy2(ROOT / relative, PYTHON_TARGET / relative)
    for relative in PYTHON_DIRECTORIES:
        _copy_python_tree(ROOT / relative, PYTHON_TARGET / relative)
    for relative in ASSET_DIRECTORIES:
        shutil.copytree(
            ROOT / relative, ASSET_TARGET / relative,
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'),
        )

    files = sorted(
        str(path.relative_to(ASSET_TARGET)).replace('\\', '/')
        for path in ASSET_TARGET.rglob('*')
        if path.is_file()
    )
    manifest = {
        'version': '0.2.0',
        'file_count': len(files),
        'files': files,
    }
    (ASSET_TARGET / 'android-resource-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(f'Android Python sources: {len(PYTHON_FILES)} files + {len(PYTHON_DIRECTORIES)} packages')
    print(f'Android assets: {len(files)} files')


if __name__ == '__main__':
    main()

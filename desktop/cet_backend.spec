# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


ROOT = Path(SPECPATH).parent
BUILD_DEPS = ROOT / 'desktop' / '.python-build-deps'

datas = [
    (str(ROOT / 'templates'), 'templates'),
    (str(ROOT / 'static'), 'static'),
    (str(ROOT / 'resources'), 'resources'),
    (str(ROOT / 'skills'), 'skills'),
    (str(ROOT / 'seed' / 'reading_corpus'), 'seed/reading_corpus'),
    (str(ROOT / 'seed' / 'reading_source_manifest.json'), 'seed'),
]

a = Analysis(
    [str(ROOT / 'desktop_backend.py')],
    pathex=[str(ROOT), str(ROOT / '.runtime_deps'), str(ROOT / '.deps'), str(BUILD_DEPS)],
    binaries=[],
    datas=datas,
    hiddenimports=['waitress', 'waitress.server'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='cet-backend-x86_64-pc-windows-msvc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=True,
)

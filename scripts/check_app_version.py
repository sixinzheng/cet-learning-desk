"""在构建与发布前确认三端版本完全一致。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_version import ANDROID_VERSION_CODE, APP_VERSION


def require(pattern: str, text: str, label: str) -> None:
    if not re.search(pattern, text, re.MULTILINE):
        raise SystemExit(f"版本不一致：{label}")


def main() -> None:
    tauri = json.loads((ROOT / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "desktop/package.json").read_text(encoding="utf-8"))
    cargo = (ROOT / "desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8")
    gradle = (ROOT / "android/app/build.gradle").read_text(encoding="utf-8")
    java = (ROOT / "android/app/src/main/java/cn/cet/learningdesk/MainActivity.java").read_text(encoding="utf-8")
    prepare = (ROOT / "android/prepare_android.py").read_text(encoding="utf-8")
    if tauri["version"] != APP_VERSION or package["version"] != APP_VERSION:
        raise SystemExit("版本不一致：Tauri 或 desktop/package.json")
    require(rf'^version\s*=\s*"{re.escape(APP_VERSION)}"', cargo, "Cargo.toml")
    require(rf"versionName\s+'{re.escape(APP_VERSION)}'", gradle, "Android versionName")
    require(rf"versionCode\s+{ANDROID_VERSION_CODE}\b", gradle, "Android versionCode")
    require(rf'RESOURCE_VERSION\s*=\s*"{re.escape(APP_VERSION)}"', java, "Android resources")
    require(rf"'version':\s*'{re.escape(APP_VERSION)}'", prepare, "Android resource manifest")
    print(f"Version contract OK: {APP_VERSION} / Android {ANDROID_VERSION_CODE}")


if __name__ == "__main__":
    main()

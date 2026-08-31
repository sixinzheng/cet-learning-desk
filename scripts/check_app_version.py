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
    signer = (ROOT / "android/sign_android.ps1").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    if tauri["version"] != APP_VERSION or package["version"] != APP_VERSION:
        raise SystemExit("版本不一致：Tauri 或 desktop/package.json")
    require(rf'^version\s*=\s*"{re.escape(APP_VERSION)}"', cargo, "Cargo.toml")
    require(rf"versionName\s+'{re.escape(APP_VERSION)}'", gradle, "Android versionName")
    require(rf"versionCode\s+{ANDROID_VERSION_CODE}\b", gradle, "Android versionCode")
    require(r'RESOURCE_VERSION\s*=\s*BuildConfig\.VERSION_NAME', java, "Android resources")
    require(r"'version':\s*APP_VERSION", prepare, "Android resource manifest")
    require(r'\$versionSource\s*=\s*Get-Content.*app_version\.py', signer, "Android signed artifact version source")
    require(r'CET-Learning-Desk-Android-arm64-v\$appVersion\.apk', signer, "Android signed artifact name")
    require(r'android_version_code=.*ANDROID_VERSION_CODE', workflow, "Release Android version code source")
    require(r'--android-version-code\s+"\$android_version_code"', workflow, "Release Android manifest version code")
    require(r'notes_file="docs/releases/\$\{GITHUB_REF_NAME\}\.md"', workflow, "Versioned release notes source")
    require(r'--notes-file\s+"\$notes_file"', workflow, "Updater manifest release notes")
    notes_file = ROOT / f"docs/releases/v{APP_VERSION}.md"
    if not notes_file.is_file() or not notes_file.read_text(encoding="utf-8").strip():
        raise SystemExit(f"版本不一致：缺少发布说明 {notes_file.relative_to(ROOT)}")
    print(f"Version contract OK: {APP_VERSION} / Android {ANDROID_VERSION_CODE}")


if __name__ == "__main__":
    main()

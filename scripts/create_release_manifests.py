"""根据已签名构建产物生成固定 Release 更新清单。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY = "https://github.com/sixinzheng/cet-learning-desk"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--android-version-code", required=True, type=int)
    parser.add_argument("--windows", required=True, type=Path)
    parser.add_argument("--windows-signature", required=True, type=Path)
    parser.add_argument("--android", required=True, type=Path)
    parser.add_argument("--notes-file", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    version = args.version.lstrip("v")
    tag = f"v{version}"
    base = f"{REPOSITORY}/releases/download/{tag}"
    args.output.mkdir(parents=True, exist_ok=True)
    published = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    notes = "稳定版更新。完整说明请查看 GitHub Release。"
    if args.notes_file:
        if not args.notes_file.is_file():
            parser.error(f"release notes file not found: {args.notes_file}")
        notes = args.notes_file.read_text(encoding="utf-8").strip()
        if not notes:
            parser.error("release notes file is empty")
    latest = {
        "version": version,
        "notes": notes,
        "pub_date": published,
        "platforms": {
            "windows-x86_64": {
                "signature": args.windows_signature.read_text(encoding="utf-8").strip(),
                "url": f"{base}/{args.windows.name}",
            }
        },
    }
    android = {
        "version": version,
        "version_code": args.android_version_code,
        "published_at": published,
        "notes": notes,
        "apk_url": f"{base}/{args.android.name}",
        "size": args.android.stat().st_size,
        "sha256": sha256(args.android),
        "package_name": "cn.cet.learningdesk",
    }
    (args.output / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "android-latest.json").write_text(json.dumps(android, ensure_ascii=False, indent=2), encoding="utf-8")
    sums = [
        f"{sha256(args.windows)}  {args.windows.name}",
        f"{sha256(args.android)}  {args.android.name}",
    ]
    (args.output / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

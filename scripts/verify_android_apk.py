"""Verify that a built Android APK contains the complete offline runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile


ASSET_PREFIX = "assets/app_resources/"
RESOURCE_MANIFEST = f"{ASSET_PREFIX}android-resource-manifest.json"
SEED_ENTRY = f"{ASSET_PREFIX}resources/distribution/vocab.seed.db"
PRONUNCIATION_ENTRY = (
    f"{ASSET_PREFIX}resources/pronunciation/pronunciation-pack-v1.zip"
)


class VerificationError(RuntimeError):
    """Raised when an APK is signed or published without its offline runtime."""


def _digest_stream(stream) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def _digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return _digest_stream(stream)


def _normalized_entry_names(archive: zipfile.ZipFile) -> set[str]:
    """Include the UTF-8 spelling used by AAPT when its ZIP flag is absent."""
    names: set[str] = set()
    for name in archive.namelist():
        names.add(name)
        try:
            names.add(name.encode("cp437").decode("utf-8"))
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return names


def verify_apk(
    apk: Path,
    *,
    seed: Path,
    pronunciation_pack: Path,
    expected_version: str | None = None,
) -> dict[str, object]:
    if not apk.is_file():
        raise VerificationError(f"APK does not exist: {apk}")
    for label, path in (("seed database", seed), ("pronunciation pack", pronunciation_pack)):
        if not path.is_file():
            raise VerificationError(f"Source {label} does not exist: {path}")

    try:
        archive = zipfile.ZipFile(apk, "r")
    except (OSError, zipfile.BadZipFile) as error:
        raise VerificationError(f"APK is not a readable ZIP archive: {apk}") from error

    with archive:
        names = _normalized_entry_names(archive)
        required = {RESOURCE_MANIFEST, SEED_ENTRY, PRONUNCIATION_ENTRY}
        missing = sorted(required - names)
        if missing:
            raise VerificationError(
                "APK is missing required offline assets: " + ", ".join(missing)
            )

        try:
            manifest = json.loads(archive.read(RESOURCE_MANIFEST).decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise VerificationError("APK resource manifest is unreadable") from error
        if expected_version and manifest.get("version") != expected_version:
            raise VerificationError(
                f"APK resource version mismatch: expected {expected_version}, "
                f"found {manifest.get('version')}"
            )

        manifest_files = manifest.get("files")
        if not isinstance(manifest_files, list) or not manifest_files:
            raise VerificationError("APK resource manifest has no file inventory")
        missing_manifest_files = [
            relative
            for relative in manifest_files
            if not isinstance(relative, str) or f"{ASSET_PREFIX}{relative}" not in names
        ]
        if missing_manifest_files:
            raise VerificationError(
                f"APK is missing {len(missing_manifest_files)} files declared by its resource manifest: "
                + ", ".join(str(item) for item in missing_manifest_files[:5])
            )

        with archive.open(SEED_ENTRY) as stream:
            header = stream.read(16)
        if header != b"SQLite format 3\x00":
            raise VerificationError("APK seed database does not have a valid SQLite header")

        with archive.open(SEED_ENTRY) as stream:
            embedded_seed_hash = _digest_stream(stream)
        if embedded_seed_hash != _digest_file(seed):
            raise VerificationError("APK seed database differs from the release seed")

        with archive.open(PRONUNCIATION_ENTRY) as stream:
            embedded_pronunciation_hash = _digest_stream(stream)
        if embedded_pronunciation_hash != _digest_file(pronunciation_pack):
            raise VerificationError("APK pronunciation pack differs from the verified source pack")

    return {
        "version": manifest.get("version"),
        "resource_files": len(manifest_files),
        "apk_bytes": apk.stat().st_size,
        "seed_sha256": embedded_seed_hash,
        "pronunciation_sha256": embedded_pronunciation_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument(
        "--seed", type=Path, default=Path("resources/distribution/vocab.seed.db")
    )
    parser.add_argument(
        "--pronunciation-pack",
        type=Path,
        default=Path("resources/pronunciation/pronunciation-pack-v1.zip"),
    )
    parser.add_argument("--version")
    args = parser.parse_args()
    try:
        result = verify_apk(
            args.apk,
            seed=args.seed,
            pronunciation_pack=args.pronunciation_pack,
            expected_version=args.version,
        )
    except VerificationError as error:
        print(f"Android APK verification failed: {error}", file=sys.stderr)
        return 1
    print(
        "Android APK offline runtime OK: "
        f"version={result['version']}, resources={result['resource_files']}, "
        f"bytes={result['apk_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Download the immutable pronunciation asset used by release builds."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen


DEFAULT_URL = (
    'https://github.com/sixinzheng/cet-learning-desk/releases/download/'
    'pronunciation-v1/pronunciation-pack-v1.zip'
)
MAX_BYTES = 250 * 1024 * 1024


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default=DEFAULT_URL)
    parser.add_argument('--manifest', type=Path, default=Path('resources/pronunciation/manifest.json'))
    parser.add_argument('--output', type=Path, default=Path('resources/pronunciation/pronunciation-pack-v1.zip'))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    expected = str(manifest.get('pack_sha256') or '').lower()
    if len(expected) != 64:
        raise SystemExit('Pronunciation manifest does not contain a release checksum.')
    if args.output.is_file() and file_sha256(args.output) == expected:
        print(f'Pronunciation pack already verified: {args.output}')
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    request = Request(args.url, headers={'User-Agent': 'CETLearningDesk-Build/1'})
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix='pronunciation-', suffix='.zip', dir=args.output.parent, delete=False
        ) as target:
            temporary = Path(target.name)
            with urlopen(request, timeout=60) as response:
                content_length = int(response.headers.get('Content-Length') or 0)
                if content_length > MAX_BYTES:
                    raise RuntimeError('Pronunciation download exceeds the 250 MB ceiling.')
                copied = 0
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    copied += len(block)
                    if copied > MAX_BYTES:
                        raise RuntimeError('Pronunciation download exceeds the 250 MB ceiling.')
                    target.write(block)
        if file_sha256(temporary) != expected:
            raise RuntimeError('Pronunciation pack checksum mismatch; the downloaded file was rejected.')
        shutil.move(str(temporary), str(args.output))
        temporary = None
        print(f'Pronunciation pack downloaded and verified: {args.output}')
        return 0
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


if __name__ == '__main__':
    raise SystemExit(main())

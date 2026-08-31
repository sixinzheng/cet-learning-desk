"""Fail a release build when the offline pronunciation pack is incomplete."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zipfile


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, default=Path('data/vocab.db'))
    parser.add_argument('--manifest', type=Path, default=Path('resources/pronunciation/manifest.json'))
    parser.add_argument('--pack', type=Path, default=Path('resources/pronunciation/pronunciation-pack-v1.zip'))
    parser.add_argument('--max-bytes', type=int, default=250 * 1024 * 1024)
    args = parser.parse_args()
    if not args.database.is_file():
        raise SystemExit(f'Pronunciation verification database is missing: {args.database}')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    connection = sqlite3.connect(args.database)
    try:
        expected_ids = {str(row[0]) for row in connection.execute('SELECT id FROM words')}
        expected_sentence_ids = {str(row[0]) for row in connection.execute('''
            SELECT s.id FROM sentences s
            WHERE s.translation != ''
              AND s.id = (
                SELECT MIN(first_sentence.id) FROM sentences first_sentence
                WHERE first_sentence.word_id=s.word_id AND first_sentence.translation != ''
              )
        ''')}
        expected_scenario_ids = {str(row[0]) for row in connection.execute(
            "SELECT id FROM listening_scenarios WHERE layer='dialogue' AND is_active=1"
        )}
    finally:
        connection.close()
    entries = manifest.get('entries') or {}
    listening = manifest.get('listening') or {}
    sentence_entries = listening.get('sentences') or {}
    scenario_entries = listening.get('scenarios') or {}
    if set(entries) != expected_ids:
        missing = len(expected_ids - set(entries))
        extra = len(set(entries) - expected_ids)
        raise SystemExit(f'Pronunciation index mismatch: missing={missing}, extra={extra}')
    if set(sentence_entries) != expected_sentence_ids:
        raise SystemExit('Listening sentence pronunciation index mismatch.')
    if set(scenario_entries) != expected_scenario_ids:
        raise SystemExit('Listening scenario pronunciation index mismatch.')
    if not args.pack.is_file() or args.pack.stat().st_size > args.max_bytes:
        raise SystemExit('Pronunciation pack is missing or exceeds the release size ceiling.')
    if digest(args.pack) != manifest.get('pack_sha256'):
        raise SystemExit('Pronunciation pack checksum mismatch.')
    with zipfile.ZipFile(args.pack, 'r') as archive:
        names = set(archive.namelist())
        for word_id, item in entries.items():
            path = item.get('path')
            if path not in names or archive.getinfo(path).file_size <= 0:
                raise SystemExit(f'Missing or empty audio entry for word {word_id}.')
        for category, indexed in (('sentence', sentence_entries), ('scenario', scenario_entries)):
            for item_id, item in indexed.items():
                path = item.get('path')
                if path not in names or archive.getinfo(path).file_size <= 0:
                    raise SystemExit(f'Missing or empty audio entry for {category} {item_id}.')
    print(
        f'Pronunciation pack OK: {len(entries)} words, '
        f'{len(sentence_entries)} sentences, {len(scenario_entries)} scenarios, '
        f'{args.pack.stat().st_size} bytes'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())

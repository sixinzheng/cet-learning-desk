"""Generate the versioned US-English pronunciation pack.

Build-only dependencies:
    pip install piper-tts==1.3.0 lameenc==1.8.1

The script is resumable: encoded MP3 files remain in --cache-dir until the ZIP
and manifest have been written successfully.
"""

from __future__ import annotations

import argparse
from array import array
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import wave
import zipfile


_WORKER_VOICE = None
_WORKER_LAMEENC = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, default=Path('data/vocab.db'))
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=Path('resources/pronunciation'))
    parser.add_argument('--cache-dir', type=Path, default=Path('.pronunciation-cache'))
    parser.add_argument('--limit', type=int, default=0, help='Development-only limit; 0 builds every word.')
    parser.add_argument('--workers', type=int, default=min(4, max(1, os.cpu_count() or 1)))
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def file_metadata(path: Path) -> tuple[int, str]:
    return path.stat().st_size, sha256(path)


def _trim_and_normalize(pcm: bytes, sample_rate: int) -> bytes:
    """Trim long silence and normalize peaks without changing the spoken content."""
    samples = array('h')
    samples.frombytes(pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    if not samples:
        return pcm
    threshold = 180
    start = next((i for i, value in enumerate(samples) if abs(value) >= threshold), 0)
    end = next((i for i in range(len(samples) - 1, -1, -1) if abs(samples[i]) >= threshold), len(samples) - 1)
    padding = int(sample_rate * 0.035)
    start = max(0, start - padding)
    end = min(len(samples), end + padding + 1)
    samples = samples[start:end]
    peak = max((abs(value) for value in samples), default=0)
    if peak:
        scale = min(6.0, (32767 * 0.90) / peak)
        samples = array('h', (max(-32768, min(32767, round(value * scale))) for value in samples))
    if sys.byteorder != 'little':
        samples.byteswap()
    return samples.tobytes()


def encode_word(voice, encoder, text: str) -> bytes:
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        voice.synthesize_wav(text, wav_file)
    wav_buffer.seek(0)
    with wave.open(wav_buffer, 'rb') as wav_file:
        if wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
            raise RuntimeError('Piper output must be mono 16-bit PCM.')
        pcm = wav_file.readframes(wav_file.getnframes())
        sample_rate = wav_file.getframerate()
    pcm = _trim_and_normalize(pcm, sample_rate)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(1)
    encoder.set_bit_rate(32)
    encoder.set_quality(2)
    return encoder.encode(pcm) + encoder.flush()


def _init_worker(model: str, config: str) -> None:
    global _WORKER_VOICE, _WORKER_LAMEENC
    import lameenc
    import onnxruntime
    from piper.voice import PiperVoice
    # Piper 1.3 creates a default ONNX session which otherwise starts a large
    # thread pool in every worker. Keep each worker single-threaded and scale
    # predictably with --workers instead of oversubscribing the whole machine.
    original_session_options = onnxruntime.SessionOptions
    def limited_session_options():
        options = original_session_options()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
        return options
    onnxruntime.SessionOptions = limited_session_options
    _WORKER_LAMEENC = lameenc
    try:
        _WORKER_VOICE = PiperVoice.load(model, config_path=config, use_cuda=False)
    finally:
        onnxruntime.SessionOptions = original_session_options


def _encode_cached(task: tuple[str, int, str, str]) -> tuple[str, int, int]:
    category, item_id, text, cache_name = task
    cached = Path(cache_name)
    encoded = encode_word(_WORKER_VOICE, _WORKER_LAMEENC.Encoder(), text)
    temporary = cached.with_suffix(f'.mp3.{os.getpid()}.building')
    temporary.write_bytes(encoded)
    temporary.replace(cached)
    return category, item_id, len(encoded)


def main() -> int:
    args = parse_args()
    try:
        import lameenc  # noqa: F401 - verify build dependency before spawning workers
        from piper.voice import PiperVoice  # noqa: F401
    except ImportError as exc:
        raise SystemExit('Missing build dependency. Install piper-tts==1.3.0 and lameenc==1.8.1.') from exc

    database = args.database.resolve()
    model = args.model.resolve()
    config = args.config.resolve()
    for required in (database, model, config):
        if not required.is_file():
            raise SystemExit(f'Missing required file: {required}')

    connection = sqlite3.connect(database)
    try:
        rows = connection.execute('SELECT id, word FROM words ORDER BY id').fetchall()
        sentence_rows = connection.execute('''
            SELECT s.id, s.word_id, s.content
            FROM sentences s
            WHERE s.translation != ''
              AND s.id = (
                SELECT MIN(first_sentence.id)
                FROM sentences first_sentence
                WHERE first_sentence.word_id = s.word_id
                  AND first_sentence.translation != ''
              )
            ORDER BY s.id
        ''').fetchall()
        scenario_rows = connection.execute('''
            SELECT id, script, question FROM listening_scenarios
            WHERE layer='dialogue' AND is_active=1
            ORDER BY id
        ''').fetchall()
    finally:
        connection.close()
    if args.limit > 0:
        rows = rows[:args.limit]
        allowed_word_ids = {row[0] for row in rows}
        sentence_rows = [row for row in sentence_rows if row[1] in allowed_word_ids]
    if not rows:
        raise SystemExit('No words found.')

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    entries: dict[str, dict[str, str | int]] = {}
    sentence_entries: dict[str, dict[str, str | int]] = {}
    scenario_entries: dict[str, dict[str, str | int]] = {}

    missing = []
    for word_id, word in rows:
        cached = args.cache_dir / f'{word_id}.mp3'
        if not cached.is_file() or cached.stat().st_size == 0:
            missing.append(('word', int(word_id), str(word), str(cached.resolve())))
    for sentence_id, _word_id, content in sentence_rows:
        cached = args.cache_dir / f'sentence-{sentence_id}.mp3'
        if not cached.is_file() or cached.stat().st_size == 0:
            missing.append(('sentence', int(sentence_id), str(content), str(cached.resolve())))
    for scenario_id, script, question in scenario_rows:
        cached = args.cache_dir / f'scenario-{scenario_id}.mp3'
        if not cached.is_file() or cached.stat().st_size == 0:
            spoken_script = re.sub(r'(?m)^[A-Z]\s*:\s*', '', str(script)).strip()
            spoken_text = '. '.join(value for value in (spoken_script, str(question).strip()) if value)
            missing.append(('scenario', int(scenario_id), spoken_text, str(cached.resolve())))

    total_items = len(rows) + len(sentence_rows) + len(scenario_rows)
    completed = total_items - len(missing)
    if completed:
        print(f'resuming with {completed}/{total_items} cached', flush=True)
    if missing:
        worker_count = max(1, min(args.workers, len(missing)))
        with ProcessPoolExecutor(
            max_workers=worker_count,
            initializer=_init_worker,
            initargs=(str(model), str(config)),
        ) as executor:
            futures = [executor.submit(_encode_cached, task) for task in missing]
            for future in as_completed(futures):
                future.result()
                completed += 1
                if completed % 100 == 0 or completed == total_items:
                    print(f'encoded {completed}/{total_items}', flush=True)

    cache_paths = (
        [args.cache_dir / f'{word_id}.mp3' for word_id, _word in rows]
        + [args.cache_dir / f'sentence-{sentence_id}.mp3' for sentence_id, _word_id, _content in sentence_rows]
        + [args.cache_dir / f'scenario-{scenario_id}.mp3' for scenario_id, _script, _question in scenario_rows]
    )
    # Antivirus and Windows filesystem metadata checks dominate this phase when
    # 24k small files are opened one by one. Hash concurrently while keeping the
    # manifest order deterministic.
    hash_workers = min(32, max(4, (os.cpu_count() or 1) * 2))
    with ThreadPoolExecutor(max_workers=hash_workers) as executor:
        metadata = dict(zip(cache_paths, executor.map(file_metadata, cache_paths)))

    for index, (word_id, word) in enumerate(rows, start=1):
        cached = args.cache_dir / f'{word_id}.mp3'
        byte_count, checksum = metadata[cached]
        entries[str(word_id)] = {
            'path': f'words/{word_id}.mp3',
            'word': str(word),
            'bytes': byte_count,
            'sha256': checksum,
        }
    for sentence_id, word_id, content in sentence_rows:
        cached = args.cache_dir / f'sentence-{sentence_id}.mp3'
        byte_count, checksum = metadata[cached]
        sentence_entries[str(sentence_id)] = {
            'path': f'listening/sentences/{sentence_id}.mp3',
            'word_id': int(word_id),
            'text': str(content),
            'bytes': byte_count,
            'sha256': checksum,
        }
    for scenario_id, script, question in scenario_rows:
        cached = args.cache_dir / f'scenario-{scenario_id}.mp3'
        byte_count, checksum = metadata[cached]
        scenario_entries[str(scenario_id)] = {
            'path': f'listening/scenarios/{scenario_id}.mp3',
            'text': '. '.join(value for value in (str(script), str(question)) if value),
            'bytes': byte_count,
            'sha256': checksum,
        }

    output_zip = args.output_dir / 'pronunciation-pack-v1.zip'
    temporary_zip = output_zip.with_suffix('.zip.building')
    with zipfile.ZipFile(temporary_zip, 'w', compression=zipfile.ZIP_STORED) as archive:
        for word_id, item in entries.items():
            archive.write(args.cache_dir / f'{word_id}.mp3', item['path'])
        for sentence_id, item in sentence_entries.items():
            archive.write(args.cache_dir / f'sentence-{sentence_id}.mp3', item['path'])
        for scenario_id, item in scenario_entries.items():
            archive.write(args.cache_dir / f'scenario-{scenario_id}.mp3', item['path'])
    temporary_zip.replace(output_zip)

    manifest = {
        'version': 1,
        'voice': 'en_US-ljspeech-high',
        'format': 'mp3',
        'sample_rate': 22050,
        'bitrate_kbps': 32,
        'word_count': len(entries),
        'database_word_count': len(rows),
        'listening_sentence_count': len(sentence_entries),
        'listening_scenario_count': len(scenario_entries),
        'model_sha256': sha256(model),
        'config_sha256': sha256(config),
        'pack_sha256': sha256(output_zip),
        'entries': entries,
        'listening': {
            'sentences': sentence_entries,
            'scenarios': scenario_entries,
        },
    }
    manifest_path = args.output_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'pack': str(output_zip),
        'manifest': str(manifest_path),
        'words': len(entries),
        'sentences': len(sentence_entries),
        'scenarios': len(scenario_entries),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# Offline pronunciation pack

The application reads `pronunciation-pack-v1.zip` and `manifest.json` from
this directory. The ZIP is a release/build artifact and is deliberately not
committed as thousands of standalone audio files.

Build it with `scripts/build_pronunciation_pack.py` using the pinned
`en_US-ljspeech-high` Piper voice. The pack covers all vocabulary words plus
the fixed sentence and dialogue material used by listening practice. Only
generated MP3 audio is distributed; the Piper runtime and ONNX voice model
remain build-time inputs.

Release builds fetch the immutable ZIP from the `pronunciation-v1` GitHub
Release with `scripts/fetch_pronunciation_pack.py`, then reject it unless its
SHA-256 matches the tracked manifest. Local Android and Windows builds run the
same completeness and 250 MB checks before packaging.

The voice model card identifies the voice as US English, trained from scratch
on the public-domain LJSpeech dataset:

https://huggingface.co/rhasspy/piper-voices/raw/main/en/en_US/ljspeech/high/MODEL_CARD

See `THIRD_PARTY_NOTICES.md` for attribution and build-tool licensing notes.

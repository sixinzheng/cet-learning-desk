"""Upload release signing secrets without printing credentials or secret values.

Secret values are accepted only through stdin as a JSON object. GitHub
credentials are obtained from the configured Git Credential Manager and kept
in memory for the duration of this process.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request

from nacl.public import PublicKey, SealedBox


def github_token() -> str:
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        text=True,
        capture_output=True,
        check=True,
    )
    fields = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    token = fields.get("password", "")
    if not token:
        raise RuntimeError("Git Credential Manager did not return a GitHub token.")
    return token


def request_json(url: str, token: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CETLearningDesk-ReleaseSetup/0.3.0",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"GitHub API returned HTTP {error.code}: {message}") from None
    return json.loads(raw) if raw else {}


def encrypted_value(public_key: str, value: str) -> str:
    key = PublicKey(base64.b64decode(public_key))
    encrypted = SealedBox(key).encrypt(value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="sixinzheng/cet-learning-desk")
    args = parser.parse_args()
    if args.repo != "sixinzheng/cet-learning-desk":
        raise RuntimeError("Refusing to configure an unexpected repository.")

    secrets = json.load(sys.stdin)
    if not isinstance(secrets, dict) or not secrets:
        raise RuntimeError("No release secrets were provided on stdin.")
    allowed = {
        "TAURI_SIGNING_PRIVATE_KEY",
        "ANDROID_KEYSTORE_BASE64",
        "ANDROID_KEYSTORE_PASSWORD",
        "ANDROID_KEY_ALIAS",
    }
    unexpected = set(secrets) - allowed
    if unexpected:
        raise RuntimeError(f"Unexpected secret names: {', '.join(sorted(unexpected))}")
    if any(not isinstance(value, str) or not value for value in secrets.values()):
        raise RuntimeError("Every supplied release secret must be a non-empty string.")

    token = github_token()
    key_url = f"https://api.github.com/repos/{args.repo}/actions/secrets/public-key"
    public = request_json(key_url, token)
    key_id = public.get("key_id")
    key_value = public.get("key")
    if not key_id or not key_value:
        raise RuntimeError("GitHub did not return an Actions secret public key.")

    for name, value in secrets.items():
        url = f"https://api.github.com/repos/{args.repo}/actions/secrets/{name}"
        request_json(
            url,
            token,
            method="PUT",
            payload={"encrypted_value": encrypted_value(key_value, value), "key_id": key_id},
        )
        print(f"Configured GitHub Actions secret: {name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Release secret setup failed: {error}", file=sys.stderr)
        raise SystemExit(1)

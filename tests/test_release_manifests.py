import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from scripts import create_release_manifests


class ReleaseManifestTests(unittest.TestCase):
    def test_versioned_notes_are_shared_by_windows_and_android_manifests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            windows = root / "CETLearningDesk-Windows-x64-v0.3.1-setup.exe"
            signature = root / f"{windows.name}.sig"
            android = root / "CETLearningDesk-Android-arm64-v0.3.1.apk"
            notes_file = root / "v0.3.1.md"
            output = root / "dist"
            windows.write_bytes(b"windows-installer")
            signature.write_text("signed-update", encoding="utf-8")
            android.write_bytes(b"android-apk")
            notes = "v0.3.1 user-facing notes\n\nAndroid users must overwrite-install."
            notes_file.write_text(notes, encoding="utf-8")

            argv = [
                "create_release_manifests.py",
                "--version", "0.3.1",
                "--android-version-code", "4",
                "--windows", str(windows),
                "--windows-signature", str(signature),
                "--android", str(android),
                "--notes-file", str(notes_file),
                "--output", str(output),
            ]
            with mock.patch.object(sys, "argv", argv):
                create_release_manifests.main()

            latest = json.loads((output / "latest.json").read_text(encoding="utf-8"))
            android_latest = json.loads((output / "android-latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["notes"], notes)
            self.assertEqual(android_latest["notes"], notes)
            self.assertEqual(android_latest["version_code"], 4)
            self.assertEqual(latest["platforms"]["windows-x86_64"]["signature"], "signed-update")

    def test_empty_release_notes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            windows = root / "windows.exe"
            signature = root / "windows.exe.sig"
            android = root / "android.apk"
            notes_file = root / "notes.md"
            for path in (windows, signature, android):
                path.write_bytes(b"test")
            notes_file.write_text("   \n", encoding="utf-8")
            argv = [
                "create_release_manifests.py",
                "--version", "0.3.1",
                "--android-version-code", "4",
                "--windows", str(windows),
                "--windows-signature", str(signature),
                "--android", str(android),
                "--notes-file", str(notes_file),
                "--output", str(root / "dist"),
            ]
            with mock.patch.object(sys, "argv", argv), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    create_release_manifests.main()


if __name__ == "__main__":
    unittest.main()

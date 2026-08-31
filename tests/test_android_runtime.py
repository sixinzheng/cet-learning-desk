import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import json
import zipfile

import android_backend
from android import prepare_android
from scripts.verify_android_apk import (
    VerificationError,
    _normalized_entry_names,
    verify_apk,
)


class AndroidRuntimeTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_unpacked_resource_root_is_available_for_seed_imports(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            seed = root / "seed"
            seed.mkdir()
            (seed / "runtime_probe.py").write_text(
                "VALUE = 'android-seed-import-ok'\n", encoding="utf-8"
            )

            original_path = list(sys.path)
            try:
                resolved = android_backend._activate_resource_imports(str(root))
                module = importlib.import_module("seed.runtime_probe")
                self.assertEqual(resolved, os.path.abspath(str(root)))
                self.assertEqual(module.VALUE, "android-seed-import-ok")
            finally:
                sys.path[:] = original_path
                sys.modules.pop("seed.runtime_probe", None)
                sys.modules.pop("seed", None)

    def test_missing_resource_root_is_rejected_before_app_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            with self.assertRaisesRegex(RuntimeError, "Android 资源目录不存在"):
                android_backend._activate_resource_imports(str(missing))

    def test_prepare_probe_uses_generated_python_and_unpacked_assets(self):
        completed = mock.Mock(stdout="Android runtime imports OK\n")
        with mock.patch("android.prepare_android.subprocess.run", return_value=completed) as run:
            prepare_android._validate_runtime_imports()
        command = run.call_args.args[0]
        self.assertEqual(command[1:3], ["-I", "-c"])
        self.assertIn(str(prepare_android.PYTHON_TARGET.resolve()), command)
        self.assertIn(str(prepare_android.ASSET_TARGET.resolve()), command)
        self.assertTrue(run.call_args.kwargs["check"])

    def test_pronunciation_verification_uses_release_seed_database(self):
        completed = mock.Mock(returncode=0, stdout="Pronunciation pack OK\n", stderr="")
        with mock.patch("android.prepare_android.subprocess.run", return_value=completed) as run:
            prepare_android._verify_pronunciation_pack()
        command = run.call_args.args[0]
        database_index = command.index("--database") + 1
        self.assertEqual(Path(command[database_index]), prepare_android.SEED_DATABASE)
        self.assertNotIn(str(prepare_android.ROOT / "data" / "vocab.db"), command)

    def _build_apk_fixture(self, root: Path, *, include_seed: bool = True):
        seed = root / "vocab.seed.db"
        seed.write_bytes(b"SQLite format 3\x00" + b"\x00" * 1024)
        pronunciation = root / "pronunciation-pack-v1.zip"
        pronunciation.write_bytes(b"pronunciation-fixture")
        files = ["resources/pronunciation/pronunciation-pack-v1.zip"]
        if include_seed:
            files.append("resources/distribution/vocab.seed.db")
        manifest = {"version": "9.9.9", "file_count": len(files), "files": files}
        apk = root / "fixture.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr(
                "assets/app_resources/android-resource-manifest.json",
                json.dumps(manifest),
            )
            archive.writestr(
                "assets/app_resources/resources/pronunciation/pronunciation-pack-v1.zip",
                pronunciation.read_bytes(),
            )
            if include_seed:
                archive.writestr(
                    "assets/app_resources/resources/distribution/vocab.seed.db",
                    seed.read_bytes(),
                )
        return apk, seed, pronunciation

    def test_apk_verifier_accepts_complete_offline_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            apk, seed, pronunciation = self._build_apk_fixture(Path(temp_dir))
            result = verify_apk(
                apk,
                seed=seed,
                pronunciation_pack=pronunciation,
                expected_version="9.9.9",
            )
        self.assertEqual(result["resource_files"], 2)

    def test_apk_verifier_rejects_shell_without_seed_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            apk, seed, pronunciation = self._build_apk_fixture(
                Path(temp_dir), include_seed=False
            )
            with self.assertRaisesRegex(VerificationError, "vocab.seed.db"):
                verify_apk(
                    apk,
                    seed=seed,
                    pronunciation_pack=pronunciation,
                    expected_version="9.9.9",
                )

    def test_apk_verifier_normalizes_aapt_utf8_names_without_zip_flag(self):
        original = "assets/app_resources/seed/reading_corpus/教育.json"
        mojibake = original.encode("utf-8").decode("cp437")
        archive = mock.Mock()
        archive.namelist.return_value = [mojibake]
        self.assertIn(original, _normalized_entry_names(archive))

    def test_android_assets_exclude_impeccable_development_cache(self):
        self.assertIn(".impeccable", prepare_android.ASSET_IGNORE_PATTERNS)

    def test_release_workflow_stops_and_checks_built_apk(self):
        workflow = (self.ROOT / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Android resource preparation failed", workflow)
        self.assertIn("scripts/verify_android_apk.py", workflow)
        self.assertIn("Android APK offline runtime verification failed", workflow)

    def test_secure_store_reports_only_durable_writes(self):
        source = (self.ROOT / "android/app/src/main/java/cn/cet/learningdesk/SecureStore.java").read_text(
            encoding="utf-8"
        )
        self.assertIn(".commit()", source)
        self.assertNotIn(".apply()", source)
        self.assertIn("API Key 安全配置写入失败", source)

    def test_native_updater_keeps_fixed_verified_cancel_safe_contract(self):
        source = (self.ROOT / "android/app/src/main/java/cn/cet/learningdesk/MainActivity.java").read_text(
            encoding="utf-8"
        )
        required = [
            "https://github.com/sixinzheng/cet-learning-desk/releases/latest/download/android-latest.json",
            'expectedHash.matches("[0-9a-f]{64}")',
            "versionCode <= BuildConfig.VERSION_CODE",
            "expectedHash.equals(sha256(apk))",
            "verifyApkIdentity(apk, versionCode)",
            "Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES",
            'notifyUpdate("cancelled"',
            "apk.delete()",
        ]
        for contract in required:
            self.assertIn(contract, source)

        test_probe = self.ROOT / (
            "android/app/src/androidTest/java/cn/cet/learningdesk/"
            "UpgradeProbeInstrumentation.java"
        )
        self.assertTrue(test_probe.is_file())
        self.assertFalse(
            (self.ROOT / "android/app/src/main/java/cn/cet/learningdesk/UpgradeProbeInstrumentation.java").exists()
        )


if __name__ == "__main__":
    unittest.main()

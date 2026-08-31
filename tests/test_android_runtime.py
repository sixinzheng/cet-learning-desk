import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import android_backend
from android import prepare_android


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

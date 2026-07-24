import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from updater import (
    _extract_windows_executable,
    download_release,
    is_newer_version,
    launch_windows_replacement,
    select_release_asset,
    version_tuple,
)


class UpdaterTests(unittest.TestCase):
    def test_version_comparison_is_numeric(self):
        self.assertEqual(version_tuple("v1.10.2"), (1, 10, 2))
        self.assertTrue(is_newer_version("1.10.0", "1.9.9"))
        self.assertFalse(is_newer_version("1.1.1", "1.1.1"))

    def test_windows_prefers_executable(self):
        assets = [
            {"name": "Petpet-v2-macOS-arm64.zip", "browser_download_url": "mac"},
            {"name": "Petpet-v2-windows.zip", "browser_download_url": "zip"},
            {"name": "Petpet.exe", "browser_download_url": "exe"},
        ]
        selected = select_release_asset(
            assets, platform_name="win32", machine="AMD64"
        )
        self.assertEqual(selected["browser_download_url"], "exe")

    def test_macos_selects_matching_architecture(self):
        assets = [
            {"name": "Petpet-v2-macOS-intel.zip", "browser_download_url": "intel"},
            {"name": "Petpet-v2-macOS-arm64.zip", "browser_download_url": "arm"},
        ]
        arm = select_release_asset(
            assets, platform_name="darwin", machine="arm64"
        )
        intel = select_release_asset(
            assets, platform_name="darwin", machine="x86_64"
        )
        self.assertEqual(arm["browser_download_url"], "arm")
        self.assertEqual(intel["browser_download_url"], "intel")

    def test_extracts_petpet_exe_from_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive_path = root / "update.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("release/Petpet.exe", b"new executable")
            extracted = _extract_windows_executable(
                archive_path, root / "staging"
            )
            self.assertEqual(extracted.read_bytes(), b"new executable")

    def test_download_validates_size_and_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.exe"
            payload = b"verified update"
            source.write_bytes(payload)
            info = {
                "asset_name": "Petpet.exe",
                "download_url": source.as_uri(),
                "asset_size": len(payload),
                "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            }
            result = download_release(info, root / "downloads")
            self.assertTrue(result["ok"])
            self.assertEqual(Path(result["path"]).read_bytes(), payload)

    def test_windows_replacement_uses_hidden_powershell(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            downloaded = root / "Petpet.exe"
            downloaded.write_bytes(b"new executable")
            current = root / "current" / "Petpet.exe"
            current.parent.mkdir()
            with patch("updater.subprocess.Popen") as popen:
                result = launch_windows_replacement(
                    downloaded, current, root / "更新缓存", process_id=1234
                )
            self.assertTrue(result["ok"])
            command = popen.call_args.args[0]
            self.assertEqual(command[0], "powershell.exe")
            self.assertIn("-WindowStyle", command)
            helper = root / "更新缓存" / "apply-update.ps1"
            script = helper.read_text(encoding="utf-8-sig")
            self.assertIn("Wait-Process -Id $petProcessId", script)
            self.assertIn("Copy-Item -LiteralPath", script)


if __name__ == "__main__":
    unittest.main()

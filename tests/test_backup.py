"""存档备份（2026-09-11）：backup 模块纯逻辑 + 设置页接线。"""

import glob
import os
import unittest
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from petpet.app import backup


def make_data_dir(tmp_path):
    files = {
        "pet_state.json": '{"level": 3}',
        "pet_settings.json": '{"a": 1}',
        "memory.json": '{"history": []}',
        "memory-ice_cream.json": '{"history": []}',
        "chat_quota_state.json": '{}',
        "player_avatar.png": b"\x89PNG fake",
        "config.json": '{"api_key": "SECRET"}',
    }
    for name, content in files.items():
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(os.path.join(tmp_path, name), mode) as fh:
            fh.write(content)
    return tmp_path


class BackupModuleTests(unittest.TestCase):
    def test_zip_contains_player_data_but_not_api_key(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = make_data_dir(tmp)
            dest = os.path.join(tmp, "out.zip")
            count = backup.create_backup_zip(dest, data_dir=root)
            self.assertEqual(count, 6)
            with zipfile.ZipFile(dest) as bundle:
                names = set(bundle.namelist())
            self.assertIn("pet_state.json", names)
            self.assertIn("memory-ice_cream.json", names)
            self.assertIn("player_avatar.png", names)
            self.assertNotIn("config.json", names)

    def test_backup_now_rotates_to_keep_five(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = make_data_dir(tmp)
            # 预置 6 份旧备份
            folder = backup.backup_dir(root)
            for i in range(6):
                open(os.path.join(
                    folder, f"petpet-backup-2020010{i}-000000.zip"),
                    "w").close()
            path, count = backup.backup_now(root)
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(count, 6)
            remaining = glob.glob(
                os.path.join(folder, "petpet-backup-*.zip"))
            self.assertEqual(len(remaining), backup.KEEP)
            # 最旧的被清掉，新写入的还在。
            self.assertTrue(os.path.isfile(path))
            self.assertFalse(os.path.exists(os.path.join(
                folder, "petpet-backup-20200100-000000.zip")))


class SettingsBackupWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_backup_now_reports_into_status_label(self):
        import pet

        class FakePet:
            settings = dict(pet.DEFAULT_SETTINGS)

            def apply_runtime_settings(self, previous):
                pass

        window = pet.SettingsWindow(FakePet())
        self.addCleanup(window.close)
        self.assertTrue(hasattr(window, "backup_now"))
        self.assertTrue(hasattr(window, "export_backup"))
        # conftest 已把 LOCALAPPDATA 指到测试临时目录——这里写的是
        # 沙盒数据目录，不会碰玩家真实存档（曾引发审查误报，特此注明）。
        window.backup_now()
        self.assertIn("已备份", window.status_label.text())


if __name__ == "__main__":
    unittest.main()

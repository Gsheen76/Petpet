import tempfile
import unittest
from pathlib import Path

from app_paths import (
    _copy_missing_data_files,
    _legacy_windows_data_dirs,
    _windows_app_data_dir,
)


class AppPathsTests(unittest.TestCase):
    def test_windows_data_dir_is_independent_of_executable(self):
        target = _windows_app_data_dir({"LOCALAPPDATA": r"C:\Users\Pet\AppData\Local"})
        self.assertEqual(
            Path(target),
            Path(r"C:\Users\Pet\AppData\Local") / "Petpet",
        )

    def test_migration_prefers_original_data_above_legacy_update_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            install_dir = root / "portable"
            cached_dir = install_dir / "updates" / "v1.2.1"
            stable_dir = root / "LocalAppData" / "Petpet"
            cached_dir.mkdir(parents=True)
            (install_dir / "pet_state.json").write_text(
                '{"level": 8, "pet_name": "summer"}', encoding="utf-8"
            )
            (install_dir / "memory.json").write_text(
                '{"history": ["old-memory"]}', encoding="utf-8"
            )
            (cached_dir / "pet_state.json").write_text(
                '{"level": 1}', encoding="utf-8"
            )

            sources = _legacy_windows_data_dirs(cached_dir / "Petpet.exe")
            copied = _copy_missing_data_files(sources, stable_dir)

            self.assertIn("pet_state.json", copied)
            self.assertIn('"level": 8', (
                stable_dir / "pet_state.json"
            ).read_text(encoding="utf-8"))
            self.assertTrue((stable_dir / "memory.json").exists())

    def test_migration_never_overwrites_stable_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy_dir = root / "legacy"
            stable_dir = root / "stable"
            legacy_dir.mkdir()
            stable_dir.mkdir()
            (legacy_dir / "pet_state.json").write_text(
                '{"level": 8}', encoding="utf-8"
            )
            (stable_dir / "pet_state.json").write_text(
                '{"level": 12}', encoding="utf-8"
            )

            _copy_missing_data_files([legacy_dir], stable_dir)

            self.assertIn('"level": 12', (
                stable_dir / "pet_state.json"
            ).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

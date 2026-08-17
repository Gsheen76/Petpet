import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import pet


ROOT = Path(__file__).resolve().parents[1]


class WindowsPackagingTests(unittest.TestCase):
    def test_icon_generation_uses_runtime_asset_paths(self):
        icon_tool = (ROOT / "tools" / "make_icons.py").read_text(
            encoding="utf-8"
        )
        mac_build = (ROOT / "scripts" / "build_macos.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '"assets", "runtime", "pets", "desktop", "poses"',
            icon_tool,
        )
        self.assertIn('"assets", "runtime", "icons"', icon_tool)
        self.assertIn("assets/runtime/icons/", mac_build)
        self.assertNotIn("cp assets/icons/", mac_build)

    def test_build_reuses_complete_local_dependencies_before_pip(self):
        script = (
            ROOT / "scripts" / "build_windows.ps1"
        ).read_text(encoding="utf-8")
        probe = "import PyQt5, PyInstaller, requests, PIL, numpy"
        install = "python -m pip install --upgrade --target"

        self.assertIn(probe, script)
        self.assertIn("if (-not $dependenciesReady)", script)
        self.assertLess(script.index(probe), script.index(install))

    def test_manifest_declares_per_monitor_v2_dpi_awareness(self):
        manifest_path = ROOT / "packaging" / "Petpet-windows.manifest"
        root = ET.parse(manifest_path).getroot()
        values = {
            element.tag.rsplit("}", 1)[-1]: (element.text or "").strip()
            for element in root.iter()
        }
        self.assertEqual(values.get("dpiAware"), "true/pm")
        self.assertEqual(values.get("dpiAwareness"), "PerMonitorV2")

    def test_windows_spec_embeds_custom_manifest(self):
        spec = (
            ROOT / "packaging" / "Petpet-windows.spec"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'manifest=str(project_root / "packaging" / '
            '"Petpet-windows.manifest")',
            spec,
        )
        self.assertIn(
            '(str(runtime_assets_root), "assets/runtime")',
            spec,
        )

    def test_qt_windows_scaling_is_fixed_to_authored_pixels(self):
        source = (ROOT / "pet.py").read_text(encoding="utf-8")
        common_source = (
            ROOT / "petpet" / "ui" / "common.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from petpet.ui.common import (", source)
        self.assertIn("FIXED_FONT_SCALE = 2.0", common_source)
        self.assertIn("def independent_font_px(size):", common_source)
        self.assertIn("def tutorial_font_px(size):", common_source)
        self.assertIn("SETTINGS_FONT_SCALE = 1.08", common_source)
        self.assertNotIn('os.environ["QT_SCALE_FACTOR"]', source)
        self.assertIn("Qt.AA_DisableHighDpiScaling", source)
        self.assertIn("SetProcessDpiAwarenessContext", source)
        self.assertIn("configure_display_scaling()", source)

    def test_platform_pet_sizes_and_macos_tool_window_visibility_are_defined(self):
        source = (ROOT / "petpet" / "app" / "pet_window.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(pet.MACOS_PET_SIZE, (150, 180, 132))
        self.assertEqual(pet.DEFAULT_PET_SIZE, (190, 220, 160))
        self.assertIn("Qt.WA_MacAlwaysShowToolWindow", source)
        self.assertIn('_dependency("MACOS_PET_SIZE")', source)
        self.assertIn('_dependency("DEFAULT_PET_SIZE")', source)


if __name__ == "__main__":
    unittest.main()

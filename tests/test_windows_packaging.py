import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowsPackagingTests(unittest.TestCase):
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
            '(str(assets_root / "props"), "assets/props")',
            spec,
        )

    def test_qt_windows_scaling_is_fixed_to_authored_pixels(self):
        source = (ROOT / "pet.py").read_text(encoding="utf-8")
        self.assertIn("FIXED_FONT_SCALE = 2.0", source)
        self.assertIn("def independent_font_px(size):", source)
        self.assertIn("def tutorial_font_px(size):", source)
        self.assertIn("SETTINGS_FONT_SCALE = 1.08", source)
        self.assertNotIn('os.environ["QT_SCALE_FACTOR"]', source)
        self.assertIn("Qt.AA_DisableHighDpiScaling", source)
        self.assertIn("SetProcessDpiAwarenessContext", source)
        self.assertIn("configure_display_scaling()", source)


if __name__ == "__main__":
    unittest.main()

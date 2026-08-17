import unittest

import pet
from petpet.ui import common


class CommonUiTypographyTests(unittest.TestCase):
    def test_root_pet_reexports_package_typography_api(self):
        names = (
            "FIXED_FONT_SCALE",
            "SETTINGS_FONT_SCALE",
            "font_px",
            "independent_font_px",
            "settings_font_px",
            "tutorial_font_px",
            "pixel_font",
            "independent_pixel_font",
        )
        for name in names:
            self.assertIs(getattr(pet, name), getattr(common, name))

    def test_authored_font_sizes_are_preserved(self):
        self.assertEqual(common.font_px(12), 24)
        self.assertEqual(common.independent_font_px(17), 17)
        self.assertEqual(common.settings_font_px(20), 22)
        self.assertEqual(common.tutorial_font_px(23), 23)
        self.assertEqual(common.pixel_font(12).pixelSize(), 24)
        self.assertEqual(common.independent_pixel_font(17).pixelSize(), 17)


if __name__ == "__main__":
    unittest.main()

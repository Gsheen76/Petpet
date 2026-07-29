import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QRect, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton

import progression
from progression_ui import AchievementsWindow, RecordsWindow, ShopWindow


class ProgressionWindowUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.pet = SimpleNamespace(
            state=progression.ensure_progression({
                "born": 1,
                "level": 3,
                "hunger": 80,
                "mood": 70,
                "energy": 90,
            }),
            current_screen_rect=Mock(return_value=QRect(0, 0, 1200, 900)),
            geometry=Mock(return_value=QRect(900, 600, 190, 220)),
            say=Mock(),
            update=Mock(),
        )
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.close()

    def test_all_three_windows_paint_a_real_background_base(self):
        self.windows = [
            RecordsWindow(self.pet, Mock()),
            AchievementsWindow(self.pet, Mock()),
            ShopWindow(self.pet, Mock()),
        ]

        for window in self.windows:
            self.assertTrue(window.testAttribute(Qt.WA_StyledBackground))
            self.assertEqual(window.objectName(), "cozyProgressWindow")
            window.show()
        QApplication.processEvents()
        for window in self.windows:
            image = window.grab().toImage()
            base = QColor.fromRgba(
                image.pixel(10, window.height() // 2)
            )
            self.assertGreater(base.alpha(), 240)
            self.assertGreater(base.red(), 240)
            self.assertGreater(base.green(), 220)

    def test_shop_uses_separate_decoration_and_upgrade_pages(self):
        shop = ShopWindow(self.pet, Mock())
        self.windows = [shop]

        shop.refresh()
        decoration_text = " ".join(
            label.text() for label in shop.findChildren(QLabel)
        )
        tab_texts = [
            button.text() for button in shop.findChildren(QPushButton)
            if button.objectName() == "tabButton"
        ]
        self.assertTrue(any("第一页 · 装饰" in text for text in tab_texts))
        self.assertTrue(any("第二页 · 强化" in text for text in tab_texts))
        self.assertIn("装饰小铺", decoration_text)
        self.assertIn("暖心红项圈", decoration_text)
        self.assertNotIn("温柔抚摸", decoration_text)

        shop._set_page("upgrades")
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()
        upgrade_text = " ".join(
            label.text() for label in shop.findChildren(QLabel)
        )
        self.assertIn("成长强化", upgrade_text)
        self.assertIn("温柔抚摸", upgrade_text)
        self.assertNotIn("装饰小铺", upgrade_text)

    def test_new_panels_use_the_larger_typography(self):
        shop = ShopWindow(self.pet, Mock())
        self.windows = [shop]
        stylesheet = shop.styleSheet()

        self.assertIn("font-size: 19px", stylesheet)
        self.assertIn("font-size: 30px", stylesheet)

    def test_free_collar_runs_through_claim_equip_and_unequip(self):
        save = Mock()
        shop = ShopWindow(self.pet, save)
        self.windows = [shop]

        shop._purchase_decoration("red_collar")
        self.assertIn(
            "red_collar", self.pet.state["owned_decorations"]
        )
        shop._equip_decoration("red_collar")
        self.assertEqual(
            self.pet.state["equipped_decorations"]["neck"],
            "red_collar",
        )
        shop._unequip_decoration("neck")

        self.assertIsNone(
            self.pet.state["equipped_decorations"]["neck"]
        )
        self.assertEqual(save.call_count, 3)
        self.assertEqual(self.pet.update.call_count, 3)


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPoint, QRect, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton

import progression
from progression_ui import (
    AchievementsWindow,
    DecorationAdjustWindow,
    DecorationPreview,
    DecorationPreviewWindow,
    RecordsWindow,
    ShopWindow,
)


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
            interface_window_position=Mock(return_value=QPoint(700, 180)),
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

    def test_progression_window_uses_active_interface_position(self):
        records = RecordsWindow(self.pet, Mock())
        self.windows = [records]

        records.show_near_pet()

        self.assertEqual(records.pos(), QPoint(700, 180))
        self.pet.interface_window_position.assert_called_once_with(
            records.size(),
            gap=20,
        )

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
        self.assertEqual(tab_texts, ["🎀 装饰", "🏠 家居", "✨ 强化"])
        category_texts = [
            button.text() for button in shop.findChildren(QPushButton)
            if button.objectName() == "categoryTabButton"
        ]
        self.assertEqual(category_texts, ["颈饰", "帽子", "眼镜"])
        self.assertIn("装饰小铺", decoration_text)
        self.assertIn("暖心红项圈", decoration_text)
        self.assertIn("晴空爪印领结", decoration_text)
        self.assertNotIn("奶油贝雷帽", decoration_text)
        self.assertNotIn("暖金圆框眼镜", decoration_text)
        self.assertNotIn("温柔抚摸", decoration_text)

        shop._set_decoration_category("head")
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()
        hat_text = " ".join(
            label.text() for label in shop.findChildren(QLabel)
        )
        self.assertIn("奶油贝雷帽", hat_text)
        self.assertIn("噜噜小橘子", hat_text)
        self.assertNotIn("暖心红项圈", hat_text)

        shop._set_decoration_category("eyes")
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()
        glasses_text = " ".join(
            label.text() for label in shop.findChildren(QLabel)
        )
        self.assertIn("暖金圆框眼镜", glasses_text)
        self.assertIn("酷黑爪印墨镜", glasses_text)
        self.assertNotIn("奶油贝雷帽", glasses_text)

        shop._set_page("upgrades")
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()
        upgrade_text = " ".join(
            label.text() for label in shop.findChildren(QLabel)
        )
        self.assertIn("成长强化", upgrade_text)
        self.assertIn("温柔抚摸", upgrade_text)
        self.assertIn("持久活力", upgrade_text)
        self.assertIn("清醒属性消耗减缓 0%", upgrade_text)
        self.assertIn("清醒属性消耗减缓 10%", upgrade_text)
        self.assertNotIn("装饰小铺", upgrade_text)

    def test_home_shop_page_lists_home_furniture(self):
        shop = ShopWindow(self.pet, Mock())
        self.windows = [shop]

        shop._set_page("home")
        labels = " ".join(label.text() for label in shop.findChildren(QLabel))

        self.assertIn("舒适沙发", labels)
        self.assertIn("绿植盆栽", labels)
        self.assertIn("暖绒地毯", labels)
        self.assertIn("墙面装饰画", labels)

    def test_new_panels_use_the_larger_typography(self):
        shop = ShopWindow(self.pet, Mock())
        self.windows = [shop]
        stylesheet = shop.styleSheet()

        self.assertIn("font-size: 20px", stylesheet)
        self.assertIn("font-size: 33px", stylesheet)
        self.assertIn("QLabel#effectCurrent", stylesheet)
        self.assertIn("QLabel#effectNext", stylesheet)

    def test_achievement_header_shows_completed_over_total(self):
        achievements = AchievementsWindow(self.pet, Mock())
        self.windows = [achievements]

        achievements.refresh()
        texts = [
            label.text() for label in achievements.findChildren(QLabel)
        ]

        self.assertTrue(any(
            text.startswith("已完成 ") and "/" in text
            for text in texts
        ))

    def test_records_include_new_activity_and_collection_counters(self):
        records = RecordsWindow(self.pet, Mock())
        self.windows = [records]

        records.refresh()
        text = " ".join(
            label.text() for label in records.findChildren(QLabel)
        )

        for title in (
            "AI 回复", "自主散步", "收集装扮",
            "更换装扮", "购买强化", "领取成就",
            "小游戏局数", "游戏收入",
        ):
            self.assertIn(title, text)

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

    def test_equipped_decoration_opens_idle_adjustment_editor(self):
        save = Mock()
        shop = ShopWindow(self.pet, save)
        self.windows = [shop]
        shop._purchase_decoration("red_collar")
        shop._equip_decoration("red_collar")

        adjust_buttons = [
            button for button in shop.findChildren(QPushButton)
            if button.text() == "微调位置"
        ]
        self.assertEqual(len(adjust_buttons), 1)

        shop._open_decoration_adjuster("red_collar")
        editor = shop.adjust_window
        self.assertIsInstance(editor, DecorationAdjustWindow)
        labels = [
            label.text() for label in editor.findChildren(QLabel)
        ]
        self.assertNotIn("位置微调", labels)
        button_texts = [
            button.text() for button in editor.findChildren(QPushButton)
        ]
        for arrow in ("←", "↑", "↓", "→"):
            self.assertNotIn(arrow, button_texts)
        self.assertEqual(DecorationPreview.SELECTION_COLOR, "#f2b705")
        before = progression.decoration_transform(
            self.pet.state, "red_collar"
        )
        editor._change(x=0.015, scale=0.035, rotation=2.0)
        after = progression.decoration_transform(
            self.pet.state, "red_collar"
        )

        self.assertGreater(after["x"], before["x"])
        self.assertGreater(after["scale"], before["scale"])
        self.assertGreater(after["rotation"], before["rotation"])
        self.assertGreaterEqual(save.call_count, 3)

    def test_shop_preview_is_non_destructive_and_try_on_equips_copy(self):
        shop = ShopWindow(self.pet, Mock())
        self.windows = [shop]
        original_owned = list(self.pet.state["owned_decorations"])
        original_equipped = dict(self.pet.state["equipped_decorations"])

        shop._open_decoration_preview("black_sunglasses")
        preview = shop.preview_window
        self.assertIsInstance(preview, DecorationPreviewWindow)
        self.assertEqual(self.pet.state["owned_decorations"], original_owned)
        self.assertEqual(
            self.pet.state["equipped_decorations"], original_equipped
        )
        self.assertIn(
            "black_sunglasses", preview.preview_state["owned_decorations"]
        )
        self.assertEqual(
            preview.preview_state["equipped_decorations"]["eyes"],
            "black_sunglasses",
        )
        self.assertFalse(preview.preview.allow_drag)


if __name__ == "__main__":
    unittest.main()

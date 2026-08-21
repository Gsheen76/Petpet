import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPoint, QRect, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QFrame, QGridLayout, QLabel, QPushButton

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

    def test_shop_lists_complete_outfits_and_keeps_upgrade_page(self):
        shop = ShopWindow(self.pet, Mock())
        self.windows = [shop]

        shop.refresh()
        outfit_text = " ".join(
            label.text() for label in shop.findChildren(QLabel)
        )
        tab_texts = [
            button.text() for button in shop.findChildren(QPushButton)
            if button.objectName() == "tabButton"
        ]
        self.assertEqual(tab_texts, ["🎁 套装", "🏠 家居", "✨ 强化"])
        self.assertIn("套装商店", outfit_text)
        self.assertIn("小恐龙套装", outfit_text)
        self.assertIn("680 Pet币", outfit_text)
        self.assertIn("草莓小子套装", outfit_text)
        self.assertIn("760 Pet币", outfit_text)
        self.assertNotIn("暖心红项圈", outfit_text)
        self.assertNotIn("奶油贝雷帽", outfit_text)
        self.assertNotIn("暖金圆框眼镜", outfit_text)
        self.assertNotIn("当前分类", outfit_text)

        preview = shop.findChild(QLabel, "outfitPreview_dinosaur_suit")
        self.assertIsNotNone(preview)
        self.assertIsNotNone(preview.pixmap())
        self.assertFalse(preview.pixmap().isNull())
        strawberry_preview = shop.findChild(
            QLabel, "outfitPreview_strawberry_suit"
        )
        self.assertIsNotNone(strawberry_preview)
        self.assertIsNotNone(strawberry_preview.pixmap())
        self.assertFalse(strawberry_preview.pixmap().isNull())

        shop._set_page("upgrades")
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()
        upgrade_text = " ".join(
            label.text() for label in shop.findChildren(QLabel)
        )
        self.assertIn("成长强化", upgrade_text)
        self.assertIn("温柔抚摸", upgrade_text)
        self.assertIn("持久活力", upgrade_text)
        self.assertIn("提高每次抚摸恢复的心情值", upgrade_text)
        self.assertIn("减缓清醒状态下的属性自然消耗", upgrade_text)
        self.assertIn("清醒属性消耗减缓 0%", upgrade_text)
        self.assertNotIn("当前加成：", upgrade_text)
        self.assertNotIn("套装商店", upgrade_text)

    def test_pet_cards_fit_the_scroll_viewport_without_losing_information(self):
        self.pet.state["pets"] = {
            "lunch_meat": {"name": "午餐肉"},
            "ice_cream": {"name": "冰淇淋"},
        }
        self.pet.state["owned_pet_ids"] = ["lunch_meat", "ice_cream"]
        self.pet.state["active_pet_id"] = "ice_cream"
        shop = ShopWindow(self.pet, Mock())
        self.windows = [shop]

        shop.refresh()
        shop.show()
        QApplication.processEvents()

        viewport = shop.scroll.viewport()
        for pet_id in ("lunch_meat", "ice_cream"):
            card = shop.findChild(QFrame, f"petCard_{pet_id}")
            self.assertIsNotNone(card)
            right = card.mapTo(viewport, card.rect().bottomRight()).x()
            self.assertLessEqual(right, viewport.rect().right())
            description = shop.findChild(QLabel, f"petDescription_{pet_id}")
            self.assertIsNotNone(description)
            self.assertFalse(description.wordWrap())
            self.assertIsNotNone(shop.findChild(QLabel, f"petPrice_{pet_id}"))
            self.assertIsNotNone(shop.findChild(QLabel, f"petStatus_{pet_id}"))
            self.assertIsNotNone(shop.findChild(QPushButton, f"petAction_{pet_id}"))

    def test_outfit_purchase_and_equip_refreshes_the_pet(self):
        save = Mock()
        self.pet.state["pet_coins"] = 680
        shop = ShopWindow(self.pet, save)
        self.windows = [shop]

        shop._purchase_outfit("dinosaur_suit")
        shop._equip_outfit("dinosaur_suit")

        self.assertEqual(
            self.pet.state["owned_outfits"], ["dinosaur_suit"]
        )
        self.assertEqual(
            self.pet.state["equipped_outfit"], "dinosaur_suit"
        )
        self.assertEqual(save.call_count, 2)
        self.assertEqual(self.pet.update.call_count, 2)

    def test_home_shop_page_lists_home_furniture(self):
        shop = ShopWindow(self.pet, Mock())
        self.windows = [shop]

        shop._set_page("home")
        labels = " ".join(label.text() for label in shop.findChildren(QLabel))

        self.assertIn("舒适沙发", labels)
        self.assertIn("绿植盆栽", labels)
        self.assertIn("暖绒地毯", labels)
        self.assertIn("墙面装饰画", labels)
        self.assertIn("小狗状态卡", labels)
        self.assertIn(
            "免费领取",
            [button.text() for button in shop.findChildren(QPushButton)],
        )

    def test_upgrade_shop_uses_two_compact_columns(self):
        shop = ShopWindow(self.pet, Mock())
        self.windows = [shop]

        shop._set_page("upgrades")
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()

        grid = shop.findChild(QGridLayout, "upgradeGrid")
        self.assertIsNotNone(grid)
        self.assertEqual(grid.count(), len(progression.UPGRADE_DEFINITIONS))
        positions = [grid.getItemPosition(index)[:2] for index in range(grid.count())]
        self.assertEqual(positions[:4], [(0, 0), (0, 1), (1, 0), (1, 1)])
        labels = " ".join(label.text() for label in shop.findChildren(QLabel))
        self.assertNotIn("升级后效果", labels)
        self.assertNotIn("本次强化费用", labels)
        cards = [grid.itemAt(index).widget() for index in range(grid.count())]
        self.assertEqual({card.height() for card in cards}, {230})

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

if __name__ == "__main__":
    unittest.main()

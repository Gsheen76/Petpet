"""Pet profile panel: snapshot data and window behaviour."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QMouseEvent

from petpet.app import state as app_state
from petpet.progression import core as progression


def _fresh_state():
    state = app_state.ensure_state_schema({}, "Sheen", str)
    progression.ensure_progression(state)
    return state


class SnapshotTests(unittest.TestCase):
    def test_lunch_meat_default_snapshot(self):
        from petpet.ui.pet_profile import pet_profile_snapshot

        snap = pet_profile_snapshot(_fresh_state(), "lunch_meat")
        self.assertTrue(snap["owned"])
        self.assertTrue(snap["active"])
        self.assertEqual(snap["level"], 1)
        self.assertEqual(snap["xp_next"], 100)
        self.assertEqual(snap["affection_level"], 1)
        self.assertEqual(snap["affection_next"], 30)
        self.assertEqual(len(snap["outfits"]), 2)
        self.assertFalse(any(outfit["equipped"] for outfit in snap["outfits"]))
        self.assertTrue(snap["avatar_path"])
        self.assertTrue(snap["preview_path"])

    def test_unowned_ice_cream_snapshot(self):
        from petpet.ui.pet_profile import pet_profile_snapshot

        snap = pet_profile_snapshot(_fresh_state(), "ice_cream")
        self.assertFalse(snap["owned"])
        self.assertFalse(snap["active"])
        self.assertEqual(snap["price"], 760)
        self.assertEqual(snap["outfits"], [])
        self.assertEqual(snap["name"], "冰淇淋")

    def test_owned_pet_and_outfit_flags(self):
        from petpet.ui.pet_profile import pet_profile_snapshot

        state = _fresh_state()
        state["owned_pet_ids"] = ["lunch_meat", "ice_cream"]
        state["owned_outfits"] = ["dinosaur_suit"]
        state["equipped_outfit"] = "dinosaur_suit"

        ice = pet_profile_snapshot(state, "ice_cream")
        self.assertTrue(ice["owned"])

        lunch = pet_profile_snapshot(state, "lunch_meat")
        dinosaur = next(
            outfit for outfit in lunch["outfits"]
            if outfit["id"] == "dinosaur_suit"
        )
        self.assertTrue(dinosaur["owned"])
        self.assertTrue(dinosaur["equipped"])
        strawberry = next(
            outfit for outfit in lunch["outfits"]
            if outfit["id"] == "strawberry_suit"
        )
        self.assertFalse(strawberry["owned"])

    def test_active_pet_name_falls_back_to_facade(self):
        from petpet.ui.pet_profile import pet_profile_snapshot

        state = _fresh_state()
        state["pet_name"] = "烟花"
        snap = pet_profile_snapshot(state, "lunch_meat")
        self.assertEqual(snap["name"], "烟花")

    def test_outfit_snapshot_keeps_asset_paths(self):
        """套装快照必须保留 asset_folder/preview_asset，否则预览路径解析为 None。"""
        from petpet.ui.pet_profile import pet_profile_snapshot, _outfit_preview_path

        snap = pet_profile_snapshot(_fresh_state(), "lunch_meat")
        for outfit in snap["outfits"]:
            self.assertTrue(outfit["asset_folder"], f"{outfit['id']} 缺 asset_folder")
            self.assertEqual(outfit["preview_asset"], "preview.png")
            path = _outfit_preview_path("lunch_meat", outfit)
            self.assertIsNotNone(path, f"{outfit['id']} 预览图应存在")
            self.assertTrue(os.path.isfile(path))


class ProfileWindowShellTests(unittest.TestCase):
    """新素材空壳页：background 原生尺寸 + base_UI 叠加 + 圆角。"""

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _window(self, state=None):
        from petpet.ui.pet_profile import PetProfileWindow

        pet = SimpleNamespace(
            state=state or _fresh_state(),
            set_active_pet=Mock(return_value={"ok": True}),
            set_pet_name=Mock(),
            update=Mock(),
            say=Mock(),
            home_scene_window=None,
            open_shop=Mock(),
        )
        window = PetProfileWindow(pet, save_state=Mock())
        self.addCleanup(window.close)
        return window, pet

    def test_window_size_matches_unified_panel_size(self):
        from petpet.ui import pet_profile as module

        # 用户定稿：与其他常驻面板统一 850x960（艺术稿 1201x1304 非等比铺满）。
        self.assertEqual((module.ART_W, module.ART_H), (1201, 1304))
        self.assertEqual((module.UNIFIED_W, module.UNIFIED_H), (850, 960))
        window, _ = self._window()
        self.assertEqual((window.width(), window.height()), (850, 960))

    def test_resolve_scale_fits_small_screens(self):
        from PyQt5.QtCore import QRect

        from petpet.ui.pet_profile import _resolve_scale

        self.assertEqual(_resolve_scale(None), 1.0)
        factor = _resolve_scale(QRect(0, 0, 1280, 860))
        self.assertLessEqual(round(960 * factor), 860)
        self.assertGreaterEqual(factor, 0.55)

    def test_close_button_has_hover_and_press_feedback(self):
        from PyQt5.QtTest import QTest

        window, _ = self._window()
        window.show()
        self.app.processEvents()
        button = window._close_button
        # 用户定稿：悬停不再描边（描边已移除），但仍需 hover 态反馈。
        self.assertFalse(button.hovered)
        button.enterEvent(None)
        self.assertTrue(button.hovered, "悬停必须置 hover 态")
        button.leaveEvent(None)
        self.assertFalse(button.hovered)

        button.mousePressEvent(
            QMouseEvent(QEvent.MouseButtonPress, QPoint(10, 10),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        )
        self.assertEqual(button._phase, "pressed", "按下须进入按压反馈段")
        QTest.qWait(200)
        self.assertFalse(window.isVisible(), "两段反馈播完后窗口应关闭")

    def test_close_button_sits_below_base_ui_knob(self):
        from petpet.ui.pet_profile import CLOSE_BUTTON_AT

        # 用户定稿：按键往下移动一点（原 y=16）。
        self.assertGreater(CLOSE_BUTTON_AT[1], 20)

    # ---- 第三轮：内容区 ----

    def test_switch_cards_in_left_panel_switch_pet(self):
        state = _fresh_state()
        state["owned_pet_ids"] = ["lunch_meat", "ice_cream"]
        window, pet = self._window(state)
        self.assertEqual(len(window._pet_cards), 2)
        # 名字与「使用中」pill 已按用户指示删除，卡片只保留头像按钮。
        for card in window._pet_cards.values():
            self.assertEqual(set(card.keys()), {"button"})
        window._select_pet("ice_cream")
        pet.set_active_pet.assert_called_once_with("ice_cream")

    def test_pet_card_icons_enlarged_and_closer(self):
        from petpet.ui.pet_profile import PET_CARD_SIZE, PET_CARD_SLOTS

        self.assertGreaterEqual(PET_CARD_SIZE[0], 180, "头像须放大")
        gap = PET_CARD_SLOTS[1][1] - PET_CARD_SLOTS[0][1]
        self.assertLessEqual(gap, 310, "两卡须更靠近")

    def test_switch_to_unowned_pet_is_refused(self):
        window, pet = self._window()
        window._select_pet("ice_cream")
        pet.set_active_pet.assert_not_called()

    def test_idle_animation_frames_loaded_and_playing(self):
        from petpet.ui import pet_profile as module

        window, _ = self._window()
        self.assertTrue(window._idle_frames, "应加载桌面 idle 动画帧")
        self.assertGreaterEqual(len(window._idle_frames), 8)
        self.assertIsNotNone(window._idle_timer)
        index = window._idle_index
        window._advance_idle_frame()
        self.assertEqual(window._idle_index, (index + 1) % len(window._idle_frames))

    def test_intro_tab_shows_name_affection_attributes_personality(self):
        from petpet.ui.pet_profile import pet_profile_snapshot

        state = _fresh_state()
        state["pet_name"] = "烟花"
        window, _ = self._window(state)
        intro = window._intro_label
        html = intro.text()
        self.assertIn("烟花", html)
        self.assertIn("午餐肉", html, "初始名应写在括号里")
        self.assertIn("好感度", html)
        for word in ("饱腹", "心情", "精力"):
            self.assertIn(word, html, f"属性值应含 {word}")
        self.assertIn("陪伴小狗", html, "性格介绍应来自 registry description")

        # 未改名 → 直接显示初始名，不出现括号对。
        state2 = _fresh_state()
        state2["pet_name"] = "午餐肉"
        window2, _ = self._window(state2)
        html2 = window2._intro_label.text()
        self.assertIn("午餐肉", html2)
        self.assertNotIn("（午餐肉）", html2)

    def test_tabs_switch_between_intro_and_outfits(self):
        from PyQt5.QtTest import QTest

        window, _ = self._window()
        self.assertTrue(window._intro_page.isVisibleTo(window))
        QTest.mouseClick(window._tab_buttons["套装"], Qt.LeftButton)
        self.assertTrue(window._outfit_page.isVisibleTo(window))
        self.assertFalse(window._intro_page.isVisibleTo(window))
        QTest.mouseClick(window._tab_buttons["简介"], Qt.LeftButton)
        self.assertTrue(window._intro_page.isVisibleTo(window))

    def test_outfit_tab_shows_art_for_each_outfit(self):
        window, _ = self._window()
        window._show_tab("套装")
        self.assertEqual(len(window._outfit_widgets), 2)
        for widget in window._outfit_widgets:
            self.assertFalse(widget["pixmap"].pixmap().isNull(),
                             "套装应使用新素材图")

    def test_content_pages_live_in_scroll_areas(self):
        window, _ = self._window()
        from PyQt5.QtWidgets import QScrollArea

        for page in (window._intro_page, window._outfit_page):
            self.assertIsInstance(page, QScrollArea, "内容页须是滚动区")

    def test_close_button_uses_art_asset(self):
        from petpet.ui.pet_profile import CLOSE_BUTTON_AT

        window, _ = self._window()
        self.assertFalse(window._close_button._art.isNull(),
                         "关闭键应使用 close_button.png 素材")
        # 用户定稿（第八轮）：往下移动（原 y=23 → 现在 > 50）。
        self.assertGreater(CLOSE_BUTTON_AT[1], 50)

    def test_pet_card_icons_have_hover_and_press_feedback(self):
        window, _ = self._window()
        for card in window._pet_cards.values():
            qss = card["button"].styleSheet()
            self.assertIn(":hover", qss, "头像按钮必须有悬停态")
            self.assertIn(":pressed", qss, "头像按钮必须有按压态")

    def test_ice_cream_card_sits_higher_than_before(self):
        from petpet.ui.pet_profile import PET_CARD_SLOTS

        # 用户定稿：冰淇淋头型上移 → 卡位从 y=547 上移 ≥14px。
        self.assertLessEqual(PET_CARD_SLOTS[1][1], 533)

    def test_shell_renders_background(self):
        window, _ = self._window()
        window.show()
        self.app.processEvents()
        image = window.grab().toImage()
        from PyQt5.QtGui import QColor

        # 奶油底：页面中部应为暖色不透明。
        mid = QColor.fromRgba(image.pixel(window.width() // 2, 200))
        self.assertGreater(mid.alpha(), 240)
        self.assertGreater(mid.red(), 230)

    def test_base_ui_layer_removed(self):
        """base_UI 已撤：原横幅区（x390-1151 y30-120）应为纯奶油底。"""
        window, _ = self._window()
        window.show()
        self.app.processEvents()
        image = window.grab().toImage()
        from PyQt5.QtGui import QColor

        kx, ky = window.width() / 1201, window.height() / 1304
        colored = 0
        for x in range(round(500 * kx), round(900 * kx), 6):
            for y in range(round(40 * ky), round(110 * ky), 6):
                c = QColor.fromRgba(image.pixel(x, y))
                if c.alpha() > 100 and (
                    c.red() - c.blue() > 45 or c.green() - c.blue() > 40
                ):
                    colored += 1
        self.assertLess(colored, 6, "原 base_UI 横幅区不应残留橙色元素")

    def test_page_corners_are_rounded_transparent(self):
        window, _ = self._window()
        window.show()
        self.app.processEvents()
        image = window.grab().toImage()
        from PyQt5.QtGui import QColor

        w, h = window.width(), window.height()
        for cx, cy in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)):
            corner = QColor.fromRgba(image.pixel(cx, cy))
            self.assertLess(corner.alpha(), 30,
                            f"角 ({cx},{cy}) 应被圆角裁剪为透明")

    def test_shell_shows_centered_via_show_near_pet(self):
        window, _ = self._window()
        window.show_near_pet()
        self.assertTrue(window.isVisible())
        window.close()


class BubbleMenuEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_primary_page_has_pet_profile_action(self):
        from petpet.ui.desktop import BubbleMenu

        actions = [entry[2] for entry in BubbleMenu.PRIMARY_ACTIONS]
        self.assertIn("pet_profile", actions)
        self.assertLess(actions.index("pet_profile"), 3)
        self.assertEqual(BubbleMenu.PAGE_COLUMNS["primary"], 6)

    def test_dispatch_opens_pet_profile(self):
        import pet

        fake_pet = SimpleNamespace(open_pet_profile=Mock())
        fake_menu = SimpleNamespace(pet=fake_pet, _close=Mock())

        pet.BubbleMenu._run_action(fake_menu, "pet_profile")

        fake_pet.open_pet_profile.assert_called_once_with()
        fake_menu._close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

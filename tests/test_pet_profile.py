"""Pet profile panel: snapshot data and window behaviour."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QMouseEvent


def _mouse_press(x, y):
    return QMouseEvent(QEvent.MouseButtonPress, QPoint(x, y),
                       Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)


def _mouse_release(x, y):
    return QMouseEvent(QEvent.MouseButtonRelease, QPoint(x, y),
                       Qt.LeftButton, Qt.NoButton, Qt.NoModifier)

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

        # 用户定稿：与其他常驻面板统一 850x960（艺术稿 1085x1663 非等比铺满）。
        self.assertEqual((module.ART_W, module.ART_H), (1085, 1450))
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
        # 二十轮：卡下名字删去，卡片只剩头像按钮（tag 已停用为 None）。
        for card in window._pet_cards.values():
            self.assertNotIn("name", card)
            self.assertIsNone(card["tag"])
        window._select_pet("ice_cream")
        pet.set_active_pet.assert_called_once_with("ice_cream")

    def test_pet_card_icons_enlarged_and_closer(self):
        from petpet.ui.pet_profile import PET_CARD_SIZE, PET_CARD_SLOTS

        self.assertGreaterEqual(PET_CARD_SIZE[0], 130, "头像随 rail 缩小")
        gap = PET_CARD_SLOTS[1][1] - PET_CARD_SLOTS[0][1]
        self.assertLessEqual(gap, 360, "两卡间距符合参考图")

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

    def _intro_text(self, window):
        parts = []
        for key, value in window._intro_sections.items():
            head = window._intro_heads[key]
            parts.append(f"{head.text()} {value.text()}")
        return "\n".join(parts)

    def test_intro_tab_shows_name_affection_attributes_personality(self):
        state = _fresh_state()
        state["pet_name"] = "烟花"
        window, _ = self._window(state)
        html = self._intro_text(window)
        # 第十九轮：名字只显示在改名条牌上，简介内不再重复。
        self.assertEqual(window._name_label.text(), "烟花")
        self.assertNotIn("烟花", html)
        self.assertIn("好感度", html)
        for word in ("饱腹", "心情", "精力"):
            self.assertIn(word, html, f"属性值应含 {word}")
        self.assertIn("陪伴小狗", html, "性格介绍应来自 registry description")

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
        # 第十九轮：X 缩小（74x67）；第二十一轮：略微上移（y≈44）。
        self.assertLessEqual(CLOSE_BUTTON_AT[2], 80)
        self.assertLessEqual(CLOSE_BUTTON_AT[3], 72)
        self.assertAlmostEqual(CLOSE_BUTTON_AT[1], 44, delta=3)

    def test_pet_card_icons_have_hover_and_press_feedback(self):
        from petpet.ui.pet_profile import _AvatarButton

        window, _ = self._window()
        for card in window._pet_cards.values():
            button = card["button"]
            self.assertIsInstance(button, _AvatarButton,
                                  "头像按钮为自绘件（整幅绘制不裁切）")
            # 悬停态置位 → 描边绘制分支。
            button.enterEvent(None)
            self.assertTrue(button._hovered)
            button.leaveEvent(None)
            self.assertFalse(button._hovered)
            button.mousePressEvent(_mouse_press(5, 5))
            self.assertTrue(button._pressed, "按压态必须有反馈")
            button.mouseReleaseEvent(_mouse_release(5, 5))
            self.assertFalse(button._pressed)

    def test_tab_buttons_are_pill_shaped(self):
        from petpet.ui.pet_profile import TAB_SLOTS

        window, _ = self._window()
        for button in window._tab_buttons.values():
            qss = button.styleSheet()
            self.assertIn("border-radius", qss)
        # 胶囊半径 = 槽高一半。
        th = TAB_SLOTS["简介"][3]
        self.assertAlmostEqual(
            window._tab_buttons["简介"].height(), round(th * 960 / 1663), delta=3,
        )

    def test_intro_is_modular_sections(self):
        state = _fresh_state()
        state["pet_name"] = "烟花"
        window, _ = self._window(state)
        html = self._intro_text(window)
        # 模块化分节：等级 / 好感度 / 属性 / 性格 各节标签（第十九轮删名字标题）。
        self.assertNotIn("烟花", window._name_label.styleSheet())
        for key in ("level", "affection", "attrs", "personality"):
            self.assertIn(key, window._intro_sections)
        self.assertIn("经验", html, "介绍应更详细（含经验）")

    def test_outfit_page_has_no_text_labels(self):
        window, _ = self._window()
        window._show_tab("套装")
        for widget in window._outfit_widgets:
            self.assertNotIn("name", widget,
                             "套装卡不加文字标签（按钮素材自带『装备』字）")

    def test_affection_next_follows_level(self):
        """好感度上限必须随等级变化（曾因传字典被兜底成恒 30）。"""
        from petpet.ui.pet_profile import pet_profile_snapshot

        state = _fresh_state()
        profile = state.setdefault("pets", {}).setdefault("ice_cream", {})
        state["owned_pet_ids"] = ["lunch_meat", "ice_cream"]
        state["active_pet_id"] = "ice_cream"
        state["affection_level"] = 3
        state["affection_points"] = 12
        snap = pet_profile_snapshot(state, "ice_cream")
        self.assertEqual(snap["affection_next"], 50, "Lv.3 上限应为 20+3*10=50")

    def test_intro_name_removed_and_name_plate_filled(self):
        """第二十一轮：简介名字删去；名字以艺术字形式写在改名条上。"""
        from petpet.ui.pet_profile import _ArtTitle

        state = _fresh_state()
        state["pet_name"] = "烟花"
        window, _ = self._window(state)
        self.assertIsInstance(window._name_label, _ArtTitle)
        self.assertEqual(window._name_label.text(), "烟花")

    def test_rail_title_is_art_text(self):
        from petpet.ui.pet_profile import _ArtTitle

        window, _ = self._window()
        self.assertIsInstance(window._rail_title, _ArtTitle)
        self.assertEqual(window._rail_title._text, "我的伙伴")

    def test_card_positions_round_twenty(self):
        from petpet.ui.pet_profile import RAIL_TITLE_AT

        # 第二十六轮：标题左移 20 显示px（x24→-2）。
        self.assertAlmostEqual(RAIL_TITLE_AT[0], -2, delta=2)

    def test_card_positions_round_twenty_one(self):
        from petpet.ui.pet_profile import PET_CARD_SLOTS, RAIL_AT

        # 第二十一轮：右移还原并随 rail 左移 10 显示px（x76 保框内对齐）、
        # 午餐肉卡下移 10 显示px（y272）。
        self.assertEqual(PET_CARD_SLOTS[0][0], 76)
        self.assertAlmostEqual(PET_CARD_SLOTS[0][1], 272, delta=3)
        self.assertAlmostEqual(PET_CARD_SLOTS[1][1], 470, delta=3)
        self.assertEqual(RAIL_AT[0], 51)

    def test_outfit_cards_have_equip_buttons(self):
        window, _ = self._window()
        window._show_tab("套装")
        self.assertEqual(len(window._outfit_widgets), 2)
        # 恐龙=绿、草莓=橘：按钮素材映射正确。
        mapping = window._outfit_button_assets
        self.assertEqual(mapping.get("dinosaur_suit"), "equip_button_green.png")
        self.assertEqual(mapping.get("strawberry_suit"),
                         "equip_button_orange.png")
        for widget in window._outfit_widgets:
            self.assertIsNotNone(widget["button"], "每张套装卡须带装备按钮")
            self.assertFalse(widget["button"]._art.isNull())

    @staticmethod
    def _press(button):
        """触发 _ArtButton 回调（跳过 80ms 定时等待）。"""
        button._phase = "recover"
        button._advance_phase()

    def test_equip_button_equips_directly_not_shop(self):
        state = _fresh_state()
        state["owned_outfits"] = ["dinosaur_suit"]
        window, pet = self._window(state)
        window._show_tab("套装")
        widget = next(
            w for w in window._outfit_widgets
            if w["outfit_id"] == "dinosaur_suit"
        )
        self._press(widget["button"])
        self.assertEqual(state["equipped_outfit"], "dinosaur_suit",
                         "点击装备应直接换装")
        pet.open_shop.assert_not_called()
        # 已装备 → 再点卸下。
        window._show_tab("套装")
        widget = next(
            w for w in window._outfit_widgets
            if w["outfit_id"] == "dinosaur_suit"
        )
        self._press(widget["button"])
        self.assertIsNone(state["equipped_outfit"])

    def test_outfit_button_inside_card_bottom(self):
        """第二十七轮：商店同款横版卡，按钮在卡内右下（holder 对齐底部）。"""
        window, _ = self._window()
        window._show_tab("套装")
        window.show()
        self.app.processEvents()
        widget = window._outfit_widgets[0]
        button = widget["button"]
        holder = button.parentWidget()
        card = holder.parentWidget()
        # holder 通过 stretch 把按钮压在卡底部：按钮在卡内高度 >40%。
        btn_y_in_card = holder.mapTo(card, button.rect().topLeft()).y()
        self.assertGreater(btn_y_in_card, card.height() * 0.4,
                           "按钮位于卡下半部")

    def test_outfit_page_scrolls_vertically_only(self):
        window, _ = self._window()
        window._show_tab("套装")
        window.show()
        self.app.processEvents()
        self.assertEqual(
            window._outfit_page.horizontalScrollBar().maximum(), 0,
            "套装页不得出现横向滚动",
        )
        from PyQt5.QtWidgets import QVBoxLayout

        self.assertIsInstance(window._outfit_host.layout(), QVBoxLayout,
                              "套装页为纵向卡列表（上下滚动）")

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

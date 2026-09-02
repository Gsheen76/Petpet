"""Pet profile panel: snapshot data and window behaviour."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QPixmap

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


class ProfileWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _window(self, state=None):
        from petpet.ui.pet_profile import PetProfileWindow

        pet = SimpleNamespace(
            state=state or _fresh_state(),
            set_active_pet=Mock(return_value={"ok": True}),
            update=Mock(),
            say=Mock(),
            home_scene_window=None,
            open_shop=Mock(),
        )
        window = PetProfileWindow(pet, save_state=Mock())
        self.addCleanup(window.close)
        return window, pet

    def test_shows_active_pet_details(self):
        state = _fresh_state()
        state["pet_name"] = "烟花"
        window, _ = self._window(state)
        self.assertIn("烟花", window._name_label.text())
        self.assertEqual(len(window._outfit_cards), 2)

    def test_paints_warm_cream_background(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QColor

        window, _ = self._window()
        window.show()
        self.app.processEvents()
        image = window.grab().toImage()
        base = QColor.fromRgba(image.pixel(10, window.height() // 2))
        self.assertGreater(base.alpha(), 240)
        self.assertGreater(base.red(), 240)
        self.assertGreater(base.green(), 220)

    def test_switch_to_unowned_pet_is_refused(self):
        window, pet = self._window()
        window._switch_pet("ice_cream")
        pet.set_active_pet.assert_not_called()
        self.assertIn("商店", window.status_label.text())

    def test_switch_to_owned_pet_calls_setter_then_refreshes(self):
        state = _fresh_state()
        state["owned_pet_ids"] = ["lunch_meat", "ice_cream"]
        window, pet = self._window(state)
        window._switch_pet("ice_cream")
        pet.set_active_pet.assert_called_once_with("ice_cream")
        self.assertIn("冰淇淋", window._name_label.text())
        # 冰淇凌已拥有但暂无套装 → 显示准备中占位。
        self.assertEqual(len(window._outfit_cards), 1)
        self.assertIn("准备中", window._outfit_cards[0].text())

    def test_equip_owned_outfit_updates_state_and_saves(self):
        state = _fresh_state()
        state["owned_outfits"] = ["dinosaur_suit"]
        window, pet = self._window(state)
        window._apply_outfit("dinosaur_suit", equip=True)
        self.assertEqual(state["equipped_outfit"], "dinosaur_suit")
        pet.update.assert_called()

    def test_unowned_pet_detail_shops_not_outfits(self):
        window, pet = self._window()
        window._select_pet("ice_cream")
        pet.set_active_pet.assert_not_called()
        self.assertEqual(window._outfit_cards, [])
        self.assertTrue(window._locked_page.isVisibleTo(window)
                        or window._locked_page.isVisible())


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


class ReviewFixRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _window(self, state=None):
        from petpet.ui.pet_profile import PetProfileWindow

        pet = SimpleNamespace(
            state=state or _fresh_state(),
            set_active_pet=Mock(return_value={"ok": True}),
            update=Mock(),
            say=Mock(),
            home_scene_window=None,
            open_shop=Mock(),
        )
        window = PetProfileWindow(pet, save_state=Mock())
        self.addCleanup(window.close)
        return window, pet

    def test_unowned_pet_avatar_shows_lock_badge(self):
        window, _ = self._window()
        _, lunch_badge, lunch_lock = window._avatar_buttons["lunch_meat"]
        _, ice_badge, ice_lock = window._avatar_buttons["ice_cream"]
        self.assertTrue(lunch_badge.isVisibleTo(window))
        self.assertFalse(lunch_lock.isVisibleTo(window))
        self.assertFalse(ice_badge.isVisibleTo(window))
        self.assertTrue(ice_lock.isVisibleTo(window))

    def test_failed_switch_rolls_back_selection(self):
        state = _fresh_state()
        state["owned_pet_ids"] = ["lunch_meat", "ice_cream"]
        window, pet = self._window(state)
        pet.set_active_pet.return_value = {
            "ok": False, "message": "聊天正在进行中，稍后再切换～",
        }
        window._switch_pet("ice_cream")
        self.assertEqual(window._selected_pet_id, "lunch_meat")
        self.assertIn("聊天", window.status_label.text())

    def test_missing_preview_art_clears_stale_pixmap(self):
        from petpet.ui import pet_profile as module

        window, _ = self._window()
        window._preview_label.setPixmap(QPixmap(10, 10))
        with patch.object(module.pet_registry, "pet_asset_path",
                          return_value=None), \
             patch.object(module.pet_registry, "pet_avatar_path",
                          return_value=None):
            window.refresh()
        self.assertTrue(window._preview_label.pixmap().isNull())


class ArtNativeLayoutTests(unittest.TestCase):
    """重设计布局：艺术稿原生 1201x1309 基准 + 未用素材接入。"""

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _window(self, state=None):
        from petpet.ui.pet_profile import PetProfileWindow

        pet = SimpleNamespace(
            state=state or _fresh_state(),
            set_active_pet=Mock(return_value={"ok": True}),
            update=Mock(),
            say=Mock(),
            home_scene_window=None,
            open_shop=Mock(),
        )
        window = PetProfileWindow(pet, save_state=Mock())
        self.addCleanup(window.close)
        return window, pet

    def test_window_base_matches_art_at_80_percent(self):
        from petpet.ui import pet_profile as module

        # 用户定稿：整体显示为艺术稿的 80%（1201x1309 → 961x1047）。
        self.assertEqual((module.BASE_W, module.BASE_H), (961, 1047))
        self.assertEqual(module.DISPLAY_SCALE, 0.8)

    def test_resolve_scale_caps_at_display_scale_and_fits_small_screens(self):
        from PyQt5.QtCore import QRect

        from petpet.ui.pet_profile import _resolve_scale

        # 大屏不超过 80% 显示比例。
        self.assertLessEqual(_resolve_scale(QRect(0, 0, 2560, 1400)), 0.8)
        # 无屏幕信息时回退显示比例。
        self.assertEqual(_resolve_scale(None), 0.8)
        # 1707x960 的屏上按高度收缩到放得下，且不高于下限。
        s = _resolve_scale(QRect(0, 0, 1707, 960))
        self.assertLessEqual(round(1309 * s), 960)
        self.assertGreaterEqual(s, 0.55)

    def test_key_widgets_stay_inside_window(self):
        window, _ = self._window()
        for widget in (
            window._preview_label, window._name_label,
            window._xp_bar, window._aff_bar, window._desc_label,
        ):
            self.assertTrue(window.rect().contains(widget.geometry()))

    def test_pet_switch_cards_carry_badge_and_lock(self):
        window, _ = self._window()
        self.assertEqual(len(window._avatar_buttons), 2)
        _, lunch_badge, lunch_lock = window._avatar_buttons["lunch_meat"]
        _, ice_badge, ice_lock = window._avatar_buttons["ice_cream"]
        self.assertTrue(lunch_badge.isVisibleTo(window))
        self.assertFalse(lunch_lock.isVisibleTo(window))
        self.assertFalse(ice_badge.isVisibleTo(window))
        self.assertTrue(ice_lock.isVisibleTo(window))

    def test_use_button_equips_selected_and_blocks_when_active(self):
        state = _fresh_state()
        window, pet = self._window(state)
        self.assertFalse(window._use_button.isEnabled())

        state["owned_pet_ids"] = ["lunch_meat", "ice_cream"]
        window._select_pet("ice_cream")
        self.assertTrue(window._use_button.isEnabled())
        window._use_button.click()
        pet.set_active_pet.assert_called_once_with("ice_cream")
        # 模拟真实 set_active_pet 落盘后的状态，再确认按钮回到禁用。
        state["active_pet_id"] = "ice_cream"
        window.refresh()
        self.assertFalse(window._use_button.isEnabled())

    def test_outfit_area_renders_art_panel_and_buttons(self):
        state = _fresh_state()
        state["owned_outfits"] = ["dinosaur_suit"]
        window, _ = self._window(state)
        self.assertFalse(window._outfit_panel_label.pixmap().isNull())
        # 已拥有未装备的套装卡 → 装备按钮带素材图标。
        card = next(
            card for card in window._outfit_cards
            if hasattr(card, "_action_button")
        )
        button = getattr(card, "_action_button", None)
        self.assertIsNotNone(button)
        self.assertFalse(button.icon().isNull())

    def test_info_rows_use_art_labels(self):
        from petpet.ui import pet_profile as module

        window, _ = self._window()
        for asset in ("level_text.png", "exp_text.png", "affection_text.png"):
            label = window._art_labels[asset]
            self.assertFalse(label.pixmap().isNull(),
                             f"{asset} 应作为信息行标签显示")


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


if __name__ == "__main__":
    unittest.main()

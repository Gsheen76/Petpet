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

    def test_window_size_is_background_at_70_percent(self):
        from petpet.ui import pet_profile as module

        # 用户定稿：整体显示为 background 的 70%（1201x1304 → 841x913）。
        self.assertEqual((module.ART_W, module.ART_H), (1201, 1304))
        self.assertEqual(module.DISPLAY_SCALE, 0.7)
        self.assertGreater(module.CORNER_RADIUS, 50, "圆角须比上一轮 50 更大")
        window, _ = self._window()
        self.assertEqual((window.width(), window.height()), (841, 913))

    def test_resolve_scale_caps_at_display_scale_and_fits_small_screens(self):
        from PyQt5.QtCore import QRect

        from petpet.ui.pet_profile import _resolve_scale

        self.assertLessEqual(_resolve_scale(QRect(0, 0, 2560, 1440)), 0.7)
        self.assertEqual(_resolve_scale(None), 0.7)
        s = _resolve_scale(QRect(0, 0, 1280, 860))
        self.assertLessEqual(round(1304 * s), 860)
        self.assertGreaterEqual(s, 0.55)

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
        window._select_pet("ice_cream")
        pet.set_active_pet.assert_called_once_with("ice_cream")
        # Mock 不落盘：模拟真实 set_active_pet 后的状态再刷新验证。
        state["active_pet_id"] = "ice_cream"
        window.refresh()
        self.assertTrue(window._pet_cards["ice_cream"]["tag"].isVisibleTo(window))
        self.assertFalse(window._pet_cards["lunch_meat"]["tag"].isVisibleTo(window))

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

    def test_name_plate_shows_name_and_rename_button(self):
        from petpet.ui import pet_profile as module

        calls = []

        def factory(current, on_commit, parent):
            calls.append(current)
            return SimpleNamespace(exec_=Mock(
                side_effect=lambda: on_commit("烟花")
            ))

        module.configure_name_dialog_factory(factory)
        self.addCleanup(module.configure_name_dialog_factory, None)
        state = _fresh_state()
        window, pet = self._window(state)
        self.assertTrue(window._name_label.text())
        window._rename_button.click()
        self.assertEqual(len(calls), 1)
        pet.set_pet_name.assert_called_once_with("烟花")
        # Mock 不落盘：模拟真实 set_pet_name 后的状态再刷新验证。
        state["pet_name"] = "烟花"
        window.refresh()
        self.assertIn("烟花", window._name_label.text())

    def test_level_and_affection_rows_show_values(self):
        window, _ = self._window()
        self.assertIn("Lv.", window._level_label.text())
        self.assertIn("好感度", window._affection_label.text())

    def test_shell_renders_background_and_base_ui(self):
        window, _ = self._window()
        window.show()
        self.app.processEvents()
        image = window.grab().toImage()
        from PyQt5.QtGui import QColor

        # 奶油底：页面中部应为暖色不透明。
        mid = QColor.fromRgba(image.pixel(window.width() // 2, 200))
        self.assertGreater(mid.alpha(), 240)
        self.assertGreater(mid.red(), 230)
        # base_UI 右上圆钮区（艺术稿 x1080-1150, y32-100）应有非奶油内容；
        # 采样坐标按实际缩放换算。
        kx = window.width() / 1201
        ky = window.height() / 1304
        content = 0
        for x in range(round(1080 * kx), round(1150 * kx), 4):
            for y in range(round(32 * ky), round(100 * ky), 4):
                c = QColor.fromRgba(image.pixel(x, y))
                if c.alpha() > 100 and (
                    abs(c.red() - mid.red()) > 18
                    or abs(c.green() - mid.green()) > 18
                    or abs(c.blue() - mid.blue()) > 18
                ):
                    content += 1
        self.assertGreater(content, 5, "base_UI 内容应可见于右上区域")

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

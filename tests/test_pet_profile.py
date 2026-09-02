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
        self.assertGreater(module.CORNER_RADIUS, 30, "圆角须比首版的 30 更大")
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

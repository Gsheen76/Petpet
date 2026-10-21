"""宠物风格切换:面板画风节与套装经典限定标注测试(2026-10-21 风格切换轮)。"""

import unittest
from unittest.mock import Mock

try:
    from PyQt5.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

from petpet.app import state as app_state
from petpet.progression import core as progression
from petpet.ui.pet_profile import PetProfileWindow, pet_profile_snapshot


def _fresh_state():
    state = app_state.ensure_state_schema({}, "Sheen", str)
    progression.ensure_progression(state)
    return state


def _pet_shell(state):
    from types import SimpleNamespace

    return SimpleNamespace(
        state=state,
        set_active_pet=Mock(return_value={"ok": True}),
        set_pet_style=Mock(return_value={"ok": True}),
        set_pet_name=Mock(),
        update=Mock(),
        say=Mock(),
        home_scene_window=None,
        open_shop=Mock(),
    )


@unittest.skipIf(QApplication is None, "PyQt5 不可用")
class StyleSectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, state=None):
        pet = _pet_shell(state or _fresh_state())
        window = PetProfileWindow(pet, save_state=Mock())
        self.addCleanup(window.close)
        return window, pet

    def test_snapshot_carries_style_fields(self):
        snapshot = pet_profile_snapshot(_fresh_state(), "lunch_meat")
        self.assertEqual(snapshot["available_styles"], ["classic", "new"])
        self.assertEqual(snapshot["style"], "classic")
        self.assertIn("avatar_classic", snapshot["avatar_path"])

    def test_dual_style_pet_shows_both_chips(self):
        window, _ = self._window()
        self.assertEqual(sorted(window._style_chips), ["classic", "new"])
        self.assertTrue(window._style_chips["classic"].isChecked())
        self.assertFalse(window._style_chips["new"].isChecked())

    def test_single_style_pet_hides_section(self):
        window, _ = self._window()
        window._viewing_pet_id = "marshmallow"
        window.refresh()
        self.assertFalse(
            window._style_section_row.isVisibleTo(window))

    def test_choose_style_calls_transaction(self):
        window, pet = self._window()
        window._style_chips["new"].click()
        pet.set_pet_style.assert_called_once_with("lunch_meat", "new")

    def test_failed_transaction_keeps_current_chips(self):
        window, pet = self._window()
        pet.set_pet_style = Mock(return_value={"ok": False, "message": "x"})
        window._style_chips["new"].click()
        self.assertTrue(window._style_chips["classic"].isChecked())
        self.assertFalse(window._style_chips["new"].isChecked())

    def test_outfit_page_marks_classic_only_in_new_style(self):
        from PyQt5.QtWidgets import QLabel

        state = _fresh_state()
        state["pets"]["lunch_meat"]["style"] = "new"
        window, _ = self._window(state)
        window.refresh()
        texts = [label.text() for label in window._outfit_host.findChildren(QLabel)]
        self.assertIn("经典限定", texts)

        state["pets"]["lunch_meat"]["style"] = "classic"
        window.refresh()
        # deleteLater 旧卡须显式派发 DeferredDelete 再断言(既有坑位)
        from PyQt5.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        texts = [label.text() for label in window._outfit_host.findChildren(QLabel)]
        self.assertNotIn("经典限定", texts)


if __name__ == "__main__":
    unittest.main()

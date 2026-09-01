"""Pet profile panel: snapshot data and window behaviour."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
        self.assertEqual(window._outfit_cards, [])

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


if __name__ == "__main__":
    unittest.main()

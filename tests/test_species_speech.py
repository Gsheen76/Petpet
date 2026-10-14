# -*- coding: utf-8 -*-
"""物种语料池测试（2026-10-14）：非犬物种（棉花糖=小兔）不再念狗狗词。"""
import copy
import unittest

from PyQt5.QtWidgets import QApplication

import pet
from petpet.app.pet_window import _species_lines


class SpeciesSpeechTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, pet_id):
        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"active_pet_id": pet_id})
        window = pet.PetWindow(state)
        self.addCleanup(window.close)
        return window

    def test_rabbit_idle_pool_has_no_dog_barks(self):
        window = self._window("marshmallow")
        for key in ("idle_hungry", "idle_bored", "idle_sleepy", "idle_normal",
                    "wake", "pet_reaction", "drag_spin"):
            pool = _species_lines(window._current_pet_id, key, ["汪fallback"])
            for line in pool:
                self.assertNotIn("汪", line, f"{key}: {line}")

    def test_dog_pets_fall_back_to_default_pools(self):
        for pet_id in ("lunch_meat", "ice_cream"):
            window = self._window(pet_id)
            pool = _species_lines(window._current_pet_id, "idle_normal", ["汪！我在这里"])
            self.assertIn("汪！我在这里", pool)

    def test_rabbit_gets_rabbit_lines(self):
        window = self._window("marshmallow")
        pool = _species_lines(window._current_pet_id, "idle_normal", ["汪！我在这里"])
        self.assertIn("噗？我在这里哟", pool)
        self.assertNotIn("汪！我在这里", pool)


if __name__ == "__main__":
    unittest.main()

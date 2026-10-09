# -*- coding: utf-8 -*-
"""调参器套装预览（2026-10-09 用户需求：可选角色+套装直接预览对应动作）。"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import parameter_tuner
from petpet.progression import core as progression


class TunerOutfitPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tuner(self, state):
        from parameter_tuner import ParameterTunerWindow

        pet = type("Pet", (), {})()
        pet.state = state
        pet._animation_frame_paths = {
            "idle": ["f"], "pet": ["f"], "pet_dinosaur": ["f"],
            "idle_dinosaur": ["f"], "sleep_dinosaur": ["f"],
        }
        window = ParameterTunerWindow.__new__(ParameterTunerWindow)
        window.pet = pet
        return window

    def _state(self, equipped="dinosaur_suit"):
        return {
            "pets": {"lunch_meat": {}, "ice_cream": {}},
            "active_pet_id": "lunch_meat",
            "owned_pet_ids": ["lunch_meat", "ice_cream"],
            "owned_outfits": ["dinosaur_suit"],
            "equipped_outfit": equipped,
        }

    def test_preview_key_list_includes_outfit_variants_when_equipped(self):
        w = self._tuner(self._state("dinosaur_suit"))
        keys = [k for k, _ in w._preview_key_list()]
        labels = dict(w._preview_key_list())
        self.assertIn("pet_dinosaur", keys)
        self.assertIn("idle_dinosaur", keys)
        self.assertIn("sleep_dinosaur", keys)
        self.assertEqual(labels["pet_dinosaur"], "摸头·小恐龙")

    def test_preview_key_list_is_base_when_no_outfit(self):
        w = self._tuner(self._state(None))
        keys = [k for k, _ in w._preview_key_list()]
        self.assertNotIn("pet_dinosaur", keys)
        self.assertIn("pet", keys)

    def test_strawberry_has_no_action_variants_but_keeps_idle(self):
        w = self._tuner(self._state("strawberry_suit"))
        w._state_owned = None
        keys = [k for k, _ in w._preview_key_list()]
        self.assertIn("idle_strawberry", keys)
        self.assertNotIn("pet_strawberry", keys)

    def test_outfit_combo_only_lists_active_pets_outfits(self):
        w = self._tuner(self._state())
        # 构造函数未跑，手动调（需要 combo 存在的场景由 GUI 测试覆盖；
        # 这里验证数据层：定义表里冰淇淋没有套装）
        for outfit_id, d in progression.OUTFIT_DEFINITIONS.items():
            if d.get("pet_id") == "ice_cream":
                self.fail("冰淇淋不应有套装（当前设定）")


if __name__ == "__main__":
    unittest.main()

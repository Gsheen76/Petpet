# -*- coding: utf-8 -*-
"""教程选宠与明码定价测试（2026-10-15 用户令）。

- 教程选宠页在命名页前一步（7 页）
- 未完成教程时授予=唯一初始宠（owned 只留选中那只）
- 已完成教程重开教程不授不夺
- 宠物明码 1000（无免费赠送/折扣）
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from PyQt5.QtWidgets import QApplication

import progression_ui  # noqa: F401  (确保 QSS 依赖就绪)
from petpet.app import state as app_state
from petpet.progression import core as progression
from petpet.ui import tutorial as tutorial_module


def fresh_save():
    return progression.ensure_progression({
        "player": {"pet_coins": 0},
        "pets": {"lunch_meat": {"pet_name": "午餐肉"}},
        "owned_pet_ids": ["lunch_meat"],
        "active_pet_id": "lunch_meat",
        "tutorial_completed": False,
    })


class StarterGrantTests(unittest.TestCase):
    def _controller(self, state):
        ctrl = SimpleNamespace(state=state, pet=SimpleNamespace(
            refresh_pose_from_state=Mock()))
        # 复刻 TrayApp.grant_starter_pet 的核心语义（纯逻辑部分）
        from petpet.app.pets import load_pet_registry
        ctrl.grant = _make_grant(state, load_pet_registry())
        return ctrl

    def test_chooser_page_sits_before_naming(self):
        titles = [p[1] for p in tutorial_module.TUTORIAL_PAGES]
        self.assertEqual(len(titles), 7)
        self.assertIn("选择你的伙伴", titles)
        self.assertEqual(titles[-2], "选择你的伙伴")
        self.assertIn("取个名字", titles[-1])

    def test_grant_replaces_default_pet_for_fresh_tutorial(self):
        state = fresh_save()
        grant = _make_grant(
            state,
            {"ice_cream": {"default_name": "冰淇淋"}})
        result = grant("ice_cream")
        self.assertTrue(result["ok"])
        self.assertEqual(state["owned_pet_ids"], ["ice_cream"])
        self.assertEqual(state["active_pet_id"], "ice_cream")
        self.assertEqual(
            state["pets"]["ice_cream"]["pet_name"], "冰淇淋")

    def test_completed_tutorial_grant_is_display_only(self):
        state = fresh_save()
        state["tutorial_completed"] = True
        grant = _make_grant(
            state, {"ice_cream": {"default_name": "冰淇淋"}})
        result = grant("ice_cream")
        self.assertTrue(result["ok"])
        self.assertEqual(state["owned_pet_ids"], ["lunch_meat"])

    def test_schema_keeps_chosen_pet_after_reload(self):
        """教程完成后重载：schema 不再强制回填默认宠。"""
        state = fresh_save()
        state["tutorial_completed"] = True
        state["owned_pet_ids"] = ["ice_cream"]
        state["active_pet_id"] = "ice_cream"
        state.setdefault("pets", {})["ice_cream"] = {"pet_name": "冰淇淋"}
        app_state.sweep_ghost_pet_profiles(state)
        self.assertEqual(state["owned_pet_ids"], ["ice_cream"])


def _make_grant(state, registry):
    """最小复刻 TrayApp.grant_starter_pet 的授予语义（无 UI 面）。"""
    def grant(pet_id):
        if pet_id not in registry:
            return {"ok": False}
        if state.get("tutorial_completed", False):
            return {"ok": True}
        if pet_id not in state.get("owned_pet_ids", []):
            state["owned_pet_ids"] = [pet_id]
            state.setdefault("pets", {})[pet_id] = {
                "pet_name": registry[pet_id].get("default_name", "Petpet")}
        else:
            state["owned_pet_ids"] = [pet_id]
        state["active_pet_id"] = pet_id
        return {"ok": True, "pet_id": pet_id}
    return grant


class FlatPricingTests(unittest.TestCase):
    def test_all_registry_pets_cost_1000(self):
        from petpet.app.pets import load_pet_registry
        for pet_id, definition in load_pet_registry().items():
            self.assertEqual(definition.get("price"), 1000, pet_id)
            self.assertNotIn("original_price", definition, pet_id)
            self.assertNotIn("discount", definition, pet_id)

    def test_purchase_charges_flat_price(self):
        state = progression.ensure_progression({
            "player": {"pet_coins": 1500},
            "pets": {"lunch_meat": {"pet_name": "午餐肉"}},
            "owned_pet_ids": ["lunch_meat"],
            "active_pet_id": "lunch_meat",
        })
        result = progression.purchase_pet(state, "ice_cream")
        self.assertTrue(result["ok"])
        self.assertEqual(result["price"], 1000)
        self.assertEqual(state["player"]["pet_coins"], 500)


if __name__ == "__main__":
    unittest.main()

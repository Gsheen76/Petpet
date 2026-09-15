"""家园家具扩充（2026-09-10）：灯/书架/圆桌/玩具篮四件新家具。

定义进 HOME_DECORATION_DEFINITIONS、素材路径进 HOME_FURNITURE_PATHS、
类目进装修面板筛选；正式素材由用户 AI 生成后经
tools/split_furniture_sheet.py 拆分同名替换（当前为程序占位稿）。
"""

import os
import unittest
from types import SimpleNamespace

import progression
from petpet.home import rendering


class NewFurnitureTests(unittest.TestCase):
    IDS = ("home_lamp", "home_bookshelf", "home_round_table",
           "home_toy_basket")

    def test_definitions_and_assets_exist(self):
        for item_id in self.IDS:
            definition = progression.HOME_DECORATION_DEFINITIONS[item_id]
            self.assertTrue(definition["name"])
            self.assertGreater(definition["price"], 0)
            path = rendering.HOME_FURNITURE_PATHS[item_id]
            self.assertTrue(
                os.path.isfile(path), f"{item_id} 素材缺失: {path}",
            )
            from PIL import Image

            size = definition["size"]
            with Image.open(path) as im:
                # 素材画布与定义尺寸一致（渲染/缩放以此为准）。
                self.assertEqual(im.size, tuple(size), item_id)

    def test_categories_cover_new_items(self):
        for item_id in self.IDS:
            self.assertIn(
                item_id, rendering.HOME_DECORATION_CATEGORY_BY_ID,
            )
        labels = dict(rendering.HOME_DECORATION_CATEGORIES)
        for category in rendering.HOME_DECORATION_CATEGORY_BY_ID.values():
            self.assertIn(category, labels)

    def test_purchase_flow_for_new_items(self):
        state = {
            "born": 0.0, "level": 1, "xp": 0,
            "hunger": 80, "mood": 70, "energy": 90,
        }
        state = progression.ensure_progression(state)
        state["pet_coins"] = 9999
        result = progression.purchase_home_decoration(state, "home_lamp")
        self.assertTrue(result["ok"])
        self.assertIn("home_lamp", state["owned_home_decorations"])
        # 位置持久化走默认位。
        self.assertEqual(
            state["home_decoration_positions"]["home_lamp"],
            progression.HOME_DECORATION_DEFINITIONS["home_lamp"][
                "default_position"],
        )


class CozyBatch2FurnitureTests(unittest.TestCase):
    """家具第二批（2026-09-12）：挂钟/猫爬架/软垫小床/摇椅。"""

    IDS = ("home_wall_clock", "home_cat_tree", "home_pet_bed",
           "home_rocking_chair")

    def test_definitions_and_assets_exist(self):
        for item_id in self.IDS:
            definition = progression.HOME_DECORATION_DEFINITIONS[item_id]
            self.assertTrue(definition["name"])
            self.assertGreater(definition["price"], 0)
            path = rendering.HOME_FURNITURE_PATHS[item_id]
            self.assertTrue(
                os.path.isfile(path), f"{item_id} 素材缺失: {path}",
            )
            from PIL import Image

            size = definition["size"]
            with Image.open(path) as im:
                self.assertEqual(im.size, tuple(size), item_id)

    def test_categories_cover_new_items(self):
        expected = {
            "home_wall_clock": "decor",
            "home_cat_tree": "toy",
            "home_pet_bed": "furniture",
            "home_rocking_chair": "furniture",
        }
        for item_id, category in expected.items():
            self.assertEqual(
                rendering.HOME_DECORATION_CATEGORY_BY_ID.get(item_id),
                category,
            )

    def test_purchase_flow_for_new_items(self):
        state = {
            "born": 0.0, "level": 1, "xp": 0,
            "hunger": 80, "mood": 70, "energy": 90,
        }
        state = progression.ensure_progression(state)
        state["pet_coins"] = 9999
        result = progression.purchase_home_decoration(
            state, "home_pet_bed")
        self.assertTrue(result["ok"])
        self.assertIn("home_pet_bed", state["owned_home_decorations"])
        self.assertEqual(
            state["home_decoration_positions"]["home_pet_bed"],
            progression.HOME_DECORATION_DEFINITIONS["home_pet_bed"][
                "default_position"],
        )

    def test_wall_clock_paints_behind_floor_furniture(self):
        # 挂钟与挂画/状态卡同层（深度键 0）：永远垫在地面家具后面。
        from petpet.home.window import HomeSceneWindow

        self.assertEqual(
            HomeSceneWindow._furniture_depth_key(
                SimpleNamespace(
                    selection_bounds=lambda _id: SimpleNamespace(
                        bottom=lambda: 9999),
                ),
                "home_wall_clock",
            ),
            (0, 0.0),
        )


class PurchaseStoredByDefaultTests(unittest.TestCase):
    """购买家具默认收纳（2026-09-12 用户指示）。

    买完不再自动出现在场景里，先进收纳；默认位仍记录，
    从装修面板「放置」时直接落到默认位。
    """

    def test_purchase_stores_decoration_by_default(self):
        state = {
            "born": 0.0, "level": 1, "xp": 0,
            "hunger": 80, "mood": 70, "energy": 90,
        }
        state = progression.ensure_progression(state)
        state["pet_coins"] = 9999
        result = progression.purchase_home_decoration(
            state, "home_rocking_chair")
        self.assertTrue(result["ok"])
        self.assertIn(
            "home_rocking_chair", state["owned_home_decorations"])
        self.assertIn(
            "home_rocking_chair", state["home_stored_decorations"],
            "新购家具应默认进收纳，不自动摆进场景",
        )
        # 默认位仍记录：从收纳放置时直接落到默认位。
        self.assertEqual(
            state["home_decoration_positions"]["home_rocking_chair"],
            progression.HOME_DECORATION_DEFINITIONS["home_rocking_chair"][
                "default_position"],
        )

    def test_place_after_purchase_clears_stored(self):
        state = progression.ensure_progression({
            "born": 0.0, "level": 1, "xp": 0,
            "hunger": 80, "mood": 70, "energy": 90,
            "pet_coins": 9999,
        })
        progression.purchase_home_decoration(state, "home_pet_bed")
        self.assertTrue(progression.place_home_decoration(state, "home_pet_bed"))
        self.assertNotIn(
            "home_pet_bed", state["home_stored_decorations"])

"""家园家具扩充（2026-09-10）：灯/书架/圆桌/玩具篮四件新家具。

定义进 HOME_DECORATION_DEFINITIONS、素材路径进 HOME_FURNITURE_PATHS、
类目进装修面板筛选；正式素材由用户 AI 生成后经
tools/split_furniture_sheet.py 拆分同名替换（当前为程序占位稿）。
"""

import os
import unittest

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

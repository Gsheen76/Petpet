import unittest


class HomeGeometryBoundaryTests(unittest.TestCase):
    def test_root_scene_system_reexports_package_geometry(self):
        import scene_system
        from petpet.home import geometry

        self.assertIs(scene_system.home_decoration_bounds, geometry.home_decoration_bounds)
        self.assertEqual(scene_system.HOME_VIEWPORT_SIZE, geometry.HOME_VIEWPORT_SIZE)


if __name__ == "__main__":
    unittest.main()


class FurnitureClampDefinitionSyncTests(unittest.TestCase):
    """家具 clamp 尺寸必须取定义目录（单一事实源，2026-09-18）。

    手抄表停更过 8 件新家具：缺项回退 (0,0) → max_x=1800，家具可被
    整体拖出全景、场景内无法再点选。
    """

    def test_clamp_covers_every_catalog_item_with_definition_size(self):
        from petpet.home import geometry
        from petpet.progression import core as progression

        for item_id, definition in progression.HOME_DECORATION_DEFINITIONS.items():
            width, height = definition["size"]
            clamped = geometry.clamp_home_furniture_position(
                item_id, 10 ** 6, 10 ** 6
            )
            self.assertLessEqual(
                clamped["x"], geometry.HOME_WORLD_SIZE[0] - width,
                f"{item_id} 的 clamp 未使用定义尺寸",
            )
            self.assertLessEqual(
                clamped["y"], geometry.HOME_WORLD_SIZE[1] - height,
                f"{item_id} 的纵向 clamp 未使用定义尺寸",
            )

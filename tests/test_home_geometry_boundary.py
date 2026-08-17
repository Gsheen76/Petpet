import unittest


class HomeGeometryBoundaryTests(unittest.TestCase):
    def test_root_scene_system_reexports_package_geometry(self):
        import scene_system
        from petpet.home import geometry

        self.assertIs(scene_system.pan_viewport_x, geometry.pan_viewport_x)
        self.assertIs(scene_system.home_decoration_bounds, geometry.home_decoration_bounds)
        self.assertEqual(scene_system.HOME_VIEWPORT_SIZE, geometry.HOME_VIEWPORT_SIZE)


if __name__ == "__main__":
    unittest.main()

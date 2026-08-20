import unittest


class HomeRenderingBoundaryTests(unittest.TestCase):
    def test_home_scene_reexports_package_rendering(self):
        import home_scene
        from petpet.home import rendering

        self.assertIs(home_scene.render_home_status_card, rendering.render_home_status_card)
        self.assertIs(home_scene.home_pet_shadow_rect, rendering.home_pet_shadow_rect)
        self.assertIs(home_scene.HomePetWalkRenderSpec, rendering.HomePetWalkRenderSpec)


if __name__ == "__main__":
    unittest.main()

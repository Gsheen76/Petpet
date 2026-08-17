import unittest


class HomeWindowBoundaryTests(unittest.TestCase):
    def test_root_home_window_is_package_owned(self):
        import home_scene
        from petpet.home.window import HomeSceneWindow

        self.assertIs(home_scene.HomeSceneWindow, HomeSceneWindow)


if __name__ == "__main__":
    unittest.main()

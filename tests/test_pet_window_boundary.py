import unittest


class PetWindowBoundaryTests(unittest.TestCase):
    def test_root_pet_window_is_owned_by_app_package(self):
        import pet
        from petpet.app.pet_window import PetWindow

        self.assertIs(pet.PetWindow, PetWindow)

    def test_default_animation_name_uses_configured_pose_mapping(self):
        import pet
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window._animation_override = None
        window.state = {}
        window.dragging = False
        window.behavior = "idle"
        window.pose = pet.POSE["idle"]

        self.assertEqual(window._current_animation_name(), "idle")


if __name__ == "__main__":
    unittest.main()

import unittest


class DesktopSurfacesBoundaryTests(unittest.TestCase):
    def test_root_desktop_surfaces_are_owned_by_ui_package(self):
        import pet
        from petpet.ui import desktop

        for name in (
            "StatBubble",
            "BubbleMenu",
            "BonusBubble",
            "InteractiveBubble",
            "SpeechBubble",
        ):
            self.assertIs(getattr(pet, name), getattr(desktop, name))

    def test_anchor_helpers_are_package_owned(self):
        import pet
        from petpet.ui import desktop

        self.assertIs(pet._pet_interface_anchor_rect, desktop.pet_interface_anchor_rect)
        self.assertIs(pet._pet_interface_screen_rect, desktop.pet_interface_screen_rect)


if __name__ == "__main__":
    unittest.main()

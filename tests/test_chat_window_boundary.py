import unittest


class ChatWindowBoundaryTests(unittest.TestCase):
    def test_root_chat_window_is_thin_package_facade(self):
        import pet
        from petpet.ui.chat import ChatWindow as PackageChatWindow

        self.assertTrue(issubclass(pet.ChatWindow, PackageChatWindow))
        self.assertIsNot(pet.ChatWindow, PackageChatWindow)
        self.assertEqual(set(pet.ChatWindow.__dict__) - {"__module__", "__doc__"}, {"__init__"})


if __name__ == "__main__":
    unittest.main()

import unittest

from unittest.mock import patch


def test_chat_refresh_contract_is_available_for_active_pet_switch():
    from petpet.ui.chat import ChatWindow

    window = ChatWindow.__new__(ChatWindow)
    window.busy = False
    window._ui_built = False
    window.pet_id = "lunch_meat"
    window.memory_profile = "lunch_meat"
    window.mem = {"history": []}

    with patch.object(
        ChatWindow.set_pet_id.__globals__["ai"],
        "load_memory",
        return_value={"history": [], "pet_name": "冰淇淋"},
    ) as load_memory:
        assert window.set_pet_id("ice_cream") is True

    assert window.pet_id == "ice_cream"
    assert window.memory_profile == "ice_cream"
    load_memory.assert_called_once_with(pet_id="ice_cream")


class ChatWindowBoundaryTests(unittest.TestCase):
    def test_root_chat_window_is_thin_package_facade(self):
        import pet
        from petpet.ui.chat import ChatWindow as PackageChatWindow

        self.assertTrue(issubclass(pet.ChatWindow, PackageChatWindow))
        self.assertIsNot(pet.ChatWindow, PackageChatWindow)
        self.assertEqual(set(pet.ChatWindow.__dict__) - {"__module__", "__doc__"}, {"__init__"})


if __name__ == "__main__":
    unittest.main()

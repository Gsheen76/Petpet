import os
import time
import unittest
import uuid
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import pet


class SingleInstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_second_instance_notifies_primary_then_can_start_after_close(self):
        server_name = f"petpet-test-{uuid.uuid4().hex}"
        primary = pet.SingleInstanceServer(server_name)
        secondary = pet.SingleInstanceServer(server_name)
        restarted = pet.SingleInstanceServer(server_name)
        self.addCleanup(primary.close)
        self.addCleanup(secondary.close)
        self.addCleanup(restarted.close)
        activation = Mock()
        primary.activation_requested.connect(activation)

        self.assertTrue(primary.start())
        self.assertFalse(secondary.start())
        deadline = time.monotonic() + 1.0
        while activation.call_count == 0 and time.monotonic() < deadline:
            self.app.processEvents()
        activation.assert_called_once_with()

        primary.close()
        self.assertTrue(restarted.start())


if __name__ == "__main__":
    unittest.main()

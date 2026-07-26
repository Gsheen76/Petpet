import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import pet


class SpeechBubbleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_rapid_updates_keep_latest_complete_bubble(self):
        host = QWidget()
        host.setGeometry(300, 260, 190, 220)
        host.show()
        host.current_screen_rect = (
            lambda: self.app.primaryScreen().availableGeometry()
        )
        bubble = pet.SpeechBubble(host)
        self.addCleanup(bubble.close)
        self.addCleanup(host.close)

        messages = [
            "汪！",
            "主人今天也要开开心心的，我会一直陪着你～",
        ] * 20
        for message in messages:
            bubble.show_text(message, 1800)
        self.app.processEvents()

        screen = host.current_screen_rect()
        self.assertEqual(bubble.text, messages[-1])
        self.assertTrue(bubble.isVisible())
        self.assertTrue(bubble._hide_timer.isActive())
        self.assertGreaterEqual(bubble.geometry().left(), screen.left() + 4)
        self.assertLessEqual(bubble.geometry().right(), screen.right() - 4)

        image = bubble.grab().toImage()
        right_edge = image.pixelColor(
            max(0, image.width() - 4), image.height() // 2
        )
        self.assertGreater(right_edge.alpha(), 0)


if __name__ == "__main__":
    unittest.main()

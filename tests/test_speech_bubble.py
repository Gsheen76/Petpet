import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication, QWidget

import pet


class SpeechBubbleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_overlapping_messages_are_queued_without_cutting_off_current(self):
        host = QWidget()
        host.setGeometry(300, 260, 190, 220)
        host.show()
        host.current_screen_rect = (
            lambda: self.app.primaryScreen().availableGeometry()
        )
        bubble = pet.SpeechBubble(host)
        host._speech_bubble = bubble
        self.addCleanup(bubble.close)
        self.addCleanup(host.close)

        first = "肚子咕咕叫啦，主人看看我～"
        second = "嗷呜嗷呜！"
        bubble.show_text(first, 1800)
        bubble.show_text(second, 1800)
        self.app.processEvents()

        screen = host.current_screen_rect()
        self.assertEqual(bubble.text, first)
        self.assertEqual(bubble._pending_messages, [(second, 1800)])
        self.assertTrue(bubble.isVisible())
        self.assertTrue(bubble._hide_timer.isActive())
        self.assertGreaterEqual(bubble.geometry().left(), screen.left() + 4)
        self.assertLessEqual(bubble.geometry().right(), screen.right() - 4)

        bubble._show_next_or_hide()
        self.app.processEvents()
        replacement = host._speech_bubble
        self.addCleanup(replacement.close)

        self.assertIsNot(replacement, bubble)
        self.assertEqual(replacement.text, second)
        self.assertEqual(replacement._pending_messages, [])
        self.assertTrue(replacement.isVisible())

        image = replacement.grab().toImage()
        right_edge = image.pixelColor(
            max(0, image.width() - 4), image.height() // 2
        )
        self.assertGreater(right_edge.alpha(), 0)

    def test_long_message_wraps_without_ellipsis_and_stays_on_screen(self):
        host = QWidget()
        host.setGeometry(300, 260, 190, 220)
        host.show()
        host.current_screen_rect = (
            lambda: self.app.primaryScreen().availableGeometry()
        )
        bubble = pet.SpeechBubble(host)
        self.addCleanup(bubble.close)
        self.addCleanup(host.close)

        message = "主人看看我～" * 40
        bubble.show_text(message, 4500)
        self.app.processEvents()

        screen = host.current_screen_rect()
        self.assertEqual(bubble.text, message)
        self.assertNotIn("…", bubble.text)
        self.assertGreater(bubble.height(), bubble.fontMetrics().height() + 28)
        self.assertGreaterEqual(bubble.geometry().left(), screen.left() + 4)
        self.assertLessEqual(bubble.geometry().right(), screen.right() - 4)
        self.assertGreaterEqual(bubble.geometry().top(), screen.top() + 4)
        self.assertLessEqual(bubble.geometry().bottom(), screen.bottom() - 4)

    def test_hunger_prompt_is_complete_at_right_screen_edge(self):
        host = QWidget()
        host.setGeometry(690, 330, 190, 220)
        host.show()
        screen = QRect(0, 0, 800, 600)
        host.current_screen_rect = lambda: screen
        bubble = pet.SpeechBubble(host)
        self.addCleanup(bubble.close)
        self.addCleanup(host.close)

        message = "闻到好吃的味道了吗？"
        bubble.show_text(message, 2500)
        self.app.processEvents()

        self.assertEqual(bubble.text, message)
        self.assertLessEqual(bubble.geometry().right(), screen.right() - 4)
        image = bubble.grab().toImage()
        right_round_edge = image.pixelColor(
            image.width() - 5, image.height() // 2
        )
        self.assertGreater(right_round_edge.alpha(), 0)

    def test_tail_tracks_pet_head_when_bubble_body_is_screen_clamped(self):
        host = QWidget()
        host.show()
        anchor = QRect(760, 330, 40, 120)
        host.interface_anchor_rect = lambda: anchor
        host.interface_screen_rect = lambda: QRect(0, 0, 800, 600)
        host.interface_anchor_visible = lambda: True
        bubble = pet.SpeechBubble(host)
        self.addCleanup(bubble.close)
        self.addCleanup(host.close)
        bubble.setGeometry(bubble._bubble_geometry(300, 70))

        expected = anchor.center().x() - bubble.x()

        self.assertEqual(bubble._tail_x(), expected)
        self.assertGreater(bubble._tail_x(), bubble.width() / 2)

    def test_home_bubble_moves_up_without_changing_its_size_or_x_position(self):
        host = QWidget()
        host.show()
        home_active = {"value": False}
        anchor = QRect(300, 260, 190, 220)
        screen = QRect(0, 0, 1000, 800)
        host.interface_anchor_rect = lambda: anchor
        host.interface_screen_rect = lambda: screen
        host.interface_anchor_visible = lambda: True
        host._active_home_interface = (
            lambda: object() if home_active["value"] else None
        )
        bubble = pet.SpeechBubble(host)
        self.addCleanup(bubble.close)
        self.addCleanup(host.close)

        outside = bubble._bubble_geometry(180, 70)
        home_active["value"] = True
        inside = bubble._bubble_geometry(180, 70)

        self.assertEqual(inside.x(), outside.x())
        self.assertEqual(inside.size(), outside.size())
        self.assertEqual(inside.top(), outside.top() - 72)

    def test_home_bubble_uses_a_distinct_warm_room_palette(self):
        host = QWidget()
        host.show()
        home_active = {"value": False}
        host._active_home_interface = (
            lambda: object() if home_active["value"] else None
        )
        bubble = pet.SpeechBubble(host)
        bubble.resize(180, 70)
        bubble.text = ""
        self.addCleanup(bubble.close)
        self.addCleanup(host.close)

        outside = bubble.grab().toImage().pixelColor(90, 24)
        home_active["value"] = True
        inside = bubble.grab().toImage().pixelColor(90, 24)

        self.assertGreater(outside.alpha(), 0)
        self.assertGreater(inside.alpha(), 0)
        self.assertNotEqual(inside, outside)


if __name__ == "__main__":
    unittest.main()

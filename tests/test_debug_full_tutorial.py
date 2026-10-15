# -*- coding: utf-8 -*-
"""调试完整教程入口测试（2026-10-15 用户令）。"""
import unittest
from types import SimpleNamespace

from PyQt5.QtWidgets import QApplication

import pet


class FullTutorialDebugTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, completed):
        host = SimpleNamespace(
            pet_name=pet.ai.DEFAULT_PET_NAME,
            state={"tutorial_completed": completed},
            interface_screen_rect=lambda: QApplication.primaryScreen(
            ).availableGeometry(),
        )
        window = pet.TutorialWindow(host, lambda _name: None)
        self.addCleanup(window.close)
        return window

    def test_replay_defaults_to_five_pages(self):
        window = self._window(completed=True)
        window.start()
        self.assertEqual(len(window.pages), 5)

    def test_debug_force_full_shows_all_seven_pages(self):
        window = self._window(completed=True)
        window.start(force_full=True)
        self.assertEqual(len(window.pages), 7)
        self.assertIn("选择你的伙伴", [p[1] for p in window.pages])

    def test_first_run_naturally_full(self):
        window = self._window(completed=False)
        window.start()
        self.assertEqual(len(window.pages), 7)


if __name__ == "__main__":
    unittest.main()

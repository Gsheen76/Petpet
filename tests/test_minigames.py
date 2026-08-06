import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton

import progression
from minigames import (
    CoinCatchCanvas,
    CoinCatchGameWindow,
    LuckyPawsGameWindow,
    MiniGameHubWindow,
    ShellShuffleCanvas,
)


class MiniGameProgressionTests(unittest.TestCase):
    def test_rewards_have_no_daily_limit(self):
        state = progression.ensure_progression({"pet_coins": 0})

        for score in range(10):
            result = progression.award_minigame_coins(
                state, "coin_catch", 20, score=score
            )
            self.assertEqual(result["reward"], 20)

        self.assertEqual(state["pet_coins"], 200)
        self.assertEqual(state["records"]["coins_minigames"], 200)
        self.assertEqual(state["records"]["minigame_rounds"], 10)
        self.assertEqual(state["minigame_best_scores"]["coin_catch"], 9)

    def test_unknown_game_cannot_award_coins(self):
        state = progression.ensure_progression({"pet_coins": 10})

        result = progression.award_minigame_coins(
            state, "unknown", 20, score=99
        )

        self.assertFalse(result["ok"])
        self.assertEqual(state["pet_coins"], 10)
        self.assertEqual(state["records"]["minigame_rounds"], 0)


class MiniGameUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.pet = SimpleNamespace(
            state=progression.ensure_progression({"pet_coins": 0}),
            current_screen_rect=Mock(return_value=QRect(0, 0, 1400, 900)),
            geometry=Mock(return_value=QRect(900, 600, 190, 220)),
            say=Mock(),
        )
        self.windows = []

    def tearDown(self):
        for window in reversed(self.windows):
            window.close()

    def test_hub_offers_two_games_without_daily_limit_text(self):
        hub = MiniGameHubWindow(self.pet, Mock())
        self.windows = [hub]
        hub.refresh()
        labels = " ".join(
            label.text() for label in hub.findChildren(QLabel)
        )
        buttons = [
            button.text() for button in hub.findChildren(QPushButton)
        ]

        self.assertIn("金币雨", labels)
        self.assertIn("幸运爪爪", labels)
        self.assertIn("没有每日上限", labels)
        self.assertEqual(buttons.count("开始"), 2)

    def test_coin_game_settles_score_and_updates_best(self):
        save = Mock()
        game = CoinCatchGameWindow(self.pet, save)
        self.windows = [game]

        game._finish_round(7, 4)

        self.assertEqual(self.pet.state["pet_coins"], 7)
        self.assertEqual(
            self.pet.state["minigame_best_scores"]["coin_catch"], 7
        )
        self.assertEqual(self.pet.state["records"]["minigame_rounds"], 1)
        save.assert_called_once_with(self.pet.state)

    def test_coin_rain_last_five_seconds_are_double(self):
        self.assertEqual(CoinCatchCanvas.coin_value_for_remaining(5.01), 1)
        self.assertEqual(CoinCatchCanvas.coin_value_for_remaining(5.0), 2)
        self.assertEqual(CoinCatchCanvas.coin_value_for_remaining(0.1), 2)

    def test_lucky_paws_settles_completed_round(self):
        save = Mock()
        game = LuckyPawsGameWindow(self.pet, save)
        self.windows = [game]
        game.successes = 3
        game.earned_reward = 30

        game._finish_game()

        self.assertEqual(game.TOTAL_ROUNDS, 3)
        self.assertEqual(self.pet.state["pet_coins"], 30)
        self.assertEqual(
            self.pet.state["minigame_best_scores"]["lucky_paws"], 3
        )
        save.assert_called_once_with(self.pet.state)

    def test_lucky_paws_rewards_and_speed_increase_each_round(self):
        config = LuckyPawsGameWindow.ROUND_CONFIG

        self.assertEqual(
            [config[index]["reward"] for index in (1, 2, 3)],
            [5, 10, 15],
        )
        self.assertGreater(config[1]["swap_duration"], config[2]["swap_duration"])
        self.assertGreater(config[2]["swap_duration"], config[3]["swap_duration"])
        self.assertLessEqual(config[3]["swap_duration"], 0.15)
        self.assertLess(config[1]["swap_count"], config[3]["swap_count"])

    def test_shell_guess_tracks_the_actual_moved_cup(self):
        canvas = ShellShuffleCanvas()
        self.windows = [canvas]
        canvas.phase = "guess"
        canvas.bowl_order = [2, 0, 1]
        canvas.coin_bowl_id = 0

        self.assertTrue(canvas.resolve_guess(1))
        self.assertEqual(canvas.selected_slot, 1)

    def test_shell_guess_does_not_randomize_when_clicked(self):
        canvas = ShellShuffleCanvas()
        self.windows = [canvas]
        canvas.phase = "guess"
        canvas.bowl_order = [2, 0, 1]
        canvas.coin_bowl_id = 0

        self.assertFalse(canvas.resolve_guess(0))
        self.assertEqual(canvas.coin_bowl_id, 0)


if __name__ == "__main__":
    unittest.main()

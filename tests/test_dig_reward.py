import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt5.QtCore import QRect, QSize
from PyQt5.QtWidgets import QApplication, QWidget
from PIL import Image

import pet
import progression


class SequenceRng:
    def __init__(self, random_values, amount):
        self.random_values = iter(random_values)
        self.amount = amount

    def random(self):
        return next(self.random_values)

    def randint(self, minimum, maximum):
        return max(minimum, min(maximum, self.amount))


class DigRewardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_animation_is_exactly_30_frames_at_20_fps(self):
        animation_dir = Path(pet.ANIMATIONS_DIR)
        frames = sorted((animation_dir / "dig_reward").glob("*.png"))
        manifest = json.loads(
            (animation_dir / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(len(frames), 30)
        self.assertEqual(manifest["dig_reward"]["fps"], 20)
        self.assertFalse(manifest["dig_reward"]["loop"])
        for frame in frames:
            with Image.open(frame) as image:
                self.assertEqual(image.size, (512, 512))
                self.assertEqual(image.mode, "RGBA")

    def test_discovery_persists_reward_and_starts_cooldown(self):
        state = progression.ensure_progression({"pet_coins": 0})
        host = SimpleNamespace(
            state=state,
            dragging=False,
            play_scene=None,
            _dig_reward_claiming=False,
            _interactive_bubble=None,
            _last_interactive_t=0.0,
            isVisible=Mock(return_value=True),
            say=Mock(),
        )
        host._show_pending_dig_bubble = lambda: (
            pet.PetWindow._show_pending_dig_bubble(host)
        )
        rng = SequenceRng([0.01, 0.0], 10)

        with patch("pet.InteractiveBubble") as bubble, patch("pet.save_state"):
            found = pet.PetWindow.maybe_discover_dig_reward(
                host, now=5000.0, rng=rng
            )

        self.assertTrue(found)
        self.assertEqual(state["pending_dig_reward"], 10)
        self.assertEqual(state["last_dig_discovery_at"], 5000.0)
        bubble.assert_called_once_with(
            host, "发现宝藏", "dig_reward", "#e3ac36", ""
        )

    def test_treasure_bubble_is_circular_and_centered_above_pet(self):
        class Host(QWidget):
            pass

        host = Host()
        host.setGeometry(300, 300, 190, 220)
        host.show()
        host.current_screen_rect = lambda: QRect(0, 0, 1000, 800)
        host.state = progression.ensure_progression({
            "pending_dig_reward": 10,
        })
        bubble = pet.InteractiveBubble(
            host, "发现宝藏", "dig_reward", "#e3ac36", ""
        )
        self.addCleanup(bubble.close)
        self.addCleanup(host.close)

        self.assertEqual(bubble.width(), bubble.height())
        self.assertEqual(bubble.size(), QSize(80, 80))
        self.assertAlmostEqual(
            bubble.frameGeometry().center().x(),
            host.geometry().center().x(),
            delta=1,
        )
        self.assertEqual(
            bubble.frameGeometry().top(),
            host.geometry().top() - 21,
        )

    def test_desktop_menu_temporarily_hides_then_restores_treasure(self):
        bubble = SimpleNamespace(
            action_name="dig_reward",
            isVisible=Mock(return_value=True),
            hide=Mock(),
            show=Mock(),
            raise_=Mock(),
            _place_above_pet=Mock(),
        )
        host = SimpleNamespace(
            state={"pending_dig_reward": 10},
            _interactive_bubble=bubble,
            _hidden_treasure_bubble=None,
            _bubble_menu=None,
        )

        self.assertTrue(pet.PetWindow.hide_treasure_for_menu(host))
        self.assertIsNone(host._interactive_bubble)
        self.assertIs(host._hidden_treasure_bubble, bubble)
        bubble.hide.assert_called_once_with()

        self.assertTrue(pet.PetWindow.restore_treasure_after_menu(host))
        self.assertIs(host._interactive_bubble, bubble)
        self.assertIsNone(host._hidden_treasure_bubble)
        bubble._place_above_pet.assert_called_once_with()
        bubble.show.assert_called_once_with()

    def test_claim_awards_only_after_animation_finishes(self):
        state = progression.ensure_progression({
            "pet_coins": 20,
            "pending_dig_reward": 8,
        })
        callbacks = []

        def trigger(name, duration_ms=None, finished_callback=None):
            self.assertEqual(name, "dig_reward")
            callbacks.append(finished_callback)

        host = SimpleNamespace(
            state=state,
            _dig_reward_claiming=False,
            trigger_animation=trigger,
            geometry=Mock(return_value=QRect(100, 100, 190, 220)),
            say=Mock(),
            shop_win=None,
        )

        with patch("pet.save_state"), patch("pet.BonusBubble"):
            self.assertTrue(pet.PetWindow.claim_dig_reward(host))
            self.assertEqual(state["pet_coins"], 20)
            callbacks[0]()

        self.assertEqual(state["pet_coins"], 28)
        self.assertEqual(state["pending_dig_reward"], 0)
        self.assertEqual(state["records"]["coins_dug"], 8)
        self.assertEqual(state["records"]["dig_treasures_found"], 1)


if __name__ == "__main__":
    unittest.main()

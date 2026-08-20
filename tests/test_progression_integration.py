import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt5.QtCore import QPoint, QRect

import pet
import progression


class InteractionUpgradeIntegrationTests(unittest.TestCase):
    def test_feeding_upgrade_changes_the_real_feed_action(self):
        state = progression.ensure_progression({
            "sleeping": False,
            "hunger": 40,
            "mood": 40,
            "energy": 70,
            "upgrades": {"feeding": 5},
        })
        fake = SimpleNamespace(
            state=state,
            behavior="idle",
            behavior_until=0,
            say=Mock(),
            play_sound=Mock(),
            trigger_animation=Mock(),
            add_xp=Mock(),
            refresh_pose_from_state=Mock(),
        )

        with patch("pet.save_state"):
            pet.PetWindow.feed(fake)

        self.assertEqual(state["hunger"], 80)
        self.assertEqual(state["mood"], 51)
        self.assertEqual(state["records"]["feedings"], 1)
        self.assertEqual(state["records"]["interactions_total"], 1)
        self.assertEqual(state["affection_points"], 4)
        fake.add_xp.assert_called_once_with(8)

    def test_max_play_upgrade_allows_play_without_attribute_cost(self):
        state = progression.ensure_progression({
            "sleeping": False,
            "hunger": 50,
            "mood": 40,
            "energy": 0,
            "upgrades": {"playing": 5},
        })
        fake = SimpleNamespace(
            state=state,
            play_scene=None,
            behavior="idle",
            target_vx=0,
            vx=0,
            vy=0,
            on_ground=True,
            _play_return_pos=None,
            _on_play_scene_finished=Mock(),
            say=Mock(),
            play_sound=Mock(),
            add_xp=Mock(),
            pos=Mock(return_value=QPoint(30, 40)),
            hide=Mock(),
        )
        scene = Mock()

        with patch("pet.FetchPlayScene", return_value=scene), \
                patch("pet.save_state"):
            pet.PetWindow.play(fake)

        self.assertEqual(state["energy"], 0)
        self.assertEqual(state["hunger"], 50)
        self.assertEqual(state["mood"], 75)
        self.assertEqual(state["records"]["play_sessions"], 1)
        self.assertEqual(state["affection_points"], 5)
        fake.add_xp.assert_called_once_with(22)
        scene.start.assert_called_once_with()

    def test_max_sleep_upgrade_recovers_more_without_hunger_cost(self):
        state = progression.ensure_progression({
            "sleeping": True,
            "sleep_mode": "manual",
            "hunger": 50,
            "mood": 70,
            "energy": 20,
            "upgrades": {"sleeping": 5},
        })
        fake = SimpleNamespace(
            state=state,
            settings={
                "decay_energy_sleeping_gain": 4,
                "decay_hunger_sleeping": 0.08,
            },
            _update_auto_sleep_state=Mock(return_value="sleeping"),
            refresh_pose_from_state=Mock(),
        )

        with patch("pet.save_state"):
            pet.PetWindow.on_decay(fake)

        self.assertEqual(state["hunger"], 50)
        self.assertEqual(state["energy"], 30)

    def test_max_endurance_halves_all_awake_natural_decay(self):
        state = progression.ensure_progression({
            "sleeping": False,
            "hunger": 100,
            "mood": 100,
            "energy": 100,
            "upgrades": {"endurance": 5},
        })
        fake = SimpleNamespace(
            state=state,
            settings={
                "decay_hunger": 0.14,
                "decay_energy": 0.10,
                "decay_mood": 0.08,
            },
            _update_auto_sleep_state=Mock(return_value="walking"),
            refresh_pose_from_state=Mock(),
        )

        with patch("pet.save_state"):
            pet.PetWindow.on_decay(fake)

        self.assertAlmostEqual(state["hunger"], 99.965)
        self.assertAlmostEqual(state["energy"], 99.975)
        self.assertAlmostEqual(state["mood"], 99.98)

    def test_endurance_does_not_change_sleeping_hunger_cost(self):
        state = progression.ensure_progression({
            "sleeping": True,
            "sleep_mode": "manual",
            "hunger": 50,
            "mood": 70,
            "energy": 20,
            "upgrades": {"endurance": 5},
        })
        fake = SimpleNamespace(
            state=state,
            settings={
                "decay_energy_sleeping_gain": 4,
                "decay_hunger_sleeping": 0.08,
            },
            _update_auto_sleep_state=Mock(return_value="sleeping"),
            refresh_pose_from_state=Mock(),
        )

        with patch("pet.save_state"):
            pet.PetWindow.on_decay(fake)

        self.assertAlmostEqual(state["hunger"], 49.96)

    def test_experience_upgrade_is_used_by_pet_leveling(self):
        state = progression.ensure_progression({
            "level": 1,
            "xp": 90,
            "upgrades": {"experience": 5},
        })
        fake = SimpleNamespace(state=state)

        with patch("pet.save_state"):
            leveled = pet.PetWindow.add_xp(fake, 10)

        self.assertTrue(leveled)
        self.assertEqual(state["level"], 2)
        self.assertEqual(state["xp"], 5)
        self.assertEqual(state["records"]["xp_earned"], 15)
        self.assertEqual(state["records"]["level_ups"], 1)

    def test_random_need_bubbles_never_grant_experience(self):
        for action in ("feed", "play", "sleep"):
            with self.subTest(action=action):
                state = progression.ensure_progression({
                    "sleeping": False,
                    "sleep_mode": None,
                    "hunger": 40,
                    "mood": 40,
                    "energy": 50,
                    "level": 1,
                })
                fake_pet = SimpleNamespace(
                    state=state,
                    feed=Mock(),
                    play=Mock(),
                    add_xp=Mock(),
                    say=Mock(),
                    refresh_pose_from_state=Mock(),
                    geometry=Mock(return_value=QRect(20, 20, 190, 220)),
                    _interactive_bubble=object(),
                )
                fake_bubble = SimpleNamespace(
                    pet=fake_pet,
                    action_name=action,
                    color="#f39a68",
                    close=Mock(),
                )

                with patch("pet.save_state"), patch("pet.BonusBubble"):
                    pet.InteractiveBubble._trigger(fake_bubble)

                fake_pet.add_xp.assert_not_called()
                if action == "feed":
                    fake_pet.feed.assert_called_once_with(grant_xp=False)
                elif action == "play":
                    fake_pet.play.assert_called_once_with(grant_xp=False)

    def test_passive_xp_uses_affection_rate_and_skips_second_bonus(self):
        state = progression.ensure_progression({
            "level": 1,
            "xp": 0,
            "affection_level": 1,
            "passive_xp_buffer": 0.96,
            "upgrades": {"experience": 5},
        })
        fake = SimpleNamespace(
            state=state,
            add_xp=Mock(return_value=False),
            say=Mock(),
            geometry=Mock(return_value=QRect(0, 0, 190, 220)),
        )

        pet.PetWindow.on_passive_xp(fake)

        fake.add_xp.assert_called_once_with(1, apply_bonus=False)
        self.assertEqual(state["records"]["active_seconds"], 1)
        self.assertAlmostEqual(state["passive_xp_buffer"], 0.035)

    def test_passive_tick_accumulates_and_persists_fractional_affection(self):
        state = progression.ensure_progression({
            "level": 1,
            "xp": 0,
            "hunger": 100,
            "mood": 100,
            "energy": 100,
            "affection_level": 1,
            "affection_points": 0,
            "passive_xp_buffer": 0.0,
            "passive_affection_buffer": 0.995,
        })
        fake = SimpleNamespace(
            state=state,
            add_xp=Mock(return_value=False),
            say=Mock(),
            interface_bonus_origin=Mock(return_value=(10, 10)),
        )

        with patch("pet.save_state") as save, patch("pet.BonusBubble"):
            pet.PetWindow.on_passive_xp(fake)

        self.assertEqual(state["affection_points"], 1)
        self.assertAlmostEqual(state["passive_affection_buffer"], 0.005)
        save.assert_called_once_with(state)


if __name__ == "__main__":
    unittest.main()

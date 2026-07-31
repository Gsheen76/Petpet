import time
import unittest

import progression


def fresh_state(**overrides):
    state = {
        "born": time.time(),
        "level": 1,
        "xp": 0,
        "hunger": 80,
        "mood": 70,
        "energy": 90,
    }
    state.update(overrides)
    return progression.ensure_progression(state)


class ProgressionMigrationTests(unittest.TestCase):
    def test_old_save_is_extended_without_losing_existing_values(self):
        state = {
            "level": 8,
            "xp": 1172,
            "pet_name": "summer",
            "records": {"pettings": 4},
            "upgrades": {"playing": 2},
        }

        progression.ensure_progression(state)

        self.assertEqual(state["level"], 8)
        self.assertEqual(state["xp"], 1172)
        self.assertEqual(state["pet_name"], "summer")
        self.assertEqual(state["records"]["pettings"], 4)
        self.assertEqual(state["records"]["feedings"], 0)
        self.assertEqual(state["upgrades"]["playing"], 2)
        self.assertEqual(state["pet_coins"], 0)
        self.assertEqual(state["affection_level"], 1)
        self.assertEqual(state["affection_points"], 0)
        self.assertEqual(state["passive_xp_buffer"], 0.0)
        self.assertIn("pettings", state["affection_last_gains"])
        self.assertEqual(state["owned_decorations"], [])
        self.assertIsNone(state["equipped_decorations"]["neck"])
        self.assertEqual(state["records"]["ai_replies"], 0)
        self.assertEqual(state["records"]["autonomous_walks"], 0)
        self.assertEqual(state["decoration_adjustments"], {})

    def test_invalid_nested_values_are_safely_normalized(self):
        state = {
            "records": "broken",
            "upgrades": {"playing": 999, "feeding": -2},
            "claimed_achievements": "not-a-list",
            "pet_coins": -50,
        }

        progression.ensure_progression(state)

        self.assertEqual(state["pet_coins"], 0)
        self.assertEqual(state["upgrades"]["playing"], 5)
        self.assertEqual(state["upgrades"]["feeding"], 0)
        self.assertEqual(state["claimed_achievements"], [])


class RecordTests(unittest.TestCase):
    def test_core_actions_increment_individual_and_total_records(self):
        state = fresh_state()

        progression.record_action(state, "pettings")
        progression.record_action(state, "feedings", 2)
        progression.record_sleep(state, "auto")

        self.assertEqual(state["records"]["pettings"], 1)
        self.assertEqual(state["records"]["feedings"], 2)
        self.assertEqual(state["records"]["sleep_sessions"], 1)
        self.assertEqual(state["records"]["auto_sleeps"], 1)
        self.assertEqual(state["records"]["interactions_total"], 4)
        self.assertEqual(state["affection_points"], 8)

    def test_every_user_interaction_adds_balanced_affection(self):
        state = fresh_state()

        progression.record_action(state, "pettings")
        progression.record_action(state, "feedings")
        progression.record_action(state, "play_sessions")
        progression.record_action(state, "fetch_catches")
        progression.record_action(state, "chats_opened")
        progression.record_action(state, "wake_shakes")
        progression.record_sleep(state, "manual")

        self.assertEqual(state["affection_points"], 15)
        self.assertEqual(state["records"]["affection_earned"], 15)

    def test_auto_sleep_does_not_count_as_user_affection(self):
        state = fresh_state()

        progression.record_sleep(state, "auto")

        self.assertEqual(state["affection_points"], 0)
        self.assertEqual(state["records"]["affection_earned"], 0)

    def test_repeated_non_chat_action_obeys_its_own_cooldown(self):
        state = fresh_state()

        first = progression.record_action(
            state, "pettings", now=1000
        )
        blocked = progression.record_action(
            state, "pettings", now=1005
        )
        ready = progression.record_action(
            state, "pettings", now=1020
        )

        self.assertTrue(first["eligible"])
        self.assertFalse(blocked["eligible"])
        self.assertGreater(blocked["cooldown_remaining"], 0)
        self.assertTrue(ready["eligible"])
        self.assertEqual(state["records"]["pettings"], 3)
        self.assertEqual(state["affection_points"], 4)

    def test_different_actions_have_independent_cooldowns(self):
        state = fresh_state()

        progression.record_action(state, "pettings", now=1000)
        progression.record_action(state, "feedings", now=1000)

        self.assertEqual(state["affection_points"], 5)

    def test_chat_affection_has_no_cooldown(self):
        state = fresh_state()

        progression.record_action(state, "chats_opened", now=1000)
        progression.record_action(state, "chats_opened", now=1000)
        progression.record_action(state, "chats_opened", now=1000)

        self.assertEqual(state["records"]["chats_opened"], 3)
        self.assertEqual(state["affection_points"], 3)

    def test_active_time_and_coin_totals_are_lifetime_values(self):
        state = fresh_state()

        progression.record_active_time(state, 120)
        progression.add_coins(state, 35, source="achievement")

        self.assertEqual(state["records"]["active_seconds"], 120)
        self.assertEqual(state["pet_coins"], 35)
        self.assertEqual(state["records"]["coins_earned"], 35)
        self.assertEqual(progression.format_duration(90061), "1 天 1 小时")


class AchievementTests(unittest.TestCase):
    def test_early_achievements_are_easy_and_rewards_are_claimable_once(self):
        now = time.time()
        state = fresh_state(born=now - 2 * 86400, level=2)
        for key in (
            "pettings", "feedings", "play_sessions", "sleep_sessions",
            "chats_opened",
        ):
            progression.record_action(state, key)

        claimable = progression.claimable_achievements(state, now)
        ids = {item["id"] for item in claimable}

        self.assertIn("days_1", ids)
        self.assertIn("level_2", ids)
        self.assertIn("pet_1", ids)
        result = progression.claim_achievement(state, "level_2", now)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reward"], 25)
        self.assertEqual(state["pet_coins"], 25)
        duplicate = progression.claim_achievement(state, "level_2", now)
        self.assertFalse(duplicate["ok"])
        self.assertEqual(state["pet_coins"], 25)

    def test_every_reached_level_has_its_own_reward(self):
        state = fresh_state(level=6)
        items = progression.achievement_catalog(state)
        level_ids = {
            item["id"] for item in items
            if item["category"] == "等级" and item["completed"]
        }

        self.assertEqual(
            level_ids,
            {"level_2", "level_3", "level_4", "level_5", "level_6"},
        )
        self.assertTrue(any(
            item["id"] == "level_7" and not item["completed"]
            for item in items
        ))

    def test_claim_all_updates_balance_and_lifetime_income(self):
        now = time.time()
        state = fresh_state(born=now - 4 * 86400, level=3)

        result = progression.claim_all_achievements(state, now)

        self.assertGreaterEqual(result["count"], 4)
        self.assertGreater(result["reward"], 0)
        self.assertEqual(state["pet_coins"], result["reward"])
        self.assertEqual(
            state["records"]["coins_earned"], result["reward"]
        )
        self.assertEqual(
            progression.claim_all_achievements(state, now)["reward"], 0
        )

    def test_new_content_records_have_matching_achievements(self):
        state = fresh_state()
        for action in ("ai_replies", "autonomous_walks"):
            progression.record_action(state, action, 5)
        state["records"]["upgrades_purchased"] = 1
        state["records"]["decorations_collected"] = 1

        items = progression.achievement_catalog(state)
        completed_ids = {
            item["id"] for item in items if item["completed"]
        }

        self.assertIn("reply_5", completed_ids)
        self.assertIn("stroll_5", completed_ids)
        self.assertIn("upgrade_1", completed_ids)
        self.assertIn("collect_1", completed_ids)


class UpgradeBalanceTests(unittest.TestCase):
    def test_upgrade_purchase_spends_coins_and_changes_real_effect(self):
        state = fresh_state(pet_coins=100)

        result = progression.purchase_upgrade(state, "petting")
        effects = progression.upgrade_effects(state)

        self.assertTrue(result["ok"])
        self.assertEqual(result["price"], 30)
        self.assertEqual(state["pet_coins"], 70)
        self.assertEqual(state["records"]["coins_spent"], 30)
        self.assertEqual(state["records"]["upgrades_purchased"], 1)
        self.assertEqual(effects["pet_mood"], 10)
        self.assertEqual(effects["pet_xp"], 3)

    def test_play_and_sleep_max_levels_remove_attribute_costs(self):
        state = fresh_state()
        state["upgrades"]["playing"] = 5
        state["upgrades"]["sleeping"] = 5

        effects = progression.upgrade_effects(state)

        self.assertEqual(effects["play_energy_cost"], 0)
        self.assertEqual(effects["play_hunger_cost"], 0)
        self.assertEqual(effects["sleep_hunger_multiplier"], 0)
        self.assertGreater(effects["play_mood"], 20)
        self.assertGreater(effects["sleep_energy_gain_bonus"], 0)

    def test_experience_upgrade_is_capped_and_applies_to_all_xp(self):
        state = fresh_state()
        state["upgrades"]["experience"] = 5

        effective = progression.apply_xp_bonus(state, 10)

        self.assertEqual(effective, 15)
        self.assertEqual(state["records"]["xp_earned"], 15)

    def test_endurance_reduces_awake_decay_but_not_sleep_hunger(self):
        state = fresh_state(upgrades={"endurance": 1})

        self.assertAlmostEqual(
            progression.upgrade_effects(state)[
                "awake_decay_multiplier"
            ],
            0.9,
        )

        state["upgrades"]["endurance"] = 5
        effects = progression.upgrade_effects(state)
        description = progression.upgrade_description(
            state, "endurance"
        )

        self.assertAlmostEqual(
            effects["awake_decay_multiplier"], 0.5
        )
        self.assertEqual(description, "清醒属性消耗减缓 50%")

    def test_sleep_upgrade_description_uses_actual_values_not_percentages(self):
        state = fresh_state(upgrades={"sleeping": 2})

        description = progression.upgrade_description(
            state,
            "sleeping",
            decay_rates={"decay_hunger_sleeping": 0.10},
        )

        self.assertIn("精力恢复 6.4 点", description)
        self.assertIn("饱腹消耗 0.060 点", description)
        self.assertNotIn("%", description)

    def test_full_upgrade_cost_stays_long_term_but_not_unreachable(self):
        total_cost = sum(
            sum(definition["prices"])
            for definition in progression.UPGRADE_DEFINITIONS.values()
        )

        self.assertGreater(total_cost, 3500)
        self.assertLess(total_cost, 4000)


class AffectionExperienceTests(unittest.TestCase):
    def test_affection_levels_keep_remainder_and_raise_rate(self):
        state = fresh_state()
        low_rate = progression.passive_xp_per_second(state)

        result = progression.add_affection(state, 35)
        high_rate = progression.passive_xp_per_second(state)

        self.assertTrue(result["leveled"])
        self.assertEqual(state["affection_level"], 2)
        self.assertEqual(state["affection_points"], 5)
        self.assertEqual(state["records"]["affection_level_ups"], 1)
        self.assertGreater(high_rate, low_rate)

    def test_passive_rate_is_not_affected_by_pet_attributes(self):
        healthy = fresh_state(
            affection_level=8, hunger=100, mood=100, energy=100
        )
        needy = fresh_state(
            affection_level=8, hunger=0, mood=0, energy=0
        )

        self.assertEqual(
            progression.passive_xp_per_second(healthy),
            progression.passive_xp_per_second(needy),
        )

    def test_experience_upgrade_multiplies_affection_rate(self):
        base = fresh_state(affection_level=6)
        upgraded = fresh_state(
            affection_level=6,
            upgrades={"experience": 5},
        )

        self.assertAlmostEqual(
            progression.passive_xp_per_second(upgraded),
            progression.passive_xp_per_second(base) * 1.5,
        )

    def test_display_rate_converts_seconds_to_minutes(self):
        state = fresh_state(affection_level=1)

        self.assertAlmostEqual(
            progression.passive_xp_per_minute(state), 3.0
        )


class DecorationTests(unittest.TestCase):
    def test_new_decorations_have_consistent_categories_and_small_defaults(self):
        expected = {
            "black_sunglasses": ("eyes", 0.29),
            "sky_bow_tie": ("neck", 0.23),
            "little_orange_hat": ("head", 0.11),
        }

        for decoration_id, (category, maximum_scale) in expected.items():
            definition = progression.DECORATION_DEFINITIONS[decoration_id]
            self.assertEqual(definition["category"], category)
            self.assertLessEqual(
                definition["default_transform"]["scale"],
                maximum_scale,
            )
            self.assertGreaterEqual(definition["price"], 360)

    def test_paid_decorations_have_collectible_pricing(self):
        self.assertEqual(
            progression.DECORATION_DEFINITIONS["round_glasses"]["price"],
            250,
        )
        self.assertEqual(
            progression.DECORATION_DEFINITIONS["cream_beret"]["price"],
            340,
        )

    def test_all_paid_decoration_prices_use_the_rebalanced_values(self):
        expected = {
            "round_glasses": 250,
            "cream_beret": 340,
            "black_sunglasses": 360,
            "sky_bow_tie": 380,
            "little_orange_hat": 420,
        }
        self.assertEqual(
            {
                item_id: progression.DECORATION_DEFINITIONS[item_id]["price"]
                for item_id in expected
            },
            expected,
        )

    def test_dig_reward_tiers_and_cooldown_are_bounded(self):
        class FixedRng:
            def __init__(self, values):
                self.values = iter(values)

            def random(self):
                return next(self.values)

            def randint(self, minimum, maximum):
                return maximum

        common = progression.roll_dig_reward(FixedRng([0.0]))
        jackpot = progression.roll_dig_reward(FixedRng([0.999]))
        self.assertEqual(common["amount"], 10)
        self.assertEqual(jackpot["amount"], 100)

        state = fresh_state(last_dig_discovery_at=100.0)
        self.assertEqual(
            progression.dig_cooldown_remaining(state, now=100.0),
            progression.DIG_COOLDOWN_SECONDS,
        )
        self.assertEqual(
            progression.dig_cooldown_remaining(
                state,
                now=100.0 + progression.DIG_COOLDOWN_SECONDS,
            ),
            0.0,
        )

    def test_free_collar_can_be_claimed_equipped_and_removed(self):
        state = fresh_state(pet_coins=25)

        claimed = progression.purchase_decoration(
            state, "red_collar"
        )
        equipped = progression.equip_decoration(
            state, "red_collar"
        )

        self.assertTrue(claimed["ok"])
        self.assertEqual(claimed["price"], 0)
        self.assertEqual(state["pet_coins"], 25)
        self.assertTrue(equipped["ok"])
        self.assertEqual(state["records"]["decorations_collected"], 1)
        self.assertEqual(state["records"]["outfit_changes"], 1)
        self.assertEqual(
            state["equipped_decorations"]["neck"], "red_collar"
        )

        removed = progression.unequip_decoration(state, "neck")

        self.assertTrue(removed["ok"])
        self.assertEqual(state["records"]["outfit_changes"], 2)
        self.assertIsNone(state["equipped_decorations"]["neck"])
        self.assertIn("red_collar", state["owned_decorations"])

    def test_collar_cannot_be_claimed_twice_or_equipped_unowned(self):
        state = fresh_state()

        denied = progression.equip_decoration(state, "red_collar")
        progression.purchase_decoration(state, "red_collar")
        duplicate = progression.purchase_decoration(
            state, "red_collar"
        )

        self.assertFalse(denied["ok"])
        self.assertFalse(duplicate["ok"])
        self.assertEqual(
            state["owned_decorations"], ["red_collar"]
        )

    def test_decoration_adjustments_are_persisted_clamped_and_reset(self):
        state = fresh_state()
        default = progression.decoration_transform(
            state, "round_glasses"
        )

        changed = progression.set_decoration_transform(
            state,
            "round_glasses",
            x=99,
            y=-99,
            scale=0,
            rotation=80,
        )

        self.assertEqual(changed["x"], 1.15)
        self.assertEqual(changed["y"], -0.15)
        self.assertEqual(changed["scale"], 0.15)
        self.assertEqual(changed["rotation"], 30.0)
        self.assertEqual(
            progression.decoration_transform(
                state, "round_glasses"
            ),
            changed,
        )

        reset = progression.reset_decoration_transform(
            state, "round_glasses"
        )

        self.assertEqual(reset, default)
        self.assertNotIn(
            "round_glasses", state["decoration_adjustments"]
        )

    def test_invalid_saved_decoration_adjustments_are_safely_migrated(self):
        state = fresh_state(decoration_adjustments={
            "red_collar": {
                "x": "broken",
                "y": None,
                "scale": "0.7",
                "rotation": -999,
            },
            "removed_item": {"x": 0.5},
        })

        transform = progression.decoration_transform(
            state, "red_collar"
        )

        self.assertEqual(
            transform["x"],
            progression.DECORATION_DEFINITIONS[
                "red_collar"
            ]["default_transform"]["x"],
        )
        self.assertEqual(transform["scale"], 0.7)
        self.assertEqual(transform["rotation"], -30.0)
        self.assertNotIn(
            "removed_item", state["decoration_adjustments"]
        )


if __name__ == "__main__":
    unittest.main()

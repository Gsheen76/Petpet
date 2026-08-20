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


def test_purchase_pet_uses_shared_coins_once():
    state = {
        "player": {
            "pet_coins": 900,
            "owned_pet_ids": ["lunch_meat"],
        },
        "owned_pet_ids": ["lunch_meat"],
        "pets": {"lunch_meat": {"pet_name": "午餐肉"}},
    }

    result = progression.purchase_pet(state, "ice_cream")

    assert result["ok"] is True
    assert result["price"] == 760
    assert result["original_price"] == 1000
    assert result["discount"] == 0.76
    assert state["player"]["pet_coins"] == 140
    assert state["owned_pet_ids"] == ["lunch_meat", "ice_cream"]
    assert "ice_cream" not in state["pets"]
    assert progression.purchase_pet(state, "ice_cream")["ok"] is False


def test_available_pet_ids_preserve_registry_order():
    assert progression.available_pet_ids() == (
        "lunch_meat", "ice_cream"
    )


def test_pet_owned_reads_the_shared_owned_pet_ids():
    state = {"owned_pet_ids": ["lunch_meat"]}

    assert progression.pet_owned(state, "lunch_meat") is True
    assert progression.pet_owned(state, "ice_cream") is False


def test_pet_owned_does_not_normalize_render_state():
    state = {"owned_pet_ids": ("lunch_meat", "lunch_meat", 7)}

    assert progression.pet_owned(state, "lunch_meat") is True
    assert state == {"owned_pet_ids": ("lunch_meat", "lunch_meat", 7)}


def test_purchase_pet_keeps_the_legacy_coin_facade_in_sync():
    state = {
        "player": {"pet_coins": 760},
        "pet_coins": 760,
        "owned_pet_ids": ["lunch_meat"],
    }

    progression.purchase_pet(state, "ice_cream")

    assert state["player"]["pet_coins"] == 0
    assert state["pet_coins"] == 0


def test_first_purchase_discount_only_applies_to_pets():
    state = fresh_state(pet_coins=2000)
    result = progression.purchase_pet(state, "ice_cream")
    assert result["price"] == 760
    assert state["pet_coins"] == 1240
    assert state["shop_first_purchase_discounts"]["pets"] is False

    outfit = progression.purchase_outfit(state, "dinosaur_suit")
    assert outfit["price"] == 680
    home = progression.purchase_home_decoration(state, "home_sofa")
    assert home["price"] == 240
    assert state["pet_coins"] == 320


def test_old_outfit_and_home_discount_flags_are_ignored():
    state = fresh_state(
        pet_coins=1000,
        shop_first_purchase_discounts={
            "pets": True,
            "outfits": True,
            "home": True,
        },
    )
    assert progression.purchase_outfit(state, "dinosaur_suit")["price"] == 680
    assert progression.purchase_home_decoration(state, "home_rug")["price"] == 120


def test_outfit_and_home_purchases_use_and_sync_shared_player_coins():
    outfit_state = fresh_state(
        pet_coins=0,
        player={"pet_coins": 680},
    )
    assert progression.purchase_outfit(outfit_state, "dinosaur_suit")["ok"] is True
    assert outfit_state["player"]["pet_coins"] == 0
    assert outfit_state["pet_coins"] == 0

    home_state = fresh_state(
        pet_coins=0,
        player={"pet_coins": 240},
    )
    assert progression.purchase_home_decoration(home_state, "home_sofa")["ok"] is True
    assert home_state["player"]["pet_coins"] == 0
    assert home_state["pet_coins"] == 0


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
        self.assertEqual(state["passive_affection_buffer"], 0.0)
        self.assertIn("pettings", state["affection_last_gains"])
        self.assertEqual(state["owned_decorations"], [])
        self.assertIsNone(state["equipped_decorations"]["neck"])
        self.assertEqual(state["records"]["ai_replies"], 0)
        self.assertEqual(state["records"]["autonomous_walks"], 0)
        self.assertEqual(state["decoration_adjustments"], {})

    def test_outfit_state_is_initialized_without_legacy_decorations(self):
        state = fresh_state()

        self.assertEqual(list(progression.OUTFIT_DEFINITIONS), [
            "dinosaur_suit",
            "strawberry_suit",
        ])
        self.assertEqual(state["owned_outfits"], [])
        self.assertIsNone(state["equipped_outfit"])

    def test_dinosaur_outfit_can_be_purchased_and_equipped(self):
        state = fresh_state(pet_coins=680)

        purchased = progression.purchase_outfit(state, "dinosaur_suit")
        equipped = progression.equip_outfit(state, "dinosaur_suit")

        self.assertTrue(purchased["ok"])
        self.assertTrue(equipped["ok"])
        self.assertEqual(state["pet_coins"], 0)
        self.assertEqual(state["owned_outfits"], ["dinosaur_suit"])
        self.assertEqual(state["equipped_outfit"], "dinosaur_suit")
        self.assertEqual(
            progression.equipped_outfit_animation(state), "idle_dinosaur"
        )

    def test_strawberry_outfit_can_be_purchased_and_equipped(self):
        state = fresh_state(pet_coins=760)

        purchased = progression.purchase_outfit(state, "strawberry_suit")
        equipped = progression.equip_outfit(state, "strawberry_suit")

        self.assertTrue(purchased["ok"])
        self.assertTrue(equipped["ok"])
        self.assertEqual(state["pet_coins"], 0)
        self.assertEqual(state["equipped_outfit"], "strawberry_suit")
        self.assertEqual(
            progression.equipped_outfit_animation(state), "idle_strawberry"
        )

    def test_old_save_receives_home_scene_defaults(self):
        state = {"level": 3, "pet_coins": 20}

        progression.ensure_progression(state)

        self.assertEqual(
            state["home_scene"],
            {
                "enabled": False,
                "background_visible": True,
                "screen_index": 0,
                "viewport_x": 0,
                "viewport_y": 0,
                "viewport_pinned": False,
                "decorating": False,
            },
        )
        self.assertEqual(state["owned_home_decorations"], [])
        self.assertEqual(state["home_decoration_positions"], {})
        self.assertEqual(state["home_stored_decorations"], [])
        self.assertEqual(state["home_decoration_transforms"], {})

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
        self.assertEqual(state["affection_points"], 9)

    def test_every_user_interaction_adds_balanced_affection(self):
        state = fresh_state()

        progression.record_action(state, "pettings")
        progression.record_action(state, "feedings")
        progression.record_action(state, "play_sessions")
        progression.record_action(state, "fetch_catches")
        progression.record_action(state, "chats_opened")
        progression.record_action(state, "wake_shakes")
        progression.record_sleep(state, "manual")

        self.assertEqual(state["affection_points"], 16)
        self.assertEqual(state["records"]["affection_earned"], 16)

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
            state, "pettings", now=1060
        )

        self.assertTrue(first["eligible"])
        self.assertFalse(blocked["eligible"])
        self.assertGreater(blocked["cooldown_remaining"], 0)
        self.assertTrue(ready["eligible"])
        self.assertEqual(state["records"]["pettings"], 3)
        self.assertEqual(state["affection_points"], 2)

    def test_different_actions_have_independent_cooldowns(self):
        state = fresh_state()

        progression.record_action(state, "pettings", now=1000)
        progression.record_action(state, "feedings", now=1000)

        self.assertEqual(state["affection_points"], 5)

    def test_only_successful_ai_reply_grants_chat_affection_with_cooldown(self):
        state = fresh_state()

        progression.record_action(state, "chats_opened", now=1000)
        first = progression.record_action(state, "ai_replies", now=1000)
        blocked = progression.record_action(state, "ai_replies", now=1100)
        ready = progression.record_action(state, "ai_replies", now=1180)

        self.assertTrue(first["eligible"])
        self.assertFalse(blocked["eligible"])
        self.assertTrue(ready["eligible"])
        self.assertEqual(state["records"]["chats_opened"], 1)
        self.assertEqual(state["records"]["ai_replies"], 3)
        self.assertEqual(state["affection_points"], 2)

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


class HomeDecorationTests(unittest.TestCase):
    def test_status_card_is_a_free_wall_furniture_claim(self):
        state = fresh_state(pet_coins=0)

        result = progression.purchase_home_decoration(
            state, "home_status_card"
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["price"], 0)
        self.assertEqual(state["pet_coins"], 0)
        self.assertIn("home_status_card", state["owned_home_decorations"])
        self.assertLessEqual(
            progression.home_decoration_position(
                state, "home_status_card"
            )["y"],
            220,
        )

    def test_home_decoration_purchase_spends_coins_and_persists_position(self):
        state = fresh_state(pet_coins=500)

        result = progression.purchase_home_decoration(state, "home_sofa")

        self.assertTrue(result["ok"])
        self.assertIn("home_sofa", state["owned_home_decorations"])
        self.assertEqual(state["pet_coins"], 260)
        self.assertEqual(
            progression.set_home_decoration_position(state, "home_sofa", -80, 900),
            {"x": 0, "y": 543},
        )
        self.assertEqual(
            progression.home_decoration_position(state, "home_sofa"),
            {"x": 0, "y": 543},
        )

    def test_home_decoration_cannot_be_bought_twice_or_without_funds(self):
        state = fresh_state(pet_coins=0)
        denied = progression.purchase_home_decoration(state, "home_plant")
        self.assertFalse(denied["ok"])

        state["pet_coins"] = 500
        self.assertTrue(progression.purchase_home_decoration(state, "home_plant")["ok"])
        duplicate = progression.purchase_home_decoration(state, "home_plant")
        self.assertFalse(duplicate["ok"])

    def test_home_decoration_storage_and_transform_are_persisted(self):
        state = fresh_state(pet_coins=500)
        progression.purchase_home_decoration(state, "home_sofa")

        self.assertTrue(progression.store_home_decoration(state, "home_sofa"))
        self.assertIn("home_sofa", state["home_stored_decorations"])
        self.assertTrue(progression.place_home_decoration(state, "home_sofa"))
        self.assertNotIn("home_sofa", state["home_stored_decorations"])
        self.assertEqual(
            progression.set_home_decoration_transform(
                state, "home_sofa", scale=1.1, rotation=15
            ),
            {"scale": 1.1, "rotation": 15.0},
        )


class AffectionExperienceTests(unittest.TestCase):
    def test_affection_threshold_starts_small_and_caps_at_200(self):
        self.assertEqual(progression.affection_to_next(1), 30)
        self.assertEqual(progression.affection_to_next(2), 40)
        self.assertEqual(progression.affection_to_next(18), 200)
        self.assertEqual(progression.affection_to_next(99), 200)

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

    def test_passive_affection_halves_for_each_zero_attribute(self):
        healthy = fresh_state(hunger=100, mood=100, energy=100)
        one_zero = fresh_state(hunger=0, mood=100, energy=100)
        two_zero = fresh_state(hunger=0, mood=0, energy=100)
        three_zero = fresh_state(hunger=0, mood=0, energy=0)

        self.assertAlmostEqual(
            progression.passive_affection_per_minute(healthy), 0.60
        )
        self.assertAlmostEqual(
            progression.passive_affection_per_minute(one_zero), 0.30
        )
        self.assertAlmostEqual(
            progression.passive_affection_per_minute(two_zero), 0.15
        )
        self.assertAlmostEqual(
            progression.passive_affection_per_minute(three_zero), 0.075
        )

    def test_zero_attributes_map_to_restoring_interactions(self):
        healthy = fresh_state(hunger=10, mood=10, energy=10)
        hungry = fresh_state(hunger=0, mood=10, energy=10)
        unhappy = fresh_state(hunger=10, mood=0, energy=10)
        tired = fresh_state(hunger=10, mood=10, energy=0)

        self.assertEqual(progression.zero_stat_interaction_actions(healthy), set())
        self.assertEqual(
            progression.zero_stat_interaction_actions(hungry), {"feedings"}
        )
        self.assertEqual(
            progression.zero_stat_interaction_actions(unhappy),
            {"pettings", "feedings", "play_sessions"},
        )
        self.assertEqual(
            progression.zero_stat_interaction_actions(tired), {"manual_sleeps"}
        )

    def test_interaction_affection_balance_matches_design(self):
        self.assertEqual(
            progression.AFFECTION_ACTION_GAINS,
            {
                "pettings": 1,
                "feedings": 4,
                "play_sessions": 5,
                "fetch_catches": 2,
                "ai_replies": 1,
                "wake_shakes": 1,
                "manual_sleeps": 3,
            },
        )
        self.assertEqual(
            progression.AFFECTION_ACTION_COOLDOWNS,
            {
                "pettings": 60,
                "feedings": 8 * 60,
                "play_sessions": 6 * 60,
                "fetch_catches": 5 * 60,
                "ai_replies": 3 * 60,
                "wake_shakes": 5 * 60,
                "manual_sleeps": 15 * 60,
            },
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
        self.assertEqual(common["amount"], 20)
        self.assertEqual(jackpot["amount"], 200)

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

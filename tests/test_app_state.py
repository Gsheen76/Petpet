import unittest

from petpet.app import state as app_state
from petpet.app.state import (
    STATE_SCHEMA_VERSION,
    ensure_state_schema,
    prepare_state_for_save,
)


def normalize_name(value):
    return str(value or "").strip()[:6] or "Sheen"


class DualPetStateMigrationTests(unittest.TestCase):
    def legacy_state(self):
        return {
            "born": 100.0,
            "level": 8,
            "xp": 1172,
            "pet_coins": 63,
            "claimed_achievements": ["days_3"],
            "owned_decorations": ["red_collar"],
            "pet_name": "团子",
            "hunger": 72,
            "mood": 81,
            "energy": 66,
            "affection_level": 4,
            "affection_points": 19,
            "passive_affection_buffer": 0.4,
            "affection_last_gains": {"pettings": 120.0},
            "sleeping": False,
            "sleep_mode": None,
            "x": 240,
            "y": 510,
            "equipped_decorations": {"neck": "red_collar"},
            "decoration_adjustments": {
                "red_collar": {"x": 0.5, "y": 0.56}
            },
        }

    def test_legacy_state_is_copied_into_player_and_active_pet_profile(self):
        state = self.legacy_state()

        result = ensure_state_schema(state, "Sheen", normalize_name)

        self.assertIs(result, state)
        self.assertEqual(state["state_schema_version"], STATE_SCHEMA_VERSION)
        self.assertEqual(state["active_pet_id"], "lunch_meat")
        self.assertEqual(state["owned_pet_ids"], ["lunch_meat"])
        self.assertEqual(state["player"]["level"], 8)
        self.assertEqual(state["player"]["xp"], 1172)
        self.assertEqual(state["player"]["pet_coins"], 63)
        self.assertEqual(state["pets"]["lunch_meat"]["pet_name"], "团子")
        self.assertEqual(state["pets"]["lunch_meat"]["hunger"], 72)
        self.assertNotIn("desktop", state["pets"])
        self.assertNotIn("home", state["pets"])

    def test_repeated_migration_preserves_active_pet_values(self):
        state = self.legacy_state()
        ensure_state_schema(state, "Sheen", normalize_name)
        state["pets"]["lunch_meat"]["pet_name"] = "豆包"
        state["pets"]["lunch_meat"]["hunger"] = 23
        state["pet_name"] = "桌桌"
        state["hunger"] = 94

        ensure_state_schema(state, "Sheen", normalize_name)

        self.assertEqual(state["pets"]["lunch_meat"]["pet_name"], "豆包")
        self.assertEqual(state["pets"]["lunch_meat"]["hunger"], 23)
        self.assertEqual(state["pet_name"], "豆包")
        self.assertEqual(state["hunger"], 23)

    def test_save_preparation_updates_player_and_active_pet_only(self):
        state = self.legacy_state()
        ensure_state_schema(state, "Sheen", normalize_name)
        state["pets"]["ice_cream"] = {"pet_name": "豆包", "mood": 31}
        state["level"] = 9
        state["pet_coins"] = 77
        state["pet_name"] = "桌桌"
        state["mood"] = 92

        result = prepare_state_for_save(state)

        self.assertIs(result, state)
        self.assertEqual(state["player"]["level"], 9)
        self.assertEqual(state["player"]["pet_coins"], 77)
        self.assertEqual(state["pets"]["lunch_meat"]["pet_name"], "桌桌")
        self.assertEqual(state["pets"]["lunch_meat"]["mood"], 92)
        self.assertEqual(state["pets"]["ice_cream"]["pet_name"], "豆包")
        self.assertEqual(state["pets"]["ice_cream"]["mood"], 31)

    def test_legacy_desktop_home_profiles_migrate_to_lunch_meat(self):
        state = ensure_state_schema(
            {"pet_name": "小肉", "hunger": 12, "pets": {
                "desktop": {"pet_name": "小肉", "hunger": 12},
                "home": {"pet_name": "旧家园", "hunger": 88},
            }},
            "午餐肉",
            lambda value: str(value or "午餐肉"),
        )

        self.assertEqual(state["active_pet_id"], "lunch_meat")
        self.assertEqual(state["pets"]["lunch_meat"]["pet_name"], "小肉")
        self.assertEqual(state["pets"]["lunch_meat"]["hunger"], 12)

    def test_switch_keeps_player_data_and_isolates_pet_data(self):
        state = ensure_state_schema(
            {},
            "午餐肉",
            lambda value: str(value or "午餐肉"),
        )
        state["player"]["pet_coins"] = 100
        state["pets"]["ice_cream"] = {
            "pet_name": "冰淇淋",
            "hunger": 80,
            "mood": 70,
            "energy": 90,
            "affection_level": 1,
            "affection_points": 0,
            "passive_affection_buffer": 0.0,
            "affection_last_gains": {},
            "sleeping": False,
            "sleep_mode": None,
            "x": None,
            "y": None,
            "equipped_decorations": {},
            "decoration_adjustments": {},
        }
        state["pets"]["lunch_meat"]["hunger"] = 20

        app_state.bind_active_pet(state, "ice_cream")
        state["hunger"] = 90
        app_state.capture_active_pet(state)

        self.assertEqual(state["player"]["pet_coins"], 100)
        self.assertEqual(state["pets"]["lunch_meat"]["hunger"], 20)
        self.assertEqual(state["pets"]["ice_cream"]["hunger"], 90)

    def test_new_pet_runtime_fields_default_to_nullable_values(self):
        profile = app_state.pet_profile(
            ensure_state_schema(
                {}, "午餐肉", lambda value: str(value or "午餐肉")
            ),
            "ice_cream",
        )

        self.assertIsNone(profile["desktop_position"])
        self.assertIsNone(profile["home_position"])
        self.assertIsNone(profile["chat_memory_key"])
        self.assertIsNone(profile["equipped_outfit"])

    def test_switch_preserves_shared_top_level_facade_mutations(self):
        state = ensure_state_schema(
            {}, "午餐肉", lambda value: str(value or "午餐肉")
        )
        state["pet_coins"] = 100
        state["level"] = 4
        state["xp"] = 321

        app_state.bind_active_pet(state, "ice_cream")

        self.assertEqual(state["player"]["pet_coins"], 100)
        self.assertEqual(state["player"]["level"], 4)
        self.assertEqual(state["player"]["xp"], 321)
        self.assertEqual(state["pet_coins"], 100)
        self.assertEqual(state["level"], 4)
        self.assertEqual(state["xp"], 321)

    def test_new_profile_uses_schema_default_pet_name(self):
        state = ensure_state_schema(
            {}, "午餐肉", lambda value: str(value or "午餐肉")
        )

        self.assertEqual(
            app_state.pet_profile(state, "ice_cream")["pet_name"],
            "午餐肉",
        )


if __name__ == "__main__":
    unittest.main()

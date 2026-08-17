import unittest

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

    def test_legacy_state_is_copied_into_player_and_two_independent_pets(self):
        state = self.legacy_state()

        result = ensure_state_schema(state, "Sheen", normalize_name)

        self.assertIs(result, state)
        self.assertEqual(state["state_schema_version"], STATE_SCHEMA_VERSION)
        self.assertEqual(state["player"]["level"], 8)
        self.assertEqual(state["player"]["xp"], 1172)
        self.assertEqual(state["player"]["pet_coins"], 63)
        self.assertEqual(state["pets"]["desktop"]["pet_name"], "团子")
        self.assertEqual(state["pets"]["home"]["pet_name"], "团子")
        self.assertEqual(state["pets"]["home"]["hunger"], 72)
        self.assertIsNot(
            state["pets"]["desktop"], state["pets"]["home"]
        )
        self.assertIsNot(
            state["pets"]["desktop"]["affection_last_gains"],
            state["pets"]["home"]["affection_last_gains"],
        )
        self.assertIsNot(
            state["pets"]["desktop"]["equipped_decorations"],
            state["pets"]["home"]["equipped_decorations"],
        )

    def test_repeated_migration_preserves_newer_home_pet_values(self):
        state = self.legacy_state()
        ensure_state_schema(state, "Sheen", normalize_name)
        state["pets"]["home"]["pet_name"] = "豆包"
        state["pets"]["home"]["hunger"] = 23
        state["pet_name"] = "桌桌"
        state["hunger"] = 94

        ensure_state_schema(state, "Sheen", normalize_name)

        self.assertEqual(state["pets"]["home"]["pet_name"], "豆包")
        self.assertEqual(state["pets"]["home"]["hunger"], 23)
        self.assertEqual(state["pet_name"], "团子")
        self.assertEqual(state["hunger"], 72)

    def test_save_preparation_updates_player_and_desktop_only(self):
        state = self.legacy_state()
        ensure_state_schema(state, "Sheen", normalize_name)
        state["pets"]["home"]["pet_name"] = "豆包"
        state["pets"]["home"]["mood"] = 31
        state["level"] = 9
        state["pet_coins"] = 77
        state["pet_name"] = "桌桌"
        state["mood"] = 92

        result = prepare_state_for_save(state)

        self.assertIs(result, state)
        self.assertEqual(state["player"]["level"], 9)
        self.assertEqual(state["player"]["pet_coins"], 77)
        self.assertEqual(state["pets"]["desktop"]["pet_name"], "桌桌")
        self.assertEqual(state["pets"]["desktop"]["mood"], 92)
        self.assertEqual(state["pets"]["home"]["pet_name"], "豆包")
        self.assertEqual(state["pets"]["home"]["mood"], 31)


if __name__ == "__main__":
    unittest.main()

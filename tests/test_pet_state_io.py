import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pet


class PetStateIoTests(unittest.TestCase):
    def test_legacy_save_round_trip_preserves_stable_pet_profiles(self):
        with tempfile.TemporaryDirectory() as folder:
            save_path = Path(folder) / "pet_state.json"
            save_path.write_text(
                json.dumps(
                    {
                        "level": 7,
                        "xp": 321,
                        "pet_coins": 45,
                        "pet_name": "旧名字",
                        "hunger": 64,
                        "mood": 73,
                        "energy": 82,
                        "affection_level": 3,
                        "affection_points": 11,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(pet, "SAVE_PATH", str(save_path)):
                state = pet.load_state()
                self.assertEqual(state["player"]["level"], 7)
                self.assertEqual(state["active_pet_id"], "lunch_meat")
                self.assertEqual(
                    state["pets"]["lunch_meat"]["pet_name"], "旧名字"
                )

                state["level"] = 8
                state["pet_name"] = "桌桌"
                state["pets"]["ice_cream"] = {
                    "pet_name": "豆包", "hunger": 24
                }
                pet.save_state(state)

            saved = json.loads(save_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["player"]["level"], 8)
            self.assertEqual(saved["pets"]["lunch_meat"]["pet_name"], "桌桌")
            self.assertEqual(saved["pets"]["ice_cream"]["pet_name"], "豆包")
            self.assertEqual(saved["pets"]["ice_cream"]["hunger"], 24)


if __name__ == "__main__":
    unittest.main()

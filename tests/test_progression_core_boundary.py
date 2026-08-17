import unittest


class ProgressionCoreBoundaryTests(unittest.TestCase):
    def test_root_progression_reexports_package_core(self):
        import progression
        from petpet.progression import core

        self.assertIs(progression.ensure_progression, core.ensure_progression)
        self.assertIs(progression.record_action, core.record_action)
        self.assertIs(progression.achievement_catalog, core.achievement_catalog)

    def test_runtime_tuning_updates_packaged_rules(self):
        import progression
        from petpet.progression import core

        original = core.DIG_DISCOVERY_CHANCE
        try:
            progression.DIG_DISCOVERY_CHANCE = 0.37
            self.assertEqual(core.DIG_DISCOVERY_CHANCE, 0.37)
        finally:
            progression.DIG_DISCOVERY_CHANCE = original


if __name__ == "__main__":
    unittest.main()

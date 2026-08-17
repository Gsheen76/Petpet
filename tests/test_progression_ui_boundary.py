import progression_ui

from petpet.progression import ui


def test_root_progression_ui_is_a_compatibility_facade():
    assert progression_ui.CozyProgressWindow is ui.CozyProgressWindow
    assert progression_ui.RecordsWindow is ui.RecordsWindow
    assert progression_ui.AchievementsWindow is ui.AchievementsWindow
    assert progression_ui.ShopWindow is ui.ShopWindow


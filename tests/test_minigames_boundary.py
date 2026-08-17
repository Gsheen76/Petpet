import minigames

from petpet.minigames import ui


def test_root_minigames_is_a_compatibility_facade():
    assert minigames.CoinCatchCanvas is ui.CoinCatchCanvas
    assert minigames.CoinCatchGameWindow is ui.CoinCatchGameWindow
    assert minigames.LuckyPawsGameWindow is ui.LuckyPawsGameWindow
    assert minigames.MiniGameHubWindow is ui.MiniGameHubWindow


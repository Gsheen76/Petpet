"""宠物风格切换:家园接线与新装套装门控测试(2026-10-21 风格切换轮)。"""

from petpet.app import pet_window as pw
from petpet.app.pet_window import PetWindow
from petpet.home.window import HomeSceneWindow


def _home_shell(state):
    window = HomeSceneWindow.__new__(HomeSceneWindow)
    window.state = state
    return window


def _pet_shell(state):
    window = PetWindow.__new__(PetWindow)
    window.state = state
    window._current_pet_id = "lunch_meat"
    return window


def _outfitted_state(style):
    return {
        "active_pet_id": "lunch_meat",
        "owned_outfits": ["dinosaur_suit"],
        "equipped_outfit": "dinosaur_suit",
        "pets": {"lunch_meat": {"style": style}} if style else {},
    }


def test_home_signature_includes_style():
    window = _home_shell({"active_pet_id": "lunch_meat"})
    classic_sig = window._pet_assets_signature_tuple(None)
    window.state["pets"] = {"lunch_meat": {"style": "new"}}
    new_sig = window._pet_assets_signature_tuple(None)
    assert classic_sig != new_sig
    assert new_sig[-1] == "new"
    assert classic_sig[-1] == "classic"


def test_home_effective_outfit_gated_by_style():
    window = _home_shell(_outfitted_state("new"))
    assert window._effective_outfit("classic") == "dinosaur_suit"
    assert window._effective_outfit("new") == ""
    # 单风格宠物(None)套装照常
    assert window._effective_outfit(None) == "dinosaur_suit"


def test_outfit_action_variant_none_in_new_style():
    window = _pet_shell(_outfitted_state("new"))
    window.animation_frames = {"pet_dinosaur": object()}
    window._animation_frame_paths = {"pet_dinosaur": ["x"]}
    assert window._outfit_action_variant("pet") is None


def test_outfit_action_variant_kept_in_classic_style():
    window = _pet_shell(_outfitted_state("classic"))
    window.animation_frames = {"pet_dinosaur": object()}
    window._animation_frame_paths = {"pet_dinosaur": ["x"]}
    assert window._outfit_action_variant("pet") == "pet_dinosaur"


def test_outfit_drag_preview_none_in_new_style():
    window = _pet_shell(_outfitted_state("new"))
    window._outfit_preview_cache = {"dinosaur_suit": object()}
    assert window._equipped_outfit_preview() is None


def test_outfit_drag_preview_kept_in_classic_style():
    window = _pet_shell(_outfitted_state("classic"))
    marker = object()
    window._outfit_preview_cache = {"dinosaur_suit": marker}
    assert window._equipped_outfit_preview() is marker

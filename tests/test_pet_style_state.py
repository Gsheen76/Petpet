"""宠物风格切换:存档风格字段写入测试(2026-10-21 风格切换轮)。"""

import pytest

from petpet.app.state import set_pet_style
from tests.test_pet_style_registry import build_styled_registry


@pytest.fixture
def styled_registry(tmp_path, monkeypatch):
    return build_styled_registry(tmp_path, monkeypatch)


def test_set_pet_style_writes_profile(styled_registry):
    state = {"pets": {}}
    profile = set_pet_style(state, "dog", "classic")
    assert state["pets"]["dog"]["style"] == "classic"
    assert profile["style"] == "classic"


def test_set_pet_style_rejects_unknown(styled_registry):
    with pytest.raises(ValueError):
        set_pet_style({"pets": {}}, "dog", "bogus")


def test_set_pet_style_single_style_noop(styled_registry):
    state = {"pets": {}}
    set_pet_style(state, "lunch_meat", "new")
    assert "style" not in state["pets"].get("lunch_meat", {})

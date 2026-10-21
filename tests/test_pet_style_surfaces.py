"""宠物风格切换:聊天头像/教程预览的风格解析测试(2026-10-21 风格切换轮)。"""

from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QApplication

from petpet.ui import chat as chat_module
from petpet.ui import tutorial as tutorial_module


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _chat_shell(state):
    window = chat_module.ChatWindow.__new__(chat_module.ChatWindow)
    window.pet_id = "lunch_meat"
    window.pet = SimpleNamespace(state=state)
    return window


def test_chat_avatar_follows_style(qapp):
    window = _chat_shell({"pets": {"lunch_meat": {"style": "classic"}}})
    _pixmap, source_classic = window._avatar_pixmap("assistant")
    window.pet = SimpleNamespace(state={"pets": {"lunch_meat": {"style": "new"}}})
    _pixmap, source_new = window._avatar_pixmap("assistant")
    assert "desktop_new" not in source_classic.replace("/", "\\")
    assert "desktop_new" in source_new.replace("/", "\\")


def test_tutorial_idle_dir_follows_style():
    classic_dir = tutorial_module._pet_idle_frames_dir(
        "lunch_meat", {"pets": {"lunch_meat": {"style": "classic"}}})
    new_dir = tutorial_module._pet_idle_frames_dir(
        "lunch_meat", {"pets": {"lunch_meat": {"style": "new"}}})
    assert "desktop_new" not in str(classic_dir)
    assert "desktop_new" in str(new_dir)
    single_dir = tutorial_module._pet_idle_frames_dir("marshmallow", {})
    assert "desktop_new" not in str(single_dir)

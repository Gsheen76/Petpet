# -*- coding: utf-8 -*-
"""SANDBOX 探针(2026-10-31 按钮批产轮):真平台截图验收功能专属水彩皮肤。

铁律(2026-10-26 存档覆盖事故):LOCALAPPDATA 必须先指到临时目录,再 import
任何应用模块——裸探针构造真 PetWindow 曾把空档写进真实玩家数据。
运行: python assets/source/meowa/button-skins-2026-10-31/probe_skins.py
"""
import os
import tempfile

os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="petpet_skinprobe_")

import sys  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)

from PyQt5.QtWidgets import QApplication, QPushButton  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "review")

app = QApplication(sys.argv)

from unittest.mock import Mock  # noqa: E402
from PyQt5.QtCore import QPoint, QRect  # noqa: E402

from petpet.progression import core as progression  # noqa: E402
from petpet.progression.ui import (  # noqa: E402
    AchievementsWindow, DailyWindow, ShopWindow)
from petpet.minigames.ui import (  # noqa: E402
    CoinCatchGameWindow, LuckyPawsGameWindow, MiniGameHubWindow)
from petpet.ui.pet_profile import PetProfileWindow  # noqa: E402
import pet  # noqa: E402


class FakePet:
    def __init__(self):
        self.settings = dict(pet.DEFAULT_SETTINGS)
        self.state = progression.ensure_progression({})
        self.state["coins"] = 5000
        progression.purchase_pet(self.state, "ice_cream")
        progression.purchase_pet(self.state, "marshmallow")

    @property
    def pet_name(self):
        return "summer"

    def current_screen_rect(self):
        return QApplication.primaryScreen().availableGeometry()

    def geometry(self):
        return QRect(900, 600, 190, 220)

    def interface_window_position(self):
        return QPoint(700, 180)

    def say(self, *_a, **_k):
        pass

    def update(self, *_a, **_k):
        pass

    def trigger_animation(self, *_a, **_k):
        pass


def grab(window, name):
    app.processEvents()
    pm = window.grab()
    path = os.path.join(OUT, name)
    pm.save(path)
    print("saved", name, pm.width(), "x", pm.height())


petobj = FakePet()
save = lambda state: None  # noqa: E731

windows = []
try:
    w = DailyWindow(petobj, save); windows.append(w)
    w.refresh(); grab(w, "p_daily.jpg")
    w = AchievementsWindow(petobj, save); windows.append(w)
    w.refresh(); grab(w, "p_achievements.jpg")
    w = MiniGameHubWindow(petobj, save); windows.append(w)
    w.refresh(); grab(w, "p_hub.jpg")
    w = CoinCatchGameWindow(petobj, save); windows.append(w)
    grab(w, "p_coin.jpg")
    w = LuckyPawsGameWindow(petobj, save); windows.append(w)
    grab(w, "p_paws.jpg")
    w = pet.SettingsWindow(FakePet()); windows.append(w); grab(w, "p_settings.jpg")
    w = pet.ChatWindow(FakePet()); windows.append(w); grab(w, "p_chat.jpg")
    w = ShopWindow(petobj, save); windows.append(w)
    w.refresh(); grab(w, "p_shop.jpg")
    w = PetProfileWindow(petobj, save_state=save); windows.append(w)
    grab(w, "p_profile.jpg")
    # 皮肤名点验:每日窗应有 skinClaim/skinCheckin
    daily = windows[0]
    names = {b.objectName() for b in daily.findChildren(QPushButton)}
    print("daily skin buttons:", sorted(n for n in names if n.startswith("skin")))
finally:
    sys.stdout.flush()
    os._exit(0)

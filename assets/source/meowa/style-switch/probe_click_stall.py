# -*- coding: utf-8 -*-
"""点击链取证探针:双响与卡顿根因测量(真实平台)。
量:①每次 play_click 调用时刻+调用方 ②事件循环最大滞后 ③load_settings
每次磁盘读耗时 ④重动作(切宠/切页)单击全程 wall。"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer
from PyQt5.QtTest import QTest

from petpet.app import sounds
from petpet.app import settings as settings_mod

PLAY_LOG = []
_orig_play = sounds.play_click


def probe_play():
    import inspect
    caller = ''
    for fr in inspect.stack()[1:6]:
        f = os.path.basename(fr.filename)
        if f not in ('sounds.py', '__init__.py'):
            caller = f'{f}:{fr.lineno}'
            break
    PLAY_LOG.append((time.monotonic(), caller))
    _orig_play()


sounds.play_click = probe_play
# pet_profile 内部 import 方式:from petpet.progression.ui import FeedbackButton→
# FeedbackButton._play_click 内 from petpet.app.sounds import play_click(调用时
# 再取)→monkeypatch 生效。

SETT_LOG = []
_orig_ls = settings_mod.load_settings


def probe_ls(path=None):
    t0 = time.perf_counter()
    r = _orig_ls() if path is None else _orig_ls(path)
    SETT_LOG.append((time.perf_counter() - t0) * 1000)
    return r


settings_mod.load_settings = probe_ls
sounds.load_settings = probe_ls  # sounds 里 from-import 绑定也换掉

app = QApplication([])
import pet  # noqa: E402 依赖注入
from petpet.app.state import ensure_state_schema
from petpet.app.pet_window import PetWindow

state = ensure_state_schema({}, "Probe", str)
window = PetWindow(state)

# 事件循环滞后监测:1ms 心跳测最大断档
lag = {"max": 0.0, "last": time.monotonic()}


def heartbeat():
    now = time.monotonic()
    gap = now - lag["last"]
    if gap > lag["max"]:
        lag["max"] = gap
    lag["last"] = now


hb = QTimer()
hb.timeout.connect(heartbeat)
hb.start(1)

from petpet.ui.pet_profile import PetProfileWindow  # noqa: E402

panel = PetProfileWindow(window, save_state=lambda s: None)
panel.resize(850, 960)
panel.show()
app.processEvents()

results = []


def click_seq(widget, label, n=3, refetch=None):
    t0 = time.perf_counter()
    for _ in range(n):
        w = refetch() if refetch else widget
        QTest.mouseClick(w, Qt.LeftButton, pos=w.rect().center())
        app.processEvents()
        QTest.qWait(30)
    results.append((label, (time.perf_counter() - t0) / n * 1000))


# 1) 画风胶囊(切宠风格事务=重路径)
chip_new = panel._style_chips.get("new")
chip_cls = panel._style_chips.get("classic")
def get_chip(key):
    return panel._style_chips.get(key)

if get_chip("new") and get_chip("classic"):
    click_seq(None, "画风胶囊(经典)", 2, refetch=lambda: get_chip("classic"))
    click_seq(None, "画风胶囊(新装)", 2, refetch=lambda: get_chip("new"))

# 2) 面板页签(套装页构建)
from PyQt5.QtWidgets import QPushButton, QAbstractButton
tabs = [b for b in panel.findChildren(QAbstractButton)]
intro_tab = None
for b in tabs:
    if b.text() in ("简介", "套装", "礼物"):
        results.append(("tab候选", b.text()))
        break
if tabs:
    click_seq(tabs[0], f"面板按钮({tabs[0].text()[:6]})", 2)

# 3) 侧栏头像(切查看对象→预览帧加载)
from petpet.ui.pet_profile import _AvatarButton
avatars = panel.findChildren(_AvatarButton)
if len(avatars) >= 2:
    click_seq(avatars[1], "头像切换(冰淇淋)", 2)
    click_seq(avatars[0], "头像切换(回午餐肉)", 2)

# 双响分析:同一次逻辑点击的两次播音间隔
gaps = []
for i in range(1, len(PLAY_LOG)):
    dt = (PLAY_LOG[i][0] - PLAY_LOG[i - 1][0]) * 1000
    gaps.append((round(dt, 1), PLAY_LOG[i - 1][1], PLAY_LOG[i][1]))
double_candidates = [g for g in gaps if 55 < g[0] < 400]

print("== 播音调用总数:", len(PLAY_LOG))
print("== >55ms 间隔对(双响候选):", double_candidates[:6])
print("== 事件循环最大滞后: %.1f ms" % (lag["max"] * 1000))
if SETT_LOG:
    SETT_LOG.sort()
    print("== load_settings 次数 %d | p50 %.2fms p95 %.2fms max %.2fms" % (
        len(SETT_LOG), SETT_LOG[len(SETT_LOG) // 2],
        SETT_LOG[int(len(SETT_LOG) * 0.95)], SETT_LOG[-1]))
for label, ms in results:
    if isinstance(ms, float):
        print("== 单击均耗 %-22s %7.1f ms" % (label, ms))
window.close()
panel.close()

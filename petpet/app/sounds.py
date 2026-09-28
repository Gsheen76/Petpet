# -*- coding: utf-8 -*-
"""统一点击音（2026-09-28 用户定稿）：**所有**可点击按键在触发时播
``click.wav``——含分栏/页签等 checkable 键（同日三轮用户明确：
「包括分栏的按键」）。

**播放通道（2026-09-28 晚终版）**：QSoundEffect **单实例**——
出声延迟最低（WASAPI 直通）。三个历史坑位的结构性规避：
- 「播放中再 play()=restart」有 ~300ms 同步段 → **节流 40ms >
  音效时长 35ms**：轮到下次播放时上一次必然已自然结束，数学上
  永不进 restart 路径（人手最快连点 ~60-80ms 间隔，40ms 节流
  不吞正常点击）；
- 多实例在本机 WASAPI 每次 play ~500ms（实测灾难）→ 单实例；
- 静音预热不得在播放中解除（漏声）→ 预热 volume=0 播放、
  **音量只在真实播放前设**（winsound 因无此能力且 waveOut 有
  系统出声缓冲延迟（用户耳朵吃亏）已弃用）。

覆盖结构（40ms 节流去重防双响）：
- 各触发点显式调用（FeedbackButton 松开/家园键/贴图键/头像/
  气泡菜单）；
- ``install_click_sound_filter(app)``：**应用级事件过滤器**兜住
  其余一切按键——QAbstractButton（含 checkable 页签）、QTabBar、
  以及设了 PointingHandCursor 的自绘按键 widget，左键在键内
  松开即响（拖出键外不响）；
- 跟随设置项 ``sound_enabled``（读盘取值即时生效）。

坑位存档：
- ``app.paths`` 的 RESOURCE_DIR/SOURCE_DIR 是 **str**——路径只能
  ``os.path.join``；曾用 ``/`` 拼接抛 TypeError 被 except 吞掉、
  点击音整轮静默失效。
- 音效时长改动时必须同步评估节流值：**节流 > 音效时长**是单
  实例不撞 restart 的结构性保证。
"""
import os
import time

from petpet.app.paths import SOUNDS_DIR

CLICK_PATH = os.path.join(SOUNDS_DIR, "click.wav")
VOLUME = 0.30

_EFFECT = None  # None=未加载 | QSoundEffect | False=加载失败
_LAST_PLAY_TS = 0.0
_PLAY_THROTTLE_S = 0.040  # > 音效时长 35ms——见模块 docstring


def prewarm():
    """启动期预热（pet.py main 调用）：单实例 volume=0 播一次
    （设备接入完成，全程零出声），**不真实播放**。"""
    global _EFFECT
    if _EFFECT is None:
        try:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtMultimedia import QSoundEffect

            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(CLICK_PATH))
            effect.setVolume(0.0)
            effect.play()
            _EFFECT = effect
        except Exception:
            _EFFECT = False


def play_click():
    """播一次统一点击音（40ms 节流；设置关/通道失败时静默）。"""
    global _LAST_PLAY_TS
    now = time.monotonic()
    if now - _LAST_PLAY_TS < _PLAY_THROTTLE_S:
        return  # 同一次点击的多层命中只响一次（且上一次必然播完）
    try:
        from petpet.app.settings import load_settings

        if not load_settings().get("sound_enabled", True):
            return
    except Exception:
        pass  # 设置读不了也照播——宁可响，不可哑
    if _EFFECT is None:
        prewarm()
    if _EFFECT is False or _EFFECT is None:
        return
    _LAST_PLAY_TS = now
    try:
        # 预热后的实例音量为 0——真实播放前恢复（不在播放中解除
        # 静音，防漏声）；单实例+40ms 节流>音长=永不进 restart 段。
        _EFFECT.setVolume(VOLUME)
        _EFFECT.play()
    except RuntimeError:
        pass  # 音频后端已关（进程收尾等）


class ClickSoundFilter:
    """类级 eventFilter 工厂：应用级兜底点击音（2026-09-28 三轮）。

    覆盖非 FeedbackButton 体系的一切按键：QAbstractButton 全家
    （含 checkable 页签——用户明确要求分栏键也响）、QTabBar、
    设 PointingHandCursor 的自绘键 widget。左键、键内松开才响。
    """

    def __new__(cls, app):
        """安装到 app（幂等）；返回过滤器本体供测试直调。"""
        if getattr(app, "_petpet_click_sound_filter", None) is not None:
            return app._petpet_click_sound_filter

        from PyQt5.QtCore import QEvent, QObject, Qt
        from PyQt5.QtWidgets import QAbstractButton, QTabBar, QWidget

        class _Filter(QObject):
            def eventFilter(self, obj, event):
                try:
                    if (event.type() == QEvent.MouseButtonRelease
                            and event.button() == Qt.LeftButton
                            and isinstance(obj, QWidget)):
                        # 游戏画布等整幅手势光标区显式豁免
                        # （评审轮：金币雨/猜猜看连点画布曾被误响）。
                        if obj.property("petpetNoClickSound"):
                            return False
                        if (isinstance(obj, (QAbstractButton, QTabBar))
                                or obj.cursor().shape()
                                == Qt.PointingHandCursor):
                            if obj.rect().contains(event.pos()):
                                play_click()
                except Exception:
                    pass  # 音效兜底绝不拖垮事件分发
                return False

        filt = _Filter(app)
        app.installEventFilter(filt)
        app._petpet_click_sound_filter = filt
        return filt


def install_click_sound_filter(app):
    """应用级点击音过滤器（pet.py main 里安装一次）。"""
    return ClickSoundFilter(app)

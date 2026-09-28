# -*- coding: utf-8 -*-
"""统一点击音（2026-09-28 用户定稿）：**所有**可点击按键在触发时播
``click.wav``——含分栏/页签等 checkable 键（同日三轮用户明确：
「包括分栏的按键」）。

覆盖结构（三层，25ms 节流去重防双响）：
- 各触发点显式调用（FeedbackButton 松开/家园键/贴图键/头像/
  气泡菜单）；
- ``install_click_sound_filter(app)``：**应用级事件过滤器**兜住
  其余一切按键——QAbstractButton（QPushButton/QCheckBox/…含
  checkable 页签）、QTabBar、以及设了 PointingHandCursor 的
  自绘按键 widget，左键在键内松开即响（拖出键外不响）；
- 节流：同一次点击最多响一次（不同层同时命中/事件与显式调用
  同毫秒到达时只播首个）。

单例 QSoundEffect 懒加载（音量 0.35、静音预热防首次 ~600ms
卡顿）；跟随设置项 ``sound_enabled``（读盘取值即时生效）。
坑位存档：``app.paths`` 的 RESOURCE_DIR/SOURCE_DIR 是 **str**——
路径只能 ``os.path.join``；曾用 ``/`` 拼接抛 TypeError 被
``except Exception`` 吞成失败标记，点击音整轮静默失效。
"""
import os
import time

_EFFECT = None  # None=未加载 | QSoundEffect | False=加载失败
_LAST_PLAY_TS = 0.0
_PLAY_THROTTLE_S = 0.025


def play_click():
    """播一次统一点击音（25ms 节流；设置关/加载失败时静默）。"""
    global _EFFECT, _LAST_PLAY_TS
    now = time.monotonic()
    if now - _LAST_PLAY_TS < _PLAY_THROTTLE_S:
        return  # 同一次点击的多层命中只响一次
    try:
        from petpet.app.settings import load_settings

        if not load_settings().get("sound_enabled", True):
            return
    except Exception:
        pass  # 设置读不了也照播——宁可响，不可哑
    if _EFFECT is None:
        try:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtMultimedia import QSoundEffect

            from petpet.app.paths import SOUNDS_DIR

            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(
                os.path.join(SOUNDS_DIR, "click.wav")))
            effect.setVolume(0.35)
            effect.setMuted(True)  # 预热（首次播放 600ms 卡顿坑）
            effect.play()
            effect.setMuted(False)
            _EFFECT = effect
        except Exception:
            _EFFECT = False
            return
    if _EFFECT is False:
        return
    _LAST_PLAY_TS = now
    try:
        _EFFECT.stop()
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


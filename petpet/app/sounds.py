# -*- coding: utf-8 -*-
"""统一点击音（2026-09-28 用户定稿）：全应用可交互按键在回弹触发
瞬间播 ``click.wav``。

- 单例 QSoundEffect 懒加载（音量 0.35、静音预热防首次播放 ~600ms
  卡顿坑）；加载失败静默降级、不再重试。
- 跟随设置项 ``sound_enabled``（设置面板「互动音效」同一开关）；
  每次播放前读盘取值，改设置立即生效。checkable（页签/筛选）与
  禁用键不响——与 FeedbackButton 既有规则一致。
- 坑位存档：``app.paths`` 的 RESOURCE_DIR/SOURCE_DIR 是 **str**——
  路径只能 ``os.path.join``；曾用 ``/`` 拼接抛 TypeError 被
  ``except Exception`` 吞成失败标记，点击音整轮静默失效。
"""
import os

_EFFECT = None  # None=未加载 | QSoundEffect | False=加载失败


def play_click():
    """播一次统一点击音（设置关/加载失败时静默）。"""
    global _EFFECT
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
    try:
        _EFFECT.stop()
        _EFFECT.play()
    except RuntimeError:
        pass  # 音频后端已关（进程收尾等）

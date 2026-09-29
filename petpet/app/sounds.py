# -*- coding: utf-8 -*-
"""统一点击音（2026-09-28 用户定稿）：**所有**可点击按键在触发时播
``click.wav``——含分栏/页签等 checkable 键（同日三轮用户明确：
「包括分栏的按键」）。

**播放通道（2026-09-29 终版）**：Windows 用 **QAudioOutput 常开
推流**（欠载态 write 即播，出声 ~10ms——QSoundEffect 的 WASAPI
输出缓冲实测造成 ~500ms 出声滞后，用户「慢半秒」的根因；winsound
~150ms 作兜底；非 Windows 用 QSoundEffect 单实例）。此前版本：
QSoundEffect 单实例——
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
import atexit
import os
import sys
import time

from petpet.app.paths import SOUNDS_DIR

_IS_WINDOWS = sys.platform == "win32"

CLICK_PATH = os.path.join(SOUNDS_DIR, "click.wav")
VOLUME = 0.30

_PUSH = None       # None=未建 | dict(io, out, pcm) | False=不可用（兜底）
_QT_EFFECT = None  # 非 Windows 兜底单实例
_LAST_PLAY_TS = 0.0
_PLAY_THROTTLE_S = 0.040  # > 音效时长 35ms——上一次必然播完


def _load_click_pcm():
    """读 click.wav 为原始 PCM（音量预乘进样本——推流通道无设备
    音量旋钮参与）。"""
    import struct
    import wave

    with wave.open(CLICK_PATH, "rb") as w:
        rate = w.getframerate()
        channels = w.getnchannels()
        width = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width == 2:
        samples = struct.unpack(f"<{len(raw) // 2}h", raw)
        scaled = tuple(int(v * VOLUME) for v in samples)
        raw = struct.pack(f"<{len(scaled)}h", *scaled)
    return raw, rate, channels, width


def _shutdown_push_channel():
    """进程退出早期关推流通道（atexit 注册，早于 Qt teardown）。

    模块级 QAudioOutput/QIODevice 若活到解释器退出阶段，会在
    QApplication 已析构后再被 GC 析构 C++ 对象——pytest 全量收尾
    段错误（2026-09-29 实证：offscreen 下 start() 也返回真对象）。
    """
    global _PUSH
    push, _PUSH = _PUSH, None
    if isinstance(push, dict):
        out = push.get("out")
        try:
            out.stop()
        except Exception:
            pass
        # QApplication 尚存活的收尾钩子（pytest sessionfinish）里可
        # 显式销毁 C++ 对象；atexit 路径（解释器退出晚期）只断引用。
        try:
            from PyQt5 import sip

            if not sip.isdeleted(out):
                sip.delete(out)
        except Exception:
            pass


atexit.register(_shutdown_push_channel)


def _open_push_channel():
    """常开 QAudioOutput 推流（2026-09-29 终版通道）。

    QSoundEffect 在本机 WASAPI 后端的输出缓冲造成 ~500ms 出声滞后
    （API 返回快≠出声快）；推流通道平时欠载（缓冲空），点击时
    ``io.write(pcm)`` 直进播放头——出声延迟 ≈ 一个 WASAPI 周期
    （~10ms）。write 后自动进入 Active、播完回 Idle（原型实测
    15×write ≤1.4ms、状态机自动往返）。
    """
    from PyQt5.QtMultimedia import QAudioFormat, QAudioOutput

    raw, rate, channels, width = _load_click_pcm()
    fmt = QAudioFormat()
    fmt.setSampleRate(rate)
    fmt.setChannelCount(channels)
    fmt.setSampleType(QAudioFormat.SignedInt)
    fmt.setSampleSize(width * 8)
    fmt.setCodec("audio/pcm")
    out = QAudioOutput(fmt)
    out.setBufferSize(max(8192, len(raw) * 2))
    io = out.start()
    if io is None:
        return None
    return {"io": io, "out": out, "pcm": raw}


def prewarm():
    """启动期预热（pet.py main 调用）：开推流通道（付 WASAPI 打开
    成本，全程零出声）。失败置 False——play_click 走兜底链。"""
    global _PUSH
    if not _IS_WINDOWS or _PUSH is not None:
        return
    try:
        _PUSH = _open_push_channel()
    except Exception:
        _PUSH = None
    if _PUSH is None:
        _PUSH = False


def _winsound_fallback():
    if not _IS_WINDOWS:
        _qt_play()
        return
    import winsound

    try:
        winsound.PlaySound(
            CLICK_PATH,
            winsound.SND_FILENAME
            | winsound.SND_ASYNC
            | winsound.SND_NODEFAULT,
        )
    except Exception:
        pass


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
    _LAST_PLAY_TS = now
    if _IS_WINDOWS:
        if _PUSH is None:
            prewarm()
        if isinstance(_PUSH, dict):
            try:
                _PUSH["io"].write(_PUSH["pcm"])
                return
            except Exception:
                _winsound_fallback()
                return
    _qt_play()


def _qt_play():
    """非 Windows（或推流+winsound 均不可用）的 QSoundEffect 单实例。"""
    global _QT_EFFECT
    if _QT_EFFECT is None:
        try:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtMultimedia import QSoundEffect

            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(CLICK_PATH))
            effect.setVolume(VOLUME)
            _QT_EFFECT = effect
        except Exception:
            _QT_EFFECT = False
    if _QT_EFFECT is False or _QT_EFFECT is None:
        return
    try:
        _QT_EFFECT.play()
    except RuntimeError:
        pass


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

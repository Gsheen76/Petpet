"""宠物详情面板：数据快照纯函数 + 新素材面板（逐轮搭建）。

页面骨架：background 原生尺寸（显示比例 0.7）单层画布，整页圆角裁剪
（CORNER_RADIUS），无边框可拖拽（base_UI 图层已于第六轮撤下）。
内容区（第三轮）：左栏宠物切换卡、待机动画、名字牌+改名、等级/好感两行。
"""

from __future__ import annotations

import io
import json
import os

import numpy as np
from PIL import Image as PILImage
from PyQt5.QtCore import (QEasingCurve, QRect, QSize, Qt, QTimer,
                          pyqtSignal, QVariantAnimation)
from PyQt5.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import (QApplication, QGraphicsOpacityEffect,
                             QGridLayout, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QStackedWidget,
                             QVBoxLayout, QWidget)

from petpet.app.fonts import APP_FONT_FAMILY
from petpet.app.paths import GIFTS_UI_DIR
from petpet.app import pets as pet_registry
from petpet.app import state as app_state
from petpet.progression import core as progression
from petpet.progression.ui import PurchasePopup

_NAME_DIALOG_FACTORY = None

# 各宠物的头像框素材（图1 左栏卡；无素材的物种回退 avatar.png）。
SPECIES_RAIL_ICON = {"lunch_meat": "pet_icon_1.png", "ice_cream": "pet_icon_2.png"}

_ASSET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets", "runtime", "ui", "pet_profile_new",
)

# 页面布局坐标 = new_background.png 艺术稿像素（1085x1450，第十五轮原比例版）。
# 显示：与其他常驻面板统一 850x960——艺术稿按宽高各自比例非等比铺满；
# 小屏放不下时按等比因子整体收缩（下限 0.55），保持 850:960 比例。
ART_W, ART_H = 1085, 1450
UNIFIED_W, UNIFIED_H = 850, 960
_SX = UNIFIED_W / ART_W
_SY = UNIFIED_H / ART_H
_FIT = 1.0

# 整页圆角半径（用户定稿：逐轮加大，当前 64）。
CORNER_RADIUS = 64

# 右上关闭按钮（close_button.png 素材；花形钮位随新背景右上角）。
CLOSE_BUTTON_AT = (970, 44, 74, 67)
CLOSE_PRESS_FLASH_MS = 40
CLOSE_CLICK_DEFER_MS = 80

# 图1 左栏：宠物头像 rail（pet_avatar_rail，纯背景板无烘焙槽）+
# 程序布局双卡槽（坐标按参考图反推到 art 比例）。
RAIL_AT = (51, 230, 200, 992)
# 第七十二轮：左下角商店提示框（rail 下方）。
# 第七十二轮（改稿2）：左下角商店提示框——宽度与上方 rail 对齐
# （同 x/同宽），白色边框加粗，框内加「小tips」标题。
SHOP_TIP_AT = (56, 1238, 192, 113)   # 改稿7：累计右移 4px（改稿6 右1 + 本轮右3）、上移 15px
RAIL_TITLE_AT = (-2, 182, 320, 46)           # 「我的伙伴」（rail 正上方，加粗）
PET_CARD_SLOTS = ((76, 272), (76, 470))      # 每卡头像左上（烟花上移80、奶油上移200、右移10，显示px 换算）
PET_CARD_SIZE = (150, 150)
PET_CARD_NAME_AT = (-20, 156, 190, 36)       # 名字（相对卡，卡下，略宽于卡居中）
PET_CARD_TAG_AT = (12, 118, 142, 34)         # 使用中 pill（已按指示停用）

# 图2 待机动画：粉垫 x340-940 y430-570（虚线圆中心 ~640,360）。
IDLE_PREVIEW_RECT = (415, 140, 450, 430)
IDLE_FRAME_HEIGHT = 410
IDLE_FPS = 8

# 图3 名字牌（rename_bg 323x63）+ 改名钮（change_name 94x55）：
# 垫正下方居中，两素材均放大 50%（第十五轮后续）；改名钮放牌内右端。
NAME_PLATE_AT = (466, 578, 360, 70)   # 第七十二轮B：下移 5 显示px（+8 art）
# 名字在牌内部整体居中（第二十六轮）：可用区 = 牌宽 - 钮宽 - 边距，居中放。
NAME_ART_AT = (478, 581, 220, 64)   # 居中于牌内可用区（左缘~按钮左缘）
RENAME_BUTTON_AT = (700, 581, 113, 66)   # 原生 94x55 × 1.2 等比（不被压扁）

# 分栏（第三十七轮）：参考图裁切的两枚素材按钮（简介/套装），
# 附着在内容背景图上方；选中态用另一枚按钮互换表示。
TAB_SLOTS = {
    "简介": "tab_intro.png",
    "套装": "tab_outfit.png",
    "礼物": "tab_gift.png",
}
TAB_BAR_AT = (264, 723, 758, 130)
CONTENT_AT = (264, 737, 758, 614)   # 第六十六轮：整块下移 5 显示px（+8 art）

# 套装素材（新 art 直接按套装 id 映射；未映射回退 idle 预览路径）。
OUTFIT_ART = {
    "strawberry_suit": "outfit_strawberry.png",
    "dinosaur_suit": "outfit_dinosaur.png",
}
OUTFIT_CARD_SIZE = (620, 400)

# 套装装备按钮素材（绿=恐龙、橘=草莓，第十一轮）。
OUTFIT_EQUIP_BUTTON = {
    "dinosaur_suit": "equip_button_green.png",
    "strawberry_suit": "equip_button_orange.png",
}

# 套装专属待机动画（manifest 动画键）：卡右侧播放穿上套装的小狗。
OUTFIT_IDLE_ANIM = {
    "dinosaur_suit": "idle_dinosaur",
    "strawberry_suit": "idle_strawberry",
}
OUTFIT_IDLE_HEIGHT = 160   # 第二十九轮：缩小 20%（200×0.8）


def _R(x, y, w, h):
    """艺术稿坐标 → 实际画布几何（横纵各自缩放铺满统一尺寸）。"""
    return QRect(round(x * _SX * _FIT), round(y * _SY * _FIT),
                 round(w * _SX * _FIT), round(h * _SY * _FIT))


def _resolve_scale(screen_rect) -> float:
    """小屏等比收缩因子：上限 1.0（即统一 850x960），下限 0.55。"""
    if screen_rect is None or screen_rect.width() <= 0:
        return 1.0
    by_h = (screen_rect.height() - 40) / UNIFIED_H
    by_w = (screen_rect.width() - 40) / UNIFIED_W
    return max(0.55, min(1.0, by_h, by_w))


def configure_name_dialog_factory(factory):
    """注入改名对话框类（定义在根模块 pet.py，包内不能直接 import）。"""
    global _NAME_DIALOG_FACTORY
    _NAME_DIALOG_FACTORY = factory


def _pp_asset(name):
    """素材绝对路径；不存在返回 None（单素材缺失不拖垮面板）。"""
    path = os.path.join(_ASSET_DIR, name)
    return path if os.path.isfile(path) else None


def _pp_pixmap(name, w=None, h=None):
    """按需缩放的素材位图；缺失时返回空位图。"""
    path = _pp_asset(name)
    pixmap = QPixmap(path) if path else QPixmap()
    if pixmap.isNull():
        return pixmap
    if w and h:
        pixmap = pixmap.scaled(round(w * _SX * _FIT), round(h * _SY * _FIT),
                               Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return pixmap


def pet_profile_snapshot(state: dict, pet_id: str) -> dict:
    """汇总一只宠物的展示数据；当前宠物读顶层 facade，其余读自身 profile。"""
    definition = pet_registry.pet_definition(pet_id)
    active_id = state.get("active_pet_id", pet_registry.DEFAULT_PET_ID)
    if pet_id == active_id:
        profile = state
    else:
        profile = app_state.pet_profile(state, pet_id)
    owned = (
        pet_id == active_id
        or pet_id in (state.get("owned_pet_ids") or ())
    )

    if pet_id == active_id:
        name = state.get("name") or state.get("pet_name")
        if not (isinstance(name, str) and name.strip()):
            name = definition.get("default_name", pet_id)
    elif owned:
        # 非当前宠物：schema 填充名（等于当前门面名）视为未改名，回退物种默认名。
        filler_name = app_state.default_pet_name(state)
        name = profile.get("name") or profile.get("pet_name")
        if (
            not (isinstance(name, str) and name.strip())
            or name == filler_name
        ):
            name = definition.get("default_name", pet_id)
    else:
        name = definition.get("default_name", pet_id)

    affection_level = int(profile.get("affection_level") or 1)
    affection_points = int(profile.get("affection_points") or 0)
    level = int(profile.get("level") or 1)
    owned_outfits = profile.get("owned_outfits") or []
    equipped_outfit = profile.get("equipped_outfit")

    outfits = []
    for outfit_id, outfit in progression.OUTFIT_DEFINITIONS.items():
        if outfit.get("pet_id") != pet_id:
            continue
        outfits.append({
            "id": outfit_id,
            "name": outfit.get("name", outfit_id),
            "icon": outfit.get("icon", ""),
            "price": int(outfit.get("price", 0)),
            "description": outfit.get("description", ""),
            "asset_folder": outfit.get("asset_folder", ""),
            "preview_asset": outfit.get("preview_asset", "preview.png"),
            "owned": outfit_id in owned_outfits,
            "equipped": equipped_outfit == outfit_id,
        })

    return {
        "id": pet_id,
        "name": name,
        "default_name": definition.get("default_name", pet_id),
        "description": definition.get("description", ""),
        "price": int(definition.get("price", 0) or 0),
        "owned": owned,
        "active": pet_id == active_id,
        "level": level,
        "xp": int(profile.get("xp") or 0),
        "xp_next": progression.xp_to_next(level),
        "affection_level": affection_level,
        "affection_points": affection_points,
        # 注意：传等级数（传字典会被 _safe_int 兜底成 1 → 上限恒 30）。
        "affection_next": progression.affection_to_next(affection_level),
        "avatar_path": pet_registry.pet_avatar_path(pet_id),
        "preview_path": pet_registry.pet_asset_path(pet_id, "desktop", "idle"),
        "hunger": int(profile.get("hunger") or 0),
        "mood": int(profile.get("mood") or 0),
        "energy": int(profile.get("energy") or 0),
        "outfits": outfits,
    }


def _outfit_preview_path(pet_id, outfit):
    """从桌面 idle 资产推导套装预览图的绝对路径（idle 是最终回退，必然存在）。"""
    idle = pet_registry.pet_asset_path(pet_id, "desktop", "idle")
    if not idle:
        return None
    desktop_dir = os.path.dirname(os.path.dirname(idle))
    candidate = os.path.join(
        desktop_dir, "outfits",
        outfit.get("asset_folder", ""),
        outfit.get("preview_asset", "preview.png"),
    )
    return candidate if os.path.isfile(candidate) else None


def _grayscale_pixmap(path):
    """灰阶化并保留 alpha（PIL+numpy 向量化；Format_Grayscale8 会把透明变黑）。"""
    if not path or not os.path.isfile(path):
        return QPixmap()
    try:
        img = PILImage.open(path).convert("RGBA")
        arr = np.asarray(img)
        gray = (
            0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        ).astype("uint8")
        out = np.dstack([gray, gray, gray, arr[:, :, 3]])
        buf = io.BytesIO()
        PILImage.fromarray(out, "RGBA").save(buf, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())
        return pixmap
    except Exception:
        return QPixmap(path)


_IDLE_FRAMES_CACHE = {}


def _load_idle_frames(pet_id, height, anim_key="idle"):
    """加载指定桌面动画全部帧（等高缩放）；带缓存，缺动画回退空列表。

    一次磁盘加载 ~124ms（16 帧），切换宠物/套装会反复取同一组帧——
    不缓存则每次 refresh 主线程冻结 250ms，按压反馈被冻在屏上。
    """
    cache_key = (pet_id, anim_key, round(height))
    if cache_key in _IDLE_FRAMES_CACHE:
        return _IDLE_FRAMES_CACHE[cache_key]
    folder = pet_registry.pet_asset_path(pet_id, "desktop", "idle")
    if not folder:
        return []
    desktop_dir = os.path.dirname(os.path.dirname(folder))
    manifest_path = os.path.join(
        desktop_dir, "animations", "manifest.json",
    )
    frames = []
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        anim = manifest.get(anim_key) or {}
        rel = anim.get("folder")
        if not rel:
            return frames
        frame_dir = os.path.join(desktop_dir, "animations", rel)
        names = sorted(
            name for name in os.listdir(frame_dir)
            if name.endswith(".png")
        )
        for name in names:
            pixmap = QPixmap(os.path.join(frame_dir, name))
            if not pixmap.isNull():
                frames.append(pixmap.scaledToHeight(
                    round(height * _SX * _FIT), Qt.SmoothTransformation,
                ))
    except (OSError, ValueError):
        pass
    _IDLE_FRAMES_CACHE[cache_key] = frames
    return frames


class _ArtTitle(QWidget):
    """宠物风格艺术字标题：粗体棕字 + 白描边 + 底部浅影（形似「宠物」牌匾字）。"""

    def __init__(self, text, parent=None, font_px=38):
        super().__init__(parent)
        self._text = text
        self._font_px = font_px
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def setText(self, text):
        self._text = text
        self.update()

    def text(self):
        return self._text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont(APP_FONT_FAMILY)
        font.setBold(True)
        font.setPixelSize(max(1, round(self._font_px * _SX * _FIT)))
        painter.setFont(font)
        # 底部浅影
        painter.setPen(QColor(240, 205, 170))
        painter.drawText(self.rect().adjusted(0, 3, 0, 3),
                         Qt.AlignCenter, self._text)
        # 白描边（多向偏移）
        painter.setPen(QColor(255, 252, 246))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2),
                       (-2, -2), (2, -2), (-2, 2), (2, 2)):
            painter.drawText(self.rect().adjusted(dx, dy, dx, dy),
                             Qt.AlignCenter, self._text)
        # 主体棕字
        painter.setPen(QColor("#9a5b3f"))
        painter.drawText(self.rect(), Qt.AlignCenter, self._text)


class _MiniBar(QWidget):
    """简介进度条（第三十六轮素材版）：progress_track/fill 贴图绘制；
    数值变化 450ms 缓动滑动 + 高光循环扫过（第三十五轮行为保留）。"""

    SWEEP_MS = 2400
    TICK_MS = 33

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._maximum = 1
        self._display_value = 0.0
        # 素材：空槽轨道 + 满填充（圆头含在素材里）。
        self._track_pm = _pp_pixmap("progress_track.png")
        self._fill_pm = _pp_pixmap("progress_fill.png")
        bar_h = max(10, round(26 * _FIT))
        self.setFixedHeight(bar_h)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)
        self._sweep_phase = 0.0
        self._sweep_timer = QTimer(self)
        self._sweep_timer.setInterval(self.TICK_MS)
        self._sweep_timer.timeout.connect(self._advance_sweep)
        self._sweep_timer.start()

    def _on_anim_value(self, v):
        self._display_value = float(v)
        self.update()

    def _advance_sweep(self):
        self._sweep_phase = (self._sweep_phase + self.TICK_MS / self.SWEEP_MS) % 1.0
        self.update()

    def set_ratio(self, value, maximum):
        self._value = max(0, int(value))
        self._maximum = max(1, int(maximum))
        target = max(0.0, min(1.0, self._value / self._maximum))
        self._anim.stop()
        self._anim.setStartValue(float(self._display_value))
        self._anim.setEndValue(target)
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # 轨道：空槽贴图拉满整宽（高度自适应）。
        if not self._track_pm.isNull():
            painter.drawPixmap(0, 0, w, h, self._track_pm)
        else:
            radius = h / 2
            track = QPainterPath()
            track.addRoundedRect(0, 0, w, h, radius, radius)
            painter.setPen(QPen(QColor(232, 197, 158), max(1, h // 16)))
            painter.setBrush(QColor("#f6ead8"))
            painter.drawPath(track)
        frac = max(0.0, min(1.0, self._display_value / self._maximum))
        if frac <= 0:
            return
        fill_w = max(int(w * frac), h)
        # 填充：满填充贴图按宽度裁剪（保留左侧圆头）。
        if not self._fill_pm.isNull():
            painter.drawPixmap(0, 0, fill_w, h, self._fill_pm, 0, 0,
                               max(1, int(self._fill_pm.width() * frac)), 0)
        else:
            radius = h / 2
            inset = max(1, h // 10)
            fill = QPainterPath()
            fill.addRoundedRect(inset, inset, fill_w - inset * 2, h - inset * 2,
                                radius - inset, radius - inset)
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0, QColor("#f9b39c"))
            grad.setColorAt(1, QColor("#ef8a70"))
            painter.setPen(Qt.NoPen)
            painter.setBrush(grad)
            painter.drawPath(fill)
        # 高光带：只在填充内扫过。
        band_w = max(24, int(w * 0.18))
        band_x = int((self._sweep_phase * (w + band_w * 2)) - band_w)
        if band_x + band_w > 0 and frac > 0.02:
            clip = QPainterPath()
            radius = h / 2
            clip.addRoundedRect(0, 0, fill_w, h, radius, radius)
            painter.setClipPath(clip)
            band_grad = QLinearGradient(band_x, 0, band_x + band_w, 0)
            band_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            band_grad.setColorAt(0.5, QColor(255, 255, 255, 110))
            band_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(band_grad)
            painter.drawRect(band_x, 0, band_w, h)


class _RoundedBgLabel(QWidget):
    """区域背景（第三十九轮）：素材按区域等比绘制并裁剪圆角。"""

    def __init__(self, parent=None, radius=28):
        super().__init__(parent)
        self._art = QPixmap()
        self._radius = radius
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_art(self, pixmap):
        self._art = pixmap if pixmap is not None and not pixmap.isNull() else QPixmap()
        self.update()

    def paintEvent(self, event):
        if self._art.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        radius = self._radius * _FIT
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, radius, radius)
        painter.setClipPath(clip)
        scaled = self._art.scaled(
            w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
        )
        painter.drawPixmap(
            (w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled,
        )
        # 纯白实线描边（第六十六轮）：外围 3px 粗。
        # 坑位：setClipPath(空路径) = 裁掉一切，描边整段消失；
        # 解除裁剪必须用 setClipping(False)。
        painter.setClipping(False)
        pen_w = 3
        painter.setPen(QPen(QColor("#ffffff"), pen_w))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(
            pen_w // 2, pen_w // 2, w - pen_w, h - pen_w, radius, radius,
        )


class _TabButton(QWidget):
    """素材分栏按钮（第三十七轮）：参考图裁切的「简介/套装」牌。
    悬停=放大+白洗；按住=缩小+压暗（alpha 60），松开在内才切换。"""

    clicked = pyqtSignal(str)

    def __init__(self, text, parent=None, art=None, headroom=0, side_margin=0):
        super().__init__(parent)
        self._text = text
        self._art = art if art is not None and not art.isNull() else QPixmap()
        self._hovered = False
        self._pressed = False
        self.checked = False
        # 第五十八轮：素材区上下的悬浮余量（显示px）。悬浮放大会向外扩
        # 2px，自绘只能在 widget 边界内作画——无余量时顶部被裁 ~5px。
        self._headroom = max(0, headroom)
        # 第六十三轮：左右悬浮余量。悬浮时 KeepAspectRatio 缩放会从
        # 高度受限翻转为宽度受限，素材横向涨幅（+4px）远超纵向，
        # 余量不足即左右截断（用户实测）。
        self._side_margin = max(0, side_margin)
        self.setCursor(Qt.PointingHandCursor)

    def setChecked(self, checked):
        self.checked = bool(checked)
        self.update()

    def set_art(self, art):
        self._art = art if art is not None and not art.isNull() else QPixmap()
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            if self.rect().contains(event.pos()):
                self.clicked.emit(self._text)
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # 素材区 = widget 去掉四周余量；悬浮放大从素材区向外扩，
        # 扩入余量带，不再触边裁切。
        rect = QRect(self._side_margin, self._headroom,
                     w - 2 * self._side_margin, h - 2 * self._headroom)
        if self._pressed:
            rect = rect.adjusted(3, 3, -3, -3)
        elif self._hovered:
            rect = rect.adjusted(-2, -2, 2, 2)
        if not self._art.isNull():
            scaled = self._art.scaled(
                rect.width(), rect.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            # 未选中透明度（第七十二轮B：0.65→0.55 再降一档）。
            if not (self.checked or self._hovered or self._pressed):
                painter.setOpacity(0.55)
            painter.drawPixmap(
                rect.x() + (rect.width() - scaled.width()) // 2,
                rect.y() + (rect.height() - scaled.height()) // 2,
                scaled,
            )
            painter.setOpacity(1.0)
        else:
            # 无素材回退：文字胶囊。
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#f5a48f"))
            painter.drawRoundedRect(rect, h / 2, h / 2)
            font = QFont(APP_FONT_FAMILY)
            font.setBold(True)
            font.setPixelSize(max(1, round(26 * _SX * _FIT)))
            painter.setFont(font)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(rect, Qt.AlignCenter, self._text)
        painter.setPen(Qt.NoPen)
        art_pos = QRect(
            rect.x() + (rect.width() - (scaled.width() if not self._art.isNull() else rect.width())) // 2,
            rect.y() + (rect.height() - (scaled.height() if not self._art.isNull() else rect.height())) // 2,
            (scaled.width() if not self._art.isNull() else rect.width()),
            (scaled.height() if not self._art.isNull() else rect.height()),
        )
        if self._pressed:
            painter.setBrush(QColor(70, 42, 28, 60))
            painter.drawRoundedRect(art_pos, 12, 12)
        elif self._hovered:
            painter.setBrush(QColor(255, 252, 246, 80))
            painter.drawRoundedRect(art_pos, 12, 12)


class _OutfitIdleLabel(QLabel):
    """套装卡右侧：穿上对应套装的小狗待机动画（8fps 循环）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._frames = []
        self._index = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self._advance)

    def set_frames(self, frames):
        self._frames = frames
        self._index = 0
        if frames:
            self.setPixmap(frames[0])
            self._timer.start(round(1000 / IDLE_FPS))
        else:
            self._timer.stop()
            self.setPixmap(QPixmap())

    def _advance(self):
        if not self._frames:
            return
        self._index = (self._index + 1) % len(self._frames)
        self.setPixmap(self._frames[self._index])


class _AvatarButton(QWidget):
    """宠物头像按钮：整幅绘制不裁切；悬停=圆角正方形珊瑚描边+白洗，
    按压=暗洗+描边（贴合素材的绝对圆角方形，不受 QSS padding 影响）。"""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._hovered = False
        self._pressed = False
        self.selected = False  # 当前使用宠物：常驻描边
        self.setCursor(Qt.PointingHandCursor)

    def set_pixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            inside = self.rect().contains(event.pos())
            if inside:
                self.clicked.emit()
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # 头像整幅等比居中（不裁切）。
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            painter.drawPixmap(
                (w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled,
            )
        # 反馈：圆角正方形描边（边长 = 按钮方形），悬停/按压变色。
        radius = max(6, round(16 * _FIT))
        pen_w = max(3, round(4 * _FIT))
        if self._pressed:
            painter.setPen(QPen(QColor("#e8714f"), pen_w))
            painter.setBrush(QColor(70, 42, 28, 60))
            painter.drawRoundedRect(
                pen_w // 2, pen_w // 2, w - pen_w, h - pen_w, radius, radius,
            )
        else:
            if self._hovered:
                painter.setBrush(QColor(255, 252, 246, 90))
                painter.drawRoundedRect(0, 0, w, h, radius, radius)
            # 选中（当前宠物）：淡琥珀虚线常驻描边；未选中悬停用珊瑚实线。
            if self.selected:
                pen = QPen(QColor(230, 183, 110, 200), pen_w, Qt.DotLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(
                    pen_w // 2, pen_w // 2, w - pen_w, h - pen_w,
                    radius, radius,
                )
            if self._hovered:
                painter.setPen(QPen(QColor("#f28f76"), pen_w))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(
                    pen_w // 2, pen_w // 2, w - pen_w, h - pen_w,
                    radius, radius,
                )


class _ArtButton(QWidget):
    """素材图标按钮（第十九/二十一轮泛化）：悬浮放大+白洗，点击缩小→
    还原后触发回调（两段式，节奏 CLOSE_*_MS）。用于关闭/改名等贴图键。"""

    def __init__(self, parent, art, on_activate):
        super().__init__(parent)
        self._art = art if not art.isNull() else QPixmap()
        self._on_activate = on_activate
        self.hovered = False
        self._phase = None  # None | "pressed" | "recover"
        self._armed = False      # 按下中（拖走取消判定）
        self._pending_fire = False  # 已在按钮内松开，待动画播完执行
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance_phase)
        self.setCursor(Qt.PointingHandCursor)

    def set_art_rect(self, art_rect):
        self.setGeometry(_R(*art_rect))

    def _art_rect(self):
        """素材绘制区（按钮内居中，按状态缩放）。"""
        full = QRect(0, 0, self.width(), self.height())
        rect = full
        if self._phase == "pressed":
            # 按住持续缩小（第三十四轮：幅度 4→3px 略减）。
            rect = full.adjusted(3, 3, -3, -3)
        elif self.hovered and self._phase is None:
            rect = full.adjusted(-3, -3, 3, 3)
        return rect

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self._art_rect()
        if not self._art.isNull():
            # 保持素材原比例居中绘制（缩放交互不压扁素材）。
            scaled = self._art.scaled(
                rect.width(), rect.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            painter.drawPixmap(
                rect.x() + (rect.width() - scaled.width()) // 2,
                rect.y() + (rect.height() - scaled.height()) // 2,
                scaled,
            )
        painter.setPen(Qt.NoPen)
        # 洗色位置 = 素材实际绘制位置（scaled 在按钮内居中后的矩形）。
        art_pos = QRect(
            rect.x() + (rect.width() - scaled.width()) // 2,
            rect.y() + (rect.height() - scaled.height()) // 2,
            scaled.width(), scaled.height(),
        )
        if self._phase == "pressed":
            # 黑闪盖素材实际范围（第三十四轮：alpha 80→60 略减）。
            painter.setBrush(QColor(70, 42, 28, 60))
            painter.drawRoundedRect(art_pos, 10, 10)
        elif self.hovered:
            painter.setBrush(QColor(255, 252, 246, 80))
            painter.drawRoundedRect(art_pos, 10, 10)

    def enterEvent(self, event):
        self.hovered = True
        self.update()

    def leaveEvent(self, event):
        self.hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        event.accept()
        self._armed = True
        # 头像式交互：按住持续缩小+压暗，松开才决定执行与否（不播定时动画）。
        self._phase = "pressed"
        self.update()

    def mouseReleaseEvent(self, event):
        """松开才执行：按钮内松开 → 待发；拖走松开 → 取消。"""
        if event.button() != Qt.LeftButton:
            return
        event.accept()
        armed = self._armed
        self._armed = False
        if not armed or not self.rect().contains(event.pos()):
            # 拖走松开：立刻恢复常态，取消反馈与执行。
            self._pending_fire = False
            self._phase = None
            self._timer.stop()
            self.update()
            return
        # 在按钮内松开：立即恢复常态并执行。
        self._phase = None
        self.update()
        self._fire()

    def _fire(self):
        activate = self._on_activate
        if callable(activate):
            activate()

    def _advance_phase(self):
        """兼容入口：立即恢复常态（两段定时动画已随头像式交互移除）。"""
        self._phase = None
        self.update()


class PetProfileWindow(QWidget):
    """宠物详情面板：background 圆角画布上的宠物内容区。

    所有按键加入时必须带悬停与点击反馈（AGENTS.md UI 约定）。
    """

    def __init__(self, pet, save_state):
        super().__init__()
        self.pet = pet
        self._save_state = (
            save_state if callable(save_state) else (lambda _state: None)
        )
        self._drag_offset = None
        self._name_dialog = None
        self._pet_cards = {}
        self._idle_frames = []
        self._idle_index = 0

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        global _FIT
        screen = None
        rect = getattr(pet, "current_screen_rect", None)
        try:
            screen = rect() if callable(rect) else None
        except (RuntimeError, AttributeError):
            screen = None
        _FIT = _resolve_scale(screen)
        self.setFixedSize(round(UNIFIED_W * _FIT), round(UNIFIED_H * _FIT))
        self._background = _pp_pixmap("new_background.png", ART_W, ART_H)
        # 头像列表 rail（宠物系统独立背景板，叠加在背景左侧）。
        self._rail = _pp_pixmap("pet_avatar_rail.png", RAIL_AT[2], RAIL_AT[3])
        # 素材逐个接入（base_UI 已于第六轮撤下）。
        self._close_button = _ArtButton(
            self, _pp_pixmap("close_button.png"), self.close,
        )
        self._close_button.set_art_rect(CLOSE_BUTTON_AT)
        # 套装装备按钮素材映射（绿=恐龙、橘=草莓），测试与刷新共用。
        self._outfit_button_assets = dict(OUTFIT_EQUIP_BUTTON)

        # 第七十二轮（改稿5）：边框再淡（奶黄 #fae7c0），字体 21→23。
        tip_host = QWidget(self)
        tip_host.setObjectName("shopTipBox")
        tip_host.setAttribute(Qt.WA_StyledBackground, True)
        tip_host.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        tip_host.setStyleSheet(
            "QWidget#shopTipBox{background:#fff6e8;"
            f"border:3px solid #fae7c0;border-radius:{round(14 * _FIT)}px;}}"
        )
        tip_layout = QVBoxLayout(tip_host)
        tip_layout.setContentsMargins(6, 6, 6, 6)
        self._shop_tip = QLabel("宠物和套装\n可前往商店购买")
        self._shop_tip.setWordWrap(True)
        self._shop_tip.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self._shop_tip.setStyleSheet(
            f"font-family:'{APP_FONT_FAMILY}';"
            f"font-size:{round(23 * _SX * _FIT)}px;"
            "font-weight:600;color:#a8742c;background:transparent;"
        )
        tip_layout.addWidget(self._shop_tip)
        tip_host.setGeometry(_R(*SHOP_TIP_AT))

        self._build_content()
        self._start_idle_animation()
        self.refresh()
        # 首帧绘制后后台预热各宠物/套装动画帧，消除首次切换的磁盘加载卡顿。
        QTimer.singleShot(0, self._prewarm_animation_frames)

    def _prewarm_animation_frames(self):
        """预载所有宠物的 idle 与套装专属动画帧（一次性磁盘 IO 移出交互路径）。

        注意：singleShot 可能在窗口已销毁后才触发（槽内对已删 C++ 对象
        访问会 RuntimeError，PyQt 对槽内异常直接终止进程）——必须兜底。
        """
        try:
            card_h = round(130 * _FIT)
            for pet_id in pet_registry.load_pet_registry():
                _load_idle_frames(pet_id, IDLE_FRAME_HEIGHT)
                for anim_key in OUTFIT_IDLE_ANIM.values():
                    _load_idle_frames(pet_id, card_h, anim_key=anim_key)
        except RuntimeError:
            pass  # 窗口已销毁，预热无意义。

    # ---- 内容区构建 ----

    def _label(self, text, x, y, w, h, *, size=16, color="#6b5646",
               bold=False, align=Qt.AlignLeft | Qt.AlignVCenter):
        label = QLabel(text, self)
        label.setAlignment(align)
        label.setWordWrap(False)
        style = (
            f"font-family:'{APP_FONT_FAMILY}';font-size:{round(size * _SX * _FIT)}px;"
            f"color:{color};background:transparent;"
        )
        if bold:
            style += "font-weight:600;"
        label.setStyleSheet(style)
        label.setGeometry(_R(x, y, w, h))
        return label

    def _pixmap_label(self, asset, x, y, w, h):
        label = QLabel(self)
        label.setPixmap(_pp_pixmap(asset, w, h))
        label.setScaledContents(True)
        label.setGeometry(_R(x, y, w, h))
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return label

    def _build_content(self):
        # 图1：左栏「我的伙伴与套装」标题 + rail 上双宠切换卡
        # （头像 + 卡下名字 + 卡内底部「使用中」pill，恢复自参考图）。
        self._rail_title = _ArtTitle("我的伙伴", self)
        self._rail_title.setGeometry(_R(*RAIL_TITLE_AT))
        for index, pet_id in enumerate(pet_registry.load_pet_registry()):
            if index >= len(PET_CARD_SLOTS):
                break
            card_x, card_y = PET_CARD_SLOTS[index]
            # 头像按钮（第二十三轮重写）：直接绘制整幅头像（修复 QPushButton
            # icon+padding 机制造成的显示不完整），反馈为贴合素材的
            # 圆角正方形描边（悬停珊瑚）+ 暗洗（按压）。
            button = _AvatarButton(self)
            # 方形按钮：横纵显示比例不同（_SX≠_SY）会把 150x150 拉成 118x99，
            # 用统一方形边长（取显示像素 106 ≈ 150*_SX）保证绝对正方形。
            button.setFixedSize(round(118 * _FIT), round(118 * _FIT))
            button.move(_R(card_x, card_y, 0, 0).topLeft())
            button.clicked.connect(
                lambda _checked=False, target=pet_id: self._select_pet(target)
            )
            # 「使用中」pill 已按用户指示停用（PET_CARD_TAG_AT 保留备用）。
            tag = None
            # 卡下名字已按用户指示删去（PET_CARD_NAME_AT 保留备用）。
            self._pet_cards[pet_id] = {"button": button, "tag": tag}

        # 图2：待机动画位（垫上，底部对齐）。
        self._idle_label = QLabel(self)
        self._idle_label.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self._idle_label.setGeometry(_R(*IDLE_PREVIEW_RECT))
        self._idle_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # 图3：名字牌（rename_bg）+ 艺术字名字 + 改名钮（change_name 素材，
        # 第二十一轮：与关闭键同款 _ArtButton 交互——悬浮放大/点击缩小还原）。
        self._pixmap_label("rename_bg.png", *NAME_PLATE_AT)
        self._name_label = _ArtTitle("", self, font_px=34)
        self._name_label.setGeometry(_R(*NAME_ART_AT))
        self._rename_button = _ArtButton(
            self, _pp_pixmap("change_name.png"), self._open_name_dialog,
        )
        self._rename_button.set_art_rect(RENAME_BUTTON_AT)

        # 第三十七轮：背景图直接覆盖原分栏+内容整块区域；两枚素材
        # 分栏按钮（参考图裁切）附着在背景图上方选择当前栏目。
        block_x, block_y = TAB_BAR_AT[0], TAB_BAR_AT[1]
        block_w = TAB_BAR_AT[2]
        block_h = (CONTENT_AT[1] + CONTENT_AT[3]) - TAB_BAR_AT[1]
        # 第三十九轮：统一背景 region_background.png（圆角裁剪），
        # 两枚素材分栏按钮移到背景图上方（骑在圆角顶边）。
        self._region_bg = _RoundedBgLabel(self, radius=28)
        self._region_bg.setGeometry(_R(block_x, block_y, block_w, block_h))
        self._region_bg.set_art(_pp_pixmap("region_background.png"))

        self._tab_buttons = {}
        tab_w = round(250 * _SX * _FIT)
        tab_h = round(72 * _SY * _FIT)
        # 第五十九轮：两键恢复同尺寸（文件名归位 + 新简介素材接入）。
        # 第六十一轮：紧靠在一起——widget 按素材实宽收窄（左右各 3px
        # 悬浮余量），两 widget 相接，素材间距 6px；简介素材位置不动。
        tab_headroom = 4
        # 第六十三轮：左右余量 3→5（悬浮横向涨幅 +4px + 抗锯齿 1px 缓冲）。
        side_margin = 5
        # 第六十二轮：两键放大 20%（素材高 32→38）。
        tab_scale = 1.2
        base_art_h = round(tab_h * _SY * _FIT * tab_scale)
        # 第六十五轮：两键精准吸附到背景卡边框上方——素材底缘 = 卡顶缘
        # （不再半嵌卡片）。
        card_top = _R(0, TAB_BAR_AT[1], 1, 1).y()
        old_w = _R(0, 0, tab_w, 1).width()
        prev_rect = None
        for i, (name, art_name) in enumerate(TAB_SLOTS.items()):
            pm = _pp_pixmap(art_name)
            tab = _TabButton(name, self, art=pm, headroom=tab_headroom,
                             side_margin=side_margin)
            if pm.isNull() or pm.height() == 0:
                art_w = old_w - 2 * side_margin
            else:
                art_w = round(pm.width() / pm.height() * base_art_h)
            w = art_w + 2 * side_margin
            tx = block_x + round((6 + i * 216) * _SX * _FIT)
            if prev_rect is None:
                # 首键素材左缘对齐内容区左缘（内容边距 22）。
                x = _R(CONTENT_AT[0], 0, 1, 1).x() + 22 - side_margin
            else:
                # 第七十一轮：与上一枚紧连（widget 重叠 6px，素材间距 4px）。
                x = prev_rect.x() + prev_rect.width() - 6
            rect = QRect(x, card_top - base_art_h - tab_headroom,
                         w, base_art_h + 2 * tab_headroom)
            tab.setGeometry(rect)
            prev_rect = rect
            tab.raise_()
            tab.clicked.connect(
                lambda target=name: self._show_tab(target)
            )
            self._tab_buttons[name] = tab

        self._content = QStackedWidget(self)
        self._content.setGeometry(_R(*CONTENT_AT))
        # 内容直接写在区域背景内框里（第三十九轮：剥掉所有中间层）。
        self._content.setContentsMargins(22, 6, 22, 10)
        self._intro_page = self._build_intro_page()
        self._outfit_page = self._build_outfit_page()
        self._gift_page = self._build_gift_page()
        self._content.addWidget(self._intro_page)
        self._content.addWidget(self._outfit_page)
        self._content.addWidget(self._gift_page)
        self._show_tab("简介")

    def _tab_qss(self):
        """分栏按钮：胶囊形（第九轮），选中珊瑚、悬停白洗、按压压暗。"""
        font_px = round(26 * _SX * _FIT)
        th = TAB_SLOTS["简介"][3]
        radius = max(8, round(th * _SY * _FIT / 2))
        return (
            "QPushButton{"
            f"font-family:'{APP_FONT_FAMILY}';font-size:{font_px}px;"
            f"font-weight:600;color:#6b5646;background:transparent;"
            f"border:none;border-radius:{radius}px;padding:0 14px;}}"
            "QPushButton:hover{background:rgba(255,252,246,150);}"
            "QPushButton:pressed{background:rgba(70,42,28,70);}"
            "QPushButton:checked{background:#f5a48f;color:#ffffff;}"
            "QPushButton:checked:hover{background:#f28f76;}"
        )

    def _scroll_qss(self, bar_right_shift=0):
        """商店同款滚动条样式（progression/ui PANEL_STYLE）。

        bar_right_shift：滚动条右移量（px）。QSS 负 margin 让滚动条
        越出视口右缘绘制——这是唯一能穿透 QStackedWidget 硬性
        contentsMargins 的办法（容器负边距对它无效，实测）。
        """
        shift = f"margin:4px {bar_right_shift}px 4px 0;" if bar_right_shift else "margin:4px 0;"
        return (
            "QScrollArea{border:0;background:transparent;}"
            "QScrollArea>QWidget>QWidget{background:transparent;border:0;}"
            f"QScrollBar:vertical{{background:transparent;width:11px;"
            f"{shift}}}"
            "QScrollBar::handle:vertical{background:#e8bfa8;"
            "border-radius:5px;min-height:38px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{"
            "height:0;width:0;}"
        )

    # 简介各节的图标素材（第三十六轮）。偏好节沿用星星图标（原等级节）。
    SECTION_ICONS = {
        "affection": "icon_heart_affection.png",
        "attrs": "icon_paw_attributes.png",
        "personality": "icon_leaf_personality.png",
        "gifts": "icon_star_level.png",
    }

    def _build_intro_page(self):
        """简介页（第三十六轮素材版）：jieshao 背景图 + 图标节标 +
        数值 + 素材进度条；滑动/扫光动画保留。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._scroll_qss())
        host = QWidget()
        # 背景在外层 _region_bg（第三十七轮覆盖整块区域）。
        layout = QVBoxLayout(host)
        layout.setContentsMargins(24, 18, 24, 14)
        layout.setSpacing(6)
        k = _SX * _FIT

        self._intro_sections = {}
        self._intro_heads = {}
        # 第五十四轮：图标竖跨两行（左），节名/数值两行文字（右）。
        # 偏好轮：等级节删除（等级随宠物卡/状态卡展示），改为「偏好」
        # 节置底，显示该宠物每档的最爱礼物（registry gift_preferences）。
        sections = (
            ("好感", "affection"),
            ("属性", "attrs"),
            ("性格", "personality"),
            ("偏好", "gifts"),
        )
        for title, key in sections:
            row, value = self._intro_section(title, key, k)
            layout.addWidget(row)
            self._intro_heads[key] = row
            self._intro_sections[key] = value
            # 第七十一轮：模块间隙 = 最小 8px + 均摊剩余空间，
            # 四模块铺满内容区（原尾部堆一堆空白不美观）。
            layout.addSpacing(8)
            layout.addStretch(1)
        scroll.setWidget(host)
        return scroll

    def _intro_section(self, title, key, k):
        """图标竖跨两行居中 + 右侧两行文字（节名/数值）（第五十四轮）。"""
        row = QWidget()
        row.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        icon = QLabel()
        pm = _pp_pixmap(self.SECTION_ICONS.get(key, ""))
        if not pm.isNull():
            icon_px = max(18, round(60 * _FIT))   # 两行高度（第五十一轮）
            icon.setPixmap(pm.scaled(
                icon_px, icon_px,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            ))
            h.addWidget(icon, 0, Qt.AlignVCenter)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-family:'{APP_FONT_FAMILY}';font-size:{round(27 * k)}px;"
            "font-weight:600;color:#d29a38;background:transparent;"
        )
        col.addWidget(title_label)
        value = QLabel()
        value.setWordWrap(True)
        value.setStyleSheet(
            f"font-family:'{APP_FONT_FAMILY}';font-size:{round(26 * k)}px;"
            "font-weight:600;color:#a8742c;background:transparent;"
        )
        col.addWidget(value)
        # 文字列吃满剩余宽度，数值尽量单行（wordWrap 仅兜底长文本）。
        h.addLayout(col, 1)
        return row, value

    def _build_outfit_page(self):
        """套装页（第十轮）：大卡纵排，只上下滚动。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(self._scroll_qss())
        self._outfit_host = QWidget()
        self._outfit_layout = QVBoxLayout(self._outfit_host)
        # 第五十六轮：左右边距收窄（8/14→2/4），套装卡加宽 16 显示px。
        self._outfit_layout.setContentsMargins(2, 10, 4, 10)
        self._outfit_layout.setSpacing(12)
        self._outfit_layout.addStretch(1)
        # 背景在外层 _region_bg（第三十七轮覆盖整块区域）。
        scroll.setWidget(self._outfit_host)
        return scroll

    def _show_tab(self, name):
        """切换分栏（同步选中态 + 区域背景图随页切换）。"""
        pages = {
            "简介": self._intro_page,
            "套装": self._outfit_page,
            "礼物": self._gift_page,
        }
        page = pages.get(name, self._intro_page)
        self._content.setCurrentWidget(page)
        # 礼物页滚动条贴缘（2026-09-09）：切到礼物页时把内容栈右边距
        # 22→0（滚动条 QSS 负 margin 11px 已吃进这 22px 空间，剩余 11
        # 为视觉间隙）；切回其他页恢复，避免简介/套装页布局变化。
        if name == "礼物":
            self._content.setContentsMargins(22, 6, 0, 10)
        else:
            self._content.setContentsMargins(22, 6, 22, 10)
        for label, button in self._tab_buttons.items():
            button.setChecked(label == name)

    def _start_idle_animation(self):
        """加载当前宠物 idle 动画帧并按 8fps 循环播放。"""
        self._idle_frames = _load_idle_frames(
            self._active_pet_id(), IDLE_FRAME_HEIGHT,
        )
        self._idle_index = 0
        if self._idle_frames:
            self._idle_label.setPixmap(self._idle_frames[0])
            if not hasattr(self, "_idle_timer") or self._idle_timer is None:
                self._idle_timer = QTimer(self)
                self._idle_timer.timeout.connect(self._advance_idle_frame)
            self._idle_timer.start(round(1000 / IDLE_FPS))
        else:
            self._idle_timer = None

    def _advance_idle_frame(self):
        if not self._idle_frames:
            return
        self._idle_index = (self._idle_index + 1) % len(self._idle_frames)
        self._idle_label.setPixmap(self._idle_frames[self._idle_index])

    def _active_pet_id(self):
        return str(self.pet.state.get(
            "active_pet_id", pet_registry.DEFAULT_PET_ID,
        ))

    # ---- 数据刷新与交互 ----

    def refresh(self):
        state = self.pet.state
        active_id = self._active_pet_id()
        snapshot = pet_profile_snapshot(state, active_id)

        owned_ids = set(state.get("owned_pet_ids") or ())
        owned_ids.add(active_id)
        for pet_id, card in self._pet_cards.items():
            owned = pet_id in owned_ids
            icon_name = SPECIES_RAIL_ICON.get(pet_id)
            icon_path = (
                _pp_asset(icon_name) if icon_name
                else pet_registry.pet_avatar_path(pet_id)
            )
            if owned:
                icon = QPixmap(icon_path) if icon_path else QPixmap()
            else:
                icon = _grayscale_pixmap(icon_path) if icon_path else QPixmap()
            card["button"].set_pixmap(icon)
            card["button"].selected = pet_id == active_id
            card["button"].update()
            if card.get("tag") is not None:
                card["tag"].setVisible(pet_id == active_id)

        self._refresh_intro(snapshot)
        self._refresh_outfits(snapshot)
        self._refresh_gifts()

    def _refresh_intro(self, snapshot):
        """简介页：分节数值；名字在名字牌。

        偏好轮：等级节删除，「偏好」节置底显示该宠物每档最爱
        （registry gift_preferences，按档 1→3）。未声明偏好的宠物
        显示「还没有特别的偏好」。
        """
        self._name_label.setText(snapshot["name"])
        self._intro_sections["affection"].setText(
            f"Lv.{snapshot['affection_level']}　"
            f"{snapshot['affection_points']} / {snapshot['affection_next']}"
        )

        self._intro_sections["attrs"].setText(
            f"饱腹 {snapshot['hunger']}　心情 {snapshot['mood']}　"
            f"精力 {snapshot['energy']}"
        )
        self._intro_sections["personality"].setText(snapshot["description"])

        favorites = progression.preferred_gift_ids(snapshot["id"])
        if favorites:
            self._intro_sections["gifts"].setText(
                " · ".join(
                    progression.GIFT_DEFINITIONS[g]["name"]
                    for g in favorites
                )
            )
        else:
            self._intro_sections["gifts"].setText("还没有特别的偏好")

    def _refresh_outfits(self, snapshot):
        """套装页（第二十七轮）：商店同款横版卡（左图右文+卡内装备钮）。"""
        while self._outfit_layout.count() > 1:
            item = self._outfit_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._outfit_widgets = []
        pet_id = snapshot["id"]
        card_h = round(215 * _SY * _FIT)
        for outfit in snapshot["outfits"]:
            art_name = OUTFIT_ART.get(outfit["id"])
            art_path = _pp_asset(art_name) if art_name else None
            if not art_path:
                art_path = _outfit_preview_path(pet_id, outfit)
            card = QWidget()
            card.setMinimumHeight(card_h)
            # 套装外围框（第五十二轮恢复）：暖棕虚线圆角。
            # 第五十五轮：选择器收窄到卡片本体——裸 QWidget 会把虚线框
            # 传染给卡内图片/动画等 QLabel 子控件（用户指出两处内框删除）。
            card.setObjectName("outfitCard")
            card.setStyleSheet(
                "QWidget#outfitCard{background:transparent;"
                f"border:2px dashed #d6a880;border-radius:16px;}}"
            )
            row = QHBoxLayout(card)
            row.setContentsMargins(12, 8, 12, 8)
            row.setSpacing(12)

            pixmap_label = QLabel()
            pixmap_label.setAlignment(Qt.AlignCenter)
            # 图定框等比（防按高缩放过宽挤爆文字行）。
            pixmap_label.setFixedSize(
                round(150 * _SX * _FIT), round((card_h - 16) * _SY * _FIT),
            )
            art = QPixmap(art_path) if art_path else QPixmap()
            if not art.isNull():
                pixmap_label.setPixmap(art.scaled(
                    pixmap_label.width(), pixmap_label.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                ))
            row.addWidget(pixmap_label)

            text_col = QVBoxLayout()
            text_col.setContentsMargins(0, 6, 0, 6)
            text_col.setSpacing(6)
            name_label = QLabel(outfit["name"])
            name_label.setStyleSheet(
                f"font-family:'{APP_FONT_FAMILY}';"
                f"font-size:{round(26 * _SX * _FIT)}px;font-weight:600;"
                "color:#a8742c;background:transparent;border:0;"
            )
            desc_label = QLabel(outfit.get("description") or "")
            desc_label.setWordWrap(True)
            # 第三十二轮：文字列加宽用控件 min-width（不能给装了控件的
            # layout 做 text_host 包装——reparent 链会同步销毁按钮）。
            name_label.setMinimumWidth(round(250 * _SX * _FIT))
            desc_label.setMinimumWidth(round(250 * _SX * _FIT))
            # 描述字号（第二十八轮：19→23）。
            desc_label.setStyleSheet(
                f"font-family:'{APP_FONT_FAMILY}';"
                f"font-size:{round(23 * _SX * _FIT)}px;"
                "color:#b08a5e;background:transparent;border:0;"
            )
            text_col.addWidget(name_label)
            text_col.addWidget(desc_label)
            text_col.addStretch(1)
            # 装备按钮（第二十八轮）：描述小字正下方空出处。
            equip_asset = OUTFIT_EQUIP_BUTTON.get(outfit["id"])
            button = None
            if equip_asset and not art.isNull():
                button = _ArtButton(
                    card, _pp_pixmap(equip_asset),
                    lambda oid=outfit["id"]: self._toggle_outfit(oid),
                )
                btn_w = round(190 * _SX * _FIT)
                btn_h = round(60 * _SY * _FIT)
                button.setFixedSize(btn_w, btn_h)
                text_col.addWidget(button, 0, Qt.AlignHCenter)
            row.addLayout(text_col, 1)

            # 右侧空位：穿上对应套装的小狗待机动画。
            idle = _OutfitIdleLabel(card)
            # 等比方形（双比例会拉伸/裁切），帧高直接用 label 实际像素。
            # 第三十二轮：框 150px（随卡内空间收紧）。
            idle_px = round(130 * _FIT)
            idle.setFixedSize(idle_px, idle_px)
            idle.set_frames(_load_idle_frames(
                pet_id, idle_px,
                anim_key=OUTFIT_IDLE_ANIM.get(outfit["id"], ""),
            ))
            idle.show()
            row.addWidget(idle, 0, Qt.AlignBottom)

            # 第三十一轮：行宽自适应——文字列实际可用宽 = 卡宽-图-动画-边距，
            # 若描述实测超 2 行，加高卡让文字放宽后两行完整显示。
            from PyQt5.QtGui import QFontMetrics
            fm = QFontMetrics(desc_label.font())
            # 第三十二轮：文字行宽加宽 10 显示px。
            text_w = max(200, card.width() - pixmap_label.width()
                         - idle.width() - round(60 * _SX * _FIT)
                         + round(10 / _SX))
            lines_needed = 0
            remaining = outfit.get("description") or ""
            while remaining and lines_needed < 4:
                chunk = fm.elidedText(remaining, Qt.ElideNone, text_w)
                if not chunk:
                    break
                lines_needed += 1
                remaining = remaining[len(chunk):]
            if lines_needed > 2:
                extra = (lines_needed - 2) * fm.lineSpacing()
                card.setMinimumHeight(card_h + extra)

            self._outfit_layout.insertWidget(
                self._outfit_layout.count() - 1, card,
            )
            self._outfit_widgets.append(
                {"pixmap": pixmap_label, "button": button,
                 "idle": idle, "outfit_id": outfit["id"]},
            )
    # ---- 礼物分栏（2026-09-07 礼物系统轮） ----

    def _build_gift_page(self):
        """礼物页：与套装页同骨架（纵向滚动），内容随 refresh 重建。

        滚动条右移走 QSS 负 margin（见下方实现注释），页面仍是
        直接的 QScrollArea。
        """
        self._gift_widgets = {}
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 滚动条右移走 QSS 负 margin（_scroll_qss 的 bar_right_shift）：
        # page 在 QStackedWidget 内，容器负边距被其硬性 contentsMargins
        # 钳住无效（-8/-22/-44 三轮实测）。33px = 内容栈右边距 22 +
        # 滚动条宽 11：bar 右缘 768 → 801（region_background 右缘），
        # 2026-09-09 真机几何实测定值。
        scroll.setStyleSheet(self._scroll_qss(bar_right_shift=33))
        self._gift_host = QWidget()
        self._gift_layout = QVBoxLayout(self._gift_host)
        # 右边距 4→8：给右移后的滚动条留 ~3px+ 间隙。
        self._gift_layout.setContentsMargins(2, 10, 8, 10)
        self._gift_layout.setSpacing(12)
        self._gift_layout.addStretch(1)
        scroll.setWidget(self._gift_host)
        return scroll

    def _refresh_gifts(self):
        """按共享背包重建礼物卡；空背包显示引导文案。

        简略三列网格（2026-09-08 用户定稿）：一行三个、图标+名称+
        最爱/好感/数量+送出键，三列等宽（最爱与否占位一致）。
        """
        while self._gift_layout.count() > 1:
            item = self._gift_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._gift_widgets = {}
        state = self.pet.state
        inventory = progression.gift_inventory(state)
        if not inventory:
            host = QWidget()
            col = QVBoxLayout(host)
            col.setContentsMargins(0, 30, 0, 30)
            col.setSpacing(16)
            empty = QLabel(
                "背包里还没有礼物\n可以去商店的「礼物」页挑选心意"
            )
            empty.setObjectName("giftEmptyHint")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"font-family:'{APP_FONT_FAMILY}';"
                f"font-size:{round(23 * _SX * _FIT)}px;"
                "color:#b08a5e;background:transparent;border:0;"
            )
            col.addWidget(empty)
            # 直达商店礼物页（2026-09-10 用户指示）：胶囊键，悬浮提亮、
            # 按住压暗（面板 QSS 胶囊同款反馈）。
            go_shop = QPushButton("去商店挑选")
            go_shop.setObjectName("giftGoShopButton")
            go_shop.setCursor(Qt.PointingHandCursor)
            go_shop.setFixedSize(
                round(210 * _SX * _FIT), round(54 * _SY * _FIT))
            go_shop.setStyleSheet(
                f"QPushButton{{font-family:'{APP_FONT_FAMILY}';"
                f"font-size:{round(22 * _SX * _FIT)}px;font-weight:600;"
                "color:#ffffff;background:#f28f76;border:0;"
                f"border-radius:{round(27 * _SY * _FIT)}px;}}"
                "QPushButton:hover{background:#f5a48f;}"
                "QPushButton:pressed{background:#dd7a5f;}"
            )
            go_shop.clicked.connect(lambda: self._open_shop("gifts"))
            col.addWidget(go_shop, 0, Qt.AlignHCenter)
            self._gift_layout.insertWidget(0, host)
            return
        stocked = [
            gift_id for gift_id in progression.GIFT_DEFINITIONS
            if int(inventory.get(gift_id, 0)) > 0
        ]
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        for index, gift_id in enumerate(stocked):
            card = self._gift_card(
                gift_id, int(inventory.get(gift_id, 0)),
            )
            grid.addWidget(card, index // 3, index % 3)
            self._gift_widgets[gift_id] = card
        self._gift_layout.insertWidget(0, grid_host)

    def _gift_card(self, gift_id, count):
        """简略竖卡：图标/名称/最爱标记/好感×数量/送出键，整体居中。"""
        definition = progression.GIFT_DEFINITIONS[gift_id]
        _base, affection, preferred = progression.gift_affection_for(
            self._active_pet_id(), gift_id,
        )
        card = QWidget()
        # 选择器必须 objectName 限定（第五十五轮坑位：裸 QWidget 会把
        # 边框传染给卡内 QLabel）。
        card.setObjectName("giftCard")
        card.setStyleSheet(
            "QWidget#giftCard{background:transparent;"
            f"border:2px dashed #d6a880;border-radius:16px;}}"
        )
        col = QVBoxLayout(card)
        col.setContentsMargins(8, 8, 8, 8)
        col.setSpacing(4)

        icon = QLabel()
        icon.setAlignment(Qt.AlignCenter)
        icon_px = round(82 * _FIT)
        icon.setFixedSize(icon_px, icon_px)
        art = QPixmap(os.path.join(
            GIFTS_UI_DIR, definition.get("icon", ""),
        ))
        if not art.isNull():
            icon.setPixmap(art.scaled(
                icon.width(), icon.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            ))
        col.addWidget(icon, 0, Qt.AlignHCenter)

        name = QLabel(definition.get("name", gift_id))
        name.setObjectName(f"giftName_{gift_id}")
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet(
            f"font-family:'{APP_FONT_FAMILY}';"
            f"font-size:{round(24 * _SX * _FIT)}px;font-weight:600;"
            "color:#a8742c;background:transparent;border:0;"
        )
        col.addWidget(name, 0, Qt.AlignHCenter)

        # 数值行不带 ♥ 字符：幼圆缺该字形会回退到更高字体（30 vs 27px）
        # 导致最爱卡整卡比普通卡高（2026-09-09 用户反馈）；最爱只用
        # 珊瑚色表达，普通卡琥珀色。
        count_label = QLabel(
            f"+{affection} ×{count}"
        )
        count_label.setObjectName(f"giftCount_{gift_id}")
        count_label.setAlignment(Qt.AlignCenter)
        count_label.setStyleSheet(
            f"font-family:'{APP_FONT_FAMILY}';"
            f"font-size:{round(22 * _SX * _FIT)}px;font-weight:600;"
            + ("color:#ef7a5f;" if preferred else "color:#d29a38;")
            + "background:transparent;border:0;"
        )
        col.addWidget(count_label, 0, Qt.AlignHCenter)
        col.addStretch(1)

        send = _ArtButton(
            card, _pp_pixmap("send_gift_button.png"),
            lambda gid=gift_id: self._give_gift(gid),
        )
        send.setObjectName(f"sendGift_{gift_id}")
        send.setFixedSize(round(150 * _SX * _FIT), round(54 * _SY * _FIT))
        col.addWidget(send, 0, Qt.AlignHCenter)
        return card

    def _give_gift(self, gift_id):
        """送出按钮：确认弹窗 → 扣库存加好感 → 存档/气泡/心心/刷新。"""
        state = self.pet.state
        if progression.gift_count(state, gift_id) <= 0:
            return
        if not self._confirm_send_gift(gift_id):
            return
        result = progression.give_gift(
            state, self._active_pet_id(), gift_id,
        )
        say = getattr(self.pet, "say", None)
        message = result.get("message", "")
        if result.get("ok"):
            self._save_state(state)
            self._play_gift_hearts()
        if callable(say) and message:
            try:
                self.pet.say(message, 2100)
            except RuntimeError:
                pass
        self.refresh()

    def _confirm_send_gift(self, gift_id):
        """送礼确认弹窗（复用商店 PurchasePopup，双键确认）。"""
        definition = progression.GIFT_DEFINITIONS.get(gift_id, {})
        name = definition.get("name", gift_id)
        _base, affection, preferred = progression.gift_affection_for(
            self._active_pet_id(), gift_id,
        )
        affection_line = (
            f"好感 +{affection}（TA的最爱！）"
            if preferred else f"好感 +{affection}"
        )
        state = self.pet.state
        pet_name = (
            state.get("name") or state.get("pet_name")
            or pet_registry.pet_definition(
                self._active_pet_id(),
            ).get("default_name", self._active_pet_id())
        )
        popup = PurchasePopup(
            "送出礼物",
            [f"把「{name}」送给 {pet_name} 吗？", affection_line],
            self,
            confirm_text="送出",
            cancel_text="再想想",
        )
        geometry = self.frameGeometry()
        popup.move(
            geometry.center().x() - popup.width() // 2,
            geometry.center().y() - popup.height() // 2,
        )
        return popup.exec_() == PurchasePopup.Accepted

    def _play_gift_hearts(self):
        """送礼成功：待机动画区上错峰飘起 5 颗心（抬升+淡出后自删）。

        槽内异常会静默终止进程（AGENTS 坑位），全部兜 RuntimeError。
        """
        try:
            base_rect = self._idle_label.geometry()
            for index in range(5):
                QTimer.singleShot(
                    index * 130,
                    lambda i=index: self._spawn_gift_heart(base_rect, i),
                )
        except RuntimeError:
            pass

    def _spawn_gift_heart(self, base_rect, index):
        try:
            size = round((30 + (index % 3) * 9) * _FIT)
            heart = QLabel("♥", self)
            heart.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            heart.setStyleSheet(
                f"font-family:'{APP_FONT_FAMILY}';font-size:{size}px;"
                "font-weight:600;color:#ef7a5f;background:transparent;"
            )
            x = base_rect.x() + round(
                (0.18 + 0.16 * index) * base_rect.width()
            )
            y0 = base_rect.y() + round(base_rect.height() * 0.62)
            heart.move(x, y0)
            heart.adjustSize()
            heart.show()
            heart.raise_()
            effect = QGraphicsOpacityEffect(heart)
            heart.setGraphicsEffect(effect)
            lift = round(95 * _FIT)
            anim = QVariantAnimation(
                self, startValue=0.0, endValue=1.0,
                duration=900 + index * 120,
            )
            anim.setEasingCurve(QEasingCurve.OutCubic)

            def on_step(value, heart=heart, y0=y0, lift=lift):
                try:
                    heart.move(heart.x(), y0 - round(value * lift))
                except RuntimeError:
                    pass

            def on_fade(value, effect=effect):
                try:
                    effect.setOpacity(1.0 - value)
                except RuntimeError:
                    pass

            def on_finish(heart=heart):
                try:
                    heart.deleteLater()
                except RuntimeError:
                    pass

            anim.valueChanged.connect(on_step)
            anim.valueChanged.connect(on_fade)
            anim.finished.connect(on_finish)
            anim.start(QVariantAnimation.DeleteWhenStopped)
        except RuntimeError:
            pass

    def _toggle_outfit(self, outfit_id):
        """点击装备按钮：未装备→装备，已装备→卸下；保存并同步桌面/小屋。"""
        if self.pet.state.get("equipped_outfit") == outfit_id:
            result = progression.unequip_outfit(self.pet.state)
        else:
            result = progression.equip_outfit(self.pet.state, outfit_id)
        if result.get("ok"):
            self._save_state(self.pet.state)
            self.pet.update()
            home = getattr(self.pet, "home_scene_window", None)
            refresh_home = getattr(home, "refresh_pet_assets", None)
            if callable(refresh_home):
                refresh_home()
        self.refresh()

    def _open_shop(self, page=None):
        opener = getattr(self.pet, "open_shop", None)
        if callable(opener):
            try:
                opener(page)
            except TypeError:
                # 宿主 open_shop 不支持页签参数（旧注入）。
                opener()

    def _open_name_dialog(self):
        if _NAME_DIALOG_FACTORY is None:
            return
        snapshot = pet_profile_snapshot(self.pet.state, self._active_pet_id())
        dialog = _NAME_DIALOG_FACTORY(
            snapshot["name"], self._commit_name, self.window(),
        )
        self._name_dialog = dialog
        dialog.exec_()
        self._name_dialog = None

    def _commit_name(self, new_name):
        if not (isinstance(new_name, str) and new_name.strip()):
            return
        setter = getattr(self.pet, "set_pet_name", None)
        if callable(setter):
            setter(new_name.strip())
        self._save_state(self.pet.state)
        self.refresh()

    def _select_pet(self, pet_id):
        if pet_id == self._active_pet_id():
            return
        snapshot = pet_profile_snapshot(self.pet.state, pet_id)
        if not snapshot["owned"]:
            return
        result = self.pet.set_active_pet(pet_id)
        if isinstance(result, dict) and result.get("ok") is False:
            return
        self._start_idle_animation()
        self.refresh()

    def show_near_pet(self):
        """面板在屏幕居中打开（与商店/成就/记录面板一致）。"""
        self.refresh()
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )
        self.show()
        self.raise_()
        self.activateWindow()

    # ---- 画布绘制与拖拽 ----

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        radius = CORNER_RADIUS * _SX * _FIT
        clip.addRoundedRect(0, 0, self.width(), self.height(),
                            radius, radius)
        painter.setClipPath(clip)
        if not self._background.isNull():
            painter.drawPixmap(0, 0, self._background)
        if not self._rail.isNull():
            painter.drawPixmap(_R(*RAIL_AT).topLeft(), self._rail)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

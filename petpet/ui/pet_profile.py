"""宠物详情面板：数据快照纯函数 + 新素材面板（逐轮搭建）。

页面骨架：background 原生尺寸 1201x1304（显示比例 0.7），background + base_UI
两层，整页圆角裁剪（CORNER_RADIUS），无边框可拖拽。
内容区（第三轮）：左栏宠物切换卡、待机动画、名字牌+改名、等级/好感两行。
"""

from __future__ import annotations

import io
import json
import os

import numpy as np
from PIL import Image as PILImage
from PyQt5.QtCore import QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import (QApplication, QLabel, QPushButton,
                             QScrollArea, QStackedWidget, QVBoxLayout,
                             QWidget)

from petpet.app.fonts import APP_FONT_FAMILY
from petpet.app import pets as pet_registry
from petpet.app import state as app_state
from petpet.progression import core as progression

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

# 图1 左栏：宠物头像列表 rail（250x1326 素材，纯背景板无烘焙槽）+
# 程序布局双卡槽（坐标按参考图反推到 art 比例）。
RAIL_AT = (51, 230, 200, 992)
RAIL_TITLE_AT = (24, 182, 320, 46)           # 「我的伙伴」（rail 正上方，加粗）
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
NAME_PLATE_AT = (440, 585, 360, 70)
NAME_ART_AT = (452, 588, 205, 64)
RENAME_BUTTON_AT = (668, 588, 113, 66)   # 原生 94x55 × 1.2 等比（不被压扁）

# 分栏（description_bg）：名字牌下方；两页「简介 / 套装」。
TAB_BAR_AT = (305, 684, 728, 69)
TAB_SLOTS = {
    "简介": (365, 696, 140, 46),
    "套装": (515, 696, 140, 46),
}
CONTENT_AT = (305, 778, 728, 600)

# 套装素材（新 art 直接按套装 id 映射；未映射回退 idle 预览路径）。
OUTFIT_ART = {
    "strawberry_suit": "outfit_strawberry.png",
    "dinosaur_suit": "outfit_diansour.png",
}
OUTFIT_CARD_SIZE = (620, 400)

# 套装装备按钮素材（绿=恐龙、橘=草莓，第十一轮）。
OUTFIT_EQUIP_BUTTON = {
    "dinosaur_suit": "equip_button_green.png",
    "strawberry_suit": "equip_button_orange.png",
}


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


def _load_idle_frames(pet_id, height):
    """加载桌面 idle 动画全部帧（等高缩放）；无动画回退空列表。"""
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
        anim = manifest.get("idle") or {}
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
        return frames
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
    """简介进度条：深奶油槽 + 珊瑚渐变填充 + 高光带（第二十一轮恢复）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._maximum = 1
        self.setFixedHeight(max(8, round(18 * _SY * _FIT)))

    def set_ratio(self, value, maximum):
        self._value = max(0, int(value))
        self._maximum = max(1, int(maximum))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        radius = h / 2
        track = QPainterPath()
        track.addRoundedRect(0, 0, w, h, radius, radius)
        painter.setPen(QPen(QColor(232, 197, 158), max(1, h // 16)))
        painter.setBrush(QColor("#f6ead8"))
        painter.drawPath(track)
        frac = max(0.0, min(1.0, self._value / self._maximum))
        if frac <= 0:
            return
        fill_w = max(int(w * frac), h)
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
        highlight = QPainterPath()
        hl_h = (h - inset * 4) * 0.42
        highlight.addRoundedRect(inset * 2, inset * 2,
                                 max(0.0, fill_w - inset * 4), hl_h,
                                 hl_h / 2, hl_h / 2)
        painter.setBrush(QColor(255, 255, 255, 90))
        painter.drawPath(highlight)


class _AvatarButton(QWidget):
    """宠物头像按钮：整幅绘制不裁切；悬停=圆角正方形珊瑚描边+白洗，
    按压=暗洗+描边（贴合素材的绝对圆角方形，不受 QSS padding 影响）。"""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._hovered = False
        self._pressed = False
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
        radius = max(6, round(18 * _SX * _FIT))
        pen_w = max(2, round(3 * _SX * _FIT))
        if self._pressed:
            painter.setPen(QPen(QColor("#e8714f"), pen_w))
            painter.setBrush(QColor(70, 42, 28, 60))
            painter.drawRoundedRect(
                pen_w // 2, pen_w // 2, w - pen_w, h - pen_w, radius, radius,
            )
        elif self._hovered:
            painter.setBrush(QColor(255, 252, 246, 90))
            painter.drawRoundedRect(0, 0, w, h, radius, radius)
            painter.setPen(QPen(QColor("#f28f76"), pen_w))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(
                pen_w // 2, pen_w // 2, w - pen_w, h - pen_w, radius, radius,
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
        if self.hovered and self._phase is None:
            rect = full.adjusted(-3, -3, 3, 3)
        elif self._phase == "pressed":
            rect = full.adjusted(4, 4, -4, -4)
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
        if self._phase == "pressed":
            painter.setBrush(QColor(70, 42, 28, 120))
            painter.drawRoundedRect(rect, 12, 12)
        elif self.hovered or self._phase == "recover":
            painter.setBrush(QColor(255, 252, 246, 80))
            painter.drawRoundedRect(rect, 12, 12)

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
        self._phase = "pressed"
        self._timer.start(CLOSE_PRESS_FLASH_MS + 20)
        self.update()

    def _advance_phase(self):
        if self._phase == "pressed":
            self._phase = "recover"
            self._timer.start(
                CLOSE_CLICK_DEFER_MS - CLOSE_PRESS_FLASH_MS + 20
            )
            self.update()
            return
        self._phase = None
        self.update()
        activate = self._on_activate
        if callable(activate):
            activate()


class PetProfileWindow(QWidget):
    """宠物详情面板：background + base_UI 圆角画布上的宠物内容区。

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
        self._rail = _pp_pixmap("宠物头像列表.png", RAIL_AT[2], RAIL_AT[3])
        # base_UI 已按用户指示撤下（第六轮）；第七轮：新 UI 素材逐个接入。
        self._close_button = _ArtButton(
            self, _pp_pixmap("close_button.png"), self.close,
        )
        self._close_button.set_art_rect(CLOSE_BUTTON_AT)
        # 套装装备按钮素材映射（绿=恐龙、橘=草莓），测试与刷新共用。
        self._outfit_button_assets = dict(OUTFIT_EQUIP_BUTTON)

        self._build_content()
        self._start_idle_animation()
        self.refresh()

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
            button.setGeometry(_R(card_x, card_y, *PET_CARD_SIZE))
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

        # 分栏（description_bg 素材）+ 内容页（滚动区承载，超出可滚）。
        self._pixmap_label("description_bg.png", *TAB_BAR_AT)
        self._tab_buttons = {}
        for name, (tx, ty, tw, th) in TAB_SLOTS.items():
            tab = QPushButton(name, self)
            tab.setCursor(Qt.PointingHandCursor)
            tab.setCheckable(True)
            tab.setStyleSheet(self._tab_qss())
            tab.setGeometry(_R(tx, ty, tw, th))
            tab.clicked.connect(
                lambda _checked=False, target=name: self._show_tab(target)
            )
            self._tab_buttons[name] = tab

        self._content = QStackedWidget(self)
        self._content.setGeometry(_R(*CONTENT_AT))
        self._intro_page = self._build_intro_page()
        self._outfit_page = self._build_outfit_page()
        self._content.addWidget(self._intro_page)
        self._content.addWidget(self._outfit_page)
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

    def _scroll_qss(self):
        return (
            "QScrollArea{border:none;background:transparent;}"
            "QScrollArea>QWidget>QWidget{background:transparent;}"
            "QScrollBar:vertical{background:#f3e4d2;width:8px;border-radius:4px;}"
            "QScrollBar::handle:vertical{background:#e0b48c;border-radius:4px;"
            "min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{"
            "height:0;width:0;}"
        )

    def _build_intro_page(self):
        """简介页（第十轮）：分节标签 + 数值 + 进度条（等级经验与三属性）。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._scroll_qss())
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(4)
        k = _SX * _FIT

        def styled_label(size, color, weight=600):
            label = QLabel()
            label.setWordWrap(True)
            label.setStyleSheet(
                f"font-family:'{APP_FONT_FAMILY}';font-size:{round(size * k)}px;"
                f"font-weight:{weight};color:{color};background:transparent;"
            )
            return label

        # 第十九轮：删名字大标题与全部进度条；字体统一商店琥珀色 #a8742c。
        self._intro_sections = {}
        self._intro_heads = {}
        self._level_bar = None
        self._affection_bar = None
        self._attr_bars = {}
        sections = (
            ("等级", "level"),
            ("好感度", "affection"),
            ("属性", "attrs"),
        )
        for title, key in sections:
            head = styled_label(27, "#d29a38")
            head.setText(f"『{title}』")
            layout.addWidget(head)
            self._intro_heads[key] = head
            value = styled_label(26, "#a8742c")
            layout.addWidget(value)
            self._intro_sections[key] = value
            # 进度条（第二十一轮恢复）：等级=经验、好感=好感值、属性=三项。
            if key == "level":
                self._level_bar = _MiniBar()
                layout.addWidget(self._level_bar)
            elif key == "affection":
                self._affection_bar = _MiniBar()
                layout.addWidget(self._affection_bar)
            else:
                for attr in ("hunger", "mood", "energy"):
                    bar = _MiniBar()
                    layout.addWidget(bar)
                    self._attr_bars[attr] = bar
            layout.addSpacing(24)
        # 性格。
        head = styled_label(27, "#d29a38")
        head.setText("『性格』")
        layout.addWidget(head)
        self._intro_heads["personality"] = head
        self._intro_sections["personality"] = styled_label(26, "#a8742c")
        layout.addWidget(self._intro_sections["personality"])
        layout.addStretch(1)
        scroll.setWidget(host)
        return scroll

    def _build_outfit_page(self):
        """套装页（第十轮）：大卡纵排，只上下滚动。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(self._scroll_qss())
        self._outfit_host = QWidget()
        self._outfit_layout = QVBoxLayout(self._outfit_host)
        self._outfit_layout.setContentsMargins(8, 8, 8, 8)
        self._outfit_layout.setSpacing(14)
        self._outfit_layout.addStretch(1)
        scroll.setWidget(self._outfit_host)
        return scroll

    def _show_tab(self, name):
        """切换分栏（并同步选中态）。"""
        pages = {"简介": self._intro_page, "套装": self._outfit_page}
        page = pages.get(name, self._intro_page)
        self._content.setCurrentWidget(page)
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
            if card.get("tag") is not None:
                card["tag"].setVisible(pet_id == active_id)

        self._refresh_intro(snapshot)
        self._refresh_outfits(snapshot)

    def _refresh_intro(self, snapshot):
        """简介页（第十九轮）：分节数值；名字在名字牌，进度条已删。"""
        self._name_label.setText(snapshot["name"])
        self._intro_sections["level"].setText(
            f"Lv.{snapshot['level']}　经验 {snapshot['xp']} / "
            f"{snapshot['xp_next']}"
        )
        self._intro_sections["affection"].setText(
            f"Lv.{snapshot['affection_level']}　"
            f"{snapshot['affection_points']} / {snapshot['affection_next']}"
        )
        self._affection_bar.set_ratio(
            snapshot["affection_points"], snapshot["affection_next"]
        )
        self._level_bar.set_ratio(snapshot["xp"], snapshot["xp_next"])
        self._intro_sections["attrs"].setText(
            f"饱腹 {snapshot['hunger']}　心情 {snapshot['mood']}　"
            f"精力 {snapshot['energy']}"
        )
        for key in ("hunger", "mood", "energy"):
            self._attr_bars[key].set_ratio(snapshot[key], 100)
        self._intro_sections["personality"].setText(snapshot["description"])

    def _refresh_outfits(self, snapshot):
        """套装页（第九轮）：只放大图卡，不加文字。"""
        while self._outfit_layout.count() > 1:
            item = self._outfit_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._outfit_widgets = []
        pet_id = snapshot["id"]
        for outfit in snapshot["outfits"]:
            art_name = OUTFIT_ART.get(outfit["id"])
            art_path = _pp_asset(art_name) if art_name else None
            if not art_path:
                art_path = _outfit_preview_path(pet_id, outfit)
            pixmap_label = QLabel()
            pixmap_label.setAlignment(Qt.AlignCenter)
            art = QPixmap(art_path) if art_path else QPixmap()
            if not art.isNull():
                w, h = OUTFIT_CARD_SIZE
                pixmap_label.setPixmap(art.scaled(
                    round(w * _SX * _FIT), round(h * _SY * _FIT),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                ))
            # 装备按钮（第十三轮）：叠在卡内底部居中（参考图样式），
            # 点击直接换装/卸下；素材烘焙「装备」白字。
            equip_asset = OUTFIT_EQUIP_BUTTON.get(outfit["id"])
            button = None
            if equip_asset and not pixmap_label.pixmap().isNull():
                button = QPushButton(pixmap_label)
                button.setCursor(Qt.PointingHandCursor)
                button.setFlat(True)
                button.setStyleSheet(
                    "QPushButton{border:none;background:transparent;}"
                    "QPushButton:hover{background:rgba(255,252,246,90);"
                    "border-radius:16px;}"
                    "QPushButton:pressed{background:rgba(70,42,28,70);"
                    "border-radius:16px;}"
                )
                btn_w = round(168 * _SX * _FIT)
                btn_h = round(53 * _SY * _FIT)
                button.setFixedSize(btn_w, btn_h)
                button.setIcon(QIcon(_pp_asset(equip_asset)))
                button.setIconSize(QSize(btn_w, btn_h))
                # 压在卡内底部，水平对齐描述文字块中心（参考图：
                # 文字在卡右侧 42%-98%，中心 ~70% 卡宽）。
                pm = pixmap_label.pixmap()
                text_center = round(pm.width() * 0.70)
                button.move(
                    text_center - btn_w // 2,
                    pm.height() - btn_h - round(14 * _SY * _FIT),
                )
                button.clicked.connect(
                    lambda _checked=False, oid=outfit["id"]: (
                        self._toggle_outfit(oid)
                    )
                )
                button.show()
            self._outfit_layout.insertWidget(
                self._outfit_layout.count() - 1, pixmap_label,
            )
            self._outfit_widgets.append(
                {"pixmap": pixmap_label, "button": button,
                 "outfit_id": outfit["id"]},
            )

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

    def _open_shop(self):
        opener = getattr(self.pet, "open_shop", None)
        if callable(opener):
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

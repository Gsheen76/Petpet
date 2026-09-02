"""宠物详情面板：数据快照纯函数 + 空壳页面（新素材逐轮搭建中）。

页面骨架（本轮）：background 原生尺寸 1201x1304，background + base_UI 两层，
整页圆角裁剪（CORNER_RADIUS），无边框可拖拽。内容区按用户后续指示逐轮加入。
"""

from __future__ import annotations

import os

from PyQt5.QtCore import QRect, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QApplication, QWidget

from petpet.app import pets as pet_registry
from petpet.app import state as app_state
from petpet.progression import core as progression

_NAME_DIALOG_FACTORY = None

_ASSET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets", "runtime", "ui", "pet_profile_new",
)

# 页面尺寸 = background.png 原生大小；布局坐标 = 该画布像素。
# DISPLAY_SCALE 为整体显示比例（用户定稿：2026-09-01 缩小 30%）；
# _S 为运行时缩放：默认显示比例，屏幕放不下时继续收缩（下限 0.55）。
ART_W, ART_H = 1201, 1304
DISPLAY_SCALE = 0.7
_S = DISPLAY_SCALE

# 整页圆角半径（用户定稿：比首版 30 更大）。
CORNER_RADIUS = 50

# 右上关闭按钮（base_UI 圆钮位已烘焙 X 图案，交互层克隆其像素做反馈）。
CLOSE_BUTTON_AT = (1068, 16, 94, 94)
CLOSE_KNOB_AT = (1076, 24, 78, 78)
CLOSE_PRESS_FLASH_MS = 40
CLOSE_CLICK_DEFER_MS = 80


def _R(x, y, w, h):
    """艺术稿坐标 → 实际画布几何。"""
    return QRect(round(x * _S), round(y * _S), round(w * _S), round(h * _S))


def _resolve_scale(screen_rect) -> float:
    """按目标屏幕自适应：上限显示比例，小屏按比例收缩，下限 0.55。"""
    if screen_rect is None or screen_rect.width() <= 0:
        return DISPLAY_SCALE
    by_h = (screen_rect.height() - 40) / ART_H
    by_w = (screen_rect.width() - 40) / ART_W
    return max(0.55, min(DISPLAY_SCALE, by_h, by_w))


def configure_name_dialog_factory(factory):
    """注入改名对话框类（定义在根模块 pet.py，包内不能直接 import）。"""
    global _NAME_DIALOG_FACTORY
    _NAME_DIALOG_FACTORY = factory


def _pp_asset(name):
    """素材绝对路径；不存在返回 None（单素材缺失不拖垮面板）。"""
    path = os.path.join(_ASSET_DIR, name)
    return path if os.path.isfile(path) else None


def _pp_pixmap(name, w, h):
    """缩放到目标尺寸的素材位图；缺失时返回空位图。"""
    path = _pp_asset(name)
    pixmap = QPixmap(path) if path else QPixmap()
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


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
        "affection_next": progression.affection_to_next(
            {"affection_level": affection_level}
        ),
        "avatar_path": pet_registry.pet_avatar_path(pet_id),
        "preview_path": pet_registry.pet_asset_path(pet_id, "desktop", "idle"),
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


class _CloseButton(QWidget):
    """右上关闭钮：X 图案烘焙在 base_UI 里，本件克隆圆钮像素做反馈层。

    悬停：放大 + 白洗 + 珊瑚描边（突出）；按下：两段式——缩小变暗 →
    回弹+高亮 → 关闭（与家园胶囊按键同节奏，常量 CLOSE_*_MS）。
    """

    def __init__(self, parent, knob_pixmap, on_activate):
        super().__init__(parent)
        self._knob = knob_pixmap
        self._on_activate = on_activate
        self.hovered = False
        self._phase = None  # None | "pressed" | "recover"
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance_phase)
        self.setCursor(Qt.PointingHandCursor)

    def geometry_from_art(self):
        self.setGeometry(_R(*CLOSE_BUTTON_AT))

    def _knob_rect(self):
        """当前状态下圆钮的绘制区（按钮矩形内居中，按相位缩放）。"""
        full = QRect(0, 0, self.width(), self.height())
        inset_x = (full.width() - round(CLOSE_KNOB_AT[2] * _S)) // 2
        inset_y = (full.height() - round(CLOSE_KNOB_AT[3] * _S)) // 2
        rect = full.adjusted(inset_x, inset_y, -inset_x, -inset_y)
        if self.hovered and self._phase is None:
            rect = rect.adjusted(-3, -3, 3, 3)
        elif self._phase == "pressed":
            rect = rect.adjusted(4, 4, -4, -4)
        return rect

    def paintEvent(self, event):
        if self._knob.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self._knob_rect()
        painter.drawPixmap(rect, self._knob)
        if self._phase == "pressed":
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(70, 42, 28, 120))
            painter.drawEllipse(rect)
        elif self.hovered or self._phase == "recover":
            painter.setPen(QPen(QColor("#f28f76"), max(2, round(3 * _S))))
            painter.setBrush(QColor(255, 252, 246, 70))
            painter.drawEllipse(rect.adjusted(1, 1, -1, -1))

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
    """宠物详情空壳页：background + base_UI + 圆角；内容逐轮按指示加入。

    所有按键加入时必须带悬停与点击反馈（AGENTS.md UI 约定）。
    """

    def __init__(self, pet, save_state):
        super().__init__()
        self.pet = pet
        self._save_state = (
            save_state if callable(save_state) else (lambda _state: None)
        )
        self._drag_offset = None

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        global _S
        screen = None
        rect = getattr(pet, "current_screen_rect", None)
        try:
            screen = rect() if callable(rect) else None
        except (RuntimeError, AttributeError):
            screen = None
        _S = _resolve_scale(screen)
        self.setFixedSize(round(ART_W * _S), round(ART_H * _S))
        self._background = _pp_pixmap("background.png", self.width(), self.height())
        # base_UI 原生 1201x1309 比页面高 5px：按宽度等比缩放，底部多出部分
        # 被圆角裁剪切掉（其内容止于 y875，无视觉影响），避免纵向压扁素材。
        base_path = _pp_asset("base_UI.png")
        base_native = QPixmap(base_path) if base_path else QPixmap()
        if not base_native.isNull():
            self._base_ui = base_native.scaledToWidth(
                self.width(), Qt.SmoothTransformation,
            )
            knob = base_native.copy(
                CLOSE_KNOB_AT[0], CLOSE_KNOB_AT[1],
                CLOSE_KNOB_AT[2], CLOSE_KNOB_AT[3],
            )
        else:
            self._base_ui = QPixmap()
            knob = QPixmap()
        self._close_button = _CloseButton(self, knob, self.close)
        self._close_button.geometry_from_art()

    def refresh(self):
        """预留：内容轮加入后在此刷新（当前壳无动态内容）。"""

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
        radius = CORNER_RADIUS * _S
        clip.addRoundedRect(0, 0, self.width(), self.height(),
                            radius, radius)
        painter.setClipPath(clip)
        if not self._background.isNull():
            painter.drawPixmap(0, 0, self._background)
        if not self._base_ui.isNull():
            painter.drawPixmap(0, 0, self._base_ui)

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

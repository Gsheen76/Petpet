"""宠物详情面板：展示数据快照与面板窗口。"""

from __future__ import annotations

import io
import os

import numpy as np
from PIL import Image as PILImage
from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from petpet.app.fonts import APP_FONT_FAMILY
from petpet.app import pets as pet_registry
from petpet.app import state as app_state
from petpet.progression import core as progression

_NAME_DIALOG_FACTORY = None

_ASSET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets", "runtime", "ui", "pet_profile",
)

# 画布基于素材原生尺寸（background.png 1201x1309）设计，布局坐标 = 艺术稿像素。
# 整体显示比例：用户定稿为艺术稿的 80%（2026-09-01 "整体缩小 20%"）；
# _S 为运行时缩放，屏幕放不下时在此基础上继续收缩。
ART_W, ART_H = 1201, 1309
DISPLAY_SCALE = 0.8
BASE_W, BASE_H = round(ART_W * DISPLAY_SCALE), round(ART_H * DISPLAY_SCALE)
_S = DISPLAY_SCALE

# 各物种的切换卡头像素材（无素材的物种回退 avatar.png）。
SPECIES_RAIL_ICON = {"lunch_meat": "pet_icon_1.png", "ice_cream": "pet_icon_2.png"}

_TEXT_BROWN = "#6b5646"
_TEXT_SOFT = "#8a7361"


def _R(x, y, w, h):
    """艺术稿坐标 → 实际画布几何。"""
    return QRect(round(x * _S), round(y * _S), round(w * _S), round(h * _S))


def _resolve_scale(screen_rect) -> float:
    """按目标屏幕自适应：默认艺术稿 80%，小屏按比例继续缩小，下限 0.55。"""
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


def _pp_pixmap(name, w=None, h=None, grayscale=False):
    """按需缩放的素材位图；缺失时返回空位图。"""
    path = _pp_asset(name)
    if not path:
        return QPixmap()
    pixmap = _grayscale_pixmap(path) if grayscale else QPixmap(path)
    if pixmap.isNull():
        return pixmap
    if w and h:
        pixmap = pixmap.scaled(round(w * _S), round(h * _S),
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


def _grayscale_pixmap(path):
    """灰阶化并保留 alpha 通道（Format_Grayscale8 会把透明变黑）。

    PIL + numpy 向量化：亮度写回 RGB、alpha 原样保留，经 PNG 缓冲转回 QPixmap。
    """
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


def _rounded_pixmap(path, w, h, radius, grayscale=False):
    """圆角卡片位图；路径缺失返回空位图。"""
    output = QPixmap(round(w * _S), round(h * _S))
    output.fill(Qt.transparent)
    if not path or not os.path.isfile(path):
        return output
    source = _grayscale_pixmap(path) if grayscale else QPixmap(path)
    if source.isNull():
        return output
    painter = QPainter(output)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, output.width(), output.height(),
                        radius * _S, radius * _S)
    painter.setClipPath(clip)
    scaled = source.scaled(
        output.width(), output.height(),
        Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
    )
    painter.drawPixmap(
        (output.width() - scaled.width()) // 2,
        (output.height() - scaled.height()) // 2, scaled,
    )
    painter.end()
    return output


class ArtBar(QWidget):
    """素材艺术条：轨迹为浅色圆角槽，填充按数值裁剪素材位图。"""

    def __init__(self, fill_asset, parent=None):
        super().__init__(parent)
        self._fill = _pp_pixmap(fill_asset)
        self._value = 0
        self._maximum = 1

    def set_ratio(self, value, maximum):
        self._value = max(0, int(value))
        self._maximum = max(1, int(maximum))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        track_path = QPainterPath()
        track_path.addRoundedRect(0, 0, w, h, h / 2, h / 2)
        painter.setPen(Qt.NoPen)
        # 轨迹槽：素材填充色的浅调（与艺术稿同族）。
        painter.setBrush(QColor(247, 233, 219))
        painter.drawPath(track_path)
        if self._fill.isNull() or self._value <= 0:
            return
        frac = max(0.0, min(1.0, self._value / self._maximum))
        fill_w = max(int(w * frac), h)
        fill_w = min(fill_w, w)
        painter.setClipPath(track_path)
        scaled = self._fill.scaled(
            w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation,
        )
        painter.drawPixmap(0, 0, fill_w, h, scaled)


def _label(parent, text, x, y, w, h, *, size=14, color=_TEXT_BROWN,
           bold=False, align=Qt.AlignLeft | Qt.AlignVCenter, name=None):
    """绝对定位文本标签的便捷工厂（坐标与字号按 _S 缩放）。"""
    label = QLabel(text, parent)
    if name:
        label.setObjectName(name)
    label.setAlignment(align)
    label.setWordWrap(False)
    style = (
        f"font-family:'{APP_FONT_FAMILY}';font-size:{round(size * _S)}px;"
        f"color:{color};background:transparent;"
    )
    if bold:
        style += "font-weight:600;"
    label.setStyleSheet(style)
    label.setGeometry(_R(x, y, w, h))
    return label


def _pixmap_label(parent, asset, x, y, w, h, grayscale=False):
    label = QLabel(parent)
    label.setPixmap(_pp_pixmap(asset, w, h, grayscale=grayscale))
    label.setScaledContents(True)
    label.setGeometry(_R(x, y, w, h))
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    return label


# ---- 艺术稿布局表（1201x1309 原生像素） ----
# 左栏 left_panel.png(297x1007) 的内部槽位（网格实测）：
#   圆窗 Ø190 中心(148,150)；名牌 y300-362；改名小圆钮 y516-560；
#   上胶囊 y712-762；下胶囊 y812-862。
LEFT_PANEL_AT = (36, 150)
AVATAR_CIRCLE = (53, 55, 190, 190)          # 圆窗（相对左栏）
NAME_PLATE = (48, 298, 201, 66)              # 名牌（相对左栏）
EDIT_BUTTON = (124, 514, 50, 50)             # 改名铅笔小圆钮（相对左栏）
USE_BUTTON = (72, 710, 154, 52)              # 装备胶囊（相对左栏）
RENAME_BUTTON = (96, 810, 106, 62)           # 改名钮素材位（相对左栏）

SWITCH_CARD_AT = ((790, 170), (988, 170))    # 右上双宠切换卡（各 175x212）
PREVIEW_AT = (390, 160, 390, 440)            # 右侧大立绘
INFO_ROW_Y = (640, 712, 784)                 # 等级/经验/好感三行
DESC_AT = (390, 876, 758, 72)                # 描述胶囊
OUTFIT_PANEL_AT = (368, 968)                 # outfit_panel 783x314
OUTFIT_CARD_REL = (43, 18)                   # 示例卡起点（相对 panel）
OUTFIT_CARD_STEP = 140                       # 卡间距
OUTFIT_SLOT_CIRCLE = (5, 0, 90, 90)          # 圆窗（相对卡）
OUTFIT_SLOT_NAME = (-10, 122, 120, 28)       # 名字（相对卡）
OUTFIT_SLOT_BUTTON = (8, 240, 84, 28)        # 按钮（相对卡）


def _left_abs(x, y, w, h):
    """左栏相对坐标 → 窗口坐标。"""
    return (LEFT_PANEL_AT[0] + x, LEFT_PANEL_AT[1] + y, w, h)


class PetProfileWindow(QWidget):
    """宠物详情面板：艺术稿原生画布上的形象、昵称、好感度、套装与切换。"""

    def __init__(self, pet, save_state):
        super().__init__()
        self.pet = pet
        self._save_state = (
            save_state if callable(save_state) else (lambda _state: None)
        )
        self._selected_pet_id = str(
            pet.state.get("active_pet_id", pet_registry.DEFAULT_PET_ID)
        )
        self._drag_offset = None
        self._name_dialog = None
        self._avatar_buttons = {}
        self._switch_card_names = {}
        self._outfit_cards = []
        self._detail_widgets = []
        self._locked_widgets = []
        self._art_labels = {}

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
        self._background = _pp_pixmap(
            "background.png", ART_W, ART_H,
        )

        self._build_canvas()
        self.refresh()

    # ---- 画布构建（绝对布局，坐标来自艺术稿） ----

    def _build_canvas(self):
        # 标题（自绘木牌在 paintEvent）+ 副标题素材。
        _pixmap_label(self, "title_text.png", 322, 56, 200, 34)
        close = QPushButton(self)
        close.setIcon(QIcon(_pp_pixmap("close_button.png", 64, 59)))
        close.setIconSize(QSize(round(64 * _S), round(59 * _S)))
        close.setFlat(True)
        close.setStyleSheet("QPushButton{border:none;background:transparent;}")
        close.setCursor(Qt.PointingHandCursor)
        close.setGeometry(_R(1112, 20, 64, 59))
        close.clicked.connect(self.close)

        # 左栏：圆窗头像 → 名牌 → 改名铅笔 → 装备胶囊 → 改名钮。
        _pixmap_label(self, "left_panel.png", *LEFT_PANEL_AT, 297, 1007)

        ax, ay, aw, ah = _left_abs(*AVATAR_CIRCLE)
        self._avatar_stage = QLabel(self)
        self._avatar_stage.setAlignment(Qt.AlignCenter)
        self._avatar_stage.setGeometry(_R(ax, ay, aw, ah))
        self._avatar_stage.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        nx, ny, nw, nh = _left_abs(*NAME_PLATE)
        self._name_label = _label(
            self, "", nx + 8, ny + 8, nw - 16, nh - 16, size=26, bold=True,
            align=Qt.AlignCenter, name="profileName",
        )

        ex, ey, ew, eh = _left_abs(*EDIT_BUTTON)
        edit_button = QPushButton(self)
        edit_icon = _pp_pixmap("edit_icon.png", ew, eh)
        if not edit_icon.isNull():
            edit_button.setIcon(QIcon(edit_icon))
        edit_button.setIconSize(QSize(round(ew * _S), round(eh * _S)))
        edit_button.setFlat(True)
        edit_button.setStyleSheet("QPushButton{border:none;background:transparent;}")
        edit_button.setCursor(Qt.PointingHandCursor)
        edit_button.setGeometry(_R(ex, ey, ew, eh))
        edit_button.clicked.connect(self._open_name_dialog)
        self._edit_button = edit_button
        self._detail_widgets.append(edit_button)

        ux, uy, uw, uh = _left_abs(*USE_BUTTON)
        use_button = QPushButton(self)
        use_icon = _pp_pixmap("equip_button_orange.png", uw, uh)
        if not use_icon.isNull():
            use_button.setIcon(QIcon(use_icon))
            use_button.setIconSize(QSize(round(uw * _S), round(uh * _S)))
        use_button.setFlat(True)
        use_button.setStyleSheet("QPushButton{border:none;background:transparent;}")
        use_button.setCursor(Qt.PointingHandCursor)
        use_button.setGeometry(_R(ux, uy, uw, uh))
        use_button.clicked.connect(
            lambda: self._switch_pet(self._selected_pet_id)
        )
        self._use_button = use_button
        self._detail_widgets.append(use_button)

        rx, ry, rw, rh = _left_abs(*RENAME_BUTTON)
        rename_button = QPushButton(self)
        rename_icon = _pp_pixmap("rename_button.png", rw, rh)
        if not rename_icon.isNull():
            rename_button.setIcon(QIcon(rename_icon))
            rename_button.setIconSize(QSize(round(rw * _S), round(rh * _S)))
        rename_button.setFlat(True)
        rename_button.setStyleSheet("QPushButton{border:none;background:transparent;}")
        rename_button.setCursor(Qt.PointingHandCursor)
        rename_button.setGeometry(_R(rx, ry, rw, rh))
        rename_button.clicked.connect(self._open_name_dialog)
        self._rename_button = rename_button
        self._detail_widgets.append(rename_button)

        # 右上双宠切换卡：头像素材 + 使用中徽章/未拥有锁 + 名字。
        for index, pet_id in enumerate(pet_registry.load_pet_registry()):
            if index >= len(SWITCH_CARD_AT):
                break
            card_x, card_y = SWITCH_CARD_AT[index]
            button = QPushButton(self)
            button.setObjectName("profileAvatarButton")
            button.setFlat(True)
            button.setStyleSheet("QPushButton{border:none;background:transparent;}")
            button.setCursor(Qt.PointingHandCursor)
            button.setGeometry(_R(card_x + 28, card_y + 14, 118, 118))
            button.setIconSize(QSize(112, 112))
            button.clicked.connect(
                lambda _checked=False, target=pet_id: self._select_pet(target)
            )
            badge = QLabel(self)
            badge.setPixmap(_pp_pixmap("in_use_tag.png", 100, 32))
            badge.setScaledContents(True)
            badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            badge.setAlignment(Qt.AlignCenter)
            badge.setGeometry(_R(card_x + 37, card_y + 130, 100, 32))
            lock = _label(
                self, "未拥有", card_x + 30, card_y + 138, 114, 22,
                size=13, color="#ffffff", align=Qt.AlignCenter, name="lockBadge",
            )
            lock.setStyleSheet(
                f"font-family:'{APP_FONT_FAMILY}';font-size:13px;"
                "color:#ffffff;background:#cfc4b8;border-radius:11px;"
                "padding:1px 10px;"
            )
            name = _label(
                self, "", card_x + 8, card_y + 172, 159, 28, size=17,
                bold=True, align=Qt.AlignCenter,
            )
            self._switch_card_names[pet_id] = name
            self._avatar_buttons[pet_id] = (button, badge, lock)

        # 右侧大立绘（站垫由 paintEvent 绘制）。
        self._preview_label = QLabel(self)
        self._preview_label.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self._preview_label.setGeometry(_R(*PREVIEW_AT))
        self._preview_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # 信息三行：烘焙标签素材 + 动态数值 + 艺术条。
        row_specs = (
            ("level_icon.png", "level_text.png", 66),
            ("exp_icon.png", "exp_text.png", 200),
            ("affection_icon.png", "affection_text.png", 158),
        )
        for row_y, (icon_asset, text_asset, text_w) in zip(INFO_ROW_Y, row_specs):
            self._detail_widgets.append(
                _pixmap_label(self, icon_asset, 396, row_y + 6, 30, 29)
            )
            art = _pixmap_label(self, text_asset, 444, row_y, text_w, 30)
            self._art_labels[text_asset] = art
            self._detail_widgets.append(art)

        self._level_label = _label(
            self, "", 700, INFO_ROW_Y[0], 140, 34, size=22, bold=True,
            name="profileLevel",
        )
        self._detail_widgets.append(self._level_label)

        self._exp_value = _label(
            self, "", 700, INFO_ROW_Y[1], 150, 32, size=16, color=_TEXT_SOFT,
        )
        self._detail_widgets.append(self._exp_value)
        self._xp_bar = ArtBar("exp_bar.png", self)
        self._xp_bar.setGeometry(_R(860, INFO_ROW_Y[1] + 5, 210, 22))
        self._detail_widgets.append(self._xp_bar)

        self._affection_label = _label(
            self, "", 700, INFO_ROW_Y[2], 150, 32, size=16, name="profileAffection",
        )
        self._detail_widgets.append(self._affection_label)
        self._aff_value = _label(
            self, "", 860, INFO_ROW_Y[2], 140, 32, size=16, color=_TEXT_SOFT,
        )
        self._detail_widgets.append(self._aff_value)
        self._aff_bar = ArtBar("affection_bar.png", self)
        self._aff_bar.setGeometry(_R(1010, INFO_ROW_Y[2] + 5, 150, 22))
        self._detail_widgets.append(self._aff_bar)
        self._detail_widgets.append(
            _pixmap_label(self, "heart_icon_small.png", 1170, INFO_ROW_Y[2] - 10, 54, 48)
        )

        # 描述胶囊。
        _pixmap_label(self, "description_bg.png", *DESC_AT)
        self._desc_label = _label(
            self, "", DESC_AT[0] + 18, DESC_AT[1] + 10,
            DESC_AT[2] - 36, DESC_AT[3] - 20, size=16, color=_TEXT_SOFT,
            align=Qt.AlignCenter,
        )
        self._detail_widgets.append(self._desc_label)

        # 套装区：outfit_panel 底板 + 示例卡几何的动态卡。
        self._outfit_panel_label = _pixmap_label(
            self, "outfit_panel.png", *OUTFIT_PANEL_AT, 783, 314,
        )
        outfit_title = _label(
            self, "套装", OUTFIT_PANEL_AT[0] + 22, OUTFIT_PANEL_AT[1] + 10,
            100, 28, size=18, bold=True, name="sectionTitle",
        )
        self._detail_widgets.append(outfit_title)

        # 锁定页部件（未拥有宠物）。
        self._locked_page = QWidget(self)
        self._locked_page.setGeometry(_R(390, 620, 760, 340))
        self._locked_page.setStyleSheet("background:transparent;")
        self._locked_hint = _label(
            self._locked_page, "", 20, 60, 720, 120, size=17, color=_TEXT_SOFT,
            align=Qt.AlignCenter,
        )
        self._locked_hint.setWordWrap(True)
        self._locked_shop = QPushButton("去商店购买", self._locked_page)
        self._locked_shop.setObjectName("lockedShopButton")
        self._locked_shop.setCursor(Qt.PointingHandCursor)
        self._locked_shop.setGeometry(_R(280, 200, 200, 48))
        self._locked_shop.clicked.connect(self._open_shop)
        self._locked_shop.setStyleSheet(
            "QPushButton{"
            f"font-family:'{APP_FONT_FAMILY}';font-size:20px;"
            "background:#f28f76;color:#ffffff;border:none;"
            "border-radius:24px;}"
            "QPushButton:hover{background:#ee7c60;}"
        )

        # 底部状态行。
        self.status_label = _label(
            self, "", 36, 1224, 1129, 30, size=15, color="#a06b5e",
            align=Qt.AlignCenter, name="status",
        )

    # ---- 数据刷新 ----

    def refresh(self):
        state = self.pet.state
        active_id = state.get("active_pet_id", pet_registry.DEFAULT_PET_ID)
        snapshot = pet_profile_snapshot(state, self._selected_pet_id)

        for pet_id, parts in self._avatar_buttons.items():
            button, badge, lock = parts
            owned = (
                pet_id == active_id
                or pet_id in (state.get("owned_pet_ids") or ())
            )
            icon_name = SPECIES_RAIL_ICON.get(pet_id)
            icon_path = (
                _pp_asset(icon_name) if icon_name
                else pet_registry.pet_avatar_path(pet_id)
            )
            button.setIcon(QIcon(_rounded_pixmap(
                icon_path, 112, 112, 56, grayscale=not owned,
            )))
            badge.setVisible(pet_id == active_id)
            lock.setVisible(not owned)
            name = self._switch_card_names.get(pet_id)
            if name is not None:
                pet_snapshot = pet_profile_snapshot(state, pet_id)
                name.setText(pet_snapshot["name"])

        # 左栏圆窗显示选中宠物头像；装备按钮只在「选中≠当前且已拥有」时可点。
        icon_name = SPECIES_RAIL_ICON.get(snapshot["id"])
        stage_path = (
            _pp_asset(icon_name) if icon_name
            else snapshot.get("avatar_path")
        )
        if snapshot["owned"]:
            self._avatar_stage.setPixmap(_rounded_pixmap(
                stage_path, 176, 176, 88,
            ))
        else:
            self._avatar_stage.setPixmap(_rounded_pixmap(
                stage_path, 176, 176, 88, grayscale=True,
            ))
        self._use_button.setEnabled(
            snapshot["owned"] and snapshot["id"] != active_id
        )
        if not self._use_button.isEnabled():
            self._use_button.setCursor(Qt.ArrowCursor)
        else:
            self._use_button.setCursor(Qt.PointingHandCursor)

        if snapshot["owned"]:
            self._show_detail(snapshot)
        else:
            self._show_locked(snapshot)

    def _load_preview_pixmap(self, snapshot, height_px, grayscale=False):
        """立绘位图：优先桌面 idle，回退头像；grayscale 用于锁定页。"""
        path = snapshot.get("preview_path") or ""
        if not os.path.isfile(path):
            path = snapshot.get("avatar_path") or ""
        if not os.path.isfile(path):
            return QPixmap()
        if grayscale:
            pixmap = _grayscale_pixmap(path)
        else:
            pixmap = QPixmap(path)
        if pixmap.isNull():
            return QPixmap()
        return pixmap.scaledToHeight(round(height_px * _S),
                                      Qt.SmoothTransformation)

    def _show_detail(self, snapshot):
        for widget in self._locked_widgets:
            widget.setVisible(False)
        for widget in self._detail_widgets:
            widget.setVisible(True)
        self._locked_page.setVisible(False)

        self._preview_label.setPixmap(self._load_preview_pixmap(snapshot, 430))
        self._name_label.setText(snapshot["name"])
        self._level_label.setText(f"Lv.{snapshot['level']}")
        self._exp_value.setText(
            f"{snapshot['xp']} / {snapshot['xp_next']}"
        )
        self._xp_bar.set_ratio(snapshot["xp"], snapshot["xp_next"])
        self._affection_label.setText(f"好感度 Lv.{snapshot['affection_level']}")
        self._aff_value.setText(
            f"{snapshot['affection_points']} / {snapshot['affection_next']}"
        )
        self._aff_bar.set_ratio(
            snapshot["affection_points"], snapshot["affection_next"]
        )
        self._desc_label.setText(snapshot["description"])
        self._refresh_outfits(snapshot)

    def _show_locked(self, snapshot):
        for widget in self._detail_widgets:
            widget.setVisible(False)
        for widget in self._locked_widgets:
            widget.setVisible(True)
        self._locked_page.setVisible(True)
        self._clear_outfits()

        self._preview_label.setPixmap(
            self._load_preview_pixmap(snapshot, 400, grayscale=True)
        )
        self._name_label.setText(snapshot["name"])
        self._locked_hint.setText(
            f"{snapshot['description']}\n"
            f"还未拥有，{snapshot['price']} Pet币 就能带它回家。"
        )

    def _clear_outfits(self):
        for card in self._outfit_cards:
            card.hide()
            card.deleteLater()
        self._outfit_cards = []

    def _refresh_outfits(self, snapshot):
        self._clear_outfits()
        if not snapshot["outfits"]:
            empty = _label(
                self, "这只宠物的套装正在准备中，敬请期待～",
                OUTFIT_PANEL_AT[0] + 120, OUTFIT_PANEL_AT[1] + 150,
                540, 30, size=16, color=_TEXT_SOFT,
                align=Qt.AlignCenter,
            )
            self._outfit_cards.append(empty)
            empty.show()
            return

        pet_id = snapshot["id"]
        base_x = OUTFIT_PANEL_AT[0] + OUTFIT_CARD_REL[0]
        base_y = OUTFIT_PANEL_AT[1] + OUTFIT_CARD_REL[1]
        for index, outfit in enumerate(snapshot["outfits"]):
            card = QWidget(self)
            card_x = base_x + index * OUTFIT_CARD_STEP
            card.setGeometry(_R(card_x, base_y, 100, 268))
            card.setToolTip(outfit["description"])

            preview = QLabel(card)
            preview.setAlignment(Qt.AlignCenter)
            sx, sy, sw, sh = OUTFIT_SLOT_CIRCLE
            preview.setGeometry(_R(sx, sy, sw, sh))
            pixmap = QPixmap(_outfit_preview_path(pet_id, outfit) or "")
            if not pixmap.isNull():
                preview.setPixmap(
                    pixmap.scaledToHeight(round(84 * _S), Qt.SmoothTransformation)
                )
            preview.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            name = _label(
                card, outfit["name"],
                OUTFIT_SLOT_NAME[0], OUTFIT_SLOT_NAME[1],
                OUTFIT_SLOT_NAME[2], OUTFIT_SLOT_NAME[3],
                size=15, bold=True, align=Qt.AlignCenter,
            )
            name.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            if outfit["equipped"]:
                button = self._art_button(
                    "equip_button_green.png", "卸下", "#8fbf7f", card
                )
                button.clicked.connect(
                    lambda _checked=False: self._apply_outfit(equip=False)
                )
            elif outfit["owned"]:
                button = self._art_button(
                    "equip_button_orange.png", "装备", "#f49a8a", card
                )
                button.clicked.connect(
                    lambda _checked=False, oid=outfit["id"]:
                        self._apply_outfit(oid, equip=True)
                )
            else:
                button = self._pill_button(
                    f"商店·{outfit['price']}币", "#f28f76", card
                )
                button.clicked.connect(self._open_shop)
            bx, by, bw, bh = OUTFIT_SLOT_BUTTON
            button.setGeometry(_R(bx, by, bw, bh))
            card._action_button = button
            card.show()
            self._outfit_cards.append(card)

    def _art_button(self, asset, fallback_text, fallback_color, parent):
        """素材贴图按钮（装备/卸下），无字素材时回退胶囊。"""
        bx, by, bw, bh = OUTFIT_SLOT_BUTTON
        icon = _pp_pixmap(asset, bw, bh)
        button = QPushButton(parent)
        button.setCursor(Qt.PointingHandCursor)
        if icon.isNull():
            return self._pill_button(fallback_text, fallback_color, parent)
        button.setFlat(True)
        button.setStyleSheet("QPushButton{border:none;background:transparent;}")
        button.setIcon(QIcon(icon))
        button.setIconSize(QSize(round(bw * _S), round(bh * _S)))
        return button

    def _pill_button(self, text, color, parent):
        # 注意：Qt 样式表里裸声明与规则块混用会导致规则被丢弃，
        # 字体声明必须放进规则块内部。
        button = QPushButton(text, parent)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton{"
            f"font-family:'{APP_FONT_FAMILY}';font-size:13px;"
            f"background:{color};color:#ffffff;border:none;"
            "border-radius:14px;}"
        )
        return button

    def _select_pet(self, pet_id):
        self._selected_pet_id = pet_id
        snapshot = pet_profile_snapshot(self.pet.state, pet_id)
        if not snapshot["owned"]:
            self.refresh()
            self.status_label.setText("还没有拥有这只宠物，去商店看看吧～")
            return
        active_id = self.pet.state.get(
            "active_pet_id", pet_registry.DEFAULT_PET_ID
        )
        self.refresh()
        if pet_id != active_id:
            self.status_label.setText(
                f"已选中 {snapshot['name']}，点左下「装备」让它陪你了～"
            )

    def _switch_pet(self, pet_id):
        snapshot = pet_profile_snapshot(self.pet.state, pet_id)
        if not snapshot["owned"]:
            self.status_label.setText("还没有拥有这只宠物，去商店看看吧～")
            return
        previous_selection = self._selected_pet_id
        self._selected_pet_id = pet_id
        result = self.pet.set_active_pet(pet_id)
        if isinstance(result, dict) and result.get("ok") is False:
            self._selected_pet_id = previous_selection
            self.refresh()
            self.status_label.setText(
                result.get("message", "切换失败，稍后再试。")
            )
            return
        self.refresh()
        self.status_label.setText(
            f"已切换到 {snapshot['name']}，桌面和小屋都换它陪你了～"
        )

    def _apply_outfit(self, outfit_id=None, equip=True):
        if equip:
            result = progression.equip_outfit(self.pet.state, outfit_id)
        else:
            result = progression.unequip_outfit(self.pet.state)
        if result.get("ok"):
            self._save_state(self.pet.state)
            self.pet.update()
            home = getattr(self.pet, "home_scene_window", None)
            refresh_home = getattr(home, "refresh_pet_assets", None)
            if callable(refresh_home):
                refresh_home()
        self.refresh()
        self.status_label.setText(result.get("message", "装扮状态没有改变。"))

    def _open_shop(self):
        opener = getattr(self.pet, "open_shop", None)
        if callable(opener):
            opener()

    def _open_name_dialog(self):
        if _NAME_DIALOG_FACTORY is None:
            return
        snapshot = pet_profile_snapshot(self.pet.state, self._selected_pet_id)
        dialog = _NAME_DIALOG_FACTORY(snapshot["name"], self._commit_name, None)
        self._name_dialog = dialog
        dialog.exec_()
        self._name_dialog = None
        self.refresh()

    def _commit_name(self, new_name):
        if not (isinstance(new_name, str) and new_name.strip()):
            return
        setter = getattr(self.pet, "set_pet_name", None)
        if callable(setter):
            setter(new_name.strip())
        self._save_state(self.pet.state)
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
        if not self._background.isNull():
            painter.drawPixmap(0, 0, self._background)
        # 标题木牌（艺术稿无独立切图，按素材同族配色绘制）。
        rect = _R(36, 14, 264, 92)
        painter.setPen(QPen(QColor(232, 178, 122), 3))
        painter.setBrush(QColor(250, 233, 205, 255))
        painter.drawRoundedRect(rect, 26, 26)
        painter.setPen(QPen(QColor(232, 178, 122, 160), 2, Qt.DashLine))
        painter.drawRoundedRect(rect.adjusted(6, 6, -6, -6), 20, 20)
        painter.setPen(QColor(_TEXT_BROWN))
        font = painter.font()
        font.setFamily(APP_FONT_FAMILY)
        font.setBold(True)
        font.setPixelSize(max(1, round(34 * _S)))
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, "宠物")
        # 立绘下的粉色蕾丝站垫（素材无独立切图，按参考图同色绘制）。
        mat = _R(400, 548, 370, 70)
        painter.setPen(QColor(246, 205, 200))
        painter.setBrush(QColor(250, 222, 218, 235))
        painter.drawEllipse(mat)
        painter.setBrush(QColor(253, 236, 232, 235))
        painter.drawEllipse(mat.adjusted(16, 8, -16, -12))

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

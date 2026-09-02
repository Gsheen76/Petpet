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
from PyQt5.QtCore import QRect, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QStackedWidget,
                             QVBoxLayout, QWidget)

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

# 页面尺寸 = background.png 原生大小；布局坐标 = 该画布像素。
# DISPLAY_SCALE 为整体显示比例（用户定稿：2026-09-01 缩小 30%）；
# _S 为运行时缩放：默认显示比例，屏幕放不下时继续收缩（下限 0.55）。
ART_W, ART_H = 1201, 1304
DISPLAY_SCALE = 0.7
_S = DISPLAY_SCALE

# 整页圆角半径（用户定稿：逐轮加大，当前 64）。
CORNER_RADIUS = 64

# 右上关闭按钮（close_button.png 素材，放回原 base_UI 圆钮位）。
CLOSE_BUTTON_AT = (1083, 23, 76, 70)
CLOSE_PRESS_FLASH_MS = 40
CLOSE_CLICK_DEFER_MS = 80

# 图1 左栏宠物卡（background 烘焙卡片 x85-334 y208-1089 内部两张）。
# 用户定稿（第四轮）：头像放大到 180、两卡靠近；卡下名字与「使用中」pill 删除。
PET_CARD_SLOTS = ((103, 243), (103, 547))
PET_CARD_SIZE = (180, 180)

# 图2 待机动画：垫 x437-975 y515-639，狗底部对齐垫，高约 350。
IDLE_PREVIEW_RECT = (460, 230, 480, 390)
IDLE_FRAME_HEIGHT = 360
IDLE_FPS = 8

# 分栏（description_bg）：待机动画正下方；两页「简介 / 套装」，更多页后续加。
TAB_BAR_AT = (336, 660, 728, 69)
TAB_SLOTS = {
    "简介": (396, 672, 140, 46),
    "套装": (546, 672, 140, 46),
}
CONTENT_AT = (336, 748, 728, 456)

# 套装素材（新 art 直接按套装 id 映射；未映射回退 idle 预览路径）。
OUTFIT_ART = {
    "strawberry_suit": "outfit_strawberry.png",
    "dinosaur_suit": "outfit_diansour.png",
}
OUTFIT_CARD_SIZE = (330, 210)


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


def _pp_pixmap(name, w=None, h=None):
    """按需缩放的素材位图；缺失时返回空位图。"""
    path = _pp_asset(name)
    pixmap = QPixmap(path) if path else QPixmap()
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
                    round(height * _S), Qt.SmoothTransformation,
                ))
    except (OSError, ValueError):
        return frames
    return frames


class _CloseButton(QWidget):
    """右上关闭钮：close_button.png 素材（自有像素，可自由缩放/洗色）。

    悬停：放大 + 白洗；按下：两段式——缩小变暗 → 回弹白洗 → 关闭
    （与家园胶囊按键同节奏，常量 CLOSE_*_MS）。
    """

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

    def geometry_from_art(self):
        self.setGeometry(_R(*CLOSE_BUTTON_AT))

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
            painter.drawPixmap(rect, self._art)
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
        global _S
        screen = None
        rect = getattr(pet, "current_screen_rect", None)
        try:
            screen = rect() if callable(rect) else None
        except (RuntimeError, AttributeError):
            screen = None
        _S = _resolve_scale(screen)
        self.setFixedSize(round(ART_W * _S), round(ART_H * _S))
        self._background = _pp_pixmap("background.png", ART_W, ART_H)
        # base_UI 已按用户指示撤下（第六轮）；第七轮：新 UI 素材逐个接入。
        self._close_button = _CloseButton(
            self, _pp_pixmap("close_button.png"), self.close,
        )
        self._close_button.geometry_from_art()

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
            f"font-family:'{APP_FONT_FAMILY}';font-size:{round(size * _S)}px;"
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
        # 图1：左栏宠物切换卡（pet_icon 素材；名字/使用中已按用户指示删除）。
        for index, pet_id in enumerate(pet_registry.load_pet_registry()):
            if index >= len(PET_CARD_SLOTS):
                break
            card_x, card_y = PET_CARD_SLOTS[index]
            button = QPushButton(self)
            button.setFlat(True)
            button.setStyleSheet("QPushButton{border:none;background:transparent;}")
            button.setCursor(Qt.PointingHandCursor)
            button.setGeometry(_R(card_x, card_y, *PET_CARD_SIZE))
            button.clicked.connect(
                lambda _checked=False, target=pet_id: self._select_pet(target)
            )
            self._pet_cards[pet_id] = {"button": button}

        # 图2：待机动画位（垫上，底部对齐）。
        self._idle_label = QLabel(self)
        self._idle_label.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self._idle_label.setGeometry(_R(*IDLE_PREVIEW_RECT))
        self._idle_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

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
        """分栏按钮样式：选中珊瑚、悬停白洗、按压压暗（两态反馈必备）。"""
        font_px = round(20 * _S)
        return (
            "QPushButton{"
            f"font-family:'{APP_FONT_FAMILY}';font-size:{font_px}px;"
            "color:#6b5646;background:transparent;border:none;"
            "border-radius:20px;}"
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._scroll_qss())
        self._intro_label = QLabel()
        self._intro_label.setWordWrap(True)
        self._intro_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._intro_label.setStyleSheet(
            f"font-family:'{APP_FONT_FAMILY}';font-size:{round(21 * _S)}px;"
            "color:#6b5646;background:transparent;padding:6px;"
        )
        scroll.setWidget(self._intro_label)
        return scroll

    def _build_outfit_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._scroll_qss())
        self._outfit_host = QWidget()
        self._outfit_layout = QHBoxLayout(self._outfit_host)
        self._outfit_layout.setContentsMargins(8, 8, 8, 8)
        self._outfit_layout.setSpacing(16)
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
            card["button"].setIcon(QIcon(icon))
            card["button"].setIconSize(QSize(*[
                round(value * _S) for value in PET_CARD_SIZE
            ]))

        self._refresh_intro(snapshot)
        self._refresh_outfits(snapshot)

    def _refresh_intro(self, snapshot):
        """简介页：名字（初始名括注）→ 好感度 → 属性值 → 性格介绍。"""
        if snapshot["name"] == snapshot["default_name"]:
            name_part = snapshot["default_name"]
        else:
            name_part = f"{snapshot['name']}（{snapshot['default_name']}）"
        px = round(21 * _S)
        small_px = round(19 * _S)
        color = "#6b5646"
        soft = "#8a7361"
        self._intro_label.setText(
            f"<div style='line-height:1.7'>"
            f"<p style='margin:2px 0'><span style='font-size:{px}px;"
            f"font-weight:600;color:{color}'>{name_part}</span></p>"
            f"<p style='margin:2px 0;font-size:{small_px}px;color:{color}'>"
            f"好感度 Lv.{snapshot['affection_level']}"
            f"（{snapshot['affection_points']} / "
            f"{snapshot['affection_next']}）</p>"
            f"<p style='margin:2px 0;font-size:{small_px}px;color:{color}'>"
            f"饱腹 {snapshot['hunger']} · 心情 {snapshot['mood']} · "
            f"精力 {snapshot['energy']}</p>"
            f"<p style='margin:8px 0 2px;font-size:{small_px}px;"
            f"color:{soft}'>{snapshot['description']}</p>"
            f"</div>"
        )

    def _refresh_outfits(self, snapshot):
        """套装页：当前宠物套装卡（新素材图 + 名称）。"""
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
            card = QWidget()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            pixmap_label = QLabel()
            pixmap_label.setAlignment(Qt.AlignCenter)
            art = QPixmap(art_path) if art_path else QPixmap()
            if not art.isNull():
                w, h = OUTFIT_CARD_SIZE
                pixmap_label.setPixmap(art.scaled(
                    round(w * _S), round(h * _S),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                ))
            name_label = QLabel(outfit["name"])
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setStyleSheet(
                f"font-family:'{APP_FONT_FAMILY}';"
                f"font-size:{round(17 * _S)}px;font-weight:600;"
                "color:#6b5646;background:transparent;"
            )
            layout.addWidget(pixmap_label)
            layout.addWidget(name_label)
            self._outfit_layout.insertWidget(
                self._outfit_layout.count() - 1, card,
            )
            self._outfit_widgets.append(
                {"pixmap": pixmap_label, "name": name_label},
            )

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
        radius = CORNER_RADIUS * _S
        clip.addRoundedRect(0, 0, self.width(), self.height(),
                            radius, radius)
        painter.setClipPath(clip)
        if not self._background.isNull():
            painter.drawPixmap(0, 0, self._background)

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

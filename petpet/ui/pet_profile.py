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
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QWidget

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

# 右上关闭按钮：X 圆钮烘焙在 base_UI 原位（还原，不擦不克隆），
# 交互层为纯透明覆盖，反馈只用半透明洗色（悬停白洗、按压暗洗）。
CLOSE_BUTTON_AT = (1082, 22, 78, 79)
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

# 图3 名字牌（base_UI 烘焙 x564-869 y620-679，改名红钮在牌右端）。
NAME_PLATE_AT = (564, 620, 305, 59)
NAME_LABEL_AT = (584, 624, 180, 51)
RENAME_BUTTON_AT = (775, 624, 86, 52)

# 图4 数值两行：background 已烘焙星/心图标（第一列 x~396 y696/752），
# 文本放图标右侧；第一排等级，第二排好感。
LEVEL_ROW_AT = (444, 684)
AFFECTION_ROW_AT = (444, 740)
ROW_TEXT_SIZE = (260, 46)


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
    """右上关闭钮：X 图案原样烘焙在 base_UI 里（还原），本件是纯透明覆盖。

    悬停：白洗提亮；按下：两段式——暗洗 → 回弹白洗 → 关闭
    （与家园胶囊按键同节奏，常量 CLOSE_*_MS）。不克隆/移动/擦除原画。
    """

    def __init__(self, parent, on_activate):
        super().__init__(parent)
        self._on_activate = on_activate
        self.hovered = False
        self._phase = None  # None | "pressed" | "recover"
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance_phase)
        self.setCursor(Qt.PointingHandCursor)

    def geometry_from_art(self):
        self.setGeometry(_R(*CLOSE_BUTTON_AT))

    def _overlay_rect(self):
        """洗色椭圆范围（按钮内居中，按压时略收缩）。"""
        full = QRect(0, 0, self.width(), self.height())
        rect = full.adjusted(8, 8, -8, -8)
        if self._phase == "pressed":
            rect = rect.adjusted(3, 3, -3, -3)
        return rect

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self._overlay_rect()
        painter.setPen(Qt.NoPen)
        if self._phase == "pressed":
            painter.setBrush(QColor(70, 42, 28, 120))
            painter.drawEllipse(rect)
        elif self.hovered or self._phase == "recover":
            painter.setBrush(QColor(255, 252, 246, 80))
            painter.drawEllipse(rect)

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
        self._background = _pp_pixmap("background.png", self.width(), self.height())
        # base_UI 已按用户指示撤下（第六轮）：其元素（标题横幅/X 圆钮/名字牌/
        # 心气泡/描述胶囊）等新 UI 素材到位后逐个重接。关闭键暂以原位透明
        # 覆盖层保底（悬停显洗色），新素材到位后重新定位。
        self._close_button = _CloseButton(self, self.close)
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

        # 图3：名字 + 改名交互键（改名红钮已烘焙在 base_UI 牌右端）。
        self._name_label = self._label(
            "", *NAME_LABEL_AT, size=30, bold=True, align=Qt.AlignCenter,
        )
        self._rename_button = QPushButton(self)
        self._rename_button.setFlat(True)
        self._rename_button.setStyleSheet(
            "QPushButton{border:none;background:transparent;}"
        )
        self._rename_button.setCursor(Qt.PointingHandCursor)
        self._rename_button.setGeometry(_R(*RENAME_BUTTON_AT))
        self._rename_button.clicked.connect(self._open_name_dialog)

        # 图4：第一排等级、第二排好感（星/心图标已烘焙在 background，
        # 文本放第一列图标右侧）。
        lx, ly = LEVEL_ROW_AT
        self._level_label = self._label(
            "", lx, ly, *ROW_TEXT_SIZE, size=26, bold=True,
        )
        ax, ay = AFFECTION_ROW_AT
        self._affection_label = self._label(
            "", ax, ay, *ROW_TEXT_SIZE, size=26, bold=True,
        )

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

        self._name_label.setText(snapshot["name"])
        self._level_label.setText(f"Lv.{snapshot['level']}")
        self._affection_label.setText(f"好感度 Lv.{snapshot['affection_level']}")

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

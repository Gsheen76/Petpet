"""宠物详情面板：展示数据快照与面板窗口。"""

from __future__ import annotations

import os

from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPixmap
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

# 画布按素材艺术稿等比设计（艺术稿 1201x1309）。
CANVAS_W, CANVAS_H = 800, 872

# 各物种的左栏卡头像素材（无素材的物种回退 avatar.png）。
SPECIES_RAIL_ICON = {"lunch_meat": "pet_icon_1.png", "ice_cream": "pet_icon_2.png"}

_TEXT_BROWN = "#6b5646"
_TEXT_SOFT = "#8a7361"


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
    pixmap = QPixmap(path) if path else QPixmap()
    if pixmap.isNull():
        return pixmap
    if grayscale:
        image = pixmap.toImage().convertToFormat(QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(image)
    if w and h:
        pixmap = pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
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
    """灰阶化但保留 alpha 通道（Format_Grayscale8 会把透明变黑）。"""
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return pixmap
    image = pixmap.toImage()
    gray = image.convertToFormat(QImage.Format_Grayscale8)
    result = gray.convertToFormat(QImage.Format_ARGB32)
    # 把原图 alpha 逐像素拷回。
    for y in range(result.height()):
        for x in range(result.width()):
            result.setPixel(x, y, (image.pixel(x, y) & 0xFF000000) | 0x00FFFFFF)
    return QPixmap.fromImage(result)


def _rounded_pixmap(path, w, h, radius, grayscale=False):
    """圆角卡片位图；路径缺失返回空位图。"""
    output = QPixmap(w, h)
    output.fill(Qt.transparent)
    if not path or not os.path.isfile(path):
        return output
    source = QPixmap(path)
    if source.isNull():
        return output
    if grayscale:
        image = source.toImage().convertToFormat(QImage.Format_Grayscale8)
        source = QPixmap.fromImage(image)
    painter = QPainter(output)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, w, h, radius, radius)
    painter.setClipPath(clip)
    scaled = source.scaled(
        w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
    )
    painter.drawPixmap(
        (w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled,
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
        painter.setBrush(Qt.NoBrush)
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
    """绝对定位文本标签的便捷工厂。"""
    label = QLabel(text, parent)
    if name:
        label.setObjectName(name)
    label.setAlignment(align)
    label.setWordWrap(False)
    style = (
        f"font-family:'{APP_FONT_FAMILY}';font-size:{size}px;"
        f"color:{color};background:transparent;"
    )
    if bold:
        style += "font-weight:600;"
    label.setStyleSheet(style)
    label.setGeometry(QRect(x, y, w, h))
    return label


def _pixmap_label(parent, asset, x, y, w, h, grayscale=False):
    label = QLabel(parent)
    label.setPixmap(_pp_pixmap(asset, w, h, grayscale=grayscale))
    label.setScaledContents(True)
    label.setGeometry(QRect(x, y, w, h))
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    return label


class PetProfileWindow(QWidget):
    """宠物详情面板：艺术稿画布上的形象、昵称、好感度、套装与切换。"""

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
        self._outfit_cards = []
        self._detail_widgets = []
        self._locked_widgets = []

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(CANVAS_W, CANVAS_H)
        self._background = _pp_pixmap("background.png", CANVAS_W, CANVAS_H)
        # 标题木牌只在完整组合图里，裁其左上角区域叠加。
        main_art = _pp_pixmap("main_panel.png")
        if main_art.isNull():
            self._plaque = QPixmap()
        else:
            self._plaque = main_art.copy(10, 0, 420, 150).scaled(
                280, 100, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )

        self._build_canvas()
        self.refresh()

    # ---- 画布构建（绝对布局，坐标来自艺术稿等比换算） ----

    def _build_canvas(self):
        # 副标题（title_text 实为「我的伙伴与套装」文案）。
        _pixmap_label(self, "title_text.png", 40, 112, 175, 30)
        close = QPushButton(self)
        close.setIcon(QIcon(_pp_pixmap("close_button.png", 51, 47)))
        close.setIconSize(QSize(51, 47))
        close.setFlat(True)
        close.setStyleSheet("QPushButton{border:none;background:transparent;}")
        close.setCursor(Qt.PointingHandCursor)
        close.setGeometry(QRect(726, 12, 51, 47))
        close.clicked.connect(self.close)

        # 左栏切换卡： species 头像 + 名字 + 使用中/未拥有 标签。
        rail = _pixmap_label(self, "left_panel.png", 27, 128, 198, 675)
        self._rail = rail
        rail_bottom = 128 + 675
        slot_y = (160, 372)
        for index, pet_id in enumerate(pet_registry.load_pet_registry()):
            if index >= len(slot_y):
                # 满两席后不再放置卡位（当前仅两只宠物）。
                break
            button_y, name_y, tag_y = (
                slot_y[index], slot_y[index] + 140, slot_y[index] + 166
            )
            button = QPushButton(self)
            button.setObjectName("profileAvatarButton")
            button.setFlat(True)
            button.setStyleSheet(
                "QPushButton{border:none;background:transparent;}"
            )
            button.setCursor(Qt.PointingHandCursor)
            button.setGeometry(QRect(66, button_y, 120, 120))
            button.setIconSize(QSize(112, 112))
            button.clicked.connect(
                lambda _checked=False, target=pet_id: self._select_pet(target)
            )
            name = _label(
                self, "", 27, name_y, 198, 22,
                size=16, bold=True, align=Qt.AlignCenter,
            )
            badge = QLabel(self)
            badge.setPixmap(_pp_pixmap("in_use_tag.png", 96, 31))
            badge.setScaledContents(True)
            badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            badge.setAlignment(Qt.AlignCenter)
            badge.setGeometry(QRect(78, tag_y, 96, 31))
            lock = _label(
                self, "🔒 未拥有", 27, tag_y, 198, 24,
                size=12, color="#ffffff", align=Qt.AlignCenter, name="lockBadge",
            )
            lock.setStyleSheet(
                f"font-family:'{APP_FONT_FAMILY}';font-size:12px;"
                "color:#ffffff;background:#cfc4b8;border-radius:9px;"
                "padding:1px 9px;"
            )
            self._avatar_buttons[pet_id] = (button, badge, lock)

        # 右侧大立绘（粉色站垫由 paintEvent 绘制）。
        self._preview_label = QLabel(self)
        self._preview_label.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self._preview_label.setGeometry(QRect(330, 110, 340, 300))
        self._preview_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # 名牌 + 铅笔 + 改名钮。
        _pixmap_label(self, "name_plate.png", 300, 408, 266, 50)
        self._name_label = _label(
            self, "", 318, 414, 150, 38, size=24, bold=True,
            align=Qt.AlignCenter, name="profileName",
        )
        edit_button = QPushButton(self)
        edit_icon = _pp_pixmap("edit_icon.png", 24, 25)
        if not edit_icon.isNull():
            edit_button.setIcon(QIcon(edit_icon))
        edit_button.setIconSize(QSize(24, 25))
        edit_button.setFlat(True)
        edit_button.setStyleSheet("QPushButton{border:none;background:transparent;}")
        edit_button.setCursor(Qt.PointingHandCursor)
        edit_button.setGeometry(QRect(470, 420, 26, 27))
        edit_button.clicked.connect(self._open_name_dialog)
        self._edit_button = edit_button
        self._detail_widgets.append(edit_button)
        rename_button = QPushButton(self)
        rename_icon = _pp_pixmap("rename_button.png", 71, 41)
        rename_button.setIcon(QIcon(rename_icon))
        rename_button.setIconSize(QSize(71, 41))
        rename_button.setFlat(True)
        rename_button.setStyleSheet("QPushButton{border:none;background:transparent;}")
        rename_button.setCursor(Qt.PointingHandCursor)
        rename_button.setGeometry(QRect(578, 412, 71, 41))
        rename_button.clicked.connect(self._open_name_dialog)
        self._detail_widgets.append(rename_button)

        # 等级 / 经验行。
        self._detail_widgets.append(_pixmap_label(self, "level_icon.png", 300, 466, 22, 22))
        self._level_label = _label(self, "", 326, 464, 96, 24, size=15, name="profileLevel")
        self._detail_widgets.append(self._level_label)
        self._detail_widgets.append(_pixmap_label(self, "exp_icon.png", 424, 467, 20, 20))
        self._exp_value = _label(self, "", 448, 464, 150, 24, size=15, color=_TEXT_SOFT)
        self._detail_widgets.append(self._exp_value)
        self._xp_bar = ArtBar("exp_bar.png", self)
        self._xp_bar.setGeometry(QRect(602, 467, 167, 18))
        self._detail_widgets.append(self._xp_bar)

        # 好感度行。
        self._detail_widgets.append(_pixmap_label(self, "affection_icon.png", 300, 514, 21, 20))
        self._affection_label = _label(self, "", 324, 512, 128, 24, size=15, name="profileAffection")
        self._detail_widgets.append(self._affection_label)
        self._detail_widgets.append(_pixmap_label(self, "affection_icon_2.png", 452, 515, 21, 20))
        self._aff_value = _label(self, "", 476, 512, 110, 24, size=15, color=_TEXT_SOFT)
        self._detail_widgets.append(self._aff_value)
        self._aff_bar = ArtBar("affection_bar.png", self)
        self._aff_bar.setGeometry(QRect(590, 515, 167, 18))
        self._detail_widgets.append(self._aff_bar)
        self._detail_widgets.append(_pixmap_label(self, "heart_icon_small.png", 748, 498, 46, 41))

        # 介绍胶囊。
        _pixmap_label(self, "description_bg.png", 300, 553, 485, 46)
        self._desc_label = _label(
            self, "", 315, 559, 455, 34, size=14, color=_TEXT_SOFT,
            align=Qt.AlignCenter,
        )
        self._detail_widgets.append(self._desc_label)

        # 套装区。
        outfit_title = _label(
            self, "🐾 套装", 300, 634, 120, 26, size=17, bold=True,
            name="sectionTitle",
        )
        self._detail_widgets.append(outfit_title)
        self._outfit_slots = (
            QRect(288, 668, 236, 148), QRect(538, 668, 236, 148),
        )

        # 锁定页部件（未拥有宠物）。
        self._locked_page = QWidget(self)
        self._locked_page.setGeometry(QRect(300, 500, 470, 330))
        self._locked_page.setStyleSheet("background:transparent;")
        self._locked_hint = _label(
            self._locked_page, "", 10, 80, 450, 60, size=14, color=_TEXT_SOFT,
            align=Qt.AlignCenter,
        )
        self._locked_hint.setWordWrap(True)
        self._locked_shop = QPushButton("去商店购买", self._locked_page)
        self._locked_shop.setObjectName("lockedShopButton")
        self._locked_shop.setCursor(Qt.PointingHandCursor)
        self._locked_shop.setGeometry(QRect(135, 150, 200, 44))
        self._locked_shop.clicked.connect(self._open_shop)
        self._locked_shop.setStyleSheet(
            "QPushButton{"
            f"font-family:'{APP_FONT_FAMILY}';font-size:17px;"
            "background:#f28f76;color:#ffffff;border:none;"
            "border-radius:22px;}"
            "QPushButton:hover{background:#ee7c60;}"
        )

        # 底部状态行。
        self.status_label = _label(
            self, "", 40, 838, 720, 26, size=14, color="#a06b5e",
            align=Qt.AlignCenter, name="status",
        )

    # ---- 数据刷新 ----

    def refresh(self):
        state = self.pet.state
        active_id = state.get("active_pet_id", pet_registry.DEFAULT_PET_ID)
        snapshot = pet_profile_snapshot(state, self._selected_pet_id)

        for pet_id, (button, badge, lock) in self._avatar_buttons.items():
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
                icon_path, 96, 96, 20, grayscale=not owned,
            )))
            badge.setVisible(pet_id == active_id)
            lock.setVisible(not owned)

        if snapshot["owned"]:
            self._show_detail(snapshot)
        else:
            self._show_locked(snapshot)

    def _show_detail(self, snapshot):
        for widget in self._locked_widgets:
            widget.setVisible(False)
        for widget in self._detail_widgets:
            widget.setVisible(True)
        self._locked_page.setVisible(False)

        preview = QPixmap(snapshot.get("preview_path") or "")
        if preview.isNull():
            preview = QPixmap(snapshot.get("avatar_path") or "")
        if preview.isNull():
            self._preview_label.setPixmap(QPixmap())
        else:
            self._preview_label.setPixmap(
                preview.scaledToHeight(330, Qt.SmoothTransformation)
            )
        self._name_label.setText(snapshot["name"])
        self._level_label.setText(f"Lv.{snapshot['level']}")
        self._exp_value.setText(
            f"经验 {snapshot['xp']} / {snapshot['xp_next']}"
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

        preview = QPixmap(snapshot.get("preview_path") or "")
        if preview.isNull():
            preview = QPixmap(snapshot.get("avatar_path") or "")
        if preview.isNull():
            self._preview_label.setPixmap(QPixmap())
        else:
            self._preview_label.setPixmap(
                _grayscale_pixmap(snapshot.get("preview_path")
                                  or snapshot.get("avatar_path")).scaledToHeight(
                    280, Qt.SmoothTransformation
                )
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
                300, 730, 470, 30, size=14, color=_TEXT_SOFT,
                align=Qt.AlignCenter,
            )
            self._outfit_cards.append(empty)
            empty.show()
            return

        pet_id = snapshot["id"]
        for slot, outfit in zip(self._outfit_slots, snapshot["outfits"]):
            card = QWidget(self)
            card.setGeometry(slot)

            preview = QLabel(card)
            preview.setAlignment(Qt.AlignCenter)
            preview.setGeometry(QRect(10, 24, 96, 96))
            pixmap = QPixmap(_outfit_preview_path(pet_id, outfit) or "")
            if not pixmap.isNull():
                preview.setPixmap(
                    pixmap.scaledToHeight(88, Qt.SmoothTransformation)
                )
            preview.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            name = _label(
                card, f"{outfit['icon']} {outfit['name']}",
                112, 18, 118, 24, size=15, bold=True,
            )
            desc = _label(
                card, outfit["description"], 112, 44, 118, 56,
                size=11, color=_TEXT_SOFT, align=Qt.AlignLeft | Qt.AlignTop,
            )
            desc.setWordWrap(True)

            if outfit["equipped"]:
                button = self._pill_button("卸下", "#8fbf7f", card)
                button.clicked.connect(
                    lambda _checked=False: self._apply_outfit(equip=False)
                )
            elif outfit["owned"]:
                button = self._pill_button("装备", "#f49a8a", card)
                button.clicked.connect(
                    lambda _checked=False, oid=outfit["id"]:
                        self._apply_outfit(oid, equip=True)
                )
            else:
                button = self._pill_button(
                    f"去商店 · {outfit['price']}币", "#f28f76", card
                )
                button.clicked.connect(self._open_shop)
            button.setGeometry(QRect(112, 104, 118, 37))

            card.show()
            self._outfit_cards.append(card)

    def _pill_button(self, text, color, parent):
        # 注意：Qt 样式表里裸声明与规则块混用会导致规则被丢弃，
        # 字体声明必须放进规则块内部。
        button = QPushButton(text, parent)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton{"
            f"font-family:'{APP_FONT_FAMILY}';font-size:15px;"
            f"background:{color};color:#ffffff;border:none;"
            "border-radius:18px;}"
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
        if pet_id != active_id:
            self._switch_pet(pet_id)
            return
        self.refresh()

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
        # 立绘下的粉色蕾丝站垫（素材无独立切图，按参考图同色绘制）。
        mat = QRect(330, 372, 340, 84)
        painter.setPen(QColor(246, 205, 200))
        painter.setBrush(QColor(250, 222, 218, 235))
        painter.drawEllipse(mat)
        painter.setBrush(QColor(253, 236, 232, 235))
        painter.drawEllipse(mat.adjusted(14, 8, -14, -14))
        if not self._plaque.isNull():
            painter.drawPixmap(7, 0, self._plaque)

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

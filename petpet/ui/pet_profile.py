"""宠物详情面板：展示数据快照与面板窗口。"""

from __future__ import annotations

import os

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QImage, QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from petpet.app.fonts import APP_FONT_FAMILY
from petpet.app import pets as pet_registry
from petpet.app import state as app_state
from petpet.progression import core as progression
from petpet.progression.ui import FeedbackButton, PANEL_STYLE, CozyProgressWindow

_NAME_DIALOG_FACTORY = None


def configure_name_dialog_factory(factory):
    """注入改名对话框类（定义在根模块 pet.py，包内不能直接 import）。"""
    global _NAME_DIALOG_FACTORY
    _NAME_DIALOG_FACTORY = factory


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


_PROFILE_EXTRA_STYLE = f"""
QWidget {{ font-family: "{APP_FONT_FAMILY}"; }}
QLabel#profileName {{ font-size: 26px; font-weight: 600; color: #5a4636; }}
QLabel#profileLevel, QLabel#profileAffection {{
    font-size: 15px; color: #8a7361;
}}
QLabel#profileDesc {{ font-size: 15px; color: #8a7361; }}
QLabel#sectionTitle {{ font-size: 17px; font-weight: 600; color: #6b5646; }}
QProgressBar#profileBar {{
    background: #f6e7d7; border: none; border-radius: 7px;
    max-height: 12px; text-align: center;
}}
QProgressBar#profileBar::chunk {{ background: #f28f76; border-radius: 7px; }}
QFrame#petRail {{ background: rgba(242, 143, 118, 0.10); border-radius: 16px; }}
QLabel#petRailName {{ color: #6b5646; font-size: 14px; }}
QLabel#activeBadge {{
    background: #f28f76; color: #ffffff; border-radius: 9px;
    padding: 1px 9px; font-size: 12px;
}}
QLabel#lockBadge {{
    background: #cfc4b8; color: #ffffff; border-radius: 9px;
    padding: 1px 9px; font-size: 12px;
}}
QPushButton#profileAvatarButton {{
    border: 3px solid transparent; border-radius: 50px;
    padding: 2px; background: transparent;
}}
QPushButton#profileAvatarButton[selected="true"] {{
    border: 3px solid #f28f76; background: rgba(242, 143, 118, 0.12);
}}
QFrame#outfitCard {{
    background: #fffdf6; border: 2px solid #f6dccd; border-radius: 14px;
}}
QLabel#outfitName {{ font-size: 15px; font-weight: 600; color: #5a4646; }}
QLabel#outfitDesc {{ font-size: 12px; color: #a08a78; }}
QPushButton#lockedShopButton {{
    background: #f28f76; color: #ffffff; border: none;
    border-radius: 20px; padding: 10px 26px; font-size: 17px;
}}
QPushButton#lockedShopButton:hover {{ background: #ee7c60; }}
"""


def _circular_pixmap(path, size, grayscale=False):
    """把头像裁成圆形；路径缺失时返回透明占位。"""
    output = QPixmap(size, size)
    output.fill(Qt.transparent)
    if not path or not os.path.isfile(path):
        return output
    source = QPixmap(path)
    if grayscale and not source.isNull():
        image = source.toImage().convertToFormat(QImage.Format_Grayscale8)
        source = QPixmap.fromImage(image)
    if source.isNull():
        return output
    painter = QPainter(output)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    painter.setClipPath(clip)
    scaled = source.scaled(
        size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
    )
    painter.drawPixmap(
        (size - scaled.width()) // 2,
        (size - scaled.height()) // 2,
        scaled,
    )
    painter.end()
    return output


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


class PetProfileWindow(CozyProgressWindow):
    """宠物详情面板：形象、昵称、好感度、套装与宠物切换。"""

    def __init__(self, pet, save_state):
        super().__init__(pet, "宠物", "我的伙伴与套装", (780, 860))
        self._save_state = (
            save_state if callable(save_state) else (lambda _state: None)
        )
        self._selected_pet_id = str(
            pet.state.get("active_pet_id", pet_registry.DEFAULT_PET_ID)
        )
        self._avatar_buttons = {}
        self._outfit_cards = []

        body = QHBoxLayout()
        body.setContentsMargins(0, 4, 0, 0)
        body.setSpacing(14)
        body.addWidget(self._build_rail())

        self._pages = QStackedWidget()
        self._detail_page = self._build_detail_page()
        self._locked_page = self._build_locked_page()
        self._pages.addWidget(self._detail_page)
        self._pages.addWidget(self._locked_page)
        body.addWidget(self._pages, 1)

        self.content_layout.addLayout(body)
        self.setStyleSheet(PANEL_STYLE + _PROFILE_EXTRA_STYLE)
        self.refresh()

    def _build_rail(self):
        rail = QFrame()
        rail.setObjectName("petRail")
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        for pet_id, definition in pet_registry.load_pet_registry().items():
            item = QWidget()
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(3)
            item_layout.setAlignment(Qt.AlignHCenter)

            button = QPushButton()
            button.setObjectName("profileAvatarButton")
            button.setFixedSize(100, 100)
            button.setIconSize(QSize(84, 84))
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, target=pet_id: self._select_pet(target)
            )
            name = QLabel(definition.get("default_name", pet_id))
            name.setObjectName("petRailName")
            name.setAlignment(Qt.AlignCenter)
            badge = QLabel("使用中")
            badge.setObjectName("activeBadge")
            badge.setAlignment(Qt.AlignCenter)
            lock = QLabel("🔒 未拥有")
            lock.setObjectName("lockBadge")
            lock.setAlignment(Qt.AlignCenter)

            item_layout.addWidget(button)
            item_layout.addWidget(name)
            item_layout.addWidget(badge)
            item_layout.addWidget(lock)
            layout.addWidget(item)
            self._avatar_buttons[pet_id] = (button, badge, lock)
        return rail

    def _build_detail_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(9)

        self._preview_label = QLabel()
        self._preview_label.setObjectName("profilePreview")
        self._preview_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._preview_label)

        name_row = QHBoxLayout()
        name_row.setAlignment(Qt.AlignCenter)
        name_row.setSpacing(10)
        self._name_label = QLabel("")
        self._name_label.setObjectName("profileName")
        name_row.addWidget(self._name_label)
        edit_button = FeedbackButton("✏️ 改名")
        edit_button.setObjectName("profileEditButton")
        edit_button.setCursor(Qt.PointingHandCursor)
        edit_button.clicked.connect(self._open_name_dialog)
        name_row.addWidget(edit_button)
        layout.addLayout(name_row)

        self._level_label = QLabel("")
        self._level_label.setObjectName("profileLevel")
        self._level_label.setAlignment(Qt.AlignCenter)
        self._xp_bar = self._build_bar()
        layout.addWidget(self._level_label)
        layout.addWidget(self._xp_bar)

        self._affection_label = QLabel("")
        self._affection_label.setObjectName("profileAffection")
        self._affection_label.setAlignment(Qt.AlignCenter)
        self._aff_bar = self._build_bar()
        layout.addWidget(self._affection_label)
        layout.addWidget(self._aff_bar)

        self._desc_label = QLabel("")
        self._desc_label.setObjectName("profileDesc")
        self._desc_label.setWordWrap(True)
        self._desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._desc_label)

        outfit_title = QLabel("套装")
        outfit_title.setObjectName("sectionTitle")
        layout.addWidget(outfit_title)

        self._outfit_row = QHBoxLayout()
        self._outfit_row.setSpacing(10)
        layout.addLayout(self._outfit_row)
        layout.addStretch(1)
        return page

    def _build_locked_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        self._locked_preview = QLabel()
        self._locked_preview.setAlignment(Qt.AlignCenter)
        self._locked_name = QLabel("")
        self._locked_name.setObjectName("profileName")
        self._locked_name.setAlignment(Qt.AlignCenter)
        self._locked_hint = QLabel("")
        self._locked_hint.setObjectName("profileDesc")
        self._locked_hint.setWordWrap(True)
        self._locked_hint.setAlignment(Qt.AlignCenter)
        shop_button = QPushButton("去商店购买")
        shop_button.setObjectName("lockedShopButton")
        shop_button.setCursor(Qt.PointingHandCursor)
        shop_button.clicked.connect(self._open_shop)

        layout.addWidget(self._locked_preview)
        layout.addWidget(self._locked_name)
        layout.addWidget(self._locked_hint)
        layout.addWidget(shop_button)
        return page

    def _build_bar(self):
        bar = QProgressBar()
        bar.setObjectName("profileBar")
        bar.setTextVisible(False)
        bar.setFixedHeight(12)
        return bar

    def refresh(self):
        state = self.pet.state
        active_id = state.get("active_pet_id", pet_registry.DEFAULT_PET_ID)
        snapshot = pet_profile_snapshot(state, self._selected_pet_id)

        for pet_id, (button, badge, lock) in self._avatar_buttons.items():
            button.setProperty("selected", pet_id == self._selected_pet_id)
            style = button.style()
            style.unpolish(button)
            style.polish(button)
            owned = (
                pet_id == active_id
                or pet_id in (state.get("owned_pet_ids") or ())
            )
            button.setIcon(QIcon(_circular_pixmap(
                pet_registry.pet_avatar_path(pet_id), 84,
                grayscale=not owned,
            )))
            badge.setVisible(pet_id == active_id)
            lock.setVisible(not owned)

        if snapshot["owned"]:
            self._pages.setCurrentWidget(self._detail_page)
            self._refresh_detail(snapshot)
        else:
            self._clear_outfits()
            self._pages.setCurrentWidget(self._locked_page)
            self._refresh_locked(snapshot)

    def _clear_outfits(self):
        while self._outfit_row.count():
            item = self._outfit_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._outfit_cards = []

    def _refresh_detail(self, snapshot):
        preview = QPixmap(snapshot.get("preview_path") or "")
        if preview.isNull():
            preview = QPixmap(snapshot.get("avatar_path") or "")
        if preview.isNull():
            self._preview_label.setPixmap(QPixmap())
        else:
            self._preview_label.setPixmap(
                preview.scaledToWidth(240, Qt.SmoothTransformation)
            )
        self._name_label.setText(snapshot["name"])
        self._level_label.setText(
            f"Lv.{snapshot['level']} · 经验 {snapshot['xp']}/{snapshot['xp_next']}"
        )
        self._set_bar(self._xp_bar, snapshot["xp"], snapshot["xp_next"])
        self._affection_label.setText(
            f"好感度 Lv.{snapshot['affection_level']} · "
            f"{snapshot['affection_points']}/{snapshot['affection_next']}"
        )
        self._set_bar(
            self._aff_bar,
            snapshot["affection_points"],
            snapshot["affection_next"],
        )
        self._desc_label.setText(snapshot["description"])
        self._refresh_outfits(snapshot)

    def _refresh_locked(self, snapshot):
        preview = QPixmap(snapshot.get("preview_path") or "")
        if preview.isNull():
            preview = QPixmap(snapshot.get("avatar_path") or "")
        if preview.isNull():
            self._locked_preview.setPixmap(QPixmap())
        else:
            grayscale = preview.toImage().convertToFormat(
                QImage.Format_Grayscale8
            )
            self._locked_preview.setPixmap(
                QPixmap.fromImage(grayscale).scaledToWidth(
                    240, Qt.SmoothTransformation
                )
            )
        self._locked_name.setText(snapshot["name"])
        self._locked_hint.setText(
            f"{snapshot['description']}\n还未拥有，可在商店用 {snapshot['price']} Pet币 带它回家。"
        )

    def _refresh_outfits(self, snapshot):
        self._clear_outfits()

        if not snapshot["outfits"]:
            empty = QLabel("这只宠物的套装正在准备中，敬请期待～")
            empty.setObjectName("outfitDesc")
            self._outfit_row.addWidget(empty)
            return

        pet_id = snapshot["id"]
        for outfit in snapshot["outfits"]:
            card = QFrame()
            card.setObjectName("outfitCard")
            card.setFixedWidth(200)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(4)

            preview = QLabel()
            preview.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(_outfit_preview_path(pet_id, outfit) or "")
            if not pixmap.isNull():
                preview.setPixmap(
                    pixmap.scaledToWidth(160, Qt.SmoothTransformation)
                )
            name = QLabel(f"{outfit['icon']} {outfit['name']}")
            name.setObjectName("outfitName")
            name.setAlignment(Qt.AlignCenter)
            desc = QLabel(outfit["description"])
            desc.setObjectName("outfitDesc")
            desc.setWordWrap(True)
            desc.setAlignment(Qt.AlignCenter)

            if outfit["equipped"]:
                action_text = "卸下"
                handler = (
                    lambda _checked=False: self._apply_outfit(equip=False)
                )
            elif outfit["owned"]:
                action_text = "装备"
                handler = (
                    lambda _checked=False, oid=outfit["id"]:
                        self._apply_outfit(oid, equip=True)
                )
            else:
                action_text = f"去商店 · {outfit['price']}币"
                handler = (lambda _checked=False: self._open_shop())
            button = FeedbackButton(action_text)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(handler)

            layout.addWidget(preview)
            layout.addWidget(name)
            layout.addWidget(desc)
            layout.addWidget(button)
            self._outfit_row.addWidget(card)
            self._outfit_cards.append(card)

    def _set_bar(self, bar, value, maximum):
        bar.setRange(0, max(1, int(maximum)))
        bar.setValue(max(0, min(int(value), int(maximum))))

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

"""Warm rounded chat window UI, independent from the desktop entry point."""

import os
import threading
import time

from petpet.chat import api as ai
from petpet.app.pets import pet_asset_path, pet_definition
from PyQt5.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from petpet.ui.common import independent_font_px, independent_pixel_font


class ChatWindow(QWidget):
    """A small chat panel that floats beside the pet.
    Sheen replies stream in token-by-token via the bridge."""
    def __init__(self, pet_window, pet_id="lunch_meat", *, memory_profile=None,
                 bridge_provider, confirm_dialog_factory, popup_menu_factory,
                 save_state_callback, progression_service):
        super().__init__()
        self.pet = pet_window
        self._bridge_provider = bridge_provider
        self._confirm_dialog_factory = confirm_dialog_factory
        self._popup_menu_factory = popup_menu_factory
        self._save_state_callback = save_state_callback
        self._progression_service = progression_service
        self.s = pet_window.settings  # live settings reference
        self.pet_id = ai.normalize_memory_pet_id(
            memory_profile if memory_profile is not None else pet_id
        )
        self.memory_profile = self.pet_id  # compatibility attribute
        self.mem = ai.load_memory(pet_id=self.pet_id)
        self.busy = False
        self._pending_user = None
        self._pending_image = None
        self._streaming = ""
        self._last_assistant_bubble = None

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool  # no taskbar button
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("chat")
        self.setFixedSize(self.s["chat_width"], self.s["chat_height"])
        self._apply_style()

    def _pet_name(self):
        facade_name = ai.normalize_pet_name(
            getattr(self.pet, "pet_name", "")
        )
        if facade_name != ai.DEFAULT_PET_NAME:
            return facade_name
        profiles = self.pet.state.get("pets", {})
        profile = profiles.get(self.pet_id, {}) \
            if isinstance(profiles, dict) else {}
        if isinstance(profile, dict) and profile.get("pet_name"):
            return ai.normalize_pet_name(profile["pet_name"])
        return ai.normalize_pet_name(
            self.mem.get("pet_name") or self.pet.pet_name
        )

    def _chat_title(self) -> str:
        nickname = self._pet_name()
        real_name = pet_definition(self.pet_id).get("default_name", nickname)
        return nickname if nickname == real_name else f"{nickname}（{real_name}）"

    def set_pet_id(self, pet_id):
        """Switch the window to one pet's independent conversation history."""
        if self.busy:
            return False
        self.pet_id = ai.normalize_memory_pet_id(pet_id)
        self.memory_profile = self.pet_id
        self.mem = ai.load_memory(pet_id=self.pet_id)
        if getattr(self, "_ui_built", False):
            self.refresh_pet_name()
            self._set_log_messages(self._history_messages())
        return True

    def set_memory_profile(self, profile):
        """Compatibility alias for switching by the old profile name."""
        self.set_pet_id(profile)

    def _chat_font_px(self):
        return independent_font_px(self.s["chat_font_size"])

    def _apply_style(self):
        # The chat window has its own user-controlled font setting. Keep it
        # independent from the compact pet-surface enlargement.
        fs = self._chat_font_px()
        self.setStyleSheet(f"""
            QWidget#chat {{
                background:transparent;
                border:0;
            }}
            QFrame#chatCard {{
                background:#faf7f3;
                border:1px solid #e6d8cf;
                border-radius:24px;
            }}
            QScrollArea#chatHistory {{
                background:#fffdfa;
                border:1px solid #eee4dd;
                border-radius:18px;
            }}
            QWidget#chatHistoryBody {{
                background:#fffdfa;
            }}
            QScrollBar:vertical {{
                background:#f5efea;
                width:10px;
                margin:8px 4px 8px 0;
                border-radius:5px;
            }}
            QScrollBar::handle:vertical {{
                background:#d8c5b8;
                min-height:34px;
                border-radius:5px;
            }}
            QScrollBar::handle:vertical:hover {{ background:#c9ad9d; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height:0;
            }}
            QLineEdit {{
                background:#fffefc;
                border:1px solid #e4d5ca;
                border-radius:15px;
                padding:10px 14px;
                font-family:'Microsoft YaHei',sans-serif;
                font-size:{fs}px;
                color:#65483b;
            }}
            QLineEdit:focus {{
                border:2px solid #dfa48e;
                background:#ffffff;
            }}
            QPushButton#send {{
                background:#dc806a; color:#fff; border:0;
                border-radius:15px;
                padding:10px 23px; font-weight:700; font-size:{fs}px;
            }}
            QPushButton#send:hover {{ background:#e19179; }}
            QPushButton#send:disabled {{ background:#ccb9ae; }}
            QPushButton#send:pressed {{ background:#c66e5b; }}
            QFrame#chatTools {{
                background:#f8f2ed;
                border:1px solid #eaded5;
                border-radius:18px;
            }}
            QFrame#chatModeSegments {{
                background:#fff1e8;
                border:1px solid #f1d8cc;
                border-radius:17px;
            }}
            QPushButton#chatModeSegment {{
                background:transparent; color:#a18070;
                border:0; border-radius:20px; padding:0;
                font-weight:600;
            }}
            QPushButton#chatModeSegment:checked {{
                background:#f8dcd7; color:#70483c;
                border:1px solid #efc4bb;
            }}
            QPushButton#chatModeSegment:hover:!checked {{
                background:#f6e9e1;
            }}
            QPushButton#chatTool {{
                background:#fffdfb; color:#76594b;
                border:1px solid #e5d5ca; border-radius:15px;
                padding:0 12px;
                font-weight:700;
            }}
            QPushButton#chatTool:hover {{
                background:#f8e9e1; color:#8f604e; border-color:#ddbaa8;
            }}
            QPushButton#chatTool:pressed {{
                background:#efd9cc;
            }}
            QPushButton#roundTool {{
                min-width:40px; max-width:40px;
                min-height:38px; max-height:38px;
                padding:0; border-radius:20px;
                color:#8f695b; background:#fffdfb;
                border:1px solid #e5d5ca;
                font-weight:700;
            }}
            QPushButton#roundTool:hover {{
                background:#f8e9e1; color:#8f604e; border-color:#ddbaa8;
            }}
            QPushButton#clearTool {{
                min-width:44px; max-width:44px;
                min-height:38px; max-height:38px;
                padding:0; border-radius:20px;
                font-weight:800;
                color:#9a7067; background:#fffaf8; border-color:#e6d3cc;
                border:1px solid #e6d3cc;
            }}
            QPushButton#clearTool:hover {{
                color:#b45d56; background:#f9e8e3; border-color:#dfb2a9;
            }}
            QLabel#title {{
                font-size:{fs+2}px; font-weight:800; color:#70483c;
                padding:7px 12px;
            }}
        """)

        # Runtime settings refreshes must only restyle the existing widgets.
        if getattr(self, "_ui_built", False):
            return

        # title bar (draggable) — title label on the left, close button on the right
        self.title = QLabel(f"  {self._chat_title()}")
        self.title.setObjectName("title")
        self.title.setFixedHeight(38)
        self.title.setStyleSheet(
            "background:#faf0ea;"
            "color:#755448;"
            "border-top-left-radius:18px;"
            "border-top-right-radius:18px;"
            "padding:6px 10px;")
        self._drag_off = None
        self.title.mousePressEvent = self._title_press
        self.title.mouseMoveEvent = self._title_move
        self.title.mouseReleaseEvent = lambda e: setattr(self, "_drag_off", None)

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setToolTip("关闭")
        self.close_btn.setStyleSheet(
            "QPushButton{background:transparent;border:0;color:#a47b69;"
            "font-size:26px;font-weight:700;padding:0;}"
            "QPushButton:hover{background:#ffcfc5;color:#bf5c52;border-radius:14px;}"
        )
        self.close_btn.clicked.connect(self.close)

        self.avatar_btn = QPushButton("头像")
        self.avatar_btn.setObjectName("avatarEdit")
        self.avatar_btn.setCursor(Qt.PointingHandCursor)
        self.avatar_btn.setToolTip("编辑我的头像")
        self.avatar_btn.setStyleSheet(
            "QPushButton{background:#fffaf6;color:#8c6252;"
            "border:1px solid #e6cfc2;border-radius:14px;"
            "padding:5px 11px;font-weight:700;}"
            "QPushButton:hover{background:#ffe8dc;border-color:#dda993;}"
        )
        self.avatar_btn.clicked.connect(self.show_player_avatar_menu)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 8, 0)
        title_row.setSpacing(0)
        title_row.addWidget(self.title, 1)
        title_row.addWidget(self.avatar_btn)
        title_row.addSpacing(6)
        title_row.addWidget(self.close_btn)

        # Real widgets keep each message softly rounded on every platform.
        # QTextEdit's HTML renderer ignores several modern CSS properties.
        self.log = QScrollArea()
        self.log.setObjectName("chatHistory")
        self.log.setFrameShape(QFrame.NoFrame)
        self.log.setWidgetResizable(True)
        self.log.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.log_body = QWidget()
        self.log_body.setObjectName("chatHistoryBody")
        self.log_layout = QVBoxLayout(self.log_body)
        self.log_layout.setContentsMargins(16, 14, 16, 14)
        self.log_layout.setSpacing(4)
        self.log.setWidget(self.log_body)
        self._displayed_messages = []
        self._set_log_messages(self._history_messages())

        # input row
        self.input = QLineEdit()
        self.input.setPlaceholderText(
            f"跟 {self._pet_name()} 说点什么…"
        )
        self.input.returnPressed.connect(self.send)
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("send")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self.send)

        self.chat_notice = QLabel()
        self.chat_notice.setObjectName("chatNotice")
        self.chat_notice.setWordWrap(True)
        self.chat_notice.setStyleSheet(
            "QLabel#chatNotice{background:#fff3dc;color:#8a5b42;"
            "border:1px solid #efcfaa;border-radius:10px;"
            "padding:7px 10px;font-size:13px;}"
        )
        self.chat_notice.hide()

        self.image_preview = QFrame()
        self.image_preview.setObjectName("imagePreview")
        self.image_preview.setStyleSheet(
            "QFrame#imagePreview{background:#fff8f1;border:1px solid #ead3c5;"
            "border-radius:10px;}"
        )
        preview_row = QHBoxLayout(self.image_preview)
        preview_row.setContentsMargins(8, 5, 7, 5)
        preview_row.setSpacing(7)
        self.image_preview_thumb = QLabel()
        self.image_preview_thumb.setObjectName("imagePreviewThumb")
        self.image_preview_thumb.setFixedSize(34, 34)
        self.image_preview_thumb.setAlignment(Qt.AlignCenter)
        self.image_preview_name = QLabel()
        self.image_preview_name.setObjectName("imagePreviewName")
        self.image_preview_name.setStyleSheet("color:#805e50;font-weight:700;")
        self.image_remove_btn = QPushButton("×")
        self.image_remove_btn.setObjectName("imageRemove")
        self.image_remove_btn.setToolTip("移除这张图片")
        self.image_remove_btn.setCursor(Qt.PointingHandCursor)
        self.image_remove_btn.setFixedSize(26, 26)
        self.image_remove_btn.setStyleSheet(
            "QPushButton#imageRemove{background:#fffdfb;color:#a47364;"
            "border:1px solid #e4c9bc;border-radius:13px;font-size:19px;font-weight:700;}"
            "QPushButton#imageRemove:hover{background:#ffe3d8;color:#bd6658;}"
        )
        self.image_remove_btn.clicked.connect(self.clear_pending_image)
        preview_row.addWidget(self.image_preview_thumb)
        preview_row.addWidget(self.image_preview_name, 1)
        preview_row.addWidget(self.image_remove_btn)
        self.image_preview.hide()

        self.mode_frame = QFrame()
        self.mode_frame.setObjectName("chatModeSegments")
        mode_row = QHBoxLayout(self.mode_frame)
        mode_row.setContentsMargins(3, 3, 3, 3)
        mode_row.setSpacing(2)
        self.free_mode_btn = QPushButton("免费")
        self.personal_mode_btn = QPushButton("自定义")
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        segment_font = independent_pixel_font(17, QFont.DemiBold)
        segment_width = max(
            QFontMetrics(segment_font).horizontalAdvance(label)
            for label in ("免费", "自定义")
        ) + 28
        for mode_button in (self.free_mode_btn, self.personal_mode_btn):
            mode_button.setObjectName("chatModeSegment")
            mode_button.setCheckable(True)
            mode_button.setCursor(Qt.PointingHandCursor)
            mode_button.setFont(segment_font)
            mode_button.setFixedSize(segment_width, 40)
            self.mode_group.addButton(mode_button)
            mode_row.addWidget(mode_button)
        self.free_mode_btn.clicked.connect(
            lambda: self.select_chat_mode("default")
        )
        self.personal_mode_btn.clicked.connect(
            lambda: self.select_chat_mode("personal")
        )
        self.mode_frame.setFixedSize(segment_width * 2 + 8, 46)

        self.personal_setup_dot = QLabel(self.personal_mode_btn)
        self.personal_setup_dot.setObjectName("personalSetupDot")
        self.personal_setup_dot.setFixedSize(10, 10)
        self.personal_setup_dot.setStyleSheet(
            "background:#ee5e62;border:2px solid #fff9f4;border-radius:5px;"
        )
        self.personal_setup_dot.move(segment_width - 13, 4)

        self.model_btn = QPushButton("GLM-4.6V")
        self.model_btn.setObjectName("chatTool")
        self.model_btn.setCursor(Qt.PointingHandCursor)
        self.model_btn.setToolTip("当前模型：GLM-4.6V-Flash")
        self.model_btn.clicked.connect(self.configure_api_key)

        self.image_btn = QPushButton("上传")
        self.image_btn.setObjectName("chatTool")
        self.image_btn.setCursor(Qt.PointingHandCursor)
        self.image_btn.setToolTip("上传图片")
        self.image_btn.clicked.connect(self.select_image)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("roundTool")
        self.settings_btn.setToolTip("API 设置")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self.configure_api_key)

        self.clear_btn = QPushButton("DEL")
        self.clear_btn.setObjectName("clearTool")
        self.clear_btn.setMinimumWidth(44)
        self.clear_btn.setMaximumWidth(44)
        self.clear_btn.setToolTip(
            f"让 {self._pet_name()} 忘记所有对话"
        )
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.confirm_clear_memory)
        for control in (
                self.model_btn, self.image_btn,
                self.settings_btn, self.clear_btn):
            control.setFont(independent_pixel_font(17, QFont.Bold))
            control.setFixedHeight(40)
        self._refresh_ai_tool_buttons()

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)

        self.tools_frame = QFrame()
        self.tools_frame.setObjectName("chatTools")
        tools_row = QHBoxLayout(self.tools_frame)
        tools_row.setContentsMargins(7, 5, 7, 5)
        tools_row.setSpacing(7)
        tools_row.addWidget(self.mode_frame)
        tools_row.addWidget(self.model_btn)
        tools_row.addWidget(self.image_btn)
        tools_row.addStretch(1)
        tools_row.addWidget(self.settings_btn)
        tools_row.addWidget(self.clear_btn)

        self.chat_card = QFrame()
        self.chat_card.setObjectName("chatCard")
        card_layout = QVBoxLayout(self.chat_card)
        card_layout.setContentsMargins(12, 10, 12, 12)
        card_layout.setSpacing(9)
        card_layout.addLayout(title_row)
        card_layout.addWidget(self.log, 1)
        card_layout.addWidget(self.chat_notice)
        card_layout.addWidget(self.image_preview)
        card_layout.addLayout(row)
        card_layout.addWidget(self.tools_frame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chat_card)
        self._ui_built = True

    def refresh_pet_name(self):
        """Refresh every visible name after onboarding or renaming."""
        name = self._pet_name()
        self.mem["pet_name"] = name
        self.title.setText(f"  {self._chat_title()}")
        self.clear_btn.setToolTip(f"让 {name} 忘记所有对话")
        if not self.busy:
            self.input.setPlaceholderText(f"跟 {name} 说点什么…")

    def _refresh_ai_tool_buttons(self):
        mode = ai.get_chat_mode()
        personal = mode == "personal"
        self.free_mode_btn.setChecked(not personal)
        self.personal_mode_btn.setChecked(personal)
        self.model_btn.setVisible(personal)
        self.settings_btn.setVisible(personal)
        self.free_mode_btn.setEnabled(not self.busy)
        self.personal_mode_btn.setEnabled(not self.busy)
        self.model_btn.setEnabled(not self.busy)
        self.settings_btn.setEnabled(not self.busy)
        self.image_btn.setEnabled(not self.busy)
        self.clear_btn.setEnabled(not self.busy)
        self.personal_setup_dot.setVisible(ai.needs_personal_setup_reminder())
        self.personal_setup_dot.raise_()
        self._refresh_image_upload_state()

    def select_chat_mode(self, mode):
        if mode == "default":
            ai.set_chat_mode("default")
            self._refresh_ai_tool_buttons()
            return
        if ai.get_api_key_source() != "none":
            ai.set_chat_mode("personal")
            self._refresh_ai_tool_buttons()
            return
        self.configure_api_key(activate_personal=True)
        self._refresh_ai_tool_buttons()

    def _refresh_image_upload_state(self):
        """Keep the image controls constrained to the visual model."""
        visual_model = ai.is_vision_model()
        self.image_btn.setVisible(visual_model)
        if not visual_model:
            self.clear_pending_image()
        elif self._pending_image:
            self.image_preview.show()

    def select_image(self):
        """Choose the single local picture for the next visual-model turn."""
        if not ai.is_vision_model():
            QMessageBox.information(
                self, "需要视觉模型",
                "请先切换到 GLM-4.6V-Flash，再上传图片。",
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择要和小狗分享的图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        try:
            self._set_pending_image(ai.prepare_image_attachment(path))
        except ValueError as exc:
            QMessageBox.warning(self, "图片无法使用", str(exc))

    def _set_pending_image(self, attachment):
        """Render a selected attachment without persisting its request bytes."""
        if self._pending_image:
            self.clear_pending_image()
        self._pending_image = dict(attachment or {})
        filename = str(self._pending_image.get("filename", "图片"))
        self.image_preview_name.setText(f"🖼 已选择：{filename}")
        self.image_preview_thumb.clear()
        history_image = self._pending_image.get("history_image", {})
        preview_path = ai.resolve_history_image(history_image.get("thumbnail"))
        preview = QPixmap(preview_path) if preview_path else QPixmap()
        if not preview.isNull():
            self.image_preview_thumb.setPixmap(preview.scaled(
                30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation,
            ))
        else:
            self.image_preview_thumb.setText("📷")
        self.image_preview.show()

    def clear_pending_image(self, keep_history=False):
        """Discard an unsent preview while preserving a sent history image."""
        attachment = self._pending_image
        if attachment and not keep_history:
            image = attachment.get("history_image", {})
            thumbnail_path = ai.resolve_history_image(image.get("thumbnail"))
            if thumbnail_path:
                try:
                    os.remove(thumbnail_path)
                except OSError:
                    pass
        self._pending_image = None
        if hasattr(self, "image_preview"):
            self.image_preview_thumb.clear()
            self.image_preview_name.clear()
            self.image_preview.hide()

    def _build_api_key_dialog(self):
        """Build the warm frameless personal-API editor."""
        dialog = QDialog(self)
        dialog.setObjectName("apiKeyDialog")
        dialog.setModal(True)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.setAttribute(Qt.WA_TranslucentBackground, True)
        dialog.setFixedWidth(510)
        dialog.setStyleSheet("""
            QDialog#apiKeyDialog { background:transparent; }
            QFrame#apiKeyCard {
                background:#fff9f4; color:#704b3c;
                border:1px solid #edcfc2; border-radius:24px;
                font-family:'Microsoft YaHei',sans-serif;
                font-size:16px;
            }
            QLabel { color:#704b3c; }
            QLabel#apiTitle { font-size:21px; font-weight:800; }
            QLabel#apiStatus {
                background:#fff1cc; color:#8b684d;
                border:1px solid #efdba6; border-radius:13px;
                padding:9px 11px; font-size:13px;
            }
            QLabel#keyHint {
                color:#a47b6b; font-size:13px;
            }
            QLabel#apiModelCard {
                background:#f7d7b5; color:#704b3c;
                border:1px solid #e9c49f; border-radius:14px;
                padding:10px 12px; font-weight:700;
            }
            QLineEdit {
                background:#fffdf9; border:1px solid #e8cabe;
                border-radius:14px;
                padding:10px 12px;
                font-size:16px;
            }
            QLineEdit:focus { border:2px solid #f3b8ad; }
            QComboBox {
                background:#fffdf9; color:#704b3c;
                border:1px solid #e8cabe; border-radius:14px;
                padding:9px 12px;
            }
            QComboBox QAbstractItemView {
                background:#fff9f4; color:#704b3c;
                border:1px solid #edcfc2;
                selection-background-color:#f8dcd7;
                selection-color:#704b3c; outline:0;
            }
            QPushButton {
                min-height:36px; padding:0 16px;
                background:#fffdf9; color:#7d5a4c;
                border:1px solid #e7cec1; border-radius:18px;
                font-weight:700;
            }
            QPushButton:hover { background:#f8dcd7; }
            QPushButton#saveKey {
                color:#704b3c; background:#f8dcd7;
                border-color:#efc4bb;
            }
            QPushButton#saveKey:hover { background:#f3c9c1; }
            QPushButton#removeKey { color:#a66c62; background:#fff1e8; }
        """)

        card = QFrame()
        card.setObjectName("apiKeyCard")
        title = QLabel("自定义聊天")
        title.setObjectName("apiTitle")
        title.setFont(independent_pixel_font(21, QFont.Bold))
        source = ai.get_api_key_source()
        if source == "environment":
            status_text = "正在使用系统环境变量中的 Key。"
        elif source == "config":
            status_text = "本机已保存 Key，输入新内容可替换。"
        else:
            status_text = "填写智谱 API Key 后即可使用图文聊天。"
        status = QLabel(status_text)
        status.setObjectName("apiStatus")
        status.setFont(independent_pixel_font(15))
        status.setWordWrap(True)

        model_label = QLabel("聊天模型")
        model_label.setFont(independent_pixel_font(18, QFont.Bold))
        model_ids = list(ai.PERSONAL_MODELS)
        model_selector = None
        if len(model_ids) == 1:
            model_id = model_ids[0]
            model_widget = QLabel(ai.PERSONAL_MODELS[model_id])
            model_widget.setObjectName("apiModelCard")
            model_widget.setFont(independent_pixel_font(17, QFont.Bold))
        else:
            model_selector = QComboBox()
            for model_id, display_name in ai.PERSONAL_MODELS.items():
                model_selector.addItem(display_name, model_id)
            current_index = model_selector.findData(ai.load_config().get("model"))
            model_selector.setCurrentIndex(max(0, current_index))
            model_widget = model_selector

        key_edit = QLineEdit()
        key_edit.setFont(independent_pixel_font(17))
        key_edit.setEchoMode(QLineEdit.Password)
        key_edit.setPlaceholderText("输入 API Key")
        key_edit.setClearButtonEnabled(True)

        privacy = QLabel("Key 只保存在当前电脑，不会显示完整内容。")
        privacy.setObjectName("keyHint")
        privacy.setFont(independent_pixel_font(15))
        privacy.setWordWrap(True)

        show_btn = QPushButton("按住显示")
        show_btn.setCursor(Qt.PointingHandCursor)
        show_btn.pressed.connect(
            lambda: key_edit.setEchoMode(QLineEdit.Normal)
        )
        show_btn.released.connect(
            lambda: key_edit.setEchoMode(QLineEdit.Password)
        )

        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(dialog.reject)
        save_btn = QPushButton("保存")
        save_btn.setObjectName("saveKey")
        save_btn.setCursor(Qt.PointingHandCursor)

        def accept_key():
            if key_edit.text().strip() or ai.get_api_key_source() != "none":
                dialog.accept()
                return
            status.setText("请先输入 API Key。")
            status.setStyleSheet(
                "background:#f8dcd7;color:#965f57;border:1px solid #efc4bb;"
                "border-radius:13px;padding:9px 11px;font-weight:700;"
            )
            key_edit.setFocus()

        save_btn.clicked.connect(accept_key)
        key_edit.returnPressed.connect(accept_key)
        remove_btn = QPushButton("移除本机 Key")
        remove_btn.setObjectName("removeKey")
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setVisible(ai.load_config().get("api_key", "") != "")
        remove_btn.clicked.connect(lambda: dialog.done(2))
        for button in (show_btn, cancel_btn, save_btn, remove_btn):
            button.setFont(independent_pixel_font(17, QFont.Bold))
            button.setMinimumHeight(40)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_row.addWidget(key_edit, 1)
        key_row.addWidget(show_btn)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addWidget(remove_btn)
        button_row.addStretch(1)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(12)
        card_layout.addWidget(title)
        card_layout.addWidget(status)
        card_layout.addWidget(model_label)
        card_layout.addWidget(model_widget)
        card_layout.addLayout(key_row)
        card_layout.addWidget(privacy)
        card_layout.addLayout(button_row)
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(card)
        key_edit.setFocus()

        dialog.key_edit = key_edit
        dialog.status_label = status
        dialog.model_selector = model_selector
        dialog.selected_model_id = (
            model_ids[0] if len(model_ids) == 1 else None
        )
        return dialog

    def configure_api_key(self, activate_personal=False):
        """Open the warm API editor without displaying the saved key."""
        ai.mark_personal_setup_seen()
        self._refresh_ai_tool_buttons()
        dialog = self._build_api_key_dialog()

        result = dialog.exec_()
        if result == QDialog.Accepted:
            new_key = dialog.key_edit.text().strip()
            if not new_key and ai.get_api_key_source() == "none":
                return
            try:
                if new_key:
                    ai.set_api_key(new_key)
                model_id = dialog.selected_model_id
                if dialog.model_selector is not None:
                    model_id = dialog.model_selector.currentData()
                ai.set_model(model_id)
                ai.set_chat_mode("personal")
            except Exception:
                self.chat_notice.setText("保存失败，请稍后再试。")
                self.chat_notice.show()
                return
            self._refresh_ai_tool_buttons()
        elif result == 2:
            confirm = self._confirm_dialog_factory(
                self,
                title="移除 API Key",
                message="要移除保存在这台电脑上的 Key 吗？",
                accept_text="移除",
                reject_text="保留",
            )
            if confirm.exec_() == QDialog.Accepted:
                try:
                    ai.set_api_key("")
                except Exception:
                    self.chat_notice.setText("移除失败，请稍后再试。")
                    self.chat_notice.show()
                    return
                self._refresh_ai_tool_buttons()

    def select_model(self, model_id):
        try:
            ai.set_model(model_id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                self, "模型切换失败", f"无法保存模型设置：{exc}"
            )
            return
        self._refresh_ai_tool_buttons()

    def _history_messages(self, exclude_last_assistant=False):
        """Return the recent transcript for the native message widget list."""
        hs = list(self.mem.get("history", []))[-20:]
        if exclude_last_assistant and hs and hs[-1]["role"] == "assistant":
            hs = hs[:-1]
        return [
            (
                str(item.get("role", "assistant")),
                str(item.get("content", "")),
                item.get("image"),
            )
            for item in hs
        ]

    def _message_width(self):
        viewport_width = self.log.viewport().width()
        if viewport_width <= 1:
            viewport_width = self.width() - 32
        return max(240, int(viewport_width * 0.72))

    def _avatar_pixmap(self, role, size=42):
        """Build a circular desktop-pet or player avatar pixmap."""
        source = "default"
        image = QImage()
        if role == "assistant":
            source = os.path.normpath(
                pet_asset_path(self.pet_id, "desktop", "idle") or ""
            )
            image = QImage(source)
        else:
            player_path = ai.get_player_avatar_path()
            if os.path.isfile(player_path):
                source = player_path
                image = QImage(player_path)

        canvas = QPixmap(size, size)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(QRectF(0, 0, size, size))
        painter.setClipPath(path)
        painter.fillRect(canvas.rect(), QColor("#f3ded0"))
        if not image.isNull():
            if role == "assistant":
                edge = min(image.width(), max(1, int(image.height() * 0.68)))
                source_rect = QRect(
                    (image.width() - edge) // 2,
                    max(0, int(image.height() * 0.04)),
                    edge,
                    edge,
                )
            else:
                edge = min(image.width(), image.height())
                source_rect = QRect(
                    (image.width() - edge) // 2,
                    (image.height() - edge) // 2,
                    edge,
                    edge,
                )
            painter.drawImage(QRect(0, 0, size, size), image, source_rect)
        else:
            painter.setBrush(QColor("#d99a7f"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(size * .34, size * .18,
                                       size * .32, size * .32))
            painter.drawEllipse(QRectF(size * .19, size * .52,
                                       size * .62, size * .55))
        painter.setClipping(False)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#e4c5b5"), 2))
        painter.drawEllipse(QRectF(1, 1, size - 2, size - 2))
        painter.end()
        return canvas, source

    def _chat_avatar(self, role):
        avatar = QLabel()
        avatar.setObjectName("chatAvatar")
        avatar.setProperty("avatarRole", role)
        avatar.setFixedSize(42, 42)
        pixmap, source = self._avatar_pixmap(role)
        avatar.setProperty("avatarSource", source)
        avatar.setPixmap(pixmap)
        avatar.setAlignment(Qt.AlignCenter)
        return avatar

    def show_player_avatar_menu(self):
        """Open the warm player-avatar action card."""
        self._avatar_popup = self._popup_menu_factory(self)
        self._avatar_popup.add_action("选择头像", self.select_player_avatar)
        self._avatar_popup.add_action("恢复默认", self.reset_player_avatar)
        self._avatar_popup.popup_below(self.avatar_btn)

    def select_player_avatar(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择我的头像",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        try:
            ai.prepare_player_avatar(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "头像无法使用", str(exc))
            return
        self._set_log_messages(self._displayed_messages)

    def reset_player_avatar(self):
        try:
            ai.clear_player_avatar()
        except OSError as exc:
            QMessageBox.warning(self, "恢复失败", f"无法恢复默认头像：{exc}")
            return
        self._set_log_messages(self._displayed_messages)

    def _set_log_messages(self, messages):
        """Render actual rounded message widgets instead of rich-text blocks."""
        self._displayed_messages = list(messages)
        self._last_assistant_bubble = None
        chat_font_size = self._chat_font_px()
        while self.log_layout.count():
            item = self.log_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        if not self._displayed_messages:
            empty = QLabel("🐶 汪！来聊聊吧～")
            empty.setObjectName("emptyChat")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(
                f"color:#9b8174;font-size:{chat_font_size}px;padding:36px 12px;"
            )
            self.log_layout.addWidget(empty)
        else:
            width = self._message_width()
            for message in self._displayed_messages:
                role, text = message[:2]
                image = message[2] if len(message) > 2 else None
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 3, 0, 3)
                row_layout.setSpacing(8)

                display_text = text if role == "user" else ai.clean_assistant_reply(text)
                bubble = QLabel(display_text)
                bubble.setObjectName("chatMessage")
                bubble.setWordWrap(True)
                bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
                bubble.setMaximumWidth(width)
                bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
                if role == "user":
                    bubble.setProperty("messageRole", "user")
                    bubble.setStyleSheet(
                        f"background:#fbf1ec;color:#704f43;font-size:{chat_font_size}px;"
                        "border:1px solid #ead9d1;border-radius:18px;"
                        "padding:9px 13px;"
                    )
                    row_layout.addStretch(1)
                    if isinstance(image, dict):
                        preview_path = ai.resolve_history_image(
                            image.get("thumbnail")
                        )
                        preview = QPixmap(preview_path) if preview_path else QPixmap()
                        if not preview.isNull():
                            image_label = QLabel()
                            image_label.setObjectName("chatImage")
                            image_label.setPixmap(preview.scaled(
                                min(width, 190), 150,
                                Qt.KeepAspectRatio, Qt.SmoothTransformation,
                            ))
                            image_label.setStyleSheet(
                                "background:#fffaf6;border:1px solid #e7cdc0;"
                                "border-radius:12px;padding:3px;"
                            )
                            image_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                            image_box = QWidget()
                            image_layout = QVBoxLayout(image_box)
                            image_layout.setContentsMargins(0, 0, 0, 0)
                            image_layout.setSpacing(4)
                            image_layout.addWidget(image_label, 0, Qt.AlignRight)
                            image_layout.addWidget(bubble, 0, Qt.AlignRight)
                            row_layout.addWidget(image_box)
                        else:
                            row_layout.addWidget(bubble)
                    else:
                        row_layout.addWidget(bubble)
                    row_layout.addWidget(
                        self._chat_avatar("user"), 0, Qt.AlignTop
                    )
                else:
                    bubble.setProperty("messageRole", "assistant")
                    bubble.setStyleSheet(
                        f"background:#f5e9df;color:#55433a;font-size:{chat_font_size}px;"
                        "border:1px solid #dfc9ba;border-radius:18px;"
                        "padding:9px 13px;"
                    )
                    row_layout.addWidget(
                        self._chat_avatar("assistant"), 0, Qt.AlignTop
                    )
                    row_layout.addWidget(bubble)
                    row_layout.addStretch(1)
                    self._last_assistant_bubble = bubble
                self.log_layout.addWidget(row)
        self.log_layout.addStretch(1)
        self._scroll_log_to_bottom()
        # A new layout may finish after the current event loop returns.
        QTimer.singleShot(0, self._scroll_log_to_bottom)
        QTimer.singleShot(40, self._scroll_log_to_bottom)

    def _scroll_log_to_bottom(self):
        try:
            scrollbar = self.log.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except RuntimeError:
            # A delayed callback may arrive just after the window was closed.
            pass

    def _title_press(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_off = e.globalPos() - self.frameGeometry().topLeft()
    def _title_move(self, e):
        if self._drag_off is not None:
            self.move(e.globalPos() - self._drag_off)

    def show_near_pet(self):
        # clamp window size to screen so it always fits
        screen = self.pet.interface_screen_rect()
        max_w = screen.width() - 20
        max_h = screen.height() - 80
        w = min(self.s["chat_width"], max_w)
        h = min(self.s["chat_height"], max_h)
        if (w, h) != (self.width(), self.height()):
            self.setFixedSize(w, h)
        self.move(self.pet.interface_window_position(self.size(), gap=16))
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def send(self):
        if self.busy:
            return
        text = self.input.text().strip()
        if not text and not self._pending_image:
            return
        if ai.get_chat_mode() == "default" and not ai.has_default_chat_consent():
            choice = QMessageBox.question(
                self, "免费聊天说明",
                "默认聊天会将文字发送至限时免费模型，内容可能用于模型改进。是否同意并开始聊天？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if choice != QMessageBox.Yes:
                return
            ai.set_default_chat_consent(True)
        self.chat_notice.hide()
        # A real sent message counts as a chat interaction. Merely opening
        # and closing the panel no longer grants affection.
        self._progression_service.record_action(self.pet.state, "chats_opened")
        self._save_state_callback(self.pet.state)
        self.input.clear()
        # add user bubble immediately
        attachment = self._pending_image
        display_text = text
        if attachment and not display_text:
            display_text = f"我发送了一张图片：{attachment['filename']}"
        self._pending_user = display_text
        self._streaming = ""
        self._set_log_messages(
            self._history_messages()
            + [("user", display_text,
                attachment.get("history_image") if attachment else None),
               ("assistant", "…")]
        )
        self.busy = True
        self.send_btn.setEnabled(False)
        self._refresh_ai_tool_buttons()
        self.input.setPlaceholderText(f"{self._pet_name()} 正在思考…")
        # run AI in background thread so GUI doesn't freeze
        t = threading.Thread(
            target=self._ai_thread, args=(text, attachment), daemon=True
        )
        t.start()

    def _ai_thread(self, user_text, image_attachment=None):
        full = []
        err = None
        for kind, payload in ai.chat_stream(
                user_text, mem=self.mem,
                pet_name=self._pet_name(), image_attachment=image_attachment,
                pet_id=self.pet_id):
            if kind == "token":
                full.append(payload)
                self._bridge_provider().token.emit(payload)
            elif kind == "done":
                full = [payload]
                break
            elif kind == "error":
                err = payload
                break
        if err:
            if err in ai.DEFAULT_CHAT_ERRORS:
                reply = err
            else:
                reply = ai.fallback_reply(
                    user_text, err, pet_name=self._pet_name()
                )
            self._bridge_provider().error.emit(reply)
        else:
            self._bridge_provider().done.emit("".join(full))

    # slots (connected in main)
    def on_token(self, chunk):
        self._streaming += chunk
        # Updating the pending bubble in place keeps the history and scrollbar
        # stable. Rebuilding every row for every token caused blank flashes.
        text = ai.clean_assistant_reply(self._streaming) + "▍"
        try:
            if self._last_assistant_bubble is None:
                raise RuntimeError
            self._last_assistant_bubble.setText(text)
            self._last_assistant_bubble.adjustSize()
            self._scroll_log_to_bottom()
        except RuntimeError:
            # The window may have been rebuilt between queued token signals.
            self._set_log_messages(
                self._history_messages()
                + [("user", self._pending_user,
                    self._pending_image.get("history_image")
                    if self._pending_image else None),
                   ("assistant", text)]
            )

    def on_done(self, full):
        # commit to memory
        full = ai.clean_assistant_reply(full) or "我在呢，你再和我说一点吧。"
        image = self._pending_image.get("history_image") \
            if self._pending_image else None
        ai.append_history(
            self.mem, "user", self._pending_user, image=image,
            pet_id=self.pet_id,
        )
        ai.append_history(
            self.mem, "assistant", full, pet_id=self.pet_id
        )
        self._progression_service.record_action(self.pet.state, "ai_replies")
        self._save_state_callback(self.pet.state)
        self.mem = ai.load_memory(pet_id=self.pet_id)
        self._pending_user = None
        self.clear_pending_image(keep_history=True)
        self._streaming = ""
        self.busy = False
        self.send_btn.setEnabled(True)
        self._refresh_ai_tool_buttons()
        self.input.setPlaceholderText(
            f"跟 {self._pet_name()} 说点什么…"
        )
        self.input.setFocus()
        self._set_log_messages(self._history_messages())
        # also show a speech bubble on the pet
        short = full if len(full) < 40 else full[:38] + "…"
        self.pet.say(short, 3000)

    def on_error(self, reply):
        if reply == "default_quota_exhausted":
            self.chat_notice.setText("今日免费次数已用完，可切换自定义。")
            self.chat_notice.show()
            self._finish_chat_request(keep_history_image=False)
            self.personal_mode_btn.setFocus()
            return
        if reply == "default_consent_required":
            self.chat_notice.setText("需要先同意免费聊天说明，才能发送消息。")
            self.chat_notice.show()
            self._finish_chat_request(keep_history_image=False)
            return
        if reply == "personal_key_required_for_image":
            self.chat_notice.setText(
                "图片聊天需要配置自己的 API Key，并使用 GLM-4.6V-Flash。"
            )
            self.chat_notice.show()
            self._finish_chat_request(keep_history_image=False)
            self.personal_mode_btn.setFocus()
            return
        if reply == "personal_api_key_required":
            self.chat_notice.setText(
                "自己配置 API 模式还没有可用的 Key，请点击聊天模式完成配置。"
            )
            self.chat_notice.show()
            self._finish_chat_request(keep_history_image=False)
            self.personal_mode_btn.setFocus()
            return
        if reply == "default_provider_unavailable":
            self.chat_notice.setText("免费聊天暂不可用，请稍后再试。")
            self.chat_notice.show()
            self._finish_chat_request(keep_history_image=False)
            return
        reply = ai.clean_assistant_reply(reply) or "我在呢，你再和我说一点吧。"
        if self._pending_user:
            image = self._pending_image.get("history_image") \
                if self._pending_image else None
            ai.append_history(
                self.mem, "user", self._pending_user, image=image,
                pet_id=self.pet_id,
            )
            ai.append_history(
                self.mem, "assistant", reply, pet_id=self.pet_id
            )
            self._progression_service.record_action(self.pet.state, "ai_replies")
            self._save_state_callback(self.pet.state)
        self.mem = ai.load_memory(pet_id=self.pet_id)
        self._pending_user = None
        self.clear_pending_image(keep_history=True)
        self._streaming = ""
        self.busy = False
        self.send_btn.setEnabled(True)
        self._refresh_ai_tool_buttons()
        self.input.setPlaceholderText(
            f"跟 {self._pet_name()} 说点什么…"
        )
        self._set_log_messages(self._history_messages())
        self.pet.say(reply[:30], 2000)

    def _finish_chat_request(self, keep_history_image=False):
        """Return the composer to an interactive state after a terminal event."""
        self._pending_user = None
        self.clear_pending_image(keep_history=keep_history_image)
        self._streaming = ""
        self.busy = False
        self.send_btn.setEnabled(True)
        self._refresh_ai_tool_buttons()
        self.input.setPlaceholderText(
            f"跟 {self._pet_name()} 说点什么…"
        )
        self._set_log_messages(self._history_messages())

    def confirm_clear_memory(self):
        """Ask for confirmation in the pet's voice; on yes, wipe memory."""
        if self.busy:
            return
        dialog = self._confirm_dialog_factory(
            self,
            title="清除记忆",
            message="主人，我会忘记你的。要和我重新认识一次吗？",
            accept_text="重新相识",
            reject_text="继续陪着我",
        )
        if dialog.exec_() == QDialog.Accepted:
            # wipe memory
            try:
                path = ai.memory_path(self.pet_id)
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
            ai.remove_memory_thumbnails(self.mem)
            self.clear_pending_image()
            self.mem = ai._default_memory()
            self.mem["pet_name"] = self._pet_name()
            ai.save_memory(self.mem, pet_id=self.pet_id)
            self._set_log_messages([
                ("assistant", "汪？你是…我们重新认识一下吧。")
            ])
            self.pet.say("汪？我们重新认识一下吧 🐶", 2500)

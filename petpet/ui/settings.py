"""Static presets used by Petpet's settings window."""

from PyQt5.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from petpet.app.settings import DEFAULT_SETTINGS, save_settings
from petpet.ui.common import independent_pixel_font
from petpet.ui.controls import StepperControl, ThreeLevelSlider, ToggleSwitch


HEALTH_PRESETS = (
    {
        "remind_drink_min": 120,
        "remind_rest_min": 180,
        "remind_stand_min": 90,
    },
    {
        "remind_drink_min": 60,
        "remind_rest_min": 90,
        "remind_stand_min": 45,
    },
    {
        "remind_drink_min": 40,
        "remind_rest_min": 60,
        "remind_stand_min": 30,
    },
)

PERSONALITY_PRESETS = (
    {
        "needy_speak_chance": 0.05,
        "ask_weight_normal": 0.2,
        "ask_weight_needy": 0.25,
        "nudge_idle_min": 3600,
        "nudge_gap_min": 21600,
    },
    {
        "needy_speak_chance": DEFAULT_SETTINGS["needy_speak_chance"],
        "ask_weight_normal": DEFAULT_SETTINGS["ask_weight_normal"],
        "ask_weight_needy": DEFAULT_SETTINGS["ask_weight_needy"],
        "nudge_idle_min": DEFAULT_SETTINGS["nudge_idle_min"],
        "nudge_gap_min": DEFAULT_SETTINGS["nudge_gap_min"],
    },
    {
        "needy_speak_chance": 0.3,
        "ask_weight_normal": 1.0,
        "ask_weight_needy": 1.25,
        "nudge_idle_min": 900,
        "nudge_gap_min": 3600,
    },
)

class SettingsWindow(QWidget):
    """Tunable settings panel — chat window size, decay rates, chatter frequency, etc."""
    CHANGED = pyqtSignal()
    PREFERRED_WIDTH = 840
    PREFERRED_HEIGHT = 960
    COMPACT_MIN_WIDTH = 648
    COMPACT_MIN_HEIGHT = 708

    HEALTH_PRESETS = HEALTH_PRESETS
    PERSONALITY_PRESETS = PERSONALITY_PRESETS

    FIELDS = [
        # (key, label, min, max, step, hint)
        ("chat_font_size", "聊天字体大小", 12, 32, 1,
         "聊天记录、输入框和按钮的文字大小"),
        ("ui_font_size", "设置页字体大小", 20, 40, 1,
         "调整当前设置页面的整体文字大小"),
        ("remind_drink_min","喝水提醒间隔(分钟)", 0, 300, 5, "0=关 60=每小时"),
        ("remind_rest_min", "休息眼睛间隔(分钟)", 0, 300, 5, "0=关 90=每1.5小时"),
        ("remind_stand_min","起身活动间隔(分钟)", 0, 300, 5, "0=关 45=每45分钟"),
        ("needy_speak_chance", "需求自言自语概率", 0.0, 1.0, 0.05, "0=安静 1=每次都说"),
        ("ask_weight_normal", "自主搭话权重(平时)", 0.0, 3.0, 0.1, "越大越爱搭话"),
        ("ask_weight_needy",  "自主搭话权重(需要照顾)", 0.0, 3.0, 0.1, "饿了/无聊时权重"),
        ("nudge_idle_min", "AI 主动找你最短闲置(秒)", 300, 7200, 300, "多久不理它才会主动找你"),
        ("nudge_gap_min",  "AI 主动找你最小间隔(秒)", 1800, 21600, 1800, "两次主动找你的最小间隔"),
    ]

    SWITCHES = [
        ("always_on_top", "小狗始终置顶", "关闭后允许其他窗口遮挡小狗"),
        ("sound_enabled", "互动音效", "喂食、玩耍和抚摸时播放声音"),
        ("auto_check_updates", "启动时检查更新", "开启后每次启动都会检查 GitHub 最新版本"),
    ]

    CHAT_SIZES = [
        ("小巧 · 480 × 620", (480, 620)),
        ("舒适 · 560 × 720", (560, 720)),
        ("标准 · 640 × 820", (640, 820)),
        ("宽敞 · 720 × 900", (720, 900)),
        ("超大 · 800 × 980", (800, 980)),
    ]

    def __init__(self, pet_window):
        super().__init__()
        self.pet = pet_window
        self.s = pet_window.settings
        self.inputs = {}
        self.switch_labels = {}
        self.chat_size_combo = None

        self._drag_offset = None
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("settingsWindow")
        self.setWindowTitle("温馨设置")
        self._build_ui()
        self._apply_font()
        screen = QApplication.primaryScreen().availableGeometry()
        self.setFixedSize(
            max(
                self.COMPACT_MIN_WIDTH,
                min(self.PREFERRED_WIDTH, screen.width() - 60),
            ),
            max(
                self.COMPACT_MIN_HEIGHT,
                min(self.PREFERRED_HEIGHT, screen.height() - 80),
            ),
        )

    def show_near_pet(self):
        """Show settings centered on the active pet's screen."""
        screen = self.pet.interface_screen_rect()
        window_size = self.size()
        self.move(QPoint(
            screen.x() + (screen.width() - window_size.width()) // 2,
            screen.y() + (screen.height() - window_size.height()) // 2,
        ))
        self.show()
        self.raise_()
        self.activateWindow()

    def _apply_font(self):
        fs = int(self.s.get("ui_font_size", 24))
        font_scale = fs / 24.0
        title_fs = max(1, int(round(31 * font_scale)))
        group_fs = max(1, int(round(25 * font_scale)))
        body_fs = max(1, int(round(23 * font_scale)))
        detail_fs = max(1, int(round(20 * font_scale)))
        self.setStyleSheet(f"""
            QWidget {{
                background:transparent;
                font-family:'Microsoft YaHei',sans-serif;
                color:#65483b;
            }}
            QWidget#settingsWindow {{
                background:transparent;
                border:0;
            }}
            QFrame#settingsCard {{
                background:#fff8ec;
                border:1px solid #e7c4ad;
                border-radius:24px;
            }}
            QScrollArea, QScrollArea > QWidget > QWidget {{
                background:transparent;
                border:0;
            }}
            QLabel {{ background:transparent; }}
            QLabel#settingsTitle {{
                font-weight:900;
                color:#754b3a;
            }}
            QLabel#settingsSubtitle {{
                color:#a27a68;
            }}
            QLabel#settingsStatus {{
                color:#cf765e;
                font-weight:800;
                padding:0;
            }}
            QLabel#switchState {{
                color:#a36b58;
                font-weight:700;
            }}
            QLabel#settingDescription {{
                color:#aa8270;
            }}
            QComboBox, QDoubleSpinBox, QSpinBox {{
                background:#fffdf9;
                border:1px solid #e7c6ad;
                border-radius:10px;
                padding:7px 12px;
                color:#65483b;
                selection-background-color:#ffc9b8;
            }}
            QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
                border:2px solid #f39b80;
            }}
            QComboBox::drop-down {{
                width:34px;
                border:0;
            }}
            QComboBox QAbstractItemView {{
                background:#fffdf9;
                border:1px solid #e7c6ad;
                selection-background-color:#ffe1d4;
                selection-color:#65483b;
                padding:6px;
            }}
            QPushButton {{
                background:#f28f76;
                color:#fff;
                border:0;
                border-radius:12px;
                padding:11px 21px;
                font-weight:700;
            }}
            QPushButton:hover {{ background:#f5a08a; }}
            QPushButton:pressed {{ background:#df7d67; }}
            QPushButton#stepButton {{
                background:#fff0e6;
                color:#b36650;
                border:1px solid #efc8b3;
                border-radius:10px;
                padding:0;
                font-weight:900;
            }}
            QPushButton#stepButton:hover {{
                background:#ffe1d3;
                border-color:#e8a88b;
            }}
            QPushButton#stepButton:pressed {{ background:#ffd1bf; }}
            QPushButton#closeButton {{
                background:#ffe5dc;
                color:#a96254;
                border:1px solid #efc6b8;
                border-radius:16px;
                padding:0;
                font-weight:600;
            }}
            QPushButton#closeButton:hover {{
                background:#f49a84;
                color:#ffffff;
                border-color:#ed8a73;
            }}
            QPushButton#closeButton:pressed {{
                background:#dc765f;
                color:#ffffff;
            }}
            QPushButton#reset {{ background:#d7b9a6; color:#6d5145; }}
            QPushButton#reset:hover {{ background:#e2c8b8; }}
            QPushButton#reset:pressed {{ background:#c9a892; }}
            QPushButton#threeLevelOption {{
                min-height:38px; padding:0; border-radius:16px;
                color:#9a796b; background:#f8ebe4;
                border:1px solid transparent;
            }}
            QPushButton#threeLevelOption:checked {{
                color:#70483c; background:#f8dcd7;
                border-color:#efc4bb;
            }}
            QSlider#threeLevelSlider {{ min-height:24px; max-height:24px; }}
            QSlider#threeLevelSlider::groove:horizontal {{
                height:8px; background:#efdcd2; border-radius:4px;
            }}
            QSlider#threeLevelSlider::sub-page:horizontal {{
                background:#edb8ae; border-radius:4px;
            }}
            QSlider#threeLevelSlider::handle:horizontal {{
                width:22px; margin:-7px 0; background:#fff9f4;
                border:2px solid #df998b; border-radius:11px;
            }}
            QGroupBox {{
                background:#fffdf8;
                border:1px solid #edcfb5;
                border-radius:17px;
                margin-top:17px;
                padding:21px 18px 15px 18px;
            }}
            QGroupBox::title {{
                color:#925d49;
                font-weight:800;
                left:15px;
                padding:0 8px;
                background:#fff8ec;
            }}
            QScrollBar:vertical {{
                background:transparent;
                width:10px;
                margin:4px 0;
            }}
            QScrollBar::handle:vertical {{
                background:#e8bfa8;
                border-radius:5px;
                min-height:36px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height:0;
            }}
        """)
        self.setFont(independent_pixel_font(body_fs))
        if hasattr(self, "title_label"):
            self.title_label.setFont(independent_pixel_font(title_fs, QFont.Bold))
        if hasattr(self, "subtitle_label"):
            self.subtitle_label.setFont(independent_pixel_font(detail_fs))
        for label in self.findChildren(QLabel, "settingsGroupTitle"):
            label.setFont(independent_pixel_font(group_fs, QFont.Bold))
        for label in self.findChildren(QLabel, "settingDescription"):
            label.setFont(independent_pixel_font(detail_fs))

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        self.settings_card = QFrame()
        self.settings_card.setObjectName("settingsCard")
        outer.addWidget(self.settings_card)
        root = QVBoxLayout(self.settings_card)
        root.setContentsMargins(26, 18, 26, 18)
        root.setSpacing(8)

        title_bar = QFrame()
        title_bar.setObjectName("settingsTitleBar")
        title_bar.setCursor(Qt.ArrowCursor)
        title_row = QHBoxLayout(title_bar)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        self.title_label = QLabel("🌼 温馨设置")
        self.title_label.setObjectName("settingsTitle")
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setToolTip("关闭温馨设置")
        close_button.setFixedSize(36, 36)
        close_button.clicked.connect(self.close)
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        title_row.addWidget(close_button)
        title_bar.mousePressEvent = self._title_bar_press
        title_bar.mouseMoveEvent = self._title_bar_move
        title_bar.mouseReleaseEvent = self._title_bar_release
        root.addWidget(title_bar)

        self.subtitle_label = QLabel("选择适合你和小狗的陪伴方式。")
        self.subtitle_label.setObjectName("settingsSubtitle")
        root.addWidget(self.subtitle_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 4, 10, 4)
        content_layout.setSpacing(10)
        content_layout.setAlignment(Qt.AlignTop)

        content_layout.addWidget(self._interface_group())
        content_layout.addWidget(self._preference_group(
            "🌿 健康提醒",
            "喝水、休息眼睛和起身活动都会保留，只调整提醒频率。",
            "health_level", ("少", "适中", "多"),
            ("remind_drink_min", "remind_rest_min", "remind_stand_min"),
            self.HEALTH_PRESETS,
        ))
        content_layout.addWidget(self._preference_group(
            "🐾 性格偏好",
            "从安静陪伴到爱说话、爱提醒、爱主动找你。",
            "personality_level", ("文静", "适中", "活泼"),
            ("needy_speak_chance", "ask_weight_normal", "ask_weight_needy",
             "nudge_idle_min", "nudge_gap_min"),
            self.PERSONALITY_PRESETS,
        ))
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("settingsStatus")
        self.status_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(14)
        reset_btn = QPushButton("恢复全部默认值")
        reset_btn.setObjectName("reset")
        reset_btn.setMinimumHeight(44)
        reset_btn.clicked.connect(self.reset_defaults)
        ok_btn = QPushButton("保存并立即应用")
        ok_btn.setMinimumHeight(44)
        ok_btn.clicked.connect(self.apply)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)

    def _title_bar_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPos() - self.frameGeometry().topLeft()
            )
            event.accept()

    def _title_bar_move(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()

    def _title_bar_release(self, event):
        self._drag_offset = None
        event.accept()

    def _interface_group(self):
        group = QGroupBox()
        layout = QVBoxLayout(group)
        layout.setSpacing(9)
        group_title = QLabel("🍑 界面体验")
        group_title.setObjectName("settingsGroupTitle")
        layout.addWidget(group_title)

        combo = QComboBox()
        combo.setMinimumWidth(220)
        for label, size in self.CHAT_SIZES:
            combo.addItem(label, size)
        self.chat_size_combo = combo
        self._select_chat_size(
            int(self.s.get("chat_width", 640)),
            int(self.s.get("chat_height", 820)),
        )
        self._add_row(
            layout,
            "聊天窗口大小",
            "五档常用比例，从小巧到超大",
            combo,
        )

        for key in ("chat_font_size", "ui_font_size"):
            self._add_numeric_row(layout, key)
        for key, label, hint in self.SWITCHES:
            switch = ToggleSwitch()
            switch.setChecked(bool(self.s.get(key, False)))
            self.inputs[key] = switch
            state = QLabel()
            state.setFixedWidth(36)
            state.setObjectName("switchState")
            self.switch_labels[key] = state
            switch.toggled.connect(
                lambda checked, setting=key:
                self._update_switch_label(setting, checked)
            )
            self._update_switch_label(key, switch.isChecked())
            control = QWidget()
            control_layout = QHBoxLayout(control)
            control_layout.setContentsMargins(0, 0, 0, 0)
            control_layout.setSpacing(7)
            control_layout.addWidget(state)
            control_layout.addWidget(switch)
            self._add_row(layout, label, hint, control)
        return group

    def _preference_group(self, title, hint, key, labels, field_keys, presets):
        group = QGroupBox()
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("settingsGroupTitle")
        description = QLabel(hint)
        description.setObjectName("settingDescription")
        description.setWordWrap(True)
        control = ThreeLevelSlider(labels)
        control.setValue(self._nearest_preset_index(field_keys, presets))
        self.inputs[key] = control
        layout.addWidget(title_label)
        layout.addWidget(description)
        layout.addWidget(control)
        return group

    def _group(self, title, keys):
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setSpacing(9)
        for key in keys:
            self._add_numeric_row(layout, key)
        return group

    def _add_numeric_row(self, layout, key):
        label, minimum, maximum, step, hint = self._field_meta(key)
        control = StepperControl(
            minimum, maximum, step, self.s.get(key, 0)
        )
        control.setToolTip(hint)
        self.inputs[key] = control
        self._add_row(layout, label, hint, control)

    def _add_row(self, layout, label, hint, control):
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(4, 5, 4, 5)
        row.setSpacing(16)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        title = QLabel(label)
        title.setStyleSheet("font-weight:800; color:#704b3c;")
        description = QLabel(hint)
        description.setObjectName("settingDescription")
        description.setWordWrap(True)
        text_layout.addWidget(title)
        text_layout.addWidget(description)
        row.addLayout(text_layout, 1)
        row.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(row_widget)

    def _update_switch_label(self, key, checked):
        label = self.switch_labels.get(key)
        if label is not None:
            label.setText("开启" if checked else "关闭")

    def _select_chat_size(self, width, height):
        if self.chat_size_combo is None:
            return
        best_index = 0
        best_distance = None
        for index in range(self.chat_size_combo.count()):
            size = self.chat_size_combo.itemData(index)
            distance = abs(size[0] - width) + abs(size[1] - height)
            if best_distance is None or distance < best_distance:
                best_index = index
                best_distance = distance
        self.chat_size_combo.setCurrentIndex(best_index)

    def _field_meta(self, key):
        for k, label, mn, mx, step, hint in self.FIELDS:
            if k == key: return label, mn, mx, step, hint
        return key, 0, 100, 1, ""

    def _nearest_preset_index(self, keys, presets):
        scales = {
            key: max(
                max(float(preset[key]) for preset in presets)
                - min(float(preset[key]) for preset in presets),
                1.0,
            )
            for key in keys
        }

        def distance(preset):
            total = 0.0
            for key in keys:
                target = float(preset[key])
                current = float(self.s.get(key, DEFAULT_SETTINGS.get(key, target)))
                total += abs(current - target) / scales[key]
            return total
        return min(range(len(presets)), key=lambda index: distance(presets[index]))

    def apply(self):
        previous = dict(self.s)
        width, height = self.chat_size_combo.currentData()
        self.s["chat_width"] = int(width)
        self.s["chat_height"] = int(height)
        for key, control in self.inputs.items():
            if key in {"health_level", "personality_level"}:
                continue
            if isinstance(control, ToggleSwitch):
                value = bool(control.isChecked())
            else:
                value = control.value()
                default = DEFAULT_SETTINGS.get(key)
                if isinstance(default, int) and not isinstance(default, bool):
                    value = int(value)
                elif isinstance(default, float):
                    value = float(value)
            self.s[key] = value
        for key, value in self.HEALTH_PRESETS[
                self.inputs["health_level"].value()].items():
            self.s[key] = value
        for key, value in self.PERSONALITY_PRESETS[
                self.inputs["personality_level"].value()].items():
            self.s[key] = value
        self.s.pop("chat_bubble_max", None)
        save_settings(self.s)
        self.pet.apply_runtime_settings(previous)
        self._apply_font()
        self.CHANGED.emit()
        self.pet.say("好啦，记住了~", 1500)
        self.status_label.setText("✓ 所有设置已保存并立即应用")
        QTimer.singleShot(1800, lambda: self.status_label.setText(""))

    def reset_defaults(self):
        previous = dict(self.s)
        self.s.clear()
        self.s.update(DEFAULT_SETTINGS)
        self.s.pop("chat_bubble_max", None)
        save_settings(self.s)
        self.pet.settings = self.s
        self._select_chat_size(
            DEFAULT_SETTINGS["chat_width"],
            DEFAULT_SETTINGS["chat_height"],
        )
        for key, control in self.inputs.items():
            if key == "health_level":
                control.setValue(1)
                continue
            if key == "personality_level":
                control.setValue(1)
                continue
            value = DEFAULT_SETTINGS.get(key, 0)
            if isinstance(control, ToggleSwitch):
                control.setChecked(bool(value))
            else:
                control.setValue(value)
        self.pet.apply_runtime_settings(previous)
        self._apply_font()
        self.pet.say("已恢复默认~", 1500)
        self.status_label.setText("✓ 已恢复全部默认值并立即应用")
        QTimer.singleShot(1800, lambda: self.status_label.setText(""))
        self.CHANGED.emit()

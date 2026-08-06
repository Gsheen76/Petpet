"""Live parameter tuning window for Petpet gameplay feel experiments."""

from __future__ import annotations

import json

from PyQt5.QtCore import QSignalBlocker, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)


# key, label, minimum, maximum, step, unit, hint
PARAMETER_GROUPS = (
    (
        "宠物尺寸",
        (
            ("pet_width", "窗口宽度", 90, 280, 1, "px", "透明窗口宽度"),
            ("pet_height", "窗口高度", 110, 320, 1, "px", "包含气泡预留空间"),
            ("dog_height", "小狗绘制高度", 70, 260, 1, "px", "只改变绘制区域"),
        ),
    ),
    (
        "运动手感",
        (
            ("gravity", "重力", 400, 4200, 50, "px/s²", "拖拽松手后的下落速度"),
            ("wall_bounce", "墙壁弹性", 0, 1, 0.01, "", "撞到左右边缘保留的速度"),
            ("floor_bounce", "地面弹性", 0, 1, 0.01, "", "落地时保留的向上速度"),
            ("ground_friction", "地面摩擦", 0.5, 0.99, 0.01, "", "落地后横向滑行衰减"),
            ("walk_speed_min", "自主行走最低速度", 10, 300, 5, "px/s", "自主走路随机速度下限"),
            ("walk_speed_max", "自主行走最高速度", 20, 420, 5, "px/s", "自主走路随机速度上限"),
            ("auto_sleep_walk_speed", "自动休息行走速度", 20, 300, 5, "px/s", "精力不足走向角落的速度"),
        ),
    ),
    (
        "动画速度",
        (
            ("animation_idle_fps", "待机", 1, 30, 1, "FPS", "待机呼吸/眨眼"),
            ("animation_walk_fps", "行走", 1, 30, 1, "FPS", "连续行走帧"),
            ("animation_eat_fps", "进食", 1, 30, 1, "FPS", "进食连续帧"),
            ("animation_pet_fps", "摸头", 1, 30, 1, "FPS", "摸头连续帧"),
            ("animation_play_fps", "玩耍", 1, 30, 1, "FPS", "接球扑跃"),
            ("animation_sleep_fps", "睡觉", 0.5, 12, 0.5, "FPS", "睡觉呼吸"),
            ("animation_dig_reward_fps", "挖宝奖励", 1, 30, 1, "FPS", "挖宝发现动画"),
        ),
    ),
    (
        "状态与自动行为",
        (
            ("decay_hunger", "清醒饥饿衰减", 0, 1, 0.01, "/tick", "每 2 秒减少"),
            ("decay_mood", "清醒心情衰减", 0, 1, 0.01, "/tick", "每 2 秒减少"),
            ("decay_energy", "清醒精力衰减", 0, 1, 0.5, "/tick", "每 2 秒减少"),
            ("decay_hunger_sleeping", "睡觉饥饿衰减", 0, 1, 0.01, "/tick", "睡觉时每 2 秒减少"),
            ("decay_energy_sleeping_gain", "睡觉精力恢复", 0, 15, 0.5, "/tick", "睡觉时每 2 秒恢复"),
            ("auto_sleep_energy_threshold", "自动睡觉阈值", 0, 80, 1, "%", "低于此精力自动休息"),
            ("auto_wake_energy_threshold", "自动醒来阈值", 20, 100, 1, "%", "高于此精力自动醒来"),
            ("autonomy_idle_weight", "自主待机权重", 0, 20, 0.5, "", "越大越常待机"),
            ("autonomy_walk_weight", "自主行走权重", 0, 20, 0.5, "", "越大越常走动"),
            ("autonomy_sit_weight", "自主坐下权重", 0, 20, 0.5, "", "越大越常坐下"),
            ("dig_discovery_chance", "挖宝发现概率", 0, 1, 0.01, "", "每次检查的发现概率"),
            ("dig_cooldown_minutes", "挖宝冷却", 1, 240, 1, "min", "两次挖宝发现的间隔"),
        ),
    ),
    (
        "互动反馈",
        (
            ("petting_affection_gain", "抚摸好感", 0, 20, 1, "点", "每次可获得好感"),
            ("feeding_affection_gain", "喂食好感", 0, 20, 1, "点", "冷却结束后获得"),
            ("play_affection_gain", "玩耍好感", 0, 20, 1, "点", "冷却结束后获得"),
            ("petting_cooldown", "抚摸好感冷却", 0, 300, 1, "秒", "同类好感再次生效间隔"),
            ("feeding_cooldown", "喂食好感冷却", 0, 1800, 5, "秒", "同类好感再次生效间隔"),
            ("play_cooldown", "玩耍好感冷却", 0, 1800, 5, "秒", "同类好感再次生效间隔"),
            ("feed_animation_duration", "进食动作时长", 0.2, 6, 0.1, "秒", "喂食后动作持续时间"),
        ),
    ),
    (
        "小游戏",
        (
            ("coin_catch_duration", "金币雨局时长", 5, 60, 1, "秒", "一局金币雨持续时间"),
            ("coin_target_lifetime", "金币停留时间", 0.2, 3, 0.1, "秒", "金币换位置的频率"),
            ("lucky_swap_1", "幸运爪爪第 1 轮速度", 0.1, 2, 0.01, "秒", "每次交换耗时"),
            ("lucky_swap_2", "幸运爪爪第 2 轮速度", 0.05, 2, 0.01, "秒", "每次交换耗时"),
            ("lucky_swap_3", "幸运爪爪第 3 轮速度", 0.03, 2, 0.01, "秒", "每次交换耗时"),
        ),
    ),
)


_IMMEDIATE_EFFECT_KEYS = {
    "pet_width", "pet_height", "dog_height",
    "gravity", "wall_bounce", "floor_bounce", "ground_friction",
    "animation_idle_fps", "animation_walk_fps", "animation_eat_fps",
    "animation_pet_fps", "animation_play_fps", "animation_sleep_fps",
    "animation_dig_reward_fps", "decay_hunger", "decay_mood",
    "decay_energy", "decay_hunger_sleeping",
    "decay_energy_sleeping_gain", "feed_animation_duration",
    "coin_catch_duration", "coin_target_lifetime", "lucky_swap_1",
    "lucky_swap_2", "lucky_swap_3",
}

_DEFERRED_EFFECT_KEYS = {
    "walk_speed_min", "walk_speed_max", "auto_sleep_walk_speed",
    "auto_sleep_energy_threshold", "auto_wake_energy_threshold",
    "autonomy_idle_weight", "autonomy_walk_weight",
    "autonomy_sit_weight", "dig_discovery_chance", "dig_cooldown_minutes",
    "petting_affection_gain", "feeding_affection_gain",
    "play_affection_gain", "petting_cooldown", "feeding_cooldown",
    "play_cooldown",
}

PARAMETER_EFFECT_TIMING = {
    key: "立即生效" for key in _IMMEDIATE_EFFECT_KEYS
}
PARAMETER_EFFECT_TIMING.update({
    key: "下一次行为生效" for key in _DEFERRED_EFFECT_KEYS
})


class ParameterTunerWindow(QWidget):
    """Scrollable live tuning panel; every control applies immediately."""

    PREFERRED_WIDTH = 1080
    PREFERRED_HEIGHT = 920

    def __init__(self, pet):
        super().__init__()
        self.pet = pet
        self._syncing = False
        self.controls = {}
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setObjectName("parameterTuner")
        self.setWindowTitle("Petpet · 参数调试")
        self.setFixedSize(self.PREFERRED_WIDTH, self.PREFERRED_HEIGHT)
        self._apply_style()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("🧪 参数调试器")
        title.setObjectName("tunerTitle")
        subtitle = QLabel("修改会立即作用于当前运行中的小狗和小游戏")
        subtitle.setObjectName("tunerSubtitle")
        header_text = QVBoxLayout()
        header_text.setSpacing(1)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)
        close_button = QPushButton("×")
        close_button.setObjectName("tunerClose")
        close_button.setFixedSize(34, 34)
        close_button.setToolTip("关闭参数调试器")
        close_button.clicked.connect(self.close)
        header.addWidget(close_button)
        root.addLayout(header)

        self.status = QLabel("实时调节中 · 保存后下次启动仍会使用这组参数")
        self.status.setObjectName("tunerStatus")
        root.addWidget(self.status)

        scroll = QScrollArea()
        scroll.setObjectName("tunerScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 8, 8)
        content_layout.setSpacing(12)
        for group_name, definitions in PARAMETER_GROUPS:
            group = QFrame()
            group.setObjectName("tunerGroup")
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(14, 12, 14, 12)
            group_layout.setSpacing(8)
            group_title = QLabel(group_name)
            group_title.setObjectName("tunerGroupTitle")
            group_layout.addWidget(group_title)
            for definition in definitions:
                group_layout.addWidget(self._parameter_row(*definition))
            content_layout.addWidget(group)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        reset = QPushButton("恢复默认")
        reset.setObjectName("tunerSecondary")
        reset.clicked.connect(self.reset_defaults)
        copy = QPushButton("复制当前参数")
        copy.setObjectName("tunerSecondary")
        copy.clicked.connect(self.copy_parameters)
        save = QPushButton("保存调试参数")
        save.setObjectName("tunerPrimary")
        save.clicked.connect(self.save_parameters)
        footer.addWidget(reset)
        footer.addWidget(copy)
        footer.addStretch(1)
        footer.addWidget(save)
        root.addLayout(footer)

    def _apply_style(self):
        self.setStyleSheet("""
            QWidget#parameterTuner { background:#fbf7f3; color:#5f4b42;
                font-family:'Microsoft YaHei',sans-serif; font-size:18px; }
            QLabel#tunerTitle { color:#704b3d; font-size:30px; font-weight:800; }
            QLabel#tunerSubtitle { color:#a18475; font-size:17px; }
            QLabel#tunerStatus { background:#f6e9e0; color:#8e6b5b;
                border:1px solid #ead8cc; border-radius:11px; padding:11px 14px;
                min-height:26px; }
            QFrame#tunerGroup { background:#fffdfa; border:1px solid #eaded5;
                border-radius:14px; }
            QLabel#tunerGroupTitle { color:#8c5e4d; font-size:22px; font-weight:800;
                padding-bottom:4px; }
            QLabel#tunerLabel { color:#624d43; font-size:18px; font-weight:700; }
            QLabel#tunerHint { color:#ad9487; font-size:15px; }
            QLabel#tunerFeedback { color:#9a7563; font-size:15px; padding:2px 0; }
            QDoubleSpinBox { background:#fff; color:#5d493f; border:1px solid #decabd;
                border-radius:9px; padding:7px 9px; min-width:124px; min-height:38px;
                font-size:18px; }
            QSlider::groove:horizontal { height:8px; background:#eddfd6; border-radius:4px; }
            QSlider::handle:horizontal { width:22px; margin:-8px 0; background:#d98a72;
                border:3px solid #fff; border-radius:11px; }
            QPushButton#tunerReset { background:transparent; color:#a77c6a;
                border:0; font-size:22px; padding:3px 7px; min-height:38px; }
            QPushButton#tunerReset:hover { color:#c46452; background:#faebe4; border-radius:8px; }
            QPushButton#tunerSecondary { background:#fffaf6; color:#866052;
                border:1px solid #e2cfc4; border-radius:10px; padding:11px 17px;
                min-height:44px; font-size:18px; font-weight:700; }
            QPushButton#tunerSecondary:hover { background:#f8e9e0; }
            QPushButton#tunerPrimary { background:#d98068; color:white; border:0;
                border-radius:10px; padding:11px 20px; min-height:44px;
                font-size:18px; font-weight:800; }
            QPushButton#tunerPrimary:hover { background:#e29079; }
            QPushButton#tunerClose { background:transparent; color:#a77c6a; border:0;
                font-size:30px; border-radius:20px; min-height:40px; }
            QPushButton#tunerClose:hover { background:#f2ddd3; color:#8c5949; }
            QScrollArea#tunerScroll { background:transparent; border:0; }
            QScrollBar:vertical { width:13px; background:#f5ede8; border-radius:6px; }
            QScrollBar::handle:vertical { background:#d9c2b5; min-height:42px; border-radius:6px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """)

    def _parameter_row(self, key, label, minimum, maximum, step, unit, hint):
        row = QFrame()
        row.setObjectName("tunerRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(6)
        name = QLabel(label)
        name.setObjectName("tunerLabel")
        note = QLabel(f"{hint}{(' · ' + unit) if unit else ''}")
        note.setObjectName("tunerHint")
        runtime_value = float(self.pet.debug_parameter_value(key))
        value = QDoubleSpinBox()
        decimals = max(0, len(str(step).rstrip("0").split(".")[-1])) if step < 1 else 0
        value.setDecimals(decimals)
        value.setRange(min(float(minimum), runtime_value), max(float(maximum), runtime_value))
        value.setSingleStep(step)
        value.setValue(runtime_value)
        value.setAlignment(Qt.AlignRight)
        value.setToolTip(f"{label}：{hint}")
        reset = QPushButton("↺")
        reset.setObjectName("tunerReset")
        reset.setFixedWidth(28)
        reset.setToolTip("恢复此项默认值")
        reset.clicked.connect(lambda _checked=False, selected=key: self.reset_parameter(selected))
        top.addWidget(name)
        top.addWidget(note)
        top.addStretch(1)
        top.addWidget(value)
        top.addWidget(reset)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(
            round(min(float(minimum), runtime_value) / step),
            round(max(float(maximum), runtime_value) / step),
        )
        slider.setValue(round(value.value() / step))
        slider.setToolTip(f"拖动调节：{label}")
        feedback = QLabel()
        feedback.setObjectName("tunerFeedback")
        feedback.setWordWrap(True)
        layout.addLayout(top)
        layout.addWidget(feedback)
        layout.addWidget(slider)
        self.controls[key] = {
            "spin": value,
            "slider": slider,
            "feedback": feedback,
            "default": self.pet.debug_parameter_defaults()[key],
            "step": step,
        }
        self._update_feedback(key, value.value())
        value.valueChanged.connect(lambda changed, selected=key: self._spin_changed(selected, changed))
        slider.valueChanged.connect(lambda changed, selected=key: self._slider_changed(selected, changed))
        return row

    def _format_value(self, key, value):
        for _, definitions in PARAMETER_GROUPS:
            for definition in definitions:
                if definition[0] == key:
                    step = definition[4]
                    if step < 1:
                        decimals = max(1, len(str(step).rstrip("0").split(".")[-1]))
                        return f"{float(value):.{decimals}f}"
                    return str(int(round(float(value))))
        return str(value)

    def _update_feedback(self, key, value):
        control = self.controls[key]
        timing = PARAMETER_EFFECT_TIMING.get(key, "当前运行时生效")
        control["feedback"].setText(
            f"当前生效：{self._format_value(key, value)} · {timing}"
        )

    def _sync_control_value(self, control, value):
        value = float(value)
        spin = control["spin"]
        if value < spin.minimum() or value > spin.maximum():
            spin.setRange(min(spin.minimum(), value), max(spin.maximum(), value))
        spin_blocker = QSignalBlocker(spin)
        spin.setValue(value)
        del spin_blocker
        slider = control["slider"]
        slider_value = round(value / control["step"])
        if slider_value < slider.minimum() or slider_value > slider.maximum():
            slider.setRange(min(slider.minimum(), slider_value), max(slider.maximum(), slider_value))
        slider_blocker = QSignalBlocker(slider)
        slider.setValue(slider_value)
        del slider_blocker

    def _apply_value(self, key, value):
        control = self.controls[key]
        result = self.pet.set_debug_parameter(key, value)
        if result is False:
            actual = self.pet.debug_parameter_value(key)
            self._sync_control_value(control, actual)
            self._update_feedback(key, actual)
            control["feedback"].setText("当前生效：应用失败，运行时值未改变")
            self.status.setText("参数应用失败 · 当前运行时值保持不变")
            self._update_feedback(key, actual)
            return False
        actual = self.pet.debug_parameter_value(key)
        self._sync_control_value(control, actual)
        self._update_feedback(key, actual)
        self.status.setText(
            f"已实时应用 · {key} = {self._format_value(key, actual)}"
        )
        return True

    def _spin_changed(self, key, value):
        self._apply_value(key, value)

    def _slider_changed(self, key, value):
        control = self.controls[key]
        self._apply_value(key, value * control["step"])

    def reset_parameter(self, key):
        self._apply_value(key, self.controls[key]["default"])

    def reset_defaults(self):
        for key in self.controls:
            self.reset_parameter(key)
        self.status.setText("已恢复默认值（仅当前运行生效，保存后才会写入调试档案）")

    def parameter_text(self):
        values = self.pet.debug_parameter_snapshot(self.controls.keys())
        return json.dumps(values, ensure_ascii=False, indent=2)

    def copy_parameters(self):
        QApplication.clipboard().setText(self.parameter_text())
        self.status.setText("当前参数已复制，可以直接发给开发者作为调试反馈")

    def save_parameters(self):
        self.pet.save_debug_parameters(self.pet.debug_parameter_snapshot(self.controls.keys()))
        self.status.setText("调试参数已保存，下次启动会自动加载这组参数")

    def show_near_pet(self):
        screen = self.pet.current_screen_rect()
        geometry = self.pet.geometry()
        width = min(self.PREFERRED_WIDTH, max(1, screen.width() - 24))
        height = min(self.PREFERRED_HEIGHT, max(1, screen.height() - 60))
        self.setFixedSize(width, height)
        x = geometry.right() + 16
        y = geometry.top()
        if x + width > screen.right():
            x = geometry.left() - width - 16
        x = max(screen.left(), min(x, screen.right() - width + 1))
        y = max(screen.top(), min(y, screen.bottom() - height + 1))
        self.move(int(x), int(y))
        self.show()
        self.raise_()
        self.activateWindow()

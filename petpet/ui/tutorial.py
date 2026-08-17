"""Static content for Petpet's first-run tutorial."""

from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from petpet.chat import api as ai
from petpet.ui.common import independent_pixel_font

TUTORIAL_PAGES = (
    (
        "🐶",
        "欢迎认识你的桌面伙伴",
        "小狗会住在桌面上，拥有自己的状态和成长记录。\n"
        "它会散步、撒娇、陪你聊天，也会记住一起度过的时间。",
    ),
    (
        "🖱️",
        "摸摸它，也可以带它走",
        "单击小狗可以抚摸，双击进入小屋，按住左键可以拖动。\n"
        "睡着后按住左键左右晃几下，就能温柔地把它摇醒。",
    ),
    (
        "🌷",
        "右键打开快捷菜单",
        "右键会显示状态卡和快捷菜单：聊天、小屋、商店、互动和更多。\n"
        "记录、成就、小游戏、设置和教程都在“更多”里。",
    ),
    (
        "🏠",
        "在小屋里自由生活",
        "左键地面可以指定移动位置，右键小狗可以和它互动。\n"
        "精力不足时，小狗会走到垫子旁边睡觉。",
    ),
    (
        "💬",
        "聊天与陪伴偏好",
        "聊天可以选择免费或自定义模式；自定义模式还能上传图片交流。\n"
        "设置里可以选择健康提醒和性格偏好，不需要调整复杂数值。",
    ),
    (
        "🏷️",
        "最后，给小狗取个名字吧",
        "名字会显示在聊天和档案中，最多 6 个字符。",
    ),
)


class TutorialWindow(QWidget):
    """Warm first-run guide whose final step names the pet."""

    PAGES = TUTORIAL_PAGES

    def __init__(self, pet_window, on_complete):
        super().__init__()
        self.pet = pet_window
        self.on_complete = on_complete
        self.page_index = 0
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setObjectName("tutorialWindow")
        self.setWindowTitle("初次见面 · 新手教程")
        self.setFixedSize(740, 620)
        self.setStyleSheet("""
            QWidget#tutorialWindow {
                background:transparent;
                border:0;
            }
            QFrame#tutorialCard {
                background:#fff8ec;
                border:1px solid #e7c4ad;
                border-radius:24px;
                color:#65483b;
                font-family:'Microsoft YaHei',sans-serif;
            }
            QLabel { background:transparent; }
            QLabel#tutorialIcon { }
            QLabel#tutorialTitle {
                color:#754b3a;
                font-weight:900;
            }
            QLabel#tutorialBody {
                color:#8e6959;
                line-height:1.6;
            }
            QLabel#tutorialProgress {
                color:#e18d76;
                letter-spacing:5px;
            }
            QLabel#nameHint {
                color:#b36f5b;
                font-weight:700;
            }
            QFrame#nameCard {
                background:#fffdf8;
                border:1px solid #edcfb5;
                border-radius:17px;
            }
            QLineEdit {
                background:#ffffff;
                border:2px solid #edcdb3;
                border-radius:14px;
                padding:12px 16px;
                color:#65483b;
                selection-background-color:#ffc9b8;
            }
            QLineEdit:focus { border-color:#f19a7f; }
            QPushButton {
                min-height:52px;
                padding:7px 25px;
                border:0;
                border-radius:17px;
                background:#f28f76;
                color:#ffffff;
                font-weight:800;
            }
            QPushButton:hover { background:#f5a08a; }
            QPushButton:pressed { background:#df7d67; }
            QPushButton#secondary {
                background:#f1dfd2;
                color:#7e5b4c;
            }
            QPushButton#secondary:hover { background:#ead1c1; }
            QPushButton#later {
                background:transparent;
                color:#ad8170;
                padding:4px 12px;
                min-height:38px;
            }
            QPushButton#later:hover {
                background:#ffebe3;
                color:#a45d4e;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        self.tutorial_card = QFrame()
        self.tutorial_card.setObjectName("tutorialCard")
        outer.addWidget(self.tutorial_card)
        root = QVBoxLayout(self.tutorial_card)
        root.setContentsMargins(38, 28, 38, 30)
        root.setSpacing(14)

        top = QHBoxLayout()
        brand = QLabel("🌼 Pet陪它 · 新手教程")
        brand.setFont(independent_pixel_font(18, QFont.Bold))
        brand.setStyleSheet("font-weight:900; color:#93624f;")
        self.later_button = QPushButton("稍后再说")
        self.later_button.setObjectName("later")
        self.later_button.clicked.connect(self.close)
        top.addWidget(brand)
        top.addStretch(1)
        top.addWidget(self.later_button)
        root.addLayout(top)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("tutorialIcon")
        self.icon_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.icon_label)

        self.title_label = QLabel()
        self.title_label.setObjectName("tutorialTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.title_label)

        self.body_label = QLabel()
        self.body_label.setObjectName("tutorialBody")
        self.body_label.setAlignment(Qt.AlignCenter)
        self.body_label.setWordWrap(True)
        self.body_label.setMinimumHeight(58)
        self.body_label.setMaximumHeight(92)
        root.addWidget(self.body_label)

        self.name_card = QFrame()
        self.name_card.setObjectName("nameCard")
        name_layout = QVBoxLayout(self.name_card)
        name_layout.setContentsMargins(20, 10, 20, 10)
        name_layout.setSpacing(4)
        self.name_input = QLineEdit()
        self.name_input.setObjectName("petNameInput")
        self.name_input.setMaxLength(6)
        self.name_input.setPlaceholderText("例如：团子、旺财、Sheen")
        self.name_input.returnPressed.connect(self._next)
        self.name_hint = QLabel("")
        self.name_hint.setObjectName("nameHint")
        self.name_hint.setAlignment(Qt.AlignCenter)
        name_layout.addWidget(self.name_input)
        name_layout.addWidget(self.name_hint)
        root.addWidget(self.name_card)

        root.addStretch(1)
        self.progress_label = QLabel()
        self.progress_label.setObjectName("tutorialProgress")
        self.progress_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.progress_label)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.back_button = QPushButton("上一步")
        self.back_button.setObjectName("secondary")
        self.back_button.clicked.connect(self._back)
        self.next_button = QPushButton("下一步")
        self.next_button.clicked.connect(self._next)
        controls.addWidget(self.back_button)
        controls.addStretch(1)
        controls.addWidget(self.next_button)
        root.addLayout(controls)

        self.icon_label.setFont(independent_pixel_font(80))
        self.title_label.setFont(independent_pixel_font(31, QFont.Bold))
        self.body_label.setFont(independent_pixel_font(23))
        self.progress_label.setFont(independent_pixel_font(20, QFont.Bold))
        self.name_input.setFont(independent_pixel_font(23))
        self.name_hint.setFont(independent_pixel_font(20, QFont.Bold))
        for button in (self.later_button, self.back_button, self.next_button):
            button.setFont(independent_pixel_font(22, QFont.Bold))

        self._refresh_page()

    def start(self):
        """Restart the guide from page one and center it on the pet's screen."""
        self.page_index = 0
        current_name = self.pet.pet_name
        if (
            not self.pet.state.get("tutorial_completed", False)
            and current_name == ai.DEFAULT_PET_NAME
        ):
            self.name_input.clear()
        else:
            self.name_input.setText(current_name)
        self.name_hint.clear()
        self._refresh_page()
        screen = self.pet.interface_screen_rect()
        self.move(QPoint(
            screen.x() + (screen.width() - self.width()) // 2,
            screen.y() + (screen.height() - self.height()) // 2,
        ))
        self.show()
        self.raise_()
        self.activateWindow()

    def _refresh_page(self):
        emoji, title, body = self.PAGES[self.page_index]
        is_last = self.page_index == len(self.PAGES) - 1
        self.icon_label.setText(emoji)
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.name_card.setVisible(is_last)
        self.body_label.setMaximumHeight(58 if is_last else 92)
        self.back_button.setVisible(self.page_index > 0)
        self.next_button.setText("完成相遇" if is_last else "下一步")
        self.progress_label.setText(
            " ".join(
                "●" if index == self.page_index else "○"
                for index in range(len(self.PAGES))
            )
        )
        self.later_button.setText(
            "关闭" if self.pet.state.get("tutorial_completed") else "稍后再说"
        )
        if is_last:
            QTimer.singleShot(0, self.name_input.setFocus)

    def _back(self):
        if self.page_index > 0:
            self.page_index -= 1
            self.name_hint.clear()
            self._refresh_page()

    def _next(self):
        if self.page_index < len(self.PAGES) - 1:
            self.page_index += 1
            self._refresh_page()
            return
        raw_name = " ".join(self.name_input.text().split())
        if not any(char.isalnum() for char in raw_name):
            self.name_hint.setText("请先给小狗取一个名字，再开始陪伴吧～")
            self.name_input.setFocus()
            return
        name = ai.normalize_pet_name(raw_name)
        self.name_input.setText(name)
        self.name_hint.clear()
        self.on_complete(name)
        self.close()

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

from petpet.progression.ui import FeedbackButton
from petpet.chat import api as ai
from petpet.app import pets as pet_registry
from petpet.ui.common import KeepAliveTopLevelWindow
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
        "🐾",
        "选择你的伙伴",
        "挑选一只作为你的初始桌宠。点一下头像认识 TA，确认后开始陪伴。",
    ),
    (
        "🏷️",
        "最后，给TA取个名字吧",
        "名字会显示在聊天和档案中，最多 6 个字符。",
    ),
)


class TutorialWindow(KeepAliveTopLevelWindow):
    """Warm first-run guide whose final step names the pet."""

    PAGES = TUTORIAL_PAGES

    def __init__(self, pet_window, on_complete):
        super().__init__()
        self.pet = pet_window
        self.on_complete = on_complete
        self.page_index = 0
        self.pages = self.PAGES  # start() 按首次/重看切换页集
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setObjectName("tutorialWindow")
        self.setWindowTitle("初次见面 · 新手教程")
        self.setFixedSize(740, 660)
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
                min-height:56px;
                padding:8px 34px;
                border:0;
                border-radius:28px;
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #f6a289, stop:1 #ee8266);
                color:#ffffff;
                font-weight:800;
                letter-spacing:2px;
            }
            QPushButton:hover {
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #f8b39c, stop:1 #f29377);
            }
            QPushButton:pressed {
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #e87a5e, stop:1 #de6e52);
            }
            QPushButton#secondary {
                background:#f7e6d8;
                color:#7e5b4c;
                border:2px solid #ecd2bd;
            }
            QPushButton#secondary:hover {
                background:#f3dbc8;
                border-color:#e5bfa5;
            }
            QPushButton#later {
                background:transparent;
                color:#ad8170;
                padding:4px 16px;
                min-height:40px;
                border-radius:20px;
            }
            QPushButton#later:hover {
                background:#ffebe3;
                color:#a45d4e;
            }
            QPushButton#petChoiceButton {
                background:#fffdf8;
                border:3px solid #f0dcc8;
                border-radius:26px;
                padding:0;
                min-height:0;
            }
            QPushButton#petChoiceButton:hover {
                border-color:#f5b39c;
                background:#fff6ee;
            }
            QPushButton#petChoiceButton[chosen="true"] {
                border-color:#f28f76;
                background:#fff3ea;
            }
            QPushButton#later {
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
        self.later_button = FeedbackButton("稍后再说")
        self.later_button.setObjectName("later")
        self.later_button.setQssHover(True)
        self.later_button.clicked.connect(self.close)
        top.addWidget(brand)
        top.addStretch(1)
        top.addWidget(self.later_button)
        root.addLayout(top)

        # 2026-10-15 素材升级（用户令）：欢迎页顶部 hero 插画（Meowa 生成，
        # 素材缺失回退 emoji 大图标不拖垮）
        self.hero_label = QLabel()
        self.hero_label.setObjectName("tutorialHero")
        self.hero_label.setAlignment(Qt.AlignCenter)
        self.hero_label.setFixedSize(608, 160)
        root.addWidget(self.hero_label)

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

        # ---- 2026-10-15 选宠页（命名页前一步，用户令）----
        self.chooser_card = QFrame()
        self.chooser_card.setObjectName("nameCard")
        chooser_layout = QVBoxLayout(self.chooser_card)
        chooser_layout.setContentsMargins(16, 14, 16, 12)
        chooser_layout.setSpacing(10)
        self.pet_chooser_row = QHBoxLayout()
        self.pet_chooser_row.setSpacing(18)
        self._pet_choice_buttons = {}
        for pet_id, definition in pet_registry.load_pet_registry().items():
            button = QPushButton()
            button.setObjectName("petChoiceButton")
            button.setFixedSize(92, 92)
            avatar_path = pet_registry.pet_avatar_path(pet_id)
            from PyQt5.QtGui import QPixmap, QIcon
            pm = QPixmap(avatar_path) if avatar_path else QPixmap()
            if not pm.isNull():
                button.setIcon(QIcon(pm.scaled(
                    78, 78, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                button.setIconSize(pm.scaled(
                    78, 78, Qt.KeepAspectRatio).size())
            button.setToolTip(definition.get("default_name", pet_id))
            button.clicked.connect(
                lambda _checked=False, pid=pet_id: self._select_starter(pid))
            self._pet_choice_buttons[pet_id] = button
            self.pet_chooser_row.addWidget(button)
        self.pet_chooser_row.addStretch(1)
        self.pet_chooser_row.insertStretch(0)
        self.pet_info_label = QLabel("点一只头像，认识一下TA吧～")
        self.pet_info_label.setObjectName("tutorialBody")
        self.pet_info_label.setAlignment(Qt.AlignCenter)
        self.pet_info_label.setWordWrap(True)
        self.pet_info_label.setMinimumHeight(46)
        self.pet_info_label.setFont(independent_pixel_font(19))
        chooser_layout.addLayout(self.pet_chooser_row)
        chooser_layout.addWidget(self.pet_info_label)
        root.addWidget(self.chooser_card)
        self._starter_pet_id = None

        self.name_card = QFrame()
        self.name_card.setObjectName("nameCard")
        name_layout = QVBoxLayout(self.name_card)
        name_layout.setContentsMargins(20, 10, 20, 10)
        name_layout.setSpacing(4)
        self.name_input = QLineEdit()
        self.name_input.setObjectName("petNameInput")
        self.name_input.setMaxLength(6)
        self.name_input.setMinimumHeight(58)
        self.name_input.setPlaceholderText("例如：团子、旺财、Sheen")
        self.name_input.returnPressed.connect(self._next)
        self.name_hint = QLabel("")
        self.name_hint.setObjectName("nameHint")
        self.name_hint.setAlignment(Qt.AlignCenter)
        name_layout.addWidget(self.name_input)
        name_layout.addWidget(self.name_hint)
        # 2026-10-15 用户令：默认按钮——不想起名的玩家一键用默认宠物名
        self.default_name_button = FeedbackButton("用默认名字")
        self.default_name_button.setObjectName("secondary")
        self.default_name_button.setQssHover(True)
        self.default_name_button.clicked.connect(self._use_default_name)
        name_layout.addWidget(self.default_name_button)
        root.addWidget(self.name_card)

        root.addStretch(1)
        self.progress_label = QLabel()
        self.progress_label.setObjectName("tutorialProgress")
        self.progress_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.progress_label)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.back_button = FeedbackButton("上一步")
        self.back_button.setObjectName("secondary")
        self.back_button.setQssHover(True)
        self.back_button.clicked.connect(self._back)
        self.next_button = FeedbackButton("下一步")
        self.next_button.setQssHover(True)
        self.next_button.clicked.connect(self._next)
        controls.addWidget(self.back_button)
        controls.addStretch(1)
        controls.addWidget(self.next_button)
        root.addLayout(controls)

        # hero 插画（Meowa 生成，缺文件静默回退 emoji）
        from petpet.app.paths import ASSETS_DIR as _ASSETS
        import os as _os
        _hero_path = _os.path.join(
            _ASSETS, "ui", "tutorial", "tutorial_hero.png")
        from PyQt5.QtGui import QPixmap as _QPM
        self._hero_pixmap = (
            _QPM(_hero_path) if _os.path.exists(_hero_path) else _QPM())

        self.icon_label.setFont(independent_pixel_font(80))
        self.title_label.setFont(independent_pixel_font(31, QFont.Bold))
        self.body_label.setFont(independent_pixel_font(23))
        self.progress_label.setFont(independent_pixel_font(20, QFont.Bold))
        self.name_input.setFont(independent_pixel_font(23))
        self.name_hint.setFont(independent_pixel_font(20, QFont.Bold))
        for button in (self.later_button, self.back_button, self.next_button):
            button.setFont(independent_pixel_font(22, QFont.Bold))

        self._refresh_page()

    def start(self, force_full=False):
        """Restart the guide from page one and center it on the pet's screen.

        2026-10-15 用户令：选宠+起名只属于**下载后第一次**教程（教程未完
        成）；已完成教程再打开（菜单重看）只展示玩法五页，不重选不重名。
        force_full（调试入口）：无视完成态强制完整 7 页（选宠授予对已完成
        玩家自动 no-op，仅展示）。
        """
        first_run = force_full or not self.pet.state.get(
            "tutorial_completed", False)
        self.pages = self.PAGES if first_run else self.PAGES[:5]
        self.page_index = 0
        self._starter_pet_id = None
        for button in self._pet_choice_buttons.values():
            button.setProperty("chosen", False)
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

    CHOOSER_PAGE_INDEX = -2  # 倒数第二页=选宠（构造后按 len 计算）

    def _refresh_page(self):
        emoji, title, body = self.pages[self.page_index]
        is_last = self.page_index == len(self.pages) - 1
        is_chooser = (
            len(self.pages) == 7 and self.page_index == len(self.pages) - 2)
        self.icon_label.setText(emoji)
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.name_card.setVisible(is_last and len(self.pages) == 7)
        self.chooser_card.setVisible(is_chooser)
        self.body_label.setMaximumHeight(58 if (is_last or is_chooser) else 92)
        # hero 插画只在欢迎页。isVisible() 在窗口未 show 前恒 False，
        # 不能用它判定（曾致 hero+emoji 双显、页面顶部大片空白）——用
        # 素材有效性直接推导。
        hero = getattr(self, "_hero_pixmap", None)
        hero_ready = hero is not None and not hero.isNull()
        hero_active = self.page_index == 0 and hero_ready
        self.hero_label.setVisible(hero_active)
        if hero_active:
            from PyQt5.QtCore import Qt as _Qt
            self.hero_label.setPixmap(hero.scaled(
                600, 150, _Qt.KeepAspectRatio,
                _Qt.SmoothTransformation))
        self.icon_label.setVisible(not is_chooser and not hero_active)
        self.back_button.setVisible(self.page_index > 0)
        self.next_button.setText(
            ("完成相遇" if len(self.pages) == 7 else "完成回顾")
            if is_last else "下一步")
        self.progress_label.setText(
            " ".join(
                "●" if index == self.page_index else "○"
                for index in range(len(self.pages))
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

    def _select_starter(self, pet_id):
        """选宠页：点亮头像 + 展示基本信息。"""
        registry = pet_registry.load_pet_registry()
        definition = registry.get(pet_id, {})
        self._starter_pet_id = pet_id
        for pid, button in self._pet_choice_buttons.items():
            button.setProperty("chosen", pid == pet_id)
            button.style().unpolish(button)
            button.style().polish(button)
        name = definition.get("default_name", pet_id)
        desc = definition.get("description", "")
        personality = definition.get("chat_personality", "")
        brief = "、".join(
            personality.replace("；", "，").split("，")[:2]) if personality else ""
        extra = f"性格：{brief}" if brief else ""
        combined = f"{name} · {desc}" + (("\n" + extra) if extra else "")
        self.pet_info_label.setText(combined)

    def _use_default_name(self):
        """命名页默认按钮：一键填入选中宠的默认名。"""
        registry = pet_registry.load_pet_registry()
        pet_id = self._starter_pet_id or self.pet.state.get(
            "active_pet_id", "lunch_meat")
        default_name = registry.get(pet_id, {}).get("default_name", "午餐肉")
        self.name_input.setText(default_name)
        self.name_hint.clear()

    def _next(self):
        # 选宠页：未选不能过；确认后授予（教程未完成=唯一初始宠）
        if len(self.pages) == 7 and self.page_index == len(self.pages) - 2:
            if not self._starter_pet_id:
                self.pet_info_label.setText("先点一只头像选出你的伙伴吧～")
                return
            grant = getattr(self.pet, "_grant_starter_pet_callback", None)
            if callable(grant):
                grant(self._starter_pet_id)
        if self.page_index < len(self.pages) - 1:
            self.page_index += 1
            self._refresh_page()
            return
        if len(self.pages) < 7:
            # 重看模式末页：直接关闭，不起名不重复授予
            self.close()
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

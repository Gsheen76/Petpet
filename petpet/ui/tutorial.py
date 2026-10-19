from pathlib import Path
"""Static content for Petpet's first-run tutorial."""

from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtGui import QPainter, QPainterPath
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QFont
from PyQt5.QtGui import QPainter
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

# 2026-10-15 素材升级：emoji→Meowa Image-2 生成图标（缺素材回退 emoji）
TUTORIAL_PAGE_ICONS = {
    1: "tutorial_page_pet_hand.png",
    2: "tutorial_page_menu_card.png",
    3: "tutorial_page_house_cozy.png",
    4: "tutorial_page_chat_gather.png",
    5: "tutorial_page_chooser.png",
    6: "tutorial_page_nametag.png",
}

# 命名页（页6）插图随选中宠物切换（2026-10-19 用户令；Meowa 生成，
# 缺素材回退上方通用名牌图）
TUTORIAL_PAGE_NAME_ICONS = {
    "lunch_meat": "tutorial_page_name_lunch_meat.png",
    "ice_cream": "tutorial_page_name_ice_cream.png",
    "marshmallow": "tutorial_page_name_marshmallow.png",
}

def hl(word):
    return f'<b style="color:#d4593f">{word}</b>'


TUTORIAL_PAGES = (
    (
        "🐶",
        "欢迎认识你的桌面伙伴",
        f"小宠物会住在你的{hl('桌面上')}，拥有自己的{hl('饱腹')}、{hl('心情')}和{hl('精力')}三种状态，"
        f"还会随着{hl('陪伴时间')}慢慢{hl('成长')}、{hl('升级')}、{hl('解锁')}各种好玩的内容。"
        f"它会散步、撒娇、陪你{hl('聊天')}，也会{hl('记住')}你们一起度过的每一段时间。",
    ),
    (
        "🖱️",
        "摸摸它，也可以带它走",
        f"{hl('单击')}宠物可以{hl('摸摸')}它，它会开心地摇尾巴或竖起耳朵。"
        f"{hl('双击')}可以{hl('进入小屋')}，{hl('按住左键')}{hl('拖动')}能把它带到屏幕的任何角落。"
        f"当它睡着后，{hl('按住左键左右晃')}几下，就能温柔地把它{hl('摇醒')}。",
    ),
    (
        "🌷",
        "右键打开快捷菜单",
        f"{hl('右键')}宠物会显示{hl('状态卡')}和{hl('快捷菜单')}，一目了然地看到它的心情。"
        f"菜单里有{hl('聊天')}、{hl('小屋')}、{hl('商店')}、{hl('互动')}和{hl('喂养')}。"
        f"{hl('记录')}、{hl('成就')}、{hl('小游戏')}、{hl('设置')}和{hl('教程')}都收纳在{hl('「更多」')}里面。",
    ),
    (
        "🏠",
        "在小屋里自由生活",
        f"小屋里有一个温暖的{hl('小家')}，宠物可以在这里{hl('自由活动')}。"
        f"{hl('左键点击地面')}可以指定它{hl('移动')}的位置。"
        f"{hl('右下角的互动按键')}可以{hl('抚摸')}、{hl('喂食')}、{hl('玩耍')}或{hl('睡觉')}。"
        f"当{hl('精力不足')}时，它会自己走到{hl('垫子')}旁边蜷成一团睡觉。",
    ),
    (
        "💬",
        "聊天与陪伴偏好",
        f"和宠物{hl('聊天')}可以选择{hl('免费模式')}或{hl('自定义模式')}。"
        f"自定义模式支持{hl('上传图片')}交流，它还会{hl('记住')}你们聊过的话题。"
        f"{hl('设置')}里可以调整{hl('健康提醒')}和{hl('性格偏好')}，都是简单直观的选项。",
    ),
    (
        "🐾",
        "选择你的伙伴",
        f"三只小伙伴都在等你。{hl('挑选一只')}作为你的{hl('初始桌宠')}，{hl('点击头像')}认识它。"
        f"看看它的{hl('性格')}和{hl('介绍')}，{hl('选中后')}进入下一步，开始你们的{hl('陪伴之旅')}。",
    ),
    (
        "🏷️",
        "最后，给TA取个名字吧",
        f"给伙伴取一个{hl('专属的名字')}吧，它会显示在{hl('聊天')}和{hl('档案')}中。"
        f"名字最多{hl('6 个字符')}，也可以使用{hl('默认名字')}。",
    ),
)




class _TutorialCard(QFrame):
    """教程卡片：paintEvent 直接绘制水彩背景图（不走 QSS border-image
    ——那层会破坏子控件 Alpha 复合，2026-10-15 七修定稿）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_pixmap = None

    def set_background(self, pixmap):
        self._bg_pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        if self._bg_pixmap is not None and not self._bg_pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), 24, 24)
            painter.setClipPath(path)
            pm = self._bg_pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (self.width() - pm.width()) // 2
            y = (self.height() - pm.height()) // 2
            painter.drawPixmap(x, y, pm)
            painter.end()
        super().paintEvent(event)


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
        self.setFixedSize(740, 800)
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
                border:2px solid #f0dcc8;
                border-radius:28px;
                padding:0 18px;
                min-height:52px;
                max-height:52px;
                color:#65483b;
                selection-background-color:#ffc9b8;
            }
            QLineEdit:focus {
                border-color:#f28f76;
                background:#fffaf5;
            }
            QPushButton#defaultNameBtn {
                background:#f7e6d8;
                color:#7e5b4c;
                border:1px solid #ecd2bd;
                border-radius:28px;
                padding:0 12px;
                min-height:54px;
                max-height:54px;
                min-width:62px;
                max-width:62px;
            }
            QPushButton#defaultNameBtn:hover {
                background:#f3dbc8;
                border-color:#e5bfa5;
            }
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
                border:1px solid #ecd2bd;
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
                border-radius:20px;
                padding:0;
                min-height:110px;
                max-height:110px;
                min-width:110px;
                max-width:110px;
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
        self.tutorial_card = _TutorialCard()
        self.tutorial_card.setObjectName("tutorialCard")
        # 加载水彩背景图
        from petpet.app.paths import ASSETS_DIR as _BG_DIR
        import os as _bg_os
        _bg_path = _bg_os.path.join(_BG_DIR, "ui", "tutorial", "tutorial_bg.png")
        from PyQt5.QtGui import QPixmap as _BGP
        if _bg_os.path.exists(_bg_path):
            self.tutorial_card.set_background(_BGP(_bg_path))
        outer.addWidget(self.tutorial_card)
        root = QVBoxLayout(self.tutorial_card)
        self.root_layout = root
        root.setContentsMargins(38, 28, 38, 30)
        root.setSpacing(14)

        top = QHBoxLayout()
        brand = QLabel("Pet陪它 · 新手教程")
        brand.setFont(independent_pixel_font(17, QFont.Bold))
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
        self.hero_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.hero_label.setFixedSize(560, 308)
        root.addWidget(self.hero_label, 0, Qt.AlignHCenter)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("tutorialIcon")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.icon_label.setFixedSize(646, 260)
        root.addWidget(self.icon_label, 0, Qt.AlignHCenter)

        self.title_label = QLabel()
        self.title_label.setObjectName("tutorialTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.title_label, 0, Qt.AlignHCenter)

        self.body_label = QLabel()
        self.body_label.setObjectName("tutorialBody")
        self.body_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.body_label.setWordWrap(True)
        self.body_label.setMinimumWidth(450)
        self.body_label.setMaximumWidth(450)
        self.body_label.setFixedHeight(
            120 if self.page_index < 5 else 100)  # 前五页 120px 容纳长文案
       
        root.addWidget(self.body_label, 0, Qt.AlignHCenter)

        # ---- 2026-10-15 选宠页（命名页前一步，用户令）----
        self.chooser_card = QFrame()
        self.chooser_card.setFixedSize(500, 400)  # 用户令：外框锁死不随选择变化
        self.chooser_card.setObjectName("nameCard")
        chooser_layout = QVBoxLayout(self.chooser_card)
        chooser_layout.setContentsMargins(16, 14, 16, 12)
        chooser_layout.setSpacing(10)
        self.pet_chooser_row = QHBoxLayout()
        self.pet_chooser_row.setSpacing(12)
        self._pet_choice_buttons = {}
        for pet_id, definition in pet_registry.load_pet_registry().items():
            button = QPushButton()
            button.setObjectName("petChoiceButton")
            button.setFixedSize(110, 110)
            avatar_path = pet_registry.pet_avatar_path(pet_id)
            from PyQt5.QtGui import QPixmap, QIcon
            pm = QPixmap(avatar_path) if avatar_path else QPixmap()
            if not pm.isNull():
                button.setIcon(QIcon(pm.scaled(
                    96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                button.setIconSize(pm.scaled(
                    70, 70, Qt.KeepAspectRatio).size())
            button.setToolTip(definition.get("default_name", pet_id))
            button.clicked.connect(
                lambda _checked=False, pid=pet_id: self._select_starter(pid))
            self._pet_choice_buttons[pet_id] = button
            self.pet_chooser_row.addWidget(button)
        # 居中（2026-10-15 修正）：insertStretch(0) 是零系数弹簧（第一参
        # 是索引！）——右端 factor-1 弹簧吃光空隙、按钮被推到左边。两侧都
        # 必须显式系数 1
        self.pet_chooser_row.addStretch(1)
        self.pet_chooser_row.insertStretch(0, 1)
        self.pet_info_label = QLabel("点一只头像，认识一下TA吧～")
        self.pet_info_label.setObjectName("tutorialBody")
        self.pet_info_label.setAlignment(Qt.AlignCenter)
        self.pet_info_label.setWordWrap(False)  # 用户令：一定一行显示
        self.pet_info_label.setMinimumHeight(28)
        self.pet_info_label.setFont(independent_pixel_font(20))
        # 2026-10-15 用户令：选中后在下方展示该宠的待机动画
        self.pet_preview_label = QLabel()
        self.pet_preview_label.setObjectName("tutorialPetPreview")
        self.pet_preview_label.setAlignment(Qt.AlignCenter)
        self.pet_preview_label.setAttribute(Qt.WA_TranslucentBackground, True)
        # 画布 150 高（地线钉在画布内），保证布局压缩时也不裁脚底
        self.pet_preview_label.setMinimumHeight(150)
        chooser_layout.addLayout(self.pet_chooser_row)
        chooser_layout.addWidget(self.pet_info_label)
        chooser_layout.addWidget(self.pet_preview_label)
        root.addWidget(self.chooser_card, 0, Qt.AlignHCenter)
        # idle 帧定时器
        self._preview_frames = []
        self._preview_index = 0
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._advance_preview)
        self._starter_pet_id = None

        # ---- 命名行（2026-10-19 二轮定稿）：外框删除（用户令），胶囊
        # 输入框与「默认」键同高并排直接放在页面上，提示行居中在下；
        # 输入初始恒空（用户令：让玩家自己输入）
        self.name_card = QWidget()
        self.name_card.setObjectName("nameRowHost")  # 无 QSS=无边框透明
        name_layout = QVBoxLayout(self.name_card)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(10)
        name_row = QHBoxLayout()
        name_row.setSpacing(14)
        self.name_input = QLineEdit()
        self.name_input.setObjectName("petNameInput")
        self.name_input.setMaxLength(6)
        self.name_input.setFixedSize(320, 56)
        self.name_input.setFont(independent_pixel_font(24))
        self.name_input.setAlignment(Qt.AlignCenter)
        self.name_input.setPlaceholderText("例如：团子、旺财、豆豆")
        self.name_input.returnPressed.connect(self._next)
        name_row.addWidget(self.name_input)
        self.default_name_button = FeedbackButton("默认")
        # 独立 ID 样式（不复用 secondary）：全局 QPushButton 规则的
        # min-height 56+padding 8/34 会把定高撑爆——ID 选择器覆盖之，
        # 与输入框严格同高同线
        self.default_name_button.setObjectName("defaultNameBtn")
        self.default_name_button.setQssHover(True)
        self.default_name_button.setFixedSize(88, 56)
        self.default_name_button.clicked.connect(self._use_default_name)
        name_row.addWidget(self.default_name_button)
        name_layout.addLayout(name_row)
        name_layout.setAlignment(name_row, Qt.AlignHCenter)
        self.name_hint = QLabel("")
        self.name_hint.setObjectName("nameHint")
        self.name_hint.setAlignment(Qt.AlignCenter)
        self.name_hint.setFixedHeight(24)
        self.name_hint.setFont(independent_pixel_font(16))
        name_layout.addWidget(self.name_hint, 0, Qt.AlignHCenter)
        root.addWidget(self.name_card, 0, Qt.AlignHCenter)

        root.addStretch(1)
        # 底部严格对齐（2026-10-15 用户令）：进度点与按键行绝对定位钉在
        # 卡底同一 y——hero/图标/选宠卡等页内容高度不同时不再漂移
        self.bottom_bar = QWidget(self.tutorial_card)
        self.bottom_bar.setObjectName("tutorialBottom")
        bottom_layout = QVBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(12)
        self.progress_label = QLabel()
        self.progress_label.setObjectName("tutorialProgress")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setFixedHeight(24)  # 定高消除逐 2px 漂移
        bottom_layout.addWidget(self.progress_label)

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
        bottom_layout.addLayout(controls)
        # 卡高=窗 700-外边距16=684；底栏高 96，贴卡底内边距 18
        self.bottom_bar.setGeometry(38, 784 - 20 - 118, 646, 118)

        # hero 插画（Meowa 生成，缺文件静默回退 emoji）
        from petpet.app.paths import ASSETS_DIR as _ASSETS
        import os as _os
        _hero_path = _os.path.join(
            _ASSETS, "ui", "tutorial", "tutorial_hero.png")
        from PyQt5.QtGui import QPixmap as _QPM
        self._hero_pixmap = (
            _QPM(_hero_path) if _os.path.exists(_hero_path) else _QPM())

        self.icon_label.setFont(independent_pixel_font(64))
        self.title_label.setFont(independent_pixel_font(33, QFont.Bold))
        self.body_label.setFont(independent_pixel_font(20))
        self.progress_label.setFont(independent_pixel_font(17, QFont.Bold))
        self.name_input.setFont(independent_pixel_font(20))
        self.name_hint.setFont(independent_pixel_font(20, QFont.Bold))
        for button in (self.later_button, self.back_button, self.next_button):
            button.setFont(independent_pixel_font(20, QFont.Bold))

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
        # 2026-10-19 用户令：输入初始恒空让玩家自己输入（旧逻辑重看时
        # 预填当前名「奶油」被否）——默认名一键补全交给「默认」键
        self.name_input.clear()
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
        icon_pixmap = self._page_icon_pixmap(self.page_index)
        if icon_pixmap is not None and not icon_pixmap.isNull():
            self.icon_label.setPixmap(icon_pixmap)
        else:
            self.icon_label.setText(emoji)
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.name_card.setVisible(is_last and len(self.pages) == 7)
        self.chooser_card.setVisible(is_chooser)
        if not is_chooser and hasattr(self, "_preview_timer"):
            self._preview_timer.stop()
        # 高/宽按页锁定（2026-10-19 根治：旧 setMaximumHeight 与构造期
        # fixed 120 冲突、min 恒胜，「页5-6 100px」从未生效——改走
        # setFixedHeight；选宠页外框加高到 400 后行距同步收紧防撞底栏）
        self.body_label.setFixedHeight(
            84 if (is_chooser or is_last) else 120)
        self.body_label.setFixedWidth(500 if is_chooser else 450)
        # 选宠/命名两页行距收紧——内容件更高的这两页防撞底部按键行
        self.root_layout.setSpacing(10 if (is_chooser or is_last) else 14)
        # hero 插画只在欢迎页。isVisible() 在窗口未 show 前恒 False，
        # 不能用它判定（曾致 hero+emoji 双显、页面顶部大片空白）——用
        # 素材有效性直接推导。
        hero = getattr(self, "_hero_pixmap", None)
        hero_ready = hero is not None and not hero.isNull()
        hero_active = self.page_index == 0 and hero_ready
        self.hero_label.setVisible(hero_active)
        if hero_active:
            from PyQt5.QtCore import Qt as _Qt
            scaled_hero = hero.scaled(
                self.hero_label.width(), self.hero_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.hero_label.setPixmap(scaled_hero)


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

    def _page_icon_pixmap(self, page_index):
        """页图标素材（Meowa 生成）；缺素材返回 None 回退 emoji。

        命名页（页6）随选中宠物换图（2026-10-19 用户令）——未选中或
        缺素材回退通用名牌图 TUTORIAL_PAGE_ICONS[6]。
        """
        from petpet.app.paths import ASSETS_DIR as _ASSETS
        import os as _os
        name = TUTORIAL_PAGE_ICONS.get(page_index)
        if page_index == 6:
            name = TUTORIAL_PAGE_NAME_ICONS.get(
                getattr(self, "_starter_pet_id", None), name)
        if not name:
            return None
        cache = getattr(self, "_page_icon_cache", None)
        if cache is None:
            cache = self._page_icon_cache = {}
        if name not in cache:
            path = _os.path.join(_ASSETS, "ui", "tutorial", name)
            from PyQt5.QtGui import QPixmap as _QPM
            cache[name] = (
                _QPM(path).scaled(
                    240, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if _os.path.exists(path) else _QPM())
        return cache[name] or None

    def _advance_preview(self):
        if not self._preview_frames:
            return
        pm = self._preview_frames[self._preview_index % len(self._preview_frames)]
        self.pet_preview_label.setPixmap(pm)  # 帧已归一到统一画布
        self._preview_index += 1

    def _select_starter(self, pet_id):
        """选宠页：点亮头像 + 展示基本信息 + 加载 idle 预览。"""
        registry = pet_registry.load_pet_registry()
        definition = registry.get(pet_id, {})
        self._starter_pet_id = pet_id
        for pid, button in self._pet_choice_buttons.items():
            button.setProperty("chosen", pid == pet_id)
            button.style().unpolish(button)
            button.style().polish(button)
        name = definition.get("default_name", pet_id)
        desc = definition.get("description", "").rstrip("。")
        personality = definition.get("chat_personality", "")
        # 介绍两行（2026-10-19 用户令）：行1「名 · 描述」/行2「性格：双四字
        # 词」（manifest traits 字段，缺省回退从 personality 解析 4 字分词）
        traits = [t for t in definition.get("traits", []) if t]
        if not traits:
            traits = [
                token.strip() for token in personality.replace(
                    "，", "、").replace("；", "、").split("、")
                if token.strip() and len(token.strip()) == 4
            ]
        words = traits[:2]
        from PyQt5.QtGui import QFontMetrics
        fm = QFontMetrics(self.pet_info_label.font())
        max_w = 466
        line1 = fm.elidedText(f"{name} · {desc}", Qt.ElideRight, max_w)
        line2 = (
            fm.elidedText("性格：" + "、".join(words), Qt.ElideRight, max_w)
            if words else "")
        combined = line1 + (("\n" + line2) if line2 else "")
        self.pet_info_label.setText(combined)
        # 加载该宠的 idle 动画帧做预览（动画目录而非姿势文件）；
        # 归一化到统一画布（2026-10-19 用户令：宠物大小统一/同一地线）
        from petpet.app.paths import ASSETS_DIR as _ASSETS2
        import os as _os2
        idle_dir = Path(_ASSETS2) / "pets" / pet_id / "desktop" / "animations" / "idle"
        paths = []
        if idle_dir and idle_dir.is_dir():
            paths = [
                idle_dir / n for n in sorted(
                    n for n in _os2.listdir(idle_dir) if n.endswith(".png"))[:8]
            ]
        self._preview_frames = self._normalized_preview_frames(paths)
        self._preview_index = 0
        if self._preview_frames:
            self._preview_timer.start(150)
            self._advance_preview()
        else:
            self._preview_timer.stop()
            self.pet_preview_label.clear()

    # 预览归一化画布：三宠 idle 帧同为 640² 但内容占比不同（体高
    # 459~576/底距 32~93），统一整帧缩放必然大小不一、底线错开——
    # 按参考帧内容 bbox 定每宠缩放（体高统一 126）+ 常量偏移（脚底
    # 钉同一地线），逐帧画到 190×150 定格画布
    PREVIEW_CANVAS_W, PREVIEW_CANVAS_H = 190, 150
    PREVIEW_BODY_H = 126
    PREVIEW_GROUND_MARGIN = 6

    def _normalized_preview_frames(self, paths):
        from PyQt5.QtGui import QPixmap
        if not paths:
            return []
        try:
            from PIL import Image
            import numpy as np
            boxes = []
            for p in paths:
                arr = np.asarray(Image.open(p).convert("RGBA"))
                ys, xs = np.where(arr[:, :, 3] > 10)
                if len(ys):
                    boxes.append(
                        (int(ys.min()), int(ys.max()),
                         int(xs.min()), int(xs.max())))
        except Exception:
            boxes = []
        if not boxes:
            return [
                pm for pm in (
                    QPixmap(str(p)).scaled(
                        self.PREVIEW_CANVAS_W, self.PREVIEW_CANVAS_H,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    for p in paths)
                if not pm.isNull()
            ]
        ref_h, ref_w = arr.shape[0], arr.shape[1]
        # 体高基准取全帧并集（呼吸/眨眼帧偏矮）——三宠「最大体高」严格一致
        content_h = max(b[1] - b[0] + 1 for b in boxes)
        y_max = boxes[0][1]
        x_min = min(b[2] for b in boxes)
        x_max = max(b[3] for b in boxes)
        content_w = x_max - x_min + 1
        src_h, src_w = ref_h, ref_w
        scale = self.PREVIEW_BODY_H / max(content_h, 1)
        frame_w = max(1, int(round(src_w * scale)))
        frame_h = max(1, int(round(src_h * scale)))
        # 内容水平居中、参考帧内容底钉地线
        dx = (
            (self.PREVIEW_CANVAS_W - int(round(content_w * scale))) // 2
            - int(round(x_min * scale)))
        dy = (
            (self.PREVIEW_CANVAS_H - self.PREVIEW_GROUND_MARGIN)
            - int(round((y_max + 1) * scale)))
        frames = []
        for path in paths:
            pm = QPixmap(str(path))
            if pm.isNull():
                continue
            canvas = QPixmap(self.PREVIEW_CANVAS_W, self.PREVIEW_CANVAS_H)
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(dx, dy, pm.scaled(
                frame_w, frame_h,
                Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            painter.end()
            frames.append(canvas)
        return frames

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
            self.name_hint.setText("请先给伙伴取一个名字，再开始陪伴吧～")
            self.name_input.setFocus()
            return
        name = ai.normalize_pet_name(raw_name)
        self.name_input.setText(name)
        self.name_hint.clear()
        self.on_complete(name)
        self.close()

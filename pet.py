"""Desktop Pet — a companion dog that lives on your desktop.
Transparent always-on-top window + system tray icon.

Features:
  - Drag the dog anywhere; fling physics when released while moving
  - Click to interact (pet / bark / snuggle)
  - Right-click menu: feed / play / sleep / hide / autostart / quit
  - Stats decay over time: hunger / mood / energy
  - Autonomous AI: walks, sits, naps, occasionally asks for things
  - Bounces off screen edges when flung
  - Tray icon: double-click to show/hide, right-click menu

Requirements: PyQt5
Run: python pet.py
"""
import sys, os, math, time, json, random, threading
from app_paths import (
    ANIMATIONS_DIR,
    APP_NAME,
    DATA_DIR,
    ICONS_DIR,
    MAC_BUNDLE_ID,
    POSES_DIR,
    PROPS_DIR,
    RESOURCE_DIR,
    SOUNDS_DIR,
)
from petpet.app import state as app_state
from petpet.app import pet_window as pet_window_controller
from petpet.app.settings import (
    DEFAULT_SETTINGS,
    SETTINGS_PATH,
    load_settings,
    save_settings,
)
from updater import (
    check_for_updates_async,
    cleanup_stale_windows_updates,
    download_release,
    launch_windows_replacement,
    open_macos_update,
    repair_legacy_windows_install,
    update_cache_dir,
)

# ---------- version & update ----------
from version import VERSION

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_FROZEN = bool(getattr(sys, "frozen", False))
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QTextEdit, QMenu, QAction,
    QSystemTrayIcon, QVBoxLayout, QHBoxLayout, QPushButton, QFrame,
    QGroupBox, QSpinBox, QDoubleSpinBox, QMessageBox, QProgressBar,
    QProgressDialog, QComboBox, QScrollArea, QAbstractSpinBox,
    QAbstractButton, QButtonGroup, QDialog, QSizePolicy, QFileDialog, QSlider
)
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtGui import (
    QPainter, QPixmap, QImage, QCursor, QIcon, QColor, QFont, QFontMetrics, QPen,
    QLinearGradient, QRadialGradient, QTextDocument, QDesktopServices, QRegion,
    QPainterPath, QPolygonF
)
from PyQt5.QtCore import (
    Qt, QEvent, QTimer, QPoint, QPointF, QRect, QRectF, QByteArray, QSize,
    pyqtSignal, QObject, QUrl
)
from petpet.ui.common import (
    FIXED_FONT_SCALE,
    SETTINGS_FONT_SCALE,
    font_px,
    independent_font_px,
    independent_pixel_font,
    pixel_font,
    settings_font_px,
    tutorial_font_px,
)
from petpet.ui.controls import StepperControl, ThreeLevelSlider, ToggleSwitch
from petpet.ui.tutorial import TUTORIAL_PAGES, TutorialWindow
from petpet.ui.settings import (
    HEALTH_PRESETS,
    PERSONALITY_PRESETS,
    SettingsWindow,
)

# AI engine (same folder)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buddy_ai as ai
from petpet.ui.chat import ChatWindow as PackageChatWindow
from petpet.ui import desktop as desktop_ui
import progression
import decoration_renderer
import minigames
from progression_ui import AchievementsWindow, RecordsWindow, ShopWindow
from minigames import MiniGameHubWindow
from home_scene import HomeSceneWindow

# Sound (optional — QtMultimedia may not be installed)
try:
    from PyQt5.QtMultimedia import QSoundEffect
    HAS_SOUND = True
except Exception:
    HAS_SOUND = False


def configure_display_scaling():
    """Keep Petpet's window geometry stable across Windows DPI settings."""
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    if not IS_WINDOWS:
        return

    # Window, control and pet geometry stay at their authored pixel sizes.
    # Typography is enlarged independently through FIXED_FONT_SCALE.
    QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
    try:
        import ctypes

        user32 = ctypes.windll.user32
        set_context = getattr(user32, "SetProcessDpiAwarenessContext", None)
        if set_context is not None:
            set_context.argtypes = [ctypes.c_void_p]
            set_context.restype = ctypes.c_bool
            if set_context(ctypes.c_void_p(-4)):
                return
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except Exception:
            user32.SetProcessDPIAware()
    except Exception:
        # The packaged EXE also carries a PerMonitorV2 manifest.
        pass


DEFAULT_PET_SIZE = (190, 220, 160)
MACOS_PET_SIZE = (150, 180, 132)


# ---------- paths ----------
RES_DIR = RESOURCE_DIR
SVG_PATH = os.path.join(RES_DIR, "pet.svg")
ICON_PATH = os.path.join(ICONS_DIR, "icon-64.png")
SAVE_PATH = os.path.join(DATA_DIR, "pet_state.json")
DEBUG_PARAMETERS_PATH = os.path.join(DATA_DIR, "debug_parameters.json")
POSE_NAMES = ["idle", "happy", "sad", "eat", "sleep", "drag", "close"]
POSE = {name: i for i, name in enumerate(POSE_NAMES)}
CELL = 200  # each pose is 200x200; spritesheet is 1200x200

DEFAULT_ANIMATIONS = {
    "idle":  {"fps": 8,  "loop": True,  "fallback": "idle"},
    "idle_dinosaur": {"fps": 8, "loop": True, "fallback": "idle"},
    "walk":  {"fps": 6,  "loop": True,  "fallback": "idle",
              "scale": 1.56, "anchor_bottom": True},
    "eat":   {"fps": 20, "loop": True,  "fallback": "eat",
              "scale": 1.0, "anchor_bottom": True,
              "saturation": 0.9, "brightness": 0.97},
    "play":  {"fps": 24, "loop": False, "fallback": "happy",
              "scale": 1.3, "anchor_bottom": True},
    "happy": {"fps": 8,  "loop": True,  "fallback": "happy"},
    "pet":   {"fps": 20, "loop": False, "fallback": "happy",
              "scale": 1.0, "anchor_bottom": True,
              "saturation": 0.9, "brightness": 0.97},
    "dig_reward": {"fps": 20, "loop": False, "fallback": "happy",
                   "scale": 1.0, "anchor_bottom": True},
    "sleep": {"fps": 2.4, "loop": True,  "fallback": "sleep",
              "scale": 0.6, "anchor_bottom": True},
    "drag":  {"fps": 6,  "loop": True,  "fallback": "drag"},
    "sad":   {"fps": 5,  "loop": True,  "fallback": "sad"},
    "sit":   {"fps": 6,  "loop": True,  "fallback": "idle"},
    "ask":   {"fps": 8,  "loop": False, "fallback": "idle"},
}

# Source-only live tuning defaults.  These values mirror the authored game
# constants so the tuner can restore a known baseline without touching user
# save data or release settings.
DEFAULT_DEBUG_PARAMETERS = {
    "pet_width": DEFAULT_PET_SIZE[0],
    "pet_height": DEFAULT_PET_SIZE[1],
    "dog_height": DEFAULT_PET_SIZE[2],
    "gravity": 2200.0,
    "wall_bounce": 0.55,
    "floor_bounce": 0.45,
    "ground_friction": 0.88,
    "walk_speed_min": 60.0,
    "walk_speed_max": 180.0,
    "auto_sleep_walk_speed": 118.0,
    "animation_idle_fps": 8.0,
    "animation_walk_fps": 6.0,
    "animation_eat_fps": 20.0,
    "animation_pet_fps": 20.0,
    "animation_play_fps": 24.0,
    "animation_sleep_fps": 2.4,
    "animation_dig_reward_fps": 20.0,
    "decay_hunger": 0.14,
    "decay_mood": 0.08,
    "decay_energy": 0.10,
    "decay_hunger_sleeping": 0.08,
    "decay_energy_sleeping_gain": 4.0,
    "auto_sleep_energy_threshold": 30.0,
    "auto_wake_energy_threshold": 80.0,
    "autonomy_idle_weight": 9.0,
    "autonomy_walk_weight": 1.0,
    "autonomy_sit_weight": 2.0,
    "dig_discovery_chance": progression.DIG_DISCOVERY_CHANCE,
    "dig_cooldown_minutes": progression.DIG_COOLDOWN_SECONDS / 60.0,
    "petting_affection_gain": progression.AFFECTION_ACTION_GAINS["pettings"],
    "feeding_affection_gain": progression.AFFECTION_ACTION_GAINS["feedings"],
    "play_affection_gain": progression.AFFECTION_ACTION_GAINS["play_sessions"],
    "petting_cooldown": progression.AFFECTION_ACTION_COOLDOWNS["pettings"],
    "feeding_cooldown": progression.AFFECTION_ACTION_COOLDOWNS["feedings"],
    "play_cooldown": progression.AFFECTION_ACTION_COOLDOWNS["play_sessions"],
    "feed_animation_duration": 1.5,
    "coin_catch_duration": minigames.CoinCatchCanvas.DURATION_SECONDS,
    "coin_target_lifetime": minigames.CoinCatchCanvas.TARGET_LIFETIME,
    "lucky_swap_1": minigames.LuckyPawsGameWindow.ROUND_CONFIG[1]["swap_duration"],
    "lucky_swap_2": minigames.LuckyPawsGameWindow.ROUND_CONFIG[2]["swap_duration"],
    "lucky_swap_3": minigames.LuckyPawsGameWindow.ROUND_CONFIG[3]["swap_duration"],
}

INSTANCE_SERVER_NAME = "com.gsheen.petpet.single-instance"


class SingleInstanceServer(QObject):
    """Allow one Petpet process and wake it when another copy is launched."""

    activation_requested = pyqtSignal()

    def __init__(self, server_name=INSTANCE_SERVER_NAME):
        super().__init__()
        self.server_name = server_name
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._on_new_connection)
        self.is_primary = False

    def start(self):
        """Return True for the primary process; notify it otherwise."""
        if self._notify_existing():
            return False

        # A crashed process can leave a stale Unix socket file.  On Windows
        # this is harmless, while on macOS removeServer clears that stale path.
        QLocalServer.removeServer(self.server_name)
        if self.server.listen(self.server_name):
            self.is_primary = True
            return True

        # Resolve the narrow race where two processes start together.
        return False if self._notify_existing() else False

    def _notify_existing(self):
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(450):
            return False
        socket.write(b"activate")
        socket.flush()
        socket.waitForBytesWritten(450)
        socket.disconnectFromServer()
        return True

    def _on_new_connection(self):
        received = False
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.readAll()
            socket.disconnectFromServer()
            socket.deleteLater()
            received = True
        if received:
            self.activation_requested.emit()

    def close(self):
        if not self.is_primary:
            return
        self.server.close()
        QLocalServer.removeServer(self.server_name)
        self.is_primary = False


class WakeShakeDetector:
    """Recognize a deliberate long-press, left-right shake gesture."""

    def __init__(self, hold_seconds=0.45, min_step=6,
                 required_reversals=3, min_distance=90):
        self.hold_seconds = float(hold_seconds)
        self.min_step = int(min_step)
        self.required_reversals = int(required_reversals)
        self.min_distance = float(min_distance)
        self.reset()

    def reset(self):
        self.started_at = None
        self.last_x = None
        self.direction = 0
        self.reversals = 0
        self.distance = 0.0

    def start(self, x, now=None):
        self.reset()
        self.started_at = time.monotonic() if now is None else float(now)
        self.last_x = float(x)

    def move(self, x, now=None):
        if self.started_at is None or self.last_x is None:
            return False
        now = time.monotonic() if now is None else float(now)
        x = float(x)
        delta = x - self.last_x
        if abs(delta) < self.min_step:
            return False

        new_direction = 1 if delta > 0 else -1
        self.distance += abs(delta)
        self.last_x = x
        if self.direction and new_direction != self.direction:
            self.reversals += 1
        self.direction = new_direction
        return (
            now - self.started_at >= self.hold_seconds
            and self.reversals >= self.required_reversals
            and self.distance >= self.min_distance
        )


def adjust_animation_colors(pixmap, saturation=1.0, brightness=1.0):
    """Apply a fast, alpha-safe color correction to an animation frame.

    ``saturation`` and ``brightness`` are intentionally limited to 0..1.
    Animation source PNGs stay untouched, so corrections remain reversible
    and can be tuned independently for every action in the manifest.
    """
    try:
        saturation = max(0.0, min(1.0, float(saturation)))
        brightness = max(0.0, min(1.0, float(brightness)))
    except (TypeError, ValueError):
        return pixmap
    if pixmap.isNull() or (
            abs(saturation - 1.0) < 0.001
            and abs(brightness - 1.0) < 0.001):
        return pixmap

    image = pixmap.toImage().convertToFormat(
        QImage.Format_ARGB32_Premultiplied
    )
    result = QImage(image)

    if saturation < 0.999:
        grayscale = image.convertToFormat(QImage.Format_Grayscale8)
        grayscale = grayscale.convertToFormat(
            QImage.Format_ARGB32_Premultiplied
        )
        # Copy the source transparency without relying on alphaChannel(),
        # which is unavailable in some PyQt5 builds.
        mask_painter = QPainter(grayscale)
        mask_painter.setCompositionMode(
            QPainter.CompositionMode_DestinationIn
        )
        mask_painter.drawImage(0, 0, image)
        mask_painter.end()
        painter = QPainter(result)
        painter.setOpacity(1.0 - saturation)
        painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        painter.drawImage(0, 0, grayscale)
        painter.end()

    if brightness < 0.999:
        painter = QPainter(result)
        painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        painter.fillRect(
            result.rect(),
            QColor(0, 0, 0, int(round((1.0 - brightness) * 255))),
        )
        painter.end()

    return QPixmap.fromImage(result)


WARM_MENU_STYLE = """
    QMenu {
        background:#fffaf0;
        color:#65483b;
        border:1px solid #edc9ad;
        border-radius:15px;
        padding:12px;
        min-width:310px;
        font-family:'Microsoft YaHei';
        font-size:17px;
    }
    QMenu::item {
        padding:12px 40px 12px 18px;
        border-radius:10px;
        margin:2px 4px;
    }
    QMenu::item:selected {
        background:#ffe2d8;
        color:#8a4f40;
    }
    QMenu::item:disabled {
        color:#b98f7a;
        background:#fff3e4;
    }
    QMenu::separator {
        height:2px;
        background:#efd8c4;
        margin:8px 12px;
    }
    QMenu::indicator:checked {
        background:#f28f76;
        border-radius:5px;
    }
"""

def load_debug_parameters():
    """Load source-only tuning values, ignoring unknown or invalid entries."""
    values = dict(DEFAULT_DEBUG_PARAMETERS)
    try:
        with open(DEBUG_PARAMETERS_PATH, "r", encoding="utf-8-sig") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            for key, default in DEFAULT_DEBUG_PARAMETERS.items():
                value = loaded.get(key, default)
                try:
                    value = float(value)
                    values[key] = value if math.isfinite(value) else default
                except (TypeError, ValueError):
                    values[key] = default
    except (OSError, ValueError, TypeError):
        pass
    return values


def save_debug_parameters(values):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(DEBUG_PARAMETERS_PATH, "w", encoding="utf-8") as f:
            json.dump(values, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ---------- state ----------
DEFAULT_STATE = {
    "hunger": 80, "mood": 70, "energy": 90,
    "x": None, "y": None, "sleeping": False, "sleep_mode": None,
    "born": time.time(),
    "autostart": False,
    "level": 1, "xp": 0,
    "affection_level": 1, "affection_points": 0,
    "passive_xp_buffer": 0.0,
    "passive_affection_buffer": 0.0,
    "pet_coins": 0,
    "pending_dig_reward": 0,
    "last_dig_discovery_at": 0.0,
    "pet_name": ai.DEFAULT_PET_NAME,
    "tutorial_completed": False,
}

# XP needed to go from level L to L+1: 100 * L^1.5 (slowing curve)
def xp_to_next(level):
    return int(100 * (level ** 1.5))

def load_state():
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            s = json.load(f)
            state = {**DEFAULT_STATE, **s}
            state["pet_name"] = ai.normalize_pet_name(
                state.get("pet_name")
            )
            state["tutorial_completed"] = bool(
                state.get("tutorial_completed", False)
            )
            if state.get("sleeping"):
                if state.get("sleep_mode") not in ("manual", "auto"):
                    # Sleeping saves from older versions are user-controlled.
                    state["sleep_mode"] = "manual"
            else:
                state["sleep_mode"] = None
            progression.ensure_progression(state)
            return app_state.ensure_state_schema(
                state,
                ai.DEFAULT_PET_NAME,
                ai.normalize_pet_name,
            )
    except Exception:
        state = progression.ensure_progression(dict(DEFAULT_STATE))
        return app_state.ensure_state_schema(
            state,
            ai.DEFAULT_PET_NAME,
            ai.normalize_pet_name,
        )

def save_state(s):
    try:
        app_state.prepare_state_for_save(s)
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f)
    except Exception:
        pass


# ---------- AI thread -> GUI signal bridge ----------
class _Bridge(QObject):
    token = pyqtSignal(str)        # one chunk of reply text
    done  = pyqtSignal(str)        # full reply (finished)
    error = pyqtSignal(str)        # error message
    update_checked = pyqtSignal(object)
    update_progress = pyqtSignal(int)
    update_finished = pyqtSignal(object)

bridge = None  # set in main


class PetpetConfirmDialog(QDialog):
    """Warm, frameless confirmation card shared by Petpet surfaces."""
    def __init__(self, parent=None, *, title, message,
                 accept_text="确认", reject_text="取消"):
        super().__init__(parent)
        self.setObjectName("petpetConfirm")
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(430)

        card = QFrame()
        card.setObjectName("petpetDialogCard")
        badge = QLabel("?")
        badge.setObjectName("petpetDialogBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(44, 44)
        heading = QLabel(title)
        heading.setObjectName("petpetDialogTitle")
        heading.setFont(independent_pixel_font(21, QFont.Bold))
        body = QLabel(message)
        body.setObjectName("petpetDialogMessage")
        body.setFont(independent_pixel_font(18))
        body.setWordWrap(True)

        self.reject_btn = QPushButton(reject_text)
        self.reject_btn.setObjectName("petpetSecondary")
        self.accept_btn = QPushButton(accept_text)
        self.accept_btn.setObjectName("petpetPrimary")
        for button in (self.reject_btn, self.accept_btn):
            button.setFont(independent_pixel_font(17, QFont.Bold))
            button.setMinimumHeight(40)
        self.reject_btn.clicked.connect(self.reject)
        self.accept_btn.clicked.connect(self.accept)
        self.reject_btn.setDefault(True)

        text_box = QVBoxLayout()
        text_box.setSpacing(5)
        text_box.addWidget(heading)
        text_box.addWidget(body)
        header = QHBoxLayout()
        header.setSpacing(13)
        header.addWidget(badge, 0, Qt.AlignTop)
        header.addLayout(text_box, 1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.reject_btn)
        actions.addWidget(self.accept_btn)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 18)
        card_layout.setSpacing(16)
        card_layout.addLayout(header)
        card_layout.addLayout(actions)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(card)
        self.setStyleSheet("""
            QDialog#petpetConfirm { background:transparent; }
            QFrame#petpetDialogCard {
                background:#fff9f4; border:1px solid #edcfc2;
                border-radius:22px;
            }
            QLabel#petpetDialogBadge {
                background:#fff1cc; color:#c77b67; border:1px solid #f0d59c;
                border-radius:22px; font-weight:800;
            }
            QLabel#petpetDialogTitle { color:#704b3c; font-weight:800; }
            QLabel#petpetDialogMessage { color:#8e6858; }
            QPushButton { min-height:40px; padding:0 18px; border-radius:20px; font-weight:700; }
            QPushButton#petpetSecondary {
                background:#fffdf9; color:#7d5a4c; border:1px solid #e7cec1;
            }
            QPushButton#petpetSecondary:hover { background:#fff1e8; }
            QPushButton#petpetPrimary {
                background:#f8dcd7; color:#704b3c; border:1px solid #efc4bb;
            }
            QPushButton#petpetPrimary:hover { background:#f3c9c1; }
        """)


class PetNameEditDialog(QDialog):
    """Small warm name editor used by the desktop attribute card."""
    def __init__(self, current_name, on_apply, parent=None):
        super().__init__(parent)
        self.on_apply = on_apply
        self.setWindowTitle("给小狗改名")
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(360)

        card = QFrame()
        card.setObjectName("petNameEditCard")
        title = QLabel("给小狗改个名字")
        title.setObjectName("petNameEditTitle")
        title.setFont(independent_pixel_font(21, QFont.Bold))
        hint = QLabel("最多 6 个字符")
        hint.setObjectName("petNameEditHint")
        hint.setFont(independent_pixel_font(16))
        self.name_input = QLineEdit(str(current_name))
        self.name_input.setMaxLength(6)
        self.name_input.setFont(independent_pixel_font(20))
        self.name_input.returnPressed.connect(self._apply)
        self.error_label = QLabel("")
        self.error_label.setObjectName("petNameEditError")
        self.error_label.setFont(independent_pixel_font(15, QFont.Bold))
        cancel = QPushButton("取消")
        cancel.setObjectName("petNameEditSecondary")
        apply_button = QPushButton("保存")
        apply_button.setObjectName("petNameEditPrimary")
        for button in (cancel, apply_button):
            button.setFont(independent_pixel_font(17, QFont.Bold))
            button.setMinimumHeight(40)
        cancel.clicked.connect(self.reject)
        apply_button.clicked.connect(self._apply)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self.name_input)
        layout.addWidget(self.error_label)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(apply_button)
        layout.addLayout(actions)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(card)
        self.setStyleSheet("""
            QDialog { background:transparent; }
            QFrame#petNameEditCard {
                background:#fff9f4; border:1px solid #edcfc2; border-radius:22px;
            }
            QLabel#petNameEditTitle { color:#704b3c; }
            QLabel#petNameEditHint { color:#a77b69; }
            QLabel#petNameEditError { color:#c66d5a; }
            QLineEdit {
                min-height:42px; padding:0 14px; background:#fffdf9;
                color:#65483b; border:2px solid #edcdb3; border-radius:15px;
                selection-background-color:#ffc9b8;
            }
            QPushButton { min-height:40px; padding:0 18px; border-radius:20px; }
            QPushButton#petNameEditSecondary {
                background:#fffdf9; color:#7d5a4c; border:1px solid #e7cec1;
            }
            QPushButton#petNameEditPrimary {
                background:#f8dcd7; color:#704b3c; border:1px solid #efc4bb;
            }
        """)

    def center_on_screen(self, screen_rect=None):
        """Center the editor on the active pet screen."""
        if screen_rect is None:
            screen = QApplication.screenAt(self.parentWidget().frameGeometry().center()) \
                if self.parentWidget() is not None else QApplication.primaryScreen()
            screen_rect = screen.availableGeometry() if screen is not None else QRect()
        self.adjustSize()
        self.move(
            screen_rect.x() + (screen_rect.width() - self.width()) // 2,
            screen_rect.y() + (screen_rect.height() - self.height()) // 2,
        )

    def _apply(self):
        raw_name = " ".join(self.name_input.text().split())
        if not any(char.isalnum() for char in raw_name):
            self.error_label.setText("请输入一个名字哦")
            self.name_input.setFocus()
            return False
        self.on_apply(ai.normalize_pet_name(raw_name))
        self.accept()
        return True


class PetpetPopupMenu(QFrame):
    """Small rounded popup card that closes when focus leaves it."""
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("petpetPopup")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._card = QFrame()
        self._card.setObjectName("petpetPopupCard")
        self._actions_layout = QVBoxLayout(self._card)
        self._actions_layout.setContentsMargins(6, 6, 6, 6)
        self._actions_layout.setSpacing(3)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(3, 3, 3, 3)
        outer.addWidget(self._card)
        self.setStyleSheet("""
            QFrame#petpetPopup { background:transparent; border:0; }
            QFrame#petpetPopupCard {
                background:#fff9f4; border:1px solid #edcfc2;
                border-radius:16px;
            }
            QPushButton#petpetPopupAction {
                min-width:148px; min-height:40px; text-align:left;
                padding:0 14px; background:transparent; color:#704b3c;
                border:0; border-radius:11px; font-weight:700;
            }
            QPushButton#petpetPopupAction:hover { background:#f8dcd7; }
        """)

    def add_action(self, text, callback):
        button = QPushButton(text)
        button.setObjectName("petpetPopupAction")
        button.setFont(independent_pixel_font(17, QFont.Bold))
        button.setMinimumHeight(40)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        button.clicked.connect(self.close)
        self._actions_layout.addWidget(button)
        return button

    def popup_below(self, anchor):
        self.adjustSize()
        point = anchor.mapToGlobal(QPoint(0, anchor.height() + 6))
        self.move(point)
        self.show()
        self.raise_()




class ChatWindow(PackageChatWindow):
    """Compatibility facade for the packaged chat window implementation."""

    def __init__(self, pet_window, memory_profile="desktop"):
        super().__init__(
            pet_window,
            memory_profile,
            bridge_provider=lambda: bridge,
            confirm_dialog_factory=lambda *args, **kwargs: PetpetConfirmDialog(
                *args, **kwargs
            ),
            popup_menu_factory=lambda *args, **kwargs: PetpetPopupMenu(
                *args, **kwargs
            ),
            save_state_callback=lambda state: save_state(state),
            progression_service=progression,
        )


class StatsWindow(QWidget):
    """A pretty stats / level panel — gives the player a sense of achievement."""
    def __init__(self, pet_window):
        super().__init__()
        self.pet = pet_window
        self.s = pet_window.settings

        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowTitle(
            f"{self.pet.pet_name} · 温暖档案"
        )
        self.setFixedSize(460, 580)

        # stats panel uses its own larger font scale (not ui_font_size)
        fs = 16
        self.setStyleSheet(f"""
            QWidget {{ background:#fff8ec; font-family:'Microsoft YaHei',sans-serif;
                       font-size:{font_px(fs)}px; color:#65483b; }}
            QLabel {{ padding:2px 0; }}
            QFrame#card {{ background:#fffdf8; border:1px solid #efd1b8;
                            border-radius:17px; }}
            QProgressBar {{ background:#f3e3d5; border:0; border-radius:8px;
                            height:16px; text-align:center; color:#fff;
                            font-size:{font_px(max(11, fs-2))}px; font-weight:700; }}
            QProgressBar::chunk {{ border-radius:8px; }}
            QLabel#h1 {{ font-size:{font_px(fs+7)}px; font-weight:800; color:#744d3e; }}
            QLabel#h2 {{ font-size:{font_px(fs+2)}px; font-weight:700; color:#a46c58; }}
            QLabel#big {{ font-size:{font_px(fs+22)}px; font-weight:900; color:#f28f76; }}
            QLabel#gold {{ font-size:{font_px(fs+1)}px; font-weight:800; color:#c68a38; }}
            QLabel#small {{ font-size:{font_px(max(11,fs-2))}px; color:#aa8170; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        # Header: level + title
        head = QHBoxLayout()
        head.setSpacing(12)
        self.lvl_label = QLabel()
        self.lvl_label.setObjectName("big")
        self.lvl_label.setAlignment(Qt.AlignCenter)
        self.lvl_label.setFixedWidth(105)
        head.addWidget(self.lvl_label)
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        self.title_label = QLabel()
        self.title_label.setObjectName("h1")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("small")
        title_col.addWidget(self.title_label)
        title_col.addWidget(self.subtitle_label)
        head.addLayout(title_col, 1)
        layout.addLayout(head)

        # XP bar
        self.xp_bar = QProgressBar()
        self.xp_bar.setTextVisible(True)
        layout.addWidget(self.xp_bar)

        # Days together
        self.days_label = QLabel()
        self.days_label.setObjectName("h2")
        self.days_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.days_label)

        # Stat cards
        self.bars = {}
        for key, name, emoji, color in [
            ("hunger", "饱腹", "🍗", "#f49a62"),
            ("mood",   "心情", "🌷", "#ef8fa2"),
            ("energy", "精力", "⚡", "#9b8ade"),
        ]:
            card = QFrame()
            card.setObjectName("card")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 10, 14, 12)
            cl.setSpacing(6)
            row = QHBoxLayout()
            nm = QLabel(f"{emoji}  {name}")
            nm.setStyleSheet(
                f"font-size:{font_px(fs+1)}px; font-weight:700;"
            )
            val = QLabel()
            val.setStyleSheet(
                f"font-size:{font_px(fs+2)}px; font-weight:800; color:{color};"
            )
            val.setAlignment(Qt.AlignRight)
            row.addWidget(nm); row.addStretch(1); row.addWidget(val)
            cl.addLayout(row)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{ background:#f2e3d7; border:0; border-radius:7px; height:12px; }}
                QProgressBar::chunk {{ background:{color}; border-radius:7px; }}
            """)
            cl.addWidget(bar)
            layout.addWidget(card)
            self.bars[key] = (bar, val, color)

        # footer
        hint = QLabel("♡ 每一次照顾，都在积累温暖的陪伴")
        hint.setObjectName("small")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        # refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(1000)
        self.refresh()

    def refresh(self):
        st = self.pet.state
        name = self.pet.pet_name
        self.setWindowTitle(f"{name} · 温暖档案")
        lvl = st.get("level", 1)
        xp = st.get("xp", 0)
        need = xp_to_next(lvl)
        self.lvl_label.setText(f"Lv.{lvl}")
        self.title_label.setText(f"{name} 的小屋")
        self.subtitle_label.setText(f"距离下一级：{max(0, need-xp)} EXP")
        self.subtitle_label.setObjectName("gold")
        self.subtitle_label.setStyleSheet(
            "font-size:34px; font-weight:800; color:#c68a38;")
        # QProgressBar uses 32-bit integers; render a normalized ratio so very
        # high levels cannot overflow while the label still shows real values.
        progress_scale = 10000
        self.xp_bar.setRange(0, progress_scale)
        self.xp_bar.setValue(int(max(0.0, min(1.0, xp / max(1, need))) *
                                 progress_scale))
        self.xp_bar.setFormat(f"EXP {int(xp)} / {need}")
        self.xp_bar.setStyleSheet("""
            QProgressBar { background:#f1dfcf; border:0; border-radius:9px; height:21px;
                           text-align:center; color:#9a672f; font-weight:800;
                           font-size:28px; }
            QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #ffc05c, stop:0.5 #ffd36f, stop:1 #ffe59b); border-radius:9px; }
        """)
        days = max(1, int((time.time() - st.get("born", time.time())) / 86400))
        self.days_label.setText(f"♡ 已经温暖陪伴你 {days} 天")
        for key, (bar, val, color) in self.bars.items():
            v = int(st.get(key, 0))
            bar.setValue(v)
            val.setText(f"{v}/100")


desktop_ui.configure_dependency_resolver(lambda name: globals()[name])

_pet_interface_anchor_rect = desktop_ui.pet_interface_anchor_rect
_pet_interface_anchor_visible = desktop_ui.pet_interface_anchor_visible
_pet_interface_screen_rect = desktop_ui.pet_interface_screen_rect
_pet_interface_bonus_origin = desktop_ui.pet_interface_bonus_origin
StatBubble = desktop_ui.StatBubble
BubbleMenu = desktop_ui.BubbleMenu
BonusBubble = desktop_ui.BonusBubble
InteractiveBubble = desktop_ui.InteractiveBubble
_esc = desktop_ui._esc
SpeechBubble = desktop_ui.SpeechBubble





class FetchPlayScene(QWidget):
    """Interactive zoomed-out fetch scene with a clickable throw zone."""

    ZOOM_SECONDS = 0.42
    COUNTDOWN_SECONDS = 3.0
    CELEBRATION_SECONDS = 1.0
    FRAME_BASELINE_RATIO = 440.0 / 512.0
    CATCH_BASELINE_RATIO = 0.37

    def __init__(self, pet_window, on_finished):
        super().__init__(None)
        self.pet = pet_window
        self._on_finished = on_finished
        self._finishing = False
        self._phase = "zoom"
        self._phase_started_at = time.monotonic()
        self._countdown_deadline = None
        self._target = None
        self._frame_index = 0
        self._hovering_target = False
        self.last_throw_was_automatic = False

        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.pet.settings.get("always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        screen = self.pet.current_screen_rect()
        width = max(360, min(760, screen.width() - 40))
        height = max(280, min(460, screen.height() - 80))
        pet_geometry = self.pet.geometry()
        x = pet_geometry.center().x() - width // 2
        y = pet_geometry.center().y() - height // 2
        x = max(screen.left(), min(x, screen.right() - width + 1))
        y = max(screen.top(), min(y, screen.bottom() - height + 1))
        self.setGeometry(int(x), int(y), int(width), int(height))

        self._zoom_origin = QPointF(
            pet_geometry.center().x() - x,
            pet_geometry.bottom() - y - 8,
        )
        target_x = width * 0.14
        target_y = 72.0
        target_width = max(190.0, width * 0.72)
        target_height = max(130.0, height - 158.0)
        self.target_rect = QRectF(
            target_x, target_y, target_width, target_height
        )
        # The puppy waits inside the far end of the play field and faces the
        # player.  The ball starts close to the player at the bottom centre,
        # creating a straight-ahead throw instead of a sideways chase.
        self._dog_start = QPointF(
            self.target_rect.center().x(),
            self.target_rect.top() + self.target_rect.height() * 0.62,
        )
        self._throw_origin = QPointF(width * 0.5, height - 34)
        self._default_target = QPointF(
            self._dog_start.x(),
            self._dog_start.y() - 122.0 * self.CATCH_BASELINE_RATIO,
        )

        ensure_animation_loaded = getattr(
            self.pet, "_ensure_animation_loaded", None
        )
        if callable(ensure_animation_loaded):
            ensure_animation_loaded("play")
        self.frames = list(self.pet.animation_frames.get("play", ()))
        if not self.frames:
            fallback = (
                self.pet.pose_pixmaps.get(POSE["happy"])
                or self.pet.pose_pixmaps.get(POSE["idle"])
            )
            if fallback is not None:
                self.frames = [fallback]
        try:
            self.fps = max(
                1.0,
                float(self.pet.animation_specs.get("play", {}).get("fps", 14)),
            )
        except (TypeError, ValueError):
            self.fps = 24.0

        ball_path = os.path.join(PROPS_DIR, "fetch_ball.png")
        self.ball_pixmap = QPixmap(ball_path)
        if not self.ball_pixmap.isNull():
            visible = QRegion(self.ball_pixmap.mask()).boundingRect()
            if visible.isValid() and not visible.isEmpty():
                self.ball_pixmap = self.ball_pixmap.copy(visible)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.setInterval(16)

    @staticmethod
    def _ease_out_cubic(value):
        value = max(0.0, min(1.0, float(value)))
        return 1.0 - (1.0 - value) ** 3

    @staticmethod
    def _lerp_point(start, end, progress):
        return QPointF(
            start.x() + (end.x() - start.x()) * progress,
            start.y() + (end.y() - start.y()) * progress,
        )

    def _font(self, size, weight=QFont.Normal):
        font = QFont("Microsoft YaHei")
        font.setPixelSize(max(1, int(size)))
        font.setWeight(weight)
        return font

    def start(self):
        self._phase = "zoom"
        self._phase_started_at = time.monotonic()
        self.show()
        self.raise_()
        self.timer.start()
        self.update()

    def countdown_value(self, now=None):
        if self._phase != "aim" or self._countdown_deadline is None:
            return 0
        now = time.monotonic() if now is None else float(now)
        return max(1, int(math.ceil(self._countdown_deadline - now)))

    def _clamp_target(self, point):
        inset = self.target_rect.adjusted(14, 14, -14, -14)
        return QPointF(
            max(inset.left(), min(float(point.x()), inset.right())),
            max(inset.top(), min(float(point.y()), inset.bottom())),
        )

    def start_throw(self, target, automatic=False, now=None):
        if self._phase in ("fetch", "celebrate"):
            return
        self._target = self._clamp_target(target)
        self.last_throw_was_automatic = bool(automatic)
        self._phase = "fetch"
        self._phase_started_at = (
            time.monotonic() if now is None else float(now)
        )
        self._frame_index = 0
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def _advance(self, now):
        if self._finishing:
            return
        if self._phase == "zoom":
            if now - self._phase_started_at >= self.ZOOM_SECONDS:
                self._phase = "aim"
                self._phase_started_at = now
                self._countdown_deadline = now + self.COUNTDOWN_SECONDS
        elif self._phase == "aim":
            if (self._countdown_deadline is not None
                    and now >= self._countdown_deadline):
                self.start_throw(
                    self._default_target,
                    automatic=True,
                    now=now,
                )
        elif self._phase == "fetch":
            frame_count = max(1, len(self.frames))
            elapsed = max(0.0, now - self._phase_started_at)
            frame_index = int(elapsed * self.fps)
            if frame_index >= frame_count:
                self._phase = "celebrate"
                self._phase_started_at = now
                self._frame_index = frame_count - 1
            else:
                self._frame_index = frame_index
        elif self._phase == "celebrate":
            if now - self._phase_started_at >= self.CELEBRATION_SECONDS:
                self._finish(completed=True)
                return
        self.update()

    def _tick(self):
        self._advance(time.monotonic())

    def _finish(self, completed):
        if self._finishing:
            return
        self._finishing = True
        self.timer.stop()
        self.hide()
        callback = self._on_finished
        self._on_finished = None
        if callable(callback):
            callback(self, bool(completed))
        self.close()
        self.deleteLater()

    def cancel(self, notify=True):
        if notify:
            self._finish(completed=False)
            return
        self._finishing = True
        self.timer.stop()
        self._on_finished = None
        self.hide()
        self.close()
        self.deleteLater()

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)

    def mouseMoveEvent(self, event):
        hovering = (
            self._phase == "aim"
            and self.target_rect.contains(QPointF(event.pos()))
        )
        if hovering != self._hovering_target:
            self._hovering_target = hovering
            self.setCursor(
                Qt.CrossCursor if hovering else Qt.ArrowCursor
            )
            self.update()

    def leaveEvent(self, event):
        self._hovering_target = False
        self.setCursor(Qt.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if (event.button() == Qt.LeftButton
                and self._phase == "aim"
                and self.target_rect.contains(QPointF(event.pos()))):
            self.start_throw(QPointF(event.pos()), automatic=False)
            return
        super().mousePressEvent(event)

    def _fetch_dog_baseline(self, frame_index, dog_size):
        progress = self._fetch_progress(frame_index)
        end = QPointF(
            self._target.x(),
            self._target.y() + dog_size * self.CATCH_BASELINE_RATIO,
        )
        end.setY(min(self.height() - 34.0, end.y()))
        eased = progress * progress * (3.0 - 2.0 * progress)
        point = self._lerp_point(self._dog_start, end, eased)
        point.setY(point.y() - 58.0 * math.sin(math.pi * progress))
        return point

    def _fetch_progress(self, frame_index):
        last_frame = max(1, len(self.frames) - 1)
        return max(0.0, min(1.0, float(frame_index) / last_frame))

    def _ball_position(self, frame_index):
        progress = self._fetch_progress(frame_index)
        point = self._lerp_point(
            self._throw_origin, self._target, progress
        )
        point.setY(point.y() - 92.0 * math.sin(math.pi * progress))
        return point

    def _draw_ball(self, painter, center, size, rotation=0.0):
        if self.ball_pixmap.isNull():
            painter.setPen(QPen(QColor("#d95d52"), 2))
            painter.setBrush(QColor("#f27262"))
            painter.drawEllipse(
                QRectF(
                    center.x() - size / 2,
                    center.y() - size / 2,
                    size, size,
                )
            )
            return
        painter.save()
        painter.translate(center)
        painter.rotate(rotation)
        painter.drawPixmap(
            QRectF(-size / 2, -size / 2, size, size),
            self.ball_pixmap,
            QRectF(
                0, 0,
                self.ball_pixmap.width(),
                self.ball_pixmap.height(),
            ),
        )
        painter.restore()

    def _draw_dog(self, painter, frame_index, baseline, size):
        if not self.frames:
            return
        pixmap = self.frames[
            max(0, min(int(frame_index), len(self.frames) - 1))
        ]
        shadow_width = size * 0.54
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(92, 61, 42, 42))
        painter.drawEllipse(QRectF(
            baseline.x() - shadow_width / 2,
            baseline.y() - 8,
            shadow_width, 14,
        ))
        target = QRectF(
            baseline.x() - size / 2,
            baseline.y() - size * self.FRAME_BASELINE_RATIO,
            size, size,
        )
        painter.drawPixmap(
            target, pixmap,
            QRectF(0, 0, pixmap.width(), pixmap.height()),
        )

    def _draw_celebration(self, painter, now):
        elapsed = max(0.0, now - self._phase_started_at)
        progress = min(1.0, elapsed / self.CELEBRATION_SECONDS)
        eased = self._ease_out_cubic(progress)
        center = QPointF(self._target)

        ring_radius = 19.0 + 31.0 * eased
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(
            QColor(255, 181, 79, int(190 * (1.0 - progress))),
            2.5,
        ))
        painter.drawEllipse(center, ring_radius, ring_radius)

        colors = (
            QColor("#ff8f7c"),
            QColor("#ffc45d"),
            QColor("#f487ab"),
            QColor("#9d8bea"),
        )
        for index in range(10):
            angle = -math.pi + index * math.pi * 2.0 / 10.0
            radius = 31.0 + eased * (25.0 + (index % 3) * 5.0)
            particle_center = QPointF(
                center.x() + math.cos(angle) * radius,
                center.y() + math.sin(angle) * radius
                - 7.0 * math.sin(progress * math.pi),
            )
            size = 4.5 + (index % 2) * 1.5
            color = QColor(colors[index % len(colors)])
            color.setAlpha(int(245 * (1.0 - 0.28 * progress)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            if index % 2:
                heart = QPainterPath()
                heart.moveTo(
                    particle_center.x(),
                    particle_center.y() + size * 0.75,
                )
                heart.cubicTo(
                    particle_center.x() - size * 1.35,
                    particle_center.y() - size * 0.1,
                    particle_center.x() - size * 0.65,
                    particle_center.y() - size,
                    particle_center.x(),
                    particle_center.y() - size * 0.35,
                )
                heart.cubicTo(
                    particle_center.x() + size * 0.65,
                    particle_center.y() - size,
                    particle_center.x() + size * 1.35,
                    particle_center.y() - size * 0.1,
                    particle_center.x(),
                    particle_center.y() + size * 0.75,
                )
                painter.drawPath(heart)
            else:
                points = []
                for point_index in range(10):
                    point_angle = (
                        -math.pi / 2.0 + point_index * math.pi / 5.0
                    )
                    point_radius = (
                        size if point_index % 2 == 0 else size * 0.42
                    )
                    points.append(QPointF(
                        particle_center.x()
                        + math.cos(point_angle) * point_radius,
                        particle_center.y()
                        + math.sin(point_angle) * point_radius,
                    ))
                painter.drawPolygon(QPolygonF(points))

        badge_width = 116.0
        badge_height = 34.0
        badge_x = max(
            self.target_rect.left() + 8.0,
            min(
                center.x() - badge_width / 2.0,
                self.target_rect.right() - badge_width - 8.0,
            ),
        )
        badge_y = max(
            self.target_rect.top() + 9.0,
            center.y() - 68.0 - 4.0 * math.sin(progress * math.pi),
        )
        badge = QRectF(
            badge_x, badge_y, badge_width, badge_height
        )
        painter.setPen(QPen(QColor("#ef9f67"), 1.5))
        painter.setBrush(QColor(255, 249, 220, 245))
        painter.drawRoundedRect(badge, 15, 15)
        painter.setPen(QColor("#b05f45"))
        painter.setFont(self._font(16, QFont.Bold))
        painter.drawText(
            badge, Qt.AlignCenter | Qt.TextSingleLine, "接住啦！"
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        now = time.monotonic()
        if self._phase == "zoom":
            zoom_progress = self._ease_out_cubic(
                (now - self._phase_started_at) / self.ZOOM_SECONDS
            )
        else:
            zoom_progress = 1.0

        # A warm translucent play field that still leaves the desktop visible.
        field_alpha = int(zoom_progress * 190)
        field = self.target_rect
        painter.setPen(QPen(
            QColor(235, 146, 112, int(zoom_progress * 230)),
            2.2,
            Qt.DashLine,
        ))
        field_color = QColor(255, 244, 229, field_alpha)
        if self._hovering_target:
            field_color = QColor(255, 225, 210, 218)
        painter.setBrush(field_color)
        painter.drawRoundedRect(field, 24, 24)

        if self._phase == "aim":
            painter.setFont(self._font(16, QFont.Bold))
            painter.setPen(QColor("#a36b58"))
            painter.drawText(
                field.adjusted(14, 14, -14, -14),
                Qt.AlignTop | Qt.AlignHCenter,
                "点击这里，决定小球的落点",
            )
            pulse = 1.0 + 0.12 * math.sin(now * 6.0)
            painter.setPen(QPen(QColor(235, 146, 112, 155), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(
                self._default_target,
                17 * pulse,
                17 * pulse,
            )

        header = QRectF(
            self.width() / 2 - 176,
            16, 352, 46,
        )
        painter.setPen(QPen(QColor(239, 193, 163, 230), 1.2))
        painter.setBrush(QColor(255, 248, 238, 240))
        painter.drawRoundedRect(header, 18, 18)
        painter.setPen(QColor("#805748"))
        painter.setFont(self._font(18, QFont.Bold))
        if self._phase == "zoom":
            header_text = "视角拉远中…准备玩球！"
        elif self._phase == "aim":
            header_text = (
                f"点击区域扔球  ·  {self.countdown_value(now)}"
            )
        else:
            header_text = "快去接住它！"
        painter.drawText(
            header, Qt.AlignCenter | Qt.TextSingleLine, header_text
        )
        if self._phase == "celebrate":
            painter.setPen(QPen(QColor(239, 193, 163, 230), 1.2))
            painter.setBrush(QColor(255, 248, 224, 245))
            painter.drawRoundedRect(header, 18, 18)
            painter.setPen(QColor("#a85f45"))
            painter.setFont(self._font(18, QFont.Bold))
            painter.drawText(
                header,
                Qt.AlignCenter | Qt.TextSingleLine,
                "接球成功 · 太棒啦！",
            )

        if self._phase == "zoom":
            dog_baseline = self._lerp_point(
                self._zoom_origin, self._dog_start, zoom_progress
            )
            dog_size = 168.0 - 46.0 * zoom_progress
            self._draw_dog(painter, 0, dog_baseline, dog_size)
        elif self._phase == "aim":
            self._draw_dog(painter, 0, self._dog_start, 122.0)
            self._draw_ball(
                painter, self._throw_origin, 28.0,
                rotation=now * 70.0 % 360.0,
            )
        else:
            frame_index = self._frame_index
            flight_progress = self._fetch_progress(frame_index)
            dog_size = 122.0 + 14.0 * math.sin(
                math.pi * flight_progress
            )
            baseline = self._fetch_dog_baseline(
                frame_index, dog_size
            )
            self._draw_dog(
                painter, frame_index, baseline, dog_size
            )
            ball_size = 32.0 - 20.0 * flight_progress
            self._draw_ball(
                painter,
                self._ball_position(frame_index),
                ball_size,
                rotation=frame_index * 32.0,
            )
            if self._phase == "celebrate":
                self._draw_celebration(painter, now)

        painter.end()


pet_window_controller.configure_dependency_resolver(
    lambda name: globals()[name]
)
PetWindow = pet_window_controller.PetWindow





class TrayApp:
    def __init__(self, app=None):
        self.app = app or QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        # AI bridge (must be created before PetWindow uses it)
        global bridge
        bridge = _Bridge()
        self.state = load_state()
        progression.record_session(self.state)
        save_state(self.state)
        self.pet = PetWindow(self.state)
        self.pet._app_action_cb = self._handle_bubble_action
        ai.set_pet_name(self.pet.pet_name)
        self.pet.show()

        # tray
        self.tray = QSystemTrayIcon(QIcon(ICON_PATH), self.app)
        self.tray.setToolTip(
            f"我的小狗 {self.pet.pet_name} — 双击显示/隐藏"
        )
        self.tray.activated.connect(self.on_tray_activated)
        self.menu = QMenu()
        self.menu.setStyleSheet(WARM_MENU_STYLE)
        self.build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        # share the menu with the pet so right-click on pet shows it too
        self.pet._ctx_menu_cb = lambda: self._fresh_menu()
        self._install_interaction_handlers()

        self._update_checking = False
        self._manual_update_check = False
        self._update_progress_dialog = None
        self._update_cancel_event = None
        self.tutorial_win = None
        self.pet._settings_applied_cb = self._on_settings_applied
        bridge.update_checked.connect(self._on_update_result)
        bridge.update_progress.connect(self._on_update_progress)
        bridge.update_finished.connect(self._on_update_finished)

        # Keep launch fast, then check quietly when the user enables it.
        if self.pet.settings.get("auto_check_updates", True):
            QTimer.singleShot(
                5000, lambda: self._check_update(manual=False)
            )
        if self.state.get("tutorial_completed", False):
            if ai.get_api_key():
                QTimer.singleShot(
                    1500,
                    lambda: self.pet.say(
                        ai.time_greeting(self.pet.pet_name), 3000
                    ),
                )
        else:
            QTimer.singleShot(700, self.open_tutorial)

    def _on_settings_applied(self, previous, current):
        """Handle app-level settings that PetWindow cannot apply itself."""
        if (not bool(previous.get("auto_check_updates", True)) and
                bool(current.get("auto_check_updates", True))):
            self._check_update(manual=False)
        self.refresh_menu()

    def _handle_bubble_action(self, action):
        """Handle app-level actions from the secondary bubble canvas."""
        if action == "hide":
            self.toggle_visible()
        elif action == "tutorial":
            self.open_tutorial()
        elif action == "quit":
            self.quit()

    def activate_existing_instance(self):
        """Bring the existing pet back when Petpet is launched again."""
        scene = self.pet.play_scene
        if scene is not None:
            try:
                if scene.isVisible():
                    scene.raise_()
                    return
            except RuntimeError:
                self.pet.play_scene = None
        # A second launch is an explicit summon action. Reposition first so
        # a pet that walked to an edge or stale monitor coordinate is visible.
        self.pet.recall()
        if not self.pet.isVisible():
            self.pet.show()
        self.pet.raise_()
        self.pet.say("我已经在这里啦～", 1800)

    def open_tutorial(self):
        """Open or restart the first-run guide."""
        if self.tutorial_win is None:
            self.tutorial_win = TutorialWindow(
                self.pet, self._complete_tutorial
            )
        self.tutorial_win.start()

    def _complete_tutorial(self, pet_name):
        """Persist onboarding completion and apply the chosen name."""
        name = self.pet.set_pet_name(pet_name)
        self.state["tutorial_completed"] = True
        save_state(self.state)
        self.tray.setToolTip(
            f"我的小狗 {name} — 双击显示/隐藏"
        )
        self.refresh_menu()
        self.pet.say(f"以后我就叫 {name} 啦！请多多关照～", 3600)

    def _install_interaction_handlers(self):
        """Install click, double-click, drag, and right-click handling."""
        self._press_pos = None
        self._press_t = 0
        self._press_button = None
        self._last_left_click_t = 0
        self._pending_single_click = None
        self.pet.mousePressEvent_orig = self.pet.mousePressEvent
        self.pet.mouseReleaseEvent_orig = self.pet.mouseReleaseEvent
        self.pet.mousePressEvent = self._wrap_press
        self.pet.mouseReleaseEvent = self._wrap_release

    def _check_update(self, manual=False):
        """Check GitHub Releases without blocking the pet or the tray."""
        if self._update_checking:
            if manual:
                self.pet.say("正在检查更新，请稍等一下～", 1800)
            return
        self._update_checking = True
        self._manual_update_check = bool(manual)
        if manual:
            self.pet.say("正在检查新版本…", 1600)
        check_for_updates_async(VERSION, bridge.update_checked.emit)

    def _on_update_result(self, info):
        """Runs on the Qt thread through ``bridge.update_checked``."""
        self._update_checking = False
        manual = self._manual_update_check
        self._manual_update_check = False
        status = (info or {}).get("status", "error")

        if status == "latest":
            if manual:
                QMessageBox.information(
                    self.pet,
                    "已经是最新版",
                    f"当前版本 v{VERSION} 已经是最新版本。",
                )
            return
        if status in ("error", "unsupported"):
            if manual:
                message = info.get("message", "暂时无法获取更新信息。")
                if info.get("release_url"):
                    message += "\n\n可以前往 GitHub Releases 手动查看。"
                QMessageBox.warning(self.pet, "检查更新失败", message)
            return
        if status != "update":
            return

        msg = QMessageBox(self.pet)
        msg.setWindowTitle(f"{self.pet.pet_name} 有新版本")
        msg.setIcon(QMessageBox.Information)
        v = info["version"]
        notes = info.get("notes", "").strip() or "（暂无更新说明）"
        asset_name = info.get("asset_name", "")
        msg.setText(
            f"发现新版本 v{v}（当前 v{VERSION}）\n\n"
            f"更新包：{asset_name}\n\n更新内容：\n{notes[:500]}"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.button(QMessageBox.Yes).setText(
            "下载并打开" if IS_MACOS else "立即更新")
        msg.button(QMessageBox.No).setText("以后再说")
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec_() != QMessageBox.Yes:
            return

        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                self.pet,
                "开发模式",
                "当前是源码运行模式，不能自动替换程序本体。"
                "\n已为你打开最新版下载页面；打包后的 Petpet 可以自动更新。",
            )
            QDesktopServices.openUrl(
                QUrl(info.get("release_url") or info["download_url"])
            )
            return

        self._start_update_download(info)

    def _start_update_download(self, info):
        self._update_cancel_event = threading.Event()
        dialog = QProgressDialog(
            f"正在下载 Petpet v{info['version']}…", "取消", 0, 100, self.pet
        )
        dialog.setWindowTitle("更新 Petpet")
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setValue(0)
        dialog.canceled.connect(self._update_cancel_event.set)
        self._update_progress_dialog = dialog
        dialog.show()

        def worker():
            # Updates are disposable program files, never user data.  Keeping
            # them in the OS temp area prevents a downloaded EXE from treating
            # its cache directory as a fresh pet profile.
            update_dir = str(update_cache_dir(info["version"]))

            def progress(done, total):
                if total:
                    bridge.update_progress.emit(
                        max(0, min(100, int(done * 100 / total)))
                    )

            result = download_release(
                info,
                update_dir,
                progress=progress,
                cancel_event=self._update_cancel_event,
            )
            if result.get("ok"):
                try:
                    if IS_WINDOWS:
                        result = launch_windows_replacement(
                            result["path"],
                            sys.executable,
                            update_dir,
                        )
                    elif IS_MACOS:
                        result = open_macos_update(result["path"])
                    else:
                        result = {
                            "ok": False,
                            "message": "当前系统暂不支持自动更新",
                        }
                except Exception as exc:
                    result = {"ok": False, "message": str(exc)}
            bridge.update_finished.emit(result)

        threading.Thread(
            target=worker, daemon=True, name="Petpet-update-download"
        ).start()

    def _on_update_progress(self, value):
        if self._update_progress_dialog is not None:
            self._update_progress_dialog.setValue(value)

    def _on_update_finished(self, result):
        dialog = self._update_progress_dialog
        self._update_progress_dialog = None
        self._update_cancel_event = None
        if dialog is not None:
            dialog.close()

        if result.get("cancelled"):
            self.pet.say("已取消更新。", 1500)
            return
        if not result.get("ok"):
            QMessageBox.warning(
                self.pet,
                "更新失败",
                result.get("message", "下载失败，请稍后重试。"),
            )
            return
        if result.get("action") == "restart":
            self.pet.say("下载完成，马上重启到新版本～", 1800)
            QTimer.singleShot(700, QApplication.quit)
            return
        if result.get("action") == "open":
            QMessageBox.information(
                self.pet,
                "更新包已下载",
                "已打开最新版 macOS 更新包。"
                "\n请将 Petpet 拖入“应用程序”并替换旧版本。",
            )

    def _wrap_press(self, e):
        if e.button() == Qt.LeftButton:
            self._press_pos = e.globalPos()
            self._press_t = time.time()
            self._press_button = "left"
        elif e.button() == Qt.RightButton:
            self._press_pos = e.globalPos()
            self._press_t = time.time()
            self._press_button = "right"
        self.pet.mousePressEvent_orig(e)

    def _wrap_release(self, e):
        if e.button() == Qt.LeftButton and self._press_button == "left":
            moved = (e.globalPos() - self._press_pos).manhattanLength()
            dt = time.time() - self._press_t
            if moved < 8 and dt < 0.35:
                # short left click — but wait to see if it's a double click
                now = time.time()
                if now - self._last_left_click_t < 0.35:
                    # double click: cancel pending single click, open the home scene
                    if self._pending_single_click is not None:
                        self._pending_single_click.stop()
                        self._pending_single_click = None
                    self._last_left_click_t = 0
                    self.pet.open_home_scene()
                else:
                    # first click: schedule single-click action after delay
                    self._last_left_click_t = now
                    self._pending_single_click = QTimer(self.app)
                    self._pending_single_click.setSingleShot(True)
                    self._pending_single_click.timeout.connect(self._do_single_click)
                    self._pending_single_click.start(320)
            self._press_button = None
            self._press_pos = None
        elif e.button() == Qt.RightButton and self._press_button == "right":
            self._press_button = None
            self._press_pos = None
        self.pet.mouseReleaseEvent_orig(e)

    def _do_single_click(self):
        self._pending_single_click = None
        if not self.pet.state.get("sleeping"):
            self.pet.pet_click()

    def _show_pet_menu(self, pos):
        """Pop up the radial bubble menu (stat bar + 6 round bubbles)."""
        self.pet._bubble_menu = BubbleMenu(self.pet)

    def _populate_menu(self, m, include_status=False):
        """Shared menu layout — used by both tray and pet right-click menu.
        Order: status summary > 互动 > 管理 > 系统."""
        if include_status:
            # Optional status summary for standalone menus; the tray stays clean.
            lvl = self.state.get('level', 1)
            xp = int(self.state.get('xp', 0))
            need = xp_to_next(lvl)
            a_sum = QAction(f"📊 Lv.{lvl}  EXP {xp}/{need}", m)
            a_sum.setEnabled(False); m.addAction(a_sum)
            days = max(1, int((time.time() - self.state.get("born", time.time())) / 86400))
            a_age = QAction(f"📅 陪伴第 {days} 天", m)
            a_age.setEnabled(False); m.addAction(a_age)
            m.addSeparator()

        # ---- 互动 ----
        a_chat = QAction("💬 聊聊天", m); a_chat.triggered.connect(self.pet.chat); m.addAction(a_chat)
        a_feed = QAction("🍖 喂食", m); a_feed.triggered.connect(self.pet.feed); m.addAction(a_feed)
        a_play = QAction("🎾 玩耍", m); a_play.triggered.connect(self.pet.play); m.addAction(a_play)
        a_sleep = QAction("💤 睡觉/起床", m); a_sleep.triggered.connect(self.pet.toggle_sleep); m.addAction(a_sleep)
        m.addSeparator()

        # ---- 管理 ----
        a_recall = QAction("🎯 回到屏幕中央", m); a_recall.triggered.connect(self.pet.recall); m.addAction(a_recall)
        a_hide = QAction("👁 显示/隐藏", m); a_hide.triggered.connect(self.toggle_visible); m.addAction(a_hide)
        a_settings = QAction("⚙️ 设置", m); a_settings.triggered.connect(self.pet.open_settings); m.addAction(a_settings)
        m.addSeparator()

        # ---- 系统 ----
        a_update = QAction(f"🔄 检查更新（当前 v{VERSION}）", m)
        a_update.triggered.connect(
            lambda _checked=False: self._check_update(manual=True)
        )
        m.addAction(a_update)
        autostart_label = "↻ 登录时启动" if IS_MACOS else "↻ 开机自启"
        a_autostart = QAction(autostart_label, m); a_autostart.setCheckable(True)
        a_autostart.setChecked(self.state.get("autostart", False))
        a_autostart.triggered.connect(lambda: self.toggle_autostart(a_autostart))
        m.addAction(a_autostart)
        # Debug shortcuts are for local source development only. PyInstaller
        # sets sys.frozen in release builds, so users never see this menu.
        if not IS_FROZEN:
            self._add_debug_menu(m)
        m.addSeparator()
        a_quit = QAction("✕ 退出", m); a_quit.triggered.connect(self.quit); m.addAction(a_quit)

    def build_menu(self):
        self.menu.clear()
        self._populate_menu(self.menu, include_status=False)

    def refresh_menu(self):
        self.build_menu()

    def _add_debug_menu(self, parent_menu):
        """Add a '调试' submenu with stat-tweaking shortcuts."""
        dm = QMenu("🔧 调试", parent_menu)
        a_tuner = QAction("🧪 参数调试器", dm)
        tuner_callback = getattr(self.pet, "open_parameter_tuner", lambda: None)
        a_tuner.triggered.connect(tuner_callback)
        dm.addAction(a_tuner)
        dm.addSeparator()
        a_low = QAction("降低所有属性 (测试气泡)", dm)
        a_low.triggered.connect(lambda: self._debug_set_stats(20, 20, 20))
        dm.addAction(a_low)
        a_hungry = QAction("只降饱腹", dm)
        a_hungry.triggered.connect(lambda: self._debug_set_stats(hunger=15))
        dm.addAction(a_hungry)
        a_bored = QAction("只降心情", dm)
        a_bored.triggered.connect(lambda: self._debug_set_stats(mood=15))
        dm.addAction(a_bored)
        a_tired = QAction("只降精力", dm)
        a_tired.triggered.connect(lambda: self._debug_set_stats(energy=15))
        dm.addAction(a_tired)
        dm.addSeparator()
        a_full = QAction("回满所有属性", dm)
        a_full.triggered.connect(lambda: self._debug_set_stats(100, 100, 100))
        dm.addAction(a_full)
        a_force = QAction("强制弹出交互气泡", dm)
        a_force.triggered.connect(self._debug_force_bubble)
        dm.addAction(a_force)
        parent_menu.addMenu(dm)

    def _debug_set_stats(self, hunger=None, mood=None, energy=None):
        if hunger is not None: self.state["hunger"] = hunger
        if mood is not None:   self.state["mood"] = mood
        if energy is not None: self.state["energy"] = energy
        save_state(self.state)
        self.pet.refresh_pose_from_state()
        self.pet.say("汪？", 1200)

    def _debug_force_bubble(self):
        # bypass throttle and stat checks
        self.pet._last_interactive_t = 0
        # pick lowest stat
        s = self.pet.state
        candidates = []
        if s["hunger"] < 100:
            candidates.append((
                "feed", "喂喂我", "#f39a68"
            ))
        if s["mood"] < 100:
            candidates.append((
                "play", "陪我玩", "#75cda8"
            ))
        if not candidates: return
        # choose the lowest
        order = {"feed": s["hunger"], "play": s["mood"]}
        candidates.sort(key=lambda c: order[c[0]])
        action, label, color = candidates[0]
        if self.pet._interactive_bubble is not None:
            try: self.pet._interactive_bubble.close()
            except Exception: pass
            self.pet._interactive_bubble = None
        self.pet._interactive_bubble = InteractiveBubble(self.pet, label, action, color, "")
        self.pet._last_interactive_t = time.time()

    def _fresh_menu(self):
        """Build a fresh standalone menu for right-click on pet."""
        m = QMenu()
        m.setStyleSheet(WARM_MENU_STYLE)
        self._populate_menu(m, include_status=True)
        return m

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_visible()

    def toggle_visible(self):
        scene = self.pet.play_scene
        if scene is not None:
            try:
                if scene.isVisible():
                    self.pet.cancel_play_scene(show_pet=False)
                    return
            except RuntimeError:
                self.pet.play_scene = None
        home = getattr(self.pet, "home_scene_window", None)
        if home is not None:
            try:
                if home.isVisible():
                    home.hide_scene()
                    return
            except RuntimeError:
                self.pet.home_scene_window = None
        if self.pet.isVisible():
            self.pet.set_user_visible(False)
        else:
            self.pet.set_user_visible(True)

    def open_data_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(DATA_DIR))

    def toggle_autostart(self, action):
        on = action.isChecked()
        self.state["autostart"] = on
        save_state(self.state)
        try:
            self.set_autostart(on)
            enabled_text = "已设置登录时启动" if IS_MACOS else "已设置开机自启"
            disabled_text = "已取消登录时启动" if IS_MACOS else "已取消开机自启"
            self.pet.say(enabled_text if on else disabled_text, 1500)
        except Exception as e:
            self.pet.say("设置失败：" + str(e)[:20], 2000)

    def set_autostart(self, on):
        if IS_WINDOWS:
            self._set_windows_autostart(on)
        elif IS_MACOS:
            self._set_macos_autostart(on)
        else:
            raise RuntimeError("当前系统暂不支持自动启动")

    def _set_windows_autostart(self, on):
        import winreg
        key = winreg.HKEY_CURRENT_USER
        sub = r"Software\Microsoft\Windows\CurrentVersion\Run"
        name = "DesktopPetSheen"
        with winreg.OpenKey(key, sub, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                exe = sys.executable
                script = os.path.abspath(__file__)
                if exe.lower().endswith("pythonw.exe") or exe.lower().endswith("python.exe"):
                    val = f'"{exe}" "{script}"'
                else:
                    val = f'"{exe}"'
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
            else:
                try: winreg.DeleteValue(k, name)
                except FileNotFoundError: pass

    def _set_macos_autostart(self, on):
        import plistlib
        launch_agents = os.path.expanduser("~/Library/LaunchAgents")
        plist_path = os.path.join(launch_agents, MAC_BUNDLE_ID + ".plist")
        if not on:
            try:
                os.remove(plist_path)
            except FileNotFoundError:
                pass
            return

        os.makedirs(launch_agents, exist_ok=True)
        if getattr(sys, "frozen", False):
            program_args = [sys.executable]
        else:
            program_args = [sys.executable, os.path.abspath(__file__)]
        payload = {
            "Label": MAC_BUNDLE_ID,
            "ProgramArguments": program_args,
            "RunAtLoad": True,
            "ProcessType": "Interactive",
        }
        with open(plist_path, "wb") as f:
            plistlib.dump(payload, f)

    def quit(self):
        self.pet.cancel_play_scene(show_pet=False)
        if self.pet.chat_win is not None:
            self.pet.chat_win.close()
        self.state["x"] = self.pet.x()
        self.state["y"] = self.pet.y()
        save_state(self.state)
        self.tray.hide()
        instance_server = getattr(self, "_instance_server", None)
        if instance_server is not None:
            instance_server.close()
        self.app.quit()

    def run(self):
        return self.app.exec_()


def main():
    configure_display_scaling()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    instance_server = SingleInstanceServer()
    if not instance_server.start():
        return 0
    if IS_WINDOWS and IS_FROZEN:
        repair_result = repair_legacy_windows_install(sys.executable)
        if repair_result.get("action") == "restart":
            instance_server.close()
            return 0
        cleanup_stale_windows_updates(sys.executable)
    tray_app = TrayApp(app)
    tray_app._instance_server = instance_server
    instance_server.activation_requested.connect(
        tray_app.activate_existing_instance
    )
    return tray_app.run()


if __name__ == "__main__":
    sys.exit(main())

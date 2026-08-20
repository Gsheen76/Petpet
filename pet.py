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
    QAbstractButton, QDialog, QSizePolicy
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

# AI engine (same folder)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buddy_ai as ai
import progression
import decoration_renderer
import minigames
from progression_ui import AchievementsWindow, RecordsWindow, ShopWindow
from minigames import MiniGameHubWindow

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


FIXED_FONT_SCALE = 2.0
SETTINGS_FONT_SCALE = 1.08
DEFAULT_PET_SIZE = (190, 220, 160)
MACOS_PET_SIZE = (150, 180, 132)


def font_px(size):
    """Scale typography used by the pet's compact on-screen surfaces."""
    return max(1, int(round(float(size) * FIXED_FONT_SCALE)))


def independent_font_px(size):
    """Keep full-window and system-menu typography at its authored size."""
    return max(1, int(round(float(size))))


def settings_font_px(size):
    """Map the settings value 20 to the former value-12 visual size."""
    return max(1, int(round(float(size) * SETTINGS_FONT_SCALE)))


def tutorial_font_px(size):
    """Keep tutorial typography independent from the compact pet scale."""
    return independent_font_px(size)


def pixel_font(size, weight=QFont.Normal, family="Microsoft YaHei"):
    """Create a font whose rendered size is independent of monitor DPI."""
    font = QFont(family)
    font.setPixelSize(font_px(size))
    font.setWeight(weight)
    return font


# ---------- paths ----------
RES_DIR = RESOURCE_DIR
SVG_PATH = os.path.join(RES_DIR, "pet.svg")
ICON_PATH = os.path.join(ICONS_DIR, "icon-64.png")
SAVE_PATH = os.path.join(DATA_DIR, "pet_state.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "pet_settings.json")
DEBUG_PARAMETERS_PATH = os.path.join(DATA_DIR, "debug_parameters.json")
POSE_NAMES = ["idle", "happy", "sad", "eat", "sleep", "drag", "close"]
POSE = {name: i for i, name in enumerate(POSE_NAMES)}
CELL = 200  # each pose is 200x200; spritesheet is 1200x200

DEFAULT_ANIMATIONS = {
    "idle":  {"fps": 5,  "loop": True,  "fallback": "idle"},
    "walk":  {"fps": 6,  "loop": True,  "fallback": "idle",
              "scale": 1.56, "anchor_bottom": True},
    "eat":   {"fps": 20, "loop": True,  "fallback": "eat",
              "scale": 1.2, "anchor_bottom": True,
              "saturation": 0.9, "brightness": 0.97},
    "play":  {"fps": 24, "loop": False, "fallback": "happy",
              "scale": 1.3, "anchor_bottom": True},
    "happy": {"fps": 8,  "loop": True,  "fallback": "happy"},
    "pet":   {"fps": 20, "loop": False, "fallback": "happy",
              "scale": 1.2, "anchor_bottom": True,
              "saturation": 0.9, "brightness": 0.97},
    "dig_reward": {"fps": 20, "loop": False, "fallback": "happy",
                   "scale": 1.2, "anchor_bottom": True},
    "sleep": {"fps": 2.4, "loop": True,  "fallback": "sleep",
              "scale": 0.8, "anchor_bottom": True},
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
    "animation_idle_fps": 5.0,
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


# ---------- settings (user-tunable) ----------
DEFAULT_SETTINGS = {
    "chat_width": 640,
    "chat_height": 820,
    "chat_font_size": 20,
    "ui_font_size": 24,        # settings panel font size
    "always_on_top": True,     # pet window stays on top of other windows
    "auto_check_updates": True, # check GitHub Releases shortly after launch
    # health reminders (minutes; 0 = off)
    "remind_drink_min": 60,    # remind to drink water every N min
    "remind_rest_min": 90,     # remind to rest eyes every N min
    "remind_stand_min": 45,    # remind to stand up every N min
    "sound_enabled": True,     # sound effects on/off
    # stat decay per tick (tick = 2s). Lower = slower.
    "decay_hunger": 0.14,     # was 0.7 -> /5
    "decay_energy": 0.10,     # was 0.5 -> /5
    "decay_mood":   0.08,     # was 0.4 -> /5
    "decay_hunger_sleeping": 0.08,  # was 0.4 -> /5
    "decay_energy_sleeping_gain": 4, # energy gain while sleeping (per tick)
    # how often pet emits spontaneous speech bubbles (0..1 chance per decay tick).
    # Lower = quieter. Reduced ~3x from original 0.4.
    "needy_speak_chance": 0.13,
    # Small global boost for spontaneous chatter while preserving user settings.
    "chatter_frequency_boost": 1.2,
    # autonomy "ask" behavior weight (lower = less random barks)
    "ask_weight_normal": 0.5,    # was 0.3
    "ask_weight_needy":  0.5,    # was 1.5 (also lowered so total chatter drops ~3x)
    # AI nudge idle threshold (seconds) and minimum gap between nudges
    "nudge_idle_min": 1800,
    "nudge_gap_min":  10800,  # 3h
}

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

def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        s = {**DEFAULT_SETTINGS, **loaded}
        # Removed in v1.2: bubble width now follows the selected chat size.
        s.pop("chat_bubble_max", None)
        # one-time migration: if user has old font values outside new range, reset them
        if not (20 <= s.get("ui_font_size", 24) <= 40):
            s["ui_font_size"] = DEFAULT_SETTINGS["ui_font_size"]
        if not (12 <= s.get("chat_font_size", 20) <= 32):
            s["chat_font_size"] = DEFAULT_SETTINGS["chat_font_size"]
        return s
    except Exception:
        return dict(DEFAULT_SETTINGS)

def save_settings(s):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


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
            return progression.ensure_progression(state)
    except Exception:
        return progression.ensure_progression(dict(DEFAULT_STATE))

def save_state(s):
    try:
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


class ChatWindow(QWidget):
    """A small chat panel that floats beside the pet.
    Sheen replies stream in token-by-token via the bridge."""
    def __init__(self, pet_window):
        super().__init__()
        self.pet = pet_window
        self.s = pet_window.settings  # live settings reference
        self.mem = ai.load_memory()
        self.busy = False
        self._pending_user = None
        self._streaming = ""

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool  # no taskbar button
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setObjectName("chat")
        self.setFixedSize(self.s["chat_width"], self.s["chat_height"])
        self._apply_style()

    def _pet_name(self):
        return self.pet.pet_name

    def _chat_font_px(self):
        return independent_font_px(self.s["chat_font_size"])

    def _apply_style(self):
        # The chat window has its own user-controlled font setting. Keep it
        # independent from the compact pet-surface enlargement.
        fs = self._chat_font_px()
        self.setStyleSheet(f"""
            QWidget#chat {{
                background:#faf7f3;
                border:1px solid #e6d8cf;
                border-radius:18px;
            }}
            QScrollArea#chatHistory {{
                background:#fffdfa;
                border:1px solid #eee4dd;
                border-radius:12px;
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
                border-radius:13px;
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
                border-radius:13px;
                padding:10px 23px; font-weight:700; font-size:{fs}px;
            }}
            QPushButton#send:hover {{ background:#e19179; }}
            QPushButton#send:disabled {{ background:#ccb9ae; }}
            QPushButton#send:pressed {{ background:#c66e5b; }}
            QFrame#chatTools {{
                background:#f8f2ed;
                border:1px solid #eaded5;
                border-radius:12px;
            }}
            QPushButton#chatTool, QPushButton#clearTool {{
                background:#fffdfb; color:#76594b;
                border:1px solid #e5d5ca; border-radius:9px;
                padding:7px 12px;
                font-size:{max(fs-5,12)}px; font-weight:700;
            }}
            QPushButton#chatTool:hover {{
                background:#f8e9e1; color:#8f604e; border-color:#ddbaa8;
            }}
            QPushButton#chatTool:pressed {{
                background:#efd9cc;
            }}
            QPushButton#clearTool {{
                color:#9a7067; background:#fffaf8; border-color:#e6d3cc;
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
        self.title = QLabel(f"  🐶 {self._pet_name()}")
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

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 8, 0)
        title_row.setSpacing(0)
        title_row.addWidget(self.title, 1)
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

        self.api_key_btn = QPushButton()
        self.api_key_btn.setObjectName("chatTool")
        self.api_key_btn.setCursor(Qt.PointingHandCursor)
        self.api_key_btn.clicked.connect(self.configure_api_key)
        self.api_key_badge = QLabel(self.api_key_btn)
        self.api_key_badge.setObjectName("apiKeyBadge")
        self.api_key_badge.setFixedSize(12, 12)
        self.api_key_badge.setStyleSheet(
            "background:#e85d62;border:2px solid #fffdfb;border-radius:6px;"
        )
        self.api_key_badge.hide()

        self.model_btn = QPushButton()
        self.model_btn.setObjectName("chatTool")
        self.model_btn.setCursor(Qt.PointingHandCursor)
        self.model_btn.setToolTip("选择聊天使用的 AI 模型")
        self.model_btn.clicked.connect(self.show_model_menu)

        self.clear_btn = QPushButton("🧹 清除记忆")
        self.clear_btn.setObjectName("clearTool")
        self.clear_btn.setToolTip(
            f"让 {self._pet_name()} 忘记所有对话"
        )
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.confirm_clear_memory)
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
        tools_row.addWidget(self.api_key_btn)
        tools_row.addWidget(self.model_btn)
        tools_row.addStretch(1)
        tools_row.addWidget(self.clear_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(9)
        layout.addLayout(title_row)
        layout.addWidget(self.log, 1)
        layout.addLayout(row)
        layout.addWidget(self.tools_frame)
        self._ui_built = True

    def refresh_pet_name(self):
        """Refresh every visible name after onboarding or renaming."""
        name = self._pet_name()
        self.mem["pet_name"] = name
        self.title.setText(f"  🐶 {name}")
        self.clear_btn.setToolTip(f"让 {name} 忘记所有对话")
        if not self.busy:
            self.input.setPlaceholderText(f"跟 {name} 说点什么…")

    def _position_api_key_badge(self):
        badge = self.api_key_badge
        badge.move(
            max(0, self.api_key_btn.width() - badge.width() - 2),
            2,
        )

    def _set_api_key_badge(self, visible):
        self.api_key_badge.setVisible(bool(visible))
        if visible:
            QTimer.singleShot(0, self._position_api_key_badge)

    def _refresh_ai_tool_buttons(self):
        source = ai.get_api_key_source()
        self._set_api_key_badge(source == "none")
        if source == "environment":
            self._set_api_key_badge(False)
            self.api_key_btn.setText("🔑 API Key：环境变量")
            self.api_key_btn.setToolTip(
                "当前优先使用系统环境变量 ZHIPU_API_KEY；"
                "仍可在这里保存本机备用 Key"
            )
        elif source == "config":
            self._set_api_key_badge(False)
            self.api_key_btn.setText("🔑 API Key：已配置")
            self.api_key_btn.setToolTip("修改或移除本机保存的 API Key")
        else:
            self.api_key_btn.setText("🔑 添加 API Key")
            self.api_key_btn.setToolTip("添加智谱 API Key，开启 AI 聊天")
        self.model_btn.setText(f"🤖 {ai.get_model_name()} ▾")

        if source == "none":
            self.api_key_btn.setText("🔑 API Key：未配置")

    def configure_api_key(self):
        """Open a password-form editor without ever displaying the saved key."""
        dialog = QDialog(self)
        dialog.setObjectName("apiKeyDialog")
        dialog.setWindowTitle("配置 API Key")
        dialog.setModal(True)
        dialog.setFixedWidth(500)
        dialog.setStyleSheet("""
            QDialog#apiKeyDialog {
                background:#fff8ec;
                color:#65483b;
                font-family:'Microsoft YaHei',sans-serif;
                font-size:16px;
            }
            QLabel { color:#76584b; }
            QLabel#keyHint {
                color:#aa8170;
                font-size:13px;
            }
            QLineEdit {
                background:#fffdf8;
                border:1px solid #e9c8ae;
                border-radius:12px;
                padding:10px 12px;
                font-size:16px;
            }
            QLineEdit:focus { border:2px solid #f19a7e; }
            QPushButton {
                background:#fff4e9;
                color:#8a6251;
                border:1px solid #e9c8ae;
                border-radius:10px;
                padding:8px 15px;
                font-weight:700;
            }
            QPushButton:hover { background:#ffe4d7; }
            QPushButton#saveKey {
                color:white;
                background:#f28f76;
                border-color:#f28f76;
            }
            QPushButton#saveKey:hover { background:#e98169; }
            QPushButton#removeKey { color:#c56868; }
        """)

        title = QLabel("🔑 让小狗连接 AI")
        title.setStyleSheet(
            "font-size:20px;font-weight:800;color:#7a4d3b;"
        )
        source = ai.get_api_key_source()
        if source == "environment":
            status_text = (
                "已检测到系统环境变量，它会优先于这里保存的 Key。"
            )
        elif source == "config":
            status_text = "本机已经保存了 API Key，输入新 Key 即可替换。"
        else:
            status_text = "输入你的智谱 API Key，保存后下一次聊天立即生效。"
        status = QLabel(status_text)
        status.setWordWrap(True)

        key_edit = QLineEdit()
        key_edit.setEchoMode(QLineEdit.Password)
        key_edit.setPlaceholderText("请输入新的 API Key")
        key_edit.setClearButtonEnabled(True)

        privacy = QLabel(
            "Key 只保存在当前电脑的用户数据目录中，界面不会回显完整内容。"
        )
        privacy.setObjectName("keyHint")
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
            if key_edit.text().strip():
                dialog.accept()
                return
            status.setText("请先输入 API Key，再点击保存。")
            status.setStyleSheet("color:#cf5f5f;font-weight:700;")
            key_edit.setFocus()

        save_btn.clicked.connect(accept_key)
        key_edit.returnPressed.connect(accept_key)
        remove_btn = QPushButton("移除本机 Key")
        remove_btn.setObjectName("removeKey")
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setVisible(ai.load_config().get("api_key", "") != "")
        remove_btn.clicked.connect(lambda: dialog.done(2))

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

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(status)
        layout.addLayout(key_row)
        layout.addWidget(privacy)
        layout.addLayout(button_row)
        key_edit.setFocus()

        result = dialog.exec_()
        if result == QDialog.Accepted:
            new_key = key_edit.text().strip()
            if not new_key:
                QMessageBox.warning(
                    self, "API Key 未保存", "请输入 API Key 后再保存。"
                )
                return
            try:
                ai.set_api_key(new_key)
            except Exception as exc:
                QMessageBox.warning(
                    self, "保存失败",
                    f"无法保存 API Key：{exc}"
                )
                return
            self._refresh_ai_tool_buttons()
            note = "API Key 已保存，下一次聊天会立即使用。"
            if ai.get_api_key_source() == "environment":
                note = (
                    "本机备用 Key 已保存；当前仍优先使用系统环境变量。"
                )
            QMessageBox.information(self, "保存成功", note)
        elif result == 2:
            choice = QMessageBox.question(
                self, "移除 API Key",
                "确定移除保存在这台电脑上的 API Key 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if choice == QMessageBox.Yes:
                try:
                    ai.set_api_key("")
                except Exception as exc:
                    QMessageBox.warning(
                        self, "移除失败",
                        f"无法移除 API Key：{exc}"
                    )
                    return
                self._refresh_ai_tool_buttons()

    def show_model_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background:#fffaf3;
                color:#76584b;
                border:1px solid #e9c8ae;
                border-radius:10px;
                padding:6px;
                font-size:15px;
            }
            QMenu::item {
                border-radius:7px;
                padding:8px 24px 8px 12px;
            }
            QMenu::item:selected { background:#ffe2d4; }
            QMenu::indicator { width:14px; height:14px; }
        """)
        current = ai.get_model()
        for model_id, display_name in ai.SUPPORTED_MODELS.items():
            action = QAction(display_name, menu)
            action.setCheckable(True)
            action.setChecked(model_id == current)
            action.triggered.connect(
                lambda checked=False, selected=model_id:
                self.select_model(selected)
            )
            menu.addAction(action)
        menu.exec_(
            self.model_btn.mapToGlobal(
                QPoint(0, self.model_btn.height() + 4)
            )
        )

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
            (str(item.get("role", "assistant")), str(item.get("content", "")))
            for item in hs
        ]

    def _message_width(self):
        viewport_width = self.log.viewport().width()
        if viewport_width <= 1:
            viewport_width = self.width() - 32
        return max(240, int(viewport_width * 0.72))

    def _set_log_messages(self, messages):
        """Render actual rounded message widgets instead of rich-text blocks."""
        self._displayed_messages = list(messages)
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
            for role, text in self._displayed_messages:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 3, 0, 3)
                row_layout.setSpacing(0)

                bubble = QLabel(text if role == "user" else f"🐶 {text}")
                bubble.setObjectName("chatMessage")
                bubble.setWordWrap(True)
                bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
                bubble.setMaximumWidth(width)
                bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
                if role == "user":
                    bubble.setProperty("messageRole", "user")
                    bubble.setStyleSheet(
                        f"background:#fbf1ec;color:#704f43;font-size:{chat_font_size}px;"
                        "border:1px solid #ead9d1;border-radius:14px;"
                        "padding:9px 13px;"
                    )
                    row_layout.addStretch(1)
                    row_layout.addWidget(bubble)
                else:
                    bubble.setProperty("messageRole", "assistant")
                    bubble.setStyleSheet(
                        f"background:#f5e9df;color:#55433a;font-size:{chat_font_size}px;"
                        "border:1px solid #dfc9ba;border-radius:14px;"
                        "padding:9px 13px;"
                    )
                    row_layout.addWidget(bubble)
                    row_layout.addStretch(1)
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
        g = self.pet.geometry()
        # clamp window size to screen so it always fits
        screen = self.pet.current_screen_rect()
        max_w = screen.width() - 20
        max_h = screen.height() - 80
        w = min(self.s["chat_width"], max_w)
        h = min(self.s["chat_height"], max_h)
        if (w, h) != (self.width(), self.height()):
            self.setFixedSize(w, h)
        x = g.right() + 16
        y = g.top()
        if x + w > screen.right():
            x = g.left() - w - 16
        if y + h > screen.bottom() - 40:
            y = screen.bottom() - h - 40
        if x < screen.left(): x = screen.left()
        if y < screen.top(): y = screen.top()
        self.move(int(x), int(y))
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def send(self):
        if self.busy:
            return
        text = self.input.text().strip()
        if not text:
            return
        # A real sent message counts as a chat interaction. Merely opening
        # and closing the panel no longer grants affection.
        progression.record_action(self.pet.state, "chats_opened")
        save_state(self.pet.state)
        self.input.clear()
        # add user bubble immediately
        self._pending_user = text
        self._streaming = ""
        self._set_log_messages(
            self._history_messages()
            + [("user", text), ("assistant", "…")]
        )
        self.busy = True
        self.send_btn.setEnabled(False)
        self.input.setPlaceholderText(f"{self._pet_name()} 正在思考…")
        # run AI in background thread so GUI doesn't freeze
        t = threading.Thread(target=self._ai_thread, args=(text,), daemon=True)
        t.start()

    def _ai_thread(self, user_text):
        full = []
        err = None
        for kind, payload in ai.chat_stream(
                user_text, mem=self.mem,
                on_token=lambda chunk: bridge.token.emit(chunk),
                pet_name=self._pet_name()):
            if kind == "token":
                full.append(payload)
            elif kind == "done":
                full = [payload]
                break
            elif kind == "error":
                err = payload
                break
        if err:
            reply = ai.fallback_reply(
                user_text, err, pet_name=self._pet_name()
            )
            bridge.error.emit(reply)
        else:
            bridge.done.emit("".join(full))

    # slots (connected in main)
    def on_token(self, chunk):
        self._streaming += chunk
        # The history has not been saved yet, so render the pending pair.
        self._set_log_messages(
            self._history_messages()
            + [("user", self._pending_user),
               ("assistant", self._streaming + "▍")]
        )

    def on_done(self, full):
        # commit to memory
        ai.append_history(self.mem, "user", self._pending_user)
        ai.append_history(self.mem, "assistant", full)
        progression.record_action(self.pet.state, "ai_replies")
        save_state(self.pet.state)
        self.mem = ai.load_memory()
        self._pending_user = None
        self._streaming = ""
        self.busy = False
        self.send_btn.setEnabled(True)
        self.input.setPlaceholderText(
            f"跟 {self._pet_name()} 说点什么…"
        )
        self.input.setFocus()
        self._set_log_messages(self._history_messages())
        # also show a speech bubble on the pet
        short = full if len(full) < 40 else full[:38] + "…"
        self.pet.say(short, 3000)

    def on_error(self, reply):
        if self._pending_user:
            ai.append_history(self.mem, "user", self._pending_user)
            ai.append_history(self.mem, "assistant", reply)
            progression.record_action(self.pet.state, "ai_replies")
            save_state(self.pet.state)
        self.mem = ai.load_memory()
        self._pending_user = None
        self._streaming = ""
        self.busy = False
        self.send_btn.setEnabled(True)
        self.input.setPlaceholderText(
            f"跟 {self._pet_name()} 说点什么…"
        )
        self._set_log_messages(self._history_messages())
        self.pet.say(reply[:30], 2000)

    def confirm_clear_memory(self):
        """Ask for confirmation in the pet's voice; on yes, wipe memory."""
        if self.busy:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle(f"{self._pet_name()} · 清除记忆")
        msg.setIcon(QMessageBox.Question)
        msg.setText("主人，我会忘记你的，还是想要和我重新相识一次？")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.button(QMessageBox.Yes).setText("重新相识")
        msg.button(QMessageBox.No).setText("不要，继续陪着我")
        msg.setDefaultButton(QMessageBox.No)
        choice = msg.exec_()
        if choice == QMessageBox.Yes:
            # wipe memory
            try:
                if os.path.exists(ai.MEMORY_PATH):
                    os.remove(ai.MEMORY_PATH)
            except Exception:
                pass
            self.mem = ai._default_memory()
            ai.save_memory(self.mem)
            self._set_log_messages([
                ("assistant", "汪？你是…我们重新认识一下吧。")
            ])
            self.pet.say("汪？我们重新认识一下吧 🐶", 2500)


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


class ToggleSwitch(QAbstractButton):
    """Compact iOS-style on/off control used for boolean settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(60, 32)
        self.setFocusPolicy(Qt.StrongFocus)
        self.toggled.connect(lambda _checked: self.update())

    def sizeHint(self):
        return QSize(60, 32)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = QRectF(1, 2, self.width() - 2, self.height() - 4)
        track_color = QColor("#f08e72") if self.isChecked() else QColor("#d8c8bd")
        if not self.isEnabled():
            track_color.setAlpha(120)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 14, 14)
        knob_size = 24
        knob_x = self.width() - knob_size - 4 if self.isChecked() else 4
        painter.setBrush(QColor("#fffdf9"))
        painter.drawEllipse(QRectF(knob_x, 4, knob_size, knob_size))
        painter.end()


class StepperControl(QWidget):
    """Spin box with large, friendly minus/plus buttons."""

    def __init__(self, minimum, maximum, step, value, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.minus = QPushButton("−")
        self.plus = QPushButton("+")
        for button in (self.minus, self.plus):
            button.setObjectName("stepButton")
            button.setFixedSize(38, 38)
            button.setAutoRepeat(True)
            button.setAutoRepeatDelay(350)
            button.setAutoRepeatInterval(90)

        if isinstance(step, float):
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(2 if step < 0.1 else 1)
        else:
            self.spin = QSpinBox()
        self.spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.spin.setValue(value)
        self.spin.setFixedSize(104, 38)
        self.minus.clicked.connect(self.spin.stepDown)
        self.plus.clicked.connect(self.spin.stepUp)
        layout.addWidget(self.minus)
        layout.addWidget(self.spin)
        layout.addWidget(self.plus)

    def value(self):
        return self.spin.value()

    def setValue(self, value):
        self.spin.setValue(value)

    def setToolTip(self, text):
        super().setToolTip(text)
        self.minus.setToolTip(text)
        self.spin.setToolTip(text)
        self.plus.setToolTip(text)


class SettingsWindow(QWidget):
    """Tunable settings panel — chat window size, decay rates, chatter frequency, etc."""
    CHANGED = pyqtSignal()
    PREFERRED_WIDTH = 840
    PREFERRED_HEIGHT = 960
    COMPACT_MIN_WIDTH = 648
    COMPACT_MIN_HEIGHT = 708

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

    def _apply_font(self):
        fs = int(self.s.get("ui_font_size", 24))
        body_fs = settings_font_px(fs)
        title_fs = max(1, int(round(body_fs * 24 / 22)))
        subtitle_fs = max(1, int(round(body_fs * 14 / 22)))
        status_fs = max(1, int(round(body_fs * 13 / 22)))
        detail_fs = max(1, int(round(body_fs * 12 / 22)))
        step_fs = max(1, int(round(body_fs * 16 / 22)))
        self.setStyleSheet(f"""
            QWidget {{
                background:transparent;
                font-family:'Microsoft YaHei',sans-serif;
                font-size:{body_fs}px;
                color:#65483b;
            }}
            QWidget#settingsWindow {{
                background:#fff8ec;
                border:1px solid #e7c4ad;
                border-radius:18px;
            }}
            QScrollArea, QScrollArea > QWidget > QWidget {{
                background:transparent;
                border:0;
            }}
            QLabel {{ background:transparent; }}
            QLabel#settingsTitle {{
                font-size:{title_fs}px;
                font-weight:900;
                color:#754b3a;
            }}
            QLabel#settingsSubtitle {{
                color:#a27a68;
                font-size:{subtitle_fs}px;
            }}
            QLabel#settingsStatus {{
                color:#cf765e;
                font-size:{status_fs}px;
                font-weight:800;
                padding:0;
            }}
            QLabel#switchState {{
                color:#a36b58;
                font-size:{detail_fs}px;
                font-weight:700;
            }}
            QLabel#settingDescription {{
                color:#aa8270;
                font-size:{detail_fs}px;
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
                font-size:{step_fs}px;
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
                font-size:26px;
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

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 18, 26, 18)
        root.setSpacing(8)

        title_bar = QFrame()
        title_bar.setObjectName("settingsTitleBar")
        title_bar.setCursor(Qt.ArrowCursor)
        title_row = QHBoxLayout(title_bar)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        title = QLabel("🌼 温馨设置")
        title.setObjectName("settingsTitle")
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setToolTip("关闭温馨设置")
        close_button.setFixedSize(36, 36)
        close_button.clicked.connect(self.close)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(close_button)
        title_bar.mousePressEvent = self._title_bar_press
        title_bar.mouseMoveEvent = self._title_bar_move
        title_bar.mouseReleaseEvent = self._title_bar_release
        root.addWidget(title_bar)

        subtitle = QLabel("每一项都会保存并立即应用，按需要慢慢调就好。")
        subtitle.setObjectName("settingsSubtitle")
        root.addWidget(subtitle)

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
        content_layout.addWidget(self._group("🌿 健康提醒", [
            "remind_drink_min", "remind_rest_min", "remind_stand_min"
        ]))
        content_layout.addWidget(self._group("💬 日常互动", [
            "needy_speak_chance", "ask_weight_normal", "ask_weight_needy"
        ]))
        content_layout.addWidget(self._group("✨ AI 主动陪伴", [
            "nudge_idle_min", "nudge_gap_min"
        ]))
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
        group = QGroupBox("🍑 界面、声音与更新")
        layout = QVBoxLayout(group)
        layout.setSpacing(9)

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

    def apply(self):
        previous = dict(self.s)
        width, height = self.chat_size_combo.currentData()
        self.s["chat_width"] = int(width)
        self.s["chat_height"] = int(height)
        for key, control in self.inputs.items():
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


class TutorialWindow(QWidget):
    """Warm first-run guide whose final step names the pet."""

    PAGES = [
        (
            "🐶",
            "欢迎认识你的桌面伙伴",
            "从今天开始，这只小狗会住在你的桌面上。\n"
            "它会散步、撒娇、陪你聊天，也会记住你们一起度过的时间。",
        ),
        (
            "🖱️",
            "摸摸它，也可以带它走",
            "单击小狗可以抚摸它，双击会打开聊天窗口。\n"
            "按住左键拖动可以移动小狗，快速甩出去时它还会弹跳。\n"
            "睡着后，按住左键左右晃几下，就能温柔地把它摇醒。",
        ),
        (
            "🌷",
            "右键打开治愈互动",
            "点击右键会显示状态卡和互动气泡，可以聊天、喂食、玩耍或睡觉。\n"
            "点击“更多”可以进入设置、隐藏、教程等功能。",
        ),
        (
            "💬",
            "聊天、设置与托盘",
            "配置智谱 API Key 后，小狗就能在线陪你聊天；没有 Key 时也会使用本地话术。\n"
            "托盘图标可以显示或隐藏小狗、检查更新、设置开机自启和退出。",
        ),
        (
            "🏷️",
            "最后，给小狗取个名字吧",
            "这是它以后陪伴你时使用的名字，也会显示在聊天、状态档案和托盘中。\n"
            "名字可以使用中文、英文、数字、空格、“-”、“_”或“·”，最多 12 个字符。",
        ),
    ]

    def __init__(self, pet_window, on_complete):
        super().__init__()
        self.pet = pet_window
        self.on_complete = on_complete
        self.page_index = 0
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setObjectName("tutorialWindow")
        self.setWindowTitle("初次见面 · 新手教程")
        self.setFixedSize(800, 680)
        self.setStyleSheet("""
            QWidget#tutorialWindow {
                background:#fff8ec;
                border:1px solid #e7c4ad;
                border-radius:24px;
                color:#65483b;
                font-family:'Microsoft YaHei',sans-serif;
            }
            QLabel { background:transparent; }
            QLabel#tutorialIcon { font-size:%dpx; }
            QLabel#tutorialTitle {
                color:#754b3a;
                font-size:%dpx;
                font-weight:900;
            }
            QLabel#tutorialBody {
                color:#8e6959;
                font-size:%dpx;
                line-height:1.6;
            }
            QLabel#tutorialProgress {
                color:#e18d76;
                font-size:%dpx;
                letter-spacing:5px;
            }
            QLabel#nameHint {
                color:#b36f5b;
                font-size:%dpx;
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
                font-size:%dpx;
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
                font-size:%dpx;
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
        """ % (
            tutorial_font_px(88),
            tutorial_font_px(38),
            tutorial_font_px(28),
            tutorial_font_px(23),
            tutorial_font_px(20),
            tutorial_font_px(28),
            tutorial_font_px(22),
        ))

        root = QVBoxLayout(self)
        root.setContentsMargins(38, 28, 38, 30)
        root.setSpacing(14)

        top = QHBoxLayout()
        brand = QLabel("🌼 Pet陪它 · 新手教程")
        brand.setStyleSheet(
            "font-size:23px; font-weight:900; color:#93624f;"
        )
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
        self.body_label.setMinimumHeight(132)
        root.addWidget(self.body_label)

        self.name_card = QFrame()
        self.name_card.setObjectName("nameCard")
        name_layout = QVBoxLayout(self.name_card)
        name_layout.setContentsMargins(20, 15, 20, 15)
        name_layout.setSpacing(7)
        self.name_input = QLineEdit()
        self.name_input.setObjectName("petNameInput")
        self.name_input.setMaxLength(12)
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

        self._refresh_page()

    def start(self):
        """Restart the guide from page one and place it near the pet."""
        self.page_index = 0
        current_name = self.pet.pet_name
        if (not self.pet.state.get("tutorial_completed", False)
                and current_name == ai.DEFAULT_PET_NAME):
            self.name_input.clear()
        else:
            self.name_input.setText(current_name)
        self.name_hint.clear()
        self._refresh_page()
        screen = self.pet.current_screen_rect()
        x = screen.center().x() - self.width() // 2
        y = screen.center().y() - self.height() // 2
        self.move(int(x), int(y))
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
        self.back_button.setVisible(self.page_index > 0)
        self.next_button.setText(
            "完成相遇" if is_last else "下一步"
        )
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


class StatBubble(QWidget):
    """A warm, readable growth card shown above the right-click actions."""
    def __init__(self, pet):
        super().__init__()
        self.pet = pet
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFixedSize(620, 416)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)  # refresh stats 2x/sec
        self._place()
        self.show()
        self.raise_()

    def _tick(self):
        self.update()

    def _place(self):
        """Place above the action bubbles, centered on the pet."""
        g = self.pet.geometry()
        scr = self.pet.current_screen_rect()
        w, h = self.width(), self.height()
        x = g.center().x() - w // 2
        y = g.top() - h - 112
        x = max(scr.left(), min(x, scr.right() - w))
        y = max(scr.top(), min(y, scr.bottom() - h))
        self.move(int(x), int(y))

    @staticmethod
    def _fit_font(text, preferred_size, max_width, weight=QFont.Normal,
                  minimum_size=8):
        """Return the largest font that keeps dynamic text fully visible."""
        size = preferred_size
        while size > minimum_size:
            font = pixel_font(size, weight)
            if QFontMetrics(font).horizontalAdvance(str(text)) <= max_width:
                return font
            size -= 1
        return pixel_font(minimum_size, weight)

    @staticmethod
    def _draw_stat_icon(painter, rect, kind, color):
        """Draw font-independent hunger, mood, and energy pictograms."""
        painter.save()
        c = QColor(color)
        cx, cy = rect.center().x(), rect.center().y()
        if kind == "hunger":
            painter.setPen(QPen(c, 5, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(rect.left() + 10, cy),
                             QPointF(rect.right() - 10, cy))
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            for x in (rect.left() + 9, rect.right() - 9):
                painter.drawEllipse(QPointF(x, cy - 4), 3.5, 3.5)
                painter.drawEllipse(QPointF(x, cy + 4), 3.5, 3.5)
        elif kind == "mood":
            path = QPainterPath()
            path.moveTo(cx, rect.bottom() - 7)
            path.cubicTo(rect.left() + 5, cy + 2,
                         rect.left() + 5, rect.top() + 8,
                         cx, rect.top() + 12)
            path.cubicTo(rect.right() - 5, rect.top() + 8,
                         rect.right() - 5, cy + 2,
                         cx, rect.bottom() - 7)
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            painter.drawPath(path)
        else:
            points = QPolygonF([
                QPointF(cx + 2, rect.top() + 5),
                QPointF(cx - 8, cy + 2),
                QPointF(cx - 1, cy + 2),
                QPointF(cx - 5, rect.bottom() - 5),
                QPointF(cx + 10, cy - 4),
                QPointF(cx + 3, cy - 4),
            ])
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            painter.drawPolygon(points)
        painter.restore()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        st = self.pet.state
        W, H = self.width(), self.height()
        outer = QRectF(7, 5, W - 14, H - 13)

        # Soft cocoa shadow and warm milk-card background.
        p.setBrush(QColor(92, 60, 42, 42))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(outer.adjusted(3, 4, 3, 4), 24, 24)
        bg = QLinearGradient(outer.topLeft(), outer.bottomRight())
        bg.setColorAt(0.0, QColor(255, 252, 242, 252))
        bg.setColorAt(0.55, QColor(255, 244, 224, 252))
        bg.setColorAt(1.0, QColor(255, 237, 219, 252))
        p.setBrush(bg)
        p.setPen(QPen(QColor(235, 190, 154), 1.3))
        p.drawRoundedRect(outer, 24, 24)

        lvl = st.get("level", 1)
        xp = int(st.get("xp", 0))
        need = xp_to_next(lvl)
        days = max(1, int((time.time() - st.get("born", time.time())) / 86400))

        # ---- Header: title and companionship badge never share a text rect. ----
        title_text = f"🐾 {self.pet.pet_name} 的小屋"
        title_rect = QRectF(27, 15, 300, 40)
        p.setPen(QColor("#7b4d3a"))
        p.setFont(self._fit_font(
            title_text, 16, title_rect.width(), QFont.Bold, 7
        ))
        p.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter,
                   title_text)

        coin_text = f"Pet币 {st.get('pet_coins', 0)}"
        coin_rect = QRectF(W - 278, 18, 90, 33)
        p.setBrush(QColor(255, 241, 198, 240))
        p.setPen(QPen(QColor("#e8be68"), 1))
        p.drawRoundedRect(coin_rect, 16, 16)
        p.setPen(QColor("#a66a26"))
        p.setFont(self._fit_font(
            coin_text, 9, coin_rect.width() - 12, QFont.Bold, 6
        ))
        p.drawText(
            coin_rect.adjusted(6, 0, -6, 0),
            Qt.AlignCenter | Qt.TextSingleLine,
            coin_text,
        )

        days_text = f"♡ 陪伴第 {days} 天"
        days_rect = QRectF(W - 179, 18, 153, 33)
        p.setBrush(QColor(255, 224, 214, 235))
        p.setPen(QPen(QColor("#e9a494"), 1))
        p.drawRoundedRect(days_rect, 16, 16)
        p.setPen(QColor("#a95f55"))
        p.setFont(self._fit_font(days_text, 11, days_rect.width() - 18,
                                 QFont.Bold, 6))
        p.drawText(days_rect.adjusted(9, 0, -9, 0),
                   Qt.AlignCenter | Qt.TextSingleLine, days_text)

        # ---- Growth card: level badge, XP label/value, then progress bar. ----
        growth = QRectF(22, 64, W - 44, 80)
        p.setBrush(QColor(255, 255, 255, 178))
        p.setPen(QPen(QColor(242, 209, 174), 1))
        p.drawRoundedRect(growth, 18, 18)

        level_rect = QRectF(34, 77, 104, 54)
        level_grad = QLinearGradient(level_rect.topLeft(), level_rect.bottomRight())
        level_grad.setColorAt(0.0, QColor("#ffb989"))
        level_grad.setColorAt(1.0, QColor("#ff8f70"))
        p.setBrush(level_grad)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(level_rect, 16, 16)
        level_text = f"LV.{lvl}"
        p.setPen(QColor(255, 255, 255))
        p.setFont(self._fit_font(level_text, 18, level_rect.width() - 16,
                                 QFont.Bold, 6))
        p.drawText(level_rect.adjusted(8, 0, -8, 0),
                   Qt.AlignCenter | Qt.TextSingleLine, level_text)

        xp_area_x = 158
        xp_area_w = W - xp_area_x - 34
        xp_rate = progression.passive_xp_per_minute(st)
        rate_text = f"经验  +{xp_rate:.1f} EXP/min"
        p.setPen(QColor("#8a6654"))
        p.setFont(self._fit_font(
            rate_text, 10, 202, QFont.Bold, 7
        ))
        p.drawText(
            QRectF(xp_area_x, 76, 202, 23),
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
            rate_text,
        )
        xp_text = f"{xp} / {need} EXP"
        xp_value_rect = QRectF(
            xp_area_x + 205, 76, xp_area_w - 205, 23
        )
        p.setFont(self._fit_font(xp_text, 10, xp_value_rect.width(),
                                 QFont.Bold, 6))
        p.setPen(QColor("#b47b31"))
        p.drawText(xp_value_rect, Qt.AlignRight | Qt.AlignVCenter |
                   Qt.TextSingleLine, xp_text)

        xp_rect = QRectF(xp_area_x, 111, xp_area_w, 14)
        p.setBrush(QColor(244, 226, 207))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(xp_rect, 6.5, 6.5)
        progress = max(0.0, min(1.0, xp / max(1, need)))
        xp_fill = QRectF(xp_rect.left(), xp_rect.top(),
                         xp_rect.width() * progress, xp_rect.height())
        xp_grad = QLinearGradient(xp_rect.topLeft(), xp_rect.topRight())
        xp_grad.setColorAt(0.0, QColor("#ffc55c"))
        xp_grad.setColorAt(1.0, QColor("#ffdf85"))
        p.setBrush(xp_grad)
        p.drawRoundedRect(xp_fill, 7, 7)

        # ---- Affection: its level alone controls passive EXP per second. ----
        affection_level = int(st.get("affection_level", 1))
        affection_points = int(st.get("affection_points", 0))
        affection_need = progression.affection_to_next(affection_level)
        affection_card = QRectF(22, 154, W - 44, 70)
        affection_bg = QLinearGradient(
            affection_card.topLeft(), affection_card.topRight()
        )
        affection_bg.setColorAt(0.0, QColor(255, 232, 229, 210))
        affection_bg.setColorAt(1.0, QColor(255, 246, 225, 210))
        p.setBrush(affection_bg)
        p.setPen(QPen(QColor("#efb5a7"), 1))
        p.drawRoundedRect(affection_card, 17, 17)

        heart_rect = QRectF(35, 166, 45, 45)
        p.setBrush(QColor(255, 255, 255, 210))
        p.setPen(Qt.NoPen)
        p.drawEllipse(heart_rect)
        p.setPen(QColor("#ef877c"))
        p.setFont(pixel_font(20, QFont.Bold))
        p.drawText(heart_rect, Qt.AlignCenter, "♡")

        affection_title = f"好感 Lv.{affection_level}"
        p.setPen(QColor("#82584f"))
        p.setFont(self._fit_font(
            affection_title, 11, 122, QFont.Bold, 8
        ))
        p.drawText(
            QRectF(91, 159, 122, 29),
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
            affection_title,
        )
        affection_value = f"{affection_points} / {affection_need}"
        p.setPen(QColor("#d37469"))
        p.setFont(self._fit_font(
            affection_value, 10, 94, QFont.Bold, 7
        ))
        p.drawText(
            QRectF(210, 159, 94, 29),
            Qt.AlignRight | Qt.AlignVCenter | Qt.TextSingleLine,
            affection_value,
        )

        affection_bar = QRectF(91, 196, W - 126, 10)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(246, 220, 210))
        p.drawRoundedRect(affection_bar, 5, 5)
        affection_progress = max(
            0.0,
            min(1.0, affection_points / max(1, affection_need)),
        )
        affection_fill = QRectF(
            affection_bar.left(),
            affection_bar.top(),
            affection_bar.width() * affection_progress,
            affection_bar.height(),
        )
        affection_grad = QLinearGradient(
            affection_bar.topLeft(), affection_bar.topRight()
        )
        affection_grad.setColorAt(0.0, QColor("#f18d88"))
        affection_grad.setColorAt(1.0, QColor("#ffc28f"))
        p.setBrush(affection_grad)
        p.drawRoundedRect(affection_fill, 5, 5)

        # ---- Three stat cards with dedicated name/value/status regions. ----
        stats = [
            ("hunger", "饱腹", st.get("hunger", 0), "#f49a62",
             ("肚肚空空", "刚刚好", "肚肚饱饱")),
            ("mood", "心情", st.get("mood", 0), "#ef8fa2",
             ("想要抱抱", "心情不错", "开心摇尾巴")),
            ("energy", "精力", st.get("energy", 0), "#9b8ade",
             ("需要充电", "精神还好", "元气满满")),
        ]
        pad = 20
        gap = 12
        card_w = (W - pad * 2 - gap * 2) / 3
        card_y = 238
        card_h = 145
        for i, (icon_kind, name, val, color, moods) in enumerate(stats):
            val = max(0.0, min(100.0, float(val)))
            cx = pad + i * (card_w + gap)
            card = QRectF(cx, card_y, card_w, card_h)
            tint = QColor(color)
            tint.setAlpha(30)
            p.setBrush(tint)
            p.setPen(QPen(QColor(color).lighter(125), 1))
            p.drawRoundedRect(card, 16, 16)

            icon_rect = QRectF(cx + 13, card_y + 13, 42, 42)
            p.setBrush(QColor(255, 255, 255, 190))
            p.setPen(Qt.NoPen)
            p.drawEllipse(icon_rect)
            self._draw_stat_icon(
                p, icon_rect.adjusted(5, 5, -5, -5), icon_kind, color)

            name_rect = QRectF(cx + 64, card_y + 12, 52, 34)
            p.setPen(QColor("#76584b"))
            p.setFont(self._fit_font(
                name, 12, name_rect.width(), QFont.Bold, 10))
            p.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter |
                       Qt.TextSingleLine, name)

            value_text = f"{int(round(val))}%"
            value_rect = QRectF(cx + 118, card_y + 11, card_w - 130, 35)
            p.setPen(QColor(color))
            p.setFont(self._fit_font(value_text, 14, value_rect.width(),
                                     QFont.Bold, 8))
            p.drawText(value_rect, Qt.AlignRight | Qt.AlignVCenter |
                       Qt.TextSingleLine, value_text)

            br = QRectF(cx + 15, card_y + 75, card_w - 30, 11)
            p.setBrush(QColor(255, 255, 255, 190))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(br, 5, 5)
            fill = QRectF(br.left(), br.top(), br.width() * val / 100, br.height())
            p.setBrush(QColor(color))
            p.drawRoundedRect(fill, 5, 5)

            mood_text = moods[0] if val < 35 else (moods[1] if val < 70 else moods[2])
            mood_rect = QRectF(cx + 12, card_y + 105, card_w - 24, 27)
            p.setPen(QColor("#8a6f62"))
            p.setFont(self._fit_font(mood_text, 9, mood_rect.width(),
                                     QFont.Normal, 8))
            p.drawText(mood_rect, Qt.AlignCenter | Qt.TextSingleLine, mood_text)


class BubbleMenu(QWidget):
    """Soft candy-style action buttons with a warm growth card."""
    PRIMARY_ACTIONS = [
        ("💬", "聊天", "chat", "#ef8fa2"),
        ("🍖", "喂食", "feed", "#f49a62"),
        ("🎾", "玩耍", "play", "#72bf9b"),
        ("💤", "睡觉", "sleep", "#9b8ade"),
        ("⋯", "更多", "more", "#e7ae64"),
    ]
    MORE_ACTIONS = [
        ("📒", "记录", "records", "#df9f6f"),
        ("🏅", "成就", "achievements", "#efa47d"),
        ("🛍", "商店", "shop", "#e0a85f"),
        ("🎮", "小游戏", "minigames", "#72b6b0"),
        ("⚙️", "设置", "settings", "#e7ae64"),
        ("👁", "隐藏", "hide", "#79a9d8"),
        ("📖", "教程", "tutorial", "#d392bd"),
        ("↩", "返回", "back", "#79bd9a"),
        ("✕", "退出", "quit", "#df8f91"),
    ]

    def __init__(self, pet, page="primary"):
        super().__init__()
        self.pet = pet
        self.page = page if page in ("primary", "more") else "primary"
        self.actions = list(
            self.PRIMARY_ACTIONS
            if self.page == "primary"
            else self.MORE_ACTIONS
        )
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Popup
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Larger hit targets with room for both icon and label.
        self.W = 590 if self.page == "primary" else 500
        self.H = 112 if self.page == "primary" else 292
        self.resize(self.W, self.H)
        self._bubble_rects = []
        self._hover = -1
        self._press = -1
        self._closing = False
        self._hover_scales = [0.0] * len(self.actions)
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._tick)
        self._anim.start(16)
        self._app = QApplication.instance()
        if self._app is not None:
            self._app.applicationStateChanged.connect(
                self._on_application_state_changed
            )
            self._app.installEventFilter(self)

        # The growth card belongs only to the primary interaction canvas.
        # Opening "更多" replaces the whole first canvas.
        self.stat_bubble = (
            StatBubble(pet) if self.page == "primary" else None
        )

        self._place()
        self.show()
        self.raise_()
        self.activateWindow()
        self.setMouseTracking(True)

    def _tick(self):
        # ease hover scales
        target = [1.0 if i == self._hover else 0.0 for i in range(len(self.actions))]
        changed = False
        for i in range(len(self.actions)):
            diff = target[i] - self._hover_scales[i]
            if abs(diff) > 0.01:
                self._hover_scales[i] += diff * 0.25
                changed = True
        if changed:
            self.update()

    def follow_pet(self):
        """Reposition both the bubble menu and stat bubble to follow the pet."""
        self._place()
        if self.stat_bubble is not None:
            try:
                self.stat_bubble._place()
            except Exception:
                pass

    def _place(self):
        """Position the row of bubbles just above the pet's head."""
        g = self.pet.geometry()
        x = g.center().x() - self.W // 2
        y = g.top() - self.H + 19
        scr = self.pet.current_screen_rect()
        x = max(scr.left(), min(x, scr.right() - self.W))
        y = max(scr.top(), min(y, scr.bottom() - self.H))
        self.move(int(x), int(y))

    @staticmethod
    def needs_api_key_configuration():
        return ai.get_api_key_source() == "none"

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._bubble_rects = []
        n = len(self.actions)
        button_w = 102
        button_h = 78
        gap = 10
        columns = n if self.page == "primary" else 3
        rows = int(math.ceil(n / columns))
        total_w = columns * button_w + (columns - 1) * gap
        total_h = rows * button_h + (rows - 1) * gap
        start_x = (self.W - total_w) / 2
        start_y = (self.H - total_h) / 2
        has_claimable = progression.has_claimable_achievements(
            self.pet.state
        )
        needs_api_key = self.needs_api_key_configuration()
        for i, (emoji, label, action, color) in enumerate(self.actions):
            row = i // columns
            column = i % columns
            bx = start_x + column * (button_w + gap)
            by = start_y + row * (button_h + gap)
            scale = 1.0 + self._hover_scales[i] * 0.07
            if self._press == i:
                scale *= 0.96
            bw = button_w * scale
            bh = button_h * scale
            rect = QRectF(
                bx + (button_w - bw) / 2,
                by + (button_h - bh) / 2,
                bw, bh,
            )
            self._bubble_rects.append((i, rect, action, color, emoji))

            # Warm soft shadow.
            p.setBrush(QColor(92, 60, 42, 48))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect.adjusted(2, 4, 2, 4), 23, 23)

            # Pastel candy surface.
            c = QColor(color)
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, c.lighter(145))
            grad.setColorAt(1.0, c.lighter(108))
            p.setBrush(grad)
            p.setPen(QPen(c.darker(120), 1.2))
            p.drawRoundedRect(rect, 23, 23)

            # Top gloss makes each button feel like a soft candy.
            gloss = QRectF(rect.x() + 8, rect.y() + 5,
                           rect.width() - 16, rect.height() * 0.38)
            gloss_grad = QLinearGradient(gloss.topLeft(), gloss.bottomLeft())
            gloss_grad.setColorAt(0.0, QColor(255, 255, 255, 105))
            gloss_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setBrush(gloss_grad)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(gloss, 16, 16)

            p.setPen(QColor(255, 255, 255))
            p.setFont(pixel_font(17, QFont.Bold))
            p.drawText(QRectF(rect.x(), rect.y() + 7, rect.width(), 34),
                       Qt.AlignCenter, emoji)
            p.setFont(pixel_font(10, QFont.Bold))
            p.drawText(QRectF(rect.x() + 5, rect.y() + 43,
                              rect.width() - 10, 25),
                       Qt.AlignCenter | Qt.TextSingleLine, label)

            # Claimable achievements place a clear red reminder on both the
            # primary "更多" entry and the secondary "成就" entry.
            if (
                (action in ("more", "achievements") and has_claimable)
                or (action == "settings" and needs_api_key)
            ):
                dot_center = QPointF(rect.right() - 10, rect.top() + 10)
                p.setBrush(QColor(255, 255, 255))
                p.setPen(Qt.NoPen)
                p.drawEllipse(dot_center, 8, 8)
                p.setBrush(QColor("#ee5e62"))
                p.drawEllipse(dot_center, 5.5, 5.5)

    def mouseMoveEvent(self, e):
        pos = e.pos()
        new_hover = -1
        for i, rect, _, _, _ in self._bubble_rects:
            if rect.contains(QPointF(pos)):
                new_hover = i; break
        if new_hover != self._hover:
            self._hover = new_hover

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            self._close()
            return
        pos = e.pos()
        for i, rect, action, _, _ in self._bubble_rects:
            if rect.contains(QPointF(pos)):
                self._press = i
                self.update()
                return
        self._close()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            pos = e.pos()
            for i, rect, action, _, _ in self._bubble_rects:
                if rect.contains(QPointF(pos)) and self._press == i:
                    self._press = -1
                    self._run_action(action)
                    return
            self._press = -1
            if not any(rect.contains(QPointF(pos)) for _, rect, _, _, _ in self._bubble_rects):
                self._close()

    def _run_action(self, action):
        pet = self.pet
        if action in ("more", "back"):
            # Switching pages always replaces the complete current canvas.
            # Returning rebuilds the primary growth card and five bubbles.
            target_page = "more" if action == "more" else "primary"
            self._close()
            pet._bubble_menu = BubbleMenu(pet, page=target_page)
            return

        if action == "chat":
            pet.chat()
        elif action == "feed":
            pet.feed()
        elif action == "play":
            pet.play()
        elif action == "sleep":
            pet.toggle_sleep()
        elif action == "settings":
            pet.open_settings()
        elif action == "records":
            pet.open_records()
        elif action == "achievements":
            pet.open_achievements()
        elif action == "shop":
            pet.open_shop()
        elif action == "minigames":
            pet.open_minigames()
        elif action in ("hide", "tutorial", "quit"):
            self._close()
            callback = getattr(pet, "_app_action_cb", None)
            if callable(callback):
                callback(action)
            return
        self._close()

    def _close(self):
        if self._closing:
            return
        self._closing = True
        if self._app is not None:
            try:
                self._app.applicationStateChanged.disconnect(
                    self._on_application_state_changed
                )
            except (TypeError, RuntimeError):
                pass
            try:
                self._app.removeEventFilter(self)
            except (TypeError, RuntimeError):
                pass
        if self.stat_bubble is not None:
            try:
                self.stat_bubble.close()
            except Exception:
                pass
        try:
            self.releaseMouse()
        except Exception:
            pass
        self.close()
        if getattr(self.pet, "_bubble_menu", None) is self:
            self.pet._bubble_menu = None

    def _on_application_state_changed(self, state):
        if state == Qt.ApplicationInactive and self.isVisible():
            self._close()

    def eventFilter(self, watched, event):
        if (not self._closing and self.isVisible()
                and event.type() == QEvent.MouseButtonPress
                and hasattr(event, "globalPos")):
            point = event.globalPos()
            inside = self.frameGeometry().contains(point)
            if self.stat_bubble is not None:
                try:
                    inside = inside or (
                        self.stat_bubble.isVisible()
                        and self.stat_bubble.frameGeometry().contains(point)
                    )
                except RuntimeError:
                    pass
            if not inside:
                QTimer.singleShot(0, self._close)
        return False

    def event(self, event):
        if (
            event.type() == QEvent.UngrabMouse
            and self.isVisible()
            and not self._closing
        ):
            QTimer.singleShot(0, self._close)
        return super().event(event)

    def hideEvent(self, event):
        if not self._closing:
            QTimer.singleShot(0, self._close)
        super().hideEvent(event)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._close()


class BonusBubble(QWidget):
    """A floating '+25 饱腹' style bubble that drifts up and fades out.
    Shown after the user interacts with the pet via an InteractiveBubble."""
    def __init__(self, text, x, y, color="#ff8c42"):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.text = text
        self.color = QColor(color)
        self.life = 0
        self.setFont(pixel_font(14, QFont.Bold))
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(text) + 36
        h = fm.height() + 20
        self.resize(w, h)
        self.move(int(x - w/2), int(y - h))
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(33)
        self.show()

    def _tick(self):
        self.life += 1
        if self.life <= 36:
            self.move(self.x(), self.y() - 2)
        if self.life > 36:
            op = max(0, 1 - (self.life - 36) / 18)
            self.setWindowOpacity(op)
        if self.life > 54:
            self.close()
            return
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(4, 4, -4, -4)
        # soft shadow
        shadow = QRectF(r.x()+2, r.y()+3, r.width(), r.height())
        p.setBrush(QColor(0, 0, 0, 45))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(shadow, 14, 14)
        # main pill — white with subtle color tint
        bg = QColor(self.color); bg.setAlpha(35)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, QColor(255, 255, 255))
        grad.setColorAt(1.0, bg)
        p.setBrush(grad)
        p.setPen(QPen(self.color, 1.5))
        p.drawRoundedRect(r, 14, 14)
        # top gloss highlight
        gloss = QRectF(r.x()+3, r.y()+2, r.width()-6, r.height()/2.5)
        g2 = QLinearGradient(gloss.topLeft(), gloss.bottomLeft())
        g2.setColorAt(0.0, QColor(255, 255, 255, 120))
        g2.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(g2)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(gloss, 11, 11)
        # colored bold text
        p.setPen(self.color)
        p.setFont(self.font())
        p.drawText(r, Qt.AlignCenter, self.text)


class InteractiveBubble(QWidget):
    """A clickable bubble floating above the pet, e.g. '🦴 喂我'.
    Refined style: soft shadow, gradient, pulse animation, oval shape.
    Clicking triggers the associated action and shows a BonusBubble."""
    def __init__(self, pet, label, action_name, color, bonus_text):
        super().__init__()
        self.pet = pet
        self.action_name = action_name
        self.bonus_text = bonus_text
        self.color = color
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(pixel_font(12, QFont.Bold))
        fm = self.fontMetrics()
        w = max(148, fm.horizontalAdvance(label) + 64)
        self.resize(w + 16, 64)
        self.label = label
        self._pulse = 0.0
        self._hovered = False
        self._tail_on_left = True
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._tick)
        self._anim.start(40)
        self._place_above_pet()
        self.show()

    def _tick(self):
        self._pulse += 0.08
        self.update()

    def _place_above_pet(self):
        """Place bubble to the side of the pet that has more room.
        If pet is in left half of screen -> bubble goes right; else left."""
        g = self.pet.geometry()
        scr = self.pet.current_screen_rect()
        pet_cx = g.center().x()
        screen_cx = scr.center().x()
        toward_pet = 12
        if pet_cx < screen_cx:
            # Bubble is on the right, so shift it left toward the pet.
            x = g.right() + 8 - toward_pet
            self._tail_on_left = True
        else:
            # Bubble is on the left, so shift it right toward the pet.
            x = g.left() - self.width() - 8 + toward_pet
            self._tail_on_left = False
        y = g.center().y() - self.height() // 2 + 15
        # clamp to screen
        x = max(scr.left(), min(x, scr.right() - self.width()))
        y = max(scr.top(), min(y, scr.bottom() - self.height()))
        self.move(int(x), int(y))

    def mousePressEvent(self, e):
        if (e.button() == Qt.LeftButton and
                self._ellipse_rect().contains(QPointF(e.pos()))):
            self._trigger()

    def _ellipse_rect(self):
        return QRectF(
            8, 6,
            self.width() - 16,
            self.height() - 12,
        )

    def _trigger(self):
        """Execute the action and pop a BonusBubble with explicit deltas.
        Compute deltas from before/after state so feedback is always shown,
        even if the pet was sleeping (we wake it first)."""
        pet = self.pet
        progression.ensure_progression(pet.state)
        if self.action_name == "dig_reward":
            pet._interactive_bubble = None
            self.close()
            pet.claim_dig_reward()
            return
        before = dict(pet.state)
        before_xp_earned = pet.state["records"]["xp_earned"]
        before_affection_earned = pet.state["records"]["affection_earned"]
        before_affection_level = int(
            pet.state.get("affection_level", 1)
        )
        before_level = int(pet.state.get("level", 1))
        acted = True
        # wake the pet if sleeping, so feed/play actually take effect
        if pet.state.get("sleeping") and self.action_name in ("feed", "play"):
            pet.state["sleeping"] = False
            pet.state["sleep_mode"] = None
            pet._auto_sleep_phase = None
            pet._auto_sleep_target_x = None
            pet._auto_sleep_snooze_until = time.time() + 60.0
            pet.refresh_pose_from_state()
        if self.action_name == "feed":
            pet.feed(grant_xp=False)
        elif self.action_name == "play":
            play_cost = progression.upgrade_effects(
                pet.state
            )["play_energy_cost"]
            if pet.state["energy"] < 15 and play_cost > 0:
                pet.state["mood"] = min(100, pet.state["mood"] + 6)
                pet.say("没力气…摸摸我也行", 1500)
                acted = False
            else:
                pet.play(grant_xp=False)
        elif self.action_name == "sleep":
            pet.state["energy"] = min(100, pet.state["energy"] + 30)
            progression.grant_interaction_affection(
                pet.state, "rest_bubble"
            )
            pet.say("小憩一下 💤", 1800)
            pet.refresh_pose_from_state()
            save_state(pet.state)

        # compute deltas from before vs after state
        deltas = []
        labels = {"hunger":"饱腹", "mood":"心情", "energy":"精力"}
        for k, name in labels.items():
            d = pet.state.get(k, 0) - before.get(k, 0)
            if abs(d) >= 0.5:
                sign = "+" if d > 0 else ""
                deltas.append(f"{name}{sign}{int(round(d))}")

        xp_gain = max(
            0, pet.state["records"]["xp_earned"] - before_xp_earned
        )
        leveled_up = int(pet.state.get("level", 1)) > before_level

        parts = list(deltas)
        affection_gain = max(
            0,
            pet.state["records"]["affection_earned"]
            - before_affection_earned,
        )
        if affection_gain:
            parts.append(f"好感+{affection_gain}")
        if (
            int(pet.state.get("affection_level", 1))
            > before_affection_level
        ):
            parts.append(
                f"好感Lv.{pet.state.get('affection_level', 1)}"
            )
        if xp_gain:
            parts.append(f"EXP+{xp_gain}")
        if leveled_up:
            parts.append(f"LVUP→{pet.state.get('level',1)}")
        bonus_text = "  ".join(parts) if parts else "✨"

        # ALWAYS pop the floating BonusBubble (guaranteed visible)
        g = pet.geometry()
        color = "#ffcc00" if leveled_up else self.color
        try:
            bb = BonusBubble(bonus_text, g.center().x(), g.top() - 10, color)
            pet._last_bonus = bb  # keep ref so it isn't GC'd
        except Exception as e:
            print("BonusBubble fail:", e)

        if leveled_up:
            lvl = pet.state.get("level", 1)
            def _celebrate():
                gg = pet.geometry()
                try:
                    BonusBubble(f"🎉 Lv.{lvl}", gg.center().x(), gg.top() - 30, "#ffcc00")
                except Exception: pass
                pet.say(f"升级啦！Lv.{lvl} 🎉", 2500)
            QTimer.singleShot(700, _celebrate)

        # release the slot so a new interactive bubble can spawn later
        pet._interactive_bubble = None
        self.close()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scale = (
            1.0
            + math.sin(self._pulse) * 0.008
            + (0.022 if self._hovered else 0.0)
        )
        cx, cy = self.width() / 2, self.height() / 2
        p.translate(cx, cy)
        p.scale(scale, scale)
        p.translate(-cx, -cy)

        r = self._ellipse_rect()
        c = QColor(self.color)

        glow = QColor(c)
        glow.setAlpha(int(28 + math.sin(self._pulse) * 8))
        p.setBrush(glow)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), 25, 25)

        shadow = r.translated(2, 3)
        p.setBrush(QColor(91, 59, 44, 42))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(shadow, 24, 24)

        tail_y = r.center().y()
        if self._tail_on_left:
            tail = QPolygonF([
                QPointF(r.left() + 2, tail_y - 7),
                QPointF(2, tail_y),
                QPointF(r.left() + 2, tail_y + 7),
            ])
        else:
            tail = QPolygonF([
                QPointF(r.right() - 2, tail_y - 7),
                QPointF(self.width() - 2, tail_y),
                QPointF(r.right() - 2, tail_y + 7),
            ])
        p.setBrush(c.lighter(150))
        p.drawPolygon(tail)

        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, c.lighter(190))
        grad.setColorAt(0.48, c.lighter(165))
        grad.setColorAt(1.0, c.lighter(130))
        p.setBrush(grad)
        p.setPen(QPen(c.darker(112), 1.25))
        p.drawRoundedRect(r, 24, 24)

        gloss = QRectF(
            r.x() + 12, r.y() + 4,
            r.width() - 24, r.height() * 0.38,
        )
        gloss_grad = QLinearGradient(gloss.topLeft(), gloss.bottomLeft())
        gloss_grad.setColorAt(0.0, QColor(255, 255, 255, 125))
        gloss_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(gloss_grad)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(gloss, 16, 16)

        icon_center = QPointF(r.left() + 27, r.center().y())
        p.setBrush(QColor(255, 252, 246, 230))
        p.setPen(QPen(QColor(255, 255, 255, 190), 1))
        p.drawEllipse(icon_center, 17, 17)
        self._draw_action_icon(p, icon_center, c.darker(105))

        text_rect = QRectF(
            r.left() + 49, r.top(),
            r.width() - 57, r.height(),
        )
        p.setFont(self.font())
        p.setPen(QColor(92, 63, 52, 220))
        p.drawText(
            text_rect.translated(0, 1),
            Qt.AlignCenter | Qt.TextSingleLine,
            self.label,
        )
        p.setPen(QColor("#70483d"))
        p.drawText(
            text_rect,
            Qt.AlignCenter | Qt.TextSingleLine,
            self.label,
        )

    def _draw_action_icon(self, painter, center, color):
        painter.setPen(QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        if self.action_name == "feed":
            bone = QRectF(
                center.x() - 7, center.y() - 3,
                14, 6,
            )
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bone, 3, 3)
            for dx in (-7, 7):
                painter.drawEllipse(
                    QPointF(center.x() + dx, center.y() - 4), 3.5, 3.5
                )
                painter.drawEllipse(
                    QPointF(center.x() + dx, center.y() + 4), 3.5, 3.5
                )
        elif self.action_name == "play":
            ball = QRectF(
                center.x() - 9, center.y() - 9,
                18, 18,
            )
            painter.drawEllipse(ball)
            painter.drawArc(ball.adjusted(4, -1, 4, 1), 80 * 16, 95 * 16)
            painter.drawArc(ball.adjusted(-4, -1, -4, 1), 260 * 16, 95 * 16)
        elif self.action_name == "dig_reward":
            painter.setBrush(QColor("#f7bd35"))
            painter.setPen(QPen(color, 1.8))
            painter.drawEllipse(center, 9, 9)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, 5.5, 5.5)
            painter.drawLine(
                QPointF(center.x() - 3, center.y()),
                QPointF(center.x() + 3, center.y()),
            )
            painter.drawLine(
                QPointF(center.x(), center.y() - 3),
                QPointF(center.x(), center.y() + 3),
            )
        else:
            painter.setFont(pixel_font(14, QFont.Bold))
            painter.drawText(
                QRectF(
                    center.x() - 14, center.y() - 14,
                    28, 28,
                ),
                Qt.AlignCenter,
                "Z",
            )

    def enterEvent(self, e):
        self._hovered = True
        self.setCursor(Qt.PointingHandCursor)
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self.update()
        super().leaveEvent(e)


def _esc(text):
    """HTML-escape user content for safe bubble rendering."""
    return (text.replace("&","&amp;").replace("<","&lt;")
                .replace(">","&gt;").replace("\n","<br>"))


class SpeechBubble(QWidget):
    """A complete, queued speech bubble that wraps long messages."""
    def __init__(self, pet):
        super().__init__()
        self.pet = pet
        self.text = ""
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFont(pixel_font(11, QFont.Bold))
        self._pending_messages = []
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._show_next_or_hide)

    def show_text(self, text, ms):
        text = " ".join(str(text).replace("\r", "\n").splitlines()).strip()
        duration = max(1, int(ms))
        if not text:
            return
        # Never cut off a message that is already being read. Interactions,
        # autonomous reminders and level-up lines can arrive in the same event
        # loop, so subsequent lines wait their turn instead of resizing and
        # repainting the visible translucent window underneath the reader.
        if self.isVisible() and self._hide_timer.isActive():
            if text == self.text:
                self._hide_timer.start(
                    max(duration, self._hide_timer.remainingTime())
                )
            elif not self._pending_messages or (
                self._pending_messages[-1][0] != text
            ):
                self._pending_messages.append((text, duration))
            return
        self._display_text(text, duration)

    def _display_text(self, text, duration):
        self._hide_timer.stop()
        screen = self._available_screen_rect()
        fm = self.fontMetrics()
        padding_x = 18
        max_bubble_width = max(126, min(520, screen.width() - 8))
        max_text_width = max(80, max_bubble_width - padding_x * 2 - 10)
        natural_width = max(1, fm.horizontalAdvance(text) + 2)
        text_width = min(natural_width, max_text_width)
        text_bounds = fm.boundingRect(
            QRect(0, 0, int(text_width), 10000),
            Qt.AlignCenter | Qt.TextWordWrap,
            text,
        )
        self.text = text
        width = text_width + padding_x * 2 + 10
        height = max(fm.height(), text_bounds.height()) + 28
        # Hiding first forces Windows to allocate a correctly sized backing
        # surface for this translucent top-level window. Resizing it while
        # visible can leave the newly exposed right/bottom area unpainted.
        if self.isVisible():
            self.hide()
        self.setGeometry(self._bubble_geometry(width, height))
        self.show()
        self.raise_()
        self.repaint()
        self._hide_timer.start(duration)

    def _show_next_or_hide(self):
        if not self.pet.isVisible():
            self.clear_messages()
            return
        if self._pending_messages:
            text, duration = self._pending_messages.pop(0)
            # A brand-new top-level widget gets a fresh native translucent
            # surface. Reusing a previously shown window can leave its right
            # side permanently clipped on Windows after the width changes.
            replacement = SpeechBubble(self.pet)
            replacement._pending_messages = self._pending_messages
            self._pending_messages = []
            if getattr(self.pet, "_speech_bubble", None) is self:
                self.pet._speech_bubble = replacement
            self._hide_timer.stop()
            self.close()
            replacement._display_text(text, duration)
            return
        self.hide()

    def clear_messages(self):
        self._hide_timer.stop()
        self._pending_messages.clear()
        self.hide()

    def follow_pet(self):
        if not self.pet.isVisible():
            self.clear_messages()
            return
        rect = self._bubble_geometry(self.width(), self.height())
        self.move(rect.topLeft())

    def _bubble_geometry(self, width, height):
        """Return one complete on-screen geometry for an atomic update."""
        g = self.pet.geometry()
        screen = self._available_screen_rect()
        x = g.center().x() - width // 2
        # Keep the tail close to the dog's head even when long text wraps.
        y = g.top() + 3 - max(0, height - 56)
        x = max(screen.left() + 4, min(x, screen.right() - width - 4))
        y = max(screen.top() + 4, min(y, screen.bottom() - height - 4))
        return QRect(int(x), int(y), int(width), int(height))

    def _available_screen_rect(self):
        """Resolve the pet's screen without using its one-second movement cache."""
        screen_at = getattr(self.pet, "screen_at", None)
        if callable(screen_at):
            screen = screen_at(self.pet.geometry().center())
            if screen is not None:
                return screen.availableGeometry()
        return self.pet.current_screen_rect()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Explicitly clear the complete translucent surface.  This matters
        # when a visible bubble changes from short to long several times in
        # quick succession on Windows.
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        body = QRectF(4, 3, self.width() - 8, self.height() - 12)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 38))
        p.drawRoundedRect(body.adjusted(2, 3, 2, 3), 13, 13)

        grad = QLinearGradient(body.topLeft(), body.bottomRight())
        grad.setColorAt(0.0, QColor(255, 250, 232))
        grad.setColorAt(1.0, QColor(255, 236, 180))
        p.setBrush(grad)
        p.setPen(QPen(QColor(230, 180, 80), 1.2))
        p.drawRoundedRect(body, 13, 13)

        tail_x = body.center().x()
        p.setBrush(QColor(255, 241, 198))
        p.drawPolygon([
            QPointF(tail_x - 6, body.bottom() - 1),
            QPointF(tail_x + 6, body.bottom() - 1),
            QPointF(tail_x, body.bottom() + 8),
        ])

        p.setFont(self.font())
        p.setPen(QColor(80, 50, 20))
        p.drawText(body.adjusted(18, 0, -18, 0),
                   Qt.AlignCenter | Qt.TextWordWrap,
                   self.text)


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


class PetWindow(QWidget):
    flung = pyqtSignal()
    AUTO_SLEEP_ENERGY_THRESHOLD = 30.0
    AUTO_WAKE_ENERGY_THRESHOLD = 80.0
    AUTO_SLEEP_WALK_SPEED = 118.0
    AUTO_SLEEP_CORNER_MARGIN = 18
    AUTONOMY_IDLE_WEIGHT = 9.0
    AUTONOMY_WALK_WEIGHT = 1.0
    AUTONOMY_SIT_WEIGHT = 2.0

    @staticmethod
    def needs_api_key_configuration():
        return ai.get_api_key_source() == "none"

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.settings = load_settings()
        self.debug_parameters = self.debug_parameter_defaults()
        loaded_debug = load_debug_parameters()
        if IS_MACOS and not os.path.exists(DEBUG_PARAMETERS_PATH):
            loaded_debug.update(dict(zip(
                ("pet_width", "pet_height", "dog_height"), MACOS_PET_SIZE
            )))
        self.debug_parameters.update(loaded_debug)
        self.debug_physics = {
            "gravity": self.debug_parameters["gravity"],
            "wall_bounce": self.debug_parameters["wall_bounce"],
            "floor_bounce": self.debug_parameters["floor_bounce"],
            "ground_friction": self.debug_parameters["ground_friction"],
        }
        self.walk_speed_min = self.debug_parameters["walk_speed_min"]
        self.walk_speed_max = self.debug_parameters["walk_speed_max"]
        self.feed_animation_duration = self.debug_parameters["feed_animation_duration"]
        self.auto_sleep_energy_threshold = self.debug_parameters["auto_sleep_energy_threshold"]
        self.auto_wake_energy_threshold = self.debug_parameters["auto_wake_energy_threshold"]
        platform_size = MACOS_PET_SIZE if IS_MACOS else DEFAULT_PET_SIZE
        pet_w = int(self.debug_parameters["pet_width"] or platform_size[0])
        pet_h = int(self.debug_parameters["pet_height"])
        dog_h = int(self.debug_parameters["dog_height"])
        self.PET_W, self.PET_H = pet_w, pet_h
        self.DOG_H = dog_h  # actual dog drawing height; remaining space is for bubbles

        # transparent, frameless, always-on-top, no taskbar button, tool window
        on_top = self.settings.get("always_on_top", True)
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        if on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if IS_MACOS:
            self.setAttribute(
                Qt.WA_MacAlwaysShowToolWindow,
                bool(on_top),
            )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        # Load pose images: prefer PNG frames in poses/, fall back to SVG spritesheet
        self.pose_pixmaps = {}  # pose index -> QPixmap
        self.use_png = False
        for name, idx in POSE.items():
            p = os.path.join(POSES_DIR, f"{name}.png")
            if os.path.exists(p):
                pm = QPixmap(p)
                if not pm.isNull():
                    # keep original aspect; we'll scale at draw time
                    self.pose_pixmaps[idx] = pm
        if len(self.pose_pixmaps) == len(POSE):
            self.use_png = True
        else:
            # fall back to SVG spritesheet
            with open(SVG_PATH, "rb") as f:
                self.svg_bytes = QByteArray(f.read())
            self.renderer = QSvgRenderer(self.svg_bytes)
            if not self.renderer.isValid():
                raise RuntimeError("no pose PNGs and pet.svg invalid")

        self.decoration_pixmaps = (
            decoration_renderer.load_decoration_pixmaps()
        )

        # Optional multi-frame actions. Each action lives in
        # assets/animations/<action>/ and falls back to the static pose above.
        self.animation_specs = {}
        self.animation_frames = {}
        self._active_animation = None
        self._animation_started_at = time.monotonic()
        self._animation_override = None
        self._animation_override_token = 0
        self._load_animations()
        # Apply persisted source-tuning values after animation specs exist.
        for _key, _value in self.debug_parameters.items():
            self.set_debug_parameter(_key, _value)

        # current pose + blink timer
        self.pose = POSE["idle"]
        self.blink = False
        self.blink_t = 0.0

        # sound effects
        self.sounds = {}
        if HAS_SOUND:
            for name in ["bark", "eat", "sleep", "pet", "bounce"]:
                p = os.path.join(SOUNDS_DIR, f"{name}.wav")
                if os.path.exists(p):
                    se = QSoundEffect(self)
                    se.setSource(QUrl.fromLocalFile(p))
                    se.setVolume(0.5)
                    self.sounds[name] = se

        # physics
        self.vx = 0.0
        self.vy = 0.0
        self.target_vx = 0.0  # walking target speed
        self.on_ground = True  # touched bottom of screen
        self.facing = 1  # 1 right, -1 left

        # dragging
        self.dragging = False
        self.drag_offset = QPoint(0, 0)
        self.last_drag_pos = QPoint(0, 0)
        self.last_drag_t = 0.0
        self.drag_samples = []  # for velocity calc
        self._wake_shake = WakeShakeDetector()
        self._woke_from_shake = False

        # walk timer / autonomous behavior
        self.behavior = "idle"  # idle / walk / sit / nap / ask
        self.behavior_until = 0.0
        self.next_behavior_at = time.time() + random.uniform(7, 13)
        self._auto_sleep_phase = (
            "sleeping"
            if self.state.get("sleeping")
            and self.state.get("sleep_mode") == "auto"
            else None
        )
        self._auto_sleep_target_x = None
        self._auto_sleep_snooze_until = 0.0

        # AI: track idle time for proactive nudges
        self.last_user_t = time.time()
        self.last_nudge_check = time.time()
        self.chat_win = None  # lazy-created on first chat
        self.settings_win = None  # lazy-created on first settings open
        self.records_win = None
        self.achievements_win = None
        self.shop_win = None
        self.minigames_win = None
        self.parameter_tuner_win = None
        self.play_scene = None  # zoomed-out interactive fetch scene
        self._play_return_pos = None
        self._interactive_bubble = None  # current floating action bubble
        self._dig_reward_claiming = False
        self._bubble_menu = None         # radial bubble menu (right-click)
        self._last_interactive_t = 0.0   # throttle: don't spam
        self._ctx_menu_cb = None  # set by TrayApp to provide a right-click menu
        self._settings_applied_cb = None
        self._app_action_cb = None

        # Speech uses a detached top-level window so it can wrap outside the
        # pet widget without being clipped by the pet's own bounds.
        self._speech_bubble = None

        # resize to pet size; place at saved pos
        self.resize(int(self.PET_W), int(self.PET_H))
        self.place_initial()
        # safety: if saved position landed pet off-screen (e.g. monitor unplugged), recall
        if not self.is_visible_on_screen():
            self.recall()

        # timers
        self.tick = QTimer(self)
        self.tick.timeout.connect(self.on_tick)
        self.tick.start(33)  # ~30fps

        self.decay = QTimer(self)
        self.decay.timeout.connect(self.on_decay)
        self.decay.start(2000)

        self.autonomy = QTimer(self)
        self.autonomy.timeout.connect(self.on_autonomy)
        self.autonomy.start(1000)

        # Passive XP accrual is fractional and updates every second. Its rate
        # depends on affection, never on hunger/mood/energy.
        self.xp_timer = QTimer(self)
        self.xp_timer.timeout.connect(self.on_passive_xp)
        self.xp_timer.start(1000)

        # Treasure checks are deliberately sparse. A pending find survives a
        # restart and keeps returning until the player chooses to claim it.
        self._dig_timer = QTimer(self)
        self._dig_timer.timeout.connect(self.maybe_discover_dig_reward)
        self._dig_timer.start(60000)
        QTimer.singleShot(5000, self.maybe_discover_dig_reward)

        # health reminders
        self._last_drink_t = time.time()
        self._last_rest_t = time.time()
        self._last_stand_t = time.time()
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self.on_health_check)
        self._health_timer.start(30000)  # check every 30s

        # multi-sample drag velocity: track mouse move events
        # (handled in mouseMoveEvent)

    @property
    def pet_name(self):
        return ai.normalize_pet_name(self.state.get("pet_name"))

    def debug_parameter_defaults(self):
        defaults = dict(DEFAULT_DEBUG_PARAMETERS)
        if IS_MACOS:
            defaults.update(dict(zip(
                ("pet_width", "pet_height", "dog_height"), MACOS_PET_SIZE
            )))
        return defaults

    def debug_parameter_value(self, key):
        if key in self.debug_parameters:
            return self.debug_parameters[key]
        return self.debug_parameter_defaults().get(key, 0)

    def debug_parameter_snapshot(self, keys=None):
        selected = self.debug_parameters if keys is None else {
            key: self.debug_parameter_value(key) for key in keys
        }
        return {key: float(value) if isinstance(value, (int, float)) else value
                for key, value in selected.items()}

    def set_debug_parameter(self, key, value):
        if key not in DEFAULT_DEBUG_PARAMETERS:
            return False
        try:
            value = float(value)
        except (TypeError, ValueError):
            return False
        if key in {"pet_width", "pet_height", "dog_height"}:
            value = max(
                {"pet_width": 40, "pet_height": 60, "dog_height": 30}[key],
                int(round(value)),
            )
        elif key == "gravity":
            value = max(0.0, value)
        elif key in {"wall_bounce", "floor_bounce"}:
            value = max(0.0, min(1.0, value))
        elif key == "ground_friction":
            value = max(0.0, value)
        elif key in {"walk_speed_min", "walk_speed_max", "auto_sleep_walk_speed"}:
            value = max(0.0, value)
        elif key.startswith("animation_") and key.endswith("_fps"):
            value = max(0.1, value)
        elif key in {
            "decay_hunger", "decay_mood", "decay_energy",
            "decay_hunger_sleeping",
        }:
            value = max(0.0, value)
        elif key == "decay_energy_sleeping_gain":
            value = max(0.0, value)
        elif key in {"auto_sleep_energy_threshold", "auto_wake_energy_threshold"}:
            value = max(0.0, min(100.0, value))
        elif key in {
            "autonomy_idle_weight", "autonomy_walk_weight",
            "autonomy_sit_weight", "dig_discovery_chance",
        }:
            value = max(0.0, min(1.0, value)) if key == "dig_discovery_chance" else max(0.0, value)
        elif key == "dig_cooldown_minutes":
            value = max(1.0, value)
        elif key in {
            "petting_affection_gain", "feeding_affection_gain",
            "play_affection_gain", "petting_cooldown", "feeding_cooldown",
            "play_cooldown",
        }:
            value = max(0, int(round(value)))
        elif key == "feed_animation_duration":
            value = max(0.05, value)
        elif key == "coin_catch_duration":
            value = max(1.0, value)
        elif key == "coin_target_lifetime":
            value = max(0.05, value)
        elif key.startswith("lucky_swap_"):
            value = max(0.03, value)
        old_geometry = self.geometry()
        self.debug_parameters[key] = value
        if key == "pet_width":
            self.PET_W = max(40, int(round(value)))
        elif key == "pet_height":
            self.PET_H = max(60, int(round(value)))
        elif key == "dog_height":
            self.DOG_H = max(30, int(round(value)))
        elif key in self.debug_physics:
            self.debug_physics[key] = value
        elif key in ("walk_speed_min", "walk_speed_max"):
            self.walk_speed_min = self.debug_parameters["walk_speed_min"]
            self.walk_speed_max = self.debug_parameters["walk_speed_max"]
        elif key == "auto_sleep_walk_speed":
            self.AUTO_SLEEP_WALK_SPEED = value
        elif key.startswith("animation_") and key.endswith("_fps"):
            animation_name = key[len("animation_"):-len("_fps")]
            if animation_name in self.animation_specs:
                self.animation_specs[animation_name]["fps"] = max(0.1, value)
        elif key in {
            "decay_hunger", "decay_mood", "decay_energy",
            "decay_hunger_sleeping", "decay_energy_sleeping_gain",
        }:
            self.settings[key] = value
        elif key == "auto_sleep_energy_threshold":
            self.auto_sleep_energy_threshold = value
        elif key == "auto_wake_energy_threshold":
            self.auto_wake_energy_threshold = value
        elif key == "autonomy_idle_weight":
            self.AUTONOMY_IDLE_WEIGHT = max(0.0, value)
        elif key == "autonomy_walk_weight":
            self.AUTONOMY_WALK_WEIGHT = max(0.0, value)
        elif key == "autonomy_sit_weight":
            self.AUTONOMY_SIT_WEIGHT = max(0.0, value)
        elif key == "dig_discovery_chance":
            progression.DIG_DISCOVERY_CHANCE = max(0.0, min(1.0, value))
        elif key == "dig_cooldown_minutes":
            progression.DIG_COOLDOWN_SECONDS = max(60.0, value * 60.0)
        elif key in {
            "petting_affection_gain", "feeding_affection_gain",
            "play_affection_gain",
        }:
            action = {
                "petting_affection_gain": "pettings",
                "feeding_affection_gain": "feedings",
                "play_affection_gain": "play_sessions",
            }[key]
            progression.AFFECTION_ACTION_GAINS[action] = max(0, int(round(value)))
        elif key in {"petting_cooldown", "feeding_cooldown", "play_cooldown"}:
            action = {
                "petting_cooldown": "pettings",
                "feeding_cooldown": "feedings",
                "play_cooldown": "play_sessions",
            }[key]
            progression.AFFECTION_ACTION_COOLDOWNS[action] = max(0, int(round(value)))
        elif key == "feed_animation_duration":
            self.feed_animation_duration = max(0.05, value)
        elif key == "coin_catch_duration":
            minigames.CoinCatchCanvas.DURATION_SECONDS = max(1.0, value)
        elif key == "coin_target_lifetime":
            minigames.CoinCatchCanvas.TARGET_LIFETIME = max(0.05, value)
        elif key.startswith("lucky_swap_"):
            round_number = int(key.rsplit("_", 1)[1])
            minigames.LuckyPawsGameWindow.ROUND_CONFIG[round_number]["swap_duration"] = max(0.03, value)
        if key in ("pet_width", "pet_height"):
            self.resize(int(self.PET_W), int(self.PET_H))
            self.move(old_geometry.x(), old_geometry.bottom() - self.PET_H + 1)
        self.update()
        self.repaint()
        return True

    def save_debug_parameters(self, values):
        values = {key: self.debug_parameter_value(key) for key in DEFAULT_DEBUG_PARAMETERS}
        save_debug_parameters(values)

    def open_parameter_tuner(self):
        if IS_FROZEN:
            return
        if self.parameter_tuner_win is None:
            from parameter_tuner import ParameterTunerWindow
            self.parameter_tuner_win = ParameterTunerWindow(self)
        self.parameter_tuner_win.show_near_pet()

    def set_pet_name(self, value):
        """Persist a new name and refresh already-open pet windows."""
        name = ai.normalize_pet_name(value)
        self.state["pet_name"] = name
        save_state(self.state)
        ai.set_pet_name(name)
        if self.chat_win is not None:
            self.chat_win.refresh_pet_name()
        self.update()
        return name

    def on_health_check(self):
        """Check if it's time to remind the user to drink/rest/stand."""
        if self.state.get("sleeping"):
            return
        s = self.settings
        now = time.time()
        drink_min = s.get("remind_drink_min", 60)
        rest_min = s.get("remind_rest_min", 90)
        stand_min = s.get("remind_stand_min", 45)
        msgs = []
        if drink_min > 0 and now - self._last_drink_t > drink_min * 60:
            msgs.append(random.choice([
                "主人，该喝口水啦～💧",
                "喝杯水吧，对身体好哦💧",
                "汪…你已经很久没喝水了💧",
            ]))
            self._last_drink_t = now
        if stand_min > 0 and now - self._last_stand_t > stand_min * 60:
            msgs.append(random.choice([
                "站起来活动一下呀！🧘",
                "坐太久不好，站起来伸个懒腰～",
                "汪汪！陪我站着玩一会儿？",
            ]))
            self._last_stand_t = now
        if rest_min > 0 and now - self._last_rest_t > rest_min * 60:
            msgs.append(random.choice([
                "眼睛累了，看看远处休息一下👀",
                "闭眼休息 20 秒吧～",
                "屏幕看久了不好，歇会儿吧",
            ]))
            self._last_rest_t = now
        if msgs:
            self.say(random.choice(msgs), 4500)

    def add_xp(self, amount, *, apply_bonus=True):
        """Add XP, level up if threshold met. Returns True if leveled up."""
        if apply_bonus:
            amount = progression.apply_xp_bonus(self.state, amount)
        else:
            amount = progression.record_xp(self.state, amount)
        if amount <= 0:
            return False
        self.state["xp"] = self.state.get("xp", 0) + amount
        leveled = False
        levels_gained = 0
        while True:
            need = xp_to_next(self.state.get("level", 1))
            if self.state["xp"] >= need:
                self.state["xp"] -= need
                self.state["level"] = self.state.get("level", 1) + 1
                leveled = True
                levels_gained += 1
            else:
                break
        if levels_gained:
            self.state["records"]["level_ups"] += levels_gained
        save_state(self.state)
        return leveled

    def on_passive_xp(self):
        """Accumulate affection-driven passive XP once per second."""
        progression.record_active_time(self.state, 1)
        rate = progression.passive_xp_per_second(self.state)
        buffer_value = float(self.state.get("passive_xp_buffer", 0.0))
        buffer_value += rate
        whole_xp = int(buffer_value)
        self.state["passive_xp_buffer"] = buffer_value - whole_xp
        if whole_xp <= 0:
            return
        leveled = self.add_xp(whole_xp, apply_bonus=False)
        if leveled:
            self.say(f"升级啦！Lv.{self.state.get('level',1)} 🎉", 2500)
            g = self.geometry()
            BonusBubble(f"升级！Lv.{self.state.get('level',1)}",
                        g.center().x(), g.top() - 20, "#ffcc00")

    # ---------- placement ----------
    def place_initial(self):
        virt = self.screen_rect()  # all screens
        x = self.state.get("x")
        y = self.state.get("y")
        if x is None or y is None:
            # default: bottom-right of primary screen
            ps = QApplication.primaryScreen().availableGeometry()
            x = ps.right() - self.PET_W - 40
            y = ps.bottom() - self.PET_H - 20
        # clamp within virtual desktop
        x = max(virt.left(), min(int(x), virt.right() - self.PET_W))
        y = max(virt.top(), min(int(y), virt.bottom() - self.PET_H))
        self.move(x, y)

    def screen_rect(self):
        """Return the virtual bounding rect of all screens (multi-monitor)."""
        return QApplication.primaryScreen().virtualGeometry()

    def screen_at(self, pos):
        """Return the QScreen that contains pos, or the nearest one."""
        for scr in QApplication.screens():
            if scr.geometry().contains(pos):
                return scr
        return QApplication.primaryScreen()

    def current_screen_rect(self):
        """Geometry of the screen the pet is currently on (cached per tick)."""
        # cache for ~1 second to avoid calling screen_at every frame
        now = time.time()
        if hasattr(self, "_cached_screen_t") and now - self._cached_screen_t < 1.0:
            return self._cached_screen
        g = self.geometry()
        scr = self.screen_at(g.center())
        self._cached_screen = scr.availableGeometry()
        self._cached_screen_t = now
        return self._cached_screen

    def recall(self):
        """Move pet to a safe, visible position at the bottom-center of the current screen."""
        screen = self.current_screen_rect()
        x = screen.center().x() - self.PET_W // 2
        y = screen.bottom() - self.PET_H - 20
        self.move(x, y)
        self.vx = 0; self.vy = 0
        self.state["x"] = x; self.state["y"] = y
        save_state(self.state)
        self.say("我回来啦！🐶", 1500)

    def apply_window_flags(self, show=True):
        """Toggle always-on-top based on settings. Call after settings change."""
        on_top = self.settings.get("always_on_top", True)
        was_visible = show and self.isVisible()
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        if on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        # On macOS, Qt.Tool windows are normally hidden when the application
        # loses activation. This attribute promotes the tool window to the
        # persistent desktop layer while preserving the user's toggle.
        if IS_MACOS:
            self.setAttribute(
                Qt.WA_MacAlwaysShowToolWindow,
                bool(on_top),
            )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # setWindowFlags hides the widget; re-show if it was visible
        if was_visible:
            self.show()

    def apply_runtime_settings(self, previous=None):
        """Apply every user-facing setting immediately after save/reset."""
        previous = previous or {}
        self.apply_window_flags()

        now = time.time()
        reminder_keys = (
            ("remind_drink_min", "_last_drink_t"),
            ("remind_rest_min", "_last_rest_t"),
            ("remind_stand_min", "_last_stand_t"),
        )
        for key, timestamp_name in reminder_keys:
            if previous.get(key) != self.settings.get(key):
                setattr(self, timestamp_name, now)

        if self.chat_win is not None:
            chat = self.chat_win
            chat.s = self.settings
            screen = self.current_screen_rect()
            width = min(
                int(self.settings["chat_width"]),
                max(320, screen.width() - 20),
            )
            height = min(
                int(self.settings["chat_height"]),
                max(400, screen.height() - 80),
            )
            chat.setFixedSize(width, height)
            chat._apply_style()
            chat._refresh_ai_tool_buttons()
            chat._set_log_messages(chat._history_messages())
            if chat.isVisible():
                chat.show_near_pet()
                chat.update()
                chat.repaint()

        if callable(self._settings_applied_cb):
            self._settings_applied_cb(previous, self.settings)

    def is_visible_on_screen(self):
        g = self.geometry()
        # A virtual desktop can contain gaps between differently arranged
        # monitors. Check each physical screen instead of its outer bounds.
        for screen in QApplication.screens():
            overlap = g.intersected(screen.geometry())
            if overlap.width() >= 30 and overlap.height() >= 30:
                return True
        return False

    def pet_center(self):
        g = self.geometry()
        return QPointF(g.x() + g.width()/2, g.y() + g.height()/2)

    # ---------- action animation ----------
    def _load_animations(self):
        """Load optional PNG frame sequences without requiring them to exist."""
        specs = {name: dict(values)
                 for name, values in DEFAULT_ANIMATIONS.items()}
        manifest_path = os.path.join(ANIMATIONS_DIR, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8-sig") as f:
                    custom = json.load(f)
                if isinstance(custom, dict):
                    for name, values in custom.items():
                        if isinstance(values, dict):
                            specs.setdefault(name, {}).update(values)
            except (OSError, ValueError):
                pass

        self.animation_specs = specs
        for name, spec in specs.items():
            folder = str(spec.get("folder", name))
            frame_dir = os.path.join(ANIMATIONS_DIR, folder)
            if not os.path.isdir(frame_dir):
                continue
            frame_paths = sorted(
                (os.path.join(frame_dir, filename)
                 for filename in os.listdir(frame_dir)
                 if filename.lower().endswith(".png")),
                key=lambda path: os.path.basename(path).lower(),
            )
            frames = []
            for frame_path in frame_paths:
                pixmap = QPixmap(frame_path)
                if pixmap.isNull():
                    continue
                # AI source frames can be large. Retaining a 2x render size
                # keeps Retina output sharp without consuming hundreds of MB.
                if pixmap.width() > 512 or pixmap.height() > 512:
                    pixmap = pixmap.scaled(
                        512, 512, Qt.KeepAspectRatio,
                        Qt.SmoothTransformation)
                pixmap = adjust_animation_colors(
                    pixmap,
                    saturation=spec.get("saturation", 1.0),
                    brightness=spec.get("brightness", 1.0),
                )
                frames.append(pixmap)
            if frames:
                self.animation_frames[name] = frames

    @staticmethod
    def _show_idle_decorations(
            animation_name, pose, animation_pixmap):
        """Keep passive states on the same decorated idle appearance."""
        if (
            animation_pixmap is not None
            or animation_name not in ("idle", "sit", "ask")
            or pose not in (POSE["idle"], POSE["close"])
        ):
            return False
        return True

    def _animation_duration_ms(self, name, cycles=1):
        """Return the exact time needed to show an animation for N cycles."""
        frames = self.animation_frames.get(name, ())
        spec = self.animation_specs.get(name, {})
        try:
            fps = max(1.0, float(spec.get("fps", 8)))
        except (TypeError, ValueError):
            fps = 8.0
        if not frames:
            return 1
        cycles = max(1, int(cycles))
        return max(1, int(math.ceil(len(frames) * cycles * 1000.0 / fps)))

    def trigger_animation(
        self, name, duration_ms=None, finished_callback=None
    ):
        """Temporarily override state animation, optionally for one full run."""
        if duration_ms is None:
            duration_ms = self._animation_duration_ms(name)
        self._animation_override_token += 1
        token = self._animation_override_token
        self._animation_override = name
        self._active_animation = None
        self._animation_started_at = time.monotonic()

        def finish():
            if token == self._animation_override_token:
                self._animation_override = None
                self._active_animation = None
                self._animation_started_at = time.monotonic()
                self.refresh_pose_from_state()
            if callable(finished_callback):
                finished_callback()

        QTimer.singleShot(max(1, int(duration_ms)), finish)
        self.update()

    def _current_animation_name(self):
        if self._animation_override:
            return self._animation_override
        if self.state.get("sleeping"):
            return "sleep"
        if self.dragging:
            return "drag"
        if self.behavior == "eat":
            return "eat"
        if self.behavior in ("walk", "auto_sleep_walk"):
            return "walk"
        if self.behavior in ("sit", "ask"):
            return self.behavior
        return POSE_NAMES[self.pose]

    def _animation_frame(self, name):
        frames = self.animation_frames.get(name)
        if not frames:
            self._animation_frame_index = None
            return None
        if self._active_animation != name:
            self._active_animation = name
            self._animation_started_at = time.monotonic()
        spec = self.animation_specs.get(name, {})
        try:
            fps = max(1.0, float(spec.get("fps", 8)))
        except (TypeError, ValueError):
            fps = 8.0
        index = int((time.monotonic() - self._animation_started_at) * fps)
        if bool(spec.get("loop", True)):
            index %= len(frames)
        else:
            index = min(index, len(frames) - 1)
        self._animation_frame_index = index
        return frames[index]

    def _fallback_pose(self, animation_name):
        spec = self.animation_specs.get(animation_name, {})
        fallback = str(spec.get("fallback", animation_name))
        return POSE.get(fallback, self.pose)

    @staticmethod
    def _apply_blink_frame(blink, pose, animation_pixmap):
        """Blink without replacing an active action-animation frame."""
        if (
            blink
            and animation_pixmap is None
            and pose in (POSE["idle"], POSE["happy"])
        ):
            return POSE["close"], None
        return pose, animation_pixmap

    # ---------- painting ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # Determine action animation and its static fallback.
        animation_name = self._current_animation_name()
        pose = self._fallback_pose(animation_name)
        animation_pixmap = self._animation_frame(animation_name)
        # Passive sit/ask behavior changes dialogue timing, not appearance.
        # Keep the authored idle model so equipped decorations never vanish.
        if (
            animation_pixmap is None
            and animation_name in ("idle", "sit", "ask")
        ):
            pose = POSE["idle"]
        # blink: briefly switch to "close" (eyes-closed) pose if available
        pose, animation_pixmap = self._apply_blink_frame(
            self.blink, pose, animation_pixmap
        )

        # dog occupies lower part of widget; top is reserved for speech bubble
        dog_y = self.PET_H - self.DOG_H
        dst = QRectF(0, dog_y, self.PET_W, self.DOG_H)

        # Flip horizontally if facing left
        if self.facing < 0:
            p.save()
            p.translate(self.PET_W, 0)
            p.scale(-1, 1)

        if animation_pixmap is not None or self.use_png:
            pm = (animation_pixmap or self.pose_pixmaps.get(pose)
                  or self.pose_pixmaps.get(POSE["idle"]))
            if pm is not None and not pm.isNull():
                # scale pixmap to fit dst, keep aspect ratio (fit inside)
                pw, ph = pm.width(), pm.height()
                scale = min(self.PET_W / pw, self.DOG_H / ph)
                spec = self.animation_specs.get(animation_name, {})
                if animation_pixmap is not None:
                    try:
                        scale *= max(0.1, float(spec.get("scale", 1.0)))
                    except (TypeError, ValueError):
                        pass
                dw, dh = pw * scale, ph * scale
                dx = (self.PET_W - dw) / 2
                if (animation_pixmap is not None and
                        bool(spec.get("anchor_bottom", False))):
                    # AI sprite sheets often leave different amounts of
                    # transparent padding around each frame. Anchor the
                    # visible alpha bounds instead of the full canvas so a
                    # grounded walk cycle never hops between source rows.
                    visible = QRegion(pm.mask()).boundingRect()
                    visible_bottom = visible.y() + visible.height()
                    dy = dog_y + self.DOG_H - visible_bottom * scale
                else:
                    dy = dog_y + (self.DOG_H - dh) / 2
                p.drawPixmap(QRectF(dx, dy, dw, dh), pm,
                             QRectF(0, 0, pw, ph))
        else:
            # SVG spritesheet fallback
            sx = pose * CELL
            src = QRectF(sx, 0, CELL, CELL)
            self.renderer.setViewBox(src)
            self.renderer.render(p, dst)

        if self._show_idle_decorations(
                animation_name, pose, animation_pixmap):
            decoration_renderer.draw_equipped_idle(
                p,
                self.state,
                dst,
                self.decoration_pixmaps,
            )

        if self.facing < 0:
            p.restore()

        if self.needs_api_key_configuration():
            badge_center = QPointF(self.PET_W - 13, dog_y + 13)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255))
            p.drawEllipse(badge_center, 8, 8)
            p.setBrush(QColor("#ee5e62"))
            p.drawEllipse(badge_center, 5.5, 5.5)

        p.end()

    def _draw_bubble(self, p):
        """Draw speech bubble in the top reserved area, with word wrap and
        max-width so long text doesn't overflow. Caches QTextDocument."""
        text = self.bubble_text
        font = pixel_font(11, QFont.Bold)
        p.setFont(font)
        max_bw = max(self.PET_W + 80, 260)
        wrap_w = max_bw - 24
        # cache the QTextDocument; rebuild only when text changes
        if (not hasattr(self, "_bubble_doc") or
                getattr(self, "_bubble_doc_text", None) != text):
            doc = QTextDocument()
            doc.setDefaultFont(font)
            doc.setTextWidth(wrap_w)
            doc.setPlainText(text)
            self._bubble_doc = doc
            self._bubble_doc_text = text
        else:
            doc = self._bubble_doc
            if doc.textWidth() != wrap_w:
                doc.setTextWidth(wrap_w)
        text_h = doc.size().height()
        text_w = doc.idealWidth()
        bw = int(min(max_bw, text_w + 24))
        bh = int(text_h + 14)
        # if too tall (more than ~3 lines), truncate
        max_bh = 78
        if bh > max_bh:
            bh = max_bh
        bx = (self.PET_W - bw) / 2
        by = 4
        if bw > self.PET_W:
            bw = self.PET_W
            wrap_w = bw - 24
            doc.setTextWidth(wrap_w)
            text_h = doc.size().height()
            text_w = doc.idealWidth()
            bh = int(min(text_h + 14, max_bh))
            bx = 0
        rect = QRectF(bx, by, bw, bh)
        # shadow
        shadow = QRectF(bx + 2, by + 2, bw, bh)
        p.setBrush(QColor(0, 0, 0, 40))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(shadow, 12, 12)
        # main bubble — warm cream gradient
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(255, 248, 225))
        grad.setColorAt(1.0, QColor(255, 238, 186))
        p.setBrush(grad)
        p.setPen(QPen(QColor(230, 180, 80), 1.2))
        p.drawRoundedRect(rect, 12, 12)
        # tail shadow
        tail_pts = [QPointF(bx+bw/2-7, by+bh), QPointF(bx+bw/2+7, by+bh),
                    QPointF(bx+bw/2, by+bh+10)]
        p.setBrush(QColor(0, 0, 0, 30))
        p.setPen(Qt.NoPen)
        p.drawPolygon(tail_pts)
        # tail main
        tail_pts2 = [QPointF(bx+bw/2-6, by+bh), QPointF(bx+bw/2+6, by+bh),
                     QPointF(bx+bw/2, by+bh+9)]
        p.setBrush(QColor(255, 243, 200))
        p.setPen(QPen(QColor(230, 180, 80), 1.0))
        p.drawPolygon(tail_pts2)
        # text (clipped to bubble rect, wrapped)
        p.setPen(QColor(80, 50, 20))
        p.save()
        p.translate(QPointF(bx + 12, by + 7))
        clip = QRectF(0, 0, bw - 24, bh - 14)
        p.setClipRect(clip)
        doc.drawContents(p, clip)
        p.restore()

    # ---------- say ----------
    def play_sound(self, name):
        if not self.settings.get("sound_enabled", True):
            return
        se = self.sounds.get(name)
        if se is not None:
            se.stop()
            se.play()


    def say(self, text, ms=2200):
        if not self.isVisible():
            return
        speech = self._speech_bubble
        if speech is not None:
            try:
                # Do not reuse a hidden native translucent window at a new
                # size; construct a fresh backing surface for the next line.
                if not speech.isVisible():
                    speech.close()
                    speech = None
            except RuntimeError:
                speech = None
        if speech is None:
            self._speech_bubble = SpeechBubble(self)
        self._speech_bubble.show_text(text, ms)

    def hide_overlays(self):
        """Close every detached bubble that visually belongs to the pet."""
        speech = self._speech_bubble
        if speech is not None:
            try:
                speech.clear_messages()
            except RuntimeError:
                self._speech_bubble = None

        interactive = self._interactive_bubble
        self._interactive_bubble = None
        if interactive is not None:
            try:
                interactive.close()
            except RuntimeError:
                pass

        menu = self._bubble_menu
        self._bubble_menu = None
        if menu is not None:
            try:
                menu._close()
            except RuntimeError:
                pass

        bonus = getattr(self, "_last_bonus", None)
        self._last_bonus = None
        if bonus is not None:
            try:
                bonus.close()
            except RuntimeError:
                pass

    def hideEvent(self, event):
        self.hide_overlays()
        super().hideEvent(event)

    # ---------- mouse ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._woke_from_shake = False
            if self.state.get("sleeping"):
                self._wake_shake.start(
                    e.globalPos().x(), time.monotonic())
            else:
                self._wake_shake.reset()
            self.dragging = True
            self.drag_offset = e.globalPos() - self.frameGeometry().topLeft()
            self.last_drag_pos = e.globalPos()
            self.last_drag_t = time.time()
            self.drag_samples = [(e.globalPos(), self.last_drag_t)]
            self.pose = POSE["drag"]
            self.behavior = "drag"
            self.vx = 0; self.vy = 0
            self.setCursor(Qt.ClosedHandCursor)
        elif e.button() == Qt.RightButton:
            # context menu handled by parent; here we ignore
            pass

    def mouseMoveEvent(self, e):
        if self.dragging:
            now = time.time()
            if (self.state.get("sleeping")
                    and self._wake_shake.move(
                        e.globalPos().x(), time.monotonic())):
                self.wake_from_shake()
            new_pos = e.globalPos() - self.drag_offset
            # clamp so the pet stays at least partially visible on screen
            screen = self.screen_rect()
            w, h = self.PET_W, self.DOG_H  # use dog drawing size for clamping
            # allow at most 70% off-screen on any side, so a chunk always shows
            # but account for the 60px bubble space at top of widget
            new_x = max(-int(w*0.7), min(new_pos.x(), screen.width() - int(w*0.3)))
            new_y = max(-int(h*0.7) + 60, min(new_pos.y(), screen.height() - int(h*0.3) - 40))
            self.move(new_x, new_y)
            # store raw (unclamped) cursor velocity samples within last 1s,
            # so fling speed reflects hand motion even near screen edges
            self.drag_samples.append((e.globalPos(), now))
            self.drag_samples = [s for s in self.drag_samples if now - s[1] < 1.0]
            self.last_drag_pos = e.globalPos()
            self.last_drag_t = now

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.setCursor(Qt.ArrowCursor)
            # fling: use instantaneous velocity from the last ~100ms of motion,
            # NOT the average over the whole drag. This gives real inertia:
            # if you were still moving when you let go, it flies; if you'd
            # already stopped, it just drops.
            now = time.time()
            window = [s for s in self.drag_samples if now - s[1] < 0.10]
            if not self._woke_from_shake and len(window) >= 2:
                (p0, t0), (p1, t1) = window[0], window[-1]
                dt = t1 - t0
                if dt > 0.005:
                    self.vx = (p1.x() - p0.x()) / dt
                    self.vy = (p1.y() - p0.y()) / dt
                    # allow strong flings
                    self.vx = max(-2800, min(2800, self.vx))
                    self.vy = max(-2800, min(2800, self.vy))
                    # if motion was mostly horizontal, keep some upward lift
                    # so it sails instead of instantly dropping
                    if abs(self.vy) < 80 and abs(self.vx) > 300:
                        self.vy = -120  # slight upward bias -> arc trajectory
            if self._woke_from_shake:
                # A wake-up shake is affectionate interaction, not a throw.
                self.vx = 0
                self.vy = 0
            # mark airborne so gravity + bounce physics take over
            self.on_ground = False
            self.pose = POSE["idle"]
            self.behavior = "idle"
            self.behavior_until = time.time() + 1.0
            self.next_behavior_at = time.time() + random.uniform(2, 5)
            speed = math.hypot(self.vx, self.vy)
            if speed > 120:
                self.say(random.choice(["汪！Whee~","嗖——","飞起来啦！","汪汪！"]), 1200)
            self.drag_samples = []
            self._wake_shake.reset()
            self._woke_from_shake = False

    # single click (press & release without much move) = pet
    def mouseReleaseEvent_pet(self):
        # we detect a "click" in release if movement was tiny
        pass

    # ---------- physics tick ----------
    def on_tick(self):
        now = time.time()
        screen = self.current_screen_rect()
        g = self.geometry()
        x, y = float(g.x()), float(g.y())
        w, h = g.width(), g.height()

        dt = 0.033           # ~30 fps
        G = self.debug_physics["gravity"]
        GROUND_PAD = 10      # pixels above taskbar
        ground_y = screen.bottom() - h - GROUND_PAD
        BOUNCE = self.debug_physics["wall_bounce"]
        BOUNCE_FLOOR = self.debug_physics["floor_bounce"]
        FRICTION = self.debug_physics["ground_friction"]
        STOP_V = 2.0         # below this, snap to 0
        auto_sleep_arrived = False

        if self._auto_sleep_phase == "walking" and not self.dragging:
            if self._auto_sleep_target_x is None:
                self._auto_sleep_target_x = self._auto_sleep_corner_x()
            delta_x = self._auto_sleep_target_x - x
            self.behavior = "auto_sleep_walk"
            if abs(delta_x) <= self.AUTO_SLEEP_WALK_SPEED * dt:
                self.target_vx = 0
                self.vx = 0
                auto_sleep_arrived = self.on_ground
            else:
                direction = 1.0 if delta_x > 0 else -1.0
                self.target_vx = direction * self.AUTO_SLEEP_WALK_SPEED
                self.vx = self.target_vx

        is_walking = self.behavior in ("walk", "auto_sleep_walk")

        if not self.dragging:
            # walking overrides gravity (stay glued to ground while walking)
            if is_walking and self.on_ground:
                self.vx = self.target_vx
                self.vy = 0
            else:
                # gravity always pulling down when airborne
                self.vy += G * dt

            # integrate position
            new_x = x + self.vx * dt
            new_y = y + self.vy * dt
            if auto_sleep_arrived:
                new_x = self._auto_sleep_target_x

            # ---- floor collision ----
            if new_y >= ground_y:
                if self.on_ground:
                    # already on ground; just clamp
                    new_y = ground_y
                    if not is_walking:
                        self.vy = 0
                else:
                    # landing from a fall/fling -> bounce
                    new_y = ground_y
                    if abs(self.vy) > 60:
                        self.vy = -self.vy * BOUNCE_FLOOR
                        if abs(self.vy) > 250:
                            self.say("哎哟！", 800)
                    else:
                        self.vy = 0
                    # settle to ground if bounce too small
                    if abs(self.vy) < 50:
                        self.vy = 0
                        self.on_ground = True
                    else:
                        # still bouncing, leave airborne
                        self.on_ground = False
            else:
                self.on_ground = False

            # ---- left / right walls ----
            if new_x < screen.left():
                new_x = screen.left()
                if self.vx < 0:
                    self.vx = -self.vx * BOUNCE
                    if abs(self.vx) > 80:
                        now2 = time.time()
                        if not hasattr(self, "_last_wall_t") or now2 - self._last_wall_t > 0.5:
                            self._last_wall_t = now2
                            self.say("哎哟！", 800)
            elif new_x > screen.right() - w:
                new_x = screen.right() - w
                if self.vx > 0:
                    self.vx = -self.vx * BOUNCE
                    if abs(self.vx) > 80:
                        now2 = time.time()
                        if not hasattr(self, "_last_wall_t") or now2 - self._last_wall_t > 0.5:
                            self._last_wall_t = now2
                            self.say("哎哟！", 800)

            # ---- ceiling ----
            if new_y < screen.top():
                new_y = screen.top()
                if self.vy < 0:
                    self.vy = -self.vy * BOUNCE

            # ---- ground friction ----
            if self.on_ground and not is_walking:
                self.vx *= FRICTION
                if abs(self.vx) < STOP_V:
                    self.vx = 0

            # ---- facing follows horizontal velocity ----
            if abs(self.vx) > 5:
                self.facing = 1 if self.vx > 0 else -1
            elif is_walking:
                self.facing = 1 if self.target_vx > 0 else -1

            # Preserve the legacy bob only while no real walk frames exist.
            if (self.on_ground and abs(self.vx) > 20 and
                    not (is_walking and
                         self.animation_frames.get("walk"))):
                new_y -= abs(math.sin(time.time() * 6)) * 4

            self.move(int(new_x), int(new_y))
            if auto_sleep_arrived:
                self._enter_auto_sleep()

        # keep interactive bubble glued to the pet
        if self._interactive_bubble is not None:
            try:
                if self._interactive_bubble.isVisible():
                    self._interactive_bubble._place_above_pet()
                else:
                    self._interactive_bubble = None
            except RuntimeError:
                self._interactive_bubble = None

        # keep bubble menu + stat bubble following the pet
        if self._bubble_menu is not None:
            try:
                if self._bubble_menu.isVisible():
                    self._bubble_menu.follow_pet()
                else:
                    self._bubble_menu = None
            except RuntimeError:
                self._bubble_menu = None

        # keep the detached speech bubble following the pet
        if self._speech_bubble is not None and self._speech_bubble.isVisible():
            try:
                self._speech_bubble.follow_pet()
            except RuntimeError:
                self._speech_bubble = None

        # update blink occasionally
        self.blink_t += 0.033
        if self.blink_t > 2.5 and not self.blink:
            self.blink = True
            self.blink_t = 0
        elif self.blink and self.blink_t > 0.12:
            self.blink = False
            self.blink_t = 0

        # save pos occasionally
        if random.random() < 0.02:
            self.state["x"] = self.x()
            self.state["y"] = self.y()
            save_state(self.state)

        self.update()

    def _auto_sleep_corner_x(self):
        screen = self.current_screen_rect()
        left_x = screen.left() + self.AUTO_SLEEP_CORNER_MARGIN
        right_x = (
            screen.right() - self.width()
            - self.AUTO_SLEEP_CORNER_MARGIN + 1
        )
        if abs(self.x() - left_x) <= abs(self.x() - right_x):
            return float(left_x)
        return float(right_x)

    def _begin_auto_sleep(self, now=None):
        now = time.time() if now is None else float(now)
        if (
            self.state.get("sleeping")
            or self._auto_sleep_phase == "walking"
            or self.dragging
            or self.play_scene is not None
            or not self.isVisible()
            or now < self._auto_sleep_snooze_until
        ):
            return False
        self._auto_sleep_phase = "walking"
        self._auto_sleep_target_x = self._auto_sleep_corner_x()
        self.behavior = "auto_sleep_walk"
        direction = 1.0 if self._auto_sleep_target_x > self.x() else -1.0
        self.target_vx = direction * self.AUTO_SLEEP_WALK_SPEED
        self.vx = self.target_vx
        self.vy = 0
        self.behavior_until = float("inf")
        self.next_behavior_at = float("inf")
        self.state["sleep_mode"] = None

        interactive = self._interactive_bubble
        self._interactive_bubble = None
        if interactive is not None:
            try:
                interactive.close()
            except RuntimeError:
                pass

        lines = [
            "我困了，要去角落睡一会儿～",
            "眼皮好重呀，我先去睡觉啦。",
            "精力快见底啦，我去找个舒服的地方休息。",
        ]
        hour = time.localtime().tm_hour
        if 11 <= hour < 18:
            lines.append("有点困啦，午安主人，我去睡一会儿～")
        elif hour >= 21 or hour < 6:
            lines.append("好困呀，晚安主人，我去睡觉啦～")
        self.say(random.choice(lines), 3200)
        self.refresh_pose_from_state()
        self.update()
        return True

    def _enter_auto_sleep(self):
        if self._auto_sleep_phase != "walking":
            return False
        if self._auto_sleep_target_x is not None:
            self.move(int(round(self._auto_sleep_target_x)), self.y())
        self._auto_sleep_phase = "sleeping"
        self._auto_sleep_target_x = None
        self.state["sleeping"] = True
        self.state["sleep_mode"] = "auto"
        progression.record_sleep(self.state, "auto")
        self.state["x"] = self.x()
        self.state["y"] = self.y()
        self.behavior = "idle"
        self.target_vx = 0
        self.vx = 0
        self.vy = 0
        self.on_ground = True

        hour = time.localtime().tm_hour
        if 11 <= hour < 18:
            line = random.choice([
                "午安主人，我在这里睡一会儿～",
                "主人午安，醒来再陪你玩。",
            ])
        elif hour >= 21 or hour < 6:
            line = random.choice([
                "晚安主人，做个好梦～",
                "主人晚安，我要进入香香的梦乡啦。",
            ])
        else:
            line = random.choice([
                "我先睡一会儿，醒了再回来陪你～",
                "这里很舒服，我要开始充电啦。",
            ])
        self.say(line, 3000)
        self.play_sound("sleep")
        save_state(self.state)
        self.refresh_pose_from_state()
        self.update()
        return True

    def _wake_from_auto_sleep(self):
        if (
            not self.state.get("sleeping")
            or self.state.get("sleep_mode") != "auto"
        ):
            return False
        self.state["sleeping"] = False
        self.state["sleep_mode"] = None
        self._auto_sleep_phase = None
        self._auto_sleep_target_x = None
        self.behavior = "idle"
        self.behavior_until = time.time() + 1.2
        self.next_behavior_at = self.behavior_until + random.uniform(2, 5)
        self.target_vx = 0
        self.vx = 0
        self.vy = 0
        self.say(random.choice([
            "睡醒啦，我又回来啦！",
            "充满电啦！主人，我醒啦～",
            "这一觉好舒服，我们继续玩吧！",
            "早呀主人，我现在精神满满！",
        ]), 2600)
        self.play_sound("bark")
        save_state(self.state)
        self.refresh_pose_from_state()
        self.update()
        return True

    def _update_auto_sleep_state(self, now=None):
        now = time.time() if now is None else float(now)
        if self.state.get("sleeping"):
            if self.state.get("sleep_mode") == "auto":
                self._auto_sleep_phase = "sleeping"
                wake_threshold = getattr(
                    self, "auto_wake_energy_threshold",
                    self.AUTO_WAKE_ENERGY_THRESHOLD,
                )
                if self.state.get("energy", 0) > wake_threshold:
                    self._wake_from_auto_sleep()
                    return "woke"
            else:
                self._auto_sleep_phase = None
            return "sleeping"

        self.state["sleep_mode"] = None
        if self._auto_sleep_phase == "sleeping":
            self._auto_sleep_phase = None
        if self._auto_sleep_phase == "walking":
            return "walking"
        sleep_threshold = getattr(
            self, "auto_sleep_energy_threshold",
            self.AUTO_SLEEP_ENERGY_THRESHOLD,
        )
        if (
            self.state.get("energy", 0) < sleep_threshold
            and now >= self._auto_sleep_snooze_until
            and self._begin_auto_sleep(now)
        ):
            return "walking"
        return None

    # ---------- decay ----------
    def on_decay(self):
        s = self.settings
        effects = progression.upgrade_effects(self.state)
        awake_decay_multiplier = effects["awake_decay_multiplier"]
        if self.state["sleeping"]:
            energy_gain = (
                s["decay_energy_sleeping_gain"]
                + effects["sleep_energy_gain_bonus"]
            )
            hunger_cost = (
                s["decay_hunger_sleeping"]
                * effects["sleep_hunger_multiplier"]
            )
            self.state["energy"] = min(
                100, self.state["energy"] + energy_gain
            )
            self.state["hunger"] = max(
                0, self.state["hunger"] - hunger_cost
            )
        else:
            self.state["hunger"] = max(
                0,
                self.state["hunger"]
                - s["decay_hunger"] * awake_decay_multiplier,
            )
            self.state["energy"] = max(
                0,
                self.state["energy"]
                - s["decay_energy"] * awake_decay_multiplier,
            )
            self.state["mood"] = max(
                0,
                self.state["mood"]
                - s["decay_mood"] * awake_decay_multiplier,
            )
        auto_sleep_event = self._update_auto_sleep_state()
        save_state(self.state)
        self.refresh_pose_from_state()
        if auto_sleep_event in ("walking", "woke"):
            return
        # occasional needy remarks (rate-controlled by settings)
        if not self.state["sleeping"]:
            boost = s.get("chatter_frequency_boost", 1.2)
            chance = min(1.0, s["needy_speak_chance"] * boost)
            if self.state["hunger"] < 20 and random.random() < chance:
                self.say(random.choice([
                    "好饿啊…🍗", "给我点吃的嘛", "肚子咕咕叫了…",
                    "闻到好吃的味道了吗？", "想啃一块小肉干", "饭饭什么时候来呀",
                    "我的小肚子空空的", "主人，投喂时间到啦",
                ]))
            elif self.state["mood"] < 20 and random.random() < chance:
                self.say(random.choice([
                    "呜呜…陪我玩嘛🥺", "好无聊呀…", "我想贴贴…",
                    "小球是不是藏起来了？", "陪我闹一会儿嘛", "尾巴都无聊得不摇了",
                    "主人看看我嘛", "摸摸头就会开心一点",
                ]))
            elif self.state["energy"] < 20 and random.random() < chance:
                self.say(random.choice([
                    "困死了…💤", "想睡觉了…", "眼皮开始打架了…",
                    "我的小窝在叫我", "要变成一只瞌睡狗了", "打个哈欠先…哈呜",
                    "可以陪我眯一会儿吗", "电量快要见底啦",
                ]))
        # Hunger and mood may ask for help. Low energy is handled by the
        # autonomous walk-to-corner sleep flow instead of a random bubble.
        if (not self.state["sleeping"]
                and self._auto_sleep_phase != "walking"):
            self.maybe_show_interactive_bubble()

    def maybe_show_interactive_bubble(self):
        """Occasionally offer a warm action bubble for hunger or low mood."""
        if not self.isVisible():
            return
        # already showing one? skip
        if self._interactive_bubble is not None:
            try:
                if self._interactive_bubble.isVisible():
                    return
            except Exception:
                self._interactive_bubble = None
        # throttle: at most once per 90s
        if time.time() - self._last_interactive_t < 90:
            return
        # don't pop while dragging or sleeping or chat open
        if self.dragging or self.state.get("sleeping"):
            return
        # Energy is deliberately absent: tiredness uses autonomous sleep.
        candidates = []
        if self.state["hunger"] < 40:
            candidates.append((
                "feed", "喂喂我", "#f39a68", "饱腹"
            ))
        if self.state["mood"] < 40:
            candidates.append((
                "play", "陪我玩", "#75cda8", "心情"
            ))
        if not candidates:
            return
        # Mood is communicated by a nearby action bubble instead of swapping
        # the decorated idle model for the legacy sad pose. Prefer that bubble
        # when hunger and mood happen to be low at the same time.
        mood_candidates = [
            candidate for candidate in candidates
            if candidate[0] == "play"
        ]
        action, label, color, _ = (
            mood_candidates[0]
            if mood_candidates
            else candidates[0]
        )
        # bonus_text not pre-computed; computed from actual deltas on click
        self._interactive_bubble = InteractiveBubble(self, label, action, color, "")
        self._last_interactive_t = time.time()
        # also show a tiny speech line to draw attention
        if action == "feed":
            self.say("肚子咕咕叫啦，主人看看我～", 2500)
        elif action == "play":
            self.say("心情有点低落，陪我玩一会儿嘛～", 2500)

    def _show_pending_dig_bubble(self):
        if int(self.state.get("pending_dig_reward", 0)) <= 0:
            return False
        if self._interactive_bubble is not None:
            try:
                if self._interactive_bubble.isVisible():
                    return False
            except RuntimeError:
                self._interactive_bubble = None
        self._interactive_bubble = InteractiveBubble(
            self, "发现宝藏", "dig_reward", "#e3ac36", ""
        )
        self._last_interactive_t = time.time()
        return True

    def maybe_discover_dig_reward(self, now=None, rng=None):
        """Occasionally surface one persistent, cooldown-limited treasure."""
        progression.ensure_progression(self.state)
        if not self.isVisible():
            return False
        if int(self.state.get("pending_dig_reward", 0)) > 0:
            if self.dragging or self.state.get("sleeping") or self.play_scene:
                return False
            return self._show_pending_dig_bubble()
        if (
            self.dragging
            or self.state.get("sleeping")
            or self.play_scene is not None
            or self._dig_reward_claiming
        ):
            return False
        now = time.time() if now is None else float(now)
        if progression.dig_cooldown_remaining(self.state, now) > 0:
            return False
        rng = rng or random
        if float(rng.random()) >= progression.DIG_DISCOVERY_CHANCE:
            return False
        reward = progression.roll_dig_reward(rng)
        self.state["pending_dig_reward"] = int(reward["amount"])
        self.state["last_dig_discovery_at"] = now
        save_state(self.state)
        shown = self._show_pending_dig_bubble()
        if shown:
            self.say("好像挖到亮闪闪的东西啦！", 2400)
        return True

    def claim_dig_reward(self):
        """Play the full reveal first, then add the pending Pet coins."""
        progression.ensure_progression(self.state)
        if self._dig_reward_claiming:
            return False
        amount = int(self.state.get("pending_dig_reward", 0))
        if amount <= 0:
            return False
        self._dig_reward_claiming = True

        def award():
            pending = int(self.state.get("pending_dig_reward", 0))
            if pending > 0:
                self.state["pending_dig_reward"] = 0
                self.state["records"]["dig_treasures_found"] += 1
                progression.add_coins(
                    self.state, pending, source="digging"
                )
                save_state(self.state)
                try:
                    geometry = self.geometry()
                    self._last_bonus = BonusBubble(
                        f"Pet币 +{pending}",
                        geometry.center().x(),
                        geometry.top() - 10,
                        "#e3ac36",
                    )
                except Exception:
                    pass
                self.say(f"挖到 {pending} 枚 Pet币！", 2500)
                if self.shop_win is not None:
                    try:
                        self.shop_win.refresh()
                    except RuntimeError:
                        self.shop_win = None
            self._dig_reward_claiming = False

        self.trigger_animation("dig_reward", finished_callback=award)
        return True

    def refresh_pose_from_state(self):
        if self.state["sleeping"]:
            self.pose = POSE["sleep"]; return
        if self.dragging:
            self.pose = POSE["drag"]; return
        if self.behavior == "eat":
            self.pose = POSE["eat"]; return
        # Hunger and mood are expressed through nearby action bubbles. Passive
        # appearance always returns to the decorated idle model.
        self.pose = POSE["idle"]

    # ---------- autonomous behavior ----------
    def on_autonomy(self):
        now = time.time()
        auto_sleep_event = self._update_auto_sleep_state(now)
        if auto_sleep_event in ("walking", "woke"):
            return
        # AI proactive nudge check (runs even if sleeping? no—sleeping skip)
        if not self.state["sleeping"]:
            self.check_ai_nudge()
        if self.dragging or self.state["sleeping"]:
            return
        # if currently doing something with a deadline, wait
        if now < self.behavior_until:
            return
        # pick a new behavior
        if now >= self.next_behavior_at:
            s = self.settings
            boost = s.get("chatter_frequency_boost", 1.2)
            ask_w = (s["ask_weight_needy"] if self.needy()
                     else s["ask_weight_normal"]) * boost
            choice = random.choices(
                ["idle","walk","sit","ask"],
                weights=[
                    self.AUTONOMY_IDLE_WEIGHT,
                    self.AUTONOMY_WALK_WEIGHT,
                    self.AUTONOMY_SIT_WEIGHT,
                    ask_w,
                ],
                k=1
            )[0]
            if choice == "walk":
                self.behavior = "walk"
                progression.record_action(
                    self.state, "autonomous_walks"
                )
                self.target_vx = random.choice([-1,1]) * random.uniform(
                    min(self.walk_speed_min, self.walk_speed_max),
                    max(self.walk_speed_min, self.walk_speed_max),
                )
                self.behavior_until = now + random.uniform(2, 5)
                self.facing = 1 if self.target_vx > 0 else -1
            elif choice == "sit":
                self.behavior = "sit"
                self.target_vx = 0
                self.vx = 0
                self.behavior_until = now + random.uniform(2, 4)
            elif choice == "ask":
                self.behavior = "ask"
                self.behavior_until = now + 1.5
                if self.state["hunger"] < 50:
                    self.say(random.choice([
                        "想吃东西🍗", "今天有小零食吗？", "鼻子闻到香味啦",
                        "一小口就好嘛", "要是有肉干就好啦",
                    ]))
                elif self.state["mood"] < 50:
                    self.say(random.choice([
                        "想玩🎾", "我们来追小球吧", "陪我玩一小会儿嘛",
                        "尾巴已经准备好摇啦", "主人，来碰个爪！",
                    ]))
                elif self.state["energy"] < 40:
                    self.say(random.choice([
                        "想睡觉💤", "找个舒服的姿势趴下", "我先眯一小会儿",
                        "困意追上我啦", "小狗也要充充电",
                    ]))
                else:
                    h = time.localtime().tm_hour
                    normal_lines = [
                        "汪！我在这里", "想贴贴❤️", "偷偷看主人一眼",
                        "尾巴今天摇得很有精神", "主人现在在忙什么呀",
                        "我刚刚发了一会儿呆", "有我陪着你呢", "今天也要开心一点",
                        "路过，蹭一下主人", "我的耳朵刚才动了一下",
                        "嘿嘿，突然想叫你一声", "要不要摸摸我的头？",
                    ]
                    if 5 <= h < 11:
                        normal_lines.extend(["早上的空气真好呀", "主人吃早饭了吗？"])
                    elif 18 <= h < 23:
                        normal_lines.extend(["晚上也陪着你呀", "今天辛苦啦，蹭蹭"])
                    self.say(random.choice(normal_lines))
            else:
                self.behavior = "idle"
                self.target_vx = 0
                self.vx = 0
                self.behavior_until = now + random.uniform(4, 8)
            self.next_behavior_at = (
                self.behavior_until + random.uniform(5, 10)
            )
        if self.behavior == "eat" and now >= self.behavior_until:
            self.behavior = "idle"
        # stop walking when deadline hits
        if self.behavior == "walk" and now >= self.behavior_until:
            self.behavior = "idle"
            self.target_vx = 0
            self.vx = 0
        self.refresh_pose_from_state()

    def needy(self):
        return (self.state["hunger"] < 40 or self.state["mood"] < 40
                or self.state["energy"] < 40)

    # ---------- actions ----------
    def feed(self, _checked=False, *, grant_xp=True):
        if self.state["sleeping"]:
            self.say("呼…睡着呢💤"); return
        effects = progression.upgrade_effects(self.state)
        self.state["hunger"] = min(
            100, self.state["hunger"] + effects["feed_hunger"]
        )
        self.state["mood"] = min(
            100, self.state["mood"] + effects["feed_mood"]
        )
        progression.record_action(self.state, "feedings")
        self.behavior = "eat"
        feed_duration = float(getattr(self, "feed_animation_duration", 1.5))
        if getattr(self, "animation_frames", {}).get("eat"):
            duration_ms = self._animation_duration_ms("eat", cycles=2)
        else:
            duration_ms = int(round(feed_duration * 1000))
        self.behavior_until = time.time() + feed_duration
        self.trigger_animation("eat", duration_ms)
        self.say("嗷呜嗷呜！🍖", duration_ms)
        self.play_sound("eat")
        if grant_xp:
            self.add_xp(effects["feed_xp"])
        save_state(self.state)
        self.refresh_pose_from_state()

    def play(self, _checked=False, *, grant_xp=True):
        if self.state["sleeping"]:
            self.say("呼…睡着呢💤"); return
        effects = progression.upgrade_effects(self.state)
        if (
            self.state["energy"] < 15
            and effects["play_energy_cost"] > 0
        ):
            self.say("没力气了…"); return
        if self.play_scene is not None:
            try:
                self.play_scene.raise_()
            except RuntimeError:
                self.play_scene = None
            return
        self.state["mood"] = min(
            100, self.state["mood"] + effects["play_mood"]
        )
        self.state["energy"] = max(
            0, self.state["energy"] - effects["play_energy_cost"]
        )
        self.state["hunger"] = max(
            0, self.state["hunger"] - effects["play_hunger_cost"]
        )
        progression.record_action(self.state, "play_sessions")
        self.behavior = "idle"
        self.target_vx = 0
        self.vx = 0
        self.vy = 0
        self.on_ground = True
        self.play_sound("bark")
        if grant_xp:
            self.add_xp(effects["play_xp"])
        save_state(self.state)
        self._play_return_pos = QPoint(self.pos())
        scene = FetchPlayScene(self, self._on_play_scene_finished)
        self.play_scene = scene
        self.hide()
        scene.start()

    def _restore_after_play(self, show_pet):
        if self._play_return_pos is not None:
            self.move(QPoint(self._play_return_pos))
        self._play_return_pos = None
        self.behavior = "idle"
        self.target_vx = 0
        self.vx = 0
        self.vy = 0
        self.on_ground = True
        self.pose = POSE["idle"]
        self.next_behavior_at = time.time() + random.uniform(2, 5)
        self.refresh_pose_from_state()
        if show_pet:
            self.show()
            self.raise_()

    def _on_play_scene_finished(self, scene, completed):
        if scene is not self.play_scene:
            return
        self.play_scene = None
        self._restore_after_play(show_pet=True)
        if completed:
            progression.record_action(self.state, "fetch_catches")
            save_state(self.state)
            self.say(random.choice([
                "接住啦！🎾",
                "嘿！我扑到球啦～",
                "汪汪，再来一次！",
            ]), 1900)
            self.play_sound("bark")

    def cancel_play_scene(self, show_pet=True):
        scene = self.play_scene
        if scene is None:
            return False
        self.play_scene = None
        try:
            scene.cancel(notify=False)
        except RuntimeError:
            pass
        self._restore_after_play(show_pet=show_pet)
        return True

    def toggle_sleep(self):
        was_sleeping = bool(self.state.get("sleeping"))
        self.state["sleeping"] = not was_sleeping
        self._auto_sleep_phase = None
        self._auto_sleep_target_x = None
        if self.state["sleeping"]:
            # Manual sleep is intentionally excluded from automatic wake-up.
            self.state["sleep_mode"] = "manual"
            progression.record_sleep(self.state, "manual")
            self.behavior = "idle"; self.target_vx = 0; self.vx = 0
            self.say("晚安主人，我会乖乖睡到你叫醒我～", 2400)
            self.play_sound("sleep")
        else:
            self.state["sleep_mode"] = None
            self._auto_sleep_snooze_until = time.time() + 45.0
            self.say("醒来啦！又可以陪主人了～", 2000)
            self.play_sound("bark")
        save_state(self.state)
        self.refresh_pose_from_state()

    def wake_from_shake(self):
        """Wake the sleeping pet after a deliberate left-right shake."""
        if not self.state.get("sleeping"):
            return False
        self.state["sleeping"] = False
        self.state["sleep_mode"] = None
        self._auto_sleep_phase = None
        self._auto_sleep_target_x = None
        self._auto_sleep_snooze_until = time.time() + 60.0
        self._woke_from_shake = True
        progression.record_action(self.state, "wake_shakes")
        self._wake_shake.reset()
        self._animation_override_token += 1
        self._animation_override = None
        self._active_animation = None
        self._animation_started_at = time.monotonic()
        self.behavior = "drag" if self.dragging else "idle"
        self.say(random.choice([
            "唔……被你摇醒啦！☀️",
            "汪呜？天亮了吗～",
            "醒啦醒啦，抱稳我呀～",
        ]), 2200)
        self.play_sound("bark")
        save_state(self.state)
        self.refresh_pose_from_state()
        self.update()
        return True

    def pet_click(self):
        """Called when user clicks (not drags) on the dog."""
        if self.state["sleeping"]:
            self.say("嘘…在睡觉💤"); return
        effects = progression.upgrade_effects(self.state)
        self.state["mood"] = min(
            100, self.state["mood"] + effects["pet_mood"]
        )
        progression.record_action(self.state, "pettings")
        self.last_user_t = time.time()
        self.say(random.choice(["汪汪！","好舒服～","再摸摸！","嘿嘿","爱你哟","蹭蹭你"]),
                 random.randint(1000, 1800))
        self.play_sound("pet")
        # Play every petting frame once, then return to the current state.
        self.pose = POSE["happy"]
        self.trigger_animation("pet")
        self.add_xp(effects["pet_xp"])
        save_state(self.state)

    def contextMenuEvent(self, event):
        """Right-click on the pet -> show the radial bubble menu."""
        self._bubble_menu = BubbleMenu(self)
        super().contextMenuEvent(event)

    def chat(self):
        """Open the chat panel beside the pet."""
        if self.chat_win is None:
            self.chat_win = ChatWindow(self)
            # connect AI bridge signals to chat window slots
            bridge.token.connect(self.chat_win.on_token)
            bridge.done.connect(self.chat_win.on_done)
            bridge.error.connect(self.chat_win.on_error)
        self.chat_win.mem = ai.load_memory()
        self.chat_win.show_near_pet()
        # mark user activity
        self.last_user_t = time.time()

    def open_records(self):
        """Open the lifetime companion record panel."""
        if self.records_win is None:
            self.records_win = RecordsWindow(self, save_state)
        self.records_win.show_near_pet()

    def open_achievements(self):
        """Open claimable and upcoming Pet-coin achievements."""
        if self.achievements_win is None:
            self.achievements_win = AchievementsWindow(self, save_state)
        self.achievements_win.show_near_pet()

    def open_shop(self):
        """Open the Pet-coin shop and interaction upgrades."""
        if self.shop_win is None:
            self.shop_win = ShopWindow(self, save_state)
        self.shop_win.show_near_pet()

    def open_minigames(self):
        """Open the expandable mini-game picker."""
        if self.minigames_win is None:
            self.minigames_win = MiniGameHubWindow(self, save_state)
        self.minigames_win.show_near_pet()

    def open_settings(self):
        """Open the settings panel."""
        if self.settings_win is None:
            self.settings_win = SettingsWindow(self)
        else:
            self.settings_win.s = self.settings
        self.settings_win.show()
        self.settings_win.raise_()
        self.settings_win.activateWindow()

    def check_ai_nudge(self):
        """Called from autonomy timer; maybe send a proactive AI nudge."""
        if self.state.get("sleeping"):
            return
        s = self.settings
        idle = time.time() - self.last_user_t
        if idle < s["nudge_idle_min"]:
            return
        # only check every 5 min
        if time.time() - self.last_nudge_check < 300:
            return
        self.last_nudge_check = time.time()
        mem = ai.load_memory()
        # pass settings to maybe_nudge so it respects nudge_gap_min
        msg = ai.maybe_nudge(
            mem,
            idle,
            pet_state=self.state,
            idle_min=s["nudge_idle_min"],
            gap_min=s["nudge_gap_min"],
            pet_name=self.pet_name,
        )
        if msg:
            # show as a longer speech bubble; do not call AI to save quota
            self.say(msg, 4500)
            self.last_user_t = time.time() - (s["nudge_idle_min"] - 100)


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

        # Defer the progress dialog until the confirmation button's mouse
        # release has been fully processed.  Otherwise Qt can deliver that
        # release to the newly-created dialog's Cancel button and immediately
        # set the download cancellation event.
        QTimer.singleShot(
            0, lambda update_info=info: self._start_update_download(update_info)
        )

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
                    # double click: cancel pending single click, open chat
                    if self._pending_single_click is not None:
                        self._pending_single_click.stop()
                        self._pending_single_click = None
                    self._last_left_click_t = 0
                    self.pet.chat()
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
            self._show_pet_menu(e.globalPos())
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
        if self.pet.isVisible():
            self.pet.hide_overlays()
            self.pet.hide()
        else:
            self.pet.show()

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

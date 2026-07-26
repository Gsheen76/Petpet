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
VERSION = "1.2.3"
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_FROZEN = bool(getattr(sys, "frozen", False))
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QTextEdit, QMenu, QAction,
    QSystemTrayIcon, QVBoxLayout, QHBoxLayout, QPushButton, QFrame,
    QGroupBox, QSpinBox, QDoubleSpinBox, QMessageBox, QProgressBar,
    QProgressDialog, QComboBox, QScrollArea, QAbstractSpinBox,
    QAbstractButton
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
POSE_NAMES = ["idle", "happy", "sad", "eat", "sleep", "drag", "close"]
POSE = {name: i for i, name in enumerate(POSE_NAMES)}
CELL = 200  # each pose is 200x200; spritesheet is 1200x200

DEFAULT_ANIMATIONS = {
    "idle":  {"fps": 5,  "loop": True,  "fallback": "idle"},
    "walk":  {"fps": 6,  "loop": True,  "fallback": "idle",
              "scale": 1.56, "anchor_bottom": True},
    "eat":   {"fps": 4,  "loop": True,  "fallback": "eat",
              "scale": 1.2, "anchor_bottom": True,
              "saturation": 0.9, "brightness": 0.97},
    "play":  {"fps": 10, "loop": False, "fallback": "happy"},
    "happy": {"fps": 8,  "loop": True,  "fallback": "happy"},
    "sleep": {"fps": 2.4, "loop": True,  "fallback": "sleep",
              "scale": 0.8, "anchor_bottom": True},
    "drag":  {"fps": 6,  "loop": True,  "fallback": "drag"},
    "sad":   {"fps": 5,  "loop": True,  "fallback": "sad"},
    "sit":   {"fps": 6,  "loop": True,  "fallback": "idle"},
    "ask":   {"fps": 8,  "loop": False, "fallback": "idle"},
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


# ---------- state ----------
DEFAULT_STATE = {
    "hunger": 80, "mood": 70, "energy": 90,
    "x": None, "y": None, "sleeping": False, "born": time.time(),
    "autostart": False,
    "level": 1, "xp": 0,
    "pet_name": ai.DEFAULT_PET_NAME,
    "tutorial_completed": False,
}

# XP needed to go from level L to L+1: 100 * L^1.5 (slowing curve)
def xp_to_next(level):
    return int(100 * (level ** 1.5))

# passive XP per tick based on average stat (0..100). Tick = 60s.
# avg=100 -> +6 xp/min; avg=50 -> +1.5 xp/min; avg=0 -> +0
def passive_xp(hunger, mood, energy):
    avg = (hunger + mood + energy) / 3.0
    return avg * 0.06

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
            return state
    except Exception:
        return dict(DEFAULT_STATE)

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

    def _apply_style(self):
        # The chat window has its own user-controlled font setting. Keep it
        # independent from the compact pet-surface enlargement.
        fs = independent_font_px(self.s["chat_font_size"])
        self.setStyleSheet(f"""
            QWidget#chat {{
                background:#fff8ec;
                border:1px solid #efc5a5;
                border-radius:20px;
            }}
            QTextEdit {{
                background:#fffdf8;
                border:1px solid #f0d8c2;
                border-radius:16px;
                padding:12px;
                font-family:'Microsoft YaHei',sans-serif;
                font-size:{fs}px;
                color:#5f463b;
                selection-background-color:#ffc9b8;
            }}
            QLineEdit {{
                background:#ffffff;
                border:1px solid #edcdb3;
                border-radius:15px;
                padding:9px 13px;
                font-family:'Microsoft YaHei',sans-serif;
                font-size:{fs}px;
                color:#65483b;
            }}
            QLineEdit:focus {{ border:2px solid #f39b80; }}
            QPushButton#send {{
                background:#f28f76; color:#fff; border:0;
                border-radius:15px;
                padding:9px 22px; font-weight:700; font-size:{fs}px;
            }}
            QPushButton#send:hover {{ background:#f59f88; }}
            QPushButton#send:disabled {{ background:#d9c6bb; }}
            QPushButton#send:pressed {{ background:#df7d67; }}
            QPushButton#clear {{
                background:transparent; color:#b58b79; border:0;
                padding:5px 9px; font-size:{max(fs-3,10)}px;
            }}
            QPushButton#clear:hover {{ color:#d96868; background:#ffebe5; border-radius:10px; }}
            QLabel#title {{
                font-size:{fs+2}px; font-weight:700; color:#7a4d3b;
                padding:6px 12px;
            }}
        """)

        # title bar (draggable) — title label on the left, close button on the right
        self.title = QLabel(f"  🐶 {self._pet_name()}")
        self.title.setObjectName("title")
        self.title.setFixedHeight(38)
        self.title.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #fff0df, stop:1 #ffe2d8);"
            "color:#7a4d3b;"
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

        # chat history
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setText(self._render_history())

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

        self.clear_btn = QPushButton("清除记忆")
        self.clear_btn.setObjectName("clear")
        self.clear_btn.setToolTip(
            f"让 {self._pet_name()} 忘记所有对话"
        )
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.confirm_clear_memory)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 4, 0)
        bottom_row.addStretch(1)
        bottom_row.addWidget(self.clear_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)
        layout.addLayout(title_row)
        layout.addWidget(self.log, 1)
        layout.addLayout(row)
        layout.addLayout(bottom_row)

    def refresh_pet_name(self):
        """Refresh every visible name after onboarding or renaming."""
        name = self._pet_name()
        self.mem["pet_name"] = name
        self.title.setText(f"  🐶 {name}")
        self.clear_btn.setToolTip(f"让 {name} 忘记所有对话")
        if not self.busy:
            self.input.setPlaceholderText(f"跟 {name} 说点什么…")

    def _render_history(self, exclude_last_assistant=False):
        """Render last N turns as HTML chat bubbles.
        exclude_last_assistant: drop the trailing assistant turn (used while streaming).
        """
        hs = list(self.mem.get("history", []))[-20:]
        if exclude_last_assistant and hs and hs[-1]["role"] == "assistant":
            hs = hs[:-1]
        if not hs:
            return '<div style="color:#bbb;text-align:center;padding:20px;">🐶 汪！来聊聊吧～</div>'
        html = []
        for h in hs:
            html.append(self._bubble_html(h["role"], h["content"]))
        return "".join(html)

    def _bubble_html(self, role, text):
        # Keep bubbles proportional to the selected chat window size.
        W = max(260, min(620, int(self.width() * 0.72)))
        if role == "user":
            return (f'<div style="margin:6px 0;text-align:right;">'
                    f'<span style="background:#f28f76;color:#fff;padding:8px 14px;'
                    f'border-radius:14px 14px 4px 14px;display:inline-block;'
                    f'max-width:{W}px;white-space:pre-wrap;'
                    f'box-shadow:0 1px 2px rgba(242,143,118,0.25);">{_esc(text)}</span></div>')
        return (f'<div style="margin:6px 0;text-align:left;">'
                f'<span style="background:#fff0df;color:#5f463b;padding:8px 14px;'
                f'border-radius:14px 14px 14px 4px;display:inline-block;'
                f'max-width:{W}px;white-space:pre-wrap;">'
                f'🐶 {_esc(text)}</span></div>')

    def _set_log_html(self, html):
        self.log.setHtml(html)
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

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
        self.input.clear()
        # add user bubble immediately
        self._pending_user = text
        self._streaming = ""
        self._set_log_html(self._render_history(exclude_last_assistant=False)
                           + self._bubble_html("user", text)
                           + self._bubble_html("assistant", "🐶 …"))
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
        # rebuild: history (incl. user turn just added via append_history below? no —
        # we haven't saved yet) + pending user bubble + streaming assistant bubble
        html = (self._render_history()
                + self._bubble_html("user", self._pending_user)
                + self._bubble_html("assistant", self._streaming + "▍"))
        self._set_log_html(html)

    def on_done(self, full):
        # commit to memory
        ai.append_history(self.mem, "user", self._pending_user)
        ai.append_history(self.mem, "assistant", full)
        self.mem = ai.load_memory()
        self._pending_user = None
        self._streaming = ""
        self.busy = False
        self.send_btn.setEnabled(True)
        self.input.setPlaceholderText(
            f"跟 {self._pet_name()} 说点什么…"
        )
        self.input.setFocus()
        self._set_log_html(self._render_history())
        # also show a speech bubble on the pet
        short = full if len(full) < 40 else full[:38] + "…"
        self.pet.say(short, 3000)

    def on_error(self, reply):
        if self._pending_user:
            ai.append_history(self.mem, "user", self._pending_user)
            ai.append_history(self.mem, "assistant", reply)
        self.mem = ai.load_memory()
        self._pending_user = None
        self._streaming = ""
        self.busy = False
        self.send_btn.setEnabled(True)
        self.input.setPlaceholderText(
            f"跟 {self._pet_name()} 说点什么…"
        )
        self._set_log_html(self._render_history())
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
            self._set_log_html('<div style="color:#bbb;text-align:center;padding:20px;">🐶 汪？你是…我们重新认识一下吧。</div>')
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
        self.setFixedSize(620, 330)
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
        title_rect = QRectF(27, 15, 330, 40)
        p.setPen(QColor("#7b4d3a"))
        p.setFont(pixel_font(16, QFont.Bold))
        p.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter,
                   f"🐾 {self.pet.pet_name} 的小屋")

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
        p.setPen(QColor("#8a6654"))
        p.setFont(pixel_font(10, QFont.Bold))
        p.drawText(QRectF(xp_area_x, 76, 104, 23),
                   Qt.AlignLeft | Qt.AlignVCenter, "经验")
        xp_text = f"{xp} / {need} EXP"
        xp_value_rect = QRectF(xp_area_x + 108, 76, xp_area_w - 108, 23)
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
        card_y = 157
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
    """Five soft candy-style action buttons with a warm growth card."""
    PRIMARY_ACTIONS = [
        ("💬", "聊天", "chat", "#ef8fa2"),
        ("🍖", "喂食", "feed", "#f49a62"),
        ("🎾", "玩耍", "play", "#72bf9b"),
        ("💤", "睡觉", "sleep", "#9b8ade"),
        ("⋯", "更多", "more", "#e7ae64"),
    ]
    MORE_ACTIONS = [
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
        self.W = 590 if self.page == "primary" else max(
            480, len(self.actions) * 102 + (len(self.actions) - 1) * 10 + 40
        )
        self.H = 112
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

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._bubble_rects = []
        n = len(self.actions)
        button_w = 102
        button_h = 78
        gap = 10
        total_w = n * button_w + (n - 1) * gap
        start_x = (self.W - total_w) / 2
        cy = self.H / 2
        for i, (emoji, label, action, color) in enumerate(self.actions):
            bx = start_x + i * (button_w + gap)
            scale = 1.0 + self._hover_scales[i] * 0.07
            if self._press == i:
                scale *= 0.96
            bw = button_w * scale
            bh = button_h * scale
            rect = QRectF(
                bx + (button_w - bw) / 2,
                cy - bh / 2,
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
        w = fm.horizontalAdvance(label) + 52
        h = fm.height() + 30
        self.resize(w + 10, h + 10)  # extra room for shadow + pulse
        self.label = label
        self._pulse = 0.0
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
        else:
            # Bubble is on the left, so shift it right toward the pet.
            x = g.left() - self.width() - 8 + toward_pet
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
        margin = 5
        return QRectF(
            margin, margin,
            self.width() - margin * 2,
            self.height() - margin * 2 - 4,
        )

    def _trigger(self):
        """Execute the action and pop a BonusBubble with explicit deltas.
        Compute deltas from before/after state so feedback is always shown,
        even if the pet was sleeping (we wake it first)."""
        pet = self.pet
        before = dict(pet.state)
        acted = True
        # wake the pet if sleeping, so feed/play actually take effect
        if pet.state.get("sleeping") and self.action_name in ("feed", "play"):
            pet.state["sleeping"] = False
            pet.refresh_pose_from_state()
        if self.action_name == "feed":
            pet.feed()
        elif self.action_name == "play":
            if pet.state["energy"] < 15:
                pet.state["mood"] = min(100, pet.state["mood"] + 6)
                pet.say("没力气…摸摸我也行", 1500)
                acted = False
            else:
                pet.play()
        elif self.action_name == "sleep":
            pet.state["energy"] = min(100, pet.state["energy"] + 30)
            pet.say("小憩一下 💤", 1800)
            pet.refresh_pose_from_state()
            pet.add_xp(5)
            save_state(pet.state)

        # compute deltas from before vs after state
        deltas = []
        labels = {"hunger":"饱腹", "mood":"心情", "energy":"精力"}
        for k, name in labels.items():
            d = pet.state.get(k, 0) - before.get(k, 0)
            if abs(d) >= 0.5:
                sign = "+" if d > 0 else ""
                deltas.append(f"{name}{sign}{int(round(d))}")

        xp_gain = 15 if (self.action_name == "play" and acted) else 10
        leveled_up = pet.add_xp(xp_gain)

        parts = list(deltas)
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
        # pulse scale: gentle breathing 1.0 -> 1.05
        scale = 1.0 + math.sin(self._pulse) * 0.03
        cx, cy = self.width() / 2, self.height() / 2
        p.translate(cx, cy)
        p.scale(scale, scale)
        p.translate(-cx, -cy)
        # main oval
        r = self._ellipse_rect()
        # soft outer glow (pulse-driven)
        glow_alpha = int(60 + math.sin(self._pulse) * 20)
        c = QColor(self.color)
        glow = QColor(c); glow.setAlpha(glow_alpha)
        p.setBrush(glow)
        p.setPen(Qt.NoPen)
        p.drawEllipse(r.adjusted(-2, -2, 2, 2))
        # shadow
        shadow = QRectF(r.x()+2, r.y()+3, r.width(), r.height())
        p.setBrush(QColor(0, 0, 0, 50))
        p.setPen(Qt.NoPen)
        p.drawEllipse(shadow)
        # gradient oval
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, c.lighter(135))
        grad.setColorAt(1.0, c)
        p.setBrush(grad)
        p.setPen(QPen(c.darker(150), 1.0))
        p.drawEllipse(r)
        # inner highlight (top gloss)
        gloss = QRectF(r.x()+10, r.y()+3, r.width()-20, r.height()/2.2)
        gloss_grad = QLinearGradient(gloss.topLeft(), gloss.bottomLeft())
        gloss_grad.setColorAt(0.0, QColor(255, 255, 255, 90))
        gloss_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(gloss_grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(gloss)
        # white text with subtle shadow
        p.setPen(QColor(0, 0, 0, 80))
        p.setFont(self.font())
        text_rect = QRectF(r.x(), r.y()+1, r.width(), r.height())
        p.drawText(text_rect, Qt.AlignCenter, self.label)
        p.setPen(QColor(255, 255, 255))
        p.drawText(r, Qt.AlignCenter, self.label)

    def enterEvent(self, e):
        self.setCursor(Qt.PointingHandCursor)


def _esc(text):
    """HTML-escape user content for safe bubble rendering."""
    return (text.replace("&","&amp;").replace("<","&lt;")
                .replace(">","&gt;").replace("\n","<br>"))


class SpeechBubble(QWidget):
    """A single-line speech bubble that grows horizontally with its text."""
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
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text, ms):
        # Flatten all input so the bubble can never wrap onto a second line.
        # Stop the previous countdown first.  Rapid clicks can otherwise leave
        # an old timeout queued while the same translucent window is resized.
        self._hide_timer.stop()
        text = " ".join(str(text).replace("\r", "\n").splitlines()).strip()
        screen = self.pet.current_screen_rect()
        fm = self.fontMetrics()
        padding_x = 18
        max_text_width = max(80, screen.width() - padding_x * 2 - 24)
        self.text = fm.elidedText(text, Qt.ElideRight, max_text_width)
        text_width = fm.horizontalAdvance(self.text)
        width = text_width + padding_x * 2 + 10
        height = fm.height() + 28
        self.setGeometry(self._bubble_geometry(width, height))
        if not self.isVisible():
            self.show()
        self.raise_()
        # A synchronous full repaint prevents Windows' translucent backing
        # surface from briefly retaining the old width after rapid updates.
        self.repaint()
        self._hide_timer.start(max(1, int(ms)))

    def follow_pet(self):
        if not self.pet.isVisible():
            self.hide()
            return
        rect = self._bubble_geometry(self.width(), self.height())
        self.move(rect.topLeft())

    def _bubble_geometry(self, width, height):
        """Return one complete on-screen geometry for an atomic update."""
        g = self.pet.geometry()
        screen = self.pet.current_screen_rect()
        x = g.center().x() - width // 2
        # Keep the one-line bubble inside the pet window's reserved head space.
        y = g.top() + 3
        x = max(screen.left() + 4, min(x, screen.right() - width - 4))
        y = max(screen.top() + 4, min(y, screen.bottom() - height - 4))
        return QRect(int(x), int(y), int(width), int(height))

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
                   Qt.AlignVCenter | Qt.AlignHCenter | Qt.TextSingleLine,
                   self.text)


class PetWindow(QWidget):
    flung = pyqtSignal()

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.settings = load_settings()
        self.PET_W, self.PET_H = 190, 220
        self.DOG_H = 160  # actual dog drawing height; top 60px is bubble space
        self.scale = 0.8  # render scale

        # transparent, frameless, always-on-top, no taskbar button, tool window
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus
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

        # Optional multi-frame actions. Each action lives in
        # assets/animations/<action>/ and falls back to the static pose above.
        self.animation_specs = {}
        self.animation_frames = {}
        self._active_animation = None
        self._animation_started_at = time.monotonic()
        self._animation_override = None
        self._animation_override_token = 0
        self._load_animations()

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
        self.next_behavior_at = time.time() + random.uniform(3, 7)

        # AI: track idle time for proactive nudges
        self.last_user_t = time.time()
        self.last_nudge_check = time.time()
        self.chat_win = None  # lazy-created on first chat
        self.settings_win = None  # lazy-created on first settings open
        self._interactive_bubble = None  # current floating action bubble
        self._bubble_menu = None         # radial bubble menu (right-click)
        self._last_interactive_t = 0.0   # throttle: don't spam
        self._ctx_menu_cb = None  # set by TrayApp to provide a right-click menu
        self._settings_applied_cb = None
        self._app_action_cb = None

        # Single-line speech bubble is a separate window so it can grow wider
        # than the pet widget without clipping or wrapping.
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

        # passive XP accrual (every 60s, based on average stat)
        self.xp_timer = QTimer(self)
        self.xp_timer.timeout.connect(self.on_passive_xp)
        self.xp_timer.start(60000)

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

    def add_xp(self, amount):
        """Add XP, level up if threshold met. Returns True if leveled up."""
        if amount <= 0:
            return False
        self.state["xp"] = self.state.get("xp", 0) + amount
        leveled = False
        while True:
            need = xp_to_next(self.state.get("level", 1))
            if self.state["xp"] >= need:
                self.state["xp"] -= need
                self.state["level"] = self.state.get("level", 1) + 1
                leveled = True
            else:
                break
        save_state(self.state)
        return leveled

    def on_passive_xp(self):
        """Passive XP from keeping stats high (rewards good care)."""
        if self.state.get("sleeping"):
            # sleeping gives half passive XP
            gain = passive_xp(self.state["hunger"], self.state["mood"], self.state["energy"]) * 0.5
        else:
            gain = passive_xp(self.state["hunger"], self.state["mood"], self.state["energy"])
        if gain <= 0:
            return
        leveled = self.add_xp(int(round(gain)))
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

    def apply_window_flags(self):
        """Toggle always-on-top based on settings. Call after settings change."""
        on_top = self.settings.get("always_on_top", True)
        was_visible = self.isVisible()
        if on_top:
            self.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                Qt.Tool | Qt.WindowDoesNotAcceptFocus
            )
        else:
            self.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.Tool | Qt.WindowDoesNotAcceptFocus
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
            chat._set_log_html(chat._render_history())
            if chat.isVisible():
                chat.show_near_pet()
                chat.update()
                chat.repaint()

        if callable(self._settings_applied_cb):
            self._settings_applied_cb(previous, self.settings)

    def is_visible_on_screen(self):
        g = self.geometry()
        s = self.screen_rect()
        # at least 30x30 px overlap with screen
        ox = max(0, min(g.right(), s.right()) - max(g.left(), s.left()))
        oy = max(0, min(g.bottom(), s.bottom()) - max(g.top(), s.top()))
        return ox >= 30 and oy >= 30

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

    def trigger_animation(self, name, duration_ms):
        """Temporarily override state-driven animation for an interaction."""
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
        if self.behavior == "walk":
            return "walk"
        if self.behavior in ("sit", "ask"):
            return self.behavior
        return POSE_NAMES[self.pose]

    def _animation_frame(self, name):
        frames = self.animation_frames.get(name)
        if not frames:
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
        return frames[index]

    def _fallback_pose(self, animation_name):
        spec = self.animation_specs.get(animation_name, {})
        fallback = str(spec.get("fallback", animation_name))
        return POSE.get(fallback, self.pose)

    # ---------- painting ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # Determine action animation and its static fallback.
        animation_name = self._current_animation_name()
        pose = self._fallback_pose(animation_name)
        animation_pixmap = self._animation_frame(animation_name)
        # blink: briefly switch to "close" (eyes-closed) pose if available
        if self.blink and pose in (POSE["idle"], POSE["happy"]):
            pose = POSE["close"]
            animation_pixmap = None

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

        if self.facing < 0:
            p.restore()

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
        if self._speech_bubble is None:
            self._speech_bubble = SpeechBubble(self)
        self._speech_bubble.show_text(text, ms)

    def hide_overlays(self):
        """Close every detached bubble that visually belongs to the pet."""
        speech = self._speech_bubble
        if speech is not None:
            try:
                speech._hide_timer.stop()
                speech.hide()
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
        G = 2200.0           # gravity, px/s^2
        GROUND_PAD = 10      # pixels above taskbar
        ground_y = screen.bottom() - h - GROUND_PAD
        BOUNCE = 0.55        # energy retained on wall bounce
        BOUNCE_FLOOR = 0.45  # energy retained on floor bounce
        FRICTION = 0.88      # per-tick ground friction
        STOP_V = 2.0         # below this, snap to 0

        if not self.dragging:
            # walking overrides gravity (stay glued to ground while walking)
            if self.behavior == "walk" and self.on_ground:
                self.vx = self.target_vx
                self.vy = 0
            else:
                # gravity always pulling down when airborne
                self.vy += G * dt

            # integrate position
            new_x = x + self.vx * dt
            new_y = y + self.vy * dt

            # ---- floor collision ----
            if new_y >= ground_y:
                if self.on_ground:
                    # already on ground; just clamp
                    new_y = ground_y
                    if self.behavior != "walk":
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
            if self.on_ground and self.behavior != "walk":
                self.vx *= FRICTION
                if abs(self.vx) < STOP_V:
                    self.vx = 0

            # ---- facing follows horizontal velocity ----
            if abs(self.vx) > 5:
                self.facing = 1 if self.vx > 0 else -1
            elif self.behavior == "walk":
                self.facing = 1 if self.target_vx > 0 else -1

            # Preserve the legacy bob only while no real walk frames exist.
            if (self.on_ground and abs(self.vx) > 20 and
                    not (self.behavior == "walk" and
                         self.animation_frames.get("walk"))):
                new_y -= abs(math.sin(time.time() * 6)) * 4

            self.move(int(new_x), int(new_y))

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

        # keep the single-line speech bubble following the pet
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

    # ---------- decay ----------
    def on_decay(self):
        s = self.settings
        if self.state["sleeping"]:
            self.state["energy"] = min(100, self.state["energy"] + s["decay_energy_sleeping_gain"])
            self.state["hunger"] = max(0, self.state["hunger"] - s["decay_hunger_sleeping"])
        else:
            self.state["hunger"] = max(0, self.state["hunger"] - s["decay_hunger"])
            self.state["energy"] = max(0, self.state["energy"] - s["decay_energy"])
            self.state["mood"] = max(0, self.state["mood"] - s["decay_mood"])
        save_state(self.state)
        self.refresh_pose_from_state()
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
        # maybe show a clickable interactive bubble when a stat is low
        if not self.state["sleeping"]:
            self.maybe_show_interactive_bubble()

    def maybe_show_interactive_bubble(self):
        """When hunger/mood/energy is low, sometimes pop a clickable action
        bubble above the pet. Clicking it performs the action and shows a
        floating '+N stat' bonus bubble."""
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
        # decide which stat is most urgent and roll the dice
        candidates = []
        if self.state["hunger"] < 40:
            candidates.append(("feed",  "🦴 喂我",   "#ff8c42", "饱腹"))
        if self.state["mood"] < 40:
            candidates.append(("play",  "🎾 陪我玩", "#4aa8ff", "心情"))
        if self.state["energy"] < 40:
            candidates.append(("sleep", "💤 让我睡", "#9b6bff", "精力"))
        if not candidates:
            return
        # ~25% chance per decay tick (every 2s) when a stat is low ->
        # feels organic, not spammy
        if random.random() > 0.25:
            return
        action, label, color, _ = random.choice(candidates)
        # bonus_text not pre-computed; computed from actual deltas on click
        self._interactive_bubble = InteractiveBubble(self, label, action, color, "")
        self._last_interactive_t = time.time()
        # also show a tiny speech line to draw attention
        if action == "feed":
            self.say("汪…好饿 🦴", 2500)
        elif action == "play":
            self.say("想玩 🎾", 2500)
        else:
            self.say("困了… 💤", 2500)

    def refresh_pose_from_state(self):
        if self.state["sleeping"]:
            self.pose = POSE["sleep"]; return
        if self.dragging:
            self.pose = POSE["drag"]; return
        if self.behavior == "eat":
            self.pose = POSE["eat"]; return
        # sad only when very low mood or very hungry
        if self.state["mood"] < 25 or self.state["hunger"] < 20:
            self.pose = POSE["sad"]; return
        # default: idle (happy is only set temporarily by interactions)
        self.pose = POSE["idle"]

    # ---------- autonomous behavior ----------
    def on_autonomy(self):
        now = time.time()
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
                weights=[4, 4, 2, ask_w],
                k=1
            )[0]
            if choice == "walk":
                self.behavior = "walk"
                self.target_vx = random.choice([-1,1]) * random.uniform(60, 180)
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
                self.behavior_until = now + random.uniform(1, 3)
            self.next_behavior_at = self.behavior_until + random.uniform(2, 6)
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
    def feed(self):
        if self.state["sleeping"]:
            self.say("呼…睡着呢💤"); return
        self.state["hunger"] = min(100, self.state["hunger"] + 25)
        self.state["mood"] = min(100, self.state["mood"] + 6)
        self.behavior = "eat"
        self.behavior_until = time.time() + 1.8
        self.trigger_animation("eat", 1800)
        self.say("嗷呜嗷呜！🍖", 1800)
        self.play_sound("eat")
        self.add_xp(8)
        save_state(self.state)
        self.refresh_pose_from_state()

    def play(self):
        if self.state["sleeping"]:
            self.say("呼…睡着呢💤"); return
        if self.state["energy"] < 15:
            self.say("没力气了…"); return
        self.state["mood"] = min(100, self.state["mood"] + 20)
        self.state["energy"] = max(0, self.state["energy"] - 12)
        self.state["hunger"] = max(0, self.state["hunger"] - 5)
        # jump!
        self.vy = -950
        self.vx = random.choice([-1,1]) * 350
        self.on_ground = False
        self.trigger_animation("play", 1500)
        self.say("汪汪！接球！🎾", 1500)
        self.play_sound("bark")
        self.add_xp(12)
        save_state(self.state)
        # happy pose briefly, then back to idle
        self.pose = POSE["happy"]
        QTimer.singleShot(1500, self.refresh_pose_from_state)

    def toggle_sleep(self):
        self.state["sleeping"] = not self.state["sleeping"]
        if self.state["sleeping"]:
            self.behavior = "idle"; self.target_vx = 0; self.vx = 0
            self.say("zzz…晚安💤", 2000)
            self.play_sound("sleep")
        else:
            self.say("精神百倍！☀️", 1800)
            self.play_sound("bark")
        save_state(self.state)
        self.refresh_pose_from_state()

    def wake_from_shake(self):
        """Wake the sleeping pet after a deliberate left-right shake."""
        if not self.state.get("sleeping"):
            return False
        self.state["sleeping"] = False
        self._woke_from_shake = True
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
        self.state["mood"] = min(100, self.state["mood"] + 8)
        self.last_user_t = time.time()
        self.say(random.choice(["汪汪！","好舒服～","再摸摸！","嘿嘿","爱你哟","蹭蹭你"]),
                 random.randint(1000, 1800))
        self.play_sound("pet")
        # happy pose briefly
        self.pose = POSE["happy"]
        self.trigger_animation("happy", 1200)
        QTimer.singleShot(1200, self.refresh_pose_from_state)
        self.add_xp(3)
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
        if s["hunger"] < 100: candidates.append(("feed",  "🦴 喂我",   "#ff8c42"))
        if s["mood"]   < 100: candidates.append(("play",  "🎾 陪我玩", "#4aa8ff"))
        if s["energy"] < 100: candidates.append(("sleep", "💤 让我睡", "#9b6bff"))
        if not candidates: return
        # choose the lowest
        order = {"feed": s["hunger"], "play": s["mood"], "sleep": s["energy"]}
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

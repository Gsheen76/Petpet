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
import sys, os, math, time, json, random, threading, urllib.request, urllib.error

# ---------- version & update ----------
VERSION = "1.1.1"
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
APP_NAME = "Petpet"
MAC_BUNDLE_ID = "com.gsheen.petpet"
# GitHub Releases API endpoint. Replace USER/REPO with your repo.
# Format: https://api.github.com/repos/USER/REPO/releases/latest
RELEASES_URL = "https://api.github.com/repos/Gsheen76/Petpet/releases/latest"


def select_release_asset(assets, platform_name=None):
    """Return the download URL for the current platform's release asset."""
    platform_name = platform_name or sys.platform
    for asset in assets:
        name = (asset.get("name") or "").lower()
        if platform_name.startswith("win") and name.endswith(".exe"):
            return asset.get("browser_download_url")
        if (platform_name == "darwin" and
                ("mac" in name or "darwin" in name) and
                name.endswith((".dmg", ".zip"))):
            return asset.get("browser_download_url")
    if not (platform_name.startswith("win") or platform_name == "darwin"):
        return assets[0].get("browser_download_url") if assets else None
    return None


def check_update_async(on_result):
    """Check GitHub Releases for a newer version. Runs in background thread.
    on_result(info_or_None) is called on the main thread via QTimer.
    info = {'version':str, 'download_url':str, 'notes':str} or None if no update."""
    def worker():
        try:
            req = urllib.request.Request(RELEASES_URL, headers={
                "User-Agent": "SheenPet/%s" % VERSION,
                "Accept": "application/vnd.github+json",
            })
            r = urllib.request.urlopen(req, timeout=10)
            data = json.loads(r.read().decode("utf-8"))
            tag = (data.get("tag_name") or "").lstrip("v")
            assets = data.get("assets", [])
            dl_url = select_release_asset(assets)
            notes = (data.get("body") or "")[:500]
            if tag and tag != VERSION and dl_url:
                # compare version: simple string compare works for "1.2.3"
                # but to be safe, compare tuples
                def parse(s): return tuple(int(x) for x in s.split(".") if x.isdigit())
                try:
                    if parse(tag) > parse(VERSION):
                        info = {"version": tag, "download_url": dl_url, "notes": notes}
                    else:
                        info = None
                except Exception:
                    if tag > VERSION:
                        info = {"version": tag, "download_url": dl_url, "notes": notes}
                    else:
                        info = None
            else:
                info = None
        except Exception as e:
            info = None
        # marshal back to main thread
        QTimer.singleShot(0, lambda: on_result(info))
    threading.Thread(target=worker, daemon=True).start()


def download_and_update(download_url, on_progress=None):
    """Download new exe to <name>_new.exe next to current exe, then run
    update.bat which replaces the running exe and restarts.
    Returns True on success (will have quit the app)."""
    if not IS_WINDOWS:
        return False  # macOS updates are downloaded via the browser
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        cur_exe = sys.executable
    else:
        return False  # dev mode, no update
    new_path = os.path.join(exe_dir, os.path.basename(cur_exe).replace(".exe", "_new.exe"))
    try:
        req = urllib.request.Request(download_url, headers={"User-Agent": "SheenPet"})
        r = urllib.request.urlopen(req, timeout=60)
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(new_path, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk: break
                f.write(chunk)
                done += len(chunk)
                if on_progress and total:
                    on_progress(done, total)
        # write update.bat
        bat = os.path.join(exe_dir, "update_sheen.bat")
        with open(bat, "w", encoding="ascii") as f:
            f.write('@echo off\r\n')
            f.write('timeout /t 2 /nobreak >nul\r\n')
            f.write('del "%s"\r\n' % cur_exe)
            f.write('ren "%s" "%s"\r\n' % (new_path, os.path.basename(cur_exe)))
            f.write('start "" "%s"\r\n' % cur_exe)
            f.write('del "%s"\r\n' % bat)
        # launch the bat and quit
        import subprocess
        subprocess.Popen(['cmd', '/c', bat], cwd=exe_dir,
                         creationflags=0x08000000)  # CREATE_NO_WINDOW
        return True
    except Exception as e:
        try: os.remove(new_path)
        except Exception: pass
        return False
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QTextEdit, QMenu, QAction,
    QSystemTrayIcon, QVBoxLayout, QHBoxLayout, QPushButton, QFrame,
    QGroupBox, QSpinBox, QDoubleSpinBox, QMessageBox, QProgressBar
)
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtGui import (
    QPainter, QPixmap, QImage, QCursor, QIcon, QColor, QFont, QFontMetrics, QPen,
    QLinearGradient, QRadialGradient, QTextDocument, QDesktopServices
)
from PyQt5.QtCore import (
    Qt, QTimer, QPoint, QPointF, QRect, QRectF, QByteArray, QSize, pyqtSignal, QObject, QUrl
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

# ---------- paths ----------
# Resources are bundled by PyInstaller. On macOS, writable user data lives in
# ~/Library/Application Support/Petpet because the .app bundle is read-only.
if getattr(sys, 'frozen', False):
    RES_DIR = sys._MEIPASS
    if IS_MACOS:
        DATA_DIR = os.path.join(
            os.path.expanduser("~/Library/Application Support"), APP_NAME)
    else:
        DATA_DIR = os.path.dirname(sys.executable)
else:
    RES_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = RES_DIR
os.makedirs(DATA_DIR, exist_ok=True)
HERE = RES_DIR
SVG_PATH = os.path.join(RES_DIR, "pet.svg")
POSES_DIR = os.path.join(RES_DIR, "poses")
ICON_PATH = os.path.join(RES_DIR, "icons", "icon-64.png")
SAVE_PATH = os.path.join(DATA_DIR, "pet_state.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "pet_settings.json")

# Seed a safe editable config on first packaged launch.
if getattr(sys, 'frozen', False):
    _config_path = os.path.join(DATA_DIR, "config.json")
    _config_example = os.path.join(RES_DIR, "config.json.example")
    if not os.path.exists(_config_path) and os.path.exists(_config_example):
        try:
            import shutil
            shutil.copyfile(_config_example, _config_path)
        except Exception:
            pass
POSE_NAMES = ["idle", "happy", "sad", "eat", "sleep", "drag", "close"]
POSE = {name: i for i, name in enumerate(POSE_NAMES)}
CELL = 200  # each pose is 200x200; spritesheet is 1200x200

# ---------- settings (user-tunable) ----------
DEFAULT_SETTINGS = {
    "chat_width": 640,
    "chat_height": 820,
    "chat_bubble_max": 500,
    "chat_font_size": 20,
    "ui_font_size": 20,        # settings panel font size
    "always_on_top": True,     # pet window stays on top of other windows
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
        border-radius:12px;
        padding:8px;
        font-family:'Microsoft YaHei';
        font-size:14px;
    }
    QMenu::item {
        padding:8px 28px 8px 12px;
        border-radius:8px;
        margin:1px 2px;
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
        height:1px;
        background:#efd8c4;
        margin:6px 8px;
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
        # one-time migration: if user has old font values outside new range, reset them
        if not (10 <= s.get("ui_font_size", 20) <= 28):
            s["ui_font_size"] = DEFAULT_SETTINGS["ui_font_size"]
        if not (10 <= s.get("chat_font_size", 20) <= 40):
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
            return {**DEFAULT_STATE, **s}
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

    def _apply_style(self):
        fs = self.s["chat_font_size"]
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
        self.title = QLabel("  🐶 Sheen")
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
            "font-size:22px;font-weight:700;padding:0;}"
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
        self.input.setPlaceholderText("跟 Sheen 说点什么…")
        self.input.returnPressed.connect(self.send)
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("send")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self.send)

        self.clear_btn = QPushButton("清除记忆")
        self.clear_btn.setObjectName("clear")
        self.clear_btn.setToolTip("让 Sheen 忘记所有对话")
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
        W = self.s["chat_bubble_max"]  # bubble max width
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
        self.input.setPlaceholderText("Sheen 正在思考…")
        # run AI in background thread so GUI doesn't freeze
        t = threading.Thread(target=self._ai_thread, args=(text,), daemon=True)
        t.start()

    def _ai_thread(self, user_text):
        full = []
        err = None
        for kind, payload in ai.chat_stream(user_text, mem=self.mem,
                                            on_token=lambda chunk: bridge.token.emit(chunk)):
            if kind == "token":
                full.append(payload)
            elif kind == "done":
                full = [payload]
                break
            elif kind == "error":
                err = payload
                break
        if err:
            reply = ai.fallback_reply(user_text, err)
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
        self.input.setPlaceholderText("跟 Sheen 说点什么…")
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
        self.input.setPlaceholderText("跟 Sheen 说点什么…")
        self._set_log_html(self._render_history())
        self.pet.say(reply[:30], 2000)

    def confirm_clear_memory(self):
        """Ask for confirmation with Sheen's voice; on yes, wipe memory."""
        if self.busy:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Sheen · 清除记忆")
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
        self.setWindowTitle("Sheen · 温暖成长档案")
        self.setFixedSize(460, 580)

        # stats panel uses its own larger font scale (not ui_font_size)
        fs = 16
        self.setStyleSheet(f"""
            QWidget {{ background:#fff8ec; font-family:'Microsoft YaHei',sans-serif;
                       font-size:{fs}px; color:#65483b; }}
            QLabel {{ padding:2px 0; }}
            QFrame#card {{ background:#fffdf8; border:1px solid #efd1b8;
                            border-radius:17px; }}
            QProgressBar {{ background:#f3e3d5; border:0; border-radius:8px;
                            height:16px; text-align:center; color:#fff;
                            font-size:{max(11, fs-2)}px; font-weight:700; }}
            QProgressBar::chunk {{ border-radius:8px; }}
            QLabel#h1 {{ font-size:{fs+7}px; font-weight:800; color:#744d3e; }}
            QLabel#h2 {{ font-size:{fs+2}px; font-weight:700; color:#a46c58; }}
            QLabel#big {{ font-size:{fs+22}px; font-weight:900; color:#f28f76; }}
            QLabel#gold {{ font-size:{fs+1}px; font-weight:800; color:#c68a38; }}
            QLabel#small {{ font-size:{max(11,fs-2)}px; color:#aa8170; }}
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
            nm.setStyleSheet(f"font-size:{fs+1}px; font-weight:700;")
            val = QLabel()
            val.setStyleSheet(f"font-size:{fs+2}px; font-weight:800; color:{color};")
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
        lvl = st.get("level", 1)
        xp = st.get("xp", 0)
        need = xp_to_next(lvl)
        self.lvl_label.setText(f"Lv.{lvl}")
        self.title_label.setText("Sheen 的成长小屋")
        self.subtitle_label.setText(f"距离下一级：{max(0, need-xp)} EXP")
        self.subtitle_label.setObjectName("gold")
        self.subtitle_label.setStyleSheet(
            "font-size:17px; font-weight:800; color:#c68a38;")
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
                           font-size:14px; }
            QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #ffc05c, stop:0.5 #ffd36f, stop:1 #ffe59b); border-radius:9px; }
        """)
        days = max(1, int((time.time() - st.get("born", time.time())) / 86400))
        self.days_label.setText(f"♡ 已经温暖陪伴你 {days} 天")
        for key, (bar, val, color) in self.bars.items():
            v = int(st.get(key, 0))
            bar.setValue(v)
            val.setText(f"{v}/100")


class SettingsWindow(QWidget):
    """Tunable settings panel — chat window size, decay rates, chatter frequency, etc."""
    CHANGED = pyqtSignal()

    FIELDS = [
        # (key, label, min, max, step, hint)
        ("chat_width",   "聊天窗口宽度",    320, 1200, 20, "像素"),
        ("chat_height",  "聊天窗口高度",    400, 1000, 20, "像素"),
        ("chat_bubble_max", "聊天气泡最大宽度", 240, 900, 20, "像素"),
        ("chat_font_size",  "聊天字体大小",   10, 40, 1, "px (10-40)"),
        ("ui_font_size",    "设置面板字体大小", 10, 28, 1, "px (10-28)"),
        ("always_on_top",   "始终置顶 (1是 0否)",  0, 1, 1, "1=总在最前 0=可被遮挡"),
        ("sound_enabled",   "音效开关 (1开 0关)",  0, 1, 1, "1=有声 0=静音"),
        ("remind_drink_min","喝水提醒间隔(分钟)", 0, 300, 5, "0=关 60=每小时"),
        ("remind_rest_min", "休息眼睛间隔(分钟)", 0, 300, 5, "0=关 90=每1.5小时"),
        ("remind_stand_min","起身活动间隔(分钟)", 0, 300, 5, "0=关 45=每45分钟"),
        ("decay_hunger", "饱腹下降速度",     0.02, 2.0, 0.02, "每2秒降低（越小越慢）"),
        ("decay_energy", "精力下降速度",     0.02, 2.0, 0.02, "每2秒降低"),
        ("decay_mood",   "心情下降速度",     0.02, 2.0, 0.02, "每2秒降低"),
        ("needy_speak_chance", "需求自言自语概率", 0.0, 1.0, 0.05, "0=安静 1=每次都说"),
        ("ask_weight_normal", "自主搭话权重(平时)", 0.0, 3.0, 0.1, "越大越爱搭话"),
        ("ask_weight_needy",  "自主搭话权重(需要照顾)", 0.0, 3.0, 0.1, "饿了/无聊时权重"),
        ("nudge_idle_min", "AI 主动找你最短闲置(秒)", 300, 7200, 300, "多久不理它才会主动找你"),
        ("nudge_gap_min",  "AI 主动找你最小间隔(秒)", 1800, 21600, 1800, "两次主动找你的最小间隔"),
    ]

    def __init__(self, pet_window):
        super().__init__()
        self.pet = pet_window
        self.s = pet_window.settings
        self.inputs = {}

        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowTitle("Sheen · 温馨设置")
        self._apply_font()
        self._build_ui()
        self.setFixedWidth(500)

    def _apply_font(self):
        fs = self.s.get("ui_font_size", 13)
        self.setStyleSheet(f"""
            QWidget {{ background:#fff8ec; font-family:'Microsoft YaHei',sans-serif;
                       font-size:{fs}px; color:#65483b; }}
            QLabel {{ padding:4px 0; }}
            QDoubleSpinBox, QSpinBox {{
                background:#fffdf8; border:1px solid #edc9ad; border-radius:9px;
                padding:6px 8px; min-width:100px; color:#65483b;
                selection-background-color:#ffc9b8;
            }}
            QDoubleSpinBox:focus, QSpinBox:focus {{
                border:2px solid #f39b80;
            }}
            QPushButton {{
                background:#f28f76; color:#fff; border:0; border-radius:11px;
                padding:9px 18px; font-weight:700;
            }}
            QPushButton:hover {{ background:#f5a08a; }}
            QPushButton:pressed {{ background:#df7d67; }}
            QPushButton#reset {{ background:#d7b9a6; color:#6d5145; }}
            QPushButton#reset:hover {{ background:#e2c8b8; }}
            QPushButton#reset:pressed {{ background:#c9a892; }}
            QGroupBox {{
                background:#fffdf8; border:1px solid #edcfb5; border-radius:15px;
                margin-top:12px; padding:13px 12px 10px 12px;
            }}
            QGroupBox::title {{
                color:#9b6651; font-weight:700; left:14px;
                padding:0 7px; background:#fff8ec;
            }}
        """)
        self.setFixedWidth(500)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("🌼 Sheen 的温馨设置")
        title.setStyleSheet(
            "font-size:19px; font-weight:800; color:#7a4d3b; padding:0 0 7px 0;")
        layout.addWidget(title)

        layout.addWidget(self._group("🍑 界面与声音", [
            "chat_width","chat_height","chat_bubble_max","chat_font_size","ui_font_size",
            "always_on_top","sound_enabled"]))
        layout.addWidget(self._group("🌿 健康提醒", [
            "remind_drink_min","remind_rest_min","remind_stand_min"]))

        # buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        reset_btn = QPushButton("恢复默认"); reset_btn.setObjectName("reset")
        reset_btn.clicked.connect(self.reset_defaults)
        ok_btn = QPushButton("保存并应用"); ok_btn.clicked.connect(self.apply)
        btn_row.addWidget(reset_btn); btn_row.addStretch(1); btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        # status line (shows "已保存" feedback)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            "color:#cf765e; font-size:13px; font-weight:700; padding:2px 0;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        hint = QLabel("♡ 保存后立即生效，Sheen 会乖乖记住你的偏好。")
        hint.setStyleSheet("color:#aa8170; font-size:11px; padding:4px 0;")
        layout.addWidget(hint)

    def _group(self, title, keys):
        gb = QGroupBox(title)
        v = QVBoxLayout(gb); v.setSpacing(6)
        for key in keys:
            label, mn, mx, step, hint = self._field_meta(key)
            row = QHBoxLayout()
            row.setContentsMargins(0,0,0,0)
            lbl = QLabel(label)
            lbl.setMinimumWidth(150)
            # choose spinbox type by step/decimal
            if isinstance(step, float) or "." in str(step):
                sb = QDoubleSpinBox()
                sb.setDecimals(2 if step < 0.1 else (1 if step < 1 else 0))
            else:
                sb = QSpinBox()
            sb.setRange(mn, mx); sb.setSingleStep(step)
            sb.setValue(self.s.get(key, 0))
            sb.setToolTip(hint)
            self.inputs[key] = sb
            row.addWidget(lbl); row.addStretch(1); row.addWidget(sb)
            v.addLayout(row)
        return gb

    def _field_meta(self, key):
        for k, label, mn, mx, step, hint in self.FIELDS:
            if k == key: return label, mn, mx, step, hint
        return key, 0, 100, 1, ""

    def apply(self):
        for key, sb in self.inputs.items():
            val = sb.value()
            # QDoubleSpinBox may return float; convert int fields to int
            if isinstance(self.s.get(key), int):
                val = int(val)
            self.s[key] = val
        save_settings(self.s)
        # self.s IS pet.settings (same ref), so pet already sees new values.
        # But re-assign to be explicit & safe.
        self.pet.settings = self.s
        # apply always-on-top flag to pet window
        self.pet.apply_window_flags()
        # refresh this settings panel's own font live
        self._apply_font()
        # if chat window exists (open or not), update its size and style live
        if self.pet.chat_win is not None:
            cw = self.pet.chat_win
            cw.s = self.s  # re-bind to latest settings dict
            # clamp to screen
            screen = self.pet.current_screen_rect()
            w = min(self.s["chat_width"], screen.width() - 20)
            h = min(self.s["chat_height"], screen.height() - 80)
            cw.setFixedSize(w, h)
            cw._apply_style()
            cw._set_log_html(cw._render_history())
            if cw.isVisible():
                # reposition in case it no longer fits
                cw.show_near_pet()
                cw.update()
                cw.repaint()
        self.CHANGED.emit()
        self.pet.say("好啦，记住了~", 1500)
        # show an in-panel status line so user sees real feedback
        if hasattr(self, "status_label"):
            self.status_label.setText("✓ 已保存并应用")
            QTimer.singleShot(1500, lambda: self.status_label.setText(""))

    def reset_defaults(self):
        # mutate the SAME dict object so pet.settings (same ref) sees changes
        self.s.clear()
        self.s.update(DEFAULT_SETTINGS)
        save_settings(self.s)
        self.pet.settings = self.s
        # refresh UI spinboxes
        for key, sb in self.inputs.items():
            sb.setValue(self.s.get(key, 0))
        # refresh this panel's font
        self._apply_font()
        # apply to chat window if exists
        if self.pet.chat_win is not None:
            cw = self.pet.chat_win
            cw.s = self.s
            screen = self.pet.current_screen_rect()
            w = min(self.s["chat_width"], screen.width() - 20)
            h = min(self.s["chat_height"], screen.height() - 80)
            cw.setFixedSize(w, h)
            cw._apply_style()
            cw._set_log_html(cw._render_history())
            if cw.isVisible():
                cw.show_near_pet()
                cw.update(); cw.repaint()
        self.pet.say("已恢复默认~", 1500)


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
        self.setFixedSize(580, 310)
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
            font = QFont("Microsoft YaHei", size, weight)
            if QFontMetrics(font).horizontalAdvance(str(text)) <= max_width:
                return font
            size -= 1
        return QFont("Microsoft YaHei", minimum_size, weight)

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
        p.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        p.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter,
                   "🐾 Sheen 的成长小屋")

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
        p.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        p.drawText(QRectF(xp_area_x, 76, 104, 23),
                   Qt.AlignLeft | Qt.AlignVCenter, "成长经验")
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
            ("🍗", "饱腹", st.get("hunger", 0), "#f49a62",
             ("肚肚空空", "刚刚好", "肚肚饱饱")),
            ("🌷", "心情", st.get("mood", 0), "#ef8fa2",
             ("想要抱抱", "心情不错", "开心摇尾巴")),
            ("⚡", "精力", st.get("energy", 0), "#9b8ade",
             ("需要充电", "精神还好", "元气满满")),
        ]
        pad = 20
        gap = 12
        card_w = (W - pad * 2 - gap * 2) / 3
        card_y = 157
        card_h = 125
        for i, (emoji, name, val, color, moods) in enumerate(stats):
            val = max(0.0, min(100.0, float(val)))
            cx = pad + i * (card_w + gap)
            card = QRectF(cx, card_y, card_w, card_h)
            tint = QColor(color)
            tint.setAlpha(30)
            p.setBrush(tint)
            p.setPen(QPen(QColor(color).lighter(125), 1))
            p.drawRoundedRect(card, 16, 16)

            icon_rect = QRectF(cx + 13, card_y + 12, 38, 38)
            p.setBrush(QColor(255, 255, 255, 190))
            p.setPen(Qt.NoPen)
            p.drawEllipse(icon_rect)
            p.setFont(QFont("Microsoft YaHei", 15))
            p.drawText(icon_rect, Qt.AlignCenter, emoji)

            name_rect = QRectF(cx + 59, card_y + 12, 42, 26)
            p.setPen(QColor("#76584b"))
            p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
            p.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, name)

            value_text = f"{int(round(val))}%"
            value_rect = QRectF(cx + 104, card_y + 11, card_w - 117, 28)
            p.setPen(QColor(color))
            p.setFont(self._fit_font(value_text, 14, value_rect.width(),
                                     QFont.Bold, 8))
            p.drawText(value_rect, Qt.AlignRight | Qt.AlignVCenter |
                       Qt.TextSingleLine, value_text)

            br = QRectF(cx + 15, card_y + 65, card_w - 30, 11)
            p.setBrush(QColor(255, 255, 255, 190))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(br, 5, 5)
            fill = QRectF(br.left(), br.top(), br.width() * val / 100, br.height())
            p.setBrush(QColor(color))
            p.drawRoundedRect(fill, 5, 5)

            mood_text = moods[0] if val < 35 else (moods[1] if val < 70 else moods[2])
            mood_rect = QRectF(cx + 12, card_y + 88, card_w - 24, 25)
            p.setPen(QColor("#8a6f62"))
            p.setFont(self._fit_font(mood_text, 9, mood_rect.width(),
                                     QFont.Normal, 8))
            p.drawText(mood_rect, Qt.AlignCenter | Qt.TextSingleLine, mood_text)


class BubbleMenu(QWidget):
    """Five soft candy-style action buttons with a warm growth card."""
    def __init__(self, pet):
        super().__init__()
        self.pet = pet
        self.actions = [
            ("💬", "聊天", "chat", "#ef8fa2"),
            ("🍖", "喂食", "feed", "#f49a62"),
            ("🎾", "玩耍", "play", "#72bf9b"),
            ("💤", "睡觉", "sleep", "#9b8ade"),
            ("⚙️", "设置", "settings", "#e7ae64"),
        ]
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Larger hit targets with room for both icon and label.
        self.W = 590
        self.H = 112
        self.resize(self.W, self.H)
        self._bubble_rects = []
        self._hover = -1
        self._press = -1
        self._hover_scales = [0.0] * len(self.actions)
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._tick)
        self._anim.start(16)

        # stat bubble (follows pet too)
        self.stat_bubble = StatBubble(pet)

        self._place()
        self.show()
        self.raise_()
        self.setMouseTracking(True)
        self.grabMouse()

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
            p.setFont(QFont("Microsoft YaHei", 17, QFont.Bold))
            p.drawText(QRectF(rect.x(), rect.y() + 7, rect.width(), 34),
                       Qt.AlignCenter, emoji)
            p.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
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
        if e.button() == Qt.LeftButton:
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
        self._close()

    def _close(self):
        try:
            self.stat_bubble.close()
        except Exception:
            pass
        try:
            self.releaseMouse()
        except Exception:
            pass
        self.close()

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
        self.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
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
        self.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
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
        self.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text, ms):
        # Flatten all input so the bubble can never wrap onto a second line.
        text = " ".join(str(text).replace("\r", "\n").splitlines()).strip()
        screen = self.pet.current_screen_rect()
        fm = self.fontMetrics()
        padding_x = 18
        max_text_width = max(80, screen.width() - padding_x * 2 - 24)
        self.text = fm.elidedText(text, Qt.ElideRight, max_text_width)
        text_width = fm.horizontalAdvance(self.text)
        self.resize(text_width + padding_x * 2 + 10, fm.height() + 28)
        self.follow_pet()
        self.show()
        self.raise_()
        self._hide_timer.start(max(1, int(ms)))
        self.update()

    def follow_pet(self):
        if not self.pet.isVisible():
            self.hide()
            return
        g = self.pet.geometry()
        screen = self.pet.current_screen_rect()
        x = g.center().x() - self.width() // 2
        # Keep the one-line bubble inside the pet window's reserved head space.
        y = g.top() + 3
        x = max(screen.left() + 4, min(x, screen.right() - self.width() - 4))
        y = max(screen.top() + 4, min(y, screen.bottom() - self.height() - 4))
        self.move(int(x), int(y))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
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
        self.PET_W, self.PET_H = 160, 220
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

        # current pose + blink timer
        self.pose = POSE["idle"]
        self.blink = False
        self.blink_t = 0.0

        # sound effects
        self.sounds = {}
        if HAS_SOUND:
            sound_dir = os.path.join(POSES_DIR, "sounds")
            for name in ["bark", "eat", "sleep", "pet", "bounce"]:
                p = os.path.join(sound_dir, f"{name}.wav")
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

        # walk timer / autonomous behavior
        self.behavior = "idle"  # idle / walk / sit / nap / ask
        self.behavior_until = 0.0
        self.next_behavior_at = time.time() + random.uniform(3, 7)

        # AI: track idle time for proactive nudges
        self.last_user_t = time.time()
        self.last_nudge_check = time.time()
        self.chat_win = None  # lazy-created on first chat
        self.settings_win = None  # lazy-created on first settings open
        self.stats_win = None     # lazy-created on first stats open
        self._interactive_bubble = None  # current floating action bubble
        self._bubble_menu = None         # radial bubble menu (right-click)
        self._last_interactive_t = 0.0   # throttle: don't spam
        self._ctx_menu_cb = None  # set by TrayApp to provide a right-click menu

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

    # ---------- painting ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # Determine pose for rendering
        pose = self.pose
        # blink: briefly switch to "close" (eyes-closed) pose if available
        if self.blink and pose in (POSE["idle"], POSE["happy"]):
            pose = POSE["close"]

        # dog occupies lower part of widget; top is reserved for speech bubble
        dog_y = self.PET_H - self.DOG_H
        dst = QRectF(0, dog_y, self.PET_W, self.DOG_H)

        # Flip horizontally if facing left
        if self.facing < 0:
            p.save()
            p.translate(self.PET_W, 0)
            p.scale(-1, 1)

        if self.use_png:
            pm = self.pose_pixmaps.get(pose) or self.pose_pixmaps.get(POSE["idle"])
            if pm is not None and not pm.isNull():
                # scale pixmap to fit dst, keep aspect ratio (fit inside)
                pw, ph = pm.width(), pm.height()
                scale = min(self.PET_W / pw, self.DOG_H / ph)
                dw, dh = pw * scale, ph * scale
                dx = (self.PET_W - dw) / 2
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
        font = QFont("Microsoft YaHei", 11, QFont.Bold)
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
        if self._speech_bubble is None:
            self._speech_bubble = SpeechBubble(self)
        self._speech_bubble.show_text(text, ms)

    # ---------- mouse ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
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
            if len(window) >= 2:
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

            # walking bounce animation: small vertical bob when moving on ground
            if self.on_ground and abs(self.vx) > 20:
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

    def open_stats(self):
        """Open the stats / level panel near the pet."""
        if self.stats_win is None:
            self.stats_win = StatsWindow(self)
        # position beside the pet (prefer right side, fall back to left)
        g = self.geometry()
        screen = self.current_screen_rect()
        sw, sh = self.stats_win.width(), self.stats_win.height()
        x = g.right() + 16
        y = g.center().y() - sh // 2
        if x + sw > screen.right():
            x = g.left() - sw - 16
        if x < screen.left():
            x = max(screen.left(), min(g.center().x() - sw // 2,
                                       screen.right() - sw))
        y = max(screen.top() + 8,
                min(y, screen.bottom() - sh - 40))
        self.stats_win.move(int(x), int(y))
        self.stats_win.show()
        self.stats_win.raise_()
        self.stats_win.activateWindow()
        self.stats_win.refresh()

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
        msg = ai.maybe_nudge(mem, idle, pet_state=self.state,
                             idle_min=s["nudge_idle_min"], gap_min=s["nudge_gap_min"])
        if msg:
            # show as a longer speech bubble; do not call AI to save quota
            self.say(msg, 4500)
            self.last_user_t = time.time() - (s["nudge_idle_min"] - 100)


class TrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        # AI bridge (must be created before PetWindow uses it)
        global bridge
        bridge = _Bridge()
        self.state = load_state()
        self.pet = PetWindow(self.state)
        # initial greeting from Sheen (only if has API key)
        if ai.get_api_key():
            QTimer.singleShot(1500, lambda: self.pet.say(ai.time_greeting(), 3000))
        self.pet.show()

        # tray
        self.tray = QSystemTrayIcon(QIcon(ICON_PATH), self.app)
        self.tray.setToolTip("我的小狗 Sheen — 双击显示/隐藏")
        self.tray.activated.connect(self.on_tray_activated)
        self.menu = QMenu()
        self.menu.setStyleSheet(WARM_MENU_STYLE)
        self.build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        # share the menu with the pet so right-click on pet shows it too
        self.pet._ctx_menu_cb = lambda: self._fresh_menu()
        self._install_interaction_handlers()

        # auto-check for updates after 5 seconds (silent, only prompts if newer)
        QTimer.singleShot(5000, self._check_update)

    def _install_interaction_handlers(self):
        """Install click, double-click, drag, and right-long-press handling."""
        self._press_pos = None
        self._press_t = 0
        self._press_button = None
        self._right_long_timer = None
        self._right_long_fired = False
        self._last_left_click_t = 0
        self._pending_single_click = None
        self.pet.mousePressEvent_orig = self.pet.mousePressEvent
        self.pet.mouseReleaseEvent_orig = self.pet.mouseReleaseEvent
        self.pet.mousePressEvent = self._wrap_press
        self.pet.mouseReleaseEvent = self._wrap_release

    def _check_update(self):
        if RELEASES_URL.startswith("https://api.github.com/repos/USER/REPO"):
            return  # not configured yet
        check_update_async(self._on_update_result)

    def _on_update_result(self, info):
        if info is None:
            return
        # show a message box asking user to update
        from PyQt5.QtWidgets import QMessageBox, QProgressDialog
        msg = QMessageBox(self.pet)
        msg.setWindowTitle("Sheen 有新版本")
        msg.setIcon(QMessageBox.Information)
        v = info["version"]
        notes = info.get("notes", "").strip() or "（暂无更新说明）"
        msg.setText(f"发现新版本 v{v}（当前 v{VERSION}）\n\n更新内容：\n{notes[:300]}")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.button(QMessageBox.Yes).setText(
            "打开下载" if IS_MACOS else "立即更新")
        msg.button(QMessageBox.No).setText("以后再说")
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec_() != QMessageBox.Yes:
            return
        if IS_MACOS:
            QDesktopServices.openUrl(QUrl(info["download_url"]))
            return
        # download with progress dialog
        prog = QProgressDialog("正在下载新版本…", "取消", 0, 100, self.pet)
        prog.setWindowTitle("更新")
        prog.setMinimumDuration(0)
        prog.setValue(0)
        def on_progress(done, total):
            if prog.wasCanceled():
                return
            pct = int(done * 100 / total) if total else 0
            prog.setValue(pct)
        def do_download():
            ok = download_and_update(info["download_url"], on_progress=on_progress)
            prog.close()
            if ok:
                # quit; the bat will replace and restart
                QApplication.quit()
            else:
                QMessageBox.warning(self.pet, "更新失败", "下载失败，请稍后重试或手动下载。")
        # run download in thread so GUI stays responsive
        threading.Thread(target=do_download, daemon=True).start()

    def _wrap_press(self, e):
        if e.button() == Qt.LeftButton:
            self._press_pos = e.globalPos()
            self._press_t = time.time()
            self._press_button = "left"
        elif e.button() == Qt.RightButton:
            self._press_pos = e.globalPos()
            self._press_t = time.time()
            self._press_button = "right"
            self._right_long_fired = False
            # start a timer; if not released within 500ms, fire stats page
            self._right_long_timer = QTimer(self.app)
            self._right_long_timer.setSingleShot(True)
            self._right_long_timer.timeout.connect(self._on_right_long)
            self._right_long_timer.start(500)
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
            # stop the long-press timer
            if self._right_long_timer is not None:
                self._right_long_timer.stop()
                self._right_long_timer = None
            if not self._right_long_fired:
                # short right press -> menu
                self._show_pet_menu(e.globalPos())
            self._press_button = None
            self._press_pos = None
        self.pet.mouseReleaseEvent_orig(e)

    def _do_single_click(self):
        self._pending_single_click = None
        if not self.pet.state.get("sleeping"):
            self.pet.pet_click()

    def _on_right_long(self):
        """Long right press -> open stats page near the pet."""
        self._right_long_fired = True
        self._right_long_timer = None
        self.pet.open_stats()

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
        a_stats = QAction("📊 状态页", m); a_stats.triggered.connect(self.pet.open_stats); m.addAction(a_stats)
        a_recall = QAction("🎯 回到屏幕中央", m); a_recall.triggered.connect(self.pet.recall); m.addAction(a_recall)
        a_hide = QAction("👁 显示/隐藏", m); a_hide.triggered.connect(self.toggle_visible); m.addAction(a_hide)
        a_settings = QAction("⚙️ 设置", m); a_settings.triggered.connect(self.pet.open_settings); m.addAction(a_settings)
        a_data = QAction("📁 打开数据文件夹", m); a_data.triggered.connect(self.open_data_folder); m.addAction(a_data)
        m.addSeparator()

        # ---- 系统 ----
        a_update = QAction("🔄 检查更新", m); a_update.triggered.connect(self._check_update); m.addAction(a_update)
        autostart_label = "↻ 登录时启动" if IS_MACOS else "↻ 开机自启"
        a_autostart = QAction(autostart_label, m); a_autostart.setCheckable(True)
        a_autostart.setChecked(self.state.get("autostart", False))
        a_autostart.triggered.connect(lambda: self.toggle_autostart(a_autostart))
        m.addAction(a_autostart)
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
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec_())


if __name__ == "__main__":
    TrayApp().run()

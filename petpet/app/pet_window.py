"""Desktop pet runtime controller extracted from the legacy entry module."""

import json
import math
import os
import random
import threading
import time

from petpet.chat import api as ai
from petpet.ui import decorations as decoration_renderer
from petpet.minigames import ui as minigames
from petpet.progression import core as progression
from petpet.app.paths import OUTFITS_DIR, SOUNDS_DIR
from petpet.app.pets import pet_asset_path, pet_definition
from petpet.app.settings import load_settings
from petpet.ui.common import pixel_font
from PyQt5.QtCore import (
    QByteArray,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QRegion,
    QTextDocument,
)
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QApplication, QWidget


_dependency_resolver = None


def configure_dependency_resolver(resolver):
    """Install lazy access to entry-owned compatibility objects."""
    global _dependency_resolver
    _dependency_resolver = resolver


def _dependency(name):
    if _dependency_resolver is None:
        raise RuntimeError(f"PetWindow dependency is not configured: {name}")
    return _dependency_resolver(name)


class PetWindow(QWidget):
    # Runtime frames are displayed at roughly half this size on desktop.
    # Keeping a 2x-ish buffer preserves crispness while bounding Qt memory.
    ANIMATION_MAX_SIZE = 384
    PRELOADED_ANIMATIONS = (
        "idle", "pet", "eat", "play", "sleep", "dig_reward"
    )
    STAT_DECAY_RATE_MULTIPLIER = 0.5
    flung = pyqtSignal()
    AUTO_SLEEP_ENERGY_THRESHOLD = 30.0
    AUTO_WAKE_ENERGY_THRESHOLD = 80.0
    AUTO_SLEEP_WALK_SPEED = 118.0
    AUTO_SLEEP_CORNER_MARGIN = 18
    AUTONOMY_IDLE_WEIGHT = 9.0
    AUTONOMY_WALK_WEIGHT = 1.0
    AUTONOMY_SIT_WEIGHT = 2.0
    STAT_REMINDER_COOLDOWN_SECONDS = 10 * 60

    @staticmethod
    def needs_api_key_configuration():
        return ai.needs_personal_setup_reminder()

    def pet_needs_stat_attention(self):
        return bool(progression.zero_stat_interaction_actions(self.state))

    def treasure_notice_active(self):
        """Return whether the treasure notice is visible or menu-hidden."""
        if getattr(self, "_hidden_treasure_bubble", None) is not None:
            return True
        bubble = getattr(self, "_interactive_bubble", None)
        if bubble is None or getattr(bubble, "action_name", None) != "dig_reward":
            return False
        try:
            return bool(bubble.isVisible())
        except RuntimeError:
            return False

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.settings = load_settings()
        self.debug_parameters = self.debug_parameter_defaults()
        loaded_debug = _dependency("load_debug_parameters")()
        if _dependency("IS_MACOS") and not os.path.exists(_dependency("DEBUG_PARAMETERS_PATH")):
            loaded_debug.update(dict(zip(
                ("pet_width", "pet_height", "dog_height"), _dependency("MACOS_PET_SIZE")
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
        platform_size = _dependency("MACOS_PET_SIZE") if _dependency("IS_MACOS") else _dependency("DEFAULT_PET_SIZE")
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
        if _dependency("IS_MACOS"):
            self.setAttribute(
                Qt.WA_MacAlwaysShowToolWindow,
                bool(on_top),
            )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        self._current_pet_id = pet_definition(
            self.state.get("active_pet_id", "lunch_meat")
        )["id"]
        self._load_static_pose_assets()

        self.decoration_pixmaps = (
            decoration_renderer.load_decoration_pixmaps()
        )

        # Optional multi-frame actions. Each action lives in
        # assets/runtime/pets/desktop/animations/<action>/ and falls back to
        # the static pose above.
        self.animation_specs = {}
        self.animation_frames = {}
        self._animation_frame_paths = {}
        self._persistent_animation_names = set(self.PRELOADED_ANIMATIONS)
        self._active_animation = None
        self._animation_started_at = time.monotonic()
        self._animation_override = None
        self._animation_override_token = 0
        self._load_animations()
        # Apply persisted source-tuning values after animation specs exist.
        for _key, _value in self.debug_parameters.items():
            self.set_debug_parameter(_key, _value)

        # current pose + blink timer
        self.pose = _dependency("POSE")["idle"]
        self.blink = False
        self.blink_t = 0.0

        # sound effects
        self.sounds = {}
        if _dependency("HAS_SOUND"):
            for name in ["bark", "eat", "sleep", "pet", "bounce"]:
                p = os.path.join(SOUNDS_DIR, f"{name}.wav")
                if os.path.exists(p):
                    se = _dependency("QSoundEffect")(self)
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
        self._wake_shake = _dependency("WakeShakeDetector")()
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
        self.home_scene_window = None
        self.minigames_win = None
        self.parameter_tuner_win = None
        self.play_scene = None  # zoomed-out interactive fetch scene
        self._play_return_pos = None
        self._interactive_bubble = None  # current floating action bubble
        self._hidden_treasure_bubble = None
        self._dig_reward_claiming = False
        self._bubble_menu = None         # radial bubble menu (right-click)
        self._last_bubble_menu_t = 0.0
        self._status_bubble = None
        self._last_interactive_t = 0.0   # throttle: don't spam
        self._last_stat_reminder_t = {
            "energy": 0.0,
            "hunger": 0.0,
            "mood": 0.0,
        }
        self._ctx_menu_cb = None  # set by TrayApp to provide a right-click menu
        self._settings_applied_cb = None
        self._app_action_cb = None
        self._user_hidden = False
        self._presence_guard_t = 0.0

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

        self.presence_guard = QTimer(self)
        self.presence_guard.timeout.connect(self._maintain_desktop_presence)
        self.presence_guard.start(5000)

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

        # Prime the first-use menu paints away from the user's click path.
        self._prewarmed_bubble_menus = {}
        self._ui_warmup_timer = QTimer(self)
        self._ui_warmup_timer.setSingleShot(True)
        self._ui_warmup_timer.timeout.connect(self._warm_up_interaction_surfaces)
        self._ui_warmup_timer.start(1200)

        # multi-sample drag velocity: track mouse move events
        # (handled in mouseMoveEvent)

    @property
    def pet_name(self):
        return ai.normalize_pet_name(self.state.get("pet_name"))

    @property
    def current_pet_id(self):
        return getattr(
            self,
            "_current_pet_id",
            pet_definition(self.state.get("active_pet_id", "lunch_meat"))["id"],
        )

    def _load_static_pose_assets(self):
        """Load the selected pet's static poses, using its idle as fallback."""
        self.pose_pixmaps = {}
        self.use_png = False
        for name, idx in _dependency("POSE").items():
            path = pet_asset_path(self.current_pet_id, "desktop", name)
            if not path:
                continue
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.pose_pixmaps[idx] = pixmap
        if len(self.pose_pixmaps) == len(_dependency("POSE")):
            self.use_png = True
            return

        with open(_dependency("SVG_PATH"), "rb") as source:
            self.svg_bytes = QByteArray(source.read())
        self.renderer = QSvgRenderer(self.svg_bytes)
        if not self.renderer.isValid():
            raise RuntimeError("no pose PNGs and pet.svg invalid")

    def _desktop_animation_manifest_path(self):
        desktop = pet_definition(self.current_pet_id).get("desktop")
        if not isinstance(desktop, dict) or not desktop.get("animations_manifest"):
            return None
        path = pet_asset_path(
            self.current_pet_id, "desktop", "animations_manifest"
        )
        return path if path and path.lower().endswith(".json") else None

    def refresh_pet_assets(self, pet_id=None):
        """Reload renderer resources for the selected stable pet ID."""
        selected_pet_id = pet_definition(
            pet_id or self.state.get("active_pet_id", "lunch_meat")
        )["id"]
        self._current_pet_id = selected_pet_id
        self._outfit_preview_cache = {}
        self.animation_frames = {}
        self._animation_frame_paths = {}
        self._persistent_animation_names = set(self.PRELOADED_ANIMATIONS)
        self._load_static_pose_assets()
        self._load_animations()
        self._active_animation = None
        self._animation_override = None
        self._animation_override_token += 1
        self._animation_started_at = time.monotonic()
        self.pose = _dependency("POSE")["idle"]
        self.blink = False
        if hasattr(self, "update"):
            self.update()

    def set_active_pet(self, pet_id):
        """Forward active-pet switching to the application transaction."""
        callback = getattr(self, "_set_active_pet_callback", None)
        if not callable(callback):
            return False
        result = callback(pet_id)
        if result is False or (
            isinstance(result, dict) and result.get("ok") is False
        ):
            return result
        self._current_pet_id = pet_definition(pet_id)["id"]
        return result

    def debug_parameter_defaults(self):
        defaults = dict(_dependency("DEFAULT_DEBUG_PARAMETERS"))
        if _dependency("IS_MACOS"):
            defaults.update(dict(zip(
                ("pet_width", "pet_height", "dog_height"), _dependency("MACOS_PET_SIZE")
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
        if key not in _dependency("DEFAULT_DEBUG_PARAMETERS"):
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
        values = {key: self.debug_parameter_value(key) for key in _dependency("DEFAULT_DEBUG_PARAMETERS")}
        _dependency("save_debug_parameters")(values)

    def open_parameter_tuner(self):
        if _dependency("IS_FROZEN"):
            return
        if self.parameter_tuner_win is None:
            from parameter_tuner import ParameterTunerWindow
            self.parameter_tuner_win = ParameterTunerWindow(self)
        self.parameter_tuner_win.show_near_pet()

    def set_pet_name(self, value):
        """Persist a new name and refresh already-open pet windows."""
        name = ai.normalize_pet_name(value)
        self.state["pet_name"] = name
        _dependency("save_state")(self.state)
        ai.set_pet_name(name, pet_id=self.current_pet_id)
        if self.chat_win is not None:
            self.chat_win.refresh_pet_name()
        self.update()
        return name

    def _capture_desktop_position(self):
        position = [int(self.x()), int(self.y())]
        self.state["x"], self.state["y"] = position
        pets = self.state.get("pets")
        pet_id = self.state.get("active_pet_id")
        profile = pets.get(pet_id) if isinstance(pets, dict) else None
        if isinstance(profile, dict):
            profile["desktop_position"] = position
        return position

    def _save_desktop_position(self):
        self._capture_desktop_position()
        _dependency("save_state")(self.state)

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
            need = _dependency("xp_to_next")(self.state.get("level", 1))
            if self.state["xp"] >= need:
                self.state["xp"] -= need
                self.state["level"] = self.state.get("level", 1) + 1
                leveled = True
                levels_gained += 1
            else:
                break
        if levels_gained:
            self.state["records"]["level_ups"] += levels_gained
        _dependency("save_state")(self.state)
        return leveled

    def on_passive_xp(self):
        """Accumulate passive XP and companionship affection once per second."""
        progression.record_active_time(self.state, 1)
        rate = progression.passive_xp_per_second(self.state)
        buffer_value = float(self.state.get("passive_xp_buffer", 0.0))
        buffer_value += rate
        whole_xp = int(buffer_value)
        self.state["passive_xp_buffer"] = buffer_value - whole_xp

        affection_buffer = float(
            self.state.get("passive_affection_buffer", 0.0)
        )
        affection_buffer += progression.passive_affection_per_second(
            self.state
        )
        whole_affection = int(affection_buffer)
        self.state["passive_affection_buffer"] = (
            affection_buffer - whole_affection
        )
        affection_result = progression.add_affection(
            self.state, whole_affection
        )

        leveled = False
        if whole_xp > 0:
            leveled = self.add_xp(whole_xp, apply_bonus=False)
        if leveled:
            self.say(f"升级啦！Lv.{self.state.get('level',1)} 🎉", 2500)
            bonus_x, bonus_y = self.interface_bonus_origin(-20)
            _dependency("BonusBubble")(f"升级！Lv.{self.state.get('level',1)}",
                        bonus_x, bonus_y, "#ffcc00")
        if affection_result["leveled"]:
            bonus_x, bonus_y = self.interface_bonus_origin(-48)
            _dependency("BonusBubble")(
                f"好感 Lv.{self.state.get('affection_level', 1)}",
                bonus_x,
                bonus_y,
                "#ef8f8a",
            )
        _dependency("save_state")(self.state)

    # ---------- placement ----------
    def place_initial(self):
        virt = self.screen_rect()  # all screens
        profile = self.state.get("pets", {}).get(self.current_pet_id)
        saved_position = (
            profile.get("desktop_position")
            if isinstance(profile, dict)
            else None
        )
        if isinstance(saved_position, (list, tuple)) and len(saved_position) >= 2:
            x, y = saved_position[:2]
        else:
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

    def _active_home_interface(self):
        """Return the home scene while its pet is the active UI anchor."""

        home = getattr(self, "home_scene_window", None)
        if home is None:
            return None
        try:
            if (
                home.isVisible()
                and not home.is_decorating()
                and home.home_pet_visible()
            ):
                return home
        except RuntimeError:
            return None
        return None

    def interface_anchor_rect(self):
        """Return the visible pet body used to place detached UI."""

        home = self._active_home_interface()
        if home is not None:
            rect = home.home_pet_global_rect()
            if not rect.isEmpty():
                return rect
        return self.geometry()

    def interface_anchor_visible(self):
        """Return whether either indoor or outdoor pet can host UI."""

        return self._active_home_interface() is not None or self.isVisible()

    def interface_screen_rect(self):
        """Return the available screen containing the active UI anchor."""

        anchor = self.interface_anchor_rect()
        screen = self.screen_at(anchor.center())
        if screen is not None:
            return screen.availableGeometry()
        return self.current_screen_rect()

    def interface_window_position(self, window_size, gap=16):
        """Return an on-screen point beside the active pet when possible."""

        anchor = self.interface_anchor_rect()
        screen = self.interface_screen_rect()
        width = int(window_size.width())
        height = int(window_size.height())
        gap = int(gap)
        right_x = anchor.right() + gap
        left_x = anchor.left() - width - gap
        if right_x + width - 1 <= screen.right():
            x = right_x
        elif left_x >= screen.left():
            x = left_x
        else:
            x = screen.center().x() - width // 2
        y = anchor.center().y() - height // 2
        x = max(screen.left(), min(x, screen.right() - width + 1))
        y = max(screen.top(), min(y, screen.bottom() - height + 1))
        return QPoint(int(x), int(y))

    def interface_bonus_origin(self, y_offset=-10):
        """Return the active pet-centered origin for transient reward bubbles."""

        anchor = self.interface_anchor_rect()
        return anchor.center().x(), anchor.top() + int(y_offset)

    def recall(self):
        """Move pet to a safe, visible position at the bottom-center of the current screen."""
        screen = self.current_screen_rect()
        x = screen.center().x() - self.PET_W // 2
        y = screen.bottom() - self.PET_H - 20
        self.move(x, y)
        self.vx = 0; self.vy = 0
        self._save_desktop_position()
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
        if _dependency("IS_MACOS"):
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

    def set_user_visible(self, visible):
        """Change desktop visibility while preserving the user's intent."""
        self._user_hidden = not bool(visible)
        if visible:
            self.show()
            self.raise_()
        else:
            self.hide_overlays()
            self.hide()

    def _maintain_desktop_presence(self, now=None):
        """Recover accidental hides and periodically reassert topmost order."""
        if self.__dict__.get("_user_hidden", False):
            return False
        if self.play_scene is not None or self._home_scene_active():
            return False

        restored = False
        try:
            visible = self.isVisible()
        except RuntimeError:
            visible = False
        if not visible:
            self.show()
            restored = True

        if not self.settings.get("always_on_top", True):
            return restored
        now = time.monotonic() if now is None else float(now)
        if now - self.__dict__.get("_presence_guard_t", 0.0) < 5.0:
            return restored
        self._presence_guard_t = now
        if not bool(self.windowFlags() & Qt.WindowStaysOnTopHint):
            self.apply_window_flags(show=True)
        self.raise_()
        return True

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
                 for name, values in _dependency("DEFAULT_ANIMATIONS").items()}
        manifest_path = self._desktop_animation_manifest_path()
        if manifest_path and os.path.exists(manifest_path):
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
        animation_dir = (
            os.path.dirname(manifest_path) if manifest_path is not None else None
        )
        idle_path = pet_asset_path(self.current_pet_id, "desktop", "idle")
        for name, spec in specs.items():
            folder = str(spec.get("folder", name))
            frame_dir = (
                os.path.join(animation_dir, folder) if animation_dir else None
            )
            if not frame_dir or not os.path.isdir(frame_dir):
                if name != "idle" and (
                        pet_asset_path(self.current_pet_id, "desktop", name)
                        == idle_path):
                    spec["fallback"] = "idle"
                continue
            frame_paths = sorted(
                (os.path.join(frame_dir, filename)
                 for filename in os.listdir(frame_dir)
                 if filename.lower().endswith(".png")),
                key=lambda path: os.path.basename(path).lower(),
            )
            if frame_paths:
                self._animation_frame_paths[name] = frame_paths

        # Preload frequent interactions so the first click never blocks the
        # event loop on PNG decoding. Rare sequences remain on demand.
        equipped_animation = progression.equipped_outfit_animation(self.state)
        if equipped_animation in self._animation_frame_paths:
            self._persistent_animation_names.add(equipped_animation)
        for animation_name in self._persistent_animation_names:
            self._ensure_animation_loaded(animation_name)

    def _load_animation(self, name):
        """Decode one animation sequence from its paths into the Qt cache."""
        if name in self.animation_frames:
            return
        frame_paths = self._animation_frame_paths.get(name, ())
        if not frame_paths:
            return
        spec = self.animation_specs.get(name, {})
        frames = []
        for frame_path in frame_paths:
            pixmap = QPixmap(frame_path)
            if pixmap.isNull():
                continue
            if (pixmap.width() > self.ANIMATION_MAX_SIZE or
                    pixmap.height() > self.ANIMATION_MAX_SIZE):
                pixmap = pixmap.scaled(
                    self.ANIMATION_MAX_SIZE, self.ANIMATION_MAX_SIZE,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap = _dependency("adjust_animation_colors")(
                pixmap,
                saturation=spec.get("saturation", 1.0),
                brightness=spec.get("brightness", 1.0),
            )
            frames.append(pixmap)
        sequence = spec.get("frame_sequence")
        if isinstance(sequence, list):
            try:
                indices = [int(frame_number) - 1 for frame_number in sequence]
            except (TypeError, ValueError):
                indices = []
            if indices and all(0 <= index < len(frames) for index in indices):
                authored_durations = spec.get("frame_durations_ms")
                if (
                    isinstance(authored_durations, list)
                    and len(authored_durations) == len(frames)
                ):
                    spec["frame_durations_ms"] = [
                        authored_durations[index] for index in indices
                    ]
                frames = [frames[index] for index in indices]
        if frames:
            self.animation_frames[name] = frames

    def _ensure_animation_loaded(self, name):
        """Load a known animation only when a caller needs its frames."""
        if name not in self.animation_frames:
            self._load_animation(name)

    @staticmethod
    def _retained_animation_names(loaded, persistent, active):
        """Return cache keys that must survive an animation switch."""
        retained = set(loaded) & set(persistent)
        if active in loaded:
            retained.add(active)
        return retained

    def _release_inactive_animation_frames(self, active):
        retained = self._retained_animation_names(
            self.animation_frames,
            getattr(self, "_persistent_animation_names", {"idle"}),
            active,
        )
        for name in list(self.animation_frames):
            if name not in retained:
                del self.animation_frames[name]

    @staticmethod
    def _show_idle_decorations(
            animation_name, pose, animation_pixmap):
        """Keep passive states on the same decorated idle appearance."""
        if (
            animation_pixmap is not None
            or animation_name not in ("idle", "sit", "ask")
            or pose not in (_dependency("POSE")["idle"], _dependency("POSE")["close"])
        ):
            return False
        return True

    def _animation_duration_ms(self, name, cycles=1):
        """Return the exact time needed to show an animation for N cycles."""
        ensure_loaded = getattr(self, "_ensure_animation_loaded", None)
        if callable(ensure_loaded):
            ensure_loaded(name)
        frames = self.animation_frames.get(name, ())
        if not frames:
            return 1
        cycles = max(1, int(cycles))
        return max(1, int(math.ceil(
            sum(PetWindow._frame_durations_ms(
                self.animation_specs.get(name, {}), len(frames)
            )) * cycles)))

    @staticmethod
    def _frame_durations_ms(spec, frame_count):
        """Return authored frame durations, or the legacy fixed FPS timing."""
        durations = spec.get("frame_durations_ms")
        if isinstance(durations, (list, tuple)) and len(durations) == frame_count:
            try:
                durations = [float(duration) for duration in durations]
            except (TypeError, ValueError):
                durations = ()
            if all(math.isfinite(duration) and duration > 0 for duration in durations):
                return durations
        try:
            fps = max(1.0, float(spec.get("fps", 8)))
        except (TypeError, ValueError):
            fps = 8.0
        return [1000.0 / fps] * frame_count

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
        outfit_animation = progression.equipped_outfit_animation(self.state)
        if outfit_animation in self.__dict__.get("animation_frames", {}) or (
                outfit_animation in self.__dict__.get("_animation_frame_paths", {})):
            return outfit_animation
        return "idle"

    def _equipped_outfit_preview(self):
        outfit_id = progression.equipped_outfit(self.state)
        cache = self.__dict__.get("_outfit_preview_cache")
        if cache is None:
            cache = self._outfit_preview_cache = {}
        if outfit_id in cache:
            return cache[outfit_id]
        definition = progression.OUTFIT_DEFINITIONS.get(outfit_id)
        if not definition:
            return None
        asset_name = definition.get("preview_asset")
        if not asset_name:
            return None
        asset_folder = definition.get("asset_folder", outfit_id)
        path = os.path.join(OUTFITS_DIR, asset_folder, asset_name)
        if not os.path.exists(path):
            return None
        pixmap = QPixmap(path)
        preview = None if pixmap.isNull() else pixmap
        cache[outfit_id] = preview
        return preview

    def _animation_frame(self, name):
        self._ensure_animation_loaded(name)
        frames = self.animation_frames.get(name)
        if not frames:
            self._animation_frame_index = None
            return None
        if self._active_animation != name:
            self._release_inactive_animation_frames(name)
            self._active_animation = name
            self._animation_started_at = time.monotonic()
        spec = self.animation_specs.get(name, {})
        durations = self._frame_durations_ms(spec, len(frames))
        duration_ms = sum(durations)
        elapsed_ms = max(0.0, (time.monotonic() - self._animation_started_at) * 1000.0)
        if bool(spec.get("loop", True)):
            elapsed_ms %= duration_ms
        elif elapsed_ms >= duration_ms:
            self._animation_frame_index = len(frames) - 1
            return frames[-1]
        index = 0
        for index, frame_duration_ms in enumerate(durations):
            if elapsed_ms < frame_duration_ms:
                break
            elapsed_ms -= frame_duration_ms
        self._animation_frame_index = index
        return frames[index]

    def shared_animation_frame(self):
        """Expose the currently rendered desktop action to the home scene."""

        name = self._current_animation_name()
        pixmap = self._animation_frame(name)
        if pixmap is None:
            pose = self._fallback_pose(name)
            pixmap = self.pose_pixmaps.get(
                pose,
                self.pose_pixmaps.get(_dependency("POSE")["idle"]),
            )
        if pixmap is None or pixmap.isNull():
            return None
        return {
            "name": name,
            "pixmap": pixmap,
            "frame_index": getattr(self, "_animation_frame_index", 0) or 0,
            "spec": dict(self.animation_specs.get(name, {})),
        }

    def _fallback_pose(self, animation_name):
        spec = self.animation_specs.get(animation_name, {})
        fallback = str(spec.get("fallback", animation_name))
        return _dependency("POSE").get(fallback, self.pose)

    @staticmethod
    def _apply_blink_frame(blink, pose, animation_pixmap):
        """Blink without replacing an active action-animation frame."""
        if (
            blink
            and animation_pixmap is None
            and pose in (_dependency("POSE")["idle"], _dependency("POSE")["happy"])
        ):
            return _dependency("POSE")["close"], None
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
        render_spec_name = animation_name
        if self.dragging:
            outfit_preview = self._equipped_outfit_preview()
            if outfit_preview is not None:
                animation_pixmap = outfit_preview
                render_spec_name = (
                    progression.equipped_outfit_animation(self.state)
                    or animation_name
                )
        # Passive sit/ask behavior changes dialogue timing, not appearance.
        # Keep the authored idle model so equipped decorations never vanish.
        if (
            animation_pixmap is None
            and animation_name in ("idle", "sit", "ask")
        ):
            pose = _dependency("POSE")["idle"]
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
                  or self.pose_pixmaps.get(_dependency("POSE")["idle"]))
            if pm is not None and not pm.isNull():
                # scale pixmap to fit dst, keep aspect ratio (fit inside)
                pw, ph = pm.width(), pm.height()
                scale = min(self.PET_W / pw, self.DOG_H / ph)
                spec = self.animation_specs.get(render_spec_name, {})
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
            sx = pose * _dependency("CELL")
            src = QRectF(sx, 0, _dependency("CELL"), _dependency("CELL"))
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

        if (
            self.needs_api_key_configuration()
            or self.pet_needs_stat_attention()
        ):
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
        if not self.interface_anchor_visible():
            return
        if PetWindow.treasure_notice_active(self):
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
            self._speech_bubble = _dependency("SpeechBubble")(self)
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

        for menu in getattr(self, "_prewarmed_bubble_menus", {}).values():
            try:
                menu._close()
            except RuntimeError:
                pass
        self._prewarmed_bubble_menus = {}

        hidden_treasure = getattr(self, "_hidden_treasure_bubble", None)
        self._hidden_treasure_bubble = None
        if hidden_treasure is not None:
            try:
                hidden_treasure.close()
            except RuntimeError:
                pass

        menu = self._bubble_menu
        self._bubble_menu = None
        if menu is not None:
            try:
                menu._close()
            except RuntimeError:
                pass

        status = getattr(self, "_status_bubble", None)
        self._status_bubble = None
        if status is not None:
            try:
                status.close()
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
            self.pose = _dependency("POSE")["drag"]
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
        if e.button() == Qt.RightButton:
            self.open_bubble_menu()
            e.accept()
            return
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
            self.pose = _dependency("POSE")["idle"]
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
    def _home_scene_active(self):
        home_scene = getattr(self, "home_scene_window", None)
        if home_scene is None:
            return False
        try:
            return home_scene.isVisible()
        except RuntimeError:
            return False

    def follow_interface_overlays(self):
        """Keep detached pet UI aligned with the active indoor/outdoor pet."""

        if self._interactive_bubble is not None:
            try:
                if self._interactive_bubble.isVisible():
                    self._interactive_bubble._place_above_pet()
                else:
                    self._interactive_bubble = None
            except RuntimeError:
                self._interactive_bubble = None

        if self._bubble_menu is not None:
            try:
                if self._bubble_menu.isVisible():
                    self._bubble_menu.follow_pet()
                else:
                    self._bubble_menu = None
            except RuntimeError:
                self._bubble_menu = None

        if self._speech_bubble is not None:
            try:
                if self._speech_bubble.isVisible():
                    self._speech_bubble.follow_pet()
            except RuntimeError:
                self._speech_bubble = None

    def on_tick(self):
        if PetWindow._home_scene_active(self):
            return
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

        self.follow_interface_overlays()

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
            self._save_desktop_position()

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
        _dependency("save_state")(self.state)
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
        _dependency("save_state")(self.state)
        self.refresh_pose_from_state()
        self.update()
        return True

    def _update_auto_sleep_state(self, now=None):
        if PetWindow._home_scene_active(self):
            return "home"
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
    def _warm_up_interaction_surfaces(self):
        """Create reusable offscreen menu windows before the first click."""
        if (not self.isVisible() or self._bubble_menu is not None or
                self._prewarmed_bubble_menus):
            return
        for page in ("primary", "interaction", "more"):
            menu = _dependency("BubbleMenu")(
                self, page=page, show_window=False
            )
            menu._prewarming = True
            menu.move(-10000, -10000)
            if menu.stat_bubble is not None:
                menu.stat_bubble.move(-10000, -10000)
                menu.stat_bubble.show()
            menu.show()
            menu.repaint()
            if menu.stat_bubble is not None:
                menu.stat_bubble.repaint()
            menu._anim.stop()
            if menu.stat_bubble is not None:
                menu.stat_bubble._timer.stop()
            self._prewarmed_bubble_menus[page] = menu

    def _create_bubble_menu(self, page="primary"):
        menu = self._prewarmed_bubble_menus.pop(page, None)
        if menu is None:
            return _dependency("BubbleMenu")(self, page=page)
        try:
            menu._prewarming = False
            menu._closing = False
            menu._anim.start(16)
            if menu.stat_bubble is not None:
                menu.stat_bubble._timer.start(500)
                menu.stat_bubble._place()
                menu.stat_bubble.show()
                menu.stat_bubble.raise_()
            menu._place()
            menu.show()
            menu.raise_()
            menu.activateWindow()
            return menu
        except RuntimeError:
            return _dependency("BubbleMenu")(self, page=page)

    def on_decay(self):
        s = self.settings
        effects = progression.upgrade_effects(self.state)
        awake_decay_multiplier = effects["awake_decay_multiplier"]
        decay_rate_multiplier = getattr(
            self, "STAT_DECAY_RATE_MULTIPLIER", 0.5
        )
        if self.state["sleeping"]:
            energy_gain = (
                s["decay_energy_sleeping_gain"]
                + effects["sleep_energy_gain_bonus"]
            )
            hunger_cost = (
                s["decay_hunger_sleeping"]
                * effects["sleep_hunger_multiplier"]
                * decay_rate_multiplier
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
                - s["decay_hunger"] * awake_decay_multiplier
                * decay_rate_multiplier,
            )
            self.state["energy"] = max(
                0,
                self.state["energy"]
                - s["decay_energy"] * awake_decay_multiplier
                * decay_rate_multiplier,
            )
            self.state["mood"] = max(
                0,
                self.state["mood"]
                - s["decay_mood"] * awake_decay_multiplier
                * decay_rate_multiplier,
            )
        _dependency("save_state")(self.state)
        self.refresh_pose_from_state()
        reminder = PetWindow.next_stat_reminder(self)
        if reminder is not None:
            _stat, line = reminder
            self.say(line, 3200)

    def next_stat_reminder(self, now=None):
        """Return the next low-stat line using priority and separate cooldowns."""
        if self.state.get("sleeping"):
            return None
        if PetWindow.treasure_notice_active(self):
            return None
        now = time.time() if now is None else float(now)
        lines = {
            "energy": [
                "主人，我有点困啦，想休息一会儿。",
                "我的精力快见底啦，可以让我睡一觉吗？",
            ],
            "hunger": [
                "主人，我的小肚子空空啦。",
                "到饭饭时间了吗？我有点饿啦。",
            ],
            "mood": [
                "主人，陪我玩一会儿好吗？",
                "我想和你贴贴，摸摸我吧。",
            ],
        }
        last_times = getattr(self, "_last_stat_reminder_t", None)
        if not isinstance(last_times, dict):
            last_times = {key: 0.0 for key in lines}
            self._last_stat_reminder_t = last_times
        for stat in ("energy", "hunger", "mood"):
            if float(self.state.get(stat, 0)) >= 20:
                continue
            last = float(last_times.get(stat, 0.0))
            if now - last < PetWindow.STAT_REMINDER_COOLDOWN_SECONDS:
                continue
            last_times[stat] = now
            return stat, random.choice(lines[stat])
        return None

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
        self._interactive_bubble = _dependency("InteractiveBubble")(self, label, action, color, "")
        self._last_interactive_t = time.time()
        # also show a tiny speech line to draw attention
        if action == "feed":
            self.say("肚子咕咕叫啦，主人看看我～", 2500)
        elif action == "play":
            self.say("心情有点低落，陪我玩一会儿嘛～", 2500)

    def _show_pending_dig_bubble(self):
        if int(self.state.get("pending_dig_reward", 0)) <= 0:
            return False
        menu = getattr(self, "_bubble_menu", None)
        if menu is not None:
            try:
                if menu.isVisible():
                    return False
            except RuntimeError:
                self._bubble_menu = None
        if getattr(self, "_hidden_treasure_bubble", None) is not None:
            return self.restore_treasure_after_menu()
        if self._interactive_bubble is not None:
            try:
                if self._interactive_bubble.isVisible():
                    return False
            except RuntimeError:
                self._interactive_bubble = None
        self._interactive_bubble = _dependency("InteractiveBubble")(
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
        _dependency("save_state")(self.state)
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
                _dependency("save_state")(self.state)
                try:
                    bonus_x, bonus_y = self.interface_bonus_origin(-10)
                    self._last_bonus = _dependency("BonusBubble")(
                        f"Pet币 +{pending}",
                        bonus_x,
                        bonus_y,
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
            self.pose = _dependency("POSE")["sleep"]; return
        if self.dragging:
            self.pose = _dependency("POSE")["drag"]; return
        if self.behavior == "eat":
            self.pose = _dependency("POSE")["eat"]; return
        # Hunger and mood are expressed through nearby action bubbles. Passive
        # appearance always returns to the decorated idle model.
        self.pose = _dependency("POSE")["idle"]

    # ---------- autonomous behavior ----------
    def desktop_autonomy_choices(self):
        """Desktop autonomy can idle, sit, or speak, but never self-walk."""
        s = self.settings
        boost = s.get("chatter_frequency_boost", 1.2)
        ask_weight = (
            s["ask_weight_needy"] if self.needy()
            else s["ask_weight_normal"]
        ) * boost
        return (
            ["idle", "sit", "ask"],
            [
                self.AUTONOMY_IDLE_WEIGHT,
                self.AUTONOMY_SIT_WEIGHT,
                ask_weight,
            ],
        )

    def on_autonomy(self):
        if PetWindow._home_scene_active(self):
            return
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
            choices, weights = self.desktop_autonomy_choices()
            choice = random.choices(
                choices,
                weights=weights,
                k=1
            )[0]
            if choice == "sit":
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
        _dependency("save_state")(self.state)
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
        _dependency("save_state")(self.state)
        self._play_return_pos = QPoint(self.pos())
        scene = _dependency("FetchPlayScene")(self, self._on_play_scene_finished)
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
        self.pose = _dependency("POSE")["idle"]
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
            _dependency("save_state")(self.state)
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
        active_home = getattr(self, "_active_home_interface", None)
        home = active_home() if callable(active_home) else None
        if home is not None:
            home.toggle_home_sleep()
            return
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
        _dependency("save_state")(self.state)
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
        _dependency("save_state")(self.state)
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
        self.pose = _dependency("POSE")["happy"]
        self.trigger_animation("pet")
        self.add_xp(effects["pet_xp"])
        _dependency("save_state")(self.state)

    def contextMenuEvent(self, event):
        """Right-click on the pet -> show the radial bubble menu."""
        self.open_bubble_menu()
        event.accept()

    def open_bubble_menu(self):
        """Replace any existing shortcut canvas with the shared primary menu."""

        now = time.monotonic()
        old = getattr(self, "_bubble_menu", None)
        if (
            old is not None
            and now - self.__dict__.get("_last_bubble_menu_t", 0.0) < 0.25
        ):
            try:
                if old.isVisible():
                    return
            except RuntimeError:
                pass
        self._last_bubble_menu_t = now

        if old is not None:
            try:
                old._close()
            except RuntimeError:
                pass

        status = getattr(self, "_status_bubble", None)
        self._status_bubble = None
        if status is not None:
            try:
                status.close()
            except RuntimeError:
                pass

        PetWindow.hide_treasure_for_menu(self)
        factory = getattr(self, "_create_bubble_menu", None)
        self._bubble_menu = (
            factory()
            if callable(factory)
            else _dependency("BubbleMenu")(self)
        )

    def hide_treasure_for_menu(self):
        """Temporarily hide a pending treasure while the desktop menu is open."""
        bubble = getattr(self, "_interactive_bubble", None)
        if bubble is None or getattr(bubble, "action_name", None) != "dig_reward":
            return False
        try:
            if not bubble.isVisible():
                return False
            bubble.hide()
        except RuntimeError:
            self._interactive_bubble = None
            return False
        self._interactive_bubble = None
        self._hidden_treasure_bubble = bubble
        return True

    def restore_treasure_after_menu(self):
        """Restore the same treasure bubble after all shortcut pages close."""
        if int(self.state.get("pending_dig_reward", 0)) <= 0:
            return False
        menu = getattr(self, "_bubble_menu", None)
        if menu is not None:
            try:
                if menu.isVisible():
                    return False
            except RuntimeError:
                self._bubble_menu = None
        bubble = getattr(self, "_hidden_treasure_bubble", None)
        if bubble is None:
            return False
        self._hidden_treasure_bubble = None
        self._interactive_bubble = bubble
        try:
            bubble._place_above_pet()
            bubble.show()
            bubble.raise_()
        except RuntimeError:
            self._interactive_bubble = None
            return False
        return True

    def chat(self):
        """Open the chat panel beside the pet."""
        profile = self.active_chat_profile()
        if self.chat_win is None:
            self.chat_win = _dependency("ChatWindow")(self, memory_profile=profile)
            # connect AI _dependency("bridge") signals to chat window slots
            _dependency("bridge").token.connect(self.chat_win.on_token)
            _dependency("bridge").done.connect(self.chat_win.on_done)
            _dependency("bridge").error.connect(self.chat_win.on_error)
        else:
            self.chat_win.set_memory_profile(profile)
        self.chat_win.show_near_pet()
        # mark user activity
        self.last_user_t = time.time()

    def active_chat_profile(self):
        """Return the pet identity represented by the currently open scene."""
        home = getattr(self, "home_scene_window", None)
        if home is not None:
            try:
                if home.isVisible():
                    return "home"
            except RuntimeError:
                pass
        return "desktop"

    def open_records(self):
        """Open the lifetime companion record panel."""
        if self.records_win is None:
            self.records_win = _dependency("RecordsWindow")(self, _dependency("save_state"))
        self.records_win.show_near_pet()

    def open_status(self):
        """Open the shared warm attribute card beside the active pet."""
        old = getattr(self, "_status_bubble", None)
        if old is not None:
            try:
                old.close()
            except RuntimeError:
                pass
        self._status_bubble = _dependency("StatBubble")(self)

    def open_achievements(self):
        """Open claimable and upcoming Pet-coin achievements."""
        if self.achievements_win is None:
            self.achievements_win = _dependency("AchievementsWindow")(self, _dependency("save_state"))
        self.achievements_win.show_near_pet()

    def open_shop(self):
        """Open the Pet-coin shop and interaction upgrades."""
        if self.shop_win is None:
            self.shop_win = _dependency("ShopWindow")(self, _dependency("save_state"))
        self.shop_win.show_near_pet()

    def open_home_scene(self):
        """Show the fixed home board and bring the pet into its viewport."""
        if (
            self.home_scene_window is not None
            and self.home_scene_window.isVisible()
        ):
            self.home_scene_window.raise_()
            return
        if self.home_scene_window is None:
            self.home_scene_window = _dependency("HomeSceneWindow")(self, _dependency("save_state"))
        self.home_scene_window.show_scene()
        self.vx = 0
        self.vy = 0
        self.on_ground = True

    def open_minigames(self):
        """Open the expandable mini-game picker."""
        if self.minigames_win is None:
            self.minigames_win = _dependency("MiniGameHubWindow")(self, _dependency("save_state"))
        self.minigames_win.show_near_pet()

    def open_settings(self):
        """Open the settings panel."""
        if self.settings_win is None:
            self.settings_win = _dependency("SettingsWindow")(self)
        else:
            self.settings_win.s = self.settings
        self.settings_win.show_near_pet()

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

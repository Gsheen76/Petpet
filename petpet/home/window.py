"""Home scene board, furniture rendering, and viewport coordination."""

from __future__ import annotations

import os
import math
import time
from dataclasses import dataclass

from PyQt5.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import QWidget

from petpet.progression import core as progression
from petpet.app.pets import pet_asset_path, pet_definition
from petpet.home.pet import (
    HOME_DEFAULT_SLEEP_POINT,
    HomePetController,
    clamp_to_walkable,
    load_home_pet_position,
    route_footprints,
    serialize_home_pet_position,
)
from petpet.home.geometry import (
    HOME_CAMERA_PAN_STEP,
    HOME_CAMERA_REPEAT_STEP,
    HOME_VIEWPORT_SIZE,
    camera_x_for_dog,
    home_decoration_bounds,
    home_decoration_handles,
    pan_viewport_x,
    rotation_from_pointer,
    scene_rect_for_screen,
    scale_from_handle,
)


from petpet.home.rendering import *  # noqa: F401,F403





class HomeSceneWindow(QWidget):
    """Fixed home board rendered behind the independent PetWindow."""

    def __init__(self, pet, save_state):
        super().__init__()
        self.pet = pet
        self.state = pet.state
        self.save_state = save_state
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedHeight(HOME_VIEWPORT_SIZE[1])
        self.background = QPixmap(HOME_BACKGROUND_PATH)
        self.home_pet_walk_down = QPixmap(HOME_PET_WALK_DOWN_PATH)
        self.home_pet_walk_back_right = QPixmap(HOME_PET_WALK_BACK_RIGHT_PATH)
        self.home_pet_idle = QPixmap(HOME_PET_IDLE_PATH)
        self.home_pet_sleep = QPixmap(HOME_PET_SLEEP_PATH)
        self._home_pet_walk_down_is_sheet = True
        self._home_pet_walk_back_right_is_sheet = True
        self._home_pet_sleep_is_sheet = True
        self._home_pet_walk_down_source_rect = None
        self._home_pet_walk_back_right_source_rect = None
        self._home_pet_sleep_source_rect = home_pet_sleep_source_rect(0)
        self._home_pet_idle_source_rect = HOME_PET_IDLE_CONTENT_RECT
        self._home_pet_animation_source_rects = {}
        self._home_pet_directional_walk_frames = {}
        self._home_pet_desktop_walk_frames = ()
        self._home_pet_static_contact = (0.50, 0.55, 0.99)
        self._home_pet_asset_state = {
            "idle": HOME_PET_IDLE_PATH,
            "walk": "home",
            "sleep": "home",
        }
        self.home_nav_paw = QPixmap(HOME_NAV_PAW_PATH)
        self.home_nav_target = QPixmap(HOME_NAV_TARGET_PATH)
        self.home_nav_arrow = QPixmap(HOME_NAV_ARROW_PATH)
        self.furniture = {
            item_id: QPixmap(path)
            for item_id, path in HOME_FURNITURE_PATHS.items()
        }
        self.furniture["home_status_card"] = render_home_status_card(self.state)
        self.action_button_pixmaps = {
            name: QPixmap(path)
            for name, path in HOME_BUTTON_PATHS.items()
        }
        self._manual_destination = None
        self._manual_route = None
        self._destination_fade_started_at = None
        self._reset_home_pet_controller()
        self._dragging_item = None
        self._drag_offset = QPoint()
        self._camera_x = camera_x_for_dog(self.home_pet.position[0], 0)
        self._manual_camera = False
        self._pan_direction = None
        self._selected_furniture = None
        self._editing_gesture = None
        self._decoration_category = "all"
        self._menu_open = False
        self._interaction_menu_open = False
        self._last_pet_tick = time.monotonic()
        self._last_persisted_home_target = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._sync_scene)
        self._timer.start(33)
        self._pan_timer = QTimer(self)
        self._pan_timer.setInterval(55)
        self._pan_timer.timeout.connect(self._repeat_pan)
        self._sync_scene()

    def _screen_rect(self):
        try:
            return self.pet.current_screen_rect()
        except (AttributeError, RuntimeError):
            return self.screen().availableGeometry()

    def _sync_scene(self):
        if not self.isVisible():
            return
        rect = scene_window_geometry(self._screen_rect())
        if self.geometry() != rect:
            self.setGeometry(rect)
        self._advance_home_pet(time.monotonic())
        if not self.is_decorating() or not self._manual_camera:
            self._camera_x = camera_x_for_dog(self.home_pet.position[0], 0)
        follow = getattr(self.pet, "follow_interface_overlays", None)
        if callable(follow):
            follow()
        self.update()

    def scene_canvas_rect(self):
        """Return the right-hand scene canvas in this window's local coordinates."""
        return QRect(
            max(0, self.width() - HOME_VIEWPORT_SIZE[0]),
            0,
            HOME_VIEWPORT_SIZE[0],
            self.height(),
        )

    def _scene_content_offset(self):
        return self.scene_canvas_rect().x()

    def home_pet_visible(self):
        """Return whether the in-scene pet should be rendered."""

        return self.isVisible() and not self.is_decorating()

    def _reset_home_pet_controller(self):
        profile = self._active_pet_profile()
        if profile is not None:
            position = load_home_pet_position(
                profile.get("home_position"),
                clamp=False,
            )
        else:
            position = load_home_pet_position(
                self.state.get("home_scene"),
                self.state.get("home_scene_dog_world_x"),
            )
        self.home_pet = HomePetController(position)
        sleeping = (
            profile.get("sleeping", False)
            if profile is not None
                else self.state.get("sleeping")
        )
        if sleeping:
            self.home_pet.set_sleeping()
        if profile is not None and profile.get("home_position") is not None:
            self.home_pet.position = position

    def _active_pet_profile(self):
        pet_id = self.state.get("active_pet_id")
        pets = self.state.get("pets")
        if not isinstance(pet_id, str) or not isinstance(pets, dict):
            return None
        profile = pets.get(pet_id)
        return profile if isinstance(profile, dict) else None

    @property
    def current_pet_id(self):
        return pet_definition(
            self.state.get("active_pet_id", "lunch_meat")
        )["id"]

    def _save_home_pet_position(self):
        serialized = serialize_home_pet_position(self.home_pet.position)
        profile = self._active_pet_profile()
        if profile is not None:
            profile["home_position"] = [
                round(float(self.home_pet.position[0]), 2),
                round(float(self.home_pet.position[1]), 2),
            ]
        home_scene = self.state.setdefault("home_scene", {})
        home_scene["pet_position"] = serialized
        self.save_state(self.state)

    def refresh_pet_assets(self, pet_id: str | None = None) -> None:
        """Load the home artwork registered for the selected stable pet."""

        self._home_pet_animation_source_rects = {}
        definition = pet_definition(
            pet_id or self.state.get("active_pet_id", "lunch_meat")
        )
        selected_pet_id = definition["id"]
        idle_path = pet_asset_path(selected_pet_id, "home", "idle")
        idle_pixmap = QPixmap(idle_path) if idle_path else QPixmap()

        def resolve(action):
            path = pet_asset_path(selected_pet_id, "home", action)
            if path and not QPixmap(path).isNull():
                return path
            return idle_path

        walk_down_path = resolve("walk_down")
        walk_back_right_path = resolve("walk_back_right")
        sleep_path = resolve("sleep")
        self._home_pet_directional_walk_frames = {}
        home_definition = definition.get("home", {})
        grid_columns = home_definition.get("walk_grid_columns", 0)
        grid_rows = home_definition.get("walk_grid_rows", 0)
        outfit_id = progression.equipped_outfit(self.state)
        outfit_definition = progression.OUTFIT_DEFINITIONS.get(outfit_id, {})
        walk_action = outfit_definition.get("home_walk_action", "walk_right")
        walk_source = pet_asset_path(selected_pet_id, "home", walk_action)
        if isinstance(grid_columns, int) and isinstance(grid_rows, int):
            if walk_source and walk_source != idle_path:
                frames = self._home_walk_grid_frames(
                    walk_source, grid_columns, grid_rows
                )
                if frames:
                    self._home_pet_directional_walk_frames = {
                        "left": frames,
                        "right": frames,
                    }
        self._home_pet_desktop_walk_frames = ()
        if not self._home_pet_directional_walk_frames and walk_down_path == idle_path:
            ensure_walk = getattr(self.pet, "_ensure_animation_loaded", None)
            if callable(ensure_walk):
                ensure_walk("walk")
            frames = getattr(self.pet, "animation_frames", {}).get("walk", ())
            self._home_pet_desktop_walk_frames = tuple(
                frame
                for frame in frames
                if isinstance(frame, QPixmap) and not frame.isNull()
            )
        self.home_pet_idle = idle_pixmap
        self.home_pet_walk_down = QPixmap(walk_down_path) if walk_down_path else QPixmap()
        self.home_pet_walk_back_right = (
            QPixmap(walk_back_right_path) if walk_back_right_path else QPixmap()
        )
        self.home_pet_sleep = QPixmap(sleep_path) if sleep_path else QPixmap()

        def is_sheet(pixmap):
            return (
                not pixmap.isNull()
                and pixmap.width() >= HOME_PET_WALK_FRAME_SIZE * 3
                and pixmap.height() >= HOME_PET_WALK_FRAME_SIZE * 3
            )

        self._home_pet_walk_down_is_sheet = is_sheet(self.home_pet_walk_down)
        self._home_pet_walk_back_right_is_sheet = is_sheet(
            self.home_pet_walk_back_right
        )
        self._home_pet_sleep_is_sheet = is_sheet(self.home_pet_sleep)
        self._home_pet_walk_down_source_rect = (
            None
            if self._home_pet_walk_down_is_sheet
            else home_pet_static_source_rect(self.home_pet_walk_down)
        )
        self._home_pet_walk_back_right_source_rect = (
            None
            if self._home_pet_walk_back_right_is_sheet
            else home_pet_static_source_rect(self.home_pet_walk_back_right)
        )
        self._home_pet_sleep_source_rect = (
            home_pet_sleep_source_rect(0)
            if self._home_pet_sleep_is_sheet
            else home_pet_static_source_rect(self.home_pet_sleep)
        )
        self._home_pet_idle_source_rect = (
            HOME_PET_IDLE_CONTENT_RECT
            if idle_path
            and os.path.normcase(os.path.normpath(idle_path))
            == os.path.normcase(os.path.normpath(HOME_PET_IDLE_PATH))
            else home_pet_static_source_rect(self.home_pet_idle)
        )
        self._home_pet_asset_state = {
            "idle": idle_path,
            "walk": (
                "home_side"
                if self._home_pet_directional_walk_frames
                else "home"
                if walk_down_path and walk_down_path != idle_path
                else "desktop_animation"
                if self._home_pet_desktop_walk_frames
                else "idle"
            ),
            "sleep": "home" if sleep_path and sleep_path != idle_path else "idle",
            "pet_id": selected_pet_id,
            "outfit": outfit_id,
            "walk_source": walk_source,
        }

    @staticmethod
    def _home_walk_grid_frames(path, columns, rows):
        """Split an authored rectangular walk grid into transparent frames."""

        if columns <= 0 or rows <= 0:
            return ()
        sheet = QPixmap(path)
        if sheet.isNull():
            return ()
        frames = []
        for row in range(rows):
            top = round(row * sheet.height() / rows)
            bottom = round((row + 1) * sheet.height() / rows)
            for column in range(columns):
                left = round(column * sheet.width() / columns)
                right = round((column + 1) * sheet.width() / columns)
                frame = sheet.copy(left, top, right - left, bottom - top)
                if not frame.isNull():
                    frames.append(frame)
        return tuple(frames)

    def refresh_active_pet(self) -> None:
        """Reload the selected pet's controller and registered artwork."""
        self._reset_home_pet_controller()
        self.refresh_pet_assets(self.current_pet_id)
        self._clear_manual_destination()
        self._last_persisted_home_target = None
        self._camera_x = camera_x_for_dog(self.home_pet.position[0], 0)
        self._manual_camera = False
        self.furniture["home_status_card"] = render_home_status_card(self.state)
        self.update()

    def home_pet_asset_state(self) -> dict:
        """Return the registered source and fallback kind for boundary tests."""

        return dict(self._home_pet_asset_state)

    def _clear_manual_destination(self):
        self._manual_destination = None
        self._manual_route = None
        self._destination_fade_started_at = None

    def _set_manual_destination(self, target):
        """Capture one immutable world-space route for a manual command."""

        if target is None:
            self._clear_manual_destination()
            return
        start = tuple(float(value) for value in self.home_pet.position)
        end = tuple(float(value) for value in target)
        self._manual_destination = end
        self._manual_route = {
            "start": start,
            "end": end,
            "footprints": route_footprints(start, end),
        }
        self._destination_fade_started_at = None

    def _expire_manual_destination(self, now):
        if (
            self._manual_destination is not None
            and home_destination_opacity(
                self._destination_fade_started_at,
                now,
            ) <= 0.0
        ):
            self._clear_manual_destination()

    def _home_pet_energy(self):
        try:
            energy = float(self.state.get("energy", 100.0))
        except (TypeError, ValueError, OverflowError):
            return 100.0
        return energy if math.isfinite(energy) else 100.0

    def home_sleep_target(self):
        """Return the current rug center or the authored fallback sleep point."""

        if (
            "home_rug" not in self.state.get("owned_home_decorations", [])
            or "home_rug" in self.state.get("home_stored_decorations", [])
        ):
            return HOME_DEFAULT_SLEEP_POINT
        pixmap = self.furniture.get("home_rug")
        if pixmap is None or pixmap.isNull():
            return HOME_DEFAULT_SLEEP_POINT
        try:
            position = progression.home_decoration_position(
                self.state, "home_rug"
            )
            target = (
                float(position["x"]) + pixmap.width() / 2.0,
                float(position["y"]) + pixmap.height() / 2.0,
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            return HOME_DEFAULT_SLEEP_POINT
        if not all(math.isfinite(value) for value in target):
            return HOME_DEFAULT_SLEEP_POINT
        return clamp_to_walkable(target)

    def toggle_home_sleep(self, now=None):
        """Wake in place or walk to the current home sleep target."""

        if not self.home_pet_visible() or self.is_decorating():
            return False
        current = time.monotonic() if now is None else float(now)
        if self.home_pet.state == "sleeping" or self.state.get("sleeping"):
            self.home_pet.target = None
            self.home_pet.state = "idle"
            self.home_pet.sleep_retry_until = current + 45.0
            self.state["sleeping"] = False
            self.state["sleep_mode"] = None
            self._clear_manual_destination()
            self._save_home_pet_position()
            say = getattr(self.pet, "say", None)
            if callable(say):
                say("醒来啦！又可以陪主人了～", 2000)
            sound = getattr(self.pet, "play_sound", None)
            if callable(sound):
                sound("bark")
            self.update()
            return True

        self.home_pet.cancel_target()
        target = self.home_sleep_target()
        self.home_pet.last_player_command_at = current
        if not self.home_pet.request_manual_sleep(target, current):
            return False
        self.state["sleeping"] = False
        self.state["sleep_mode"] = None
        self._set_manual_destination(target)
        say = getattr(self.pet, "say", None)
        if callable(say):
            say("去小垫子上睡觉啦～", 2200)
        self.update()
        return True

    def _advance_home_pet(self, now=None):
        """Advance the in-scene pet and synchronize shared sleep transitions."""

        current = time.monotonic() if now is None else float(now)
        self._expire_manual_destination(current)
        elapsed = max(0.0, current - self._last_pet_tick)
        self._last_pet_tick = current
        if self.is_decorating():
            return ()

        energy = self._home_pet_energy()
        wake_threshold = float(
            getattr(self.pet, "auto_wake_energy_threshold", 80.0)
        )
        if (
            self.state.get("sleep_mode") == "auto"
            and self.home_pet.wake_if_recovered(energy, wake_threshold)
        ):
            self.state["sleeping"] = False
            self.state["sleep_mode"] = None
            self._save_home_pet_position()
            return ()

        sleep_threshold = float(
            getattr(self.pet, "auto_sleep_energy_threshold", 30.0)
        )
        if self.home_pet.state == "idle" and energy < sleep_threshold:
            self.home_pet.request_auto_sleep(
                self.home_sleep_target(), current
            )
        elif self.home_pet.state == "idle":
            if self.home_pet.maybe_start_autonomous_walk(current):
                progression.record_action(
                    self.state, "autonomous_walks"
                )

        target_before = self.home_pet.target
        events = self.home_pet.advance(elapsed)
        if "manual_sleep_started" in events:
            self.state["sleeping"] = True
            self.state["sleep_mode"] = "manual"
            progression.record_sleep(self.state, "manual")
            if self._manual_destination is not None:
                self._destination_fade_started_at = current
            self._save_home_pet_position()
            sound = getattr(self.pet, "play_sound", None)
            if callable(sound):
                sound("sleep")
        elif "sleep_started" in events:
            self.state["sleeping"] = True
            self.state["sleep_mode"] = "auto"
            progression.record_sleep(self.state, "auto")
            self._save_home_pet_position()
        elif "arrived" in events:
            if self._manual_destination is not None:
                self._destination_fade_started_at = current
            self._save_home_pet_position()
            self._last_persisted_home_target = None
        elif target_before is not None and self.home_pet.target is not None:
            if target_before != self._last_persisted_home_target:
                self._save_home_pet_position()
                self._last_persisted_home_target = target_before
        return events

    def pan_view(self, direction, step=HOME_CAMERA_PAN_STEP):
        """Pan the authored world viewport and persist the new camera position."""
        if not self.view_pan_enabled():
            return self._camera_x
        self._camera_x = pan_viewport_x(self._camera_x, direction, step)
        self._manual_camera = True
        home_scene = self.state.setdefault("home_scene", {})
        home_scene["viewport_x"] = self._camera_x
        home_scene["viewport_pinned"] = True
        self.save_state(self.state)
        self.update()
        return self._camera_x

    def begin_pan(self, direction):
        if direction not in ("left", "right") or not self.view_pan_enabled():
            return
        self._pan_direction = direction
        self.pan_view(direction)
        self._pan_timer.start()

    def _repeat_pan(self):
        if self._pan_direction is not None:
            self.pan_view(self._pan_direction, HOME_CAMERA_REPEAT_STEP)

    def end_pan(self):
        self._pan_direction = None
        self._pan_timer.stop()

    def _set_pet_visible(self, visible):
        action = getattr(self.pet, "show" if visible else "hide", None)
        if callable(action):
            action()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        canvas = self.scene_canvas_rect()
        clip = QPainterPath()
        clip.addRoundedRect(
            QRectF(canvas), HOME_SCENE_CORNER_RADIUS, HOME_SCENE_CORNER_RADIUS
        )
        painter.setClipPath(clip)
        painter.fillRect(canvas, QColor("#f3dfc4"))
        if not self.background.isNull():
            source = QRect(self._camera_x, 0, canvas.width(), canvas.height())
            painter.drawPixmap(canvas, self.background, source)
        for _depth, kind, item_id in self._scene_render_entries():
            if kind == "pet":
                self._draw_home_pet(painter)
                continue
            if kind == "navigation":
                self._draw_navigation_feedback(painter)
                continue
            position = self.state.get("home_decoration_positions", {}).get(
                item_id, {}
            )
            self._draw_furniture(painter, item_id, position)
        if self.is_decorating() and self._selected_furniture is not None:
            self._draw_selection(painter, self._selected_furniture)
        if self.view_pan_enabled():
            self._draw_scene_button(painter, self.left_view_button_rect(), "左移")
            self._draw_scene_button(painter, self.right_view_button_rect(), "右移")
        if self._menu_open:
            menu_labels = {"shop": "商店", "decorate": "装修", "exit": "退出"}
            for action, rect in self.menu_item_rects().items():
                self._draw_action_button(painter, rect, action, menu_labels[action])
        if self._interaction_menu_open:
            interaction_labels = {
                "pet": "抚摸",
                "feed": "喂食",
                "play": "玩耍",
                "sleep": "睡觉",
            }
            attention = self.interaction_actions_needing_attention()
            for action, rect in self.interaction_item_rects().items():
                self._draw_action_button(
                    painter, rect, action, interaction_labels[action]
                )
                if action in attention:
                    self._draw_attention_dot(painter, rect.topRight())
        self._draw_action_button(
            painter, self.interaction_toggle_rect(), "interaction_toggle", ""
        )
        self._draw_action_button(
            painter, self.menu_toggle_rect(), "menu_toggle", ""
        )
        if self.interaction_header_needs_attention() and not self._interaction_menu_open:
            self._draw_attention_dot(
                painter, self.interaction_toggle_rect().topRight()
            )
        painter.restore()
        if self.is_decorating():
            self._draw_decoration_panel(painter)
        painter.end()

    def show_scene(self):
        progression.ensure_progression(self.state)
        self.refresh_pet_assets()
        self._menu_open = False
        self._interaction_menu_open = False
        self._clear_manual_destination()
        self._reset_home_pet_controller()
        self.state.setdefault("home_scene", {})["enabled"] = True
        saved_scene = self.state["home_scene"]
        saved_scene["decorating"] = False
        saved_scene["viewport_pinned"] = False
        self._manual_camera = False
        self._camera_x = camera_x_for_dog(self.home_pet.position[0], 0)
        hide_overlays = getattr(self.pet, "hide_overlays", None)
        if callable(hide_overlays):
            hide_overlays()
        self._set_pet_visible(False)
        self.show()
        self.raise_()
        self._sync_scene()
        self.save_state(self.state)

    def hide_scene(self):
        self._menu_open = False
        self._interaction_menu_open = False
        self.state.setdefault("home_scene", {})["enabled"] = False
        hide_overlays = getattr(self.pet, "hide_overlays", None)
        if callable(hide_overlays):
            hide_overlays()
        self.end_pan()
        self.state["home_scene"]["decorating"] = False
        self._selected_furniture = None
        self._clear_manual_destination()
        self.home_pet.cancel_target()
        self._save_home_pet_position()
        self.hide()
        self._set_pet_visible(True)
        show_treasure = getattr(self.pet, "_show_pending_dig_bubble", None)
        if callable(show_treasure):
            show_treasure()
        raise_pet = getattr(self.pet, "raise_", None)
        if callable(raise_pet):
            raise_pet()

    def interaction_toggle_rect(self):
        """Left toggle (interaction) beside the menu toggle."""
        menu_toggle = self.menu_toggle_rect()
        width, height = HOME_TOGGLE_SIZE
        return QRect(
            menu_toggle.left() - 8 - width,
            menu_toggle.top(),
            width,
            height,
        )

    def menu_toggle_rect(self):
        """Right toggle (menu), the pair centered under the item stacks."""
        canvas = self.scene_canvas_rect()
        width, height = HOME_TOGGLE_SIZE
        stack_right = canvas.right() - 14 - 12
        pair_width = 2 * width + 8
        right = stack_right - max(
            0, (HOME_BUTTON_SIZE[0] - pair_width) // 2
        )
        return QRect(
            right - width + 1,
            self._toggle_top(),
            width,
            height,
        )

    def _toggle_top(self):
        canvas = self.scene_canvas_rect()
        _, height = HOME_TOGGLE_SIZE
        return canvas.bottom() - 14 - height + 1

    def interaction_item_rects(self):
        """Items stacked upward above the toggle pair."""
        return self._stacked_item_rects(("pet", "feed", "play", "sleep"))

    def menu_item_rects(self):
        """Items stacked upward above the toggle pair."""
        return self._stacked_item_rects(("shop", "decorate", "exit"))

    def _stacked_item_rects(self, names):
        """Items stack upward, centered over their circular toggle."""
        width, height = HOME_BUTTON_SIZE
        gap = 7
        bottom = self._toggle_top() - 6
        rects = {}
        toggles = (
            self.menu_toggle_rect()
            if names[0] == "shop"
            else self.interaction_toggle_rect()
        )
        center = toggles.center().x()
        # QRect.center() truncates; offset by (width-1)//2 so the printed
        # center lands exactly on the toggle center.
        left = center - (width - 1) // 2
        for index, name in enumerate(names):
            item_bottom = bottom - index * (height + gap)
            rects[name] = QRect(
                left,
                item_bottom - height + 1,
                width,
                height,
            )
        return rects

    # Compatibility aliases kept for tests and external callers.
    def home_action_toggle_rect(self):
        return self.menu_toggle_rect()

    def home_action_button_rects(self):
        return self.menu_item_rects()

    def exit_button_rect(self):
        return self.menu_item_rects()["exit"]

    def decoration_button_rect(self):
        return self.menu_item_rects()["decorate"]

    def shop_button_rect(self):
        return self.menu_item_rects()["shop"]

    def interaction_button_rect(self):
        return self.interaction_toggle_rect()

    def home_interaction_action_rects(self):
        return self.interaction_item_rects()

    def left_view_button_rect(self):
        return QRect(
            self._scene_content_offset() + 14,
            max(14, (self.height() - 44) // 2),
            68,
            44,
        )

    def right_view_button_rect(self):
        canvas = self.scene_canvas_rect()
        return QRect(
            canvas.right() - 68 + 1,
            max(14, (self.height() - 44) // 2),
            68,
            44,
        )

    def decoration_panel_close_button_rect(self):
        panel = self._panel_rect()
        size = 30
        margin = 10
        return QRect(
            panel.right() - margin - size + 1,
            panel.top() + margin,
            size,
            size,
        )

    @staticmethod
    def scene_button_label(button):
        return {
            "left": "左移",
            "right": "右移",
            "menu": "菜单⌃",
            "shop": "商店",
            "interaction": "互动",
            "decorate": "装修",
            "exit": "退出",
        }.get(button, "")

    def _needs_menu_attention(self):
        """The menu toggle currently has no red-dot condition."""
        return False

    @staticmethod
    def _cute_button_font():
        """Return the cutest rounded CJK font available on this system."""
        families = set(QFontDatabase().families())
        for preferred in ("幼圆", "YouYuan", "华文琥珀", "楷体", "微软雅黑"):
            for family in families:
                if family.startswith(preferred):
                    font = QFont(family)
                    font.setBold(True)
                    font.setPixelSize(17)
                    return font
        font = QFont()
        font.setBold(True)
        font.setPixelSize(17)
        return font


    def _draw_action_button(self, painter, rect, name, label):
        """Draw one image button, with an optional runtime label overlay."""
        pixmap = self.action_button_pixmaps.get(name)
        if pixmap is None or pixmap.isNull():
            self._draw_scene_button(painter, rect, label, variant="menu_item")
            return
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawPixmap(rect, pixmap)
        if label:
            painter.setFont(self._cute_button_font())
            painter.setPen(QColor("#9A5B3F"))
            text_rect = rect.adjusted(
                int(rect.width() * 0.55), 0, -int(rect.width() * 0.18), 0
            )
            painter.drawText(text_rect, Qt.AlignCenter, label)
        painter.restore()

    def _draw_scene_button(self, painter, rect, label, variant="primary"):
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(78, 47, 36, 76))
        painter.drawRoundedRect(rect.translated(0, 3), 14, 14)
        if variant == "menu_item":
            fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            fill.setColorAt(0, QColor(255, 252, 246, 248))
            fill.setColorAt(1, QColor(250, 230, 211, 248))
            border = QColor("#d89b7d")
            text = QColor("#754532")
        else:
            fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            fill.setColorAt(0, QColor("#f59378"))
            fill.setColorAt(1, QColor("#d96f59"))
            border = QColor("#ffe5cf")
            text = QColor("#fffaf3")
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 14, 14)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 13, 13)
        font = painter.font()
        font.setBold(variant == "menu_toggle")
        painter.setFont(font)
        painter.setPen(text)
        painter.drawText(rect, Qt.AlignCenter, label)
        painter.restore()

    @staticmethod
    def _draw_attention_dot(painter, anchor):
        painter.save()
        painter.setPen(QPen(QColor("#fff7ef"), 2))
        painter.setBrush(QColor("#f05f62"))
        painter.drawEllipse(QPointF(anchor.x() - 3, anchor.y() + 4), 6, 6)
        painter.restore()

    def interaction_actions_needing_attention(self):
        record_actions = progression.zero_stat_interaction_actions(self.state)
        return {
            {
                "pettings": "pet",
                "feedings": "feed",
                "play_sessions": "play",
                "manual_sleeps": "sleep",
            }[action]
            for action in record_actions
        }

    def home_pet_needs_attention(self):
        return bool(self.interaction_actions_needing_attention())

    def interaction_header_needs_attention(self):
        return self.home_pet_needs_attention()

    def trigger_home_interaction(self, action):
        method_name = {
            "pet": "pet_click",
            "feed": "feed",
            "play": "play",
            "sleep": "toggle_sleep",
        }.get(action)
        method = getattr(self.pet, method_name, None) if method_name else None
        if not callable(method):
            return False
        self.home_pet.last_player_command_at = time.monotonic()
        method()
        self._menu_open = False
        self._interaction_menu_open = False
        self.update()
        return True

    def is_decorating(self):
        return bool(self.state.get("home_scene", {}).get("decorating", False))

    def view_pan_enabled(self):
        """Manual home viewport controls are available only while decorating."""
        return self.is_decorating()

    def toggle_decoration_mode(self):
        decorating = not self.is_decorating()
        self._menu_open = False
        self._interaction_menu_open = False
        home_scene = self.state.setdefault("home_scene", {})
        home_scene["decorating"] = decorating
        if decorating:
            hide_overlays = getattr(self.pet, "hide_overlays", None)
            if callable(hide_overlays):
                hide_overlays()
            self._clear_manual_destination()
            self.home_pet.cancel_target()
            self._manual_camera = True
            home_scene["viewport_x"] = self._camera_x
            home_scene["viewport_pinned"] = True
        else:
            self.end_pan()
            self._manual_camera = False
            home_scene["viewport_pinned"] = False
            self._camera_x = camera_x_for_dog(self.home_pet.position[0], 0)
            self._selected_furniture = None
            self._dragging_item = None
            self._editing_gesture = None
        self.save_state(self.state)
        self.update()
        return decorating

    def select_furniture(self, decoration_id):
        if decoration_id in self.state.get("owned_home_decorations", []):
            self._selected_furniture = decoration_id
            self.update()

    def store_furniture(self, decoration_id):
        if not self.is_decorating():
            return False
        result = progression.store_home_decoration(self.state, decoration_id)
        if result:
            if self._selected_furniture == decoration_id:
                self._selected_furniture = None
            self.save_state(self.state)
            self.update()
        return result

    def place_furniture(self, decoration_id):
        if not self.is_decorating():
            return False
        result = progression.place_home_decoration(self.state, decoration_id)
        if result:
            self.save_state(self.state)
            self.update()
        return result

    def adjust_selected_furniture(self, kind, amount):
        if not self.is_decorating() or self._selected_furniture is None:
            return None
        transform = progression.home_decoration_transform(
            self.state, self._selected_furniture
        )
        if kind == "scale":
            transform["scale"] += float(amount)
        elif kind == "rotation":
            transform["rotation"] += float(amount)
        else:
            return None
        result = progression.set_home_decoration_transform(
            self.state, self._selected_furniture, **transform
        )
        self.save_state(self.state)
        self.update()
        return result

    def _draw_furniture(self, painter, decoration_id, position):
        pixmap = (
            render_home_status_card(self.state)
            if decoration_id == "home_status_card"
            else self.furniture.get(decoration_id)
        )
        if pixmap is None or pixmap.isNull():
            return
        transform = progression.home_decoration_transform(self.state, decoration_id)
        logical_width, logical_height = progression.HOME_DECORATION_DEFINITIONS[
            decoration_id
        ]["size"]
        painter.save()
        painter.translate(
            self._scene_content_offset()
            + int(position.get("x", 0))
            - self._camera_x
            + logical_width / 2,
            int(position.get("y", 0)) + logical_height / 2,
        )
        painter.rotate(transform["rotation"])
        painter.scale(transform["scale"], transform["scale"])
        painter.drawPixmap(
            QRectF(
                -logical_width / 2,
                -logical_height / 2,
                logical_width,
                logical_height,
            ),
            pixmap,
            QRectF(0, 0, pixmap.width(), pixmap.height()),
        )
        painter.restore()

    def home_pet_draw_rect(
        self,
        visual_scale=1.0,
        aspect_ratio=512.0 / 464.0,
    ):
        """Return the home-pet artwork rect anchored to its world-space feet."""

        world_x, world_y = self.home_pet.position
        height = 464.0 * 0.23 * HOME_PET_FIXED_DEPTH_SCALE * visual_scale
        width = height * float(aspect_ratio)
        center_x = self._scene_content_offset() + world_x - self._camera_x
        return QRectF(
            center_x - width / 2.0,
            world_y - height,
            width,
            height,
        )

    def _home_pet_body_scale(self):
        """Per-pet body scale; ice cream renders 10% smaller at home."""

        return 0.9 if self.current_pet_id == "ice_cream" else 1.0

    def home_pet_render_rect(self, render_spec):
        """Return a foot-anchored rect without stretching the source artwork."""

        if render_spec is None or render_spec.source_rect.height() <= 0:
            return self.home_pet_draw_rect()
        return self.home_pet_draw_rect(
            render_spec.visual_scale * self._home_pet_body_scale(),
            render_spec.source_rect.width() / render_spec.source_rect.height(),
        )

    def home_pet_hit_rect(self):
        """Return the local rendered body rectangle used for pointer hits."""

        return self.home_pet_render_rect(self.home_pet_render_spec())

    def home_pet_global_rect(self):
        """Return the rendered home-pet body in global screen coordinates."""

        local = self.home_pet_hit_rect().toAlignedRect()
        return QRect(self.mapToGlobal(local.topLeft()), local.size())

    def open_home_pet_menu(self, point):
        """The home scene deliberately owns no right-click shortcut menu."""
        return False

    def home_pet_walk_frame(self, now=None):
        """Return the current authored frame, holding frame zero while idle."""

        if self.home_pet.state not in {
            "manual_walk",
            "auto_walk",
            "manual_sleep_walk",
            "auto_sleep_walk",
        }:
            return 0
        current = time.monotonic() if now is None else max(0.0, float(now))
        return int(current * HOME_PET_WALK_FPS)

    def home_pet_sleep_frame(self, now=None):
        """Return the current sleep frame at its deliberately gentle cadence."""

        if self.home_pet.state != "sleeping":
            return 0
        current = time.monotonic() if now is None else max(0.0, float(now))
        return int(current * HOME_PET_SLEEP_FPS) % HOME_PET_SLEEP_FRAME_COUNT

    def home_pet_walk_render_spec(self, now=None):
        """Return all artwork and foot-contact data for the active walk frame."""

        if self.home_pet.state == "sleeping":
            return None
        # Ice cream's two sheets are diagonals keyed by the movement delta:
        # upward walks use the back sheet (mirrored for up-left), downward
        # walks the front sheet (mirrored for down-right); pure horizontal
        # travel follows the last horizontal side.
        if (
            self.current_pet_id == "ice_cream"
            and self.home_pet.state in {
                "manual_walk", "auto_walk",
                "manual_sleep_walk", "auto_sleep_walk",
            }
        ):
            dx = getattr(self.home_pet, "last_move_dx", 0.0)
            dy = getattr(self.home_pet, "last_move_dy", 0.0)
            side_left = self.home_pet.direction == "left"
            use_back = (dy < 0) or (dy == 0 and not side_left)
            if use_back:
                if self.home_pet_walk_back_right.isNull():
                    return None
                spec_pixmap = self.home_pet_walk_back_right
                mirrored = dx < 0 or (dx == 0 and side_left)
                visual_scale = 1.08
                contact_width = 0.52
                # Walking away: the shadow sits higher on the body.
                contact_foot_y = 0.90
            else:
                if self.home_pet_walk_down.isNull():
                    return None
                spec_pixmap = self.home_pet_walk_down
                mirrored = (dy > 0 and dx < 0) or (dx == 0 and side_left)
                visual_scale = 0.92
                contact_width = 0.52
                contact_foot_y = 0.98
            frame_index = self.home_pet_walk_frame(now) % (
                HOME_PET_WALK_FRAME_COUNT
            )
            # The shadow tracks the body; mirroring flips the art across
            # the center line, so the contact center flips with it.
            contact_center = 0.45 if mirrored else 0.55
            # Shadow slant swaps on the down diagonals only; the art
            # itself never flips here.
            # Ice cream: up-left walks slant -16, the rest +16.
            shadow_slant = -16 if mirrored else 16
            self._walk_shadow_slant = shadow_slant
            return HomePetWalkRenderSpec(
                pixmap=spec_pixmap,
                source_rect=home_pet_walk_source_rect(frame_index),
                mirrored=mirrored,
                frame_index=frame_index,
                visual_scale=visual_scale,
                contact_center_x=contact_center,
                contact_width=contact_width,
                contact_foot_y=contact_foot_y,
            )
        frame = self.home_pet_walk_frame(now)
        directional_walk_frames = self._home_pet_directional_walk_frames.get(
            self.home_pet.direction, ()
        )
        if directional_walk_frames:
            frame_index = frame % len(directional_walk_frames)
            pixmap = directional_walk_frames[frame_index]
            source_rect = self._shared_animation_source_rect(
                {
                    "name": f"home_{self.home_pet.direction}_walk",
                    "pixmap": pixmap,
                    "frames": directional_walk_frames,
                }
            )
            return HomePetWalkRenderSpec(
                pixmap=pixmap,
                source_rect=source_rect,
                mirrored=self.home_pet.direction == "left",
                frame_index=frame_index,
                visual_scale=1.0,
                contact_center_x=0.50,
                contact_width=0.55,
                contact_foot_y=0.98,
            )
        desktop_walk_frames = self._home_pet_desktop_walk_frames
        if desktop_walk_frames:
            frame_index = frame % len(desktop_walk_frames)
            pixmap = desktop_walk_frames[frame_index]
            source_rect = self._shared_animation_source_rect(
                {
                    "name": "home_desktop_walk",
                    "pixmap": pixmap,
                    "frames": desktop_walk_frames,
                }
            )
            return HomePetWalkRenderSpec(
                pixmap=pixmap,
                source_rect=source_rect,
                mirrored=self.home_pet.direction in {"front_left", "back_left", "left"},
                frame_index=frame_index,
                visual_scale=1.0,
                contact_center_x=0.50,
                contact_width=0.55,
                contact_foot_y=0.98,
            )
        contact = home_pet_frame_contact(self.home_pet.direction, frame)
        if self.home_pet.direction in {
            "front", "front_left", "front_right", "left", "right"
        }:
            if self.home_pet_walk_down.isNull():
                return None
            source_rect = (
                home_pet_walk_source_rect(frame)
                if self._home_pet_walk_down_is_sheet
                else self._home_pet_walk_down_source_rect
            )
            contact = (
                contact
                if self._home_pet_walk_down_is_sheet
                else self._home_pet_static_contact
            )
            return HomePetWalkRenderSpec(
                pixmap=self.home_pet_walk_down,
                source_rect=source_rect,
                mirrored=self.home_pet.direction in {"front_left", "left"},
                frame_index=frame if self._home_pet_walk_down_is_sheet else 0,
                visual_scale=1.0,
                contact_center_x=contact[0],
                contact_width=contact[1],
                contact_foot_y=contact[2],
            )
        if self.home_pet.direction in {"back", "back_left", "back_right"}:
            if self.home_pet_walk_back_right.isNull():
                return None
            source_rect = (
                home_pet_back_walk_source_rect(frame)
                if self._home_pet_walk_back_right_is_sheet
                else self._home_pet_walk_back_right_source_rect
            )
            contact = (
                contact
                if self._home_pet_walk_back_right_is_sheet
                else self._home_pet_static_contact
            )
            return HomePetWalkRenderSpec(
                pixmap=self.home_pet_walk_back_right,
                source_rect=source_rect,
                mirrored=self.home_pet.direction == "back_left",
                frame_index=frame if self._home_pet_walk_back_right_is_sheet else 0,
                visual_scale=1.06,
                contact_center_x=contact[0],
                contact_width=contact[1],
                contact_foot_y=contact[2],
            )
        return None

    def _shared_animation_source_rect(self, shared):
        """Return the stable crop cached for one pet animation sequence."""

        name = str(shared.get("name", "idle"))
        key = (self.current_pet_id, name)
        cached = self._home_pet_animation_source_rects.get(key)
        if cached is not None:
            return cached
        frames = shared.get("frames") or getattr(
            self.pet, "animation_frames", {}
        ).get(name, ())
        source_rect = home_pet_animation_source_rect(frames)
        if source_rect.isEmpty():
            source_rect = home_pet_static_source_rect(shared["pixmap"])
        self._home_pet_animation_source_rects[key] = QRect(source_rect)
        return source_rect

    def home_pet_render_spec(self, now=None):
        """Return the authored artwork for the current home-pet state."""

        if self.home_pet.state == "sleeping":
            if self.home_pet_sleep.isNull():
                return None
            frame = self.home_pet_sleep_frame(now)
            source_rect = (
                home_pet_sleep_source_rect(frame)
                if self._home_pet_sleep_is_sheet
                else self._home_pet_sleep_source_rect
            )
            contact = (
                (0.50, 0.84, 0.98)
                if self._home_pet_sleep_is_sheet
                else self._home_pet_static_contact
            )
            return HomePetWalkRenderSpec(
                pixmap=self.home_pet_sleep,
                source_rect=source_rect,
                mirrored=False,
                frame_index=frame if self._home_pet_sleep_is_sheet else 0,
                visual_scale=(
                    HOME_PET_SLEEP_VISUAL_SCALE
                    if self.current_pet_id == "ice_cream"
                    else HOME_PET_DEFAULT_SLEEP_VISUAL_SCALE
                ),
                contact_center_x=contact[0],
                contact_width=contact[1],
                contact_foot_y=contact[2],
            )

        if self.home_pet.state not in {
            "manual_walk",
            "auto_walk",
            "manual_sleep_walk",
            "auto_sleep_walk",
        }:
            shared_frame = getattr(self.pet, "shared_animation_frame", None)
            shared = shared_frame() if callable(shared_frame) else None
            if shared and not shared["pixmap"].isNull():
                scale = shared.get("spec", {}).get("scale", 1.0)
                try:
                    scale = max(0.1, float(scale))
                except (TypeError, ValueError):
                    scale = 1.0
                return HomePetWalkRenderSpec(
                    pixmap=shared["pixmap"],
                    source_rect=self._shared_animation_source_rect(shared),
                    mirrored=False,
                    frame_index=int(shared.get("frame_index", 0)),
                    visual_scale=scale,
                    contact_center_x=0.5,
                    contact_width=0.7,
                    contact_foot_y=0.98,
                )

        if self.home_pet.state == "idle" and not self.home_pet_idle.isNull():
            idle_mirrored = (
                self.current_pet_id == "ice_cream"
                and (
                    self.home_pet.last_move_dx < 0
                    or (
                        self.home_pet.last_move_dx == 0
                        and self.home_pet.direction == "left"
                    )
                )
            )
            return HomePetWalkRenderSpec(
                pixmap=self.home_pet_idle,
                source_rect=self._home_pet_idle_source_rect,
                mirrored=idle_mirrored,
                frame_index=0,
                visual_scale=1.0,
                contact_center_x=0.55,
                contact_width=0.55,
                contact_foot_y=0.99,
            )
        return self.home_pet_walk_render_spec(now)

    def navigation_feedback(self, now=None):
        """Return transient screen-space path and destination geometry."""

        if self._manual_destination is None or not self.home_pet_visible():
            return None
        current = time.monotonic() if now is None else float(now)
        opacity = home_destination_opacity(
            self._destination_fade_started_at,
            current,
        )
        if opacity <= 0.0:
            return None
        end_x, end_y = self._manual_destination
        route = self._manual_route
        if route is None or route.get("end") != self._manual_destination:
            start = tuple(float(value) for value in self.home_pet.position)
            route = {
                "start": start,
                "end": self._manual_destination,
                "footprints": route_footprints(
                    start,
                    self._manual_destination,
                ),
            }
        start_x, start_y = route["start"]
        offset = self._scene_content_offset() - self._camera_x
        footprint_height = 22.0
        footprint_width = footprint_height * (
            HOME_NAV_PAW_CONTENT_RECT.width()
            / HOME_NAV_PAW_CONTENT_RECT.height()
        )
        footprints = []
        route_dx = end_x - start_x
        route_dy = end_y - start_y
        route_length_sq = route_dx * route_dx + route_dy * route_dy
        pet_x, pet_y = self.home_pet.position
        pet_progress = (
            (pet_x - start_x) * route_dx
            + (pet_y - start_y) * route_dy
        )
        passed_tolerance = 6.0 * math.sqrt(route_length_sq)
        for placement in route["footprints"]:
            footprint_progress = (
                (placement["x"] - start_x) * route_dx
                + (placement["y"] - start_y) * route_dy
            )
            if footprint_progress <= pet_progress + passed_tolerance:
                continue
            center = QPointF(offset + placement["x"], placement["y"])
            footprints.append({
                "rect": QRectF(
                    center.x() - footprint_width / 2.0,
                    center.y() - footprint_height / 2.0,
                    footprint_width,
                    footprint_height,
                ),
                "angle": placement["angle"] + 90.0,
                "mirrored": placement["mirrored"],
            })
        end = QPointF(offset + end_x, end_y)
        pulse = 1.0 + 0.04 * math.sin(current * math.tau / 0.9)
        target_height = 24.0 * pulse
        target_width = target_height * (
            HOME_NAV_TARGET_CONTENT_RECT.width()
            / HOME_NAV_TARGET_CONTENT_RECT.height()
        )
        target_rect = QRectF(
            end.x() - target_width / 2.0,
            end.y() - target_height / 2.0,
            target_width,
            target_height,
        )
        arrow_offset = 2.5 * math.sin(current * math.tau / 0.9)
        arrow_height = 27.0 * pulse
        arrow_width = arrow_height * (
            HOME_NAV_ARROW_CONTENT_RECT.width()
            / HOME_NAV_ARROW_CONTENT_RECT.height()
        )
        arrow_rect = QRectF(
            end.x() - arrow_width / 2.0,
            target_rect.top() - arrow_height - 2.0 + arrow_offset,
            arrow_width,
            arrow_height,
        )
        return {
            "start": QPointF(offset + start_x, start_y),
            "end": end,
            "opacity": opacity,
            "pulse": pulse,
            "footprints": tuple(footprints),
            "target_rect": target_rect,
            "arrow_rect": arrow_rect,
            "arrow_offset": arrow_offset,
        }

    @staticmethod
    def _draw_navigation_pixmap(
        painter,
        pixmap,
        source_rect,
        target_rect,
        *,
        rotation=0.0,
        mirrored=False,
        opacity=1.0,
    ):
        """Draw one alpha asset centered, rotated, and never stretched."""

        if pixmap is None or pixmap.isNull() or target_rect.isEmpty():
            return
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setOpacity(max(0.0, min(1.0, float(opacity))))
        center = target_rect.center()
        painter.translate(center)
        painter.rotate(float(rotation))
        if mirrored:
            painter.scale(-1.0, 1.0)
        local_target = QRectF(
            -target_rect.width() / 2.0,
            -target_rect.height() / 2.0,
            target_rect.width(),
            target_rect.height(),
        )
        painter.drawPixmap(local_target, pixmap, QRectF(source_rect))
        painter.restore()

    def _draw_navigation_feedback(self, painter, now=None):
        """Draw the manual route and warm destination marker on the floor."""

        feedback = self.navigation_feedback(now)
        if feedback is None:
            return
        opacity = feedback["opacity"]

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        for footprint in feedback["footprints"]:
            self._draw_navigation_pixmap(
                painter,
                self.home_nav_paw,
                HOME_NAV_PAW_CONTENT_RECT,
                footprint["rect"],
                rotation=footprint["angle"],
                mirrored=footprint["mirrored"],
                opacity=opacity * 0.82,
            )
        self._draw_navigation_pixmap(
            painter,
            self.home_nav_target,
            HOME_NAV_TARGET_CONTENT_RECT,
            feedback["target_rect"],
            opacity=opacity,
        )
        self._draw_navigation_pixmap(
            painter,
            self.home_nav_arrow,
            HOME_NAV_ARROW_CONTENT_RECT,
            feedback["arrow_rect"],
            opacity=opacity,
        )
        painter.restore()

    def _draw_home_pet(self, painter):
        """Draw the replaceable four-direction placeholder pet."""

        if not self.home_pet_visible():
            return
        render_spec = self.home_pet_render_spec()
        body = self.home_pet_render_rect(render_spec)
        if render_spec is None:
            contact = home_pet_frame_contact(self.home_pet.direction, 0)
        else:
            contact = (
                render_spec.contact_center_x,
                render_spec.contact_width,
                render_spec.contact_foot_y,
            )
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        if render_spec is None or self.home_pet.state != "sleeping":
            shadow = home_pet_shadow_rect(body, contact)
            painter.setPen(Qt.NoPen)
            ice_walking = (
                self.current_pet_id == "ice_cream"
                and self.home_pet.state in {
                    "manual_walk", "auto_walk",
                    "manual_sleep_walk", "auto_sleep_walk",
                }
            )
            if ice_walking:
                # Directional slanted shadow only for ice cream's walks;
                # lunch meat and idle states keep the flat original.
                painter.setBrush(QColor(91, 64, 45, 55))
                slant = getattr(self, "_walk_shadow_slant", -16)
                painter.save()
                painter.translate(shadow.center())
                painter.rotate(slant)
                painter.drawEllipse(QRectF(
                    -shadow.width() / 2.0, -shadow.height() / 2.0,
                    shadow.width(), shadow.height(),
                ))
                painter.restore()
            else:
                painter.setBrush(QColor(91, 64, 45, 42))
                painter.drawEllipse(shadow)

        if render_spec is not None:
            source = QRectF(render_spec.source_rect)
            if render_spec.mirrored:
                painter.save()
                painter.translate(body.left() + body.right(), 0.0)
                painter.scale(-1.0, 1.0)
                painter.drawPixmap(body, render_spec.pixmap, source)
                painter.restore()
            else:
                painter.drawPixmap(body, render_spec.pixmap, source)
        else:
            draw_body = QRectF(body)
            if self.home_pet.state in {
                "manual_walk", "auto_walk", "auto_sleep_walk"
            }:
                bob = 3.0 * math.sin(time.monotonic() * 12.0)
                draw_body.translate(0.0, -abs(bob))
            elif self.home_pet.state == "sleeping":
                sleep_height = draw_body.height() * 0.62
                draw_body.setTop(draw_body.bottom() - sleep_height)

            colors = {
                "front_left": QColor("#d88974"),
                "front_right": QColor("#e4a06f"),
                "back_left": QColor("#8aa890"),
                "back_right": QColor("#79a3ad"),
            }
            painter.setBrush(colors.get(self.home_pet.direction, QColor("#d88974")))
            painter.setPen(QPen(QColor("#754b3a"), 2))
            painter.drawRoundedRect(draw_body, 14, 14)
            labels = {
                "front_left": "↙",
                "front_right": "↘",
                "back_left": "↖",
                "back_right": "↗",
            }
            painter.setPen(QColor("#fff8ed"))
            painter.drawText(
                draw_body,
                Qt.AlignCenter,
                "Z  Z" if self.home_pet.state == "sleeping" else labels.get(
                    self.home_pet.direction, "•"
                ),
            )
        if self.home_pet_needs_attention():
            self._draw_attention_dot(painter, body.topRight())
        painter.restore()

    def _furniture_depth_key(self, decoration_id):
        if decoration_id in {"home_wall_art", "home_status_card"}:
            return (0, 0.0)
        if decoration_id == "home_rug":
            return (1, 0.0)
        return (2, float(self.selection_bounds(decoration_id).bottom()))

    def _scene_render_entries(self):
        """Return normal scene entries in deterministic 2.5D paint order."""

        entries = []
        for item_id in self.state.get("owned_home_decorations", []):
            if item_id in self.state.get("home_stored_decorations", []):
                continue
            pixmap = (
                render_home_status_card(self.state)
                if item_id == "home_status_card"
                else self.furniture.get(item_id)
            )
            if pixmap is None or pixmap.isNull():
                continue
            entries.append((self._furniture_depth_key(item_id), "furniture", item_id))
        if self.navigation_feedback() is not None:
            entries.append(((1, 1.0), "navigation", "home_navigation"))
        if self.home_pet_visible():
            entries.append(((2, float(self.home_pet.position[1])), "pet", "home_pet"))
        return sorted(entries, key=lambda entry: entry[0])

    def _furniture_transform_rect(self, decoration_id):
        return self.selection_bounds(decoration_id).toAlignedRect()

    def selection_bounds(self, decoration_id):
        pixmap = self.furniture.get(decoration_id)
        if pixmap is None or pixmap.isNull():
            return QRectF()
        position = self.state.get("home_decoration_positions", {}).get(decoration_id, {})
        transform = progression.home_decoration_transform(self.state, decoration_id)
        logical_size = progression.HOME_DECORATION_DEFINITIONS[decoration_id]["size"]
        bounds = home_decoration_bounds(
            position,
            logical_size,
            transform,
            self._camera_x,
        )
        bounds.translate(self._scene_content_offset(), 0)
        return bounds

    def selection_handles(self, decoration_id):
        return home_decoration_handles(self.selection_bounds(decoration_id))

    def _draw_selection(self, painter, decoration_id):
        bounds = self.selection_bounds(decoration_id)
        handles = self.selection_handles(decoration_id)
        painter.save()
        painter.setBrush(HOME_SELECTION_FILL_COLOR)
        painter.setPen(QPen(QColor(HOME_SELECTION_BORDER_COLOR), 2))
        painter.drawRoundedRect(bounds, 9, 9)
        rotate = handles["rotate"]
        painter.setPen(QPen(QColor(HOME_SELECTION_BORDER_COLOR), 1))
        painter.drawLine(
            int(bounds.center().x()), int(bounds.top()),
            int(rotate.center().x()), int(rotate.center().y()),
        )
        for handle, rect in handles.items():
            painter.setBrush(QColor(HOME_SELECTION_HANDLE_COLOR))
            painter.setPen(QPen(QColor(HOME_SELECTION_BORDER_COLOR), 2))
            painter.drawEllipse(rect)
        painter.restore()

    def _panel_rect(self):
        return QRect(0, 0, HOME_DECORATION_SIDEBAR_WIDTH, self.height())

    def _visible_decoration_ids(self):
        category = self._decoration_category
        return [
            item_id for item_id in self.state.get("owned_home_decorations", [])
            if category == "all" or HOME_DECORATION_CATEGORY_BY_ID.get(item_id) == category
        ]

    def _category_rects(self):
        panel = self._panel_rect()
        width = (panel.width() - 24) // len(HOME_DECORATION_CATEGORIES)
        return {
            category: QRect(
                panel.x() + 12 + index * width,
                panel.y() + HOME_DECORATION_CATEGORY_TOP,
                width - 5,
                26,
            )
            for index, (category, _label) in enumerate(HOME_DECORATION_CATEGORIES)
        }

    def _item_card_rects(self):
        panel = self._panel_rect()
        items = self._visible_decoration_ids()
        card_width = (panel.width() - 36) // 2
        return {
            item_id: QRect(
                panel.x() + 12 + (index % 2) * (card_width + 8),
                panel.y()
                + HOME_DECORATION_CARD_TOP
                + (index // 2) * HOME_DECORATION_CARD_STEP,
                card_width,
                HOME_DECORATION_CARD_HEIGHT,
            )
            for index, item_id in enumerate(items)
        }

    @staticmethod
    def _item_thumbnail_rect(card):
        return QRect(
            card.x() + 8,
            card.y() + 8,
            card.width() - 16,
            HOME_DECORATION_THUMBNAIL_HEIGHT,
        )

    def furniture_preview_rect(self, decoration_id, card):
        """Fit a furniture bitmap inside its card without changing its aspect ratio."""
        thumbnail = self._item_thumbnail_rect(card)
        pixmap = self.furniture.get(decoration_id)
        if pixmap is None or pixmap.isNull():
            return QRect()
        preview = pixmap.scaled(
            thumbnail.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        return QRect(
            thumbnail.x() + (thumbnail.width() - preview.width()) // 2,
            thumbnail.y() + (thumbnail.height() - preview.height()) // 2,
            preview.width(),
            preview.height(),
        )

    @staticmethod
    def _item_action_rect(card):
        return QRect(card.x() + 8, card.bottom() - 32, card.width() - 16, 27)

    def _draw_decoration_panel(self, painter):
        panel = self._panel_rect()
        painter.setPen(QPen(QColor("#e7c4ad"), 1))
        painter.setBrush(QColor(255, 248, 236, 238))
        painter.drawRoundedRect(panel, 18, 18)
        painter.setPen(QColor("#754b3a"))
        painter.drawText(
            QRect(panel.x() + 14, panel.y() + 8, panel.width() - 64, 24),
            Qt.AlignLeft,
            "家具布置",
        )
        self._draw_scene_button(
            painter, self.decoration_panel_close_button_rect(), "×"
        )
        for category, label in HOME_DECORATION_CATEGORIES:
            rect = self._category_rects()[category]
            painter.setBrush(QColor("#cf846a" if category == self._decoration_category else "#f9e7ce"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 7, 7)
            painter.setPen(QColor("#65483b"))
            painter.drawText(rect, Qt.AlignCenter, label)
        for item_id, card in self._item_card_rects().items():
            stored = item_id in self.state.get("home_stored_decorations", [])
            name = progression.HOME_DECORATION_DEFINITIONS[item_id]["name"]
            painter.setPen(QColor("#cf846a" if item_id == self._selected_furniture else "#e7c4ad"))
            painter.setBrush(QColor("#fffaf1"))
            painter.drawRoundedRect(card, 9, 9)
            thumbnail = self._item_thumbnail_rect(card)
            pixmap = (
                render_home_status_card(self.state)
                if item_id == "home_status_card"
                else self.furniture.get(item_id)
            )
            if pixmap is not None and not pixmap.isNull():
                preview = self.furniture_preview_rect(item_id, card)
                painter.drawPixmap(
                    preview.topLeft(),
                    pixmap.scaled(
                        thumbnail.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                    ),
                )
            painter.setPen(QColor("#754b3a"))
            name_rect = QRect(card.x() + 8, card.y() + 88, card.width() - 12, 23)
            painter.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, name)
            action = "放置" if stored else "收纳"
            painter.setBrush(QColor("#f5d6b3"))
            painter.setPen(Qt.NoPen)
            action_rect = self._item_action_rect(card)
            painter.drawRoundedRect(action_rect, 7, 7)
            painter.setPen(QColor("#65483b"))
            painter.drawText(action_rect, Qt.AlignCenter, action)

    def handle_scene_click(self, point):
        """Handle non-furniture clicks without allowing the board above pet."""
        if self.interaction_toggle_rect().contains(point):
            self._interaction_menu_open = not self._interaction_menu_open
            self._menu_open = False
            self.update()
            return True
        if self.menu_toggle_rect().contains(point):
            self._menu_open = not self._menu_open
            self._interaction_menu_open = False
            self.update()
            return True
        if self._interaction_menu_open:
            for action, rect in self.interaction_item_rects().items():
                if rect.contains(point):
                    return self.trigger_home_interaction(action)
            self._interaction_menu_open = False
            self.update()
            return True
        if self._menu_open:
            if self.exit_button_rect().contains(point):
                self.hide_scene()
                return True
            if self.decoration_button_rect().contains(point):
                self.toggle_decoration_mode()
                return True
            if self.shop_button_rect().contains(point):
                opener = getattr(self.pet, "open_shop", None)
                if callable(opener):
                    opener()
                self._menu_open = False
                self.update()
                return True
            self._menu_open = False
            self.update()
            return True
        if self.view_pan_enabled() and self.left_view_button_rect().contains(point):
            self.begin_pan("left")
            return True
        if self.view_pan_enabled() and self.right_view_button_rect().contains(point):
            self.begin_pan("right")
            return True
        if self.is_decorating():
            if self._handle_decoration_panel_click(point):
                return True
            return False
        self.pet.raise_()
        return False

    def _scene_control_at(self, point):
        if self.interaction_toggle_rect().contains(point):
            return True
        if self.menu_toggle_rect().contains(point):
            return True
        if self._interaction_menu_open and any(
            rect.contains(point)
            for rect in self.interaction_item_rects().values()
        ):
            return True
        if self._menu_open and any(
            rect.contains(point)
            for rect in self.menu_item_rects().values()
        ):
            return True
        if self.view_pan_enabled() and (
            self.left_view_button_rect().contains(point)
            or self.right_view_button_rect().contains(point)
        ):
            return True
        return self.is_decorating() and self._panel_rect().contains(point)

    def canvas_to_world(self, point):
        """Convert a window-local canvas point to home-world coordinates."""

        canvas = self.scene_canvas_rect()
        return (
            float(point.x() - canvas.left() + self._camera_x),
            float(point.y()),
        )

    def command_home_pet(self, point, now=None):
        """Send the in-scene pet toward a right-clicked floor point."""

        canvas = self.scene_canvas_rect()
        if (
            not self.isVisible()
            or self.is_decorating()
            or not canvas.contains(point)
            or self._scene_control_at(point)
        ):
            return False
        command_time = time.monotonic() if now is None else float(now)
        interrupted_sleep = self.home_pet.command_move(
            self.canvas_to_world(point),
            command_time,
        )
        self.home_pet.last_player_command_at = command_time
        self._menu_open = False
        self._interaction_menu_open = False
        self._set_manual_destination(self.home_pet.target)
        if interrupted_sleep:
            self.state["sleeping"] = False
            self.state["sleep_mode"] = None
            self.save_state(self.state)
        self.update()
        return True

    def _handle_decoration_panel_click(self, point):
        if self.decoration_panel_close_button_rect().contains(point):
            self.toggle_decoration_mode()
            return True
        for category, rect in self._category_rects().items():
            if rect.contains(point):
                self._decoration_category = category
                self.update()
                return True
        for item_id, card in self._item_card_rects().items():
            if card.contains(point):
                if self._item_action_rect(card).contains(point):
                    if item_id in self.state.get("home_stored_decorations", []):
                        self.place_furniture(item_id)
                    else:
                        self.store_furniture(item_id)
                elif item_id not in self.state.get("home_stored_decorations", []):
                    self.select_furniture(item_id)
                return True
        return self._panel_rect().contains(point)

    def _furniture_rect(self, decoration_id):
        pixmap = self.furniture.get(decoration_id)
        if pixmap is None or pixmap.isNull():
            return QRect()
        position = self.state.get("home_decoration_positions", {}).get(
            decoration_id, {}
        )
        return self._furniture_transform_rect(decoration_id)

    def furniture_at(self, point):
        """Return the top-most owned furniture item at a board-local point."""
        if not self.is_decorating():
            return None
        for decoration_id in reversed(self.state.get("owned_home_decorations", [])):
            if decoration_id in self.state.get("home_stored_decorations", []):
                continue
            if self._furniture_rect(decoration_id).contains(point):
                return decoration_id
        return None

    def move_furniture(self, decoration_id, world_position):
        """Store an authored world position after a furniture drag."""
        if not self.is_decorating():
            return None
        position = progression.set_home_decoration_position(
            self.state,
            decoration_id,
            world_position.x(),
            world_position.y(),
        )
        self.save_state(self.state)
        self.update()
        return position

    def begin_furniture_gesture(self, point):
        """Select furniture or start a direct move, scale, or rotate gesture."""
        if not self.is_decorating():
            return False
        if self._selected_furniture is not None:
            for handle, rect in self.selection_handles(self._selected_furniture).items():
                if rect.contains(point):
                    item_id = self._selected_furniture
                    self._editing_gesture = {
                        "item_id": item_id,
                        "kind": "rotate" if handle == "rotate" else "scale",
                        "handle": handle,
                        "origin": QPoint(point),
                        "position": progression.home_decoration_position(self.state, item_id),
                        "transform": progression.home_decoration_transform(self.state, item_id),
                    }
                    return True
        decoration_id = self.furniture_at(point)
        if decoration_id is None:
            self._selected_furniture = None
            self.update()
            return False
        self.select_furniture(decoration_id)
        self._editing_gesture = {
            "item_id": decoration_id,
            "kind": "move",
            "origin": QPoint(point),
            "position": progression.home_decoration_position(self.state, decoration_id),
            "transform": progression.home_decoration_transform(self.state, decoration_id),
        }
        return True

    def update_furniture_gesture(self, point):
        gesture = self._editing_gesture
        if gesture is None or not self.is_decorating():
            return False
        decoration_id = gesture["item_id"]
        if gesture["kind"] == "move":
            delta = point - gesture["origin"]
            position = gesture["position"]
            self.move_furniture(
                decoration_id,
                QPoint(position["x"] + delta.x(), position["y"] + delta.y()),
            )
            return True
        bounds = self.selection_bounds(decoration_id)
        pixmap = self.furniture[decoration_id]
        transform = gesture["transform"]
        if gesture["kind"] == "scale":
            logical_size = progression.HOME_DECORATION_DEFINITIONS[
                decoration_id
            ]["size"]
            scale = scale_from_handle(
                bounds.center(), point, gesture["handle"],
                logical_size, transform["rotation"], transform["scale"],
            )
            progression.set_home_decoration_transform(
                self.state, decoration_id, scale=scale, rotation=transform["rotation"]
            )
        else:
            rotation = rotation_from_pointer(bounds.center(), point)
            progression.set_home_decoration_transform(
                self.state, decoration_id, scale=transform["scale"], rotation=rotation
            )
        self.save_state(self.state)
        self.update()
        return True

    def end_furniture_gesture(self, point):
        if self._editing_gesture is None:
            return False
        self.update_furniture_gesture(point)
        self._editing_gesture = None
        self.setCursor(Qt.ArrowCursor)
        return True

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            event.accept()
            return
        if event.button() != Qt.LeftButton:
            return
        if self.handle_scene_click(event.pos()):
            event.accept()
            return
        if not self.is_decorating():
            if self.command_home_pet(event.pos()):
                event.accept()
            return
        if not self.begin_furniture_gesture(event.pos()):
            event.accept()
            return
        self.setCursor(Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._editing_gesture is None:
            return
        self.update_furniture_gesture(event.pos())

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._pan_direction is not None:
            self.end_pan()
            event.accept()
            return
        if self._editing_gesture is None:
            return
        self.end_furniture_gesture(event.pos())

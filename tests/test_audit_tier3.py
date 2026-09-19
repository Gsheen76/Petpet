"""2026-09-19 审计遗留中危七项的回归测试。

中⑥ 幽灵 profile / 中④ 每帧读盘 / 中⑤ 多显示器钳位 / 中⑦ 小屋拖窗
弹回 / 中⑩ 图片轮重生成 / 中⑧ 币值双写口径 / 中⑨ 周报语义。
每项一个测试类，先红后绿。
"""

import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtWidgets import QApplication

import buddy_ai as ai
from petpet.app import state as app_state
from petpet.progression import core as progression


class FakePet:
    def __init__(self):
        import pet

        self.settings = dict(pet.DEFAULT_SETTINGS)
        self.state = {"pet_name": "summer"}

    @property
    def pet_name(self):
        return self.state["pet_name"]

    def current_screen_rect(self):
        return QApplication.primaryScreen().availableGeometry()

    def say(self, _text, _duration):
        pass


def fresh_state():
    state = app_state.ensure_state_schema({}, "Sheen", str)
    progression.ensure_progression(state)
    return state


class GhostProfileTests(unittest.TestCase):
    """中⑥：查看未拥有宠物不得写入存档；送礼须有所有权守卫；
    历史幽灵档（纯默认值）加载时清扫。"""

    def test_snapshot_of_unowned_pet_does_not_create_profile(self):
        from petpet.ui.pet_profile import pet_profile_snapshot

        state = fresh_state()

        snap = pet_profile_snapshot(state, "ice_cream")

        self.assertEqual(snap["level"], 1)
        self.assertFalse(snap["owned"])
        self.assertNotIn(
            "ice_cream",
            state.get("pets") or {},
            "查看未拥有宠物不得把它写进存档",
        )

    def test_give_gift_rejects_unowned_pet_even_with_ghost_profile(self):
        state = fresh_state()
        # 旧 bug 留下的幽灵档：ice_cream 不在 owned 但 pets 里有完整档案
        state["pets"]["ice_cream"] = app_state.pet_profile(state, "ice_cream")
        state["gift_inventory"]["sweet_cookie"] = 3

        result = progression.give_gift(state, "ice_cream", "sweet_cookie")

        self.assertFalse(result["ok"])
        self.assertEqual(state["gift_inventory"]["sweet_cookie"], 3)
        self.assertEqual(
            state["pets"]["ice_cream"]["affection_points"], 0
        )

    def test_schema_sweeps_pristine_ghost_profiles(self):
        state = fresh_state()
        # 模拟历史污染：纯默认幽灵档（应扫）+ 改过名的幽灵档（有用户
        # 数据，保留）+ 有好感的真实档案（保留）
        state["pets"]["ice_cream"] = dict(
            app_state.pet_profile(state, "ice_cream")
        )
        state["pets"]["lunch_meat"]["affection_points"] = 30
        ghost_kept = dict(app_state.pet_profile(state, "ice_cream"))
        ghost_kept["pet_name"] = "冰淇淋"
        state["pets"]["ice_cream"] = ghost_kept

        app_state.ensure_state_schema(state, "Sheen", str)

        # 纯默认的在被改名版替换后不存在了——用另一只宠物验证清扫：
        self.assertIn("ice_cream", state["pets"], "改名幽灵档有用户数据须保留")
        self.assertEqual(
            state["pets"]["lunch_meat"]["affection_points"], 30
        )
        # 纯默认幽灵档单独验证
        state2 = fresh_state()
        state2["pets"]["ice_cream"] = dict(
            app_state.pet_profile(state2, "ice_cream")
        )
        app_state.ensure_state_schema(state2, "Sheen", str)
        self.assertNotIn(
            "ice_cream", state2["pets"], "纯默认幽灵档应被清扫"
        )


class CoinWriteDirectionTests(unittest.TestCase):
    """中⑧：门面是会话内活跃真相（加载投影 player→门面、保存捕获
    门面→player）——购买路径不得用滞后的 player 值回滚门面上尚未
    捕获同步的增减。"""

    def test_shared_pet_coins_prefers_facade(self):
        state = fresh_state()
        state["player"]["pet_coins"] = 100
        state["pet_coins"] = 150  # 挖宝所得，捕获间隙

        holder = progression._shared_pet_coins(state)

        self.assertEqual(state["pet_coins"], 150)
        self.assertEqual(holder["pet_coins"], 150)
        self.assertEqual(state["player"]["pet_coins"], 150)

    def test_facade_missing_falls_back_to_player(self):
        state = fresh_state()
        state["player"]["pet_coins"] = 120
        del state["pet_coins"]

        holder = progression._shared_pet_coins(state)

        self.assertEqual(holder["pet_coins"], 120)
        self.assertEqual(state["pet_coins"], 120)


class WeeklyAnchorTests(unittest.TestCase):
    """中⑨：陪伴周报——records 是终身累计计数，须惰性维护周锚点，
    只统计本周增量；跨周自动重置。"""

    def test_deltas_track_increment_only(self):
        records = {"pettings": 10}
        progression.weekly_record_deltas(records)  # 首次建锚

        records["pettings"] = 13
        self.assertEqual(
            progression.weekly_record_deltas(records)["pettings"], 3
        )

    def test_anchor_rebases_on_week_rollover(self):
        records = {"pettings": 10}
        progression.weekly_record_deltas(records)
        records["pettings"] = 15
        records["week_anchor"]["key"] = "2000-W01"  # 伪造跨周

        deltas = progression.weekly_record_deltas(records)

        self.assertEqual(deltas["pettings"], 0, "跨周后增量从零重新计")
        self.assertEqual(
            records["week_anchor"]["snapshot"]["pettings"], 15
        )

    def test_summary_renders_weekly_deltas(self):
        from petpet.progression.ui import weekly_companionship_summary

        records = {"pettings": 50}
        weekly_companionship_summary(records)
        records["pettings"] = 52
        records["active_seconds"] = 3600 * 3

        lines = weekly_companionship_summary(records)

        joined = " ".join(lines)
        self.assertIn("互动 2 次", joined)
        self.assertIn("陪伴 3 小时", joined)


if __name__ == "__main__":
    unittest.main()


class SetupReminderCacheTests(unittest.TestCase):
    """中④：needs_personal_setup_reminder 被 paintEvent 30fps 每帧调用，
    不得每次都读盘解析 config.json（未配 Key 期间尤甚）。"""

    def test_reminder_caches_config_reads_within_ttl(self):
        from petpet.chat import api

        api._personal_setup_cache["at"] = 0.0  # 隔离其他测试的缓存
        calls = []

        def fake_load():
            calls.append(1)
            return {"api_key": "", "personal_setup_seen": False}

        with patch.object(api, "load_config", side_effect=fake_load):
            for _ in range(5):
                api.needs_personal_setup_reminder()

        self.assertEqual(
            len(calls), 1, "TTL 窗口内应只读一次配置"
        )
        self.assertTrue(api.needs_personal_setup_reminder.__name__)

    def test_mark_seen_invalidates_cache_immediately(self):
        from petpet.chat import api

        api._personal_setup_cache["at"] = 0.0  # 隔离前一个测试的缓存
        box = {"seen": False}

        def fake_load():
            return {"api_key": "", "personal_setup_seen": box["seen"]}

        def fake_save(config):
            box["seen"] = bool(config.get("personal_setup_seen"))

        with patch.object(api, "load_config", side_effect=fake_load),                 patch.object(api, "save_config", side_effect=fake_save):
            self.assertTrue(api.needs_personal_setup_reminder())
            api.mark_personal_setup_seen()
            self.assertFalse(
                api.needs_personal_setup_reminder(),
                "标记已看过应立即失效缓存",
            )


class DragClampTests(unittest.TestCase):
    """中⑤：拖拽钳位必须相对「当前所在屏幕」，而不是把虚拟桌面原点
    当绝对坐标——副屏在主屏左/上方时小狗拖不进那块屏。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_pet_can_be_dragged_into_left_secondary_monitor(self):
        from petpet.app.pet_window import PetWindow

        # 副屏在主屏左侧：副屏矩形 (-1920, 0, 1920, 1080)
        monitor = QRect(-1920, 0, 1920, 1080)
        clamped = PetWindow.clamp_drag_position(
            QPoint(-1000, 500), monitor, 190, 160
        )
        self.assertEqual(clamped.x(), -1000, "副屏内部位置不得被钳回主屏")

    def test_pet_stays_partially_visible_on_current_monitor_edges(self):
        from petpet.app.pet_window import PetWindow

        monitor = QRect(0, 0, 1920, 1080)
        far_left = PetWindow.clamp_drag_position(
            QPoint(-5000, 500), monitor, 190, 160
        )
        self.assertEqual(far_left.x(), -int(190 * 0.7))
        far_right = PetWindow.clamp_drag_position(
            QPoint(99999, 500), monitor, 190, 160
        )
        self.assertEqual(far_right.x(), 1920 - int(190 * 0.3))

    def test_above_monitor_clamps_with_bubble_margin(self):
        from petpet.app.pet_window import PetWindow

        monitor = QRect(0, 0, 1920, 1080)
        clamped = PetWindow.clamp_drag_position(
            QPoint(500, -5000), monitor, 190, 160
        )
        self.assertEqual(clamped.y(), -int(160 * 0.7) + 60)


class HomeWindowDragTests(unittest.TestCase):
    """中⑦：小屋空白处拖窗——2026-09-10 全景重构把几何改成每 33ms
    强制回锚点，拖动彻底失效（橡皮筋弹回）。修复=用户偏移量持久。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _scene(self):
        from petpet.home import window as home_window_pkg

        pet = SimpleNamespace(
            state=fresh_state(),
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_window_pkg.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        return scene

    def test_user_window_offset_survives_scene_sync(self):
        scene = self._scene()
        anchored = scene._target_scene_geometry()

        scene._window_offset = QPoint(40, 30)
        scene._apply_scene_geometry()
        geometry = scene.geometry()

        self.assertEqual(
            (geometry.x(), geometry.y()),
            (anchored.x() + 40, anchored.y() + 30),
            "用户拖窗偏移不得被每帧几何强制回锚点清除",
        )

    def test_decoration_mode_ignores_user_offset(self):
        scene = self._scene()
        scene._window_offset = QPoint(500, 400)
        scene.toggle_decoration_mode()

        geometry = scene.geometry()
        target = scene._target_scene_geometry()
        self.assertEqual(
            (geometry.x(), geometry.y()),
            (target.x(), target.y()),
            "装修全景几何不受用户偏移影响",
        )


class RegenerateImageTurnTests(unittest.TestCase):
    """中⑩：图片轮重生成——历史只存缩略图与占位文本，重发会把占位串
    当用户消息发给模型且原图丢失；条目被弹出后缩略图成孤儿文件。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        import tempfile

        self.temp_dir = tempfile.TemporaryDirectory()
        self.patches = [
            patch.object(ai, "CONFIG_PATH",
                         self.temp_dir.name + "/config.json"),
            patch.object(ai, "DATA_DIR", self.temp_dir.name),
            patch.object(ai, "MEMORY_PATH",
                         self.temp_dir.name + "/memory.json"),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for item in self.patches:
            item.stop()
        self.temp_dir.cleanup()

    def _window(self):
        import pet

        with patch.object(pet, "bridge", pet._Bridge()):
            window = pet.ChatWindow(FakePet())
        self.addCleanup(window.close)
        return window

    def test_regenerate_refuses_image_turn(self):
        window = self._window()
        window.mem["history"] = [
            {"role": "user", "content": "我发送了一张图片：dog.png",
             "image": {"thumbnail": "chat_images/t.png",
                       "filename": "dog.png"}},
            {"role": "assistant", "content": "好可爱！"},
        ]
        before = list(window.mem["history"])

        with patch.object(window, "_begin_reply") as begin:
            window._regenerate()

        self.assertEqual(
            window.mem["history"], before, "图片轮不得弹出历史条目"
        )
        begin.assert_not_called()

    def test_regenerate_still_works_for_text_turn(self):
        window = self._window()
        window.mem["history"] = [
            {"role": "user", "content": "讲个笑话"},
            {"role": "assistant", "content": "好呀"},
        ]

        with patch.object(window, "_begin_reply") as begin:
            window._regenerate()

        begin.assert_called_once()
        self.assertEqual(
            window.mem["history"], [], "文字轮照常弹掉尾部问答对"
        )


if __name__ == "__main__":
    unittest.main()

"""2026-09-18 全应用审计修复的回归测试。

覆盖六项确认缺陷：存档原子写盘（A2）、自动睡醒状态机接线（A1）、
档案抽取阻塞 GUI 线程（C1）、legacy 档案重复迁移自污染（C2）、
_ai_thread 异常静默死亡（C3）、fallback 回复 random 未导入（C7）。
"""

import copy
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import buddy_ai as ai
import pet
from petpet.chat import api
from petpet.chat import memory
from petpet.app import state as app_state


class FakePet:
    def __init__(self):
        self.settings = dict(pet.DEFAULT_SETTINGS)
        self.state = {"pet_name": "summer"}

    @property
    def pet_name(self):
        return self.state["pet_name"]

    def current_screen_rect(self):
        return QApplication.primaryScreen().availableGeometry()

    def say(self, _text, _duration):
        pass


class AtomicStateSaveTests(unittest.TestCase):
    """存档原子写（A2）：temp+fsync+replace，主档损坏回退 .bak。"""

    def test_corrupt_main_file_falls_back_to_bak(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "save.json")
            app_state.write_json_atomic(path, {"version": 1})
            app_state.write_json_atomic(path, {"version": 2})
            Path(path).write_text("{corrupt", encoding="utf-8")

            loaded = app_state.load_json_with_backup(path, dict)

            self.assertEqual(loaded, {"version": 1})

    def test_missing_files_return_default(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "none.json")

            self.assertEqual(app_state.load_json_with_backup(path, list), [])

    def test_atomic_write_leaves_no_tmp_and_keeps_bak(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "save.json")
            app_state.write_json_atomic(path, {"version": 1})
            app_state.write_json_atomic(path, {"version": 2})

            self.assertFalse(os.path.exists(path + ".tmp"))
            self.assertTrue(os.path.exists(path + ".bak"))
            with open(path, "r", encoding="utf-8") as stream:
                self.assertEqual(json_load(stream), {"version": 2})
            with open(path + ".bak", "r", encoding="utf-8") as stream:
                self.assertEqual(json_load(stream), {"version": 1})


def json_load(stream):
    import json
    return json.load(stream)


class AutoSleepWiringTests(unittest.TestCase):
    """自动睡醒接线（A1）：on_decay 必须驱动 _update_auto_sleep_state。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, **overrides):
        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        state.update(overrides)
        window = pet.PetWindow(state)
        self.addCleanup(window.close)
        return window

    def test_on_decay_starts_auto_sleep_when_energy_low(self):
        window = self._window(sleeping=False, energy=3)

        with patch.object(
            window, "_begin_auto_sleep", return_value=True
        ) as begin:
            window.on_decay()

        begin.assert_called_once()

    def test_on_decay_wakes_auto_sleep_when_energy_restored(self):
        window = self._window(sleeping=True, sleep_mode="auto", energy=96)

        with patch.object(
            window, "_wake_from_auto_sleep", return_value=True
        ) as wake:
            window.on_decay()

        wake.assert_called_once()


class ProfileRefreshAsyncTests(unittest.TestCase):
    """档案抽取异步化（C1）：append_history 不得在调用线程内做网络抽取。"""

    def test_append_history_does_not_block_on_extraction(self):
        mem = ai._default_memory()
        # 预置 5 条：追加本条后 user_turns=6，恰好命中 %6==0 抽取点。
        for index in range(5):
            mem["history"].append(
                {"role": "user", "content": f"消息{index}"}
            )
        started = threading.Event()

        def slow_refresh(_mem, *_args, **_kwargs):
            started.set()
            time.sleep(0.4)

        with patch.object(api, "get_chat_mode", return_value="personal"), \
                patch.object(api, "load_memory", return_value=mem), \
                patch.object(
                    api, "_refresh_user_profile", side_effect=slow_refresh
                ):
            began = time.perf_counter()
            api.append_history(mem, "user", "第七条", pet_id="lunch_meat")
            elapsed = time.perf_counter() - began
            # 等待必须在补丁作用域内：守护线程晚于 with 退出才跑会拿不到
            # personal 模式而提前返回。
            self.assertTrue(
                started.wait(2.0), "后台线程应执行抽取"
            )

        self.assertLess(elapsed, 0.2, "抽取网络调用必须离开调用线程")


class ProfileMigrationTests(unittest.TestCase):
    """legacy 档案迁移（C2）：分栏已有时不得把渲染文本再次迁入。"""

    def test_rendered_legacy_not_remigrated_when_facts_exist(self):
        # 真实污染形态：user_profile 恰为当前分栏的渲染文本（自同步串）
        rendered = memory.render_profile_facts({"其他": ["主人叫小王"]})
        mem = {
            "user_profile": rendered,
            "profile_facts": {"其他": ["主人叫小王"]},
        }

        memory.ensure_profile_facts(mem)

        self.assertEqual(mem["profile_facts"]["其他"], ["主人叫小王"])

    def test_real_legacy_still_migrates_when_facts_empty(self):
        mem = {"user_profile": "主人叫小王", "profile_facts": {}}

        memory.ensure_profile_facts(mem)

        self.assertEqual(mem["profile_facts"]["其他"], ["主人叫小王"])


class AiThreadCrashTests(unittest.TestCase):
    """_ai_thread 异常兜底（C3）：流内任何异常必须以 error 信号收场。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_stream_exception_emits_error_and_never_raises(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(
                ai, "CONFIG_PATH", os.path.join(folder, "config.json")
            ), patch.object(ai, "DATA_DIR", folder), patch.object(
                ai, "MEMORY_PATH", os.path.join(folder, "memory.json")
            ), patch.object(pet, "bridge", pet._Bridge()) as real_bridge:
                os.environ.pop("ZHIPU_API_KEY", None)
                window = pet.ChatWindow(FakePet())
                self.addCleanup(window.close)

                errors = []
                real_bridge.error.connect(errors.append)

                with patch.object(
                    ai, "chat_stream", side_effect=RuntimeError("boom")
                ):
                    window._ai_thread("你好")

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0])


class FallbackRandomTests(unittest.TestCase):
    """fallback 回复（C7）：命中情绪词时走 random.choice 而非恒第一条。"""

    def test_fallback_reply_uses_random_choice(self):
        with patch(
            "petpet.chat.api.random.choice",
            return_value="Sheen辛苦啦，摸摸头~",
        ):
            reply = ai.fallback_reply("好累呀", pet_name="Sheen")

        self.assertEqual(reply, "Sheen辛苦啦，摸摸头~")


if __name__ == "__main__":
    unittest.main()

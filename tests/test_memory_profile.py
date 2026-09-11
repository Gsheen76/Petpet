"""聊天档案入口（2026-09-11）：六栏档案查看/编辑。

三层：memory.sanitize_edited_facts 清洗网（纯函数）、
MemoryProfileDialog 编辑行为（offscreen）、ChatWindow.show_memory_profile
保存链路（__new__ 薄壳，参考 test_chat_window_boundary 模式）。
"""

import unittest

from unittest.mock import Mock

from petpet.chat.memory import (
    PROFILE_BUCKETS,
    PROFILE_BUCKET_CAPS,
    facts_differ,
    first_fact,
    sanitize_edited_facts,
)


class FactHelpersTests(unittest.TestCase):
    def test_first_fact_reads_current_alias(self):
        self.assertEqual(first_fact({"称呼": ["小明", "老板"]}, "称呼"), "小明")
        self.assertIsNone(first_fact({}, "称呼"))
        self.assertIsNone(first_fact({"称呼": []}, "称呼"))

    def test_facts_differ_compares_cleaned_items_per_bucket(self):
        old = {"称呼": ["小明"], "喜欢": ["咖啡"]}
        same = {"称呼": ["小明"], "喜欢": ["咖啡"], "其他": []}
        self.assertFalse(facts_differ(old, same))
        self.assertTrue(facts_differ(old, {"称呼": ["老板"], "喜欢": ["咖啡"]}))
        # 等价但未清洗的输入不算差异。
        self.assertFalse(facts_differ(old, {"称呼": [" 小明 "], "喜欢": ["咖啡"]}))


class SanitizeEditedFactsTests(unittest.TestCase):
    def test_strips_dedupes_and_caps_per_bucket(self):
        facts = {
            "称呼": [" 小明 ", "小明", "老板", "老师", "多余"],   # cap 3
            "喜欢": ["猫", "", None, "咖啡"],                    # 空与 None 丢弃
            "其他": ["x" * 61, "有效"],                          # 超长单条丢弃
        }
        result = sanitize_edited_facts(facts)
        self.assertEqual(result["称呼"], ["小明", "老板", "老师"])
        self.assertEqual(result["喜欢"], ["猫", "咖啡"])
        self.assertEqual(result["其他"], ["有效"])

    def test_always_returns_all_six_buckets(self):
        result = sanitize_edited_facts({})
        self.assertEqual(tuple(result.keys()), PROFILE_BUCKETS)
        self.assertTrue(all(v == [] for v in result.values()))

    def test_sixty_char_fact_is_kept(self):
        fact = "字" * 60
        self.assertEqual(sanitize_edited_facts({"其他": [fact]})["其他"], [fact])


class MemoryProfileDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, facts=None):
        from petpet.ui.memory_profile import MemoryProfileDialog

        dialog = MemoryProfileDialog(
            facts or {"称呼": ["小明"], "喜欢": ["咖啡", "猫"]},
            pet_name="烟花",
        )
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_populates_rows_from_facts_and_all_buckets_present(self):
        dialog = self._dialog()
        self.assertEqual(
            [e.text() for e, _ in dialog._rows["称呼"]], ["小明"])
        self.assertEqual(
            [e.text() for e, _ in dialog._rows["喜欢"]], ["咖啡", "猫"])
        for bucket in PROFILE_BUCKETS:
            self.assertIn(bucket, dialog._rows)
            self.assertEqual(
                dialog._counts[bucket].text(),
                f"{len(dialog._rows[bucket])}/"
                f"{PROFILE_BUCKET_CAPS[bucket]}",
            )

    def test_add_edit_remove_collect_roundtrip(self):
        dialog = self._dialog()
        dialog._rows["喜欢"][0][0].setText("奶茶")      # 编辑
        dialog._rows["喜欢"][1][1].click()              # 删除「猫」
        dialog._add_row("讨厌")                          # 新增一行
        dialog._rows["讨厌"][-1][0].setText("加班")
        dialog._add_row("其他")                          # 留空行 → 保存时丢弃

        dialog._on_save()
        self.assertEqual(dialog.result_facts["喜欢"], ["奶茶"])
        self.assertEqual(dialog.result_facts["讨厌"], ["加班"])
        self.assertEqual(dialog.result_facts["其他"], [])
        # 删除后计数刷新。
        self.assertEqual(dialog._counts["喜欢"].text(), "1/8")

    def test_add_button_disables_at_cap(self):
        dialog = self._dialog()
        add = dialog._add_buttons["称呼"]
        # 初始 1/3，补到 3 后应禁用。
        dialog._add_row("称呼")
        dialog._add_row("称呼")
        self.assertTrue(len(dialog._rows["称呼"]) == 3)
        self.assertFalse(add.isEnabled())
        # 满栏后 _add_row 直接无效。
        dialog._add_row("称呼")
        self.assertEqual(len(dialog._rows["称呼"]), 3)

    def test_line_edits_cap_input_at_sixty_chars(self):
        dialog = self._dialog()
        edit = dialog._rows["称呼"][0][0]
        self.assertEqual(edit.maxLength(), 60)


class ChatWindowProfileEntryTests(unittest.TestCase):
    def _window(self):
        from types import SimpleNamespace

        from petpet.ui.chat import ChatWindow

        window = ChatWindow.__new__(ChatWindow)
        window.busy = False
        window.pet_id = "lunch_meat"
        # 未初始化的 PyQt 壳访问属性会抛 RuntimeError，给足 _pet_name/say 依赖。
        window.pet = SimpleNamespace(
            pet_name="烟花", state={}, say=Mock(),
        )
        window.mem = {
            "profile_facts": {"称呼": ["小明"]},
            "user_profile": "称呼：小明",
        }
        return window

    def test_show_memory_profile_saves_sanitized_facts(self):
        from unittest.mock import patch

        from petpet.ui.memory_profile import MemoryProfileDialog

        window = self._window()
        new_facts = sanitize_edited_facts(
            {"称呼": ["老板"], "喜欢": ["咖啡"]})

        class FakeDialog:
            def __init__(self, *args, **kwargs):
                self.result_facts = new_facts

            def exec_(self):
                return MemoryProfileDialog.Accepted

        with patch(
            "petpet.ui.memory_profile.MemoryProfileDialog", FakeDialog,
        ), patch.object(
            __import__("petpet.ui.chat", fromlist=["ai"]).ai,
            "save_memory",
        ) as save_memory:
            window.show_memory_profile()

        self.assertEqual(window.mem["profile_facts"], new_facts)
        self.assertIn("称呼：老板", window.mem["user_profile"])
        self.assertIn("喜欢：咖啡", window.mem["user_profile"])
        # A3（2026-09-11）：称呼变化 → 气泡复述新称呼。
        window.pet.say.assert_called_once_with("好的，以后就叫你老板啦！", 3000)
        save_memory.assert_called_once_with(
            window.mem, pet_id="lunch_meat")

    def test_show_memory_profile_noop_while_busy_or_rejected(self):
        from unittest.mock import patch

        window = self._window()
        window.busy = True
        with patch(
            "petpet.ui.memory_profile.MemoryProfileDialog",
        ) as factory:
            window.show_memory_profile()
            factory.assert_not_called()

        window.busy = False
        from petpet.ui.memory_profile import MemoryProfileDialog

        class RejectedDialog:
            def __init__(self, *args, **kwargs):
                self.result_facts = {"称呼": ["不会写入"]}

            def exec_(self):
                return MemoryProfileDialog.Rejected

        with patch(
            "petpet.ui.memory_profile.MemoryProfileDialog", RejectedDialog,
        ), patch.object(
            __import__("petpet.ui.chat", fromlist=["ai"]).ai,
            "save_memory",
        ) as save_memory:
            window.show_memory_profile()
        save_memory.assert_not_called()
        self.assertEqual(window.mem["profile_facts"], {"称呼": ["小明"]})
        window.pet.say.assert_not_called()

    def test_profile_change_without_alias_reply_uses_generic_line(self):
        from unittest.mock import patch

        from petpet.ui.memory_profile import MemoryProfileDialog

        window = self._window()
        new_facts = sanitize_edited_facts(
            {"称呼": ["小明"], "喜欢": ["咖啡"]})  # 称呼未变，喜欢新增

        class FakeDialog:
            def __init__(self, *args, **kwargs):
                self.result_facts = new_facts

            def exec_(self):
                return MemoryProfileDialog.Accepted

        with patch(
            "petpet.ui.memory_profile.MemoryProfileDialog", FakeDialog,
        ), patch.object(
            __import__("petpet.ui.chat", fromlist=["ai"]).ai, "save_memory",
        ):
            window.show_memory_profile()
        window.pet.say.assert_called_once_with("嗯嗯，这些我都记住啦！", 3000)

        # 完全无变化 → 不吭声。
        window.pet.say.reset_mock()

        class SameDialog(FakeDialog):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.result_facts = sanitize_edited_facts(
                    {"称呼": ["小明"], "喜欢": ["咖啡"]})

        with patch(
            "petpet.ui.memory_profile.MemoryProfileDialog", SameDialog,
        ), patch.object(
            __import__("petpet.ui.chat", fromlist=["ai"]).ai, "save_memory",
        ):
            window.show_memory_profile()
        window.pet.say.assert_not_called()


if __name__ == "__main__":
    unittest.main()

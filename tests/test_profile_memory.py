"""长期记忆：结构化主人档案（称呼/作息/喜好/讨厌/重要的事）。

抽取与合并是纯函数（离线可测）；api 层负责调用 LLM 抽取与注入
system prompt。旧 user_profile 字符串字段自动迁移，不丢已有记忆。
"""

import unittest

from petpet.chat import memory as chat_memory


class FactMergeTests(unittest.TestCase):
    def test_merge_new_facts_into_empty_profile(self):
        merged = chat_memory.merge_profile_facts(
            {},
            {
                "称呼": ["小王"],
                "作息": ["经常熬夜到两点"],
                "喜欢": ["猫", "奶茶"],
                "讨厌": ["香菜"],
                "重要的事": ["最近在准备考试"],
            },
        )
        self.assertEqual(merged["称呼"], ["小王"])
        self.assertEqual(merged["喜欢"], ["猫", "奶茶"])
        self.assertEqual(merged["重要的事"], ["最近在准备考试"])

    def test_merge_dedupes_and_caps_each_bucket(self):
        current = {
            "称呼": ["小王"],
            "喜欢": ["猫", "奶茶"],
            "重要的事": ["旧事A", "旧事B", "旧事C", "旧事D", "旧事E",
                          "旧事F", "旧事G", "旧事H"],
        }
        merged = chat_memory.merge_profile_facts(
            current,
            {
                "称呼": ["小王", "老王"],
                "喜欢": ["奶茶", "打游戏"],
                "重要的事": ["新大事"],
            },
        )
        # 去重保序；称呼栏 incoming 顺序在前（抽取提示词要求新称呼在前）。
        self.assertEqual(merged["称呼"], ["小王", "老王"])
        # 喜欢合并去重。
        self.assertEqual(merged["喜欢"], ["猫", "奶茶", "打游戏"])
        # 重要的事有上限（默认 8）：满栏丢最旧，新大事永远保留。
        self.assertEqual(len(merged["重要的事"]), 8)
        self.assertIn("新大事", merged["重要的事"])
        self.assertNotIn("旧事A", merged["重要的事"])

    def test_merge_ignores_unknown_buckets_and_junk(self):
        merged = chat_memory.merge_profile_facts(
            {"喜欢": ["猫"]},
            {"Unknown": ["x"], "喜欢": ["", "  ", "奶茶", None, 123]},
        )
        self.assertNotIn("Unknown", merged)
        self.assertEqual(merged["喜欢"], ["猫", "奶茶"])

    def test_render_profile_for_prompt(self):
        facts = {
            "称呼": ["小王"],
            "作息": ["经常熬夜到两点"],
            "喜欢": ["猫", "奶茶"],
            "讨厌": ["香菜"],
            "重要的事": ["最近在准备考试"],
        }
        text = chat_memory.render_profile_facts(facts)
        # 分类可读、提示词友好。
        self.assertIn("称呼：小王", text)
        self.assertIn("作息：经常熬夜到两点", text)
        self.assertIn("喜欢：猫、奶茶", text)
        self.assertIn("讨厌：香菜", text)
        self.assertIn("重要的事：最近在准备考试", text)

    def test_render_empty_facts_falls_back(self):
        self.assertIn("还不了解", chat_memory.render_profile_facts({}))

    def test_parse_extraction_json_tolerates_wrapping(self):
        raw = '```json\n{"称呼": ["小王"], "喜欢": ["猫"]}\n```'
        parsed = chat_memory.parse_profile_extraction(raw)
        self.assertEqual(parsed["称呼"], ["小王"])

    def test_parse_extraction_garbage_returns_empty(self):
        self.assertEqual(chat_memory.parse_profile_extraction("不是JSON"), {})
        self.assertEqual(chat_memory.parse_profile_extraction(""), {})

    def test_migrate_legacy_user_profile_string(self):
        mem = {
            "user_profile": "主人叫小王，喜欢猫，最近在准备考试。",
            "history": [],
        }
        migrated = chat_memory.ensure_profile_facts(mem)
        # 旧一句话不丢：作为"其他"栏保留。
        self.assertIn(
            "主人叫小王，喜欢猫，最近在准备考试。",
            migrated["profile_facts"]["其他"],
        )
        # 再跑一次不重复追加。
        again = chat_memory.ensure_profile_facts(migrated)
        self.assertEqual(
            again["profile_facts"]["其他"],
            migrated["profile_facts"]["其他"],
        )

class PromptInjectionTests(unittest.TestCase):
    def test_system_prompt_renders_structured_facts(self):
        from petpet.chat import service

        memory = {
            "user_profile": "旧摘要",
            "profile_facts": {
                "称呼": ["小王"],
                "喜欢": ["猫", "奶茶"],
                "重要的事": ["最近在准备考试"],
            },
            "pet_name": "Sheen",
            "history": [],
        }
        messages = service.build_messages(
            "你好", memory,
            pet_name="Sheen",
            normalize_name=lambda s: s,
            knowledge_finder=lambda text, limit=5: [],
        )
        system = messages[0]["content"]
        self.assertIn("称呼：小王", system)
        self.assertIn("喜欢：猫、奶茶", system)
        self.assertIn("重要的事：最近在准备考试", system)
        # 旧字符串摘要按迁移设计保留在「其他」栏（不丢记忆）。
        self.assertIn("其他：旧摘要", system)

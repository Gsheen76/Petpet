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


class ReminderAndSeasonTests(unittest.TestCase):
    """生日/纪念日提醒 + 季节/公历节日搭话（2026-09-12 四项功能轮）。"""

    FACTS = {
        "称呼": ["小明"],
        "重要的事": [
            "小明的生日是6月18日", "结婚纪念日10月2日", "下月要交报告",
        ],
    }

    def test_extract_dated_facts_requires_keyword_and_date(self):
        dated = chat_memory.extract_dated_facts(self.FACTS)
        facts = [d["fact"] for d in dated]
        self.assertIn("小明的生日是6月18日", facts)
        self.assertIn("结婚纪念日10月2日", facts)
        self.assertNotIn("下月要交报告", facts)

    def test_extract_skips_date_without_anniversary_keyword(self):
        # 只有日期没有 生日/纪念日/周年 关键词 → 不当作提醒（保守，防误触发）。
        dated = chat_memory.extract_dated_facts({"重要的事": ["3月5日要交材料"]})
        self.assertEqual(dated, [])

    def test_due_reminder_matches_month_day(self):
        hit = chat_memory.due_reminder(self.FACTS, 6, 18)
        self.assertEqual(hit["fact"], "小明的生日是6月18日")
        self.assertEqual(hit["month"], 6)
        self.assertEqual(hit["day"], 18)
        self.assertIsNone(chat_memory.due_reminder(self.FACTS, 6, 19))

    def test_reminder_line_quotes_fact_and_pet(self):
        line = chat_memory.reminder_line("小明的生日是6月18日", "烟花")
        self.assertIn("小明的生日是6月18日", line)
        self.assertIn("烟花", line)

    def test_nudge_lines_put_festival_line_first_on_match(self):
        lines = chat_memory.nudge_lines({}, "烟花", 100, 15, month=10, day=1)
        self.assertTrue(lines)
        self.assertIn("国庆", lines[0])

    def test_nudge_lines_add_season_flavor(self):
        autumn = chat_memory.nudge_lines({}, "烟花", 100, 15, month=9)
        self.assertTrue(any("秋" in line for line in autumn))
        # 不传月份 → 无季节行（旧调用方式行为不变）。
        plain = chat_memory.nudge_lines({}, "烟花", 100, 15)
        self.assertFalse(any("秋" in line for line in plain))


class ChatExportFormatTests(unittest.TestCase):
    def test_format_chat_export_layout(self):
        import time as time_mod

        t = time_mod.mktime((2026, 9, 11, 15, 0, 0, 0, 254, 0))
        entries = [
            {"role": "user", "content": "你好", "t": t},
            {"role": "assistant", "content": "你好呀", "t": t + 5},
            {"role": "user", "content": "看图", "image": {"name": "a.png"}, "t": t + 9},
        ]
        text = chat_memory.format_chat_export(entries, "烟花")
        self.assertIn("烟花", text.splitlines()[0])
        self.assertIn("[2026-09-11 15:00] 我：你好", text)
        self.assertIn("[2026-09-11 15:00] 烟花：你好呀", text)
        self.assertIn("[2026-09-11 15:00] 我：[图片]", text)

    def test_format_chat_export_empty_history(self):
        text = chat_memory.format_chat_export([], "烟花")
        self.assertIn("烟花", text)
        self.assertIn("还没有对话", text)


class FactsJsonTests(unittest.TestCase):
    def test_round_trip_keeps_buckets_and_cleans(self):
        facts = {"称呼": ["小明"], "喜欢": ["猫", "奶茶"]}
        text = chat_memory.facts_to_json(facts, pet_name="烟花")
        back = chat_memory.facts_from_json(text)
        self.assertEqual(back["称呼"], ["小明"])
        self.assertEqual(back["喜欢"], ["猫", "奶茶"])
        self.assertEqual(tuple(back.keys()), chat_memory.PROFILE_BUCKETS)

    def test_from_json_rejects_bad_payloads(self):
        with self.assertRaises(ValueError):
            chat_memory.facts_from_json("不是JSON")
        with self.assertRaises(ValueError):
            chat_memory.facts_from_json('{"喜欢": "猫"}')

    def test_from_json_drops_unknown_buckets_and_junk_items(self):
        back = chat_memory.facts_from_json(
            '{"Unknown": [1], "喜欢": ["猫", "", null, 42]}')
        self.assertNotIn("Unknown", back)
        self.assertEqual(back["喜欢"], ["猫"])

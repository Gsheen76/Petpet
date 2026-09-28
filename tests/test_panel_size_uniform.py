# -*- coding: utf-8 -*-
"""面板尺寸统一守卫（2026-09-28 用户定稿：打开的页面统一大小 850×960）。

静态扫描 CozyProgressWindow 子类的 super().__init__ 偏好尺寸元组；
聊天/宠物详情以各自常量核对。新增面板用别的尺寸 → CI 红。
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STANDARD = (850, 960)
# 偏好尺寸元组后紧跟 shop_theme 形参（CozyProgressWindow 调用族）
SIZE_RE = re.compile(r"\((\d{3}), (\d{3})\),\s*\n\s*shop_theme")


class PanelSizeUniformTests(unittest.TestCase):
    def test_cozy_panels_use_standard_size(self):
        files = [
            REPO / "petpet" / "progression" / "ui.py",
            REPO / "petpet" / "minigames" / "ui.py",
        ]
        offenders = []
        for path in files:
            text = path.read_text(encoding="utf-8")
            for match in SIZE_RE.finditer(text):
                size = (int(match.group(1)), int(match.group(2)))
                if size != STANDARD:
                    line = text[: match.start()].count(chr(10)) + 1
                    offenders.append(f"{path.name}:{line} {size}")
        self.assertEqual(
            offenders, [],
            "面板偏好尺寸必须统一 850×960：" + ", ".join(offenders),
        )

    def test_chat_and_profile_constants_match(self):
        chat = (REPO / "petpet" / "ui" / "chat.py").read_text(encoding="utf-8")
        self.assertIn("setFixedSize(850, 960)", chat)
        profile = (REPO / "petpet" / "ui" / "pet_profile.py").read_text(
            encoding="utf-8")
        self.assertIn("UNIFIED_W, UNIFIED_H = 850, 960", profile)


if __name__ == "__main__":
    unittest.main()

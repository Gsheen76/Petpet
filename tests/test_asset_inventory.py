"""素材库存守卫：assets/runtime 不允许出现无引用、命名越轨或断链的素材。

规则来源：2026-09-04 素材治理轮（AGENTS.md「资源管理规范」）。
assets/source/ 是开发期归档，不受本测试约束。

已知宽松点（有意为之）：引用判定是「文件名/相对路径出现在扫描文本中」的
子串匹配，同名文件共享一次命中（如两处 close_button.png 只要有一处引用
都算通过）；帧文件与命名规则仍是精确匹配。
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "assets" / "runtime"

# 引用来源：主代码、工具、测试、打包与脚本、runtime 内全部 manifest/json。
TEXT_SCAN_GLOBS = (
    "petpet/**/*.py",
    "pet.py",
    "tools/**/*.py",
    "tests/**/*.py",
    "scripts/**/*.ps1",
    "scripts/**/*.sh",
    "packaging/*.spec",
    "assets/runtime/**/*.json",
)

# 合法文件名：snake_case 素材 / 三位数字动画帧 / 图标尺寸系列。
NAME_PATTERN = re.compile(r"^[a-z0-9_]+\.(png|wav|json)$")
FRAME_PATTERN = re.compile(r"^\d{3}\.png$")
ICON_PATTERN = re.compile(r"^icon-\d{2,4}\.png$")

# 禁止在主代码里出现盘符绝对路径引用 assets（打包后必然失效）。
DRIVE_ASSET_PATTERN = re.compile(r"[A-Za-z]:[/\\][^\n\"']*assets")


def _scanned_texts() -> str:
    chunks = []
    for pattern in TEXT_SCAN_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file():
                chunks.append(
                    path.read_text(encoding="utf-8", errors="ignore")
                )
    return "\n".join(chunks)


def _runtime_files():
    return [path for path in RUNTIME_DIR.rglob("*") if path.is_file()]


def _declared_animation_folders():
    """pets/<id>/desktop/animations 下被 manifest folder 字段声明的目录。"""
    declared = set()
    for manifest in RUNTIME_DIR.glob("pets/*/desktop/animations/manifest.json"):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for spec in data.values():
            folder = spec.get("folder") if isinstance(spec, dict) else None
            if isinstance(folder, str) and folder:
                declared.add((manifest.parent / folder).resolve())
    return declared


class AssetInventoryTests(unittest.TestCase):
    def test_runtime_files_are_referenced(self):
        texts = _scanned_texts()
        declared = _declared_animation_folders()
        orphans = []
        for path in _runtime_files():
            name = path.name
            rel = path.relative_to(RUNTIME_DIR).as_posix()
            if name in texts or rel in texts:
                continue
            # 动态拼接加载（按名查字典/f-string 拼路径）的素材：词干以
            # 引号内独立 token 出现即视为被引用，如 "happy"+".png"。
            stem = path.stem
            if f'"{stem}"' in texts or f"'{stem}'" in texts:
                continue
            if FRAME_PATTERN.match(name) and path.parent.resolve() in declared:
                continue
            orphans.append(rel)
        self.assertEqual(
            [], orphans,
            "assets/runtime 中发现无引用素材（代码/manifest/打包脚本均未命中）；"
            "若确属参考稿请移入 assets/source/，不要留在打包目录",
        )

    def test_runtime_filenames_follow_convention(self):
        offenders = []
        for path in _runtime_files():
            name = path.name
            if not (
                NAME_PATTERN.match(name)
                or FRAME_PATTERN.match(name)
                or ICON_PATTERN.match(name)
            ):
                offenders.append(
                    path.relative_to(RUNTIME_DIR).as_posix()
                )
        self.assertEqual(
            [], offenders,
            "runtime 文件名必须为纯 ASCII snake_case（帧 NNN.png、图标 icon-N.png 例外）；"
            "禁止中文/大写/连字符命名",
        )

    def test_animation_frame_folders_are_declared(self):
        declared = _declared_animation_folders()
        undeclared = []
        for animations_dir in RUNTIME_DIR.glob("pets/*/desktop/animations"):
            for folder in animations_dir.rglob("*"):
                if not folder.is_dir():
                    continue
                has_frames = any(
                    FRAME_PATTERN.match(child.name)
                    for child in folder.iterdir()
                    if child.is_file()
                )
                if has_frames and folder.resolve() not in declared:
                    undeclared.append(folder.relative_to(ROOT).as_posix())
        self.assertEqual(
            [], undeclared,
            "发现未被 manifest folder 字段声明的动画帧目录（幽灵文件夹）",
        )

    def test_no_hardcoded_absolute_asset_paths(self):
        offenders = []
        scanned = list((ROOT / "petpet").rglob("*.py")) + [ROOT / "pet.py"]
        for path in scanned:
            if not path.is_file():
                continue
            if DRIVE_ASSET_PATTERN.search(path.read_text(encoding="utf-8")):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            [], offenders,
            "主代码中禁止用盘符绝对路径引用 assets（打包后失效）；"
            "请走 petpet/app/paths.py 的目录常量拼接",
        )


if __name__ == "__main__":
    unittest.main()

"""Profile-aware JSON persistence for independent pet chat memories."""

from __future__ import annotations

from copy import deepcopy
import json
import os
import re
from typing import Callable

from petpet.app.pets import DEFAULT_PET_ID, load_pet_registry

# 结构化主人档案（2026-09-10 长期记忆轮）：分栏 + 每栏条数上限。
PROFILE_BUCKETS = ("称呼", "作息", "喜欢", "讨厌", "重要的事", "其他")
PROFILE_BUCKET_CAPS = {
    "称呼": 3,
    "作息": 4,
    "喜欢": 8,
    "讨厌": 6,
    "重要的事": 8,
    "其他": 4,
}


def _clean_fact(value: object) -> str | None:
    """单条事实清洗：非空字符串、去首尾、限长。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 60:
        return None
    return text


def merge_profile_facts(current: dict, extracted: dict) -> dict:
    """把新抽取的事实合并进现有档案。

    规则：仅接受已知分栏；条目去重保序；称呼栏新值在前（最新称呼
    优先），其余栏旧值在前（先认识的优先）；每栏截断到上限。
    """
    result = {}
    for bucket in PROFILE_BUCKETS:
        cap = PROFILE_BUCKET_CAPS[bucket]
        existing = [
            fact for fact in (
                _clean_fact(item)
                for item in (current.get(bucket) or [])
            ) if fact
        ]
        incoming = [
            fact for fact in (
                _clean_fact(item)
                for item in ((extracted or {}).get(bucket) or [])
            ) if fact
        ]
        if bucket == "称呼":
            merged = incoming + [
                fact for fact in existing if fact not in incoming
            ]
            result[bucket] = merged[:cap]
        else:
            merged = existing + [
                fact for fact in incoming if fact not in existing
            ]
            # 满栏丢最旧：取尾部 cap 条，新抽取的事实永远保留。
            result[bucket] = merged[-cap:]
    return result


def sanitize_edited_facts(facts: dict) -> dict:
    """手动编辑档案的清洗网：逐条清洗、去重保序、每栏截前 cap 条。

    编辑 UI 本身限制长度/条数，这里兜底 IME 粘贴超长、程序化赋值等
    旁路输入，保证落盘档案与 LLM 抽取路径遵守同一份契约。
    """
    result = {}
    for bucket in PROFILE_BUCKETS:
        seen: list[str] = []
        for item in (facts or {}).get(bucket) or []:
            fact = _clean_fact(item)
            if fact and fact not in seen:
                seen.append(fact)
        result[bucket] = seen[: PROFILE_BUCKET_CAPS[bucket]]
    return result


def render_profile_facts(facts: dict) -> str:
    """档案 → system prompt 注入文本（分栏中文可读行）。"""
    lines = []
    for bucket in PROFILE_BUCKETS:
        items = [
            _clean_fact(item)
            for item in ((facts or {}).get(bucket) or [])
        ]
        items = [item for item in items if item]
        if items:
            lines.append(f"{bucket}：" + "、".join(items))
    if not lines:
        return "（还不了解主人，慢慢聊就会记住啦）"
    return "\n".join(lines)


def parse_profile_extraction(raw: object) -> dict:
    """解析 LLM 抽取输出（容忍 ```json 包裹/前后废话）→ 合法分栏 dict。"""
    if not isinstance(raw, str) or not raw.strip():
        return {}
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    cleaned = {}
    for bucket in PROFILE_BUCKETS:
        raw_items = data.get(bucket)
        if isinstance(raw_items, str):
            raw_items = [raw_items]
        if isinstance(raw_items, (list, tuple)):
            items = [
                fact for fact in (
                    _clean_fact(item) for item in raw_items
                ) if fact
            ]
            if items:
                cleaned[bucket] = items
    return cleaned


def ensure_profile_facts(mem: dict) -> dict:
    """档案初始化/迁移：旧 user_profile 字符串一次性转入「其他」栏。"""
    facts = mem.get("profile_facts")
    if not isinstance(facts, dict):
        facts = {}
    legacy = mem.get("user_profile")
    if isinstance(legacy, str) and legacy.strip():
        legacy_text = legacy.strip()
        existing_other = [
            fact for fact in (
                _clean_fact(item) for item in facts.get("其他") or []
            ) if fact
        ]
        # 默认占位文案不算真实记忆；超长旧总结截断到 60 字。
        if "还不知道" not in legacy_text and legacy_text not in existing_other:
            existing_other.append(legacy_text[:60])
        facts = {**facts, "其他": existing_other[:PROFILE_BUCKET_CAPS["其他"]]}
    mem["profile_facts"] = facts
    return mem


def normalize_memory_pet_id(value: object) -> str:
    """Return a registered pet ID, mapping old profile names to lunch meat."""
    candidate = str(value or "").strip().lower()
    if candidate in {"desktop", "home"}:
        return DEFAULT_PET_ID
    try:
        registered_ids = load_pet_registry()
    except (OSError, ValueError, TypeError):
        registered_ids = {DEFAULT_PET_ID: {}}
    return candidate if candidate in registered_ids else DEFAULT_PET_ID


def _read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def load_memory(
    path: str,
    default_factory: Callable[[], dict],
    seed_path: str | None = None,
) -> dict:
    """Load one profile, seeding a missing file from another profile once."""
    loaded = _read_json(path)
    if loaded is None and not os.path.exists(path) and seed_path:
        seeded = _read_json(seed_path)
        if seeded is not None:
            loaded = deepcopy(seeded)
            save_memory(path, loaded)
    defaults = default_factory()
    if not isinstance(defaults, dict):
        defaults = {}
    return {**deepcopy(defaults), **deepcopy(loaded or {})}


def save_memory(path: str, memory: dict) -> None:
    """Persist a memory document without exposing a partially-written file."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    temporary_path = path + ".tmp"
    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(memory, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except (OSError, TypeError, ValueError):
        try:
            os.remove(temporary_path)
        except OSError:
            pass

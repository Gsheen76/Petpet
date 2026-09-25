# -*- coding: utf-8 -*-
"""签到与每日任务（2026-09-25 自 core.py 拆分——用户指示逻辑独立成模块）。

依赖方向：本模块可被 core 顶层再导出（record_action 挂进度钩子），
因此对 core 的依赖（ensure_progression/add_coins）一律函数内导入，
避免 import 环。
"""
from __future__ import annotations

import datetime
import random

DAILY_QUEST_POOL = (
    ("pettings", "摸摸它 5 次", 5, 20),
    ("feedings", "喂它吃 1 顿饭", 1, 20),
    ("play_sessions", "陪它玩 1 次", 1, 20),
    ("ai_replies", "和它聊 3 句天", 3, 20),
    ("gifts_given", "送它 1 份礼物", 1, 20),
)
DAILY_QUEST_COUNT = 3
DAILY_QUEST_BONUS = 30


def _stamp_datetime(now=None):
    """now 三态归一化（datetime/浮点纪元/None→当下）。"""
    if isinstance(now, datetime.datetime):
        return now
    if isinstance(now, (int, float)):
        return datetime.datetime.fromtimestamp(now)
    return datetime.datetime.now()


def _daily_quest_date(now=None):
    return _stamp_datetime(now).strftime("%Y-%m-%d")


def ensure_daily_quests(state, now=None):
    """惰性生成/跨日重置当日任务（2026-09-23 创新甲）。

    按日期种子确定性抽 3 条（同日全员同题，免存 rng 状态）；同日
    重复调用为无操作，进度与领取状态原样保留。
    """
    from petpet.progression.core import ensure_progression

    ensure_progression(state)
    today = _daily_quest_date(now)
    block = state.get("daily_quests")
    if (
        isinstance(block, dict)
        and block.get("date") == today
        and isinstance(block.get("quests"), list)
        and len(block["quests"]) == DAILY_QUEST_COUNT
    ):
        return
    chosen = random.Random(f"petpet-daily-{today}").sample(
        list(DAILY_QUEST_POOL), DAILY_QUEST_COUNT
    )
    state["daily_quests"] = {
        "date": today,
        "quests": [
            {
                "key": key,
                "label": label,
                "target": target,
                "reward": reward,
                "progress": 0,
                "claimed": False,
            }
            for key, label, target, reward in chosen
        ],
        "bonus_claimed": False,
    }


def daily_quest_hook(state, action, amount=1, now=None):
    """record_action 单漏斗的当日任务进度推进（缺块/过期不推进）。"""
    block = state.get("daily_quests")
    if not isinstance(block, dict) or block.get("date") != _daily_quest_date(now):
        return
    for quest in block.get("quests", []):
        if quest.get("key") == action and not quest.get("claimed"):
            quest["progress"] = min(
                int(quest.get("progress", 0)) + int(amount),
                int(quest.get("target", 1)),
            )


def claim_daily_quest(state, index, now=None):
    """领取一条完成的任务奖励，返回到账币数（不可领返回 0）。"""
    block = state.get("daily_quests")
    if not isinstance(block, dict) or block.get("date") != _daily_quest_date(now):
        return 0
    quests = block.get("quests", [])
    if not isinstance(index, int) or not 0 <= index < len(quests):
        return 0
    quest = quests[index]
    if quest.get("claimed") or int(quest.get("progress", 0)) < int(quest.get("target", 1)):
        return 0
    from petpet.progression.core import add_coins

    reward = int(quest.get("reward", 0))
    add_coins(state, reward)
    quest["claimed"] = True
    return reward


def claim_daily_bonus(state, now=None):
    """三条全部领毕后的一次性全勤奖励。"""
    block = state.get("daily_quests")
    if not isinstance(block, dict) or block.get("date") != _daily_quest_date(now):
        return 0
    quests = block.get("quests", [])
    if not quests or block.get("bonus_claimed"):
        return 0
    if not all(quest.get("claimed") for quest in quests):
        return 0
    from petpet.progression.core import add_coins

    add_coins(state, DAILY_QUEST_BONUS)
    block["bonus_claimed"] = True
    return DAILY_QUEST_BONUS


# 每日签到（2026-09-24 用户点名）：连续签到 + 7 天阶梯奖励循环，
# 第 7 天 60 币大奖后回到第 1 天（streak 不封顶，奖励按 (streak-1)%7 取）。
CHECK_IN_REWARD_CYCLE = (15, 20, 25, 30, 40, 50, 80)  # 2026-09-24 反馈轮整体上调
CHECK_IN_HISTORY_CAP = 400


def ensure_check_in(state):
    """补齐签到块；streak 合法则保留并补 history（约 13 个月容量）。"""
    from petpet.progression.core import ensure_progression

    ensure_progression(state)
    block = state.get("check_in")
    if not isinstance(block, dict) or not isinstance(block.get("streak"), int):
        block = {"last_date": None, "streak": 0}
    if not isinstance(block.get("history"), list):
        block["history"] = []
    # 迁移（2026-09-24 反馈轮）：旧代码只存 last_date——最后签到日回填
    # 进 history，否则升级当天日历上不显示已签的今天
    last = block.get("last_date")
    if isinstance(last, str) and last not in block["history"]:
        block["history"].append(last)
    state["check_in"] = block


def _check_in_today(now):
    return _stamp_datetime(now).strftime("%Y-%m-%d")


def _check_in_yesterday(now):
    return (_stamp_datetime(now) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


def check_in_status(state, now=None):
    """返回 {available, streak, today_reward}（available=今天还没签）。"""
    ensure_check_in(state)
    block = state["check_in"]
    today = _check_in_today(now)
    available = block["last_date"] != today
    streak = int(block.get("streak", 0))
    next_streak = streak + 1 if available else streak
    reward = (
        CHECK_IN_REWARD_CYCLE[(next_streak - 1) % len(CHECK_IN_REWARD_CYCLE)]
        if next_streak >= 1 else 0
    )
    return {"available": available, "streak": streak, "today_reward": reward}


def do_check_in(state, now=None):
    """签一次到：昨天签过则连续 +1，否则重置为 1；重复签到返回 0。"""
    ensure_check_in(state)
    block = state["check_in"]
    today = _check_in_today(now)
    if block["last_date"] == today:
        return 0
    streak = int(block.get("streak", 0))
    if block["last_date"] == _check_in_yesterday(now) and streak >= 1:
        streak += 1
    else:
        streak = 1
    from petpet.progression.core import add_coins

    reward = CHECK_IN_REWARD_CYCLE[(streak - 1) % len(CHECK_IN_REWARD_CYCLE)]
    add_coins(state, reward)
    block["last_date"] = today
    block["streak"] = streak
    history = block.setdefault("history", [])
    if today not in history:
        history.append(today)
    if len(history) > CHECK_IN_HISTORY_CAP:
        del history[:-CHECK_IN_HISTORY_CAP]
    return reward


def signed_dates_for_month(state, year, month):
    """返回某月已签到的日集合（日历显示用）。"""
    ensure_check_in(state)
    prefix = f"{int(year):04d}-{int(month):02d}-"
    days = set()
    for entry in state["check_in"].get("history", []):
        if isinstance(entry, str) and entry.startswith(prefix):
            try:
                days.add(int(entry[-2:]))
            except ValueError:
                continue
    return days


def daily_rewards_claimable(state, now=None):
    """红点判定：签到可签 / 任务完成可领 / 全勤可领，任一为真。"""
    if check_in_status(state, now=now)["available"]:
        return True
    block = state.get("daily_quests")
    if not isinstance(block, dict) or block.get("date") != _daily_quest_date(now):
        return False
    quests = block.get("quests", [])
    if any(
        not q.get("claimed")
        and int(q.get("progress", 0)) >= int(q.get("target", 1))
        for q in quests
    ):
        return True
    return (
        bool(quests)
        and not block.get("bonus_claimed")
        and all(q.get("claimed") for q in quests)
    )


def ms_until_next_midnight(now=None):
    """距下一个本地零点的毫秒数（零点自动刷新定时用；下限 1s 防抖）。"""
    stamp = _stamp_datetime(now)
    nxt = (stamp + datetime.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1000, int((nxt - stamp).total_seconds() * 1000))


ACTIVITY_LOG_DAYS = 28
_WEEKDAY_LABELS = ("一", "二", "三", "四", "五", "六", "日")


def note_daily_activity(state, amount=1, now=None):
    """按天累计互动量（2026-09-25 c 线）：喂周报图表/后续热力图。"""
    if int(amount) <= 0:
        return
    log = state.setdefault("activity_log", {})
    if not isinstance(log, dict):
        log = {}
        state["activity_log"] = log
    key = _stamp_datetime(now).strftime("%Y-%m-%d")
    log[key] = int(log.get(key, 0)) + int(amount)
    if len(log) > ACTIVITY_LOG_DAYS:
        for old in sorted(log)[:-ACTIVITY_LOG_DAYS]:
            del log[old]


def daily_activity_series(state, days=7, now=None):
    """最近 N 天 (星期标签, 互动量) 列表，旧→新；无记录为 0。"""
    log = state.get("activity_log") or {}
    stamp = _stamp_datetime(now)
    series = []
    for offset in range(days - 1, -1, -1):
        day = stamp - datetime.timedelta(days=offset)
        key = day.strftime("%Y-%m-%d")
        label = _WEEKDAY_LABELS[day.weekday()]
        series.append((label, int(log.get(key, 0))))
    return series

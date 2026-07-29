"""Persistent records, achievements, Pet coins, and upgrade balance."""

from __future__ import annotations

import time


RECORD_DEFAULTS = {
    "app_sessions": 0,
    "active_seconds": 0,
    "pettings": 0,
    "feedings": 0,
    "play_sessions": 0,
    "sleep_sessions": 0,
    "manual_sleeps": 0,
    "auto_sleeps": 0,
    "fetch_catches": 0,
    "chats_opened": 0,
    "wake_shakes": 0,
    "interactions_total": 0,
    "xp_earned": 0,
    "coins_earned": 0,
    "coins_spent": 0,
    "level_ups": 0,
    "affection_earned": 0,
    "affection_level_ups": 0,
}

AFFECTION_ACTION_GAINS = {
    "pettings": 2,
    "feedings": 3,
    "play_sessions": 4,
    "fetch_catches": 2,
    "chats_opened": 1,
    "wake_shakes": 1,
    "manual_sleeps": 2,
    "rest_bubble": 2,
}

AFFECTION_ACTION_COOLDOWNS = {
    "pettings": 20,
    "feedings": 5 * 60,
    "play_sessions": 3 * 60,
    "fetch_catches": 3 * 60,
    # Chat is intentionally unlimited: every valid sent message counts.
    "chats_opened": 0,
    "wake_shakes": 2 * 60,
    "manual_sleeps": 10 * 60,
    "rest_bubble": 5 * 60,
}


UPGRADE_DEFINITIONS = {
    "petting": {
        "name": "温柔抚摸",
        "icon": "♡",
        "max_level": 5,
        "prices": [30, 50, 75, 105, 145],
    },
    "feeding": {
        "name": "营养餐",
        "icon": "◇",
        "max_level": 5,
        "prices": [35, 55, 80, 115, 155],
    },
    "playing": {
        "name": "活力玩耍",
        "icon": "○",
        "max_level": 5,
        "prices": [40, 65, 95, 135, 185],
    },
    "sleeping": {
        "name": "香甜睡眠",
        "icon": "☾",
        "max_level": 5,
        "prices": [40, 60, 90, 125, 170],
    },
    "experience": {
        "name": "成长加速",
        "icon": "✦",
        "max_level": 5,
        "prices": [60, 90, 135, 195, 270],
    },
}

UPGRADE_DEFAULTS = {
    upgrade_id: 0 for upgrade_id in UPGRADE_DEFINITIONS
}

DECORATION_CATEGORIES = ("head", "neck", "eyes", "body")

DECORATION_DEFINITIONS = {
    "red_collar": {
        "name": "暖心红项圈",
        "icon": "♡",
        "category": "neck",
        "category_name": "颈饰",
        "price": 0,
        "asset": "red_collar.png",
        "description": "第一件见面礼，戴上暖暖的红色项圈吧。",
        "renderer": {
            "type": "layered_collar",
            # Current animation frames were generated independently and do
            # not share a stable skeleton. Keep accessories on trustworthy
            # static poses; complex actions hide them until a rigged source
            # model can provide real attachment data.
            "visible_animations": ["idle", "happy", "sad"],
            "strap": "#e84f4b",
            "strap_dark": "#9f302f",
            "strap_light": "#ff8a78",
            "hardware": "#f3ba50",
            "hardware_dark": "#a96d24",
        },
        # Static poses use two neck edges so the strap still has real front
        # and rear layers instead of one rectangular sticker.
        "neck_anchors": {
            "default": {
                "left": [0.36, 0.55], "right": [0.64, 0.55],
                "sag": 0.035, "thickness": 0.032,
            },
            "idle": {
                "left": [0.36, 0.55], "right": [0.64, 0.55],
                "sag": 0.035, "thickness": 0.032,
            },
            "happy": {
                "left": [0.36, 0.56], "right": [0.64, 0.56],
                "sag": 0.035, "thickness": 0.032,
            },
            "sad": {
                "left": [0.37, 0.56], "right": [0.63, 0.56],
                "sag": 0.032, "thickness": 0.032,
            },
        },
    },
}


def _safe_int(value, default=0, minimum=0):
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return int(default)


def ensure_progression(state):
    """Normalize new progression fields without disturbing an old save."""
    state["pet_coins"] = _safe_int(state.get("pet_coins", 0))
    state["affection_level"] = _safe_int(
        state.get("affection_level", 1), default=1, minimum=1
    )
    state["affection_points"] = _safe_int(
        state.get("affection_points", 0)
    )
    while (
        state["affection_points"]
        >= affection_to_next(state["affection_level"])
    ):
        state["affection_points"] -= affection_to_next(
            state["affection_level"]
        )
        state["affection_level"] += 1
    try:
        buffer_value = float(state.get("passive_xp_buffer", 0.0))
    except (TypeError, ValueError):
        buffer_value = 0.0
    state["passive_xp_buffer"] = max(0.0, min(buffer_value, 0.999999))

    raw_cooldowns = state.get("affection_last_gains")
    if not isinstance(raw_cooldowns, dict):
        raw_cooldowns = {}
    cooldowns = {}
    for action in AFFECTION_ACTION_COOLDOWNS:
        try:
            last_gain = float(raw_cooldowns.get(action, 0.0))
        except (TypeError, ValueError):
            last_gain = 0.0
        cooldowns[action] = max(0.0, last_gain)
    state["affection_last_gains"] = cooldowns

    raw_records = state.get("records")
    if not isinstance(raw_records, dict):
        raw_records = {}
    records = {}
    for key, default in RECORD_DEFAULTS.items():
        records[key] = _safe_int(raw_records.get(key, default))
    state["records"] = records

    raw_upgrades = state.get("upgrades")
    if not isinstance(raw_upgrades, dict):
        raw_upgrades = {}
    upgrades = {}
    for upgrade_id, definition in UPGRADE_DEFINITIONS.items():
        level = _safe_int(raw_upgrades.get(upgrade_id, 0))
        upgrades[upgrade_id] = min(level, definition["max_level"])
    state["upgrades"] = upgrades

    raw_owned = state.get("owned_decorations")
    if not isinstance(raw_owned, (list, tuple, set)):
        raw_owned = []
    state["owned_decorations"] = list(dict.fromkeys(
        str(item)
        for item in raw_owned
        if str(item) in DECORATION_DEFINITIONS
    ))

    raw_equipped = state.get("equipped_decorations")
    if not isinstance(raw_equipped, dict):
        raw_equipped = {}
    equipped = {}
    for category in DECORATION_CATEGORIES:
        decoration_id = raw_equipped.get(category)
        definition = DECORATION_DEFINITIONS.get(decoration_id)
        if (
            decoration_id in state["owned_decorations"]
            and definition is not None
            and definition["category"] == category
        ):
            equipped[category] = decoration_id
        else:
            equipped[category] = None
    state["equipped_decorations"] = equipped

    raw_claimed = state.get("claimed_achievements")
    if not isinstance(raw_claimed, (list, tuple, set)):
        raw_claimed = []
    state["claimed_achievements"] = list(dict.fromkeys(
        str(item) for item in raw_claimed if item
    ))
    return state


def record_session(state):
    ensure_progression(state)
    state["records"]["app_sessions"] += 1


def record_active_time(state, seconds=60):
    ensure_progression(state)
    state["records"]["active_seconds"] += _safe_int(seconds)


def affection_to_next(level):
    """Affection needed for the next level.

    Early levels arrive quickly, while long-term levels still feel meaningful.
    """
    level = _safe_int(level, default=1, minimum=1)
    return 20 + level * 10


def add_affection(state, amount):
    """Add affection and return the resulting level-up information."""
    ensure_progression(state)
    amount = _safe_int(amount)
    if amount <= 0:
        return {
            "gained": 0,
            "leveled": False,
            "levels_gained": 0,
            "level": state["affection_level"],
        }
    state["affection_points"] += amount
    state["records"]["affection_earned"] += amount
    levels_gained = 0
    while (
        state["affection_points"]
        >= affection_to_next(state["affection_level"])
    ):
        state["affection_points"] -= affection_to_next(
            state["affection_level"]
        )
        state["affection_level"] += 1
        levels_gained += 1
    state["records"]["affection_level_ups"] += levels_gained
    return {
        "gained": amount,
        "leveled": levels_gained > 0,
        "levels_gained": levels_gained,
        "level": state["affection_level"],
    }


def affection_cooldown_remaining(state, action, now=None):
    """Seconds until an action may grant affection again."""
    ensure_progression(state)
    cooldown = int(AFFECTION_ACTION_COOLDOWNS.get(action, 0))
    if cooldown <= 0:
        return 0.0
    now = time.time() if now is None else float(now)
    last_gain = float(state["affection_last_gains"].get(action, 0.0))
    if last_gain <= 0:
        return 0.0
    # If the system clock moved backwards, do not create a very long lockout.
    if last_gain > now + cooldown:
        state["affection_last_gains"][action] = 0.0
        return 0.0
    return max(0.0, cooldown - (now - last_gain))


def grant_interaction_affection(state, action, amount=1, now=None):
    """Grant affection if this action's independent cooldown is ready."""
    ensure_progression(state)
    amount = _safe_int(amount)
    gain_each = int(AFFECTION_ACTION_GAINS.get(action, 0))
    if amount <= 0 or gain_each <= 0:
        result = add_affection(state, 0)
        result.update({"eligible": False, "cooldown_remaining": 0.0})
        return result
    now = time.time() if now is None else float(now)
    remaining = affection_cooldown_remaining(state, action, now)
    if remaining > 0:
        result = add_affection(state, 0)
        result.update({
            "eligible": False,
            "cooldown_remaining": remaining,
        })
        return result
    if AFFECTION_ACTION_COOLDOWNS.get(action, 0) > 0:
        state["affection_last_gains"][action] = now
    result = add_affection(state, gain_each * amount)
    result.update({"eligible": True, "cooldown_remaining": 0.0})
    return result


def record_action(state, action, amount=1, now=None):
    """Record an interaction and grant its matching affection."""
    ensure_progression(state)
    amount = _safe_int(amount)
    if amount <= 0 or action not in state["records"]:
        return add_affection(state, 0)
    state["records"][action] += amount
    if action in {
        "pettings", "feedings", "play_sessions", "sleep_sessions"
    }:
        state["records"]["interactions_total"] += amount
    return grant_interaction_affection(state, action, amount, now)


def record_sleep(state, mode, now=None):
    record_action(state, "sleep_sessions", now=now)
    key = "auto_sleeps" if mode == "auto" else "manual_sleeps"
    return record_action(state, key, now=now)


def add_coins(state, amount, source=None):
    """Add Pet coins and retain a lifetime-earned total for records."""
    ensure_progression(state)
    amount = _safe_int(amount)
    if amount <= 0:
        return 0
    state["pet_coins"] += amount
    state["records"]["coins_earned"] += amount
    return amount


def upgrade_level(state, upgrade_id):
    ensure_progression(state)
    return int(state["upgrades"].get(upgrade_id, 0))


def upgrade_effects(state):
    """Return the currently active interaction values."""
    ensure_progression(state)
    pet_level = upgrade_level(state, "petting")
    feed_level = upgrade_level(state, "feeding")
    play_level = upgrade_level(state, "playing")
    sleep_level = upgrade_level(state, "sleeping")
    xp_level = upgrade_level(state, "experience")
    play_ratio = play_level / UPGRADE_DEFINITIONS["playing"]["max_level"]
    sleep_ratio = (
        sleep_level / UPGRADE_DEFINITIONS["sleeping"]["max_level"]
    )
    return {
        "pet_mood": 8 + 2 * pet_level,
        # Petting/feeding upgrades improve care attributes only. Experience
        # growth is intentionally owned by the separate experience upgrade.
        "pet_xp": 3,
        "feed_hunger": 25 + 3 * feed_level,
        "feed_mood": 6 + feed_level,
        "feed_xp": 8,
        "play_mood": 20 + 3 * play_level,
        "play_energy_cost": int(round(12 * (1.0 - play_ratio))),
        "play_hunger_cost": int(round(5 * (1.0 - play_ratio))),
        "play_xp": 12 + 2 * play_level,
        "sleep_energy_gain_bonus": 1.2 * sleep_level,
        "sleep_hunger_multiplier": max(0.0, 1.0 - sleep_ratio),
        "xp_multiplier": 1.0 + 0.1 * xp_level,
    }


def apply_xp_bonus(state, amount):
    ensure_progression(state)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return 0
    if amount <= 0:
        return 0
    effective = max(
        1, int(round(amount * upgrade_effects(state)["xp_multiplier"]))
    )
    state["records"]["xp_earned"] += effective
    return effective


def record_xp(state, amount):
    """Record already-calculated XP without applying a second multiplier."""
    ensure_progression(state)
    amount = _safe_int(amount)
    if amount <= 0:
        return 0
    state["records"]["xp_earned"] += amount
    return amount


def passive_xp_per_second(state):
    """Current passive XP rate, based only on affection and XP upgrades."""
    ensure_progression(state)
    affection_level = state["affection_level"]
    base_rate = min(0.50, 0.04 + affection_level * 0.01)
    return base_rate * upgrade_effects(state)["xp_multiplier"]


def passive_xp_per_minute(state):
    """User-facing passive XP rate in the more readable per-minute unit."""
    return passive_xp_per_second(state) * 60.0


def upgrade_description(state, upgrade_id, next_level=False):
    """Build short, truthful effect text for the shop."""
    ensure_progression(state)
    current = upgrade_level(state, upgrade_id)
    definition = UPGRADE_DEFINITIONS[upgrade_id]
    level = min(
        definition["max_level"],
        current + (1 if next_level else 0),
    )
    shadow = {"upgrades": dict(state["upgrades"])}
    shadow["upgrades"][upgrade_id] = level
    effects = upgrade_effects(shadow)
    if upgrade_id == "petting":
        return f"抚摸：心情 +{effects['pet_mood']}"
    if upgrade_id == "feeding":
        return (
            f"喂食：饱腹 +{effects['feed_hunger']}，"
            f"心情 +{effects['feed_mood']}"
        )
    if upgrade_id == "playing":
        suffix = "（满级无消耗）" if level >= definition["max_level"] else ""
        return (
            f"玩耍：心情 +{effects['play_mood']}，"
            f"消耗精力 {effects['play_energy_cost']} / 饱腹 "
            f"{effects['play_hunger_cost']}{suffix}"
        )
    if upgrade_id == "sleeping":
        suffix = "（满级不消耗饱腹）" if level >= definition["max_level"] else ""
        return (
            f"睡眠：每次恢复 +{4 + effects['sleep_energy_gain_bonus']:.1f} "
            f"精力，饱腹消耗 {effects['sleep_hunger_multiplier'] * 100:.0f}%"
            f"{suffix}"
        )
    return f"所有经验获取 ×{effects['xp_multiplier']:.1f}"


def purchase_upgrade(state, upgrade_id):
    ensure_progression(state)
    definition = UPGRADE_DEFINITIONS.get(upgrade_id)
    if definition is None:
        return {"ok": False, "message": "没有找到这项强化。"}
    current = upgrade_level(state, upgrade_id)
    if current >= definition["max_level"]:
        return {"ok": False, "message": "这项强化已经满级啦。"}
    price = int(definition["prices"][current])
    if state["pet_coins"] < price:
        missing = price - state["pet_coins"]
        return {
            "ok": False,
            "message": f"还差 {missing} 枚 Pet币，去完成一些成就吧～",
            "price": price,
        }
    state["pet_coins"] -= price
    state["records"]["coins_spent"] += price
    state["upgrades"][upgrade_id] = current + 1
    return {
        "ok": True,
        "price": price,
        "new_level": current + 1,
        "message": (
            f"{definition['name']} 升到 Lv.{current + 1} 啦！"
        ),
    }


def decoration_owned(state, decoration_id):
    ensure_progression(state)
    return decoration_id in state["owned_decorations"]


def equipped_decoration(state, category):
    ensure_progression(state)
    return state["equipped_decorations"].get(category)


def purchase_decoration(state, decoration_id):
    """Buy or claim a decoration without automatically equipping it."""
    ensure_progression(state)
    definition = DECORATION_DEFINITIONS.get(decoration_id)
    if definition is None:
        return {"ok": False, "message": "没有找到这件装扮。"}
    if decoration_owned(state, decoration_id):
        return {"ok": False, "message": "这件装扮已经拥有啦。"}
    price = int(definition.get("price", 0))
    if state["pet_coins"] < price:
        return {
            "ok": False,
            "price": price,
            "message": f"还差 {price - state['pet_coins']} 枚 Pet币。",
        }
    state["pet_coins"] -= price
    state["records"]["coins_spent"] += price
    state["owned_decorations"].append(decoration_id)
    return {
        "ok": True,
        "price": price,
        "message": (
            f"已领取 {definition['name']}！"
            if price == 0
            else f"已购买 {definition['name']}！"
        ),
    }


def equip_decoration(state, decoration_id):
    """Equip one owned item in its category, replacing the previous item."""
    ensure_progression(state)
    definition = DECORATION_DEFINITIONS.get(decoration_id)
    if definition is None:
        return {"ok": False, "message": "没有找到这件装扮。"}
    if not decoration_owned(state, decoration_id):
        return {"ok": False, "message": "需要先获得这件装扮。"}
    category = definition["category"]
    state["equipped_decorations"][category] = decoration_id
    return {
        "ok": True,
        "category": category,
        "message": f"已经戴上 {definition['name']} 啦～",
    }


def unequip_decoration(state, category):
    """Remove the currently equipped item from one category."""
    ensure_progression(state)
    decoration_id = state["equipped_decorations"].get(category)
    if not decoration_id:
        return {"ok": False, "message": "这个位置还没有装备装扮。"}
    state["equipped_decorations"][category] = None
    definition = DECORATION_DEFINITIONS.get(decoration_id, {})
    return {
        "ok": True,
        "decoration_id": decoration_id,
        "message": f"已收好 {definition.get('name', '装扮')}。",
    }


def _achievement(
    achievement_id, category, title, description, reward, progress, target
):
    progress = max(0.0, float(progress))
    target = max(1.0, float(target))
    return {
        "id": achievement_id,
        "category": category,
        "title": title,
        "description": description,
        "reward": int(reward),
        "progress": progress,
        "target": target,
    }


def achievement_catalog(state, now=None):
    """Return balanced achievements, including one reward for every level."""
    ensure_progression(state)
    now = time.time() if now is None else float(now)
    records = state["records"]
    born = float(state.get("born", now) or now)
    days = max(0.0, (now - born) / 86400.0)
    items = []

    for target, reward, title in [
        (1, 20, "相伴第一天"),
        (3, 35, "三日相守"),
        (7, 60, "一周伙伴"),
        (14, 100, "两周相伴"),
        (30, 160, "满月纪念"),
    ]:
        items.append(_achievement(
            f"days_{target}", "陪伴", title,
            f"陪伴小狗达到 {target} 天", reward, days, target,
        ))

    series = [
        (
            "pettings", "抚摸", "pet",
            [(1, 10, "第一次摸摸"), (10, 25, "温柔的手心"),
             (30, 45, "摸摸专家"), (80, 80, "最安心的拥抱")],
        ),
        (
            "feedings", "喂食", "feed",
            [(1, 10, "第一顿饭饭"), (5, 25, "按时开饭"),
             (20, 50, "小小营养师"), (50, 90, "金牌饲养员")],
        ),
        (
            "play_sessions", "玩耍", "play",
            [(1, 12, "第一次玩耍"), (5, 30, "快乐搭档"),
             (15, 60, "活力满满"), (40, 110, "玩耍大师")],
        ),
        (
            "sleep_sessions", "睡眠", "sleep",
            [(1, 10, "第一次好梦"), (5, 25, "香甜小憩"),
             (15, 50, "规律作息"), (40, 90, "梦乡守护者")],
        ),
        (
            "interactions_total", "互动", "interaction",
            [(10, 30, "渐渐熟悉"), (50, 50, "默契伙伴"),
             (150, 100, "形影不离")],
        ),
        (
            "fetch_catches", "玩耍", "catch",
            [(1, 15, "第一次接球"), (10, 40, "接球好手"),
             (30, 90, "飞扑明星")],
        ),
        (
            "chats_opened", "聊天", "chat",
            [(1, 10, "第一次谈心"), (10, 30, "好多悄悄话"),
             (30, 70, "无话不谈")],
        ),
    ]
    for record_key, category, prefix, tiers in series:
        current = records.get(record_key, 0)
        for target, reward, title in tiers:
            items.append(_achievement(
                f"{prefix}_{target}", category, title,
                f"{category}累计达到 {target} 次",
                reward, current, target,
            ))

    current_level = max(1, _safe_int(state.get("level", 1), 1, 1))
    highest_level_card = max(2, current_level + 1)
    for level in range(2, highest_level_card + 1):
        reward = 15 + level * 5
        items.append(_achievement(
            f"level_{level}", "等级", f"成长到 Lv.{level}",
            f"小狗达到 {level} 级", reward, current_level, level,
        ))

    claimed = set(state["claimed_achievements"])
    for item in items:
        item["claimed"] = item["id"] in claimed
        item["completed"] = item["progress"] >= item["target"]
        item["claimable"] = item["completed"] and not item["claimed"]
    return items


def claimable_achievements(state, now=None):
    return [
        item for item in achievement_catalog(state, now)
        if item["claimable"]
    ]


def has_claimable_achievements(state, now=None):
    return bool(claimable_achievements(state, now))


def claim_achievement(state, achievement_id, now=None):
    ensure_progression(state)
    match = next(
        (
            item for item in achievement_catalog(state, now)
            if item["id"] == achievement_id
        ),
        None,
    )
    if match is None:
        return {"ok": False, "message": "没有找到这个成就。"}
    if match["claimed"]:
        return {"ok": False, "message": "这个奖励已经领取过啦。"}
    if not match["completed"]:
        return {"ok": False, "message": "再努力一点就能领取啦。"}
    state["claimed_achievements"].append(match["id"])
    reward = add_coins(state, match["reward"], source="achievement")
    return {
        "ok": True,
        "reward": reward,
        "title": match["title"],
        "message": f"领取成功：Pet币 +{reward}",
    }


def claim_all_achievements(state, now=None):
    total = 0
    claimed = []
    for item in claimable_achievements(state, now):
        result = claim_achievement(state, item["id"], now)
        if result.get("ok"):
            total += result["reward"]
            claimed.append(item["id"])
    return {"count": len(claimed), "reward": total, "ids": claimed}


def format_duration(seconds):
    seconds = max(0, _safe_int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f"{days} 天 {hours} 小时"
    if hours:
        return f"{hours} 小时 {minutes} 分钟"
    return f"{minutes} 分钟"

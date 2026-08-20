"""Persistent records, achievements, Pet coins, and upgrade balance."""

from __future__ import annotations

import time
import random

from petpet.home.geometry import (
    clamp_home_furniture_position,
    normalize_home_decoration_transform,
    normalize_home_scene,
)
from petpet.app.pets import load_pet_registry as _load_pet_registry


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
    "ai_replies": 0,
    "wake_shakes": 0,
    "autonomous_walks": 0,
    "interactions_total": 0,
    "xp_earned": 0,
    "coins_earned": 0,
    "coins_spent": 0,
    "level_ups": 0,
    "affection_earned": 0,
    "affection_level_ups": 0,
    "decorations_collected": 0,
    "outfit_changes": 0,
    "upgrades_purchased": 0,
    "achievements_claimed": 0,
    "dig_treasures_found": 0,
    "coins_dug": 0,
    "minigame_rounds": 0,
    "coins_minigames": 0,
}

# Digging is an occasional bonus, not a replacement for achievements.
# A check runs once per minute; after a discovery there is a 20-minute
# cooldown. The doubled weighted average is about 24 Pet coins.
DIG_COOLDOWN_SECONDS = 20 * 60
DIG_DISCOVERY_CHANCE = 0.10
DIG_REWARD_TIERS = (
    (0.65, 10, 20, "小钱袋"),
    (0.27, 24, 40, "闪亮钱袋"),
    (0.07, 50, 80, "稀有宝藏"),
    (0.01, 120, 200, "大宝藏"),
)

MINIGAME_IDS = ("coin_catch", "lucky_paws")

AFFECTION_ACTION_GAINS = {
    "pettings": 1,
    "feedings": 4,
    "play_sessions": 5,
    "fetch_catches": 2,
    "ai_replies": 1,
    "wake_shakes": 1,
    "manual_sleeps": 3,
}

AFFECTION_ACTION_COOLDOWNS = {
    "pettings": 60,
    "feedings": 8 * 60,
    "play_sessions": 6 * 60,
    "fetch_catches": 5 * 60,
    "ai_replies": 3 * 60,
    "wake_shakes": 5 * 60,
    "manual_sleeps": 15 * 60,
}


UPGRADE_DEFINITIONS = {
    "petting": {
        "name": "温柔抚摸",
        "icon": "♡",
        "summary": "提高每次抚摸恢复的心情值。",
        "max_level": 5,
        "prices": [30, 50, 75, 105, 145],
    },
    "feeding": {
        "name": "营养餐",
        "icon": "◇",
        "summary": "提高每次喂食恢复的饱腹和心情值。",
        "max_level": 5,
        "prices": [35, 55, 80, 115, 155],
    },
    "playing": {
        "name": "活力玩耍",
        "icon": "○",
        "summary": "提高玩耍带来的心情，并降低精力与饱腹消耗。",
        "max_level": 5,
        "prices": [40, 65, 95, 135, 185],
    },
    "sleeping": {
        "name": "香甜睡眠",
        "icon": "☾",
        "summary": "提高睡眠恢复的精力，并降低睡眠期间的饱腹消耗。",
        "max_level": 5,
        "prices": [40, 60, 90, 125, 170],
    },
    "experience": {
        "name": "成长加速",
        "icon": "✦",
        "summary": "提高互动、陪伴等所有途径获得的经验。",
        "max_level": 5,
        "prices": [60, 90, 135, 195, 270],
    },
    "endurance": {
        "name": "持久活力",
        "icon": "◴",
        "summary": "减缓清醒状态下的属性自然消耗。",
        "max_level": 5,
        "prices": [80, 130, 200, 300, 420],
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
        "default_transform": {
            "x": 0.50,
            "y": 0.56,
            "scale": 0.30,
            "rotation": 0.0,
        },
        "z_index": 20,
    },
    "cream_beret": {
        "name": "奶油贝雷帽",
        "icon": "✿",
        "category": "head",
        "category_name": "帽子",
        "price": 340,
        "asset": "cream_beret.png",
        "description": "软乎乎的奶油针织帽，蝴蝶结里藏着一枚小爪印。",
        "default_transform": {
            "x": 0.50,
            "y": 0.11,
            "scale": 0.36,
            "rotation": -2.0,
        },
        "z_index": 10,
    },
    "round_glasses": {
        "name": "暖金圆框眼镜",
        "icon": "◎",
        "category": "eyes",
        "category_name": "眼镜",
        "price": 250,
        "asset": "round_glasses_no_temples.png",
        "description": "轻巧的暖金圆框，让今天的小狗看起来格外聪明。",
        "default_transform": {
            "x": 0.50,
            "y": 0.29,
            "scale": 0.30,
            "rotation": 0.0,
        },
        "z_index": 30,
    },
    "black_sunglasses": {
        "name": "酷黑爪印墨镜",
        "icon": "▰",
        "category": "eyes",
        "category_name": "眼镜",
        "price": 360,
        "asset": "black_sunglasses.png",
        "description": "圆润的烟黑镜片配上金色爪印，小狗也有酷酷的一面。",
        "default_transform": {
            "x": 0.50,
            "y": 0.29,
            "scale": 0.29,
            "rotation": 0.0,
        },
        "z_index": 30,
    },
    "sky_bow_tie": {
        "name": "晴空爪印领结",
        "icon": "❖",
        "category": "neck",
        "category_name": "颈饰",
        "price": 380,
        "asset": "sky_bow_tie.png",
        "description": "柔软的晴空蓝领结，用一枚暖金爪印点亮胸前。",
        "default_transform": {
            "x": 0.50,
            "y": 0.56,
            "scale": 0.23,
            "rotation": 0.0,
        },
        "z_index": 20,
    },
    "little_orange_hat": {
        "name": "噜噜小橘子",
        "icon": "●",
        "category": "head",
        "category_name": "帽子",
        "price": 420,
        "asset": "little_orange_hat.png",
        "description": "像水豚噜噜一样，在头顶稳稳放一颗小橘子。",
        "default_transform": {
            "x": 0.50,
            "y": 0.07,
            "scale": 0.11,
            "rotation": 0.0,
        },
        "z_index": 10,
    },
}

# Complete pet outfits replace the legacy slot-based decorations in the shop.
# Each outfit owns one authored idle animation instead of being composited.
OUTFIT_DEFINITIONS = {
    "dinosaur_suit": {
        "name": "小恐龙套装",
        "icon": "🦖",
        "price": 680,
        "asset_folder": "dinosaur",
        "preview_asset": "preview.png",
        "animation": "idle_dinosaur",
        "description": "绿色小恐龙连体套装，装备后直接替换小狗的待机动画。",
        "pet_id": "lunch_meat",
    },
    "strawberry_suit": {
        "name": "草莓小子套装",
        "icon": "🍓",
        "price": 760,
        "asset_folder": "strawberry",
        "preview_asset": "preview.png",
        "animation": "idle_strawberry",
        "description": "草莓连帽与叶子领结套装，装备后播放专属待机动画。",
        "pet_id": "lunch_meat",
    },
}

DECORATION_TRANSFORM_LIMITS = {
    "x": (-0.15, 1.15),
    "y": (-0.15, 1.15),
    "scale": (0.15, 1.20),
    "rotation": (-30.0, 30.0),
}

HOME_DECORATION_DEFINITIONS = {
    "home_rug": {
        "name": "暖绒地毯",
        "category": "home",
        "price": 120,
        "asset": "rug.png",
        "description": "为小家的地板添上一层柔软暖意。",
        "default_position": {"x": 620, "y": 430},
        "size": (440, 270),
    },
    "home_sofa": {
        "name": "舒适沙发",
        "category": "home",
        "price": 240,
        "asset": "sofa.png",
        "description": "一张适合晒太阳和歇脚的双人沙发。",
        "default_position": {"x": 210, "y": 360},
        "size": (360, 225),
    },
    "home_plant": {
        "name": "绿植盆栽",
        "category": "home",
        "price": 160,
        "asset": "plant.png",
        "description": "让房间多一位安静又有生命力的伙伴。",
        "default_position": {"x": 1500, "y": 305},
        "size": (190, 340),
    },
    "home_wall_art": {
        "name": "墙面装饰画",
        "category": "home",
        "price": 180,
        "asset": "wall-art.png",
        "description": "给墙面挂上一幅温柔的日落风景。",
        "default_position": {"x": 1110, "y": 95},
        "size": (220, 285),
    },
    "home_status_card": {
        "name": "小狗状态卡",
        "category": "home",
        "price": 0,
        "asset": None,
        "description": "挂在墙上，随时看看小狗的成长与状态。",
        "default_position": {"x": 760, "y": 105},
        "size": (420, 270),
    },
}

FIRST_PURCHASE_DISCOUNT = 0.76
FIRST_PURCHASE_CATEGORIES = ("pets",)


def _safe_int(value, default=0, minimum=0):
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value, default, minimum, maximum):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(default)
    return max(float(minimum), min(float(maximum), value))


def _shared_pet_coins(state):
    player = state.get("player")
    if isinstance(player, dict):
        player["pet_coins"] = _safe_int(
            player.get("pet_coins", state.get("pet_coins", 0))
        )
        if "pet_coins" in state:
            state["pet_coins"] = player["pet_coins"]
        return player
    state["pet_coins"] = _safe_int(state.get("pet_coins", 0))
    return state


def _shared_owned_pet_ids(state):
    owned = state.get("owned_pet_ids")
    if not isinstance(owned, (list, tuple, set)):
        player = state.get("player")
        owned = player.get("owned_pet_ids", []) if isinstance(player, dict) else []
    state["owned_pet_ids"] = list(dict.fromkeys(
        item for item in owned if isinstance(item, str)
    ))
    return state["owned_pet_ids"]


def _first_purchase_flags(state):
    raw = state.get("shop_first_purchase_discounts")
    if not isinstance(raw, dict):
        raw = {}
    flags = dict(raw)
    flags.update({
        category: bool(raw.get(category, True))
        for category in FIRST_PURCHASE_CATEGORIES
    })
    state["shop_first_purchase_discounts"] = flags
    return flags


def first_purchase_price(state, category, original_price):
    """Return the current price and discount metadata for one shop category."""
    original = _safe_int(original_price)
    eligible = (
        category in FIRST_PURCHASE_CATEGORIES
        and _first_purchase_flags(state).get(category, False)
    )
    price = (
        round(original * FIRST_PURCHASE_DISCOUNT)
        if eligible and original
        else original
    )
    return {
        "original_price": original,
        "price": price,
        "discount": FIRST_PURCHASE_DISCOUNT if eligible and original else None,
        "eligible": eligible and original > 0,
    }


def _consume_first_purchase_discount(state, category, price):
    if price > 0:
        flags = _first_purchase_flags(state)
        if flags.get(category):
            flags[category] = False


def available_pet_ids():
    """Return purchasable pet IDs in their registry order."""
    return tuple(_load_pet_registry())


def pet_owned(state, pet_id):
    """Return whether a pet ID is in the shared stable ownership list."""
    owned = state.get("owned_pet_ids")
    return isinstance(owned, (list, tuple, set)) and pet_id in owned


def purchase_pet(state, pet_id):
    """Purchase a registry pet without changing the active pet."""
    definition = _load_pet_registry().get(pet_id)
    if definition is None:
        return {
            "ok": False,
            "pet_id": pet_id,
            "message": "没有找到这只宠物。",
        }
    owned_pet_ids = _shared_owned_pet_ids(state)
    if pet_id in owned_pet_ids:
        return {
            "ok": False,
            "pet_id": pet_id,
            "message": "这只宠物已经拥有啦。",
        }

    original_price = _safe_int(definition.get("original_price", definition.get("price", 0)))
    pricing = first_purchase_price(state, "pets", original_price)
    price = pricing["price"]
    coins = _shared_pet_coins(state)
    if coins["pet_coins"] < price:
        return {
            "ok": False,
            "pet_id": pet_id,
            "price": price,
            "message": f"还差 {price - coins['pet_coins']} 枚 Pet币。",
        }

    coins["pet_coins"] -= price
    if coins is not state and "pet_coins" in state:
        state["pet_coins"] = coins["pet_coins"]
    owned_pet_ids.append(pet_id)
    _consume_first_purchase_discount(state, "pets", price)
    player = state.get("player")
    if isinstance(player, dict) and isinstance(player.get("owned_pet_ids"), list):
        player["owned_pet_ids"] = list(state["owned_pet_ids"])
    return {
        "ok": True,
        "pet_id": pet_id,
        "price": price,
        "original_price": pricing["original_price"],
        "discount": pricing["discount"],
        "message": f"已购买 {definition['default_name']}！",
    }


def _normalized_decoration_transform(decoration_id, values=None):
    definition = DECORATION_DEFINITIONS[decoration_id]
    defaults = definition["default_transform"]
    values = values if isinstance(values, dict) else {}
    normalized = {}
    for key, (minimum, maximum) in DECORATION_TRANSFORM_LIMITS.items():
        normalized[key] = _safe_float(
            values.get(key, defaults[key]),
            defaults[key],
            minimum,
            maximum,
        )
    return normalized


def ensure_progression(state):
    """Normalize new progression fields without disturbing an old save."""
    state["pet_coins"] = _safe_int(state.get("pet_coins", 0))
    _first_purchase_flags(state)
    state["pending_dig_reward"] = _safe_int(
        state.get("pending_dig_reward", 0)
    )
    try:
        last_dig = float(state.get("last_dig_discovery_at", 0.0))
    except (TypeError, ValueError):
        last_dig = 0.0
    state["last_dig_discovery_at"] = max(0.0, last_dig)
    raw_best_scores = state.get("minigame_best_scores")
    if not isinstance(raw_best_scores, dict):
        raw_best_scores = {}
    state["minigame_best_scores"] = {
        game_id: _safe_int(raw_best_scores.get(game_id, 0))
        for game_id in MINIGAME_IDS
    }
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
    try:
        affection_buffer = float(
            state.get("passive_affection_buffer", 0.0)
        )
    except (TypeError, ValueError):
        affection_buffer = 0.0
    state["passive_affection_buffer"] = max(
        0.0, min(affection_buffer, 0.999999)
    )

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

    raw_owned_outfits = state.get("owned_outfits")
    if not isinstance(raw_owned_outfits, (list, tuple, set)):
        raw_owned_outfits = []
    state["owned_outfits"] = list(dict.fromkeys(
        str(item)
        for item in raw_owned_outfits
        if str(item) in OUTFIT_DEFINITIONS
    ))
    equipped_outfit = state.get("equipped_outfit")
    state["equipped_outfit"] = (
        equipped_outfit
        if equipped_outfit in state["owned_outfits"]
        else None
    )

    raw_adjustments = state.get("decoration_adjustments")
    if not isinstance(raw_adjustments, dict):
        raw_adjustments = {}
    adjustments = {}
    for decoration_id, values in raw_adjustments.items():
        if decoration_id not in DECORATION_DEFINITIONS:
            continue
        adjustments[decoration_id] = _normalized_decoration_transform(
            decoration_id, values
        )
    state["decoration_adjustments"] = adjustments

    state["home_scene"] = normalize_home_scene(state.get("home_scene"))

    raw_home_owned = state.get("owned_home_decorations")
    if not isinstance(raw_home_owned, (list, tuple, set)):
        raw_home_owned = []
    state["owned_home_decorations"] = list(dict.fromkeys(
        str(item)
        for item in raw_home_owned
        if str(item) in HOME_DECORATION_DEFINITIONS
    ))

    raw_home_positions = state.get("home_decoration_positions")
    if not isinstance(raw_home_positions, dict):
        raw_home_positions = {}
    home_positions = {}
    for decoration_id in state["owned_home_decorations"]:
        definition = HOME_DECORATION_DEFINITIONS[decoration_id]
        default = definition["default_position"]
        saved = raw_home_positions.get(decoration_id)
        if not isinstance(saved, dict):
            saved = default
        home_positions[decoration_id] = clamp_home_furniture_position(
            decoration_id, saved.get("x", default["x"]), saved.get("y", default["y"])
        )
    state["home_decoration_positions"] = home_positions

    raw_stored = state.get("home_stored_decorations")
    if not isinstance(raw_stored, (list, tuple, set)):
        raw_stored = []
    state["home_stored_decorations"] = list(dict.fromkeys(
        str(item)
        for item in raw_stored
        if str(item) in state["owned_home_decorations"]
    ))
    raw_transforms = state.get("home_decoration_transforms")
    if not isinstance(raw_transforms, dict):
        raw_transforms = {}
    state["home_decoration_transforms"] = {
        decoration_id: normalize_home_decoration_transform(
            raw_transforms.get(decoration_id)
        )
        for decoration_id in state["owned_home_decorations"]
    }

    raw_claimed = state.get("claimed_achievements")
    if not isinstance(raw_claimed, (list, tuple, set)):
        raw_claimed = []
    state["claimed_achievements"] = list(dict.fromkeys(
        str(item) for item in raw_claimed if item
    ))
    # Reconstruct reliable lifetime totals for saves made before these
    # counters existed, while preserving any larger recorded value.
    records["decorations_collected"] = max(
        records["decorations_collected"],
        len(state["owned_decorations"]),
    )
    records["upgrades_purchased"] = max(
        records["upgrades_purchased"],
        sum(state["upgrades"].values()),
    )
    records["achievements_claimed"] = max(
        records["achievements_claimed"],
        len(state["claimed_achievements"]),
    )
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
    return min(200, 20 + level * 10)


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
    if source == "digging":
        state["records"]["coins_dug"] += amount
    elif source == "minigame":
        state["records"]["coins_minigames"] += amount
    return amount


def award_minigame_coins(
        state, game_id, requested, score=0, now=None):
    """Settle one completed mini-game round without a daily earning cap."""
    ensure_progression(state)
    if game_id not in MINIGAME_IDS:
        return {"ok": False, "reward": 0, "message": "没有找到这个小游戏。"}
    requested = _safe_int(requested)
    score = _safe_int(score)
    reward = requested
    state["records"]["minigame_rounds"] += 1
    state["minigame_best_scores"][game_id] = max(
        state["minigame_best_scores"].get(game_id, 0), score
    )
    if reward > 0:
        add_coins(state, reward, source="minigame")
    message = f"Pet币 +{reward}"
    return {
        "ok": True,
        "reward": reward,
        "requested": requested,
        "score": score,
        "message": message,
    }


def dig_cooldown_remaining(state, now=None):
    """Seconds until another treasure can be discovered."""
    ensure_progression(state)
    now = time.time() if now is None else float(now)
    last = float(state.get("last_dig_discovery_at", 0.0))
    if last <= 0:
        return 0.0
    if last > now + DIG_COOLDOWN_SECONDS:
        state["last_dig_discovery_at"] = 0.0
        return 0.0
    return max(0.0, DIG_COOLDOWN_SECONDS - (now - last))


def roll_dig_reward(rng=None):
    """Return one balanced digging reward from the weighted tiers."""
    rng = rng or random
    roll = min(0.999999, max(0.0, float(rng.random())))
    cumulative = 0.0
    for probability, minimum, maximum, label in DIG_REWARD_TIERS:
        cumulative += probability
        if roll < cumulative:
            return {
                "amount": int(rng.randint(minimum, maximum)),
                "tier": label,
            }
    probability, minimum, maximum, label = DIG_REWARD_TIERS[-1]
    return {"amount": int(rng.randint(minimum, maximum)), "tier": label}


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
    endurance_level = upgrade_level(state, "endurance")
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
        "awake_decay_multiplier": max(
            0.5, 1.0 - 0.1 * endurance_level
        ),
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


def passive_affection_per_second(state):
    """Return passive affection growth with multiplicative zero-stat penalties."""
    ensure_progression(state)
    zero_count = 0
    for key in ("hunger", "mood", "energy"):
        try:
            value = float(state.get(key, 0))
        except (TypeError, ValueError):
            value = 0.0
        if value <= 0:
            zero_count += 1
    return 0.01 * (0.5 ** zero_count)


def passive_affection_per_minute(state):
    """User-facing passive affection rate in points per minute."""
    return passive_affection_per_second(state) * 60.0


def zero_stat_interaction_actions(state):
    """Return interaction record keys that restore at least one zero stat."""
    ensure_progression(state)
    zero_stats = set()
    for key in ("hunger", "mood", "energy"):
        if key not in state:
            continue
        try:
            value = float(state.get(key, 0))
        except (TypeError, ValueError):
            value = 0.0
        if value <= 0:
            zero_stats.add(key)

    actions = set()
    if "hunger" in zero_stats:
        actions.add("feedings")
    if "mood" in zero_stats:
        actions.update(("pettings", "feedings", "play_sessions"))
    if "energy" in zero_stats:
        actions.add("manual_sleeps")
    return actions


def upgrade_description(
        state, upgrade_id, next_level=False, decay_rates=None):
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
    decay_rates = decay_rates if isinstance(decay_rates, dict) else {}
    awake_hunger_decay = float(decay_rates.get("decay_hunger", 0.14))
    awake_energy_decay = float(decay_rates.get("decay_energy", 0.10))
    awake_mood_decay = float(decay_rates.get("decay_mood", 0.08))
    sleeping_hunger_decay = float(
        decay_rates.get("decay_hunger_sleeping", 0.08)
    )
    if upgrade_id == "petting":
        return f"每次抚摸：心情恢复 {effects['pet_mood']} 点"
    if upgrade_id == "feeding":
        return (
            f"每次喂食：饱腹恢复 {effects['feed_hunger']} 点，"
            f"心情恢复 {effects['feed_mood']} 点"
        )
    if upgrade_id == "playing":
        suffix = "（满级无消耗）" if level >= definition["max_level"] else ""
        return (
            f"每次玩耍：心情恢复 {effects['play_mood']} 点；"
            f"消耗精力 {effects['play_energy_cost']} 点、饱腹 "
            f"{effects['play_hunger_cost']} 点{suffix}"
        )
    if upgrade_id == "sleeping":
        suffix = "（满级不消耗饱腹）" if level >= definition["max_level"] else ""
        hunger_cost = (
            sleeping_hunger_decay
            * effects["sleep_hunger_multiplier"]
        )
        return (
            f"每 2 秒睡眠结算：精力恢复 "
            f"{4 + effects['sleep_energy_gain_bonus']:.1f} 点；"
            f"饱腹消耗 {hunger_cost:.3f} 点"
            f"{suffix}"
        )
    if upgrade_id == "endurance":
        reduction = int(round(
            (1.0 - effects["awake_decay_multiplier"]) * 100
        ))
        return f"清醒属性消耗减缓 {reduction}%"
    return f"所有经验获取倍率：×{effects['xp_multiplier']:.1f}"


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
    state["records"]["upgrades_purchased"] += 1
    return {
        "ok": True,
        "price": price,
        "new_level": current + 1,
        "message": (
            f"{definition['name']} 升到 Lv.{current + 1} 啦！"
        ),
    }


def outfit_owned(state, outfit_id):
    ensure_progression(state)
    return outfit_id in state["owned_outfits"]


def equipped_outfit(state):
    ensure_progression(state)
    return state["equipped_outfit"]


def equipped_outfit_animation(state):
    outfit_id = equipped_outfit(state)
    definition = OUTFIT_DEFINITIONS.get(outfit_id)
    return definition.get("animation") if definition else None


def purchase_outfit(state, outfit_id):
    """Purchase one complete outfit without automatically equipping it."""
    ensure_progression(state)
    definition = OUTFIT_DEFINITIONS.get(outfit_id)
    if definition is None:
        return {"ok": False, "message": "没有找到这套装扮。"}
    if outfit_owned(state, outfit_id):
        return {"ok": False, "message": "这套装扮已经拥有啦。"}
    price = int(definition.get("price", 0))
    coins = _shared_pet_coins(state)
    if coins["pet_coins"] < price:
        return {
            "ok": False,
            "price": price,
            "message": f"还差 {price - coins['pet_coins']} 枚 Pet币。",
        }
    coins["pet_coins"] -= price
    if coins is not state:
        state["pet_coins"] = coins["pet_coins"]
    state["records"]["coins_spent"] += price
    state["owned_outfits"].append(outfit_id)
    state["records"]["decorations_collected"] += 1
    return {
        "ok": True,
        "price": price,
        "message": f"已购买 {definition['name']}！",
    }


def equip_outfit(state, outfit_id):
    """Equip one owned outfit, replacing the previous complete outfit."""
    ensure_progression(state)
    definition = OUTFIT_DEFINITIONS.get(outfit_id)
    if definition is None:
        return {"ok": False, "message": "没有找到这套装扮。"}
    if not outfit_owned(state, outfit_id):
        return {"ok": False, "message": "需要先购买这套装扮。"}
    if state["equipped_outfit"] != outfit_id:
        state["records"]["outfit_changes"] += 1
    state["equipped_outfit"] = outfit_id
    return {
        "ok": True,
        "message": f"已经换上 {definition['name']} 啦～",
    }


def unequip_outfit(state):
    """Remove the active complete outfit and restore the default idle pet."""
    ensure_progression(state)
    outfit_id = state.get("equipped_outfit")
    if not outfit_id:
        return {"ok": False, "message": "现在还没有装备套装。"}
    state["equipped_outfit"] = None
    state["records"]["outfit_changes"] += 1
    definition = OUTFIT_DEFINITIONS.get(outfit_id, {})
    return {
        "ok": True,
        "message": f"已收好 {definition.get('name', '套装')}。",
    }


def decoration_owned(state, decoration_id):
    ensure_progression(state)
    return decoration_id in state["owned_decorations"]


def equipped_decoration(state, category):
    ensure_progression(state)
    return state["equipped_decorations"].get(category)


def decoration_transform(state, decoration_id, *, normalize_state=True):
    """Return a safe idle-pose transform, including the player's adjustment."""
    if normalize_state:
        ensure_progression(state)
    if decoration_id not in DECORATION_DEFINITIONS:
        raise KeyError(decoration_id)
    saved = state.get("decoration_adjustments", {}).get(decoration_id)
    return _normalized_decoration_transform(decoration_id, saved)


def set_decoration_transform(state, decoration_id, **values):
    """Persist selected transform fields and return the normalized result."""
    ensure_progression(state)
    if decoration_id not in DECORATION_DEFINITIONS:
        raise KeyError(decoration_id)
    current = decoration_transform(state, decoration_id)
    current.update(values)
    normalized = _normalized_decoration_transform(
        decoration_id, current
    )
    state["decoration_adjustments"][decoration_id] = normalized
    return dict(normalized)


def reset_decoration_transform(state, decoration_id):
    """Discard player changes and return the authored default transform."""
    ensure_progression(state)
    if decoration_id not in DECORATION_DEFINITIONS:
        raise KeyError(decoration_id)
    state["decoration_adjustments"].pop(decoration_id, None)
    return decoration_transform(state, decoration_id)


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
    state["records"]["decorations_collected"] += 1
    return {
        "ok": True,
        "price": price,
        "message": (
            f"已领取 {definition['name']}！"
            if price == 0
            else f"已购买 {definition['name']}！"
        ),
    }


def home_decoration_position(state, decoration_id):
    """Return the persisted or authored default position for owned furniture."""
    ensure_progression(state)
    definition = HOME_DECORATION_DEFINITIONS.get(decoration_id)
    if definition is None:
        raise KeyError(decoration_id)
    return dict(state["home_decoration_positions"].get(
        decoration_id, definition["default_position"]
    ))


def set_home_decoration_position(state, decoration_id, x, y):
    """Persist a clamped top-left position for owned furniture."""
    ensure_progression(state)
    if decoration_id not in HOME_DECORATION_DEFINITIONS:
        raise KeyError(decoration_id)
    if decoration_id not in state["owned_home_decorations"]:
        raise ValueError("home decoration is not owned")
    normalized = clamp_home_furniture_position(decoration_id, x, y)
    state["home_decoration_positions"][decoration_id] = normalized
    return dict(normalized)


def home_decoration_transform(state, decoration_id):
    ensure_progression(state)
    if decoration_id not in HOME_DECORATION_DEFINITIONS:
        raise KeyError(decoration_id)
    return dict(state["home_decoration_transforms"].get(
        decoration_id, {"scale": 1.0, "rotation": 0.0}
    ))


def set_home_decoration_transform(state, decoration_id, scale=None, rotation=None):
    ensure_progression(state)
    if decoration_id not in HOME_DECORATION_DEFINITIONS:
        raise KeyError(decoration_id)
    current = home_decoration_transform(state, decoration_id)
    if scale is not None:
        current["scale"] = scale
    if rotation is not None:
        current["rotation"] = rotation
    normalized = normalize_home_decoration_transform(current)
    state["home_decoration_transforms"][decoration_id] = normalized
    return dict(normalized)


def store_home_decoration(state, decoration_id):
    ensure_progression(state)
    if decoration_id not in state["owned_home_decorations"]:
        return False
    if decoration_id not in state["home_stored_decorations"]:
        state["home_stored_decorations"].append(decoration_id)
    return True


def place_home_decoration(state, decoration_id):
    ensure_progression(state)
    if decoration_id not in state["owned_home_decorations"]:
        return False
    state["home_stored_decorations"] = [
        item for item in state["home_stored_decorations"]
        if item != decoration_id
    ]
    return True


def purchase_home_decoration(state, decoration_id):
    """Buy one home furniture item using the shared Pet coin balance."""
    ensure_progression(state)
    definition = HOME_DECORATION_DEFINITIONS.get(decoration_id)
    if definition is None:
        return {"ok": False, "message": "Home decoration not found."}
    if decoration_id in state["owned_home_decorations"]:
        return {"ok": False, "message": "Home decoration already owned."}
    price = int(definition.get("price", 0))
    coins = _shared_pet_coins(state)
    if coins["pet_coins"] < price:
        return {
            "ok": False,
            "price": price,
            "message": f"Need {price - coins['pet_coins']} more Pet coins.",
        }
    coins["pet_coins"] -= price
    if coins is not state:
        state["pet_coins"] = coins["pet_coins"]
    state["records"]["coins_spent"] += price
    state["owned_home_decorations"].append(decoration_id)
    state["home_decoration_positions"][decoration_id] = clamp_home_furniture_position(
        decoration_id,
        definition["default_position"]["x"],
        definition["default_position"]["y"],
    )
    state["home_decoration_transforms"][decoration_id] = {
        "scale": 1.0,
        "rotation": 0.0,
    }
    state["records"]["decorations_collected"] += 1
    return {
        "ok": True,
        "price": price,
        "message": (
            f"已领取 {definition['name']}。"
            if price == 0
            else f"已购买 {definition['name']}。"
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
    if state["equipped_decorations"].get(category) != decoration_id:
        state["records"]["outfit_changes"] += 1
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
    state["records"]["outfit_changes"] += 1
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
        (
            "wake_shakes", "陪伴", "wake",
            [(1, 10, "轻轻唤醒"), (5, 25, "叫醒小能手"),
             (15, 55, "每天准时起床")],
        ),
        (
            "ai_replies", "聊天", "reply",
            [(5, 15, "有问有答"), (20, 40, "聊个不停"),
             (50, 85, "懂你的伙伴")],
        ),
        (
            "autonomous_walks", "日常", "stroll",
            [(5, 15, "散步时间"), (20, 40, "桌面巡游"),
             (60, 90, "活力小跑家")],
        ),
        (
            "minigame_rounds", "小游戏", "minigame",
            [(1, 10, "第一次小游戏"), (10, 30, "游戏搭档"),
             (50, 80, "小游戏达人")],
        ),
        (
            "coins_earned", "Pet币", "coins",
            [(100, 20, "第一桶 Pet币"), (500, 50, "温馨小金库"),
             (1500, 110, "攒钱小达人")],
        ),
        (
            "decorations_collected", "装扮", "collect",
            [(1, 15, "第一件装扮"), (3, 45, "小小收藏家")],
        ),
        (
            "outfit_changes", "装扮", "outfit",
            [(1, 10, "今日穿搭"), (10, 35, "百变小狗")],
        ),
        (
            "upgrades_purchased", "强化", "upgrade",
            [(1, 15, "第一次强化"), (5, 40, "稳步成长"),
             (15, 90, "全面提升")],
        ),
        (
            "achievements_claimed", "成就", "claim",
            [(1, 10, "领取第一份奖励"), (10, 35, "成就收集者"),
             (25, 80, "满满荣誉")],
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
    state["records"]["achievements_claimed"] += 1
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
    # Claiming rewards can itself unlock coin/claim-count achievements.
    # Keep scanning until the same button press has collected that new wave.
    while True:
        pending = claimable_achievements(state, now)
        if not pending:
            break
        claimed_this_pass = 0
        for item in pending:
            result = claim_achievement(state, item["id"], now)
            if result.get("ok"):
                total += result["reward"]
                claimed.append(item["id"])
                claimed_this_pass += 1
        if claimed_this_pass == 0:
            break
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

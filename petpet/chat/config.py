"""Validated chat configuration and local free-chat quota persistence."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
FREE_MODEL = "petpet-free"
DEFAULT_MODEL = FREE_MODEL
VISION_MODEL = "glm-4.6v-flash"
SUPPORTED_MODELS = {
    DEFAULT_MODEL: "免费聊天 · OpenRouter Free",
    VISION_MODEL: "GLM-4.6V-Flash",
}
PERSONAL_MODELS = {VISION_MODEL: SUPPORTED_MODELS[VISION_MODEL]}
ALIYUN_LOCAL_DAILY_LIMIT = 20
CHAT_MODES = {"default", "personal"}
LEGACY_PERSONAL_MODELS = {"glm-4-flash", "glm-4.7-flash"}


def normalize_config(raw: Any, *, env_api_key: str = "") -> dict[str, Any]:
    """Return a validated copy while retaining unrelated forward-compatible keys."""
    clean = dict(raw) if isinstance(raw, Mapping) else {}
    api_key = clean.get("api_key", "")
    api_key = api_key.strip() if isinstance(api_key, str) else ""
    mode = clean.get("chat_mode")
    if mode not in CHAT_MODES:
        mode = "personal" if api_key or str(env_api_key or "").strip() else "default"
    model = clean.get("model", VISION_MODEL)
    if model in LEGACY_PERSONAL_MODELS or model not in PERSONAL_MODELS:
        model = VISION_MODEL
    clean.update(api_key=api_key, chat_mode=mode, model=model)
    return clean


def load_config(path: str, *, env_api_key: str = "") -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            raw = json.load(file)
    except (OSError, ValueError, TypeError):
        raw = {}
    return normalize_config(raw, env_api_key=env_api_key)


def save_config(path: str, value: Any) -> None:
    """Atomically persist normalized user configuration."""
    clean = normalize_config(value)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(clean, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        raise


def load_public_config(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            value = json.load(file)
    except (OSError, ValueError, TypeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def default_chat_primary_url(local: Mapping[str, Any], public: Mapping[str, Any]) -> str:
    return str(local.get("default_chat_primary_url", "")).strip() or str(
        public.get("default_chat_primary_url", "")
    ).strip()


def default_chat_fallback_url(local: Mapping[str, Any], public: Mapping[str, Any]) -> str:
    return str(
        local.get("default_chat_fallback_url", "")
        or local.get("default_chat_proxy_url", "")
    ).strip() or str(
        public.get("default_chat_fallback_url", "")
        or public.get("default_chat_proxy_url", "")
    ).strip()


def quota_today(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone(timedelta(hours=8)))
    return current.date().isoformat()


def valid_uuid4(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return parsed.version == 4 and str(parsed) == value.lower()


def fresh_quota_state(today: str) -> dict[str, Any]:
    return {"aliyun": {"date": today, "count": 0, "request_ids": []}}


def load_quota_state(
    path: str, today: str | None = None, *, limit: int = ALIYUN_LOCAL_DAILY_LIMIT
) -> dict[str, Any]:
    today = today or quota_today()
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            state = json.load(file)
        aliyun = state["aliyun"]
        count = aliyun["count"]
        request_ids = aliyun["request_ids"]
        if (
            aliyun["date"] != today
            or not isinstance(count, int)
            or isinstance(count, bool)
            or not 0 <= count <= limit
            or not isinstance(request_ids, list)
            or count != len(request_ids)
            or not all(valid_uuid4(item) for item in request_ids)
        ):
            raise ValueError("invalid local quota state")
        return state
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return fresh_quota_state(today)


def save_quota_state(path: str, state: Mapping[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    descriptor, temp_path = tempfile.mkstemp(
        prefix="chat_quota_state-", suffix=".tmp", dir=directory or None
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def quota_available(
    path: str, today: str | None = None, *, limit: int = ALIYUN_LOCAL_DAILY_LIMIT
) -> bool:
    return load_quota_state(path, today, limit=limit)["aliyun"]["count"] < limit


def record_quota_success(
    path: str,
    request_id: str,
    today: str | None = None,
    *,
    limit: int = ALIYUN_LOCAL_DAILY_LIMIT,
) -> bool:
    today = today or quota_today()
    if not valid_uuid4(request_id):
        return False
    state = load_quota_state(path, today, limit=limit)
    aliyun = state["aliyun"]
    if request_id in aliyun["request_ids"] or aliyun["count"] >= limit:
        return False
    aliyun["request_ids"].append(request_id)
    aliyun["count"] += 1
    save_quota_state(path, state)
    return True


"""Sheen AI engine — companion dog persona powered by Zhipu GLM models.

Features:
  - Companion-dog persona (warm, listens, remembers you)
  - Multi-turn memory persisted to local JSON
  - Streaming output (token-by-token)
  - Time-aware proactive mood (greets differently morning/night)
  - Rule-based fallback when API fails / no key / offline
  - No AI SDK dependency: HTTP uses urllib from the standard library

Config: set env ZHIPU_API_KEY, or configure the API key and model in Petpet:
        {"api_key": "your.key.here", "model": "glm-4.7-flash"}
"""
import os, json, re, time, urllib.request, urllib.error
import hmac, hashlib, base64
import shutil
import uuid
import requests
from petpet.app.paths import DATA_DIR, RESOURCE_DIR
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QImageReader
from petpet.chat import knowledge as game_knowledge
from petpet.chat import memory as chat_memory
from petpet.chat import config as chat_config
from petpet.chat import service as chat_service
from petpet.chat import transport as chat_transport

CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
DEFAULT_CONFIG_PATH = os.path.join(RESOURCE_DIR, "config.json.example")
MEMORY_PATH = os.path.join(DATA_DIR, "memory.json")
HOME_MEMORY_PATH = os.path.join(DATA_DIR, "memory-home.json")
CHAT_DIAGNOSTIC_LOG_PATH = os.path.join(DATA_DIR, "chat_diagnostic.log")
CHAT_QUOTA_STATE_PATH = os.path.join(DATA_DIR, "chat_quota_state.json")

API_URL = chat_config.API_URL
FREE_MODEL = chat_config.FREE_MODEL
DEFAULT_MODEL = chat_config.DEFAULT_MODEL
VISION_MODEL = chat_config.VISION_MODEL
SUPPORTED_MODELS = chat_config.SUPPORTED_MODELS
PERSONAL_MODELS = chat_config.PERSONAL_MODELS
DEFAULT_CHAT_ERRORS = {
    "default_consent_required",
    "default_provider_unavailable",
    "default_quota_exhausted",
    "personal_key_required_for_image",
    "personal_api_key_required",
}
# Kept for compatibility with older imports. Requests use get_model().
MODEL = DEFAULT_MODEL
DEFAULT_PET_NAME = "Sheen"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_HISTORY_THUMBNAIL_EDGE = 320
PLAYER_AVATAR_SIZE = 256
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_PROXY_MAX_SYSTEM_CHARS = chat_transport.DEFAULT_PROXY_MAX_SYSTEM_CHARS
DEFAULT_PROXY_MAX_TURN_CHARS = chat_transport.DEFAULT_PROXY_MAX_TURN_CHARS
DEFAULT_PROXY_MAX_BODY_BYTES = chat_transport.DEFAULT_PROXY_MAX_BODY_BYTES
DEFAULT_PROXY_MAX_MESSAGES = chat_transport.DEFAULT_PROXY_MAX_MESSAGES
DEFAULT_PROXY_HISTORY_MESSAGES = 10
ALIYUN_LOCAL_DAILY_LIMIT = chat_config.ALIYUN_LOCAL_DAILY_LIMIT
CHAT_DIAGNOSTIC_FIELDS = {
    "status", "exception_type", "stage", "response_content_chars",
    "response_reasoning_chars", "has_done", "model", "provider",
    "first_content_ms", "total_ms", "route",
}


def get_player_avatar_path():
    """Return the user-local player avatar path."""
    return os.path.join(DATA_DIR, "player_avatar.png")


def prepare_player_avatar(source_path):
    """Center-crop an image to a square and atomically save a local PNG."""
    reader = QImageReader(str(source_path or ""))
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise ValueError("无法读取这张图片，请选择 PNG、JPG 或 WEBP。")
    edge = min(image.width(), image.height())
    crop = image.copy(QRect(
        (image.width() - edge) // 2,
        (image.height() - edge) // 2,
        edge,
        edge,
    )).scaled(
        PLAYER_AVATAR_SIZE,
        PLAYER_AVATAR_SIZE,
        Qt.IgnoreAspectRatio,
        Qt.SmoothTransformation,
    )
    target = get_player_avatar_path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temporary = target + ".tmp.png"
    try:
        if not crop.save(temporary, "PNG"):
            raise ValueError("头像保存失败，请换一张图片再试。")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass
    return target


def clear_player_avatar():
    """Restore the generated default avatar by removing the local override."""
    try:
        os.remove(get_player_avatar_path())
    except FileNotFoundError:
        pass


def _log_chat_diagnostic(event, **details):
    """Append metadata-only chat diagnostics without prompts, replies, or keys."""
    entry = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": str(event),
    }
    for key in CHAT_DIAGNOSTIC_FIELDS:
        if key in details and details[key] is not None:
            entry[key] = details[key]
    try:
        os.makedirs(os.path.dirname(CHAT_DIAGNOSTIC_LOG_PATH), exist_ok=True)
        with open(CHAT_DIAGNOSTIC_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def normalize_pet_name(value):
    """Return a safe display/persona name, falling back to Sheen."""
    text = " ".join(str(value or "").split())
    allowed = "".join(
        char for char in text
        if char.isalnum() or char in (" ", "-", "_", "·")
    )
    return allowed[:6].strip() or DEFAULT_PET_NAME


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign_jwt(api_key: str) -> str:
    """Generate Zhipu-style JWT from api_key in '{id}.{secret}' format."""
    if "." not in api_key:
        return api_key  # let server reject it; clearer error
    key_id, secret = api_key.split(".", 1)
    header = {"alg": "HS256", "sign_type": "SIGN"}
    now_s = int(time.time())
    payload = {"api_key": key_id, "exp": now_s + 3600, "timestamp": now_s * 1000}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64url(hmac.new(secret.encode("utf-8"), f"{h}.{p}".encode("utf-8"),
                          hashlib.sha256).digest())
    return f"{h}.{p}.{sig}"

# ---------------- persona ----------------
# Package-owned persona retained through the root compatibility API.
PERSONA = chat_service.PERSONA


def clean_assistant_reply(text: str) -> str:
    """Remove stage-direction parentheses from a newly generated dog reply."""
    cleaned = str(text or "")
    previous = None
    while cleaned != previous:
        previous = cleaned
        cleaned = re.sub(r"（[^（）]*）", "", cleaned)
        cleaned = re.sub(r"\([^()]*\)", "", cleaned)
    cleaned = re.sub(r"（[^）]*$", "", cleaned)
    cleaned = re.sub(r"\([^)]*$", "", cleaned)
    cleaned = cleaned.replace("（", "").replace("）", "")
    cleaned = cleaned.replace("(", "").replace(")", "")
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def _default_memory():
    return {
        "user_profile": "主人叫什么我还不知道，慢慢聊就知道了。",
        "history": [],   # list of {role, content, t}
        "born": time.time(),
        "pet_name": DEFAULT_PET_NAME,
    }

def memory_path(profile="desktop"):
    """Return the persistent chat file for one pet identity."""
    return (
        HOME_MEMORY_PATH
        if chat_memory.normalize_profile(profile) == "home"
        else MEMORY_PATH
    )


def normalize_memory_profile(profile):
    """Expose profile normalization without leaking the storage module."""
    return chat_memory.normalize_profile(profile)


def load_memory(profile="desktop"):
    profile = chat_memory.normalize_profile(profile)
    return chat_memory.load_memory(
        memory_path(profile),
        _default_memory,
        seed_path=MEMORY_PATH if profile == "home" else None,
    )


def save_memory(m, profile="desktop"):
    chat_memory.save_memory(memory_path(profile), m)


def load_config():
    """Load the local AI configuration with safe, validated defaults."""
    return chat_config.load_config(
        CONFIG_PATH, env_api_key=os.environ.get("ZHIPU_API_KEY", "")
    )


def save_config(config):
    """Persist local AI settings atomically so a crash cannot truncate them."""
    chat_config.save_config(CONFIG_PATH, config)


def _aliyun_quota_today(now=None):
    return chat_config.quota_today(now)


def _valid_uuid4(value):
    return chat_config.valid_uuid4(value)


def _fresh_aliyun_quota_state(today):
    return chat_config.fresh_quota_state(today)


def _load_aliyun_quota_state(today=None):
    return chat_config.load_quota_state(
        CHAT_QUOTA_STATE_PATH, today, limit=ALIYUN_LOCAL_DAILY_LIMIT
    )


def _save_aliyun_quota_state(state):
    chat_config.save_quota_state(CHAT_QUOTA_STATE_PATH, state)


def _aliyun_quota_available(today=None):
    return chat_config.quota_available(
        CHAT_QUOTA_STATE_PATH, today, limit=ALIYUN_LOCAL_DAILY_LIMIT
    )


def _record_aliyun_quota_success(request_id, today=None):
    return chat_config.record_quota_success(
        CHAT_QUOTA_STATE_PATH,
        request_id,
        today,
        limit=ALIYUN_LOCAL_DAILY_LIMIT,
    )


def get_api_key_source():
    """Return the active key source without exposing the key itself."""
    if os.environ.get("ZHIPU_API_KEY", "").strip():
        return "environment"
    if load_config().get("api_key"):
        return "config"
    return "none"


def get_api_key():
    key = os.environ.get("ZHIPU_API_KEY")
    if key:
        return key.strip()
    return load_config()["api_key"]


def get_chat_mode():
    return load_config()["chat_mode"]


def set_chat_mode(mode):
    if mode not in {"default", "personal"}:
        raise ValueError(f"Unsupported chat mode: {mode}")
    config = load_config()
    config["chat_mode"] = mode
    save_config(config)


def set_api_key(api_key):
    config = load_config()
    config["api_key"] = str(api_key or "").strip()
    save_config(config)


def needs_personal_setup_reminder():
    """Show the one-time personal-chat hint until its editor is first opened."""
    config = load_config()
    return not config.get("api_key") and not bool(
        config.get("personal_setup_seen", False)
    )


def mark_personal_setup_seen():
    """Persist acknowledgement even when the player leaves the key empty."""
    config = load_config()
    config["personal_setup_seen"] = True
    save_config(config)


def has_default_chat_consent():
    return bool(load_config().get("default_chat_consent", False))


def set_default_chat_consent(accepted):
    config = load_config()
    config["default_chat_consent"] = bool(accepted)
    save_config(config)


def get_default_chat_proxy_url():
    """Compatibility alias for the Cloudflare fallback endpoint."""
    return get_default_chat_fallback_url()


def _public_chat_config():
    return chat_config.load_public_config(DEFAULT_CONFIG_PATH)


def get_default_chat_primary_url():
    return chat_config.default_chat_primary_url(load_config(), _public_chat_config())


def get_default_chat_fallback_url():
    return chat_config.default_chat_fallback_url(load_config(), _public_chat_config())


def set_default_chat_proxy_url(url):
    config = load_config()
    config["default_chat_proxy_url"] = str(url or "").strip()
    save_config(config)


def get_model():
    if get_chat_mode() == "default":
        return FREE_MODEL
    return load_config()["model"]


def set_model(model):
    if model in {"glm-4-flash", "glm-4.7-flash"}:
        model = VISION_MODEL
    if model not in PERSONAL_MODELS:
        raise ValueError(f"Unsupported model: {model}")
    config = load_config()
    config["model"] = model
    save_config(config)


def get_model_name(model=None):
    return SUPPORTED_MODELS.get(
        model or get_model(), SUPPORTED_MODELS[DEFAULT_MODEL]
    )


def is_vision_model(model=None):
    """Return whether *model* accepts image content blocks."""
    if model is not None:
        return model == VISION_MODEL
    return get_chat_mode() == "personal" and get_model() == VISION_MODEL


def _chat_images_dir():
    return os.path.join(DATA_DIR, "chat_images")


def resolve_history_image(relative_path):
    """Resolve a managed thumbnail path without accepting path traversal."""
    relative = str(relative_path or "").replace("\\", "/")
    if not relative.startswith("chat_images/"):
        return ""
    target = os.path.abspath(os.path.join(DATA_DIR, *relative.split("/")))
    root = os.path.abspath(_chat_images_dir())
    if target == root or not target.startswith(root + os.sep):
        return ""
    return target


def prepare_image_attachment(source_path):
    """Return one request-only image payload and a persistent history preview."""
    path = os.path.abspath(os.fspath(source_path))
    extension = os.path.splitext(path)[1].lower()
    if not os.path.isfile(path):
        raise ValueError("图片文件不存在")
    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError("图片仅支持 PNG、JPG、JPEG 或 WEBP 格式")
    if os.path.getsize(path) > MAX_IMAGE_BYTES:
        raise ValueError("图片不能超过 10 MiB")

    reader = QImageReader(path)
    image = reader.read()
    if image.isNull():
        raise ValueError("图片无法读取，请选择有效的图片文件")

    filename = os.path.basename(path)
    thumbnail_name = f"{uuid.uuid4().hex}.png"
    relative_thumbnail = f"chat_images/{thumbnail_name}"
    thumbnail_path = resolve_history_image(relative_thumbnail)
    os.makedirs(_chat_images_dir(), exist_ok=True)
    thumbnail = image.scaled(
        MAX_HISTORY_THUMBNAIL_EDGE, MAX_HISTORY_THUMBNAIL_EDGE,
        Qt.KeepAspectRatio, Qt.SmoothTransformation,
    )
    if not thumbnail.save(thumbnail_path, "PNG"):
        raise ValueError("图片缩略图保存失败")

    try:
        with open(path, "rb") as source_file:
            encoded = base64.b64encode(source_file.read()).decode("ascii")
    except OSError as exc:
        try:
            os.remove(thumbnail_path)
        except OSError:
            pass
        raise ValueError("图片读取失败") from exc

    return {
        "base64_data": encoded,
        "filename": filename,
        "history_image": {
            "thumbnail": relative_thumbnail,
            "filename": filename,
        },
    }


def remove_history_thumbnails():
    """Remove only Petpet's managed local chat previews."""
    directory = _chat_images_dir()
    if os.path.isdir(directory):
        shutil.rmtree(directory, ignore_errors=True)


def remove_memory_thumbnails(mem):
    """Remove only previews referenced by one pet's conversation memory."""
    removed = set()
    history = mem.get("history", []) if isinstance(mem, dict) else []
    for entry in history if isinstance(history, list) else []:
        image = entry.get("image") if isinstance(entry, dict) else None
        relative = image.get("thumbnail") if isinstance(image, dict) else None
        path = resolve_history_image(relative)
        if not path or path in removed:
            continue
        removed.add(path)
        try:
            os.remove(path)
        except OSError:
            pass


def _history_text(mem, n=8, pet_name=None):
    hs = mem["history"][-n*2:]
    if not hs:
        return "（还没有聊过天）"
    pet_name = normalize_pet_name(
        pet_name or mem.get("pet_name", DEFAULT_PET_NAME)
    )
    out = []
    for h in hs:
        who = "主人" if h["role"] == "user" else pet_name
        out.append(f"{who}：{h['content']}")
    return "\n".join(out)


_time_desc = chat_service.time_description
_detect_mood = chat_service.detect_mood


def _build_messages(user_text, mem, pet_name=None, image_attachment=None):
    """Compatibility adapter for the package-owned prompt service."""
    return chat_service.build_messages(
        user_text,
        mem,
        pet_name=pet_name or mem.get("pet_name", DEFAULT_PET_NAME),
        normalize_name=normalize_pet_name,
        knowledge_finder=game_knowledge.find_relevant_entries,
        now_description=_time_desc,
        history_limit=DEFAULT_PROXY_HISTORY_MESSAGES,
        image_attachment=image_attachment,
    )


# ---------------- streaming call ----------------
def _bound_default_proxy_content(content, role="user", max_chars=None):
    return chat_transport.bound_default_proxy_content(content, role, max_chars)


def _default_proxy_payload(request_id, install_id, messages):
    return chat_transport.default_proxy_payload(request_id, install_id, messages)


def _fit_default_proxy_payload(request_id, install_id, messages):
    return chat_transport.fit_default_proxy_payload(
        request_id,
        install_id,
        messages,
        max_body_bytes=DEFAULT_PROXY_MAX_BODY_BYTES,
    )


def _default_proxy_stream(primary_endpoint, fallback_endpoint, user_text, mem,
                          timeout, pet_name=None):
    install_id = load_config().get("default_chat_install_id")
    if not install_id:
        install_id = str(uuid.uuid4())
        config = load_config()
        config["default_chat_install_id"] = install_id
        save_config(config)
    messages = _build_messages(user_text, mem, pet_name=pet_name)
    yield from chat_transport.default_proxy_stream(
        primary_endpoint,
        fallback_endpoint,
        messages,
        timeout,
        install_id=install_id,
        quota_available=_aliyun_quota_available,
        record_quota_success=_record_aliyun_quota_success,
        log_diagnostic=_log_chat_diagnostic,
        requests_module=requests,
        getproxies=urllib.request.getproxies,
        max_messages=DEFAULT_PROXY_MAX_MESSAGES,
        max_body_bytes=DEFAULT_PROXY_MAX_BODY_BYTES,
    )





def chat_stream(user_text, mem=None, on_token=None, timeout=45,
                pet_name=None, image_attachment=None):
    """Stream tokens from GLM. Yields (kind, payload) events:
       ('token', str)         -> a piece of reply text
       ('done',  full_text)   -> finished
       ('error', msg)         -> failed; caller should fallback
       Automatically retries on 429 rate limit (up to 2 times with backoff).
    """
    if mem is None:
        mem = load_memory()

    mode = get_chat_mode()
    key = get_api_key()
    if mode == "default":
        if not has_default_chat_consent():
            yield ("error", "default_consent_required")
        else:
            primary_endpoint = get_default_chat_primary_url()
            fallback_endpoint = get_default_chat_fallback_url()
            if ((primary_endpoint and not primary_endpoint.startswith("https://"))
                    or (fallback_endpoint and not fallback_endpoint.startswith("https://"))
                    or not (primary_endpoint or fallback_endpoint)):
                yield ("error", "default_provider_unavailable")
            elif image_attachment:
                yield ("error", "personal_key_required_for_image")
            else:
                yield from _default_proxy_stream(
                    primary_endpoint, fallback_endpoint, user_text, mem,
                    timeout, pet_name=pet_name
                )
        return
    if not key:
        yield ("error", "personal_api_key_required")
        return
    model = get_model()
    if image_attachment and not is_vision_model(model):
        raise ValueError("当前模型不支持图片聊天")

    for attempt in range(3):
        for ev in _stream_once(
                user_text, mem, key, on_token, timeout, pet_name=pet_name,
                model=model, image_attachment=image_attachment):
            kind, payload = ev
            if kind == "error" and payload == "rate_limit" and attempt < 2:
                # backoff: wait 8s then 15s
                import time as _t
                _t.sleep(8 * (attempt + 1))
                break
            yield ev
            if kind in ("done", "error"):
                return


def _stream_once(user_text, mem, key, on_token, timeout, pet_name=None,
                 model=None, image_attachment=None):
    selected_model = model or get_model()
    if image_attachment and not is_vision_model(selected_model):
        raise ValueError("当前模型不支持图片聊天")
    messages = _build_messages(
        user_text,
        mem,
        pet_name=pet_name,
        image_attachment=image_attachment,
    )
    yield from chat_transport.personal_stream(
        messages=messages,
        key=key,
        selected_model=selected_model,
        api_url=API_URL,
        sign_token=_sign_jwt,
        timeout=timeout,
        on_token=on_token,
        urlopen=urllib.request.urlopen,
        request_factory=urllib.request.Request,
    )





# ---------------- one-shot helper ----------------
def chat(user_text, mem=None, timeout=30, pet_name=None):
    """Blocking call, returns full reply string. Falls back to rules on error."""
    full = []
    last_err = None
    for kind, payload in chat_stream(
            user_text, mem=mem, on_token=full.append, timeout=timeout,
            pet_name=pet_name):
        if kind == "done":
            return payload
        if kind == "error":
            last_err = payload
    return fallback_reply(user_text, last_err, pet_name=pet_name)


# ---------------- fallback (no AI) ----------------
_FALLBACK = {
    "你好": ["汪！你回来啦🐶", "嘿嘿，主人来啦~", "汪汪！想你了"],
    "难过": ["…过来，Sheen 蹭蹭你。不哭不哭。", "我陪着你呢，慢慢说。"],
    "开心": ["汪汪！看到你开心我也摇尾巴！", "嘿嘿真好！"],
    "累": ["累就歇会儿，Sheen 陪你躺着。", "辛苦啦，摸摸头~"],
    "饿": ["饿了要好好吃饭呀！Sheen 也想吃🦴", "去吃点东西嘛，我等你~"],
    "睡": ["晚安呀，Sheen 守着你睡💤", "好好睡，明天见~"],
}

def fallback_reply(user_text, err=None, pet_name=None):
    """Cheap rule-based reply when AI is unavailable."""
    pet_name = normalize_pet_name(pet_name)
    t = (user_text or "").lower()
    for key, replies in _FALLBACK.items():
        if key in t:
            reply = random.choice(replies) if "random" in globals() else replies[0]
            return reply.replace("Sheen", pet_name)
    if err == "no_api_key":
        return f"汪…{pet_name} 现在连不上聊天服务，设置好 API Key 就能聊天啦。"
    if err == "rate_limit":
        return f"汪…{pet_name} 刚才想得太快啦，等一小会儿再和我说吧。"
    if err == "empty_response":
        return f"汪…{pet_name} 刚才没听清，可以再和我说一遍吗？"
    if err:
        return f"汪…{pet_name} 刚才走神了，等一会儿再和我说吧。"
    return "汪？"


def set_pet_name(pet_name, profile="desktop"):
    """Persist the current pet name alongside chat memory."""
    mem = load_memory(profile=profile)
    mem["pet_name"] = normalize_pet_name(pet_name)
    save_memory(mem, profile=profile)


# ---------------- memory update (lightweight) ----------------
def append_history(mem, role, content, image=None, profile="desktop"):
    entry = {"role": role, "content": content, "t": time.time()}
    if isinstance(image, dict):
        thumbnail = str(image.get("thumbnail", ""))
        filename = os.path.basename(str(image.get("filename", "")))
        if resolve_history_image(thumbnail) and filename:
            entry["image"] = {
                "thumbnail": thumbnail.replace("\\", "/"),
                "filename": filename,
            }
    mem["history"].append(entry)
    # keep last 60 turns
    if len(mem["history"]) > 60:
        mem["history"] = mem["history"][-60:]
    save_memory(mem, profile=profile)
    # every 6 user turns, refresh user_profile in background
    user_turns = sum(1 for h in mem["history"] if h["role"] == "user")
    if role == "user" and user_turns % 6 == 0:
        try:
            _refresh_user_profile(mem, profile=profile)
        except Exception:
            pass


def _refresh_user_profile(mem, profile="desktop"):
    """Ask the model to summarize what it knows about the user, in background.
    Uses a cheap non-stream call. Failure is silent."""
    if get_chat_mode() != "personal":
        return
    key = get_api_key()
    if not key:
        return
    recent = mem["history"][-12:]
    pet_name = normalize_pet_name(mem.get("pet_name", DEFAULT_PET_NAME))
    convo = "\n".join(
        f"{'主人' if h['role']=='user' else pet_name}：{h['content']}"
        for h in recent
    )
    prompt = (
        "根据下面的对话，用一句话总结主人的关键信息（名字、身份、近期大事、情绪状态、喜恶），"
        "不要编造，没提到的就不写。只输出总结，不要其它内容。\n\n"
        f"对话：\n{convo}\n\n总结："
    )
    body = json.dumps({
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 80,
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Authorization": f"Bearer {_sign_jwt(key)}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req, timeout=20)
        data = json.loads(r.read().decode("utf-8"))
        summary = data["choices"][0]["message"]["content"].strip()
        if summary and len(summary) < 200:
            mem["user_profile"] = summary
            save_memory(mem, profile=profile)
    except Exception:
        pass


# ---------------- proactive nudge ----------------
def maybe_nudge(mem, idle_seconds, pet_state=None, idle_min=1800,
                gap_min=10800, pet_name=None, profile="desktop"):
    """Return a proactive message if appropriate, else None.
    Called periodically by the host app. idle_seconds = seconds since last user msg.
    pet_state optional: {'hunger':n,'mood':n,'energy':n,'sleeping':bool}
    idle_min: minimum idle seconds before first nudge.
    gap_min: minimum seconds between two nudges.
    """
    if idle_seconds < idle_min:
        return None
    # don't nudge more than once per gap_min
    last = mem.get("last_nudge_t", 0)
    if time.time() - last < gap_min:
        return None

    h = time.localtime().tm_hour
    if pet_state and pet_state.get("sleeping"):
        return None
    if 0 <= h < 7:
        return None  # let user sleep

    # vary line by idle duration + time
    if idle_seconds > 6 * 3600:
        opts = ["主人？好久没见到你了，汪…你还好吗？",
                "你回来啦！Sheen 想你了好久了🐶",
                "终于等到你啦，今天过得怎么样？"]
    elif 5 <= h < 11:
        opts = ["早安呀主人~今天也要加油哦！", "早上好！吃早饭了没？"]
    elif 11 <= h < 14:
        opts = ["中午啦，记得吃饭呀~", "午饭吃了没？别饿着肚子忙。"]
    elif 17 <= h < 22:
        opts = ["今天累不累呀？Sheen 等你呢。", "晚上好~要不要聊聊今天的事？"]
    else:
        opts = ["还没睡呀…Sheen 陪着你。", "夜深了，注意休息哦。"]

    pet_name = normalize_pet_name(
        pet_name or mem.get("pet_name", DEFAULT_PET_NAME)
    )
    msg = opts[int(time.time()) % len(opts)].replace("Sheen", pet_name)
    mem["last_nudge_t"] = time.time()
    save_memory(mem, profile=profile)
    return msg


def time_greeting(pet_name=None):
    """A proactive opener the pet might say on app launch."""
    pet_name = normalize_pet_name(pet_name)
    h = time.localtime().tm_hour
    if 5 <= h < 9:   return "早呀主人！新的一天开始啦，汪~"
    if 9 <= h < 12:  return "上午好~今天忙不忙呀？"
    if 12 <= h < 14: return "中午啦，吃饭了没？别饿着~"
    if 14 <= h < 18: return "下午好~要不要歇会儿聊聊天？"
    if 18 <= h < 22: return "晚上好，今天过得怎么样？"
    return f"这么晚了还没睡呀…{pet_name} 陪着你。"


if __name__ == "__main__":
    # quick self-test
    print("API key:", "set" if get_api_key() else "MISSING (set ZHIPU_API_KEY)")
    print("Greeting:", time_greeting())
    print("Fallback test:", fallback_reply("我今天好难过"))

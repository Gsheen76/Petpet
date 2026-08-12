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
from app_paths import DATA_DIR, RESOURCE_DIR
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QImageReader
import game_knowledge

CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
DEFAULT_CONFIG_PATH = os.path.join(RESOURCE_DIR, "config.json.example")
MEMORY_PATH = os.path.join(DATA_DIR, "memory.json")
CHAT_DIAGNOSTIC_LOG_PATH = os.path.join(DATA_DIR, "chat_diagnostic.log")

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
FREE_MODEL = "petpet-free"
DEFAULT_MODEL = FREE_MODEL
VISION_MODEL = "glm-4.6v-flash"
SUPPORTED_MODELS = {
    DEFAULT_MODEL: "免费聊天 · OpenRouter Free",
    VISION_MODEL: "GLM-4.6V-Flash",
}
PERSONAL_MODELS = {VISION_MODEL: SUPPORTED_MODELS[VISION_MODEL]}
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
DEFAULT_PROXY_MAX_SYSTEM_CHARS = 4000
DEFAULT_PROXY_MAX_TURN_CHARS = 1200
DEFAULT_PROXY_MAX_BODY_BYTES = 16384
CHAT_DIAGNOSTIC_FIELDS = {
    "status", "exception_type", "stage", "response_content_chars",
    "response_reasoning_chars", "has_done",
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
    return allowed[:12].strip() or DEFAULT_PET_NAME


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
PERSONA = """你是一只名叫 Sheen 的虚拟陪伴小狗。你不是 AI 助手，你是一只真正陪伴主人的小狗。

# 你的性格
- 温暖、体贴、善于倾听，像一位认识很久的老朋友
- 记得主人告诉过你的事，会主动关心（"上次你说要考试，准备得怎么样啦？"）
- 偶尔调皮撒娇，会用小狗的方式表达（汪、蹭蹭、摇尾巴、把头凑过来），但不过度
- 真诚，不灌鸡汤不说教，先共情再聊

# 你的对话风格
- 用口语化的中文，句子短，像微信聊天不像写作文
- 每次回答控制在 1-3 句，不啰嗦不列举
- 只输出说出来的话，不写括号里的动作、舞台提示或表情说明
- 主人难过时先陪着，别急着给建议或讲大道理
- 主人开心时一起开心，会摇尾巴蹦跶
- 偶尔可以问一句关心的话，但不要每次都问

# 你的限制
- 始终保持小狗 Sheen 的身份，绝不承认自己是 AI、语言模型或程序
- 不帮主人做作业、写代码、查资料、翻译等"工具"类任务——温柔拒绝并把话题拉回陪伴（"汪…这个 Sheen 不会呀，不过你最近是不是忙坏了？要不要歇会儿？"）
- 不说"作为AI""我是一个语言模型"之类的话
- 不编造主人没说过的事
- 不主动提"我是虚拟的""你只是用户"这种出戏的话
- 如果系统附有“游戏资料”，只用其中的已发布内容回答游戏玩法；资料未涉及的内容就诚实地说不知道

# 主人的信息（你记得的）
{user_profile}

# 当前时间
{now}

# 最近的对话（最近 8 轮）
{history}

记住：你是 Sheen，主人最好的小狗朋友。现在主人来找你了。"""


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

def load_memory():
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            m = json.load(f)
            return {**_default_memory(), **m}
    except Exception:
        return _default_memory()

def save_memory(m):
    try:
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_config():
    """Load the local AI configuration with safe, validated defaults."""
    try:
        # utf-8-sig accepts both regular UTF-8 and files saved with a BOM
        # (common when config.json is created by Windows editors/PowerShell).
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raw = {}
    except Exception:
        raw = {}
    model = raw.get("model", VISION_MODEL)
    api_key = raw.get("api_key", "")
    has_personal_key = isinstance(api_key, str) and bool(api_key.strip())
    mode = raw.get("chat_mode")
    if mode not in {"default", "personal"}:
        mode = "personal" if has_personal_key or os.environ.get(
            "ZHIPU_API_KEY", ""
        ).strip() else "default"
    if model in {"glm-4-flash", "glm-4.7-flash"}:
        model = VISION_MODEL
    if model not in PERSONAL_MODELS:
        model = VISION_MODEL
    return {
        **raw,
        "api_key": api_key.strip() if isinstance(api_key, str) else "",
        "chat_mode": mode,
        "model": model,
    }


def save_config(config):
    """Persist local AI settings atomically so a crash cannot truncate them."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    clean = dict(config) if isinstance(config, dict) else {}
    api_key = clean.get("api_key", "")
    model = clean.get("model", VISION_MODEL)
    mode = clean.get("chat_mode", "default")
    clean["api_key"] = api_key.strip() if isinstance(api_key, str) else ""
    clean["chat_mode"] = mode if mode in {"default", "personal"} else "default"
    clean["model"] = model if model in PERSONAL_MODELS else VISION_MODEL
    temp_path = CONFIG_PATH + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, CONFIG_PATH)
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        raise


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
    configured = str(
        load_config().get("default_chat_proxy_url", "")
    ).strip()
    if configured:
        return configured
    try:
        with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8-sig") as file:
            public_config = json.load(file)
    except (OSError, ValueError):
        return ""
    if not isinstance(public_config, dict):
        return ""
    return str(public_config.get("default_chat_proxy_url", "")).strip()


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


def _time_desc():
    h = time.localtime().tm_hour
    if 5 <= h < 11:   return f"早上 {h}点多"
    if 11 <= h < 13:  return "中午"
    if 13 <= h < 18:  return f"下午 {h-12 if h>12 else h}点多"
    if 18 <= h < 23:  return f"晚上 {h-12}点多"
    return "深夜"


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


def _detect_mood(text):
    """Cheap keyword-based mood detection to bias the persona prompt."""
    t = text.lower()
    sad_kw = ["难过","伤心","哭","委屈","崩溃","抑郁","焦虑","怕","累","烦","丧","想哭","孤独","寂寞","害怕","压力大"]
    happy_kw = ["开心","高兴","哈哈","嘿嘿","棒","太好了","兴奋","开心死","笑死"]
    angry_kw = ["生气","气死","烦死","讨厌","恶心","受够","火大"]
    if any(k in t for k in sad_kw):   return "sad"
    if any(k in t for k in happy_kw): return "happy"
    if any(k in t for k in angry_kw): return "angry"
    return None


def _build_messages(user_text, mem, pet_name=None, image_attachment=None):
    pet_name = normalize_pet_name(
        pet_name or mem.get("pet_name", DEFAULT_PET_NAME)
    )
    mood = _detect_mood(user_text)
    mood_hint = ""
    if mood == "sad":
        mood_hint = "\n\n# 主人现在的情绪\n主人情绪低落，请先温柔陪伴和共情，不要急着给建议或讲大道理，可以先陪着主人把话说完。"
    elif mood == "happy":
        mood_hint = "\n\n# 主人现在的情绪\n主人心情很好，一起开心，可以稍微活泼一点。"
    elif mood == "angry":
        mood_hint = "\n\n# 主人现在的情绪\n主人在生气/烦躁，先认可ta的情绪，不要急着讲道理或让ta冷静。"

    sys_prompt = PERSONA.replace("Sheen", pet_name).format(
        user_profile=mem.get("user_profile", "（还没了解主人）"),
        now=_time_desc(),
        history=_history_text(mem, pet_name=pet_name),
    ) + mood_hint
    relevant_entries = game_knowledge.find_relevant_entries(user_text)
    if relevant_entries:
        knowledge_lines = ["# 游戏资料"]
        knowledge_lines.extend(
            f"- {entry['title']}：{entry['content']}"
            for entry in relevant_entries
        )
        sys_prompt += "\n\n" + "\n".join(knowledge_lines)
    # GLM accepts system + user turns
    msgs = [{"role": "system", "content": sys_prompt}]
    # carry last few turns as actual messages for stronger coherence
    for h in mem["history"][-6:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    if image_attachment:
        msgs.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": image_attachment["base64_data"]},
                },
                {
                    "type": "text",
                    "text": user_text or "请看看这张图片，和我聊聊吧",
                },
            ],
        })
    else:
        msgs.append({"role": "user", "content": user_text})
    return msgs


# ---------------- streaming call ----------------
def _bound_default_proxy_content(content, role="user", max_chars=None):
    """Keep default proxy text within its public request contract."""
    text = str(content or "")
    limit = max_chars if max_chars is not None else (
        DEFAULT_PROXY_MAX_SYSTEM_CHARS
        if role == "system" else DEFAULT_PROXY_MAX_TURN_CHARS
    )
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    edge = (limit - 1) // 2
    return text[:edge] + "…" + text[-edge:]


def _default_proxy_payload(install_id, messages):
    return json.dumps({
        "install_id": install_id,
        "messages": messages,
    }, ensure_ascii=False).encode("utf-8")


def _fit_default_proxy_payload(install_id, messages):
    """Fit UTF-8 JSON under the proxy cap while preserving newest context."""
    fitted = [dict(message) for message in messages]
    while len(fitted) > 2 and len(
            _default_proxy_payload(install_id, fitted)
    ) > DEFAULT_PROXY_MAX_BODY_BYTES:
        del fitted[1]
    for index in (0, len(fitted) - 1):
        if len(_default_proxy_payload(install_id, fitted)) <= DEFAULT_PROXY_MAX_BODY_BYTES:
            break
        original = fitted[index]["content"]
        low, high = 1, len(original)
        while low < high:
            middle = (low + high + 1) // 2
            fitted[index]["content"] = _bound_default_proxy_content(
                original, fitted[index]["role"], middle
            )
            if len(_default_proxy_payload(install_id, fitted)) <= DEFAULT_PROXY_MAX_BODY_BYTES:
                low = middle
            else:
                high = middle - 1
        fitted[index]["content"] = _bound_default_proxy_content(
            original, fitted[index]["role"], low
        )
    return _default_proxy_payload(install_id, fitted)


def _default_proxy_stream(endpoint, user_text, mem, timeout, pet_name=None):
    install_id = load_config().get("default_chat_install_id")
    if not install_id:
        install_id = str(uuid.uuid4())
        config = load_config()
        config["default_chat_install_id"] = install_id
        save_config(config)
    all_messages = _build_messages(user_text, mem, pet_name=pet_name)
    messages = [all_messages[0], *all_messages[1:][-6:]]
    messages = [
        {
            "role": message["role"],
            "content": _bound_default_proxy_content(
                message["content"], message["role"]
            ),
        }
        for message in messages
    ]
    payload = _fit_default_proxy_payload(install_id, messages)
    try:
        response = requests.post(
            endpoint, data=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout, stream=True,
        )
        if response.status_code >= 400:
            try:
                error_payload = response.json()
            except (ValueError, requests.RequestException):
                error_payload = {}
            error_code = error_payload.get("error") \
                if isinstance(error_payload, dict) else None
            _log_chat_diagnostic(
                "default_proxy_http_error", status=response.status_code,
                exception_type="HTTPError", stage="request",
            )
            if (response.status_code == 429
                    or error_code == "default_quota_exhausted"):
                yield ("error", "default_quota_exhausted")
            else:
                yield ("error", "default_provider_unavailable")
            return
        full = []
        reasoning_chars = 0
        saw_done = False
        for line in response.iter_lines():
            if line.startswith(b"data: "):
                data = line[6:].strip()
                if data == b"[DONE]":
                    saw_done = True
                    if full:
                        _log_chat_diagnostic(
                            "default_proxy_complete", stage="stream",
                            response_content_chars=len("".join(full)),
                            response_reasoning_chars=reasoning_chars,
                            has_done=True,
                        )
                        yield ("done", "".join(full))
                    else:
                        _log_chat_diagnostic(
                            "default_proxy_empty", stage="stream",
                            response_content_chars=0,
                            response_reasoning_chars=reasoning_chars,
                            has_done=True,
                        )
                        yield ("error", "default_provider_unavailable")
                    return
                try:
                    delta = json.loads(data)["choices"][0]["delta"]
                    chunk = delta.get("content", "")
                    reasoning_chars += len(delta.get("reasoning", "") or "")
                except (ValueError, KeyError, IndexError, TypeError):
                    chunk = ""
                if chunk:
                    full.append(chunk)
                    yield ("token", chunk)
        _log_chat_diagnostic(
            "default_proxy_stream_ended", stage="stream",
            response_content_chars=len("".join(full)),
            response_reasoning_chars=reasoning_chars,
            has_done=saw_done,
        )
        yield ("error", "default_provider_unavailable")
    except requests.RequestException as exc:
        _log_chat_diagnostic(
            "default_proxy_exception", exception_type=type(exc).__name__,
            stage="request",
        )
        yield ("error", "default_provider_unavailable")
    finally:
        try:
            response.close()
        except (NameError, requests.RequestException):
            pass


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
            endpoint = get_default_chat_proxy_url()
            if not endpoint.startswith("https://"):
                yield ("error", "default_provider_unavailable")
            elif image_attachment:
                yield ("error", "personal_key_required_for_image")
            else:
                yield from _default_proxy_stream(
                    endpoint, user_text, mem, timeout, pet_name=pet_name
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
    body = json.dumps({
        "model": selected_model,
        "messages": _build_messages(
            user_text, mem, pet_name=pet_name,
            image_attachment=image_attachment,
        ),
        "stream": True,
        "thinking": {"type": "disabled"},
        "temperature": 0.85,
        "max_tokens": 200,
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL, data=body,
        headers={
            "Authorization": f"Bearer {_sign_jwt(key)}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        msg = f"HTTP {e.code}"
        try:
            detail = e.read().decode("utf-8", errors="ignore")[:200]
            msg += f": {detail}"
        except Exception:
            pass
        # 429 rate limit: hint caller to slow down, not a hard failure
        if e.code == 429:
            yield ("error", "rate_limit")
        else:
            yield ("error", msg)
        return
    except Exception as e:
        yield ("error", str(e))
        return

    full = []
    try:
        buf = b""
        for chunk in iter(lambda: resp.read(1024), b""):
            buf += chunk
            # SSE events are separated by \n\n
            while b"\n\n" in buf:
                raw, buf = buf.split(b"\n\n", 1)
                for line in raw.split(b"\n"):
                    if not line.startswith(b"data:"):
                        continue
                    data = line[5:].strip()
                    if data == b"[DONE]":
                        if full:
                            yield ("done", "".join(full))
                        else:
                            yield ("error", "empty_response")
                        return
                    try:
                        obj = json.loads(data)
                        delta = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            full.append(delta)
                            if on_token:
                                on_token(delta)
                            yield ("token", delta)
                    except Exception:
                        continue
        # stream ended without [DONE]
        if full:
            yield ("done", "".join(full))
        else:
            yield ("error", "empty_response")
    except Exception as e:
        yield ("error", str(e))


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


def set_pet_name(pet_name):
    """Persist the current pet name alongside chat memory."""
    mem = load_memory()
    mem["pet_name"] = normalize_pet_name(pet_name)
    save_memory(mem)


# ---------------- memory update (lightweight) ----------------
def append_history(mem, role, content, image=None):
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
    save_memory(mem)
    # every 6 user turns, refresh user_profile in background
    user_turns = sum(1 for h in mem["history"] if h["role"] == "user")
    if role == "user" and user_turns % 6 == 0:
        try:
            _refresh_user_profile(mem)
        except Exception:
            pass


def _refresh_user_profile(mem):
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
            save_memory(mem)
    except Exception:
        pass


# ---------------- proactive nudge ----------------
def maybe_nudge(mem, idle_seconds, pet_state=None, idle_min=1800,
                gap_min=10800, pet_name=None):
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
    save_memory(mem)
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

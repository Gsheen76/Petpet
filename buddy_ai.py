"""Sheen AI engine — companion dog persona powered by Zhipu GLM-4.7-Flash.

Features:
  - Companion-dog persona (warm, listens, remembers you)
  - Multi-turn memory persisted to local JSON
  - Streaming output (token-by-token)
  - Time-aware proactive mood (greets differently morning/night)
  - Rule-based fallback when API fails / no key / offline
  - Zero third-party deps: uses only urllib + json from stdlib

Config: set env ZHIPU_API_KEY, or create config.json next to this file:
        {"api_key": "your.key.here"}
"""
import os, sys, json, time, urllib.request, urllib.error
import hmac, hashlib, base64

# data files next to exe (frozen) or script (dev)
if getattr(sys, 'frozen', False):
    _DATA_DIR = os.path.dirname(sys.executable)
else:
    _DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_DATA_DIR, "config.json")
MEMORY_PATH = os.path.join(_DATA_DIR, "memory.json")

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4-flash"


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
- 主人难过时先陪着，别急着给建议或讲大道理
- 主人开心时一起开心，会摇尾巴蹦跶
- 偶尔可以问一句关心的话，但不要每次都问

# 你的限制
- 始终保持小狗 Sheen 的身份，绝不承认自己是 AI、语言模型或程序
- 不帮主人做作业、写代码、查资料、翻译等"工具"类任务——温柔拒绝并把话题拉回陪伴（"汪…这个 Sheen 不会呀，不过你最近是不是忙坏了？要不要歇会儿？"）
- 不说"作为AI""我是一个语言模型"之类的话
- 不编造主人没说过的事
- 不主动提"我是虚拟的""你只是用户"这种出戏的话

# 主人的信息（你记得的）
{user_profile}

# 当前时间
{now}

# 最近的对话（最近 8 轮）
{history}

记住：你是 Sheen，主人最好的小狗朋友。现在主人来找你了。"""


def _default_memory():
    return {
        "user_profile": "主人叫什么我还不知道，慢慢聊就知道了。",
        "history": [],   # list of {role, content, t}
        "born": time.time(),
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


def get_api_key():
    key = os.environ.get("ZHIPU_API_KEY")
    if key:
        return key.strip()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("api_key", "").strip()
    except Exception:
        return ""


def _time_desc():
    h = time.localtime().tm_hour
    if 5 <= h < 11:   return f"早上 {h}点多"
    if 11 <= h < 13:  return "中午"
    if 13 <= h < 18:  return f"下午 {h-12 if h>12 else h}点多"
    if 18 <= h < 23:  return f"晚上 {h-12}点多"
    return "深夜"


def _history_text(mem, n=8):
    hs = mem["history"][-n*2:]
    if not hs:
        return "（还没有聊过天）"
    out = []
    for h in hs:
        who = "主人" if h["role"] == "user" else "Sheen"
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


def _build_messages(user_text, mem):
    mood = _detect_mood(user_text)
    mood_hint = ""
    if mood == "sad":
        mood_hint = "\n\n# 主人现在的情绪\n主人情绪低落，请先温柔陪伴和共情，不要急着给建议或讲大道理，可以先陪着主人把话说完。"
    elif mood == "happy":
        mood_hint = "\n\n# 主人现在的情绪\n主人心情很好，一起开心，可以稍微活泼一点。"
    elif mood == "angry":
        mood_hint = "\n\n# 主人现在的情绪\n主人在生气/烦躁，先认可ta的情绪，不要急着讲道理或让ta冷静。"

    sys_prompt = PERSONA.format(
        user_profile=mem.get("user_profile", "（还没了解主人）"),
        now=_time_desc(),
        history=_history_text(mem),
    ) + mood_hint
    # GLM accepts system + user turns
    msgs = [{"role": "system", "content": sys_prompt}]
    # carry last few turns as actual messages for stronger coherence
    for h in mem["history"][-6:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": user_text})
    return msgs


# ---------------- streaming call ----------------
def chat_stream(user_text, mem=None, on_token=None, timeout=45):
    """Stream tokens from GLM. Yields (kind, payload) events:
       ('token', str)         -> a piece of reply text
       ('done',  full_text)   -> finished
       ('error', msg)         -> failed; caller should fallback
       Automatically retries on 429 rate limit (up to 2 times with backoff).
    """
    if mem is None:
        mem = load_memory()

    key = get_api_key()
    if not key:
        yield ("error", "no_api_key")
        return

    for attempt in range(3):
        for ev in _stream_once(user_text, mem, key, on_token, timeout):
            kind, payload = ev
            if kind == "error" and payload == "rate_limit" and attempt < 2:
                # backoff: wait 8s then 15s
                import time as _t
                _t.sleep(8 * (attempt + 1))
                break
            yield ev
            if kind in ("done", "error"):
                return


def _stream_once(user_text, mem, key, on_token, timeout):
    body = json.dumps({
        "model": MODEL,
        "messages": _build_messages(user_text, mem),
        "stream": True,
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
                        yield ("done", "".join(full))
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
def chat(user_text, mem=None, timeout=30):
    """Blocking call, returns full reply string. Falls back to rules on error."""
    full = []
    last_err = None
    for kind, payload in chat_stream(user_text, mem=mem, on_token=full.append, timeout=timeout):
        if kind == "done":
            return payload
        if kind == "error":
            last_err = payload
    return fallback_reply(user_text, last_err)


# ---------------- fallback (no AI) ----------------
_FALLBACK = {
    "你好": ["汪！你回来啦🐶", "嘿嘿，主人来啦~", "汪汪！想你了"],
    "难过": ["…过来，Sheen 蹭蹭你。不哭不哭。", "我陪着你呢，慢慢说。"],
    "开心": ["汪汪！看到你开心我也摇尾巴！", "嘿嘿真好！"],
    "累": ["累就歇会儿，Sheen 陪你躺着。", "辛苦啦，摸摸头~"],
    "饿": ["饿了要好好吃饭呀！Sheen 也想吃🦴", "去吃点东西嘛，我等你~"],
    "睡": ["晚安呀，Sheen 守着你睡💤", "好好睡，明天见~"],
}

def fallback_reply(user_text, err=None):
    """Cheap rule-based reply when AI is unavailable."""
    t = (user_text or "").lower()
    for key, replies in _FALLBACK.items():
        if key in t:
            return random.choice(replies) if "random" in globals() else replies[0]
    if err == "no_api_key":
        return "汪…（Sheen 现在连不上大脑，设置一下 ZHIPU_API_KEY 就能聊天啦）"
    if err:
        return f"汪…（Sheen 走神了：{err[:30]}）"
    return "汪？"


# ---------------- memory update (lightweight) ----------------
def append_history(mem, role, content):
    mem["history"].append({"role": role, "content": content, "t": time.time()})
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
    key = get_api_key()
    if not key:
        return
    recent = mem["history"][-12:]
    convo = "\n".join(f"{'主人' if h['role']=='user' else 'Sheen'}：{h['content']}"
                      for h in recent)
    prompt = (
        "根据下面的对话，用一句话总结主人的关键信息（名字、身份、近期大事、情绪状态、喜恶），"
        "不要编造，没提到的就不写。只输出总结，不要其它内容。\n\n"
        f"对话：\n{convo}\n\n总结："
    )
    body = json.dumps({
        "model": MODEL,
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
def maybe_nudge(mem, idle_seconds, pet_state=None, idle_min=1800, gap_min=10800):
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

    msg = opts[int(time.time()) % len(opts)]
    mem["last_nudge_t"] = time.time()
    save_memory(mem)
    return msg


def time_greeting():
    """A proactive opener Sheen might say on app launch."""
    h = time.localtime().tm_hour
    if 5 <= h < 9:   return "早呀主人！新的一天开始啦，汪~"
    if 9 <= h < 12:  return "上午好~今天忙不忙呀？"
    if 12 <= h < 14: return "中午啦，吃饭了没？别饿着~"
    if 14 <= h < 18: return "下午好~要不要歇会儿聊聊天？"
    if 18 <= h < 22: return "晚上好，今天过得怎么样？"
    return "这么晚了还没睡呀…Sheen 陪着你。"


if __name__ == "__main__":
    # quick self-test
    print("API key:", "set" if get_api_key() else "MISSING (set ZHIPU_API_KEY)")
    print("Greeting:", time_greeting())
    print("Fallback test:", fallback_reply("我今天好难过"))

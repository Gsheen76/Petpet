# -*- coding: utf-8 -*-
"""一次性脚本：api.py 接入结构化长期记忆（用后即删）。

~NL~ 占位符 = api.py 源码里的反斜杠 n 转义；JSON 示例用单引号
Python 字符串承载双引号，全程零反斜杠。
"""
import ast
import io

BSN = chr(92) + "n"

path = "petpet/chat/api.py"
with io.open(path, encoding="utf-8") as f:
    t = f.read()

old = '''def _default_memory():
    return {
        "user_profile": "主人叫什么我还不知道，慢慢聊就知道了。",
        "history": [],   # list of {role, content, t}
        "born": time.time(),
        "pet_name": DEFAULT_PET_NAME,
    }'''
new = '''def _default_memory():
    return {
        "user_profile": "主人叫什么我还不知道，慢慢聊就知道了。",
        "profile_facts": {},   # 结构化长期记忆（2026-09-10）：
        # {"称呼": [...], "作息": [...], "喜欢": [...], "讨厌": [...],
        #  "重要的事": [...], "其他": [...]}
        "history": [],   # list of {role, content, t}
        "born": time.time(),
        "pet_name": DEFAULT_PET_NAME,
    }'''
assert old in t, "default memory anchor"
t = t.replace(old, new)

old2 = '''    legacy_home_path = _memory_path_for_data_dir(
        "memory-home.json", HOME_MEMORY_PATH
    )
    return chat_memory.load_memory(
        memory_path(pet_id),
        _default_memory,
        seed_path=legacy_home_path if (
            pet_id == "lunch_meat" and not os.path.exists(memory_path(pet_id))
        ) else None,
    )'''
new2 = '''    legacy_home_path = _memory_path_for_data_dir(
        "memory-home.json", HOME_MEMORY_PATH
    )
    mem = chat_memory.load_memory(
        memory_path(pet_id),
        _default_memory,
        seed_path=legacy_home_path if (
            pet_id == "lunch_meat" and not os.path.exists(memory_path(pet_id))
        ) else None,
    )
    # 旧 user_profile 字符串一次性迁移进结构化档案（不丢记忆）。
    return chat_memory.ensure_profile_facts(mem)'''
assert old2 in t, "load_memory anchor"
t = t.replace(old2, new2)

old3 = t[t.index('def _refresh_user_profile'):
         t.index('# ---------------- proactive nudge ----------------')]

new3 = """def _refresh_user_profile(mem, pet_id="lunch_meat", *, profile=None):
    \"\"\"结构化长期记忆（2026-09-10）：LLM 从近期对话抽取主人档案
    （称呼/作息/喜好/讨厌/重要的事），合并进 mem["profile_facts"]。
    用便宜的非流式调用，失败静默；legacy user_profile 同步为分栏
    渲染文本，供旧版本回退读取。\"\"\"
    if get_chat_mode() != "personal":
        return
    key = get_api_key()
    if not key:
        return
    recent = mem["history"][-12:]
    pet_name = normalize_pet_name(mem.get("pet_name", DEFAULT_PET_NAME))
    convo = "~NL~".join(
        f"{'主人' if h['role']=='user' else pet_name}：{h['content']}"
        for h in recent
    )
    known = chat_memory.render_profile_facts(
        chat_memory.ensure_profile_facts(mem)["profile_facts"])
    fmt = '格式：{"称呼": [...], "作息": [...], "喜欢": [...], ' \\
          '"讨厌": [...], "重要的事": [...]}'
    prompt = (
        "你是记忆抽取器。根据下面的对话更新主人的档案。只输出 JSON，"
        + fmt
        + "~NL~规则：每栏 0-3 条、每条不超过 20 字；只写对话里明确"
        "提到的，不要编造；称呼栏把最新称呼放第一个；已有的档案仅供"
        "参考、避免重复提取。~NL~~NL~"
        f"已有档案：~NL~{known}~NL~~NL~对话：~NL~{convo}~NL~~NL~JSON："
    )
    body = json.dumps({
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.2,
        "max_tokens": 200,
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
        raw = data["choices"][0]["message"]["content"].strip()
        extracted = chat_memory.parse_profile_extraction(raw)
        if extracted:
            mem["profile_facts"] = chat_memory.merge_profile_facts(
                chat_memory.ensure_profile_facts(mem)["profile_facts"],
                extracted,
            )
            mem["user_profile"] = chat_memory.render_profile_facts(
                mem["profile_facts"])
            save_memory(mem, pet_id, profile=profile)
    except Exception:
        pass


""".replace("~NL~", BSN).replace("~BS~", chr(92))
t = t.replace(old3, new3)
with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(t)
ast.parse(t)
print("api.py updated OK")

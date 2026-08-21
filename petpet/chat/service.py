"""Pure persona and prompt construction for Petpet chat."""

import time


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

记住：你是 Sheen，主人最好的小狗朋友。现在主人来找你了。"""


def time_description():
    hour = time.localtime().tm_hour
    if 5 <= hour < 11:
        return f"早上 {hour}点多"
    if 11 <= hour < 13:
        return "中午"
    if 13 <= hour < 18:
        return f"下午 {hour - 12 if hour > 12 else hour}点多"
    if 18 <= hour < 23:
        return f"晚上 {hour - 12}点多"
    return "深夜"


def detect_mood(text):
    """Cheap keyword-based mood detection to bias the persona prompt."""
    lowered = str(text or "").lower()
    sad = ["难过", "伤心", "哭", "委屈", "崩溃", "抑郁", "焦虑", "怕", "累", "烦", "丧", "想哭", "孤独", "寂寞", "害怕", "压力大"]
    happy = ["开心", "高兴", "哈哈", "嘿嘿", "棒", "太好了", "兴奋", "开心死", "笑死"]
    angry = ["生气", "气死", "烦死", "讨厌", "恶心", "受够", "火大"]
    if any(keyword in lowered for keyword in sad):
        return "sad"
    if any(keyword in lowered for keyword in happy):
        return "happy"
    if any(keyword in lowered for keyword in angry):
        return "angry"
    return None


def build_messages(
    user_text,
    memory,
    *,
    pet_name,
    personality="",
    normalize_name,
    knowledge_finder,
    now_description=time_description,
    history_limit=10,
    image_attachment=None,
):
    """Build provider-neutral chat messages from explicit dependencies."""
    pet_name = normalize_name(pet_name or memory.get("pet_name"))
    mood = detect_mood(user_text)
    mood_hint = ""
    if mood == "sad":
        mood_hint = "\n\n# 主人现在的情绪\n主人情绪低落，请先温柔陪伴和共情，不要急着给建议或讲大道理，可以先陪着主人把话说完。"
    elif mood == "happy":
        mood_hint = "\n\n# 主人现在的情绪\n主人心情很好，一起开心，可以稍微活泼一点。"
    elif mood == "angry":
        mood_hint = "\n\n# 主人现在的情绪\n主人在生气/烦躁，先认可ta的情绪，不要急着讲道理或让ta冷静。"

    system = PERSONA.replace("Sheen", pet_name).format(
        user_profile=memory.get("user_profile", "（还没了解主人）"),
        now=now_description(),
    )
    if personality:
        system += "\n\n# 当前小狗的性格\n" + str(personality).strip()
    system += mood_hint
    entries = knowledge_finder(user_text, limit=5)
    if entries:
        lines = ["# 游戏资料"]
        lines.extend(
            f"- {entry['title']}：{entry['content']}" for entry in entries
        )
        system += "\n\n" + "\n".join(lines)

    messages = [{"role": "system", "content": system}]
    for item in memory["history"][-history_limit:]:
        messages.append({"role": item["role"], "content": item["content"]})
    if image_attachment:
        messages.append({
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
        messages.append({"role": "user", "content": user_text})
    return messages

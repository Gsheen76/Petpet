import buddy_ai as ai


def test_persona_is_owned_by_chat_service():
    from petpet.chat import service

    assert ai.PERSONA is service.PERSONA


def test_service_builds_mood_and_optional_game_context():
    from petpet.chat.service import build_messages

    memory = {
        "pet_name": "团子",
        "user_profile": "主人最近在上班。",
        "history": [],
    }
    messages = build_messages(
        "小屋怎么装修？我有点累",
        memory,
        pet_name="团子",
        normalize_name=lambda value: value,
        knowledge_finder=lambda _text, limit: [{
            "title": "小屋",
            "content": "可以进入装修模式摆放家具。",
        }],
        now_description=lambda: "晚上 8点多",
        history_limit=10,
    )

    system = messages[0]["content"]
    assert "名叫 团子" in system
    assert "主人情绪低落" in system
    assert "# 游戏资料" in system
    assert "装修模式" in system
    assert messages[-1] == {"role": "user", "content": "小屋怎么装修？我有点累"}


def test_service_uses_explicit_personality_after_pet_is_renamed():
    from petpet.chat.service import build_messages

    messages = build_messages(
        "你好",
        {"pet_name": "奶油", "user_profile": "", "history": []},
        pet_name="奶油",
        personality="温柔可爱，语气柔软，会耐心安慰主人。",
        normalize_name=lambda value: value,
        knowledge_finder=lambda _text, limit: [],
        now_description=lambda: "晚上 8点多",
    )

    assert "奶油" in messages[0]["content"]
    assert "温柔可爱" in messages[0]["content"]

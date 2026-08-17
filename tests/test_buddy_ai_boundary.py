import buddy_ai

from petpet.chat import api


def test_root_buddy_ai_aliases_packaged_chat_api():
    assert buddy_ai is api
    assert buddy_ai.chat_stream is api.chat_stream
    assert buddy_ai.prepare_image_attachment is api.prepare_image_attachment
    assert buddy_ai.maybe_nudge is api.maybe_nudge


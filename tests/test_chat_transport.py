import json
import unittest


class _Stream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def read(self, _size):
        return self._chunks.pop(0) if self._chunks else b""


class ChatTransportTests(unittest.TestCase):
    def test_fit_payload_keeps_system_and_newest_turn_under_byte_cap(self):
        from petpet.chat import transport

        messages = [
            {"role": "system", "content": "设定" * 100},
            {"role": "user", "content": "旧消息" * 100},
            {"role": "assistant", "content": "新回复" * 100},
            {"role": "user", "content": "最新" * 100},
        ]

        body = transport.fit_default_proxy_payload(
            "request", "install", messages, max_body_bytes=520
        )
        decoded = json.loads(body.decode("utf-8"))

        self.assertLessEqual(len(body), 520)
        self.assertEqual(decoded["messages"][0]["role"], "system")
        self.assertEqual(decoded["messages"][-1]["role"], "user")

    def test_personal_stream_parses_tokens_and_done(self):
        from petpet.chat import transport

        response = _Stream([
            b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n',
            b"data: [DONE]\n\n",
        ])
        captured = {}

        def open_request(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return response

        events = list(transport.personal_stream(
            messages=[{"role": "user", "content": "hello"}],
            key="id.secret",
            selected_model="glm-test",
            api_url="https://example.test/chat",
            sign_token=lambda _key: "token",
            urlopen=open_request,
            timeout=7,
        ))

        self.assertEqual(events, [("token", "hi"), ("done", "hi")])
        self.assertEqual(captured["timeout"], 7)
        self.assertEqual(
            json.loads(captured["request"].data.decode("utf-8"))["model"],
            "glm-test",
        )


if __name__ == "__main__":
    unittest.main()

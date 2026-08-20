import assert from "node:assert/strict";
import test from "node:test";

import { handleRequest } from "../src/server.js";

const INSTALL_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const REQUEST_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

function request(body = {}) {
  return new Request("https://chat.example/v1/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      request_id: REQUEST_ID,
      install_id: INSTALL_ID,
      messages: [{ role: "user", content: "你好" }],
      ...body,
    }),
  });
}

function environment() {
  return {
    ZHIPU_API_KEY: "test-only-key",
  };
}

test("rejects invalid request contracts before network calls", async () => {
  let calls = 0;
  const fetchImpl = async () => { calls += 1; throw new Error("unexpected"); };
  const cases = [
    new Request("https://chat.example/other", { method: "POST" }),
    new Request("https://chat.example/v1/chat", { method: "GET" }),
    new Request("https://chat.example/v1/chat", { method: "POST", body: "{}" }),
    request({ request_id: "bad" }),
    request({ install_id: "bad" }),
    request({ messages: "bad" }),
    request({ messages: Array.from({ length: 13 }, () => ({ role: "user", content: "a" })) }),
    request({ messages: [{ role: "system", content: "a".repeat(8001) }] }),
    request({ messages: [{ role: "user", content: "a".repeat(1601) }] }),
  ];
  for (const item of cases) {
    assert.equal((await handleRequest(item, { env: environment(), fetchImpl })).status, 400);
  }
  assert.equal(calls, 0);
});

test("uses paid GLM-4.7-FlashX with the expanded input contract", async () => {
  const calls = [];
  const event = "data: {\"choices\":[{\"delta\":{\"content\":\"汪\"}}]}\n\n";
  const response = await handleRequest(request({
    messages: [
      { role: "system", content: "人".repeat(8000) },
      ...Array.from({ length: 11 }, (_, index) => ({
        role: index % 2 ? "assistant" : "user",
        content: `turn-${index}`,
      })),
    ],
  }), {
    env: environment(),
    fetchImpl: async (url, options) => {
      calls.push({ url: String(url), options });
      return new Response(event, {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      });
    },
  });

  assert.equal(response.status, 200);
  assert.equal(calls.length, 1);
  const payload = JSON.parse(calls[0].options.body);
  assert.equal(payload.model, "glm-4.7-flashx");
  assert.equal(payload.stream, true);
  assert.equal(payload.max_tokens, 200);
  assert.deepEqual(payload.thinking, { type: "disabled" });
  assert.equal(response.headers.get("content-type"), "text/event-stream");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(await response.text(), event);
});

test("keeps the environment model override", async () => {
  let payload;
  await handleRequest(request(), {
    env: { ...environment(), ZHIPU_MODEL: "custom-model" },
    fetchImpl: async (_url, options) => {
      payload = JSON.parse(options.body);
      return new Response("data: [DONE]\n\n", { status: 200 });
    },
  });

  assert.equal(payload.model, "custom-model");
});

test("diagnostics contain only GLM metadata and no content or credentials", async () => {
  const entries = [];
  const response = await handleRequest(request(), {
    env: environment(),
    log: (entry) => entries.push(entry),
    fetchImpl: async () => new Response("upstream unavailable", { status: 503 }),
  });

  assert.equal(response.status, 503);
  assert.deepEqual(entries.map((entry) => [entry.event, entry.status]), [
    ["zhipu_response", 503],
  ]);
  const serialized = JSON.stringify(entries);
  assert.equal(serialized.includes("你好"), false);
  assert.equal(serialized.includes("test-only-key"), false);
});

test("logs only numeric Zhipu business code on HTTP failure", async () => {
  const entries = [];
  const response = await handleRequest(request(), {
    env: environment(),
    log: (entry) => entries.push(entry),
    fetchImpl: async () => Response.json(
      { error: { code: "1304", message: "private upstream text" } },
      { status: 429 },
    ),
  });

  assert.equal(response.status, 503);
  assert.equal(entries.at(-1).upstreamCode, 1304);
  assert.equal(JSON.stringify(entries).includes("private upstream text"), false);
});

test("maps GLM transport and HTTP failures to stable unavailable response", async () => {
  const transportFailure = await handleRequest(request(), {
    env: environment(),
    fetchImpl: async () => { throw new Error("down"); },
  });
  assert.equal(transportFailure.status, 503);

  const httpFailure = await handleRequest(request(), {
    env: environment(),
    fetchImpl: async () => new Response("no", { status: 500 }),
  });
  assert.equal(httpFailure.status, 503);
});

test("reports only the missing GLM key", async () => {
  const entries = [];
  const response = await handleRequest(request(), {
    env: {},
    log: (entry) => entries.push(entry),
    fetchImpl: async () => { throw new Error("unexpected"); },
  });

  assert.equal(response.status, 503);
  assert.deepEqual(entries, [{
    event: "configuration_missing",
    missing: ["ZHIPU_API_KEY"],
  }]);
});

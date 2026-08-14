import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

import worker, { QuotaCounter } from "../src/index.js";

function requestFor(
  installId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  requestId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
) {
  return new Request("https://chat.petpet.example/v1/chat", {
    method: "POST",
    headers: { "content-type": "application/json", "CF-Connecting-IP": "203.0.113.7" },
    body: JSON.stringify({
      request_id: requestId,
      install_id: installId,
      messages: [{ role: "user", content: "你好" }],
    }),
  });
}

function fakeEnv(values = {}) {
  const counter = values.counter || {
    async fetch() { return new Response(null, { status: 204 }); },
  };
  return {
    OPENROUTER_API_KEY: "test-only-secret",
    ZHIPU_API_KEY: "test-only-zhipu-secret",
    QUOTA_SHARED_SECRET: "test-only-quota-secret",
    CHAT_QUOTA: {
      idFromName(name) { return name; },
      get() { return counter; },
    },
    ...Object.fromEntries(Object.entries(values).filter(([key]) => key !== "counter")),
  };
}

test("GLM-4.7-Flash failure falls back to OpenRouter free", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    if (calls.length === 1) return new Response("upstream failed", { status: 503 });
    return new Response("data: [DONE]\n\n", {
      headers: { "content-type": "text/event-stream" },
    });
  };
  try {
    const response = await worker.fetch(requestFor(), fakeEnv());
    assert.equal(response.status, 200);
    assert.equal(calls.length, 2);
    assert.equal(calls[0].url, "https://open.bigmodel.cn/api/paas/v4/chat/completions");
    assert.equal(calls[1].url, "https://openrouter.ai/api/v1/chat/completions");
    const body = JSON.parse(calls[1].options.body);
    assert.equal(body.model, "openrouter/free");
    assert.equal(body.stream, true);
    assert.equal(body.max_tokens, 200);
    assert.deepEqual(body.reasoning, { effort: "none" });
    assert.equal(calls[1].options.headers.authorization, "Bearer test-only-secret");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("GLM-4.7-Flash without timely text falls back to OpenRouter free", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    if (calls.length === 1) {
      return new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(": ZHIPU PROCESSING\n\n"));
        },
      }), { headers: { "content-type": "text/event-stream" } });
    }
    return new Response(
      'data: {"model":"openrouter/free","choices":[{"delta":{"content":"快"}}]}\n\ndata: [DONE]\n\n',
      { headers: { "content-type": "text/event-stream" } },
    );
  };
  try {
    const response = await worker.fetch(requestFor(), fakeEnv({
      ZHIPU_FIRST_CONTENT_TIMEOUT_MS: "20",
    }));
    assert.equal(response.status, 200);
    assert.equal(calls.length, 2);
    assert.equal(calls[1].url, "https://openrouter.ai/api/v1/chat/completions");
    assert.match(await response.text(), /openrouter\/free/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("both providers failing returns the stable unavailable error", async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    throw new Error("provider down");
  };
  try {
    const response = await worker.fetch(requestFor(), fakeEnv());
    assert.equal(calls, 2);
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: "default_provider_unavailable" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

function transactionalStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  let queue = Promise.resolve();
  let alarm = null;
  return {
    data,
    async getAlarm() { return alarm; },
    async setAlarm(value) { alarm = value; },
    async deleteAll() { data.clear(); alarm = null; },
    transaction(callback) {
      const result = queue.then(() => callback({
        async get(key) { return data.get(key); },
        async put(key, value) { data.set(key, value); },
      }));
      queue = result.catch(() => {});
      return result;
    },
  };
}

test("invalid default chat request never calls upstream", async () => {
  const originalFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async () => { called = true; throw new Error("unexpected"); };
  try {
    const response = await worker.fetch(new Request("https://chat.petpet.example/v1/chat", {
      method: "POST", body: "{}",
    }), fakeEnv());
    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: "invalid_default_chat_request" });
    assert.equal(called, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("request without JSON content type is rejected before upstream", async () => {
  const originalFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async () => { called = true; throw new Error("unexpected"); };
  try {
    const request = new Request("https://chat.petpet.example/v1/chat", {
      method: "POST",
      headers: { "content-type": "text/plain" },
      body: JSON.stringify({
        install_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        messages: [{ role: "user", content: "hello" }],
      }),
    });
    const response = await worker.fetch(request, fakeEnv());
    assert.equal(response.status, 400);
    assert.equal(called, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("non-object messages return a stable validation error", async () => {
  const request = new Request("https://chat.petpet.example/v1/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      request_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      install_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      messages: [null],
    }),
  });

  const response = await worker.fetch(request, fakeEnv());

  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "invalid_default_chat_request" });
});

test("body size limit counts UTF-8 bytes", async () => {
  const request = new Request("https://chat.petpet.example/v1/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      request_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      install_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      messages: Array.from(
        { length: 8 },
        () => ({ role: "user", content: "你".repeat(1500) }),
      ),
    }),
  });

  const response = await worker.fetch(request, fakeEnv());

  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "invalid_default_chat_request" });
});

test("system prompt accepts 8000 characters but rejects 8001", async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response('data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n', {
      headers: { "content-type": "text/event-stream" },
    });
  };
  try {
    const accepted = requestFor();
    const acceptedBody = await accepted.json();
    acceptedBody.messages = [{ role: "system", content: "a".repeat(8000) }];
    const acceptedResponse = await worker.fetch(new Request(accepted.url, {
      method: "POST",
      headers: accepted.headers,
      body: JSON.stringify(acceptedBody),
    }), fakeEnv());
    assert.equal(acceptedResponse.status, 200);

    acceptedBody.messages[0].content += "a";
    const rejectedResponse = await worker.fetch(new Request(accepted.url, {
      method: "POST",
      headers: accepted.headers,
      body: JSON.stringify(acceptedBody),
    }), fakeEnv());
    assert.equal(rejectedResponse.status, 400);
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("ordinary turns still reject content above 1600 characters", async () => {
  const request = requestFor();
  const body = await request.json();
  body.messages = [{ role: "user", content: "a".repeat(1601) }];

  const response = await worker.fetch(new Request(request.url, {
    method: "POST",
    headers: request.headers,
    body: JSON.stringify(body),
  }), fakeEnv());

  assert.equal(response.status, 400);
});

test("accepts twelve messages but rejects thirteen", async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response(
      'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n', {
        headers: { "content-type": "text/event-stream" },
      },
    );
  };
  try {
    const accepted = requestFor();
    const body = await accepted.json();
    body.messages = Array.from(
      { length: 12 },
      (_, index) => ({ role: index % 2 ? "assistant" : "user", content: `turn-${index}` }),
    );
    const acceptedResponse = await worker.fetch(new Request(accepted.url, {
      method: "POST", headers: accepted.headers, body: JSON.stringify(body),
    }), fakeEnv());
    assert.equal(acceptedResponse.status, 200);

    body.messages.push({ role: "user", content: "too many" });
    const rejectedResponse = await worker.fetch(new Request(accepted.url, {
      method: "POST", headers: accepted.headers, body: JSON.stringify(body),
    }), fakeEnv());
    assert.equal(rejectedResponse.status, 400);
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("missing provider secret never invokes upstream", async () => {
  const originalFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async () => { called = true; throw new Error("unexpected"); };
  const env = fakeEnv();
  delete env.OPENROUTER_API_KEY;
  delete env.ZHIPU_API_KEY;
  try {
    const response = await worker.fetch(requestFor(), env);
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: "default_provider_unavailable" });
    assert.equal(called, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("forwards bounded messages with GLM-4.7-Flash and token limit", async () => {
  const originalFetch = globalThis.fetch;
  let upstream;
  globalThis.fetch = async (url, options) => {
    upstream = { url, options };
    return new Response('data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n', {
      headers: { "content-type": "text/event-stream" },
    });
  };
  try {
    const response = await worker.fetch(requestFor(), fakeEnv());
    const body = JSON.parse(upstream.options.body);
    assert.equal(upstream.url, "https://open.bigmodel.cn/api/paas/v4/chat/completions");
    assert.equal(body.model, "glm-4.7-flash");
    assert.equal(body.max_tokens, 200);
    assert.equal(body.stream, true);
    assert.deepEqual(body.thinking, { type: "disabled" });
    assert.equal("reasoning" in body, false);
    assert.equal(upstream.options.headers.authorization, "Bearer test-only-zhipu-secret");
    assert.equal(response.headers.get("content-type"), "text/event-stream");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("quota exhaustion prevents an upstream request", async () => {
  const originalFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async () => { called = true; throw new Error("unexpected"); };
  const env = fakeEnv({
    counter: { async fetch() { return new Response(null, { status: 429 }); } },
  });
  try {
    const response = await worker.fetch(requestFor(), env);
    assert.equal(response.status, 429);
    assert.deepEqual(await response.json(), { error: "default_quota_exhausted" });
    assert.equal(called, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("quota service failures return a stable provider unavailable error", async () => {
  const cases = [
    { async fetch() { throw new Error("durable object unavailable"); } },
    { async fetch() { return new Response(null, { status: 500 }); } },
  ];
  for (const counter of cases) {
    const response = await worker.fetch(requestFor(), fakeEnv({ counter }));
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: "default_provider_unavailable" });
  }
});

test("durable quota counter atomically admits only the daily limit", async () => {
  const storage = transactionalStorage();
  const counter = new QuotaCounter({ storage });
  const requests = Array.from({ length: 25 }, () => counter.fetch(new Request(
    "https://quota.petpet.internal/consume",
    {
      method: "POST",
      body: JSON.stringify({
        requestKey: `request:${crypto.randomUUID()}`,
        installKey: "install:a",
        ipKey: "ip:b",
      }),
    },
  )));

  const responses = await Promise.all(requests);

  assert.equal(responses.filter((response) => response.status === 204).length, 20);
  assert.equal(responses.filter((response) => response.status === 429).length, 5);
  assert.equal(storage.data.get("install:a"), 20);
  assert.equal(storage.data.get("ip:b"), 20);
});

test("durable quota counter schedules and performs daily cleanup", async () => {
  const storage = transactionalStorage();
  const counter = new QuotaCounter({ storage });
  const before = Date.now();

  const response = await counter.fetch(new Request(
    "https://quota.petpet.internal/consume",
    {
      method: "POST",
      body: JSON.stringify({
        requestKey: "request:a",
        installKey: "install:a",
        ipKey: "ip:b",
      }),
    },
  ));

  assert.equal(response.status, 204);
  assert.ok(await storage.getAlarm() > before);
  await counter.alarm();
  assert.equal(storage.data.size, 0);
  assert.equal(await storage.getAlarm(), null);
});

test("durable quota counter charges the same request identity only once", async () => {
  const storage = transactionalStorage();
  const counter = new QuotaCounter({ storage });
  const body = JSON.stringify({
    requestKey: "request:same",
    installKey: "install:a",
    ipKey: "ip:b",
  });

  const first = await counter.fetch(new Request(
    "https://quota.petpet.internal/consume", { method: "POST", body },
  ));
  const repeated = await counter.fetch(new Request(
    "https://quota.petpet.internal/consume", { method: "POST", body },
  ));

  assert.equal(first.status, 204);
  assert.equal(repeated.status, 204);
  assert.equal(storage.data.get("install:a"), 1);
  assert.equal(storage.data.get("ip:b"), 1);
});

test("durable quota retry may change route IP without a second charge", async () => {
  const storage = transactionalStorage();
  const counter = new QuotaCounter({ storage });
  const first = JSON.stringify({
    requestKey: "request:same", installKey: "install:a", ipKey: "ip:aliyun",
  });
  const fallback = JSON.stringify({
    requestKey: "request:same", installKey: "install:a", ipKey: "ip:cloudflare",
  });

  assert.equal((await counter.fetch(new Request(
    "https://quota.petpet.internal/consume", { method: "POST", body: first },
  ))).status, 204);
  assert.equal((await counter.fetch(new Request(
    "https://quota.petpet.internal/consume", { method: "POST", body: fallback },
  ))).status, 204);
  assert.equal(storage.data.get("install:a"), 1);
  assert.equal(storage.data.get("ip:aliyun"), 1);
  assert.equal(storage.data.has("ip:cloudflare"), false);
});

test("durable quota counter rejects request identity reuse by another subject", async () => {
  const storage = transactionalStorage();
  const counter = new QuotaCounter({ storage });
  const first = JSON.stringify({
    requestKey: "request:same", installKey: "install:a", ipKey: "ip:b",
  });
  const changed = JSON.stringify({
    requestKey: "request:same", installKey: "install:other", ipKey: "ip:b",
  });

  assert.equal((await counter.fetch(new Request(
    "https://quota.petpet.internal/consume", { method: "POST", body: first },
  ))).status, 204);
  assert.equal((await counter.fetch(new Request(
    "https://quota.petpet.internal/consume", { method: "POST", body: changed },
  ))).status, 409);
  assert.equal(storage.data.get("install:a"), 1);
  assert.equal(storage.data.has("install:other"), false);
});

test("internal quota endpoint requires its server secret and never calls a model", async () => {
  const originalFetch = globalThis.fetch;
  let upstreamCalls = 0;
  globalThis.fetch = async () => { upstreamCalls += 1; throw new Error("unexpected"); };
  const payload = {
    request_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    install_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    source_ip: "203.0.113.9",
  };
  try {
    const unauthorized = await worker.fetch(new Request(
      "https://chat.petpet.example/internal/quota/consume",
      { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) },
    ), fakeEnv());
    assert.equal(unauthorized.status, 401);

    const authorized = await worker.fetch(new Request(
      "https://chat.petpet.example/internal/quota/consume",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: "Bearer test-only-quota-secret",
        },
        body: JSON.stringify(payload),
      },
    ), fakeEnv());
    assert.equal(authorized.status, 204);
    assert.equal(upstreamCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("public chat remains compatible with clients that have no request id", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(
    'data: {"choices":[{"delta":{"content":"汪"}}]}\n\ndata: [DONE]\n\n',
    { headers: { "content-type": "text/event-stream" } },
  );
  try {
    const legacy = requestFor();
    const body = await legacy.json();
    delete body.request_id;
    const response = await worker.fetch(new Request(legacy.url, {
      method: "POST",
      headers: { "content-type": "application/json", "CF-Connecting-IP": "127.0.0.1" },
      body: JSON.stringify(body),
    }), fakeEnv());
    assert.equal(response.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("deployment examples contain bindings but no provider credential", async () => {
  const [config, example] = await Promise.all([
    readFile(new URL("../wrangler.toml", import.meta.url), "utf8"),
    readFile(new URL("../.dev.vars.example", import.meta.url), "utf8"),
  ]);
  assert.match(config, /name = "CHAT_QUOTA"/);
  assert.match(config, /class_name = "QuotaCounter"/);
  assert.match(config, /\[exports\.QuotaCounter\]/);
  assert.match(config, /^type = "durable-object"$/m);
  assert.match(config, /^storage = "sqlite"$/m);
  assert.match(config, /^workers_dev = true$/m);
  assert.match(config, /^preview_urls = false$/m);
  assert.doesNotMatch(config, /\[\[kv_namespaces\]\]/);
  assert.match(config, /^OPENROUTER_MODEL = "openrouter\/free"$/m);
  assert.match(config, /^OPENROUTER_ENDPOINT = "https:\/\/openrouter\.ai\/api\/v1\/chat\/completions"$/m);
  assert.match(example, /^OPENROUTER_API_KEY=$/m);
  assert.match(example, /^ZHIPU_API_KEY=$/m);
  assert.match(example, /^QUOTA_SHARED_SECRET=$/m);
  assert.doesNotMatch(config, /OPENCODE_/);
  assert.doesNotMatch(example, /sk-[A-Za-z0-9]/);
});

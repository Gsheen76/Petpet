const DAILY_LIMIT = 20;
const MAX_MESSAGES = 12;
const MAX_SYSTEM_CONTENT_CHARS = 8000;
const MAX_TURN_CONTENT_CHARS = 1600;
const MAX_BODY_BYTES = 32768;
const DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions";
const DEFAULT_MODEL = "openrouter/free";
const ZHIPU_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions";
const ZHIPU_MODEL = "glm-4.7-flash";
const ZHIPU_FIRST_CONTENT_TIMEOUT_MS = 5000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function error(code, status) {
  return Response.json({ error: code }, { status });
}

function validMessages(messages) {
  return Array.isArray(messages) && messages.length > 0 && messages.length <= MAX_MESSAGES
    && messages.every((message) => message && typeof message === "object"
      && ["system", "user", "assistant"].includes(message.role)
      && typeof message.content === "string"
      && message.content.length > 0
      && message.content.length <= (
        message.role === "system" ? MAX_SYSTEM_CONTENT_CHARS : MAX_TURN_CONTENT_CHARS
      ));
}

async function quotaHash(subject, value) {
  const input = new TextEncoder().encode(`${subject}:${value}`);
  const digest = await crypto.subtle.digest("SHA-256", input);
  const hash = [...new Uint8Array(digest)].map((item) => item.toString(16).padStart(2, "0")).join("");
  return `${subject}:${hash}`;
}

async function consumeQuota(namespace, requestId, installId, ip) {
  const day = new Date().toISOString().slice(0, 10);
  const stub = namespace.get(namespace.idFromName(day));
  const [requestKey, installKey, ipKey] = await Promise.all([
    quotaHash("request", requestId),
    quotaHash("install", installId),
    quotaHash("ip", ip),
  ]);
  const response = await stub.fetch("https://quota.petpet.internal/consume", {
    method: "POST",
    body: JSON.stringify({ requestKey, installKey, ipKey }),
  });
  if (response.status === 204) return "allowed";
  if (response.status === 429) return "exhausted";
  if (response.status === 409) return "identity_mismatch";
  throw new Error(`quota service returned ${response.status}`);
}

function validSourceIp(value) {
  return typeof value === "string" && value.length > 0 && value.length <= 64
    && !/[\x00-\x20\x7f]/.test(value);
}

function utcTomorrowTimestamp() {
  const now = new Date();
  return Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 5);
}

function eventContainsText(event) {
  const dataLine = event.split("\n").find((line) => line.startsWith("data:"));
  if (!dataLine) return false;
  const data = dataLine.slice(5).trim();
  if (!data || data === "[DONE]") return false;
  try {
    const parsed = JSON.parse(data);
    return (parsed.choices || []).some(
      (choice) => typeof choice?.delta?.content === "string" && choice.delta.content.length > 0,
    );
  } catch {
    return false;
  }
}

async function requireTimelyText(response, timeoutMs) {
  const reader = response.body.getReader();
  const chunks = [];
  const decoder = new TextDecoder();
  let pending = "";
  let timer;
  const deadline = new Promise((resolve) => {
    timer = setTimeout(() => resolve({ timeout: true }), timeoutMs);
  });
  try {
    while (true) {
      const result = await Promise.race([reader.read(), deadline]);
      if (result.timeout) {
        reader.cancel("first content timeout").catch(() => {});
        return null;
      }
      if (result.done) return null;
      chunks.push(result.value);
      pending += decoder.decode(result.value, { stream: true }).replaceAll("\r\n", "\n");
      const events = pending.split("\n\n");
      pending = events.pop() || "";
      if (events.some(eventContainsText)) {
        const body = new ReadableStream({
          start(controller) {
            for (const chunk of chunks) controller.enqueue(chunk);
            const pump = () => reader.read().then(({ done, value }) => {
              if (done) controller.close();
              else { controller.enqueue(value); return pump(); }
            }).catch((error) => controller.error(error));
            return pump();
          },
          cancel(reason) { return reader.cancel(reason); },
        });
        return new Response(body, { status: response.status, headers: response.headers });
      }
    }
  } finally {
    clearTimeout(timer);
  }
}

async function requestProvider(url, apiKey, payload, firstContentTimeoutMs = null) {
  if (!apiKey) return null;
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "authorization": `Bearer ${apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok || !response.body) return null;
    return firstContentTimeoutMs === null
      ? response
      : await requireTimelyText(response, firstContentTimeoutMs);
  } catch {
    return null;
  }
}

export class QuotaCounter {
  constructor(ctx) {
    this.ctx = ctx;
  }

  async fetch(request) {
    if (request.method !== "POST") return new Response(null, { status: 405 });
    let body;
    try { body = await request.json(); } catch { return new Response(null, { status: 400 }); }
    if (!body || typeof body.requestKey !== "string"
      || typeof body.installKey !== "string" || typeof body.ipKey !== "string") {
      return new Response(null, { status: 400 });
    }
    if (await this.ctx.storage.getAlarm() === null) {
      await this.ctx.storage.setAlarm(utcTomorrowTimestamp());
    }
    const result = await this.ctx.storage.transaction(async (transaction) => {
      const existingInstallKey = await transaction.get(body.requestKey);
      if (existingInstallKey !== undefined) {
        return existingInstallKey === body.installKey ? "existing" : "identity_mismatch";
      }
      const installCount = Number(await transaction.get(body.installKey) || 0);
      const ipCount = Number(await transaction.get(body.ipKey) || 0);
      if (installCount >= DAILY_LIMIT || ipCount >= DAILY_LIMIT) return "exhausted";
      await transaction.put(body.installKey, installCount + 1);
      await transaction.put(body.ipKey, ipCount + 1);
      await transaction.put(body.requestKey, body.installKey);
      return "new";
    });
    if (result === "identity_mismatch") return new Response(null, { status: 409 });
    return new Response(null, { status: result === "exhausted" ? 429 : 204 });
  }

  async alarm() {
    await this.ctx.storage.deleteAll();
  }
}

export default {
  async fetch(request, env) {
    const pathname = new URL(request.url).pathname;
    const isChatRequest = request.method === "POST" && pathname === "/v1/chat";
    const isInternalQuotaRequest = request.method === "POST"
      && pathname === "/internal/quota/consume";
    if (!isChatRequest && !isInternalQuotaRequest) {
      return error("invalid_default_chat_request", 400);
    }
    if (isInternalQuotaRequest) {
      if (!env.QUOTA_SHARED_SECRET
        || request.headers.get("authorization") !== `Bearer ${env.QUOTA_SHARED_SECRET}`) {
        return error("invalid_quota_authorization", 401);
      }
      const contentType = request.headers.get("content-type") || "";
      if (!contentType.toLowerCase().startsWith("application/json")) {
        return error("invalid_quota_request", 400);
      }
      const raw = await request.text();
      if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
        return error("invalid_quota_request", 400);
      }
      let body;
      try { body = JSON.parse(raw); } catch { return error("invalid_quota_request", 400); }
      const keys = body && typeof body === "object" ? Object.keys(body).sort() : [];
      if (keys.join(",") !== "install_id,request_id,source_ip"
        || !UUID.test(body.request_id || "") || !UUID.test(body.install_id || "")
        || !validSourceIp(body.source_ip) || !env.CHAT_QUOTA) {
        return error("invalid_quota_request", 400);
      }
      let quotaResult;
      try {
        quotaResult = await consumeQuota(
          env.CHAT_QUOTA, body.request_id, body.install_id, body.source_ip,
        );
      } catch {
        return error("default_provider_unavailable", 503);
      }
      if (quotaResult === "exhausted") return error("default_quota_exhausted", 429);
      if (quotaResult === "identity_mismatch") return error("request_identity_mismatch", 409);
      return new Response(null, { status: 204 });
    }
    const contentType = request.headers.get("content-type") || "";
    if (!contentType.toLowerCase().startsWith("application/json")) {
      return error("invalid_default_chat_request", 400);
    }
    const raw = await request.text();
    if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
      return error("invalid_default_chat_request", 400);
    }
    let body;
    try { body = JSON.parse(raw); } catch { return error("invalid_default_chat_request", 400); }
    if (!UUID.test(body.install_id || "")
      || (body.request_id !== undefined && !UUID.test(body.request_id || ""))
      || !validMessages(body.messages)) {
      return error("invalid_default_chat_request", 400);
    }
    if ((!env.OPENROUTER_API_KEY && !env.ZHIPU_API_KEY) || !env.CHAT_QUOTA) {
      return error("default_provider_unavailable", 503);
    }
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    let quotaResult;
    try {
      quotaResult = await consumeQuota(
        env.CHAT_QUOTA, body.request_id || crypto.randomUUID(), body.install_id, ip,
      );
    } catch {
      return error("default_provider_unavailable", 503);
    }
    if (quotaResult === "exhausted") {
      return error("default_quota_exhausted", 429);
    }
    if (quotaResult === "identity_mismatch") return error("request_identity_mismatch", 409);
    const zhipu = await requestProvider(
      env.ZHIPU_ENDPOINT || ZHIPU_ENDPOINT,
      env.ZHIPU_API_KEY,
      {
        model: env.ZHIPU_MODEL || ZHIPU_MODEL,
        messages: body.messages,
        stream: true,
        max_tokens: 200,
        thinking: { type: "disabled" },
      },
      Number(env.ZHIPU_FIRST_CONTENT_TIMEOUT_MS || ZHIPU_FIRST_CONTENT_TIMEOUT_MS),
    );
    const upstream = zhipu || await requestProvider(
      env.OPENROUTER_ENDPOINT || DEFAULT_ENDPOINT,
      env.OPENROUTER_API_KEY,
      {
        model: env.OPENROUTER_MODEL || DEFAULT_MODEL,
        messages: body.messages,
        stream: true,
        max_tokens: 200,
        reasoning: { effort: "none" },
      },
    );
    if (!upstream) return error("default_provider_unavailable", 503);
    return new Response(upstream.body, {
      headers: { "content-type": "text/event-stream", "cache-control": "no-store" },
    });
  },
};

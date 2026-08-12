const DAILY_LIMIT = 20;
const MAX_MESSAGES = 7;
const MAX_SYSTEM_CONTENT_CHARS = 4000;
const MAX_TURN_CONTENT_CHARS = 1200;
const MAX_BODY_BYTES = 16384;
const DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions";
const DEFAULT_MODEL = "openrouter/free";
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

async function consumeQuota(namespace, installId, ip) {
  const day = new Date().toISOString().slice(0, 10);
  const stub = namespace.get(namespace.idFromName(day));
  const [installKey, ipKey] = await Promise.all([
    quotaHash("install", installId),
    quotaHash("ip", ip),
  ]);
  const response = await stub.fetch("https://quota.petpet.internal/consume", {
    method: "POST",
    body: JSON.stringify({ installKey, ipKey }),
  });
  if (response.status === 204) return true;
  if (response.status === 429) return false;
  throw new Error(`quota service returned ${response.status}`);
}

function utcTomorrowTimestamp() {
  const now = new Date();
  return Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 5);
}

export class QuotaCounter {
  constructor(ctx) {
    this.ctx = ctx;
  }

  async fetch(request) {
    if (request.method !== "POST") return new Response(null, { status: 405 });
    let body;
    try { body = await request.json(); } catch { return new Response(null, { status: 400 }); }
    if (!body || typeof body.installKey !== "string" || typeof body.ipKey !== "string") {
      return new Response(null, { status: 400 });
    }
    if (await this.ctx.storage.getAlarm() === null) {
      await this.ctx.storage.setAlarm(utcTomorrowTimestamp());
    }
    const allowed = await this.ctx.storage.transaction(async (transaction) => {
      const installCount = Number(await transaction.get(body.installKey) || 0);
      const ipCount = Number(await transaction.get(body.ipKey) || 0);
      if (installCount >= DAILY_LIMIT || ipCount >= DAILY_LIMIT) return false;
      await transaction.put(body.installKey, installCount + 1);
      await transaction.put(body.ipKey, ipCount + 1);
      return true;
    });
    return new Response(null, { status: allowed ? 204 : 429 });
  }

  async alarm() {
    await this.ctx.storage.deleteAll();
  }
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST" || new URL(request.url).pathname !== "/v1/chat") {
      return error("invalid_default_chat_request", 400);
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
    if (!UUID.test(body.install_id || "") || !validMessages(body.messages)) {
      return error("invalid_default_chat_request", 400);
    }
    if (!env.OPENROUTER_API_KEY || !env.CHAT_QUOTA) {
      return error("default_provider_unavailable", 503);
    }
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    let quotaAllowed;
    try {
      quotaAllowed = await consumeQuota(env.CHAT_QUOTA, body.install_id, ip);
    } catch {
      return error("default_provider_unavailable", 503);
    }
    if (!quotaAllowed) {
      return error("default_quota_exhausted", 429);
    }
    try {
      const upstream = await fetch(env.OPENROUTER_ENDPOINT || DEFAULT_ENDPOINT, {
        method: "POST",
        headers: {
          "authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
          "content-type": "application/json",
        },
        body: JSON.stringify({
          model: env.OPENROUTER_MODEL || DEFAULT_MODEL,
          messages: body.messages,
          stream: true,
          max_tokens: 200,
          reasoning: { effort: "none" },
        }),
      });
      if (!upstream.ok || !upstream.body) return error("default_provider_unavailable", 503);
      return new Response(upstream.body, {
        headers: { "content-type": "text/event-stream", "cache-control": "no-store" },
      });
    } catch {
      return error("default_provider_unavailable", 503);
    }
  },
};

import http from "node:http";
import { fileURLToPath } from "node:url";

const MAX_MESSAGES = 12;
const MAX_SYSTEM_CONTENT_CHARS = 8000;
const MAX_TURN_CONTENT_CHARS = 1600;
const MAX_BODY_BYTES = 32768;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DEFAULT_ZHIPU_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions";

function error(code, status) {
  return Response.json({ error: code }, { status });
}

function validMessages(messages) {
  return Array.isArray(messages) && messages.length > 0 && messages.length <= MAX_MESSAGES
    && messages.every((message) => message && typeof message === "object"
      && ["system", "user", "assistant"].includes(message.role)
      && typeof message.content === "string" && message.content.length > 0
      && message.content.length <= (
        message.role === "system" ? MAX_SYSTEM_CONTENT_CHARS : MAX_TURN_CONTENT_CHARS
      ));
}

export async function handleRequest(request, {
  env = process.env,
  fetchImpl = fetch,
  sourceIp = "unknown",
  log = (entry) => console.log(JSON.stringify(entry)),
} = {}) {
  if (request.method !== "POST" || new URL(request.url).pathname !== "/v1/chat") {
    return error("invalid_default_chat_request", 400);
  }
  if (!(request.headers.get("content-type") || "").toLowerCase().startsWith("application/json")) {
    return error("invalid_default_chat_request", 400);
  }
  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
    return error("invalid_default_chat_request", 400);
  }
  let body;
  try { body = JSON.parse(raw); } catch { return error("invalid_default_chat_request", 400); }
  if (!UUID.test(body?.request_id || "") || !UUID.test(body?.install_id || "")
    || !validMessages(body?.messages)) {
    return error("invalid_default_chat_request", 400);
  }
  if (!env.ZHIPU_API_KEY) {
    log({
      event: "configuration_missing",
      missing: [
        !env.ZHIPU_API_KEY && "ZHIPU_API_KEY",
      ].filter(Boolean),
    });
    return error("default_provider_unavailable", 503);
  }

  let upstream;
  const zhipuStarted = Date.now();
  try {
    upstream = await fetchImpl(env.ZHIPU_ENDPOINT || DEFAULT_ZHIPU_ENDPOINT, {
      method: "POST",
      headers: {
        authorization: `Bearer ${env.ZHIPU_API_KEY}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: env.ZHIPU_MODEL || "glm-4.7-flashx",
        messages: body.messages,
        stream: true,
        max_tokens: 200,
        thinking: { type: "disabled" },
      }),
    });
  } catch (caught) {
    log({
      event: "zhipu_exception",
      exceptionType: caught?.constructor?.name || "Error",
      causeCode: typeof caught?.cause?.code === "string"
        ? caught.cause.code.slice(0, 64) : null,
      elapsedMs: Date.now() - zhipuStarted,
    });
    return error("default_provider_unavailable", 503);
  }
  if (!upstream.ok) {
    let upstreamPayload = {};
    try { upstreamPayload = await upstream.json(); } catch { /* metadata only */ }
    const rawCode = upstreamPayload?.error?.code ?? upstreamPayload?.code;
    const numericCode = Number(rawCode);
    log({
      event: "zhipu_response",
      status: upstream.status,
      upstreamCode: rawCode != null && Number.isFinite(numericCode) ? numericCode : null,
      elapsedMs: Date.now() - zhipuStarted,
    });
    return error("default_provider_unavailable", 503);
  }
  log({ event: "zhipu_response", status: upstream.status, elapsedMs: Date.now() - zhipuStarted });
  if (!upstream.body) return error("default_provider_unavailable", 503);
  return new Response(upstream.body, {
    status: 200,
    headers: { "content-type": "text/event-stream", "cache-control": "no-store" },
  });
}

function sourceAddress(request) {
  const forwarded = request.headers["x-forwarded-for"];
  const first = Array.isArray(forwarded) ? forwarded[0] : String(forwarded || "").split(",")[0];
  return first.trim() || request.socket.remoteAddress || "unknown";
}

async function nodeRequestToResponse(request, response) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const body = chunks.length ? Buffer.concat(chunks) : undefined;
  const requestOptions = {
    method: request.method,
    headers: request.headers,
    body,
  };
  if (body) requestOptions.duplex = "half";
  const webRequest = new Request(
    `http://localhost${request.url || "/"}`, requestOptions,
  );
  const webResponse = await handleRequest(webRequest, { sourceIp: sourceAddress(request) });
  response.writeHead(webResponse.status, Object.fromEntries(webResponse.headers.entries()));
  if (!webResponse.body) return response.end();
  const reader = webResponse.body.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    response.write(Buffer.from(value));
  }
  response.end();
}

export function startServer(port = Number(process.env.PORT || 9000)) {
  return http.createServer((request, response) => {
    nodeRequestToResponse(request, response).catch(() => {
      if (!response.headersSent) response.writeHead(500, { "content-type": "application/json" });
      response.end(JSON.stringify({ error: "default_provider_unavailable" }));
    });
  }).listen(port, "0.0.0.0");
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) startServer();

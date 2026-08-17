"""Streaming HTTP transports for Petpet chat providers."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from typing import Any

import requests


DEFAULT_PROXY_MAX_SYSTEM_CHARS = 8000
DEFAULT_PROXY_MAX_TURN_CHARS = 1600
DEFAULT_PROXY_MAX_BODY_BYTES = 32768
DEFAULT_PROXY_MAX_MESSAGES = 12


def bound_default_proxy_content(
    content: Any,
    role: str = "user",
    max_chars: int | None = None,
) -> str:
    text = str(content or "")
    limit = max_chars if max_chars is not None else (
        DEFAULT_PROXY_MAX_SYSTEM_CHARS
        if role == "system"
        else DEFAULT_PROXY_MAX_TURN_CHARS
    )
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    edge = (limit - 1) // 2
    return text[:edge] + "…" + text[-edge:]


def default_proxy_payload(
    request_id: str, install_id: str, messages: Sequence[Mapping[str, Any]]
) -> bytes:
    return json.dumps(
        {"request_id": request_id, "install_id": install_id, "messages": messages},
        ensure_ascii=False,
    ).encode("utf-8")


def fit_default_proxy_payload(
    request_id: str,
    install_id: str,
    messages: Sequence[Mapping[str, Any]],
    *,
    max_body_bytes: int = DEFAULT_PROXY_MAX_BODY_BYTES,
) -> bytes:
    """Fit UTF-8 JSON under the public proxy cap, preserving both ends."""
    fitted = [dict(message) for message in messages]
    while len(fitted) > 2 and len(default_proxy_payload(request_id, install_id, fitted)) > max_body_bytes:
        del fitted[1]
    for index in (0, len(fitted) - 1):
        if len(default_proxy_payload(request_id, install_id, fitted)) <= max_body_bytes:
            break
        original = str(fitted[index].get("content", ""))
        low, high = 1, len(original)
        while low < high:
            middle = (low + high + 1) // 2
            fitted[index]["content"] = bound_default_proxy_content(
                original, str(fitted[index].get("role", "user")), middle
            )
            if len(default_proxy_payload(request_id, install_id, fitted)) <= max_body_bytes:
                low = middle
            else:
                high = middle - 1
        fitted[index]["content"] = bound_default_proxy_content(
            original, str(fitted[index].get("role", "user")), low
        )
    return default_proxy_payload(request_id, install_id, fitted)


def default_proxy_stream(
    primary_endpoint: str,
    fallback_endpoint: str,
    messages: Sequence[Mapping[str, Any]],
    timeout: int | float,
    *,
    install_id: str,
    quota_available: Callable[[], bool],
    record_quota_success: Callable[[str], bool],
    log_diagnostic: Callable[..., None],
    requests_module=requests,
    getproxies: Callable[[], Mapping[str, str]] = urllib.request.getproxies,
    request_id: str | None = None,
    max_messages: int = DEFAULT_PROXY_MAX_MESSAGES,
    max_body_bytes: int = DEFAULT_PROXY_MAX_BODY_BYTES,
) -> Iterator[tuple[str, str]]:
    started_at = time.perf_counter()
    selected = [messages[0], *messages[1:][-(max_messages - 1):]]
    selected = [
        {
            "role": message["role"],
            "content": bound_default_proxy_content(message["content"], message["role"]),
        }
        for message in selected
    ]
    request_id = request_id or str(uuid.uuid4())
    payload = fit_default_proxy_payload(
        request_id, install_id, selected, max_body_bytes=max_body_bytes
    )
    response = None
    direct_session = None
    route = None
    try:
        primary_allowed = bool(primary_endpoint and quota_available())
        route = "aliyun" if primary_allowed else "cloudflare"
        system_proxies = {
            scheme: value
            for scheme, value in getproxies().items()
            if scheme in {"http", "https"} and value
        }
        shared_kwargs = {
            "data": payload,
            "headers": {"Content-Type": "application/json"},
            "timeout": (min(6, timeout), timeout),
            "stream": True,
        }
        if primary_allowed:
            direct_session = requests_module.Session()
            direct_session.trust_env = False
            try:
                response = direct_session.post(primary_endpoint, **shared_kwargs)
                if response.status_code == 200:
                    record_quota_success(request_id)
            except (requests_module.ConnectTimeout, requests_module.ConnectionError) as exc:
                if not fallback_endpoint:
                    raise
                route = "cloudflare"
                log_diagnostic(
                    "default_route_fallback",
                    route="aliyun",
                    exception_type=type(exc).__name__,
                    stage="connect",
                )
        if response is None:
            fallback_kwargs = {**shared_kwargs, "proxies": system_proxies or None}
            try:
                response = requests_module.post(fallback_endpoint, **fallback_kwargs)
            except requests_module.ConnectTimeout:
                if not system_proxies:
                    raise
                log_diagnostic(
                    "default_proxy_retry",
                    route="cloudflare",
                    exception_type="ConnectTimeout",
                    stage="request",
                )
                response = requests_module.post(fallback_endpoint, **fallback_kwargs)
        if response.status_code >= 400:
            try:
                error_payload = response.json()
            except (ValueError, requests_module.RequestException):
                error_payload = {}
            error_code = error_payload.get("error") if isinstance(error_payload, dict) else None
            log_diagnostic(
                "default_proxy_http_error",
                status=response.status_code,
                exception_type="HTTPError",
                stage="request",
                route=route,
            )
            yield (
                "error",
                "default_quota_exhausted"
                if response.status_code == 429 or error_code == "default_quota_exhausted"
                else "default_provider_unavailable",
            )
            return
        full: list[str] = []
        reasoning_chars = 0
        saw_done = False
        model = None
        provider = None
        first_content_ms = None
        for line in response.iter_lines(chunk_size=1):
            if not line.startswith(b"data: "):
                continue
            data = line[6:].strip()
            if data == b"[DONE]":
                saw_done = True
                if full:
                    log_diagnostic(
                        "default_proxy_complete",
                        stage="stream",
                        response_content_chars=len("".join(full)),
                        response_reasoning_chars=reasoning_chars,
                        has_done=True,
                        model=model,
                        provider=provider,
                        route=route,
                        first_content_ms=first_content_ms,
                        total_ms=round((time.perf_counter() - started_at) * 1000),
                    )
                    yield ("done", "".join(full))
                else:
                    log_diagnostic(
                        "default_proxy_empty",
                        stage="stream",
                        response_content_chars=0,
                        response_reasoning_chars=reasoning_chars,
                        has_done=True,
                    )
                    yield ("error", "default_provider_unavailable")
                return
            try:
                event = json.loads(data)
                model = model or event.get("model")
                provider = provider or event.get("provider")
                delta = event["choices"][0]["delta"]
                chunk = delta.get("content", "")
                reasoning_chars += len(delta.get("reasoning", "") or "")
            except (ValueError, KeyError, IndexError, TypeError):
                chunk = ""
            if chunk:
                if first_content_ms is None:
                    first_content_ms = round((time.perf_counter() - started_at) * 1000)
                full.append(chunk)
                yield ("token", chunk)
        log_diagnostic(
            "default_proxy_stream_ended",
            stage="stream",
            response_content_chars=len("".join(full)),
            response_reasoning_chars=reasoning_chars,
            has_done=saw_done,
        )
        yield ("error", "default_provider_unavailable")
    except requests_module.RequestException as exc:
        log_diagnostic(
            "default_proxy_exception",
            exception_type=type(exc).__name__,
            stage="request",
            route=route,
        )
        yield ("error", "default_provider_unavailable")
    finally:
        try:
            if response is not None:
                response.close()
            if direct_session is not None:
                direct_session.close()
        except requests_module.RequestException:
            pass


def personal_stream(
    *,
    messages: Sequence[Mapping[str, Any]],
    key: str,
    selected_model: str,
    api_url: str,
    sign_token: Callable[[str], str],
    timeout: int | float,
    on_token: Callable[[str], None] | None = None,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
    request_factory: Callable[..., Any] = urllib.request.Request,
) -> Iterator[tuple[str, str]]:
    body = json.dumps({
        "model": selected_model,
        "messages": messages,
        "stream": True,
        "thinking": {"type": "disabled"},
        "temperature": 0.85,
        "max_tokens": 200,
    }).encode("utf-8")
    request = request_factory(
        api_url,
        data=body,
        headers={
            "Authorization": f"Bearer {sign_token(key)}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    try:
        response = urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        message = f"HTTP {error.code}"
        try:
            message += f": {error.read().decode('utf-8', errors='ignore')[:200]}"
        except Exception:
            pass
        yield ("error", "rate_limit" if error.code == 429 else message)
        return
    except Exception as error:
        yield ("error", str(error))
        return
    full: list[str] = []
    try:
        buffer = b""
        for chunk in iter(lambda: response.read(1024), b""):
            buffer += chunk
            while b"\n\n" in buffer:
                raw, buffer = buffer.split(b"\n\n", 1)
                for line in raw.split(b"\n"):
                    if not line.startswith(b"data:"):
                        continue
                    data = line[5:].strip()
                    if data == b"[DONE]":
                        yield ("done", "".join(full)) if full else ("error", "empty_response")
                        return
                    try:
                        value = json.loads(data)
                        delta = value.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    except Exception:
                        delta = ""
                    if delta:
                        full.append(delta)
                        if on_token:
                            on_token(delta)
                        yield ("token", delta)
        yield ("done", "".join(full)) if full else ("error", "empty_response")
    except Exception as error:
        yield ("error", str(error))


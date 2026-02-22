"""
Ollama HTTP client helpers.

Used endpoints:
- POST /api/embeddings  -> {"embedding": [float, ...]}
- POST /api/chat        -> {"message": {"role": "assistant", "content": "..."}}
"""

from __future__ import annotations

from typing import Any

import httpx

# Ollama failures are explicit and separable from other runtime errors.
class OllamaError(RuntimeError):
    pass


def _normalize_base_url(base_url: str) -> str:
    base_url = (base_url or "").strip()
    if not base_url:
        raise OllamaError("OLLAMA_BASE_URL is empty.")
    return base_url.rstrip("/")


async def embed_text(
    *,
    base_url: str,
    model: str,
    prompt: str,
    timeout_s: float = 60.0,
) -> list[float]:
    """
    Create an embedding for `prompt` using `model`.
    """
    base_url = _normalize_base_url(base_url)
    model = (model or "").strip()
    if not model:
        raise OllamaError("Embedding model name is empty.")

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout_s) as client:
        resp = await client.post(
            "/api/embeddings",
            json={"model": model, "prompt": prompt},
        )

    if resp.status_code != 200:
        # Avoid dumping huge bodies; include a small snippet.
        body = resp.text[:500]
        raise OllamaError(f"Ollama embeddings request failed: {resp.status_code} {body}")

    data: dict[str, Any] = resp.json()
    emb = data.get("embedding")
    if not isinstance(emb, list) or not emb:
        raise OllamaError("Ollama returned no embedding.")

    # Ensure we return floats.
    try:
        return [float(x) for x in emb]
    except Exception as e:
        raise OllamaError("Ollama returned a non-numeric embedding.") from e


async def chat_text(
    *,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout_s: float = 120.0,
    temperature: float | None = None,
) -> str:
    """
    Generate one assistant message from Ollama chat API.
    """
    return await chat_messages(
        base_url=base_url,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        timeout_s=timeout_s,
        temperature=temperature,
    )


async def chat_messages(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_s: float = 120.0,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> str:
    """
    Generate one assistant message from Ollama chat API using a message list.
    """
    base_url = _normalize_base_url(base_url)
    model = (model or "").strip()
    if not model:
        raise OllamaError("Generation model name is empty.")
    if not messages:
        raise OllamaError("Messages list is empty.")

    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
    options: dict[str, Any] = {}
    if temperature is not None:
        options["temperature"] = float(temperature)
    if max_output_tokens is not None:
        options["num_predict"] = int(max_output_tokens)
    if options:
        payload["options"] = options

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout_s) as client:
        resp = await client.post("/api/chat", json=payload)

    if resp.status_code != 200:
        body = resp.text[:500]
        raise OllamaError(f"Ollama chat request failed: {resp.status_code} {body}")

    data: dict[str, Any] = resp.json()
    message = data.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

    response_text = data.get("response")
    if isinstance(response_text, str) and response_text.strip():
        return response_text.strip()

    raise OllamaError("Ollama returned an empty chat response.")

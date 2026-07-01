from __future__ import annotations

from collections.abc import AsyncIterator
import re
from typing import Any

import httpx

from app.core.config import settings


def _headers(api_key: str = "") -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _provider_error(provider: str, exc: Exception) -> str:
    return f"{provider} provider unavailable: {type(exc).__name__}: {exc}"


async def model_health(timeout: float = 2.0) -> dict[str, Any]:
    chat = await _component_health("chat", settings.chat_provider, _chat_model(settings.chat_provider), timeout)
    embedding = await _component_health("embedding", settings.embedding_provider, _embedding_model(settings.embedding_provider), timeout)
    rerank = await _component_health("rerank", settings.rerank_provider, _rerank_model(settings.rerank_provider), timeout)
    components = [chat, embedding, rerank]
    configured = [item for item in components if item["configured"]]
    healthy = [item for item in configured if item["status"] in {"healthy", "configured"}]
    return {
        "status": "fallback" if not configured else "healthy" if len(healthy) == len(configured) else "degraded",
        "fallbackAvailable": True,
        "components": components,
    }


async def _component_health(kind: str, provider: str, model: str, timeout: float) -> dict[str, Any]:
    if not provider:
        return {"kind": kind, "provider": None, "model": model, "configured": False, "status": "fallback", "message": "No provider configured; deterministic local fallback is active."}
    if provider == "ollama":
        return await _ollama_health(kind, provider, model, timeout)
    missing_key = provider in {"bailian", "aihubmix", "siliconflow"} and not _api_key(provider)
    if missing_key:
        return {"kind": kind, "provider": provider, "model": model, "configured": True, "status": "degraded", "message": "Provider selected but API key is not configured."}
    return {"kind": kind, "provider": provider, "model": model, "configured": True, "status": "configured", "message": "Remote provider credentials are present; live generation uses runtime fallback on failure."}


async def _ollama_health(kind: str, provider: str, model: str, timeout: float) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.get(f"{settings.ollama_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            data = response.json()
        names = {item.get("name") for item in data.get("models", []) if isinstance(item, dict)}
        status = "healthy" if not model or model in names else "degraded"
        message = "Ollama is reachable." if status == "healthy" else "Ollama is reachable but the configured model was not listed."
        return {"kind": kind, "provider": provider, "model": model, "configured": True, "status": status, "message": message}
    except Exception as exc:
        return {"kind": kind, "provider": provider, "model": model, "configured": True, "status": "unavailable", "message": _provider_error(provider, exc)}


def _chat_model(provider: str) -> str:
    return {
        "ollama": settings.ollama_chat_model,
        "bailian": settings.bailian_chat_model,
        "aihubmix": settings.aihubmix_chat_model,
        "siliconflow": settings.siliconflow_chat_model,
    }.get(provider, "")


def _embedding_model(provider: str) -> str:
    return {
        "ollama": settings.ollama_embedding_model,
        "aihubmix": settings.aihubmix_embedding_model,
        "siliconflow": settings.siliconflow_embedding_model,
    }.get(provider, "")


def _rerank_model(provider: str) -> str:
    return {"bailian": settings.bailian_rerank_model}.get(provider, "")


def _api_key(provider: str) -> str:
    return {
        "bailian": settings.bailian_api_key,
        "aihubmix": settings.aihubmix_api_key,
        "siliconflow": settings.siliconflow_api_key,
    }.get(provider, "")


class LLMClient:
    async def chat(self, messages: list[dict], thinking: bool = False, temperature: float | None = None, top_p: float | None = None) -> str:
        provider = settings.chat_provider
        if not provider:
            return ""
        chunks: list[str] = []
        async for chunk in self._stream_provider(provider, messages, thinking, temperature=temperature, top_p=top_p):
            chunks.append(chunk)
        return "".join(chunks)

    async def stream_chat(self, messages: list[dict], thinking: bool = False, temperature: float | None = None, top_p: float | None = None) -> AsyncIterator[str]:
        provider = settings.chat_provider
        if provider:
            try:
                async for chunk in self._stream_provider(provider, messages, thinking, temperature=temperature, top_p=top_p):
                    yield chunk
                return
            except Exception as exc:
                yield f"模型调用失败，已降级到本地 fallback。\n\n{_provider_error(provider, exc)}\n\n"
        prompt = messages[-1]["content"] if messages else ""
        yield f"当前未配置可用模型 Provider，以下为 Python Ragent 本地 fallback 回答。\n\n{self._fallback_excerpt(prompt)}"

    def _fallback_excerpt(self, prompt: str) -> str:
        for tag in ("tool-data", "documents", "data"):
            match = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", prompt, re.S)
            if match and match.group(1).strip():
                return match.group(1).strip()[:1200]
        return prompt[:800]

    async def _stream_provider(self, provider: str, messages: list[dict], thinking: bool, temperature: float | None = None, top_p: float | None = None) -> AsyncIterator[str]:
        extra = {"stream": True}
        if temperature is not None:
            extra["temperature"] = temperature
        if top_p is not None:
            extra["top_p"] = top_p
        if provider == "ollama":
            async for chunk in self._stream_openai_style(
                base_url=settings.ollama_url,
                endpoint="/v1/chat/completions",
                model=settings.ollama_chat_model,
                api_key="",
                messages=messages,
                extra=extra,
            ):
                yield chunk
            return
        if provider == "bailian":
            async for chunk in self._stream_openai_style(settings.bailian_url, "/compatible-mode/v1/chat/completions", settings.bailian_chat_model, settings.bailian_api_key, messages, extra):
                yield chunk
            return
        if provider == "aihubmix":
            async for chunk in self._stream_openai_style(settings.aihubmix_url, "/v1/chat/completions", settings.aihubmix_chat_model, settings.aihubmix_api_key, messages, extra):
                yield chunk
            return
        if provider == "siliconflow":
            async for chunk in self._stream_openai_style(settings.siliconflow_url, "/v1/chat/completions", settings.siliconflow_chat_model, settings.siliconflow_api_key, messages, extra):
                yield chunk
            return
        raise ValueError(f"unsupported chat provider: {provider}")

    async def _stream_openai_style(self, base_url: str, endpoint: str, model: str, api_key: str, messages: list[dict], extra: dict) -> AsyncIterator[str]:
        payload = {"model": model, "messages": messages, **extra}
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            async with client.stream("POST", f"{base_url.rstrip('/')}{endpoint}", headers=_headers(api_key), json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        data = httpx.Response(200, content=raw).json()
                    except Exception:
                        continue
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content") or delta.get("reasoning_content") or ""
                    if content:
                        yield content


class EmbeddingClient:
    async def embed(self, text: str) -> list[float]:
        provider = settings.embedding_provider
        if not provider:
            return self._hash_embedding(text)
        try:
            if provider == "ollama":
                return await self._openai_style_embedding(settings.ollama_url, "/v1/embeddings", settings.ollama_embedding_model, "", text)
            if provider == "aihubmix":
                return await self._openai_style_embedding(settings.aihubmix_url, "/v1/embeddings", settings.aihubmix_embedding_model, settings.aihubmix_api_key, text)
            if provider == "siliconflow":
                return await self._openai_style_embedding(settings.siliconflow_url, "/v1/embeddings", settings.siliconflow_embedding_model, settings.siliconflow_api_key, text)
            raise ValueError(f"unsupported embedding provider: {provider}")
        except Exception:
            return self._hash_embedding(text)

    async def _openai_style_embedding(self, base_url: str, endpoint: str, model: str, api_key: str, text: str) -> list[float]:
        payload = {"model": model, "input": text}
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.post(f"{base_url.rstrip('/')}{endpoint}", headers=_headers(api_key), json=payload)
            response.raise_for_status()
            data = response.json()
            return [float(x) for x in data["data"][0]["embedding"]]

    def _hash_embedding(self, text: str, dimension: int = 1536) -> list[float]:
        vector = [0.0] * dimension
        for idx, char in enumerate(text):
            bucket = (ord(char) + idx * 31) % dimension
            vector[bucket] += 1.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]


class RerankClient:
    async def rerank(self, query: str, documents: list[str]) -> list[int]:
        provider = settings.rerank_provider
        if provider == "bailian" and settings.bailian_api_key:
            try:
                payload = {"model": settings.bailian_rerank_model, "input": {"query": query, "documents": documents}}
                async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                    response = await client.post(f"{settings.bailian_url.rstrip()}/api/v1/services/rerank/text-rerank/text-rerank", headers=_headers(settings.bailian_api_key), json=payload)
                    response.raise_for_status()
                    results = response.json().get("output", {}).get("results", [])
                    return [int(item["index"]) for item in sorted(results, key=lambda item: item.get("relevance_score", 0), reverse=True)]
            except Exception:
                pass
        return list(range(len(documents)))

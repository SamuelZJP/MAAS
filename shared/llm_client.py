from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx

from config import Settings, get_settings


class LLMClientError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str = "",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "LLMClient":
        settings = settings or get_settings()
        return cls(
            endpoint=settings.llm_endpoint,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        extra_body: Mapping[str, Any] | None = None,
    ) -> str:
        if not self.endpoint:
            raise LLMClientError("LLM endpoint is not configured.")
        if not self.model:
            raise LLMClientError("LLM model is not configured.")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if extra_body:
            payload.update(dict(extra_body))

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._post_json(payload=payload, headers=headers)
                return self._extract_text(response)
            except (httpx.HTTPError, LLMClientError) as exc:
                last_error = exc
                if attempt >= self.max_retries or not self._should_retry(exc):
                    break
                await asyncio.sleep(min(2**attempt, 5))

        raise LLMClientError(f"LLM request failed: {last_error}") from last_error

    async def _post_json(self, *, payload: Mapping[str, Any], headers: Mapping[str, str]) -> dict[str, Any]:
        if self._client is not None:
            response = await self._client.post(
                self.endpoint,
                json=dict(payload),
                headers=dict(headers),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.endpoint,
                json=dict(payload),
                headers=dict(headers),
            )
            response.raise_for_status()
            return response.json()

    def _extract_text(self, response_data: Mapping[str, Any]) -> str:
        choices = response_data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMClientError("LLM response does not contain choices.")

        message = choices[0].get("message")
        if isinstance(message, Mapping):
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, Mapping) and item.get("type") == "text":
                        text = item.get("text")
                        if isinstance(text, str):
                            text_parts.append(text)
                if text_parts:
                    return "\n".join(text_parts).strip()

        text = choices[0].get("text")
        if isinstance(text, str):
            return text.strip()

        raise LLMClientError("LLM response does not contain text content.")

    @staticmethod
    def _should_retry(exc: Exception) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code >= 500 or exc.response.status_code == 429
        if isinstance(exc, httpx.RequestError):
            return True
        return False


__all__ = ["LLMClient", "LLMClientError"]

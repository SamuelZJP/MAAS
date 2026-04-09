# LLM 统一调用封装：支持 OpenAI 兼容接口、重试机制和 mock 模式

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
import re
from typing import Any

import httpx

from config import Settings, get_settings


class LLMClientError(Exception):
    pass


# LLM 客户端，通过 HTTP 调用外部 LLM API（OpenAI 兼容格式）
class LLMClient:
    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str = "",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        mock_mode: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.mock_mode = mock_mode
        self._client = client

    # 从全局配置构造 LLMClient 实例
    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "LLMClient":
        settings = settings or get_settings()
        return cls(
            endpoint=settings.llm_endpoint,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            mock_mode=settings.llm_mock_mode,
        )

    # 调用 LLM 生成文本，支持自动重试
    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        extra_body: Mapping[str, Any] | None = None,
    ) -> str:
        if self.mock_mode:
            return self._mock_response(user_prompt)

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
            self._log_request(
                attempt=attempt + 1,
                total_attempts=self.max_retries + 1,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            try:
                response = await self._post_json(payload=payload, headers=headers)
                return self._extract_text(response)
            except (httpx.HTTPError, LLMClientError) as exc:
                last_error = exc
                if attempt >= self.max_retries or not self._should_retry(exc):
                    break
                await asyncio.sleep(min(2**attempt, 5))

        raise LLMClientError(f"LLM request failed: {last_error}") from last_error

    # 发送 HTTP POST 请求并返回 JSON 响应
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

    # 输出 LLM 请求日志到控制台
    def _log_request(
        self,
        *,
        attempt: int,
        total_attempts: int,
        system_prompt: str,
        user_prompt: str,
    ) -> None:
        print(
            "[LLM] "
            f"model={self.model} "
            f"endpoint={self.endpoint} "
            f"attempt={attempt}/{total_attempts} "
            f"system_chars={len(system_prompt)} "
            f"user_chars={len(user_prompt)}"
        )

    # 从 LLM 响应 JSON 中提取文本内容（兼容多种响应格式）
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

    # mock 模式：根据提示词关键字返回预设响应，用于本地测试
    def _mock_response(self, user_prompt: str) -> str:
        if "历史事件列表" in user_prompt:
            episode_ids = [int(value) for value in re.findall(r"事件(\d+)：", user_prompt)]
            return json.dumps(episode_ids[-1:] if episode_ids else [], ensure_ascii=False)

        if "## 当前语义记忆" in user_prompt and "## 待摘要内容" in user_prompt:
            date_match = re.search(r"日期：(.+)", user_prompt)
            time_match = re.search(r"时间：(.+)", user_prompt)
            location_match = re.search(r"地点：(.+)", user_prompt)
            user_input_match = re.search(r"用户输入：(.+)", user_prompt)
            ai_response_match = re.search(r"AI回复：(.+)", user_prompt)

            parts = []
            if date_match and time_match:
                parts.append(f"{date_match.group(1).strip()} {time_match.group(1).strip()}")
            elif date_match:
                parts.append(date_match.group(1).strip())
            elif time_match:
                parts.append(time_match.group(1).strip())
            if location_match:
                parts.append(location_match.group(1).strip())
            if user_input_match:
                parts.append(f"用户：{user_input_match.group(1).strip()}")
            if ai_response_match:
                parts.append(f"AI：{ai_response_match.group(1).strip()}")
            return "，".join(parts) or "本回合摘要"

        if "待检测的回合摘要" in user_prompt:
            round_ids = [int(value) for value in re.findall(r"\[回合(\d+)\]", user_prompt)]
            has_boundary = False
            boundary_round_id = None
            latest_text = user_prompt.split("## 判断标准", 1)[0]
            boundary_markers = (
                r"事件变化|场景变化|时间跳跃|转场|第二天|离开|来到|新的场景|冲突升级|"
                r"event change|scene change|time jump|transition|second day|left|arrived|new scene|conflict escalation"
            )
            if round_ids and re.search(boundary_markers, latest_text, re.IGNORECASE):
                has_boundary = True
                boundary_round_id = round_ids[-1]
            payload: dict[str, Any] = {"has_boundary": has_boundary}
            if boundary_round_id is not None:
                payload["boundary_round_id"] = boundary_round_id
            return json.dumps(payload, ensure_ascii=False)

        if "事件包含的回合摘要" in user_prompt:
            round_ids = [int(value) for value in re.findall(r"\[回合(\d+)\]", user_prompt)]
            if round_ids:
                title = f"事件{round_ids[0]}-{round_ids[-1]}"
            else:
                title = "新事件"
            summary_lines = []
            for line in user_prompt.splitlines():
                if line.startswith("[首条消息]") or line.startswith("[回合"):
                    summary_lines.append(line.strip())
            summary = " | ".join(summary_lines[:5]) or "事件摘要内容"
            return json.dumps({"title": title, "summary": summary}, ensure_ascii=False)

        return "[]"

    # 判断是否应重试（5xx / 429 / 网络错误）
    @staticmethod
    def _should_retry(exc: Exception) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code >= 500 or exc.response.status_code == 429
        if isinstance(exc, httpx.RequestError):
            return True
        return False


__all__ = ["LLMClient", "LLMClientError"]

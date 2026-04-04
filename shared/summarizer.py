from __future__ import annotations

from typing import Any

from shared.llm_client import LLMClient
from shared.prompt_utils import render_prompt


SUMMARY_SYSTEM_PROMPT = (
    "你是一个记忆管理助手。请根据提供的内容生成简洁、准确、可复用的摘要。"
)

SUMMARY_USER_TEMPLATE = """
## 上下文
{{ context }}

## 待摘要内容
{{ content }}

## 任务
请生成一段摘要，保留关键情节、人物互动、状态变化和重要事实，避免冗余。

## 输出格式
仅输出摘要正文，不要添加额外说明。
"""


async def generate_summary(
    content: str,
    context: Any,
    llm_client: LLMClient,
) -> str:
    user_prompt = render_prompt(
        SUMMARY_USER_TEMPLATE,
        content=content,
        context=context if context not in (None, "") else "无",
    )
    return await llm_client.generate_text(
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

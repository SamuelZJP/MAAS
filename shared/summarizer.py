# 通用摘要生成工具，供各模块复用

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
主角、"我"、用户角色的名称为{{user}}。

## 当前状态
{% if semantic_memory %}
日期：{{ semantic_memory["世界"]["日期"] }}
时间：{{ semantic_memory["世界"]["时间"] }}
地点：{{ semantic_memory["世界"]["地点"] }}
{% else %}
无
{% endif %}

## 待摘要内容
用户输入：{{ user_input }}
AI回复：{{ ai_response }}

## 任务
请生成一段摘要，保留关键情节、人物互动、状态变化和重要事实，避免冗余。
若当前语义记忆中给出了日期、时间、地点，请在摘要中以指定格式表现这些信息。

## 摘要格式
年月日—时分—地点
用约150字概括本条回复的具体事件，忠实记录关键对白片段、情报、行为和情感变化。直接呈现，不加以解读。
"""


# 调用 LLM 为给定内容生成摘要
async def generate_summary(
    user_input: str,
    ai_response: str,
    context: Any,
    semantic_memory: dict[str, Any] | None,
    user: str,
    llm_client: LLMClient,
) -> str:
    user_prompt = render_prompt(
        SUMMARY_USER_TEMPLATE,
        context=context if context not in (None, "") else "无",
        semantic_memory=semantic_memory,
        user_input=user_input,
        ai_response=ai_response,
        user=user,
    )
    summary = await llm_client.generate_text(
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    summary = summary.strip()
    if not summary:
        raise ValueError("Generated round summary is empty.")
    return summary

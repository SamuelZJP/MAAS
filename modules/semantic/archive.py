from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modules.semantic.prompts import SEMANTIC_UPDATE_PROMPT
from modules.semantic.schema_loader import (
    SemanticSchemaError,
    build_default_snapshot,
    dump_snapshot_yaml,
    load_reference_info,
    load_variable_update_rules,
    validate_snapshot,
)
from repository.crud.semantic import get_latest_semantic_memory, upsert_semantic_memory
from shared.llm_client import LLMClient
from shared.prompt_utils import render_prompt


ARCHIVE_SYSTEM_PROMPT = """
你是一个专业的角色扮演游戏变量分析助手。你的任务是根据参考信息和旧有剧情，为最新剧情更新游戏变量。
`过去状态`是发生在最新剧情之前的旧变量，它需要根据`本回合对话`的内容被更新到`本回合对话`**发生之后**的最新时间点。
请注意，你必须详细检查每一个变量，并体现在<Analysis>中。
"""
logger = logging.getLogger(__name__)


# 语义记忆归档：更新语义记忆快照
async def archive(
    chat_id: str,
    round_id: int,
    user_input: str,
    ai_response: str,
    context: Any,
    user: str,
    db_session: AsyncSession,
    llm_client: LLMClient,
) -> dict[str, Any]:
    latest_snapshot_record = await get_latest_semantic_memory(db_session, chat_id)
    previous_snapshot = (
        dict(latest_snapshot_record.content)
        if latest_snapshot_record is not None
        else build_default_snapshot(chat_id)
    )

    semantic_updated = False
    next_snapshot = copy.deepcopy(previous_snapshot)

    try:
        # 将语义记忆快照转换为 YAML 格式，用于 LLM 阅读
        current_memory_yaml = dump_snapshot_yaml(chat_id, previous_snapshot)

        # 渲染语义记忆更新提示词
        prompt_text = render_prompt(
            SEMANTIC_UPDATE_PROMPT,
            context=_normalize_context(context),
            current_memory_yaml=current_memory_yaml,
            user_input=user_input,
            ai_response=ai_response,
            user=user,
            reference_info=load_reference_info(chat_id),
            variable_update_rules=load_variable_update_rules(chat_id),
        )

        # 调用 LLM 生成语义记忆更新指令
        response_text = await llm_client.generate_text(
            system_prompt=ARCHIVE_SYSTEM_PROMPT,
            user_prompt=prompt_text,
        )

        # 解析语义记忆更新指令
        patch_operations = _parse_patch_operations(response_text)
        patched_snapshot = _apply_patch_operations(previous_snapshot, patch_operations)
        next_snapshot = validate_snapshot(chat_id, patched_snapshot)
        semantic_updated = next_snapshot != previous_snapshot
    except Exception:
        logger.exception(
            "Semantic archive failed; aborting archive update",
            extra={
                "chat_id": chat_id,
                "round_id": round_id,
            },
        )
        return {
            "archive_succeeded": False,
            "semantic_updated": False,
            "semantic_memory": None,
            "previous_semantic_memory": None,
        }

    await upsert_semantic_memory(
        db_session,
        chat_id=chat_id,
        round_id=round_id,
        content=next_snapshot,
    )
    return {
        "archive_succeeded": True,
        "semantic_updated": semantic_updated,
        "semantic_memory": next_snapshot,
        "previous_semantic_memory": previous_snapshot,
    }


# 规范化上下文：将上下文转换为字典格式
def _normalize_context(context: Any) -> dict[str, Any]:
    if context is None:
        return {"extra": ""}
    if hasattr(context, "model_dump"):
        data = context.model_dump()
    elif isinstance(context, dict):
        data = dict(context)
    else:
        data = {"extra": str(context)}
    data.setdefault("extra", "")
    return data


# 解析语义记忆更新指令：将 LLM 返回的文本解析为 JSON 数组
def _parse_patch_operations(text: str) -> list[dict[str, Any]]:
    payload = _extract_json_payload(text)
    if payload is None:
        raise SemanticSchemaError("Semantic patch response does not contain a JSON array.")

    data = json.loads(payload)
    if not isinstance(data, list):
        raise SemanticSchemaError("Semantic patch response must be a JSON array.")

    operations: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        op = item.get("op")
        path = item.get("path")
        if op not in {"replace", "add", "remove"}:
            continue
        if not isinstance(path, str) or not path.startswith("/"):
            continue
        operation = {"op": op, "path": path}
        if op != "remove" and "value" not in item:
            continue
        if "value" in item:
            operation["value"] = item["value"]
        operations.append(operation)
    return operations


# 提取 JSON 数组：从 LLM 返回的文本中提取 JSON 数组
def _extract_json_payload(text: str) -> str | None:
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced_match:
        text = fenced_match.group(1).strip()

    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        return match.group(0)

    stripped = text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped
    return None


# 应用 JSON Patch 操作：将 JSON Patch 操作应用到语义记忆快照上
def _apply_patch_operations(snapshot: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(snapshot)
    for operation in operations:
        try:
            _apply_single_operation(result, operation)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return result


# 应用单个 JSON Patch 操作：将单个 JSON Patch 操作应用到语义记忆快照上
def _apply_single_operation(target: Any, operation: dict[str, Any]) -> None:
    tokens = [_unescape_json_pointer(token) for token in operation["path"].split("/")[1:]]
    if not tokens:
        raise ValueError("Root path is not supported.")

    parent, key = _resolve_parent(target, tokens)
    op = operation["op"]

    if isinstance(parent, list):
        index = _parse_list_index(parent, key, allow_append=(op == "add"))
        if op == "remove":
            del parent[index]
            return
        if op == "add" and key == "-":
            parent.append(copy.deepcopy(operation["value"]))
            return
        if op == "add" and index == len(parent):
            parent.append(copy.deepcopy(operation["value"]))
            return
        parent[index] = copy.deepcopy(operation["value"])
        return

    if not isinstance(parent, dict):
        raise TypeError("Patch parent must be a dict or list.")

    if op == "remove":
        del parent[key]
        return
    parent[key] = copy.deepcopy(operation["value"])


# 解析父级：解析 JSON Patch 操作的父级
def _resolve_parent(target: Any, tokens: list[str]) -> tuple[Any, str]:
    current = target
    for token in tokens[:-1]:
        if isinstance(current, dict):
            if token not in current:
                raise KeyError(token)
            current = current[token]
            continue
        if isinstance(current, list):
            current = current[_parse_list_index(current, token)]
            continue
        raise TypeError("Intermediate patch target must be a dict or list.")
    return current, tokens[-1]


# 解析列表索引：解析 JSON Patch 操作的列表索引
def _parse_list_index(items: list[Any], token: str, *, allow_append: bool = False) -> int:
    if token == "-" and allow_append:
        return len(items)
    if not token.isdigit():
        raise ValueError("List index must be a non-negative integer.")
    index = int(token)
    if index < 0 or index > len(items) or (index == len(items) and not allow_append):
        raise IndexError(index)
    return index


# 反转义 JSON Pointer：将 JSON Pointer 中的转义字符转换为原始字符
def _unescape_json_pointer(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")

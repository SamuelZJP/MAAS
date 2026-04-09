from __future__ import annotations

import copy
import json
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modules.semantic.prompts import SEMANTIC_UPDATE_PROMPT
from modules.semantic.schema_loader import (
    SemanticSchemaError,
    build_default_snapshot,
    dump_snapshot_yaml,
    validate_snapshot,
)
from repository.crud.semantic import get_latest_semantic_memory, upsert_semantic_memory
from shared.llm_client import LLMClient
from shared.prompt_utils import render_prompt


ARCHIVE_SYSTEM_PROMPT = "你是一个记忆管理助手。"


async def archive(
    chat_id: str,
    round_id: int,
    user_input: str,
    ai_response: str,
    context: Any,
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
        current_memory_yaml = dump_snapshot_yaml(chat_id, previous_snapshot)
        response_text = await llm_client.generate_text(
            system_prompt=ARCHIVE_SYSTEM_PROMPT,
            user_prompt=render_prompt(
                SEMANTIC_UPDATE_PROMPT,
                context=_normalize_context(context),
                current_memory_yaml=current_memory_yaml,
                user_input=user_input,
                ai_response=ai_response,
            ),
        )
        patch_operations = _parse_patch_operations(response_text)
        patched_snapshot = _apply_patch_operations(previous_snapshot, patch_operations)
        next_snapshot = validate_snapshot(chat_id, patched_snapshot)
        semantic_updated = next_snapshot != previous_snapshot
    except Exception:
        next_snapshot = previous_snapshot
        semantic_updated = False

    await upsert_semantic_memory(
        db_session,
        chat_id=chat_id,
        round_id=round_id,
        content=next_snapshot,
    )
    return {
        "semantic_updated": semantic_updated,
        "semantic_memory": next_snapshot,
    }


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


def _apply_patch_operations(snapshot: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(snapshot)
    for operation in operations:
        try:
            _apply_single_operation(result, operation)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return result


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


def _parse_list_index(items: list[Any], token: str, *, allow_append: bool = False) -> int:
    if token == "-" and allow_append:
        return len(items)
    if not token.isdigit():
        raise ValueError("List index must be a non-negative integer.")
    index = int(token)
    if index < 0 or index > len(items) or (index == len(items) and not allow_append):
        raise IndexError(index)
    return index


def _unescape_json_pointer(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")

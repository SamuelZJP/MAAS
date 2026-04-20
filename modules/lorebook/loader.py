from __future__ import annotations

from pathlib import Path
from typing import Any

from repository.crud.lorebook import bulk_create_lorebook_entries


LOREBOOK_DIR = Path(__file__).resolve().parents[2] / "lorebook"
POSITION_ORDER = {"character": 0, "depth": 1}


# TODO: 添加自定义错误类，用于捕获词条文件加载失败的情况
class LorebookLoadError(Exception):
    pass


# 从词条文件中加载词条记录
async def load_lorebook_entries(chat_id: str, db_session) -> int:
    entries = parse_lorebook_files(chat_id)
    if not entries:
        return 0

    await bulk_create_lorebook_entries(db_session, chat_id=chat_id, entries=entries)
    return len(entries)


# 解析词条文件
def parse_lorebook_files(chat_id: str) -> list[dict[str, Any]]:
    directory = LOREBOOK_DIR / chat_id
    if not directory.exists() or not directory.is_dir():
        return []

    file_paths = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".yaml")

    entries: list[dict[str, Any]] = []
    for entry_id, file_path in enumerate(file_paths, start=1):
        parsed = _parse_lorebook_file(file_path)
        parsed["entry_id"] = entry_id
        entries.append(parsed)
    return entries


# 解析单个词条文件
def _parse_lorebook_file(file_path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise LorebookLoadError("PyYAML is required for lorebook loading.") from exc

    try:
        raw_data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - parser errors depend on PyYAML internals
        raise LorebookLoadError(f"Failed to parse lorebook file '{file_path.name}': {exc}") from exc

    if not isinstance(raw_data, dict):
        raise LorebookLoadError(f"Lorebook file '{file_path.name}' must contain a YAML object.")

    position = raw_data.get("position")
    order = raw_data.get("order")
    content = raw_data.get("content")
    depth = raw_data.get("depth")
    has_template = raw_data.get("has_template", False)
    enabled = raw_data.get("enabled", True)

    if position not in POSITION_ORDER:
        raise LorebookLoadError(f"Lorebook file '{file_path.name}' has invalid position '{position}'.")
    if not isinstance(order, int) or order < 0:
        raise LorebookLoadError(f"Lorebook file '{file_path.name}' must define a non-negative integer order.")
    if not isinstance(content, str):
        raise LorebookLoadError(f"Lorebook file '{file_path.name}' must define string content.")
    if position == "depth":
        if not isinstance(depth, int) or depth < 0:
            raise LorebookLoadError(
                f"Lorebook file '{file_path.name}' must define a non-negative integer depth for depth entries."
            )
    elif depth is not None:
        raise LorebookLoadError(f"Lorebook file '{file_path.name}' must use null depth for character entries.")

    return {
        "filename": file_path.stem,
        "content": content.strip(),
        "position": position,
        "order": order,
        "depth": depth,
        "has_template": bool(has_template),
        "enabled": bool(enabled),
    }

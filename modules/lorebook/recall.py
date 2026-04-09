from __future__ import annotations

import logging
from typing import Any

from jinja2 import Environment, StrictUndefined
from sqlalchemy.ext.asyncio import AsyncSession

from repository.crud.lorebook import list_enabled_lorebook_entries
from schemas.lorebook import LorebookEntryPayload


logger = logging.getLogger(__name__)

POSITION_ORDER = {"character": 0, "depth": 1}
template_environment = Environment(
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


async def recall(
    chat_id: str,
    db_session: AsyncSession,
    semantic_memory: dict[str, Any] | None,
) -> list[LorebookEntryPayload]:
    records = await list_enabled_lorebook_entries(db_session, chat_id)
    entries: list[LorebookEntryPayload] = []

    for record in records:
        if record.has_template:
            if semantic_memory is None:
                continue
            try:
                content = template_environment.from_string(record.content).render(
                    semantic_memory=semantic_memory
                ).strip()
            except Exception:
                logger.warning(
                    "Failed to render lorebook entry",
                    extra={"chat_id": chat_id, "entry_id": record.entry_id, "filename": record.filename},
                    exc_info=True,
                )
                continue
        else:
            content = record.content.strip()

        if not content:
            continue

        entries.append(
            LorebookEntryPayload(
                entry_id=record.entry_id,
                content=content,
                position=record.position,
                order=record.order,
                depth=record.depth,
            )
        )

    entries.sort(
        key=lambda item: (
            POSITION_ORDER[item.position],
            -1 if item.depth is None else item.depth,
            item.order,
            item.entry_id,
        )
    )
    return entries

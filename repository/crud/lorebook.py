from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repository.models import LorebookEntry


async def bulk_create_lorebook_entries(
    session: AsyncSession,
    *,
    chat_id: str,
    entries: Sequence[dict[str, object]],
) -> list[LorebookEntry]:
    records = [
        LorebookEntry(
            chat_id=chat_id,
            entry_id=int(entry["entry_id"]),
            filename=str(entry["filename"]),
            content=str(entry["content"]),
            position=str(entry["position"]),
            order=int(entry["order"]),
            depth=entry["depth"] if entry["depth"] is None else int(entry["depth"]),
            has_template=bool(entry["has_template"]),
            enabled=bool(entry["enabled"]),
        )
        for entry in entries
    ]
    session.add_all(records)
    await session.flush()
    return records


async def list_enabled_lorebook_entries(
    session: AsyncSession,
    chat_id: str,
) -> list[LorebookEntry]:
    stmt = (
        select(LorebookEntry)
        .where(
            LorebookEntry.chat_id == chat_id,
            LorebookEntry.enabled.is_(True),
        )
        .order_by(
            LorebookEntry.position.asc(),
            LorebookEntry.depth.asc().nullsfirst(),
            LorebookEntry.order.asc(),
            LorebookEntry.entry_id.asc(),
        )
    )
    result = await session.scalars(stmt)
    return list(result.all())

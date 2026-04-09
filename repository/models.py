# SQLAlchemy ORM 模型定义：chats / rounds / episodes / semantic_memories / lorebook_entries

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# 角色对话主表
class Chat(Base):
    __tablename__ = "chats"

    chat_id: Mapped[str] = mapped_column(String, primary_key=True)
    first_message: Mapped[str] = mapped_column(Text, nullable=False)
    first_message_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled_modules: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    rounds: Mapped[list["Round"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    semantic_memories: Mapped[list["SemanticMemory"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    lorebook_entries: Mapped[list["LorebookEntry"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# 对话回合表，主键为 (chat_id, round_id)
class Round(Base):
    __tablename__ = "rounds"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chat_id", "episode_id"],
            ["episodes.chat_id", "episodes.episode_id"],
            name="fk_rounds_episode",
        ),
        CheckConstraint("round_id >= 1", name="ck_rounds_round_id_positive"),
    )

    chat_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("chats.chat_id", ondelete="CASCADE"),
        primary_key=True,
    )
    round_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    ai_response: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    episode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    chat: Mapped["Chat"] = relationship(back_populates="rounds")
    episode: Mapped["Episode | None"] = relationship(
        back_populates="rounds",
        foreign_keys=lambda: [Round.chat_id, Round.episode_id],
        overlaps="chat,rounds",
    )


# 事件表，主键为 (chat_id, episode_id)
class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        CheckConstraint("episode_id >= 1", name="ck_episodes_episode_id_positive"),
        CheckConstraint("start_round_id >= 1", name="ck_episodes_start_round_id_positive"),
        CheckConstraint("end_round_id >= start_round_id", name="ck_episodes_round_range"),
    )

    chat_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("chats.chat_id", ondelete="CASCADE"),
        primary_key=True,
    )
    episode_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    start_round_id: Mapped[int] = mapped_column(Integer, nullable=False)
    end_round_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    chat: Mapped["Chat"] = relationship(back_populates="episodes")
    rounds: Mapped[list["Round"]] = relationship(
        back_populates="episode",
        foreign_keys=lambda: [Round.chat_id, Round.episode_id],
        overlaps="chat,rounds",
    )


class SemanticMemory(Base):
    __tablename__ = "semantic_memories"
    __table_args__ = (
        CheckConstraint("round_id >= 0", name="ck_semantic_memories_round_id_non_negative"),
    )

    chat_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("chats.chat_id", ondelete="CASCADE"),
        primary_key=True,
    )
    round_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    chat: Mapped["Chat"] = relationship(back_populates="semantic_memories")


class LorebookEntry(Base):
    __tablename__ = "lorebook_entries"
    __table_args__ = (
        CheckConstraint("entry_id >= 1", name="ck_lorebook_entries_entry_id_positive"),
        CheckConstraint("position IN ('character', 'depth')", name="ck_lorebook_entries_position_valid"),
        CheckConstraint("sort_order >= 0", name="ck_lorebook_entries_order_non_negative"),
        CheckConstraint(
            "(position = 'character' AND depth IS NULL) OR (position = 'depth' AND depth >= 0)",
            name="ck_lorebook_entries_depth_matches_position",
        ),
    )

    chat_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("chats.chat_id", ondelete="CASCADE"),
        primary_key=True,
    )
    entry_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[str] = mapped_column(String, nullable=False)
    order: Mapped[int] = mapped_column("sort_order", Integer, nullable=False)
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    chat: Mapped["Chat"] = relationship(back_populates="lorebook_entries")


__all__ = ["Base", "Chat", "Round", "Episode", "SemanticMemory", "LorebookEntry"]

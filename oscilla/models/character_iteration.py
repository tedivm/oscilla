from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    REAL,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from oscilla.models.base import Base

if TYPE_CHECKING:
    from oscilla.models.character import CharacterRecord


class CharacterIterationRecord(Base):
    __tablename__ = "character_iterations"
    __table_args__ = (
        UniqueConstraint("character_id", "iteration", name="uq_character_iteration"),
        # Partial unique index — only one is_active=TRUE row allowed per character.
        # Both SQLite and PostgreSQL support partial indexes; dialect kwargs are
        # required because the WHERE syntax differs slightly between them.
        Index(
            "uq_active_iteration_per_character",
            "character_id",
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    character_id: Mapped[UUID] = mapped_column(ForeignKey("characters.id"), nullable=False)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False)
    # Exactly one row per character has is_active = True, enforced by
    # uq_active_iteration_per_character partial unique index.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    character_class: Mapped[str | None] = mapped_column(String, nullable=True)
    pronoun_set: Mapped[str] = mapped_column(String, nullable=False, default="they_them")

    # Active adventure — scalar identifiers live as columns; step_state is the
    # only JSON column because its keys and shape are set by the step handler at
    # runtime (e.g., {"enemy_hp": 12}). All three are NULL between adventures.
    adventure_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    adventure_step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adventure_step_state: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Run lifecycle
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )
    # Set when the run ends (prestige); NULL while this is the active run.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # In-game tick counters. Both reset to 0 on new iteration.
    # Stored as BigInteger to accommodate games with very high tick rates or long runs.
    internal_ticks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    game_ticks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Session soft-lock — detects and recovers from dead processes (see design D11).
    # session_token is a per-GameSession UUID written at lock acquisition and
    # cleared on clean exit. If a new session finds this non-NULL it concludes
    # the previous process died, steals the lock, and clears any orphaned adventure state.
    session_token: Mapped[str | None] = mapped_column(String, nullable=True)
    session_token_acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Child table relationships — cascade keeps orphans from accumulating on delete
    stat_values: Mapped[List["CharacterIterationStatValue"]] = relationship(
        "CharacterIterationStatValue", back_populates="iteration", cascade="all, delete-orphan"
    )
    inventory_rows: Mapped[List["CharacterIterationInventory"]] = relationship(
        "CharacterIterationInventory", back_populates="iteration", cascade="all, delete-orphan"
    )
    equipment_rows: Mapped[List["CharacterIterationEquipment"]] = relationship(
        "CharacterIterationEquipment", back_populates="iteration", cascade="all, delete-orphan"
    )
    item_instance_rows: Mapped[List["CharacterIterationItemInstance"]] = relationship(
        "CharacterIterationItemInstance", back_populates="iteration", cascade="all, delete-orphan"
    )
    milestone_rows: Mapped[List["CharacterIterationMilestone"]] = relationship(
        "CharacterIterationMilestone", back_populates="iteration", cascade="all, delete-orphan"
    )
    quest_rows: Mapped[List["CharacterIterationQuest"]] = relationship(
        "CharacterIterationQuest", back_populates="iteration", cascade="all, delete-orphan"
    )
    statistic_rows: Mapped[List["CharacterIterationStatistic"]] = relationship(
        "CharacterIterationStatistic", back_populates="iteration", cascade="all, delete-orphan"
    )
    skill_rows: Mapped[List["CharacterIterationSkill"]] = relationship(
        "CharacterIterationSkill", back_populates="iteration", cascade="all, delete-orphan"
    )
    skill_cooldown_rows: Mapped[List["CharacterIterationSkillCooldown"]] = relationship(
        "CharacterIterationSkillCooldown", back_populates="iteration", cascade="all, delete-orphan"
    )
    adventure_state_rows: Mapped[List["CharacterIterationAdventureState"]] = relationship(
        "CharacterIterationAdventureState", back_populates="iteration", cascade="all, delete-orphan"
    )
    era_state_rows: Mapped[List["CharacterIterationEraState"]] = relationship(
        "CharacterIterationEraState", back_populates="iteration", cascade="all, delete-orphan"
    )
    pending_trigger_rows: Mapped[List["CharacterIterationPendingTrigger"]] = relationship(
        "CharacterIterationPendingTrigger",
        back_populates="iteration",
        order_by="CharacterIterationPendingTrigger.position",
        cascade="all, delete-orphan",
    )
    active_buff_rows: Mapped[List["CharacterIterationActiveBuff"]] = relationship(
        "CharacterIterationActiveBuff", back_populates="iteration", cascade="all, delete-orphan"
    )
    character: Mapped["CharacterRecord"] = relationship(  # noqa: F821
        "CharacterRecord", back_populates="iterations"
    )

    __mapper_args__ = {"version_id_col": version}


class CharacterIterationStatValue(Base):
    """Content-defined character stat stored as a BIGINT column.

    stat_value is NULL for stats whose default is explicitly unset (e.g.
    relationship scores before first interaction). int values are stored and
    returned as-is. No encoding or decoding is needed.
    Keys and their expected types come from the content package's CharacterConfig
    — content-drift handling (add missing / drop removed) happens in
    CharacterState.from_dict().
    """

    __tablename__ = "character_iteration_stat_values"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    stat_name: Mapped[str] = mapped_column(String, primary_key=True)
    stat_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="stat_values"
    )


class CharacterIterationInventory(Base):
    """One row per item stack in the character's inventory."""

    __tablename__ = "character_iteration_inventory"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    item_ref: Mapped[str] = mapped_column(String, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="inventory_rows"
    )


class CharacterIterationEquipment(Base):
    """One row per filled equipment slot, referencing a non-stackable item instance by UUID."""

    __tablename__ = "character_iteration_equipment"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    slot: Mapped[str] = mapped_column(String, primary_key=True)
    # UUID of the ItemInstance that occupies this slot (stored as string for SQLite compatibility)
    instance_id: Mapped[str] = mapped_column(String, nullable=False)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="equipment_rows"
    )


class CharacterIterationItemInstance(Base):
    """One row per non-stackable item instance owned by the character.

    instance_id is a UUID generated at item drop time and persisted across
    saves so the service layer can correlate equipment slots to instances.
    """

    __tablename__ = "character_iteration_item_instances"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    # UUID stored as string for SQLite/PostgreSQL compatibility
    instance_id: Mapped[str] = mapped_column(String, primary_key=True)
    item_ref: Mapped[str] = mapped_column(String, nullable=False)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="item_instance_rows"
    )
    modifier_rows: Mapped[List["CharacterIterationItemInstanceModifier"]] = relationship(
        "CharacterIterationItemInstanceModifier",
        back_populates="item_instance",
        cascade="all, delete-orphan",
    )


class CharacterIterationItemInstanceModifier(Base):
    """Per-instance stat modifiers for enchanted or otherwise modified item instances.

    Deleted automatically (ON DELETE CASCADE) when the parent item instance row
    is removed.  The composite FK (iteration_id, instance_id) references
    character_iteration_item_instances.
    """

    __tablename__ = "character_iteration_item_instance_modifiers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["iteration_id", "instance_id"],
            [
                "character_iteration_item_instances.iteration_id",
                "character_iteration_item_instances.instance_id",
            ],
            ondelete="CASCADE",
        ),
    )

    iteration_id: Mapped[UUID] = mapped_column(String, primary_key=True, nullable=False)
    instance_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    stat: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    amount: Mapped[float] = mapped_column(REAL, nullable=False)

    item_instance: Mapped["CharacterIterationItemInstance"] = relationship(
        "CharacterIterationItemInstance", back_populates="modifier_rows"
    )


class CharacterIterationMilestone(Base):
    """One row per milestone held by the character in this iteration."""

    __tablename__ = "character_iteration_milestones"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    milestone_ref: Mapped[str] = mapped_column(String, primary_key=True)
    # Tick and wall-clock timestamp at which this milestone was granted.
    # Default 0 preserves compatibility with rows written before this migration.
    grant_tick: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    grant_timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="milestone_rows"
    )


class CharacterIterationQuest(Base):
    """One row per active, completed, or failed quest in this iteration.

    status is "active", "completed", or "failed".
    stage is the current quest stage name — only meaningful for active quests,
    NULL for completed and failed ones.
    """

    __tablename__ = "character_iteration_quests"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    quest_ref: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # "active" | "completed" | "failed"
    stage: Mapped[str | None] = mapped_column(String, nullable=True)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="quest_rows"
    )


class CharacterIterationStatistic(Base):
    """One row per named entity counter (enemies defeated, locations visited, etc.).

    stat_type discriminates the counter category:
      "enemies_defeated"     — maps to CharacterStatistics.enemies_defeated
      "locations_visited"    — maps to CharacterStatistics.locations_visited
      "adventures_completed" — maps to CharacterStatistics.adventures_completed

    entity_ref is the content-defined entity name (e.g., "goblin", "dungeon-entrance").
    """

    __tablename__ = "character_iteration_statistics"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    stat_type: Mapped[str] = mapped_column(String, primary_key=True)
    entity_ref: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="statistic_rows"
    )


class CharacterIterationSkill(Base):
    """One row per skill known by the character in this iteration.

    skill_ref is the content-defined Skill manifest name
    (e.g., ``"fireball"`` not the display name).
    """

    __tablename__ = "character_iteration_skills"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    skill_ref: Mapped[str] = mapped_column(String, primary_key=True)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="skill_rows"
    )


class CharacterIterationSkillCooldown(Base):
    """One row per skill that is on an adventure-scope cooldown.

    tick_expiry is the internal_ticks value at which the cooldown expires
    (0 = no tick-based constraint active).
    real_expiry is the Unix timestamp (seconds) at which the cooldown expires
    (0 = no real-time constraint active).
    Turn-scope cooldowns are not persisted — they reset every combat encounter.
    """

    __tablename__ = "character_iteration_skill_cooldowns"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    skill_ref: Mapped[str] = mapped_column(String, primary_key=True)
    tick_expiry: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    real_expiry: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="skill_cooldown_rows"
    )


class CharacterIterationAdventureState(Base):
    """One row per adventure that has been completed at least once this iteration.

    last_completed_real_ts is the Unix timestamp (seconds) at the time of the
    most recent completion — used for seconds-based cooldown checks.
    last_completed_game_ticks is the game_ticks value at the time of the most
    recent completion — used for game_ticks cooldown checks.
    last_completed_at_ticks is the internal_ticks value at the time of the most
    recent completion — used for ticks-based cooldown checks.
    """

    __tablename__ = "character_iteration_adventure_state"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    adventure_ref: Mapped[str] = mapped_column(String, primary_key=True)
    last_completed_real_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_completed_game_ticks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_completed_at_ticks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="adventure_state_rows"
    )


class CharacterIterationEraState(Base):
    """One row per era that has activated or deactivated this iteration.

    started_at_game_ticks: game_ticks at the moment the era's start_condition
        first evaluated true (or 0 for always-active eras). NULL if the era
        has not yet started.
    ended_at_game_ticks: game_ticks at the moment the era's end_condition first
        evaluated true. NULL if the era has not yet ended (or has no end_condition).
    """

    __tablename__ = "character_iteration_era_state"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    era_name: Mapped[str] = mapped_column(String, primary_key=True)
    started_at_game_ticks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ended_at_game_ticks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="era_state_rows"
    )


class CharacterIterationPendingTrigger(Base):
    """One row per queued trigger awaiting drain.

    position preserves FIFO order — rows are loaded ascending by position
    and written with consecutive 0-based positions.
    """

    __tablename__ = "character_iteration_pending_triggers"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    trigger_name: Mapped[str] = mapped_column(String, nullable=False)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="pending_trigger_rows"
    )


class CharacterIterationActiveBuff(Base):
    """One row per persistent buff active on the character in this iteration.

    Composite PK (iteration_id, buff_ref) — one stored entry per buff manifest name.
    variables_json is the JSON-serialized Dict[str, int] of resolved variables at apply time.
    Nullable expiry columns mirror the BuffDuration time-based fields.
    """

    __tablename__ = "character_iteration_active_buffs"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    buff_ref: Mapped[str] = mapped_column(String, primary_key=True)
    remaining_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    variables_json: Mapped[str] = mapped_column(String, nullable=False, default="{}")
    tick_expiry: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    game_tick_expiry: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    real_ts_expiry: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="active_buff_rows"
    )

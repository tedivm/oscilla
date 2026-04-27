"""CharacterConfig manifest — defines all player stats for a content package."""

from typing import List, Literal, Set

from pydantic import BaseModel, Field, model_validator

from oscilla.engine.models.base import BaseSpec, Condition, ManifestEnvelope

StatType = Literal["int", "bool"]
StatContext = Literal["stored", "effective"]


class StatBounds(BaseModel):
    """Inclusive bounds for an integer stat. Either bound may be omitted (defaults to INT64 range)."""

    min: int | None = None
    max: int | None = None

    @model_validator(mode="after")
    def validate_min_lte_max(self) -> "StatBounds":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"StatBounds.min ({self.min}) must be less than or equal to StatBounds.max ({self.max})")
        return self


class StatDefinition(BaseModel):
    name: str
    type: StatType
    default: int | bool | None = None
    description: str = ""
    bounds: StatBounds | None = None
    # Template string evaluated on read. If set, this stat is never written directly;
    # effects targeting it are rejected at load time.
    derived: str | None = None
    # Controls which stat dict the derived formula sees:
    #   "stored"    — player.stats (raw stored values, no equipment/passive bonuses)
    #   "effective" — effective_stats(registry) (includes equipment + passive effects)
    # Ignored when derived is None. Default "stored" is backward-compatible.
    stat_context: StatContext = "stored"

    @model_validator(mode="after")
    def validate_bounds_not_on_bool(self) -> "StatDefinition":
        if self.type == "bool" and self.bounds is not None:
            raise ValueError(f"StatBounds cannot be set on a bool stat (stat name: {self.name!r})")
        return self

    @model_validator(mode="after")
    def validate_derived_not_on_bool(self) -> "StatDefinition":
        # Derived formulas always produce int; bool derived stats are not useful.
        if self.type == "bool" and self.derived is not None:
            raise ValueError(f"Derived formula cannot be set on a bool stat (stat name: {self.name!r})")
        return self

    @model_validator(mode="after")
    def validate_derived_has_no_default(self) -> "StatDefinition":
        # Derived stats are never stored, so a default value is meaningless and misleading.
        if self.derived is not None and self.default is not None:
            raise ValueError(
                f"Derived stat {self.name!r} must not declare a default value — "
                "derived stats are never stored and have no initial value."
            )
        return self

    @model_validator(mode="after")
    def validate_stat_context_only_on_derived(self) -> "StatDefinition":
        # stat_context is only meaningful on derived stats; warn authors who set it on stored stats.
        if self.derived is None and self.stat_context != "stored":
            raise ValueError(
                f"stat_context may only be set on derived stats (stat name: {self.name!r}). "
                "Remove stat_context or add a derived formula."
            )
        return self


class SlotDefinition(BaseModel):
    name: str
    displayName: str
    # Item categories that can be equipped in this slot (empty = no restriction)
    accepts: List[str] = []
    # Condition that must pass before this slot is unlocked; None = always unlocked
    requires: Condition | None = None
    show_when_locked: bool = False


class CharacterConfigSpec(BaseSpec):
    public_stats: List[StatDefinition] = []
    hidden_stats: List[StatDefinition] = []
    equipment_slots: List[SlotDefinition] = []
    # Maps resource names used by SkillCost to stat names in public/hidden_stats.
    # Validated at load time: stat and max_stat must reference declared stats.
    skill_resources: List["SkillResourceBinding"] = []
    # Optional category governance — absent means no restrictions enforced.
    skill_category_rules: List["SkillCategoryRule"] = []
    # Additional pronoun sets beyond the built-in three. Games may add xe/xir,
    # fae/faer, etc. here without touching engine code.
    extra_pronoun_sets: List["PronounSetDefinition"] = []

    @model_validator(mode="after")
    def validate_unique_stat_names(self) -> "CharacterConfigSpec":
        all_names = [s.name for s in self.public_stats] + [s.name for s in self.hidden_stats]
        seen: Set[str] = set()
        duplicates: List[str] = []
        for name in all_names:
            if name in seen:
                duplicates.append(name)
            seen.add(name)
        if duplicates:
            raise ValueError(
                f"Duplicate stat names in CharacterConfig: {sorted(set(duplicates))!r}. "
                "Each stat name must be unique across public_stats and hidden_stats."
            )
        return self

    @model_validator(mode="after")
    def validate_unique_slot_names(self) -> "CharacterConfigSpec":
        seen_slots: Set[str] = set()
        duplicates: List[str] = []
        for slot in self.equipment_slots:
            if slot.name in seen_slots:
                duplicates.append(slot.name)
            seen_slots.add(slot.name)
        if duplicates:
            raise ValueError(
                f"Duplicate slot names in CharacterConfig: {sorted(set(duplicates))!r}. Each slot name must be unique."
            )
        return self


class CharacterConfigManifest(ManifestEnvelope):
    kind: Literal["CharacterConfig"]
    spec: CharacterConfigSpec


class SkillResourceBinding(BaseModel):
    """Maps a human-readable resource name to a character stat and its max stat."""

    name: str = Field(description="Resource name used by SkillCost (e.g. 'mana', 'psi').")
    stat: str = Field(description="Stat name holding the current resource value.")
    max_stat: str = Field(description="Stat name holding the resource maximum.")


class SkillCategoryRule(BaseModel):
    """Optional engine-side governance for a skill category."""

    category: str
    max_known: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of skills in this category a character may learn. None = unlimited.",
    )
    exclusive_with: List[str] = Field(
        default=[],
        description="Category names whose known skills conflict with this category.",
    )


class PronounSetDefinition(BaseModel):
    """A named pronoun set that can be selected during character creation."""

    name: str = Field(description="Unique key, e.g. 'xe_xir'.")
    display_name: str = Field(description="Label shown in character creation UI.")
    subject: str
    object: str
    possessive: str
    possessive_standalone: str
    reflexive: str
    uses_plural_verbs: bool = False


# Update CharacterConfigSpec forward references now that the classes are defined.
CharacterConfigSpec.model_rebuild()

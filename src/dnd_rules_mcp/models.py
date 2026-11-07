"""Explicit facts for deterministic checks. Unknown is different from false."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Condition = Literal[
    "blinded",
    "charmed",
    "deafened",
    "exhaustion",
    "frightened",
    "grappled",
    "incapacitated",
    "invisible",
    "paralyzed",
    "petrified",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
    "unconscious",
]
NonNegative = Annotated[int, Field(ge=0)]
DieRoll = Annotated[int, Field(ge=1, le=20)]


class Facts(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    # None asks a question; [] explicitly declares there are no special overrides.
    special_rules: list[str] | None = None


class ActorFacts(Facts):
    conditions: list[Condition] | None = None


class ActionEconomy(ActorFacts):
    kind: Literal["action_economy"]
    resource: Literal["action", "bonus_action", "reaction"]
    available: bool | None = None
    on_own_turn: bool | None = None
    permission: bool | None = None
    trigger_satisfied: bool | None = None


class Movement(ActorFacts):
    kind: Literal["movement"]
    on_own_turn: bool | None = None
    speed_ft: NonNegative | None = None
    movement_spent_ft: NonNegative | None = None
    extra_movement_ft: NonNegative | None = None
    distance_ft: NonNegative | None = None
    difficult_terrain: bool | None = None
    movement_mode: Literal["walk", "crawl", "stand_up"] = "walk"
    destination_clear: bool | None = None


class OpportunityAttack(ActorFacts):
    kind: Literal["opportunity_attack"]
    reaction_available: bool | None = None
    can_see_target: bool | None = None
    target_leaves_reach: bool | None = None
    target_uses_own_movement: bool | None = None
    target_teleports: bool | None = None
    target_disengaged: bool | None = None


class Spellcasting(ActorFacts):
    kind: Literal["spellcasting"]
    spell: str = Field(min_length=1, max_length=100)
    on_own_turn: bool | None = None
    casting_resource_available: bool | None = None
    trigger_satisfied: bool | None = None
    spell_access: bool | None = None
    expends_slot: bool | None = None
    slot_level: Annotated[int, Field(ge=1, le=9)] | None = None
    slot_available: bool | None = None
    slot_already_expended_this_turn: bool | None = None
    verbal_possible: bool | None = None
    somatic_possible: bool | None = None
    material_available: bool | None = None
    already_concentrating: bool | None = None
    distance_ft: NonNegative | None = None


class Concentration(ActorFacts):
    kind: Literal["concentration"]
    damage_taken: NonNegative | None = None
    save_total: int | None = None
    starting_another_concentration_effect: bool | None = None


class Damage(Facts):
    kind: Literal["damage"]
    amount: NonNegative
    flat_reduction: NonNegative | None = None
    resistance: bool | None = None
    vulnerability: bool | None = None
    immunity: bool | None = None


class Roll(Facts):
    kind: Literal["roll"]
    roll_type: Literal["ability_check", "saving_throw", "attack_roll"]
    rolls: list[DieRoll] = Field(min_length=1, max_length=2)
    modifier: int
    target: int
    advantage_sources: NonNegative | None = None
    disadvantage_sources: NonNegative | None = None


class Character(Facts):
    kind: Literal["character"]
    classes: dict[str, Annotated[int, Field(ge=1, le=20)]] = Field(min_length=1, max_length=12)
    ability_scores: dict[str, Annotated[int, Field(ge=1, le=30)]] | None = None
    proficiency_bonus: Annotated[int, Field(ge=0)] | None = None
    ability_method: Literal["point_buy", "standard_array", "rolled"] | None = None
    base_ability_scores: dict[str, Annotated[int, Field(ge=1, le=30)]] | None = None


Check = Annotated[
    ActionEconomy
    | Movement
    | OpportunityAttack
    | Spellcasting
    | Concentration
    | Damage
    | Roll
    | Character,
    Field(discriminator="kind"),
]

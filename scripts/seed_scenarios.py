"""Author the reviewed scenarios; expectations are explicit, not computed by the engine."""

import json
from pathlib import Path

cases = []


def add(
    name, facts, verdict="no_violation_found", effects=None, page=None, origin="paired_variant"
):
    facts = {"special_rules": [], **facts}
    cases.append(
        {
            "id": name,
            "origin": origin,
            "source_page": page,
            "facts": facts,
            "expected": {"verdict": verdict, "effects": effects or {}},
        }
    )


for resource in ("action", "bonus_action", "reaction"):
    base = {
        "kind": "action_economy",
        "resource": resource,
        "conditions": [],
        "available": True,
        "on_own_turn": True,
        "permission": True,
        "trigger_satisfied": True,
    }
    add(resource + "-available", base, page=10)
    add(resource + "-spent", {**base, "available": False}, "disallowed", page=10)
    add(resource + "-stunned", {**base, "conditions": ["stunned"]}, "disallowed", page=189)
    add(resource + "-unknown-state", {**base, "conditions": None}, "needs_information", page=10)
    if resource != "action":
        add(resource + "-no-permission", {**base, "permission": False}, "disallowed", page=10)
add("reaction-outside-own-turn", {**base, "on_own_turn": False}, page=10)
add("reaction-trigger-missing", {**base, "trigger_satisfied": False}, "disallowed", page=10)
move = {
    "kind": "movement",
    "conditions": [],
    "on_own_turn": True,
    "speed_ft": 30,
    "movement_spent_ft": 10,
    "extra_movement_ft": 0,
    "distance_ft": 20,
    "difficult_terrain": False,
    "destination_clear": True,
}
add(
    "split-move-thirty-feet",
    move,
    effects={"movement_cost_ft": 20, "remaining_movement_ft": 0},
    page=14,
    origin="official_worked_example",
)
add("split-move-one-foot-too-far", {**move, "distance_ft": 21}, "disallowed", page=14)
add(
    "difficult-terrain-five-feet",
    {**move, "movement_spent_ft": 0, "distance_ft": 5, "difficult_terrain": True},
    effects={"movement_cost_ft": 10},
    page=181,
    origin="official_worked_example",
)
add(
    "crawl-difficult-terrain",
    {
        **move,
        "conditions": ["prone"],
        "movement_mode": "crawl",
        "distance_ft": 5,
        "difficult_terrain": True,
    },
    effects={"movement_cost_ft": 15},
    page=179,
)
add("cannot-walk-while-prone", {**move, "conditions": ["prone"]}, "disallowed", page=186)
add(
    "stand-up-half-speed",
    {**move, "conditions": ["prone"], "movement_mode": "stand_up", "distance_ft": 0},
    effects={"movement_cost_ft": 15},
    page=186,
)
add(
    "stand-up-odd-speed-round-down",
    {
        **move,
        "speed_ft": 25,
        "movement_spent_ft": 0,
        "conditions": ["prone"],
        "movement_mode": "stand_up",
        "distance_ft": 0,
    },
    effects={"movement_cost_ft": 12},
    page=186,
)
for condition in ("grappled", "restrained", "unconscious", "petrified", "paralyzed"):
    add("movement-" + condition, {**move, "conditions": [condition]}, "disallowed", page=182)
add(
    "incapacitated-alone-does-not-set-speed-zero",
    {**move, "conditions": ["incapacitated"]},
    page=183,
)
add("occupied-end-space", {**move, "destination_clear": False}, "disallowed", page=14)
add("movement-needs-terrain", {**move, "difficult_terrain": None}, "needs_information", page=14)
oa = {
    "kind": "opportunity_attack",
    "conditions": [],
    "reaction_available": True,
    "can_see_target": True,
    "target_leaves_reach": True,
    "target_uses_own_movement": True,
    "target_teleports": False,
    "target_disengaged": False,
}
add("ordinary-opportunity-attack", oa, page=185)
for field, value in (
    ("reaction_available", False),
    ("can_see_target", False),
    ("target_leaves_reach", False),
    ("target_uses_own_movement", False),
    ("target_teleports", True),
    ("target_disengaged", True),
):
    add("opportunity-" + field, {**oa, field: value}, "disallowed", page=15)
add(
    "opportunity-unknown-disengage",
    {**oa, "target_disengaged": None},
    "needs_information",
    page=181,
)
spell = {
    "kind": "spellcasting",
    "spell": "Fireball",
    "conditions": [],
    "on_own_turn": True,
    "casting_resource_available": True,
    "spell_access": True,
    "expends_slot": True,
    "slot_level": 3,
    "slot_available": True,
    "slot_already_expended_this_turn": False,
    "verbal_possible": True,
    "somatic_possible": True,
    "material_available": True,
    "distance_ft": 150,
}
add("fireball-at-range-boundary", spell, page=131)
for field, value, name in (
    ("slot_level", 2, "slot-too-low"),
    ("distance_ft", 151, "beyond-range"),
    ("slot_available", False, "no-slot"),
    ("slot_already_expended_this_turn", True, "second-slot-on-same-turn"),
    ("verbal_possible", False, "silenced"),
    ("somatic_possible", False, "no-somatic"),
    ("material_available", False, "missing-material"),
    ("spell_access", False, "not-prepared"),
):
    add("fireball-" + name, {**spell, field: value}, "disallowed", page=105)
add(
    "fireball-missing-verbal-fact",
    {**spell, "verbal_possible": None},
    "needs_information",
    page=105,
)
add(
    "fireball-without-slot-needs-feature",
    {**spell, "expends_slot": False},
    "needs_information",
    page=104,
)
add(
    "cantrip-after-slotted-spell",
    {
        **spell,
        "spell": "Fire Bolt",
        "expends_slot": False,
        "slot_already_expended_this_turn": True,
        "distance_ft": 90,
    },
    page=105,
)
add(
    "shield-on-another-turn",
    {**spell, "spell": "Shield", "slot_level": 1, "on_own_turn": False, "trigger_satisfied": True},
    page=105,
)
add(
    "shield-second-slot-on-own-turn",
    {
        **spell,
        "spell": "Shield",
        "slot_level": 1,
        "trigger_satisfied": True,
        "slot_already_expended_this_turn": True,
    },
    "disallowed",
    page=105,
)
add(
    "shield-trigger-not-met",
    {**spell, "spell": "Shield", "slot_level": 1, "trigger_satisfied": False},
    "disallowed",
    page=105,
)
add(
    "new-concentration-replaces-old",
    {**spell, "spell": "Bless", "slot_level": 1, "already_concentrating": True, "distance_ft": 30},
    effects={"previous_concentration_ends": True},
    page=179,
)
add("unknown-spell", {**spell, "spell": "An invented spell"}, "needs_information", page=104)
add(
    "ritual-casting-needs-interpretation",
    {**spell, "spell": "Alarm", "slot_level": 1, "distance_ft": 10},
    "needs_information",
    page=105,
)
conc = {
    "kind": "concentration",
    "conditions": [],
    "starting_another_concentration_effect": False,
    "damage_taken": 22,
    "save_total": 11,
}
add("concentration-dc-eleven", conc, effects={"save_dc": 11, "concentration_ends": False}, page=179)
add(
    "concentration-failed-save",
    {**conc, "save_total": 10},
    "disallowed",
    effects={"concentration_ends": True},
    page=179,
)
add(
    "concentration-dc-cap-thirty",
    {**conc, "damage_taken": 100, "save_total": 30},
    effects={"save_dc": 30, "concentration_ends": False},
    page=179,
)
add(
    "concentration-zero-damage",
    {**conc, "damage_taken": 0, "save_total": None},
    effects={"save_required": False},
    page=179,
)
add("concentration-save-unknown", {**conc, "save_total": None}, "needs_information", page=179)
add("concentration-stunned", {**conc, "conditions": ["stunned"]}, "disallowed", page=179)
add(
    "cannot-maintain-two-concentration-effects",
    {**conc, "starting_another_concentration_effect": True},
    "disallowed",
    page=179,
)
damage = {
    "kind": "damage",
    "amount": 28,
    "flat_reduction": 5,
    "resistance": True,
    "vulnerability": True,
    "immunity": False,
}
add(
    "official-damage-order-example",
    damage,
    effects={"damage": 22},
    page=17,
    origin="official_worked_example",
)
add("damage-immunity", {**damage, "immunity": True}, effects={"damage": 0}, page=17)
add("damage-cannot-be-negative", {**damage, "flat_reduction": 40}, effects={"damage": 0}, page=17)
add(
    "damage-odd-resistance",
    {**damage, "amount": 5, "flat_reduction": 0, "vulnerability": False},
    effects={"damage": 2},
    page=17,
)
add("damage-unknown-immunity", {**damage, "immunity": None}, "needs_information", page=17)
roll = {
    "kind": "roll",
    "roll_type": "attack_roll",
    "rolls": [20],
    "modifier": -5,
    "target": 30,
    "advantage_sources": 0,
    "disadvantage_sources": 0,
}
add("natural-twenty-attack", roll, effects={"success": True, "critical_hit": True}, page=7)
add(
    "natural-twenty-check-can-fail",
    {**roll, "roll_type": "ability_check"},
    effects={"success": False, "critical_hit": False},
    page=6,
)
add(
    "natural-one-attack",
    {**roll, "rolls": [1], "modifier": 20, "target": 10},
    effects={"success": False},
    page=7,
)
add(
    "natural-one-save-can-pass",
    {**roll, "roll_type": "saving_throw", "rolls": [1], "modifier": 20, "target": 10},
    effects={"success": True},
    page=7,
)
add(
    "advantage-selects-higher",
    {**roll, "rolls": [3, 18], "modifier": 2, "target": 15, "advantage_sources": 2},
    effects={"d20": 18, "success": True},
    page=8,
)
add(
    "disadvantage-selects-lower",
    {**roll, "rolls": [3, 18], "modifier": 2, "target": 15, "disadvantage_sources": 2},
    effects={"d20": 3, "success": False},
    page=8,
)
add(
    "advantage-disadvantage-cancel-despite-count",
    {
        **roll,
        "rolls": [10],
        "modifier": 2,
        "target": 12,
        "advantage_sources": 3,
        "disadvantage_sources": 1,
    },
    effects={"d20": 10, "success": True},
    page=8,
)
add("advantage-needs-two-rolls", {**roll, "advantage_sources": 1}, "needs_information", page=8)
scores = {
    "strength": 15,
    "dexterity": 14,
    "constitution": 13,
    "intelligence": 12,
    "wisdom": 10,
    "charisma": 8,
}
character = {
    "kind": "character",
    "classes": {"Fighter": 3, "Rogue": 2},
    "ability_scores": scores,
    "proficiency_bonus": 3,
    "ability_method": "standard_array",
    "base_ability_scores": scores,
}
add(
    "official-multiclass-proficiency-example",
    character,
    effects={"total_level": 5, "expected_proficiency_bonus": 3},
    page=25,
    origin="official_worked_example",
)
add("wrong-multiclass-proficiency", {**character, "proficiency_bonus": 2}, "disallowed", page=25)
add(
    "multiclass-prerequisite-fails",
    {**character, "ability_scores": {**scores, "dexterity": 12}},
    "disallowed",
    page=24,
)
add(
    "single-class-does-not-require-thirteen",
    {
        **character,
        "classes": {"Fighter": 5},
        "ability_scores": {**scores, "strength": 8, "dexterity": 8},
    },
    page=24,
)
add(
    "character-level-cap",
    {**character, "classes": {"Fighter": 20, "Rogue": 1}},
    "disallowed",
    page=23,
)
add(
    "point-buy-over-budget",
    {**character, "ability_method": "point_buy", "base_ability_scores": {**scores, "charisma": 15}},
    "disallowed",
    page=21,
)
add(
    "point-buy-twenty-seven-points",
    {**character, "ability_method": "point_buy"},
    effects={"point_buy_cost": 27},
    page=21,
)
add("unknown-base-generation", {**character, "ability_method": None}, "needs_information", page=21)
add(
    "unknown-special-rules-is-not-false",
    {**move, "special_rules": None},
    "needs_information",
    page=10,
)
add(
    "house-rule-needs-dm",
    {**move, "special_rules": ["House rule: movement is doubled"]},
    "requires_dm_ruling",
    page=10,
)
add("roll-needs-advantage-facts", {**roll, "advantage_sources": None}, "needs_information", page=8)
add("damage-needs-reduction-fact", {**damage, "flat_reduction": None}, "needs_information", page=17)
root = Path(__file__).resolve().parents[1]
(root / "tests/fixtures/scenarios.json").write_text(json.dumps(cases, indent=2) + "\n")
(root / "examples/fireball.json").write_text(
    json.dumps({"special_rules": [], **spell}, indent=2) + "\n"
)
(root / "examples/character.json").write_text(
    json.dumps({"special_rules": [], **character}, indent=2) + "\n"
)
print(f"Wrote {len(cases)} scenarios")

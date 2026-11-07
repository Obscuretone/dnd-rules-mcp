"""Deterministic checks with explicit scope, missing facts and source citations.

A successful check is 'no_violation_found', never a claim that every SRD rule or
spell-specific interaction was evaluated. The MCP host reasons over other rules.
"""

from .corpus import Corpus, corpus
from .models import (
    ActionEconomy,
    Character,
    Check,
    Concentration,
    Damage,
    Movement,
    OpportunityAttack,
    Roll,
    Spellcasting,
)

INCAPACITATED = {"incapacitated", "paralyzed", "petrified", "stunned", "unconscious"}
IMMOBILE = {"grappled", "paralyzed", "petrified", "restrained", "unconscious"}
ABILITIES = {"strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"}
PREREQUISITES = {
    "barbarian": (("strength",),),
    "bard": (("charisma",),),
    "cleric": (("wisdom",),),
    "druid": (("wisdom",),),
    "fighter": (("strength", "dexterity"),),
    "monk": (("dexterity",), ("wisdom",)),
    "paladin": (("strength",), ("charisma",)),
    "ranger": (("dexterity",), ("wisdom",)),
    "rogue": (("dexterity",),),
    "sorcerer": (("charisma",),),
    "warlock": (("charisma",),),
    "wizard": (("intelligence",),),
}


class Review:
    def __init__(self, facts: Check, source: Corpus):
        self.facts = facts
        self.source = source
        self.findings = []
        self.missing = []
        self.checked = []
        self.unverified = []
        self.effects = {}
        self._references = set()

    def cite(self, *ids):
        self._references.update(ids)

    def require(self, *names):
        missing = [name for name in names if getattr(self.facts, name) is None]
        self.missing.extend(name for name in missing if name not in self.missing)
        return not missing

    def reject(self, code, message, *ids):
        self.findings.append({"code": code, "message": message, "rule_ids": list(ids)})
        self.cite(*ids)

    def actor(self, requires_action=False):
        if not self.require("conditions"):
            return False
        if requires_action and INCAPACITATED.intersection(self.facts.conditions):
            self.reject(
                "incapacitated",
                "The actor cannot take actions, Bonus Actions or Reactions.",
                "incapacitated",
            )
            self.cite(*(c for c in self.facts.conditions if c in INCAPACITATED))
        return True

    def result(self):
        if self.findings:
            verdict = "disallowed"
        elif self.missing:
            verdict = "needs_information"
        else:
            verdict = "no_violation_found"
        return {
            "verdict": verdict,
            "scope": self.facts.kind,
            "findings": self.findings,
            "missing_facts": self.missing,
            "checked": self.checked,
            "unverified": self.unverified,
            "effects": self.effects,
            "version": "5.2.1",
            "citations": [self.source.get(k) for k in sorted(self._references)],
            "meaning": "The verdict covers only the listed checks and supplied facts; it is not a complete adjudication.",
        }


def check_action(f: ActionEconomy, r: Review):
    r.actor(requires_action=True)
    r.cite("actions", "bonus-actions", "reactions")
    r.checked.append("base action/Bonus Action/Reaction availability")
    if r.require("available") and not f.available:
        r.reject(
            "resource_spent",
            f"No {f.resource} remains in the supplied state.",
            "actions"
            if f.resource == "action"
            else "reactions"
            if f.resource == "reaction"
            else "bonus-actions",
        )
    if f.resource != "reaction" and r.require("on_own_turn") and not f.on_own_turn:
        r.reject(
            "wrong_turn",
            "Ordinary actions and Bonus Actions are taken on your turn.",
            "actions",
            "bonus-actions",
        )
    if f.resource != "action":
        if r.require("permission") and not f.permission:
            r.reject(
                "no_permission",
                "A specific rule must grant this Bonus Action or Reaction.",
                "bonus-actions" if f.resource == "bonus_action" else "reactions",
            )
    if f.resource == "reaction" and r.require("trigger_satisfied") and not f.trigger_satisfied:
        r.reject("trigger_absent", "The Reaction's trigger is not satisfied.", "reactions")
    r.unverified = [
        "eligibility and effects of the proposed action",
        "specific feature restrictions",
    ]


def check_movement(f: Movement, r: Review):
    r.actor()
    r.cite("movement", "difficult-terrain", "occupied-space")
    r.checked.extend(
        ["movement budget", "Difficult Terrain cost", "declared condition restrictions"]
    )
    r.unverified = [
        "path geometry, hazards and Opportunity Attacks",
        "special speeds and movement through other creatures",
    ]
    if r.require("on_own_turn") and not f.on_own_turn:
        r.reject("wrong_turn", "Ordinary movement with Speed is taken on your turn.", "movement")
    if not r.require(
        "speed_ft",
        "movement_spent_ft",
        "extra_movement_ft",
        "distance_ft",
        "difficult_terrain",
        "destination_clear",
        "conditions",
    ):
        return
    effective_speed = 0 if IMMOBILE.intersection(f.conditions) else f.speed_ft
    r.cite(*(c for c in f.conditions if c in IMMOBILE))
    if not f.destination_clear:
        r.reject(
            "occupied_destination",
            "You cannot willingly end this move in an occupied space.",
            "occupied-space",
        )
    if f.movement_mode == "stand_up":
        r.cite("prone")
        cost = effective_speed // 2
        if "prone" not in f.conditions:
            r.reject("not_prone", "The supplied actor is not Prone.", "prone")
        if effective_speed == 0:
            r.reject("speed_zero", "You cannot right yourself while your Speed is 0.", "prone")
    else:
        if "prone" in f.conditions and f.movement_mode != "crawl":
            r.reject(
                "must_crawl",
                "While Prone you must crawl or right yourself before walking.",
                "prone",
            )
        cost = f.distance_ft * (1 + int(f.difficult_terrain) + int(f.movement_mode == "crawl"))
        if f.movement_mode == "crawl":
            r.cite("crawling")
        if effective_speed == 0 and f.distance_ft > 0:
            r.reject("speed_zero", "The actor has no Speed for this movement.", "movement")
    available = max(0, effective_speed + f.extra_movement_ft - f.movement_spent_ft)
    if cost > available:
        r.reject(
            "insufficient_movement",
            f"This costs {cost} feet; only {available} feet remain.",
            "movement",
            "difficult-terrain",
        )
    r.effects.update(movement_cost_ft=cost, remaining_movement_ft=max(0, available - cost))


def check_opportunity(f: OpportunityAttack, r: Review):
    r.actor(requires_action=True)
    r.cite("opportunity-attacks", "reactions", "disengage", "page:15", "page:190")
    r.checked.extend(
        [
            "Reaction availability",
            "visibility and reach trigger",
            "Disengage, teleport and forced-movement exclusions",
        ]
    )
    r.unverified = ["weapon eligibility, attack roll and damage", "other creature's special traits"]
    if not r.require(
        "reaction_available",
        "can_see_target",
        "target_leaves_reach",
        "target_uses_own_movement",
        "target_teleports",
        "target_disengaged",
    ):
        return
    for field, wanted, message in (
        ("reaction_available", True, "No Reaction remains."),
        ("can_see_target", True, "The provoking creature must be visible to the actor."),
        ("target_leaves_reach", True, "The target must leave the actor's reach."),
        (
            "target_uses_own_movement",
            True,
            "Movement without the target's action, Bonus Action, Reaction or speeds does not provoke.",
        ),
        ("target_teleports", False, "Teleportation does not provoke."),
        (
            "target_disengaged",
            False,
            "Disengage prevents this Opportunity Attack under the base rules.",
        ),
    ):
        if getattr(f, field) != wanted:
            r.reject(field, message, "opportunity-attacks", "page:15")


def check_spell(f: Spellcasting, r: Review):
    r.actor(requires_action=True)
    spell = r.source.spell(f.spell)
    r.cite("spell-slots-per-turn", "components", "casting-triggers")
    r.checked.extend(
        [
            "spell entry and casting resource",
            "one slot spent per turn",
            "declared spell access and components",
        ]
    )
    r.unverified = [
        "target eligibility, line of effect, cover and area geometry",
        "spell-specific requirements, outcomes and interactions",
        "class preparation limits and feature exceptions",
    ]
    if spell is None:
        r.missing.append("spell must identify an entry in SRD 5.2.1; search_rules can locate it")
        return
    r.cite(spell["id"])
    fields = spell["fields"]
    casting_time = fields["casting-time"]
    if casting_time not in {"Action", "Bonus Action"} and not casting_time.startswith("Reaction"):
        r.missing.append(
            "extended/ritual casting requires interpretation of the cited spell and casting rules"
        )
        r.cite("long-casting")
    if not casting_time.startswith("Reaction") and r.require("on_own_turn") and not f.on_own_turn:
        r.reject(
            "wrong_turn",
            "This casting time requires your own turn under the base rules.",
            "actions",
            "bonus-actions",
        )
    if r.require("casting_resource_available") and not f.casting_resource_available:
        r.reject(
            "resource_spent",
            f"The casting resource ({casting_time}) is unavailable.",
            spell["id"],
            "actions",
            "reactions",
        )
    if (
        "which you take" in casting_time
        and r.require("trigger_satisfied")
        and not f.trigger_satisfied
    ):
        r.reject(
            "trigger_absent",
            "The spell's casting trigger is not satisfied.",
            spell["id"],
            "casting-triggers",
        )
    if r.require("spell_access") and not f.spell_access:
        r.reject(
            "no_spell_access",
            "The actor has no supplied permission to cast this spell.",
            "page:104",
        )
    if r.require("expends_slot"):
        if f.expends_slot:
            r.require("slot_level", "slot_available", "slot_already_expended_this_turn")
            if f.slot_already_expended_this_turn:
                r.reject(
                    "one_slot_per_turn",
                    "A spell slot has already been expended to cast a spell on this turn.",
                    "spell-slots-per-turn",
                )
            if f.slot_available is False:
                r.reject("no_slot", "No slot of the declared level is available.", "page:104")
            if f.slot_level is not None and f.slot_level < fields["level"]:
                r.reject(
                    "slot_too_low",
                    "The supplied spell slot is below the spell's level.",
                    "page:104",
                    spell["id"],
                )
        elif fields["level"] > 0:
            # A leveled no-slot casting is a feature exception, never inferred from a boolean.
            r.missing.append("a specific feature authorizing this leveled spell without a slot")
    for letter, field, rule in (
        ("V", "verbal_possible", "verbal"),
        ("S", "somatic_possible", "somatic"),
        ("M", "material_available", "components"),
    ):
        required_components = fields["components"].split("(", 1)[0]
        if letter in required_components and r.require(field) and not getattr(f, field):
            r.reject(
                "missing_component_" + letter,
                f"The {letter} component is unavailable.",
                rule,
                spell["id"],
            )
    if fields["concentration"]:
        r.cite("concentration")
        if r.require("already_concentrating") and f.already_concentrating:
            r.effects["previous_concentration_ends"] = True
    numeric_range = fields["range"].split(" ", 1)[0]
    if numeric_range.isdigit():
        r.checked.append("numeric spell range")
        if r.require("distance_ft") and f.distance_ft > int(numeric_range):
            r.reject(
                "out_of_range",
                f"The target point is beyond the spell's {fields['range']} range.",
                spell["id"],
            )
    if fields["level"] == 0 and f.expends_slot:
        r.reject("cantrip_slot", "Cantrips do not use spell slots.", "page:104")


def check_concentration(f: Concentration, r: Review):
    r.actor()
    r.cite("concentration")
    r.checked.extend(
        [
            "condition-based loss of Concentration",
            "replacement Concentration",
            "damage saving throw DC",
        ]
    )
    if f.conditions and INCAPACITATED.intersection(f.conditions):
        r.effects["concentration_ends"] = True
        r.reject(
            "incapacitated",
            "The existing Concentration ends while Incapacitated.",
            "concentration",
            "incapacitated",
        )
        return
    if not r.require("starting_another_concentration_effect"):
        return
    if f.starting_another_concentration_effect:
        r.effects["concentration_ends"] = True
        r.reject(
            "replaced",
            "Starting another Concentration effect ends the existing one; it does not prohibit casting the new spell.",
            "concentration",
        )
        return
    if not r.require("damage_taken"):
        return
    if f.damage_taken == 0:
        r.effects.update(save_required=False, concentration_ends=False)
        return
    dc = min(30, max(10, f.damage_taken // 2))
    r.effects.update(save_required=True, save_dc=dc)
    if r.require("save_total"):
        r.effects["concentration_ends"] = f.save_total < dc
        if f.save_total < dc:
            r.reject(
                "failed_save",
                "The supplied saving throw fails, ending Concentration.",
                "concentration",
            )


def check_damage(f: Damage, r: Review):
    r.cite("page:17")
    r.checked.extend(
        [
            "flat reduction before Resistance",
            "rounding down",
            "Vulnerability after Resistance",
            "damage Immunity",
        ]
    )
    r.unverified = [
        "damage roll and damage type selection",
        "which resistances, vulnerabilities and immunities apply",
    ]
    if not r.require("flat_reduction", "resistance", "vulnerability", "immunity"):
        return
    value = max(0, f.amount - f.flat_reduction)
    if f.resistance:
        value //= 2
    if f.vulnerability:
        value *= 2
    if f.immunity:
        value = 0
    r.effects["damage"] = value


def check_roll(f: Roll, r: Review):
    r.cite("page:7", "page:8")
    r.checked.extend(
        [
            "Advantage/Disadvantage cancellation",
            "supplied roll and total",
            "attack-only natural 1/20 rules",
        ]
    )
    r.unverified = [
        "which modifiers or Advantage/Disadvantage sources apply",
        "special critical ranges, rerolls and substituted dice",
    ]
    if not r.require("advantage_sources", "disadvantage_sources"):
        return
    advantage = f.advantage_sources > 0 and f.disadvantage_sources == 0
    disadvantage = f.disadvantage_sources > 0 and f.advantage_sources == 0
    expected = 2 if advantage or disadvantage else 1
    if len(f.rolls) != expected:
        r.missing.append(f"rolls must contain {expected} d20 result(s) after cancellation")
        return
    die = max(f.rolls) if advantage else min(f.rolls) if disadvantage else f.rolls[0]
    total = die + f.modifier
    success = total >= f.target
    if f.roll_type == "attack_roll":
        success = die == 20 or (die != 1 and success)
    r.effects.update(
        d20=die,
        total=total,
        success=success,
        critical_hit=f.roll_type == "attack_roll" and die == 20,
    )


def check_character(f: Character, r: Review):
    r.cite("page:19", "page:21", "page:23", "page:24", "page:25")
    r.checked.extend(
        [
            "total level",
            "Proficiency Bonus",
            "multiclass ability prerequisites",
            "declared base ability generation",
        ]
    )
    r.unverified = [
        "subclasses, feats, species, backgrounds and feature choices",
        "equipment, Armor Class, Hit Points and proficiencies",
        "spell preparation, slots and individual class progression features",
    ]
    levels = {name.casefold(): level for name, level in f.classes.items()}
    if len(levels) != len(f.classes):
        r.reject("duplicate_class", "Class names must be unique ignoring case.", "page:24")
    total = sum(levels.values())
    r.effects["total_level"] = total
    if total > 20:
        r.reject("level_cap", "The SRD character progression ends at level 20.", "page:23")
    if any(name not in PREREQUISITES for name in levels):
        r.missing.append("classes outside this SRD require their own source and rules")
    if total <= 20:
        bonus = 2 + (total - 1) // 4
        r.effects["expected_proficiency_bonus"] = bonus
        if r.require("proficiency_bonus") and f.proficiency_bonus != bonus:
            r.reject(
                "proficiency_bonus",
                f"A level {total} character has Proficiency Bonus +{bonus}.",
                "page:23",
            )
    if len(levels) > 1 and r.require("ability_scores"):
        if set(f.ability_scores) != ABILITIES:
            r.missing.append("ability_scores must specify the six full lowercase ability names")
        else:
            for name in levels:
                for alternatives in PREREQUISITES.get(name, ()):
                    if not any(f.ability_scores[ability] >= 13 for ability in alternatives):
                        r.reject(
                            "multiclass_prerequisite",
                            f"{name.title()} requires 13 or higher in {' or '.join(alternatives)} to multiclass.",
                            "page:24",
                            "page:25",
                        )
    if r.require("ability_method"):
        if f.ability_method == "rolled":
            r.unverified.append("rolled ability generation and table approval")
        elif r.require("base_ability_scores"):
            scores = list(f.base_ability_scores.values())
            if set(f.base_ability_scores) != ABILITIES:
                r.missing.append(
                    "base_ability_scores must specify the six full lowercase ability names"
                )
            elif f.ability_method == "standard_array" and sorted(scores) != [8, 10, 12, 13, 14, 15]:
                r.reject(
                    "standard_array",
                    "The base Standard Array is 15, 14, 13, 12, 10, 8 before increases.",
                    "page:21",
                )
            elif f.ability_method == "point_buy":
                costs = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
                if any(score not in costs for score in scores):
                    r.reject(
                        "point_buy_range",
                        "Purchased base scores must be between 8 and 15.",
                        "page:21",
                    )
                else:
                    cost = sum(costs[score] for score in scores)
                    r.effects["point_buy_cost"] = cost
                    if cost > 27:
                        r.reject(
                            "point_buy_budget",
                            f"The base scores cost {cost} points; the budget is 27.",
                            "page:21",
                        )


HANDLERS = {
    ActionEconomy: check_action,
    Movement: check_movement,
    OpportunityAttack: check_opportunity,
    Spellcasting: check_spell,
    Concentration: check_concentration,
    Damage: check_damage,
    Roll: check_roll,
    Character: check_character,
}


def evaluate(facts: Check, source: Corpus | None = None) -> dict:
    source = source or corpus()
    review = Review(facts, source)
    if facts.special_rules is None:
        return {
            "verdict": "needs_information",
            "scope": facts.kind,
            "missing_facts": [
                "special_rules: supply [] to explicitly use the base rules, or describe overrides"
            ],
            "version": "5.2.1",
            "findings": [],
            "citations": [],
        }
    if facts.special_rules:
        return {
            "verdict": "requires_dm_ruling",
            "scope": facts.kind,
            "reason": "Declared features, exceptions or house rules require interpretation before applying base constraints.",
            "special_rules": facts.special_rules,
            "version": "5.2.1",
            "findings": [],
            "citations": [source.get("improvising")],
        }
    HANDLERS[type(facts)](facts, review)
    return review.result()

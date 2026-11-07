import json

import pytest
from pydantic import TypeAdapter, ValidationError

from dnd_rules_mcp.models import Check


@pytest.mark.parametrize(
    "facts",
    [
        {"kind": "movement", "distance_ft": -1},
        {"kind": "movement", "conditions": ["invented_condition"]},
        {"kind": "movement", "destination_clear": "true"},
        {"kind": "spellcasting", "spell": "Fireball", "slot_level": 10},
        {"kind": "character", "classes": {"Wizard": 0}},
        {"kind": "damage", "amount": -1},
        {"kind": "roll", "roll_type": "attack_roll", "rolls": [21], "modifier": 0, "target": 10},
        {"kind": "movement", "unknown_fact": True},
    ],
)
def test_invalid_or_invented_facts_are_rejected(facts):
    with pytest.raises(ValidationError):
        TypeAdapter(Check).validate_json(json.dumps(facts))

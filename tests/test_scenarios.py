import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from dnd_rules_mcp.corpus import corpus
from dnd_rules_mcp.evaluator import evaluate
from dnd_rules_mcp.models import Check

SCENARIOS = json.loads((Path(__file__).parent / "fixtures/scenarios.json").read_text())


@pytest.mark.parametrize("case", SCENARIOS, ids=lambda c: c["id"])
def test_scenario(case):
    facts = TypeAdapter(Check).validate_json(json.dumps(case["facts"]))
    result = evaluate(facts)
    assert result["verdict"] == case["expected"]["verdict"]
    for key, expected in case["expected"]["effects"].items():
        assert result["effects"][key] == expected
    for citation in result.get("citations", []):
        assert citation["status"] == "found"
        assert citation["source_sha256"] == corpus().source["sha256"]
        assert citation["text"]
    if result["verdict"] == "no_violation_found":
        assert not result["missing_facts"]
        assert not result["findings"]
        assert result["checked"]
        assert result["citations"]
        assert "not a complete adjudication" in result["meaning"]

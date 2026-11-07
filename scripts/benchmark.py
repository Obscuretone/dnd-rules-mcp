"""Run the published deterministic scenarios and report their measured coverage."""

import json
from pathlib import Path

from pydantic import TypeAdapter

from dnd_rules_mcp.corpus import corpus
from dnd_rules_mcp.evaluator import evaluate
from dnd_rules_mcp.models import Check

ROOT = Path(__file__).resolve().parents[1]


def main():
    cases = json.loads((ROOT / "tests/fixtures/scenarios.json").read_text())
    results = []
    for case in cases:
        actual = evaluate(TypeAdapter(Check).validate_json(json.dumps(case["facts"])))
        expected = case["expected"]
        passed = actual["verdict"] == expected["verdict"] and all(
            actual.get("effects", {}).get(key) == value
            for key, value in expected["effects"].items()
        )
        results.append(
            {
                "id": case["id"],
                "passed": passed,
                "origin": case["origin"],
                "expected": expected["verdict"],
                "actual": actual["verdict"],
            }
        )
    report = {
        "corpus": corpus().stats(),
        "scenarios": len(results),
        "passed": sum(r["passed"] for r in results),
        "official_worked_examples": sum(r["origin"] == "official_worked_example" for r in results),
        "scope": "Authored deterministic regression scenarios; not an independent or comprehensive SRD reasoning accuracy estimate.",
        "results": results,
    }
    print(json.dumps(report, indent=2))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

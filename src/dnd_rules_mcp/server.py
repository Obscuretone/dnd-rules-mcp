"""Read-only MCP tools, source resources and a grounded adjudication prompt."""

import json
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .corpus import corpus
from .evaluator import evaluate
from .models import Check

INSTRUCTIONS = """Independent SRD 5.2.1 rules assistant. The source is a specific
Creative Commons SRD, not every D&D publication. Search results are candidates,
not rulings. Use get_rule to read full entries (follow next_offset when present).
Resolve the user's natural-language question using retrieved sources, then call
can_i_do with explicit structured facts for supported deterministic checks.
Never interpret no_violation_found as complete legality. Report unverified
interactions and missing facts; ask the user or DM instead of inventing rules.
Separate rules as written, interpretation, and declared house rules. Keep all
citations pinned to this SRD version. No tool mutates a campaign or rolls dice.
"""

mcp = FastMCP("D&D Rules MCP", instructions=INSTRUCTIONS)
READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def search_rules(
    query: str,
    limit: int = 6,
    mode: Literal["fts", "semantic", "hybrid"] = "hybrid",
    kind: Literal["rule", "spell", "section", "passage", "page", "entry"] | None = None,
) -> dict[str, Any]:
    """Search the entire SRD. Hybrid uses local embeddings plus full-text search.

    Return cited candidates, not an adjudication. Search classes, spells,
    monsters, equipment, feats, exploration and any other SRD material.
    """
    return corpus().search(query, limit=limit, mode=mode, kind=kind)


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def get_rule(rule_id: str, offset: int = 0, max_chars: int = 16000) -> dict[str, Any]:
    """Read a cited rule, spell, section or page. Accept an ID from search, an
    exact title, or page:N. Text is normalized PDF extraction, not an AI summary.
    Follow next_offset to retrieve long entries completely.
    """
    return corpus().get(rule_id, offset, max_chars)


def review_question(
    question: str, facts: Check | None = None, mode: str = "hybrid"
) -> dict[str, Any]:
    source = corpus()
    evidence = source.search(question, limit=8, mode=mode)
    if facts is None:
        check = {
            "verdict": "requires_interpretation",
            "reason": "Read the retrieved rules and identify applicable facts; this question has not been deterministically evaluated.",
        }
    else:
        check = evaluate(facts, source)
    return {
        "question": question,
        "check": check,
        "evidence": evidence,
        "instructions": "Use get_rule for the complete applicable rules, including exceptions. Distinguish checked constraints from interpretation and report anything still unverified. A retrieval hit is not proof of permission.",
        "source": source.stats(),
    }


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def can_i_do(
    question: str, facts: Check | None = None, mode: Literal["fts", "semantic", "hybrid"] = "hybrid"
) -> dict[str, Any]:
    """Research any SRD question and optionally run deterministic checks.

    Supported fact kinds: action_economy, movement, opportunity_attack,
    spellcasting, concentration, damage, roll, character. Include special_rules:
    [] only when no feature exceptions or house rules apply. Supply null for
    unknown facts. Other interactions are handled by the MCP host using the
    complete cited corpus, not by pretending a missing checker approved them.
    """
    return review_question(question, facts, mode)


@mcp.resource("srd://source")
def source_manifest() -> str:
    """Pinned version, source hash, license attribution and coverage."""
    return json.dumps(corpus().stats(), indent=2)


@mcp.resource("srd://page/{number}")
def source_page(number: int) -> str:
    """Normalized and original extracted page text for auditing."""
    return json.dumps(corpus().page(number), ensure_ascii=False)


@mcp.prompt()
def adjudicate(question: str) -> str:
    """A grounded research workflow for any question covered by the SRD."""
    return f"""Resolve this question using only SRD 5.2.1 plus explicitly supplied
house rules: {question}
1. Call search_rules with the question; find related definitions and exceptions.
2. Read relevant entries with get_rule, following pagination. Do not treat a
   search excerpt, remembered rule, or another edition as authoritative.
3. Ask for missing facts. Separate player declarations from verified source rules.
4. Call can_i_do with structured facts for any supported checks. Include relevant
   special_rules; never drop them to obtain a no_violation_found verdict.
5. Give the proposed ruling, exact rule IDs and PDF pages, reasoning, missing
   information, exceptions considered and unverified interactions. Label an
   interpretation or house-rule override explicitly. If the SRD cannot settle
   the question, say so and defer to the DM. Do not claim every rule was checked.
"""

"""CLI mirrors the MCP service; stdout contains only JSON for non-server commands."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from .corpus import corpus
from .evaluator import evaluate
from .models import Check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="Run a read-only MCP server on stdio")
    sub.add_parser("stats", help="Show source provenance and corpus coverage")
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--mode", choices=["fts", "semantic", "hybrid"], default="hybrid")
    search.add_argument("--kind", choices=["rule", "spell", "section", "passage", "page", "entry"])
    search.add_argument("--limit", type=int, default=6)
    get = sub.add_parser("get")
    get.add_argument("rule_id")
    get.add_argument("--offset", type=int, default=0)
    get.add_argument("--max-chars", type=int, default=16000)
    check = sub.add_parser("check")
    check.add_argument("facts", help="JSON file path, or - for stdin")
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--facts", type=Path)
    ask.add_argument("--mode", choices=["fts", "semantic", "hybrid"], default="hybrid")
    args = parser.parse_args()
    try:
        if args.command == "serve":
            from .server import mcp

            mcp.run(transport="stdio")
            return
        if args.command == "stats":
            result = corpus().stats()
        elif args.command == "search":
            result = corpus().search(args.query, args.limit, args.mode, args.kind)
        elif args.command == "get":
            result = corpus().get(args.rule_id, args.offset, args.max_chars)
        elif args.command == "check":
            raw = sys.stdin.read() if args.facts == "-" else Path(args.facts).read_text()
            result = evaluate(TypeAdapter(Check).validate_json(raw))
        else:
            from .server import review_question

            facts = TypeAdapter(Check).validate_json(args.facts.read_text()) if args.facts else None
            result = review_question(args.question, facts, args.mode)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, ValidationError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()

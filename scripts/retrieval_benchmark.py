"""Measured candidate recall on authored, page-labelled SRD research questions.

This is a retrieval smoke benchmark, not a ruling-accuracy benchmark. Relevant
alternatives outside the labelled page set can be unfairly counted as misses.
"""

import argparse
import json
import time

from dnd_rules_mcp.corpus import corpus

QUERIES = [
    ("Can I concentrate on two spells at the same time?", [179]),
    ("Can a gagged character cast a spell with verbal components?", [105]),
    ("Does teleporting provoke an opportunity attack?", [15, 190]),
    ("What happens with multiple advantages and one disadvantage?", [7, 8]),
    ("In what order do flat damage reduction resistance and vulnerability apply?", [17]),
    ("How much does a wizard pay to copy a spell into a spellbook?", [78]),
    ("Bag of Holding", [212]),
    ("What interrupts a Long Rest?", [185]),
    ("Multiclassing Proficiency Bonus total character level", [25]),
    ("How much movement does standing up from prone cost?", [186]),
    ("Can I cast a second spell using a spell slot on the same turn?", [105]),
    ("How far can a Fireball reach?", [131]),
    ("Does a natural 20 on an attack roll always hit?", [7]),
    ("How do I buy ability scores with 27 points?", [21]),
    ("What happens when an unconscious creature is attacked?", [191]),
    ("What does a rogue need to use Sneak Attack?", [61]),
    ("What can a wolf do in combat?", [364]),
    ("How do I attune to a magic item?", [102, 177]),
    ("How does drowning and suffocation work?", [189]),
    ("How much can a character carry?", [178, 177]),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["fts", "semantic", "hybrid"], default="hybrid")
    args = parser.parse_args()
    source = corpus()
    results = []
    for query, pages in QUERIES:
        start = time.perf_counter()
        hits = source.search(query, limit=8, mode=args.mode)["results"]
        # Count page-contained chunks, rules, spells and heading context. A very
        # broad bookmark span alone should not create an artificial success.
        found = any(
            h["end_page"] - h["page"] <= 2 and any(h["page"] <= p <= h["end_page"] for p in pages)
            for h in hits
        )
        results.append(
            {
                "query": query,
                "labelled_pages": pages,
                "hit_at_8": found,
                "seconds": round(time.perf_counter() - start, 4),
                "result_ids": [h["id"] for h in hits],
            }
        )
    print(
        json.dumps(
            {
                "mode": args.mode,
                "queries": len(results),
                "labelled_page_hits_at_8": sum(r["hit_at_8"] for r in results),
                "corpus_sha256": source.digest,
                "limitation": "Authored page-labelled retrieval checks, not independent validation or ruling accuracy. First query includes cold model/index cost.",
                "results": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

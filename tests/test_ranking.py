from dnd_rules_mcp.corpus import corpus


def test_core_definition_is_not_buried_by_common_spell_words():
    hits = corpus().search(
        "Can I concentrate on two spells at the same time?", mode="fts", limit=8
    )["results"]
    assert hits[0]["id"] == "concentration"


def test_semantic_results_can_map_to_named_entry_context(monkeypatch):
    c = corpus()
    monkeypatch.setattr(c, "_semantic", lambda query, limit: [("srd-5.2.1-p212-c01", 0.9)])
    hits = c.search("holding capacity", mode="semantic", kind="entry")["results"]
    assert hits
    assert all(h["kind"] == "entry" and h["page"] == 212 for h in hits)

import json

import pytest

from dnd_rules_mcp.corpus import corpus


def test_full_corpus_and_source():
    c = corpus()
    assert c.stats()["pages"] == 364
    assert c.stats()["spells"] == 339
    assert c.stats()["sections"] == 519
    assert len(c.source["sha256"]) == 64
    assert "Creative Commons Attribution 4.0" in c.source["attribution"]
    assert [p["page"] for p in c.data["pages"]] == list(range(1, 365))


def test_every_chunk_has_a_matching_page_passage():
    c = corpus()
    for chunk in c.data["chunks"]:
        assert chunk["text"] in c.page(chunk["page"])["text"]
        assert chunk["page"] == chunk["end_page"]


def test_curated_rules_match_source_pages():
    c = corpus()
    for rule in c.data["rules"]:
        text = " ".join(c.page(p)["text"] for p in range(rule["page"], rule["end_page"] + 1))
        assert rule["text"] in text, rule["id"]


def test_spell_entries_are_unique_and_complete_metadata():
    c = corpus()
    assert len({s["id"] for s in c.data["spells"]}) == 339
    for spell in c.data["spells"]:
        assert "Casting Time:" in spell["text"]
        assert "Duration:" in spell["text"]
        assert spell["fields"]["components"]
        assert 0 <= spell["fields"]["level"] <= 9
        assert 107 <= spell["page"] <= spell["end_page"] <= 176


def test_column_order_does_not_attach_steed_to_fireball():
    fireball = corpus().get("spell-fireball")
    assert "8d6 Fire damage" in fireball["text"]
    assert "Otherworldly Steed" not in fireball["text"]
    assert fireball["page"] == 131


@pytest.mark.parametrize(
    "query,kind,expected",
    [
        ("Fireball", "spell", "spell-fireball"),
        ("Shield", "spell", "spell-shield"),
        ("Wish", "spell", "spell-wish"),
        ("Wolf", "section", "wolf"),
        ("Wizard", "section", "wizard"),
        ("Dwarf", "section", "dwarf"),
        ("Bag of Holding", "entry", "bag-of-holding"),
    ],
)
def test_lookup_across_srd_domains(query, kind, expected):
    results = corpus().search(query, kind=kind)["results"]
    assert results
    assert expected in results[0]["id"]


def test_pagination_reconstructs_exact_entry():
    c = corpus()
    expected = c.documents["spell-wish"]["text"]
    parts = []
    offset = 0
    while True:
        result = c.get("spell-wish", offset, 200)
        parts.append(result["text"])
        if result["next_offset"] is None:
            break
        offset = result["next_offset"]
    assert "".join(parts) == expected


def test_search_input_is_not_fts_syntax():
    assert corpus().search('" OR NOT * ( : -')["results"] == []
    assert isinstance(corpus().search('fireball" OR *')["results"], list)


@pytest.mark.parametrize("query", ["", " " * 3, "a" * 2001])
def test_invalid_queries(query):
    with pytest.raises(ValueError):
        corpus().search(query)


def test_unknown_entry_cannot_be_invented():
    assert corpus().get("spell-make-up-a-rule")["status"] == "not_found"


def test_source_manifest_is_json_serializable():
    json.dumps(corpus().stats())

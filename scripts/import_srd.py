"""Rebuild the normalized, page-cited corpus from the pinned official SRD PDF.

Whitespace, PDF ligatures and line-end hyphenation are normalized. The original
extracted page text is retained for auditing. No generated paraphrases enter the corpus.
"""

import argparse
import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
URL = "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf"
ATTRIBUTION = (
    "This work includes material from the System Reference Document 5.2.1 "
    '("SRD 5.2.1") by Wizards of the Coast LLC, available at '
    "https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative "
    "Commons Attribution 4.0 International License, available at "
    "https://creativecommons.org/licenses/by/4.0/legalcode."
)
# Page range, start heading, end heading. These identify the actual SRD passages,
# not a hand-written substitute for the rules. Import fails on a missing anchor.
SECTIONS = {
    "actions": (13, 14, "Your Turn", "Communicating."),
    "bonus-actions": (10, 10, "Bonus Actions", "Reactions"),
    "reactions": (10, 10, "Reactions", "Social Interaction"),
    "improvising": (10, 10, "Player characters and monsters", "One Thing at a Time"),
    "movement": (14, 14, "Movement and Position", "Difficult Terrain"),
    "difficult-terrain": (14, 14, "Difficult Terrain", "Breaking Up Your Move"),
    "occupied-space": (14, 14, "Moving around Other Creatures", "Making an Attack"),
    "spell-slots-per-turn": (
        105,
        105,
        "One Spell with a Spell Slot per Turn",
        "Reaction and Bonus Action Triggers",
    ),
    "casting-triggers": (105, 105, "Reaction and Bonus Action Triggers", "Longer Casting Times"),
    "long-casting": (105, 105, "Longer Casting Times", "Range"),
    "components": (105, 105, "Components", "Verbal (V)"),
    "verbal": (105, 105, "Verbal (V)", "Somatic (S)"),
    "somatic": (105, 105, "Somatic (S)", "Material (M)"),
    "concentration": (179, 179, "Concentration", "Condition"),
    "crawling": (179, 179, "Crawling", "Creature"),
    "disengage": (181, 181, "Disengage [Action]", "Dodge [Action]"),
    "dodge": (181, 181, "Dodge [Action]", "Emanation [Area of Effect]"),
    "grappled": (182, 182, "Grappled [Condition]", "Grappling"),
    "opportunity-attacks": (185, 185, "Opportunity Attacks", None),
    "paralyzed": (186, 186, "Paralyzed [Condition]", "Passive Perception"),
    "petrified": (186, 186, "Petrified [Condition]", "Player Character"),
    "prone": (186, 186, "Prone [Condition]", "Reach"),
    "restrained": (187, 187, "Restrained [Condition]", "Ritual"),
    "stunned": (189, 189, "Stunned [Condition]", "Suffocation [Hazard]"),
}
# These headings sit on pages located during import; restrict to the glossary.
AUTO_SECTIONS = {
    "dash": ("Dash [Action]", "Dead"),
    "incapacitated": ("Incapacitated [Condition]", "Influence [Action]"),
    "unconscious": ("Unconscious [Condition]", "Unoccupied Space"),
}


def normalize(text):
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    text = re.sub(r"(?<=\w)[ \t]*-\s*\n\s*(?=\w)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def build(pdf, output, allow_source_change=False):
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if output.exists() and not allow_source_change:
        pinned = json.loads(output.read_text())["source"]["sha256"]
        if digest != pinned:
            raise ValueError("PDF differs from the pinned source; review before accepting a change")
    reader = PdfReader(pdf)
    if len(reader.pages) != 364:
        raise ValueError("Expected the 364-page English SRD 5.2.1")
    pages = []
    extracted = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", str(pdf), "-"], check=True, capture_output=True, text=True
    ).stdout.split("\f")
    if extracted[-1].strip() == "":
        extracted.pop()
    if len(extracted) != 364:
        raise ValueError("Poppler extraction did not preserve 364 page boundaries")
    spell_columns = []
    for x, width in ((30, 275), (305, 280)):
        column = subprocess.run(
            [
                "pdftotext",
                "-f",
                "107",
                "-l",
                "176",
                "-r",
                "72",
                "-x",
                str(x),
                "-y",
                "32",
                "-W",
                str(width),
                "-H",
                "720",
                "-enc",
                "UTF-8",
                str(pdf),
                "-",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split("\f")
        if not column[-1].strip():
            column.pop()
        if len(column) != 70:
            raise ValueError("Spell column extraction must preserve 70 pages")
        spell_columns.append(column)
    for number, raw in enumerate(extracted, 1):
        if 107 <= number <= 176:
            raw = spell_columns[0][number - 107] + "\n" + spell_columns[1][number - 107]

        # Poppler preserves column reading order, unlike this PDF's content stream.
        # Footer can appear between the columns; remove only this exact footer.
        raw = re.sub(rf"(?m)^\s*{number}\s*\n+System Reference Document 5\.2\.1\s*\n", "\n", raw)
        raw = re.sub(rf"(?m)^System Reference Document 5\.2\.1\s*\n+{number}\s*$", "", raw)
        pages.append({"page": number, "raw_text": raw, "text": normalize(raw)})
    sections = dict(SECTIONS)
    for key, (start, end) in AUTO_SECTIONS.items():
        matches = [p["page"] for p in pages[175:193] if start in p["text"]]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous glossary heading: {start}: {matches}")
        sections[key] = (matches[0], matches[0], start, end)
    rules = []
    for key, (first, last, start, end) in sections.items():
        text = " ".join(p["text"] for p in pages[first - 1 : last])
        begin = text.index(start)
        finish = text.index(end, begin + len(start)) if end else len(text)
        excerpt = text[begin:finish].strip()
        rules.append(
            {
                "id": key,
                "title": start,
                "page": first,
                "end_page": last,
                "text": excerpt,
                "kind": "rule",
            }
        )
    # Page-contained chunks keep citations precise. Overlap preserves local context.
    chunks = []
    for page in pages[4:]:
        words = page["text"].split()
        for n, start in enumerate(range(0, len(words), 180), 1):
            chunks.append(
                {
                    "id": f"srd-5.2.1-p{page['page']:03}-c{n:02}",
                    "title": f"SRD 5.2.1 page {page['page']}, passage {n}",
                    "page": page["page"],
                    "end_page": page["page"],
                    "text": " ".join(words[start : start + 220]),
                    "kind": "passage",
                }
            )
    result = {
        "source": {
            "version": "5.2.1",
            "language": "en",
            "url": URL,
            "sha256": digest,
            "pages": 364,
            "license": "CC-BY-4.0",
            "attribution": ATTRIBUTION,
            "normalization": "Poppler reading order, explicit spell columns; NFKC, whitespace and line-end hyphenation normalized; raw extraction retained",
        },
        "rules": rules,
        "chunks": chunks,
        "pages": pages,
    }
    from enrich_corpus import enrich

    result = enrich(result, reader, write=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    temp.replace(output)
    print(
        json.dumps(
            {"pages": len(pages), "rules": len(rules), "chunks": len(chunks), "sha256": digest},
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, nargs="?", default=ROOT / "data/SRD_CC_v5.2.1.pdf")
    parser.add_argument("--output", type=Path, default=ROOT / "src/dnd_rules_mcp/data/srd.json")
    parser.add_argument("--accept-source-change", action="store_true")
    args = parser.parse_args()
    build(args.pdf, args.output, args.accept_source_change)

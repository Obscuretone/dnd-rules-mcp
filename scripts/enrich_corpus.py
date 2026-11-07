"""Extract spell entries and the PDF's complete bookmark navigation."""

import bisect
import json
import re
from pathlib import Path

from import_srd import normalize
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


def enrich(data=None, reader=None, write=True):
    path = ROOT / "src/dnd_rules_mcp/data/srd.json"
    if data is None:
        data = json.loads(path.read_text())
    if reader is None:
        reader = PdfReader(ROOT / "data/SRD_CC_v5.2.1.pdf")
    raw = ""
    starts = []
    for page in data["pages"]:
        starts.append(len(raw))
        raw += page["raw_text"] + "\n"
    start = starts[106]
    end = starts[176]
    spell_text = raw[start:end]
    pattern = re.compile(
        r"(?m)^([^\n]{2,75})\n(?:[ \t]*\n)*(?=(?:Level [1-9] |"
        r"(?:Abjuration|Conjuration|Divination|Enchantment|Evocation|Illusion|Necromancy|Transmutation) Cantrip))"
    )
    matches = list(pattern.finditer(spell_text))
    spells = []
    for n, match in enumerate(matches):
        finish = matches[n + 1].start() if n + 1 < len(matches) else len(spell_text)
        text = normalize(spell_text[match.start() : finish])
        first = bisect.bisect_right(starts, start + match.start())
        last = bisect.bisect_right(starts, start + finish - 1)
        field_text = text.replace("Component:", "Components:")
        fields = {}
        labels = ["Casting Time", "Range", "Components", "Duration"]
        for i, label in enumerate(labels):
            stop = labels[i + 1] + ":" if i + 1 < len(labels) else None
            begin = field_text.index(label + ":") + len(label) + 1
            if stop:
                value = field_text[begin : field_text.index(stop, begin)].strip()
            else:
                # Duration is metadata on one physical line; body starts next line.
                original = spell_text[match.start() : finish]
                value = normalize(re.search(r"Duration: ([^\n]+)", original).group(1))
            fields[slug(label)] = value
        level = re.search(r"Level ([1-9]) ", text)
        fields["level"] = int(level.group(1)) if level else 0
        fields["concentration"] = "Concentration" in fields["duration"]
        spells.append(
            {
                "id": "spell-" + slug(match.group(1)),
                "title": match.group(1).title(),
                "kind": "spell",
                "page": first,
                "end_page": last,
                "text": text,
                "fields": fields,
            }
        )
    if len(spells) < 300:
        raise ValueError(f"Unexpectedly few spell entries: {len(spells)}")
    outline = []

    def walk(items, parents=()):
        previous = None
        for item in items:
            if isinstance(item, list):
                walk(item, (*parents, previous) if previous else parents)
            else:
                previous = item.title
                number = reader.get_destination_page_number(item)
                if number is not None:
                    outline.append(
                        {
                            "id": "section-" + slug(" ".join((*parents, item.title))),
                            "title": item.title,
                            "page": number + 1,
                            "path": list(parents),
                            "kind": "section",
                        }
                    )

    walk(reader.outline)
    for i, entry in enumerate(outline):
        next_page = next(
            (other["page"] for other in outline[i + 1 :] if other["page"] > entry["page"]), 364
        )
        entry["end_page"] = min(next_page, 364)
        entry["text"] = " ".join(
            p["text"] for p in data["pages"][entry["page"] - 1 : entry["end_page"]]
        )
        entry["extraction"] = (
            "Complete page range from official PDF bookmarks; may include adjacent entries."
        )
    headings = []
    for page_number, pdf_page in enumerate(reader.pages, 1):
        if 107 <= page_number <= 176:
            continue  # Spells already have exact entry boundaries and metadata.
        seen = set()

        def visitor(text, cm, tm, font, size, seen=seen, page_number=page_number):
            title = normalize(text)
            font_name = str((font or {}).get("/BaseFont", ""))
            scale = max(abs(tm[0]), abs(tm[3])) * size
            if "GillSans-SemiBold" not in font_name or scale < 11.5:
                return
            if len(title) < 3 or len(title) > 130 or title in seen:
                return
            seen.add(title)
            headings.append(
                {
                    "id": f"entry-{slug(title)}-p{page_number}",
                    "title": title,
                    "kind": "entry",
                    "page": page_number,
                    "end_page": page_number,
                    "extraction": "Named heading with full source-page context, including adjacent entries.",
                }
            )

        pdf_page.extract_text(visitor_text=visitor)
    data["entries"] = headings
    data["spells"] = spells
    data["outline"] = outline
    if write:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    if write:
        print(
            json.dumps(
                {"spells": len(spells), "bookmarks": len(outline), "named_headings": len(headings)},
                indent=2,
            )
        )
    return data


if __name__ == "__main__":
    enrich()

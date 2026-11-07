"""Version-pinned corpus, SQLite FTS5, and optional local dense retrieval."""

import hashlib
import json
import os
import re
import sqlite3
import threading
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

MODEL = "BAAI/bge-small-en-v1.5"
STOP_WORDS = set(
    "a an the i my can could do does is are it this that with and or to of in on for if how what when would not using have has as be at from me you".split()
)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


class Corpus:
    def __init__(self):
        content = files("dnd_rules_mcp").joinpath("data/srd.json").read_bytes()
        self.digest = hashlib.sha256(content).hexdigest()
        self.data = json.loads(content)
        self.source = self.data["source"]
        self.documents = {
            entry["id"]: entry
            for key in ("rules", "spells", "outline", "chunks", "entries")
            for entry in self.data[key]
        }
        for entry in self.data["entries"]:
            self.documents[entry["id"]]["text"] = self.data["pages"][entry["page"] - 1]["text"]
        for page in self.data["pages"]:
            self.documents[f"page:{page['page']}"] = {
                "id": f"page:{page['page']}",
                "title": f"SRD 5.2.1 page {page['page']}",
                "page": page["page"],
                "end_page": page["page"],
                "text": page["text"],
                "kind": "page",
            }
        self._lock = threading.RLock()
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.execute(
            "CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED, title, text, tokenize='porter unicode61')"
        )
        self._db.executemany(
            "INSERT INTO search VALUES (?, ?, ?)",
            [(d["id"], d["title"], d["text"]) for d in self.documents.values()],
        )
        self._by_kind_page = {}
        for doc in self.documents.values():
            if doc["kind"] in {"page", "entry", "section"}:
                for page_number in range(doc["page"], doc["end_page"] + 1):
                    self._by_kind_page.setdefault((doc["kind"], page_number), []).append(doc["id"])
        self._model = None
        self._vectors = None
        self._vector_ids = [
            d["id"] for key in ("rules", "spells", "chunks") for d in self.data[key]
        ]

    def stats(self) -> dict:
        return {
            "version": self.source["version"],
            "language": self.source["language"],
            "pages": len(self.data["pages"]),
            "spells": len(self.data["spells"]),
            "sections": len(self.data["outline"]),
            "named_entries": len(self.data["entries"]),
            "curated_rules": len(self.data["rules"]),
            "passages": len(self.data["chunks"]),
            "source_sha256": self.source["sha256"],
            "corpus_sha256": self.digest,
            "source_url": self.source["url"],
            "attribution": self.source["attribution"],
            "text_normalization": self.source["normalization"],
        }

    def get(self, rule_id: str, offset: int = 0, max_chars: int = 16000) -> dict:
        if offset < 0 or not 200 <= max_chars <= 30000:
            raise ValueError("offset must be nonnegative and max_chars must be 200..30000")
        document = self.documents.get(rule_id)
        if document is None:
            candidates = [
                d for d in self.documents.values() if d["title"].casefold() == rule_id.casefold()
            ]
            if len(candidates) == 1:
                document = candidates[0]
            elif len(candidates) > 1:
                return {
                    "status": "ambiguous",
                    "candidates": [self.reference(d["id"]) for d in candidates],
                }
            else:
                return {"status": "not_found", "rule_id": rule_id}
        text = document["text"]
        if offset > len(text):
            raise ValueError("offset exceeds document length")
        end = min(offset + max_chars, len(text))
        return {
            **self.reference(document["id"]),
            "status": "found",
            "text": text[offset:end],
            "offset": offset,
            "next_offset": end if end < len(text) else None,
            "complete": end == len(text),
            "total_chars": len(text),
            **({"fields": document["fields"]} if "fields" in document else {}),
            **({"extraction": document["extraction"]} if "extraction" in document else {}),
        }

    def reference(self, rule_id: str) -> dict:
        d = self.documents[rule_id]
        return {
            "id": rule_id,
            "title": d["title"],
            "kind": d["kind"],
            "page": d["page"],
            "end_page": d["end_page"],
            "version": self.source["version"],
            "source_sha256": self.source["sha256"],
            "url": f"{self.source['url']}#page={d['page']}",
        }

    def spell(self, name: str) -> dict | None:
        return self.documents.get("spell-" + slug(name))

    def page(self, number: int) -> dict:
        if not 1 <= number <= self.source["pages"]:
            raise ValueError("page must be 1..364")
        return {
            **self.data["pages"][number - 1],
            "version": self.source["version"],
            "url": f"{self.source['url']}#page={number}",
            "normalization": self.source["normalization"],
        }

    def _semantic(self, query: str, limit: int) -> list[tuple[str, float]]:
        try:
            import numpy as np
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise ValueError("Semantic dependencies are missing; run uv sync --locked") from exc
        cache = Path(os.environ.get("DND_RULES_CACHE", Path.home() / ".cache/dnd-rules-mcp"))
        cache.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if self._model is None:
                self._model = TextEmbedding(
                    model_name=MODEL, cache_dir=str(cache / "models"), threads=2
                )
            if self._vectors is None:
                vector_path = cache / f"{self.digest}-{slug(MODEL)}.npy"
                if vector_path.exists():
                    self._vectors = np.load(vector_path, allow_pickle=False)
                else:
                    # Dense vectors represent page-contained chunks and short rule/spell previews.
                    texts = [
                        self.documents[k]["title"] + "\n" + self.documents[k]["text"][:1300]
                        for k in self._vector_ids
                    ]
                    self._vectors = np.asarray(
                        list(self._model.passage_embed(texts, batch_size=32)), dtype=np.float32
                    )
                    temp = vector_path.with_name(f"{vector_path.stem}-{os.getpid()}.tmp.npy")
                    np.save(temp, self._vectors, allow_pickle=False)
                    os.replace(temp, vector_path)
                if self._vectors.shape != (len(self._vector_ids), 384):
                    raise ValueError("Invalid vector cache; delete the .npy cache and rebuild")
            vector = np.asarray(next(self._model.query_embed(query)), dtype=np.float32)
            # Cosine similarity, without relying on a model's normalization convention.
            scores = (
                self._vectors
                @ vector
                / np.maximum(np.linalg.norm(self._vectors, axis=1) * np.linalg.norm(vector), 1e-12)
            )
            indices = np.argsort(-scores)[:limit]
            return [(self._vector_ids[i], float(scores[i])) for i in indices if scores[i] >= 0.35]

    def search(
        self, query: str, limit: int = 6, mode: str = "fts", kind: str | None = None
    ) -> dict:
        if not query.strip() or len(query) > 2000:
            raise ValueError("query must contain 1..2000 characters")
        if not 1 <= limit <= 20:
            raise ValueError("limit must be 1..20")
        if mode not in {"fts", "semantic", "hybrid"}:
            raise ValueError("mode must be fts, semantic or hybrid")
        if kind not in {None, "rule", "spell", "section", "passage", "page", "entry"}:
            raise ValueError("kind must be rule, spell, section, passage, or omitted")
        tokens = list(dict.fromkeys(re.findall(r"[\w]+", query.casefold())))
        tokens = [t for t in tokens if t not in STOP_WORDS][:24]
        if not tokens:
            return {
                "results": [],
                "mode": mode,
                "version": "5.2.1",
                "purpose": "retrieval_candidates",
            }
        rankings = []
        candidate_limit = len(self.documents) if kind else 80
        if mode in {"fts", "hybrid"}:
            expression = " OR ".join('"' + token + '"' for token in tokens)
            with self._lock:
                rows = self._db.execute(
                    "SELECT id, bm25(search, 0, 5, 1) FROM search WHERE search MATCH ? ORDER BY 2 LIMIT ?",
                    (expression, candidate_limit),
                ).fetchall()
            rankings.append([r[0] for r in rows])
        similarities = {}
        if mode in {"semantic", "hybrid"}:
            dense = self._semantic(query, candidate_limit)
            if kind in {"page", "entry", "section"}:
                mapped = []
                for key, similarity in dense:
                    for mapped_key in self._by_kind_page.get(
                        (kind, self.documents[key]["page"]), []
                    ):
                        if mapped_key not in similarities:
                            mapped.append(mapped_key)
                            similarities[mapped_key] = similarity
                rankings.append(mapped)
            else:
                rankings.append([r[0] for r in dense])
                similarities = dict(dense)
        scores = {}
        for ranking in rankings:
            for rank, key in enumerate(ranking, 1):
                if kind is None or self.documents[key]["kind"] == kind:
                    scores[key] = scores.get(key, 0) + 1 / (60 + rank)
        # Exact title matches are useful for spell/monster lookup and never generated.
        for key, d in self.documents.items():
            if d["title"].casefold() == query.strip().casefold() and (
                kind is None or d["kind"] == kind
            ):
                scores[key] = scores.get(key, 0) + 0.1
        # Preserve direct matches to core rule concepts such as Concentration.
        # Broad words (spell/action/turn/time) should not drown out the definition.
        generic = {
            "spell",
            "spells",
            "action",
            "actions",
            "turn",
            "time",
            "two",
            "one",
            "use",
            "same",
            "another",
            "character",
            "creature",
            "feet",
        }
        concepts = [t for t in tokens if t not in generic]
        if concepts and kind in {None, "rule"}:
            title_expression = "title : (" + " OR ".join('"' + t + '"' for t in concepts) + ")"
            with self._lock:
                concept_ids = self._db.execute(
                    "SELECT id FROM search WHERE search MATCH ?", (title_expression,)
                ).fetchall()
            for (key,) in concept_ids:
                if self.documents[key]["kind"] == "rule":
                    scores[key] = scores.get(key, 0) + 0.02
        results = []
        for key in sorted(scores, key=lambda k: (-scores[k], k))[:limit]:
            d = self.documents[key]
            # Show the window around the first query term, not an unrelated page opening.
            positions = [
                m.start()
                for t in tokens
                for m in [re.search(r"\b" + re.escape(t) + r"\b", d["text"], re.I)]
                if m
            ]
            begin = max(0, min(positions, default=0) - 180)
            results.append(
                {
                    **self.reference(key),
                    "excerpt": d["text"][begin : begin + 1400],
                    "score": round(scores[key], 6),
                    **(
                        {"cosine_similarity": round(similarities[key], 4)}
                        if key in similarities
                        else {}
                    ),
                }
            )
        return {
            "results": results,
            "mode": mode,
            "version": "5.2.1",
            "purpose": "retrieval_candidates_not_rulings",
            "model": MODEL if mode != "fts" else None,
        }


@lru_cache(maxsize=1)
def corpus() -> Corpus:
    return Corpus()

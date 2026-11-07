# D&D Rules MCP

A complete, locally runnable MCP service for researching the **entire English
SRD 5.2.1** and checking explicit constraints against it. Search spells, monsters,
classes, feats, equipment, magic items, exploration rules and the rules glossary.
Every result links back to a page in the official source.

The package contains the full 364-page source extraction, 339 structured spell
entries, 519 PDF navigation sections, and 1,700 named heading entries. It does
not need a hosted database or an API key. Hybrid vector and full-text search runs locally by default.

The MCP client's language model handles general rules interpretation using the
retrieved sources. Deterministic checks cover eight families of constraints.
This is **not a complete game simulator or an automatic implementation of every
class feature**. A search hit never means an action was approved.

## Install and run

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Obscuretone/dnd-rules-mcp.git
cd dnd-rules-mcp
uv sync --locked
uv run dnd-rules stats
uv run dnd-rules search "Fireball" --kind spell
uv run dnd-rules get spell-fireball
uv run dnd-rules check examples/fireball.json
uv run dnd-rules serve
```

`serve` runs MCP over stdio. Keep its stdout connected to an MCP client rather
than typing into it as a shell. The other commands print JSON. Invalid input
exits with code 2 and an error on stderr.

Hybrid search downloads its embedding model and builds a local index on first
use. After that it works offline. For immediate offline use, pass `--mode fts`
to search/ask, or `mode: "fts"` to an MCP tool. Deterministic `check` needs no
model. PDF tools are needed only to rebuild the bundled corpus.

## Connect an MCP client

Use this configuration shape, replacing the directory with your checkout path:

```json
{
  "mcpServers": {
    "dnd-rules": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/dnd-rules-mcp", "run", "dnd-rules", "serve"]
    }
  }
}
```

The client must provide the language model and support MCP stdio. The server
provides source evidence and checks, not a hidden remote model. It offers an
`adjudicate` prompt describing the research workflow; clients without prompt
support can follow the tool descriptions instead.

## Three tools

| Tool | Purpose |
| --- | --- |
| `search_rules` | Full-text, semantic or hybrid retrieval across the complete corpus; optionally filter by kind. |
| `get_rule` | Fetch an exact rule/spell, a named section, heading context, or `page:N`. Long results provide `next_offset`. |
| `can_i_do` | Research a natural-language question and optionally evaluate structured facts. |

Resources: `srd://source` provides provenance and coverage; `srd://page/105`
provides both normalized and original extracted page text. All tools are
read-only and return structured JSON in addition to MCP text content.

Example questions include “Can I cast another spell after spending a spell slot
this turn?”, “What does a Bag of Holding hold?”, and “How does multiclassing affect
my Proficiency Bonus?” Ask about any SRD subject; retrieve the actual rules and
check relevant exceptions before giving an interpretation.

`get_rule` accepts an ID from search or an exact title. Ambiguous titles return
candidate IDs. Heading and bookmark entries include whole page context and can
contain neighboring entries; spell entries have explicit boundaries. A result
with `complete: false` is unfinished: continue with its `next_offset`.

## Deterministic checks

Pass `facts` to `can_i_do`, or use `dnd-rules check file.json`. The discriminator
is `kind`; the MCP tool schema describes every supported field.

| Fact kind | Checks | Deliberately not inferred |
| --- | --- | --- |
| `action_economy` | Action/Bonus Action/Reaction resource, timing, permission, trigger, Incapacitated conditions | Whether a class feature grants a new action or exception |
| `movement` | Effective supplied Speed, spent/extra movement, terrain, crawling, standing, immobilizing conditions, occupied destination | Map geometry, hazards, special speeds, reactions along the path |
| `opportunity_attack` | Reaction, visibility, reach exit, own movement, Disengage and teleportation | Weapon exceptions, actual hit or damage |
| `spellcasting` | All 339 spell entries; casting resource, slot level/availability, one slot spent per turn, components, numeric range, replacement Concentration | Target eligibility, preparation limits, effect geometry and spell-specific interactions |
| `concentration` | Incapacitation, replacement, damage save DC including its cap, supplied save result | Unreported effects and how save modifiers were obtained |
| `damage` | Flat reduction, Resistance, rounding, Vulnerability, Immunity | Which defenses actually apply to the damage |
| `roll` | Advantage/Disadvantage cancellation, supplied d20 results and modifier, attack-only natural 1/20 rules | Rerolls, special critical ranges, determination of modifiers |
| `character` | All 12 SRD classes, total level, Proficiency Bonus, multiclass ability prerequisites, point buy/standard array | Full character-sheet legality, subclasses, feats, equipment, HP and spell progression |

Each response lists `checked`, `unverified`, citations, findings, missing facts
and calculated effects. `no_violation_found` means exactly that for those checks
and supplied facts; it is not blanket permission. Other verdicts are
`disallowed`, `needs_information`, and `requires_dm_ruling`. A free-form question
without structured facts returns `requires_interpretation` plus evidence.

Unknown facts are `null`, never silently false. `special_rules` must be supplied:
`[]` explicitly selects the base rules; described exceptions or house rules
require interpretation. Exceptions are returned to the host and DM rather than
silently ignored. Unsupported or invented spells cannot receive approval.

A successful spellcasting check is **not** proof the targets or spell-specific
requirements are legal. The client's ruling must also resolve the explicitly
listed unverified requirements from source evidence and the game's facts.

## Local vector and hybrid search

```sh
uv run dnd-rules search "maintain two concentration spells" --mode hybrid
```

First use downloads `BAAI/bge-small-en-v1.5`, then builds cached 384-dimensional
vectors. Later searches use the local cache. No query is sent to an embedding
API. Use `DND_RULES_CACHE` to choose the cache directory; the default is
`~/.cache/dnd-rules-mcp`.

Full-text search uses SQLite FTS5 with the Porter tokenizer. Hybrid retrieval
combines BM25 and cosine-ranked dense results with reciprocal-rank fusion. Dense
inputs are page-contained passages plus short rule/spell previews; full entries
remain available through `get_rule`. The cosine floor is a heuristic, not a
calibrated confidence score. Ranking scores are not probabilities of correctness.

## Verification

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python scripts/benchmark.py
# Real-model retrieval run (downloads a model on first use):
uv run python scripts/retrieval_benchmark.py --mode hybrid
```

The published scenario fixture contains 89 explicit regression scenarios. Four
are based on worked examples in the SRD (movement, Difficult Terrain, damage
ordering and multiclass Proficiency Bonus); other cases probe boundaries,
missing facts, conditions and paired changes. These are project-authored tests,
not independent expert validation or a general rules-accuracy percentage.

Tests also exercise the real MCP stdio handshake, all tools, resources,
prompts, strict input validation, citation resolution, cross-domain lookup,
full entry pagination, page coverage, and a column-order extraction regression.

## Rebuild the corpus

The rules JSON ships in the package. Rebuilding it requires Poppler's
`pdftotext` and the locked development dependencies:

```sh
curl --fail --location https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf -o data/SRD_CC_v5.2.1.pdf
uv run python scripts/import_srd.py
```

The importer checks the PDF's SHA-256 and 364-page count, rebuilds spell metadata
and navigation, and atomically replaces the corpus after successful parsing.
A changed source requires explicit `--accept-source-change` and review.
PDF text normalization and bookmark/heading context are disclosed. The linked
PDF remains the source for layout-sensitive tables and difficult passages.
Never merge another rules edition or unofficial ruling into this pinned corpus.

## License

Code: MIT. SRD-derived rules: CC BY 4.0 with attribution and modification notices.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The model and
software dependencies have their own licenses. This is an independent project.

The measured development snapshot, raw scenario outcomes and hybrid/full-text
retrieval comparison are published in [validation/](validation/). The retrieval
queries were used during development; they are not an independent held-out
accuracy estimate.

# Contributing

Keep source text separate from interpretations. Every deterministic rule needs an
SRD version, a source page, a reviewed scenario and a paired boundary or failure
case. Missing facts must not become false values or an approval. General rulings
must distinguish checked constraints from unresolved interactions.

Run `uv run pytest -q`, `uv run ruff check .`, and
`uv run ruff format --check .` before submitting a change. Run
`uv run python scripts/benchmark.py` when changing evaluators. Search changes
should include a measured retrieval comparison rather than only anecdotal hits.

Preserve the attribution and modification notices for the CC BY 4.0 corpus. Do
not add content from paid rulebooks, other editions, forum answers or house rules
to the official SRD corpus. Feature exceptions need explicit source evidence.

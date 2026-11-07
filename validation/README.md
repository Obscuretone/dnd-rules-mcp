# Validation snapshot — November 7, 2026

- 119 automated tests passed locally and in GitHub Actions on Python 3.11 and 3.13.
- 89 authored deterministic scenarios passed, including four scenarios drawn from
  worked examples in SRD 5.2.1 and additional boundary/missing-fact variants.
- The hybrid search path used the real local `BAAI/bge-small-en-v1.5` embedding
  model, not mocked vectors. The MCP default hybrid call was also exercised
  against a live stdio server and returned the Concentration rule.
- On 20 authored retrieval queries, a labelled relevant page appeared in the top
  eight results for 20 hybrid queries and 18 full-text-only queries.
- The warm-index hybrid run had a median request time of about 10.5 ms on the
  development machine. This is not a hardware-independent latency guarantee;
  cold model loading and initial vector generation are separate costs.
- A built wheel was installed in an isolated environment and its bundled corpus
  and spell lookup were verified. The wheel includes the SRD attribution notice.
- Rebuilding from the pinned official PDF produced a byte-identical corpus.

These are **development regression checks**, not an independent rules accuracy
study. The retrieval questions were used during development and are not a held-out
test set. Retrieval relevance labels are incomplete: valid alternative sources
can be counted as misses. A top-eight page hit is not a correct legal/action
ruling. The deterministic suite covers the implemented checks, not the entire
space of possible SRD interactions or the MCP client's reasoning quality.

`rules.json` records the scenario outcomes and source fingerprint.
`retrieval-hybrid.json` and `retrieval-fts.json` record the queries, page labels,
returned IDs, timings and corpus fingerprint. Run the scripts documented in the
main README to reproduce against your checkout and hardware. Initial vector
index generation can take several minutes and model download requires network
access; subsequent queries use the local cache.

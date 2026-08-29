# tools/compare — cross-product comparison

The "which product is strong at what" half of CraftBench. The harness
(`tools/run-agent`) runs the same scrubbed tasks across products and writes one
`result.json` per product × task; this aggregates them into the **per-capability-
bucket** taxonomy verdict (SC-003).

```sh
# all runs under runs/
python3 tools/compare/compare_products.py --runs-dir runs --out compare.json

# or specific result.json files
python3 tools/compare/compare_products.py runs/A/result.json runs/B/result.json
```

Output: a markdown table (capability × product → deterministic pass-rate `n_pass/n`,
plus the R2 advisory mean alongside) + each product's strong / weak capabilities +
the per-capability leader. A JSON form (`--out`) carries the same.

**Gate-driven, advisory-aside.** The score is the deterministic `overall`
(PASS/FAIL) — FR-020d: the R2 advisory is reported next to it but never folded into
the pass-rate. Per-capability normalization avoids "one product wins because it's
good at the oversampled bucket" (the leaderboard-schema caveat).

Pure stdlib — no UE, no network; runs on `result.json` files alone.
Tests: `cd tools/compare && python3 -m unittest tests.test_compare`.

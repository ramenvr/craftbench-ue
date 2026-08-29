# L3 — render-context structural verification + screenshot (PIE)

L3 grades tasks whose pass condition involves a **visible artifact** (a widget
renders, a particle spawns, a material reads on a mesh). Unlike L2-introspect
(headless editor-Python, no render), L3 runs a **real-RHI PIE functional test**:
the engine ticks every frame, so the scene actually renders and a screenshot has
real content (a one-shot editor-Python capture renders BLACK — no frame advances).

**There are no Python scripts in this directory.** An L3 fixture is a verifier-only
`ACraftBenchFunctionalTest` subclass in `Source/CraftBenchTests/`. Template:
`Source/CraftBenchTests/RenderProbeFunctionalTest.{h,cpp}` —

- `SetCheckpointSchedule({0.25, 0.6})` (capture after a few PIE frames, assert after flush),
- `OnCheckpoint(0)` → `FScreenshotRequest::RequestScreenshot(<Saved>/CraftBench/l3_*.png, false, false)`
  (stock-UE PIE viewport capture — never Aura),
- `OnCheckpoint(1)` → `AssertTrue(file exists)` + per-task structural predicates (the deterministic GATE).

Declare it in the task's unified block:

    ## Verifier layers
    - L1
    - L3 (fixtures: L_RenderProbe :: ARenderProbeFunctionalTest)

`L3RenderLayer` runs it via `run_l2(use_nullrhi=False)`, the structural verdict is
the gate, and the screenshots (`<workdir>/Saved/CraftBench/*.png`) are handed to the
R2 visual-advisory track (`ctx.advisory_out["L3_visual"]`). Pixel/SSIM comparison
stays OUT of the gate per FR-020d. Validated live 2026-06-02 (L_RenderProbe → 2.4MB
content PNG, status=pass).

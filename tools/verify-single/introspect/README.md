# tools/verify-single/introspect/

Verifier-owned editor-Python introspection scripts for the **L2-introspect**
layer (`../layers/l2_introspect.py`). Each task that uses structural asset
verification ships one script here, named in its `## Verifier introspection`
task-spec section.

These scripts are **verifier code, not substrate** — they live under `tools/`
(never copied into the agent's workspace), so the agent cannot see or edit them,
and they need no entry in the verifier hash manifest. The runner invokes the named script via
`UnrealEditor-Cmd -ExecutePythonScript=` against the workdir project; the script
loads the agent's generated asset (from the writable `Content/Tasks/<id>/`
carve-out) and prints a verdict block (see `../layers/INTROSPECT_CONTRACT.md`).

Copy `../layers/introspect_template.py` to start a new one.

Current scripts: **`umg_image_brush_bound.py`** (the `umg-image-brush-bound`
task's gating L2I check) and the task-agnostic **`save_all_dirty.py`** helper
below. (The `mat_emissive_pulse.py`, `animbp_locomotion_state_machine.py`,
`bp_collectible_coin.py`, and `bp_gas_launch.py` scripts were removed in the
2026-07-08 fresh-start cull along with their tasks — git history has them.)

## Blueprint deliverables (`.uasset` capture)

BP-heavy tasks ship a Blueprint deliverable instead of a source file. One piece
makes those gradeable:

- **`save_all_dirty.py`** — run by `run_task.py --capture-assets` (via
  `../asset_capture.py`) BEFORE the deliverable snapshot. It flushes every dirty
  in-memory content package to disk (`EditorLoadingAndSavingUtils.save_dirty_packages`
  / `EditorAssetLibrary.save_all_dirty`), so agent-authored Blueprints become
  real `.uasset` files. The capture then sweeps ALL of `Content/` (not just
  `Content/Tasks/`) for `.uasset`/`.umap`, honoring the manifest deny prefixes
  (`Content/Maps/` stays out). The `asset_writable` list in `AGENT_WRITABLE.json`
  declares which Content folders the sweep + sandbox accept for assets.

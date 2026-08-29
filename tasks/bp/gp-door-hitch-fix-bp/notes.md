# gp-door-hitch-fix-bp — verifier-builder notes

g2-6 port (scaleup slate T2.3, the Edit(Debug) opener), built 2026-08-12.
Companion docs: `task.md` (spec + provenance), `discrimination/MATRIX.md`
(oracle + requirements table). This file pins the two binaries
property-by-property, the authoring lane actually used (it differs from
the wave-3 recipe in one load-bearing way), and the fixture constants.

## 1. The BUGGY baseline, property-by-property

`UE-projects/ThirdPerson/Content/Tasks/gp-door-hitch-fix-bp/BP_Door.uasset`
(64,229 bytes):

- Parent `Actor`; SCS: `DoorMesh` (`StaticMeshComponent`, engine cube,
  relative location (0, 100, 110), scale (0.12, 2.0, 2.2)).
- Variable `bOpen` (bool, default false).
- Timeline `DoorTimeline`: length 1.5 s, no loop/autoplay; float track
  `DoorAngle`, keys (0.0, 0.0) and (1.5, 90.0), cubic auto-tangents.
- EventGraph:
  - `Interact` (parameterless custom event) → Branch on `bOpen`.
  - False (closed → open): Set `bOpen`=true → **`PlayFromStart`** ← the
    defect, half 1: restarts the motion at t=0 even mid-close.
  - True (open → close): Set `bOpen`=false → **`ReverseFromEnd`** ← the
    defect, half 2: snaps the position to t=1.5 before playing back.
  - `Update` → `K2_SetRelativeRotation(DoorMesh, MakeRotator(Yaw=DoorAngle))`.
- From REST both legs behave correctly (position happens to be at the
  restarted endpoint), which is why the baseline passes the rest-behavior
  gates and fails ONLY mid-swing — the targeted-debug shape the slate row
  wanted.

## 2. The reference fix

`reference/Content/Tasks/gp-door-hitch-fix-bp/BP_Door.uasset` (65,101
bytes) — identical except the two exec routes:

- Set `bOpen`=true → **`Play`** (resume forward from current position)
- Set `bOpen`=false → **`Reverse`** (resume backward from current position)

That is the entire fix: two pin rewires. (An agent may instead rebuild
the motion any other way — every gate is behavior; see MATRIX residuals.)

## 3. The authoring lane actually used (2026-08-12) — READ THIS BEFORE REUSING THE WAVE-3 RECIPE

The wave-3 runbook (stack editor + CB_UPROJECT pivot) FAILED here twice
for a new reason: the stack-guard janitor reaps a stack whose bring-up
shell exits (no session anchor — an agent-driven background shell can
never be one), and separately the DESKTOP Aura client auto-launches its
own headless editor on its last-known project at startup, which killed
the worktree editor and squatted the bridge with a wrong-project editor.
The lane that WORKS for agent-driven interactive authoring:

1. `CB_STACK_GUARD=0 CB_UPROJECT=<worktree>.uproject cb up --drive-ready`
   (the documented guard opt-out, the repo conventions §stack-auto-recovery; you now
   OWN the teardown — `cb down` when finished, no exceptions).
2. Desktop Aura client running (it is the MCP auth source; `:41200`).
   If its auto-launched editor is on the wrong project:
   `shutdown_headless(force=True)` then
   `launch_unreal_project(<worktree>.uproject)` — the CLIENT-owned
   headless editor mounts the bridge (`:41250` port file in the
   installed client's `.Aura`) and the whole session-MCP lane is then
   self-consistent. Bridge-up took ~8 min (full editor, -RenderOffScreen).
3. Author: python (BlueprintFactory + SubobjectDataSubsystem) →
   `edit_blueprint` (variables) → `edit_timeline`
   (`unreal.AuraTimelineStatics`: create → settings → configure_float_track
   → finalize → **get_timeline_info for the REAL node/pin names**) →
   `add_blueprint_node_to_strand` (8 nodes, one call) →
   `set_node_pins_defaults` → `connect_blueprint_nodes` (10 links, one
   call) → `compile_blueprint`.
4. **Every write lands in
   `Intermediate/Sandboxes/AuraSandbox/Sandbox/Game/...`** — promote by
   file copy (BPs and the map are path-stable: same /Game package path).
5. Stage/rewire/harvest for the two variants: copy the sandbox .uasset
   (BASELINE bytes) → disconnect 2 + connect 2 (the fix) → compile →
   copy again (FIXED bytes) → promote BASELINE to the substrate,
   FIXED to reference/.

**API law caught live (record beside the wave-3 pin-name laws): the
timeline's resume-from-end exec pin is `ReverseFromEnd` — the product's
own best-practices doc says "ReverseFromStart", which does not exist.**
Wire from `get_timeline_info()`'s pins array, never from the doc prose.
This was also the repo's first live end-to-end `AuraTimelineStatics`
timeline authoring (the vendor-plugin recon found no prior run anywhere).

## 4. Fixture constants (mirror of DoorHitchFunctionalTest.cpp)

| constant | value | why |
|---|---|---|
| QuietTolDeg | 2.0 | settle jitter allowance before any Interact |
| MinSwingDeg | 45.0 | "open" floor (half the 90-deg swing) |
| ClosedTolDeg | 10.0 | "closed" tolerance, both close gates |
| MidSwingMinDeg | 15.0 | the reversal must fire visibly mid-swing |
| TeleportAngleDeg | 12.0 | smooth ~1 deg/tick vs snap 40–90 deg/tick; 4x margin both ways |
| TeleportLocUnits | 50.0 | translation-teleport analog |
| checkpoints | 0.5 / 2.6 / 3.1 / 5.2 / 5.7 / 6.45 / 8.6 | phase schedule (task.md) |

Monitor: Tick override (Super first — the base checkpoint clock stays the
sequencer), armed cp0→cp6, per static-mesh part world-quat angular
distance + world location delta vs previous tick; max recorded with
timestamps. No gameplay tags anywhere in the fixture (the Editor-module
native-tag hazard, task #34, is documented — actor tags are plain FNames).

## 5. Status / remaining

- Fixture C++ built clean (UBT 91 s, zero new warnings) — committed-track.
- Baseline + reference + map authored, sandbox-promoted, graph read-back
  verified (`get_asset_graph`: fix wiring `Play`/`Reverse`, restart pins
  empty).
- Camera plan (`cameras.json` (the camera-plan lane; not part of this release)): TODO with the discriminate sweep (the
  scene exists — checklist step 5 applies to this task).
- Validation legs (reference PASS / empty FAIL-at-teleport) + registry
  bumps (56 tasks; +1 `docs/MAPS.md` row — the .umap count anchor) +
  refgate: recorded in MATRIX §Status as they run.

## Capability bucket corrected 2026-08-17

This spec read `capability_bucket: Gameplay Programming`. It now reads
**`Debug & Refactoring`**, because that is what the task is: it ships a
deliberately-broken baseline and asks for a repair.

**Why it mattered beyond tidiness.** The corpus was misdescribing its own
coverage. Measured across all 62 specs on 2026-08-17, `Debug & Refactoring` held
exactly ONE task — `kp-engine-source-search`, a *search* task — while both
genuine Edit/Debug tasks sat under `Gameplay Programming` (which already holds 45
of 62). So any coverage table built from this field said the benchmark had one
debug-ish task and no fix tasks, when it has two fix tasks. The dossier had
already flagged the symptom ("its one Debug & Refactoring row sits on a SEARCH
task rather than on either fix task"); this is the fix.

**Scope:** metadata only. `capability_bucket` is not agent-visible and has no
grading consumer (`spec.py` parses it; nothing scores on it), so this is not a
D6 contract change and prior measurements stay comparable. It does move the task
tree sha, so this task's refgate certificate re-keys and is re-gated with the
wave it ships in.

**Left for the owner:** whether `kp-engine-source-search` should stay in
`Debug & Refactoring` or move (engine-source literacy is arguably Tools &
Pipeline). Not guessed here — with these two tasks added the bucket no longer
misrepresents the corpus, so its membership is a taxonomy preference rather than
a defect.

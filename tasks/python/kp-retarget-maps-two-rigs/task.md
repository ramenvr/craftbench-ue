---
id: kp-retarget-maps-two-rigs
substrate: ThirdPerson
set: python
tier: T2
capability_bucket: Asset Management
category: other
layers: [L1, L2I]
introspect: [kp_retarget_maps_two_rigs.py]
---

# kp-retarget-maps-two-rigs

**The retargeting lane** (from a row in an earlier internal task list, not
shipped). No live task samples animation retargeting at all — every `retarget`-shaped hit
in the tree is unrelated prose. This row asks an agent to build the pipeline
from nothing: two rig definitions describing two different characters, and a
retargeter that maps one onto the other.

## Primary concept

- `animation-retargeting` — describing two skeletons in a common vocabulary so
  motion authored for one can drive the other
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine)

The load-bearing capability is **cross-asset agreement under a shared
vocabulary**: two independently-authored rig descriptions must use the *same
chain names*, or the retargeter that consumes them maps nothing. Adjacent
in-scope concept: `asset-creation`. Neither name appears in the prompt.

## Prompt given to the agent

> This project ships two character bodies:
> `Content/Characters/Mannequins/Meshes/SKM_Manny_Simple` and
> `Content/Characters/Mannequins/Meshes/SKM_Quinn_Simple`. Both are inputs —
> read them, change nothing about them.
>
> Build a motion-transfer setup in
> `Content/Tasks/kp-retarget-maps-two-rigs/`, using exactly these names:
>
> - `IK_TaskSource` — a rig description for the first body.
> - `IK_TaskTarget` — a rig description for the second body.
> - `RTG_TaskMotion` — a motion-transfer asset that reads the first rig
>   description and writes the second.
>
> Both rig descriptions must name the bone that motion is measured from, and
> both must declare a bone run called `Spine` and a bone run called `LeftArm`.
> Use whatever bones you judge correct for each body — which bones a run spans
> is yours to choose and is not graded; the names `Spine` and `LeftArm` are
> fixed, and both descriptions must use them.
>
> Finish with the motion-transfer asset in a state where each of those two
> named runs on the target actually resolves to a run on the source. Creating
> the three assets is not sufficient on its own — a motion-transfer asset can
> exist, name both rig descriptions, and still resolve nothing.
>
> Save all three where they are named.

## Workspace state pre-task

Substrate content that **exists**: nothing under
`Content/Tasks/kp-retarget-maps-two-rigs/` — this task ships **no baseline**.
The two skeletal meshes it names are stock template content under
`Content/Characters/`, which is read-only to the agent by the sandbox manifest.

Files that **do not exist** (the correct end state produces all three):

- `Content/Tasks/kp-retarget-maps-two-rigs/IK_TaskSource.uasset`
- `Content/Tasks/kp-retarget-maps-two-rigs/IK_TaskTarget.uasset`
- `Content/Tasks/kp-retarget-maps-two-rigs/RTG_TaskMotion.uasset`

Out of scope: no C++, no level, no placed actor, no functional test, no config.

## Verifier specification

Layer choice: **L1 + L2I**. Every graded property is a static property of the
submitted assets. No PIE, no world.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

Content-only submission, so L1 is a precondition, never a correctness signal.

### L2I — Structural assertion

`tools/verify-single/introspect/kp_retarget_maps_two_rigs.py`, headless under
`-nullrhi`, read-only. **Exactly 8 checks on every leg.** PASS requires all 8:

```text
source_rig_present                C1  IK_TaskSource exists, class is the rig-
                                      description class   [LIVE - absent at start]
target_rig_present                C2  likewise IK_TaskTarget
retargeter_present                C3  likewise RTG_TaskMotion
source_rig_has_retarget_root      C4  its measured-from bone is set (non-empty)
target_rig_has_retarget_root      C5  likewise
both_rigs_declare_required_chains C6  BOTH rigs declare bone runs named `Spine`
                                      and `LeftArm`
retargeter_references_both_rigs   C7  its two rig references are exactly
                                      IK_TaskSource and IK_TaskTarget
chain_mapping_resolves            C8  each required run on the target resolves
                                      to a run on the source
```

**Why this task needs no baseline, and why that is a strength.** Its sibling
`kp-motion-set-shares-one-rig` had to ship a task-owned skeleton, because UE
refuses to create its assets unanchored and the anchor checks would otherwise
have been dead. The opposite holds here: the substrate ships **no rig
description and no motion-transfer asset anywhere** (verified against
`git ls-files`), so there is nothing to duplicate and every check is live
against an empty start.

**C8 is the check that earns the row, and it is not decoration.** Measured
2026-08-14: a motion-transfer asset created by the stock factory has an **empty
internal stack**, and until that stack is populated, pointing it at both rig
descriptions and asking it to auto-map both silently succeed while resolving
nothing. So a submission can build both rigs correctly, create the asset, name
both rigs, call auto-map, and still fail C8 — which is exactly the
`retargeter-without-ops` discrimination leg. The prompt discloses this
("Creating the three assets is not sufficient on its own") without naming the
mechanism, per Hard Rule #2.

**Dead-gate audit** (house law). All 8 checks are LIVE: the empty submission
scores a genuine **0/8** (nothing exists, so every downstream check reports its
subject missing). No check equals a default or baseline state.

**Ungraded by design, disclosed in the prompt**: which bones each run spans.
Grading them would enforce an undisclosed anatomical literal against conforming
work — the F5 shape — and the capability under test is building the pipeline,
not choosing anatomy. The run NAMES are graded because they are the shared
vocabulary the two rigs must agree on, and the prompt fixes them verbatim.

**Score granularity.** `report.json` carries `x/8`. Reported, not gating.

## Reference solution metadata

- LOC range: **0** lines of shipped code; the deliverable is three assets.
- Files touched: 3 created.
- Senior-dev hours: 0.5–1.0 — the real work is knowing that the motion-transfer
  asset needs its stack populated before any mapping resolves.

## Anti-gaming notes

1. **Create the three assets and stop.** *Failure mode*: three correctly-named,
   correctly-classed assets and nothing configured — the cheapest submission
   that looks complete. *Defense*: C4–C6 require roots and named runs on both
   rigs; C8 requires the mapping to resolve. Variant `rigs-without-chains/`.
2. **Configure everything except the internal stack.** *Failure mode*: both rigs
   fully built, the transfer asset created, both rigs named on it, auto-map
   called — and every mapping still resolves to nothing, because the stack was
   never populated. This is the *plausible* wrong answer, not a lazy one.
   *Defense*: C8 fails with `RETARGET_MAPPING_UNRESOLVED chains=`. Variant
   `retargeter-without-ops/`.
3. **Disagreeing run names between the two rigs.** *Failure mode*: each rig is
   internally sensible but they use different names, so nothing maps. *Defense*:
   C6 requires BOTH rigs to declare both fixed names, and C8 catches the
   consequence independently.
4. **Point the transfer asset at the wrong rigs.** *Failure mode*: reference
   stock content, or the same rig twice. *Defense*: C7 compares both references
   against the exact expected paths (`RETARGET_REFS_WRONG source= target=`).
5. **Accepted residual, recorded honestly**: bone spans are ungraded, so a run
   named `Spine` spanning arbitrary bones passes. This is disclosed in the
   prompt and is deliberate — see *Ungraded by design*. A submission whose runs
   are anatomically wrong but correctly named and mapped is indistinguishable
   here from a careful one.

## Hidden invariants

- The check denominator is fixed at 8 on every leg, including an empty
  submission (a genuine 0/8) and a no-editor-python import.
- The chain mapping is read via the per-chain accessor. It is deliberately NOT
  read via the retargeter's chain-settings collection: UE 5.8 defines that class
  in a deprecated header and it returns EMPTY regardless of state, so a grader
  built on it would report every submission — including a perfect one — as
  having no mappings. The modern mapping struct is not exposed to editor Python
  at all. Both facts were established by live spike, not from documentation.
- Every verifier-side failure path emits a distinct token from the grader's
  `UNCREDITED_TOKENS` tuple, which appears in **no** discrimination-matrix row.
- Echoed asset paths and class names are agent-controlled, so they are
  marker-stripped and length-capped before reaching a check detail.

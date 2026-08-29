# Discrimination matrix

Status: Editor and Game compilation/linkage are green. Admission assets/map and
five exact-one real-RHI mechanism legs are green. The final map now cold-reads
with exact class-derived Quartz/Violet actor labels and enumerates exactly the
two task-declared test paths; map SHA-256 is
`4B825F6735032628D583659C4738D2006DDA4B26F2B8AA7FE98A7979C7B0F200`.
Five reference processes per fixture produced stable finite metrics. Five
empty-baseline processes per fixture produced the exact graded
`BothHandsTrackSamePhysicalHandle: compiled runtime ControlRig count=0` failure,
zero harness failures, and production empty L2I was 0/3. Those distributions
freeze the conservative bars at displacement/projection `>=4 cm`, hand error
`<=18 cm`, Control Rig target error `<=2 cm`, and feet/pelvis translation/angular
error `<=8 cm` / `<=15 deg`. After the freeze, a fresh canonical NullRHI
production run passed both L2 fixtures and all three L2I checks. Official
refgate and owner play remain before promotion.

| Submission / control | Expected L1 | Expected L2 | Expected L2I | Named discrimination |
|---|---:|---:|---:|---|
| Complete reference: base sequence -> runtime Control Rig; two declared controls drive two FABRIK arms | PASS | 8/8 total (4 gates x Quartz/Violet) | 3/3 | All named gates pass; final sentinel required. |
| Empty baseline: controls declared but no RigVM solve, base sequence goes directly to Result | PASS | FAIL | FAIL | `RuntimeControlRigComposesOverBasePose`; hands do not follow physical endpoints. |
| Handle attached to left hand | PASS | FAIL | variable | `HandleMovesThroughRealConstraint` via exact owner/component/constraint identity. |
| Direct Transform/Modify Bone for both hands | PASS | may visually approach | FAIL | `NoDirectTransformTwoBoneIKOrMirror`. |
| Two Bone IK nodes instead of runtime Control Rig | PASS | may visually approach | FAIL | `RuntimeControlRigComposesOverBasePose` and `NoDirectTransformTwoBoneIKOrMirror`. |
| One left target mirrored to the right through a boolean/branch | PASS | FAIL on asymmetric fixtures | FAIL | `RigUsesIndependentHandControls` and `NoDirectTransformTwoBoneIKOrMirror`. |
| Decorative disconnected Control Rig/FABRIK nodes plus direct pose substitute | PASS | variable | FAIL | Result/Forward Solve reachability in the first two L2I gates. |
| Prerecorded hand pose or keyed handle path | PASS | FAIL | FAIL/variable | `TrackingRespondsToSecondImpulseDirection` plus real constraint force/body identity. |
| Whole character snapped to handle | PASS | FAIL | variable | `FeetAndPelvisPreserveBasePose`. |
| Quartz fixture values hard-coded | PASS | one fixture may approach, other fails | may pass structure | Violet `BothHandsTrackSamePhysicalHandle` / `TrackingRespondsToSecondImpulseDirection`. |
| Correct graph plus extra source/map/config/asset | FAIL | not graded | FAIL | exact two-file manifest and task asset-registry inventory. |

## Fixed denominators

- L2: four gates per fixture, eight aggregate observations; a failed gate ends
  that fixture but never changes the declared denominator.
- L2I: exactly three checks on reference, empty, and every negative control.
- Harness damage is reported as `HARNESS-PRECONDITION`; submission-owned missing
  controls, wrong graph, wrong rig class, shortcut nodes, and hand errors remain
  graded failures and must not become no-verdict opt-outs.

## Requirements table

| # | Prompt requirement | Asserted | Enforcing check / exact named token | Gate skipped when | Residual |
|---|---|---|---|---|---|
| 1 | both hands follow the two grip points | fully | L2 `BothHandsTrackSamePhysicalHandle`; L2I `RigUsesIndependentHandControls` | only protected world/identity damage | frozen bars retain deliberately wide solver tolerance |
| 2 | handle remains the supplied simulated constrained body | fully | L2 `HandleMovesThroughRealConstraint` plus exact constrained components, body owner, simulation, validity, force | only protected handle/constraint damage | Chaos solver tolerances are measured, not serialized constants |
| 3 | live targets pass through the supplied AnimBP into the supplied Control Rig | fully | L2 actual `FAnimNode_ControlRig`/hierarchy telemetry; L2I `RuntimeControlRigComposesOverBasePose` | never for submission-owned wrong/missing graph; it is graded | none beyond engine's normal one-frame animation pipeline latency |
| 4 | solve both arm chains in the Control Rig | fully | L2I exact two reachable control routes and FABRIK effectors; L2 both live hand errors | never for submission-owned missing controls/units | FABRIK tuning itself is behavior-graded rather than property-pinned |
| 5 | preserve base pelvis and feet | fully | L2 `FeetAndPelvisPreserveBasePose`; L2I exact supplied base sequence feeding the rig | only non-finite protected mesh/base damage | frozen envelopes retain deliberately wide solver tolerance |
| 6 | work across two varying fixture fact sets | fully | Quartz and Violet fixture subclasses both run the same four gates; map cold readback requires distinct grip/impulse facts | one fixture's protected map actor missing/duplicated | no actor-name branch receives credit because live endpoints are sampled |
| 7 | no direct transform, Two Bone IK, or mirrored-hand substitute | fully | L2I `NoDirectTransformTwoBoneIKOrMirror`; asymmetric L2 endpoints independently sample both controls/hands | never | other engine arm solvers are also excluded by the exact accepted route |
| 8 | edit only the two supplied assets | fully | L1 accepted-file boundary plus L2I exact manifest and task asset registry inventory | never | none |

Every agent-visible requirement is joined to an exact behavior or structural
check. Numeric bars are frozen and fail-closed rather than silently skipped.

## Promotion evidence still required

Completed: shared dependency admission; clean Editor/Game builds; isolated
asset/map authoring and cold readback; five exact-one real-RHI admission legs;
the two-fixture final map; five reference and five empty legs per fixture;
frozen thresholds; exact two-asset reference harvest with byte-identical
baseline restore; canonical production reference L2/L2I PASS; and production
empty named L2/L2I failures. Remaining promotion work is owner play and official
refgate on the committed Git head.
